#include "rft_sensor.h"
#include <stdio.h>

extern UART_HandleTypeDef huart2;  /* main.c 에 선언된 USART2 핸들 */

/* ── 내부 상태 ── */
static CAN_HandleTypeDef *s_hcan;

static uint8_t  s_buf[16];   /* 두 CAN 프레임(8B × 2)을 합친 버퍼 */
static uint8_t  s_got1;      /* Transmitter #1 수신 여부 */
static uint8_t  s_got2;      /* Transmitter #2 수신 여부 */
static RFT_Data_t s_data;    /* 파싱된 최신 데이터 */

/* CommID 조회 응답 버퍼 (ISR에서 쓰고, 메인루프에서 읽음) */
static volatile struct {
    uint16_t tx_id1;
    uint16_t tx_id2;
    uint16_t rx_id;
    uint8_t  valid;
} s_commid_buf;

static uint32_t s_tx_mailbox; /* 마지막 TX 메일박스 번호 (스캔 중 abort 용) */

volatile uint32_t g_rft_isr_cnt = 0;

/* ── 내부: 특정 CAN ID로 1바이트 명령 전송 ── */
static void send_to_id(uint32_t can_id, uint8_t cmd)
{
    CAN_TxHeaderTypeDef hdr = {
        .StdId              = can_id,
        .IDE                = CAN_ID_STD,
        .RTR                = CAN_RTR_DATA,
        .DLC                = 8,
        .TransmitGlobalTime = DISABLE,
    };
    uint8_t data[8] = {cmd, 0, 0, 0, 0, 0, 0, 0};
    HAL_CAN_AddTxMessage(s_hcan, &hdr, data, &s_tx_mailbox);
}

/* ── 내부: 기본 RX ID(0x064)로 명령 전송 ── */
static void send_cmd(uint8_t cmd, uint8_t param)
{
    CAN_TxHeaderTypeDef hdr = {
        .StdId              = RFT_CAN_CMD_ID,
        .IDE                = CAN_ID_STD,
        .RTR                = CAN_RTR_DATA,
        .DLC                = 8,
        .TransmitGlobalTime = DISABLE,
    };
    uint8_t data[8] = {cmd, param, 0, 0, 0, 0, 0, 0};
    HAL_CAN_AddTxMessage(s_hcan, &hdr, data, &s_tx_mailbox);
}

/* ── 내부: 16바이트 버퍼 → RFT_Data_t 파싱 ── */
static void parse_frame(void)
{
    /* s_buf[0] = Response ID (0x0A 또는 0x0B 이어야 함) */
    if (s_buf[0] != 0x0A && s_buf[0] != 0x0B) return;

    /* D2~D13: 6개 signed 16-bit (big-endian) */
    /* 레이아웃:
       buf[0]      = Response ID
       buf[1-2]    = Fx  (upper, lower)
       buf[3-4]    = Fy
       buf[5-6]    = Fz
       buf[7-8]    = Tx  (프레임 경계 걸침)
       buf[9-10]   = Ty
       buf[11-12]  = Tz
       buf[13]     = Overload status                */
    int16_t raw[6];
    for (int i = 0; i < 6; i++) {
        raw[i] = (int16_t)((uint16_t)s_buf[2*i + 1] << 8
                          | (uint16_t)s_buf[2*i + 2]);
    }

    s_data.Fx       = (float)raw[0] / RFT_DF;
    s_data.Fy       = (float)raw[1] / RFT_DF;
    s_data.Fz       = (float)raw[2] / RFT_DF;
    s_data.Tx       = (float)raw[3] / RFT_DT;
    s_data.Ty       = (float)raw[4] / RFT_DT;
    s_data.Tz       = (float)raw[5] / RFT_DT;
    s_data.overload = s_buf[13];
    s_data.updated  = 1;
}

/* ════════════════════════════════════════════════════════════
   Public API
   ════════════════════════════════════════════════════════════ */

