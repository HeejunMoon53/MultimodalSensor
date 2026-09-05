/**
  ******************************************************************************
  * @file    network.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-06-08T17:56:07+0900
  * @brief   AI Tool Automatic Code Generator for Embedded NN computing
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  ******************************************************************************
  */


#include "network.h"
#include "network_data.h"

#include "ai_platform.h"
#include "ai_platform_interface.h"
#include "ai_math_helpers.h"

#include "core_common.h"
#include "core_convert.h"

#include "layers.h"



#undef AI_NET_OBJ_INSTANCE
#define AI_NET_OBJ_INSTANCE g_network
 
#undef AI_NETWORK_MODEL_SIGNATURE
#define AI_NETWORK_MODEL_SIGNATURE     "0x73e1d1ce1bc947b1fb9cb94139492c3c"

#ifndef AI_TOOLS_REVISION_ID
#define AI_TOOLS_REVISION_ID     ""
#endif

#undef AI_TOOLS_DATE_TIME
#define AI_TOOLS_DATE_TIME   "2026-06-08T17:56:07+0900"

#undef AI_TOOLS_COMPILE_TIME
#define AI_TOOLS_COMPILE_TIME    __DATE__ " " __TIME__

#undef AI_NETWORK_N_BATCHES
#define AI_NETWORK_N_BATCHES         (1)

static ai_ptr g_network_activations_map[1] = AI_C_ARRAY_INIT;
static ai_ptr g_network_weights_map[1] = AI_C_ARRAY_INIT;



/**  Array declarations section  **********************************************/
/* Array#0 */
AI_ARRAY_OBJ_DECLARE(
  dL_eps_output_array, AI_ARRAY_FORMAT_S8|AI_FMT_FLAG_IS_IO,
  NULL, NULL, 2, AI_STATIC)

/* Array#1 */
AI_ARRAY_OBJ_DECLARE(
  mul_result_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 128, AI_STATIC)

/* Array#2 */
AI_ARRAY_OBJ_DECLARE(
  add_result_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 128, AI_STATIC)

/* Array#3 */
AI_ARRAY_OBJ_DECLARE(
  next_activations_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 128, AI_STATIC)

/* Array#4 */
AI_ARRAY_OBJ_DECLARE(
  mul_result1_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 128, AI_STATIC)

/* Array#5 */
AI_ARRAY_OBJ_DECLARE(
  add_result1_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 128, AI_STATIC)

/* Array#6 */
AI_ARRAY_OBJ_DECLARE(
  next_activations1_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 128, AI_STATIC)

/* Array#7 */
AI_ARRAY_OBJ_DECLARE(
  mul_result2_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 64, AI_STATIC)

/* Array#8 */
AI_ARRAY_OBJ_DECLARE(
  add_result2_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 64, AI_STATIC)

/* Array#9 */
AI_ARRAY_OBJ_DECLARE(
  next_activations2_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 64, AI_STATIC)

/* Array#10 */
AI_ARRAY_OBJ_DECLARE(
  mul_result3_output_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 1, AI_STATIC)

/* Array#11 */
AI_ARRAY_OBJ_DECLARE(
  add_result3_output_array, AI_ARRAY_FORMAT_S8|AI_FMT_FLAG_IS_IO,
  NULL, NULL, 1, AI_STATIC)

/* Array#12 */
AI_ARRAY_OBJ_DECLARE(
  intercepts1_DequantizeLinear_Output_const_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 128, AI_STATIC)

/* Array#13 */
AI_ARRAY_OBJ_DECLARE(
  intercepts2_DequantizeLinear_Output_const_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 64, AI_STATIC)

/* Array#14 */
AI_ARRAY_OBJ_DECLARE(
  intercepts3_DequantizeLinear_Output_const_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 1, AI_STATIC)

/* Array#15 */
AI_ARRAY_OBJ_DECLARE(
  intercepts_DequantizeLinear_Output_const_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 128, AI_STATIC)

/* Array#16 */
AI_ARRAY_OBJ_DECLARE(
  mul_result_weights_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 256, AI_STATIC)

/* Array#17 */
AI_ARRAY_OBJ_DECLARE(
  mul_result_bias_array, AI_ARRAY_FORMAT_S32,
  NULL, NULL, 128, AI_STATIC)

/* Array#18 */
AI_ARRAY_OBJ_DECLARE(
  mul_result1_weights_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 16384, AI_STATIC)

/* Array#19 */
AI_ARRAY_OBJ_DECLARE(
  mul_result2_weights_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 8192, AI_STATIC)

/* Array#20 */
AI_ARRAY_OBJ_DECLARE(
  mul_result2_bias_array, AI_ARRAY_FORMAT_S32,
  NULL, NULL, 64, AI_STATIC)

/* Array#21 */
AI_ARRAY_OBJ_DECLARE(
  mul_result3_weights_array, AI_ARRAY_FORMAT_S8,
  NULL, NULL, 64, AI_STATIC)

