/**
  ******************************************************************************
  * @file    gate.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-08-17T01:44:25+0900
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


#include "gate.h"
#include "gate_data.h"

#include "ai_platform.h"
#include "ai_platform_interface.h"
#include "ai_math_helpers.h"

#include "core_common.h"
#include "core_convert.h"

#include "layers.h"



#undef AI_NET_OBJ_INSTANCE
#define AI_NET_OBJ_INSTANCE g_gate
 
#undef AI_GATE_MODEL_SIGNATURE
#define AI_GATE_MODEL_SIGNATURE     "0xb7fe39ede4d6b285a453ab0291c0a7a9"

#ifndef AI_TOOLS_REVISION_ID
#define AI_TOOLS_REVISION_ID     ""
#endif

#undef AI_TOOLS_DATE_TIME
#define AI_TOOLS_DATE_TIME   "2026-08-17T01:44:25+0900"

#undef AI_TOOLS_COMPILE_TIME
#define AI_TOOLS_COMPILE_TIME    __DATE__ " " __TIME__

#undef AI_GATE_N_BATCHES
#define AI_GATE_N_BATCHES         (1)

static ai_ptr g_gate_activations_map[1] = AI_C_ARRAY_INIT;
static ai_ptr g_gate_weights_map[1] = AI_C_ARRAY_INIT;



/**  Array declarations section  **********************************************/
/* Array#0 */
AI_ARRAY_OBJ_DECLARE(
  x_output_array, AI_ARRAY_FORMAT_FLOAT|AI_FMT_FLAG_IS_IO,
  NULL, NULL, 2, AI_STATIC)

/* Array#1 */
AI_ARRAY_OBJ_DECLARE(
  mul_result_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 8, AI_STATIC)

/* Array#2 */
AI_ARRAY_OBJ_DECLARE(
  next_activations_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 8, AI_STATIC)

/* Array#3 */
AI_ARRAY_OBJ_DECLARE(
  mul_result1_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 4, AI_STATIC)

/* Array#4 */
AI_ARRAY_OBJ_DECLARE(
  next_activations1_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 4, AI_STATIC)

/* Array#5 */
AI_ARRAY_OBJ_DECLARE(
  mul_result2_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 1, AI_STATIC)

/* Array#6 */
AI_ARRAY_OBJ_DECLARE(
  out_activations_result_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 1, AI_STATIC)

/* Array#7 */
AI_ARRAY_OBJ_DECLARE(
  negative_class_proba_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 1, AI_STATIC)

/* Array#8 */
AI_ARRAY_OBJ_DECLARE(
  probabilities_output_array, AI_ARRAY_FORMAT_FLOAT|AI_FMT_FLAG_IS_IO,
  NULL, NULL, 2, AI_STATIC)

/* Array#9 */
AI_ARRAY_OBJ_DECLARE(
  argmax_output_output_array, AI_ARRAY_FORMAT_S32,
  NULL, NULL, 1, AI_STATIC)

/* Array#10 */
AI_ARRAY_OBJ_DECLARE(
  classes_0_cast_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 2, AI_STATIC)

/* Array#11 */
AI_ARRAY_OBJ_DECLARE(
  array_feature_extractor_result_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 1, AI_STATIC)

/* Array#12 */
AI_ARRAY_OBJ_DECLARE(
  label_output_array, AI_ARRAY_FORMAT_S32|AI_FMT_FLAG_IS_IO,
  NULL, NULL, 1, AI_STATIC)

/* Array#13 */
AI_ARRAY_OBJ_DECLARE(
  unity_2D_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 1, AI_STATIC)

/* Array#14 */
AI_ARRAY_OBJ_DECLARE(
  mul_result_weights_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 16, AI_STATIC)

/* Array#15 */
AI_ARRAY_OBJ_DECLARE(
  mul_result_bias_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 8, AI_STATIC)

/* Array#16 */
AI_ARRAY_OBJ_DECLARE(
  mul_result1_weights_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 32, AI_STATIC)

/* Array#17 */
AI_ARRAY_OBJ_DECLARE(
  mul_result1_bias_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 4, AI_STATIC)

/* Array#18 */
AI_ARRAY_OBJ_DECLARE(
  mul_result2_weights_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 4, AI_STATIC)

/* Array#19 */
AI_ARRAY_OBJ_DECLARE(
  mul_result2_bias_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 1, AI_STATIC)