void RFT_Init(CAN_HandleTypeDef *hcan)
{
    s_hcan = hcan;

    /* mask=0 → 모든 ID 수신. ISR에서 StdId로 0x001/0x002 구분 */
    CAN_FilterTypeDef f = {
        .FilterBank           = 0,
        .FilterMode           = CAN_FILTERMODE_IDMASK,
        .FilterScale          = CAN_FILTERSCALE_32BIT,
        .FilterIdHigh         = 0x0000U,
        .FilterIdLow          = 0x0000U,
        .FilterMaskIdHigh     = 0x0000U,
        .FilterMaskIdLow      = 0x0000U,
        .FilterFIFOAssignment = CAN_RX_FIFO0,
        .FilterActivation     = ENABLE,
        .SlaveStartFilterBank = 14,
    };
    HAL_CAN_ConfigFilter(hcan, &f);
    HAL_CAN_ActivateNotification(hcan, CAN_IT_RX_FIFO0_MSG_PENDING);
    HAL_CAN_Start(hcan);
}

void RFT_SendCmdTo(uint32_t can_id, uint8_t cmd) { send_to_id(can_id, cmd); }
void RFT_StartStream(void) { send_cmd(RFT_CMD_START, 0x00); }
void RFT_StopStream(void)  { send_cmd(RFT_CMD_STOP,  0x00); }

/* ── Communication ID 조회: 0x064로 0x05 명령 전송 → 200ms 대기 ── */
RFT_CommID_t RFT_ReadCommID(void)
{
    s_commid_buf.valid = 0;
    send_to_id(RFT_CAN_CMD_ID, RFT_CMD_READ_COMM_ID);

    uint32_t t0 = HAL_GetTick();
    while (!s_commid_buf.valid && (HAL_GetTick() - t0 < 200U));

    RFT_CommID_t r;
    r.tx_id1 = s_commid_buf.tx_id1;
    r.tx_id2 = s_commid_buf.tx_id2;
    r.rx_id  = s_commid_buf.rx_id;
    r.valid  = s_commid_buf.valid;
    return r;
}

/* ── Communication ID 초기화: target_rx로 SET 명령 → 기본값(TX1=0x001 TX2=0x002 RX=0x064) EEPROM 저장 ── */
void RFT_ResetCommID(uint16_t target_rx)
{
    CAN_TxHeaderTypeDef hdr = {
        .StdId              = target_rx,
        .IDE                = CAN_ID_STD,
        .RTR                = CAN_RTR_DATA,
        .DLC                = 8,
        .TransmitGlobalTime = DISABLE,
    };
    /* datasheet 3.6.5: [D1=cmd, D2=RX(1B), D3=TX1(1B), D4=TX2(1B), D5-D8=XX]
       ID는 1바이트 (range 1~255). 기본값: RX=0x64, TX1=0x01, TX2=0x02 */
    uint8_t data[8] = {RFT_CMD_SET_COMM_ID, 0x64, 0x01, 0x02, 0x00, 0x00, 0x00, 0x00};
    uint32_t mailbox;
    HAL_CAN_AddTxMessage(s_hcan, &hdr, data, &mailbox);
    HAL_Delay(200);  /* EEPROM 기록 대기 */
}

/* ── ID 모를 때 범위 스캔 ──
   AutoRetransmission=ENABLE 상태에서 스캔하면 응답 없는 ID마다 수백 번 재시도
   → 10ms 안에 TEC 255 초과 → Bus-Off → 나머지 전부 실패.
   NART(No Auto-Retransmit) 모드로 전환: 1회 TX 후 즉시 메일박스 해제, TEC 급등 방지. */
static void rft_can_reinit_nart(uint8_t nart_enable, CAN_FilterTypeDef *pf)
{
    HAL_CAN_Stop(s_hcan);
    s_hcan->Init.AutoRetransmission = nart_enable ? DISABLE : ENABLE;
    HAL_CAN_Init(s_hcan);
    HAL_CAN_ConfigFilter(s_hcan, pf);
    HAL_CAN_ActivateNotification(s_hcan, CAN_IT_RX_FIFO0_MSG_PENDING);
    HAL_CAN_Start(s_hcan);
}

