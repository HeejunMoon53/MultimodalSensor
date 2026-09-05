/**
  ******************************************************************************
  * @file    expert_b_data_params.c
  * @author  AST Embedded Analytics Research Platform
  * @date    2026-08-14T22:25:14+0900
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
  0xbe73452d3e13d972U, 0x3f1b5f49be619f63U, 0x3ce71d2e3d6bc14cU, 0x3e07ab22be5cb9d0U,
  0xbed78d643eb6633cU, 0x3eb1c1f83e4988d1U, 0x3eb187783cb9f493U, 0xbeec2ebcbdef7199U,
  0xbe3ab704bd23ba67U, 0xbec52be03ef55d73U, 0xbdef56d03e8af87bU, 0xbee208c8bd36401cU,
  0xbedab40d3cf590eaU, 0x3c020502bcf84736U, 0x3f05c1113edbf352U, 0xbea69ea8be521d7cU,
  0xbd48dbd73eedf8f4U, 0xbe136ca83d2b6db9U, 0xbd0b2565be055e38U, 0xbd1b2c56be668bd3U,
  0xbed159fc3f32a0feU, 0xbefb046e3e841745U, 0x3f8e3b783d16d7edU, 0x3efdc303bda2a314U,
  0x3e2e78ad3da79778U, 0x3d93e9a4bf022bf8U, 0x3eee15303edfba97U, 0xbdf094bbbe70c472U,
  0x3f951df5bf33a15dU, 0xbcb34b53bcbe497eU, 0x3f1c4ed03ca86203U, 0xbe4f9e1cbe4af543U,
  0x3e36bb4cbeda0e34U, 0x3e8998e9be7ac451U, 0xbf3950453eded60fU, 0x3da73c31bd4cd51fU,
  0xbea0cb213f37ac4dU, 0x3d72f8dd3f1e4206U, 0xbf1eb2e43e9f9778U, 0x3ec23a78beba2dc3U,
  0x3f4213c83e38cdb2U, 0xbe5633403e79e7e0U, 0xbd5f6b69be181a06U, 0x3eb188e3bf2b4858U,
  0xbe2d7b343d817931U, 0xbe11fda83ecd8d18U, 0xbefd891f3f241c4dU, 0xbeac12073da0f33aU,
  0xbf2b9e643eb99e97U, 0xbf34f19b3f1788ccU, 0xbe9673513f06bfdbU, 0x3f2055623ed9cb31U,
  0x3e06a8e0be63ba02U, 0xbf0062c33e2006ebU, 0x3f15b93fbda54a36U, 0x3ef009363e2cb31dU,
  0xbee845e83f0681c4U, 0xbe2a29e23e4be8baU, 0x3f8bbdd4befd95eaU, 0x3eeb1a873f53045aU,
  0xbd9006223e8192adU, 0x3e2ea787be57cfccU, 0xbdb0c7093f19e562U, 0x3d86e256bda64eccU,
  0x3e863f43beec30c4U, 0xbed85f2cbf018c40U, 0xbe0ca8aebe75ba8aU, 0xbe4b36be3f1c2d41U,
  0xbea87be33ecd3932U, 0x3d321e59be4bb8eaU, 0x3f5f68a4be3fd355U, 0x3da266593e50d8beU,
  0x3f0527f9bf2e727fU, 0x3e76b1c0bf0af07cU, 0x3ef561a2beb88aa3U, 0xbebf44c7bf797ce5U,
  0xbeae2d723f64dc75U, 0x3f6b38633df7f053U, 0xbe3474fdbebe6cefU, 0x3e15f4e93d634fefU,
  0x3f094ce6bf4086cbU, 0xbe32216cbee48d55U, 0xbf9abc633f111f2bU, 0xbf5de9bdbe8d42f9U,
  0x3e99e6ba3e165ddcU, 0x3e025a3ebef82da8U, 0xbe1c232dbead1e92U, 0xbeced481bcccbb27U,
  0xbdb19b10bea50815U, 0x3f264e50bcf8e6e1U, 0xbee5538b3f09a3c0U, 0x3dd48b723edeb539U,
  0xbf1d0c6b3cb4c5feU, 0x3ed282b4be98daf3U, 0x3e1623ad3ec8f849U, 0xbf0290973d62e9dfU,
  0xbbeb92c83f4253d9U, 0xbee911793f196793U, 0xbecf4ccd3ec2ea62U, 0xbea6ab473ecbf7ddU,
  0xbe420f323ea8e3f4U, 0xbd6bd0dcbe0a301eU, 0x3c832c3fbf833313U, 0xbef9a659bfa7aea7U,
  0x3f4672cabdf954b7U, 0x3d5150b9bd147318U, 0x3e71d15dbf31313dU, 0x3e2aee493ea912d5U,
  0x3d738b3b3e173ba2U, 0xbec771373ec1cef1U, 0xbef0df3d3e96e50cU, 0x3dc4fc4b3e328369U,
  0xbe538ec5bcd8345eU, 0x3f0bb684bddc2cc0U, 0xbde0999fbe11a751U, 0x3f0d55a03f1d8040U,
  0xbe944ae33f2b5237U, 0x3dd9fad1beb93483U, 0x3e8f7d7bbe7affa7U, 0x3f0079633ec6305bU,
  0xbdbd34cc3e778664U, 0xbeaf299ebd95895bU, 0xbebdad7f3cd86d5cU, 0x3e29e9fa3db5a139U,
  0xbe1289333e950c57U, 0x3e9ad84dbee78d59U, 0x3ebc0e973ea36671U, 0x3e11c5713f4e1731U,
  0xbea712f63d551959U, 0xbed22801bf0e2128U, 0xbd7eb441bd85183bU, 0xbd2190b63ebad858U,
  0xbe8c295dbe3ab162U, 0x3c76aae63dd3d38eU, 0xbe0ebc063d0d5150U, 0x3d6820f0bdadc481U,
  0x3f2e5d743dee004cU, 0x3e5ab6993f0643a8U, 0x3edc77913e8a5ed9U, 0x3ed6ff9e3f0ca7fcU,
  0xbf217c6a3f1df4baU, 0xbec3d4bbbe8da405U, 0x3ee6f58d3eb87d1fU, 0x3e71e5ea3f22fb8fU,
  0x3d7c4f15bf4b167bU, 0xbe1ebaa6bf31c018U, 0xbe66c466be7069e4U, 0x3ec5392b3de038c6U,
  0x3ea37eb0bf44742fU, 0x3eb941c4befac507U, 0x3e9d08bcbdd65973U, 0x3eb15f5a3f84dac3U,
  0xbf922c673ecfe96fU, 0xbf4c5419be30ab16U, 0x3f2007973f3c4c5eU, 0xbf4894d7be010430U,
  0x3e5a13ba3d74bde1U, 0xbdb7cabb3e07fc7aU, 0xbd97b493be201189U, 0x3e9044d5beda83eaU,
  0xbe5830143ba45721U, 0x3e837a1dbe330a68U, 0xbe368fe3bec54d29U, 0x3e08f1a7bd9d1be8U,
  0x3d77276a3e1bbb47U, 0xbe7e5d67beb91069U, 0xbe97956f3eb7d58cU, 0xbe304f7ebeabf15eU,
  0x3e8f0f5dbe878eb4U, 0x3ee3542bbd949112U, 0x3ee2f8e63e8de08cU, 0xbedf7ce23e6bbf14U,
  0x3e572f543e63036bU, 0xbec41bc23b2ff867U, 0xbe49fec3be8c5bc5U, 0xbd8d3282bed1b71aU,
  0x3f13e9d83e02c934U, 0x3ec0c3ebbebc1246U, 0xbec91ea73e3a79e1U, 0xbe850ec8be8f433eU,
  0xbf0ed2193f132348U, 0xbda349663ec72cf3U, 0x3e3895e73ebe98c5U, 0x3e3cc4753e428a8eU,
  0xbe706a383e3023aeU, 0xbd3d4d46bdcd0ca7U, 0x3e8d1a1cbeeceb5aU, 0x3ec5dde83e1ad3e7U,
  0xbf0f7a273f0f5695U, 0xbe06668fbe81b9caU, 0x3db755d2bd8525a6U, 0x3e81ed4b3cb4da90U,
  0x3f29d5bfbe821a44U, 0xbe1c7b8a3dacfbc5U, 0xbdc479d5beaec206U, 0xbf156714be0e3d6bU,
  0x3ed324b3bde86762U, 0xbf1062b7beb8e18eU, 0xbeebe65fbc8cb52aU, 0xbf25a55dbe899151U,
  0x3f21d11fbf1d9d5aU, 0x3deabe023d5cbd78U, 0xbf2d887f3e9f06bfU, 0xbe3e2e83bee0ea78U,
  0x3e6cce84befa4525U, 0xbe796ea63eec1a2fU, 0x3e16c979bda8ebb8U, 0x3d68ae9f3eb0f9dcU,
  0x3e86e13ebc9fb21fU, 0xbdfa1f9a3ec999f4U, 0xbe87e88dbe8f872eU, 0x3c0b0019bf3ab037U,
  0x3ef5bfa6bdd971a3U, 0x3e2ab8793f0ac26eU, 0x3e45396ebeb3fd79U, 0xbe5cda5fbea17bd6U,
  0x3f02c20bbba4e457U, 0x3e127d2e3e5c63d3U, 0xbe14a2d8beac11c2U, 0xbe1b510e3e41cfc1U,
  0x3e96ec67be6fef1dU, 0xbeb7cfacbe985585U, 0xbeac655b3e1c63afU, 0x3e2e5ae5bee82417U,
  0xbcb38eedbd31f7eaU, 0xbb9f8e2b3e66225cU, 0xbe8102a5be9138c0U, 0xbe4d3a2fbd83b831U,
  0xbe54c69dbee8696aU, 0x3e3f8be3bef9a21bU, 0xbe544a62bed40c6fU, 0xbe5f83023c70b42dU,
  0x3ec6f620bf3ab9feU, 0xbd97125b3e239cd0U, 0xbea2b3f83e5e7164U, 0xbe8baccf3d394893U,
  0xbe0d5843be9dd796U, 0x3eed7d2dbe69e632U, 0x3de88de83d9dd19eU, 0xbe3b48c3be041cafU,
  0x3cfcf0ea3ec15f33U, 0xbf1748813e84b437U, 0x3e8681d0be0f6ae3U, 0x3e1dc1763e1665fdU,
  0x3f023b4a3e225c55U, 0xbf8a8282bef0f7d4U, 0xbd05286a3dd46f27U, 0x3deba39e3f1ce61aU,
  0xbec209553e951775U, 0xbd7115b1becad24aU, 0x3fc42ba8be9dcf1cU, 0x3e29fec83f1b653dU,
  0x3ca431a5bd81a9b2U, 0xbee405b33e2ba4cfU, 0xbd2fea7f3ce440adU, 0x3d2bdf42bdb03343U,
  0x3cd72fe33e49502bU, 0xbe0f1da03e961d62U, 0xbe613985be969eeeU, 0x3f1289ec3dbae975U,
  0xbf4f99c93c667e58U, 0x3f95ca88be5ec7feU, 0x3e062037bf36212dU, 0xbe94a92f3b573917U,
  0x3ec513903eadef08U, 0x3f383a77bf53ebd4U, 0x3f2c8f903efe30eaU, 0x3eb4492dbef31b6fU,
  0x3e634f0dbf36b7c5U, 0xbf0e876e3edcb2a3U, 0xbf652b34bedebc4dU, 0x3f7cfe993f557ea8U,
  0x3eaae517be9c9a03U, 0xbeb7be45bd4d58c5U, 0x3ef9a2513eeec65bU, 0x3f7a8eb53ea595caU,
  0xbf6483073e813480U, 0xbe3bf0c53f3d4b4fU, 0xbda553fcbe413c46U, 0x3f1068083f405052U,
  0x3ed6e020bf8887d2U, 0x3e644156bd908159U, 0x3f28e09f3eececceU, 0x3fb2c80b3f9bb716U,
  0xbee918513f08cbb7U, 0x3adb71e63f29684fU, 0x3e2b69e5beda5218U, 0x3f194668be9b0798U,
  0x3f2e1d0ebf3eccf3U, 0xbe252cf7bf060b11U, 0x3e46ad833f1b3971U, 0x3edaaedb3f15d29eU,
  0xbe8a56c8bd7cdc83U, 0x3e393ed1bec4ad88U, 0xbe8d096ebf8405efU, 0xbe1cc4d7bf0f091cU,
  0x3e80679abf513fdaU, 0x3f8bca23bf0eaf6cU, 0x3e9155af3eb59765U, 0x3f214abbbd32730fU,
  0x3e90368dbf1ff091U, 0x3eb03e1fbef14c8aU, 0x3f3cb819ba872d8cU, 0xbee950cdbececdc1U,
  0xbecb34603f766e91U, 0xbee4cb793e255c64U, 0xbf0d90243c737e4dU, 0xbf860fb7bfb42b8bU,
  0xbd04752dbea2944eU, 0x3ec99413beaf4ce0U, 0x3e747e1c3f145e92U, 0xbe8977fc3f16c5a6U,
  0xbedf4ed03f0348f1U, 0xbf3d4fd23e9333b2U, 0xbf39a4cebe6a78b0U, 0xbd65612fbed8da83U,
  0xbf3160803f52ece3U, 0xbe62a7193f372eadU, 0x3ecbf9e3bbe24253U, 0x3deb6b2bbea78a89U,
  0x3f331ac13d779f2cU, 0x3e2f8ca6bf3f1516U, 0x3dfba6083f271289U, 0x3f01de3c3f5a7ef7U,
  0xbe88c2c53df65987U, 0xb9f65056be0ffec2U, 0xbe399246bf31ee18U, 0xbf2a0f093f1c0817U,
  0xc06b9218c03abbd5U, 0xc083b1a0c079bad8U, 0x4078b38ec06df168U, 0xc06b583e407a5d4cU,
  0x407aa4c3c08c8d0fU, 0xbf6cd03a3f58c550U, 0xbe9753dbbfd58d84U, 0xbf973d7d3fc5b272U,
  0x3f168a4f4063a236U,
};


ai_handle g_expert_b_weights_table[1 + 2] = {
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
  AI_HANDLE_PTR(s_expert_b_weights_array_u64),
  AI_HANDLE_PTR(AI_MAGIC_MARKER),
};

