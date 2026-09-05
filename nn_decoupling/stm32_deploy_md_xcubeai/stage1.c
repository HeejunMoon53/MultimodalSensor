/**
  ******************************************************************************
  * @file    stage1.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-06-11T16:43:16+0900
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


#include "stage1.h"
#include "stage1_data.h"

#include "ai_platform.h"
#include "ai_platform_interface.h"
#include "ai_math_helpers.h"

#include "core_common.h"
#include "core_convert.h"

#include "layers.h"



#undef AI_NET_OBJ_INSTANCE
#define AI_NET_OBJ_INSTANCE g_stage1
 
#undef AI_STAGE1_MODEL_SIGNATURE
#define AI_STAGE1_MODEL_SIGNATURE     "0xe56d96b3edc7696495dc494b901b58a2"

#ifndef AI_TOOLS_REVISION_ID
#define AI_TOOLS_REVISION_ID     ""
#endif

#undef AI_TOOLS_DATE_TIME
#define AI_TOOLS_DATE_TIME   "2026-06-11T16:43:16+0900"

#undef AI_TOOLS_COMPILE_TIME
#define AI_TOOLS_COMPILE_TIME    __DATE__ " " __TIME__

#undef AI_STAGE1_N_BATCHES
#define AI_STAGE1_N_BATCHES         (1)

static ai_ptr g_stage1_activations_map[1] = AI_C_ARRAY_INIT;
static ai_ptr g_stage1_weights_map[1] = AI_C_ARRAY_INIT;



/**  Array declarations section  **********************************************/
/* Array#0 */
AI_ARRAY_OBJ_DECLARE(
  dR_norm_output_array, AI_ARRAY_FORMAT_FLOAT|AI_FMT_FLAG_IS_IO,
  NULL, NULL, 1, AI_STATIC)

/* Array#1 */
AI_ARRAY_OBJ_DECLARE(
  mul_result_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 16, AI_STATIC)

/* Array#2 */
AI_ARRAY_OBJ_DECLARE(
  next_activations_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 16, AI_STATIC)

/* Array#3 */
AI_ARRAY_OBJ_DECLARE(
  mul_result1_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 8, AI_STATIC)

/* Array#4 */
AI_ARRAY_OBJ_DECLARE(
  next_activations1_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 8, AI_STATIC)

/* Array#5 */
AI_ARRAY_OBJ_DECLARE(
  mul_result2_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 4, AI_STATIC)

/* Array#6 */
AI_ARRAY_OBJ_DECLARE(
  next_activations2_output_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 4, AI_STATIC)

/* Array#7 */
AI_ARRAY_OBJ_DECLARE(
  mul_result3_output_array, AI_ARRAY_FORMAT_FLOAT|AI_FMT_FLAG_IS_IO,
  NULL, NULL, 1, AI_STATIC)

/* Array#8 */
AI_ARRAY_OBJ_DECLARE(
  mul_result_weights_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 16, AI_STATIC)

/* Array#9 */
AI_ARRAY_OBJ_DECLARE(
  mul_result_bias_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 16, AI_STATIC)

/* Array#10 */
AI_ARRAY_OBJ_DECLARE(
  mul_result1_weights_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 128, AI_STATIC)

/* Array#11 */
AI_ARRAY_OBJ_DECLARE(
  mul_result1_bias_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 8, AI_STATIC)

/* Array#12 */
AI_ARRAY_OBJ_DECLARE(
  mul_result2_weights_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 32, AI_STATIC)

/* Array#13 */
AI_ARRAY_OBJ_DECLARE(
  mul_result2_bias_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 4, AI_STATIC)

/* Array#14 */
AI_ARRAY_OBJ_DECLARE(
  mul_result3_weights_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 4, AI_STATIC)

/* Array#15 */
AI_ARRAY_OBJ_DECLARE(
  mul_result3_bias_array, AI_ARRAY_FORMAT_FLOAT,
  NULL, NULL, 1, AI_STATIC)

/**  Tensor declarations section  *********************************************/
/* Tensor #0 */
AI_TENSOR_OBJ_DECLARE(
  dR_norm_output, AI_STATIC,
  0, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &dR_norm_output_array, NULL)

/* Tensor #1 */
AI_TENSOR_OBJ_DECLARE(
  mul_result1_bias, AI_STATIC,
  1, 0x0,
  AI_SHAPE_INIT(4, 1, 8, 1, 1), AI_STRIDE_INIT(4, 4, 4, 32, 32),
  1, &mul_result1_bias_array, NULL)