/* Array#22 */
AI_ARRAY_OBJ_DECLARE(
  mul_result3_bias_array, AI_ARRAY_FORMAT_S32,
  NULL, NULL, 1, AI_STATIC)

/* Array#23 */
AI_ARRAY_OBJ_DECLARE(
  mul_result_scratch0_array, AI_ARRAY_FORMAT_S16,
  NULL, NULL, 2, AI_STATIC)

/* Array#24 */
AI_ARRAY_OBJ_DECLARE(
  mul_result1_scratch0_array, AI_ARRAY_FORMAT_S16,
  NULL, NULL, 128, AI_STATIC)

/* Array#25 */
AI_ARRAY_OBJ_DECLARE(
  mul_result2_scratch0_array, AI_ARRAY_FORMAT_S16,
  NULL, NULL, 128, AI_STATIC)

/* Array#26 */
AI_ARRAY_OBJ_DECLARE(
  mul_result3_scratch0_array, AI_ARRAY_FORMAT_S16,
  NULL, NULL, 64, AI_STATIC)

/**  Array metadata declarations section  *************************************/
/* Int quant #0 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(add_result1_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.02420295961201191f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #1 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(add_result2_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.013176589272916317f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #2 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(add_result3_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.01329148467630148f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #3 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(add_result_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.00858420692384243f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #4 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(dL_eps_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.03287683427333832f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #5 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(intercepts1_DequantizeLinear_Output_const_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.0013614400522783399f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #6 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(intercepts2_DequantizeLinear_Output_const_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.0016696056118234992f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #7 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(intercepts3_DequantizeLinear_Output_const_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.0010283672017976642f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #8 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(intercepts_DequantizeLinear_Output_const_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.0023042107932269573f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #9 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(mul_result1_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.024850094690918922f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #10 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(mul_result1_weights_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.004799120593816042f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #11 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(mul_result2_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.013674786314368248f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #12 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(mul_result2_weights_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.003297855844721198f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #13 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(mul_result3_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.014319851994514465f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #14 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(mul_result3_weights_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.0035260948352515697f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #15 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(mul_result_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.0078007858246564865f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #16 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(mul_result_weights_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.002561366418376565f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #17 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(next_activations1_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.012305496260523796f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #18 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(next_activations2_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.010400891304016113f),
    AI_PACK_INTQ_ZP(0)))

/* Int quant #19 */
AI_INTQ_INFO_LIST_OBJ_DECLARE(next_activations_output_array_intq, AI_STATIC_CONST,
  AI_BUFFER_META_FLAG_SCALE_FLOAT|AI_BUFFER_META_FLAG_ZEROPOINT_S8, 1,
  AI_PACK_INTQ_INFO(
    AI_PACK_INTQ_SCALE(0.00858420692384243f),
    AI_PACK_INTQ_ZP(0)))

/**  Tensor declarations section  *********************************************/
/* Tensor #0 */
AI_TENSOR_OBJ_DECLARE(
  add_result1_output, AI_STATIC,
  0, 0x1,
  AI_SHAPE_INIT(4, 1, 128, 1, 1), AI_STRIDE_INIT(4, 1, 1, 128, 128),
  1, &add_result1_output_array, &add_result1_output_array_intq)

/* Tensor #1 */
AI_TENSOR_OBJ_DECLARE(
  add_result2_output, AI_STATIC,
  1, 0x1,
  AI_SHAPE_INIT(4, 1, 64, 1, 1), AI_STRIDE_INIT(4, 1, 1, 64, 64),
  1, &add_result2_output_array, &add_result2_output_array_intq)

/* Tensor #2 */
AI_TENSOR_OBJ_DECLARE(
  add_result3_output, AI_STATIC,
  2, 0x1,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 1, 1, 1, 1),
  1, &add_result3_output_array, &add_result3_output_array_intq)

/* Tensor #3 */
AI_TENSOR_OBJ_DECLARE(
  add_result_output, AI_STATIC,
  3, 0x1,
  AI_SHAPE_INIT(4, 1, 128, 1, 1), AI_STRIDE_INIT(4, 1, 1, 128, 128),
  1, &add_result_output_array, &add_result_output_array_intq)

/* Tensor #4 */
AI_TENSOR_OBJ_DECLARE(
  dL_eps_output, AI_STATIC,
  4, 0x1,
  AI_SHAPE_INIT(4, 1, 2, 1, 1), AI_STRIDE_INIT(4, 1, 1, 2, 2),
  1, &dL_eps_output_array, &dL_eps_output_array_intq)

/* Tensor #5 */
AI_TENSOR_OBJ_DECLARE(
  intercepts1_DequantizeLinear_Output_const, AI_STATIC,
  5, 0x1,
  AI_SHAPE_INIT(4, 1, 128, 1, 1), AI_STRIDE_INIT(4, 1, 1, 128, 128),
  1, &intercepts1_DequantizeLinear_Output_const_array, &intercepts1_DequantizeLinear_Output_const_array_intq)

