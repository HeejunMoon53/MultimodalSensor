/**
  ******************************************************************************
  * @file    expert_b_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-09-10T00:33:05+0900
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
  0xbddfd5ca3de4613dU, 0x3fc36a6cbee785feU, 0xbeec1a1a3e7634eaU, 0xbf2a0697bdb7a937U,
  0xbf3440113f2a160cU, 0x3ebc8942bde49892U, 0x3e477906be16c79fU, 0xbeecc0533ec0a5d4U,
  0x3d5916cb3dd7dff0U, 0x3ed5bf783f450a6dU, 0xbef35c853eed4e0dU, 0xbee70ee3bf0700b9U,
  0xbf904878bf8db262U, 0xbf578667be1d2298U, 0x3e5803633f77838cU, 0xbf0a6928bd80119dU,
  0xbdc93af43f0fd97dU, 0xbe914b30be0acf7fU, 0x3e907495beaef707U, 0x3bb464eabe23b164U,
  0xbf3ca8cf3f28884fU, 0xbf0720ae3e3fc6f9U, 0x3f10f56d3e3f3d4bU, 0x3de1b60cbef0df90U,
  0x3f0d87103d3a85a1U, 0x3e941272bf1cba46U, 0x3f3de7cc3f2269b8U, 0x3ea084cebf82bbbeU,
  0x3f7f46c9bee4f41fU, 0xbe07362fbdea2dffU, 0x3ed276ddbe0d0b0aU, 0xbf0b75c63ded1babU,
  0xbe9b92eebef0b097U, 0xbebaf7563eb9976aU, 0xbef5528f3e16bb83U, 0x3eb7b535be95666dU,
  0xbde2dbbb3befdb9eU, 0x3d45cb063dab5b89U, 0xbeedbff4bf05062eU, 0xbec5e6d2bdcf4fd8U,
  0x3efaad493ef2e1e2U, 0xbf287a0d3f17cc56U, 0x3f1002c33de4c59fU, 0x3ec23b63bf57c4beU,
  0x3d96eb1ebe1f005aU, 0xbe4753d83e47970aU, 0xbf2d023d3f7ff58dU, 0xbe33a7ee3ede1f86U,
  0xbf7479823f8dd5e2U, 0xbf1b58513d7cbb44U, 0xbefce1833e728f35U, 0x3ee4956abd403fc8U,
  0x3df61047bf00a05dU, 0x3ea215913eb59ec7U, 0x3f2ab4aabed13c24U, 0x3ea58418be35ea3bU,
  0xbea5a8d83f0d2de4U, 0x3f1f35ce3f24609fU, 0x3ebec2703f00db12U, 0xbd4ad0f43f2205f9U,
  0x3ea3688fbf2b8056U, 0x3edc02bbbf0cd7b4U, 0x3e6487d23ee4ea1dU, 0x3e691cb53ea183b3U,
  0x3d59bc2ebdb4219aU, 0xbf08b02b3e6cc1c5U, 0xbe844b7dbec19d1cU, 0xbdeb26633e0a45dbU,
  0xbecce6563eabb8e4U, 0x3f0d2d60bc8b395fU, 0xbe743359bb2a6e8dU, 0x3f5675683dcab90eU,
  0xbbfc9e48be064d02U, 0xbe16519fbf255eccU, 0x3e7a7fb33ed24dbbU, 0xbe96d13dbeb996a4U,
  0x3e98efe0bdacdfd0U, 0x3e563d133f09896eU, 0x3bbdfc2ebf42b9a9U, 0x3fb2f278bbad0fe7U,
  0xbe0fc04d3f121029U, 0xbe6bc71abe731b72U, 0xbef4139d3ee72703U, 0x3ebc06223f22abf1U,
  0xbe97dc8e3e191816U, 0xbe787380bf459e68U, 0xbf4e24253be00da7U, 0xbeac00e2be608bf2U,
  0x3ea41ad0bf13452dU, 0x3ec1c5efbe3d7c18U, 0xbef3e6453e020287U, 0x3ec5be253f3dba7fU,
  0xbf8b92373e804b11U, 0x3eddb8fcbe148eb7U, 0x3eb2d2443e7a3529U, 0xbf825ae43f0ff1deU,
  0x3e1457423dd10645U, 0xbe9bb1893f3dcce4U, 0x3eff26bdbe865cd2U, 0xbe1f9dbe3e2254e2U,
  0x3e3ca2ea3f0afdafU, 0x3ebfc075bdd71cb4U, 0x3f53f657bd9d42fcU, 0xbe57f88bbf0fee5cU,
  0x3fa466dfbda22ab0U, 0xbe798e53bec5fb44U, 0x3f85fd9bbf28a727U, 0x3e1d9bd2bea82ac4U,
  0x3c9bc2463ea5f143U, 0xbd40972e3bcd77dcU, 0xbe51408d3ebca133U, 0x3e2d6647be06f439U,
  0xbf6499143f17dfe2U, 0x3f0db2833ea4769eU, 0x3e808614bea12c9cU, 0x3e7d2a03bd849ca5U,
  0xbec49b403eb0abb1U, 0x3def7deebecc8cf0U, 0xbe5ab7d73e4a7202U, 0x3f8e33ec3e180183U,
  0x3ea8626dbee1e309U, 0xbd77a33e3e4a190bU, 0xbe32c3dabecc1b77U, 0xbda0e2f53e859924U,
  0x3e0a693e3f28602fU, 0x3ea87f6bbf818a0cU, 0xbe43041e3f983dcdU, 0xbf393e083f814baaU,
  0x3f191ae1bf552674U, 0xbeff9075bf7776f6U, 0x3d9336b6bf062638U, 0xbf3ce1b4beda7d7fU,
  0xbe4c76cdbf1b82dbU, 0x3ec3b325bed0c024U, 0xbe8d5759bf041290U, 0xbe10c09abde642c0U,
  0x3eafcfb33f21e7afU, 0x3e47e1f43ec0e61fU, 0x3ed35b2b3e8c2e21U, 0x3de1cf543ece96ccU,
  0xbf12a67f3e399ef5U, 0xbeaf2270be84749dU, 0xbcf721dc3ee9afc8U, 0x3cfcd1ca3eab9d1aU,
  0x3d547895bf0dc2cbU, 0xbede94c1beba4cefU, 0xbf0ca6babe9021deU, 0x3d8a86d93ebe300bU,
  0x3f0fb42fbf0a4cb0U, 0xbe6c3d40bedab935U, 0xbeb3ad423e9a9f10U, 0x3df3ff1b3e794b91U,
  0xbf4c6ea43e274d5bU, 0x3e79433d3c0f95bfU, 0x3e8e50a83eb5b8cbU, 0xbedf25dc3ea39471U,
  0x3f64ab8bbff96981U, 0x3ee90392bf198ddfU, 0x3f8affb6bf382b3fU, 0x3eea03af3e84496aU,
  0xbd9b50353eeef70bU, 0xbecdb94f3e864e20U, 0xbfa916a9be66c78eU, 0x3b2b160bbe449562U,
  0xbcd3211fbdf0143aU, 0x3d871fc0bed0f8e6U, 0xbf4052893f450909U, 0x3e45633dbef77ac2U,
  0x3e708cddbf12af20U, 0x3f06034fbd82a048U, 0x3eab69473f4bcb1aU, 0xbf02500b3f00b311U,
  0x3da1fc623e3adc98U, 0xbf4b20ed3e1891bfU, 0xbf5a9d3ebeb4dd03U, 0x3b811a60be4ddef2U,
  0x3ec4f97f3e825902U, 0x3e9b308dbee4cf41U, 0xbfbe92a93ec4ebafU, 0x3db6ea76be2e9f53U,
  0xbf1091283ed64347U, 0x3ea2c5a4bdf303b5U, 0x3dbc069e3d447297U, 0x3e10f66c3ef4a1bfU,
  0xbedcaf5a3ee0c8c2U, 0xbe97a65abcdfdcf1U, 0x3e73fa81bf2d7092U, 0x3e913b403e0c435fU,
  0xbf518b1f3ecc210bU, 0x3e160ee2be9685f8U, 0xbe687ea93d675883U, 0x3ec38c9ebe3e2ff4U,
  0x3ede007ebf24c275U, 0xbdc0f11d3e0de168U, 0x3e10a9e6bdb55bf1U, 0xbf0debf53e86e33eU,
  0x3f1d9f6ebeafda0dU, 0xbf227545bf1fa389U, 0xbefcf9ffbd0bc66aU, 0x3e3a6be33e49e7f0U,
  0x3e26fc163d2ba48aU, 0x3f14467c3e9351ccU, 0xbf263b91bc4afc39U, 0xbf17c7cb3bef08e9U,
  0x3edc1f60bea478b8U, 0xbf1108523ec62ce8U, 0x3dbeffe3be8a4773U, 0xbe9d03923f4f7bf1U,
  0x3f5129c2bf0f8f89U, 0xbc81d623be05e747U, 0x3cd9c1b8be919a5bU, 0x3dd559e1bdd2ade3U,
  0x3e9859f13e577ca1U, 0x3e8e87b73ee7cbf3U, 0x3ecd3613bf0cbbfaU, 0xbf445efdbe55bee3U,
  0x3f99ad09bf63844fU, 0x3e6678223f3954fcU, 0x3f8c7eedbe3e0823U, 0xbd78badabd6607f8U,
  0x3df9202fbe53bfc4U, 0xbef69d69bf27254aU, 0xbee9d98f3e8c535aU, 0x3dda9d603ea1a952U,
  0x3ef0611dbde82a68U, 0xbeee10963da9a602U, 0xbf3e4523bf31c566U, 0x3ddc3342be107a3fU,
  0xbf1dfed7be23bcacU, 0xbd4e9395bf7f66b0U, 0xbf82484bbd528a9dU, 0x3d5e6076bf55f370U,
  0x3eeb3f29bf396298U, 0x3ed6ed77be07b81dU, 0x3d1f613e3dec0e06U, 0x3e4484ca3f00b6d1U,
  0xbf46ef6ebe1abb83U, 0xbe1fb6ea3e287d11U, 0x3df4ab353e8dea95U, 0xbed9608d3dd1f4f7U,
  0x3e459d52bedb4223U, 0xbecff8423eeaf896U, 0x3ec557f3be590059U, 0x3e92d739beb863e7U,
  0x3ee369853e8ebc5aU, 0xbe52afb3bedeecc2U, 0xbf0be1c23e936db6U, 0x3c90b25a3eeabf93U,
  0xbf16d5a03d4a6716U, 0xbe2df8983e06aa28U, 0x3e827864bd84ee56U, 0x3ea3cfa93f145b4fU,
  0x3edf2b98be802f39U, 0xbf125e893ed67c01U, 0xbeef0453be9517f8U, 0x3e239722bed08278U,
  0x3bc7620ebe43fe70U, 0x3e9b24553d1fc518U, 0xbe9a6326be3e225eU, 0x3f2165443e913fe2U,
  0xbf3edc133e232d03U, 0x3fbcf5f6bed592a1U, 0x3df0c797be601f84U, 0xbf361c713ec01105U,
  0x3e03a16ebeec9447U, 0x3e469907bf9b48a2U, 0x3f297f3c3e571b59U, 0xbd699f1cbf48050dU,
  0xbc5da489bf1a59e8U, 0xbf91394bbe0dcab6U, 0x3d46d2a5bd99ffb6U, 0x3f391fde3f2f0bc5U,
  0xbde16cd7be65b5a7U, 0x3e195a79bde02728U, 0x3f32aa1f3e1f23e4U, 0x3fb62edf3d317c5fU,
  0xbf6e1217bf2d34c6U, 0x3f773c6c3ebabf19U, 0x3f8ba95e3c535935U, 0x3d90dae13e1b2783U,
  0xbe1c00cabefef523U, 0xbe150979beaee35fU, 0x3ea778d53e2a5509U, 0x3f8abce93edafd36U,
  0xbec046243ec98e2bU, 0x3ebc291e3fb135ceU, 0x3f5ca93abedcf39cU, 0x3f23feb5bf0dd63bU,
  0x3f8b3d49bfb5aa56U, 0xbf94634bbf7b003fU, 0x3f25d7ff3efd0b8cU, 0x3e8472db3f6aa28cU,
  0x3ce89638bf27a2f1U, 0x3d714a90bfc297f6U, 0xbd7a6acabf307cd0U, 0xbf0fc912bf52be8eU,
  0x3d85fdc2bee81d5bU, 0x3fb033093e5aae61U, 0x3f158f963ec25e32U, 0xbeff2dc6bf9020bbU,
  0xbf35b28b3e8ab9d1U, 0x3d0d2e30bf3e5321U, 0x3ed00458be1da451U, 0xbeee3cc0bd769a4bU,
  0x3eef11663c2acf30U, 0x3db9d9d9bf2de5a9U, 0x3f3ae41a3f483afeU, 0xbf00b7cbbf57443fU,
  0xbd5ab1c8be0d58f5U, 0x3e337bd2bca101bdU, 0xbf27ec3b3f2a6950U, 0xbe7516193f7e7030U,
  0xbf563cbd3f4b4e6eU, 0xbf1b07b33e518438U, 0xbf84ba513be6183cU, 0xbfa10bc7bf6f40ccU,
  0xbee9248b3f73845fU, 0xbe7cb3cf3e4cb0f4U, 0x3ea4f090bc9e00e3U, 0xbf176d26bf48892cU,
  0x3fa8dbc3be736f1eU, 0x3edfa9e8bedaa6cdU, 0x3ea0e5b83f940641U, 0x3f6e0aa23f4a9776U,
  0xbcfa4d2a3df28572U, 0x3c2f42c53cccde97U, 0xbf5467d4bec8fda4U, 0xbee261003dee968fU,
  0xbf93bd9dbf8307c0U, 0xc044f4f2c001e251U, 0xbfb1ab96bff30039U, 0xc0168ae3403e27f4U,
  0x40514767c013822cU, 0x3e2e6d8640440f9cU, 0xbff3d1bdbfa303c5U, 0xbf8187dd3f178e87U,
  0x3f3e75623f5db457U,
};


ai_handle g_expert_b_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_expert_b_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

