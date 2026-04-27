/*
 * TDM.c
 *
 *  Created on: Jan 5, 2026
 *      Author: Korea University
 */

#include "TDM.h"
#include "LDC1614.h"
#include "usart.h"


/* --- Hardware Handles --- */
extern TIM_HandleTypeDef htim6; // Time base for switching (1us tick) - TENG,R
extern TIM_HandleTypeDef htim7; // Time base for switching (1us tick) - TDM Period
extern ADC_HandleTypeDef hadc1; // TENG & R Measurement
extern ADC_HandleTypeDef hadc2;
extern ADC_HandleTypeDef hadc3;
extern ADC_HandleTypeDef hadc5;
extern I2C_HandleTypeDef hi2c2; // LDC Communication


/* --- Private variables --- */

/* ADG734 제어 핀 정의 */
#define SW_PORT		GPIOB
#define SW1_PIN     GPIO_PIN_2   // S1A: LDCIN0_A / S1B: ADCIN0_A
#define SW2_PIN     GPIO_PIN_10   // S2A: LDCIN0_B / S2B: ADCIN0_B
#define SW3_PIN     GPIO_PIN_11  // NO: R0_VD (저항 측정용 전압 주입)
#define SW4_PIN     GPIO_PIN_15  // NO: ADCIN0_B to GND (그라운드 고정)

/* 센서 데이터 변수 정의*/
volatile TDM_State_t tdm_state = TDM_STATE_IDLE;
SensorData_t g_SensorData;
uint32_t raw_adc1, raw_adc2, raw_adc3, raw_adc5;
volatile uint8_t i2c_read_step = 0; // I2C 레지스터 MSB/LSB 스텝

/* Flags for synchronization */
volatile bool flag_i2c_done = false;
volatile bool flag_adc_seq_done = false;
volatile bool flag_LDC_Ready = false;


///////////////////////////////////////////////////////////테스트용/////////////////////////////////////////////////////////////
/* --- 필터 비교용 변수 선언 --- */
// 1. 미디언 필터 버퍼 및 인덱스
volatile uint16_t teng_med_buf[3] = {0};
volatile uint16_t r_med_buf[3] = {0};
volatile uint8_t med_idx_teng = 0;
volatile uint8_t med_idx_r = 0;

// 2. IIR 필터용 과거 상태(Prev) 변수 독립 선언
float teng_iir_only_prev = 0.0f;
float teng_hybrid_prev = 0.0f;
float r_iir_only_prev = 0.0f;
float r_hybrid_prev = 0.0f;

// 3. 출력 결과 저장용 변수
volatile uint16_t teng_raw, teng_med_only, teng_iir_only, teng_hybrid;
volatile uint16_t r_raw, r_med_only, r_iir_only, r_hybrid;


/* 필터 알고리즘 함수 선언 */
uint16_t Get_Median_3(uint16_t a, uint16_t b, uint16_t c) {
    if (a > b) { uint16_t tmp = a; a = b; b = tmp; }
    if (b > c) { uint16_t tmp = b; b = c; c = tmp; }
    if (a > b) { uint16_t tmp = a; a = b; b = tmp; }
    return b;
}

uint16_t IIR_Filter_Adv(float *prev, uint32_t new_val, float alpha){
    if (*prev == 0.0f) {
        *prev = (float)new_val;
    } else {
        *prev = *prev + alpha * ((float)new_val - *prev);
    }
    return (uint16_t)(*prev);
}



///////////////////////////////////////////////////////////테스트용/////////////////////////////////////////////////////////////




/* Private function prototypes */