/* Tensor #6 */
AI_TENSOR_OBJ_DECLARE(
  intercepts2_DequantizeLinear_Output_const, AI_STATIC,
  6, 0x1,
  AI_SHAPE_INIT(4, 1, 64, 1, 1), AI_STRIDE_INIT(4, 1, 1, 64, 64),
  1, &intercepts2_DequantizeLinear_Output_const_array, &intercepts2_DequantizeLinear_Output_const_array_intq)

/* Tensor #7 */
AI_TENSOR_OBJ_DECLARE(
  intercepts3_DequantizeLinear_Output_const, AI_STATIC,
  7, 0x1,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 1, 1, 1, 1),
  1, &intercepts3_DequantizeLinear_Output_const_array, &intercepts3_DequantizeLinear_Output_const_array_intq)

/* Tensor #8 */
AI_TENSOR_OBJ_DECLARE(
  intercepts_DequantizeLinear_Output_const, AI_STATIC,
  8, 0x1,
  AI_SHAPE_INIT(4, 1, 128, 1, 1), AI_STRIDE_INIT(4, 1, 1, 128, 128),
  1, &intercepts_DequantizeLinear_Output_const_array, &intercepts_DequantizeLinear_Output_const_array_intq)

/* Tensor #9 */
AI_TENSOR_OBJ_DECLARE(
  mul_result1_output, AI_STATIC,
  9, 0x1,
  AI_SHAPE_INIT(4, 1, 128, 1, 1), AI_STRIDE_INIT(4, 1, 1, 128, 128),
  1, &mul_result1_output_array, &mul_result1_output_array_intq)

/* Tensor #10 */
AI_TENSOR_OBJ_DECLARE(
  mul_result1_scratch0, AI_STATIC,
  10, 0x0,
  AI_SHAPE_INIT(4, 1, 128, 1, 1), AI_STRIDE_INIT(4, 2, 2, 256, 256),
  1, &mul_result1_scratch0_array, NULL)

/* Tensor #11 */
AI_TENSOR_OBJ_DECLARE(
  mul_result1_weights, AI_STATIC,
  11, 0x1,
  AI_SHAPE_INIT(4, 128, 128, 1, 1), AI_STRIDE_INIT(4, 1, 128, 16384, 16384),
  1, &mul_result1_weights_array, &mul_result1_weights_array_intq)

/* Tensor #12 */
AI_TENSOR_OBJ_DECLARE(
  mul_result2_bias, AI_STATIC,
  12, 0x0,
  AI_SHAPE_INIT(4, 1, 64, 1, 1), AI_STRIDE_INIT(4, 4, 4, 256, 256),
  1, &mul_result2_bias_array, NULL)

/* Tensor #13 */
AI_TENSOR_OBJ_DECLARE(
  mul_result2_output, AI_STATIC,
  13, 0x1,
  AI_SHAPE_INIT(4, 1, 64, 1, 1), AI_STRIDE_INIT(4, 1, 1, 64, 64),
  1, &mul_result2_output_array, &mul_result2_output_array_intq)

/* Tensor #14 */
AI_TENSOR_OBJ_DECLARE(
  mul_result2_scratch0, AI_STATIC,
  14, 0x0,
  AI_SHAPE_INIT(4, 1, 128, 1, 1), AI_STRIDE_INIT(4, 2, 2, 256, 256),
  1, &mul_result2_scratch0_array, NULL)

/* Tensor #15 */
AI_TENSOR_OBJ_DECLARE(
  mul_result2_weights, AI_STATIC,
  15, 0x1,
  AI_SHAPE_INIT(4, 128, 64, 1, 1), AI_STRIDE_INIT(4, 1, 128, 8192, 8192),
  1, &mul_result2_weights_array, &mul_result2_weights_array_intq)

/* Tensor #16 */
AI_TENSOR_OBJ_DECLARE(
  mul_result3_bias, AI_STATIC,
  16, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &mul_result3_bias_array, NULL)

/* Tensor #17 */
AI_TENSOR_OBJ_DECLARE(
  mul_result3_output, AI_STATIC,
  17, 0x1,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 1, 1, 1, 1),
  1, &mul_result3_output_array, &mul_result3_output_array_intq)

/* Tensor #18 */
AI_TENSOR_OBJ_DECLARE(
  mul_result3_scratch0, AI_STATIC,
  18, 0x0,
  AI_SHAPE_INIT(4, 1, 64, 1, 1), AI_STRIDE_INIT(4, 2, 2, 128, 128),
  1, &mul_result3_scratch0_array, NULL)

/* Tensor #19 */
AI_TENSOR_OBJ_DECLARE(
  mul_result3_weights, AI_STATIC,
  19, 0x1,
  AI_SHAPE_INIT(4, 64, 1, 1, 1), AI_STRIDE_INIT(4, 1, 64, 64, 64),
  1, &mul_result3_weights_array, &mul_result3_weights_array_intq)

