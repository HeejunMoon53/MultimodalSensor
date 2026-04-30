# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.


## Git 워크플로우

작업이 마무리될 때마다 커밋 여부를 물어본다. 커밋 시 변경 내용을 한글로 간결하게 요약한 메시지로 `git add . → git commit → git push`를 순서대로 실행한다.

---

## 프로젝트 개요

**연구 제목**: Embedded AI-Driven Soft Multimodal Single-Electrode Sensor for Proximity, Tactile, and 2D-Strain Sensing

**연구자**: 문희준 (HeeJun Moon) | BioRobotics & Control Lab (BiRC), 고려대학교 기계공학과

---

### 연구 배경 및 동기

- 로봇공학·인간-기계 상호작용 발전으로 인간과 유사한 촉각 인식 능력이 요구됨
- 유연 센서는 굴곡 접촉·대형 변형·웨어러블 응용에 적합하나, 기존 멀티모달 센서는 **신호 결합(Signal Coupling)** 문제로 독립 측정이 어려움
- 기존 디커플링 방법(재료 설계·구조 설계·AI 기반)은 고가 장비 의존, 복잡한 구조, 대규모 데이터 필요 등 한계가 있음
- 기존 인덕티브 센서 연구는 최대 2가지 모달리티(L/R 조합)만 측정 가능하며 LCR 미터 등 대형 계측 장비 필요

---

### 핵심 아이디어

단일 전극(2선) EGaIn 스파이럴 코일에서 TDM(Time Division Measurement)으로 **L, R_DC, V_TENG** 3종 신호를 ~1ms 주기로 취득하고, PINN 기반 Edge-AI로 실시간 디커플링한다.

| 측정 신호 | 의존성 | 포함 정보 |
|---|---|---|
| 인덕턴스 L(ε, d) | 변형률 + 근접거리 | 인장 변형 + 근접 거리 |
| DC 저항 R_DC(ε) | 변형률만 | 인장 변형 (도미넌트) |
| TENG 전압 V | 접촉 이벤트 | 접촉 감지 |

**주요 혁신**:
- 연속적 사전-사후 접촉 공간 인식 (평면형·신축성 진정한 단일 전극)
- 독립적 임베디드 구현 (PC 불필요, STM32 단독 동작)
- PINN으로 발산 없는 디커플링 + 물리 제약 기반 데이터 효율 극대화

---

### 물리 모델

**센서 전극**: EGaIn DIW(Direct Ink Writing) 평면 직사각형 스파이럴 코일 (추후 형태 변경 가능)

이론 모델:
- `R_DC(ε) = R_DC,0 × (1 + ε²)`
- `L(ε,d) = L_self(ε) − ω²M(ε,d)²·Lt / (Rt² + ω²Lt²)`
- `R_s(ε,d) = R_DC(ε) + ω²M(ε,d)²·Rt / (Rt² + ω²Lt²)`

경험적 피팅 모델:
- `ΔR/R₀ = α₁ε + α₂ε²`
- `ΔL/L₀ = β₁ε + β₂/(d+d₀)ᵏ + β₃ε·f(d)`

**해석적 역산의 한계**:
1. 비선형성(초월함수)으로 인한 심각한 절단 오차
2. 극단 조건(근거리·대변형)에서 야코비안 특이점 → 수치 발산
→ PINN 솔루션으로 해결

---

### 2D-Strain 측정 원리 (향후 확장)

직사각형 스파이럴의 x/y 비대칭 감도 활용:
- `ΔL = f(Δl, ΔA, Δd)` → x/y 방향 변형 모두 반영
- `ΔR = f(Δl)` → 총 길이 변화만 반영
- L과 R이 **서로 다른 유효 고유 방향(effective eigen-direction)** 을 가짐 → 2축 변형 분해 가능
- 어레이/적층 구조 확장 시 3D 변형 측정으로 발전 가능

---

### PINN 디커플링 모델

**2단계 Physics-Guided 구조**:
- Stage 1: ΔR → ε̂ (저항은 변형률에만 지배적)
- Stage 2: (ΔL, ε̂) → d̂ (인덕턴스로 근접거리 추정)

**Loss 함수**:
```
Loss_Total = Loss_Data + λ·Loss_Physics
Loss_Physics = (1/N)·Σ[(ΔR − R_theory(ε̂))² + (ΔL − L_theory(ε̂,d̂))²]
```

