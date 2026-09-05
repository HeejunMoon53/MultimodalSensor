# -*- coding: utf-8 -*-
"""Paper/content.py — 논문 본문(국문/영문 동시 정의)."""
from build_paper import bullets, eq, figure, heading, para, table


def build(doc, L):
    def t(ko, en):
        return ko if L == "ko" else en

    # ── 표제 ────────────────────────────────────────────────────────────────
    para(doc, L, t(
        "단일 전극 소프트 멀티모달 센서의 시분할 측정과 임베디드 AI 기반 실시간 신호 디커플링: "
        "인장·근접·접촉력의 동시 추정",
        "Time-Division Measurement and Embedded-AI Signal Decoupling for a Soft "
        "Single-Electrode Multimodal Sensor: Simultaneous Estimation of Strain, "
        "Proximity, and Contact Force"),
        size=16, bold=True, align="c", space_after=8)
    para(doc, L, t("문희준", "Heejun Moon"), size=11, align="c", space_after=2)
    para(doc, L, t(
        "고려대학교 기계공학과 BioRobotics & Control 연구실 (BiRC)",
        "BioRobotics and Control Laboratory (BiRC), Department of Mechanical "
        "Engineering, Korea University, Seoul, Republic of Korea"),
        size=9.5, align="c", space_after=14)

    # ── 초록 ────────────────────────────────────────────────────────────────
    heading(doc, L, t("초록", "Abstract"), 1)
    para(doc, L, t(
        "유연 멀티모달 센서는 서로 다른 물리 자극이 하나의 전기 신호에 겹쳐 들어오는 신호 결합(signal "
        "coupling) 문제 때문에 각 자극을 독립적으로 측정하기 어렵다. 본 연구는 EGaIn(갈륨–인듐 공융합금) "
        "액체금속으로 직접 잉크 라이팅(DIW) 인쇄한 평면 나선형 코일 하나를, 두 가닥의 단일 전극만으로 "
        "인덕턴스 L, DC 저항 R, 마찰전기(TENG) 전압 V의 세 신호원으로 동시에 사용하는 측정 구조를 제안한다. "
        "STM32G473CBT6 마이크로컨트롤러에서 TIM7 인터럽트로 구동되는 1 ms 주기 시분할 측정(TDM, Time-Division "
        "Measurement) 스케줄이 아날로그 멀티플렉서를 통해 동일 코일을 세 측정 경로에 순차 연결하며, I²C DMA와 "
        "ADC DMA를 병렬로 실행해 1 kHz 취득률을 유지한다. 도체(금속)·유전체(손) 두 표적에 대해 인장 0–30 %와 "
        "근접 0–52 mm의 2차원 파라미터 공간을 격자 형태로 측정한 결과, ΔR/R₀는 근접거리와 무관하게 인장에만 "
        "단조 의존하고 ΔL/L₀는 인장과 근접에 동시에 의존하는 비대칭 구조가 정량적으로 확인되었으며, 이 비대칭이 "
        "디커플링의 물리적 근거가 된다. 접촉 영역으로 모달리티를 확장하자 점탄성에 의한 히스테리시스·크립과 "
        "인장×접촉력 교차 민감도가 새로 나타났고, 표준선형고체(SLS) 모델로 시간상수 τ ≈ 1.0 s를 실측하여 이를 "
        "인과적 지수이동평균(EMA) 이력 피처로 모델에 반영하였다. 최종 디커플러는 접촉 여부를 판정하는 게이트와 "
        "비접촉·접촉 전용 두 전문가로 구성된 Mixture-of-Experts(MoE) 구조로, 총 1,413개 파라미터에 불과하며 "
        "X-CUBE-AI를 통해 MCU에 임베딩되었다. 보드 단독으로 매 TDM 주기마다 추론이 수행되며 실측 지연은 "
        "중앙값 260 µs(95 백분위수 263 µs)로 1 ms 주기 안에서 완결된다. 근접이 실제로 변하는 구간에서 실기 "
        "성능은 인장 R² = 0.981(RMSE 1.37 %p), 근접거리 R² = 0.940(RMSE 2.11 mm), 접촉력 RMSE 1.80 N이었고, "
        "게이트 정확도는 98–99 %였다. 반면 근접이 준정적인 구간에서는 근접 추정의 신호 대 잡음비가 무너져 "
        "R²가 음수로 떨어졌는데, 이는 오프라인 held-out 평가만으로는 드러나지 않는 실기 고유의 한계로서 본문에 "
        "그대로 보고한다. 본 연구는 PC 연결 없이 동작하는 단일 전극 멀티모달 센싱 시스템의 설계·제작·데이터 "
        "취득·모델링·임베디드 배포 전 과정을 하나의 파이프라인으로 제시한다.",

        "Flexible multimodal sensors suffer from signal coupling: several physical "
        "stimuli are superimposed on the same electrical readout, which makes "
        "independent measurement of each stimulus difficult. This work proposes a "
        "measurement architecture in which a single planar spiral coil, printed from "
        "eutectic gallium-indium (EGaIn) liquid metal by direct ink writing (DIW) and "
        "connected through only two wires, is used simultaneously as three signal "
        "sources: inductance L, DC resistance R, and triboelectric (TENG) voltage V. "
        "A 1 ms time-division measurement (TDM) schedule, driven by a TIM7 interrupt on "
        "an STM32G473CBT6 microcontroller, sequentially connects the same coil to the "
        "three measurement paths through an analog multiplexer while running I²C DMA and "
        "ADC DMA in parallel, sustaining a 1 kHz acquisition rate. Gridded measurements "
        "over a two-dimensional parameter space of 0–30 % strain and 0–52 mm proximity, "
        "for both a conductive (metal) and a dielectric (hand) target, quantitatively "
        "confirm an asymmetry: ΔR/R₀ depends monotonically on strain alone and is "
        "essentially independent of proximity, whereas ΔL/L₀ depends on both. This "
        "asymmetry is the physical basis for decoupling. Extending the modality set to "
        "contact introduced viscoelastic hysteresis and creep together with a strain-force "
        "cross-sensitivity; a standard linear solid (SLS) model was fitted to the measured "
        "dwell relaxation, giving a time constant of τ = 1.0 s that was encoded into the "
        "model as a causal exponential-moving-average (EMA) history feature. The final "
        "decoupler is a mixture-of-experts (MoE) network consisting of a contact-detection "
        "gate and two mode-specific experts, totalling only 1,413 parameters, and was "
        "embedded on the MCU through X-CUBE-AI. Inference runs on the board itself once "
        "per TDM cycle with a measured median latency of 260 µs (95th percentile 263 µs), "
        "completing well inside the 1 ms period. In segments where the proximity axis was "
        "actually moving, on-hardware accuracy reached R² = 0.981 (RMSE 1.37 %p) for "
        "strain, R² = 0.940 (RMSE 2.11 mm) for distance and 1.80 N RMSE for contact force, "
        "with gate accuracy of 98–99 %. In quasi-static proximity segments, by contrast, "
        "the signal-to-noise ratio of the distance estimate collapsed and R² became "
        "negative; this is a hardware-specific limitation invisible to offline held-out "
        "evaluation and is reported here as measured. The study presents the complete "
        "pipeline — design, fabrication, data acquisition, modelling and embedded "
        "deployment — of a single-electrode multimodal sensing system that operates "
        "without a host PC."),
        size=9.5, align="j")

    para(doc, L, t(
        "핵심어 — 소프트 센서, 액체금속(EGaIn), 단일 전극, 멀티모달 센싱, 신호 디커플링, 시분할 측정(TDM), "
        "Mixture-of-Experts, 물리 정보 신경망(PINN), 엣지 AI, STM32",
        "Index Terms - Soft sensor, liquid metal (EGaIn), single electrode, multimodal "
        "sensing, signal decoupling, time-division measurement, mixture of experts, "
        "physics-informed neural network, edge AI, STM32"),
        size=9, italic=True, space_before=6, space_after=12)

    # ── 1. 서론 ─────────────────────────────────────────────────────────────
    heading(doc, L, t("1. 서론", "1. Introduction"), 1)
    para(doc, L, t(
        "로봇과 인간이 같은 공간을 공유하는 응용이 늘어나면서, 접촉이 일어나기 전에 물체의 접근을 감지하고, "
        "접촉이 일어난 뒤에는 접촉력을 측정하며, 동시에 자신의 형상 변화까지 인지하는 센서가 요구되고 있다. "
        "강체 센서로 이 세 가지를 구현하려면 근접 센서·촉각 센서·변형 센서를 각각 배치해야 하고, 곡면이나 "
        "대변형이 필요한 표면에는 적용이 어렵다. 유연 센서는 이 제약을 해소하지만, 하나의 유연 소자에서 여러 "
        "물리량을 읽어내면 신호가 서로 겹치는 결합 문제가 필연적으로 발생한다.",
        "As robots increasingly share workspaces with people, sensors are required that "
        "can detect an approaching object before contact occurs, measure the contact force "
        "once contact is established, and at the same time perceive their own deformation. "
        "Implementing all three with rigid sensors requires separate proximity, tactile and "
        "strain devices, and such assemblies are difficult to apply to curved or highly "
        "deformable surfaces. Flexible sensors remove this constraint, but reading several "
        "physical quantities from a single compliant element inevitably introduces signal "
        "coupling."), align="j")
    para(doc, L, t(
        "기존 디커플링 전략은 크게 세 가지로 나뉜다. (i) 재료 설계 기반 접근은 자극별로 응답이 분리되도록 "
        "복합 재료를 설계하지만 공정이 복잡하고 범용성이 낮다. (ii) 구조 설계 기반 접근은 층을 분리하거나 "
        "전극을 다중화하지만 배선 수가 늘어 유연성과 신뢰성을 희생한다. (iii) 데이터 기반 접근은 학습으로 "
        "역매핑을 얻지만, 대부분 PC에서 추론을 수행하기 때문에 USB 왕복 지연 20–40 ms가 실시간 피드백 제어를 "
        "가로막는다. 또한 인덕티브 방식 유연 센서 연구 대부분은 LCR 미터 등 탁상형 계측기를 필요로 해 이동형 "
        "응용에 적합하지 않다.",
        "Existing decoupling strategies fall into three groups. (i) Material-level designs "
        "engineer composites so that responses to different stimuli separate, but the "
        "processes are complex and poorly generalizable. (ii) Structural designs separate "
        "layers or multiply electrodes, at the cost of additional wiring and reduced "
        "compliance and reliability. (iii) Data-driven approaches learn the inverse "
        "mapping, but inference is usually performed on a host PC, where a 20–40 ms USB "
        "round trip precludes real-time feedback control. Moreover, most inductive flexible "
        "sensor studies rely on benchtop instruments such as LCR meters and are therefore "
        "unsuitable for mobile applications."), align="j")
    para(doc, L, t(
        "본 연구는 세 번째 계열에 속하되, 세 가지 점에서 차별화된다. 첫째, 물리적 비대칭을 측정으로 확인하고 "
        "그것을 모델 구조에 직접 반영한다. 둘째, 추론을 MCU 안에서 수행하여 PC를 완전히 제거한다. 셋째, "
        "오프라인 held-out 성능과 실기 성능을 분리해 보고하고, 두 값이 어긋나는 구간과 그 원인을 명시한다. "
        "본 논문의 기여는 다음과 같다.",
        "The present work belongs to the third group but differs in three respects. First, "
        "the physical asymmetry is verified by measurement and encoded directly into the "
        "model architecture. Second, inference is executed inside the MCU, eliminating the "
        "host PC entirely. Third, offline held-out performance and on-hardware performance "
        "are reported separately, and the segments where the two diverge — together with "
        "the cause — are stated explicitly. The contributions are as follows."), align="j")
    bullets(doc, L, [
        t("두 가닥 단일 전극 EGaIn 나선 코일에서 L·R·V_TENG 세 신호를 1 ms 주기로 취득하는 TDM 측정 "
          "아키텍처와 전용 6층 PCB, 그리고 이를 구동하는 ISR 기반 논블로킹 펌웨어를 제작하였다.",
          "A TDM measurement architecture that acquires L, R and V_TENG every 1 ms from a "
          "two-wire single-electrode EGaIn spiral coil, together with a dedicated six-layer "
          "PCB and ISR-driven non-blocking firmware."),
        t("5축 스테퍼 스테이지와 6축 F/T 센서를 PC-MCU 시각 동기와 정상상태 태깅으로 결합한 자동 데이터 "
          "취득 플랫폼을 구축하여, 총 30만 행 이상의 동기화된 다자극 데이터셋을 확보하였다.",
          "An automated acquisition platform combining a five-axis stepper stage and a "
          "six-axis force/torque sensor with PC-MCU time synchronization and steady-state "
          "tagging, yielding synchronized multi-stimulus datasets of more than 300,000 rows."),
        t("도체·유전체 표적에 대한 (ε, d) 응답 곡면을 격자 측정하여 R–ε 단독 의존성과 L–(ε,d) 결합 "
          "의존성을 정량적으로 입증하였다.",
          "Gridded (strain, distance) response surfaces for conductive and dielectric "
          "targets, quantitatively establishing the strain-only dependence of R and the "
          "joint dependence of L."),
        t("접촉 모달리티에서 나타나는 점탄성 완화를 표준선형고체 모델로 규명하고, 그 시간상수를 인과적 EMA "
          "피처로 변환하여 힘 예측 오차를 절반 이하로 줄였다.",
          "Identification of the viscoelastic relaxation observed in the contact regime "
          "with a standard linear solid model, and conversion of its time constant into a "
          "causal EMA feature that halved the force prediction error."),
        t("1,413 파라미터 MoE 디커플러를 STM32에 임베딩하여 260 µs 추론을 실측하고, 실기 검증에서 드러난 "
          "실패 모드(자기강화 EMA 루프)와 그 수정 과정을 보고하였다.",
          "Embedding of a 1,413-parameter MoE decoupler on the STM32 with a measured 260 µs "
          "inference time, and a report of the failure mode revealed only on hardware (a "
          "self-reinforcing EMA loop) together with its correction."),
    ], size=None)

    # ── 2. 센서 설계 ────────────────────────────────────────────────────────
    heading(doc, L, t("2. 센서 설계와 물리적 원리", "2. Sensor Design and Physical Principles"), 1)
    heading(doc, L, t("2.1 단일 전극 EGaIn 나선 코일", "2.1 Single-Electrode EGaIn Spiral Coil"), 2)
    para(doc, L, t(
        "센서 전극은 EGaIn 액체금속을 DIW(Direct Ink Writing) 방식으로 일래스토머 기판 위에 인쇄한 평면 "
        "직사각형 나선형 코일이다. 액체금속은 대변형에서도 도전 경로가 끊기지 않아 30 % 인장까지 반복 사용이 "
        "가능하며, 코일 형상 덕분에 하나의 도전 트레이스가 저항 소자와 인덕터 역할을 동시에 수행한다. 센서의 "
        "초기 유효 길이는 120 mm이고, 인장 시험은 0–36 mm(변형률 0–30 %) 범위에서 수행하였다. 코일은 두 가닥 "
        "배선만으로 계측 회로에 연결되며, 별도의 접지 전극이나 대향 전극을 두지 않는다는 의미에서 단일 전극 "
        "구조이다.",
        "The sensing electrode is a planar rectangular spiral coil printed from EGaIn "
        "liquid metal onto an elastomer substrate by direct ink writing (DIW). The liquid "
        "metal maintains a continuous conductive path under large deformation, permitting "
        "repeated use up to 30 % strain, and the coil geometry lets a single conductive "
        "trace act simultaneously as a resistive element and as an inductor. The initial "
        "effective length of the sensor is 120 mm, and tensile tests were performed over "
        "0–36 mm of elongation (0–30 % strain). The coil connects to the readout circuit "
        "through two wires only; it is single-electrode in the sense that no separate "
        "ground or counter electrode is required."), align="j")

    heading(doc, L, t("2.2 세 신호원의 생성 기구", "2.2 Generation Mechanisms of the Three Signals"), 2)
    para(doc, L, t(
        "동일한 코일에서 서로 다른 물리 기구로 세 신호가 생성된다.",
        "Three signals are generated from the same coil through distinct physical "
        "mechanisms."), align="j")
    bullets(doc, L, [
        t("DC 저항 R — 도선이 늘어나면 길이가 증가하고 단면적이 감소하여 저항이 증가한다. 근접한 물체는 "
          "도전 경로에 영향을 주지 않으므로 R은 원리적으로 근접거리와 무관하다.",
          "DC resistance R - stretching increases the conductor length and reduces its "
          "cross-section, raising the resistance. A nearby object does not alter the "
          "conductive path, so R is in principle independent of proximity."),
        t("인덕턴스 L — 코일의 자기 인덕턴스는 형상(권선 면적·둘레)에 의존하므로 인장에 반응한다. 동시에 "
          "도체가 접근하면 와전류 손실에 의한 반사 임피던스가 실효 인덕턴스를 낮추고, 유전체가 접근하면 "
          "기생 정전용량 변화가 공진 주파수를 이동시킨다. 따라서 L은 인장과 근접에 모두 의존한다.",
          "Inductance L - the self-inductance of the coil depends on its geometry (turn "
          "area and perimeter) and therefore responds to strain. At the same time, an "
          "approaching conductor lowers the effective inductance through eddy-current "
          "reflected impedance, while an approaching dielectric shifts the resonant "
          "frequency through a change in parasitic capacitance. L therefore depends on "
          "both strain and proximity."),
        t("TENG 전압 V — 표면 접촉·분리 시 마찰전기 효과로 발생하는 자체 발전 전압으로, 접촉 이벤트의 "
          "발생 시점을 표시한다. 본 연구의 디커플러 입력에는 포함하지 않았고(3.1절), 취득 채널로만 유지하였다.",
          "TENG voltage V - a self-generated voltage produced by the triboelectric effect "
          "during surface contact and separation, marking the instant at which a contact "
          "event occurs. It was not used as a decoupler input in this work (Section 3.1) "
          "and was retained only as an acquisition channel."),
    ])
    para(doc, L, t(
        "인덕턴스는 LDC1614가 측정하는 LC 탱크의 공진 주파수 f로부터 환산한다. f ∝ 1/√L 이므로 기준 상태 "
        "대비 상대 변화는 다음과 같이 계산된다.",
        "The inductance is derived from the resonant frequency f of the LC tank measured by "
        "the LDC1614. Since f is proportional to 1/√L, the relative change with "
        "respect to a reference state is computed as"), align="j")
    eq(doc, L, "ΔL/L₀ = (f₀ / f)² − 1,    ΔR/R₀ = (r − r₀) / r₀")
    para(doc, L, t(
        "여기서 f₀, r₀은 무변형·최대 이격 조건에서 세션별로 취한 중앙값 기준선이다. 기준선을 세션마다 다시 "
        "잡는 이유는 액체금속 센서의 초기 저항이 재장착·온도에 따라 수 % 수준에서 달라지기 때문이다.",
        "Here f₀ and r₀ are session-wise median baselines taken in the undeformed, "
        "maximum-separation condition. Baselines are re-estimated for every session because "
        "the initial resistance of a liquid-metal sensor varies by a few percent with "
        "remounting and temperature."), align="j")

    heading(doc, L, t("2.3 결합 구조와 디커플링 전제", "2.3 Coupling Structure and the Decoupling Premise"), 2)
    para(doc, L, t(
        "이론 모델로는 반사 임피던스를 포함한 다음 형태가 널리 쓰인다.",
        "The following reflected-impedance formulation is commonly used as a theoretical "
        "model."), align="j")
    eq(doc, L, "L(ε, d) = L_self(ε) − ω²M(ε,d)²·L_t / (R_t² + ω²L_t²)")
    eq(doc, L, "R_s(ε, d) = R_DC(ε) + ω²M(ε,d)²·R_t / (R_t² + ω²L_t²)")
    para(doc, L, t(
        "그러나 이 식을 그대로 역산하려면 상호 인덕턴스 M(ε,d)의 해석적 형태가 필요하고, 근거리·대변형 극단 "
        "조건에서 야코비안이 특이해져 수치 발산이 발생한다. 본 연구에서는 대신 경험적 피팅 모델",
        "Inverting these expressions directly, however, requires an analytical form for the "
        "mutual inductance M(strain, d), and the Jacobian becomes singular in the extreme "
        "regime of short distance and large deformation, producing numerical divergence. "
        "This work instead adopts the empirical fitting model"), align="j")
    eq(doc, L, "ΔR/R₀ = α₁ε + α₂ε²,    ΔL/L₀ = β₁ε + β₂/(d+d₀)^k + β₃·ε/(d+d₀)")
    para(doc, L, t(
        "을 사용하고, 이를 해석적 역산이 아니라 학습 손실의 제약항으로만 활용한다(6.1절). 디커플링의 전제는 "
        "위 두 식의 구조적 비대칭 — R은 ε만의 함수이고 L은 (ε, d)의 함수 — 이며, 이 전제가 실제로 성립하는지는 "
        "5장에서 측정으로 검증한다.",
        "and uses it only as a constraint term in the training loss rather than for "
        "analytical inversion (Section 6.1). The premise for decoupling is the structural "
        "asymmetry of these two expressions - R is a function of strain alone while L is a "
        "function of both strain and distance — and Section 5 verifies by measurement "
        "whether that premise actually holds."), align="j")

    # ── 3. 측정 시스템 ──────────────────────────────────────────────────────
    heading(doc, L, t("3. 측정 시스템", "3. Measurement System"), 1)
    heading(doc, L, t("3.1 시분할 측정(TDM) 펌웨어", "3.1 Time-Division Measurement Firmware"), 2)
    para(doc, L, t(
        "하나의 코일을 세 가지 방식으로 읽으려면 측정 경로를 시간축에서 분리해야 한다. 그림 1은 신호 경로와 "
        "1 ms TDM 스케줄을 함께 보여준다. TIM7이 1 ms마다 인터럽트를 발생시키면 두 경로가 동시에 시작된다. "
        "I²C 경로는 LDC1614의 28비트 공진 주파수 레지스터를 체인 DMA로 읽어 약 200 µs 안에 완료하고, ADC 경로는 "
        "ADG734 멀티플렉서를 TENG 모드로 전환한 뒤 TIM6를 기동한다. TIM6가 150 µs 후 만료되면 TENG 값을 확정하고 "
        "MUX를 저항 모드로 전환하며(스위칭 시간 29 ns), 다시 150 µs 후 저항 값을 확정한다. 두 경로 중 나중에 "
        "끝나는 쪽이 갱신 플래그를 세우고 상태를 IDLE로 되돌린다. 모든 전송이 DMA로 수행되므로 블로킹 대기가 "
        "없고, 추론을 추가하기 전 기준으로 CPU 유휴율은 93.9 %였다.",
        "Reading a single coil in three different ways requires the measurement paths to be "
        "separated in time. Figure 1 shows the signal path together with the 1 ms TDM "
        "schedule. When TIM7 fires every 1 ms, two paths start concurrently. The I²C path "
        "reads the 28-bit resonant-frequency registers of the LDC1614 through chained DMA "
        "transfers, completing in about 200 µs, while the ADC path switches the ADG734 "
        "multiplexer to TENG mode and starts TIM6. When TIM6 expires after 150 µs the TENG "
        "value is latched and the multiplexer is switched to resistance mode (switching time "
        "29 ns); after a further 150 µs the resistance value is latched. Whichever path "
        "finishes last sets the update flag and returns the state machine to IDLE. Because "
        "all transfers use DMA there is no blocking wait, and the CPU idle fraction was "
        "93.9 % before inference was added."), align="j")
    figure(doc, L, "fig1_tdm.png", t(
        "그림 1. (a) 단일 전극 신호 경로. 동일한 EGaIn 코일이 ADG734 아날로그 멀티플렉서를 통해 LDC1614, "
        "TENG용 ADC, 저항 측정용 ADC에 순차 연결된다. (b) 1 ms TDM 스케줄. I²C DMA와 ADC DMA가 병렬로 "
        "진행되고, 남는 시간에 MoE 추론(실측 260 µs)이 수행된다.",
        "Fig. 1. (a) Single-electrode signal path. The same EGaIn coil is connected in turn "
        "to the LDC1614, the TENG ADC and the resistance ADC through an ADG734 analog "
        "multiplexer. (b) The 1 ms TDM schedule. I²C DMA and ADC DMA proceed in parallel, "
        "and MoE inference (measured at 260 µs) runs in the remaining time."))

    heading(doc, L, t("3.2 다신호 스위칭 PCB", "3.2 Multisignal Switching PCB"), 2)
    para(doc, L, t(
        "전용 보드는 EasyEDA Pro로 설계한 65 × 52 mm 6층 기판이다. 메인 MCU는 STM32G473CBT6(Cortex-M4F, "
        "170 MHz, 플래시 128 KB, SRAM 32 KB)이며, 인덕턴스 측정은 LDC1614(I2C2, 주소 0x2A, 28비트 출력), "
        "신호 경로 전환은 ADG734 4채널 아날로그 스위치가 담당한다. 각 채널의 ADC 입력은 연산 증폭기로 버퍼링되며, "
        "최대 4채널까지 동시 취득할 수 있도록 설계되었다(본 연구의 모든 실험은 1채널로 수행). MUX 상태 조합은 "
        "세 가지로, SW1/SW2를 HIGH로 두면 코일이 LDC 공진 회로에 연결되고, 모두 LOW로 두면 코일이 부유 상태가 "
        "되어 TENG 전압을 읽을 수 있으며, SW3/SW4를 HIGH로 두면 전압 분배 회로가 연결되어 DC 저항을 읽는다. "
        "USB-UART는 데이터 스트리밍용이며 시스템 동작 자체에는 필요하지 않다.",
        "The dedicated board is a 65 × 52 mm six-layer design produced in EasyEDA Pro. The "
        "main MCU is an STM32G473CBT6 (Cortex-M4F, 170 MHz, 128 KB flash, 32 KB SRAM); "
        "inductance is measured by an LDC1614 (I2C2, address 0x2A, 28-bit output) and the "
        "signal path is switched by ADG734 four-channel analog switches. Each channel's ADC "
        "input is buffered by an operational amplifier, and the board supports up to four "
        "simultaneous channels (all experiments in this work used one). Three multiplexer "
        "states are defined: with SW1/SW2 high the coil is connected to the LDC resonant "
        "circuit; with all switches low the coil floats so that the TENG voltage can be "
        "read; with SW3/SW4 high a voltage divider is engaged for DC resistance. The "
        "USB-UART interface is used for data streaming and is not required for system "
        "operation."), align="j")

    heading(doc, L, t("3.3 5축 시험 플랫폼과 동기 취득",
                      "3.3 Five-Axis Test Platform and Synchronized Acquisition"), 2)
    para(doc, L, t(
        "인장과 근접·접촉을 독립적으로 제어하기 위해 5축 스테퍼 포지셔닝 스테이지를 직접 제작하였다. XA/XB/YA/YB "
        "네 축이 센서를 대칭으로 인장하고, Z축이 표적을 센서 표면에 대해 수직으로 이동시킨다. Arduino "
        "펌웨어(AccelStepper 기반)가 축별 절대·상대 이동, 원점 복귀, 리밋 스위치 알람을 처리하고, PyQt5 GUI가 "
        "시퀀스를 스크립트로 구동한다. 기본 환산은 200 step/rev × 8 마이크로스텝 ÷ 5 mm 피치 = 320 step/mm이다.",
        "A five-axis stepper positioning stage was built in-house so that strain and "
        "proximity/contact could be controlled independently. Four axes (XA/XB/YA/YB) "
        "stretch the sensor symmetrically while the Z axis moves the target perpendicular "
        "to the sensor surface. Arduino firmware based on AccelStepper handles absolute and "
        "relative moves, homing and limit-switch alarms, and a PyQt5 GUI drives the sequence "
        "from a script. The default conversion is 200 steps/rev × 8 microsteps / 5 mm pitch "
        "= 320 steps/mm."), align="j")
    para(doc, L, t(
        "초기 실험은 PC와 MCU를 비동기로 기록한 뒤 피크를 추출해 보간하는 방식이었는데, 스테퍼 가감속 "
        "구간에서 위치 라벨과 센서 신호가 어긋나는 문제가 있었다. 이를 해결하기 위해 동기 취득 시스템을 "
        "구축하여 PC가 모터 명령 타임스탬프와 MCU 스트림을 같은 시간축에 정렬하고, 가감속 과도 구간을 "
        "is_steady = 0으로 자동 태깅하도록 하였다. 접촉력의 참값은 6축 F/T 센서로 동시에 기록하였다. F/T "
        "센서는 세션마다 영점이 수백 mN 어긋나 있었으므로, 비접촉 구간(z ≥ 0)의 평균을 세션별 오프셋으로 "
        "제거한 값을 정답으로 사용하였다.",
        "Early experiments logged the PC and the MCU asynchronously and interpolated between "
        "extracted peaks, which misaligned position labels and sensor signals during stepper "
        "acceleration and deceleration. A synchronized acquisition system was therefore "
        "built in which the PC aligns motor-command timestamps and the MCU stream on a "
        "common time base and automatically tags acceleration transients as is_steady = 0. "
        "Ground-truth contact force was recorded simultaneously with a six-axis "
        "force/torque sensor. Because the F/T zero drifted by a few hundred millinewtons "
        "between sessions, the mean of the non-contact region (z >= 0) was removed as a "
        "session-wise offset before the force was used as a label."), align="j")

    # ── 4. 데이터셋 ─────────────────────────────────────────────────────────
    heading(doc, L, t("4. 데이터셋", "4. Datasets"), 1)
    para(doc, L, t(
        "연구 진행에 따라 다섯 개의 데이터셋을 순차적으로 취득하였다. 각각의 목적과 규모는 표 1과 같다. "
        "모델 입력으로 실제 사용 가능한 값은 언제나 (ΔL/L₀, ΔR/R₀)와 그로부터 인과적으로 계산 가능한 값뿐이며, "
        "스테이지 위치와 F/T 힘은 오직 정답 라벨로만 사용하였다.",
        "Five datasets were acquired in sequence as the study progressed; their purposes and "
        "sizes are summarized in Table 1. The only quantities available to the model as "
        "inputs are always (ΔL/L₀, ΔR/R₀) and values computable causally from them; stage "
        "positions and F/T forces were used solely as ground-truth labels."), align="j")
    table(doc, L,
          [t("데이터셋", "Dataset"), t("프로토콜", "Protocol"), t("규모", "Size"),
           t("용도", "Purpose")],
          [["D1 (0332)",
            t("변형 37단계(1 mm) 고정 + 근접 50→0 mm 연속, 비동기",
              "37 strain levels (1 mm steps), continuous 50->0 mm proximity, asynchronous"),
            t("약 78,000 행", "approx. 78,000 rows"),
            t("초기 2단 PINN 학습", "initial two-stage PINN training")],
           ["D2 (P1/P2)",
            t("P1: 변형 19단계 × 근접 연속 스윕 / P2: 근접 13단계 × 변형 스윕(2회)",
              "P1: 19 strain levels × continuous proximity sweep; P2: 13 proximity levels x "
              "strain sweep (2 reps)"),
            t("금속 45,633행 / 손 37,116행", "metal 45,633 rows / hand 37,116 rows"),
            t("(ε,d) 응답 곡면 특성화", "characterization of the (strain, d) response surface")],
           ["D3 (0519)",
            t("연속 동시 스윕 2세션(램프형/왕복형), PC-MCU 동기",
              "two continuous simultaneous sweeps (ramp / oscillate), PC-MCU synchronized"),
            t("188,232행 → 전처리 후 33,450", "188,232 rows -> 33,450 after preprocessing"),
            t("근접+인장 디커플러 학습", "training of the proximity + strain decoupler")],
           ["D4 (0806)",
            t("변형 19단계 × 근접→접촉 왕복 스윕, F/T 동시 기록, 최대 10.1 N",
              "19 strain levels × proximity-to-contact sweep with simultaneous F/T "
              "recording, up to 10.1 N"),
            t("51,858행 / 569 s", "51,858 rows / 569 s"),
            t("접촉 물리 분석 및 MoE 학습", "contact physics analysis and MoE training")],
           ["D5 (0819)",
            t("실기 검증 3세션: Part1 근접 스윕 / Part2 인장 스윕 / Part3 동시",
              "three on-hardware validation sessions: Part 1 proximity sweeps, Part 2 strain "
              "sweeps, Part 3 simultaneous"),
            t("26,673 / 34,016 / 32,556행", "26,673 / 34,016 / 32,556 rows"),
            t("임베디드 실시간 검증", "embedded real-time validation")]],
          caption=t("표 1. 데이터셋 요약.", "Table 1. Summary of the datasets."),
          widths=[2.2, 6.2, 3.6, 4.0])
    para(doc, L, t(
        "D3의 전처리는 다음 순서로 수행하였다. (1) 변형 < 0.5 %, 근접 > 35 mm 조건의 중앙값으로 기준선 "
        "L₀, R₀를 재추출하고 ΔL, ΔR을 재계산한다. (2) LDC1614 레지스터 포화(0x0FFFFFFF)와 물리적으로 불가능한 "
        "범위(|ΔL| > 30 %, ΔR ∉ (−5, 30) %)를 제거한다. (3) (ε, d) 평면을 24 × 24 격자로 나누고 셀당 최대 "
        "30 샘플로 상한을 두어 과대표집을 보정한다. (4) 두 세션을 병합하고 무작위 셔플 후 70/15/15로 분할한다. "
        "IIR 필터를 적용하지 않고 원시 신호를 그대로 학습에 사용한 것은 의도적인 선택이다. α = 0.02인 IIR은 "
        "시간상수가 약 500 ms여서, 10 mm/s로 이동하는 구간에서 5 mm에 해당하는 위상 지연을 만들고, 그 결과 "
        "지연된 입력이 현재 시각의 라벨과 매핑되어 동적 구간 오차를 키우기 때문이다.",
        "Preprocessing of D3 proceeded as follows. (1) Baselines L₀ and R₀ were re-extracted "
        "as medians over the region with strain < 0.5 % and distance > 35 mm, and ΔL and ΔR "
        "were recomputed. (2) LDC1614 register saturation (0x0FFFFFFF) and physically "
        "impossible ranges (|ΔL| > 30 %, ΔR outside (-5, 30) %) were removed. (3) The "
        "(strain, d) plane was divided into a 24 × 24 grid and capped at 30 samples per cell "
        "to correct over-representation. (4) The two sessions were merged, shuffled and "
        "split 70/15/15. Training on raw signals rather than IIR-filtered ones was a "
        "deliberate choice: an IIR filter with α = 0.02 has a time constant of about "
        "500 ms, which at a traverse speed of 10 mm/s corresponds to a 5 mm phase lag, so "
        "that delayed inputs would be mapped onto present-time labels and dynamic-segment "
        "error would grow."), align="j")

    # ── 5. 신호 특성화 ──────────────────────────────────────────────────────
    heading(doc, L, t("5. 신호 특성화", "5. Signal Characterization"), 1)
    heading(doc, L, t("5.1 (ε, d) 응답 곡면", "5.1 (Strain, Distance) Response Surfaces"), 2)
    para(doc, L, t(
        "그림 2는 D2를 격자 평균하여 얻은 응답 곡면이다. 금속 표적에 대한 ΔR(그림 2b)의 등고선은 근접거리 "
        "축과 거의 완전히 평행하며, 이는 저항이 인장에만 의존한다는 2.3절의 전제가 실측으로 성립함을 뜻한다. "
        "반면 ΔL(그림 2a)의 등고선은 d < 10 mm 영역에서 급격히 휘어지며, 같은 인장 상태에서도 근접거리에 따라 "
        "−15.7 %에서 +14.5 %까지 부호가 바뀔 정도로 크게 변한다. 이 강한 곡률이 근접 정보를 인덕턴스에 "
        "인코딩하는 성분이다.",
        "Figure 2 shows the response surfaces obtained by grid-averaging D2. For the metal "
        "target the contours of ΔR (Fig. 2b) are essentially parallel to the distance axis, "
        "confirming by measurement the premise of Section 2.3 that resistance depends on "
        "strain alone. The contours of ΔL (Fig. 2a), by contrast, bend sharply for d < 10 mm "
        "and, at a fixed strain, vary from -15.7 % to +14.5 % - changing sign — as the "
        "distance changes. This strong curvature is the component that encodes proximity "
        "information in the inductance."), align="j")
    figure(doc, L, "fig2_surfaces.png", t(
        "그림 2. 변형률과 근접거리에 대한 신호 응답 곡면(D2, 격자 평균). (a),(b) 금속 표적: ΔL은 근접거리에 "
        "강하게 의존하지만 ΔR의 등고선은 수직이다(인장 전용). (c),(d) 손 표적: 두 신호 모두 등고선이 거의 "
        "수직으로, 유전체 표적에서는 이 거리 범위에서 인덕턴스에 실린 근접 정보가 미약하다.",
        "Fig. 2. Signal response surfaces over strain and proximity (D2, grid-averaged). "
        "(a),(b) Metal target: ΔL depends strongly on distance whereas the contours of ΔR "
        "are vertical (strain only). (c),(d) Hand target: contours of both signals are "
        "nearly vertical, indicating that for a dielectric target the proximity information "
        "carried by the inductance is weak over this distance range."))
    para(doc, L, t(
        "표적 종류에 따른 차이는 물리 기구의 차이에서 온다. 금속에서는 와전류 손실이 지배적이어서 근접 시 "
        "실효 인덕턴스가 크게 감소하는 반면, 손(유전체)에서는 기생 정전용량 변화만 작용하여 ΔL이 항상 양수이고 "
        "크기도 작다. 그림 2c에서 손 표적의 ΔL 등고선이 거의 수직인 것은, 이 조건에서 인덕턴스가 사실상 인장 "
        "센서로만 동작한다는 뜻이며, 결과적으로 유전체 표적에 대한 근접 디커플링은 도체 표적보다 근본적으로 "
        "어렵다. 이후의 모든 모델링은 도체 표적을 대상으로 한다.",
        "The difference between targets follows from the underlying mechanism. For metal, "
        "eddy-current loss dominates and the effective inductance drops substantially on "
        "approach; for a hand (a dielectric), only the parasitic capacitance changes, so ΔL "
        "remains positive and small. The nearly vertical ΔL contours for the hand target in "
        "Fig. 2c mean that, under these conditions, the inductance behaves essentially as a "
        "strain sensor alone, and proximity decoupling for dielectric targets is therefore "
        "fundamentally harder than for conductive ones. All subsequent modelling targets the "
        "conductive case."), align="j")

    heading(doc, L, t("5.2 접촉 영역의 점탄성", "5.2 Viscoelasticity in the Contact Regime"), 2)
    para(doc, L, t(
        "접촉 모달리티를 추가하자 비접촉 실험에서는 없던 세 현상이 나타났다. 첫째, 같은 깊이·같은 사이클 안에서 "
        "인덕턴스의 샘플 간 표준편차가 압축이 깊어질수록 0.09 %p에서 0.52 %p까지 약 5배 증가하였다. 저항 측정은 "
        "단순 전압 분배여서 공진 품질과 무관한 반면 인덕턴스 측정만 공진 주파수에 의존한다는 점을 고려하면, "
        "이 비대칭은 압축에 의한 국소 단면적 감소가 코일의 Q-factor를 떨어뜨린 결과로 해석된다.",
        "Adding the contact modality produced three phenomena absent from the non-contact "
        "experiments. First, within the same cycle and at the same depth, the "
        "sample-to-sample standard deviation of the inductance grew about fivefold, from "
        "0.09 %p to 0.52 %p, as compression deepened. Since the resistance measurement is a "
        "simple voltage division independent of resonance quality while only the inductance "
        "measurement depends on the resonant frequency, this asymmetry is interpreted as a "
        "reduction of the coil Q factor caused by the local cross-section reduction under "
        "compression."), align="j")
    para(doc, L, t(
        "둘째, 로딩 경로와 언로딩 경로가 어긋나는 히스테리시스가 관측되었다(그림 3a, 3b). 깊이를 고정한 채 "
        "유지(dwell)하는 동안 ΔL은 2.33 %p, ΔR은 5.73 %p 더 변화했고, 힘을 완전히 제거한 뒤 남는 잔차는 "
        "각각 0.57 %p와 0.08 %p에 불과했다. 즉 변화의 대부분은 영구 손상이 아니라 가역적인 시간 지연 성분이다. "
        "이 거동은 즉시 반응하는 탄성 성분과 시간에 따라 완화되는 점성 성분이 병렬로 존재하는 표준선형고체(SLS) "
        "모델과 일치한다. 깊이가 고정된 dwell 구간에서 SLS의 지배 방정식 τ·dσ/dt + σ = E·ε의 해는 "
        "지수 완화 형태가 되며, 실측 dwell 곡선에 최소제곱 피팅한 결과 τ = 0.93 s를 얻었다(그림 3c). "
        "전체 데이터셋에 대한 채널별 피팅에서는 τ_L = 1.33 s, τ_R = 0.59 s, 통합 τ = 1.01 s였다.",
        "Second, hysteresis was observed between the loading and unloading paths "
        "(Figs. 3a, 3b). While the depth was held constant (dwell), ΔL drifted by a further "
        "2.33 %p and ΔR by 5.73 %p, whereas the residuals after full unloading were only "
        "0.57 %p and 0.08 %p respectively. Most of the change is therefore a reversible "
        "time-lag component rather than permanent damage. This behaviour matches a standard "
        "linear solid (SLS) model in which an instantaneous elastic component and a "
        "time-relaxing viscous component act in parallel. During a constant-depth dwell the "
        "solution of the governing equation τ·dσ/dt + σ = E·ε is an exponential relaxation; "
        "a least-squares fit to the measured dwell curve gave τ = 0.93 s (Fig. 3c). "
        "Channel-wise fits over the whole dataset gave τ_L = 1.33 s, τ_R = 0.59 s and a "
        "combined τ = 1.01 s."), align="j")
    figure(doc, L, "fig3_pressure.png", t(
        "그림 3. 접촉 영역의 신호 거동(D4). (a) 무변형 상태에서 10.1 N까지 가압: ΔR 변화 폭은 3.95 %p에 "
        "그친다. (b) 30 % 인장 상태에서 9.2 N 가압: ΔR 변화 폭이 26.14 %p로 6.6배 증가하고, ΔL은 −30.4 %까지 "
        "떨어졌다가 최대 힘 근처에서 −20.7 %로 반전한다. 로딩/언로딩 경로가 벌어지는 것이 히스테리시스다. "
        "(c) 깊이를 고정한 dwell 구간의 ΔR 완화와 SLS 지수 피팅(τ = 0.93 s).",
        "Fig. 3. Signal behaviour in the contact regime (D4). (a) Loading to 10.1 N at zero "
        "strain: the ΔR span is only 3.95 %p. (b) Loading to 9.2 N at 30 % strain: the ΔR "
        "span grows 6.6-fold to 26.14 %p, and ΔL falls to -30.4 % before reversing to "
        "-20.7 % near peak force. The separation of the loading and unloading paths is the "
        "hysteresis. (c) Relaxation of ΔR during a constant-depth dwell with an SLS "
        "exponential fit (τ = 0.93 s)."))

    heading(doc, L, t("5.3 인장 × 접촉력 교차 민감도",
                      "5.3 Strain-Force Cross-Sensitivity"), 2)
    para(doc, L, t(
        "셋째이자 모델 설계에 가장 큰 영향을 준 발견은, 인장 상태가 압력 민감도 자체를 바꾼다는 것이다. "
        "그림 3에서 보듯 무변형 상태에서 10 N을 가해도 ΔR은 3.95 %p만 움직이지만, 30 % 인장 상태에서는 유사한 "
        "힘에 대해 26.14 %p가 움직인다(약 6.6배). 이는 2.3절의 R_theory(ε) = α₁ε + α₂ε² 가정이 압력이 함께 "
        "작용하는 상황에서는 성립하지 않으며 ε×F 교차항이 필요함을 뜻한다. 두 자극의 민감도 방향 벡터를 "
        "선형 근사하면 인장 1 %p당 (ΔL, ΔR) = (+0.635, +0.664), 접촉력 1 N당 (+2.070, +11.575)이며, 두 벡터 "
        "사이 각도는 33.6°, 조건수는 약 23이다. 즉 두 자극은 완전히 겹치지는 않지만 선형 역산으로 분리하기에는 "
        "조건이 나쁘다. 실제로 물리식 역산만 사용한 경우(부록 S3) 결정계수는 0.26에 그쳤다.",
        "The third finding, which most strongly shaped the model design, is that the strain "
        "state changes the pressure sensitivity itself. As Fig. 3 shows, applying 10 N at "
        "zero strain moves ΔR by only 3.95 %p, whereas at 30 % strain a comparable force "
        "moves it by 26.14 %p, a factor of about 6.6. The assumption R_theory(ε) = α₁ε + α₂ε² "
        "of Section 2.3 therefore fails when pressure is applied simultaneously, and a "
        "strain-force cross term is required. A linear approximation of the two sensitivity "
        "directions gives (ΔL, ΔR) = (+0.635, +0.664) per %p of strain and (+2.070, +11.575) "
        "per newton of contact force; the angle between the vectors is 33.6 degrees and the "
        "condition number is about 23. The two stimuli are therefore not perfectly "
        "degenerate, but the problem is poorly conditioned for linear inversion. Indeed, "
        "physics-only inversion achieved a coefficient of determination of just 0.26 "
        "(Appendix S3)."), align="j")

    # ── 6. 디커플링 모델 ────────────────────────────────────────────────────
    heading(doc, L, t("6. 디커플링 모델", "6. Decoupling Models"), 1)
    heading(doc, L, t("6.1 2단계 물리 정보 디커플러", "6.1 Two-Stage Physics-Informed Decoupler"), 2)
    para(doc, L, t(
        "5.1절에서 확인한 비대칭을 그대로 구조로 옮기면 2단계 추정기가 된다. 1단계는 ΔR만으로 변형률을 "
        "추정하고(ε̂), 2단계는 ΔL과 ε̂을 함께 받아 근접거리를 추정한다(d̂). 이 구조는 '저항이 변형률만의 "
        "함수'라는 물리 사실을 귀납 편향으로 부여하므로, 동일 파라미터 예산에서 단일 종단 모델보다 유리하다. "
        "실제로 약 50 K 파라미터로 예산을 맞춘 공정 비교에서 2단계 구조의 근접 MAE는 1.783 mm로, 종단 구조의 "
        "1.827 mm보다 우수하였다.",
        "Transferring the asymmetry established in Section 5.1 directly into the "
        "architecture yields a two-stage estimator: stage 1 estimates strain from ΔR alone, "
        "and stage 2 receives both ΔL and the estimated strain to predict distance. The "
        "structure imposes the physical fact that resistance is a function of strain only as "
        "an inductive bias, and is therefore advantageous over a single end-to-end model at "
        "equal parameter budget. In a fair comparison at approximately 50 K parameters the "
        "two-stage model achieved a proximity MAE of 1.783 mm against 1.827 mm for the "
        "end-to-end model."), align="j")
    para(doc, L, t(
        "물리 정보 신경망(PINN) 형태로 학습할 때는 데이터 손실에 물리 잔차를 더한다.",
        "When trained as a physics-informed neural network (PINN), a physics residual is "
        "added to the data loss."), align="j")
    eq(doc, L, "L_total = L_data + λ · L_phys")
    eq(doc, L, "L_phys = MSE(R_theory(ε̂), ΔR) + MSE(L_theory(ε̂, d̂), ΔL)")
    para(doc, L, t(
        "λ는 첫 50 에폭 동안 0으로 두었다가 이후 0.10까지 선형 증가시켰다. 초기에는 순수 데이터 손실로 수렴 "
        "방향을 잡고, 이후 물리 제약을 점진적으로 부과하기 위해서다. 특이점을 피하기 위해 d₀와 k는 softplus로 "
        "양수 제약을 두었다. 818개 신경망 파라미터와 7개 물리 파라미터로 학습한 결과 테스트 MAE는 변형률 "
        "0.356 %, 근접거리 1.797 mm였고, 유효 근접 범위인 d ≤ 15 mm에서는 0.337 mm, d ≤ 10 mm에서는 0.200 mm "
        "였다. 다만 데이터가 충분한 조건에서 물리 손실의 순수 기여는 크지 않았다(근접 MAE 0.01 mm 개선). "
        "물리 제약의 실질적 가치는 정확도 향상보다 외삽 영역에서의 발산 억제에 있다고 판단된다.",
        "The weight λ was held at zero for the first 50 epochs and then increased "
        "linearly to 0.10, so that the initial convergence direction is set by the data loss "
        "alone before the physics constraint is applied progressively. To avoid a "
        "singularity, d₀ and k were constrained positive through a softplus. Training with "
        "818 network parameters and 7 physical parameters gave test MAEs of 0.356 % for "
        "strain and 1.797 mm for distance, improving to 0.337 mm for d <= 15 mm and 0.200 mm "
        "for d <= 10 mm within the useful proximity range. With ample data, however, the "
        "isolated contribution of the physics loss was small (0.01 mm improvement in "
        "proximity MAE); its practical value appears to lie less in accuracy than in "
        "suppressing divergence in extrapolation regions."), align="j")

    heading(doc, L, t("6.2 아키텍처 탐색과 양자화", "6.2 Architecture Search and Quantization"), 2)
    para(doc, L, t(
        "임베딩 비용을 최소화하기 위해 동일한 2단계 구조를 유지한 채 13가지 크기의 신경망을 학습하여 파라미터 "
        "수와 정확도의 상충 관계를 조사하였다(그림 4). 46 파라미터의 최소 모델도 근접 MAE 2.115 mm를 달성했고, "
        "978 파라미터의 medium-deep 구조가 1.765 mm로 파레토 무릎에 해당했다. 파라미터를 10,946개까지 늘려도 "
        "1.773 mm로 개선이 없어, 이 문제의 본질적 난이도는 모델 용량이 아니라 데이터와 물리에 의해 결정됨을 "
        "확인하였다. 초기 배포에 사용한 50,306 파라미터 sklearn 모델과 비교하면 medium-deep은 파라미터 47배, "
        "가중치 ROM 29배, 활성화 SRAM 53배를 절감하면서 근접 MAE 차이는 0.09 mm에 불과하다. INT8 사후 양자화 "
        "오차는 변형률 0.020 %, 근접거리 0.032 mm로 센서 잡음 수준 이하였다.",
        "To minimize embedding cost, thirteen network sizes were trained with the same "
        "two-stage structure to map the trade-off between parameter count and accuracy "
        "(Fig. 4). Even the smallest 46-parameter model reached a proximity MAE of 2.115 mm, "
        "and a 978-parameter medium-deep configuration sat at the Pareto knee with 1.765 mm. "
        "Increasing the parameter count to 10,946 gave no improvement (1.773 mm), confirming "
        "that the intrinsic difficulty of the problem is set by the data and the physics "
        "rather than by model capacity. Relative to the 50,306-parameter scikit-learn model "
        "used for the first deployment, medium-deep reduces parameters by 47x, weight ROM by "
        "29x and activation SRAM by 53x for a proximity MAE penalty of only 0.09 mm. "
        "Post-training INT8 quantization error was 0.020 % in strain and 0.032 mm in "
        "distance, below the sensor noise floor."), align="j")
    figure(doc, L, "fig4_pareto.png", t(
        "그림 4. 2단계 디커플러 아키텍처 탐색 결과. 가로축은 파라미터 수(로그), 세로축은 근접거리 MAE이다. "
        "978 파라미터의 medium-deep이 파레토 무릎이며, 50,306 파라미터 모델과 정확도 차이는 0.09 mm이다.",
        "Fig. 4. Architecture search for the two-stage decoupler. The horizontal axis is the "
        "parameter count (log scale) and the vertical axis the proximity MAE. The "
        "978-parameter medium-deep configuration lies at the Pareto knee, within 0.09 mm of "
        "the 50,306-parameter model."), width_cm=10.5)

    heading(doc, L, t("6.3 점탄성에서 유도한 이력 피처", "6.3 History Features Derived from Viscoelasticity"), 2)
    para(doc, L, t(
        "5.2절에서 확인한 것처럼, 접촉 구간의 신호는 현재 깊이만으로 결정되지 않고 '얼마나 오래 눌려 있었는지'에 "
        "의존한다. 따라서 순간값만 입력받는 모델은 원리적으로 이 정보를 복원할 수 없다. SLS 모델의 지수 완화 해에서 "
        "출발하면, 과거 샘플의 기여가 exp(−Δt/τ)로 감쇠하는 가중평균, 즉 인과적 지수이동평균이 자연스럽게 "
        "도출된다. 실시간 구현에서는 재귀식 y_n = y_{n−1} + α(x_n − y_{n−1})로 계산되며, 곱셈 1회와 상태 변수 "
        "1개만 필요하므로 MCU에서 비용이 사실상 0이다. τ = 1.01 s에 대응하는 반감기는 0.702 s이다.",
        "As established in Section 5.2, the signal in the contact regime is not determined by "
        "the instantaneous depth alone but also by how long the sensor has been compressed. "
        "A model that receives only instantaneous values therefore cannot in principle "
        "recover this information. Starting from the exponential relaxation solution of the "
        "SLS model, a weighted average in which the contribution of past samples decays as "
        "exp(−Δt/τ) — that is, a causal exponential moving average — follows naturally. In "
        "a real-time implementation it is computed by the recursion "
        "yₙ = yₙ₋₁ + α(xₙ − yₙ₋₁), requiring one multiplication and one state "
        "variable, so its cost on the MCU is effectively zero. The half-life corresponding "
        "to τ = 1.01 s is 0.702 s."), align="j")
    para(doc, L, t(
        "이 피처 하나를 추가하자 접촉력 예측의 RMSE가 0.521 N에서 0.240 N으로 절반 이하가 되었다. 참고로 정답으로 "
        "사용한 F/T 센서 자체의 잡음이 같은 조건에서 ±0.19 N이므로, 이 오차는 라벨의 측정 한계에 근접한 값이다.",
        "Adding this single feature reduced the RMSE of the contact-force prediction from "
        "0.521 N to 0.240 N, less than half. For reference, the F/T sensor used as ground "
        "truth itself fluctuates by ±0.19 N under the same conditions, so this error is "
        "close to the measurement limit of the label."), align="j")

    heading(doc, L, t("6.4 게이트–전문가(MoE) 구조", "6.4 Gate-Expert (MoE) Architecture"), 2)
    para(doc, L, t(
        "비접촉 구간과 접촉 구간은 출력 물리량 자체가 다르다. 전자는 (변형률, 근접거리)를, 후자는 (변형률, "
        "접촉력)을 추정해야 하며, 입력–출력 관계의 형태도 다르다. 하나의 회귀 모델로 두 영역을 모두 담당하게 하면 "
        "각 영역의 정확도가 저하되므로, 접촉 여부를 먼저 분류한 뒤 영역별 전문가에게 위임하는 Mixture-of-Experts "
        "구조를 채택하였다(그림 5). 여섯 가지 후보 구조를 동일한 사이클 단위 held-out 분할로 비교한 결과는 표 2와 "
        "같다.",
        "The non-contact and contact regimes differ in the very quantities to be produced: "
        "the former requires (strain, distance) and the latter (strain, force), and the "
        "input-output relations also differ in form. Forcing a single regressor to cover both "
        "degrades accuracy in each, so a mixture-of-experts architecture was adopted in which "
        "contact is classified first and the regression is then delegated to a "
        "regime-specific expert (Fig. 5). Six candidate structures compared under the same "
        "cycle-wise held-out split are summarized in Table 2."), align="j")
    figure(doc, L, "fig5_moe.png", t(
        "그림 5. MoE 디커플러 구조. 게이트는 원시 (ΔL, ΔR)만 보고 접촉 여부를 판정하며, 그 결과에 따라 같은 "
        "사이클 안에서 EMA를 즉시 리셋한 뒤 해당 전문가를 실행한다. 총 1,413 파라미터.",
        "Fig. 5. Structure of the MoE decoupler. The gate observes only the raw (ΔL, ΔR) pair "
        "to decide contact, and its decision immediately resets the EMA within the same cycle "
        "before the corresponding expert is executed. Total: 1,413 parameters."))
    table(doc, L,
          [t("후보", "Candidate"), t("게이트 정확도", "Gate acc."),
           t("근접거리 RMSE", "Distance RMSE"), t("접촉력 RMSE", "Force RMSE"),
           t("전체 변형률 RMSE", "Overall strain RMSE"), t("파라미터", "Param.")],
          [[t("C1 기준선(이력 없음)", "C1 baseline (no history)"), "0.982", "0.410 mm",
            "0.521 N", "0.194 %p", "1,317"],
           [t("C2 게이트 + EMA", "C2 gate + EMA"), "1.000", "0.318 mm", "0.253 N",
            "0.108 %p", "1,429"],
           [t("C3 통합 MLP", "C3 unified MLP"), "—", "0.322 mm", "—", "0.288 %p", "1,506"],
           [t("C4 물리 + 잔차", "C4 physics + residual"), "—", "—", "0.314 N", "—", "704"],
           [t("C5 다중 시간상수", "C5 multi-τ"), "0.999", "0.259 mm", "0.240 N",
            "0.215 %p", "1,765"],
           [t("C5b GRU(압력 전문가)", "C5b GRU (pressure expert)"), "—", "—", "0.263 N",
            "—", "306"],
           [t("C6 하이브리드", "C6 hybrid"), "1.000", "0.318 mm", "0.263 N", "0.123 %p",
            "1,061"]],
          caption=t("표 2. MoE 후보 구조 비교(D4, 사이클 단위 held-out).",
                    "Table 2. Comparison of MoE candidates (D4, cycle-wise held-out)."),
          widths=[4.4, 2.4, 2.8, 2.4, 2.8, 1.8])
    para(doc, L, t(
        "네 가지를 관찰할 수 있다. 첫째, 접촉 판정 자체는 어려운 문제가 아니다. 이력 피처 없이도 정확도 98.2 %가 "
        "나오며, 접촉 순간 ΔL과 ΔR이 뚜렷하게 꺾이기 때문이다. 둘째, 이력 피처의 이득은 변형률보다 접촉력 "
        "예측에 집중된다. 셋째, 순수 물리식 역산(C4)은 데이터 품질이 좋을 때조차 학습 기반 모델에 크게 못 "
        "미쳤다. 넷째, GRU(C5b)는 정확도에서 EMA 기반 모델과 사실상 동률이지만 파라미터는 306개로 가장 작았다. "
        "즉 사람이 τ를 골라 EMA로 넣어준 정보를 순환 신경망이 더 작은 표현으로 스스로 압축해낸 것이다. 그럼에도 "
        "본 연구는 배포 모델로 C2를 선택했는데, X-CUBE-AI에서 Dense 레이어의 지원 성숙도가 높고 호출 간 은닉 "
        "상태 관리가 필요 없어 양자화 시 오차 누적 위험이 없기 때문이다.",
        "Four observations follow. First, contact detection is not the hard part: even "
        "without history features accuracy reaches 98.2 %, because ΔL and ΔR bend sharply at "
        "the instant of contact. Second, the benefit of history features is concentrated in "
        "force rather than strain prediction. Third, purely physics-based inversion (C4) fell "
        "far short of the learned models even on high-quality data. Fourth, the GRU (C5b) was "
        "essentially tied with the EMA-based models in accuracy while using only 306 "
        "parameters — the recurrent network compressed, into a smaller representation, the "
        "same information supplied manually through a hand-chosen τ. Nevertheless C2 was "
        "selected for deployment because dense layers are the most mature path in X-CUBE-AI "
        "and require no hidden state to be carried between calls, eliminating the risk of "
        "error accumulation under quantization."), align="j")

    # ── 7. 임베디드 구현 ────────────────────────────────────────────────────
    heading(doc, L, t("7. 임베디드 구현", "7. Embedded Implementation"), 1)
    heading(doc, L, t("7.1 배포 파이프라인", "7.1 Deployment Pipeline"), 2)
    para(doc, L, t(
        "학습된 scikit-learn 모델은 skl2onnx로 ONNX로 변환한 뒤 ST의 stedgeai 도구로 STM32용 C 코드로 생성하였다. "
        "sklearn과 ONNX 사이의 수치 검증 오차는 게이트 1e−6, 전문가 1e−5 미만이었다. StandardScaler는 ONNX "
        "그래프에 포함하지 않고 평균·표준편차 상수만 헤더로 추출하여 펌웨어에서 직접 정규화하도록 했으며, "
        "게이트·전문가 A·전문가 B가 각각 독립적으로 적합된 스케일러를 사용하므로 헤더에는 세 벌의 상수가 들어간다. "
        "펌웨어에서는 매 TDM 주기마다 moe_inference_run(ΔL, ΔR)이 한 번 호출되고, 게이트 → EMA 갱신 → 전문가 "
        "순으로 실행된 뒤 결과가 UART로 스트리밍된다. 추론 시간은 DWT 사이클 카운터로 직접 측정한다.",
        "The trained scikit-learn models were converted to ONNX with skl2onnx and then "
        "generated as STM32 C code with ST's stedgeai tool. Numerical verification between "
        "scikit-learn and ONNX agreed to better than 1e-6 for the gate and 1e-5 for the "
        "experts. The StandardScaler was not embedded in the ONNX graph; instead the mean and "
        "scale constants were exported as a C header and the normalization is performed "
        "directly in firmware. Because the gate and the two experts use independently fitted "
        "scalers, three constant sets appear in the header. In firmware, "
        "moe_inference_run(ΔL, ΔR) is called once per TDM cycle and executes gate -> EMA "
        "update -> expert in that order, after which the result is streamed over UART. "
        "Inference time is measured directly with the DWT cycle counter."), align="j")

    heading(doc, L, t("7.2 자원 사용량과 지연", "7.2 Resource Usage and Latency"), 2)
    para(doc, L, t(
        "표 3은 임베디드 구현의 자원 사용량을 정리한 것이다. 초기에 배포했던 50 K 파라미터 INT8 모델은 가중치 "
        "52 KB가 명령어 캐시에 들어가지 않아 플래시 대기 사이클이 발생했고, 실측 추론 시간이 1,068 µs로 TDM 주기를 "
        "초과했다(3.56 cycles/MAC). 반면 MoE 모델은 전체 가중치가 5.7 KB에 불과해 캐시에 상주하며, 실측 지연이 "
        "중앙값 260.4 µs, 95 백분위수 262.5 µs로 1 ms 주기 안에서 여유 있게 완결된다. 지연의 산포가 2 µs 수준에 "
        "불과하다는 점은 이 구조가 결정론적 제어 루프에 사용될 수 있음을 뜻한다. 참고로 동일 추론을 PC에서 "
        "수행할 경우 USB 왕복 지연만 20–40 ms가 발생하며 지터도 ±5–15 ms에 이른다.",
        "Table 3 summarizes the resource usage of the embedded implementation. The 50 K "
        "parameter INT8 model deployed initially had 52 KB of weights that did not fit in the "
        "instruction cache, incurring flash wait states and a measured inference time of "
        "1,068 µs — exceeding the TDM period — at 3.56 cycles per MAC. The MoE model, by "
        "contrast, has only 5.7 KB of weights that stay resident in cache, and its measured "
        "latency is 260.4 µs median with a 95th percentile of 262.5 µs, completing "
        "comfortably within the 1 ms period. That the spread is only about 2 µs means the "
        "architecture is usable in a deterministic control loop. By comparison, performing the "
        "same inference on a host PC incurs 20–40 ms of USB round-trip delay with "
        "±5–15 ms of jitter."), align="j")
    table(doc, L,
          [t("항목", "Item"), t("sklearn 2단 INT8 (초기 배포)", "sklearn two-stage INT8 (first deployment)"),
           t("MoE float32 (최종)", "MoE float32 (final)")],
          [[t("파라미터 수", "Parameters"), "50,306", "1,413"],
           [t("MACs / 추론", "MACs per inference"), "50,306",
            t("2,510 (게이트 202 + 전문가 1,154 × 2)",
              "2,510 (gate 202 + experts 1,154 × 2)")],
           [t("가중치 ROM", "Weight ROM"), "~52 KB",
            t("5.66 KB (272 B + 2,696 B × 2)", "5.66 KB (272 B + 2,696 B × 2)")],
           [t("활성화 SRAM", "Activation SRAM"), "15.3 KB", "368 B"],
           [t("전체 플래시 (펌웨어 포함)", "Total flash (with firmware)"),
            "112.5 KB (85.8 %)", "83.5 KB (65.2 %)"],
           [t("추론 지연 (DWT 실측)", "Inference latency (DWT)"),
            "1,068 µs", t("260 µs (중앙값), 263 µs (p95)", "260 µs median, 263 µs p95")],
           [t("TDM 주기 내 완결", "Completes within TDM period"),
            t("아니오", "no"), t("예", "yes")]],
          caption=t("표 3. STM32G473CBT6(170 MHz, 플래시 128 KB, SRAM 32 KB) 임베딩 자원 비교.",
                    "Table 3. Embedded resource comparison on the STM32G473CBT6 (170 MHz, "
                    "128 KB flash, 32 KB SRAM)."),
          widths=[4.6, 5.6, 5.6])

    heading(doc, L, t("7.3 실기에서만 드러난 실패 모드",
                      "7.3 A Failure Mode Visible Only on Hardware"), 2)
    para(doc, L, t(
        "최초 배포한 게이트는 EMA를 포함한 4입력 구조로, 오프라인 held-out 정확도가 100.0 %였다. 그러나 보드를 "
        "실제로 눌렀다 떼자 게이트가 접촉 해제 후에도 한동안 '접촉' 판정을 유지하는 현상이 나타났다. 원인은 "
        "학습 조건과 배포 조건의 불일치였다. 학습 시 EMA는 실제 접촉 라벨(z_mm 기준)이 바뀌는 정확한 순간에 "
        "리셋되도록 만들어졌지만, 배포된 보드에는 그 정답이 없으므로 '게이트 자신의 판단이 바뀌면 리셋'이라는 "
        "근사로 대체할 수밖에 없었다. 그 결과 다음과 같은 자기강화 루프가 형성되었다. 접촉을 해제하면 원시 "
        "ΔL·ΔR은 즉시 변하지만 EMA는 τ ≈ 1 s 동안 눌린 값에 머물고, 게이트가 그 오래된 EMA를 함께 보고 계속 "
        "'접촉'으로 판단하며, 판단이 바뀌지 않으니 리셋 조건도 걸리지 않는다.",
        "The gate deployed first had four inputs including the EMA features and achieved "
        "100.0 % held-out accuracy offline. When the board was physically pressed and "
        "released, however, the gate kept reporting contact for some time after release. The "
        "cause was a mismatch between the training and deployment conditions. During training "
        "the EMA was reset at the exact instant the true contact label (from z_mm) changed, "
        "but the deployed board has no such ground truth and had to approximate it by "
        "resetting whenever the gate's own decision changed. This produced a self-reinforcing "
        "loop: on release the raw ΔL and ΔR change immediately while the EMA remains at the "
        "pressed value for about τ = 1 s; the gate, observing that stale EMA, continues to "
        "report contact; and because its decision does not change, the reset condition is "
        "never triggered."), align="j")
    para(doc, L, t(
        "해결책은 게이트를 EMA 없는 2입력 구조로 되돌리는 것이었다. 접촉 여부는 본래 즉각적인 물리적 전환이므로 "
        "평활할 이유가 없고, 이렇게 하면 루프 자체가 성립하지 않는다. 아울러 펌웨어 실행 순서를 '게이트 먼저 → "
        "그 결과로 이번 사이클에 즉시 EMA 리셋 여부 결정 → 전문가 실행'으로 바꾸어 기존의 한 사이클 지연도 "
        "제거하였다. 회귀 정확도에 실제로 도움이 되는 전문가 A·B는 4입력을 유지하였다. 이 교체로 오프라인 게이트 "
        "정확도는 100.0 %에서 98.2 %로 낮아졌지만, 실기 동작은 정상화되었다. 오프라인 지표가 배포 조건에서 "
        "재현 불가능한 가정에 의존하고 있었다는 점에서, 이 사례는 임베디드 검증이 오프라인 평가를 대체할 수 없음을 "
        "보여준다.",
        "The remedy was to revert the gate to a two-input form without EMA features. Contact "
        "is an inherently instantaneous physical transition with no reason to be smoothed, and "
        "with this change the loop cannot form. The firmware execution order was also changed "
        "to gate first, then an immediate same-cycle decision on whether to reset the EMA, "
        "then the expert, removing the previous one-cycle delay. Experts A and B, where "
        "history genuinely helps regression, retained their four inputs. The substitution "
        "lowered offline gate accuracy from 100.0 % to 98.2 % but restored correct behaviour "
        "on hardware. Because the offline metric relied on an assumption that cannot be "
        "reproduced at deployment, this case shows that embedded validation cannot be replaced "
        "by offline evaluation."), align="j")

    # ── 8. 실시간 검증 ──────────────────────────────────────────────────────
    heading(doc, L, t("8. 실시간 검증", "8. Real-Time Validation"), 1)
    heading(doc, L, t("8.1 검증 프로토콜", "8.1 Validation Protocol"), 2)
    para(doc, L, t(
        "검증은 학습에 쓰인 세션과 별개로 수행한 세 개의 연속 세션(D5)에서 이루어졌다. 각 세션은 세 부분으로 "
        "구성된다. Part 1(0–398 s)에서는 변형률을 단계적으로 고정한 채 Z축을 25 mm에서 접촉까지 반복 왕복시키고, "
        "Part 2(400–730 s)에서는 근접거리를 고정한 채 변형률을 0–30 %로 반복 스윕하며, Part 3(738 s 이후)에서는 "
        "두 축을 동시에 움직인다. 이 구성은 각 축이 단독으로 변할 때와 동시에 변할 때의 성능을 분리해 관찰하기 "
        "위한 것이다. 보고하는 모든 수치는 보드가 UART로 내보낸 자체 추정값과 스테이지·F/T 센서의 참값을 "
        "비교한 것이며, PC에서 어떠한 후처리 추론도 수행하지 않았다.",
        "Validation was performed on three continuous sessions (D5) acquired separately from "
        "those used for training. Each session has three parts. In Part 1 (0–398 s) the strain "
        "is held at stepped values while the Z axis repeatedly travels between 25 mm and "
        "contact; in Part 2 (400–730 s) the distance is held fixed while the strain is swept "
        "repeatedly over 0–30 %; and in Part 3 (from 738 s) both axes move together. This "
        "structure isolates the performance when each axis varies alone from that when both "
        "vary. All reported figures compare the board's own estimates, streamed over UART, "
        "against stage and F/T ground truth; no post-hoc inference was performed on the PC."),
        align="j")
    figure(doc, L, "fig6_realtime.png", t(
        "그림 6. 실기 실시간 디커플링(세션 0819-153948, 809 s). (a) 보드가 1 kHz로 취득해 100 Hz로 로깅한 원시 "
        "TDM 신호. (b) 변형률: 회색이 참값, 주황이 보드 추정. (c) 근접거리: 게이트가 비접촉으로 판정한 구간만 "
        "표시. (d) 접촉력: 접촉 판정 구간만 표시. 점선은 Part 경계이다.",
        "Fig. 6. On-hardware real-time decoupling (session 0819-153948, 809 s). (a) Raw TDM "
        "signals acquired on the board at 1 kHz and logged at 100 Hz. (b) Strain: grey is "
        "ground truth, orange the on-board estimate. (c) Distance, shown only where the gate "
        "reports non-contact. (d) Contact force, shown only where the gate reports contact. "
        "Dotted lines mark the Part boundaries."))

    heading(doc, L, t("8.2 구간별 결과", "8.2 Part-Wise Results"), 2)
    para(doc, L, t(
        "그림 6과 표 4가 결과를 요약한다. Part 1에서는 세 물리량이 모두 잘 복원된다. 두 번째 세션 기준으로 "
        "변형률 R² = 0.981(RMSE 1.37 %p), 근접거리 R² = 0.940(RMSE 2.11 mm)이며, 게이트 정확도는 98.3 %였다. "
        "그림 7의 패리티 플롯에서 보듯 추정값이 대각선을 따라 분포한다. 접촉력은 세션에 따라 R² 0.430–0.777로 "
        "편차가 컸는데, 이는 두 번째 세션의 접촉 샘플 수가 2,185개로 적고 최대 힘이 7.8 N에 그쳐 분산이 작았던 "
        "영향이 크다.",
        "Figure 6 and Table 4 summarize the results. In Part 1 all three quantities are "
        "recovered well: in the second session, strain reached R² = 0.981 (RMSE 1.37 %p) and "
        "distance R² = 0.940 (RMSE 2.11 mm), with 98.3 % gate accuracy. The parity plots of "
        "Fig. 7 show the estimates distributed along the diagonal. Contact force varied more "
        "between sessions (R² = 0.430–0.777), largely because the second session contained "
        "only 2,185 contact samples with a maximum force of 7.8 N and therefore lower "
        "variance."), align="j")
    figure(doc, L, "fig7_parity.png", t(
        "그림 7. Part 1 구간의 패리티 플롯(세션 0819-153948). (a) 변형률, (b) 근접거리, (c) 접촉력. "
        "점선은 이상적 대각선이다.",
        "Fig. 7. Parity plots for Part 1 (session 0819-153948): (a) strain, (b) distance, "
        "(c) contact force. Dashed lines show the ideal diagonal."))
    table(doc, L,
          [t("구간", "Segment"), t("변형률 R² / RMSE", "Strain R² / RMSE"),
           t("근접거리 R² / RMSE", "Distance R² / RMSE"),
           t("접촉력 R² / RMSE", "Force R² / RMSE")],
          [[t("Part 1 — 근접만 변화", "Part 1 - proximity only"),
            "0.981 / 1.37 %p", "0.940 / 2.11 mm", "0.430 / 1.86 N"],
           [t("Part 2 — 인장만 변화", "Part 2 - strain only"),
            "0.492 / 6.97 %p", "−0.797 / 6.19 mm", "—"],
           [t("Part 3 — 동시 변화", "Part 3 - simultaneous"),
            "0.602 / 6.27 %p", "−2.051 / 10.40 mm", "—"],
           [t("전체(참고)", "Whole session (reference)"),
            "0.780 / 4.78 %p", "0.488 / 5.59 mm", "0.430 / 1.86 N"]],
          caption=t("표 4. 실기 실시간 성능(세션 0819-153948). 각 Part는 상대 축이 실제로 움직인 순간을 "
                    "±1 s 여유를 두고 제외한 순수 구간 기준이다. 게이트 정확도 98.3 %.",
                    "Table 4. On-hardware real-time performance (session 0819-153948). Each "
                    "Part excludes, with a ±1 s guard band, the instants at which the other "
                    "axis was actually moving. Gate accuracy 98.3 %."),
          widths=[4.6, 4.0, 4.0, 3.2])

    heading(doc, L, t("8.3 준정적 구간의 성능 저하와 원인",
                      "8.3 Degradation in Quasi-Static Segments and Its Cause"), 2)
    para(doc, L, t(
        "Part 2와 Part 3에서 근접거리 추정의 R²가 음수로 떨어졌다. 음수 R²는 예측이 단순 평균보다 못하다는 "
        "뜻이므로 그대로 보고할 필요가 있다. 다만 이 구간에서 근접거리는 사실상 고정되어 있어 정답의 분산 "
        "자체가 매우 작다. R² = 1 − RMSE²/Var(y)이므로 분모가 작으면 절대 오차가 작아도 R²가 크게 나빠진다. "
        "실제로 Part 2의 근접 RMSE는 6.19 mm로, Part 1의 2.11 mm보다 3배가량 큰 데 그친다. 그럼에도 이 "
        "저하는 실재하며, 근접 신호가 준정적일 때 인덕턴스에 남는 정보가 잡음 수준으로 줄어든다는 사실을 "
        "보여준다.",
        "In Parts 2 and 3 the R² of the distance estimate became negative. A negative R² means "
        "the prediction is worse than the mean and must be reported as such. In these "
        "segments, however, the distance is essentially fixed, so the variance of the ground "
        "truth is very small. Since R² = 1 − RMSE²/Var(y), a small denominator degrades R² "
        "sharply even when the absolute error is modest: the distance RMSE in Part 2 was "
        "6.19 mm, only about three times the 2.11 mm of Part 1. The degradation is "
        "nonetheless real and shows that, when the proximity signal is quasi-static, the "
        "information remaining in the inductance falls to the noise level."), align="j")
    para(doc, L, t(
        "원인을 좁히기 위해 동일한 원시 ΔL·ΔR을 PC에서 float64로 재현하여 같은 게이트·EMA·라우팅 논리를 "
        "적용해 보았다. 게이트 판단은 임베디드와 100 % 일치했으므로 분류 단계는 원인이 아니다. 반면 회귀 "
        "단계에서는 PC 재현이 Part 2 근접 R²를 −0.797에서 0.225로, Part 3을 −2.051에서 −0.230으로 개선했다. "
        "sklearn과 ONNX의 수치 검증 오차가 1e−5 수준이므로 부동소수점 정밀도만으로는 이 격차를 설명할 수 없다. "
        "가장 유력한 원인은 EMA 재구성 방식의 차이다. 보드는 1 ms마다 들어오는 모든 원시 샘플로 EMA를 갱신하므로 "
        "그 사이의 잡음까지 전부 반영하는 반면, PC 재현은 로깅 과정에서 5분의 1로 데시메이션된 값만 보고 "
        "연속시간 근사식으로 그 사이를 매끄럽게 건너뛴다. 실제 신호가 잡음보다 훨씬 큰 Part 1에서는 두 방식의 "
        "차이가 묻히지만, 신호가 거의 없는 Part 2·3에서는 PC 쪽이 인위적으로 더 안정적으로 보이게 된다. 이는 "
        "PC가 물리적으로 더 정확하다는 뜻이 아니라, 잡음이 지배하는 구간에서 평활의 정도가 지표에 그대로 "
        "반영된다는 뜻이다.",
        "To narrow the cause, the same raw ΔL and ΔR were replayed on a PC in float64 with "
        "identical gate, EMA and routing logic. Gate decisions matched the embedded ones "
        "100 %, so the classification stage is not responsible. In the regression stage, "
        "however, the PC replay improved the Part 2 distance R² from −0.797 to 0.225 and Part "
        "3 from −2.051 to −0.230. Since scikit-learn and ONNX agree to about 1e-5, "
        "floating-point precision alone cannot explain the gap. The most plausible cause is a "
        "difference in how the EMA is reconstructed: the board updates the EMA from every raw "
        "sample arriving each millisecond and therefore absorbs all the noise in between, "
        "whereas the PC replay sees only values decimated by a factor of five during logging "
        "and interpolates smoothly across the gaps with a continuous-time approximation. Where "
        "the true signal greatly exceeds the noise (Part 1) the difference is masked; where "
        "there is almost no signal (Parts 2 and 3) the PC appears artificially more stable. "
        "This does not mean the PC is physically more accurate — it means that, in "
        "noise-dominated segments, the degree of smoothing propagates directly into the "
        "metric."), align="j")

    # ── 9. 논의 ─────────────────────────────────────────────────────────────
    heading(doc, L, t("9. 논의", "9. Discussion"), 1)
    para(doc, L, t(
        "본 연구의 결과는 단일 전극 멀티모달 센싱에서 무엇이 이미 가능하고 무엇이 아직 한계인지를 비교적 "
        "분명하게 나눈다. 가능한 것부터 정리하면 다음과 같다. 첫째, 두 가닥 배선만으로 세 신호를 1 kHz로 "
        "취득하는 것은 상용 부품과 6층 기판으로 충분히 구현 가능하며, DMA 기반 ISR 설계로 CPU 부담을 6 % 미만으로 "
        "유지할 수 있다. 둘째, 도체 표적에 대해서는 R–ε 단독 의존성이라는 물리적 비대칭이 실제로 성립하며, 이를 "
        "모델 구조에 반영하면 동일 파라미터 예산에서 종단 모델보다 우수하다. 셋째, 1,413 파라미터 규모의 모델로도 "
        "세 물리량을 동시에 추정할 수 있고, 이 정도 크기는 캐시에 상주하므로 260 µs라는 결정론적 지연을 얻는다. "
        "PC 기반 구성에서 발생하는 20–40 ms의 왕복 지연과 ±5–15 ms 지터를 제거한다는 점에서, 이 시스템에서 엣지 "
        "추론은 선택이 아니라 요건이다.",
        "The results delineate fairly clearly what is already achievable in single-electrode "
        "multimodal sensing and what remains limited. On the achievable side: first, acquiring "
        "three signals at 1 kHz through only two wires is entirely feasible with commercial "
        "components on a six-layer board, and a DMA-based ISR design keeps the CPU load below "
        "6 %. Second, for conductive targets the physical asymmetry of strain-only dependence "
        "in R genuinely holds, and encoding it in the architecture outperforms an end-to-end "
        "model at equal parameter budget. Third, a model of only 1,413 parameters suffices to "
        "estimate three quantities simultaneously, and at that size the weights stay resident "
        "in cache, yielding a deterministic 260 µs latency. Because this removes the 20–40 ms "
        "round trip and ±5–15 ms jitter of a PC-based arrangement, edge inference is a "
        "requirement rather than an option for this system."), align="j")
    para(doc, L, t(
        "한계도 분명하다. 첫째, 근접 추정은 표적이 도체일 때만 실용적이다. 그림 2c에서 확인했듯 유전체 표적에서는 "
        "인덕턴스에 실리는 근접 정보가 미약하다. 둘째, 근접거리가 준정적인 구간에서 성능이 크게 저하된다(8.3절). "
        "이는 모델의 결함이라기보다 단일 채널에 실린 정보량의 한계에 가깝다. 셋째, 접촉력 추정 정확도는 정답으로 "
        "사용한 F/T 센서의 잡음(±0.19 N)에 근접해 있어, 이보다 낮은 오차를 주장하려면 더 정밀한 기준 계측이 "
        "선행되어야 한다. 넷째, TENG 채널은 취득만 하고 디커플러 입력으로 사용하지 않았다. 접촉 이벤트 검출은 "
        "게이트가 ΔL·ΔR만으로 98 % 이상 해내므로 현재로서는 TENG의 추가 가치가 확인되지 않았으나, 미세 접촉이나 "
        "동적 텍스처 인식에서는 유용할 수 있다.",
        "The limitations are equally clear. First, proximity estimation is practical only for "
        "conductive targets; as Fig. 2c shows, a dielectric target imprints little proximity "
        "information on the inductance. Second, performance degrades substantially where the "
        "distance is quasi-static (Section 8.3) — less a defect of the model than a limit on "
        "the information carried by a single channel. Third, the accuracy of the force "
        "estimate approaches the ±0.19 N noise of the F/T sensor used as ground truth, so "
        "claiming lower error would require more precise reference instrumentation first. "
        "Fourth, the TENG channel was acquired but not used as a decoupler input: since the "
        "gate already detects contact events with over 98 % accuracy from ΔL and ΔR alone, no "
        "additional value from TENG has yet been demonstrated, although it may prove useful "
        "for light touch or dynamic texture recognition."), align="j")
    para(doc, L, t(
        "향후 방향은 세 가지다. (i) 다중 주파수 임피던스 측정. 현재는 LDC1614의 단일 공진 주파수만 사용하지만, "
        "여러 주파수에서 임피던스의 실수부·허수부를 얻으면 재질 구분과 근접 추정을 동시에 개선할 수 있고, "
        "8.3절의 준정적 구간 문제도 추가 채널로 완화될 여지가 있다. (ii) 2차원 변형 분해. 직사각형 나선 코일은 "
        "x축과 y축에 대해 비대칭 감도를 가지므로, L과 R이 서로 다른 유효 고유 방향을 갖는다는 점을 이용하면 단일 "
        "전극에서 2축 변형을 분리할 수 있을 것으로 예상된다. 이를 위해서는 x/y를 독립 구동하는 시험 플랫폼 "
        "개조가 선행되어야 한다. (iii) 순환 구조로의 전환. 표 2에서 GRU는 EMA 기반 모델과 동등한 정확도를 "
        "306 파라미터로 달성했다. X-CUBE-AI의 순환 레이어 지원과 은닉 상태 리셋 논리, 양자화 안정성을 이 "
        "보드에서 검증하는 것이 다음 과제다.",
        "Three directions follow. (i) Multi-frequency impedance measurement. Only the single "
        "resonant frequency of the LDC1614 is used at present; obtaining the real and "
        "imaginary parts of the impedance at several frequencies could improve material "
        "discrimination and proximity estimation together, and the extra channels may also "
        "mitigate the quasi-static problem of Section 8.3. (ii) Two-dimensional strain "
        "decomposition. A rectangular spiral has asymmetric sensitivity along its x and y "
        "axes, so the fact that L and R possess different effective eigen-directions should "
        "permit biaxial strain to be separated from a single electrode; this requires the test "
        "platform to be modified for independent x/y actuation. (iii) Migration to a recurrent "
        "structure. In Table 2 the GRU matched the EMA-based models with 306 parameters; "
        "verifying X-CUBE-AI's recurrent-layer support, hidden-state reset logic and "
        "quantization stability on this board is the next task."), align="j")

    # ── 10. 결론 ────────────────────────────────────────────────────────────
    heading(doc, L, t("10. 결론", "10. Conclusion"), 1)
    para(doc, L, t(
        "두 가닥 단일 전극 EGaIn 나선 코일에서 시분할 측정으로 인덕턴스·저항·마찰전기 전압을 1 ms 주기로 "
        "취득하고, 이를 임베디드 AI로 실시간 디커플링하는 멀티모달 센싱 시스템을 설계·제작·검증하였다. 도체 "
        "표적에 대한 격자 측정으로 저항이 변형률에만 의존하고 인덕턴스가 변형률과 근접거리에 함께 의존한다는 "
        "물리적 비대칭을 정량적으로 확인하였고, 접촉 모달리티에서는 표준선형고체 모델로 점탄성 완화(τ ≈ 1.0 s)를 "
        "규명하여 이를 인과적 EMA 이력 피처로 반영하였다. 최종 디커플러는 1,413 파라미터의 Mixture-of-Experts "
        "구조로, STM32G473 위에서 매 TDM 주기마다 중앙값 260 µs 만에 추론을 완료한다. 근접이 실제로 변하는 "
        "구간에서 실기 성능은 변형률 R² = 0.981, 근접거리 R² = 0.940, 게이트 정확도 98 %였으며, 근접이 "
        "준정적인 구간에서는 신호 대 잡음비 한계로 성능이 저하됨을 함께 보고하였다. 본 연구는 단일 전극 "
        "멀티모달 센서가 PC 없이 자율적으로 동작할 수 있음을 실기로 보였으며, 동시에 오프라인 지표만으로는 "
        "임베디드 성능을 담보할 수 없다는 점을 구체적 실패 사례와 함께 제시하였다.",
        "A multimodal sensing system was designed, built and validated in which inductance, "
        "resistance and triboelectric voltage are acquired every millisecond by time-division "
        "measurement from a two-wire single-electrode EGaIn spiral coil and decoupled in real "
        "time by embedded AI. Gridded measurements against a conductive target quantitatively "
        "confirmed the physical asymmetry whereby resistance depends on strain alone while "
        "inductance depends on both strain and distance; in the contact regime, a standard "
        "linear solid model identified a viscoelastic relaxation (τ = 1.0 s) that was "
        "encoded as a causal EMA history feature. The final decoupler is a 1,413-parameter "
        "mixture-of-experts network that completes inference on the STM32G473 in a median of "
        "260 µs once per TDM cycle. Where the proximity axis actually moved, on-hardware "
        "accuracy reached R² = 0.981 for strain and R² = 0.940 for distance with 98 % gate "
        "accuracy; degradation in quasi-static proximity segments, caused by the "
        "signal-to-noise limit, is reported alongside. The work demonstrates on real hardware "
        "that a single-electrode multimodal sensor can operate autonomously without a host PC, "
        "and shows through a concrete failure case that offline metrics alone cannot guarantee "
        "embedded performance."), align="j")

    # ── 참고문헌 ────────────────────────────────────────────────────────────
    heading(doc, L, t("참고문헌", "References"), 1)
    para(doc, L, t(
        "주의: 아래 목록은 본 연구 과정에서 실제로 참조한 자료이며, 권·호·페이지 등 서지 정보는 투고 전 "
        "원문으로 확인·보완해야 한다.",
        "Note: the following list records the sources actually consulted during this work; "
        "volume, issue and page details must be verified against the originals before "
        "submission."), size=8.5, italic=True)
    refs = [
        "M. Raissi, P. Perdikaris, and G. E. Karniadakis, “Physics-informed neural "
        "networks: A deep learning framework for solving forward and inverse problems "
        "involving nonlinear partial differential equations,” Journal of Computational "
        "Physics, vol. 378, pp. 686–707, 2019.",
        "Wang et al., “Programming stretchable planar coils,” Materials Today "
        "Physics, 2025.",
        "Li et al., “Fingertip-inspired spatially anisotropic inductive liquid metal "
        "sensors,” Advanced Materials, 2025.",
        "“Recent progress on flexible multimodal sensors: decoupling strategies,” "
        "Advanced Materials, 2026.",
        "Texas Instruments, LDC1612/LDC1614 Multi-Channel 28-Bit Inductance-to-Digital "
        "Converter, datasheet.",
        "Analog Devices, ADG733/ADG734 CMOS Low Voltage Triple/Quad SPDT Switches, datasheet.",
        "STMicroelectronics, STM32G473xB/xC/xE Datasheet and RM0440 Reference Manual.",
        "STMicroelectronics, X-CUBE-AI: Artificial Intelligence Expansion Package for "
        "STM32Cube, User Manual UM2526.",
        "F. Pedregosa et al., “Scikit-learn: Machine learning in Python,” Journal of "
        "Machine Learning Research, vol. 12, pp. 2825–2830, 2011.",
        "R. A. Jacobs, M. I. Jordan, S. J. Nowlan, and G. E. Hinton, “Adaptive mixtures "
        "of local experts,” Neural Computation, vol. 3, no. 1, pp. 79–87, 1991.",
        "R. M. Christensen, Theory of Viscoelasticity: An Introduction, 2nd ed. Academic "
        "Press, 1982.",
    ]
    for i, r in enumerate(refs, 1):
        para(doc, L, "[%d] %s" % (i, r), size=9, space_after=3)
