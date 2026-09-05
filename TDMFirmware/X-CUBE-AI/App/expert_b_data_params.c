/**
  ******************************************************************************
  * @file    expert_b_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-08-19T14:17:40+0900
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

#include "expert_b_data_params.h"


/**  Activations Section  ****************************************************/
ai_handle g_expert_b_activations_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(NULL),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};




/**  Weights Section  ********************************************************/
AI_ALIGNED(32)
const ai_u64 s_expert_b_weights_array_u64[337] = {
  0xbf4ce1b9bdbc2218U, 0x3f2278933e3e6c3aU, 0x3e98b73d3f0463a5U, 0x3ea51a15be1bf685U,
  0xbf5585d13eb3f9adU, 0x3e877a6e3f2373e1U, 0x3d5e074b3d1c1691U, 0xbf1712c7bdb9d9ecU,
  0xbf05f3e23dd76a70U, 0xbee143603f41ba6dU, 0xbe5beba43e90e011U, 0xbeb2f831be56d2b5U,
  0xbeda50bcbf3d64f2U, 0x3f032cc0bebd9b37U, 0x3d3e96453f46a1f1U, 0xbf3935283c33dbffU,
  0xbc8b87da3f0b595fU, 0xbeb409ab3e00a97eU, 0x3e94f3ddbe3391d1U, 0x3d85cd3bbecc0ea2U,
  0xbf0e19c53f1af110U, 0xbf35d95c3e7dacf4U, 0x3e875eff3e13ac21U, 0x3e1abb1dbd89cf32U,
  0x3f11cca8bd4078ceU, 0x3d9d8c5abf5d5d2fU, 0x3ec84eea3f212ad3U, 0x3dbe06dabdb5d1a8U,
  0x3f5a3032bf08ab1fU, 0xbd6f41003d44265aU, 0x3ee46ec9bc83f838U, 0xbe743a1b3dd9e2bfU,
  0x3e08ec96be1513c6U, 0x3e89ac7b3dbb6010U, 0xbe553c843e358752U, 0x3ec66040bebcea41U,
  0x3d965de13ef747ceU, 0xbed65d003e3be882U, 0xbf10577f3ea2d757U, 0x3e1f01f3bf135cd8U,
  0x3ea3000e3f3373d1U, 0xbe4ba2fa3f70c880U, 0x3ee6a6473d83779bU, 0x3df9250cbf1305c7U,
  0x3ddaf7713d9c46e0U, 0x3de160e73edb6f4aU, 0xbf30d7403e965a6bU, 0xbf41e5cc3e441e2cU,
  0xbf32b52b3efaaa35U, 0xbf3b3bda3e50b88eU, 0xbe78d2ed3eab34ccU, 0x3ede41993f178521U,
  0x3b360e5cbee9ba33U, 0x3ecca07a3ec5c39cU, 0x3f496a61bdd3608fU, 0x3f02b8d03ef72386U,
  0xbeba94893f0112f7U, 0xbdbbe6933e301de2U, 0x3ebdcf583ec52262U, 0x3f9482a93f179c93U,
  0xbe0ff00e3e64623dU, 0x3e68aea9be9280dbU, 0x3ef945c43f610aa2U, 0x3ea8c8633ec1a16eU,
  0x3e33411cbeda39a3U, 0xbf4281763f22dc65U, 0xbf1f13f8befb43e9U, 0xbeadd671be95a7f4U,
  0xbdbb2aac3d6180caU, 0x3fc3b3ce3dd15268U, 0x3e715754bf45ea16U, 0x3f4452b3be7036c6U,
  0xbe4f33f63eaf3f54U, 0xbf1fc88a3e86deb5U, 0xbc2a88fd3e993553U, 0x3e938316bd8e560cU,
  0x3e01d0aebddaa314U, 0x3f4112543ec2b9f6U, 0x3e7382c5bf096b68U, 0x3f7cd0bc3e4c2cd4U,
  0xbe833c3f3f3868b3U, 0xbe2d731b3ec2958cU, 0xbcb308723eb68c56U, 0x3eddb8683f339b4aU,
  0xbdf4308e3e2b4b43U, 0xbea73dd6bf15790bU, 0xbee5d312bed2cd66U, 0x3d6c6498be204849U,
  0x3e0e9bbbbd9b8a73U, 0x3f8625e4be83656dU, 0x3db8aa123f2d4203U, 0x3f12916e3fad847dU,
  0xbf62aa2b3efe6abaU, 0xbdb6cae5be06d69dU, 0x3f6d735a3f0b0fc0U, 0x3d8061f23f0d9837U,
  0x3dea8e793ec4bf11U, 0xbe0bec8a3eb476eaU, 0xbe1ecb41beb9d807U, 0xbe0cdd7f3e98a63dU,
  0x3ea7f9723c65d7b3U, 0x3e9e1495bf81f078U, 0x3d0d0d0ebe6df425U, 0xbdefcbf6be214774U,
  0x3f18adaa3e9ba3eaU, 0xbe24d23dbea6bb96U, 0x3e069e5bbf27f796U, 0xbf0b9967bc0f0894U,
  0x3e954c763d9c6da4U, 0xbf0ee9053ee4ec90U, 0xbf1e37933ea9d094U, 0xbe93aedebe47f2e6U,
  0xbf6d478f3efc2dd1U, 0x3ef724b13e75447cU, 0xbe968700beeb9d4eU, 0x3e074e30bd8b47caU,
  0xbe72d78a3e88cdbfU, 0xbdc6f5f6beadf511U, 0xbe882cce3e9f95cfU, 0x3f5f96a03ea0dad8U,
  0xbe3f56e33c96a569U, 0xbedad4583d1b40bbU, 0xbebdc22bbeb6c9c7U, 0xbea7ebd73ecd1fefU,
  0x3eba2512be3d490aU, 0x3e5d33f1bf5d43bdU, 0x3e0a2e2e3d813d39U, 0x3dd074eb3f6c7ad5U,
  0xbe78cd493eeeaef9U, 0xbe5bc027bef1106aU, 0xbd705ad1bde7fffcU, 0xbe09205e3ebf8afaU,
  0xbe4a87d1bf2bee4cU, 0xbd36c9343db235d5U, 0x3d32bc3d3e921f94U, 0x3d87f716be5a689dU,
  0xbdb8b0563f50a172U, 0xbcc6682e3f893ca8U, 0x3f085da03e99d6ffU, 0xbcea37e2be5c55aaU,
  0xbe8c9f773d89eb23U, 0xbef59edabd7b9157U, 0xbe1993e03f1ba43aU, 0x3f3a1ee03f286db7U,
  0x3ed02310bf17a17cU, 0xbf04b603bf0343ebU, 0xbf23f142bf33c779U, 0xbe5477c23d6b3b37U,
  0x3e5a6dcb3c96f43cU, 0x3cbc4a43be532133U, 0x3eb935d43ecca65aU, 0xbe9f8968bee4bdf2U,
  0xbebff1fe3e4cdfdfU, 0xbefa2612be44eb9cU, 0xbdf604d33eb952b9U, 0xbd9dbc003e361a73U,
  0x3f004c4dbe0894b3U, 0xbd9f49623c3a2884U, 0xbd42a8e5be67db53U, 0x3e1d459ebe674514U,
  0xbd01bbdc3f20a056U, 0xbe4916d63dcda0b2U, 0x3dc45a363cd212ddU, 0xbdad406cbe8fcd4bU,
  0xbd2a3adcbe9b830bU, 0xbf050804be61c0e3U, 0xbece70203f163154U, 0xbd62dfe1be67015eU,
  0x3e8b9c5cbf2bed28U, 0x3f4f0f66be4b6b5bU, 0x3f2245f63ea2c5a4U, 0xbe4edd9d3e62c15cU,
  0x3e44f87e3e826654U, 0xbeee34263e22a233U, 0xbe1f07babe0f5b86U, 0x3e2b5beabe5bb275U,
  0x3ec09949be07d241U, 0x3eaad299be62881fU, 0xbebe7de23e4b4fb9U, 0xbe508275be9f7e4fU,
  0xbf46f09f3edf2148U, 0xbc90c58b3f3aad4eU, 0x3e85e9ac3f6a2f57U, 0x3cc9367b3f0837ecU,
  0xbf51cdd23e21cd49U, 0xbe619e983ee7050bU, 0x3e9936c4bf8dad60U, 0x3edd6d753e06e5f7U,
  0xbf905a083eb125baU, 0xbe9d51263e2b9c88U, 0xbe2f1c3b3d32b14eU, 0x3f666d763dbb97ceU,
  0x3f03cd9fbdafc1fdU, 0xbd3d24183e053e2bU, 0x3bb0bd99bee92411U, 0xbf14619abec4d886U,
  0x3f40d7ecbef79ed5U, 0xbe67cc68bf89269fU, 0xbe26a7053e33d541U, 0xbe406c5b3f17213eU,
  0x3f26dd90bc3c4235U, 0x3c0dc302be94705eU, 0x3e87d18b3ed0952dU, 0xbf15d6ddbec97d34U,
  0x3eb4e2d6bf01bef7U, 0x3d931ce13e8cbf82U, 0x3e9f1460bdca130cU, 0x3c2030af3e02614aU,
  0x3dd7b379bc818ccbU, 0xbe0185f53ed555beU, 0xbe70255dbe3ccf02U, 0xbdec8741bf541aa7U,
  0x3f10c2d4bec60fb4U, 0x3e6a5f823ea255d3U, 0x3c4ec770beaeb2fbU, 0xbedf223ebeef978bU,
  0x3f28aafdbef8bc2dU, 0x3e687b423d1d1200U, 0xbe0815edbf21343cU, 0x3e1fc341bf173dcaU,
  0x3f27598fbe05c67bU, 0xbe079e66bf7585ebU, 0xbec172703ea2d7cbU, 0x3ddbe51d3ea01097U,
  0x3e816eebbc084f5fU, 0xbd3016f83ee5e3cdU, 0x3f104b60bf33b3b4U, 0xbf3785f3be3510b9U,
  0xbe64a4f6bf8de452U, 0x3f061fe5bf59d152U, 0xbd961cc5be52815aU, 0x3f8e4175bf70ea7aU,
  0x3d6b74c53c90c2b5U, 0x3e52a7f43eed1174U, 0xbe38d8213ef6d554U, 0x3eb6be833ec6b597U,
  0xbf28effabed91c81U, 0xbe033e023f3c33afU, 0x3ed4dbd03e127f50U, 0x3cca4627bed970e8U,
  0xbee78d37bdd6fd89U, 0xbe96cc72bef11cacU, 0x3d5f42693db38545U, 0xbe2e64f33e3e4042U,
  0x3f160225bf03abb9U, 0xbe968bb7bda64c60U, 0xbf02c4913e5aa444U, 0x3e924e6a3f70fc65U,
  0xbfbd8ea93f1ba185U, 0xbea146d0bea8ff06U, 0x3eb83d8dbdb8383cU, 0x3f20fd333e498648U,
  0x3f1faa523a205c7aU, 0xbecb0e023f053667U, 0x3d914668be22d883U, 0xbe0d6b94becec9b1U,
  0x3d3ef749bd608a95U, 0x3db766333e9137c9U, 0xbe2ef223bec4f65eU, 0x3f6569733ea6ff47U,
  0xbf83eb6f3f09bdd0U, 0x3f1c8d47bef9724aU, 0x3e1b825cbebf4d4cU, 0xbf5644ba3c9a712dU,
  0x3ebd9eb7be3cee61U, 0x3e37f05fbf1148a1U, 0x3f2e38003e9c170dU, 0xbe97679bbec79eebU,
  0xbe910853befdd630U, 0xbe80f3033f234dcfU, 0xbebf5916bec92614U, 0x3f745c7a3f219acdU,
  0xbeb0d27ebf046fb1U, 0xbd129454bebf88ebU, 0x3e511ea93ec83da6U, 0x3f663bc13f543fb2U,
  0xbebde9f6bf993aa6U, 0x3d6adb843f7600e0U, 0x3f0045f7be4301f4U, 0x3f1543853f294507U,
  0xbe8f589d3e34aff9U, 0xbdcfec443f263118U, 0x3dd19ae6befac4b9U, 0x3f5fd8ac3ec8821aU,
  0x3e617f343dccb7a9U, 0x3f1eb3063ed09b60U, 0x3f1a851cbe7f9669U, 0x3ed4b469be629504U,
  0x3e13cea0bf6bb7e6U, 0x3f18f1dfbf2e5bd0U, 0x3f1b698a3d8173f6U, 0x3f060c8a3f2574e4U,
  0xbea80badbe27ec31U, 0x3f81ba67bfafde17U, 0x3e9d7f3dbfb47a6eU, 0xbf2bb6dabfc2f22cU,
  0x3dfa4b4fbfa87250U, 0x3f5da6c9bf853215U, 0x3f12f2233e2e4ce3U, 0xbe1e375cbf4f4fb8U,
  0xbe64bdd7be302dfbU, 0xbed5aa6d3db6eb0aU, 0xbf19d18e3f0cf2d9U, 0xbf148f103f10493bU,
  0xbd09e3a43e9caa4aU, 0xbf72bc03be9bcb03U, 0xbef000433ef08174U, 0xbfda0d97bef7e52aU,
  0x3e40cd59bd6cf012U, 0xbf16b8303f0dce44U, 0xbedbb30f3f91b428U, 0xbe8879733f837785U,
  0xbef26b5c3f23df71U, 0xbf9033ec3df18706U, 0xbf6983353da2f733U, 0xbeadb148bf0551bcU,
  0xbf858a8e3f59f71dU, 0x3ccdbed1bf932ce8U, 0x3f011d4dbdf72e67U, 0xbf38b0b7beaafde3U,
  0x3f8732473c8302b7U, 0x3e59f615bf272e8cU, 0x3ce9b7193f5379a7U, 0xbe728e503d86d496U,
  0xbf2354f63e7d3503U, 0x3e94531a3e24af7dU, 0xbf7fed67bee23e02U, 0xbf0ac8c03e82b6d1U,
  0x3fa62aecc05a16f8U, 0xc0912e494067ebdeU, 0x4089c81bc08144fbU, 0xc060494c407e0098U,
  0x407ee540c0039162U, 0x3d9bfa3840215ec3U, 0xc0360acdbe92cbc4U, 0xbf89804fbda9f165U,
  0x3f4ed678404f80abU,
};


ai_handle g_expert_b_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_expert_b_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

