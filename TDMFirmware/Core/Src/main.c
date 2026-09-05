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
#include "app_x-cube-ai.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>
#include <TDM.h>
/* #include "nn_inference.h" -- 구 2단계(R->strain, L+strain->distance) 정적
 * 디커플러. 오늘 세션의 게이트+EMA MoE 모델(moe_inference)로 대체 — 파일은
 * 참고용으로 남겨두고 더 이상 호출하지 않는다. */
#include "moe_inference.h"
#include "LDC1614.h"
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
static char txbuf[128];  /* DMA TX buffer — must stay valid until HAL_UART_TxCpltCallback
                           * (96->128: moe_inference 출력 컬럼 5개 추가로 늘어남) */
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
  MX_X_CUBE_AI_Init();
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
  moe_inference_init();

  /* USART2 NVIC — needed so HAL_UART_TxCpltCallback fires after DMA TX */
  HAL_NVIC_SetPriority(USART2_IRQn, 1, 0);
  HAL_NVIC_EnableIRQ(USART2_IRQn);

  /* DWT cycle counter for latency measurement */
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
  DWT->CYCCNT = 0;
  DWT->CTRL  |= DWT_CTRL_CYCCNTENA_Msk;

  printf("--- System Boot ---\r\n");


  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

  MX_X_CUBE_AI_Process();
    /* USER CODE BEGIN 3 */


	  /* 부팅 후 첫 번째 유효 데이터에서 f0, L0 1회 출력 */
	  static uint8_t logged_f0 = 0;
	  if (!logged_f0 && g_SensorData.update_flag == 1 && g_SensorData.ldc_ch[0] > 0) {
		  logged_f0 = 1;
		  /* f_sensor = DATA * f_REF * FIN_DIV / (2^28 * FREF_DIV)
		   *          = DATA * 40MHz * 2 / 268435456 = DATA * 0.2981 Hz */
		  float f0_hz = (float)g_SensorData.ldc_ch[0] * 0.29802322f;
		  float L0_uH = 1e18f / (4.0f * 3.14159265f * 3.14159265f * f0_hz * f0_hz * 330.0f);
		  printf("# INIT: DATA0=%lu, f0=%.1fHz, L0=%.4fuH\r\n",
				 (unsigned long)g_SensorData.ldc_ch[0], f0_hz, L0_uH);
	  }

	  if(g_SensorData.update_flag == 1) {
		  g_SensorData.update_flag = 0;

		  float dL = 0.0f, dR = 0.0f, dV = 0.0f;

		  /* IDRIVE/STATUS 읽기: 10ms마다(매 출력주기), TIM7 잠시 정지해 I2C DMA 충돌 방지
		   * STATUS(0x18) 비트: bit9=ERR_ALE(진폭저하), bit10=ERR_AHE, bit11=ERR_WD, bit14=ERR_OR, bit15=ERR_UR */
		  static uint8_t  cached_idrive = 0;
		  static uint16_t cached_status = 0;
		  HAL_TIM_Base_Stop_IT(&htim7);
		  cached_idrive = LDC1614_ReadIDRIVE();
		  cached_status = LDC1614_ReadSTATUS();
		  HAL_TIM_Base_Start_IT(&htim7);

		  if (TDM_Get_Sensor_pct(&dL, &dR, &dV)) {
			  uint32_t t0 = DWT->CYCCNT;
			  MoeOut ai = moe_inference_run(dL, dR);
			  uint32_t cyc = DWT->CYCCNT - t0;

			  if (!uart_tx_busy) {
				  float latency_us = (float)cyc / 170.0f;
				  /* 출력 컬럼: dL_pct, dR_pct, dV_pct, IDRIVE, STATUS,
				   *           strain_pct, value(mode==0:distance_mm / mode==1:force_N),
				   *           mode(0=근접,1=압력), gate_proba, latency_us
				   *   IDRIVE : 0=Rp높음(Q양호)  31=Rp낮음(한계)
				   *   STATUS : 0x18 원본값. Python: err_ale=(s>>9)&1, err_wd=(s>>11)&1 */
				  int len = snprintf(txbuf, sizeof(txbuf),
						  "%.4f,%.4f,%.4f,%u,%u,%.3f,%.3f,%u,%.3f,%.2f\r\n",
						  (double)dL, (double)dR, (double)dV,
						  (unsigned int)cached_idrive,
						  (unsigned int)cached_status,
						  (double)ai.strain_pct, (double)ai.value,
						  (unsigned int)ai.mode, (double)ai.gate_proba,
						  (double)latency_us
						  );
				  uart_tx_busy = 1;
				  if (HAL_UART_Transmit_DMA(&huart2, (uint8_t*)txbuf, (uint16_t)len) != HAL_OK) {
					  uart_tx_busy = 0;   /* DMA 시작 실패 시 플래그 즉시 해제 */
				  }
			  }
		  }
	  }




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
