/**
  ******************************************************************************
  * @file    gate_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-08-14T22:24:42+0900
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

#include "gate_data_params.h"


/**  Activations Section  ****************************************************/
ai_handle g_gate_activations_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(NULL),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};




/**  Weights Section  ********************************************************/
AI_ALIGNED(32)
const ai_u64 s_gate_weights_array_u64[34] = {
  0x3e48ede03f800000U, 0x3f8546893d828e8cU, 0x3f5e1b8dbed61d75U, 0x3f70ffcabe822371U,
  0xbefc0a28bed75ee3U, 0x3f63e6523f0435f3U, 0xbe147be8be2d0c69U, 0x3f55e7f6bfeee182U,
  0xbf47d19dbe96a242U, 0x3f7967543f8acbb0U, 0x3ddbcc973f5d8458U, 0xbf388f983f77d821U,
  0xbf22fc053f6ba894U, 0x40191dda3fbc96f6U, 0xbf0a80624003ea90U, 0xbf8e796140062d01U,
  0x3d1c6a6840065ee1U, 0x3f5f564c3f157fc3U, 0xbf29ab373f924d68U, 0x3ceb85b13f7bb3ccU,
  0x3b39f9f2bd380a11U, 0xc03d8380bfba2874U, 0x3e8485a7bf0106deU, 0x3eea268dbfeef6e2U,
  0x3ebcd5d7bfc05b9dU, 0x3f8955403f93c553U, 0xbf51f0513fb0e102U, 0xbd1dd8c43eabe766U,
  0x3eb24326bd01fae4U, 0xbf11c708be8e0d30U, 0xc02388b03d402d91U, 0x401f6788c00a685fU,
  0xbefd1b23c017acddU, 0x100000000U,
};


ai_handle g_gate_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_gate_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

