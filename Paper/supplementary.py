# -*- coding: utf-8 -*-
"""Paper/supplementary.py — 부록(Supplementary Information) 본문."""
from build_paper import bullets, eq, heading, para, table


def build(doc, L):
    def t(ko, en):
        return ko if L == "ko" else en

    doc.add_page_break()
    para(doc, L, t("부록 — 보충 자료", "Supplementary Information"),
         size=15, bold=True, align="c", space_after=4)
    para(doc, L, t(
        "본문에서 결론에 직접 필요하지 않아 제외했으나, 재현과 후속 연구에 필요한 세부 사항을 정리한다.",
        "Details omitted from the main text as not directly required for the conclusions, "
        "but needed for reproduction and follow-up work."),
        size=9, italic=True, align="c", space_after=12)

    # S1 하드웨어
    heading(doc, L, t("S1. 하드웨어 사양 상세", "S1. Detailed Hardware Specifications"), 1)
    table(doc, L,
          [t("항목", "Item"), t("사양", "Specification")],
          [[t("센서 전극", "Sensing electrode"),
            t("EGaIn 액체금속, DIW 인쇄, 평면 직사각형 나선 코일, 2선 단일 전극",
              "EGaIn liquid metal, DIW-printed planar rectangular spiral coil, two-wire "
              "single electrode")],
           [t("센서 초기 길이", "Initial sensor length"), "120 mm"],
           [t("인장 범위", "Strain range"), t("0–36 mm (0–30 %)", "0–36 mm (0–30 %)")],
           [t("근접 측정 범위", "Proximity range"),
            t("0–52 mm (금속) / 0–30 mm (손)", "0–52 mm (metal) / 0–30 mm (hand)")],
           [t("접촉력 범위", "Contact-force range"), t("0–10.1 N", "0–10.1 N")],
           [t("MCU", "MCU"),
            "STM32G473CBT6, Cortex-M4F @ 170 MHz, 128 KB flash, 32 KB SRAM"],
           [t("인덕턴스 IC", "Inductance IC"),
            t("LDC1614, I2C2, 주소 0x2A, 28비트, SD 핀 PA10, INT 핀 PA11",
              "LDC1614, I2C2, address 0x2A, 28-bit, SD pin PA10, INT pin PA11")],
           [t("아날로그 MUX", "Analog MUX"),
            t("ADG734 ×4, 제어 GPIO PB2/PB10/PB11/PB15, 전환 29 ns",
              "ADG734 ×4, control GPIO PB2/PB10/PB11/PB15, 29 ns switching")],
           [t("PCB", "PCB"),
            t("65 × 52 mm, 6층, EasyEDA Pro v2.2.47.7",
              "65 × 52 mm, six layers, EasyEDA Pro v2.2.47.7")],
           [t("UART", "UART"), t("USART2 @ 115,200 baud (PA2/PA3)",
                                 "USART2 at 115,200 baud (PA2/PA3)")],
           [t("TDM 파라미터", "TDM parameters"),
            t("주기 1000 µs (TIM7), TENG 150 µs, R 150 µs, LDC I²C ~200 µs, 정착 6 µs",
              "period 1000 µs (TIM7), TENG 150 µs, R 150 µs, LDC I²C ~200 µs, settling 6 µs")],
           [t("시험 스테이지", "Test stage"),
            t("5축 스테퍼(XA/XB/YA/YB/Z), Arduino + AccelStepper, 320 step/mm, 115,200 baud",
              "five-axis stepper (XA/XB/YA/YB/Z), Arduino + AccelStepper, 320 steps/mm, "
              "115,200 baud")],
           [t("힘 기준", "Force reference"),
            t("6축 F/T 센서, 세션별 비접촉 구간 평균으로 영점 보정, 잡음 ±0.19 N",
              "six-axis F/T sensor, zeroed session-wise on the non-contact mean, "
              "noise ±0.19 N")]],
          widths=[4.4, 11.4])

    # S2 아키텍처 탐색 전체 표
    heading(doc, L, t("S2. 아키텍처 탐색 전체 결과", "S2. Complete Architecture Search Results"), 1)
    para(doc, L, t(
        "모든 후보는 동일한 2단계 구조(1단계 ΔR→ε, 2단계 [ΔL, ε]→d)와 Tanh 활성화를 사용하며, INT8 플래시 "
        "요구량은 파라미터당 1 바이트로 추정하였다.",
        "All candidates use the same two-stage structure (stage 1: ΔR → strain; stage 2: "
        "[ΔL, strain] → d) with tanh activations; INT8 flash requirement is estimated at one "
        "byte per parameter."), size=9)
    rows = [
        ["nano", "1-4-1", "2-8-1", "46", "32", "0.381", "2.115", "0.806"],
        ["tiny", "1-8-1", "2-16-1", "90", "64", "0.363", "2.110", "0.781"],
        ["tiny-asym", "1-8-1", "2-32-1", "154", "112", "0.368", "1.978", "0.561"],
        ["tiny-deep", "1-4-4-1", "2-8-8-1", "138", "112", "0.352", "1.837", "0.394"],
        ["small", "1-16-1", "2-16-8-1", "242", "200", "0.351", "1.802", "0.348"],
        ["small-sym", "1-16-8-1", "2-16-8-1", "370", "320", "0.349", "1.798", "0.346"],
        ["base", "1-16-8-1", "2-32-16-1", "818", "744", "0.349", "1.782", "0.322"],
        ["base-asym", "1-8-1", "2-32-16-1", "666", "608", "0.350", "1.785", "0.326"],
        ["medium-deep", "1-16-8-4-1", "2-32-16-8-1", "978", "892", "0.352", "1.765", "0.322"],
        ["base-s2+", "1-16-8-1", "2-64-32-1", "2,482", "2,360", "0.349", "1.781", "0.317"],
        ["medium", "1-32-16-1", "2-64-32-1", "2,914", "2,768", "0.352", "1.779", "0.312"],
        ["medium-asym", "1-16-8-1", "2-128-64-1", "8,882", "8,664", "0.350", "1.774", "0.318"],
        ["large", "1-64-32-1", "2-128-64-1", "10,946", "10,656", "0.349", "1.773", "0.313"],
        [t("sklearn(초기 배포)", "sklearn (first deployment)"), "1-128-128-64-1",
         "2-128-128-64-1", "50,306", "49,664", "0.344", "1.783", "0.301"],
    ]
    table(doc, L,
          [t("이름", "Name"), t("1단계", "Stage 1"), t("2단계", "Stage 2"),
           t("파라미터", "Param."), "MACs", t("MAE ε (%)", "MAE strain (%)"),
           t("MAE d (mm)", "MAE d (mm)"), t("MAE d≤15 (mm)", "MAE d≤15 (mm)")],
          rows, widths=[2.8, 2.4, 2.6, 1.8, 1.6, 1.7, 1.7, 1.8], size=8)

    # S3 물리 파라미터
    heading(doc, L, t("S3. 학습된 물리 파라미터와 물리식 역산의 한계",
                      "S3. Learned Physical Parameters and Limits of Physics-Only Inversion"), 1)
    para(doc, L, t(
        "PINN 학습으로 얻은 경험식 계수는 다음과 같다(D3 기준). α₁ = 55.535, α₂ = 26.676, β₁ = 15.434, "
        "β₂ = 4.255, β₃ = −2.367, d₀ = 7.547 mm, k = 0.0027. d₀와 k는 softplus를 통해 양수로 제약하여 "
        "d → 0에서의 특이점을 회피하였다.",
        "The empirical coefficients obtained by PINN training (on D3) are: α₁ = 55.535, "
        "α₂ = 26.676, β₁ = 15.434, β₂ = 4.255, β₃ = −2.367, d₀ = 7.547 mm, k = 0.0027. The "
        "parameters d₀ and k are constrained positive through a softplus to avoid the "
        "singularity as d approaches zero."), size=9.5)
    para(doc, L, t(
        "접촉 영역에서 ε×F 교차항을 포함한 물리식을 직접 역산한 실험(후보 C4)에서는, 전방향 피팅 자체는 "
        "R² = 0.955로 양호했으나 역산 결과는 정답 변형률을 알려준 조건에서도 R² = 0.714, 추정 변형률을 사용한 "
        "실제 조건에서는 R² = 0.263에 그쳤다. 품질이 낮은 데이터를 포함했을 때는 변형률 0 근처에서 R² = −75까지 "
        "발산하였다. 이는 조건수 23의 선형 근사(5.3절)와 일치하는 결과로, 물리식은 학습을 보조하는 제약항으로는 "
        "유효하나 그 자체로 안정적인 역산 수단이 아님을 보여준다.",
        "In an experiment that inverted the physics expression including the strain-force "
        "cross term directly (candidate C4), the forward fit itself was good (R² = 0.955), but "
        "inversion gave R² = 0.714 even when the true strain was supplied and only R² = 0.263 "
        "under realistic conditions using the estimated strain. When lower-quality data were "
        "included, the inversion diverged to R² = −75 near zero strain. This is consistent "
        "with the condition number of 23 found in Section 5.3 and shows that the physics "
        "expression is useful as a training constraint but not as a stable inversion tool by "
        "itself."), size=9.5)

    # S4 툴체인
    heading(doc, L, t("S4. 임베디드 변환 툴체인에서 마주친 문제와 해결",
                      "S4. Toolchain Issues Encountered During Embedded Conversion"), 1)
    table(doc, L,
          [t("문제", "Issue"), t("원인", "Cause"), t("해결", "Resolution")],
          [[t("stedgeai 경로 오류", "stedgeai path error"),
            t("40자 이상의 긴 경로", "paths longer than 40 characters"),
            t("C:\\ai\\xe\\ 로 복사해 단축", "copied to a short path C:\\ai\\xe\\")],
           [t("cp949 인코딩 오류", "cp949 encoding error"),
            t("한국어 Windows 로케일", "Korean Windows locale"),
            t("사전 양자화된 ONNX 사용", "used a pre-quantized ONNX file")],
           [t("MatMulInteger 미지원", "MatMulInteger unsupported"),
            t("quantize_dynamic 사용", "use of quantize_dynamic"),
            t("quantize_static + QDQ 형식으로 변경",
              "switched to quantize_static with QDQ format")],
           [t("플래시 오버플로우", "flash overflow"),
            t("-O0 컴파일 + 52 KB 가중치", "-O0 compilation with 52 KB of weights"),
            t(".cproject 최적화 옵션을 -Og로 변경",
              "changed the .cproject optimization option to -Og")],
           [t("PyTorch DLL 로드 실패", "PyTorch DLL load failure"),
            t("Windows 260자 경로 길이 제한", "the Windows 260-character path limit"),
            t("C:\\ml_env 짧은 경로에 가상환경 재구성",
              "rebuilt the virtual environment at the short path C:\\ml_env")]],
          widths=[4.6, 5.4, 5.8], size=8.5)

    # S5 데이터 취득 프로토콜
    heading(doc, L, t("S5. 데이터 취득 프로토콜 상세", "S5. Detailed Acquisition Protocols"), 1)
    bullets(doc, L, [
        t("P1(변형 이산 고정 + 근접 연속 스윕): 변형 19단계(0, 2, …, 36 mm), 근접 스윕 속도 5 mm/s(접근) / "
          "10 mm/s(복귀), 레벨당 1회, 금속 19 CSV(27,123행) + 손 19 CSV(18,611행).",
          "P1 (discrete strain, continuous proximity sweep): 19 strain levels (0, 2, ..., "
          "36 mm); sweep at 5 mm/s approaching and 10 mm/s returning; one repetition per "
          "level; 19 CSV files for metal (27,123 rows) and 19 for hand (18,611 rows)."),
        t("P2(근접 이산 고정 + 변형 연속 스윕): 근접 13단계, 변형 스윕 2 mm/s(인장) / 10 mm/s(복귀), "
          "레벨당 2회, 금속 26 CSV(18,510행) + 손 26 CSV(18,505행).",
          "P2 (discrete proximity, continuous strain sweep): 13 proximity levels; strain "
          "sweep at 2 mm/s stretching and 10 mm/s returning; two repetitions per level; "
          "26 CSV files for metal (18,510 rows) and 26 for hand (18,505 rows)."),
        t("D4(접촉 프로토콜): Z축이 25 mm → 0 mm → −1.2 mm → 0 mm → 25 mm로 한 번 왕복하는 것을 1 사이클로 "
          "하고, 사이클마다 변형률을 한 단계 올려 총 19 사이클을 수행. F/T 센서로 접촉력을 동시 기록.",
          "D4 (contact protocol): one cycle is a single Z traverse of 25 mm -> 0 mm -> "
          "-1.2 mm -> 0 mm -> 25 mm; the strain is advanced one step per cycle for 19 cycles "
          "in total, with contact force recorded simultaneously by the F/T sensor."),
        t("분할 규칙: 시간적으로 인접한 샘플의 누설을 막기 위해 샘플 단위가 아니라 사이클 단위로 held-out을 "
          "구성하였다(5 사이클 중 1개). D3에서는 파일 단위 대신 2D 격자 균등 샘플링 후 무작위 분할을 사용했다.",
          "Splitting rule: to prevent leakage between temporally adjacent samples, held-out "
          "sets were formed cycle-wise rather than sample-wise (one cycle in five). For D3, "
          "2-D grid-uniform sampling followed by a random split was used instead."),
        t("주의 사항: 초기 분석에서 원점 복귀(homing) 구간과 변형률 전환 램프가 한 사이클 안에 섞여 들어가 "
          "성능이 과소평가된 사례가 있었다. 사이클 정의를 변형률 변화 기준으로 바꾸고 최소 길이 500행을 "
          "요구하자 근접 R²가 0.982에서 0.9989로 정정되었다.",
          "Caveat: in an early analysis, homing motions and strain-transition ramps were "
          "grouped inside a single cycle and the performance was underestimated. Redefining "
          "cycles by changes in strain and requiring a minimum length of 500 rows corrected "
          "the proximity R² from 0.982 to 0.9989."),
    ], size=9.5)

    # S6 용어
    heading(doc, L, t("S6. 용어 정리", "S6. Glossary"), 1)
    items = [
        ("TDM", t("시분할 측정. 하나의 센서를 짧은 시간 단위로 나누어 여러 물리량을 순차 측정하는 방식.",
                  "Time-division measurement: sequentially measuring several quantities from "
                  "one sensor within short time slots.")),
        ("EMA", t("지수이동평균. 최근 값에 큰 가중치를 주는 인과적 평활로, 재귀식 한 줄로 구현된다.",
                  "Exponential moving average: causal smoothing that weights recent samples "
                  "more heavily, implemented as a single recursion.")),
        ("MoE", t("Mixture-of-Experts. 게이트가 상황을 분류하고 상황별 전문가 모델이 회귀를 담당하는 구조.",
                  "Mixture of experts: a gate classifies the situation and regime-specific "
                  "expert models perform the regression.")),
        ("SLS", t("표준선형고체. 즉시 반응하는 탄성 성분과 시간 지연을 갖는 점성 성분을 결합한 점탄성 모델.",
                  "Standard linear solid: a viscoelastic model combining an instantaneous "
                  "elastic component with a time-delayed viscous component.")),
        ("PINN", t("물리 정보 신경망. 학습 손실에 물리 방정식 잔차를 제약으로 추가하는 방법.",
                   "Physics-informed neural network: a method that adds the residual of a "
                   "physical equation to the training loss as a constraint.")),
        ("Q-factor", t("공진의 날카로움 지표. 낮으면 공진 주파수 판독 잡음이 커진다.",
                       "Quality factor: a measure of resonance sharpness; a low value "
                       "increases the noise in reading the resonant frequency.")),
        (t("조건수", "Condition number"),
         t("역산 문제가 입력 잡음에 얼마나 민감한지를 나타내는 값. 1에 가까울수록 안정적이다.",
           "A measure of how sensitive an inversion is to input noise; values near one are "
           "stable.")),
        ("INT8 PTQ", t("학습 후 8비트 정수 양자화. 가중치 크기를 4배 줄이고 정수 연산 가속을 활용한다.",
                       "Post-training 8-bit integer quantization: reduces weight size "
                       "fourfold and enables integer-arithmetic acceleration.")),
    ]
    table(doc, L, [t("용어", "Term"), t("설명", "Definition")], items,
          widths=[3.0, 12.8], size=9)

    # S7 코드/데이터 위치
    heading(doc, L, t("S7. 코드 및 데이터 위치", "S7. Code and Data Locations"), 1)
    bullets(doc, L, [
        t("펌웨어: TDMFirmware/ (TDM.c, LDC1614.c, moe_inference.c, nn_inference.c)",
          "Firmware: TDMFirmware/ (TDM.c, LDC1614.c, moe_inference.c, nn_inference.c)"),
        t("시험 플랫폼: 26.03.10_Tensile_Tester/ (Python GUI + Arduino 펌웨어)",
          "Test platform: 26.03.10_Tensile_Tester/ (Python GUI and Arduino firmware)"),
        t("데이터셋: nn_decoupling/data/, nn_decoupling/data_acquisition/, "
          "nn_decoupling/pressure_0805test/test0805_dataset/, "
          "nn_decoupling/test0816_RealtimeDecoupling/",
          "Datasets: nn_decoupling/data/, nn_decoupling/data_acquisition/, "
          "nn_decoupling/pressure_0805test/test0805_dataset/, "
          "nn_decoupling/test0816_RealtimeDecoupling/"),
        t("모델 학습: nn_decoupling/train_pinn_csv.py, arch_search.py, "
          "test0807_MoEDecoupling/candidate*.py, test0816_RealtimeDecoupling/retrain_moe_v3.py",
          "Model training: nn_decoupling/train_pinn_csv.py, arch_search.py, "
          "test0807_MoEDecoupling/candidate*.py, test0816_RealtimeDecoupling/retrain_moe_v3.py"),
        t("임베디드 변환: nn_decoupling/export_moe_onnx.py, "
          "test0816_RealtimeDecoupling/stm32_deploy_moe_v3/",
          "Embedded conversion: nn_decoupling/export_moe_onnx.py, "
          "test0816_RealtimeDecoupling/stm32_deploy_moe_v3/"),
        t("논문 그림 생성: Paper/make_figures.py",
          "Figure generation for this paper: Paper/make_figures.py"),
    ], size=9.5)
