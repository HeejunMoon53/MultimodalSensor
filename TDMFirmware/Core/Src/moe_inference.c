#include "moe_inference.h"
#include "main.h"          /* DWT->CYCCNT */
#include "moe_params.h"
#include "gate.h"
#include "gate_data_params.h"
#include "expert_a.h"
#include "expert_a_data_params.h"
#include "expert_b.h"
#include "expert_b_data_params.h"

/* stedgeai generated float32 models — 후보 2(게이트+EMA MLP)
 *   게이트    : 2->8->4->1   (tanh,tanh,sigmoid), 65 파라미터 — EMA 없음(원본만)
 *   전문가 A  : 4->24->16->8->2 (근접: strain,distance), 674 파라미터
 *   전문가 B  : 4->24->16->8->2 (압력: strain,force),    674 파라미터
 *
 * [실기 테스트 후 수정] 게이트를 EMA 없는 2-input으로 바꿨다 — 예전엔 게이트도
 * EMA를 봐서, 뗀 뒤에도 stale EMA 때문에 계속 "접촉"으로 판단하고, 그 판단이
 * 안 바뀌니 EMA 리셋도 안 걸리는 자기강화 루프가 있었다. 게이트가 원본 신호만
 * 즉시 보게 되면서, 아래 로직도 "게이트 먼저 실행 → 그 결과로 이번 사이클에
 * 바로 EMA 리셋 여부 결정 → 전문가 실행" 순서로 바뀌었다 — 예전의 "다음 호출에서
 * 리셋" 1사이클 지연도 함께 없어졌다.
 */

static ai_handle gate_net = AI_HANDLE_NULL;
static ai_handle ea_net   = AI_HANDLE_NULL;
static ai_handle eb_net   = AI_HANDLE_NULL;

static AI_ALIGNED(4) ai_u8 gate_act[AI_GATE_DATA_ACTIVATIONS_SIZE];
static AI_ALIGNED(4) ai_u8 ea_act[AI_EXPERT_A_DATA_ACTIVATIONS_SIZE];
static AI_ALIGNED(4) ai_u8 eb_act[AI_EXPERT_B_DATA_ACTIVATIONS_SIZE];

/* ── EMA(이력) + 모드 전환 상태 — 사이클 간 유지 ──────────────────────────── */
static float   s_dL_ema = 0.0f;
static float   s_dR_ema = 0.0f;
static int     s_prev_contact = -1;   /* -1 = 아직 없음(첫 호출) */

void moe_inference_init(void)
{
    const ai_handle gate_act_ptrs[] = {(ai_handle)gate_act};
    ai_gate_create_and_init(&gate_net, gate_act_ptrs, NULL);

    const ai_handle ea_act_ptrs[] = {(ai_handle)ea_act};
    ai_expert_a_create_and_init(&ea_net, ea_act_ptrs, NULL);

    const ai_handle eb_act_ptrs[] = {(ai_handle)eb_act};
    ai_expert_b_create_and_init(&eb_net, eb_act_ptrs, NULL);

    s_dL_ema = 0.0f;
    s_dR_ema = 0.0f;
    s_prev_contact = -1;
}

