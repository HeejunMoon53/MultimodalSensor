/**
  ******************************************************************************
  * @file    expert_a_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-08-14T22:24:58+0900
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
  0xbca36528bf8c0fa9U, 0x3f194e0fbea666b2U, 0xbe1600fe3ee0e650U, 0xbda98402be0c0ce0U,
  0x3e1eb80b3e288c62U, 0x3f29349cbd0fefbfU, 0x3eb1ef073eb400b3U, 0xbe9d891bbdd912cfU,
  0x3d4a7672be17fde1U, 0xbe76542e3e07bacaU, 0xbe5e4e163e8e16c9U, 0xbe841e3cbeeebc9fU,
  0xbe6331c2bd49f349U, 0xbec53c3a3cd153fdU, 0x3e18b5723eebd802U, 0xbec6e0f5be2fdd8cU,
  0xbe613a693f56c39fU, 0xbe0df90b3e213064U, 0x3da9a8a5be87989bU, 0xbec32f97bd672eb3U,
  0xbe8de3a13f385fc9U, 0xbd6ce8e23d47171fU, 0x3eec1c1cbf8d8801U, 0x3e9cf41cbe7bc573U,
  0x3e3f96bc3e7b71b0U, 0x3e95fe15be1665e9U, 0x3ea8d4273e29f06dU, 0xb9034ebbbed805a4U,
  0x3f08f73fbf8c8c3dU, 0xbd63b5f33e1174dfU, 0x3ed4290abf3d5259U, 0xbebf7903be023676U,
  0x3e9ba24abfc3ce8fU, 0x3e9f2e97bd205c80U, 0xbeb9dda73e7f082dU, 0x3e55dfe7be09f88fU,
  0xbe6c7e3d3ec8cd62U, 0xbf00c4303d88c62eU, 0xbf378ef33ebb029dU, 0x3cbd922abaa21520U,
  0x3e0e475c3efa2c51U, 0xbe2e083c3de7fc9dU, 0x3e0f0f473efc19c9U, 0x3ec667f9bf3a401dU,
  0x3e2c1e1cbe1044f4U, 0x3d9a86243e8fe5ccU, 0xbe15fe843f737a67U, 0x3dacfdd23d6441a6U,
  0xbf1d4c943f63dd79U, 0xbf902d803f9084c6U, 0xbef78e663f007855U, 0x3f5553e13f2fef71U,
  0xbc38c16cbedc6de2U, 0x3f9d3c56bd25b75bU, 0x3f3b56eabf3edec7U, 0x3f3709403ead0637U,
  0xbed08ee23f83572dU, 0xbf6184cb3f6ce4a5U, 0x3d47004a3d5baee6U, 0x3e558ff33f1aee34U,
  0x3e5cc4503eb5c6caU, 0x3eab0cbebf0b3afeU, 0x3e1eef413eb02af2U, 0xbd3bdf213f04ed0bU,
  0x3e8f8d26beb10aadU, 0xbe6c9bc53ddac354U, 0xbe7c9030be97ae78U, 0xbe9248953dbc1394U,
  0xbd9af2b93ebdbcfcU, 0x3ea050563d9072daU, 0xbe7e5359bdd74fc4U, 0x3ec606773cc31ba6U,
  0xbe4a13f6bd8526d4U, 0xbf05e7eb3f2c6e44U, 0xbdbc5aaf3ef26881U, 0xbe165028bde968baU,
  0x3bfd50383ba4eff6U, 0x3e8e3a1e3e80d3baU, 0x3e368afebf091dcaU, 0x3f130315bec924f5U,
  0xbccda9103e7c2b8eU, 0xbec4601abe650c3eU, 0xbe615f733ee277b7U, 0x3e249ebf3f40aa90U,
  0xbea503b4bca08b5dU, 0xbe898212bf14929aU, 0x3e7b49ba3ea7a8cfU, 0x3e7951153e8b49fdU,
  0xbde1adba3e789148U, 0x3d9899773e9862cfU, 0x3ea85d75be1ae9cdU, 0xbdcf46cbbe010e57U,
  0xbefc658fbec16805U, 0x3fa082b6bca5967aU, 0x3e84d6e33e4bdbc7U, 0xbe9e276e3efedd37U,
  0xbe6ad2d8400e2955U, 0xbedfeb1e3f036d57U, 0xbef4a4ec3e5bcfb9U, 0xbda69b593f83b623U,
  0x3ec3abf9bf47e8c5U, 0x4001c6d2bf5bc8cdU, 0x3e79e455beed1f3aU, 0x3fca865c3f810cd3U,
  0xbe05855340132e3bU, 0xbf2b6b2f3e032fc9U, 0xbf0f28c2beb948ccU, 0xbbec88a33e77068eU,
  0x3c0ba0af3c63552bU, 0xbf09aacf3fa39426U, 0xbf245b6f3e9efee5U, 0x3e366e1a3dc90ea8U,
  0xbf291f3b3ebade83U, 0x3f9100c7be1146e0U, 0x3df1bd9bbe1b724fU, 0x3f0d2d66bab7cd72U,
  0xbf015f713ef47b1bU, 0xbf4e40c0be7c7fc3U, 0x3f4a226f3c362b85U, 0x3f5c08093ea5c328U,
  0xbead82914020725aU, 0xbefbe7b53e655115U, 0xbf04b56c3db6b979U, 0xbd2d16573f786820U,
  0x3f07bf65bfb93c02U, 0x400b38d8bf68ade7U, 0x3e3f5f96be2f6658U, 0x3fa863c83fefca1bU,
  0xbf2c41fb403d2352U, 0xbecff8edbe8d1163U, 0xbf854607be040262U, 0xbe57f9ca3ee26cd4U,
  0xb882ebcbbf9ea32cU, 0x3ea84771be4c3fa3U, 0x3e49e34bbee101fcU, 0xbe6c7984bfa185b0U,
  0x3e9d4a523ef3e732U, 0xbf93a6f93d4cd381U, 0x3e8750063f807767U, 0xbdd72bc63e3f8ab1U,
  0xbe83ef27bf8258e5U, 0xbc584508bf738682U, 0x3f44fe843e7c362cU, 0xbd9f41283e96da8aU,
  0xbe188d983d1cd254U, 0xbf4b5a4abe9a8e32U, 0x3dfc3c823dcff682U, 0x3f13ffbc3ec9f550U,
  0x3e802825be03c3caU, 0xbe5cdb513e062f10U, 0x3f46a37dbecc76e1U, 0xbd618ad2beceeeadU,
  0xbf0bbb583dcf7e7dU, 0x3f68f4ce3ec2622fU, 0x3e94a4693eef5f84U, 0xbe3efe203e2723aaU,
  0x3e12ec2b3e958642U, 0xbe81f7313f11c452U, 0xbe466874be96af42U, 0x3ecab8cbbe9133fbU,
  0xbef4912ebdc8d746U, 0xbcbb69b6bdee542fU, 0xbe1f12dfbd691f10U, 0x3f1d69de3c70d1acU,
  0xbdcb5d8c3f66d9d5U, 0xbf058826bf111458U, 0xbe815cc03ee8481aU, 0x3e238677be94f86dU,
  0x3ecbd80ebe6613a3U, 0x3f11a68abe57640eU, 0x3f158f2c3e0af9ceU, 0xbeeaa0a93e0d528fU,
  0x3eac438a3e1fdc82U, 0xbeb6556d3c524ff5U, 0xbe49da64bda01096U, 0xbdb9a0af3dc94cfdU,
  0x3f1a3dea3e1391a7U, 0x3de7d8c5bf1482e2U, 0xbdddc9853e90d00aU, 0xbe115d07bee5a64eU,
  0xbf177066bcd09d61U, 0xbdfe3f1b3eeea885U, 0x3e4d03683ec6d743U, 0x3e5224e83cdc73ddU,
  0xbeb0fdfa3f10fc3fU, 0xbe6ed601baf223b1U, 0x3ea18effbf036792U, 0x3ecfd9c0be47bb31U,
  0xbf311bc63e0ee488U, 0xbe3d586dbe8d3db4U, 0x3e19cd27bdb012d6U, 0x3db2bf42bd030e02U,
  0x3f1fee9dbf7eefc4U, 0xbc8fa06b3d35ebb1U, 0xbd9c2db1be6b5e3eU, 0xbf134ddfbe7ed0e8U,
  0x3edb852bbe0ab89eU, 0xbf25b38abecd8800U, 0xbedc89b63d2a4ca1U, 0xbeea891e3e7d668eU,
  0x3f25cc9fbe9fd2cbU, 0xbcbc6eb1bda0f1f2U, 0xbef46a733e9e1215U, 0xbd86e9d0be8301a2U,
  0x3c91a7973e93f936U, 0xbf06fe813f12f311U, 0x3e3b1ba13de78119U, 0x3f0661ef3fad57bcU,
  0x3ea1db49bd9425d8U, 0x3f55b2ec3f445554U, 0x3e07ab59bf679883U, 0x3e2a4bb6bedd351dU,
  0x3e2525283ef5daa9U, 0xbe61826f3f888cd0U, 0x3dbb5820bd71d55aU, 0x3de293babd5965f6U,
  0x3eb4577d3da53278U, 0x3d3853863e7c5110U, 0xbe18a8b1bc8d9e33U, 0x3df0e3443edcc3e3U,
  0x3ec56dd4bea25183U, 0xbec4622dbdaab107U, 0xbdf37830bdbe6590U, 0x3e26e60ebec66e38U,
  0xbe19d8efbe31dd62U, 0xbe51135e3f33470dU, 0xbda50c42beeddfd3U, 0xbdf9ec433e8492e2U,
  0xbf29c8963d9153d1U, 0xbe8f1dbfbed692d8U, 0xbeba3e60bd868e8aU, 0x3eb019e7bee0c7f8U,
  0xbd99fe8bbec181daU, 0x3e213bba3bc7c522U, 0x3e4b58d6bdc70976U, 0xbd6ffe8dbcd9e3eaU,
  0xbef3ef67be9ac4c4U, 0x3f6f0d963e607768U, 0xbe75532f3ee22c67U, 0x3cc923413ddaaf1aU,
  0x3e204fccbd81d8ddU, 0xbedf5d9cbc327b9aU, 0xbcb921b5bb71ab92U, 0xbc74931fbf446176U,
  0xbe0869ad3f437e3cU, 0xbf97172dbdb705a7U, 0xbe037d583e01aab0U, 0xbea2cc523d549027U,
  0xbea8bae4bf7f8d05U, 0x3ed834cfbeaee2eaU, 0x3f0814d93c40e4a0U, 0x3f00b5a83ee20e9fU,
  0x3f166ee0be6ee798U, 0xbea6afdc3f1bf0efU, 0x3b7e86f33d95851cU, 0x3ebc73a9bead6b8dU,
  0xbd5c09273e82e778U, 0xbdf8f7f43ea9ffa5U, 0xbd84d7d1bd37ebaaU, 0x3efbe8d53ed994caU,
  0xbf5987ab3f086091U, 0x3f4ed8dabf87bcc8U, 0x3f1969523b7fe5c4U, 0xbf2f05babe544d2cU,
  0x3f0d664c3ef04893U, 0x3ef996ffbf719dd2U, 0x3eddb1d13eaf6f06U, 0xbf89f77fbf6035aaU,
  0x3e388dd3befcd42dU, 0xbf8bebe53f9c442bU, 0xc02628f6bf4a98aaU, 0x3faa19de3efd42e1U,
  0xbe1bdf9cbe3ca217U, 0xbf551be03e8cba20U, 0x3e503f323ea63dfeU, 0x3ec924be3eb87572U,
  0xbc5b2453be12702eU, 0xbf9893af3f8f552aU, 0xbf9d29cebda3b210U, 0x3f0663f73f75710dU,
  0xbf175e93bf8cd0f4U, 0xbf188a053f42a774U, 0x3d62c55cbd3eee99U, 0x3f4f7c413f9a26a7U,
  0xbeb5197c3f1e281eU, 0x3f80f3743f77f9abU, 0x3f01d7efbf2ebd0cU, 0x3f506c1ebea1cc49U,
  0x3f3ee2f5bf845697U, 0xbdddb629bf1b2a4dU, 0x3e7ee0d23fba0d99U, 0xbe9d22c93e0d5fc3U,
  0xbef7496cbde44795U, 0xbd6c030bbf15991eU, 0xbdd6ba64bf51f210U, 0xbf49e0153c900995U,
  0x3eb1a69fbf480eb2U, 0x3f98a458bf2dc82aU, 0x3e3b59993d94e4dbU, 0xbca92a7dbf89605fU,
  0xbf6a92813f460464U, 0x3ed7ae093df100c2U, 0x3fae9bc8bf6ba03fU, 0x3cd7ad74be86d38aU,
  0x3f35c1263ed92c87U, 0x3eb1aebdbf6ab8e0U, 0x3ebf253e3f72c3e9U, 0xbf4925acbf30ddc1U,
  0xbc1800a7bed097a0U, 0xbf259964bf1d8d36U, 0xbf07d37f3f9f9de7U, 0xbf41cfd13f2dfaecU,
  0xbecc425f3f8c4ce8U, 0xbf21aa113e1e0c02U, 0xbf5a2bf5bf1526c8U, 0x3e713d593dc1690aU,
  0xbf462f163f0ce351U, 0x3f0332a33f6c94bdU, 0x3f5d16debf0b1464U, 0xbe8f7e1ebeaa902dU,
  0x3f3c2193bf306f25U, 0x3e53d681bf450e80U, 0x3f64c42e3f5cf9eeU, 0x3de597ad3d0d6f39U,
  0xbe1ed8b43da4ae03U, 0xbd8f1bc43eb5f87aU, 0xbf8e0f85bf239170U, 0xbf227e9c3f05b153U,
  0xc0016b12c06ad149U, 0xc0b8973e3edb437cU, 0xc08815d3c0892d41U, 0xc0a3ea7540b39b02U,
  0x40ab34a8c0978397U, 0x3f9ee00940b08df1U, 0xc072fae8c06f5d8aU, 0xbfc6f1e1be954d0aU,
  0x402aea1d4082d0b6U,
};


ai_handle g_expert_a_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_expert_a_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