/* Tensor #2 */
AI_TENSOR_OBJ_DECLARE(
  mul_result1_output, AI_STATIC,
  2, 0x0,
  AI_SHAPE_INIT(4, 1, 8, 1, 1), AI_STRIDE_INIT(4, 4, 4, 32, 32),
  1, &mul_result1_output_array, NULL)

/* Tensor #3 */
AI_TENSOR_OBJ_DECLARE(
  mul_result1_weights, AI_STATIC,
  3, 0x0,
  AI_SHAPE_INIT(4, 16, 8, 1, 1), AI_STRIDE_INIT(4, 4, 64, 512, 512),
  1, &mul_result1_weights_array, NULL)

/* Tensor #4 */
AI_TENSOR_OBJ_DECLARE(
  mul_result2_bias, AI_STATIC,
  4, 0x0,
  AI_SHAPE_INIT(4, 1, 4, 1, 1), AI_STRIDE_INIT(4, 4, 4, 16, 16),
  1, &mul_result2_bias_array, NULL)

/* Tensor #5 */
AI_TENSOR_OBJ_DECLARE(
  mul_result2_output, AI_STATIC,
  5, 0x0,
  AI_SHAPE_INIT(4, 1, 4, 1, 1), AI_STRIDE_INIT(4, 4, 4, 16, 16),
  1, &mul_result2_output_array, NULL)

/* Tensor #6 */
AI_TENSOR_OBJ_DECLARE(
  mul_result2_weights, AI_STATIC,
  6, 0x0,
  AI_SHAPE_INIT(4, 8, 4, 1, 1), AI_STRIDE_INIT(4, 4, 32, 128, 128),
  1, &mul_result2_weights_array, NULL)

/* Tensor #7 */
AI_TENSOR_OBJ_DECLARE(
  mul_result3_bias, AI_STATIC,
  7, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &mul_result3_bias_array, NULL)

/* Tensor #8 */
AI_TENSOR_OBJ_DECLARE(
  mul_result3_output, AI_STATIC,
  8, 0x0,
  AI_SHAPE_INIT(4, 1, 1, 1, 1), AI_STRIDE_INIT(4, 4, 4, 4, 4),
  1, &mul_result3_output_array, NULL)

/* Tensor #9 */
AI_TENSOR_OBJ_DECLARE(
  mul_result3_weights, AI_STATIC,
  9, 0x0,
  AI_SHAPE_INIT(4, 4, 1, 1, 1), AI_STRIDE_INIT(4, 4, 16, 16, 16),
  1, &mul_result3_weights_array, NULL)

/* Tensor #10 */
AI_TENSOR_OBJ_DECLARE(
  mul_result_bias, AI_STATIC,
  10, 0x0,
  AI_SHAPE_INIT(4, 1, 16, 1, 1), AI_STRIDE_INIT(4, 4, 4, 64, 64),
  1, &mul_result_bias_array, NULL)

/* Tensor #11 */
AI_TENSOR_OBJ_DECLARE(
  mul_result_output, AI_STATIC,
  11, 0x0,
  AI_SHAPE_INIT(4, 1, 16, 1, 1), AI_STRIDE_INIT(4, 4, 4, 64, 64),
  1, &mul_result_output_array, NULL)

/* Tensor #12 */
AI_TENSOR_OBJ_DECLARE(
  mul_result_weights, AI_STATIC,
  12, 0x0,
  AI_SHAPE_INIT(4, 1, 16, 1, 1), AI_STRIDE_INIT(4, 4, 4, 64, 64),
  1, &mul_result_weights_array, NULL)

/* Tensor #13 */
AI_TENSOR_OBJ_DECLARE(
  next_activations1_output, AI_STATIC,
  13, 0x0,
  AI_SHAPE_INIT(4, 1, 8, 1, 1), AI_STRIDE_INIT(4, 4, 4, 32, 32),
  1, &next_activations1_output_array, NULL)

/* Tensor #14 */
AI_TENSOR_OBJ_DECLARE(
  next_activations2_output, AI_STATIC,
  14, 0x0,
  AI_SHAPE_INIT(4, 1, 4, 1, 1), AI_STRIDE_INIT(4, 4, 4, 16, 16),
  1, &next_activations2_output_array, NULL)

/* Tensor #15 */
AI_TENSOR_OBJ_DECLARE(
  next_activations_output, AI_STATIC,
  15, 0x0,
  AI_SHAPE_INIT(4, 1, 16, 1, 1), AI_STRIDE_INIT(4, 4, 4, 64, 64),
  1, &next_activations_output_array, NULL)



