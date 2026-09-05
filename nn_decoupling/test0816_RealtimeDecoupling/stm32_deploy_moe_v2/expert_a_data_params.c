/**
  ******************************************************************************
  * @file    expert_a_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-08-17T01:44:41+0900
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
  0x3d9161c6be151e20U, 0x3f7d7da2bfe11962U, 0xbe8e3cb4bc082901U, 0x3e2e236fbbe7de89U,
  0xbf825c713f9b96c5U, 0x3fb5b4b6bfcaa1f8U, 0xba4f7871be5ec579U, 0xbfa62f473f79f023U,
  0xbe67112dbf2c756eU, 0x3f41acaf4037a030U, 0xbefa85c83f83fb03U, 0xbdda426abe9dfc38U,
  0xbfeb6e953f0cf79bU, 0x3f65948cbfedebf6U, 0x3fb2ac973fa7ceafU, 0xbfc5933dbf7b565cU,
  0xbe3b55573f56703eU, 0xbe6072eebe41f8c8U, 0xbda441b2bd8b62d7U, 0xbe5cff2bbe8cb398U,
  0xbf09bff73fa3a81fU, 0xbed0af4e3e0f2ae6U, 0x3f7394803dfa397aU, 0xbf0adafdbf3a45caU,
  0xbc88753b3f9bf386U, 0xbccfcb4dbfd217cfU, 0x3f76e5593fab98c9U, 0xbf147275bfd2d354U,
  0x3f74f213bfb934feU, 0xbdcc8d433e8da8e6U, 0x3f4cb1a33da82946U, 0xbfdff357bef22aedU,
  0xbd461e4bbc95cd9dU, 0x3fd6a6213d7f17b4U, 0xbf588b6f3e8956b9U, 0x3ef905dfbe662632U,
  0xbf4608053f78c9a6U, 0xbeda94ca3f3a7fbaU, 0xbfcf0f3f3eca1f96U, 0x3f6a95c2bee75f46U,
  0xbe77ae923f6d0422U, 0xbf51d8714006ad82U, 0xbddec9ba3f9dc97cU, 0x3e121401bf99fbf6U,
  0xbf0863e43ea5b2c6U, 0xbea7e8f53e90756aU, 0xbe9559643f6055e7U, 0x3d546b61bedbd91bU,
  0xbf711d753f6e2e78U, 0xbf9dcfbf3e073fdaU, 0xbf18e88e3f861edaU, 0xbe8fb13dbdfd66cbU,
  0xbe910f3abe74d640U, 0x3e9c5745bec60a8eU, 0x3da36c0bbdbdeda9U, 0x3ff30e353ecce404U,
  0xbec84bf53fab4cb2U, 0xbf185ef4bf54c3faU, 0x3cdf36de3e83d105U, 0x3e8a760b3f735185U,
  0x3dc8fc07bf86e651U, 0x3ec15e8fc03045f6U, 0xbecc77bb3f59fa75U, 0xc04094c2bef137a9U,
  0xbdc5fe9fbf0eded8U, 0xbf936323bf994d76U, 0xc072297bc0019fffU, 0xbf405b6340431763U,
  0xbeccb82abf238815U, 0xbe56f9ba3f78ec71U, 0xc0d3982ebf427692U, 0xbf126ffd3e37bd1fU,
  0xbee459373f77736dU, 0xc0448dc34003dd23U, 0xbb51e0bc3f8b9713U, 0xbf04712cbdd4f068U,
  0xbd1544303e6ba771U, 0xbfbafa213f314935U, 0x3f739db5be38d401U, 0x3ef749e4bfae901eU,
  0x3f0888953ff4895bU, 0x3fbaaa89bf977d56U, 0x404140e8be9d0108U, 0x3f699e913f6a60eaU,
  0xbf5e54843f800a03U, 0xbe9a315cbedc80afU, 0xbeab56603f018d11U, 0x3f47ee5ebe9c1ef8U,
  0xbeaa8839beb63afaU, 0xbe6ebb253df374eaU, 0xbf9596cebf924eb4U, 0x3e787d09bd890183U,
  0xbf4fe966beeedcb8U, 0xbf61bea2bed95450U, 0xbf3c855d3dff9a85U, 0x3f497d0f3fc70e12U,
  0xbe5d323d3f85fbc9U, 0xbf7d94a4405359f2U, 0xbf3748173e03e876U, 0xbf3c5af13e12e351U,
  0x3e0efc8cbe66d466U, 0xbe1b6fbfc0122e37U, 0x3f0882133f3cb9d6U, 0x3d5bdde83f7d40a1U,
  0x3eaa02413ed0dd2cU, 0xbf018696bffd8c4dU, 0x3ff2bb6cbfa1b59bU, 0x3e66ac093ec3e330U,
  0xbe8ed4223f73a55eU, 0xbfd737dc3f900b94U, 0xbedc760d3f9f43d6U, 0xbf17858a3eb406ffU,
  0xbef3fcbbbdff7ce0U, 0x3e23bb903f09cf5eU, 0xbe907d04beb027cbU, 0x3f46bc53bf0ed496U,
  0xbe875f973fab546bU, 0xbf2b6e1e3e9a8ef3U, 0xbf1eb4c13f141d01U, 0x3f62f8673f154959U,
  0xbefbbc6e3f6df888U, 0xbeec3b73bf5a26cbU, 0xc001bf003de5acc2U, 0x3ffa4d1d3f2ad00fU,
  0xbb40a71fbf7febeaU, 0x3f4c0f57c034d599U, 0xbef7998ebe543b96U, 0x3f02ae5540a46299U,
  0xbf1b81773f156254U, 0xbf4298ecc007fa9bU, 0xbfe25e9cbea04067U, 0xbf0cf8203ef40844U,
  0x3db9bdbe3ee82026U, 0x3f416f1d3f839360U, 0x3f6f7f04bed65353U, 0xc017aef0bf6c28d1U,
  0xbe37558d3f89d4f8U, 0xbf0759b93e8d2807U, 0x3e54f5143f1d508bU, 0xbf11b1cabedbc04fU,
  0xbf063ac5beb29125U, 0xbedc80863f04815eU, 0x40229f0cbe508307U, 0x395a14513cae8333U,
  0xbd788f993f3257eaU, 0xbf948b013e93a435U, 0x3f23920e3ee0daecU, 0xbf1254533e9aa7bcU,
  0x3eb5bd7ebe90ed06U, 0xbed06d9b3e975928U, 0xbf0c45543e9a14daU, 0x3f8949d6bfd98ee2U,
  0x3e2fd58e3f156b14U, 0x3f579a5a3d8c0a36U, 0x3fd4c6fabdfe9e70U, 0x3f1436cd3f054073U,
  0x3e8555813f9138f7U, 0xbe79b11abe641074U, 0xbfa4b8df3f6e2111U, 0x40857e7cbf2b6aa1U,
  0x3e805b26bf8d39e6U, 0x40258b8cc02bd805U, 0x3ff560c33ed04355U, 0x401227e94086688bU,
  0xbd850fa93fc9b98bU, 0xbeb9399dc0385521U, 0x3f97f64bbe7d810eU, 0xbeb3e001bf295101U,
  0x3e1b263b3e76f76cU, 0x3d840d3e3fd8225aU, 0x3dc10c993f9f0b1eU, 0xbf33009c3fa38630U,
  0x3eaa7afcbe1ab28bU, 0xbf398a16be89a7e7U, 0xbef21a46bf845eafU, 0x3f5c8cd2be96e549U,
  0x3f7b01583f702e5eU, 0x3fa60e94bebba745U, 0x3ef066863e6913e3U, 0x3e200a9cbda841b8U,
  0xbf626cddbc8d6634U, 0xbf4771263f38b23bU, 0x3ea61d7d3f980e43U, 0xbebbe0f43e9ede7eU,
  0x3e5a3230be49a8d2U, 0xbf62344bbecde020U, 0xbf2397cdbff16b2bU, 0x3eb47aa93dfd848aU,
  0xbf6749f8be2aa255U, 0x3e8a1dca3e4abbb7U, 0xbfa32c483eb51dcaU, 0xbf1dc5223e88e745U,
  0x3ebd17563fc47b8cU, 0x3ccaa322408c8688U, 0x3f31a707bf0098bcU, 0xc09a7dcabf17a4c0U,
  0x3e1457aa3c878e21U, 0xc01a1a45bf399550U, 0xc04814d63f6b3b5eU, 0xc0485dafbf8dd1f0U,
  0x3e95493abf65a943U, 0xbf4eab75bcd3d0a7U, 0x3ff433613d871f8dU, 0x3f5cd8bb3ed66ddbU,
  0xbd37b0fe3e8b544eU, 0xbe84ffb53e8b5e4dU, 0xbe3deda2bd8fcad4U, 0x3e84da43bdc52094U,
  0x3f4ab0a1be6bd8e4U, 0xbefdb49c3f026d36U, 0x3e036d90bdf41636U, 0x3f24a783bbf1945fU,
  0xbe8ce9cdbee3feecU, 0xbe4deda23dd8ed42U, 0xbe701c91bdd95437U, 0x3de4638b3e31573cU,
  0x3fc93cfe3e2ac10aU, 0xbfa5e7ed4036bd0cU, 0x3e9d8aefbea1bf5dU, 0xc079b34dbf14708eU,
  0x3f51d7afbe10a9a6U, 0xc013a5a93e5da447U, 0xc0044aa83e2e2845U, 0xbee3f38bbfa96810U,
  0x4082be4dbf8e2e9eU, 0x40ac8d2abdcae0b6U, 0x3f4ab08ac00d4994U, 0xbed98c3bbd8b8c13U,
  0xbf105603bed0fbd5U, 0x3cf5d061bf690a05U, 0xbe6c01fc3ea3144fU, 0xbf0be607beec8affU,
  0xbcfdbabcbde4f2b5U, 0x3f445e473f039c81U, 0xbeff12b1bda04112U, 0xbf02fc35bf4a4b1aU,
  0xbec1706cbf13fbf0U, 0x3f891b2a3e9d1bc5U, 0x3e9991d0be656421U, 0x3ed803b13ec52056U,
  0x3e8baba53f81eb47U, 0xbfb9d3223fa9402cU, 0x3f2382f7bf8f8c78U, 0xbf5240b3bed7d1d2U,
  0x3e8ab20c3ef74c4aU, 0xbf6d89473ef12695U, 0x3ee656673fabde74U, 0xbe8ccd24bfb47300U,
  0x3e988b4d40194762U, 0xbdc9fb92bed74956U, 0x408eaef73bb6d81eU, 0x3f63e53c3e4c7fd5U,
  0x3f581f4cbe815517U, 0xbdf2d2473f5b3bcdU, 0x3ea655d63edb0b21U, 0x3f2e299abf1df95bU,
  0xbdd5db503eb4889eU, 0xbea8fd923f0b3964U, 0xbf3cd042be543af1U, 0x3e8948f23f164870U,
  0xc0538259bf535e35U, 0x3fc8b323bd5dfc33U, 0x3e8b26f2bf810c4aU, 0x3e7592a93f320dcfU,
  0x3fb3c0f8becfcbefU, 0x3f8145b83f3416c7U, 0x3f7605593ea49d6cU, 0x3f892a693bb71586U,
  0xbff99514c06a54bfU, 0xbfecfe1f3fd4d750U, 0xc037e66b3f345af2U, 0x3fdb34823eb1fcdeU,
  0x3fbf2ff7bf99bd38U, 0x3f3b4d663eca9998U, 0xbd0223ef3f81fb6cU, 0x3ec5b2923f58be1aU,
  0xc019e415bf0eed3fU, 0xbec8cd913f69ef6bU, 0xbf09388d3f1864a3U, 0x3fc247aa3ea68c06U,
  0x3dc33997bedd560dU, 0x3ea26e823e0de110U, 0x3f4e6d4f3edb61d9U, 0x3facf2b83f32dd5fU,
  0x3df50998bef4b85aU, 0xbeb7e3d6bd4488b4U, 0x3f8c21c7be807a2fU, 0x3eacbffbbf9e4c94U,
  0x4018279ebf97c055U, 0xbec9afe2bee8e81aU, 0x3ed1fbaac006bb51U, 0x3f2061003f1c9c7cU,
  0xbf227cd03f71248cU, 0xbef9199bbfaaf606U, 0xbf097f6cbfd73650U, 0x3d6e746dbf5ea185U,
  0x3eccf967bf60eba8U, 0x3fcd97d2bdb4f6f3U, 0x3e129ae43fc16f40U, 0x3f92000cbf2b0281U,
  0xbdde534e3f33516dU, 0x3eb38b69bef191eaU, 0x3e2383e93e1e788bU, 0xbf0d74ad3f20b454U,
  0xbe53b4d13f81f664U, 0xbea2c22a3f05e757U, 0xbe6fe5dc3fe1de9cU, 0xbda5e0f2bf32e74cU,
  0x3f2e6dcf3e50770cU, 0x3e310899bd571dd0U, 0xbd15cfc03f40ca40U, 0xbf96ce7b3f80f869U,
  0xbf04cbf03df11070U, 0xbf9edc5b3ddc6782U, 0xbc045901bfebefc3U, 0xbe705a39bdf403f1U,
  0xbf6e4ac13e54bc9cU, 0x3e88a2a33ee9721dU, 0x3f866cfcbf907896U, 0xbe90839dbf1d361bU,
  0x3f0025e03e5080ebU, 0x3e57fa82bed13b6bU, 0x3d8b2ffb3fd7e6a1U, 0xbf0d135f3f36565dU,
  0xbc84c1233d6bbdaeU, 0xbf07d9753ee0f1f3U, 0xbfe99d8ebfa4212dU, 0xbf2f6a1b3f1d3bf1U,
  0x3e50de533ec70ee6U, 0xc05632a6bf23d056U, 0xc0ad4a06c0be30fcU, 0xc0a438b14100eaedU,
  0x405e5ec3c0cf855aU, 0x3ed8f54f40ee10d4U, 0xc0753bf2c05ad618U, 0x400702a33d958d1fU,
  0x4023618640b09779U,
};


ai_handle g_expert_a_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_expert_a_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