/* Array#20 */
AI_ARRAY_OBJ_DECLARE(
  classes_array, AI_ARRAY_FORMAT_S32,
  NULL, NULL, 2, AI_STATIC)

/**  Tensor declarations section  *********************************************/
/* Tensor #0 */
AI_TENSOR_OBJ_DECLARE(
  argmax_output_output, AI_STATIC,
  0, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &argmax_output_output_array, NULL)

/* Tensor #1 */
AI_TENSOR_OBJ_DECLARE(
  array_feature_extractor_result_output, AI_STATIC,
  1, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &array_feature_extractor_result_output_array, NULL)

/* Tensor #2 */
AI_TENSOR_OBJ_DECLARE(
  classes, AI_STATIC,
  2, 0x0,
  AI_SHAPE_INIT(4, 1, 2, 1, 1), AI_STRIDE_INIT(4, 4, 4, 8, 8),
  1, &classes_array, NULL)

/* Tensor #3 */
AI_TENSOR_OBJ_DECLARE(
  classes_0_cast_output, AI_STATIC,
  3, 0x0,
  AI_SHAPE_INIT(4, 1, 2, 1, 1), AI_STRIDE_INIT(4, 4, 4, 8, 8),
  1, &classes_0_cast_output_array, NULL)

/* Tensor #4 */
AI_TENSOR_OBJ_DECLARE(
  label_output, AI_STATIC,
  4, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &label_output_array, NULL)

/* Tensor #5 */
AI_TENSOR_OBJ_DECLARE(
  mul_result1_bias, AI_STATIC,
  5, 0x0,
  AI_SHAPE_INIT(4, 1, 4, 1, 1), AI_STRIDE_INIT(4, 4, 4, 16, 16),
  1, &mul_result1_bias_array, NULL)

/* Tensor #6 */
AI_TENSOR_OBJ_DECLARE(
  mul_result1_output, AI_STATIC,
  6, 0x0,
  AI_SHAPE_INIT(4, 1, 4, 1, 1), AI_STRIDE_INIT(4, 4, 4, 16, 16),
  1, &mul_result1_output_array, NULL)

/* Tensor #7 */
AI_TENSOR_OBJ_DECLARE(
  mul_result1_weights, AI_STATIC,
  7, 0x0,
  AI_SHAPE_INIT(4, 8, 4, 1, 1), AI_STRIDE_INIT(4, 4, 32, 128, 128),
  1, &mul_result1_weights_array, NULL)

/* Tensor #8 */
AI_TENSOR_OBJ_DECLARE(
  mul_result2_bias, AI_STATIC,
  8, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &mul_result2_bias_array, NULL)

/* Tensor #9 */
AI_TENSOR_OBJ_DECLARE(
  mul_result2_output, AI_STATIC,
  9, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &mul_result2_output_array, NULL)

/* Tensor #10 */
AI_TENSOR_OBJ_DECLARE(
  mul_result2_weights, AI_STATIC,
  10, 0x0,
  AI_SHAPE_INIT(4, 4, 1, 1, 1), AI_STRIDE_INIT(4, 4, 16, 16, 16),
  1, &mul_result2_weights_array, NULL)

/* Tensor #11 */
AI_TENSOR_OBJ_DECLARE(
  mul_result_bias, AI_STATIC,
  11, 0x0,
  AI_SHAPE_INIT(4, 1, 8, 1, 1), AI_STRIDE_INIT(4, 4, 4, 32, 32),
  1, &mul_result_bias_array, NULL)

/* Tensor #12 */
AI_TENSOR_OBJ_DECLARE(
  mul_result_output, AI_STATIC,
  12, 0x0,
  AI_SHAPE_INIT(4, 1, 8, 1, 1), AI_STRIDE_INIT(4, 4, 4, 32, 32),
  1, &mul_result_output_array, NULL)

/* Tensor #13 */
AI_TENSOR_OBJ_DECLARE(
  mul_result_weights, AI_STATIC,
  13, 0x0,
  AI_SHAPE_INIT(4, 2, 8, 1, 1), AI_STRIDE_INIT(4, 4, 8, 64, 64),
  1, &mul_result_weights_array, NULL)

/* Tensor #14 */
AI_TENSOR_OBJ_DECLARE(
  negative_class_proba_output, AI_STATIC,
  14, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &negative_class_proba_output_array, NULL)