static inline float clampf(float v, float lo, float hi)
{
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

MoeOut moe_inference_run(float dL_pct, float dR_pct)
{
    /* ── 1) 게이트: 접촉 여부 판단 (원본 dL/dR만 사용, EMA 없음 — 즉각 반응) ── */
    ai_float gate_in[2];
    gate_in[0] = (dL_pct - GATE_MEAN_0) / GATE_SCALE_0;
    gate_in[1] = (dR_pct - GATE_MEAN_1) / GATE_SCALE_1;

    ai_i32   gate_label = 0;
    ai_float gate_proba[2] = {0.0f, 0.0f};

    ai_buffer *gate_in_buf  = ai_gate_inputs_get(gate_net, NULL);
    ai_buffer *gate_out_buf = ai_gate_outputs_get(gate_net, NULL);
    gate_in_buf[0].data  = (ai_handle)gate_in;
    gate_out_buf[0].data = (ai_handle)&gate_label;
    gate_out_buf[1].data = (ai_handle)gate_proba;

    uint32_t t_gate = DWT->CYCCNT;
    ai_gate_run(gate_net, gate_in_buf, gate_out_buf);
    uint32_t cyc_gate = DWT->CYCCNT - t_gate;

    float contact_proba = gate_proba[1];   /* P(class=1=contact) */
    int   contact = (contact_proba >= GATE_CONTACT_THRESHOLD) ? 1 : 0;

    /* ── 2) EMA 갱신 — 게이트 판단이 이번에 바뀌었으면 "이번 사이클부터" 즉시
     *    원본값으로 리셋(지연 없음). 안 바뀌었으면 평소처럼 블렌드. ── */
    int mode_changed = (s_prev_contact >= 0 && contact != s_prev_contact);
    if (mode_changed || s_prev_contact < 0) {
        s_dL_ema = dL_pct;
        s_dR_ema = dR_pct;
    } else {
        s_dL_ema += EMA_ALPHA * (dL_pct - s_dL_ema);
        s_dR_ema += EMA_ALPHA * (dR_pct - s_dR_ema);
    }
    s_prev_contact = contact;

    /* ── 3) 라우팅된 전문가 실행 (근접: A / 압력: B) ── */
    MoeOut out;
    out.mode        = contact ? MOE_MODE_PRESSURE : MOE_MODE_PROXIMITY;
    out.gate_proba  = contact_proba;
    out.gate_us     = (float)cyc_gate / 170.0f;   /* STM32G4 @170MHz */

    if (!contact) {
        ai_float in4[4];
        in4[0] = (dL_pct   - EA_MEAN_0) / EA_SCALE_0;
        in4[1] = (dR_pct   - EA_MEAN_1) / EA_SCALE_1;
        in4[2] = (s_dL_ema - EA_MEAN_2) / EA_SCALE_2;
        in4[3] = (s_dR_ema - EA_MEAN_3) / EA_SCALE_3;
        ai_float out2[2] = {0.0f, 0.0f};

        ai_buffer *in_buf  = ai_expert_a_inputs_get(ea_net, NULL);
        ai_buffer *out_buf = ai_expert_a_outputs_get(ea_net, NULL);
        in_buf[0].data  = (ai_handle)in4;
        out_buf[0].data = (ai_handle)out2;

        uint32_t t_e = DWT->CYCCNT;
        ai_expert_a_run(ea_net, in_buf, out_buf);
        uint32_t cyc_e = DWT->CYCCNT - t_e;

        out.strain_pct = clampf(out2[0], STRAIN_MIN_PCT, STRAIN_MAX_PCT);
        out.value      = clampf(out2[1], DIST_MIN_MM, DIST_MAX_MM);
        out.expert_us  = (float)cyc_e / 170.0f;
    } else {
        ai_float in4[4];
        in4[0] = (dL_pct   - EB_MEAN_0) / EB_SCALE_0;
        in4[1] = (dR_pct   - EB_MEAN_1) / EB_SCALE_1;
        in4[2] = (s_dL_ema - EB_MEAN_2) / EB_SCALE_2;
        in4[3] = (s_dR_ema - EB_MEAN_3) / EB_SCALE_3;
        ai_float out2[2] = {0.0f, 0.0f};

        ai_buffer *in_buf  = ai_expert_b_inputs_get(eb_net, NULL);
        ai_buffer *out_buf = ai_expert_b_outputs_get(eb_net, NULL);
        in_buf[0].data  = (ai_handle)in4;
        out_buf[0].data = (ai_handle)out2;

        uint32_t t_e = DWT->CYCCNT;
        ai_expert_b_run(eb_net, in_buf, out_buf);
        uint32_t cyc_e = DWT->CYCCNT - t_e;

        out.strain_pct = clampf(out2[0], STRAIN_MIN_PCT, STRAIN_MAX_PCT);
        out.value      = clampf(out2[1], FORCE_MIN_N, FORCE_MAX_N);
        out.expert_us  = (float)cyc_e / 170.0f;
    }

    return out;
}