/**  Layer declarations section  **********************************************/


AI_TENSOR_CHAIN_OBJ_DECLARE(
  mul_result3_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations2_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result3_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 2, &mul_result3_weights, &mul_result3_bias),
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  mul_result3_layer, 11,
  DENSE_TYPE, 0x0, NULL,
  dense, forward_dense,
  &mul_result3_chain,
  NULL, &mul_result3_layer, AI_STATIC, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  next_activations2_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &mul_result2_output),
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &next_activations2_output),
  AI_TENSOR_LIST_OBJ_EMPTY,
  AI_TENSOR_LIST_OBJ_EMPTY
)

AI_LAYER_OBJ_DECLARE(
  next_activations2_layer, 9,
  NL_TYPE, 0x0, NULL,
  nl, forward_relu,
  &next_activations2_chain,
  NULL, &mul_result3_layer, AI_STATIC, 
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
  NULL, &next_activations2_layer, AI_STATIC, 
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
  nl, forward_relu,
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
  nl, forward_relu,
  &next_activations_chain,
  NULL, &mul_result1_layer, AI_STATIC, 
  .nl_params = NULL, 
)

AI_TENSOR_CHAIN_OBJ_DECLARE(
  mul_result_chain, AI_STATIC_CONST, 4,
  AI_TENSOR_LIST_OBJ_INIT(AI_FLAG_NONE, 1, &dR_norm_output),
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
    AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 836, 1, 1),
    836, NULL, NULL),
  AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
    AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 96, 1, 1),
    96, NULL, NULL),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_STAGE1_IN_NUM, &dR_norm_output),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_STAGE1_OUT_NUM, &mul_result3_output),
  &mul_result_layer, 0xe6e336f7, NULL)

#else

AI_NETWORK_OBJ_DECLARE(
  AI_NET_OBJ_INSTANCE, AI_STATIC,
  AI_BUFFER_ARRAY_OBJ_INIT_STATIC(
  	AI_FLAG_NONE, 1,
    AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
      AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 836, 1, 1),
      836, NULL, NULL)
  ),
  AI_BUFFER_ARRAY_OBJ_INIT_STATIC(
  	AI_FLAG_NONE, 1,
    AI_BUFFER_INIT(AI_FLAG_NONE,  AI_BUFFER_FORMAT_U8,
      AI_BUFFER_SHAPE_INIT(AI_SHAPE_BCWH, 4, 1, 96, 1, 1),
      96, NULL, NULL)
  ),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_STAGE1_IN_NUM, &dR_norm_output),
  AI_TENSOR_LIST_IO_OBJ_INIT(AI_FLAG_NONE, AI_STAGE1_OUT_NUM, &mul_result3_output),
  &mul_result_layer, 0xe6e336f7, NULL)

#endif	/*(AI_TOOLS_API_VERSION < AI_TOOLS_API_VERSION_1_5)*/



/******************************************************************************/
AI_DECLARE_STATIC
ai_bool stage1_configure_activations(
  ai_network* net_ctx, const ai_network_params* params)
{
  AI_ASSERT(net_ctx)

  if (ai_platform_get_activations_map(g_stage1_activations_map, 1, params)) {
    /* Updating activations (byte) offsets */
    
    dR_norm_output_array.data = AI_PTR(g_stage1_activations_map[0] + 28);
    dR_norm_output_array.data_start = AI_PTR(g_stage1_activations_map[0] + 28);
    mul_result_output_array.data = AI_PTR(g_stage1_activations_map[0] + 32);
    mul_result_output_array.data_start = AI_PTR(g_stage1_activations_map[0] + 32);
    next_activations_output_array.data = AI_PTR(g_stage1_activations_map[0] + 32);
    next_activations_output_array.data_start = AI_PTR(g_stage1_activations_map[0] + 32);
    mul_result1_output_array.data = AI_PTR(g_stage1_activations_map[0] + 0);
    mul_result1_output_array.data_start = AI_PTR(g_stage1_activations_map[0] + 0);
    next_activations1_output_array.data = AI_PTR(g_stage1_activations_map[0] + 32);
    next_activations1_output_array.data_start = AI_PTR(g_stage1_activations_map[0] + 32);
    mul_result2_output_array.data = AI_PTR(g_stage1_activations_map[0] + 0);
    mul_result2_output_array.data_start = AI_PTR(g_stage1_activations_map[0] + 0);
    next_activations2_output_array.data = AI_PTR(g_stage1_activations_map[0] + 16);
    next_activations2_output_array.data_start = AI_PTR(g_stage1_activations_map[0] + 16);
    mul_result3_output_array.data = AI_PTR(g_stage1_activations_map[0] + 0);
    mul_result3_output_array.data_start = AI_PTR(g_stage1_activations_map[0] + 0);
    return true;
  }
  AI_ERROR_TRAP(net_ctx, INIT_FAILED, NETWORK_ACTIVATIONS);
  return false;
}




