/**
  ******************************************************************************
  * @file    expert_a_data_params.h
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-08-14T22:24:58+0900
  * @brief   AI Tool Automatic Code Generator for Embedded NN computing
  ******************************************************************************
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  ******************************************************************************
  */

#ifndef EXPERT_A_DATA_PARAMS_H
#define EXPERT_A_DATA_PARAMS_H

#include "ai_platform.h"

/*
#define AI_EXPERT_A_DATA_WEIGHTS_PARAMS \
  (AI_HANDLE_PTR(&ai_expert_a_data_weights_params[1]))
*/

#define AI_EXPERT_A_DATA_CONFIG               (NULL)


#define AI_EXPERT_A_DATA_ACTIVATIONS_SIZES \
  { 160, }
#define AI_EXPERT_A_DATA_ACTIVATIONS_SIZE     (160)
#define AI_EXPERT_A_DATA_ACTIVATIONS_COUNT    (1)
#define AI_EXPERT_A_DATA_ACTIVATION_1_SIZE    (160)



#define AI_EXPERT_A_DATA_WEIGHTS_SIZES \
  { 2696, }
#define AI_EXPERT_A_DATA_WEIGHTS_SIZE         (2696)
#define AI_EXPERT_A_DATA_WEIGHTS_COUNT        (1)
#define AI_EXPERT_A_DATA_WEIGHT_1_SIZE        (2696)



#define AI_EXPERT_A_DATA_ACTIVATIONS_TABLE_GET() \
  (&g_expert_a_activations_table[1])

extern ai_handle g_expert_a_activations_table[1 + 2];



#define AI_EXPERT_A_DATA_WEIGHTS_TABLE_GET() \
  (&g_expert_a_weights_table[1])

extern ai_handle g_expert_a_weights_table[1 + 2];


#endif    /* EXPERT_A_DATA_PARAMS_H */