/* Tensor #20 */
AI_TENSOR_OBJ_DECLARE(
  mul_result_bias, AI_STATIC,
  20, 0x0,
  AI_SHAPE_INIT(4, 1, 128, 1, 1), AI_STRIDE_INIT(4, 4, 4, 512, 512),
  1, &mul_result_bias_array, NULL)

/* Tensor #21 */
AI_TENSOR_OBJ_DECLARE(
  mul_result_output, AI_STATIC,
  21, 0x1,
  AI_SHAPE_INIT(4, 1, 128, 1, 1), AI_STRIDE_INIT(4, 1, 1, 128, 128),
  1, &mul_result_output_array, &mul_result_output_array_intq)

/* Tensor #22 */
AI_TENSOR_OBJ_DECLARE(
  mul_result_scratch0, AI_STATIC,
  22, 0x0,
  AI_SHAPE_INIT(4, 1, 2, 1, 1), AI_STRIDE_INIT(4, 2, 2, 4, 4),
  1, &mul_result_scratch0_array, NULL)

/* Tensor #23 */
AI_TENSOR_OBJ_DECLARE(
  mul_result_weights, AI_STATIC,
  23, 0x1,
  AI_SHAPE_INIT(4, 2, 128, 1, 1), AI_STRIDE_INIT(4, 1, 2, 256, 256),
  1, &mul_result_weights_array, &mul_result_weights_array_intq)

/* Tensor #24 */
AI_TENSOR_OBJ_DECLARE(
  next_activations1_output, AI_STATIC,
  24, 0x1,
  AI_SHAPE_INIT(4, 1, 128, 1, 1), AI_STRIDE_INIT(4, 1, 1, 128, 128),
  1, &next_activations1_output_array, &next_activations1_output_array_intq)

/* Tensor #25 */
AI_TENSOR_OBJ_DECLARE(
  next_activations2_output, AI_STATIC,
  25, 0x1,
  AI_SHAPE_INIT(4, 1, 64, 1, 1), AI_STRIDE_INIT(4, 1, 1, 64, 64),
  1, &next_activations2_output_array, &next_activations2_output_array_intq)

/* Tensor #26 */
AI_TENSOR_OBJ_DECLARE(
  next_activations_output, AI_STATIC,
  26, 0x1,
  AI_SHAPE_INIT(4, 1, 128, 1, 1), AI_STRIDE_INIT(4, 1, 1, 128, 128),
  1, &next_activations_output_array, &next_activations_output_array_intq)



/**  Layer declarations section  **********************************************/


AI_TENSOR_CHAIN_OBJ_DECLARE(
  add_result3_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result3_output, &intercepts3_DequantizeLinear_Output_const),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &add_result3_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  add_result3_layer, 41,
  ELTWISE_INTEGER_TYPE, 0x0, NULL,
  eltwise_integer, forward_eltwise_integer_INT8,
  &add_result3_chain,
  NULL, &add_result3_layer, AI_STATIC, 
  .operation = ai_sum_f32, 
  .buffer_operation = ai_sum_buffer_INT8, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  mul_result3_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations2_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result3_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result3_weights, &mul_result3_bias),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result3_scratch0)
)

AI_LAYER_OBJ_DECLARE(
  mul_result3_layer, 38,
  DENSE_TYPE, 0x0, NULL,
  dense, forward_dense_integer_SSSA,
  &mul_result3_chain,
  NULL, &add_result3_layer, AI_STATIC, 
)


AI_STATIC_CONST ai_i8 next_activations2_nl_params_data[] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 3, 4, 5, 6, 8, 9, 10, 11, 13, 14, 15, 16, 18, 19, 20, 22, 23, 24, 25, 27, 28, 29, 30, 32, 33, 34, 35, 37, 38, 39, 41, 42, 43, 44, 46, 47, 48, 49, 51, 52, 53, 54, 56, 57, 58, 60, 61, 62, 63, 65, 66, 67, 68, 70, 71, 72, 73, 75, 76, 77, 79, 80, 81, 82, 84, 85, 86, 87, 89, 90, 91, 92, 94, 95, 96, 98, 99, 100, 101, 103, 104, 105, 106, 108, 109, 110, 111, 113, 114, 115, 117, 118, 119, 120, 122, 123, 124, 125, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127 };
AI_ARRAY_OBJ_DECLARE(
    next_activations2_nl_params, AI_ARRAY_FORMAT_S8,
    next_activations2_nl_params_data, next_activations2_nl_params_data, 256, AI_STATIC_CONST)
AI_TENSOR_CHAIN_OBJ_DECLARE(
  next_activations2_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &add_result2_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations2_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  next_activations2_layer, 35,
  NL_TYPE, 0x0, NULL,
  nl, forward_nl_integer,
  &next_activations2_chain,
  NULL, &mul_result3_layer, AI_STATIC, 
  .nl_params = &next_activations2_nl_params, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  add_result2_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result2_output, &intercepts2_DequantizeLinear_Output_const),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &add_result2_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  add_result2_layer, 32,
  ELTWISE_INTEGER_TYPE, 0x0, NULL,
  eltwise_integer, forward_eltwise_integer_INT8,
  &add_result2_chain,
  NULL, &next_activations2_layer, AI_STATIC, 
  .operation = ai_sum_f32, 
  .buffer_operation = ai_sum_buffer_INT8, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  mul_result2_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations1_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result2_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result2_weights, &mul_result2_bias),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result2_scratch0)
)

