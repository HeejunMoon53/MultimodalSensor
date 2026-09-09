/**
  ******************************************************************************
  * @file    expert_a_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-09-10T00:32:49+0900
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

#include "expert_a_data_params.h"


/**  Activations Section  ****************************************************/
ai_handle g_expert_a_activations_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(NULL),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};




/**  Weights Section  ********************************************************/
AI_ALIGNED(32)
const ai_u64 s_expert_a_weights_array_u64[337] = {
  0x3e1f659bbed0ce7aU, 0x3f509629bf7de8c2U, 0x3cb98a6f3de47857U, 0xbeb8e88d3ec31e62U,
  0xbee58d6fbebec2b5U, 0x3ed6338abea433e6U, 0x3db0fbafbea00eeaU, 0xbfb1483abe53c8ceU,
  0x3ecfdbd0bf008fcfU, 0xbf7c86023fb4c58aU, 0xbf0c7fd73fdc692eU, 0xbe94b2b8bee6abe4U,
  0xbf16aa5cbdd102ccU, 0xbe29fd33be01a67cU, 0x3f0567543eb3668aU, 0xbf2cac30bef5133aU,
  0x3d8147973f157e08U, 0xbf4909933f06111cU, 0xbebff1683db6ad07U, 0xbc87fa47be1c6cb4U,
  0x3d7d364e3f70bd2fU, 0xbc6ddb933e3943e9U, 0x3f3596cebef1eda1U, 0x3e956617bf7d2ebbU,
  0xbe4735e73e633edbU, 0x3e51adbdbefb4705U, 0x3f3e40383f927bddU, 0xbf0dda6abfb54c0eU,
  0x3f74fffebf5f46f6U, 0xbf1bff8f3e12ef67U, 0x3f41438fbe263632U, 0xbef45666bf359a9aU,
  0x3f0ab6e3be86356cU, 0x3ebfb553bed1f572U, 0xbeb9284fbd24e9a9U, 0x3ed138c9be4d6cfcU,
  0xbf56cf7f3ebea46cU, 0x3dbf56de3f2ddb14U, 0xbf9311153e243066U, 0x3e30ee2abedddaa2U,
  0x3f5204d93fb4529cU, 0xbfa8ea75bf14b4f7U, 0x3dcae5513f06100dU, 0xbdbb64d8bf1c2570U,
  0xbe9f77f43ef02a1fU, 0x3f3014773dead09dU, 0x3dd3fcf43facbfc6U, 0xbf28577c3e48d513U,
  0xbf7074163f46bc72U, 0xbfa5fdb03f4772a0U, 0xbf3f8ca7bf08303dU, 0x3ebdc4693fa45804U,
  0xbe142ef8bef2be54U, 0x3f523bd93da045ebU, 0x3e9ffe2cbe2acf1fU, 0x3f25a571be0eb158U,
  0xbefe14b03f006dd0U, 0xbf97f4c53e160effU, 0xbf23f06ebf01d3a3U, 0xbf0552573ef0cbc1U,
  0x3d84500fbff2ddffU, 0x3f4fad9fbedad1c6U, 0x3ee4ce89401d321aU, 0x3d4f25e4bf32fd05U,
  0x3e5cc16e3fb6f4e3U, 0xc0147fcdbe023bf3U, 0xbe911df9be4f7462U, 0xbf1725a93d3afc02U,
  0xbe66433bbe9ccd2eU, 0x3ed5ee5b3eb9182aU, 0xbec55b513cf35195U, 0x3f0ae7d13dcae76bU,
  0xbf2c5cb240057096U, 0xc0840eb23f12bbabU, 0x3f127e49c03b678cU, 0x4039e1eb3e1db440U,
  0xbdcfbcc0bf4089d0U, 0x3fed3f713fb4cedfU, 0x401853d8bf58d35eU, 0x3efa3768bf000402U,
  0xc000c8e83fe2489bU, 0xc0850bd0bee0cc16U, 0xbec78e3c3e625272U, 0x3fb1a96e3f85bb5bU,
  0xbf0ed9f33ee357e4U, 0xbf6c89fe3e6024baU, 0xbea6aed2be84bb77U, 0x3e36eafb3e4a1be9U,
  0xbe97707cbe484dfbU, 0xbdcf1f103e4418c3U, 0x3eb1af18bef9d718U, 0x3da850cbbf0d8d3fU,
  0xbf04a0153b9492f8U, 0x3f3a8058bd891832U, 0xbb2372133dd2a855U, 0xbe5336853f7b00a0U,
  0x3e5445e0be05d50eU, 0xbf0d5c9c3e235de9U, 0xbedae655bd40ff6eU, 0xbf1898033f27d125U,
  0x3e091b8dbf3169d4U, 0x3f2df793bef45035U, 0xbf23d7c83d1f135dU, 0xbdf518773ea08dabU,
  0x3f1edd953e48adf5U, 0xbf76dae3bdbafeeeU, 0xbdfefe77bfcd0055U, 0xbe2172393e335ca2U,
  0xbe31346f3dfb8d64U, 0xbf8d90123f1ad819U, 0xbe9608a53df4f4fbU, 0x3e9311ff3ee24370U,
  0xbeb1d77b3e31c4e1U, 0x3f2054aa3ee477c5U, 0x3d9b912fbe96b6f0U, 0x3f1a7c9abe598cd2U,
  0xbf1718ee3f472d4aU, 0xbf8084dfbea5c86cU, 0xbecd113dbf4ef73bU, 0x3f8d54fc3f40b9f6U,
  0xbf0c9eca408f5a82U, 0xbf303f203eb008eeU, 0x402871f0c0b9d65fU, 0x3e6719633e8de090U,
  0x3e8e08edbf862906U, 0x40036f0abf466f30U, 0x3f65e05e3ec606c0U, 0x3ecc4dcbbde17c00U,
  0xbdc180273f6baa0cU, 0xbe4d4e5dbcdac048U, 0xbecd0a97bfa9ef1dU, 0xbf0a11ce3f054c50U,
  0xbe8bf254bf0bd763U, 0x3f0cdf333c324ed0U, 0x400b934fbf72a759U, 0x3f17c65ebf135fcaU,
  0x3ed5ef2b3f0186c7U, 0x3e5955ce3ebf34abU, 0x400e9f483e950b26U, 0x3f74d2693f06bb00U,
  0xbf0d02a83ed7cf9fU, 0xbe075995bf08ee31U, 0x3f1543a0400f971eU, 0x3e725f7d3e8a2fb4U,
  0x3eb52e52bf63ad90U, 0xbde57e9dbe06a9d9U, 0x3ed608843f397edbU, 0xbd9e89473e55a74cU,
  0x3e72858f3e66f700U, 0xbfc6ff503e535c10U, 0x3e38f3213d5977bfU, 0xbf0332dbbf930655U,
  0x3d4fab44bed48c37U, 0x3f3bd3683e6edefeU, 0x3f0819033f8d40a9U, 0x3ea63ceebdf7b695U,
  0x3f072fbcbf0ba46bU, 0x3f01247cbf04d978U, 0x3f39343f3e96649bU, 0x3f365b0abf5f4c06U,
  0xbf011cd53f0df1fbU, 0xbc952c5dbdd252eeU, 0x3f803a44befd54feU, 0x3f4ba9863ec34fecU,
  0xbec612ff3ddb87b1U, 0xbf3848d9bf3c8109U, 0x3d938d3e3fb6e2fcU, 0xbe91b7b2bf4d0ecdU,
  0x3da2d60c3d324872U, 0x3ec9597f3e19a5c5U, 0x3d03b0e9bc9c0c3cU, 0x3cd938d23ee3c07fU,
  0x3ec635a73dd8628bU, 0xbe9909c2bdc8a6b2U, 0x3d4ff9f2becc75e6U, 0x3de90f3e3daccee1U,
  0x3dde4eb23df96116U, 0x3d877213be8d1f65U, 0xbef0326b3ed70cbdU, 0xbdaf6ef83d8b7a05U,
  0xbebe0f1abe19e370U, 0x3e4ec9233e19ec21U, 0xbe59b8783f9947dbU, 0x3e36072d3d473830U,
  0xbeb4becc3ec8ddcaU, 0xbea083cabe5b4cd8U, 0x3ea166bfbf07df78U, 0x3e7ad2653e73c89aU,
  0xbf770d3b3f107204U, 0xbf900d0bbefe6471U, 0x3e14d3393e345454U, 0xbdf309c9be2ea986U,
  0x3f6798ffc00c8d07U, 0x3f93e83abe48e57bU, 0x3f25407d3f57da29U, 0xbfc5a501bf029d62U,
  0x3ebea83e3f421e60U, 0xbfc491ebbe3bf470U, 0xbf75d37d3f08d510U, 0xbf0b13e23e0ea46aU,
  0x3fdc1a84bfa73678U, 0x3fda34cebe683fb4U, 0x3d716e233f9a7badU, 0xbe2da5adbf1cb6ddU,
  0xbd470e093c8c8abfU, 0xbebb36823f23e145U, 0x3eb5eedc3d37fb19U, 0x3f2c85193f8971daU,
  0x3e853f50bc124d84U, 0x3e75903f3f2797c3U, 0x3e0c2e9bbecdb6b0U, 0x3f233a75bfa0f0c3U,
  0xbdf1793b3e8629c9U, 0xbdb005b63e85c15fU, 0x3d4366d43ec8881cU, 0xbe14bd69becc00a8U,
  0x3efef450bf2e86dbU, 0x3f2af277bd7bf672U, 0xbfb91b0cbe804468U, 0xbf6d1e1dbf347c86U,
  0xbd86c6f4beb42523U, 0xbf871cddbd1a0e9cU, 0xbf5de813be02e0d9U, 0xbf4aecb2bf9ee16dU,
  0x3e40f8ec3e035ef2U, 0x3f833f80bccd81eaU, 0xbf05d5c5c00932c8U, 0xbed7335c3cf99bccU,
  0xbf2b3971bcc68f04U, 0xbe53a2693c9cb52aU, 0xbf13b2b5bea3925aU, 0x3e7f4d5cbe7c6342U,
  0x3d9ab73cbdbf081bU, 0xbf359413be338c38U, 0x3f0ca1d83d5011b2U, 0xbf02da7cbea3d132U,
  0xbe8512a8bf05fc77U, 0x3f57fd0a3dfb7c8cU, 0xbb1b27873f4e9c00U, 0x3b94f2803ea32f01U,
  0x3f0be86bbf963aa9U, 0xbd9ec98cbe7be38aU, 0x3f913d593dacf77aU, 0xbe067326bea4354dU,
  0x3c003be63f7e8663U, 0xbfb215103d646babU, 0xbea40df63ea17cadU, 0xbf92df1ebed887e3U,
  0x3c829478bf5592aeU, 0x3f656153bdc4944aU, 0x3f4a50263ea64286U, 0x3f304c973e8f33e8U,
  0x3f6bce90bda2a6b2U, 0xbf37f3fb3f54b561U, 0x3e1e7e043e8ecc4dU, 0xbb33839cbd13d659U,
  0x3e70a3cd3d43cbecU, 0xbea5545e3e3c450bU, 0xbe602e87bd588d9cU, 0x3e0d18bd3f1581d9U,
  0x3d9a96b6bebcb78aU, 0xbe56f124bfa4d76aU, 0xbdb5a758bea23a64U, 0x3e25c3323f8de5a0U,
  0x3ef2ee67bed437adU, 0x3eed346d3e880d8bU, 0xbe864aa0bcd95dcdU, 0x3f1ea3babf0abf81U,
  0x3f1f5e2ebf7d6d96U, 0xbf122c593f4a51a4U, 0xc028c0b8bf02b8c7U, 0x3f46a89abea3024bU,
  0xbe8ef18fbf983b96U, 0xbf1a4b213ecbba4aU, 0xbe937be43ecb8c94U, 0x3f71d2733f413c9eU,
  0x3e012e10bf3f663eU, 0xbedc64823f6a553fU, 0xbe5102a13e46d407U, 0x3ffef9e13ff6108aU,
  0x3e77f05abf341c3fU, 0xbeb97ea73f866f74U, 0x400adc68be883835U, 0x3fb07e553f82c3f0U,
  0xbefa32323ed21d56U, 0xbdcd6c623d6bb4cbU, 0x3b795678bf306f5cU, 0xbde07671bdd06f88U,
  0x3fe5f111bf35f752U, 0x3d8c1d66bf495022U, 0x3f0364863fb64b78U, 0xbf7022fa3f41be44U,
  0x3e993e3b3e2c1f90U, 0x3edb4bd8bfbebc8bU, 0x3f402e1abf75770aU, 0xbe52c371bee36b65U,
  0x3e4aa67ebf2a9e6dU, 0x3fa41aaabc929e3dU, 0xbefa8d683d70b259U, 0xbf5698f1bf055b25U,
  0xbf2686343f38c212U, 0x3eab1ababf9aa257U, 0x3ef5e22abf2efe13U, 0xbe8b2bc2bf7b365aU,
  0xbe376b493fb6911fU, 0x3ee827ddbef10a3aU, 0xbf7a3e963f4306adU, 0xbed52480bf38006aU,
  0x3e0123823da5bb1eU, 0xbd0b0f663ec7b648U, 0x3e80bbc73f67739eU, 0x3ed682773e330fd6U,
  0xbfe961513ecd8f0eU, 0xbf21602cbdf1d681U, 0xbebd0341bf182c7fU, 0x3fa3190a3e11302eU,
  0xbf81d3a33f228603U, 0xbd572b24be8cdb5fU, 0x3ed9a66ebf360c74U, 0x3f0815163bc35799U,
  0x3fd0e793bed4b4aeU, 0xbd4b05d5becb1672U, 0x3f1790b03f9f1f0cU, 0xbf85874c3ef577f7U,
  0xbe8132d03b22193bU, 0xbe14b48f3eb60c90U, 0xbfc16777bf65e0c9U, 0xbebc7b223f11454eU,
  0xbe9affe5c07c9981U, 0xc0af7c8dbef4688bU, 0xc0882c3ac065e38bU, 0xc0aada3940aa37b3U,
  0x40b58a28c077fd03U, 0x3efd857240b3700aU, 0xc078d1e4c0630fffU, 0xbe413d31bebdc2b2U,
  0x401535cc407b1027U,
};


ai_handle g_expert_a_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_expert_a_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