/* Tensor #15 */
AI_TENSOR_OBJ_DECLARE(
  next_activations1_output, AI_STATIC,
  15, 0x0,
  AI_SHAPE_INIT(4, 1, 4, 1, 1), AI_STRIDE_INIT(4, 4, 4, 16, 16),
  1, &next_activations1_output_array, NULL)

/* Tensor #16 */
AI_TENSOR_OBJ_DECLARE(
  next_activations_output, AI_STATIC,
  16, 0x0,
  AI_SHAPE_INIT(4, 1, 8, 1, 1), AI_STRIDE_INIT(4, 4, 4, 32, 32),
  1, &next_activations_output_array, NULL)

/* Tensor #17 */
AI_TENSOR_OBJ_DECLARE(
  out_activations_result_output, AI_STATIC,
  17, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &out_activations_result_output_array, NULL)

/* Tensor #18 */
AI_TENSOR_OBJ_DECLARE(
  probabilities_output, AI_STATIC,
  18, 0x0,
  AI_SHAPE_INIT(4, 1, 2, 1, 1), AI_STRIDE_INIT(4, 4, 4, 8, 8),
  1, &probabilities_output_array, NULL)

/* Tensor #19 */
AI_TENSOR_OBJ_DECLARE(
  unity_2D, AI_STATIC,
  19, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &unity_2D_array, NULL)

/* Tensor #20 */
AI_TENSOR_OBJ_DECLARE(
  x_output, AI_STATIC,
  20, 0x0,
  AI_SHAPE_INIT(4, 1, 2, 1, 1), AI_STRIDE_INIT(4, 4, 4, 8, 8),
  1, &x_output_array, NULL)



/**  Layer declarations section  **********************************************/


AI_TENSOR_CHAIN_OBJ_DECLARE(
  label_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &array_feature_extractor_result_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &label_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  label_layer, 15,
  CAST_TYPE, 0x0, NULL,
  cast, forward_cast,
  &label_chain,
  NULL, &label_layer, AI_STATIC, 
  .to_format = AI_ARRAY_FORMAT_S32, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  array_feature_extractor_result_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &classes_0_cast_output, &argmax_output_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &array_feature_extractor_result_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  array_feature_extractor_result_layer, 13,
  ARRAYFEATUREEXTRACTOR_TYPE, 0x0, NULL,
  arrayfeatureextractor, forward_arrayfeatureextractor,
  &array_feature_extractor_result_chain,
  NULL, &label_layer, AI_STATIC, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  classes_0_cast_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &classes),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &classes_0_cast_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  classes_0_cast_layer, 13,
  CAST_TYPE, 0x0, NULL,
  cast, forward_cast,
  &classes_0_cast_chain,
  NULL, &array_feature_extractor_result_layer, AI_STATIC, 
  .to_format = AI_ARRAY_FORMAT_FLOAT, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  argmax_output_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &probabilities_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &argmax_output_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  argmax_output_layer, 12,
  ARGMINMAX_TYPE, 0x0, NULL,
  argminmax, forward_argmax,
  &argmax_output_chain,
  NULL, &classes_0_cast_layer, AI_STATIC, 
  .axis = AI_SHAPE_CHANNEL, 
  .select_last_index = 0, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  probabilities_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &negative_class_proba_output, &out_activations_result_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &probabilities_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  probabilities_layer, 11,
  CONCAT_TYPE, 0x0, NULL,
  concat, forward_concat,
  &probabilities_chain,
  NULL, &argmax_output_layer, AI_STATIC, 
  .axis = AI_SHAPE_CHANNEL, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  negative_class_proba_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &unity_2D, &out_activations_result_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &negative_class_proba_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  negative_class_proba_layer, 10,
  ELTWISE_TYPE, 0x0, NULL,
  eltwise, forward_eltwise,
  &negative_class_proba_chain,
  NULL, &probabilities_layer, AI_STATIC, 
  .operation = ai_sub_f32, 
  .buffer_operation = ai_sub_buffer_f32, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  out_activations_result_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result2_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &out_activations_result_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  out_activations_result_layer, 9,
  NL_TYPE, 0x0, NULL,
  nl, forward_sigmoid,
  &out_activations_result_chain,
  NULL, &negative_class_proba_layer, AI_STATIC, 
  .nl_params = NULL, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  mul_result2_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations1_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result2_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result2_weights, &mul_result2_bias),
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  mul_result2_layer, 8,
  DENSE_TYPE, 0x0, NULL,
  dense, forward_dense,
  &mul_result2_chain,
  NULL, &out_activations_result_layer, AI_STATIC, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  next_activations1_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result1_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations1_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  next_activations1_layer, 6,
  NL_TYPE, 0x0, NULL,
  nl, forward_tanh,
  &next_activations1_chain,
  NULL, &mul_result2_layer, AI_STATIC, 
  .nl_params = NULL, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  mul_result1_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result1_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result1_weights, &mul_result1_bias),
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  mul_result1_layer, 5,
  DENSE_TYPE, 0x0, NULL,
  dense, forward_dense,
  &mul_result1_chain,
  NULL, &next_activations1_layer, AI_STATIC, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  next_activations_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  next_activations_layer, 3,
  NL_TYPE, 0x0, NULL,
  nl, forward_tanh,
  &next_activations_chain,
  NULL, &mul_result1_layer, AI_STATIC, 
  .nl_params = NULL, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  mul_result_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &x_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result_weights, &mul_result_bias),
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  mul_result_layer, 2,
  DENSE_TYPE, 0x0, NULL,
  dense, forward_dense,
  &mul_result_chain,
  NULL, &next_activations_layer, AI_STATIC, 
)


