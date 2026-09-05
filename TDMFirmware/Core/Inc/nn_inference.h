#ifndef NN_INFERENCE_H
#define NN_INFERENCE_H

typedef struct {
    float eps_pct;
    float d_mm;
    int   d_valid;
    float stage1_us;   /* Stage1 추론 시간 (µs) — DWT 실측 */
    float stage2_us;   /* Stage2 추론 시간 (µs) — DWT 실측 */
} NNOut;

void  nn_inference_init(void);
NNOut nn_inference_run(float dL_pct, float dR_pct);

#endif /* NN_INFERENCE_H */
