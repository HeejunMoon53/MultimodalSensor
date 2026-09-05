# -*- coding: utf-8 -*-
"""Paper/content.py — 논문 본문(국문/영문 동시 정의).

근거 자료: 저장소 실측 데이터(JSON/CSV) + 26.03.27 세미나 자료 + 26.08.20 그룹미팅 자료.
"""
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
        "액체금속을 직접 잉크 라이팅(DIW)으로 인쇄한 평면 직사각형 나선 코일 하나를, 두 가닥의 단일 전극만으로 "
        "인덕턴스 L, DC 저항 R, 마찰전기(TENG) 전압 V의 세 신호원으로 동시에 사용하는 측정 구조를 제안한다. "
        "코일 내부 단자를 권선 위로 넘겨 빼내는 브리징 공정이 나선 구조를 두 가닥 배선으로 완결시키며, "
        "STM32G473CBT6 마이크로컨트롤러에서 TIM7 인터럽트로 구동되는 1 ms 주기 시분할 측정(TDM, Time-Division "
        "Measurement) 스케줄이 아날로그 멀티플렉서를 통해 동일 코일에 AC 여기·DC 여기·무여기 상태를 순차 "
        "인가한다. I²C DMA와 ADC DMA를 병렬 실행하여 1 kHz 취득률을 유지하며 CPU 유휴율은 93.9 %이다. "
        "도체(금속)·유전체(손) 두 표적에 대해 인장 0–30 %와 근접 0–52 mm의 2차원 공간을 격자 측정한 결과, "
        "ΔR/R₀는 근접거리와 무관하게 인장에만 단조 의존하고 ΔL/L₀는 인장과 근접에 동시에 의존하는 비대칭이 "
        "정량적으로 확인되었으며, 이 비대칭이 디커플링의 물리적 근거가 된다. 접촉 모달리티 추가를 위해 직경 "
        "5 mm·높이 0.5 mm의 돌기 구조를 도입하여 ΔR/R₀ 100 %에 필요한 하중을 210 N에서 20 N으로 낮췄다. 접촉 "
        "영역에서는 점탄성 히스테리시스·크립과 인장×접촉력 교차 민감도가 새로 나타났고, 표준선형고체(SLS) "
        "모델로 시간상수 τ ≈ 1.0 s를 실측하여 인과적 지수이동평균(EMA) 이력 피처로 반영하였다. 압축 시 "
        "인덕턴스가 증가하는 것처럼 보이는 현상은 Q-factor 저하에 따른 근사 공진식 역산의 겉보기 효과임을 "
        "규명하였다. 최종 디커플러는 접촉 여부를 판정하는 게이트와 비접촉·접촉 전용 두 전문가로 구성된 "
        "SLS-EMA + Gate-MoE 구조로, 총 1,413개 파라미터에 불과하며 X-CUBE-AI를 통해 MCU에 임베딩되었다. 보드 "
        "단독으로 매 TDM 주기마다 추론이 수행되고 실측 지연은 중앙값 260 µs(95 백분위수 263 µs)로 1 ms 주기 "
        "안에서 완결된다. 근접이 실제로 변하는 구간에서 실기 성능은 인장 R² = 0.981(RMSE 1.37 %p), 근접거리 "
        "R² = 0.940(RMSE 2.11 mm), 접촉력 RMSE 1.80 N이었고 게이트 정확도는 98–99 %였다. 반면 근접이 준정적인 "
        "구간에서는 근접 추정의 신호 대 잡음비가 무너져 R²가 음수로 떨어졌는데, 이는 오프라인 held-out 평가만"
        "으로는 드러나지 않는 실기 고유의 한계로서 그대로 보고한다. 본 연구는 PC 연결 없이 동작하는 단일 전극 "
        "멀티모달 센싱 시스템의 설계·제작·데이터 취득·모델링·임베디드 배포 전 과정을 하나의 파이프라인으로 "
        "제시한다.",

        "Flexible multimodal sensors suffer from signal coupling: several physical "
        "stimuli are superimposed on the same electrical readout, which makes "
        "independent measurement of each stimulus difficult. This work proposes a "
        "measurement architecture in which a single planar rectangular spiral coil, "
        "printed from eutectic gallium-indium (EGaIn) liquid metal by direct ink writing "
        "(DIW) and connected through only two wires, serves simultaneously as three "
        "signal sources: inductance L, DC resistance R, and triboelectric (TENG) voltage "
        "V. A bridging step that routes the inner terminal out over the windings is what "
        "completes the spiral as a two-wire structure. A 1 ms time-division measurement "
        "(TDM) schedule, driven by a TIM7 interrupt on an STM32G473CBT6 microcontroller, "
        "applies AC excitation, DC excitation and no excitation to the same coil in "
        "sequence through an analog multiplexer. I²C DMA and ADC DMA run in parallel, "
        "sustaining a 1 kHz acquisition rate at 93.9 % CPU idle. Gridded measurements "
        "over 0–30 % strain and 0–52 mm proximity, for both a conductive (metal) and a "
        "dielectric (hand) target, quantitatively confirm an asymmetry: ΔR/R₀ depends "
        "monotonically on strain alone and is essentially independent of proximity, "
        "whereas ΔL/L₀ depends on both. This asymmetry is the physical basis for "
        "decoupling. To add the contact modality, a bump array 5 mm in diameter and "
        "0.5 mm high reduced the load required for a 100 % ΔR/R₀ response from 210 N to "
        "20 N. In the contact regime, viscoelastic hysteresis and creep appeared together "
        "with a strain-force cross-sensitivity; a standard linear solid (SLS) model fitted "
        "to the measured dwell relaxation gave a time constant τ ≈ 1.0 s, encoded as a "
        "causal exponential-moving-average (EMA) history feature. The apparent increase of "
        "inductance under compression is shown to be an artefact of inverting an "
        "approximate resonance expression while the Q factor falls. The final decoupler, "
        "an SLS-EMA + Gate-MoE network comprising a contact gate and two mode-specific "
        "experts, totals only 1,413 parameters and was embedded on the MCU through "
        "X-CUBE-AI. Inference runs on the board once per TDM cycle with a measured median "
        "latency of 260 µs (95th percentile 263 µs), completing inside the 1 ms period. "
        "Where the proximity axis actually moved, on-hardware accuracy reached R² = 0.981 "
        "(RMSE 1.37 %p) for strain, R² = 0.940 (RMSE 2.11 mm) for distance and 1.80 N RMSE "
        "for contact force, with 98–99 % gate accuracy. In quasi-static proximity "
        "segments, by contrast, the signal-to-noise ratio of the distance estimate "
        "collapsed and R² became negative; this hardware-specific limitation, invisible to "
        "offline held-out evaluation, is reported as measured. The study presents the "
        "complete pipeline — design, fabrication, data acquisition, modelling and embedded "
        "deployment — of a single-electrode multimodal sensing system that operates "
        "without a host PC."),
        size=9.5, align="j")

    para(doc, L, t(
        "핵심어 — 소프트 센서, 액체금속(EGaIn), 단일 전극, 멀티모달 센싱, 신호 디커플링, 시분할 측정(TDM), "
        "Mixture-of-Experts, 점탄성, 엣지 AI, STM32",
        "Index Terms — Soft sensor, liquid metal (EGaIn), single electrode, multimodal "
        "sensing, signal decoupling, time-division measurement, mixture of experts, "
        "viscoelasticity, edge AI, STM32"),
        size=9, italic=True, space_before=6, space_after=12)

    # ── 1. 서론 (intro.py 로 분리) ──────────────────────────────────────────
    import intro
    intro.build(doc, L)

    # ── 2. 센서 설계 ────────────────────────────────────────────────────────
    heading(doc, L, t("2. 센서 설계와 물리적 원리", "2. Sensor Design and Physical Principles"), 1)
    heading(doc, L, t("2.1 단일 전극 EGaIn 나선 코일과 제작 공정",
                      "2.1 Single-Electrode EGaIn Spiral Coil and Fabrication"), 2)
    para(doc, L, t(
        "센서 전극은 EGaIn 액체금속을 일래스토머 기판 위에 DIW(Direct Ink Writing)로 인쇄한 평면 직사각형 "
        "나선 코일이다(그림 1a). 액체금속은 대변형에서도 도전 경로가 끊기지 않아 30 % 인장까지 반복 사용이 "
        "가능하며, 코일 형상 덕분에 하나의 도전 트레이스가 저항 소자와 인덕터 역할을 동시에 수행한다. 센서의 "
        "초기 유효 길이는 120 mm이고, 인장 시험은 0–36 mm(변형률 0–30 %) 범위에서 수행하였다.",
        "The sensing electrode is a planar rectangular spiral coil printed from EGaIn "
        "liquid metal onto an elastomer substrate by direct ink writing (DIW) (Fig. 1a). "
        "The liquid metal maintains a continuous conductive path under large deformation, "
        "permitting repeated use up to 30 % strain, and the coil geometry lets a single "
        "conductive trace act simultaneously as a resistive element and an inductor. The "
        "initial effective length of the sensor is 120 mm, and tensile tests were performed "
        "over 0–36 mm of elongation (0–30 % strain)."), align="j")
    para(doc, L, t(
        "제작은 네 단계로 이루어진다(그림 1b). ① EGaIn DIW — 노즐로 액체금속을 압출하여 나선 채널을 "
        "인쇄한다. ② 브리징 — 나선의 안쪽 끝 단자를 권선 위로 넘겨 바깥으로 빼낸다. 이 단계가 본 센서를 진정한 "
        "두 가닥 단일 전극으로 만드는 핵심이다. 브리징이 없으면 나선의 내부 단자에 접근할 수 없어 별도의 관통 "
        "배선이나 대향 전극이 필요해지고, 그 순간 평면성과 신축성이 훼손된다. ③ 커버링 — 어플리케이터로 "
        "일래스토머를 도포해 채널을 밀봉한다. ④ 배선 삽입 및 재단 — 리드선을 삽입하고 시편을 십자형 외형으로 "
        "재단한다. 십자형 외형은 4축 대칭 인장 시 코일 중심이 이동하지 않도록 하며, 향후 2축 변형 측정으로 "
        "확장할 때 x/y 독립 구동을 가능하게 한다.",
        "Fabrication proceeds in four steps (Fig. 1b). (i) EGaIn DIW — liquid metal is "
        "extruded through a nozzle to print the spiral channel. (ii) Bridging — the inner "
        "terminal of the spiral is routed out over the windings. This step is what makes "
        "the device a true two-wire single electrode: without it the inner terminal cannot "
        "be reached without a through-connection or a counter electrode, which would "
        "immediately compromise planarity and stretchability. (iii) Covering — an "
        "elastomer is applied to seal the channel. (iv) Wire insertion and cutting — lead "
        "wires are inserted and the specimen is cut to a cruciform outline. The cruciform "
        "shape keeps the coil centre stationary under four-axis symmetric tension and "
        "enables independent x/y actuation for the planned extension to biaxial strain "
        "sensing."), align="j")
    para(doc, L, t(
        "접촉 모달리티를 추가하는 단계에서 압력 민감도를 높이기 위해 센서 표면에 돌기 구조를 도입하였다. 필름 "
        "마스킹과 어플리케이터를 이용해 직경 5 mm, 높이 0.5 mm의 균일한 돌기를 배열하였다. 돌기는 접촉 하중을 "
        "국소 지점에 집중시켜 도전 채널의 단면적 변화를 증폭한다. 도입 전에는 ΔR/R₀가 100 %에 도달하는 데 약 "
        "210 N이 필요했으나 도입 후에는 약 20 N으로 낮아져, 실용 하중 범위에서 약 10배의 민감도 이득을 얻었다.",
        "When the contact modality was added, a bump array was introduced on the sensor "
        "surface to raise the pressure sensitivity. Using film masking and an applicator, "
        "uniform bumps 5 mm in diameter and 0.5 mm high were arrayed. The bumps concentrate "
        "the contact load at local points and thereby amplify the change in cross-section "
        "of the conductive channel. Before their introduction, reaching a 100 % ΔR/R₀ "
        "response required about 210 N; afterwards about 20 N sufficed, a roughly tenfold "
        "sensitivity gain within a practical load range."), align="j")
    figure(doc, L, "fig0_sensor.png", t(
        "그림 1. 센서 설계 개요. (a) 평면 직사각형 나선 코일의 기하 — 짧은 변 a, 긴 변 b, 액체금속 채널 반경 r, "
        "표적까지의 거리 d, 표적의 등가 인덕턴스·저항 L_t, R_t. (b) 네 단계 제작 공정. 브리징이 나선을 두 가닥 "
        "단일 전극으로 완결시킨다. (c) 자극별 응답 시그니처. * 표시는 압축 시 실제 L은 감소하지만 Q-factor "
        "저하 때문에 근사 역산 결과가 증가로 나타남을 뜻한다(5.2절).",
        "Fig. 1. Sensor design overview. (a) Geometry of the planar rectangular spiral: "
        "short side a, long side b, liquid-metal channel radius r, target distance d, and "
        "the equivalent target inductance and resistance L_t, R_t. (b) The four-step "
        "fabrication process; bridging is what completes the spiral as a two-wire single "
        "electrode. (c) Response signature of each stimulus. The asterisk indicates that "
        "under compression the true L decreases while the approximate inversion reports an "
        "increase because the Q factor falls (Section 5.2)."))

    heading(doc, L, t("2.2 전자기적 특성과 신호 생성 기구",
                      "2.2 Electromagnetic Characteristics and Signal Generation"), 2)
    para(doc, L, t(
        "동일한 코일에서 서로 다른 물리 기구로 세 신호가 생성된다. DC 저항은 도선의 기하에만 의존한다. 길이가 "
        "(1+ε)배로 늘고 단면적이 그에 반비례해 줄면 저항은 다음과 같이 변한다.",
        "Three signals are generated from the same coil through distinct mechanisms. The DC "
        "resistance depends only on the conductor geometry: when the length increases by a "
        "factor (1+ε) and the cross-section decreases inversely, the resistance follows"),
        align="j")
    eq(doc, L, "R_DC(ε) = R_DC,0 · (1 + ε)²")
    para(doc, L, t(
        "자기 인덕턴스는 직사각형 평면 나선에 대한 Rosa 계열의 부분 인덕턴스 식으로 기술되며, 권선 면적 A, "
        "종횡비 t = b/a, 채널 반경 r이 인장에 따라 각각 다른 지수로 변한다.",
        "The self-inductance is described by a Rosa-type partial-inductance expression for "
        "a rectangular planar spiral, in which the turn area A, the aspect ratio t = b/a "
        "and the channel radius r each scale with strain under a different exponent."),
        align="j")
    eq(doc, L, "A(ε) = A₀(1+ε)^0.5,   t(ε) = t₀(1+ε)^1.5,   r(ε) = r₀(1+ε)^(−0.5)")
    para(doc, L, t(
        "표적이 접근하면 코일과 표적 사이의 상호 인덕턴스 M(ε, d)를 통해 반사 임피던스가 나타나[22], [23], 실효 "
        "인덕턴스와 AC 등가 직렬 저항이 다음과 같이 변한다.",
        "When a target approaches, a reflected impedance appears through the mutual "
        "inductance M(ε, d) between coil and target [22], [23], modifying the effective inductance and "
        "the AC equivalent series resistance as"), align="j")
    eq(doc, L, "L(ε, d) = L_self(ε) − ω²M(ε,d)²·L_t / (R_t² + ω²L_t²)")
    eq(doc, L, "R_s(ε, d) = R_DC(ε) + ω²M(ε,d)²·R_t / (R_t² + ω²L_t²)")
    para(doc, L, t(
        "이로부터 그림 1c의 응답 시그니처가 도출된다. 인장은 L, R_s, R_DC를 모두 증가시킨다. 도체가 접근하면 "
        "와전류 손실에 의해 L은 감소하고 R_s는 증가하지만 R_DC는 변하지 않는다. 유전체가 접근하면 유전율 변화와 "
        "전기장 재분포로 L이 오히려 증가한다. 대전된 물체가 접촉하면 마찰전기 전하 이동으로 V_TENG에 피크가 "
        "발생한다. 도체와 유전체에서 ΔL의 부호가 반대라는 점은 단순한 방해 요인이 아니라, 향후 물체의 전기적 "
        "성질을 식별하는 데 쓸 수 있는 정보다(9절).",
        "These relations yield the response signature of Fig. 1c. Stretching increases L, "
        "R_s and R_DC together. An approaching conductor decreases L and increases R_s "
        "through eddy-current loss while leaving R_DC unchanged. An approaching dielectric "
        "instead increases L through the change in permittivity and the redistribution of "
        "the electric field. Contact by a charged body produces a peak in V_TENG through "
        "triboelectric charge transfer. That ΔL has opposite signs for conductors and "
        "dielectrics is not merely a nuisance: it is information that can be used to "
        "identify the electrical property of an object (Section 9)."), align="j")
    para(doc, L, t(
        "인덕턴스는 LDC1614가 측정하는 LC 탱크의 공진 주파수 f로부터 환산한다. f ∝ 1/√L 이므로 기준 상태 대비 "
        "상대 변화는 다음과 같이 계산된다.",
        "The inductance is derived from the resonant frequency f of the LC tank measured by "
        "the LDC1614. Since f is proportional to 1/√L, the relative change with respect to "
        "a reference state is computed as"), align="j")
    eq(doc, L, "ΔL/L₀ = (f₀ / f)² − 1,    ΔR/R₀ = (r − r₀) / r₀")
    para(doc, L, t(
        "여기서 f₀, r₀은 무변형·최대 이격 조건에서 세션별로 취한 중앙값 기준선이다. 기준선을 세션마다 다시 "
        "잡는 이유는 액체금속 센서의 초기 저항이 재장착·온도에 따라 수 % 수준에서 달라지기 때문이다.",
        "Here f₀ and r₀ are session-wise median baselines taken in the undeformed, "
        "maximum-separation condition. Baselines are re-estimated for each session because "
        "the initial resistance of a liquid-metal sensor varies by a few percent with "
        "remounting and temperature."), align="j")

    heading(doc, L, t("2.3 결합 구조와 해석적 역산의 한계",
                      "2.3 Coupling Structure and Limits of Analytical Inversion"), 2)
    para(doc, L, t(
        "위 이론식은 상호 인덕턴스 M(ε, d)의 해석적 형태를 요구하므로, 실용적으로는 다음의 경험적 피팅 모델을 "
        "사용한다.",
        "The theoretical expressions above require an analytical form for the mutual "
        "inductance M(ε, d); in practice the following empirical fitting model is used "
        "instead."), align="j")
    eq(doc, L, "ΔR/R₀ = α₁ε + α₂ε²,    ΔL/L₀ = β₁ε + β₂/(d+d₀)^k + β₃·ε·f(d)")
    para(doc, L, t(
        "두 물리량을 신호로부터 되찾으려면 이 관계를 역산해야 한다. 미소 변화에 대해 선형화하면 야코비안 J로 "
        "표현되고, 역산은 J의 역행렬로 주어진다.",
        "Recovering the two physical quantities from the signals requires inverting these "
        "relations. Linearizing for small changes gives a Jacobian J, and the inversion is "
        "its matrix inverse."), align="j")
    eq(doc, L, "[ΔR, ΔL]ᵀ = J · [Δε, Δd]ᵀ,    [ε, d]ᵀ = [ε₀, d₀]ᵀ + J⁻¹ · [ΔR, ΔL]ᵀ")
    para(doc, L, t(
        "이 접근은 두 가지 이유로 실패한다. 첫째, 절단 오차다. 근거리에서는 M² 항이, 대변형에서는 sinh⁻¹와 "
        "ln 항이 지배하는 강한 비선형 영역이므로 선형 근사가 국소적으로만 유효하다. 둘째, 특이점과 직교성 "
        "상실이다. ∇R과 ∇L의 방향이 가까워지면 det(J) → 0이 되어 J⁻¹이 발산하고, 작은 측정 잡음이 크게 "
        "증폭된다. 실제로 접촉 영역에서 교차항을 포함한 물리식을 직접 역산했을 때 결정계수는 0.26에 그쳤고, "
        "품질이 낮은 데이터가 섞이면 변형률 0 근처에서 R² = −75까지 발산하였다(부록 S4). 반면 5.1절에서 "
        "보이듯 ∇L과 ∇R은 전역적으로는 선형 독립이므로 정보 자체는 존재한다. 즉 문제는 정보의 부재가 아니라 "
        "역산 방법에 있으며, 이것이 순방향 연산만 수행하여 특이점이 원리적으로 발생하지 않고 O(1) 지연으로 "
        "동작하는 학습 기반 디커플러를 채택한 이유다.",
        "This approach fails for two reasons. First, truncation error: the near field is "
        "dominated by the M² term and large strain by sinh⁻¹ and ln terms, so the linear "
        "approximation is valid only locally. Second, singularity and loss of "
        "orthogonality: as the directions of ∇R and ∇L converge, det(J) approaches zero, "
        "J⁻¹ diverges and small measurement noise is greatly amplified. In practice, direct "
        "inversion of the physics expression including the cross term in the contact regime "
        "reached a coefficient of determination of only 0.26, and diverged to R² = −75 near "
        "zero strain when lower-quality data were included (Appendix S4). As Section 5.1 "
        "shows, however, ∇L and ∇R are globally linearly independent, so the information "
        "itself is present. The problem lies in the inversion method rather than in missing "
        "information, which is why a learned decoupler was adopted: it performs only "
        "forward operations, so singularities cannot arise in principle, and it runs with "
        "O(1) latency."), align="j")

    # ── 3. 측정 시스템 ──────────────────────────────────────────────────────
    heading(doc, L, t("3. 측정 시스템", "3. Measurement System"), 1)
    heading(doc, L, t("3.1 시분할 측정(TDM) 아키텍처",
                      "3.1 Time-Division Measurement Architecture"), 2)
    para(doc, L, t(
        "하나의 코일에서 세 신호를 얻으려면 여기(excitation) 상태를 시간축에서 분리해야 한다. 본 시스템은 동일 "
        "코일에 AC 여기(공진 주파수 측정), DC 여기(전압 분배 저항 측정), 무여기(부유 상태 TENG 전압 측정)를 "
        "1 ms 주기로 순환 인가한다. 그림 2는 신호 경로와 스케줄을 함께 보여준다.",
        "Obtaining three signals from one coil requires the excitation state to be "
        "separated in time. The system cycles AC excitation (resonant-frequency "
        "measurement), DC excitation (resistance measurement through a voltage divider) and "
        "no excitation (TENG voltage measured with the coil floating) on the same coil with "
        "a 1 ms period. Figure 2 shows the signal path together with the schedule."),
        align="j")
    para(doc, L, t(
        "TIM7이 1 ms마다 인터럽트를 발생시키면 두 경로가 동시에 시작된다. I²C 경로는 LDC1614의 28비트 공진 "
        "주파수 레지스터를 체인 DMA로 읽어 약 200 µs 안에 완료한다. ADC 경로는 ADG734 멀티플렉서를 TENG 모드로 "
        "전환한 뒤 TIM6를 기동하고, 150 µs 후 TENG 값을 확정하며 MUX를 저항 모드로 전환한 다음(스위칭 29 ns) "
        "다시 150 µs 후 저항 값을 확정한다. 두 경로 중 나중에 끝나는 쪽이 갱신 플래그를 세우고 상태를 IDLE로 "
        "되돌린다. 모든 전송이 DMA로 수행되어 블로킹 대기가 없으며, 추론 추가 전 기준으로 CPU 유휴율은 "
        "93.9 %였다. 고정 샘플링 주기를 유지하는 것은 AI 모델과 결합할 때 지터를 방지하기 위해서다.",
        "When TIM7 fires every 1 ms, two paths start concurrently. The I²C path reads the "
        "28-bit resonant-frequency registers of the LDC1614 through chained DMA transfers, "
        "completing in about 200 µs. The ADC path switches the ADG734 multiplexer to TENG "
        "mode and starts TIM6; after 150 µs the TENG value is latched and the multiplexer "
        "is switched to resistance mode (29 ns switching), and after a further 150 µs the "
        "resistance value is latched. Whichever path finishes last sets the update flag and "
        "returns the state machine to IDLE. All transfers use DMA, so there is no blocking "
        "wait, and the CPU idle fraction was 93.9 % before inference was added. The fixed "
        "sampling period is maintained specifically to prevent jitter when the acquisition "
        "is coupled to an AI model."), align="j")
    figure(doc, L, "fig1_tdm.png", t(
        "그림 2. (a) 단일 전극 신호 경로. 동일한 EGaIn 코일이 ADG734 아날로그 멀티플렉서를 통해 LDC1614, "
        "TENG용 ADC, 저항 측정용 ADC에 순차 연결된다. (b) 1 ms TDM 스케줄. I²C DMA와 ADC DMA가 병렬로 "
        "진행되고, 남는 시간에 MoE 추론(실측 260 µs)이 수행된다.",
        "Fig. 2. (a) Single-electrode signal path. The same EGaIn coil is connected in turn "
        "to the LDC1614, the TENG ADC and the resistance ADC through an ADG734 analog "
        "multiplexer. (b) The 1 ms TDM schedule. I²C DMA and ADC DMA proceed in parallel, "
        "and MoE inference (measured at 260 µs) runs in the remaining time."))

    heading(doc, L, t("3.2 다신호 스위칭 PCB", "3.2 Multisignal Switching PCB"), 2)
    para(doc, L, t(
        "전용 보드는 EasyEDA Pro로 설계한 65 × 52 mm 6층 기판이며, 최대 4채널 센서 어레이를 지원한다(본 "
        "연구의 모든 실험은 1채널로 수행). 메인 MCU는 STM32G473CBT6(Cortex-M4F, 170 MHz, 플래시 128 KB, "
        "SRAM 32 KB)이다. 인덕턴스 측정은 LDC1614가 담당한다[27](VDD 3.3 V, IDD 2.1 mA, 구동 전류 1.5 mA 미만, "
        "1 kHz–10 MHz, 28비트). 레지스터 설정에 따른 시간 상수는 정착 t_settle ≈ 8 µs, 채널 전환 "
        "t_switch = 692 ns + 5/f_ref ≈ 1 µs, 변환 t_conversion = (RCount×16+4)/f_ref ≈ 991 µs이며, 400 kHz "
        "I²C 전송 시간은 약 420 µs이다. 신호 경로 전환은 ADG734 4채널 아날로그 스위치가 담당한다[28](R_on 2.5 Ω, "
        "C_on 34 pF, t_on 29 ns, t_off 9 ns, 대역폭 200 MHz). 대역폭이 충분히 넓어 스위치 자체가 고주파 공진을 "
        "일으키지 않는다.",
        "The dedicated board is a 65 × 52 mm six-layer design produced in EasyEDA Pro and "
        "supports a sensor array of up to four channels (all experiments here used one). "
        "The main MCU is an STM32G473CBT6 (Cortex-M4F, 170 MHz, 128 KB flash, 32 KB SRAM). "
        "Inductance is measured by an LDC1614 [27] (VDD 3.3 V, IDD 2.1 mA, drive current below "
        "1.5 mA, 1 kHz–10 MHz, 28-bit). With the chosen register settings the time constants "
        "are t_settle ≈ 8 µs, t_switch = 692 ns + 5/f_ref ≈ 1 µs and "
        "t_conversion = (RCount×16+4)/f_ref ≈ 991 µs, while an I²C transfer at 400 kHz takes "
        "about 420 µs. Signal-path switching uses ADG734 four-channel analog switches [28] "
        "(R_on 2.5 Ω, C_on 34 pF, t_on 29 ns, t_off 9 ns, 200 MHz bandwidth), whose "
        "bandwidth is wide enough that the switch itself introduces no high-frequency "
        "resonance."), align="j")
    para(doc, L, t(
        "ADC 경로는 STM32 내장 12비트 ADC와 G 시리즈 내장 연산 증폭기를 내부 연결하여 구성한다. 두 모드의 전달 "
        "관계는 R_DC,ADC = R/(R₀+R) × Gain_op, V_TENG,ADC = V × Gain_op 이다. MUX 상태 조합은 세 가지로, "
        "SW1/SW2를 HIGH로 두면 코일이 LDC 공진 회로에 연결되고, 모두 LOW로 두면 코일이 부유 상태가 되어 TENG "
        "전압을 읽을 수 있으며, SW3/SW4를 HIGH로 두면 전압 분배 회로가 연결된다. TENG 경로에는 정전기 방전에 "
        "대비한 TVS 다이오드를 배치하였다. USB-UART는 데이터 스트리밍용이며 시스템 동작 자체에는 필요하지 않다.",
        "The ADC path uses the STM32's built-in 12-bit ADC with the internal operational "
        "amplifier of the G series. The transfer relations for the two modes are "
        "R_DC,ADC = R/(R₀+R) × Gain_op and V_TENG,ADC = V × Gain_op. Three multiplexer "
        "states are defined: with SW1/SW2 high the coil connects to the LDC resonant "
        "circuit; with all switches low the coil floats so the TENG voltage can be read; "
        "with SW3/SW4 high the voltage divider is engaged. TVS diodes protect the TENG path "
        "against electrostatic discharge. The USB-UART interface is used for data streaming "
        "and is not required for system operation."), align="j")

    heading(doc, L, t("3.3 5축 시험 플랫폼과 동기 취득",
                      "3.3 Five-Axis Test Platform and Synchronized Acquisition"), 2)
    para(doc, L, t(
        "인장과 근접·접촉을 독립적으로 제어하기 위해 시험 플랫폼을 직접 제작하였다. 상용 CNC 기반 인장 장치를 "
        "사용하지 않은 이유는 명확하다. 한쪽 축만 구동하는 일반적인 인장 시험 방식에서는 시편이 늘어나면서 "
        "중심점이 이동하는데, 본 실험에서는 코일 중심 바로 위에 근접 표적을 두어야 하므로 중심 이동이 곧 근접 "
        "거리 라벨의 오차가 된다. 따라서 XA/XB/YA/YB 네 축이 시편을 대칭으로 인장하여 코일 중심을 고정하고, "
        "독립된 Z축이 표적을 센서 표면에 수직으로 이동시키는 구조를 채택하였다.",
        "A test platform was built in-house so that strain and proximity/contact could be "
        "controlled independently. The reason for not using a commercial CNC-based tensile "
        "device is straightforward: in conventional single-sided tensile testing the "
        "specimen centre translates as it elongates, and since the proximity target must "
        "sit directly above the coil centre, any such translation becomes an error in the "
        "distance label. Four axes (XA/XB/YA/YB) therefore stretch the specimen "
        "symmetrically to hold the coil centre fixed, while an independent Z axis moves the "
        "target perpendicular to the sensor surface."), align="j")
    para(doc, L, t(
        "프레임은 700 × 700 mm, 높이 200–300 mm 규모이며, Nema23 스테퍼 모터와 TB6600 드라이버, "
        "SMPS LRS-350-24 전원부, Arduino Uno 제어 보드, 리밋 스위치, 센서 장착 지그로 구성된다. 기본 환산은 "
        "200 step/rev × 8 마이크로스텝 ÷ 5 mm 피치 = 320 step/mm이다. PyQt5 GUI가 수동 이동(0.1/1/5 mm), "
        "원점 설정, 시퀀스 스크립트 실행, 비상 정지와 모터 해제를 제공한다.",
        "The frame measures 700 × 700 mm with a height of 200–300 mm and comprises Nema23 "
        "stepper motors with TB6600 drivers, an SMPS LRS-350-24 supply, an Arduino Uno "
        "control board, limit switches and a sensor mounting jig. The default conversion is "
        "200 steps/rev × 8 microsteps / 5 mm pitch = 320 steps/mm. A PyQt5 GUI provides "
        "manual jogging (0.1/1/5 mm), homing, script-driven sequence execution, emergency "
        "stop and motor release."), align="j")
    para(doc, L, t(
        "초기 실험은 PC와 MCU를 비동기로 기록한 뒤 피크를 추출해 보간하는 방식이었는데, 스테퍼 가감속 구간에서 "
        "위치 라벨과 센서 신호가 어긋나는 문제가 있었다. 이를 해결하기 위해 동기 취득 시스템을 구축하여 PC가 "
        "모터 명령 타임스탬프와 MCU 스트림을 같은 시간축에 정렬하고, 가감속 과도 구간을 is_steady = 0으로 자동 "
        "태깅하도록 하였다. 접촉 모달리티 실험에서는 6축 F/T 센서를 CAN으로 연결해 접촉력 참값을 동시에 "
        "기록하였다. F/T 센서는 세션마다 영점이 수백 mN 어긋나 있었으므로, 비접촉 구간(z ≥ 0)의 평균을 세션별 "
        "오프셋으로 제거한 값을 정답으로 사용하였다.",
        "Early experiments logged the PC and MCU asynchronously and interpolated between "
        "extracted peaks, which misaligned position labels and sensor signals during "
        "stepper acceleration and deceleration. A synchronized acquisition system was "
        "therefore built in which the PC aligns motor-command timestamps and the MCU stream "
        "on a common time base and automatically tags acceleration transients as "
        "is_steady = 0. For the contact experiments a six-axis force/torque sensor was "
        "connected over CAN to record ground-truth contact force simultaneously. Because "
        "the F/T zero drifted by a few hundred millinewtons between sessions, the mean of "
        "the non-contact region (z ≥ 0) was removed as a session-wise offset before the "
        "force was used as a label."), align="j")

    # ── 4. 데이터셋 ─────────────────────────────────────────────────────────
    heading(doc, L, t("4. 데이터셋", "4. Datasets"), 1)
    para(doc, L, t(
        "연구 진행에 따라 다섯 개의 데이터셋을 순차적으로 취득하였다(표 2). 모델 입력으로 실제 사용 가능한 값은 "
        "언제나 (ΔL/L₀, ΔR/R₀)와 그로부터 인과적으로 계산 가능한 값뿐이며, 스테이지 위치와 F/T 힘은 오직 정답 "
        "라벨로만 사용하였다.",
        "Five datasets were acquired in sequence as the study progressed (Table 2). The "
        "only quantities available to the model as inputs are always (ΔL/L₀, ΔR/R₀) and "
        "values computable causally from them; stage positions and F/T forces were used "
        "solely as ground-truth labels."), align="j")
    table(doc, L,
          [t("데이터셋", "Dataset"), t("프로토콜", "Protocol"), t("규모", "Size"),
           t("용도", "Purpose")],
          [["D1 (0332)",
            t("변형 37단계(1 mm) 고정 + 근접 50→0 mm 연속, 비동기",
              "37 strain levels (1 mm steps), continuous 50→0 mm proximity, asynchronous"),
            t("약 78,000 행", "approx. 78,000 rows"),
            t("초기 2단 PINN 학습", "initial two-stage PINN training")],
           ["D2 (P1/P2)",
            t("P1: 변형 19단계 × 근접 연속 스윕 / P2: 근접 13단계 × 변형 스윕(2회)",
              "P1: 19 strain levels × continuous proximity sweep; P2: 13 proximity levels × "
              "strain sweep (2 reps)"),
            t("금속 45,633행 / 손 37,116행", "metal 45,633 rows / hand 37,116 rows"),
            t("(ε, d) 응답 곡면 특성화",
              "characterization of the (strain, d) response surface")],
           ["D3 (0519)",
            t("세션 A: 변형 24단계 단조 증가 + 근접 36→1 mm 연속 / 세션 B: 변형 연속 증가 + 근접 24단계 감소",
              "session A: strain increasing in 24 steps with continuous 36→1 mm proximity; "
              "session B: continuous strain with proximity decreasing in 24 steps"),
            t("100,353 + 87,879행 → 전처리 후 33,450",
              "100,353 + 87,879 rows → 33,450 after preprocessing"),
            t("근접+인장 디커플러 학습",
              "training of the proximity + strain decoupler")],
           ["D4 (0806)",
            t("변형 19단계(2 mm) × 근접 25 mm→0→−1.2 mm 왕복, F/T 동시 기록, 최대 10.1 N",
              "19 strain levels (2 mm) × a 25 mm→0→−1.2 mm proximity-to-contact traverse "
              "with simultaneous F/T recording, up to 10.1 N"),
            t("51,858행 / 569 s", "51,858 rows / 569 s"),
            t("접촉 물리 분석 및 MoE 학습", "contact physics analysis and MoE training")],
           ["D5 (0819)",
            t("실기 검증 3세션: Part1 근접 스윕 / Part2 인장 스윕 / Part3 동시",
              "three on-hardware validation sessions: Part 1 proximity sweeps, Part 2 "
              "strain sweeps, Part 3 simultaneous"),
            t("26,673 / 34,016 / 32,556행", "26,673 / 34,016 / 32,556 rows"),
            t("임베디드 실시간 검증", "embedded real-time validation")]],
          caption=t("표 2. 데이터셋 요약.", "Table 2. Summary of the datasets."),
          widths=[2.2, 6.2, 3.6, 4.0])
    para(doc, L, t(
        "D3의 전처리는 다음 순서로 수행하였다. (1) 변형 < 0.5 %, 근접 > 35 mm 조건의 중앙값으로 기준선 L₀, R₀를 "
        "재추출하고 ΔL, ΔR을 재계산한다. (2) LDC1614 레지스터 포화(0x0FFFFFFF)와 물리적으로 불가능한 범위"
        "(|ΔL| > 30 %, ΔR ∉ (−5, 30) %)를 제거한다. (3) (ε, d) 평면을 24 × 24 격자로 나누고 셀당 최대 30 샘플로 "
        "상한을 두어 과대표집을 보정한다. (4) 두 세션을 병합하고 무작위 셔플 후 70/15/15로 분할한다. IIR 필터를 "
        "적용하지 않고 원시 신호를 그대로 학습에 사용한 것은 의도적인 선택이다. α = 0.02인 IIR은 시간상수가 약 "
        "500 ms여서 10 mm/s 이동 구간에서 5 mm에 해당하는 위상 지연을 만들고, 그 결과 지연된 입력이 현재 시각의 "
        "라벨과 매핑되어 동적 구간 오차를 키우기 때문이다.",
        "Preprocessing of D3 proceeded as follows. (1) Baselines L₀ and R₀ were "
        "re-extracted as medians over the region with strain < 0.5 % and distance > 35 mm, "
        "and ΔL and ΔR were recomputed. (2) LDC1614 register saturation (0x0FFFFFFF) and "
        "physically impossible ranges (|ΔL| > 30 %, ΔR outside (−5, 30) %) were removed. "
        "(3) The (strain, d) plane was divided into a 24 × 24 grid and capped at 30 samples "
        "per cell to correct over-representation. (4) The two sessions were merged, "
        "shuffled and split 70/15/15. Training on raw rather than IIR-filtered signals was "
        "a deliberate choice: an IIR filter with α = 0.02 has a time constant of about "
        "500 ms, which at 10 mm/s corresponds to a 5 mm phase lag, so delayed inputs would "
        "be mapped onto present-time labels and dynamic-segment error would grow."),
        align="j")

    # ── 5. 신호 특성화 ──────────────────────────────────────────────────────
    heading(doc, L, t("5. 신호 특성화", "5. Signal Characterization"), 1)
    heading(doc, L, t("5.1 (ε, d) 응답 곡면과 표적 의존성",
                      "5.1 Response Surfaces and Target Dependence"), 2)
    para(doc, L, t(
        "그림 3은 D2를 격자 평균하여 얻은 응답 곡면이다. 금속 표적에 대한 ΔR(그림 3b)의 등고선은 근접거리 축과 "
        "거의 완전히 평행하며, 이는 저항이 인장에만 의존한다는 2.2절의 관계가 실측으로 성립함을 뜻한다. 반면 "
        "ΔL(그림 3a)의 등고선은 d < 10 mm 영역에서 급격히 휘어지며, 같은 인장 상태에서도 근접거리에 따라 "
        "−15.7 %에서 +14.5 %까지 부호가 바뀔 정도로 크게 변한다. 두 곡면의 기울기 벡터 ∇L(d, ε)와 ∇R(d, ε)가 "
        "전역적으로 선형 독립이라는 점이 디커플링 가능성의 직접적인 근거다.",
        "Figure 3 shows the response surfaces obtained by grid-averaging D2. For the metal "
        "target the contours of ΔR (Fig. 3b) are essentially parallel to the distance axis, "
        "confirming by measurement the relation of Section 2.2 that resistance depends on "
        "strain alone. The contours of ΔL (Fig. 3a), by contrast, bend sharply for "
        "d < 10 mm and, at fixed strain, vary from −15.7 % to +14.5 % — changing sign — as "
        "the distance changes. That the gradient vectors ∇L(d, ε) and ∇R(d, ε) of the two "
        "surfaces are globally linearly independent is the direct evidence that decoupling "
        "is feasible."), align="j")
    figure(doc, L, "fig2_surfaces.png", t(
        "그림 3. 변형률과 근접거리에 대한 신호 응답 곡면(D2, 격자 평균). (a),(b) 금속 표적: ΔL은 근접거리에 "
        "강하게 의존하지만 ΔR의 등고선은 수직이다(인장 전용). (c),(d) 손 표적: 두 신호 모두 등고선이 거의 "
        "수직으로, 유전체 표적에서는 이 거리 범위에서 인덕턴스에 실린 근접 정보가 미약하다.",
        "Fig. 3. Signal response surfaces over strain and proximity (D2, grid-averaged). "
        "(a),(b) Metal target: ΔL depends strongly on distance whereas the contours of ΔR "
        "are vertical (strain only). (c),(d) Hand target: contours of both signals are "
        "nearly vertical, indicating that for a dielectric target the proximity information "
        "carried by the inductance is weak over this distance range."))
    para(doc, L, t(
        "표적 종류에 따른 차이는 2.2절의 기구 차이에서 직접 따라온다. 금속에서는 와전류 손실이 지배적이어서 "
        "근접 시 실효 인덕턴스가 크게 감소하는 반면, 손(유전체)에서는 유전율 변화에 의한 신호 증폭만 작용하여 "
        "ΔL이 항상 양수이고 크기도 작다. 그림 3c에서 손 표적의 ΔL 등고선이 거의 수직인 것은, 이 조건에서 "
        "인덕턴스가 사실상 인장 센서로만 동작한다는 뜻이며, 결과적으로 유전체 표적에 대한 근접 디커플링은 도체 "
        "표적보다 근본적으로 어렵다. 이후의 모든 모델링은 도체 표적을 대상으로 한다.",
        "The difference between targets follows directly from the mechanisms of Section "
        "2.2. For metal, eddy-current loss dominates and the effective inductance drops "
        "substantially on approach; for a hand (a dielectric), only permittivity-driven "
        "signal amplification acts, so ΔL remains positive and small. The nearly vertical "
        "ΔL contours for the hand target in Fig. 3c mean that, under these conditions, the "
        "inductance behaves essentially as a strain sensor alone, and proximity decoupling "
        "for dielectric targets is therefore fundamentally harder than for conductive ones. "
        "All subsequent modelling targets the conductive case."), align="j")

    heading(doc, L, t("5.2 접촉 영역의 점탄성과 Q-factor 겉보기 효과",
                      "5.2 Viscoelasticity and the Q-Factor Artefact in the Contact Regime"), 2)
    para(doc, L, t(
        "접촉 모달리티를 추가하자 비접촉 실험에서는 없던 현상이 나타났다. 첫째, 같은 깊이·같은 사이클 안에서 "
        "인덕턴스의 샘플 간 표준편차가 압축이 깊어질수록 0.09 %p에서 0.52 %p까지 약 5배 증가하였다. 저항 측정은 "
        "단순 전압 분배여서 공진 품질과 무관한 반면 인덕턴스 측정만 공진 주파수에 의존하므로, 이 비대칭은 "
        "압축에 의한 Q-factor 저하로 설명된다.",
        "Adding the contact modality produced phenomena absent from the non-contact "
        "experiments. First, within the same cycle and at the same depth, the "
        "sample-to-sample standard deviation of the inductance grew about fivefold, from "
        "0.09 %p to 0.52 %p, as compression deepened. Since the resistance measurement is a "
        "simple voltage division independent of resonance quality while only the inductance "
        "measurement depends on the resonant frequency, this asymmetry is explained by a "
        "fall in the Q factor under compression."), align="j")
    para(doc, L, t(
        "Q-factor는 코일에 저장되는 에너지와 한 주기당 소산되는 에너지의 비로 정의된다.",
        "The Q factor is defined as the ratio of the energy stored in the coil to the "
        "energy dissipated per cycle."), align="j")
    eq(doc, L, t("Q = ω · (최대 저장 에너지 / 주기당 소산 에너지) = X / R_s = ωL / R_s",
                 "Q = ω · (maximum stored energy / energy dissipated per cycle) "
                 "= X / R_s = ωL / R_s"))
    para(doc, L, t(
        "이 관계는 압축 시 관측된 역설적 거동을 설명한다. 센서가 눌리면 L은 감소하고 R_DC와 와전류 손실 저항이 "
        "모두 증가하므로 Q가 급격히 낮아진다. 실제 공진 주파수는 Q에 의존하는 다음 형태를 가진다.",
        "This relation explains a paradoxical behaviour observed under compression. When "
        "the sensor is pressed, L decreases while both R_DC and the eddy-current loss "
        "resistance increase, so Q falls sharply. The true resonant frequency depends on Q "
        "as"), align="j")
    eq(doc, L, "f = 1/(2π√(LC)) · √(1 − 1/Q²)")
    para(doc, L, t(
        "그러나 LDC1614 출력에서 인덕턴스를 되찾을 때는 근사식 f ≈ 1/(2π√(LC))를 사용하여 "
        "ΔL/L₀ = f₀²/f² − 1로 계산한다. Q가 작아져 실제 공진 주파수가 감소하면, 이 근사 역산은 L이 증가한 "
        "것처럼 보고한다. 즉 그림 4b에서 강한 압축 시 ΔL이 반등하는 것은 인덕턴스의 실제 증가가 아니라 역산 "
        "과정의 겉보기 효과다. 본 연구에서는 이 항을 별도로 보정하지 않았다. 학습 기반 디커플러는 (ΔL, ΔR)에서 "
        "목표 물리량으로 가는 매핑을 직접 학습하므로, Q 의존성이 입력에 일관되게 포함되어 있는 한 별도의 역산 "
        "보정 없이도 올바른 출력을 낼 수 있기 때문이다. 이는 해석적 역산 대비 학습 기반 접근의 실용적 이점 중 "
        "하나다.",
        "When the inductance is recovered from the LDC1614 output, however, the "
        "approximation f ≈ 1/(2π√(LC)) is used and ΔL/L₀ is computed as f₀²/f² − 1. As Q "
        "falls and the true resonant frequency decreases, this approximate inversion "
        "reports an apparent increase in L. The rebound of ΔL under strong compression in "
        "Fig. 4b is therefore an artefact of the inversion rather than a genuine rise in "
        "inductance. No correction for this term was applied here: because the learned "
        "decoupler maps (ΔL, ΔR) directly onto the target quantities, it can produce "
        "correct outputs without an explicit inversion correction as long as the Q "
        "dependence is consistently present in its inputs. This is one of the practical "
        "advantages of the learned approach over analytical inversion."), align="j")
    para(doc, L, t(
        "둘째, 로딩 경로와 언로딩 경로가 어긋나는 히스테리시스가 관측되었다(그림 4a, 4b). 깊이를 고정한 채 "
        "유지(dwell)하는 동안 ΔL은 2.33 %p, ΔR은 5.73 %p 더 변화했고, 힘을 완전히 제거한 뒤 남는 잔차는 각각 "
        "0.57 %p와 0.08 %p에 불과했다. 즉 변화의 대부분은 영구 손상이 아니라 가역적인 시간 지연 성분이다. 이 "
        "거동 — 접촉 순간 즉시 반응하고, 유지 중 서서히 더 변하며, 떼면 거의 완전히 회복 — 은 즉시 반응하는 "
        "탄성 성분과 시간에 따라 완화되는 점성 성분이 결합된 표준선형고체(SLS) 모델과 일치한다[26]. 반면 Maxwell "
        "모델은 완전 회복을 설명하지 못하고 Kelvin–Voigt 모델은 즉시 반응 성분이 없어 맞지 않는다. SLS의 지배 "
        "방정식은 다음과 같고, 깊이가 고정된 dwell 구간에서 그 해는 지수 완화 형태가 된다.",
        "Second, hysteresis was observed between the loading and unloading paths "
        "(Figs. 4a, 4b). While the depth was held constant (dwell), ΔL drifted by a further "
        "2.33 %p and ΔR by 5.73 %p, whereas the residuals after full unloading were only "
        "0.57 %p and 0.08 %p respectively. Most of the change is therefore a reversible "
        "time-lag component rather than permanent damage. This behaviour — an immediate "
        "response on contact, continued drift during the hold, and near-complete recovery "
        "on release — matches a standard linear solid (SLS) model [26] combining an "
        "instantaneous elastic component with a time-relaxing viscous one. A Maxwell model "
        "cannot explain the complete recovery and a Kelvin-Voigt model lacks the "
        "instantaneous component. The governing equation of the SLS is given below, and "
        "during a constant-depth dwell its solution is an exponential relaxation."),
        align="j")
    eq(doc, L, "σ + (η/(E₁+E₂))·σ̇ = (E₁E₂/(E₁+E₂))·ε + (E₁η/(E₁+E₂))·ε̇,    τ_c = η/E₂")
    para(doc, L, t(
        "실측 dwell 곡선에 최소제곱 피팅한 결과 τ = 0.93 s를 얻었고(그림 4c), 전체 데이터셋에 대한 채널별 "
        "피팅에서는 τ_L = 1.33 s, τ_R = 0.59 s, 통합 τ = 1.01 s였다.",
        "A least-squares fit to the measured dwell curve gave τ = 0.93 s (Fig. 4c), while "
        "channel-wise fits over the whole dataset gave τ_L = 1.33 s, τ_R = 0.59 s and a "
        "combined τ = 1.01 s."), align="j")
    figure(doc, L, "fig3_pressure.png", t(
        "그림 4. 접촉 영역의 신호 거동(D4). (a) 무변형 상태에서 10.1 N까지 가압: ΔR 변화 폭은 3.95 %p에 "
        "그친다. (b) 30 % 인장 상태에서 9.2 N 가압: ΔR 변화 폭이 26.14 %p로 6.6배 증가하고, ΔL은 −30.4 %까지 "
        "떨어졌다가 최대 힘 근처에서 −20.7 %로 반등한다(Q-factor 겉보기 효과). 로딩/언로딩 경로가 벌어지는 "
        "것이 히스테리시스다. (c) 깊이를 고정한 dwell 구간의 ΔR 완화와 SLS 지수 피팅(τ = 0.93 s).",
        "Fig. 4. Signal behaviour in the contact regime (D4). (a) Loading to 10.1 N at zero "
        "strain: the ΔR span is only 3.95 %p. (b) Loading to 9.2 N at 30 % strain: the ΔR "
        "span grows 6.6-fold to 26.14 %p, and ΔL falls to −30.4 % before rebounding to "
        "−20.7 % near peak force (the Q-factor artefact). The separation of the loading and "
        "unloading paths is the hysteresis. (c) Relaxation of ΔR during a constant-depth "
        "dwell with an SLS exponential fit (τ = 0.93 s)."))

    heading(doc, L, t("5.3 인장 × 접촉력 교차 민감도", "5.3 Strain-Force Cross-Sensitivity"), 2)
    para(doc, L, t(
        "셋째이자 모델 설계에 가장 큰 영향을 준 발견은, 인장 상태가 압력 민감도 자체를 바꾼다는 것이다. 그림 "
        "4에서 보듯 무변형 상태에서 10 N을 가해도 ΔR은 3.95 %p만 움직이지만, 30 % 인장 상태에서는 유사한 힘에 "
        "대해 26.14 %p가 움직인다(약 6.6배). 이는 2.3절의 R_theory(ε) = α₁ε + α₂ε² 가정이 압력이 함께 작용하는 "
        "상황에서는 성립하지 않으며 ε×F 교차항이 필요함을 뜻한다. 두 자극의 민감도 방향 벡터를 선형 근사하면 "
        "인장 1 %p당 (ΔL, ΔR) = (+0.635, +0.664), 접촉력 1 N당 (+2.070, +11.575)이며, 두 벡터 사이 각도는 "
        "33.6°, 조건수는 약 23이다. 즉 두 자극은 완전히 겹치지는 않지만 선형 역산으로 분리하기에는 조건이 나쁘다.",
        "The third finding, which most strongly shaped the model design, is that the strain "
        "state changes the pressure sensitivity itself. As Fig. 4 shows, applying 10 N at "
        "zero strain moves ΔR by only 3.95 %p, whereas at 30 % strain a comparable force "
        "moves it by 26.14 %p, a factor of about 6.6. The assumption "
        "R_theory(ε) = α₁ε + α₂ε² of Section 2.3 therefore fails when pressure is applied "
        "simultaneously, and a strain-force cross term is required. A linear approximation "
        "of the two sensitivity directions gives (ΔL, ΔR) = (+0.635, +0.664) per %p of "
        "strain and (+2.070, +11.575) per newton of contact force; the angle between the "
        "vectors is 33.6 degrees and the condition number is about 23. The two stimuli are "
        "therefore not perfectly degenerate, but the problem is poorly conditioned for "
        "linear inversion."), align="j")

    # ── 6. 디커플링 모델 ────────────────────────────────────────────────────
    heading(doc, L, t("6. 디커플링 모델", "6. Decoupling Models"), 1)
    heading(doc, L, t("6.1 2단계 물리 기반 디커플러(인장·근접)",
                      "6.1 Two-Stage Physics-Guided Decoupler (Strain and Proximity)"), 2)
    para(doc, L, t(
        "5.1절에서 확인한 비대칭을 그대로 구조로 옮기면 2단계 추정기가 된다. 1단계는 ΔR만으로 변형률을 "
        "추정하고(ε̂), 2단계는 ΔL과 ε̂을 함께 받아 근접거리를 추정한다(d̂). 이 구조는 저항이 변형률만의 함수라는 "
        "물리 사실을 귀납 편향으로 부여하므로, 동일 파라미터 예산에서 단일 종단 모델보다 유리하다. 약 50 K "
        "파라미터로 예산을 맞춘 공정 비교에서 2단계 구조(50,306 파라미터, 49,664 MACs)의 근접 MAE는 1.783 mm로 "
        "종단 구조(49,592 파라미터, 49,140 MACs)의 1.827 mm보다 우수하였다.",
        "Transferring the asymmetry established in Section 5.1 directly into the "
        "architecture yields a two-stage estimator: stage 1 estimates strain from ΔR alone, "
        "and stage 2 receives both ΔL and the estimated strain to predict distance. The "
        "structure imposes the physical fact that resistance is a function of strain only "
        "as an inductive bias, and is therefore advantageous over a single end-to-end model "
        "at equal parameter budget. In a fair comparison at approximately 50 K parameters "
        "the two-stage model (50,306 parameters, 49,664 MACs) achieved a proximity MAE of "
        "1.783 mm against 1.827 mm for the end-to-end model (49,592 parameters, 49,140 "
        "MACs)."), align="j")
    para(doc, L, t(
        "물리 정보 신경망(PINN)[24] 형태로도 학습하였다. 데이터 손실에 물리 잔차를 더하고, λ를 첫 50 에폭 동안 "
        "0으로 두었다가 이후 0.10까지 선형 증가시켜 초기 수렴 방향을 데이터로 잡은 뒤 물리 제약을 점진 "
        "부과하였다. 특이점을 피하기 위해 d₀와 k는 softplus로 양수 제약을 두었다. 818개 신경망 파라미터와 7개 "
        "물리 파라미터로 학습한 결과 테스트 MAE는 변형률 0.356 %, 근접거리 1.797 mm였고, 유효 근접 범위인 "
        "d ≤ 15 mm에서는 0.337 mm, d ≤ 10 mm에서는 0.200 mm였다. 다만 데이터가 충분한 조건에서 물리 손실의 순수 "
        "기여는 크지 않았다(근접 MAE 0.01 mm 개선). 물리 제약의 실질적 가치는 정확도 향상보다 외삽 영역에서의 "
        "발산 억제에 있다고 판단된다.",
        "A physics-informed (PINN) [24] variant was also trained, adding a physics residual to "
        "the data loss with λ held at zero for the first 50 epochs and then increased "
        "linearly to 0.10, so that the initial convergence direction is set by the data "
        "before the physics constraint is applied progressively. To avoid a singularity, d₀ "
        "and k were constrained positive through a softplus. Training with 818 network "
        "parameters and 7 physical parameters gave test MAEs of 0.356 % for strain and "
        "1.797 mm for distance, improving to 0.337 mm for d ≤ 15 mm and 0.200 mm for "
        "d ≤ 10 mm within the useful proximity range. With ample data, however, the "
        "isolated contribution of the physics loss was small (0.01 mm in proximity MAE); "
        "its practical value appears to lie less in accuracy than in suppressing divergence "
        "in extrapolation regions."), align="j")
    para(doc, L, t(
        "오차 구조에는 뚜렷한 비대칭이 있다. 변형률 오차는 전 구간에서 분산이 일정한 동분산 특성을 보이는 반면, "
        "근접거리 오차는 이분산 특성을 보여 d > 10 mm에서 급격히 불안정해진다. 이는 5.1절에서 본 ΔL 곡면의 "
        "곡률이 근거리에 집중되어 있다는 사실의 직접적 귀결이며, 이후 모든 평가에서 d ≤ 15 mm와 d ≤ 10 mm "
        "구간을 별도로 보고하는 이유다.",
        "The error structure is markedly asymmetric. The strain error is homoscedastic "
        "across the range, whereas the distance error is heteroscedastic and becomes "
        "unstable beyond d = 10 mm. This follows directly from the concentration of ΔL "
        "surface curvature in the near field seen in Section 5.1, and is the reason the "
        "d ≤ 15 mm and d ≤ 10 mm ranges are reported separately in all subsequent "
        "evaluations."), align="j")

    heading(doc, L, t("6.2 아키텍처 탐색과 양자화", "6.2 Architecture Search and Quantization"), 2)
    para(doc, L, t(
        "임베딩 비용을 최소화하기 위해 동일한 2단계 구조를 유지한 채 13가지 크기의 신경망을 학습하여 파라미터 "
        "수와 정확도의 상충 관계를 조사하였다(그림 5, 부록 S2). 46 파라미터의 최소 모델도 근접 MAE 2.115 mm를 "
        "달성했고, 978 파라미터의 medium-deep 구조가 1.765 mm로 파레토 무릎에 해당했다. 파라미터를 10,946개까지 "
        "늘려도 1.773 mm로 개선이 없어, 이 문제의 본질적 난이도는 모델 용량이 아니라 데이터와 물리에 의해 "
        "결정됨을 확인하였다.",
        "To minimize embedding cost, thirteen network sizes were trained with the same "
        "two-stage structure to map the trade-off between parameter count and accuracy "
        "(Fig. 5, Appendix S2). Even the smallest 46-parameter model reached a proximity "
        "MAE of 2.115 mm, and a 978-parameter medium-deep configuration sat at the Pareto "
        "knee with 1.765 mm. Increasing the parameter count to 10,946 gave no improvement "
        "(1.773 mm), confirming that the intrinsic difficulty of the problem is set by the "
        "data and the physics rather than by model capacity."), align="j")
    figure(doc, L, "fig4_pareto.png", t(
        "그림 5. 2단계 디커플러 아키텍처 탐색 결과. 가로축은 파라미터 수(로그), 세로축은 근접거리 MAE이다. "
        "978 파라미터의 medium-deep이 파레토 무릎이며, 50,306 파라미터 모델과 정확도 차이는 0.09 mm이다.",
        "Fig. 5. Architecture search for the two-stage decoupler. The horizontal axis is "
        "the parameter count (log scale) and the vertical axis the proximity MAE. The "
        "978-parameter medium-deep configuration lies at the Pareto knee, within 0.09 mm of "
        "the 50,306-parameter model."), width_cm=10.5)
    para(doc, L, t(
        "초기 배포에는 50,306 파라미터 모델을 INT8 양자화하여 사용하였다. 사후 양자화로 플래시 요구량은 196 KB "
        "에서 52 KB로 줄었고, 양자화에 의한 오차 증가는 변형률 0.061 %, 근접거리 0.070 mm로 센서 잡음 수준 "
        "이하였다. 그러나 52 KB 가중치가 명령어 캐시에 들어가지 않아 플래시 대기 사이클이 발생했고, 실측 추론 "
        "시간이 1,068 µs로 TDM 주기를 초과했다. medium-deep(978 파라미터)으로 교체하자 가중치가 3.9 KB로 줄어 "
        "캐시에 완전히 상주하게 되었고, 실측 추론 시간은 141 µs로 약 7.6배 단축되었다. 이 경험이 이후 MoE "
        "모델을 1,413 파라미터 규모로 설계한 직접적 근거가 되었다.",
        "The first deployment used the 50,306-parameter model quantized to INT8. "
        "Post-training quantization reduced the flash requirement from 196 KB to 52 KB, and "
        "the resulting error increase — 0.061 % in strain and 0.070 mm in distance — was "
        "below the sensor noise floor. The 52 KB of weights did not fit in the instruction "
        "cache, however, incurring flash wait states and a measured inference time of "
        "1,068 µs, which exceeds the TDM period. Replacing it with medium-deep (978 "
        "parameters) shrank the weights to 3.9 KB so that they reside entirely in cache, "
        "and the measured inference time fell to 141 µs, a speed-up of about 7.6×. This "
        "experience is the direct reason the later MoE model was designed at the "
        "1,413-parameter scale."), align="j")

    heading(doc, L, t("6.3 점탄성에서 유도한 이력 피처 (SLS-EMA)",
                      "6.3 History Features Derived from Viscoelasticity (SLS-EMA)"), 2)
    para(doc, L, t(
        "5.2절에서 확인한 것처럼, 접촉 구간의 신호는 현재 깊이만으로 결정되지 않고 얼마나 오래 눌려 있었는지에 "
        "의존한다. 따라서 순간값만 입력받는 모델은 원리적으로 이 정보를 복원할 수 없다. SLS 모델의 지수 완화 "
        "해에서 출발하면, 과거 샘플의 기여가 exp(−Δt/τ)로 감쇠하는 가중평균, 즉 인과적 지수이동평균(EMA)이 "
        "자연스럽게 도출된다.",
        "As established in Section 5.2, the signal in the contact regime is determined not "
        "by the instantaneous depth alone but by how long the sensor has been compressed. A "
        "model receiving only instantaneous values therefore cannot in principle recover "
        "this information. Starting from the exponential relaxation solution of the SLS "
        "model, a weighted average in which the contribution of past samples decays as "
        "exp(−Δt/τ) — that is, a causal exponential moving average (EMA) — follows "
        "naturally."), align="j")
    eq(doc, L, "EMA(t) = Σ x(t−Δt)·w(Δt) / Σ w(Δt),   w(Δt) = exp(−Δt/τ)")
    eq(doc, L, "EMAₙ = EMAₙ₋₁ + α(xₙ − EMAₙ₋₁),   α = 1 − exp(−Δt_sample/τ)")
    para(doc, L, t(
        "실시간 구현에서는 위의 재귀식으로 계산되며, 곱셈 1회와 상태 변수 1개만 필요하므로 MCU에서 비용이 "
        "사실상 0이다. τ = 1.01 s에 대응하는 반감기는 0.702 s이다. 중요한 점은 EMA가 정답 라벨이 아니라 "
        "실시간으로 들어오는 ΔL·ΔR만으로 계산된다는 것이며, 그래서 학습에 사용한 피처를 배포된 보드에서 그대로 "
        "재현할 수 있다. 이 피처 하나를 추가하자 접촉력 예측 RMSE가 0.521 N에서 0.253 N으로 절반 이하가 되었다. "
        "참고로 정답으로 사용한 F/T 센서 자체의 잡음이 같은 조건에서 ±0.19 N이므로, 이 오차는 라벨의 측정 "
        "한계에 근접한 값이다.",
        "In a real-time implementation it is computed by the recursion above, requiring one "
        "multiplication and one state variable, so its cost on the MCU is effectively zero. "
        "The half-life corresponding to τ = 1.01 s is 0.702 s. Crucially, the EMA is "
        "computed from the incoming ΔL and ΔR alone rather than from ground-truth labels, "
        "so the feature used in training can be reproduced exactly on the deployed board. "
        "Adding this single feature reduced the RMSE of the contact-force prediction from "
        "0.521 N to 0.253 N, less than half. For reference, the F/T sensor used as ground "
        "truth itself fluctuates by ±0.19 N under the same conditions, so this error is "
        "close to the measurement limit of the label."), align="j")

    heading(doc, L, t("6.4 게이트–전문가(Gate-MoE) 구조와 절제 실험",
                      "6.4 Gate-Expert (Gate-MoE) Architecture and Ablation"), 2)
    para(doc, L, t(
        "비접촉 구간과 접촉 구간은 출력 물리량 자체가 다르다. 전자는 (변형률, 근접거리)를, 후자는 (변형률, "
        "접촉력)을 추정해야 하며, 입력–출력 관계의 형태도 다르다. 하나의 회귀 모델로 두 영역을 모두 담당하게 "
        "하면 각 영역의 정확도가 저하되므로, 접촉 여부를 먼저 분류한 뒤 영역별 전문가에게 위임하는 "
        "Mixture-of-Experts 구조[25]를 채택하였다(그림 6). 게이트–전문가 구조와 SLS-EMA 이력 피처의 기여를 "
        "분리하기 위해 두 요소를 각각 켜고 끈 네 가지 모델을 동일한 사이클 단위 held-out 분할로 비교하였다(표 3).",
        "The non-contact and contact regimes differ in the very quantities to be produced: "
        "the former requires (strain, distance) and the latter (strain, force), and the "
        "input-output relations also differ in form. Forcing a single regressor to cover "
        "both degrades accuracy in each, so a mixture-of-experts architecture [25] was adopted "
        "in which contact is classified first and the regression delegated to a "
        "regime-specific expert (Fig. 6). To separate the contributions of the gate-expert "
        "structure and of the SLS-EMA history features, four models with each element "
        "switched on and off were compared under the same cycle-wise held-out split "
        "(Table 3)."), align="j")
    figure(doc, L, "fig5_moe.png", t(
        "그림 6. 배포한 MoE 디커플러 구조. 게이트는 원시 (ΔL, ΔR)만 보고 접촉 여부를 판정하며, 그 결과에 따라 "
        "같은 사이클 안에서 EMA를 즉시 리셋한 뒤 해당 전문가를 실행한다. 총 1,413 파라미터.",
        "Fig. 6. Structure of the deployed MoE decoupler. The gate observes only the raw "
        "(ΔL, ΔR) pair to decide contact, and its decision immediately resets the EMA "
        "within the same cycle before the corresponding expert is executed. Total: 1,413 "
        "parameters."))
    table(doc, L,
          [t("모델", "Model"), t("게이트 정확도", "Gate acc."),
           t("변형률 R² / RMSE", "Strain R² / RMSE"),
           t("근접거리 R² / RMSE", "Distance R² / RMSE"),
           t("접촉력 R² / RMSE", "Force R² / RMSE"), t("파라미터", "Param.")],
          [["A: Gate-MoE + SLS-EMA", "1.000", "0.999 / 0.108 %p", "0.999 / 0.318 mm",
            "0.995 / 0.253 N", "1,429"],
           [t("B: SLS-EMA만 (통합 모델)", "B: SLS-EMA only (unified)"), "—",
            "0.998 / 0.288 %p", "0.999 / 0.322 mm", "0.963 / 0.079 mm †", "1,506"],
           [t("C: Gate-MoE만 (이력 없음)", "C: Gate-MoE only (no history)"), "0.982",
            "0.999 / 0.194 %p", "0.998 / 0.410 mm", "0.981 / 0.521 N", "1,317"],
           ["D: Gate-MoE + GRU", "1.000", "0.999 / 0.123 %p", "0.999 / 0.318 mm",
            "0.995 / 0.263 N", "1,061"]],
          caption=t("표 3. 절제 실험(D4, 사이클 단위 held-out). † 모델 B는 접촉·비접촉을 구분하지 않으므로 "
                    "힘(N)이 아니라 통합 위치(mm)를 출력한다. F/T 센서 잡음은 ±0.19 N이다.",
                    "Table 3. Ablation study (D4, cycle-wise held-out). † Model B does not "
                    "distinguish contact from non-contact and therefore outputs a unified "
                    "position (mm) rather than a force (N). The F/T sensor noise is "
                    "±0.19 N."),
          widths=[4.2, 2.2, 3.0, 3.0, 3.0, 1.6])
    para(doc, L, t(
        "네 가지를 관찰할 수 있다. 첫째, 접촉 판정 자체는 어려운 문제가 아니다. 이력 피처 없이도 정확도 "
        "98.2 %가 나오며, 접촉 순간 ΔL과 ΔR이 뚜렷하게 꺾이기 때문이다. 둘째, 이력 피처(SLS-EMA)의 이득은 "
        "변형률보다 접촉력 예측에 집중된다. 모델 C와 A를 비교하면 힘 RMSE가 0.521 N에서 0.253 N으로 절반 "
        "이하가 되는 반면 변형률 RMSE 개선은 0.194에서 0.108 %p에 그친다. 셋째, 게이트–전문가 구조의 기여는 "
        "모델 B와 A의 비교에서 드러난다. 통합 모델은 근접거리는 잘 맞추지만 변형률 RMSE가 0.288 %p로 2.7배 "
        "나쁘다. 접촉 구간과 비접촉 구간의 인장 응답이 서로 다르기 때문이다. 넷째, GRU(모델 D)는 정확도에서 "
        "EMA 기반 모델과 사실상 동률이지만 압력 전문가 파라미터가 306개로 가장 작았다. 즉 사람이 τ를 골라 "
        "EMA로 넣어준 정보를 순환 신경망이 더 작은 표현으로 스스로 압축해낸 것이다. 그럼에도 본 연구는 배포 "
        "모델로 A를 선택했는데, X-CUBE-AI에서 Dense 레이어의 지원 성숙도가 높고 호출 간 은닉 상태 관리가 "
        "필요 없어 양자화 시 오차 누적 위험이 없기 때문이다.",
        "Four observations follow. First, contact detection is not the hard part: even "
        "without history features accuracy reaches 98.2 %, because ΔL and ΔR bend sharply "
        "at the instant of contact. Second, the benefit of the history features (SLS-EMA) "
        "is concentrated in force rather than strain prediction: comparing models C and A, "
        "the force RMSE falls from 0.521 N to 0.253 N, less than half, whereas the strain "
        "RMSE improves only from 0.194 to 0.108 %p. Third, the contribution of the "
        "gate-expert structure appears in the comparison of models B and A: the unified "
        "model predicts distance well but its strain RMSE of 0.288 %p is 2.7× worse, "
        "because the strain response differs between the contact and non-contact regimes. "
        "Fourth, the GRU (model D) is essentially tied with the EMA-based models in "
        "accuracy while using only 306 parameters for the pressure expert — the recurrent "
        "network compressed, into a smaller representation, the same information supplied "
        "manually through a hand-chosen τ. Model A was nonetheless selected for deployment "
        "because dense layers are the most mature path in X-CUBE-AI and require no hidden "
        "state to be carried between calls, eliminating the risk of error accumulation "
        "under quantization."), align="j")

    # ── 7. 임베디드 구현 ────────────────────────────────────────────────────
    heading(doc, L, t("7. 임베디드 구현", "7. Embedded Implementation"), 1)
    heading(doc, L, t("7.1 배포 파이프라인", "7.1 Deployment Pipeline"), 2)
    para(doc, L, t(
        "학습된 scikit-learn[30] 모델은 skl2onnx로 ONNX로 변환한 뒤 ST의 stedgeai 도구[29]로 STM32용 C 코드로 "
        "생성하였다. sklearn과 ONNX 사이의 수치 검증 오차는 게이트 1e−6, 전문가 1e−5 미만이었다. "
        "StandardScaler는 ONNX 그래프에 포함하지 않고 평균·표준편차 상수만 헤더로 추출하여 펌웨어에서 직접 "
        "정규화하도록 했으며, 게이트·전문가 A·전문가 B가 각각 독립적으로 적합된 스케일러를 사용하므로 헤더에는 "
        "세 벌의 상수가 들어간다. 펌웨어에서는 매 TDM 주기마다 moe_inference_run(ΔL, ΔR)이 한 번 호출되고, "
        "게이트 → EMA 갱신 → 전문가 순으로 실행된 뒤 결과가 UART로 스트리밍된다. 추론 시간은 DWT 사이클 "
        "카운터로 직접 측정한다.",
        "The trained scikit-learn [30] models were converted to ONNX with skl2onnx and then "
        "generated as STM32 C code with ST's stedgeai tool [29]. Numerical verification between "
        "scikit-learn and ONNX agreed to better than 1e−6 for the gate and 1e−5 for the "
        "experts. The StandardScaler was not embedded in the ONNX graph; instead the mean "
        "and scale constants were exported as a C header and normalization is performed "
        "directly in firmware. Because the gate and the two experts use independently "
        "fitted scalers, three constant sets appear in the header. In firmware, "
        "moe_inference_run(ΔL, ΔR) is called once per TDM cycle and executes gate → EMA "
        "update → expert in that order, after which the result is streamed over UART. "
        "Inference time is measured directly with the DWT cycle counter."), align="j")

    heading(doc, L, t("7.2 자원 사용량과 지연", "7.2 Resource Usage and Latency"), 2)
    para(doc, L, t(
        "표 4은 임베디드 구현의 자원 사용량을 정리한 것이다. MoE 모델은 전체 가중치가 5.7 KB에 불과해 캐시에 "
        "상주하며, 실측 지연이 중앙값 260.4 µs, 95 백분위수 262.5 µs로 1 ms 주기 안에서 여유 있게 완결된다. "
        "지연의 산포가 2 µs 수준에 불과하다는 점은 이 구조가 결정론적 제어 루프에 사용될 수 있음을 뜻한다. "
        "참고로 동일 추론을 PC에서 수행할 경우 USB 왕복 지연만 20–40 ms가 발생하며 지터도 ±5–15 ms에 이른다. "
        "즉 이 시스템에서 엣지 추론은 성능 최적화가 아니라 실시간 동작을 위한 요건이다.",
        "Table 4 summarizes the resource usage of the embedded implementation. The MoE "
        "model has only 5.7 KB of weights, which stay resident in cache, and its measured "
        "latency is 260.4 µs median with a 95th percentile of 262.5 µs, completing "
        "comfortably within the 1 ms period. That the spread is only about 2 µs means the "
        "architecture is usable in a deterministic control loop. By comparison, performing "
        "the same inference on a host PC incurs 20–40 ms of USB round-trip delay with "
        "±5–15 ms of jitter; edge inference in this system is therefore a requirement for "
        "real-time operation rather than a performance optimization."), align="j")
    table(doc, L,
          [t("항목", "Item"),
           t("2단 INT8 (초기 배포)", "Two-stage INT8 (first)"),
           t("medium-deep float32", "medium-deep float32"),
           t("MoE float32 (최종)", "MoE float32 (final)")],
          [[t("파라미터 수", "Parameters"), "50,306", "978", "1,413"],
           [t("MACs / 추론", "MACs per inference"), "50,306", "1,062",
            t("2,510 (게이트 202 + 전문가 1,154)",
              "2,510 (gate 202 + expert 1,154)")],
           [t("가중치 ROM", "Weight ROM"), "~52 KB", "3,912 B", "5.66 KB"],
           [t("활성화 SRAM", "Activation SRAM"), "15.3 KB", "288 B", "368 B"],
           [t("전체 플래시 (펌웨어 포함)", "Total flash (with firmware)"),
            "112.5 KB (85.8 %)", t("~68 KB (추정)", "~68 KB (est.)"), "83.5 KB (65.2 %)"],
           [t("추론 지연 (DWT 실측)", "Inference latency (DWT)"),
            "1,068 µs", "141 µs", t("260 µs (중앙값) / 263 µs (p95)",
                                    "260 µs median / 263 µs p95")],
           [t("TDM 주기 내 완결", "Completes within TDM period"),
            t("아니오", "no"), t("예", "yes"), t("예", "yes")]],
          caption=t("표 4. STM32G473CBT6(170 MHz, 플래시 128 KB, SRAM 32 KB) 임베딩 자원 비교.",
                    "Table 4. Embedded resource comparison on the STM32G473CBT6 (170 MHz, "
                    "128 KB flash, 32 KB SRAM)."),
          widths=[4.0, 4.2, 3.4, 4.2])

    heading(doc, L, t("7.3 실기에서만 드러난 실패 모드",
                      "7.3 A Failure Mode Visible Only on Hardware"), 2)
    para(doc, L, t(
        "최초 배포한 게이트는 EMA를 포함한 4입력 구조로, 오프라인 held-out 정확도가 100.0 %였다(표 3 모델 A). "
        "그러나 보드를 실제로 눌렀다 떼자 게이트가 접촉 해제 후에도 한동안 접촉 판정을 유지하는 현상이 "
        "나타났다. 원인은 학습 조건과 배포 조건의 불일치였다. 학습 시 EMA는 실제 접촉 라벨(z 기준)이 바뀌는 "
        "정확한 순간에 리셋되도록 만들어졌지만, 배포된 보드에는 그 정답이 없으므로 게이트 자신의 판단이 바뀌면 "
        "리셋한다는 근사로 대체할 수밖에 없었다. 그 결과 다음과 같은 자기강화 루프가 형성되었다. 접촉을 "
        "해제하면 원시 ΔL·ΔR은 즉시 변하지만 EMA는 τ ≈ 1 s 동안 눌린 값에 머물고, 게이트가 그 오래된 EMA를 "
        "함께 보고 계속 접촉으로 판단하며, 판단이 바뀌지 않으니 리셋 조건도 걸리지 않는다. 실제로 학습 데이터의 "
        "평균 압력 유지 시간이 약 0.6초로 EMA 시간상수보다 짧았다는 점도 이 불일치를 키웠다.",
        "The gate deployed first had four inputs including the EMA features and achieved "
        "100.0 % held-out accuracy offline (model A in Table 3). When the board was "
        "physically pressed and released, however, the gate kept reporting contact for some "
        "time after release. The cause was a mismatch between the training and deployment "
        "conditions. During training the EMA was reset at the exact instant the true "
        "contact label (from z) changed, but the deployed board has no such ground truth "
        "and had to approximate it by resetting whenever the gate's own decision changed. "
        "This produced a self-reinforcing loop: on release the raw ΔL and ΔR change "
        "immediately while the EMA remains at the pressed value for about τ = 1 s; the "
        "gate, observing that stale EMA, continues to report contact; and because its "
        "decision does not change, the reset condition is never triggered. The mismatch was "
        "aggravated by the fact that the mean press duration in the training data was about "
        "0.6 s, shorter than the EMA time constant itself."), align="j")
    para(doc, L, t(
        "해결책은 게이트를 EMA 없는 2입력 구조로 되돌리는 것이었다. 접촉 여부는 본래 즉각적인 물리적 전환이므로 "
        "평활할 이유가 없고, 이렇게 하면 루프 자체가 성립하지 않는다. 아울러 펌웨어 실행 순서를 게이트 먼저 → "
        "그 결과로 이번 사이클에 즉시 EMA 리셋 여부 결정 → 전문가 실행으로 바꾸어 기존의 한 사이클 지연도 "
        "제거하였다. 회귀 정확도에 실제로 도움이 되는 전문가 A·B는 4입력을 유지하였다. 이 교체로 오프라인 "
        "게이트 정확도는 100.0 %에서 98.2 %로 낮아졌고 전체 파라미터도 1,429개에서 1,413개로 바뀌었지만, 실기 "
        "동작은 정상화되었다. 오프라인 지표가 배포 조건에서 재현 불가능한 가정에 의존하고 있었다는 점에서, 이 "
        "사례는 임베디드 검증이 오프라인 평가를 대체할 수 없음을 보여준다.",
        "The remedy was to revert the gate to a two-input form without EMA features. "
        "Contact is an inherently instantaneous physical transition with no reason to be "
        "smoothed, and with this change the loop cannot form. The firmware execution order "
        "was also changed to gate first, then an immediate same-cycle decision on whether "
        "to reset the EMA, then the expert, removing the previous one-cycle delay. Experts "
        "A and B, where history genuinely helps regression, retained their four inputs. The "
        "substitution lowered offline gate accuracy from 100.0 % to 98.2 % and changed the "
        "total parameter count from 1,429 to 1,413, but restored correct behaviour on "
        "hardware. Because the offline metric relied on an assumption that cannot be "
        "reproduced at deployment, this case shows that embedded validation cannot be "
        "replaced by offline evaluation."), align="j")

    # ── 8. 실시간 검증 ──────────────────────────────────────────────────────
    heading(doc, L, t("8. 실시간 검증", "8. Real-Time Validation"), 1)
    heading(doc, L, t("8.1 검증 프로토콜", "8.1 Validation Protocol"), 2)
    para(doc, L, t(
        "검증은 학습에 쓰인 세션과 별개로 수행한 세 개의 연속 세션(D5)에서 이루어졌다. 각 세션은 세 부분으로 "
        "구성된다. Part 1(0–398 s)에서는 변형률을 단계적으로 고정한 채 Z축을 25 mm에서 접촉까지 반복 "
        "왕복시키고, Part 2(400–730 s)에서는 근접거리를 고정한 채 변형률을 0–30 %로 반복 스윕하며, "
        "Part 3(738 s 이후)에서는 두 축을 동시에 움직인다. 이 구성은 각 축이 단독으로 변할 때와 동시에 변할 "
        "때의 성능을 분리해 관찰하기 위한 것이다. 보고하는 모든 수치는 보드가 UART로 내보낸 자체 추정값과 "
        "스테이지·F/T 센서의 참값을 비교한 것이며, PC에서 어떠한 후처리 추론도 수행하지 않았다.",
        "Validation was performed on three continuous sessions (D5) acquired separately "
        "from those used for training. Each session has three parts. In Part 1 (0–398 s) "
        "the strain is held at stepped values while the Z axis repeatedly travels between "
        "25 mm and contact; in Part 2 (400–730 s) the distance is held fixed while the "
        "strain is swept repeatedly over 0–30 %; and in Part 3 (from 738 s) both axes move "
        "together. This structure isolates the performance when each axis varies alone from "
        "that when both vary. All reported figures compare the board's own estimates, "
        "streamed over UART, against stage and F/T ground truth; no post-hoc inference was "
        "performed on the PC."), align="j")
    figure(doc, L, "fig6_realtime.png", t(
        "그림 7. 실기 실시간 디커플링(세션 0819-153948, 809 s). (a) 보드가 1 kHz로 취득해 100 Hz로 로깅한 "
        "원시 TDM 신호. (b) 변형률: 회색이 참값, 주황이 보드 추정. (c) 근접거리: 게이트가 비접촉으로 판정한 "
        "구간만 표시. (d) 접촉력: 접촉 판정 구간만 표시. 점선은 Part 경계이다.",
        "Fig. 7. On-hardware real-time decoupling (session 0819-153948, 809 s). (a) Raw TDM "
        "signals acquired on the board at 1 kHz and logged at 100 Hz. (b) Strain: grey is "
        "ground truth, orange the on-board estimate. (c) Distance, shown only where the "
        "gate reports non-contact. (d) Contact force, shown only where the gate reports "
        "contact. Dotted lines mark the Part boundaries."))

    heading(doc, L, t("8.2 구간별 결과", "8.2 Part-Wise Results"), 2)
    para(doc, L, t(
        "그림 7과 표 5가 결과를 요약한다. Part 1에서는 세 물리량이 모두 잘 복원된다. 두 번째 세션 기준으로 "
        "변형률 R² = 0.981(RMSE 1.37 %p), 근접거리 R² = 0.940(RMSE 2.11 mm)이며, 게이트 정확도는 98.3 %였다. "
        "그림 8의 패리티 플롯에서 보듯 추정값이 대각선을 따라 분포한다. 접촉력은 세션에 따라 R² 0.430–0.777로 "
        "편차가 컸는데, 이는 두 번째 세션의 접촉 샘플 수가 2,185개로 적고 최대 힘이 7.8 N에 그쳐 분산이 작았던 "
        "영향이 크다.",
        "Figure 7 and Table 5 summarize the results. In Part 1 all three quantities are "
        "recovered well: in the second session, strain reached R² = 0.981 (RMSE 1.37 %p) "
        "and distance R² = 0.940 (RMSE 2.11 mm), with 98.3 % gate accuracy. The parity "
        "plots of Fig. 8 show the estimates distributed along the diagonal. Contact force "
        "varied more between sessions (R² = 0.430–0.777), largely because the second "
        "session contained only 2,185 contact samples with a maximum force of 7.8 N and "
        "therefore lower variance."), align="j")
    figure(doc, L, "fig7_parity.png", t(
        "그림 8. Part 1 구간의 패리티 플롯(세션 0819-153948). (a) 변형률, (b) 근접거리, (c) 접촉력. "
        "점선은 이상적 대각선이다.",
        "Fig. 8. Parity plots for Part 1 (session 0819-153948): (a) strain, (b) distance, "
        "(c) contact force. Dashed lines show the ideal diagonal."))
    table(doc, L,
          [t("구간", "Segment"), t("변형률 R² / RMSE", "Strain R² / RMSE"),
           t("근접거리 R² / RMSE", "Distance R² / RMSE"),
           t("접촉력 R² / RMSE", "Force R² / RMSE")],
          [[t("Part 1 — 근접만 변화", "Part 1 — proximity only"),
            "0.981 / 1.37 %p", "0.940 / 2.11 mm", "0.430 / 1.86 N"],
           [t("Part 2 — 인장만 변화", "Part 2 — strain only"),
            "0.492 / 6.97 %p", "−0.797 / 6.19 mm", "—"],
           [t("Part 3 — 동시 변화", "Part 3 — simultaneous"),
            "0.602 / 6.27 %p", "−2.051 / 10.40 mm", "—"],
           [t("전체(참고)", "Whole session (reference)"),
            "0.780 / 4.78 %p", "0.488 / 5.59 mm", "0.430 / 1.86 N"]],
          caption=t("표 5. 실기 실시간 성능(세션 0819-153948). 각 Part는 상대 축이 실제로 움직인 순간을 "
                    "±1 s 여유를 두고 제외한 순수 구간 기준이다. 게이트 정확도 98.3 %.",
                    "Table 5. On-hardware real-time performance (session 0819-153948). Each "
                    "Part excludes, with a ±1 s guard band, the instants at which the other "
                    "axis was actually moving. Gate accuracy 98.3 %."),
          widths=[4.6, 4.0, 4.0, 3.2])
    para(doc, L, t(
        "인장·근접만 다루던 이전 단계의 2단계 디커플러에 대해서도 학습·PC 실시간·임베디드 실시간 세 조건을 "
        "비교하였다(표 6). PC 기반 추론이 학습 오차보다 낮게 나온 것은 실시간 궤적이 학습 분포의 중앙 영역에 "
        "집중되었기 때문이며, 임베디드 추론은 INT8 양자화와 실시간 잡음의 영향으로 다소 열화된다. 그럼에도 "
        "유효 근접 범위(d ≤ 10 mm)에서 임베디드 오차는 0.669 mm로, 근접 감지 용도로는 충분한 수준이다.",
        "For the earlier two-stage decoupler, which handled only strain and proximity, the "
        "three conditions of training, PC real-time and embedded real-time were also "
        "compared (Table 6). PC-based inference scored better than the training error "
        "because the real-time trajectory concentrated in the central region of the "
        "training distribution, while embedded inference degrades somewhat under INT8 "
        "quantization and real-time noise. Even so, within the useful proximity range "
        "(d ≤ 10 mm) the embedded error was 0.669 mm, adequate for proximity detection."),
        align="j")
    table(doc, L,
          [t("지표 / 구간", "Metric / range"), t("학습 오차", "Training"),
           t("PC 실시간", "PC real-time"), t("임베디드 실시간", "Embedded real-time")],
          [[t("변형률 MAE", "Strain MAE"), "0.343 %", "0.208 %", "0.422 %"],
           [t("변형률 RMSE", "Strain RMSE"), "0.432 %", "0.272 %", "0.519 %"],
           [t("근접 MAE (전체)", "Distance MAE (all)"), "1.783 mm", "1.438 mm", "2.281 mm"],
           [t("근접 MAE (d ≤ 15 mm)", "Distance MAE (d ≤ 15 mm)"), "—", "0.145 mm",
            "0.867 mm"],
           [t("근접 MAE (d ≤ 10 mm)", "Distance MAE (d ≤ 10 mm)"), "—", "0.096 mm",
            "0.669 mm"]],
          caption=t("표 6. 2단계 디커플러(인장·근접)의 학습 / PC 실시간 / 임베디드 실시간 오차 비교.",
                    "Table 6. Training, PC real-time and embedded real-time errors for the "
                    "two-stage (strain and proximity) decoupler."),
          widths=[4.6, 3.4, 3.6, 4.2])

    heading(doc, L, t("8.3 준정적 구간의 성능 저하와 원인",
                      "8.3 Degradation in Quasi-Static Segments and Its Cause"), 2)
    para(doc, L, t(
        "Part 2와 Part 3에서 근접거리 추정의 R²가 음수로 떨어졌다. 음수 R²는 예측이 단순 평균보다 못하다는 "
        "뜻이므로 그대로 보고할 필요가 있다. 다만 이 구간에서 근접거리는 사실상 고정되어 있어 정답의 분산 "
        "자체가 매우 작다. R² = 1 − RMSE²/Var(y)이므로 분모가 작으면 절대 오차가 작아도 R²가 크게 나빠진다. "
        "실제로 Part 2의 근접 RMSE는 6.19 mm로, Part 1의 2.11 mm보다 3배가량 큰 데 그친다. 그럼에도 이 저하는 "
        "실재하며, 근접 신호가 준정적일 때 인덕턴스에 남는 정보가 잡음 수준으로 줄어든다는 사실을 보여준다. "
        "이는 6.1절에서 확인한 근접 오차의 이분산 특성과 같은 뿌리를 갖는다.",
        "In Parts 2 and 3 the R² of the distance estimate became negative. A negative R² "
        "means the prediction is worse than the mean and must be reported as such. In these "
        "segments, however, the distance is essentially fixed, so the variance of the "
        "ground truth is very small. Since R² = 1 − RMSE²/Var(y), a small denominator "
        "degrades R² sharply even when the absolute error is modest: the distance RMSE in "
        "Part 2 was 6.19 mm, only about three times the 2.11 mm of Part 1. The degradation "
        "is nonetheless real and shows that, when the proximity signal is quasi-static, the "
        "information remaining in the inductance falls to the noise level. This shares a "
        "root with the heteroscedastic distance error identified in Section 6.1."),
        align="j")
    para(doc, L, t(
        "원인을 좁히기 위해 동일한 원시 ΔL·ΔR을 PC에서 float64로 재현하여 같은 게이트·EMA·라우팅 논리를 "
        "적용해 보았다. 게이트 판단은 임베디드와 100 % 일치했으므로 분류 단계는 원인이 아니다. 반면 회귀 "
        "단계에서는 PC 재현이 Part 2 근접 R²를 −0.797에서 0.225로, Part 3을 −2.051에서 −0.230으로 개선했다. "
        "sklearn과 ONNX의 수치 검증 오차가 1e−5 수준이므로 부동소수점 정밀도만으로는 이 격차를 설명할 수 없다. "
        "가장 유력한 원인은 EMA 재구성 방식의 차이다. 보드는 1 ms마다 들어오는 모든 원시 샘플로 EMA를 "
        "갱신하므로 그 사이의 잡음까지 전부 반영하는 반면, PC 재현은 로깅 과정에서 5분의 1로 데시메이션된 값만 "
        "보고 연속시간 근사식으로 그 사이를 매끄럽게 건너뛴다. 실제 신호가 잡음보다 훨씬 큰 Part 1에서는 두 "
        "방식의 차이가 묻히지만, 신호가 거의 없는 Part 2·3에서는 PC 쪽이 인위적으로 더 안정적으로 보이게 된다. "
        "이는 PC가 물리적으로 더 정확하다는 뜻이 아니라, 잡음이 지배하는 구간에서 평활의 정도가 지표에 그대로 "
        "반영된다는 뜻이다.",
        "To narrow the cause, the same raw ΔL and ΔR were replayed on a PC in float64 with "
        "identical gate, EMA and routing logic. Gate decisions matched the embedded ones "
        "100 %, so the classification stage is not responsible. In the regression stage, "
        "however, the PC replay improved the Part 2 distance R² from −0.797 to 0.225 and "
        "Part 3 from −2.051 to −0.230. Since scikit-learn and ONNX agree to about 1e−5, "
        "floating-point precision alone cannot explain the gap. The most plausible cause is "
        "a difference in how the EMA is reconstructed: the board updates the EMA from every "
        "raw sample arriving each millisecond and therefore absorbs all the noise in "
        "between, whereas the PC replay sees only values decimated by a factor of five "
        "during logging and interpolates smoothly across the gaps with a continuous-time "
        "approximation. Where the true signal greatly exceeds the noise (Part 1) the "
        "difference is masked; where there is almost no signal (Parts 2 and 3) the PC "
        "appears artificially more stable. This does not mean the PC is physically more "
        "accurate — it means that, in noise-dominated segments, the degree of smoothing "
        "propagates directly into the metric."), align="j")

    # ── 9. 논의 ─────────────────────────────────────────────────────────────
    heading(doc, L, t("9. 논의", "9. Discussion"), 1)
    para(doc, L, t(
        "본 연구의 결과는 단일 전극 멀티모달 센싱에서 무엇이 이미 가능하고 무엇이 아직 한계인지를 비교적 "
        "분명하게 나눈다. 가능한 것부터 정리하면 다음과 같다. 첫째, 두 가닥 배선만으로 세 신호를 1 kHz로 "
        "취득하는 것은 상용 부품과 6층 기판으로 충분히 구현 가능하며, DMA 기반 ISR 설계로 CPU 유휴율 93.9 %를 "
        "유지할 수 있다. 둘째, 도체 표적에 대해서는 R–ε 단독 의존성이라는 물리적 비대칭이 실제로 성립하며, "
        "이를 모델 구조에 반영하면 동일 파라미터 예산에서 종단 모델보다 우수하다. 셋째, 1,413 파라미터 규모의 "
        "모델로도 세 물리량을 동시에 추정할 수 있고, 이 정도 크기는 캐시에 상주하므로 260 µs라는 결정론적 "
        "지연을 얻는다. 넷째, 접촉 영역의 점탄성처럼 겉보기에 모델링을 방해하는 현상도, 물리 모델로 시간상수를 "
        "규명한 뒤 계산 비용이 거의 없는 이력 피처로 환원하면 오히려 정확도를 높이는 정보가 된다.",
        "The results delineate fairly clearly what is already achievable in "
        "single-electrode multimodal sensing and what remains limited. On the achievable "
        "side: first, acquiring three signals at 1 kHz through only two wires is entirely "
        "feasible with commercial components on a six-layer board, and a DMA-based ISR "
        "design sustains 93.9 % CPU idle. Second, for conductive targets the physical "
        "asymmetry of strain-only dependence in R genuinely holds, and encoding it in the "
        "architecture outperforms an end-to-end model at equal parameter budget. Third, a "
        "model of only 1,413 parameters suffices to estimate three quantities "
        "simultaneously, and at that size the weights stay resident in cache, yielding a "
        "deterministic 260 µs latency. Fourth, a phenomenon that appears to obstruct "
        "modelling — the viscoelasticity of the contact regime — becomes information that "
        "improves accuracy once its time constant is identified with a physical model and "
        "reduced to a history feature of negligible computational cost."), align="j")
    para(doc, L, t(
        "한계도 분명하다. 첫째, 근접 추정은 표적이 도체일 때만 실용적이다. 그림 3c에서 확인했듯 유전체 "
        "표적에서는 인덕턴스에 실리는 근접 정보가 미약하다. 둘째, 근접거리가 준정적인 구간에서 성능이 크게 "
        "저하된다(8.3절). 이는 모델의 결함이라기보다 단일 채널에 실린 정보량의 한계에 가깝다. 셋째, 접촉력 "
        "추정 정확도는 정답으로 사용한 F/T 센서의 잡음(±0.19 N)에 근접해 있어, 이보다 낮은 오차를 주장하려면 "
        "더 정밀한 기준 계측이 선행되어야 한다. 넷째, TENG 채널은 취득만 하고 디커플러 입력으로 사용하지 "
        "않았다. 접촉 이벤트 검출은 게이트가 ΔL·ΔR만으로 98 % 이상 해내므로 현재로서는 TENG의 추가 가치가 "
        "확인되지 않았으나, 미세 접촉이나 동적 텍스처 인식에서는 유용할 수 있다. 다섯째, 압축 시 Q-factor "
        "저하로 인한 겉보기 효과를 별도로 보정하지 않았다. 학습 기반 디커플러가 이를 흡수하지만, R_s를 별도로 "
        "측정할 수 있게 되면 물리적으로 더 정확한 인덕턴스 복원이 가능해질 것이다.",
        "The limitations are equally clear. First, proximity estimation is practical only "
        "for conductive targets; as Fig. 3c shows, a dielectric target imprints little "
        "proximity information on the inductance. Second, performance degrades "
        "substantially where the distance is quasi-static (Section 8.3) — less a defect of "
        "the model than a limit on the information carried by a single channel. Third, the "
        "accuracy of the force estimate approaches the ±0.19 N noise of the F/T sensor used "
        "as ground truth, so claiming lower error would require more precise reference "
        "instrumentation first. Fourth, the TENG channel was acquired but not used as a "
        "decoupler input: since the gate already detects contact events with over 98 % "
        "accuracy from ΔL and ΔR alone, no additional value from TENG has yet been "
        "demonstrated, although it may prove useful for light touch or dynamic texture "
        "recognition. Fifth, the apparent effect of the falling Q factor under compression "
        "was not separately corrected; the learned decoupler absorbs it, but physically "
        "more accurate inductance recovery would become possible if R_s could be measured "
        "independently."), align="j")
    para(doc, L, t(
        "향후 방향은 네 가지다. (i) AC 등가 직렬 저항 R_s의 추가 취득. 현재 TDM은 AC 여기에서 공진 주파수만 "
        "읽는데, 같은 슬롯에서 R_s까지 얻으면 그림 1c의 시그니처가 완성되어 도체와 유전체를 부호로 구분할 수 "
        "있고, 5.2절의 Q-factor 보정도 직접 가능해진다. (ii) 다중 주파수 임피던스 측정. 여러 주파수에서 "
        "임피던스의 실수부·허수부를 얻으면 재질 구분과 근접 추정을 동시에 개선할 수 있고, 8.3절의 준정적 구간 "
        "문제도 추가 채널로 완화될 여지가 있다. (iii) 2차원 변형 분해. 직사각형 나선은 x축과 y축에 대해 비대칭 "
        "감도를 가지며, ΔL이 (Δl, ΔA, Δd)의 함수인 반면 ΔR은 Δl만의 함수이므로 L과 R이 서로 다른 유효 고유 "
        "방향(effective eigen-direction)을 갖는다. 이를 이용하면 단일 전극에서 2축 변형을 분리할 수 있을 "
        "것으로 예상되며, 십자형 시편과 4축 대칭 스테이지는 이미 그 준비를 마친 상태다. (iv) 순환 구조로의 "
        "전환. 표 3에서 GRU는 EMA 기반 모델과 동등한 정확도를 306 파라미터로 달성했다. X-CUBE-AI의 순환 레이어 "
        "지원과 은닉 상태 리셋 논리, 양자화 안정성을 이 보드에서 검증하는 것이 다음 과제다.",
        "Four directions follow. (i) Additional acquisition of the AC equivalent series "
        "resistance R_s. The present TDM reads only the resonant frequency during AC "
        "excitation; obtaining R_s in the same slot would complete the signature of "
        "Fig. 1c, allowing conductors and dielectrics to be distinguished by sign and "
        "enabling the Q-factor correction of Section 5.2 to be applied directly. "
        "(ii) Multi-frequency impedance measurement. Obtaining the real and imaginary parts "
        "of the impedance at several frequencies could improve material discrimination and "
        "proximity estimation together, and the extra channels may also mitigate the "
        "quasi-static problem of Section 8.3. (iii) Two-dimensional strain decomposition. A "
        "rectangular spiral has asymmetric sensitivity along its x and y axes, and since ΔL "
        "is a function of (Δl, ΔA, Δd) whereas ΔR depends on Δl alone, L and R possess "
        "different effective eigen-directions. This should permit biaxial strain to be "
        "separated from a single electrode; the cruciform specimen and the four-axis "
        "symmetric stage are already in place for it. (iv) Migration to a recurrent "
        "structure. In Table 3 the GRU matched the EMA-based models with 306 parameters; "
        "verifying X-CUBE-AI's recurrent-layer support, hidden-state reset logic and "
        "quantization stability on this board is the next task."), align="j")

    # ── 10. 결론 ────────────────────────────────────────────────────────────
    heading(doc, L, t("10. 결론", "10. Conclusion"), 1)
    para(doc, L, t(
        "두 가닥 단일 전극 EGaIn 나선 코일에서 시분할 측정으로 인덕턴스·저항·마찰전기 전압을 1 ms 주기로 "
        "취득하고, 이를 임베디드 AI로 실시간 디커플링하는 멀티모달 센싱 시스템을 설계·제작·검증하였다. 브리징 "
        "공정으로 나선을 두 가닥 배선으로 완결하고, 돌기 구조로 압력 민감도를 약 10배 높였다. 도체 표적에 대한 "
        "격자 측정으로 저항이 변형률에만 의존하고 인덕턴스가 변형률과 근접거리에 함께 의존한다는 물리적 "
        "비대칭을 정량적으로 확인하였으며, 접촉 모달리티에서는 표준선형고체 모델로 점탄성 완화(τ ≈ 1.0 s)를 "
        "규명하여 인과적 EMA 이력 피처로 반영하고, 압축 시 인덕턴스가 증가해 보이는 현상이 Q-factor 저하에 "
        "따른 역산 겉보기 효과임을 밝혔다. 최종 디커플러는 1,413 파라미터의 SLS-EMA + Gate-MoE 구조로, "
        "STM32G473 위에서 매 TDM 주기마다 중앙값 260 µs 만에 추론을 완료한다. 근접이 실제로 변하는 구간에서 "
        "실기 성능은 변형률 R² = 0.981, 근접거리 R² = 0.940, 게이트 정확도 98 %였으며, 근접이 준정적인 "
        "구간에서는 신호 대 잡음비 한계로 성능이 저하됨을 함께 보고하였다. 본 연구는 단일 전극 멀티모달 센서가 "
        "PC 없이 자율적으로 동작할 수 있음을 실기로 보였으며, 동시에 오프라인 지표만으로는 임베디드 성능을 "
        "담보할 수 없다는 점을 구체적 실패 사례와 함께 제시하였다.",
        "A multimodal sensing system was designed, built and validated in which inductance, "
        "resistance and triboelectric voltage are acquired every millisecond by "
        "time-division measurement from a two-wire single-electrode EGaIn spiral coil and "
        "decoupled in real time by embedded AI. A bridging step completes the spiral as a "
        "two-wire structure, and a bump array raises the pressure sensitivity roughly "
        "tenfold. Gridded measurements against a conductive target quantitatively confirmed "
        "the physical asymmetry whereby resistance depends on strain alone while inductance "
        "depends on both strain and distance. In the contact regime, a standard linear "
        "solid model identified a viscoelastic relaxation (τ ≈ 1.0 s) that was encoded as a "
        "causal EMA history feature, and the apparent increase of inductance under "
        "compression was shown to be an inversion artefact of the falling Q factor. The "
        "final decoupler is a 1,413-parameter SLS-EMA + Gate-MoE network that completes "
        "inference on the STM32G473 in a median of 260 µs once per TDM cycle. Where the "
        "proximity axis actually moved, on-hardware accuracy reached R² = 0.981 for strain "
        "and R² = 0.940 for distance with 98 % gate accuracy; degradation in quasi-static "
        "proximity segments, caused by the signal-to-noise limit, is reported alongside. "
        "The work demonstrates on real hardware that a single-electrode multimodal sensor "
        "can operate autonomously without a host PC, and shows through a concrete failure "
        "case that offline metrics alone cannot guarantee embedded performance."),
        align="j")

    # ── 참고문헌 ────────────────────────────────────────────────────────────
    heading(doc, L, t("참고문헌", "References"), 1)
    para(doc, L, t(
        "주의: 아래 목록은 본 연구 과정에서 실제로 참조한 자료이며, 일부 항목의 권·호·페이지는 투고 전 원문으로 "
        "확인·보완해야 한다.",
        "Note: the following list records the sources actually consulted during this work; "
        "volume, issue and page details for some entries must be verified against the "
        "originals before submission."), size=8.5, italic=True)
    from refs import REFS as refs
    for i, r in enumerate(refs, 1):
        para(doc, L, "[%d] %s" % (i, r), size=9, space_after=3)
