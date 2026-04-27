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
#define TENG_MEASURE_TIME_US    100  	 	// TENG 측정 시간 20	/100
#define R_DC_MEASURE_TIME_US    100  	// 저항 측정 시간 6			/100
//#define ADC_BURST_SIZE 10				// ADC 버스트 개수

/* --- Data Structure for Complete Sensor Packet --- */
typedef struct {
    uint32_t ldc_ch[ACTIVE_SENSOR_COUNT];     // LDC Inductance Data (28-bit)
    uint16_t teng_adc[ACTIVE_SENSOR_COUNT];      // TENG Voltage ADC Raw
    uint16_t r_dc_adc[ACTIVE_SENSOR_COUNT];      // Resistance ADC Raw
    uint8_t  update_flag;   // 1 = New Data Ready
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

uint16_t IIR_Filter(float *prev, uint32_t new_val); //+추가

#endif /* TDM_H_ */
