#include "commid_tool.h"
#include "rft_sensor.h"
#include <stdio.h>

extern volatile uint32_t g_rft_isr_cnt;

/* 센서 CommID를 기본값(RX=0x64, TX1=0x01, TX2=0x02)으로 복구.
   UART로 진행 상황 출력. 완료 시 반환 (caller가 while(1)로 정지). */
void CommID_RunRecovery(UART_HandleTypeDef *huart)
{
    char msg[80];
    int  n;

    /* Step 1: 기본 RX=0x064로 READ 시도 */
    RFT_CommID_t cid = RFT_ReadCommID();
    if (cid.valid) {
        n = snprintf(msg, sizeof(msg),
            "CommID: RX=0x%02X TX1=0x%02X TX2=0x%02X\r\n",
            (unsigned)cid.rx_id, (unsigned)cid.tx_id1, (unsigned)cid.tx_id2);
        HAL_UART_Transmit(huart, (uint8_t*)msg, (uint16_t)n, 100);

        if (cid.rx_id != 0x64U || cid.tx_id1 != 0x01U || cid.tx_id2 != 0x02U) {
            RFT_ResetCommID(0x064U);
            n = snprintf(msg, sizeof(msg), "Reset sent — power cycle sensor\r\n");
        } else {
            n = snprintf(msg, sizeof(msg), "Already at defaults\r\n");
        }
        HAL_UART_Transmit(huart, (uint8_t*)msg, (uint16_t)n, 100);
        return;
    }

    /* Step 2: 전체 11비트 범위 스캔 (~25s) */
    n = snprintf(msg, sizeof(msg), "No resp at 0x064 — scanning 0x000-0x7FF (~25s)\r\n");
    HAL_UART_Transmit(huart, (uint8_t*)msg, (uint16_t)n, 100);

    cid = RFT_ScanAndReadCommID(0x000U, 0x7FFU);
    if (cid.valid) {
        n = snprintf(msg, sizeof(msg),
            "Found! ScanID=0x%02X | RX=0x%02X TX1=0x%02X TX2=0x%02X\r\n",
            (unsigned)cid.scan_id, (unsigned)cid.rx_id,
            (unsigned)cid.tx_id1,  (unsigned)cid.tx_id2);
        HAL_UART_Transmit(huart, (uint8_t*)msg, (uint16_t)n, 100);
        RFT_ResetCommID(cid.scan_id);
        n = snprintf(msg, sizeof(msg),
            "Reset sent to 0x%02X — power cycle sensor\r\n", (unsigned)cid.scan_id);
        HAL_UART_Transmit(huart, (uint8_t*)msg, (uint16_t)n, 100);
        return;
    }

    /* Step 3: 펌웨어 생존 확인 (배선 문제 vs CommID 문제 구분) */
    n = snprintf(msg, sizeof(msg), "Scan failed — checking firmware\r\n");
    HAL_UART_Transmit(huart, (uint8_t*)msg, (uint16_t)n, 100);

    g_rft_isr_cnt = 0;
    RFT_SendCmdTo(0x064U, RFT_CMD_START);
    HAL_Delay(500);
    uint32_t got = g_rft_isr_cnt;
    RFT_SendCmdTo(0x064U, RFT_CMD_STOP);

    if (got == 0) {
        g_rft_isr_cnt = 0;
        RFT_SendCmdTo(0x064U, RFT_CMD_READ);
        HAL_Delay(200);
        got = g_rft_isr_cnt;
    }

    if (got > 0) {
        n = snprintf(msg, sizeof(msg),
            "Firmware alive (isr=%lu) — CommID mismatch\r\n", got);
    } else {
        n = snprintf(msg, sizeof(msg),
            "No response — check wiring, then power cycle 30s\r\n");
    }
    HAL_UART_Transmit(huart, (uint8_t*)msg, (uint16_t)n, 100);
}