AI_LAYER_OBJ_DECLARE(
  mul_result2_layer, 29,
  DENSE_TYPE, 0x0, NULL,
  dense, forward_dense_integer_SSSA,
  &mul_result2_chain,
  NULL, &add_result2_layer, AI_STATIC, 
)


AI_STATIC_CONST ai_i8 next_activations1_nl_params_data[] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 31, 33, 35, 37, 39, 41, 43, 45, 47, 49, 51, 53, 55, 57, 59, 61, 63, 65, 67, 69, 71, 73, 75, 77, 79, 81, 83, 85, 87, 89, 90, 92, 94, 96, 98, 100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 122, 124, 126, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127 };
AI_ARRAY_OBJ_DECLARE(
    next_activations1_nl_params, AI_ARRAY_FORMAT_S8,
    next_activations1_nl_params_data, next_activations1_nl_params_data, 256, AI_STATIC_CONST)
AI_TENSOR_CHAIN_OBJ_DECLARE(
  next_activations1_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &add_result1_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations1_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  next_activations1_layer, 26,
  NL_TYPE, 0x0, NULL,
  nl, forward_nl_integer,
  &next_activations1_chain,
  NULL, &mul_result2_layer, AI_STATIC, 
  .nl_params = &next_activations1_nl_params, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  add_result1_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result1_output, &intercepts1_DequantizeLinear_Output_const),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &add_result1_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  add_result1_layer, 23,
  ELTWISE_INTEGER_TYPE, 0x0, NULL,
  eltwise_integer, forward_eltwise_integer_INT8,
  &add_result1_chain,
  NULL, &next_activations1_layer, AI_STATIC, 
  .operation = ai_sum_f32, 
  .buffer_operation = ai_sum_buffer_INT8, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  mul_result1_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result1_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result1_weights, &mul_result_bias),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result1_scratch0)
)

AI_LAYER_OBJ_DECLARE(
  mul_result1_layer, 20,
  DENSE_TYPE, 0x0, NULL,
  dense, forward_dense_integer_SSSA,
  &mul_result1_chain,
  NULL, &add_result1_layer, AI_STATIC, 
)


AI_STATIC_CONST ai_i8 next_activations_nl_params_data[] = { 0 };
AI_ARRAY_OBJ_DECLARE(
    next_activations_nl_params, AI_ARRAY_FORMAT_S8,
    next_activations_nl_params_data, next_activations_nl_params_data, 1, AI_STATIC_CONST)
AI_TENSOR_CHAIN_OBJ_DECLARE(
  next_activations_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &add_result_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  next_activations_layer, 17,
  NL_TYPE, 0x0, NULL,
  nl, forward_relu_integer,
  &next_activations_chain,
  NULL, &mul_result1_layer, AI_STATIC, 
  .nl_params = &next_activations_nl_params, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  add_result_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result_output, &intercepts_DequantizeLinear_Output_const),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &add_result_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  add_result_layer, 14,
  ELTWISE_INTEGER_TYPE, 0x0, NULL,
  eltwise_integer, forward_eltwise_integer_INT8,
  &add_result_chain,
  NULL, &next_activations_layer, AI_STATIC, 
  .operation = ai_sum_f32, 
  .buffer_operation = ai_sum_buffer_INT8, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  mul_result_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &dL_eps_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result_weights, &mul_result_bias),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result_scratch0)
)

AI_LAYER_OBJ_DECLARE(
  mul_result_layer, 11,
  DENSE_TYPE, 0x0, NULL,
  dense, forward_dense_integer_SSSA,
  &mul_result_chain,
  NULL, &add_result_layer, AI_STATIC, 
)


#if (AI_TOOLS_API_VERSION < AI_TOOLS_API_VERSION_1_5)

AI_NETWORK_OBJ_DECLARE(
  AI_NET_OBJ_INSTANCE, AI_STATIC,
  AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
    AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 25992, 1, 1),
    25992, NULL, NULL),
  AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
    AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 512, 1, 1),
    512, NULL, NULL),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_NETWORK_IN_NUM, &dL_eps_output),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_NETWORK_OUT_NUM, &add_result3_output),
  &mul_result_layer, 0x318aaaad, NULL)

#else

AI_NETWORK_OBJ_DECLARE(
  AI_NET_OBJ_INSTANCE, AI_STATIC,
  AI_BUFFER_ARRAY_OBJ_INIT_STATIC(
  	AI_FLAG_NONE, 1,
    AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
      AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 25992, 1, 1),
      25992, NULL, NULL)
  ),
  AI_BUFFER_ARRAY_OBJ_INIT_STATIC(
  	AI_FLAG_NONE, 1,
    AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
      AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 512, 1, 1),
      512, NULL, NULL)
  ),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_NETWORK_IN_NUM, &dL_eps_output),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_NETWORK_OUT_NUM, &add_result3_output),
  &mul_result_layer, 0x318aaaad, NULL)

