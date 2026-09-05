# -*- coding: utf-8 -*-
"""Paper/intro.py — 1. 서론 (국문/영문 동시 정의).

인용 번호는 content.py 하단 REFS 목록과 일치해야 한다.
"""
from build_paper import bullets, heading, para, table


def build(doc, L):
    def t(ko, en):
        return ko if L == "ko" else en

    heading(doc, L, t("1. 서론", "1. Introduction"), 1)

    # ── 1.1 멀티모달 인지의 필요성 ──────────────────────────────────────────
    para(doc, L, t(
        "로봇과 인간이 같은 공간을 공유하는 응용이 늘어나면서, 로봇 표면이 주변 상황과 자기 자신의 상태를 함께 "
        "인지할 것이 요구되고 있다[1]. 실제 상호작용에서는 여러 자극이 동시에 작용하기 때문에 단일 물리량만 "
        "측정하는 센서는 현실 상황에서 활용도가 제한된다. 압력과 온도가 저항 드리프트로 함께 나타나거나[2], "
        "다축 힘 성분이 서로 중첩되거나[3], 인장과 근접이 같은 정전용량 변화로 나타나는[4] 사례가 대표적이며, "
        "이처럼 서로 다른 자극이 하나의 전기적 응답에 겹쳐 들어오는 현상을 신호 결합(signal coupling)이라 "
        "한다[5]. 본 연구가 목표로 하는 세 모달리티 — 근접, 접촉력, 인장 — 는 각각 독립적인 필요성을 가지며, "
        "동시에 서로 결합되어 있다는 점에서 함께 다루어져야 한다.",
        "As robots increasingly share workspaces with people, a robot surface is expected "
        "to perceive both its surroundings and its own state [1]. Because several stimuli "
        "act simultaneously in real interaction, a sensor that measures only one physical "
        "quantity has limited practical utility. Representative cases include pressure and "
        "temperature appearing together as resistance drift [2], superposition of "
        "multi-axial force components [3], and strain and proximity both manifesting as the "
        "same capacitance change [4]; this superposition of distinct stimuli onto a single "
        "electrical response is termed signal coupling [5]. The three modalities targeted "
        "here — proximity, contact force and strain — each have an independent motivation, "
        "and at the same time must be treated together because they are mutually coupled."),
        align="j")

    # ── 1.2 각 모달리티의 필요성 ────────────────────────────────────────────
    heading(doc, L, t("1.1 각 모달리티의 필요성", "1.1 Why Each Modality Is Needed"), 2)
    para(doc, L, t(
        "근접(비접촉) 감지는 충돌이 일어나기 전에 개입할 수 있는 유일한 수단이다. 안전한 인간–로봇 물리적 "
        "상호작용(pHRI)에서는 접촉이 발생한 뒤 반응하는 것으로는 충분하지 않으며, 접촉 이전에 물체의 접근을 "
        "예측하고 궤적을 수정해야 한다[6], [7]. 이 때문에 로봇 팔 외피 전면에 근접 센서를 분포시켜 표면 전체에서 "
        "충돌을 회피하거나[8], 레이저 거리계 링을 몸체에 둘러 준전신(quasi whole-body) 감지를 구현하는[9] "
        "연구가 이어져 왔다. 근접 감지는 파지에서도 유용해, 손이 물체에 닿기 전에 자세를 미리 정렬하는 데 쓰인다.",
        "Proximity (non-contact) sensing is the only means of intervening before a "
        "collision occurs. In safe physical human-robot interaction (pHRI), reacting after "
        "contact has already happened is insufficient: the approach of an object must be "
        "anticipated and the trajectory corrected beforehand [6], [7]. This has motivated "
        "work that distributes proximity sensors over the whole exterior of a manipulator "
        "to avoid collisions across its entire surface [8], or wraps laser-ranging rings "
        "around the body for quasi whole-body sensing [9]. Proximity sensing is also useful "
        "in grasping, where it is used to pre-shape the hand before it reaches the object."),
        align="j")
    para(doc, L, t(
        "접촉력 감지는 접촉이 시작된 순간부터 필요해진다. 파지 안정성은 가하는 힘의 크기에 직접 좌우되므로, "
        "촉각 피드백 없이는 물체를 놓치거나 반대로 과도한 힘으로 손상시키기 쉽다[10]. 특히 미끄러짐은 빠르게 "
        "검출하고 보정하지 않으면 곧바로 파지 실패로 이어지기 때문에, 초기 미끄러짐(incipient slip)을 감시하여 "
        "힘을 조절하는 접근이 연구되어 왔다[11]. 즉 근접이 '언제 닿을 것인가'를 다룬다면 접촉력은 '얼마나 세게 "
        "닿아 있는가'를 다루며, 두 정보는 접촉 순간을 경계로 연속적으로 이어져야 한다[12].",
        "Contact-force sensing becomes necessary from the instant contact begins. Grasp "
        "stability depends directly on the magnitude of the applied force, so without "
        "tactile feedback an object is easily dropped or, conversely, damaged by excessive "
        "force [10]. Slip in particular leads immediately to grasp failure unless it is "
        "detected and corrected quickly, motivating approaches that monitor incipient slip "
        "and regulate force accordingly [11]. Where proximity answers when contact will "
        "occur, contact force answers how hard contact is being made, and the two must join "
        "continuously across the moment of contact [12]."), align="j")
    para(doc, L, t(
        "인장(자기수용감각) 감지는 센서가 부착된 몸체 자체가 변형하는 경우에 필수적이다. 소프트 로봇은 사실상 "
        "무한한 자유도를 가지며, 재료의 컴플라이언스와 구동기의 비선형 응답 때문에 개루프 제어만으로 정확한 "
        "작업을 수행하기가 매우 어렵다[13]. 따라서 자신의 형상을 되먹임하는 자기수용감각이 제어 루프를 닫는 "
        "전제 조건이 되며[14], 액체금속 기반 신축 변형 센서를 소프트 크롤링 로봇에 통합해 폐루프 제어를 구현한 "
        "사례가 보고되어 있다[15].",
        "Strain (proprioceptive) sensing is essential whenever the body carrying the sensor "
        "itself deforms. Soft robots possess effectively infinite degrees of freedom, and "
        "the compliance of their materials together with the nonlinear response of their "
        "actuators makes accurate task execution under open-loop control extremely "
        "difficult [13]. Proprioceptive feedback of the robot's own shape is therefore a "
        "precondition for closing the control loop [14], and liquid-metal stretchable "
        "strain sensors have been integrated into soft crawling robots to realize "
        "closed-loop control [15]."), align="j")
    para(doc, L, t(
        "세 모달리티를 같은 지점에서 동시에 얻어야 하는 이유는 단순한 편의가 아니다. 변형하는 표면 위에서는 "
        "근접·접촉 신호의 기준 자체가 변형 상태에 따라 달라지기 때문이다. 본 연구의 측정에서도 인장 상태가 "
        "압력 민감도를 6.6배까지 바꾸는 교차 민감도가 관측되었다(5.3절). 즉 변형률을 모르면 같은 저항 변화가 "
        "어느 정도의 접촉력에 해당하는지 확정할 수 없다. 세 물리량을 각각 별개의 센서로 측정하더라도 이 결합은 "
        "사라지지 않으며, 오히려 서로 다른 위치에서 측정된 값을 정합해야 하는 문제가 추가된다. 따라서 결합이 "
        "발생하는 바로 그 지점에서 세 신호를 동시에 취득하고 함께 디커플링하는 것이 원리적으로 타당한 접근이다.",
        "The need to obtain all three modalities simultaneously at the same location is not "
        "merely a matter of convenience. On a deforming surface, the very reference for the "
        "proximity and contact signals shifts with the deformation state. In the "
        "measurements reported here, the strain state was found to change the pressure "
        "sensitivity by up to a factor of 6.6 (Section 5.3): without knowing the strain, it "
        "is impossible to determine what contact force a given resistance change "
        "corresponds to. Measuring the three quantities with three separate sensors does "
        "not remove this coupling; it merely adds the problem of registering values "
        "measured at different locations. Acquiring the three signals at the very point "
        "where the coupling arises, and decoupling them jointly, is therefore the "
        "principled approach."), align="j")

    # ── 1.3 왜 소프트 단일 전극 센서인가 ────────────────────────────────────
    heading(doc, L, t("1.2 왜 소프트 단일 전극 센서인가",
                      "1.2 Why a Soft Single-Electrode Sensor"), 2)
    para(doc, L, t(
        "센서가 부착될 대상은 곡면이거나 크게 변형하는 표면이다. 강체 센서를 배열하면 이러한 표면에 밀착시킬 수 "
        "없고, 배열 사이의 강성 불연속이 오히려 변형을 방해한다. 유연 센서는 등각 접촉(conformal contact)과 "
        "대변형을 허용하므로 이 제약을 해소하며, 웨어러블 응용으로도 확장된다[4], [16].",
        "The surfaces on which such a sensor must be mounted are curved or undergo large "
        "deformation. An array of rigid sensors cannot conform to them, and the stiffness "
        "discontinuities between elements actively impede deformation. Flexible sensors "
        "permit conformal contact and large deformation, removing this constraint and "
        "extending to wearable applications [4], [16]."), align="j")
    para(doc, L, t(
        "그러나 유연화만으로는 충분하지 않다. 세 모달리티를 세 개의 개별 소자로 구현하면 소자 수에 비례해 배선이 "
        "늘어나고, 적층에 따른 두께 증가와 박리 위험, 인접 소자 간 크로스토크가 뒤따른다[1], [5]. 대면적 전자 "
        "피부에서는 이 배선 복잡도가 실용화의 주된 병목으로 지적되어 왔다. 본 연구가 채택한 접근은 소자 수를 "
        "늘리는 대신 하나의 소자를 시간축에서 나누어 쓰는 것이다. EGaIn 나선 코일 하나에 두 가닥 배선만 연결하고, "
        "여기(excitation) 상태를 바꿔가며 인덕턴스·저항·마찰전기 전압을 순차 취득한다. 소자가 하나뿐이므로 소자 "
        "간 크로스토크가 원리적으로 존재하지 않고, 배선 수는 모달리티 수와 무관하게 2로 고정되며, 평면성과 "
        "신축성이 그대로 유지된다. 코일 형태를 유지한다는 점은 향후 무선 전력 전송이나 통신으로 확장할 여지도 "
        "남긴다.",
        "Flexibility alone, however, is not sufficient. Implementing the three modalities "
        "as three separate devices increases the wiring in proportion to the device count "
        "and brings with it added thickness, delamination risk from stacking, and "
        "cross-talk between neighbouring elements [1], [5]. In large-area electronic skin "
        "this wiring complexity has been identified as a principal bottleneck to practical "
        "deployment. The approach adopted here is to divide one device in time rather than "
        "to multiply devices. A single EGaIn spiral coil is connected through only two "
        "wires, and inductance, resistance and triboelectric voltage are acquired in "
        "sequence as the excitation state is switched. Because there is only one device, "
        "cross-talk between devices cannot arise in principle; the wire count stays fixed "
        "at two regardless of the number of modalities; and planarity and stretchability "
        "are preserved. Retaining a coil geometry also leaves room for later extension to "
        "wireless power transfer or communication."), align="j")

    # ── 1.4 왜 임베디드 AI인가 ──────────────────────────────────────────────
    heading(doc, L, t("1.3 왜 임베디드 AI인가", "1.3 Why Embedded AI"), 2)
    para(doc, L, t(
        "단일 소자에서 세 신호를 얻으면 신호 결합은 하드웨어가 아니라 계산으로 풀어야 한다. 문제는 그 계산을 "
        "어디에서 수행하느냐다. 결합된 관계를 해석적으로 역산하는 방법은 야코비안 특이점에서 발산하므로 "
        "실용적이지 않고(2.3절), 학습 기반 역매핑이 현실적인 대안이 된다. 그런데 데이터 기반 디커플링을 PC에서 "
        "수행하면 매 샘플마다 MCU–PC 왕복이 발생한다. USB 시리얼 링크의 왕복 지연은 20–40 ms, 지터는 "
        "±5–15 ms 수준이다. 접촉 전이(轉移)는 밀리초 단위로 진행되므로 이 지연은 되먹임 제어에 그대로 실패로 "
        "이어진다. 병목은 모델이 아니라 통신 링크에 있으며, 모델을 아무리 빠르게 만들어도 링크를 거치는 한 "
        "해소되지 않는다.",
        "Once three signals are obtained from a single device, the signal coupling must be "
        "resolved computationally rather than in hardware, and the question becomes where "
        "that computation runs. Inverting the coupled relations analytically is impractical "
        "because it diverges at Jacobian singularities (Section 2.3), leaving a learned "
        "inverse mapping as the realistic alternative. Performing data-driven decoupling on "
        "a host PC, however, incurs an MCU-PC round trip for every sample. The round-trip "
        "delay of a USB serial link is 20-40 ms with ±5-15 ms of jitter. Since contact "
        "transitions evolve on a millisecond scale, this delay translates directly into "
        "failure of feedback control. The bottleneck is the communication link rather than "
        "the model, and no amount of model acceleration removes it while the link remains "
        "in the loop."), align="j")
    para(doc, L, t(
        "인덕턴스 계측을 LCR 미터 같은 탁상형 장비에 의존하는 것도 같은 성격의 제약이다. 정밀도는 확보되지만 "
        "이동형·착용형 응용은 불가능해진다. 따라서 계측과 추론을 모두 센서 옆의 마이크로컨트롤러 안에서 끝내는 "
        "구성이 필요하다. 온디바이스 추론은 네트워크 의존성 없이 결정론적인 지연을 제공하고, 배터리 구동이 "
        "가능하며, 데이터를 외부로 내보내지 않는다. 다만 이 선택은 강한 제약을 동반한다. 모델은 플래시 128 KB와 "
        "SRAM 32 KB 안에 들어가야 하고, 1 ms TDM 주기 안에서 취득과 추론을 모두 끝내야 한다. 본 연구에서 모델 "
        "구조를 물리적 비대칭에 맞추어 설계하고 파라미터 수를 1,413개까지 줄인 것은 정확도만을 위한 선택이 "
        "아니라 이 제약에서 출발한 결과다.",
        "Relying on benchtop instruments such as LCR meters for the inductance measurement "
        "is a constraint of the same kind: precision is obtained, but mobile and wearable "
        "applications become impossible. What is needed is therefore a configuration in "
        "which both measurement and inference complete inside a microcontroller beside the "
        "sensor. On-device inference provides deterministic latency without network "
        "dependency, permits battery operation, and keeps data local. This choice carries "
        "hard constraints, however: the model must fit within 128 KB of flash and 32 KB of "
        "SRAM, and acquisition and inference together must finish inside the 1 ms TDM "
        "period. Designing the model structure around the physical asymmetry and reducing "
        "it to 1,413 parameters was thus driven by these constraints, not by accuracy "
        "alone."), align="j")

    # ── 1.5 기존 연구의 한계 ────────────────────────────────────────────────
    heading(doc, L, t("1.4 기존 연구의 한계와 본 연구의 대응",
                      "1.4 Limitations of Prior Work and How This Work Responds"), 2)
    para(doc, L, t(
        "인덕티브 소프트 센서 자체는 활발히 연구되어 왔다. 액체금속 코일을 이용한 고해상도 인장 센서[16], "
        "와전류 효과 기반 촉각 센서[17], 평면 코일 굽힘 센서[18], 마찰전기–인덕티브 하이브리드 물체 인식 "
        "센서[19], 정전용량–인덕턴스 결합 인간–로봇 안전 센서[6], 자기수용감각과 촉각을 함께 얻는 이중 모달 "
        "센서[20], 손끝을 모사한 이방성 액체금속 센서[21] 등이 보고되었다. 그러나 이들 대부분은 디커플링의 "
        "어려움 때문에 인장 또는 자기장 변화 중 한쪽만 단독으로 사용하거나, 두 모달리티까지만 다룬다. 표 1은 "
        "선행 접근들의 한계와 본 연구가 그에 대응하는 방식을 정리한 것이다.",
        "Inductive soft sensors themselves have been studied actively: high-resolution "
        "strain sensors using liquid-metal coils [16], eddy-current tactile sensors [17], "
        "planar-coil bend sensors [18], triboelectric-inductive hybrid sensors for object "
        "recognition [19], safety sensors coupling capacitive and inductive measurement for "
        "pHRI [6], bimodal sensors providing proprioception and tactile sensing [20], and "
        "fingertip-inspired anisotropic liquid-metal sensors [21]. Most of these, however, "
        "use only one of strain or magnetic-field variation because decoupling is "
        "difficult, or address at most two modalities. Table 1 summarizes the limitations "
        "of prior approaches and how the present work responds to each."), align="j")
    table(doc, L,
          [t("선행 접근", "Prior approach"), t("한계", "Limitation"),
           t("본 연구의 대응", "Response in this work")],
          [[t("강체 근접 센서 분포 배치 [8], [9]",
              "Distributed rigid proximity sensors [8], [9]"),
            t("곡면·대변형 표면에 밀착 불가. 배선 수가 센서 수에 비례해 증가",
              "Cannot conform to curved or highly deformable surfaces; wire count scales "
              "with the number of sensors"),
            t("두 가닥 단일 전극의 평면·신축 코일 하나로 대체",
              "Replaced by a single planar, stretchable coil with a two-wire electrode")],
           [t("정전용량형 근접+촉각 유연 센서 [4], [12]",
              "Capacitive proximity and tactile flexible sensors [4], [12]"),
            t("인장과 근접이 동일한 정전용량 변화로 나타나 원리적으로 분리 곤란",
              "Strain and proximity appear as the same capacitance change, so separation is "
              "difficult in principle"),
            t("L은 (ε, d)에, R은 ε에만 의존하는 물리적 비대칭을 이용해 분리",
              "Separated by exploiting the physical asymmetry in which L depends on "
              "(strain, d) while R depends on strain alone")],
           [t("인덕티브 소프트 센서 (단일 모달) [16]–[18], [21]",
              "Inductive soft sensors, single modality [16]–[18], [21]"),
            t("디커플링 난이도 때문에 인장 또는 근접 중 하나만 사용",
              "Use only strain or only proximity because decoupling is hard"),
            t("동일 코일에서 인장·근접·접촉력 3종을 동시 추정",
              "Estimates strain, proximity and contact force simultaneously from the same "
              "coil")],
           [t("다중 소자 하이브리드 통합 [19], [20]",
              "Hybrid integration of multiple devices [19], [20]"),
            t("소자 수만큼 배선·두께·크로스토크 증가",
              "Wiring, thickness and cross-talk grow with the device count"),
            t("소자를 늘리지 않고 1 ms TDM으로 하나의 소자를 시분할 사용",
              "Time-shares one device with a 1 ms TDM schedule instead of adding devices")],
           [t("LCR 미터 기반 인덕턴스 계측 [16], [22]",
              "Inductance measurement with an LCR meter [16], [22]"),
            t("탁상형 계측기 필요. 이동형·착용형 응용 불가",
              "Requires benchtop instrumentation; unsuitable for mobile or wearable use"),
            t("LDC1614를 실은 65 × 52 mm 보드로 대체",
              "Replaced by a 65 × 52 mm board carrying an LDC1614")],
           [t("PC 기반 AI 디커플링",
              "PC-based AI decoupling"),
            t("USB 왕복 20–40 ms, 지터 ±5–15 ms → 접촉 시간축에서 되먹임 제어 불가",
              "20–40 ms USB round trip with ±5–15 ms jitter, precluding feedback control on "
              "contact timescales"),
            t("MCU 온보드 추론, 실측 260 µs, 지연 산포 약 2 µs",
              "On-board MCU inference measured at 260 µs with about 2 µs spread")],
           [t("대규모 학습 데이터·연산을 요구하는 디커플링 모델 [1]",
              "Decoupling models demanding large datasets and computation [1]"),
            t("라벨 취득 비용이 크고 엣지 배포가 어려움",
              "Labelling is costly and edge deployment is difficult"),
            t("물리 구조를 모델에 반영해 1,413 파라미터로 축소",
              "Reduced to 1,413 parameters by encoding the physical structure into the "
              "model")]],
          caption=t("표 1. 선행 접근의 한계와 본 연구의 대응.",
                    "Table 1. Limitations of prior approaches and the response of this "
                    "work."),
          widths=[4.6, 5.6, 5.6])

    # ── 1.6 기여 ────────────────────────────────────────────────────────────
    para(doc, L, t("본 논문의 기여는 다음과 같다.",
                   "The contributions of this paper are as follows."), align="j")
    bullets(doc, L, [
        t("두 가닥 단일 전극 EGaIn 나선 코일에서 L·R·V_TENG 세 신호를 1 ms 주기로 취득하는 TDM 측정 "
          "아키텍처와 전용 6층 PCB, ISR 기반 논블로킹 펌웨어를 제작하였다(CPU 유휴율 93.9 %).",
          "A TDM measurement architecture acquiring L, R and V_TENG every 1 ms from a "
          "two-wire single-electrode EGaIn spiral coil, with a dedicated six-layer PCB and "
          "ISR-driven non-blocking firmware (93.9 % CPU idle)."),
        t("인장 시 중심점이 이동하는 상용 인장 시험기의 한계를 피하기 위해 대칭 4축 인장 + 1축 근접 스테이지를 "
          "제작하고, 6축 F/T 센서와 PC-MCU 시각 동기·정상상태 태깅을 결합한 자동 취득 플랫폼을 구축하였다.",
          "A five-axis platform — four symmetric tensile axes plus one proximity axis — "
          "built to avoid the centre-point drift of commercial tensile testers, combined "
          "with a six-axis force/torque sensor, PC-MCU time synchronization and "
          "steady-state tagging."),
        t("도체·유전체 표적에 대한 (ε, d) 응답 곡면을 격자 측정하여 R–ε 단독 의존성과 L–(ε, d) 결합 의존성을 "
          "정량적으로 입증하고, 두 표적의 부호 차이가 물체 전기적 성질 식별의 단서가 됨을 보였다.",
          "Gridded (strain, distance) response surfaces for conductive and dielectric "
          "targets, quantitatively establishing the strain-only dependence of R and the "
          "joint dependence of L, and showing that the sign difference between the two "
          "targets provides a route to identifying the electrical property of an object."),
        t("접촉 모달리티에서 나타나는 점탄성 완화를 표준선형고체 모델로 규명하고, 압축 시 인덕턴스가 증가해 "
          "보이는 현상이 Q-factor 저하에 의한 역산 겉보기 효과임을 밝혔다.",
          "Identification of the viscoelastic relaxation in the contact regime with a "
          "standard linear solid model, and demonstration that the apparent rise of "
          "inductance under compression is an inversion artefact caused by the falling Q "
          "factor."),
        t("1,413 파라미터 SLS-EMA + Gate-MoE 디커플러를 STM32에 임베딩하여 260 µs 추론을 실측하고, 실기 "
          "검증에서만 드러난 실패 모드(자기강화 EMA 루프)와 그 수정 과정을 보고하였다.",
          "Embedding of a 1,413-parameter SLS-EMA + Gate-MoE decoupler on the STM32 with a "
          "measured 260 µs inference time, and a report of the failure mode revealed only "
          "on hardware (a self-reinforcing EMA loop) together with its correction."),
    ])
