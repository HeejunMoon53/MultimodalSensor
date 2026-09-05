/**
  ******************************************************************************
  * @file    gate_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-08-19T14:17:07+0900
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
  0x3e1e8a9d3f800000U, 0x3f5be0803ee6e824U, 0x3f2e2d60bf054f0eU, 0x3f46ab4cbdaa7736U,
  0xbef84a76bee9c817U, 0x3ec7d3ca3ef4d12fU, 0xbe606f013f27e1b1U, 0x3f750f77bf22b234U,
  0xbec80952bf4d3379U, 0x3f3f1d263f4c7551U, 0x3d91d12d3f337920U, 0xbc4f0abd3e521149U,
  0xbf2650173f1f7ed9U, 0x3e7c57fa3f023578U, 0xbf145b3f3f728da6U, 0xbe5193483e9c95faU,
  0xbdadb6b33f8505b2U, 0x3f2f911f3ea9dc4dU, 0xbf17b6123f42f55bU, 0x3e0601ac3c130906U,
  0xbe49e1b3be2bd717U, 0xbf82da9abf501d00U, 0x3f2477a6bcf4b947U, 0xbe6c511abd23cd1fU,
  0x3ea7b83dbf4ee718U, 0x3f164fcf3f6229fdU, 0xbf5d95fe3f626855U, 0x3d8e16d6bee5e2e6U,
  0x3e1198f1bdd545f0U, 0xbe94d864be07dcb0U, 0xbf9b94373e0b3a33U, 0x3f89c1f8bf711db4U,
  0xbf3dbe56bf92fdf8U, 0x100000000U,
};


ai_handle g_gate_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_gate_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

