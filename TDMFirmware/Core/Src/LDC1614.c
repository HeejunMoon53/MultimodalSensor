/*
 * LDC1614.c
 *
 *  Created on: Oct 22, 2025
 *      Author: Heejun Moon
 */


#include "LDC1614.h"
#include "main.h"
#include <stdint.h>
#include "usart.h"
#include "TDM.h"

extern I2C_HandleTypeDef hi2c2;

uint8_t ldc_dma_buffer[ACTIVE_SENSOR_COUNT*4];


/*I2C Address & GPIO Pins*/

uint8_t LDC2 =2;
#define LDC2_ADDR  (0x2A << 1)
#define LDC2_SD_GPIO_PORT GPIOA
#define LDC2_SD_PIN       GPIO_PIN_10
#define LDC2_INT_GPIO_PORT GPIOA
#define LDC2_INT_PIN       GPIO_PIN_11



/*LDC Setting Functions*/

void LDC1614_WriteReg(uint8_t LDC, uint8_t reg, uint16_t data) {
    uint8_t buf[3];
    if(LDC==2){
    	buf[0] = reg;
    	buf[1] = (data >> 8) & 0xFF;
    	buf[2] = data & 0xFF;
    	HAL_I2C_Master_Transmit(&hi2c2, LDC2_ADDR, buf, 3, HAL_MAX_DELAY);
    }
}

uint16_t LDC1614_ReadReg(uint8_t LDC, uint8_t reg) {
    uint8_t buf[2];

    if(LDC==2){
    	HAL_I2C_Master_Transmit(&hi2c2, LDC2_ADDR, &reg, 1, HAL_MAX_DELAY);
    	HAL_I2C_Master_Receive(&hi2c2, LDC2_ADDR, buf, 2, HAL_MAX_DELAY);
    	return (buf[0] << 8) | buf[1];
    }
}

uint32_t LDC1614_ReadData(uint8_t LDC, uint8_t Ch) {
	uint8_t reg_msb, reg_lsb;
	switch(Ch){
	case 0 : reg_msb = 0x00; reg_lsb = 0x01; break;
	case 1 : reg_msb = 0x02; reg_lsb = 0x03; break;
	case 2 : reg_msb = 0x04; reg_lsb = 0x05; break;
	case 3 : reg_msb = 0x06; reg_lsb = 0x07; break;
	default : return 0;
	}

	uint16_t msb_data, lsb_data;

	if(LDC==2){
		msb_data = LDC1614_ReadReg(LDC2, reg_msb);
		lsb_data = LDC1614_ReadReg(LDC2, reg_lsb);
	}

	return ( ((uint32_t)msb_data << 16) | lsb_data  & 0x0FFFFFFF );
}


void LDC1614_SD_Activate(uint8_t LDC) {
	if (LDC==2) HAL_GPIO_WritePin(LDC2_SD_GPIO_PORT, LDC2_SD_PIN, GPIO_PIN_RESET);
}

void LDC1614_SD_Shutdown(uint8_t LDC) {
	if (LDC==2) HAL_GPIO_WritePin(LDC2_SD_GPIO_PORT, LDC2_SD_PIN, GPIO_PIN_SET);
}


void LDC1614_SetMultiChannel(uint8_t LDC, uint8_t num_Ch) {
    uint16_t mux_val;
    mux_val = LDC1614_ReadReg(LDC, 0x1B);
    mux_val &= ~((1u << 15) | (0x3 << 13));

    switch(num_Ch){
    	case 1 : break;
    	case 2 : mux_val |= (0b100 << 13); break;
    	case 3 : mux_val |= (0b101 << 13); break;
    	case 4 : mux_val |= (0b110 << 13); break;
    	default : mux_val |= (0b110 << 13); break;
    }
    LDC1614_WriteReg(LDC, 0x1B, mux_val);
}


