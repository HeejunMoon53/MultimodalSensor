/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "adc.h"
#include "dma.h"
#include "i2c.h"
#include "opamp.h"
#include "spi.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>
#include <TDM.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
volatile uint8_t uart_tx_busy = 0;
extern volatile TDM_State_t tdm_state;

uint32_t idle_counter = 0;//테스트용 삭제
uint32_t last_tick = 0;//테스트용 삭제

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_ADC3_Init();
  MX_USART1_UART_Init();
  MX_USART2_UART_Init();
  MX_ADC5_Init();
  MX_OPAMP1_Init();
  MX_OPAMP3_Init();
  MX_OPAMP5_Init();
  MX_ADC1_Init();
  MX_ADC2_Init();
  MX_ADC4_Init();
  MX_I2C2_Init();
  MX_OPAMP2_Init();
  MX_SPI1_Init();
  MX_TIM3_Init();
  MX_TIM6_Init();
  MX_TIM7_Init();
  /* USER CODE BEGIN 2 */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0, GPIO_PIN_SET); //전원 LED


  HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
  HAL_ADCEx_Calibration_Start(&hadc2, ADC_SINGLE_ENDED);
  HAL_ADCEx_Calibration_Start(&hadc3, ADC_SINGLE_ENDED);
  HAL_ADCEx_Calibration_Start(&hadc5, ADC_SINGLE_ENDED);
  HAL_OPAMP_SelfCalibrate(&hopamp1);
  HAL_OPAMP_SelfCalibrate(&hopamp2);
  HAL_OPAMP_SelfCalibrate(&hopamp3);
  HAL_OPAMP_SelfCalibrate(&hopamp5);
  HAL_OPAMP_Start(&hopamp1);
  HAL_OPAMP_Start(&hopamp2);
  HAL_OPAMP_Start(&hopamp3);
  HAL_OPAMP_Start(&hopamp5);

  TDM_Init();


  printf("--- System Boot ---\r\n");


  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */


	  if(g_SensorData.update_flag == 1 && (uart_tx_busy == 0)){
		  g_SensorData.update_flag = 0;
		  uart_tx_busy = 1;
//		  TDM_Print_Calibrated_Data();
//		  TDM_Print_Calibrated_Data3();
//		  TDM_Print_Calibrated_Data4();
		  TDM_Print_Filter_Comparison();

		  uart_tx_busy = 0;
	  }
	  HAL_Delay(10);




	  //메인 코어 점유율 검사////////////////////////////////////////
//	  idle_counter++;
//	  if (HAL_GetTick() - last_tick >= 1000) {
//		  last_tick = HAL_GetTick();
//		  printf("CPU Idle Count: %lu\r\n", idle_counter);
//		  idle_counter = 0;
//	  }
//	  if (g_SensorData.update_flag == 1) {
//		  g_SensorData.update_flag = 0;
//	  }
	  ////////////////////////////////////////////////////////////



  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1_BOOST);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = RCC_PLLM_DIV2;
  RCC_OscInitStruct.PLL.PLLN = 85;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */


int _write(int file, char *ptr, int len) {
    HAL_UART_Transmit(&huart2, (uint8_t *)ptr, len, 10);
//    HAL_UART_Transmit_DMA(&huart2, (uint8_t *)ptr, len);
    return len;
}



/* 1. LDC 인터럽트 (PA11 -> EXTI15_10) */
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin) {
    if (GPIO_Pin == GPIO_PIN_11) {
//        TDM_Start_Sequence_From_ISR();
    }
}

/* 2. 타이머 인터럽트 (TIM6) */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim) {
	if (htim->Instance == TIM6) {
//		TDM_Handle_Timer_ISR();
		TDM_Handle_Timer_ADC_ISR();
	}
	else if (htim->Instance == TIM7) {
		TDM_Handle_Timer_Main_ISR();
	}
}

/* 3. I2C DMA 완료 인터럽트 */
void HAL_I2C_MemRxCpltCallback(I2C_HandleTypeDef *hi2c) {
    if (hi2c->Instance == I2C2) {
        TDM_Handle_I2C_RxCplt();
    }
}

// I2C 에러 처리 그냥 없애주는 함수
void HAL_I2C_ErrorCallback(I2C_HandleTypeDef *hi2c) {
	if (hi2c->Instance == I2C2) {
	        // 1. 에러가 났지만, TDM 로직이 멈추지 않게 하기 위해
	        //    마치 통신이 끝난 것처럼 처리해줍니다.

	        // 외부 변수 가져오기 (main.c 위에 선언 안 되어 있으면 extern 필요)
	        extern volatile bool flag_i2c_done;
	        extern volatile bool flag_adc_seq_done;
	        extern volatile TDM_State_t tdm_state;

	        flag_i2c_done = true; // "일단 온 걸로 치자" (강제 플래그 설정)

	        // 2. 만약 ADC 쪽이 이미 끝나서 기다리고 있었다면? -> 문 닫고 퇴근(IDLE) 시켜줌
	        if (flag_adc_seq_done) {
	            // 이번 데이터는 에러라서 신뢰할 수 없지만, 시스템이 멈추는 것보단 낫습니다.
	            // g_SensorData.update_flag = 1; (선택사항: 에러 데이터도 보낼 거면 주석 해제)

	            tdm_state = TDM_STATE_IDLE; // [핵심] 상태를 풀어줘서 다음 인터럽트를 받을 수 있게 함
	        }

	        // (선택) 디버깅용: LED를 살짝 깜빡여서 "아, 방금 에러 났었네"라고 알림
	        // HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_0);
	    }
}

/* 4. UART DMA 완료 인터럽트 */
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance == USART2) {
    uart_tx_busy = 0; // 전송 완료! 이제 다음 데이터 보낼 수 있음
  }
}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
