/*
 * LDC1614.h
 *
 *  Created on: Oct 1, 2025
 *      Author: USER
 */

#ifndef INC_LDC1614_H_
#define INC_LDC1614_H_

#include "main.h"
#include "gpio.h"
#include "TDM.h"

/*Function Prototype*/
void LDC1614_WriteReg(uint8_t LDC, uint8_t reg, uint16_t data);
uint16_t LDC1614_ReadReg(uint8_t LDC, uint8_t reg);
uint32_t LDC1614_ReadData(uint8_t LDC, uint8_t Ch);
void LDC1614_SD_Activate(uint8_t LDC);
void LDC1614_SD_Shutdown(uint8_t LDC);
void LDC1614_SetMultiChannel(uint8_t LDC, uint8_t num_Ch);
void LDC1614_Init(void);
void LDC1614_INT_Callback(uint8_t LDC);
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin);
HAL_StatusTypeDef LDC1614_Start_DMA_Read_MSB(int ch);	//
HAL_StatusTypeDef LDC1614_Start_DMA_Read_LSB(int ch);	//


#endif /* INC_LDC1614_H_ */