void LDC1614_Init(void) {
	LDC1614_SD_Activate(LDC2);
	HAL_Delay(5);

	//LDC Initialization
	LDC1614_WriteReg(LDC2, 0x08, 0x0250); // RCOUNT_CH0 0x0250
	LDC1614_WriteReg(LDC2, 0x09, 0x04D6); // RCOUNT_CH1
	LDC1614_WriteReg(LDC2, 0x0A, 0x04D6); // RCOUNT_CH2
	LDC1614_WriteReg(LDC2, 0x0B, 0x04D6); // RCOUNT_CH3
	LDC1614_WriteReg(LDC2, 0x10, 0x0001); // SETTLECOUNT_CH0: auto-amp 수렴 여유 (0x0001)
	LDC1614_WriteReg(LDC2, 0x11, 0x000A); // SETTLECOUNT_CH1
	LDC1614_WriteReg(LDC2, 0x12, 0x000A); // SETTLECOUNT_CH2
	LDC1614_WriteReg(LDC2, 0x13, 0x000A); // SETTLECOUNT_CH3
	LDC1614_WriteReg(LDC2, 0x14, 0x2001); // CLOCK_DIVIDERS_CH0 (FIN_DIV=1, FREF_DIV=2) 0x2001
	LDC1614_WriteReg(LDC2, 0x15, 0x1002); // CLOCK_DIVIDERS_CH1 (FIN_DIV=1, FREF_DIV=2)
	LDC1614_WriteReg(LDC2, 0x16, 0x1002); // CLOCK_DIVIDERS_CH2 (FIN_DIV=1, FREF_DIV=2)
	LDC1614_WriteReg(LDC2, 0x17, 0x1002); // CLOCK_DIVIDERS_CH3 (FIN_DIV=1, FREF_DIV=2)
	LDC1614_WriteReg(LDC2, 0x19, 0x0001); // ERROR_CONFIG: DRDY_2INT only (AL_ERR2OUT 비활성 — 우리 센서 Rp₀<Rp_min이라 항상 세트됨)
	LDC1614_WriteReg(LDC2, 0x1B, 0x020C); // MUX_CONFIG (enable CH0 continuous; deglitch)0x020C
	LDC1614_WriteReg(LDC2, 0x1E, 0xF800); // DRIVE_CURRENT_CH0: IDRIVE=31 고정 (AUTO_AMP_DIS=1이라 자동조절 없음)
	LDC1614_WriteReg(LDC2, 0x1F, 0x9000); // DRIVE_CURRENT_CH1
	LDC1614_WriteReg(LDC2, 0x20, 0x9000); // DRIVE_CURRENT_CH2
	LDC1614_WriteReg(LDC2, 0x21, 0x9000); // DRIVE_CURRENT_CH3
	/* CONFIG 0x1401: bit12=RP_OVERRIDE_EN, bit10=AUTO_AMP_DIS(고정전류모드), bit0=INTB_DIS
	 * ※ AUTO_AMP 켜려면 0x0041 (bit6=HIGH_CURRENT_DRV) — AUTO_AMP_DIS=0 필요조건 확인 후 사용 */
	LDC1614_WriteReg(LDC2, 0x1A, 0x1401);

	LDC1614_SetMultiChannel(LDC2, ACTIVE_SENSOR_COUNT);
}



/*Data Processing Functions*/
/*
void LDC1614_StreamData(void)
{
    char msg[128];
    uint32_t d2[4];


    for(int i=0; i<4; i++) d2[i] = LDC1614_ReadData(LDC2, i);

    sprintf(msg, "%lu,%lu,%lu,%lu\r\n",
            d2[0], d2[1], d2[2], d2[3]);

    UART_SendString(msg);
}



void UART_SendString(char *str)
{
    HAL_UART_Transmit(&huart2, (uint8_t *)str, strlen(str), HAL_MAX_DELAY);
}
*/


////////////////DMA 처리 함수//////////////////////

HAL_StatusTypeDef LDC1614_Start_DMA_Read_MSB(int ch) {
	uint8_t msb_reg;
	switch(ch){
	case 0 : msb_reg = 0x00; break;
	case 1 : msb_reg = 0x02; break;
	case 2 : msb_reg = 0x04; break;
	case 3 : msb_reg = 0x06; break;
	default : return 0;
	}
	return HAL_I2C_Mem_Read_DMA(&hi2c2, LDC2_ADDR, msb_reg, I2C_MEMADD_SIZE_8BIT, &ldc_dma_buffer[ch*4], 2);
}

HAL_StatusTypeDef LDC1614_Start_DMA_Read_LSB(int ch) {
	uint8_t lsb_reg;
	switch(ch){
	case 0 : lsb_reg = 0x01; break;
	case 1 : lsb_reg = 0x03; break;
	case 2 : lsb_reg = 0x05; break;
	case 3 : lsb_reg = 0x07; break;
	default : return 0;
	}
	return HAL_I2C_Mem_Read_DMA(&hi2c2, LDC2_ADDR, lsb_reg, I2C_MEMADD_SIZE_8BIT, &ldc_dma_buffer[ch*4+2], 2);
}