**배포 목표**: STM32 Edge-AI 임베딩 (X-CUBE-AI INT8, PC 불필요, O(1) 지연)

---

### 데이터셋

- 센서 초기 길이: 120mm
- 변형률: 0→36mm (약 30% strain), 1mm 간격, 37회 시험
- 각 시험: **고정 변형률 + 근접도 50mm→0mm 연속 스윔** (변형+근접 동시 자극 데이터)
- 스테퍼 모터 가감속 보상, 시공간 동기화 완료
- 데이터 위치: `0332_DecouplingTest_TXTFiles/strain0.txt ~ strain36.txt` (분석 스크립트: `graphcode.py`, `graphcode2.py`, `graphcode3.py`)
- 코일 해석 스크립트: `Analysis/fringing_3d.py`
- 세미나 자료: `Docs/26.03.27_세미나_문희준.pdf`
- 출력 포맷 (CSV): `LDC_freq, R_DC_filtered, TENG_filtered, R_DC_raw, TENG_raw`

---

### 연구 진행 단계

| 단계 | 내용 | 상태 |
|---|---|---|
| Part 1 | 센서 제작, PCB 설계, 소프트웨어 개발, 테스트 플랫폼 구축 | ✅ 완료 |
| Part 2 | 복합 신호 취득, 신호 디커플링 분석, 데이터셋 설계, 모델 학습 | 🔄 진행 중 |
| Part 3 | Edge-AI 임베딩, 실시간 추론, 응용 시나리오, 최종 통합 | ⏳ 예정 |

---

### 현재 논의 중인 결정 사항 (2026-04-30 기준)

아래 5가지 항목을 순서대로 결정해야 한다. 각 항목은 이전 결정에 종속된다.

| # | 항목 | 상태 |
|---|---|---|
| 1 | **물리량·모달리티·어플리케이션 결정** — 어떤 신호를 측정하고 무엇을 감지할 것인가 | 🔄 논의 중 |
| 2 | **회로 재설계** — 결정된 물리량을 수집하기 위한 PCB 재설계 | ⏳ 대기 |
| 3 | **데이터 수집 계획** — 실험 프로토콜, 변수 범위, 동시 자극 시나리오 | ⏳ 대기 |
| 4 | **모델 설계 및 학습 방법** — Embedded 가능한 경량 모델 구조, PINN 등 | ⏳ 대기 |
| 5 | **테스트 및 실시간 임베디드 구현** — STM32 Edge-AI 배포, 실시간 검증 | ⏳ 대기 |

---

### 미래 방향

1. **다중 주파수 임피던스 측정 검토**: 현재 LDC1614 공진 주파수 단일 값(L)만 취득 중. 향후 고주파/저주파 여러 주파수에서 임피던스 실수부·허수부를 측정하는 방식으로 전환하면 물체 재질 인식(물체 인식)과 근접도를 동시에 더 높은 정밀도로 추정 가능. PCB 재설계 또는 별도 임피던스 분석 IC 적용 고려 중.

2. **무선 전력 전송 + 통신 동시 수행**: 코일 특성을 활용하여 TDM 내에 무선전력 전송(배터리 충전)·신호 송수신·센싱 슬롯을 분리 운용 (어플리케이션 수준).

3. **2D/3D 변형 측정**: 직사각형 스파이럴의 축별 비대칭 감도를 이용해 단일 전극에서 2D 변형 분해. 어레이·적층 구조로 3D 변형 확장.

4. **크롤링 로봇**: 단일 센서로 모든 모달리티 자가 인지 + 셀프 충전.

5. **Weakly electric fish 유사 감지**: 원거리 물체·재질 인식.

6. **터치리스 인터페이스 / 로봇 안전 센서**: 비접촉 근접 감지 기반 응용.

---

### 하위 프로젝트 구성

1. **`Switching_testing_26.01.01/`** — STM32G473CBT6 펌웨어 (STM32CubeIDE): TDM 방식으로 DC 저항, TENG 전압, 인덕턴스를 최대 4채널 동시 측정
2. **`26.03.10_Tensile_Tester/`** — Python GUI + Arduino 펌웨어: 5축 스테핑 모터 포지셔닝 스테이지 (데이터 취득용 커스텀 인장 시험기)