#if (AI_TOOLS_API_VERSION < AI_TOOLS_API_VERSION_1_5)

AI_NETWORK_OBJ_DECLARE(
  AI_NET_OBJ_INSTANCE, AI_STATIC,
  AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
    AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 272, 1, 1),
    272, NULL, NULL),
  AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
    AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 48, 1, 1),
    48, NULL, NULL),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_GATE_IN_NUM, &x_output),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_GATE_OUT_NUM, &label_output, &probabilities_output),
  &mul_result_layer, 0xa750dcce, NULL)

#else

AI_NETWORK_OBJ_DECLARE(
  AI_NET_OBJ_INSTANCE, AI_STATIC,
  AI_BUFFER_ARRAY_OBJ_INIT_STATIC(
  	AI_FLAG_NONE, 1,
    AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
      AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 272, 1, 1),
      272, NULL, NULL)
  ),
  AI_BUFFER_ARRAY_OBJ_INIT_STATIC(
  	AI_FLAG_NONE, 1,
    AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
      AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 48, 1, 1),
      48, NULL, NULL)
  ),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_GATE_IN_NUM, &x_output),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_GATE_OUT_NUM, &label_output, &probabilities_output),
  &mul_result_layer, 0xa750dcce, NULL)

#endif	/*(AI_TOOLS_API_VERSION < AI_TOOLS_API_VERSION_1_5)*/



/******************************************************************************/
AI_DECLARE_STATIC
ai_bool gate_configure_activations(
  ai_network* net_ctx, const ai_network_params* params)
{
  AI_ASSERT(net_ctx)

  if (ai_platform_get_activations_map(g_gate_activations_map, 1, params)) {
    /* Updating activations (byte) offsets */
    
    x_output_array.data = AI_PTR(g_gate_activations_map[0] + 8);
    x_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 8);
    mul_result_output_array.data = AI_PTR(g_gate_activations_map[0] + 16);
    mul_result_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 16);
    next_activations_output_array.data = AI_PTR(g_gate_activations_map[0] + 16);
    next_activations_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 16);
    mul_result1_output_array.data = AI_PTR(g_gate_activations_map[0] + 0);
    mul_result1_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 0);
    next_activations1_output_array.data = AI_PTR(g_gate_activations_map[0] + 16);
    next_activations1_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 16);
    mul_result2_output_array.data = AI_PTR(g_gate_activations_map[0] + 0);
    mul_result2_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 0);
    out_activations_result_output_array.data = AI_PTR(g_gate_activations_map[0] + 4);
    out_activations_result_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 4);
    negative_class_proba_output_array.data = AI_PTR(g_gate_activations_map[0] + 0);
    negative_class_proba_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 0);
    probabilities_output_array.data = AI_PTR(g_gate_activations_map[0] + 8);
    probabilities_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 8);
    argmax_output_output_array.data = AI_PTR(g_gate_activations_map[0] + 0);
    argmax_output_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 0);
    classes_0_cast_output_array.data = AI_PTR(g_gate_activations_map[0] + 16);
    classes_0_cast_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 16);
    array_feature_extractor_result_output_array.data = AI_PTR(g_gate_activations_map[0] + 4);
    array_feature_extractor_result_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 4);
    label_output_array.data = AI_PTR(g_gate_activations_map[0] + 0);
    label_output_array.data_start = AI_PTR(g_gate_activations_map[0] + 0);
    return true;
  }
  AI_ERROR_TRAP(net_ctx, INIT_FAILED, NETWORK_ACTIVATIONS);
  return false;
}




