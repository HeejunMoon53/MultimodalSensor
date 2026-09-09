/**
  ******************************************************************************
  * @file    gate_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-09-10T00:32:33+0900
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
  0x3eaf08ea3f800000U, 0x3f532ce93ee7faedU, 0x3f3aa050bee05c1bU, 0x3f3899b6be6e931cU,
  0xbeb575b4beb9f195U, 0x3f5c7dc33f3e16feU, 0xbefc92163a255332U, 0x3f18a9e5bff7cd09U,
  0xbf210a31bf4c2fd3U, 0x3f71dd8a3f953608U, 0x3e46def73f65010fU, 0xbe5837df3f5d8816U,
  0xbf33b6c13f434c3fU, 0x3f90c6023f51551dU, 0xbf0924e83fb5d9f7U, 0xbf0f11d83f80e496U,
  0x3d9fe55b3f9d27adU, 0x3f7dc1873ef09f70U, 0xbf06063f3f682e75U, 0xbf2b12f53f91d769U,
  0xbddd1297be15a546U, 0xbfe6f923bf85c105U, 0x3ea3b7d3be684c27U, 0x3cb352cdbf5f47b0U,
  0x3ee81444bf67f3a0U, 0x3f88fc1c3f5e620fU, 0xbf306c1c3f65842fU, 0xbf1866243f04b753U,
  0x3ec9ef3bbe4c04deU, 0xbefc1193be68c168U, 0xbff535dd3c91bb7eU, 0x3fff9117bffcb95bU,
  0xbf25b1b5c005badaU, 0x100000000U,
};


ai_handle g_gate_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_gate_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

