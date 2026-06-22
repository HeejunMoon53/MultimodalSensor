/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
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

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "rft_sensor.h"
#include <stdio.h>
#include <string.h>
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
CAN_HandleTypeDef hcan;

UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */
RFT_Data_t ft;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_CAN_Init(void);
static void MX_USART2_UART_Init(void);
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
  MX_CAN_Init();
  MX_USART2_UART_Init();
  /* USER CODE BEGIN 2 */


  /* ── RFT 센서 초기화 ── */
  RFT_Init(&hcan);
  HAL_Delay(2000);          /* 센서 부팅 대기 */

  /* ════════════════════════════════════════════════════════════════
     Communication ID 복구 모드 (구 센서 ID 리셋 전용)
     사용법:
       1. 불량 센서만 버스에 연결 (정상 센서 분리)
       2. 아래 매크로를 1로 변경 후 빌드·플래시
       3. SerialPlot/터미널에서 UART 출력 확인
       4. "Reset OK" 확인 후 매크로 다시 0으로 복원하여 재빌드
  ════════════════════════════════════════════════════════════════ */
#define COMM_ID_CONFIG_MODE  1

#if COMM_ID_CONFIG_MODE
  {
      char msg[80];
      int  n;

      /* Step 1: 기본 RX=0x064 로 READ 시도 */
      RFT_CommID_t cid = RFT_ReadCommID();
      if (cid.valid) {
          n = snprintf(msg, sizeof(msg),
              "CommID: TX1=0x%03X TX2=0x%03X RX=0x%03X\r\n",
              cid.tx_id1, cid.tx_id2, cid.rx_id);
          HAL_UART_Transmit(&huart2, (uint8_t*)msg, (uint16_t)n, 100);

          if (cid.tx_id1 != 0x001U || cid.tx_id2 != 0x002U || cid.rx_id != 0x064U) {
              RFT_ResetCommID(0x064U);
              n = snprintf(msg, sizeof(msg), "Reset to defaults OK\r\n");
          } else {
              n = snprintf(msg, sizeof(msg), "Already at defaults — sensor may be faulty\r\n");
          }
          HAL_UART_Transmit(&huart2, (uint8_t*)msg, (uint16_t)n, 100);
      } else {
          /* Step 2: RX ID 도 변경됨 — 0x060~0x06F 범위 스캔 */
          n = snprintf(msg, sizeof(msg), "No resp at 0x064, scanning 0x060-0x06F...\r\n");
          HAL_UART_Transmit(&huart2, (uint8_t*)msg, (uint16_t)n, 100);

          /* 전체 11비트 표준 ID 스캔: 10ms×2048 = ~25초 소요, 0x100마다 진행 출력 */
          n = snprintf(msg, sizeof(msg), "Scanning 0x000-0x7FF (~25s)...\r\n");
          HAL_UART_Transmit(&huart2, (uint8_t*)msg, (uint16_t)n, 100);
          cid = RFT_ScanAndReadCommID(0x000U, 0x7FFU);
          if (cid.valid) {
              /* 1바이트 파싱: scan_id=실제 수신 CAN ID, rx/tx1/tx2=센서 저장값 */
              n = snprintf(msg, sizeof(msg),
                  "Found! ScanID=0x%02X | currRX=0x%02X TX1=0x%02X TX2=0x%02X\r\n",
                  (unsigned)cid.scan_id, (unsigned)cid.rx_id,
                  (unsigned)cid.tx_id1,  (unsigned)cid.tx_id2);
              HAL_UART_Transmit(&huart2, (uint8_t*)msg, (uint16_t)n, 100);
              RFT_ResetCommID(cid.scan_id);  /* 실제 응답한 CAN ID로 전송 */
              n = snprintf(msg, sizeof(msg),
                  "Reset cmd sent to RX=0x%02X — power cycle sensor now\r\n",
                  (unsigned)cid.scan_id);
          } else {
              n = snprintf(msg, sizeof(msg), "CommID scan failed. Testing firmware alive...\r\n");
              HAL_UART_Transmit(&huart2, (uint8_t*)msg, (uint16_t)n, 100);

              /* 펌웨어 생존 확인: START 전송 후 어떤 ID든 응답 오면 펌웨어 살아있음 */
              g_rft_isr_cnt = 0;
              RFT_SendCmdTo(0x064U, RFT_CMD_START);   /* 0x0B */
              HAL_Delay(500);
              uint32_t got = g_rft_isr_cnt;
              RFT_SendCmdTo(0x064U, RFT_CMD_STOP);    /* 0x0C */

              if (got > 0) {
                  n = snprintf(msg, sizeof(msg),
                      "Firmware ALIVE: isr=%lu frames (wrong CommID)\r\n", got);
              } else {
                  /* READ 단발 시도 */
                  g_rft_isr_cnt = 0;
                  RFT_SendCmdTo(0x064U, RFT_CMD_READ);  /* 0x0A */
                  HAL_Delay(200);
                  got = g_rft_isr_cnt;
                  if (got > 0) {
                      n = snprintf(msg, sizeof(msg),
                          "Firmware ALIVE (READ): isr=%lu (wrong CommID)\r\n", got);
                  } else {
                      n = snprintf(msg, sizeof(msg),
                          "No response to START/READ either — power cycle sensor 30s\r\n");
                  }
              }
          }
          HAL_UART_Transmit(&huart2, (uint8_t*)msg, (uint16_t)n, 100);
      }
      while (1);  /* 복구 완료 → 매크로 0으로 복원 후 재빌드 */
  }
