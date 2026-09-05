/**
  ******************************************************************************
  * @file    stage1_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-06-11T16:43:16+0900
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

#include "stage1_data_params.h"


/**  Activations Section  ****************************************************/
ai_handle g_stage1_activations_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(NULL),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};




/**  Weights Section  ********************************************************/
AI_ALIGNED(32)
const ai_u64 s_stage1_weights_array_u64[105] = {
  0x3f31270bbe9daf21U, 0x3edc0ec0U, 0xbf123814be4465beU, 0x3f1c11c3bf263811U,
  0x3daed6873d61c5eeU, 0x3f091ed2bf39bce4U, 0xbefc97003ebf20bcU, 0xbefc4437be9b7750U,
  0x3e5c44bcbc8f94a0U, 0xbe7e02963db5c433U, 0xbe3dc3a43ea6e3f5U, 0x3ce89c79bd221d42U,
  0x3e367db5bde8518cU, 0xbc03e411be26a4a9U, 0xbf0138de3e23100cU, 0xbe682a4b3e56676fU,
  0x8744ca3a912bca39U, 0x8d919dea80000000U, 0x989045f280000000U, 0x92b167003d352b1U,
  0xce8c24c80000000U, 0x1106d109bU, 0x98694ecdU, 0x81a2072a80000000U,
  0xbd4792543f156b48U, 0x80000000beb6bc4bU, 0x3ec9078e3e210111U, 0xbd905c0d3e6ad9aaU,
  0xbe95c752bdd84240U, 0x3eb5962b3ed57a5aU, 0x3f05021abd05fe90U, 0x3d863c6dbeb7bd2aU,
  0xbf0c736e3f15371fU, 0x93e4b8743edb573fU, 0x3e9918dabe6a72fbU, 0xbeadee0ebd73fd49U,
  0xbe136a7896529cf4U, 0xbf22596a3e79ebd7U, 0x3e64cb5ebe4326f7U, 0x3f13f92b3e645659U,
  0x3f121b6c3e40b5a4U, 0x800000003ee5371dU, 0x3e51b2e13e518a5bU, 0x3ec38decbf05b03cU,
  0x3ec3b57ebeb0d614U, 0xbe7d8e523e929edbU, 0x3f2a9ee2be08b4adU, 0xbe8eb56dbdfd5f98U,
  0x80000000U, 0x11d2ae7aU, 0x800000008fc3b26dU, 0x8000000000000000U,
  0x959c4522U, 0x0U, 0x14dcbb4287ba3749U, 0x93123a51U,
  0x3ea4c7c1bf446de7U, 0x800000003f10daafU, 0xbf1616973ea93bd8U, 0x3e6a6942beaf60faU,
  0xbe98659f3e377351U, 0x3d8a420cbf01b8bbU, 0xbe9ca900bca7f5e9U, 0x3dd65b75bed22f21U,
  0xbaaf152239d0c44bU, 0x8000094a3e95ef9fU, 0xbe935ecf3e013c4eU, 0x3eecb5bd3d9feb7bU,
  0xbd421891be0b5b83U, 0x3ef99bb63e6d2b3cU, 0xbed1f1193f1dff65U, 0xbecdf1593e750db3U,
  0x3df937a53d3d6834U, 0x3ee83e75U, 0x3de321f03e171444U, 0x3dd580c43d340ff0U,
  0xbe08bb1580000000U, 0x3ec5e4f23daea183U, 0x3f2adccfbb3c74e5U, 0x3e5b720dbac2afc9U,
  0x3de78298be0763dcU, 0x3e397ef43e85a896U, 0x3ef3f28bbed1c58aU, 0xbe23e5e73c83fc42U,
  0xbdb70266a4cea7b6U, 0xbd1e41b73db47db0U, 0x3e72129d00016402U, 0x3ea8aecf3f45b2dcU,
  0x8918851600000000U, 0x9d8cee1480000000U, 0x8451da8380000000U, 0x1ec5162000000000U,
  0x3e66096800000000U, 0x3f21b8123f198f85U, 0xbea890fb1314ed8aU, 0x3ece6454be4cbfb2U,
  0xbf0034c5a6b21f21U, 0x3f372085bf2488e7U, 0x3f40384b00000000U, 0x3edab0b0bc6844f9U,
  0xbf168eb33eae8c69U, 0x3f327bbebee481a8U, 0xb31be50d3ed46505U, 0x3f04a7cebf5e3673U,
  0xbf75d954U,
};


ai_handle g_stage1_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_stage1_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