/******************************************************************************/
AI_DECLARE_STATIC
ai_bool gate_configure_weights(
  ai_network* net_ctx, const ai_network_params* params)
{
  AI_ASSERT(net_ctx)

  if (ai_platform_get_weights_map(g_gate_weights_map, 1, params)) {
    /* Updating weights (byte) offsets */
    
    unity_2D_array.format |= AI_FMT_FLAG_CONST;
    unity_2D_array.data = AI_PTR(g_gate_weights_map[0] + 0);
    unity_2D_array.data_start = AI_PTR(g_gate_weights_map[0] + 0);
    mul_result_weights_array.format |= AI_FMT_FLAG_CONST;
    mul_result_weights_array.data = AI_PTR(g_gate_weights_map[0] + 4);
    mul_result_weights_array.data_start = AI_PTR(g_gate_weights_map[0] + 4);
    mul_result_bias_array.format |= AI_FMT_FLAG_CONST;
    mul_result_bias_array.data = AI_PTR(g_gate_weights_map[0] + 68);
    mul_result_bias_array.data_start = AI_PTR(g_gate_weights_map[0] + 68);
    mul_result1_weights_array.format |= AI_FMT_FLAG_CONST;
    mul_result1_weights_array.data = AI_PTR(g_gate_weights_map[0] + 100);
    mul_result1_weights_array.data_start = AI_PTR(g_gate_weights_map[0] + 100);
    mul_result1_bias_array.format |= AI_FMT_FLAG_CONST;
    mul_result1_bias_array.data = AI_PTR(g_gate_weights_map[0] + 228);
    mul_result1_bias_array.data_start = AI_PTR(g_gate_weights_map[0] + 228);
    mul_result2_weights_array.format |= AI_FMT_FLAG_CONST;
    mul_result2_weights_array.data = AI_PTR(g_gate_weights_map[0] + 244);
    mul_result2_weights_array.data_start = AI_PTR(g_gate_weights_map[0] + 244);
    mul_result2_bias_array.format |= AI_FMT_FLAG_CONST;
    mul_result2_bias_array.data = AI_PTR(g_gate_weights_map[0] + 260);
    mul_result2_bias_array.data_start = AI_PTR(g_gate_weights_map[0] + 260);
    classes_array.format |= AI_FMT_FLAG_CONST;
    classes_array.data = AI_PTR(g_gate_weights_map[0] + 264);
    classes_array.data_start = AI_PTR(g_gate_weights_map[0] + 264);
    return true;
  }
  AI_ERROR_TRAP(net_ctx, INIT_FAILED, NETWORK_WEIGHTS);
  return false;
}


/**  PUBLIC APIs SECTION  *****************************************************/



AI_DEPRECATED
AI_API_ENTRY
ai_bool ai_gate_get_info(
  ai_handle network, ai_network_report* report)
{
  ai_network* net_ctx = AI_NETWORK_ACQUIRE_CTX(network);

  if (report && net_ctx)
  {
    ai_network_report r = {
      .model_name        = AI_GATE_MODEL_NAME,
      .model_signature   = AI_GATE_MODEL_SIGNATURE,
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
      
      .n_macc            = 202,
      .n_inputs          = 0,
      .inputs            = NULL,
      .n_outputs         = 0,
      .outputs           = NULL,
      .params            = AI_STRUCT_INIT,
      .activations       = AI_STRUCT_INIT,
      .n_nodes           = 0,
      .signature         = 0xa750dcce,
    };

    if (!ai_platform_api_get_network_report(network, &r)) return false;

    *report = r;
    return true;
  }
  return false;
}



AI_API_ENTRY
ai_bool ai_gate_get_report(
  ai_handle network, ai_network_report* report)
{
  ai_network* net_ctx = AI_NETWORK_ACQUIRE_CTX(network);

  if (report && net_ctx)
  {
    ai_network_report r = {
      .model_name        = AI_GATE_MODEL_NAME,
      .model_signature   = AI_GATE_MODEL_SIGNATURE,
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
      
      .n_macc            = 202,
      .n_inputs          = 0,
      .inputs            = NULL,
      .n_outputs         = 0,
      .outputs           = NULL,
      .map_signature     = AI_MAGIC_SIGNATURE,
      .map_weights       = AI_STRUCT_INIT,
      .map_activations   = AI_STRUCT_INIT,
      .n_nodes           = 0,
      .signature         = 0xa750dcce,
    };

    if (!ai_platform_api_get_network_report(network, &r)) return false;

    *report = r;
    return true;
  }
  return false;
}