void LDC1614_Parse_DMA_Data(void) {
	for(int i=0; i<ACTIVE_SENSOR_COUNT; i++) {
		//[MSB_High, MSB_Low, LSB_High, LSB_Low] (총 4바이트)
		int idx = i * 4;

		uint16_t reg_msb = (ldc_dma_buffer[idx] << 8) | ldc_dma_buffer[idx+1];
		uint16_t reg_lsb = (ldc_dma_buffer[idx+2] << 8) | ldc_dma_buffer[idx+3];

		/* DATA_CHn_MSB 에러 비트 검사 (datasheet Table 8.6.1.1)
		 *   bit15 = ERR_UR  : 주파수 under-range
		 *   bit14 = ERR_OR  : 주파수 over-range
		 *   bit13 = ERR_WD  : Watchdog timeout (발진 정지)
		 *   bit12 = ERR_AE  : 진폭 에러 (AL_ERR2OUT 필요 — 우리 센서는 항상 세트되므로 비활성)
		 * → 에러 시 ldc_ch[i] 갱신 않고 마지막 유효값 유지 (hold-last-valid) */
		if (reg_msb & 0xE000) {  // bits[15:13]: UR/OR/WD 만 체크 (bit12 ERR_AE 제외)
			g_SensorData.ldc_err = (uint8_t)((reg_msb >> 12) & 0x0F); // 에러 종류: b3=UR b2=OR b1=WD b0=AE
			/* ldc_ch[i] 갱신 안 함 → 이전 값 유지 */
		} else {
			uint32_t val = ((uint32_t)(reg_msb & 0x0FFF) << 16) | reg_lsb;
			if (val > 0) {
				g_SensorData.ldc_ch[i] = val;
				g_SensorData.ldc_err   = 0;
			}
		}
	}
}


/* auto-amplitude 모드에서 LDC가 수렴시킨 IDRIVE 값(0~31)을 읽어 반환한다.
 * IDRIVE 높음 → Rp 낮음(Q 저하) → 오버플로우 근접
 * Rp_est(kΩ) ≈ 1500 / I_drive(µA)  (V_target ≈ 1.5V 기준) */
uint8_t LDC1614_ReadIDRIVE(void) {
    uint16_t reg = LDC1614_ReadReg(LDC2, 0x1E);
    return (uint8_t)((reg >> 11) & 0x1F);  // bits[15:11] = IDRIVE
}

/* STATUS 레지스터(0x18) 읽기 — 읽으면 자동 클리어
 * 주요 에러 비트:
 *   bit 9  ERR_ALE : 진폭 < 1.2V (Q 저하, Rp 부족 → 우리 overflow 원인)
 *   bit 10 ERR_AHE : 진폭 > 1.8V (IDRIVE 과다)
 *   bit 11 ERR_WD  : Watchdog timeout (발진 완전 정지)
 *   bit 14 ERR_OR  : 주파수 over-range
 *   bit 15 ERR_UR  : 주파수 under-range
 * Python 파싱: err_ale = (status >> 9) & 1 */
uint16_t LDC1614_ReadSTATUS(void) {
    return LDC1614_ReadReg(LDC2, 0x18);
}


void LDC1614_Kickstart(void) {
    printf("--- LDC Kickstart Sequence ---\r\n");

    // INTB 핀이 Low(0V)인 동안은 계속 읽어서 High로 띄워라!
    int retry_count = 100; // 충분히 많이
    uint8_t dummy_status;

    while (HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_11) == GPIO_PIN_RESET && retry_count > 0)
    {
        // Status 레지스터 읽기 (딜레이 없이!)
        // I2C 통신 시간 자체가 딜레이 역할을 함
        HAL_I2C_Mem_Read(&hi2c2, (0x2A<<1), 0x18, I2C_MEMADD_SIZE_8BIT, &dummy_status, 1, 2);
        retry_count--;
    }

    if (retry_count == 0) {
        printf("Error: LDC INTB Pin Stuck Low!\r\n");
        // 필요시 에러 처리 (예: 무한루프, 리셋)
    } else {
        printf("LDC INTB Pin Released (High). Ready.\r\n");
    }
}