#endif	/*(AI_TOOLS_API_VERSION < AI_TOOLS_API_VERSION_1_5)*/



/******************************************************************************/
AI_DECLARE_STATIC
ai_bool network_configure_activations(
  ai_network* net_ctx, const ai_network_params* params)
{
  AI_ASSERT(net_ctx)

  if (ai_platform_get_activations_map(g_network_activations_map, 1, params)) {
    /* Updating activations (byte) offsets */
    
    dL_eps_output_array.data = AI_PTR(g_network_activations_map[0] + 132);
    dL_eps_output_array.data_start = AI_PTR(g_network_activations_map[0] + 132);
    mul_result_scratch0_array.data = AI_PTR(g_network_activations_map[0] + 128);
    mul_result_scratch0_array.data_start = AI_PTR(g_network_activations_map[0] + 128);
    mul_result_output_array.data = AI_PTR(g_network_activations_map[0] + 0);
    mul_result_output_array.data_start = AI_PTR(g_network_activations_map[0] + 0);
    add_result_output_array.data = AI_PTR(g_network_activations_map[0] + 0);
    add_result_output_array.data_start = AI_PTR(g_network_activations_map[0] + 0);
    next_activations_output_array.data = AI_PTR(g_network_activations_map[0] + 0);
    next_activations_output_array.data_start = AI_PTR(g_network_activations_map[0] + 0);
    mul_result1_scratch0_array.data = AI_PTR(g_network_activations_map[0] + 128);
    mul_result1_scratch0_array.data_start = AI_PTR(g_network_activations_map[0] + 128);
    mul_result1_output_array.data = AI_PTR(g_network_activations_map[0] + 384);
    mul_result1_output_array.data_start = AI_PTR(g_network_activations_map[0] + 384);
    add_result1_output_array.data = AI_PTR(g_network_activations_map[0] + 0);
    add_result1_output_array.data_start = AI_PTR(g_network_activations_map[0] + 0);
    next_activations1_output_array.data = AI_PTR(g_network_activations_map[0] + 128);
    next_activations1_output_array.data_start = AI_PTR(g_network_activations_map[0] + 128);
    mul_result2_scratch0_array.data = AI_PTR(g_network_activations_map[0] + 256);
    mul_result2_scratch0_array.data_start = AI_PTR(g_network_activations_map[0] + 256);
    mul_result2_output_array.data = AI_PTR(g_network_activations_map[0] + 0);
    mul_result2_output_array.data_start = AI_PTR(g_network_activations_map[0] + 0);
    add_result2_output_array.data = AI_PTR(g_network_activations_map[0] + 64);
    add_result2_output_array.data_start = AI_PTR(g_network_activations_map[0] + 64);
    next_activations2_output_array.data = AI_PTR(g_network_activations_map[0] + 0);
    next_activations2_output_array.data_start = AI_PTR(g_network_activations_map[0] + 0);
    mul_result3_scratch0_array.data = AI_PTR(g_network_activations_map[0] + 64);
    mul_result3_scratch0_array.data_start = AI_PTR(g_network_activations_map[0] + 64);
    mul_result3_output_array.data = AI_PTR(g_network_activations_map[0] + 192);
    mul_result3_output_array.data_start = AI_PTR(g_network_activations_map[0] + 192);
    add_result3_output_array.data = AI_PTR(g_network_activations_map[0] + 0);
    add_result3_output_array.data_start = AI_PTR(g_network_activations_map[0] + 0);
    return true;
  }
  AI_ERROR_TRAP(net_ctx, INIT_FAILED, NETWORK_ACTIVATIONS);
  return false;
}




