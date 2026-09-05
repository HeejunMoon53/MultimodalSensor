/**
  ******************************************************************************
  * @file    expert_b_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-08-17T01:44:58+0900
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
  0xbc803bb33e5adcfcU, 0x3ed2c217bdf95664U, 0xbe48ff503f385c3bU, 0x3e24f6cc3f1f7eeeU,
  0xbf55b1293f2302d9U, 0x3f1ba4ea3e5536faU, 0x3f16c69fbd832c1fU, 0xbf5c6ef13e5257fcU,
  0x3bc77b8c3d389f74U, 0xbebea4473f4ab368U, 0x3da303b6bde287c3U, 0xbf4f8f2ebe59407aU,
  0xbf21170c3eb51fe3U, 0x3e30f551be1a8500U, 0x3f3da1683f6df7d5U, 0xbe6df0debe67d332U,
  0xbe7a251a3f45d64cU, 0xbe9c893d3f139409U, 0xbcf1e35abe1da7ecU, 0xbecbd43b3d692689U,
  0x3ce90c863ed15a07U, 0xbf38b3c13efc8c8aU, 0x3f6fc8e03dc0004aU, 0x3f5c05febea8a989U,
  0x3ecf0e16beb0d307U, 0xbeffb07dbeecaaf1U, 0x3ea6a5b03f8f1774U, 0x3e966bc2beda96d5U,
  0x3f5f52a6bf37f624U, 0xbee6e10c3e8650b6U, 0x3f09a65ebe8e88cfU, 0x3d00f896be825ec2U,
  0xbe3802d1be8a614cU, 0x3f1b4af6bf8beccbU, 0xbf20973d3ecb97ecU, 0x3f0c38f2becb7f7dU,
  0x3e3080df3ecf1dfdU, 0xbf4f9d333faf1f1cU, 0xbf2327a13f05b14dU, 0x3eb53338bf085849U,
  0x3f2cb6b3bd9ed31eU, 0xbf4663c33e77e223U, 0xbdc7eced3f18212dU, 0x3f8a6bc5bfc86fc8U,
  0xbe81e4883da5063eU, 0xbec786853f6f1c28U, 0xbf9445ee3f0b6288U, 0xbf8c4fe23ec7363aU,
  0xbf3375f2bf5aa94bU, 0xbf331af93f15a569U, 0x3d6bd2573f2d52a5U, 0x3f72d3f83f026ffeU,
  0x3c4f88d1be2c94edU, 0x3ca530303e70b9bdU, 0x3f813618bed61632U, 0x3f2187e13d96a7b7U,
  0xbe8afd603eb5bb4aU, 0xbe819ab73ee2f331U, 0x3e8c59f43ed5f5baU, 0x3ebdd0ff3f1de093U,
  0x3d8f7ccdbdcd8f5aU, 0x3f3511ecbf92774dU, 0x3ebc44483f068bd5U, 0xbddd004dbe3d0562U,
  0x3ed128cabdf80e6eU, 0xbf57175d3e0c7620U, 0xbef6db96bc83c6c0U, 0xbe817f9e3f1f42b1U,
  0xbf492e483d2f4b04U, 0xbe5b3df53da73b28U, 0xbf0af4a93ed47e8aU, 0x3f550c3d3edd4afdU,
  0xbe3bba423d5778f6U, 0xbd714c9d3e77e46dU, 0x3e105c693f1858d8U, 0xbf46a3ffbd92f448U,
  0x3de83601bdaf0812U, 0x3e9799123e9002f4U, 0xbf2dd8eabf0ecfebU, 0x3e9defdebf7b4e0eU,
  0x3fb4a78d3ec22cb3U, 0x3df62e6fbda3f6d5U, 0xbebe1268bf05247aU, 0x3f20a7f73fba5214U,
  0x3e79144c3f601e53U, 0x3f62c8abbf79f266U, 0xbdd01b283e89e499U, 0xbe533450bf0ca36cU,
  0xbedc5b85bd7c874dU, 0x3f8835c0bd22c532U, 0xbea588be3efa5dc8U, 0x3e45e4393ec47f5eU,
  0xbf27af383de4f211U, 0x3d8be444bf0d3f0bU, 0x3e7c373c3d809c95U, 0xbf124bac3f3df42fU,
  0x3d51776a3d68383dU, 0xbf9d84ef3f8945b5U, 0xbef9db6abf852adaU, 0xbcbe5ce23f63e3baU,
  0xbe9f85053e9d6dcdU, 0xbd5f31a9bf96fda1U, 0x3ee1ac46beeb3b1cU, 0xbe76a97ac00c64dbU,
  0x4011f1b53e6b7de7U, 0x3f805a53bf1f8623U, 0x3f9b3a77bfdab002U, 0x3e8a858bbf4f2284U,
  0x3e89d1ec3e70a352U, 0xbe95fc583eb57a09U, 0xbf1664753e8cd525U, 0xbea3f359bc92054cU,
  0xbebaab6c3e9a2eceU, 0x3f0adb783df9afc9U, 0xbf04f9b7bdb5d6a5U, 0x3ee197e93e0da74fU,
  0xbdf6b9183ea4f0e7U, 0xbdb9faadbf067518U, 0xbf275b82bf1f837fU, 0x3f22275c3eb78923U,
  0x3bc0b5d33f8db3f0U, 0x3dfc8f5bbf011500U, 0xbd054255be86a2cbU, 0xbec78436bf2f436cU,
  0xbe9044193f817ee0U, 0x3ed818b6bd0d0023U, 0xbe27918a3f053aa5U, 0xbee2dd28bd56bb92U,
  0x3e940a0bbede74a6U, 0xbe25c11e3f162e74U, 0xbf0ebe0fbf39e9bbU, 0xbeb686813ee96d2fU,
  0xbe803e32bea9463aU, 0x3d07c6dc3f299e67U, 0xbe49c19b3ef5060dU, 0xbecbdc1abe139eb1U,
  0x3ed4ebea3e8cc7dcU, 0x3f649c4e3ee8ba3fU, 0x3ef618053d273650U, 0x3eaa5bef3edaef68U,
  0xbf1cf6943ee7adf0U, 0x3e74503fbdd2fa4fU, 0xbe6cb4213e407b46U, 0xbf4956f03f2aaa5bU,
  0x3edfd5b8bec3a913U, 0x3e027c66bf54116eU, 0xbcb7f48bbe3ccaf2U, 0x3f1566363df4b49eU,
  0x3e7b3ab6bef6867cU, 0x3ebe4321be704d2bU, 0x3f088b0c3f165800U, 0x3d4b1e83bfbb550bU,
  0xbe141e813ea56782U, 0xbe601eb5bf524efbU, 0x3fb9484a3f24a220U, 0xbf52a6c9bdaa9233U,
  0x3de928743e976048U, 0xbea5cff53ef97b3aU, 0xbe9b33fbbe3e7abcU, 0x3f2d885fbe9a173dU,
  0xbeb36f84beac63a2U, 0xbd77cc16beb3c444U, 0x3df8acb9becf3a97U, 0x3edd3afdbd8f4735U,
  0x3e67007d3f145739U, 0xbe5c705abef419b0U, 0x3eba78903ea4248bU, 0xbe59c003be94d5ceU,
  0x3f05ec5c3db89aefU, 0x3f712d9d3c8e456dU, 0x3a4ff4a53f1cfe18U, 0xc0011f803b03d146U,
  0x3cbf7bb93eca4015U, 0x3e1495683f129a31U, 0xbf89d3dd3e05c25dU, 0xbf079e1cbe551747U,
  0x3ed039553d342fd9U, 0x3e9ee246bf2ba424U, 0xc008c5a1bc1519a6U, 0xbf1fcf5e3e90d391U,
  0xbea320153e852a88U, 0xbf8793be3e686a74U, 0x3e1dfbf83e8c2e4eU, 0x3f1a7b723e3258d0U,
  0xbef0d4ca3e900a71U, 0x3d25da8ebe80b099U, 0x3efd1b96bf0a2bccU, 0x3f37f8d43e4ae234U,
  0xbf0580bb3e3ab15eU, 0xbf600ec2bf2b5d09U, 0x3f01f5fbbd4c0cceU, 0x3e875e3ebe38b17dU,
  0x3f385ac7bf2e2e6bU, 0xbd480cccbf8a08d8U, 0x3e9b6bcebf831dd8U, 0xbf8f27c93ea38fc9U,
  0x3f89bd233eec9405U, 0xbf95cbfcbf6a23fdU, 0xbff2b4d43e7e54ffU, 0xbf2dfbb73e47610eU,
  0xbe1d11f1bf9bdd68U, 0x3f03b65c3e08a698U, 0xbf6823473f154014U, 0x3d461494bfa8138eU,
  0x3ef36a59be8917e4U, 0xbe2c49e83e8919b4U, 0x3e388d84bf3ecaf2U, 0xbd7f03da3a63c9f6U,
  0x3e588bf73bfcfab3U, 0x3da3b64cbe34a36bU, 0xbe9d9c79be21ff41U, 0xbe42a3a8bdaaef22U,
  0x3e85dd72be8bdaf6U, 0x3db25bf83eeb0e8aU, 0x3da27eb0be2bf124U, 0xbf555bcabf932023U,
  0x3efbcc28be6c8b4fU, 0xbe325b423e86a942U, 0xbe813b60bf083fb0U, 0xbe003ce13d1ff3ddU,
  0x3dc39551bdd672e5U, 0xbe977497bf21f752U, 0xbe9505e4bd8ac117U, 0xbc996c19bdf0d4a7U,
  0x3e4d6fa8be79fa45U, 0xbdbff7aa3df41898U, 0xbd849e61bee526f0U, 0xbf09153ebed22b42U,
  0xbbb93538bdef2b4eU, 0x3f390ec6c01124afU, 0xbe3eebe6bf919199U, 0xbf8941f9be5dfe75U,
  0x3f233215bf207e22U, 0xbd13bde9befed68aU, 0xbf97f89d3f926801U, 0xbe9f5e693f56f75cU,
  0xbeb1053fbea6ce82U, 0x3e631921bf184341U, 0xbefe1e20be81d777U, 0xbef0e7c0bed900c1U,
  0x3df8670dbec8e131U, 0xbe892078bd4834e8U, 0x3e97856bbe90440cU, 0x3def58bf3e2d1fadU,
  0x3e8a0a603ea2e101U, 0xbed1414ebefcbd4bU, 0xbce2f36a3d97563cU, 0xbe3a42943e51a304U,
  0x3d533b0e3e015c2dU, 0x3e3d0f94bf0742b9U, 0x3ef4a4e7be6f1480U, 0xbdb232a73d77ef24U,
  0x3f04f210be332563U, 0xbedd08f43e39c36dU, 0xbec91d1abdf63403U, 0xbdc308ef3d0b01deU,
  0xbe6f17ac3e9e4d3fU, 0x3e8e97073ea3f89bU, 0xbe8866ddbefffde6U, 0x3eaa0ef2be1b56a4U,
  0xbf46d380bd9adcf9U, 0xbe192e51be48a42bU, 0xbea13d76bf8c2043U, 0xbed7dff23f1d37c7U,
  0xbe4282723d279861U, 0x3f24e48abf7d641bU, 0x3f3cbedb3f2bb04dU, 0x3d12062e3d9733f0U,
  0x3f0050e2bf482210U, 0xc03b7f483f32f55aU, 0xbfb765aebe96ffacU, 0x3fbfa7f13fab9ac1U,
  0x3f8ff600bf0f3e94U, 0xbf53cea9bf0ecc58U, 0x3f5143743f155185U, 0x3f990cb73f8b9bf1U,
  0xbee653c5bbcbefcbU, 0xbc558edebed3854aU, 0xbfa21d79bf141771U, 0x3db0e04e3ed8f5abU,
  0x3e5d04f4bf971da5U, 0x3f140b843f2a6955U, 0x3e1fc0eabecf9e60U, 0x3f4d2fe93f826e1eU,
  0x3e6cb41d3eb9bd48U, 0xbd974aad3e24ef3aU, 0xbe8386c2bf4ec932U, 0x3ed140883f0102d6U,
  0x3f10e701bf30d192U, 0xbc3e3dbcbe8c548bU, 0xbc531b783e800754U, 0x3f24d2c53eafadb3U,
  0xbef3db80be9e5c13U, 0x3ef64bc6bf9983adU, 0xbf300379bf15faa5U, 0xbf578a9bbf82442bU,
  0xbf1e6898be75060cU, 0x3e321a21bf01bce7U, 0x3e2243483e3365e1U, 0xbe71f927bf38bf6fU,
  0x3df8dd613e9e6b92U, 0x3e59f0953ea1368aU, 0x3f1b5631be0b1ae8U, 0xbe8429e33f4e3b8cU,
  0xbe91dc9c3f3901faU, 0x3e6f79babea4412bU, 0xbf828dc6bf24f79bU, 0xbfafb7c23ac9f6cfU,
  0xbe3051c43d0306b0U, 0x3e5b346abf0c2467U, 0x3df71bf53f6512faU, 0xbe4b006b3f3dbcb0U,
  0xbede2cc73f2d68f7U, 0xbef434b33e813eddU, 0xbf7edaf0bece1bc4U, 0xbdee4d9cbe97388bU,
  0xbf349c9c3f062fd9U, 0xbe487d433e8fac1cU, 0x3ecd634d3f59afe2U, 0xbf0a3db93ec0d8beU,
  0x3fc3d28abe94ede0U, 0x3d1a2fd3bfd53e8fU, 0x3f006b1c3f85ac1eU, 0x3f186dac3ee160f4U,
  0xbf20c6bf3aa64a2bU, 0x3d99e3413efc405bU, 0x3e895b28bf384c7fU, 0xbf6257713f468d4eU,
  0xbe31c265c0821931U, 0xc095a966c08a1073U, 0x40873d80c02f0688U, 0xc04981b8409798acU,
  0x40ae1e07c016794dU, 0xbf8c887f3f2824beU, 0xbfcc34cabf82eb1eU, 0xc01898f23f81383aU,
  0x3f04367e4090de87U,
};


ai_handle g_expert_b_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_expert_b_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