#endif /* COMM_ID_CONFIG_MODE */

  RFT_StartStream();       /* 200Hz 연속 스트리밍 시작 */
  HAL_Delay(100);          /* 전송 후 잠시 대기 — ACK 수신 시간 확보 */

  /* ── DEBUG: CAN 상태 진단 ──────────────────────────────────────────
     UART 출력 예시:
       DBG can_err=0x00000000 free=3  → 정상 (TX 완료, ACK 수신)
       DBG can_err=0x00000080 free=3  → HAL_CAN_ERROR_ACK: 종단저항/배선 문제
       DBG can_err=0x00000080 free=2  → ACK 없음, TX 메일박스 1개 점유 중
       DBG can_err=0x00000008 free=3  → 비트도미넌트 오류 (CANH/CANL 단락 의심)
  ────────────────────────────────────────────────────────────────── */
  {
    uint32_t can_err  = HAL_CAN_GetError(&hcan);
    uint32_t tx_free  = HAL_CAN_GetTxMailboxesFreeLevel(&hcan);
    char dbg[80];
    int n = snprintf(dbg, sizeof(dbg),
        "DBG can_err=0x%08lX free=%lu\r\n", can_err, tx_free);
    HAL_UART_Transmit(&huart2, (uint8_t*)dbg, (uint16_t)n, 50);
  }
  /* ── END DEBUG ── */

  /* 영점 설정: 센서를 공중에 놓은 상태에서 실행
     RFT_SetBias(1);       */

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */

    /* ── DEBUG: 1초마다 ISR 카운터 출력 ──────────────────────────────
       기대값 (200Hz 스트리밍):
         isr=400 f1=200 f2=200 parsed=200  → 정상
         isr=0   f1=0   f2=0   parsed=0   → 인터럽트 미발화 (필터/NVIC 문제)
         isr>0   f1>0   f2=0   parsed=0   → ID=0x002 프레임 미수신
    ────────────────────────────────────────────────────────────────── */
    static uint32_t s_last_tick = 0;
    uint32_t now = HAL_GetTick();
    if (now - s_last_tick >= 1000) {
        s_last_tick = now;

        /* ── 폴링: 인터럽트와 무관하게 FIFO0에 메시지 있는지 직접 확인 ── */
        uint32_t fifo_fill = HAL_CAN_GetRxFifoFillLevel(&hcan, CAN_RX_FIFO0);

        /* 폴링으로 프레임 꺼내기 시도 */
        CAN_RxHeaderTypeDef poll_hdr;
        uint8_t poll_data[8];
        uint8_t poll_got = 0;
        if (HAL_CAN_GetRxMessage(&hcan, CAN_RX_FIFO0, &poll_hdr, poll_data) == HAL_OK) {
            poll_got = 1;
        }

        /* CAN ESR 하드웨어 레지스터 직접 읽기 */
        uint32_t esr = hcan.Instance->ESR;
        uint8_t  lec = (uint8_t)((esr >> 4)  & 0x07U);  /* Last Error Code */
        uint8_t  tec = (uint8_t)((esr >> 16) & 0xFFU);  /* TX Error Counter */
        uint8_t  rec = (uint8_t)((esr >> 24) & 0xFFU);  /* RX Error Counter */
        /* LEC: 0=없음 1=Stuff 2=Form 3=ACK오류 4=BitR 5=BitD 6=CRC */

        char dbg[128];
        int n = snprintf(dbg, sizeof(dbg),
            "isr=%lu fifo=%lu poll=%u | LEC=%u TEC=%u REC=%u BOFF=%lu\r\n",
            g_rft_isr_cnt, fifo_fill, poll_got,
            lec, tec, rec,
            (esr & CAN_ESR_BOFF) ? 1UL : 0UL);
        HAL_UART_Transmit(&huart2, (uint8_t*)dbg, (uint16_t)n, 20);

        /* Bus-Off 감지 시 자동 복구 후 START 재전송 */
        if (hcan.Instance->ESR & CAN_ESR_BOFF) {
            HAL_CAN_Stop(&hcan);
            HAL_Delay(10);
            HAL_CAN_Start(&hcan);
            const char *msg = "BUS-OFF recovered\r\n";
            HAL_UART_Transmit(&huart2, (uint8_t*)msg, strlen(msg), 20);
        }
        RFT_StartStream();
    }
    /* ── END DEBUG ── */

    ft = RFT_GetData();

    if (ft.updated) {
      /* SerialPlot 호환 CSV 포맷: Fx,Fy,Fz,Tx,Ty,Tz
         SerialPlot → File → Open Port (115200) → 채널 6개 자동 감지  */
      char buf[80];
      int len = snprintf(buf, sizeof(buf),
          "%.3f,%.3f,%.3f,%.5f,%.5f,%.5f\r\n",
          (double)ft.Fx, (double)ft.Fy, (double)ft.Fz,
          (double)ft.Tx, (double)ft.Ty, (double)ft.Tz);
      HAL_UART_Transmit(&huart2, (uint8_t *)buf, (uint16_t)len, 10);

      /* 과부하 경고 (선택): 비트 필드 확인
         if (ft.overload) {
           const char *warn = "OVERLOAD!\r\n";
           HAL_UART_Transmit(&huart2, (uint8_t *)warn, strlen(warn), 10);
         }                                                              */
    }

    /* ── PC → STM32 명령 수신 (선택) ──
       단일 바이트 명령: 'b'=영점설정, 'B'=영점해제, 's'=시작, 'S'=정지
    uint8_t rx_byte;
    if (HAL_UART_Receive(&huart2, &rx_byte, 1, 0) == HAL_OK) {
      switch (rx_byte) {
        case 'b': RFT_SetBias(1);      break;
        case 'B': RFT_SetBias(0);      break;
        case 's': RFT_StartStream();   break;
        case 'S': RFT_StopStream();    break;
      }
    }
    */
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

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
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
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief CAN Initialization Function
  * @param None
  * @retval None
  */
static void MX_CAN_Init(void)
{

  /* USER CODE BEGIN CAN_Init 0 */

  /* USER CODE END CAN_Init 0 */

  /* USER CODE BEGIN CAN_Init 1 */

  /* USER CODE END CAN_Init 1 */
  hcan.Instance = CAN1;
  hcan.Init.Prescaler = 4;
  hcan.Init.Mode = CAN_MODE_NORMAL;
  hcan.Init.SyncJumpWidth = CAN_SJW_1TQ;
  hcan.Init.TimeSeg1 = CAN_BS1_6TQ;
  hcan.Init.TimeSeg2 = CAN_BS2_2TQ;
  hcan.Init.TimeTriggeredMode = DISABLE;
  hcan.Init.AutoBusOff = DISABLE;
  hcan.Init.AutoWakeUp = DISABLE;
  hcan.Init.AutoRetransmission = ENABLE;
  hcan.Init.ReceiveFifoLocked = DISABLE;
  hcan.Init.TransmitFifoPriority = DISABLE;
  if (HAL_CAN_Init(&hcan) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN CAN_Init 2 */

  /* USER CODE END CAN_Init 2 */

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 115200;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

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
