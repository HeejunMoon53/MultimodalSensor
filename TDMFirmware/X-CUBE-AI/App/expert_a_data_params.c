/**
  ******************************************************************************
  * @file    expert_a_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-08-19T14:17:24+0900
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
  0xbdb39cc6bf7603fcU, 0x3f246c9ebe7110f4U, 0x3e900c7a3ee7ae8dU, 0xbeaf92393e7781cdU,
  0xbeb595d9bdc0bc64U, 0x3f4fa02c3db29c79U, 0x3e93bd023da8aa38U, 0xbf8699143e259a6dU,
  0x3e87d96fbe19d03cU, 0x3e4346ef3f19bf19U, 0x3e8999283ef4dd98U, 0xbf7ae3febeb1a0bbU,
  0xbc4194de3ddf31f0U, 0xbf8a68083d88ffe0U, 0x3f23c80f3f12fc3cU, 0x3dccea89beeda67bU,
  0x3e3617bb3f6af684U, 0xbdce04ba3e6c4688U, 0x3f0613dd3db54918U, 0xbefe5a0abe069d73U,
  0xbedbe4073f23c303U, 0xbd353c5b3d9ac7ccU, 0x3ea7298fbf7a92f9U, 0x3ec62334be92a37aU,
  0x3f2ba66c3eb50ff2U, 0xbae72b47bec19d8aU, 0x3f128cff3edad3b7U, 0xbeafc2dbbf885f41U,
  0x3f35dd15bf90029dU, 0xbdd142773e027b67U, 0x3f2490aabeb27dc8U, 0xbed62744bea890aaU,
  0x3e9fabe8bfbda090U, 0x3e5063573dede64eU, 0xbf1e653d3db9ecf3U, 0x3f033e983e37451bU,
  0xbed9d2ee3dcc6f3bU, 0xbf0978cd3eb13621U, 0xbeb597e03ea50ad7U, 0xbf18737bbef1daadU,
  0x3f18bec53f62e346U, 0xbe25630c3eab6f18U, 0x3d140f9d3f8d3c7fU, 0x3e8bd850bf230190U,
  0x3e051cee3db21590U, 0x3e3c22ae3e8b0cc7U, 0x3e3bacaf3fda15d1U, 0xbaf0b3733e1aca50U,
  0xbf1ea24c3f59bbccU, 0xbf4260603f06981cU, 0xbeef66803e893f4cU, 0x3f4fcfe53f9af4d4U,
  0x3d80286bbe5fe019U, 0x3f7be2163d08b4d0U, 0x3f25b76fbf13f950U, 0x3f3967ea3ea62f7cU,
  0xbecf0f3c3f45084aU, 0xbf9fd00b3ea8a714U, 0x3d8fc3403d85b3a3U, 0x3deee3a93f0ed2f2U,
  0x3e7f285e3f224307U, 0x3eb1e791bf12dc75U, 0x3c65e3973e60a600U, 0x3de3354e3eebf6fbU,
  0x3f40f088bf17a119U, 0x3f2fdd81be0bc09bU, 0xbeae6714be81096bU, 0xbe9a3d723f405185U,
  0xbe67a6693f89c46aU, 0x3e105b703e4b720bU, 0xbe474d44be529194U, 0xbd127eb43da037d5U,
  0xbce7c896bd44009aU, 0xbf1f6c5e3f11d3aeU, 0xbeb3a9de3f6ed3c0U, 0xbf027c21beaef93bU,
  0xbdf386213d57aa4bU, 0x3e708c203e163697U, 0xbdeb720abed729c7U, 0x3e917078be8406deU,
  0x3eae4a0e3e9c207eU, 0xbf2ff99dbda6c51dU, 0xbe21edb33f31fd2fU, 0x3d5518a33f4a655bU,
  0xbec87ca33ef59cdfU, 0xbd839241be1ea942U, 0x3d1c2b3e3ef5cc6cU, 0x3e89a0a4bd631156U,
  0xbe8130c8bc7e7eb3U, 0x3ebd17c83e380a19U, 0x3d1f8627be9187d5U, 0x3e04a74cbe006696U,
  0xbf0353e0bd5325fcU, 0x3f04e8523eb6f4f7U, 0x3f0d27913f01a559U, 0xbd9c468d3f6ef1e8U,
  0xbe80a31b405719a6U, 0xbf16e9353ee99cd9U, 0xbf20aae83e3f0ce6U, 0xbdbdb4db3f55986bU,
  0x3e1455a5bf234734U, 0x3fdd6531bf3f3f7eU, 0x3e6cc7f6be549f72U, 0x3f7a973d3f41ff00U,
  0x3e6e32163fedfa0cU, 0xbf171384be0f6243U, 0xbf0cd6b2bebe1394U, 0xbe90ba1e3e134431U,
  0x3bc17474bdb82a1eU, 0xbfad807f3f8247ccU, 0xbf1b469b3e238e9aU, 0x3f8a1dd73ebd2c0cU,
  0xbec5ff4b3ea62651U, 0x3f41e5693dc1d5b6U, 0x3da42d61be3c0bf7U, 0x3f1b6304be527323U,
  0xbecbe2353eaae031U, 0xbf1a7d0abea4ac66U, 0x3ea8ec7dbe80dad6U, 0x3f2b12403f14ac8fU,
  0xbcec1ca73fd0eb67U, 0xbf0bdaab3e58ee19U, 0xbf393b01bcb6d7d8U, 0xbe426bf23f752fe7U,
  0x3f32342abf89d278U, 0x3fcec114bf39348aU, 0x3f153fb23e96b971U, 0x3fa210b03fdbb69aU,
  0xbf7d9edc3fdd0c4fU, 0xbf1d04c7be337181U, 0xbfa7cfd5beacdc7bU, 0xbec356203eaffbc6U,
  0x3d81a98bc03b270aU, 0x3efc4e5abeb975e1U, 0x3f14bdcabeab7875U, 0xbe55c841be525833U,
  0x3f9bc7fe3f2f4316U, 0xbf93b60c3e9bb3e1U, 0x3faa801e3f0f5589U, 0x3f2b6a5bbe2dbb83U,
  0xbf3c7daabf97f192U, 0x3e613ecfbe9a0461U, 0x3f48d5ba3e3715f1U, 0x3d05561a3e8881abU,
  0x3f07b169c01e080bU, 0xbdbb91d4bef8da8fU, 0x3f115189be2ed11cU, 0x3eea3b403ee7c135U,
  0x3fadfba93df9aea0U, 0xbf414fafbbb8db0bU, 0x3fb6f2bc3ed98d7eU, 0x3f09e823be9d51b3U,
  0xbf663a5ebf20d8bdU, 0x3f82f1053d454709U, 0x3f0b0fe93eedd1a4U, 0xbe3d64903b5845b1U,
  0x3e520d993e6ea118U, 0xbee1bd1a3e917b0aU, 0xbeacae36be7f8808U, 0x3d46ab86bf428968U,
  0xbf1fa9743db4fc5fU, 0xbbc0dec53e389aaeU, 0xbedfbce13e983402U, 0xbcc23e50bec143a5U,
  0x3e4d3b94bc0a1221U, 0xbe6b0662bf1f4c7fU, 0x3de74e2d3eb6672bU, 0xbe4eae95beb73d13U,
  0x3e98e99cbe6a5d4cU, 0x3ed2d24cbdfbe754U, 0x3f00af123e0cce33U, 0xbe63d7123dc6467eU,
  0x3ea7213d3e1d9b89U, 0xbeaa0add3e07e9d3U, 0xbea0e603bdb1e95dU, 0xbd32d6fe3da17718U,
  0x3f00337b3e96b47bU, 0x3f7a5dc0bf405f01U, 0xbee683a33dd90693U, 0xbe9e0789bee9b26cU,
  0xbefaa335bc559fc4U, 0x3e33fabf3e6f4fb9U, 0x3e0576733eeab0feU, 0xbe1eb0f73e0effbfU,
  0x3ca5fa7d3e9a1c2eU, 0xbe88d341beb6660aU, 0x3f9604debebfe4d5U, 0x3f52f9343ca1ceebU,
  0xbf5d8949bda0f70bU, 0xbc6b442dbe87a593U, 0xbd8eceb33c1040f3U, 0xbe17e9e2bdb12a0aU,
  0x3f12c1fbbfabeb41U, 0xbef294693eba7d14U, 0xbee42a7ebe267c0eU, 0xbf1ebfca3eb57464U,
  0x3f696bbcbdc1353cU, 0xbfd9ffd53da6f1acU, 0xbe182bffbd1aa821U, 0xbf5e64d5bf075868U,
  0x3effb7abbfcaf4a4U, 0x3daf4b393e54963cU, 0xbeb766243e865bbdU, 0x3c9f412bbdde660eU,
  0x3e64eaa43e49f451U, 0xbf16a7483ef3eb34U, 0xbdd5d193be1f7964U, 0x3ee7e4513f9adde8U,
  0x3f802dd1bd7553a5U, 0x3ee9ced53f3e1d51U, 0x3f08da16bf8f748fU, 0x3ed57847be92e024U,
  0xbf076fb23e291d83U, 0xbf2cdafe3f85321dU, 0xbdeaea0fbd58a6d9U, 0x3e1b85463c62696bU,
  0x3f1adb66be527654U, 0x3f4cd5c3beb68834U, 0x3f11b848be5efb80U, 0xbf2d3e2a3e9f8bb3U,
  0x3f170152beb356a2U, 0xbf1ae0b1bd55bbc6U, 0xbeaa0d0ebda41a92U, 0x3dee9dd9bee86accU,
  0xbd7f3e3bbe5e66c7U, 0xbe1434353f1a59d2U, 0xbecb169fbf620c31U, 0xbe7951c33cd828e3U,
  0xbf43ac823f19849cU, 0xbe63b63cbe1e2aafU, 0xbe4b1117be87e796U, 0x3ef50e8ebe5f41cbU,
  0x3defde95be8b759fU, 0x3e8c91d83d62fd81U, 0x3ee8a9d0bec49471U, 0xbe8393eebf2e3bceU,
  0xbd8dcb30bf0576dcU, 0x3f99e32e3e159328U, 0x3e291a4b3f02a8bbU, 0x3e3f8afe3dd7260dU,
  0x3eaee43ebf15b4e5U, 0xbd3b41e0be84123eU, 0x3f3753c1be2f38e4U, 0x3cbb72cebf17b1a4U,
  0xbcd2fb9e3f562859U, 0xbf75d141bd3650c9U, 0xbeb626923e18ff1aU, 0xbf693e55be76d520U,
  0x3e7c4228bf8a9d57U, 0x3f192dacbea8e609U, 0x3fa5bae53e443b6cU, 0x3ef523573ea6db0fU,
  0x3edf6d92be803465U, 0xbecd99a53f312a22U, 0xbbe346d43e4654e1U, 0x3cbb405bbe97df9eU,
  0xbd0ab9f83e3a15c1U, 0x3d0608563e87406cU, 0xbe81afad3e03b1d0U, 0x3ea4faa93f1bf8cdU,
  0xbf038d7f3f54385bU, 0x3f36e8a8bf8ede98U, 0x3f01afbd3e455154U, 0xbf66d095bd0968e5U,
  0x3f1302f83da5e95fU, 0x3e69b274bf2ddb9eU, 0x3d6c26cc3d131c05U, 0x3bee9368bf3c288fU,
  0x3ed0151cbf4a55ecU, 0xbf82edda3f5e393aU, 0xbfea5546bf04e184U, 0x3fd9d0f03f6426faU,
  0xbeb4d392bf2efb2cU, 0xbf963a45be18ba0dU, 0x3ec4a7643eae209dU, 0x3facda1c3e9577d4U,
  0x3b769ca9bf4b4835U, 0xbecd468e3f91c2beU, 0xbf86ef75bf8765b8U, 0xbdec44ff3f8219aaU,
  0xbebf5a95bf2547faU, 0xbd3eca2a3ee57eedU, 0x3ed7c0b73def2388U, 0x3f2ba79d3fb9ea5dU,
  0xbf07c4f1bd4cd548U, 0x3f9e5de93e9e65a8U, 0xbdccb670bf341531U, 0x3f61b0debf41d32eU,
  0x3f341b3cbec70c9cU, 0xbeab6e63bf9a7495U, 0x3e3c9a8f3fda8217U, 0xbddac9da3eafbe12U,
  0x3e6c7450bf490c9cU, 0xbe0b669bbfd6bcd2U, 0xbe833a6d3d7f8383U, 0x3e8832f63f2802c0U,
  0xbe2b0b3dbf8666e9U, 0x3e9815ccbe4bee04U, 0x3deae86b3f0564ccU, 0x3ea43578bf0e8ce7U,
  0xbe53b701bdcf62c4U, 0x3e89644fbe64fed1U, 0x3f5e8dcbbfd02f12U, 0x3f1ff48dbf280a18U,
  0x3ed2fd79bd92ef6eU, 0x3efd9cedbf518964U, 0x3ed771623f81c5f1U, 0xbf78adffbe831d49U,
  0xbeaec241be1f4870U, 0xbf2448b93e14b156U, 0x3f05c22c3f511a29U, 0xbe6c0c4d3f49a507U,
  0xbe2409b83f6465acU, 0xbdbc5fe63ea0e7e0U, 0xbf97c678bf8286e4U, 0xbdf3bbe1bf0d78e4U,
  0xbf9318203f3efb2cU, 0xbec971eabf623645U, 0x3ef65146bf7d682aU, 0xbe6774c6bde3c927U,
  0x3f7e61cabd9dda46U, 0x3e9a1353bf6086cbU, 0x3f2593d73f344ad5U, 0xbc2a6aaebdf7df68U,
  0xbe3a70603d8dd648U, 0xbda219763ec1f8a1U, 0xbf54e6fdbeac50d6U, 0xbf55253d3e7f5ad9U,
  0xbfa7d205c026bf04U, 0xc0c3ca8bbe8b9ac4U, 0xc0a200c6c08845e5U, 0xc088ebc940bfebc7U,
  0x40a2eb88c09c980aU, 0x4001c5dc40a459d9U, 0xc0052e8bc068b501U, 0xc053eab3bd945ad2U,
  0x4024b477408138d1U,
};


ai_handle g_expert_a_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_expert_a_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