/******************************************************************************/
AI_DECLARE_STATIC
ai_bool stage1_configure_weights(
  ai_network* net_ctx, const ai_network_params* params)
{
  AI_ASSERT(net_ctx)

  if (ai_platform_get_weights_map(g_stage1_weights_map, 1, params)) {
    /* Updating weights (byte) offsets */
    
    mul_result_weights_array.format |= AI_FMT_FLAG_CONST;
    mul_result_weights_array.data = AI_PTR(g_stage1_weights_map[0] + 0);
    mul_result_weights_array.data_start = AI_PTR(g_stage1_weights_map[0] + 0);
    mul_result_bias_array.format |= AI_FMT_FLAG_CONST;
    mul_result_bias_array.data = AI_PTR(g_stage1_weights_map[0] + 64);
    mul_result_bias_array.data_start = AI_PTR(g_stage1_weights_map[0] + 64);
    mul_result1_weights_array.format |= AI_FMT_FLAG_CONST;
    mul_result1_weights_array.data = AI_PTR(g_stage1_weights_map[0] + 128);
    mul_result1_weights_array.data_start = AI_PTR(g_stage1_weights_map[0] + 128);
    mul_result1_bias_array.format |= AI_FMT_FLAG_CONST;
    mul_result1_bias_array.data = AI_PTR(g_stage1_weights_map[0] + 640);
    mul_result1_bias_array.data_start = AI_PTR(g_stage1_weights_map[0] + 640);
    mul_result2_weights_array.format |= AI_FMT_FLAG_CONST;
    mul_result2_weights_array.data = AI_PTR(g_stage1_weights_map[0] + 672);
    mul_result2_weights_array.data_start = AI_PTR(g_stage1_weights_map[0] + 672);
    mul_result2_bias_array.format |= AI_FMT_FLAG_CONST;
    mul_result2_bias_array.data = AI_PTR(g_stage1_weights_map[0] + 800);
    mul_result2_bias_array.data_start = AI_PTR(g_stage1_weights_map[0] + 800);
    mul_result3_weights_array.format |= AI_FMT_FLAG_CONST;
    mul_result3_weights_array.data = AI_PTR(g_stage1_weights_map[0] + 816);
    mul_result3_weights_array.data_start = AI_PTR(g_stage1_weights_map[0] + 816);
    mul_result3_bias_array.format |= AI_FMT_FLAG_CONST;
    mul_result3_bias_array.data = AI_PTR(g_stage1_weights_map[0] + 832);
    mul_result3_bias_array.data_start = AI_PTR(g_stage1_weights_map[0] + 832);
    return true;
  }
  AI_ERROR_TRAP(net_ctx, INIT_FAILED, NETWORK_WEIGHTS);
  return false;
}


/**  PUBLIC APIs SECTION  *****************************************************/



AI_DEPRECATED
AI_API_ENTRY
ai_bool ai_stage1_get_info(
  ai_handle network, ai_network_report* report)
{
  ai_network* net_ctx = AI_NETWORK_ACQUIRE_CTX(network);

  if (report && net_ctx)
  {
    ai_network_report r = {
      .model_name        = AI_STAGE1_MODEL_NAME,
      .model_signature   = AI_STAGE1_MODEL_SIGNATURE,
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
      
      .n_macc            = 237,
      .n_inputs          = 0,
      .inputs            = NULL,
      .n_outputs         = 0,
      .outputs           = NULL,
      .params            = AI_STRUCT_INIT,
      .activations       = AI_STRUCT_INIT,
      .n_nodes           = 0,
      .signature         = 0xe6e336f7,
    };

    if (!ai_platform_api_get_network_report(network, &r)) return false;

    *report = r;
    return true;
  }
  return false;
}