RFT_CommID_t RFT_ScanAndReadCommID(uint16_t id_start, uint16_t id_end)
{
    RFT_CommID_t result = {0, 0, 0, 0};

    /* pass-all 필터 (스캔 중 재사용) */
    CAN_FilterTypeDef f = {
        .FilterBank=0, .FilterMode=CAN_FILTERMODE_IDMASK,
        .FilterScale=CAN_FILTERSCALE_32BIT,
        .FilterIdHigh=0, .FilterIdLow=0,
        .FilterMaskIdHigh=0, .FilterMaskIdLow=0,
        .FilterFIFOAssignment=CAN_RX_FIFO0,
        .FilterActivation=ENABLE, .SlaveStartFilterBank=14,
    };

    /* NART 모드 진입: 1회 TX만 수행 */
    rft_can_reinit_nart(1, &f);

    for (uint16_t id = id_start; id <= id_end; id++) {
        /* Bus-Off 복구 (32개 실패 누적 시 발생) */
        if (s_hcan->Instance->ESR & CAN_ESR_BOFF) {
            HAL_CAN_Stop(s_hcan);
            HAL_Delay(5);
            HAL_CAN_Init(s_hcan);  /* AutoRetransmission=DISABLE 유지 */
            HAL_CAN_ConfigFilter(s_hcan, &f);
            HAL_CAN_ActivateNotification(s_hcan, CAN_IT_RX_FIFO0_MSG_PENDING);
            HAL_CAN_Start(s_hcan);
        }

        /* TX 메일박스 여유 대기 (NART라 보통 즉시 여유) */
        uint32_t tw = HAL_GetTick();
        while (HAL_CAN_GetTxMailboxesFreeLevel(s_hcan) == 0 && (HAL_GetTick()-tw < 10U));

        s_commid_buf.valid = 0;
        send_to_id(id, RFT_CMD_READ_COMM_ID);

        uint32_t t0 = HAL_GetTick();
        while (!s_commid_buf.valid && (HAL_GetTick()-t0 < 5U));

        if (s_commid_buf.valid) {
            result.tx_id1  = s_commid_buf.tx_id1;
            result.tx_id2  = s_commid_buf.tx_id2;
            result.rx_id   = s_commid_buf.rx_id;
            result.scan_id = id;   /* 실제 응답이 온 CAN ID */
            result.valid   = 1;
            break;
        }
    }

    /* AutoRetransmission 복원 */
    rft_can_reinit_nart(0, &f);

    return result;
}

void RFT_SetBias(uint8_t enable)
{
    send_cmd(enable ? RFT_CMD_BIAS_ON : RFT_CMD_BIAS_OFF, 0x00);
}

RFT_Data_t RFT_GetData(void)
{
    RFT_Data_t d = s_data;
    s_data.updated = 0;
    return d;
}

/* ════════════════════════════════════════════════════════════
   HAL Callback (stm32f1xx_it.c 의 USB_LP_CAN1_RX0_IRQHandler →
                 HAL_CAN_IRQHandler 가 이 함수를 호출)
   ════════════════════════════════════════════════════════════ */
void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan)
{
    g_rft_isr_cnt++;

    CAN_RxHeaderTypeDef rxhdr;
    uint8_t rxdata[8];

    while (HAL_CAN_GetRxMessage(hcan, CAN_RX_FIFO0, &rxhdr, rxdata) == HAL_OK)
    {
        if (rxhdr.IDE != CAN_ID_STD) continue;

        /* CommID 응답 (0x05): [0x05, currRX, currTX1, currTX2, newRX, newTX1, newTX2, XX]
           ID는 1바이트 (range 1~255), 2바이트 아님 */
        if (rxhdr.DLC == 8U && rxdata[0] == RFT_CMD_READ_COMM_ID) {
            s_commid_buf.rx_id  = rxdata[1];  /* 현재 RX ID */
            s_commid_buf.tx_id1 = rxdata[2];  /* 현재 TX1 ID */
            s_commid_buf.tx_id2 = rxdata[3];  /* 현재 TX2 ID */
            s_commid_buf.valid  = 1;
            continue;
        }

        if (rxhdr.StdId == RFT_CAN_RSP_ID1) {
            memcpy(&s_buf[0], rxdata, 8);
            s_got1 = 1;
        } else if (rxhdr.StdId == RFT_CAN_RSP_ID2) {
            memcpy(&s_buf[8], rxdata, 8);
            s_got2 = 1;
        }

        if (s_got1 && s_got2) {
            s_got1 = s_got2 = 0;
            parse_frame();
        }
    }
}
