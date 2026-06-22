#ifndef COMMID_TOOL_H
#define COMMID_TOOL_H

#include "stm32f1xx_hal.h"

/* 0=정상 운용, 1=CommID 복구 모드
   1로 변경 → 빌드·플래시 → 완료 후 0으로 복원하여 재빌드 */
#define COMM_ID_CONFIG_MODE  0

void CommID_RunRecovery(UART_HandleTypeDef *huart);

#endif /* COMMID_TOOL_H */
