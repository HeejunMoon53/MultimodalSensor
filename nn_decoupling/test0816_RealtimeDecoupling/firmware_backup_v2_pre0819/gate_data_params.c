/**
  ******************************************************************************
  * @file    gate_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-08-17T01:44:25+0900
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
  0x3eec6ad43f800000U, 0x3f1f94733e5e25aaU, 0x3f0712b2bef3a9d9U, 0x3f11ee69bddde869U,
  0xbee06709bebd20e0U, 0x3f5292ba3ee1db41U, 0xbe6cb2d83eb64816U, 0x3f2c2cfabf210a22U,
  0xbf4d2083bf472bb4U, 0x3f1cca303f58032eU, 0x3eaa83433f241930U, 0xbed48e3f3de90cabU,
  0xbf13cee23f1c0375U, 0x3f23b4643f2587b7U, 0xbed3fe703f95f122U, 0xbecb1c703eeeced7U,
  0x3e96470a3f849c79U, 0x3ed6b2163e6c0aeaU, 0xbf2eb6303f18e188U, 0x3dc3d3f03f3dffe2U,
  0xbe741800be761c9aU, 0xbf3044acbf388019U, 0x3ee0872f3e32d5d7U, 0xbe7b5896bc15d90fU,
  0x3ee0feb9bf380ccdU, 0x3f071d923f3cd033U, 0xbf2a5b713f2ac75fU, 0x3dddb5d7beaa6f9bU,
  0x3ea389a7be3f6939U, 0xbe81344dbed4e5d8U, 0xbfabb27abcd5fe2dU, 0x3f97dc6bbf98e05eU,
  0xbf1a4947bfa931ddU, 0x100000000U,
};


ai_handle g_gate_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_gate_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

