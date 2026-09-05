#include "nn_inference.h"
#include "main.h"          /* DWT->CYCCNT */
#include "decoupler_params.h"
#include "stage1.h"
#include "stage1_data_params.h"
#include "stage2.h"
#include "stage2_data_params.h"

/* stedgeai generated float32 models (medium-deep, 978 params, 3.9 KB ROM) */

static ai_handle s1_net = AI_HANDLE_NULL;
static ai_handle s2_net = AI_HANDLE_NULL;

static AI_ALIGNED(4) ai_u8 s1_act[AI_STAGE1_DATA_ACTIVATIONS_SIZE];
static AI_ALIGNED(4) ai_u8 s2_act[AI_STAGE2_DATA_ACTIVATIONS_SIZE];

void nn_inference_init(void)
{
    const ai_handle s1_act_ptrs[] = {(ai_handle)s1_act};
    ai_stage1_create_and_init(&s1_net, s1_act_ptrs, NULL);

    const ai_handle s2_act_ptrs[] = {(ai_handle)s2_act};
    ai_stage2_create_and_init(&s2_net, s2_act_ptrs, NULL);
}

NNOut nn_inference_run(float dL_pct, float dR_pct)
{
    /* ── Stage1: dR_pct → eps_pct ── */
    ai_float s1_in_data  = (dR_pct - SC_DR_MEAN) / SC_DR_STD;
    ai_float s1_out_data = 0.0f;

    ai_buffer *s1_in_buf  = ai_stage1_inputs_get(s1_net, NULL);
    ai_buffer *s1_out_buf = ai_stage1_outputs_get(s1_net, NULL);
    s1_in_buf->data  = (ai_handle)&s1_in_data;
    s1_out_buf->data = (ai_handle)&s1_out_data;

    uint32_t t_s1 = DWT->CYCCNT;
    ai_stage1_run(s1_net, s1_in_buf, s1_out_buf);
    uint32_t cyc_s1 = DWT->CYCCNT - t_s1;

    float eps_pct = s1_out_data * SC_EPS_STD + SC_EPS_MEAN;
    if (eps_pct < EPS_MIN_PCT) eps_pct = EPS_MIN_PCT;
    if (eps_pct > EPS_MAX_PCT) eps_pct = EPS_MAX_PCT;

    /* ── Stage2: [dL_pct, eps_pct] → d_mm ── */
    ai_float s2_in_data[2];
    s2_in_data[0] = (dL_pct  - SC_DL_MEAN)  / SC_DL_STD;
    s2_in_data[1] = (eps_pct - SC_EPS_MEAN) / SC_EPS_STD;
    ai_float s2_out_data = 0.0f;

    ai_buffer *s2_in_buf  = ai_stage2_inputs_get(s2_net, NULL);
    ai_buffer *s2_out_buf = ai_stage2_outputs_get(s2_net, NULL);
    s2_in_buf->data  = (ai_handle)s2_in_data;
    s2_out_buf->data = (ai_handle)&s2_out_data;

    uint32_t t_s2 = DWT->CYCCNT;
    ai_stage2_run(s2_net, s2_in_buf, s2_out_buf);
    uint32_t cyc_s2 = DWT->CYCCNT - t_s2;

    float d_mm = s2_out_data * SC_D_STD + SC_D_MEAN;
    if (d_mm < D_MIN_MM) d_mm = D_MIN_MM;
    if (d_mm > D_MAX_MM) d_mm = D_MAX_MM;

    NNOut out;
    out.eps_pct  = eps_pct;
    out.d_mm     = d_mm;
    out.d_valid  = (d_mm <= PROX_VALID_MM) ? 1 : 0;
    out.stage1_us = (float)cyc_s1 / 170.0f;
    out.stage2_us = (float)cyc_s2 / 170.0f;
    return out;
}
