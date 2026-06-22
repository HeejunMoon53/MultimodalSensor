#ifndef RFT_SENSOR_H
#define RFT_SENSOR_H

#include "stm32f1xx_hal.h"
#include <string.h>

/* ── CAN IDs (RFT Series CAN-A interface default) ── */
#define RFT_CAN_CMD_ID   0x064U   /* Receiver ID  — STM32 → sensor */
#define RFT_CAN_RSP_ID1  0x001U   /* Transmitter #1 — first 8 bytes  */
#define RFT_CAN_RSP_ID2  0x002U   /* Transmitter #2 — last  8 bytes  */

/* ── Command IDs (RFT Series Manual v1.8 §3.6) ── */
#define RFT_CMD_SET_COMM_ID  0x04U    /* Set Communication ID */
#define RFT_CMD_READ_COMM_ID 0x05U    /* Read Communication ID */
#define RFT_CMD_SET_RATE     0x0FU    /* Set Data Output Rate */
#define RFT_CMD_READ         0x0AU    /* Read F/T once */
#define RFT_CMD_START        0x0BU    /* Start continuous stream */
#define RFT_CMD_STOP         0x0CU    /* Stop  continuous stream */
#define RFT_CMD_BIAS         0x11U    /* Set Bias: param 0x01=set, 0x00=clear */

/* Output rate parameters (§3.6.16, CAN 1Mbps) */
#define RFT_RATE_10HZ    0x01U
#define RFT_RATE_20HZ    0x02U
#define RFT_RATE_50HZ    0x03U
#define RFT_RATE_100HZ   0x04U
#define RFT_RATE_200HZ   0x05U
#define RFT_RATE_333HZ   0x06U
#define RFT_RATE_500HZ   0x07U
#define RFT_RATE_1000HZ  0x08U

/* ── 변환 상수 (RFT64-SB01 기준) ── */
#define RFT_DF   50.0f     /* Force  divider → N  */
#define RFT_DT   2000.0f   /* Torque divider → Nm */

typedef struct {
    float   Fx, Fy, Fz;    /* N  */
    float   Tx, Ty, Tz;    /* Nm */
    uint8_t overload;       /* bit5=Fx, bit4=Fy, bit3=Fz, bit2=Tx, bit1=Ty, bit0=Tz */
    uint8_t updated;        /* 새 데이터 도착 플래그 (GetData 호출 시 자동 클리어) */
} RFT_Data_t;

typedef struct {
    uint16_t tx_id1;   /* 센서 TX 프레임1 ID (기본값 0x001, 파싱값) */
    uint16_t tx_id2;   /* 센서 TX 프레임2 ID (기본값 0x002, 파싱값) */
    uint16_t rx_id;    /* 센서 RX ID (파싱값 — 포맷 오류 가능성 있음) */
    uint16_t scan_id;  /* 스캔에서 실제 응답이 온 CAN ID (리셋 명령 전송 대상) */
    uint8_t  valid;    /* 1=센서 응답 수신, 0=타임아웃 */
} RFT_CommID_t;

/* 진단용 — Live expression에서 확인 */
extern volatile uint32_t g_rft_isr_cnt;   /* ISR 발화 횟수 */
extern volatile uint32_t g_rft_rx_cnt;    /* 수신 프레임 수 */
extern volatile uint32_t g_rft_last_id;   /* 마지막 수신 CAN ID */
extern volatile uint32_t g_rft_parse_cnt; /* parse 성공 횟수 */

/* ── Public API ── */
void         RFT_Init(CAN_HandleTypeDef *hcan);
void         RFT_StartStream(void);
void         RFT_StopStream(void);
void         RFT_SetOutputRate(uint8_t rate_param); /* RFT_RATE_* 상수 사용 */
void         RFT_SetBias(uint8_t enable);           /* 1=영점 설정, 0=영점 해제 */
RFT_Data_t   RFT_GetData(void);                    /* updated 플래그 읽고 클리어 */

void         RFT_SendCmdTo(uint32_t can_id, uint8_t cmd); /* 임의 CAN ID로 단발 명령 전송 */

/* ── Communication ID 조회/복구 (구 센서 ID 리셋용) ── */
RFT_CommID_t RFT_ReadCommID(void);                 /* 현재 ID 조회 (기본 RX=0x064 가정) */
void         RFT_ResetCommID(uint16_t target_rx);  /* 기본값(TX1=0x001 TX2=0x002 RX=0x064)으로 리셋 */
RFT_CommID_t RFT_ScanAndReadCommID(uint16_t id_start, uint16_t id_end); /* RX ID 모를 때 범위 스캔 */

#endif /* RFT_SENSOR_H */
