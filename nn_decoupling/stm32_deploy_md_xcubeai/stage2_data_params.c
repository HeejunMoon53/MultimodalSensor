/**
  ******************************************************************************
  * @file    stage2_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-06-11T16:43:34+0900
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

#include "stage2_data_params.h"


/**  Activations Section  ****************************************************/
ai_handle g_stage2_activations_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(NULL),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};




/**  Weights Section  ********************************************************/
AI_ALIGNED(32)
const ai_u64 s_stage2_weights_array_u64[385] = {
  0xbe6c6290bead0362U, 0x3d9423543e7f896eU, 0x3e630c8a3e331c7cU, 0x3dc91a783e43844fU,
  0xbe02e41cbf009085U, 0xbe85dd5dbe4c6516U, 0x3e16ce4bbee3f1b2U, 0xbd93f5113ee8dffdU,
  0xbef8c49c3ea03a70U, 0x3e2f54d8bdf409f3U, 0xbe3c5ec4bed7aabdU, 0x3e2b140c3ef74093U,
  0xbec590753ef1a850U, 0x3e48b2bbbedf5e61U, 0xbe17c782be8249b7U, 0x3e662bbebe982eadU,
  0x3e2dfa7bbe84105fU, 0xbeb4ae783e7683e7U, 0x3e8ca336bd841cb4U, 0x3eca2d22bded474eU,
  0x3ebdfcd1bd2a0735U, 0x3ed93c21be83ae52U, 0x3e80bf81bebe5f47U, 0x3ec28f12bebbc3b2U,
  0xbdda324ebe6e9bd9U, 0xbee195953f124302U, 0xbeb72f31bdd3c96aU, 0xbe0a8ee8bcf93cccU,
  0xbe718df73e9d0135U, 0xbd6d14a9bedee416U, 0x3eaa602dbddbf71bU, 0x3d3fb982beb255daU,
  0x3d39ecabbe4ded36U, 0x3e0cd0aebefc4353U, 0x3e9be711be6c2b31U, 0xbe24ba7d3e45ccc5U,
  0x3e85b81abe9bc2f5U, 0x3d7f4b4a3e27b1a5U, 0xbe5910253e0241d4U, 0xbec7ea26bdf16e0aU,
  0x3d337ea83ea14d39U, 0xbe2a3746bdbab2cbU, 0xbd857982bca44243U, 0x3ebc7a3f3e7934b9U,
  0x3cfa330a3edcc5ebU, 0x3dccab16beae7d8dU, 0x3bbe84293e39feaeU, 0x3d9ca5353e6b837bU,
  0x3ea3c2e8bd7a76e4U, 0xbe4cabeabed166b9U, 0x3db3468bbe3fee23U, 0xbe8030393e40bd32U,
  0x3eb06bdc3df415fcU, 0x3e8a31de3e8db16dU, 0x3e877efc3cf1f317U, 0x3eaebe3fbd39d6c0U,
  0xbe26a83a3d050572U, 0xbecd4ade3d9c0943U, 0xbddebb06be44fcd6U, 0x3e384006be5f6e89U,
  0x3eae65183db6e335U, 0xbea504c83e63cb6fU, 0x3db9b5533e693b3cU, 0xbe8a6cd9beb7670eU,
  0x3db2bd0fbd96b0b3U, 0xbeb86bc83b7e62e3U, 0xbbf932fb3e049ad8U, 0xbeefad503ebb36b1U,
  0x3e972fe8bf4277a1U, 0x3e2c3e243e823f07U, 0xbbb4b51cbe5c9e9aU, 0xbd5e45133e3596c3U,
  0xbef08229bd487bb4U, 0x3e974efc3e5886eeU, 0xbe4cdee6bdb6ca21U, 0x3e236f043d6de071U,
  0xbf3f27693e44d42fU, 0x3e8c7bf93e480604U, 0xbde8e7acbe9a9cd9U, 0x3d59151f3eb1292bU,
  0x80000000U, 0x80000000U, 0x8000000000000000U, 0x8000000080000000U,
  0x8000000000000000U, 0x8000000080000000U, 0x80000000U, 0x80000000U,
  0x80000000U, 0x8000000080000000U, 0x0U, 0x0U,
  0x80000000U, 0x8000000000000000U, 0x0U, 0x8000000080000000U,
  0x3e3e3cd0bdf63a09U, 0x3d2ae243bd0473c5U, 0xbe33fa0f3c91256bU, 0xbd54e2283da72803U,
  0xbddd158fbf99d269U, 0xbd98044fbe5002f4U, 0xbe33aee8bf0ccaffU, 0xbec98c77bc817decU,
  0xbef7018c3e68d7f5U, 0x3e8e6e1ebe36f8a3U, 0x3ea879663e6d0385U, 0x3ed6abde3e7f7065U,
  0xbc036a9b3df53cabU, 0x3eafe831bdab4cecU, 0xbea61285bcd7f726U, 0x3d7adacfbd9c0939U,
  0x3e8f3e9bbe9c5da5U, 0xbe9997e4be339174U, 0xbd9b3ff3bf024962U, 0x3ea09023be3f4911U,
  0xbea4bf9d3f518062U, 0x3e8fb0443bdf921aU, 0x3f069cbdU, 0xb686d4ed3e1b80ceU,
  0xbd136308bf0a188eU, 0xbe677cd93e1703deU, 0xbee7775a3dec8705U, 0xbefa63b5bedca7c5U,
  0x3f0fb6203dc6a8bfU, 0x3ed455d0bd249772U, 0xbeaf8a083e6e37d5U, 0xbe0e1a24bdde1c37U,
  0xbe59e9663a85e6c0U, 0xbe3ab9fbbf897844U, 0xbe9726723e2aa3a4U, 0xbf5a8b7e3e405960U,
  0x3ee71b6dbea4f69fU, 0x3dce6d9b3e92e619U, 0x3d596367bd3956e2U, 0x3df51f603db57522U,
  0xbe5ef87b3d70488eU, 0x3e84df853e6450e4U, 0xbc362cab3e7d530fU, 0x3eafbde13e8b87b0U,
  0xbe15d8403e83202eU, 0x3bce57943da1ee92U, 0x3c916fcb3e9b75edU, 0xbe9531323e987525U,
  0x3e9ad16dbe2bce4cU, 0x3e6b21d73e88d14bU, 0x3e83ad39be5f5647U, 0x3e8c06963e3cdc32U,
  0xbd3a5f583f13bef6U, 0x3e2d3c24be96e313U, 0xbd30b6d8bd4b5282U, 0xbe46a88bbcbe7103U,
  0xbe326f663e6c863aU, 0xbe5c98d03e743f9dU, 0x3da669ecbeb8ad94U, 0xbf00b7c3becf1244U,
  0x3e7e0b8cbeaaa905U, 0x3e28357a3eaa281dU, 0xbdfb26913e104cc0U, 0xbe8cc5e9bdc4e924U,
  0x3aac6aa83db9bc0eU, 0xbdf6f0e13d8df109U, 0x3ea797d4be063bd6U, 0xbe8ded0f3ead4a03U,
  0x3e995448bea57983U, 0x3e3969443daf550aU, 0xbf061661be543712U, 0xbe2f56853e28bfb9U,
  0xbe3c39243e29130eU, 0xbea2d69ebcbd0865U, 0xbe006caf3d8e5421U, 0x3efb22ad3e31460bU,
  0xbde3a0d7bde66b66U, 0x3eb29a6cbe232e59U, 0x3cb9b28c3d9e5a23U, 0xbe731ab6bba5e163U,
  0x3dd487073decd230U, 0xbe02eab73892b431U, 0xbe4416aabc160aabU, 0xb425d1093cb5bf03U,
  0x3e29eb272908f7aaU, 0x3e1fdcf63e27dc5dU, 0xad92daed3dbfc185U, 0xb72221cfbcff48d4U,
  0x3dfb1eaebda21737U, 0x80000000ba80bd95U, 0xb2456b12bcd564adU, 0xbd81689bbe2be49dU,
  0x3cfff1fd3e512d2eU, 0x3df63eba3b06c6f4U, 0x3e0cca65bc50ba0bU, 0xbe1aadaa3d139061U,
  0x3e6657c5bc85baecU, 0x3dc157ee3dda2119U, 0x3e3eeeb53eaf8e7cU, 0xbdce3fecbd64971dU,
  0x3e9f0823beeb609fU, 0xbe16eb863e5cc08dU, 0x3e19e008bf074c1eU, 0xbd14bfbc3cf2f43bU,
  0xbf04adfa3eacea89U, 0xbe7a9d283e5246ddU, 0x3ee337ff3d311e7aU, 0x3f14d55c3ebd3dcdU,
  0xbf3d88fc3ec1d498U, 0xbdec1a973db70886U, 0x3d13c676be283635U, 0xbcc99311bb9b8b9dU,
  0xbd244ac8be2d71c9U, 0x3eb40e073c5fb104U, 0x3e2cb6d5bdb3d319U, 0x3eb188cfbee59707U,
  0xbde75e683e137b76U, 0xbb0fcf693d8dd4c9U, 0x3d560bc03e9a57d3U, 0x3d0d01fabe7e8e52U,
  0x3eb93115be5cbcc1U, 0xbe35d226bd849527U, 0xbd83718dbbf8ecbfU, 0xbe80e45dbf19d2f3U,
  0x3f1e8d83bd991983U, 0xbd431b953e59e484U, 0xbdbc3f723ed40dafU, 0xbeae02bcbeb5f610U,
  0xbe1939053e3f7875U, 0x3bb421693ea1c832U, 0x3c80159ebe95c78fU, 0x3e0db0a53ebf1dfeU,
  0x3dda6279bdf71ef2U, 0xbe1996fd3dc2ca89U, 0xbe220e54bf094dc5U, 0xbf023f173e3f298dU,
  0xbe9040c53e144150U, 0x3db9112c3e6223aeU, 0xbe651c1c3e9f7830U, 0x3f129e9dbdb1042eU,
  0xbe149f963dd6ba50U, 0xbe8c6f923e946461U, 0x3e170bbfbdf3eba2U, 0xbea1f4e0bd88b975U,
  0x80000000U, 0x0U, 0x80000000U, 0x8000000000000000U,
  0x80000000U, 0x8000000000000000U, 0x8000000080000000U, 0x8000000080000000U,
  0x80000000U, 0x0U, 0x8000000000000000U, 0x8000000000000000U,
  0x0U, 0x8000000000000000U, 0x0U, 0x80000000U,
  0x0U, 0x8000000000000000U, 0x8000000000000000U, 0x80000000U,
  0x8000000000000000U, 0x8000000080000000U, 0x8000000000000000U, 0x0U,
  0x8000000000000000U, 0x8000000000000000U, 0x0U, 0x80000000U,
  0x8000000080000000U, 0x80000000U, 0x8000000080000000U, 0x0U,
  0x3e5df850bdd47fdbU, 0xbdcb79ef3d4b240dU, 0xbe53fa943e6db8ebU, 0xbeb2f5cdbc94b833U,
  0xbe0dd141bee50095U, 0xbc44fd8a3e973527U, 0xbf4760eabe8dd2ebU, 0xbef43a56be692c5aU,
  0xbcb406023f0d426aU, 0x3dd4b7c03e4aad7bU, 0x3ecad34cbe40367cU, 0x3f11436a3f0c27faU,
  0xbeb6dea53da2513aU, 0xbdd14015bd8b4c62U, 0x3ec19dd73af603cdU, 0xbda45fc4be0bc285U,
  0x3e6fe7f3bd9144a4U, 0x3e3e9915beb6a334U, 0x3e2e228f3cd78a23U, 0xbe4f19103e27314eU,
  0xbce7bdb2bbbe4b48U, 0x3c27b4803dc572e0U, 0xbf063553bcf74628U, 0xbb23b350be244cf4U,
  0x3e08ed613e912715U, 0xbe83035d3d831d47U, 0x3daff3513db7d710U, 0x3da568953e0e9db4U,
  0xbe851cccbe580ef9U, 0x3b99cf6c3e35b478U, 0x3e973fa7bcc9e071U, 0xbe0cbf543e195ebbU,
  0x3e2a6addbc696a96U, 0x3e86cbb7bea6c96dU, 0xbe92bb843dba12c5U, 0x3eafcd943e60c077U,
  0xbd0a8517bebbe1d7U, 0x3e9271df3e36942bU, 0xbe52741dbe646e62U, 0xbd890d213d081013U,
  0x3dc476843e00af5dU, 0x3ea44d6700000000U, 0xbf0bc8ffbf142b57U, 0x3eaeb400beaec943U,
  0xbadb10033da60db3U, 0x3dbf1988bf202b1eU, 0x80000000U, 0xbe80239d3d83227bU,
  0x383b887dba84b815U, 0x80000000U, 0xb3010e50a239f10dU, 0xbd8b601536d91f0fU,
  0xb986c733U, 0xabbccca23d8963d5U, 0x80000000U, 0x3d8ef92900000000U,
  0x8000000080000000U, 0x8000000080000000U, 0x8000000000000000U, 0x8000000080000000U,
  0x8000000000000000U, 0x80000000U, 0x8000000080000000U, 0x8000000000000000U,
  0xbd29a0793e8b9e72U, 0x3dc6573e80000000U, 0xbeb64a393e8102d3U, 0x3eaae7eb3ed6b858U,
  0xbe4a2724bd3000e6U, 0x3ef0bdcb3ee4c749U, 0x0U, 0x3dba96afbe0439b9U,
  0x3dcb1ae7bed5ec76U, 0x3e327afd00000000U, 0xbe9cf8a3beea97a0U, 0x3ec774fabe927abdU,
  0x3e57bc34bc34f440U, 0x3ecda1f1becfeebdU, 0x8000000080000000U, 0x3ed080413dc02e4bU,
  0xbf0489dbbe7a1a62U, 0x3e22616d80000000U, 0x3ec9d2823f50bea3U, 0x3db4a0fb3d452f31U,
  0xbf966c61bd81e1baU, 0x3e9cf4fa3ef7c608U, 0x8000000000000000U, 0x3d42d980bf31ca4aU,
  0xbed703cb3e1c30a4U, 0xbe45785000000000U, 0xbdbc0e4d3ea2f8adU, 0x3d02ced53f0ae5b5U,
  0xbf357685be6a00b6U, 0xbf0509e53ee4578dU, 0x80000000U, 0xbeb287e0be1f4a14U,
  0xbfac24073ea435aeU, 0xbeff1d2600000000U, 0x3e730cff3e49d9d6U, 0xbec0f3f63eebb698U,
  0xc014e4903dc19dc3U, 0x3cabef7f3e990e1cU, 0x80000000U, 0x3eb5601dbf2f67b6U,
  0xbe38fece3e1cc9e7U, 0x3ed4a4d0beb8b155U, 0x3ddb25803dc6a2d7U, 0x3e409ca93ec34a05U,
  0xb10133cabf36af12U, 0x3f072f0a80000000U, 0x3efd057fbf546dffU, 0x3f9918b73f148e48U,
  0xbe15d5d4U,
};


ai_handle g_stage2_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_stage2_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