/******************************************************************************/
AI_DECLARE_STATIC
ai_bool network_configure_weights(
  ai_network* net_ctx, const ai_network_params* params)
{
  AI_ASSERT(net_ctx)

  if (ai_platform_get_weights_map(g_network_weights_map, 1, params)) {
    /* Updating weights (byte) offsets */
    
    intercepts1_DequantizeLinear_Output_const_array.format |= AI_FMT_FLAG_CONST;
    intercepts1_DequantizeLinear_Output_const_array.data = AI_PTR(g_network_weights_map[0] + 0);
    intercepts1_DequantizeLinear_Output_const_array.data_start = AI_PTR(g_network_weights_map[0] + 0);
    intercepts2_DequantizeLinear_Output_const_array.format |= AI_FMT_FLAG_CONST;
    intercepts2_DequantizeLinear_Output_const_array.data = AI_PTR(g_network_weights_map[0] + 128);
    intercepts2_DequantizeLinear_Output_const_array.data_start = AI_PTR(g_network_weights_map[0] + 128);
    intercepts3_DequantizeLinear_Output_const_array.format |= AI_FMT_FLAG_CONST;
    intercepts3_DequantizeLinear_Output_const_array.data = AI_PTR(g_network_weights_map[0] + 192);
    intercepts3_DequantizeLinear_Output_const_array.data_start = AI_PTR(g_network_weights_map[0] + 192);
    intercepts_DequantizeLinear_Output_const_array.format |= AI_FMT_FLAG_CONST;
    intercepts_DequantizeLinear_Output_const_array.data = AI_PTR(g_network_weights_map[0] + 196);
    intercepts_DequantizeLinear_Output_const_array.data_start = AI_PTR(g_network_weights_map[0] + 196);
    mul_result_weights_array.format |= AI_FMT_FLAG_CONST;
    mul_result_weights_array.data = AI_PTR(g_network_weights_map[0] + 324);
    mul_result_weights_array.data_start = AI_PTR(g_network_weights_map[0] + 324);
    mul_result_bias_array.format |= AI_FMT_FLAG_CONST;
    mul_result_bias_array.data = AI_PTR(g_network_weights_map[0] + 580);
    mul_result_bias_array.data_start = AI_PTR(g_network_weights_map[0] + 580);
    mul_result1_weights_array.format |= AI_FMT_FLAG_CONST;
    mul_result1_weights_array.data = AI_PTR(g_network_weights_map[0] + 1092);
    mul_result1_weights_array.data_start = AI_PTR(g_network_weights_map[0] + 1092);
    mul_result2_weights_array.format |= AI_FMT_FLAG_CONST;
    mul_result2_weights_array.data = AI_PTR(g_network_weights_map[0] + 17476);
    mul_result2_weights_array.data_start = AI_PTR(g_network_weights_map[0] + 17476);
    mul_result2_bias_array.format |= AI_FMT_FLAG_CONST;
    mul_result2_bias_array.data = AI_PTR(g_network_weights_map[0] + 25668);
    mul_result2_bias_array.data_start = AI_PTR(g_network_weights_map[0] + 25668);
    mul_result3_weights_array.format |= AI_FMT_FLAG_CONST;
    mul_result3_weights_array.data = AI_PTR(g_network_weights_map[0] + 25924);
    mul_result3_weights_array.data_start = AI_PTR(g_network_weights_map[0] + 25924);
    mul_result3_bias_array.format |= AI_FMT_FLAG_CONST;
    mul_result3_bias_array.data = AI_PTR(g_network_weights_map[0] + 25988);
    mul_result3_bias_array.data_start = AI_PTR(g_network_weights_map[0] + 25988);
    return true;
  }
  AI_ERROR_TRAP(net_ctx, INIT_FAILED, NETWORK_WEIGHTS);
  return false;
}


/**  PUBLIC APIs SECTION  *****************************************************/



AI_DEPRECATED
AI_API_ENTRY
ai_bool ai_network_get_info(
  ai_handle network, ai_network_report* report)
{
  ai_network* net_ctx = AI_NETWORK_ACQUIRE_CTX(network);

  if (report && net_ctx)
  {
    ai_network_report r = {
      .model_name        = AI_NETWORK_MODEL_NAME,
      .model_signature   = AI_NETWORK_MODEL_SIGNATURE,
      .model_datetime    = AI_TOOLS_DATE_TIME,
      
      .compile_datetime  = AI_TOOLS_COMPILE_TIME,
      
      .runtime_revision  = ai_platform_runtime_get_revision(),
      .runtime_version   = ai_platform_runtime_get_version(),

      .tool_revision     = AI_TOOLS_REVISION_ID,
      .tool_version      = {AI_TOOLS_VERSION_MAJOR, AI_TOOLS_VERSION_MINOR,
                            AI_TOOLS_VERSION_MICRO, 0x0},
      .tool_api_version  = AI_STRUCT_INIT,

      .api_version            = ai_platform_api_get_version(),
      .interface_api_version  = ai_platform_interface_api_get_version(),
      
      .n_macc            = 25858,
      .n_inputs          = 0,
      .inputs            = NULL,
      .n_outputs         = 0,
      .outputs           = NULL,
      .params            = AI_STRUCT_INIT,
      .activations       = AI_STRUCT_INIT,
      .n_nodes           = 0,
      .signature         = 0x318aaaad,
    };

    if (!ai_platform_api_get_network_report(network, &r)) return false;

    *report = r;
    return true;
  }
  return false;
}



