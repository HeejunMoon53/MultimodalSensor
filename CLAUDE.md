# CLAUDE.md
 

## Git 워크플로우

작업이 마무리될 때마다 커밋 여부를 물어본다. 커밋 시 변경 내용을 한글로 간결하게 요약한 메시지로 `git add . → git commit → git push`를 순서대로 실행한다.

---

## Repository Overview

This repo contains two independent sub-projects for multimodal sensor research:

1. **`Switching_testing_26.01.01/`** — STM32G473CBT6 firmware (STM32CubeIDE) for a TDM multimodal sensor PCB that simultaneously measures DC resistance, TENG voltage, and inductance (resonant frequency) across up to 4 sensor channels.
2. **`26.03.10_Tensile_Tester/`** — Python GUI + Arduino firmware for a 5-axis stepping motor positioning stage used as a tensile tester.

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
