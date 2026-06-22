#ifndef RFT_SENSOR_H
#define RFT_SENSOR_H

#include "stm32f1xx_hal.h"
#include <string.h>

/* ── CAN IDs (RFT Series CAN-A interface default) ── */
#define RFT_CAN_CMD_ID   0x064U   /* Receiver ID  — STM32 → sensor */
#define RFT_CAN_RSP_ID1  0x001U   /* Transmitter #1 — first 8 bytes  */
#define RFT_CAN_RSP_ID2  0x002U   /* Transmitter #2 — last  8 bytes  */

/* ── Command IDs ── */
#define RFT_CMD_SET_COMM_ID  0x04U    /* Set Communication ID (TX1/TX2/RX) */
#define RFT_CMD_READ_COMM_ID 0x05U    /* Read Communication ID */
#define RFT_CMD_READ         0x0AU    /* Single read (폴링) */
#define RFT_CMD_START        0x0BU    /* Start continuous stream */
#define RFT_CMD_STOP         0x0CU    /* Stop  continuous stream */
#define RFT_CMD_BIAS_ON      0x11U    /* Bias set (현재 하중을 영점으로) */
#define RFT_CMD_BIAS_OFF     0x12U    /* Bias clear */

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

/* ── DEBUG 카운터 ── */
extern volatile uint32_t g_rft_isr_cnt;
extern volatile uint32_t g_rft_frame1;
extern volatile uint32_t g_rft_frame2;
extern volatile uint32_t g_rft_parse_cnt;

/* ── Public API ── */
void         RFT_Init(CAN_HandleTypeDef *hcan);
void         RFT_StartStream(void);
void         RFT_StopStream(void);
void         RFT_SetBias(uint8_t enable);          /* 1=영점 설정, 0=영점 해제 */
RFT_Data_t   RFT_GetData(void);                    /* updated 플래그 읽고 클리어 */

void         RFT_SendCmdTo(uint32_t can_id, uint8_t cmd); /* 임의 CAN ID로 단발 명령 전송 */

/* ── Communication ID 조회/복구 (구 센서 ID 리셋용) ── */
RFT_CommID_t RFT_ReadCommID(void);                 /* 현재 ID 조회 (기본 RX=0x064 가정) */
void         RFT_ResetCommID(uint16_t target_rx);  /* 기본값(TX1=0x001 TX2=0x002 RX=0x064)으로 리셋 */
RFT_CommID_t RFT_ScanAndReadCommID(uint16_t id_start, uint16_t id_end); /* RX ID 모를 때 범위 스캔 */

#endif /* RFT_SENSOR_H */
