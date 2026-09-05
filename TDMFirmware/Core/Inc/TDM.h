/*
 * TDM.h
 *
 *  Created on: Jan 14, 2026
 *      Author: Korea University
 */

#ifndef TDM_H_
#define TDM_H_

#include "main.h"
#include <stdbool.h>
#include <stdio.h>
#include "gpio.h"


/* --- Hardware & Tuning Constants --- */
#define ACTIVE_SENSOR_COUNT  1			// 센서 채널 개수
#define TDM_PERIOD_TIME_US		1000	// TDM 주기 시간	 1000	/2000
#define TENG_MEASURE_TIME_US    150  	 	// TENG 측정 시간 20	/100
#define R_DC_MEASURE_TIME_US    150  	// 저항 측정 시간 6			/100
#define TDM_PRINT_EVERY_N       2.
// N × 1ms = 출력 주기 (10 → 100Hz, 5 → 200Hz, 2 → 500Hz)
// baud 460800 기준 한 줄(~60byte) 전송에 ~1.3ms 걸리므로 N=1(1kHz)은 우선순위
// 큐잉(uart_tx_busy)에 걸려 일부 샘플이 누락될 수 있다 — N=2가 안전 마진 있는 상한.
//#define ADC_BURST_SIZE 10				// ADC 버스트 개수

/* --- Data Structure for Complete Sensor Packet --- */
typedef struct {
    uint32_t ldc_ch[ACTIVE_SENSOR_COUNT];     // LDC Inductance Data (28-bit)
    uint16_t teng_adc[ACTIVE_SENSOR_COUNT];      // TENG Voltage ADC Raw
    uint16_t r_dc_adc[ACTIVE_SENSOR_COUNT];      // Resistance ADC Raw
    uint8_t  update_flag;   // 1 = New Data Ready
    uint8_t  ldc_err;       // 1 = LDC ERR_ALW/ERR_ZC 발생 (Q 부족, 마지막 유효값 홀드 중)
} SensorData_t;

/* TDM 상태 정의 */
typedef enum {
    TDM_STATE_IDLE,
    TDM_STATE_LDC_MEASURE,  // I2C DMA is running
    TDM_STATE_TENG_MEASURE, // MUX switched to TENG
    TDM_STATE_R_MEASURE,    // MUX switched to R
    TDM_STATE_COMPLETE      // Cycle Done
} TDM_State_t;

/* --- External Globals --- */
extern SensorData_t g_SensorData;
extern volatile bool flag_i2c_done;
extern volatile bool flag_adc_seq_done;
extern volatile bool flag_LDC_Ready;


/* --- OPAMP1 PGA 게인 전환 (STM32G4 규격: 비활성화 상태에서만 PGGAIN 변경 가능) ---
 * PGGAIN 비트 위치: CSR [18:14] = 0x0007C000UL (OPAMP_CSR_PGGAIN_x 매크로 사용)
 * OPAMPEN 비트: CSR [0] = OPAMP_CSR_OPAMPxEN_Msk */
#define OPAMP1_PGGAIN_MASK  (OPAMP_CSR_PGGAIN_0|OPAMP_CSR_PGGAIN_1|OPAMP_CSR_PGGAIN_2|OPAMP_CSR_PGGAIN_3|OPAMP_CSR_PGGAIN_4)

static inline void OPAMP1_Switch_Gain(uint32_t gain_val) {
    OPAMP1->CSR &= ~OPAMP_CSR_OPAMPxEN_Msk;                        // 비활성화
    OPAMP1->CSR  = (OPAMP1->CSR & ~OPAMP1_PGGAIN_MASK) | gain_val; // 게인 변경
    OPAMP1->CSR |=  OPAMP_CSR_OPAMPxEN_Msk;                        // 재활성화
    for (volatile uint32_t _d = 0; _d < 180; _d++) __NOP();        // ~5µs settling @ 170MHz
}

/* --- Function Prototypes --- */
void TDM_Init(void);
void TDM_Handle_GPIO_EXTI(void);
void TDM_Handle_Timer_Main_ISR(void);
void TDM_Handle_Timer_ADC_ISR(void);
void TDM_Handle_I2C_RxCplt(void);       // I2C DMA 완료 시 호출
void TDM_Handle_ADC_Cplt(void);         // ADC DMA 완료 시
void TDM_Handle_I2C_Error(void);



void TDM_Print_Calibrated_Data4(void);
void TDM_Print_Calibrated_Data3(void);
void TDM_Print_Filter_Comparison(void);
int  TDM_Get_Sensor_pct(float *dL_pct, float *dR_pct, float *dV_pct);

uint16_t IIR_Filter(float *prev, uint32_t new_val); //+추가

#endif /* TDM_H_ */