AI_API_ENTRY
ai_bool ai_stage1_get_report(
  ai_handle network, ai_network_report* report)
{
  ai_network* net_ctx = AI_NETWORK_ACQUIRE_CTX(network);

  if (report && net_ctx)
  {
    ai_network_report r = {
      .model_name        = AI_STAGE1_MODEL_NAME,
      .model_signature   = AI_STAGE1_MODEL_SIGNATURE,
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
      
      .n_macc            = 237,
      .n_inputs          = 0,
      .inputs            = NULL,
      .n_outputs         = 0,
      .outputs           = NULL,
      .map_signature     = AI_MAGIC_SIGNATURE,
      .map_weights       = AI_STRUCT_INIT,
      .map_activations   = AI_STRUCT_INIT,
      .n_nodes           = 0,
      .signature         = 0xe6e336f7,
    };

    if (!ai_platform_api_get_network_report(network, &r)) return false;

    *report = r;
    return true;
  }
  return false;
}


AI_API_ENTRY
ai_error ai_stage1_get_error(ai_handle network)
{
  return ai_platform_network_get_error(network);
}


AI_API_ENTRY
ai_error ai_stage1_create(
  ai_handle* network, const ai_buffer* network_config)
{
  return ai_platform_network_create(
    network, network_config, 
    AI_CONTEXT_OBJ(&AI_NET_OBJ_INSTANCE),
    AI_TOOLS_API_VERSION_MAJOR, AI_TOOLS_API_VERSION_MINOR, AI_TOOLS_API_VERSION_MICRO);
}


AI_API_ENTRY
ai_error ai_stage1_create_and_init(
  ai_handle* network, const ai_handle activations[], const ai_handle weights[])
{
  ai_error err;
  ai_network_params params;

  err = ai_stage1_create(network, AI_STAGE1_DATA_CONFIG);
  if (err.type != AI_ERROR_NONE) {
    return err;
  }
  
  if (ai_stage1_data_params_get(&params) != true) {
    err = ai_stage1_get_error(*network);
    return err;
  }
#if defined(AI_STAGE1_DATA_ACTIVATIONS_COUNT)
  /* set the addresses of the activations buffers */
  for (ai_u16 idx=0; activations && idx<params.map_activations.size; idx++) {
    AI_BUFFER_ARRAY_ITEM_SET_ADDRESS(&params.map_activations, idx, activations[idx]);
  }
#endif
#if defined(AI_STAGE1_DATA_WEIGHTS_COUNT)
  /* set the addresses of the weight buffers */
  for (ai_u16 idx=0; weights && idx<params.map_weights.size; idx++) {
    AI_BUFFER_ARRAY_ITEM_SET_ADDRESS(&params.map_weights, idx, weights[idx]);
  }
#endif
  if (ai_stage1_init(*network, &params) != true) {
    err = ai_stage1_get_error(*network);
  }
  return err;
}


AI_API_ENTRY
ai_buffer* ai_stage1_inputs_get(ai_handle network, ai_u16 *n_buffer)
{
  if (network == AI_HANDLE_NULL) {
    network = (ai_handle)&AI_NET_OBJ_INSTANCE;
    AI_NETWORK_OBJ(network)->magic = AI_MAGIC_CONTEXT_TOKEN;
  }
  return ai_platform_inputs_get(network, n_buffer);
}


AI_API_ENTRY
ai_buffer* ai_stage1_outputs_get(ai_handle network, ai_u16 *n_buffer)
{
  if (network == AI_HANDLE_NULL) {
    network = (ai_handle)&AI_NET_OBJ_INSTANCE;
    AI_NETWORK_OBJ(network)->magic = AI_MAGIC_CONTEXT_TOKEN;
  }
  return ai_platform_outputs_get(network, n_buffer);
}


AI_API_ENTRY
ai_handle ai_stage1_destroy(ai_handle network)
{
  return ai_platform_network_destroy(network);
}


AI_API_ENTRY
ai_bool ai_stage1_init(
  ai_handle network, const ai_network_params* params)
{
  ai_network* net_ctx = AI_NETWORK_OBJ(ai_platform_network_init(network, params));
  ai_bool ok = true;

  if (!net_ctx) return false;
  ok &= stage1_configure_weights(net_ctx, params);
  ok &= stage1_configure_activations(net_ctx, params);

  ok &= ai_platform_network_post_init(network);

  return ok;
}


AI_API_ENTRY
ai_i32 ai_stage1_run(
  ai_handle network, const ai_buffer* input, ai_buffer* output)
{
  return ai_platform_network_process(network, input, output);
}


AI_API_ENTRY
ai_i32 ai_stage1_forward(ai_handle network, const ai_buffer* input)
{
  return ai_platform_network_process(network, input, NULL);
}



#undef AI_STAGE1_MODEL_SIGNATURE
#undef AI_NET_OBJ_INSTANCE
#undef AI_TOOLS_DATE_TIME
#undef AI_TOOLS_COMPILE_TIME

