#ifndef MOE_INFERENCE_H
#define MOE_INFERENCE_H

typedef enum {
    MOE_MODE_PROXIMITY = 0,   /* 비접촉 — strain + 근접거리(mm) */
    MOE_MODE_PRESSURE  = 1,   /* 접촉   — strain + 힘(N) */
} MoeMode;

typedef struct {
    float   strain_pct;    /* 두 모드 공통 출력 */
    float   value;         /* mode==PROXIMITY -> distance_mm, mode==PRESSURE -> force_N */
    MoeMode mode;
    float   gate_proba;    /* 게이트가 예측한 접촉 확률(0~1), 참고/디버깅용 */
    float   gate_us;       /* 게이트 추론 시간(µs), DWT 실측 */
    float   expert_us;     /* 전문가(A 또는 B) 추론 시간(µs), DWT 실측 */
} MoeOut;

void   moe_inference_init(void);

/* dt=1ms(TDM_PERIOD_TIME_US) 주기로 매 사이클 한 번씩 호출한다고 가정.
 * EMA 이력 상태와 "직전 접촉 여부"를 내부 static 변수로 들고 다닌다 —
 * 접촉 여부가 바뀌면 다음 호출에서 EMA를 원본값으로 리셋한다(최대 1 사이클,
 * 즉 1ms 지연 — EMA 시간상수 0.7초 대비 무시할 만한 수준). */
MoeOut moe_inference_run(float dL_pct, float dR_pct);

#endif /* MOE_INFERENCE_H */