AI_API_ENTRY
ai_bool ai_network_get_report(
  ai_handle network, ai_network_report* report)
{
  ai_network* net_ctx = AI_NETWORK_ACQUIRE_CTX(network);

  if (report && net_ctx)
  {
    ai_network_report r = {
      .model_name        = AI_NETWORK_MODEL_NAME,
      .model_signature   = AI_NETWORK_MODEL_SIGNATURE,
      .model_datetime    = AI_TOOLS_DATE_TIME,
      
      .compile_datetime  = AI_TOOLS_COMPILE_TIME,
      
      .runtime_revision  = ai_platform_runtime_get_revision(),
      .runtime_version   = ai_platform_runtime_get_version(),

      .tool_revision     = AI_TOOLS_REVISION_ID,
      .tool_version      = {AI_TOOLS_VERSION_MAJOR, AI_TOOLS_VERSION_MINOR,
                            AI_TOOLS_VERSION_MICRO, 0x0},
      .tool_api_version  = AI_STRUCT_INIT,

      .api_version            = ai_platform_api_get_version(),
      .interface_api_version  = ai_platform_interface_api_get_version(),
      
      .n_macc            = 25858,
      .n_inputs          = 0,
      .inputs            = NULL,
      .n_outputs         = 0,
      .outputs           = NULL,
      .map_signature     = AI_MAGIC_SIGNATURE,
      .map_weights       = AI_STRUCT_INIT,
      .map_activations   = AI_STRUCT_INIT,
      .n_nodes           = 0,
      .signature         = 0x318aaaad,
    };

    if (!ai_platform_api_get_network_report(network, &r)) return false;

    *report = r;
    return true;
  }
  return false;
}


AI_API_ENTRY
ai_error ai_network_get_error(ai_handle network)
{
  return ai_platform_network_get_error(network);
}


AI_API_ENTRY
ai_error ai_network_create(
  ai_handle* network, const ai_buffer* network_config)
{
  return ai_platform_network_create(
    network, network_config, 
    AI_CONTEXT_OBJ(&AI_NET_OBJ_INSTANCE),
    AI_TOOLS_API_VERSION_MAJOR, AI_TOOLS_API_VERSION_MINOR, AI_TOOLS_API_VERSION_MICRO);
}


AI_API_ENTRY
ai_error ai_network_create_and_init(
  ai_handle* network, const ai_handle activations[], const ai_handle weights[])
{
  ai_error err;
  ai_network_params params;

  err = ai_network_create(network, AI_NETWORK_DATA_CONFIG);
  if (err.type != AI_ERROR_NONE) {
    return err;
  }
  
  if (ai_network_data_params_get(&params) != true) {
    err = ai_network_get_error(*network);
    return err;
  }
#if defined(AI_NETWORK_DATA_ACTIVATIONS_COUNT)
  /* set the addresses of the activations buffers */
  for (ai_u16 idx=0; activations && idx<params.map_activations.size; idx++) {
    AI_BUFFER_ARRAY_ITEM_SET_ADDRESS(&params.map_activations, idx, activations[idx]);
  }
#endif
#if defined(AI_NETWORK_DATA_WEIGHTS_COUNT)
  /* set the addresses of the weight buffers */
  for (ai_u16 idx=0; weights && idx<params.map_weights.size; idx++) {
    AI_BUFFER_ARRAY_ITEM_SET_ADDRESS(&params.map_weights, idx, weights[idx]);
  }
#endif
  if (ai_network_init(*network, &params) != true) {
    err = ai_network_get_error(*network);
  }
  return err;
}


AI_API_ENTRY
ai_buffer* ai_network_inputs_get(ai_handle network, ai_u16 *n_buffer)
{
  if (network == AI_HANDLE_NULL) {
    network = (ai_handle)&AI_NET_OBJ_INSTANCE;
    AI_NETWORK_OBJ(network)->magic = AI_MAGIC_CONTEXT_TOKEN;
  }
  return ai_platform_inputs_get(network, n_buffer);
}


AI_API_ENTRY
ai_buffer* ai_network_outputs_get(ai_handle network, ai_u16 *n_buffer)
{
  if (network == AI_HANDLE_NULL) {
    network = (ai_handle)&AI_NET_OBJ_INSTANCE;
    AI_NETWORK_OBJ(network)->magic = AI_MAGIC_CONTEXT_TOKEN;
  }
  return ai_platform_outputs_get(network, n_buffer);
}


AI_API_ENTRY
ai_handle ai_network_destroy(ai_handle network)
{
  return ai_platform_network_destroy(network);
}


AI_API_ENTRY
ai_bool ai_network_init(
  ai_handle network, const ai_network_params* params)
{
  ai_network* net_ctx = AI_NETWORK_OBJ(ai_platform_network_init(network, params));
  ai_bool ok = true;

  if (!net_ctx) return false;
  ok &= network_configure_weights(net_ctx, params);
  ok &= network_configure_activations(net_ctx, params);

  ok &= ai_platform_network_post_init(network);

  return ok;
}


AI_API_ENTRY
ai_i32 ai_network_run(
  ai_handle network, const ai_buffer* input, ai_buffer* output)
{
  return ai_platform_network_process(network, input, output);
}


AI_API_ENTRY
ai_i32 ai_network_forward(ai_handle network, const ai_buffer* input)
{
  return ai_platform_network_process(network, input, NULL);
}



#undef AI_NETWORK_MODEL_SIGNATURE
#undef AI_NET_OBJ_INSTANCE
#undef AI_TOOLS_DATE_TIME
#undef AI_TOOLS_COMPILE_TIME