AI_API_ENTRY
ai_error ai_gate_get_error(ai_handle network)
{
  return ai_platform_network_get_error(network);
}


AI_API_ENTRY
ai_error ai_gate_create(
  ai_handle* network, const ai_buffer* network_config)
{
  return ai_platform_network_create(
    network, network_config, 
    AI_CONTEXT_OBJ(&AI_NET_OBJ_INSTANCE),
    AI_TOOLS_API_VERSION_MAJOR, AI_TOOLS_API_VERSION_MINOR, AI_TOOLS_API_VERSION_MICRO);
}


AI_API_ENTRY
ai_error ai_gate_create_and_init(
  ai_handle* network, const ai_handle activations[], const ai_handle weights[])
{
  ai_error err;
  ai_network_params params;

  err = ai_gate_create(network, AI_GATE_DATA_CONFIG);
  if (err.type != AI_ERROR_NONE) {
    return err;
  }
  
  if (ai_gate_data_params_get(&params) != true) {
    err = ai_gate_get_error(*network);
    return err;
  }
#if defined(AI_GATE_DATA_ACTIVATIONS_COUNT)
  /* set the addresses of the activations buffers */
  for (ai_u16 idx=0; activations && idx<params.map_activations.size; idx++) {
    AI_BUFFER_ARRAY_ITEM_SET_ADDRESS(&params.map_activations, idx, activations[idx]);
  }
#endif
#if defined(AI_GATE_DATA_WEIGHTS_COUNT)
  /* set the addresses of the weight buffers */
  for (ai_u16 idx=0; weights && idx<params.map_weights.size; idx++) {
    AI_BUFFER_ARRAY_ITEM_SET_ADDRESS(&params.map_weights, idx, weights[idx]);
  }
#endif
  if (ai_gate_init(*network, &params) != true) {
    err = ai_gate_get_error(*network);
  }
  return err;
}


AI_API_ENTRY
ai_buffer* ai_gate_inputs_get(ai_handle network, ai_u16 *n_buffer)
{
  if (network == AI_HANDLE_NULL) {
    network = (ai_handle)&AI_NET_OBJ_INSTANCE;
    AI_NETWORK_OBJ(network)->magic = AI_MAGIC_CONTEXT_TOKEN;
  }
  return ai_platform_inputs_get(network, n_buffer);
}


AI_API_ENTRY
ai_buffer* ai_gate_outputs_get(ai_handle network, ai_u16 *n_buffer)
{
  if (network == AI_HANDLE_NULL) {
    network = (ai_handle)&AI_NET_OBJ_INSTANCE;
    AI_NETWORK_OBJ(network)->magic = AI_MAGIC_CONTEXT_TOKEN;
  }
  return ai_platform_outputs_get(network, n_buffer);
}


AI_API_ENTRY
ai_handle ai_gate_destroy(ai_handle network)
{
  return ai_platform_network_destroy(network);
}


AI_API_ENTRY
ai_bool ai_gate_init(
  ai_handle network, const ai_network_params* params)
{
  ai_network* net_ctx = AI_NETWORK_OBJ(ai_platform_network_init(network, params));
  ai_bool ok = true;

  if (!net_ctx) return false;
  ok &= gate_configure_weights(net_ctx, params);
  ok &= gate_configure_activations(net_ctx, params);

  ok &= ai_platform_network_post_init(network);

  return ok;
}


AI_API_ENTRY
ai_i32 ai_gate_run(
  ai_handle network, const ai_buffer* input, ai_buffer* output)
{
  return ai_platform_network_process(network, input, output);
}


AI_API_ENTRY
ai_i32 ai_gate_forward(ai_handle network, const ai_buffer* input)
{
  return ai_platform_network_process(network, input, NULL);
}



#undef AI_GATE_MODEL_SIGNATURE
#undef AI_NET_OBJ_INSTANCE
#undef AI_TOOLS_DATE_TIME
#undef AI_TOOLS_COMPILE_TIME