---

## PCB 설계 (Multisignal Switching Board)

**파일 위치**: `PCB/Gerber_PCB_PCB_Multisignal_Switching_25.12.19_2026-01-05_2026-04-29.zip` (추후 수정 예정)

### 기본 사양

| 항목 | 내용 |
|---|---|
| CAD 툴 | EasyEDA Pro v2.2.47.7 |
| 보드 크기 | 약 65mm × 52mm |
| 층 구성 | 6층 (Top / Inner1~4 / Bottom) |
| 설계 단위 | mm |

### 회로 구성 요약

이 PCB는 TDM(Time Division Multiplexing) 방식으로 **L / R_DC / TENG** 3종 신호를 최대 4채널 동시 취득하는 전용 보드다.

1. **STM32G473CBT6** — TIM7(1ms) 기반 TDM 사이클 구동, I2C DMA + ADC DMA 병렬 실행
2. **LDC1614** — 센서 코일의 공진 주파수(28-bit)를 I2C2로 읽어 인덕턴스 계산
3. **ADG734 MUX** — GPIO(PB2/PB10/PB11/PB15)로 신호 경로를 LDC / TENG / R 모드로 전환
4. **OPAmp** — ADC 입력 신호 버퍼링 (채널당 1개)
5. **USB2UART** — PC 없이 단독 동작 가능하지만 데이터 스트리밍 시 사용

### 주요 부품

- `U1` — STM32G473CBT6 (메인 MCU)
- `U2` — LDC1614 (인덕턴스 측정, I2C2, addr 0x2A)
- `U3~U8` — ADG734 (아날로그 MUX) + OPAmp (4채널)
- `SENSORCAP1~5` — LDC1614 공진 회로용 커패시터
- `X1` — 크리스탈 오실레이터

---

## Build & Flash

### STM32 Firmware (`Switching_testing_26.01.01/`)
- **IDE**: STM32CubeIDE (Windows). Open the `.project` file in the `Switching_testing_26.01.01/` directory.
- **Build**: Project → Build Project (or Ctrl+B). Output is `Debug/Switching_testing_26.01.01.elf`.
- **Flash**: Run/Debug configuration is in `Switching_testing_26.01.01 Debug.launch`. Uses ST-LINK.
- **Peripheral config**: Re-generated from `Switching_testing_26.01.01.ioc` (STM32CubeMX). Do not manually edit HAL-generated files in `Core/Src/` other than within `/* USER CODE BEGIN/END */` blocks.
- **Serial monitor**: USART2 at 115200 baud (PA2/PA3). `printf` is redirected to USART2 via `_write()` in `main.c`.

### Python GUI (`26.03.10_Tensile_Tester/`)
```powershell
pip install pyserial pyqt5 pyqtgraph openpyxl numpy
python "26.03.10_Tensile_Tester/Positioning_Stage_Controller_V3.2.py"
# 동기화 데이터 취득 UI (STM32 + Arduino 통합)
python "26.03.10_Tensile_Tester/SyncAcquisition_UI.py"
```

### Arduino Firmware
- Open `26.03.10_Tensile_Tester/Positioning_Stage_Firmware_V3.2_Arduino/Positioning_Stage_Firmware_V3.2_Arduino.ino` in Arduino IDE.
- Requires: `AccelStepper` library.
- Target board: Arduino Uno (or compatible), 115200 baud.

---

## TDM Firmware Architecture

### Sensor Measurement Cycle (ISR-Driven, Non-Blocking)

TDM 주기 1ms, CPU Idle 93.9%. Every `TDM_PERIOD_TIME_US` (default 1000 µs), **TIM7** fires `TDM_Handle_Timer_Main_ISR()`, which launches two parallel tasks:

1. **I2C DMA path**: Reads LDC1614 resonant frequency data (28-bit) over I2C2 using chained DMA reads (MSB then LSB per channel). Each DMA completion triggers `TDM_Handle_I2C_RxCplt()`, which chains the next read until all channels are done, then sets `flag_i2c_done`. (settling 6µs, total ~200µs)