/*     스위칭 제어 함수     */
static inline void Set_MUX_LDC(void) {//(LDC 연결), (R0/GND 분리)
    HAL_GPIO_WritePin(SW_PORT, SW1_PIN | SW2_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(SW_PORT, SW3_PIN | SW4_PIN, GPIO_PIN_RESET);
}

static inline void Set_MUX_TENG(void) {//(ADC 연결), (R0/GND 분리)
    HAL_GPIO_WritePin(SW_PORT, SW1_PIN | SW2_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(SW_PORT, SW3_PIN | SW4_PIN, GPIO_PIN_RESET);
}

static inline void Set_MUX_R(void) {//(ADC 연결), (R0/GND 연결)
    HAL_GPIO_WritePin(SW_PORT, SW1_PIN | SW2_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(SW_PORT, SW3_PIN | SW4_PIN, GPIO_PIN_SET);
}

/*		헬퍼 함수		*/
static inline void Start_Active_ADCs(void) {
    if (ACTIVE_SENSOR_COUNT >= 1) HAL_ADC_Start_DMA(&hadc1, &raw_adc1, 1);
    if (ACTIVE_SENSOR_COUNT >= 2) HAL_ADC_Start_DMA(&hadc2, &raw_adc2, 1);
    if (ACTIVE_SENSOR_COUNT >= 3) HAL_ADC_Start_DMA(&hadc3, &raw_adc3, 1);
    if (ACTIVE_SENSOR_COUNT >= 4) HAL_ADC_Start_DMA(&hadc5, &raw_adc5, 1);
}

static inline void Stop_Active_ADCs(void) {
    if (ACTIVE_SENSOR_COUNT >= 1) HAL_ADC_Stop_DMA(&hadc1);
    if (ACTIVE_SENSOR_COUNT >= 2) HAL_ADC_Stop_DMA(&hadc2);
    if (ACTIVE_SENSOR_COUNT >= 3) HAL_ADC_Stop_DMA(&hadc3);
    if (ACTIVE_SENSOR_COUNT >= 4) HAL_ADC_Stop_DMA(&hadc5);
}


/* Core Logic -----------------------------------------------*/

void TDM_Init(void) {
    Set_MUX_LDC();
    LDC1614_Init();
    __HAL_TIM_SET_COUNTER(&htim7, 0);
    __HAL_TIM_SET_AUTORELOAD(&htim7, TDM_PERIOD_TIME_US);
    HAL_TIM_Base_Start_IT(&htim7);
    printf(" TDM_Init\r\n");
}

void TDM_Handle_GPIO_EXTI(void) {
	flag_LDC_Ready = 1;
}

void TDM_Handle_Timer_Main_ISR(void){
	if(tdm_state != TDM_STATE_IDLE) return;

	// 1. 상태 및 플래그 초기화
	flag_i2c_done = false;
	flag_adc_seq_done = false;
	i2c_read_step = 0; //

	// 2. Parallel Task 1: I2C DMA 시작 (약 200us 소요) -ldc_dma_buffer에 저장
	LDC1614_Start_DMA_Read_MSB(0);

	// 3. Parallel Task 2: 모드 변경, ADC DMA
	Set_MUX_TENG();
	__HAL_TIM_SET_COUNTER(&htim6, 0);
	__HAL_TIM_SET_AUTORELOAD(&htim6, TENG_MEASURE_TIME_US);
	HAL_TIM_Base_Start_IT(&htim6);
	tdm_state = TDM_STATE_TENG_MEASURE;
	Start_Active_ADCs();

}


void TDM_Handle_Timer_ADC_ISR(void) {
	//I. TENG 측정 완료 시점 (20us 경과)
	if (tdm_state == TDM_STATE_TENG_MEASURE) {
//		if(ACTIVE_SENSOR_COUNT >= 1) g_SensorData.teng_adc[0] = (uint16_t)raw_adc1;


		//////////테스트/////////
		if(ACTIVE_SENSOR_COUNT >= 1){
		teng_raw = (uint16_t)raw_adc1;
		// 1) Median Only 산출
//		teng_med_buf[med_idx_teng] = teng_raw;
//		teng_med_only = Get_Median_3(teng_med_buf[0], teng_med_buf[1], teng_med_buf[2]);
//		med_idx_teng = (med_idx_teng + 1) % 3;
		// 2) IIR Only 산출 (알파: 0.15)
		teng_iir_only = IIR_Filter_Adv(&teng_iir_only_prev, teng_raw, 0.2f);
//		// 3) Hybrid 산출 (미디언 결과에 IIR 적용)
//		teng_hybrid = IIR_Filter_Adv(&teng_hybrid_prev, teng_med_only, 0.2f);
		// 실제 적용은 하이브리드 값으로 설정
		g_SensorData.teng_adc[0] = teng_iir_only;
		}
		//////////테스트/////////


		if(ACTIVE_SENSOR_COUNT >= 2) g_SensorData.teng_adc[1] = (uint16_t)raw_adc2;
		if(ACTIVE_SENSOR_COUNT >= 3) g_SensorData.teng_adc[2] = (uint16_t)raw_adc3;
		if(ACTIVE_SENSOR_COUNT >= 4) g_SensorData.teng_adc[3] = (uint16_t)raw_adc5;
		Stop_Active_ADCs();

		//모드 변경: TENG -> R
		Set_MUX_R();
		HAL_TIM_Base_Stop_IT(&htim6);
		__HAL_TIM_SET_COUNTER(&htim6, 0);
		__HAL_TIM_SET_AUTORELOAD(&htim6, R_DC_MEASURE_TIME_US);
		HAL_TIM_Base_Start_IT(&htim6);
		tdm_state = TDM_STATE_R_MEASURE;
		Start_Active_ADCs();
	}

	//II. R 측정 완료 시점 (6us 경과)
	else if (tdm_state == TDM_STATE_R_MEASURE) {
		HAL_TIM_Base_Stop_IT(&htim6);

//		if(ACTIVE_SENSOR_COUNT >= 1) g_SensorData.r_dc_adc[0] = (uint16_t)raw_adc1;


		//////////테스트/////////
		if(ACTIVE_SENSOR_COUNT >= 1){
			r_raw = (uint16_t)raw_adc1;
			// 1) Median Only 산출
//			r_med_buf[med_idx_r] = r_raw;
//			r_med_only = Get_Median_3(r_med_buf[0], r_med_buf[1], r_med_buf[2]);
//			med_idx_r = (med_idx_r + 1) % 3;
			// 2) IIR Only 산출 (알파: 0.15)
			r_iir_only = IIR_Filter_Adv(&r_iir_only_prev, r_raw, 0.02f);
			// 3) Hybrid 산출
//			r_hybrid = IIR_Filter_Adv(&r_hybrid_prev, r_med_only, 0.05f);
			// 실제 적용은 하이브리드 값으로 설정
			g_SensorData.r_dc_adc[0] = r_iir_only;
		}
		//////////테스트/////////


		if(ACTIVE_SENSOR_COUNT >= 2) g_SensorData.r_dc_adc[1] = (uint16_t)raw_adc2;
		if(ACTIVE_SENSOR_COUNT >= 3) g_SensorData.r_dc_adc[2] = (uint16_t)raw_adc3;
		if(ACTIVE_SENSOR_COUNT >= 4) g_SensorData.r_dc_adc[3] = (uint16_t)raw_adc5;
		Stop_Active_ADCs();
		flag_adc_seq_done = true;

		//모드 변경: R -> LDC
		Set_MUX_LDC();
		tdm_state = TDM_STATE_LDC_MEASURE;

		// 5. 전체 완료 확인 (I2C가 이미 끝났는지 확인)
		if (flag_i2c_done) {
			g_SensorData.update_flag = 1;
			tdm_state = TDM_STATE_IDLE;
		}
	}
}

void TDM_Handle_I2C_RxCplt(void) {
	i2c_read_step++;

	if (i2c_read_step >= (ACTIVE_SENSOR_COUNT * 2)) {
		LDC1614_Parse_DMA_Data();
		flag_i2c_done = true;
		if (flag_adc_seq_done) {
			g_SensorData.update_flag = 1;
			tdm_state = TDM_STATE_IDLE;
		}
		return;
	}


	int ch = i2c_read_step / 2;
	int is_lsb = i2c_read_step % 2;

	if (is_lsb) {
		LDC1614_Start_DMA_Read_LSB(ch);
	} else {
		LDC1614_Start_DMA_Read_MSB(ch);
	}
}






/* 테스트 출력용 함수들 -----------------------------------------------*/


void TDM_Print_Calibrated_Data3(void) {
	static uint32_t base_ldc = 0;
	static uint32_t base_teng = 0; // TENG 기준값 추가
	static uint32_t base_r = 0;
	static uint8_t is_calibrated = 0;

	// 1. 기준값 잡기 (최초 1회)
	if (!is_calibrated) {
		// 3개의 센서 모두 0 이상의 유효한 값이 들어올 때 캘리브레이션
		if (g_SensorData.ldc_ch[0] > 0 && g_SensorData.teng_adc[0] > 0 && g_SensorData.r_dc_adc[0] > 0) {
			base_ldc = g_SensorData.ldc_ch[0];
			base_teng = g_SensorData.teng_adc[0]; // TENG Base 저장
			base_r   = g_SensorData.r_dc_adc[0];
			is_calibrated = 1;
			printf("CALIBRATED: Base LDC=%lu, Base TENG=%u, Base R=%u\r\n",
                    base_ldc, (unsigned int)base_teng, (unsigned int)base_r);
		}
		return;
	}

	// 2. 정밀 계산 (소수점 4자리 비율, 기준 100.0000%)

	/* [LDC 인덕턴스 변화율 계산]
	 * LDC Data ∝ f ∝ 1/sqrt(L)
	 * L_current / L_base = (DATA_base / DATA_current)^2
	 */
	// 먼저 Base / Current 비율을 구함 (스케일링 100,000 곱함)
	uint64_t ldc_ratio_scaled = ((uint64_t)base_ldc * 100000) / g_SensorData.ldc_ch[0];
	// 제곱하여 인덕턴스 비율 계산 (10^10 / 10^4 = 1,000,000 -> 100.0000% 스케일)
	uint64_t ldc_inductance_ratio = (ldc_ratio_scaled * ldc_ratio_scaled) / 10000;

	uint32_t ldc_int = ldc_inductance_ratio / 10000;
	uint32_t ldc_dec = ldc_inductance_ratio % 10000;


	/* [TENG 전압 변화율 계산] */
	uint64_t teng_ratio = ((uint64_t)g_SensorData.teng_adc[0] * 1000000) / base_teng;
	uint32_t teng_int = teng_ratio / 10000;
	uint32_t teng_dec = teng_ratio % 10000;


	/* [저항(R) 변화율 계산] */
	uint64_t r_ratio = ((uint64_t)g_SensorData.r_dc_adc[0] * 1000000) / base_r;
	uint32_t r_int = r_ratio / 10000;
	uint32_t r_dec = r_ratio % 10000;

	// 3. 출력 (순서: LDC(%), TENG(%), R(%))
	printf("%lu.%04lu, %lu.%04lu, %lu.%04lu\r\n",
			ldc_int, ldc_dec,
			teng_int, teng_dec,
			r_int, r_dec);
}

void TDM_Print_Filter_Comparison(void) {
    // 순서: TENG (Raw, Median, IIR, Hybrid), R (Raw, Median, IIR, Hybrid)
//    printf("%u, %u, %u, %u, %u, %u, %u, %u, %u\r\n",
//           teng_raw, teng_med_only, teng_iir_only, teng_hybrid,
//           r_raw, r_med_only, r_iir_only, r_hybrid, g_SensorData.ldc_ch[0]);
    printf("%u, %u, %u, %u, %u\r\n",
           g_SensorData.ldc_ch[0], g_SensorData.r_dc_adc[0], g_SensorData.teng_adc[0],r_raw,teng_raw);
}
