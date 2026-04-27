# CLAUDE.md
 

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

### 핵심 아이디어

단일 전극 소프트 인덕티브 센서에서 **인덕턴스(L), DC 저항(R_DC), TENG 전압(V)** 3가지 신호를 ~1ms 주기(TDM)로 동시 측정하고, PINN(Physics Informed Neural Network) 기반 Edge-AI로 실시간 디커플링한다.

| 측정 신호 | 포함 정보 |
|---|---|
| 인덕턴스 (L) | 인장 변형 + 근접 거리 |
| DC 저항 (R_DC) | 인장 변형 (도미넌트) |
| TENG 전압 (V) | 접촉 감지 |

### 주요 혁신 포인트

- 연속적 사전-사후 접촉 공간 인식 (평면형·신축성 진정한 단일 전극)
- 독립적 임베디드 구현 (PC 불필요, STM32 단독 동작)
- PINN으로 발산 없는 디커플링 + 물리 제약 기반 데이터 효율 극대화

### 연구 진행 단계

| 단계 | 내용 | 상태 |
|---|---|---|
| Part 1 | 센서 제작, PCB 설계, 소프트웨어 개발, 테스트 플랫폼 구축 | ✅ 완료 |
| Part 2 | 복합 신호 취득, 신호 디커플링 분석, 데이터셋 설계, 모델 학습 | 🔄 진행 중 |
| Part 3 | Edge-AI 임베딩, 실시간 추론, 응용 시나리오, 최종 통합 | ⏳ 예정 |

### 현재 결과 요약

- DC 저항(R)은 인장 변형에 지배적으로 반응, 인덕턴스(L)는 인장+근접 모두에 민감
- ∇L(d,ε)와 ∇R(d,ε) 그래디언트가 선형 독립 → 디커플링 수학적으로 가능함을 확인
- 해석적 역산은 야코비안 특이점·비선형성으로 한계 → PINN 솔루션으로 해결 예정
- PINN Loss: `Loss_Total = Loss_Data + λ·Loss_Physics`

### 향후 계획

- PINN 모델 학습·평가 → STM32 Edge-AI 임베딩
- 응용: 크롤링 로봇 자가 인지·자가 충전 / 터치리스 인터페이스 / 로봇 안전 센서

---

### 하위 프로젝트 구성

1. **`Switching_testing_26.01.01/`** — STM32G473CBT6 펌웨어 (STM32CubeIDE): TDM 방식으로 DC 저항, TENG 전압, 인덕턴스를 최대 4채널 동시 측정
2. **`26.03.10_Tensile_Tester/`** — Python GUI + Arduino 펌웨어: 5축 스테핑 모터 포지셔닝 스테이지 (데이터 취득용 커스텀 인장 시험기)

---

## Build & Flash

### STM32 Firmware (`Switching_testing_26.01.01/`)
- **IDE**: STM32CubeIDE (Windows). Open the `.project` file in the `Switching_testing_26.01.01/` directory.
- **Build**: Project → Build Project (or Ctrl+B). Output is `Debug/Switching_testing_26.01.01.elf`.
- **Flash**: Run/Debug configuration is in `Switching_testing_26.01.01 Debug.launch`. Uses ST-LINK.
- **Peripheral config**: Re-generated from `Switching_testing_26.01.01.ioc` (STM32CubeMX). Do not manually edit HAL-generated files in `Core/Src/` other than within `/* USER CODE BEGIN/END */` blocks.
- **Serial monitor**: USART2 at 115200 baud (PA2/PA3). `printf` is redirected to USART2 via `_write()` in `main.c`.

### Python GUI (`26.03.10_Tensile_Tester/`)
```bash
pip install pyserial
python "26.03.10_Tensile_Tester/Positioning_Stage_Controller_V3.2.py"
```

### Arduino Firmware
- Open `26.03.10_Tensile_Tester/Positioning_Stage_Firmware_V3.2_Arduino/Positioning_Stage_Firmware_V3.2_Arduino.ino` in Arduino IDE.
- Requires: `AccelStepper` library.
- Target board: Arduino Uno (or compatible), 115200 baud.

---

## TDM Firmware Architecture

### Sensor Measurement Cycle (ISR-Driven, Non-Blocking)

Every `TDM_PERIOD_TIME_US` (default 1000 µs), **TIM7** fires `TDM_Handle_Timer_Main_ISR()`, which launches two parallel tasks:

1. **I2C DMA path**: Reads LDC1614 resonant frequency data (28-bit) over I2C2 using chained DMA reads (MSB then LSB per channel). Each DMA completion triggers `TDM_Handle_I2C_RxCplt()`, which chains the next read until all channels are done, then sets `flag_i2c_done`.

2. **ADC DMA path**: Switches the ADG734 analog MUX to TENG mode, starts ADC DMA on hadc1–hadc5, and starts **TIM6**. After `TENG_MEASURE_TIME_US` (100 µs), TIM6 fires `TDM_Handle_Timer_ADC_ISR()`, which captures TENG data, switches MUX to R (resistance) mode, and re-arms TIM6. After `R_DC_MEASURE_TIME_US` (100 µs), the same ISR captures R data and sets `flag_adc_seq_done`.

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