2. **ADC DMA path**: Switches the ADG734 analog MUX to TENG mode, starts ADC DMA on hadc1–hadc5, and starts **TIM6**. After `TENG_MEASURE_TIME_US` (100 µs), TIM6 fires `TDM_Handle_Timer_ADC_ISR()`, which captures TENG data, switches MUX to R (resistance) mode (switching 29ns), and re-arms TIM6. After `R_DC_MEASURE_TIME_US` (100 µs), the same ISR captures R data and sets `flag_adc_seq_done`.

Both paths race to completion. Whichever finishes last sets `g_SensorData.update_flag = 1` and returns `tdm_state` to `TDM_STATE_IDLE`. Main loop polls `update_flag` and transmits data via UART.

### Key Configuration Constants (`Core/Inc/TDM.h`)

| Constant | Default | Effect |
|---|---|---|
| `ACTIVE_SENSOR_COUNT` | 1 | Number of active sensor channels (1–4) |
| `TDM_PERIOD_TIME_US` | 1000 | Full TDM cycle period (µs); sets TIM7 period |
| `TENG_MEASURE_TIME_US` | 100 | ADC sampling window for TENG (µs) |
| `R_DC_MEASURE_TIME_US` | 100 | ADC sampling window for R (µs) |

### MUX Switching (ADG734 on GPIOB)

| GPIO | Pin | Function |
|---|---|---|
| SW1 | PB2 | LDC vs ADC signal path (S1A/S1B) |
| SW2 | PB10 | LDC vs ADC signal path (S2A/S2B) |
| SW3 | PB11 | Inject R reference voltage (R0_VD) |
| SW4 | PB15 | Ground ADC input (ADCIN0_B to GND) |

- `Set_MUX_LDC()`: SW1/SW2 HIGH, SW3/SW4 LOW → sensor connected to LDC coil path
- `Set_MUX_TENG()`: all LOW → sensor floating for TENG voltage measurement
- `Set_MUX_R()`: SW3/SW4 HIGH → voltage divider engaged for DC resistance measurement

### LDC1614 (Inductance Sensor IC)

- I2C address: `0x2A`, bus: I2C2
- Shutdown pin: PA10 (active LOW = operating)
- INT pin: PA11 (EXTI, currently unused in TDM flow — polling is replaced by DMA timing)
- 28-bit result: `(MSB_reg[11:0] << 16) | LSB_reg[15:0]`
- Data proportional to resonant frequency: `f ∝ 1/√L`, so inductance ratio = `(f_base/f_current)²`

### ADC Channels

Each sensor channel maps to one ADC/OPAMP pair. With `ACTIVE_SENSOR_COUNT=1`:
- Channel 0: hadc1 (OPAMP1 output) for sensor 0

hadc2/hadc3/hadc5 are only started/stopped when `ACTIVE_SENSOR_COUNT >= 2/3/4`.

### Output Format

`TDM_Print_Filter_Comparison()` outputs CSV over UART:
```
ldc_ch[0], r_dc_adc[0], teng_adc[0], r_raw, teng_raw
```
IIR filtering is applied: alpha=0.2 for TENG, alpha=0.02 for R.

---

## Tensile Tester Architecture

### Serial Protocol (Arduino ↔ Python)

Commands sent from Python (newline-terminated):

| Command | Action |
|---|---|
| `ABS:XA:steps:speed` | Absolute move (can chain axes: `ABS:XA:s:v:XB:s:v:...`) |
| `JOG:XA:steps:speed` | Relative move on one axis |
| `POS?` | Query position → response: `POS:xa:xb:ya:yb:z:a0:a1:a2:a3:a4:a5` |
| `ZERO:0` | Set all axes to position 0 |
| `EN:0` / `EN:1` | Free / Lock motor drivers |
| `RESET_EMG` | Clear emergency-stop state |

Arduino responses: `DONE` (move complete), `ALARM:LIMIT` (limit switch hit), `ALARM:CLEARED`.

### Motor Mapping (Arduino pins)

5 axes (XA, XB, YA, YB, Z), each with STEP/DIR pins. All axes have `setPinsInverted(true)` for direction. Shared enable pin: D12 (LOW = locked).

### Position Conversion

`steps_per_mm = (200 steps/rev × microstep) / screw_pitch_mm`

Default: 200 × 8 / 5.0 = 320 steps/mm (configurable via Settings window).
