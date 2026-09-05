"""
moe_realtime_monitor.py
STM32 실시간 모니터링 — 후보 2(게이트+EMA MLP) MoE 디커플러 (TDMFirmware/moe_inference.c)

추론은 보드 위(STM32)에서 이미 끝나서 오는 값이라, 이 스크립트는 PC에서 추가로
모델을 돌리지 않는다 — 순수 시각화/기록 툴이다. nn_decoupling/realtime_monitor_test.py
(구 2단계 디커플러용)의 STM32Reader/ValueCard/pyqtgraph 패턴을 그대로 재사용하고,
시리얼 포맷과 카드/그래프 구성만 새 펌웨어 출력에 맞게 바꿨다.

Arduino(5축 스테이지) + RFT F/T 센서(FTSensorCAN)를 선택적으로 연결하면 실제값
(ground truth)도 함께 기록한다 — mms_collector.py / sync_decoupler_monitor.py와 같은
ArduinoController/RFTReader 패턴을 재사용. 인장 스트레인은 YA축(YA/YB 모터)으로
가하므로 strain_act_pct는 YA 위치로 계산한다 — XA 기준으로 계산하면 X축을 쓰지 않는
테스트에서는 항상 0으로 찍힌다(0816 테스트에서 실제로 발생한 버그).

실행:
    C:/ml_env/Scripts/python nn_decoupling/moe_realtime_monitor.py

시리얼 포맷 (TDMFirmware/Core/Src/main.c, 115200 baud):
    dL_pct, dR_pct, dV_pct, IDRIVE, STATUS,
    strain_pct, value, mode, gate_proba, latency_us
    (실수 8개 + 정수 2개, 총 10개 컬럼)

    value : mode==0(근접) -> distance_mm / mode==1(압력) -> force_N
    mode  : moe_inference.h의 MoeMode (0=PROXIMITY, 1=PRESSURE)

Arduino: POS? → POS:xa:xb:ya:yb:z:...  (100ms 폴링)
RFT (FTSensorCAN): Fx,Fy,Fz,Tx,Ty,Tz  (N / N·m, UART)
"""

import sys
import time
import csv
import bisect
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import serial
import serial.tools.list_ports

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QFileDialog,
    QSplitter, QStatusBar, QFrame, QTabWidget, QGroupBox, QDoubleSpinBox, QTextEdit,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QPalette

import pyqtgraph as pg

MAX_POINTS = 600
XWINDOW_S = 6.0   # 실시간 그래프에 보여줄 시간 창(초) — 슬라이딩 윈도우
BAUD_DEFAULT = 115200      # Arduino / RFT 보드 — 이쪽은 그대로 115200
STM32_BAUD_DEFAULT = 460800  # STM32 TDM 보드 — usart.c와 맞춤 (TDM_PRINT_EVERY_N=2, 500Hz)

# [2026-08-19] STM32가 500Hz로 쏘는데 ground truth(아두이노/RFT)는 10~20Hz로만
# 갱신된다 — 그 차이만큼 STM32Reader가 파싱+큐잉해야 할 일이 쓸데없이 많아지고,
# 메인 GUI 스레드가 GIL을 오래 쥐고 있을 때(렌더링 등) 따라잡기가 힘들어져서
# ts(캡처 시각) 자체가 밀리는 원인이 된다. readline()으로 라인은 계속 읽어서
# OS 버퍼는 비우되(안 그러면 버퍼에 계속 쌓임), N개 중 1개만 실제로 파싱·큐잉하고
# 나머지는 바로 버린다 — ground truth 갱신 주기보다 훨씬 촘촘하면 충분하다.
STM32_KEEP_EVERY_N = 5   # 500Hz -> 실효 100Hz로 다운샘플 (필요시 조정)

# ── Arduino 5축 스테이지 + RFT F/T 센서 (선택 연결, ground truth 기록용) ──────────
AXES          = ["XA", "XB", "YA", "YB", "Z"]
STEPS_PER_REV = 200
DEF_MICROSTEP = 8
DEF_PITCH_MM  = 5.0
ARDUINO_POLL  = 0.1
CAL_SAMPLES   = 50
SENSOR_L0     = 120.0   # 센서 초기 길이 (mm) — strain_act 계산용, CLAUDE.md 참조

# CLAUDE.md 색상 컨벤션: L=주황, R=초록, Force/TENG=파랑
COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"
COLOR_FORCE = "#1F77B4"
COLOR_DIST = "#94e2d5"   # 거리(근접)는 컨벤션 외 채널이라 별도 teal 사용

# Catppuccin Mocha (기존 realtime_monitor_test.py와 동일 팔레트)
C = {
    "bg": "#1e1e2e", "bg2": "#181825", "bg3": "#313244",
    "text": "#cdd6f4", "text2": "#a6adc8",
    "blue": COLOR_FORCE, "green": COLOR_R, "orange": COLOR_L,
    "yellow": "#f9e2af", "mauve": "#cba6f7", "red": "#f38ba8",
    "teal": COLOR_DIST, "border": "#45475a", "peach": "#fab387",
}

MODE_NAMES = {0: "근접", 1: "압력"}
MODE_COLORS = {0: COLOR_DIST, 1: COLOR_FORCE}


# ══════════════════════════════════════════════════════════════════════════════
# 시리얼 읽기 스레드
# ══════════════════════════════════════════════════════════════════════════════

class STM32Reader(QThread):
    """시리얼을 읽는 백그라운드 스레드.

    100Hz로 매 줄마다 pyqtSignal을 emit하면 스레드 간 큐잉(marshalling) 비용이
    쌓여서 UI 전체(숫자 카드 포함)가 느려진다 — 대신 파싱한 값을 잠금 없는
    deque에 쌓아두기만 하고, UI 타이머가 한 번에 다 걷어가는(drain) 방식으로 바꿨다.
    CPython의 GIL 덕분에 deque.append()와 통째로 새 deque로 교체하는 것 둘 다
    원자적이라 별도 Lock 없이도 안전하다.
    """
    error_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser = None
        self._running = False
        self._queue = deque()
        self._line_count = 0

    def connect(self, port: str, baud: int = STM32_BAUD_DEFAULT):
        self._ser = serial.Serial(port, baud, timeout=0.2)
        time.sleep(0.5)
        self._running = True
        self._line_count = 0

    def disconnect(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()

    def drain(self):
        """누적된 (ts, vals) 항목을 전부 가져오고 큐를 비운다. UI 타이머에서 호출."""
        old, self._queue = self._queue, deque()
        return old

    def run(self):
        # in_waiting을 폴링하며 time.sleep(0.001)로 쉬는 방식은 Windows에서
        # 특히 문제였다 — Windows 기본 타이머 해상도가 ~15.6ms라 "1ms만 쉬자"고
        # 해도 실제로는 훨씬 길게(최대 15ms) 잠들어서, 100Hz(10ms 간격) 데이터가
        # 뭉텅이로 몰려 들어오고 화면도 뚝뚝 끊겨 보였다. pyserial의 readline()은
        # OS 드라이버 레벨에서 블로킹하기 때문에 이 문제가 없다.
        while self._running:
            try:
                if not self._ser:
                    time.sleep(0.05)
                    continue
                raw = self._ser.readline()   # timeout(0.2s) 안에 '\n' 못 만나면 빈 bytes 반환
                if not raw:
                    continue
                # OS 버퍼를 계속 비우기 위해 readline()은 매번 호출하지만, ground truth
                # 갱신 주기(10~20Hz)보다 훨씬 촘촘한 500Hz를 다 처리할 필요는 없다 —
                # N개 중 1개만 디코드·파싱·큐잉하고 나머지는 즉시 버려서, 메인 스레드가
                # GIL을 오래 쥐고 있어도 이 스레드가 빨리 따라잡을 수 있게 한다
                # (그래야 큐잉되는 ts 자체가 밀리지 않는다).
                self._line_count += 1
                if self._line_count % STM32_KEEP_EVERY_N != 0:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                vals = self._parse(line)
                if vals:
                    self._queue.append((time.time(), vals))
            except Exception as e:
                self.error_msg.emit(str(e))
                time.sleep(0.1)

    @staticmethod
    def _parse(line: str):
        """dL_pct,dR_pct,dV_pct,IDRIVE,STATUS,strain_pct,value,mode,gate_proba,latency_us"""
        try:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 10:
                return None
            dL, dR, dV = float(parts[0]), float(parts[1]), float(parts[2])
            idrive, status = int(float(parts[3])), int(float(parts[4]))
            strain, value = float(parts[5]), float(parts[6])
            mode = int(float(parts[7]))
            gate_proba, latency_us = float(parts[8]), float(parts[9])
            return [dL, dR, dV, idrive, status, strain, value, mode, gate_proba, latency_us]
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# Arduino 5축 스테이지 컨트롤러 (ground truth 위치)
# ══════════════════════════════════════════════════════════════════════════════

class ArduinoController(QThread):
    """POS? 폴링으로 5축(XA,XB,YA,YB,Z) 위치를 읽고, ABS/JOG/ZERO/EN 명령도 보낸다.
    sync_decoupler_monitor.py / mms_collector.py와 동일 프로토콜."""
    position_updated = pyqtSignal(float, dict)
    done_received = pyqtSignal()
    alarm_received = pyqtSignal(str)
    error_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser = None
        self._running = False
        self._lock = threading.Lock()
        self._cmd_queue = deque()
        self.steps_per_mm = (STEPS_PER_REV * DEF_MICROSTEP) / DEF_PITCH_MM
        self._cur_pos = {ax: 0.0 for ax in AXES}   # move_abs 상대 이동 계산용

    def connect(self, port: str, baud: int = BAUD_DEFAULT):
        self._ser = serial.Serial(port, baud, timeout=0.2)
        time.sleep(2.0)
        self._running = True

    def disconnect(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()

    def send(self, cmd: str):
        with self._lock:
            self._cmd_queue.append(cmd)

    def zero(self):
        self.send("ZERO:0")

    def jog(self, axis: str, dist_mm: float, speed_mms: float = 5.0):
        steps = int(abs(dist_mm) * self.steps_per_mm)
        spd = max(1, int(speed_mms * self.steps_per_mm))
        self.send(f"JOG:{axis}:{-steps if dist_mm < 0 else steps}:{spd}")

    def move_abs(self, axis_delta_spd: list):
        """[(axis, delta_mm, speed_mms), ...] — 현재 위치 기준 상대 이동을 절대 이동 명령으로 변환."""
        parts = []
        for ax, delta_mm, spd_mms in axis_delta_spd:
            tgt = int((self._cur_pos.get(ax, 0.0) + delta_mm) * self.steps_per_mm)
            spd = max(1, int(spd_mms * self.steps_per_mm))
            parts += [ax, str(tgt), str(spd)]
        self.send("ABS:" + ":".join(parts))

    def run(self):
        last_poll = 0.0
        while self._running:
            try:
                with self._lock:
                    if self._cmd_queue:
                        cmd = self._cmd_queue.popleft()
                        if self._ser and self._ser.is_open:
                            self._ser.write((cmd + "\n").encode())

                now = time.time()
                if now - last_poll >= ARDUINO_POLL:
                    with self._lock:
                        if self._ser and self._ser.is_open:
                            self._ser.write(b"POS?\n")
                    last_poll = now

                if self._ser and self._ser.in_waiting:
                    line = self._ser.readline().decode("utf-8", errors="ignore").strip()
                    if line.startswith("POS:"):
                        pos = self._parse_pos(line)
                        if pos:
                            self.position_updated.emit(time.time(), pos)
                    elif line == "DONE":
                        self.done_received.emit()
                    elif "ALARM" in line:
                        self.alarm_received.emit(line)
                else:
                    time.sleep(0.005)
            except Exception as e:
                self.error_msg.emit(str(e))
                time.sleep(0.1)

    def _parse_pos(self, line: str):
        try:
            vals = [float(v) for v in line.split(":")[1:]]
            pos = {ax: round(vals[i] / self.steps_per_mm, 3)
                   for i, ax in enumerate(AXES) if i < len(vals)}
            self._cur_pos.update(pos)
            return pos
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# RFT F/T 센서 리더 (FTSensorCAN) — ground truth 힘
# ══════════════════════════════════════════════════════════════════════════════

class RFTReader(QThread):
    """Fx,Fy,Fz,Tx,Ty,Tz 6개 값을 UART로 받는다. mms_collector.py와 동일 프로토콜."""
    data_received = pyqtSignal(float, list)
    error_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser = None
        self._running = False

    def connect(self, port: str, baud: int = BAUD_DEFAULT):
        self._ser = serial.Serial(port, baud, timeout=0.1)
        time.sleep(0.5)
        self._running = True

    def disconnect(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()

    def run(self):
        buf = ""
        while self._running:
            try:
                if self._ser and self._ser.in_waiting:
                    buf += self._ser.read(self._ser.in_waiting).decode("utf-8", errors="ignore")
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        vals = self._parse(line)
                        if vals:
                            self.data_received.emit(time.time(), vals)
                else:
                    time.sleep(0.005)
            except Exception as e:
                self.error_msg.emit(str(e))
                time.sleep(0.1)

    @staticmethod
    def _parse(line: str):
        try:
            vals = [float(v.strip()) for v in line.split(",")]
            return vals[:6] if len(vals) >= 6 else None
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# UI 헬퍼
# ══════════════════════════════════════════════════════════════════════════════

def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color: {C['border']};")
    return f


# ══════════════════════════════════════════════════════════════════════════════
# 시퀀스 텍스트 파일 파서 — G-code처럼 한 줄에 한 명령
# ══════════════════════════════════════════════════════════════════════════════
#
#   ZERO                                모든 축 원점 설정
#   ENABLE / DISABLE                    모터 활성/비활성
#   WAIT <ms>                           대기 (밀리초)
#   TARE_FZ                             RFT 힘 영점 잡기 (최근 표본 평균)
#   RECORD ON / RECORD OFF              CSV 녹화 시작/중지(중지 시 자동 저장)
#   MOVE <축>=<델타mm>@<속도mm/s> ...    현재 위치 기준 상대 이동. 여러 축을 한
#                                        줄에 나열하면 동시 이동(ABS 명령 1개).
#                                        DONE 수신까지(또는 타임아웃까지) 대기.
#   LOOP <n> ... ENDLOOP                블록을 n번 반복(정수만, 0/무한 불가)
#   # 주석
#
# 예:
#   ZERO
#   ENABLE
#   MOVE YA=6@5 YB=6@5
#   WAIT 500
#   LOOP 3
#     MOVE Z=-25@10
#     MOVE Z=25@10
#   ENDLOOP

def parse_sequence_text(text: str):
    """텍스트를 (opcode, args) 튜플 리스트로 변환한다. LOOP/ENDLOOP는 실행 시점에
    다시 풀 필요 없도록 파싱 단계에서 미리 펼쳐(unroll)둔다."""
    lines = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            lines.append(line)

    def parse_block(i):
        block = []
        while i < len(lines):
            parts = lines[i].split()
            op = parts[0].upper()
            if op == "ENDLOOP":
                return block, i + 1
            if op == "LOOP":
                if len(parts) < 2:
                    raise ValueError(f"LOOP에 반복 횟수가 없습니다: '{lines[i]}'")
                n = int(parts[1])
                if n <= 0:
                    raise ValueError(f"LOOP 반복 횟수는 1 이상이어야 합니다: '{lines[i]}'")
                inner, i = parse_block(i + 1)
                block.extend(inner * n)
                continue
            block.append((op, parts[1:]))
            i += 1
        return block, i

    instrs, _ = parse_block(0)
    return instrs


class ValueCard(QWidget):
    """큰 숫자 + 단위 + 레이블 카드."""

    def __init__(self, label: str, unit: str, color: str, fmt: str = "{:.2f}"):
        super().__init__()
        self._fmt = fmt
        self._base_color = color
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(12, 8, 12, 8)
        vbox.setSpacing(2)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{C['text2']}; font-size:11px; font-weight:600; letter-spacing:1px;")
        vbox.addWidget(lbl)

        row = QHBoxLayout()
        self._val = QLabel("—")
        self._val.setStyleSheet(f"color:{color}; font-size:30px; font-weight:700; font-family:Consolas;")
        row.addWidget(self._val)
        row.addStretch()
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet(f"color:{C['text2']}; font-size:13px; margin-top:10px;")
        row.addWidget(unit_lbl)
        vbox.addLayout(row)

        self.setStyleSheet(f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;")

    def update(self, val, color: str = None):
        if val is None:
            self._val.setText("—")
        else:
            self._val.setText(self._fmt.format(val))
        self._val.setStyleSheet(
            f"color:{color or self._base_color}; font-size:30px; font-weight:700; font-family:Consolas;")


# ══════════════════════════════════════════════════════════════════════════════
# 메인 윈도우
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MoE Decoupler Monitor — 게이트+EMA (후보 2)")
        self.resize(1360, 820)

        self._reader = STM32Reader()
        self._arduino = ArduinoController()
        self._rft = RFTReader()

        self._t0 = None
        self._ts = deque(maxlen=MAX_POINTS)
        self._bufs = {k: deque(maxlen=MAX_POINTS)
                      for k in ["dL", "dR", "dV", "strain", "value", "gate"]}

        self._recording = False
        self._rec_rows = []
        self._save_dir = str(Path.home())
        self._freq_ts = deque(maxlen=100)
        self._last_mode = None

        # ground truth (Arduino 위치 + RFT 힘) — 둘 다 선택 연결, 미연결 시 0으로 기록
        #
        # [2026-08-18 수정] 예전엔 _last_pos/_last_rft에 "가장 최근 값"만 덮어쓰고
        # _ingest()가 드레인 시점(=지금)의 값을 그대로 STM32 샘플(과거 시점 ts)에
        # 붙였다 — STM32Reader가 deque에 큐잉하다 UI 타이머가 몰아서 드레인하는
        # 구조라, 큐에 몇 초치가 쌓이면 그만큼 "미래" ground truth가 "과거" dL/dR에
        # 붙는 심각한 시간 불일치가 생겼다(실측: 세션에 따라 0~4초, 드리프트함).
        # 이제 (ts, value) 이력을 남겨두고, STM32 샘플 자신의 ts에 가장 가까운
        # ground truth를 찾아 붙인다(_lookup_nearest).
        self._last_pos = {ax: 0.0 for ax in AXES}
        self._last_rft = [0.0] * 6   # [Fx, Fy, Fz, Tx, Ty, Tz]
        self._pos_hist = deque(maxlen=2000)   # [(ts, {axis: mm, ...}), ...] 시간순
        self._rft_hist = deque(maxlen=2000)   # [(ts, [Fx,Fy,Fz,Tx,Ty,Tz]), ...] 시간순
        self._cal_buf_Fz = deque(maxlen=CAL_SAMPLES)
        self._Fz0 = 0.0

        # 모터 enable 상태 + 시퀀스 파일 실행 상태
        self._motor_enabled = False
        self._jog_speed = 5.0
        self._seq_running = False
        self._seq_done_event = threading.Event()
        self._seq_path = None
        self._seq_instrs = []

        self._build_ui()
        self._reader.error_msg.connect(lambda m: self._update_status(f"오류: {m}"))
        self._arduino.position_updated.connect(self._on_arduino_pos)
        self._arduino.error_msg.connect(lambda m: self._update_status(f"Arduino 오류: {m}"))
        self._arduino.done_received.connect(self._on_seq_done)
        self._arduino.alarm_received.connect(self._on_seq_alarm)
        self._rft.data_received.connect(self._on_rft_data)
        self._rft.error_msg.connect(lambda m: self._update_status(f"RFT 오류: {m}"))

        self._ui_timer = QTimer()
        self._ui_timer.setTimerType(Qt.PreciseTimer)  # Windows 기본(CoarseTimer)은 ~15ms
                                                        # 단위로 반올림돼서 짧은 주기가 무의미해짐
        self._ui_timer.timeout.connect(self._refresh)
        self._ui_timer.start(15)   # ~66 fps — 지금까지 최적화(auto-range/AA/배치)는 프레임당
                                    # 비용만 줄였지 갱신 주기 자체(기존 40ms=25fps)는 그대로였다.
                                    # 100Hz 데이터를 눈으로 따라가려면 주기 자체를 올려야 한다.

    # ── UI 구성 ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        pg.setConfigOption("background", C["bg"])
        pg.setConfigOption("foreground", C["text"])
        pg.setConfigOptions(antialias=False)   # 실시간 스크롤 성능 — AA 끔

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 6)

        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_gt_bar())
        root.addWidget(self._build_seq_bar())
        root.addWidget(_hline())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([300, 1060])
        root.addWidget(splitter, stretch=1)

        root.addWidget(_hline())
        root.addWidget(self._build_record_bar())

        sb = QStatusBar()
        sb.setStyleSheet(f"color:{C['text2']}; font-size:12px;")
        self.setStatusBar(sb)
        self._sb = sb
        self._update_status("시리얼 미연결")

    def _build_top_bar(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0)

        lay.addWidget(self._lbl("포트"))
        self._cb_port = QComboBox()
        self._cb_port.setMinimumWidth(100)
        lay.addWidget(self._cb_port)

        lay.addWidget(self._lbl("Baud"))
        self._cb_baud = QComboBox()
        self._cb_baud.addItems(["9600", "115200", "230400", "460800"])
        self._cb_baud.setCurrentText(str(STM32_BAUD_DEFAULT))
        lay.addWidget(self._cb_baud)

        self._btn_connect = QPushButton("연결")
        self._btn_connect.setFixedSize(64, 30)
        self._btn_connect.clicked.connect(self._toggle_connect)
        lay.addWidget(self._btn_connect)

        self._ind = QLabel("●")
        self._ind.setStyleSheet(f"color:{C['red']}; font-size:16px;")
        lay.addWidget(self._ind)

        btn_ref = QPushButton("⟳")
        btn_ref.setFixedSize(30, 30)
        btn_ref.setToolTip("포트 목록 새로고침")
        btn_ref.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_ref)

        lay.addStretch()

        # 현재 모드 표시 (근접/압력)
        self._lbl_mode = QLabel("모드: —")
        self._lbl_mode.setStyleSheet(
            f"color:{C['text2']}; font-size:13px; font-weight:700; font-family:Consolas; "
            f"padding:4px 10px; border:1px solid {C['border']}; border-radius:5px;")
        lay.addWidget(self._lbl_mode)

        lay.addSpacing(10)

        self._lbl_hz = QLabel("— Hz")
        self._lbl_hz.setStyleSheet(f"color:{C['teal']}; font-size:13px; font-weight:700; font-family:Consolas;")
        lay.addWidget(self._lbl_hz)

        self._refresh_ports()
        return bar

    def _build_gt_bar(self):
        """Arduino(5축) + RFT F/T 연결 및 실제값(ground truth) 표시 — 둘 다 선택 사항."""
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0)

        lay.addWidget(self._lbl("Arduino"))
        self._cb_arduino = QComboBox()
        self._cb_arduino.setMinimumWidth(100)
        lay.addWidget(self._cb_arduino)
        self._btn_arduino = QPushButton("연결")
        self._btn_arduino.setFixedSize(64, 28)
        self._btn_arduino.clicked.connect(self._toggle_arduino)
        lay.addWidget(self._btn_arduino)
        self._ind_arduino = QLabel("●")
        self._ind_arduino.setStyleSheet(f"color:{C['red']}; font-size:14px;")
        lay.addWidget(self._ind_arduino)

        lay.addSpacing(8)
        lay.addWidget(self._lbl("RFT F/T"))
        self._cb_rft = QComboBox()
        self._cb_rft.setMinimumWidth(100)
        lay.addWidget(self._cb_rft)
        self._btn_rft = QPushButton("연결")
        self._btn_rft.setFixedSize(64, 28)
        self._btn_rft.clicked.connect(self._toggle_rft)
        lay.addWidget(self._btn_rft)
        self._ind_rft = QLabel("●")
        self._ind_rft.setStyleSheet(f"color:{C['red']}; font-size:14px;")
        lay.addWidget(self._ind_rft)

        btn_tare = QPushButton("Tare Fz")
        btn_tare.setFixedHeight(28)
        btn_tare.setStyleSheet(
            f"background:{C['bg3']}; color:{C['blue']}; "
            f"border:1px solid {C['blue']}; border-radius:5px; font-weight:600;")
        btn_tare.clicked.connect(self._tare_fz)
        lay.addWidget(btn_tare)

        lay.addSpacing(12)
        # 실제값(ground truth) 표시 — XA/YA/Z 위치 + strain_act/value_act
        # 인장 스트레인은 YA(YA/YB 모터)로 가하므로 strain_act는 YA 기준으로 계산한다.
        self._lbl_gt_pos = QLabel("XA:—  YA:—  Z:—  Fz:—")
        self._lbl_gt_pos.setStyleSheet(f"color:{C['teal']}; font-size:12px; font-family:Consolas;")
        lay.addWidget(self._lbl_gt_pos)

        lay.addSpacing(12)
        self._lbl_gt_act = QLabel("strain_act:—%  value_act:—")
        self._lbl_gt_act.setStyleSheet(f"color:{C['mauve']}; font-size:12px; font-family:Consolas;")
        lay.addWidget(self._lbl_gt_act)

        lay.addStretch()
        self._refresh_gt_ports()
        return bar

    def _build_seq_bar(self):
        """모터 ENABLE/ZERO + 텍스트 시퀀스 파일 불러오기/실행 — Arduino 자동 동작 제어."""
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0)

        self._btn_motor = QPushButton("ENABLE")
        self._btn_motor.setFixedHeight(28)
        self._btn_motor.setStyleSheet(
            f"background:{C['green']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
        self._btn_motor.clicked.connect(self._toggle_motor)
        lay.addWidget(self._btn_motor)

        btn_zero = QPushButton("ZERO")
        btn_zero.setFixedHeight(28)
        btn_zero.clicked.connect(self._set_zero)
        lay.addWidget(btn_zero)

        lay.addSpacing(12)
        lay.addWidget(self._lbl("시퀀스:"))
        self._lbl_seq_file = QLabel("(불러온 파일 없음)")
        self._lbl_seq_file.setStyleSheet(f"color:{C['teal']}; font-family:Consolas; font-size:12px;")
        lay.addWidget(self._lbl_seq_file, stretch=1)

        btn_load = QPushButton("파일 불러오기")
        btn_load.setFixedHeight(28)
        btn_load.clicked.connect(self._load_sequence_file)
        lay.addWidget(btn_load)

        self._btn_seq_run = QPushButton("▶ 시퀀스 실행")
        self._btn_seq_run.setFixedHeight(28)
        self._btn_seq_run.setStyleSheet(
            f"background:{C['blue']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
        self._btn_seq_run.clicked.connect(self._run_sequence_file)
        self._btn_seq_run.setEnabled(False)
        lay.addWidget(self._btn_seq_run)

        self._btn_seq_stop = QPushButton("■ 정지")
        self._btn_seq_stop.setFixedHeight(28)
        self._btn_seq_stop.clicked.connect(self._stop_sequence_file)
        lay.addWidget(self._btn_seq_stop)

        self._lbl_seq_progress = QLabel("")
        self._lbl_seq_progress.setFixedWidth(140)
        self._lbl_seq_progress.setStyleSheet(f"color:{C['text2']}; font-family:Consolas; font-size:12px;")
        lay.addWidget(self._lbl_seq_progress)

        return bar

    def _build_left_panel(self):
        tabs = QTabWidget()
        tabs.addTab(self._build_sensor_tab(), "센서")
        tabs.addTab(self._build_jog_tab(), "수동 조그")
        return tabs

    def _build_sensor_tab(self):
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setSpacing(8)
        vbox.setContentsMargins(4, 4, 4, 4)

        vbox.addWidget(self._sec_lbl("RAW SENSOR"))
        self._cards = {
            "dL": ValueCard("ΔL / L₀", "%", COLOR_L, "{:+.3f}"),
            "dR": ValueCard("ΔR / R₀", "%", COLOR_R, "{:+.3f}"),
            "dV": ValueCard("V_TENG (미사용)", "ADC", C["text2"], "{:.0f}"),
        }
        for c in self._cards.values():
            vbox.addWidget(c)

        vbox.addSpacing(4)
        vbox.addWidget(_hline())
        vbox.addWidget(self._sec_lbl("MOE DECOUPLER 출력 (보드 위 추론)"))
        self._cards["strain"] = ValueCard("Strain", "%", C["mauve"], "{:.2f}")
        self._cards["dist"] = ValueCard("근접 거리", "mm", COLOR_DIST, "{:.2f}")
        self._cards["force"] = ValueCard("압력 힘", "N", COLOR_FORCE, "{:.3f}")
        self._cards["gate"] = ValueCard("게이트 P(접촉)", "", C["yellow"], "{:.3f}")
        for k in ["strain", "dist", "force", "gate"]:
            vbox.addWidget(self._cards[k])

        vbox.addSpacing(4)
        vbox.addWidget(_hline())
        vbox.addWidget(self._sec_lbl("진단"))
        diag = QHBoxLayout()
        self._cards["idrive"] = ValueCard("IDRIVE", "", C["text2"], "{:.0f}")
        self._cards["latency"] = ValueCard("추론 지연", "µs", C["text2"], "{:.1f}")
        diag.addWidget(self._cards["idrive"])
        diag.addWidget(self._cards["latency"])
        vbox.addLayout(diag)

        vbox.addStretch()
        return w

    def _build_jog_tab(self):
        """mms_collector.py의 수동 조그 탭과 동일한 구성/속도 로직을 그대로 이식."""
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setSpacing(8)
        vbox.setContentsMargins(8, 8, 8, 8)

        # 조그 속도
        row_spd = QHBoxLayout()
        row_spd.addWidget(self._lbl("속도 (mm/s)"))
        self._spin_jog_spd = QDoubleSpinBox()
        self._spin_jog_spd.setRange(0.1, 50)
        self._spin_jog_spd.setSingleStep(0.5)
        self._spin_jog_spd.setValue(self._jog_speed)
        self._spin_jog_spd.setFixedWidth(80)
        self._spin_jog_spd.setStyleSheet(
            f"background:{C['bg3']}; color:{C['peach']}; "
            f"border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;")
        self._spin_jog_spd.valueChanged.connect(lambda v: setattr(self, "_jog_speed", v))
        row_spd.addWidget(self._spin_jog_spd)
        row_spd.addStretch()
        vbox.addLayout(row_spd)

        # 전체 축 조그 버튼
        jog_grp = QGroupBox("축별 조그")
        jog_grid = QGridLayout(jog_grp)
        jog_grid.setSpacing(3)

        jog_defs = [("<<<\n10mm", -10.0), ("<<\n5mm", -5.0), ("<\n1mm", -1.0),
                    (">\n1mm", 1.0), (">>\n5mm", 5.0), (">>>\n10mm", 10.0)]

        for col, (h, _) in enumerate(jog_defs):
            lbl = QLabel(h, alignment=Qt.AlignCenter)
            lbl.setStyleSheet("font-size:9px;")
            jog_grid.addWidget(lbl, 0, col + 1)

        for row, ax in enumerate(AXES):
            jog_grid.addWidget(QLabel(ax), row + 1, 0)
            for col, (_, dist) in enumerate(jog_defs):
                btn = QPushButton("←→"[col >= 3])
                btn.setFixedSize(46, 26)
                d = dist
                btn.clicked.connect(lambda _, a=ax, d=d: self._do_jog(a, d))
                jog_grid.addWidget(btn, row + 1, col + 1)

        vbox.addWidget(jog_grp)

        # 절대 이동 (Z 전용)
        abs_grp = QGroupBox("Z 절대 이동")
        abs_lay = QHBoxLayout(abs_grp)
        abs_lay.addWidget(self._lbl("목표 Z (mm)"))
        self._spin_z_abs = QDoubleSpinBox()
        self._spin_z_abs.setRange(-500, 500)
        self._spin_z_abs.setSingleStep(0.5)
        self._spin_z_abs.setValue(0.0)
        self._spin_z_abs.setDecimals(2)
        self._spin_z_abs.setFixedWidth(90)
        self._spin_z_abs.setStyleSheet(
            f"background:{C['bg3']}; color:{C['peach']}; "
            f"border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;")
        abs_lay.addWidget(self._spin_z_abs)
        btn_go = QPushButton("이동")
        btn_go.setFixedHeight(30)
        btn_go.clicked.connect(self._go_z_abs)
        abs_lay.addWidget(btn_go)
        vbox.addWidget(abs_grp)

        # 로그
        self._jog_log = QTextEdit()
        self._jog_log.setReadOnly(True)
        self._jog_log.setMaximumHeight(120)
        self._jog_log.setStyleSheet(
            f"background:{C['bg2']}; color:{C['text2']}; font-size:11px; font-family:Consolas;")
        vbox.addWidget(self._jog_log)
        vbox.addStretch()
        return w

    def _sec_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{C['text2']}; font-size:10px; font-weight:700; letter-spacing:2px; margin-top:4px;")
        return lbl

    def _build_right_panel(self):
        pw = pg.GraphicsLayoutWidget()

        # (제목, 색, 키, Y범위) — Y도 전부 고정해서 auto-range 계산 자체를 없앤다.
        # 범위는 이 프로젝트에서 실측된 값 기준(moe_params.h 클램프 범위와 동일한 여유).
        specs = [
            ("ΔL/L₀ (%)", COLOR_L, "dL", (-50.0, 25.0)),
            ("ΔR/R₀ (%)", COLOR_R, "dR", (0.0, 50.0)),
            ("Strain (%)", C["mauve"], "strain", (-2.0, 32.0)),
            ("출력값 — 근접: 거리(mm) / 압력: 힘(N), 색으로 모드 구분", COLOR_DIST, "value", (-2.0, 26.0)),
            ("게이트 P(접촉) — 점선 0.5 임계값", C["yellow"], "gate", (0.0, 1.0)),
        ]

        self._plots = {}
        self._curves = {}
        first_plot = None

        for i, (title, color, key, yrange) in enumerate(specs):
            p = pw.addPlot(row=i, col=0, title=title)
            p.getAxis("left").setWidth(54)
            p.showGrid(x=False, y=True, alpha=0.15)
            p.titleLabel.setAttr("color", C["text2"])
            p.titleLabel.setAttr("size", "11pt")
            p.setMouseEnabled(x=False, y=False)
            # X/Y 둘 다 auto-range를 끄고 고정값을 쓴다 — 100Hz 갱신에서 플롯마다
            # 매 프레임 range를 재계산하는 게 가장 큰 병목이었다.
            p.enableAutoRange("x", False)
            p.enableAutoRange("y", False)
            p.setYRange(*yrange, padding=0)

            curve = p.plot(pen=pg.mkPen(color, width=1.8))
            curve.setClipToView(True)      # 화면 밖 포인트는 렌더링 생략
            curve.setDownsampling(auto=True, method="peak")
            self._plots[key] = p
            self._curves[key] = curve

            if i == 0:
                first_plot = p
            else:
                p.setXLink(first_plot)

            if i == len(specs) - 1:
                p.setLabel("bottom", "시간 (s)")
            else:
                p.getAxis("bottom").setStyle(showValues=False)

        self._plots["gate"].addLine(y=0.5, pen=pg.mkPen(C["text2"], width=1, style=Qt.DashLine))

        self._first_plot = first_plot
        return pw

    def _build_record_bar(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0)

        self._btn_rec = QPushButton("● RECORD")
        self._btn_rec.setFixedSize(130, 34)
        self._btn_rec.setCheckable(True)
        self._btn_rec.setStyleSheet(
            "QPushButton{background:#f38ba8; color:#1e1e2e; font-weight:700; "
            "font-size:13px; border-radius:5px;}"
            "QPushButton:checked{background:#a6e3a1; color:#1e1e2e;}")
        self._btn_rec.clicked.connect(self._toggle_record)
        lay.addWidget(self._btn_rec)

        lay.addSpacing(12)
        lay.addWidget(self._lbl("저장 폴더:"))

        self._lbl_dir = QLabel(self._save_dir)
        self._lbl_dir.setStyleSheet(f"color:{C['blue']};")
        lay.addWidget(self._lbl_dir, stretch=1)

        btn_browse = QPushButton("폴더 선택")
        btn_browse.setFixedHeight(30)
        btn_browse.clicked.connect(self._browse_dir)
        lay.addWidget(btn_browse)

        lay.addSpacing(8)
        self._lbl_rec_count = QLabel("0행")
        self._lbl_rec_count.setStyleSheet(f"color:{C['text2']}; font-family:Consolas;")
        lay.addWidget(self._lbl_rec_count)

        return bar

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{C['text2']}; font-weight:600;")
        return lbl

    # ── 데이터 수신 ───────────────────────────────────────────────────────────

    def _ingest(self, ts: float, vals: list):
        dL, dR, dV, idrive, status, strain, value, mode, gate_proba, latency_us = vals

        if self._t0 is None:
            self._t0 = ts
        t = ts - self._t0

        self._ts.append(t)
        self._bufs["dL"].append(dL)
        self._bufs["dR"].append(dR)
        self._bufs["dV"].append(dV)
        self._bufs["strain"].append(strain)
        self._bufs["value"].append(value)   # 근접: mm, 압력: N — 항상 이어서 그림(끊김 없음)
        self._bufs["gate"].append(gate_proba)
        self._freq_ts.append(ts)
        self._last_mode = mode
        self._last_idrive = idrive
        self._last_status = status
        self._last_latency = latency_us

        # ground truth — 인장 스트레인은 YA(YA/YB 모터)로 가하므로 YA 기준으로 계산한다.
        # XA 기준으로 계산하면 이번처럼 X축을 쓰지 않는 테스트에서 항상 0으로 찍힌다.
        #
        # STM32 샘플 자신의 캡처 시점(ts)에 가장 가까운 ground truth를 찾아 붙인다 —
        # "지금(드레인 시점)의 최신값"을 붙이면 큐 배치가 쌓였을 때 몇 초씩 미래
        # 값이 붙는 버그가 생긴다(2026-08-18 발견·수정).
        pos_at_ts = self._lookup_nearest(self._pos_hist, ts) or self._last_pos
        rft_at_ts = self._lookup_nearest(self._rft_hist, ts) or self._last_rft
        xa = pos_at_ts.get("XA", 0.0)
        ya = pos_at_ts.get("YA", 0.0)
        z = pos_at_ts.get("Z", 0.0)
        fz = rft_at_ts[2] - self._Fz0
        strain_act_pct = abs(ya) * 2.0 / SENSOR_L0 * 100.0
        value_act = z if mode == 0 else fz
        self._last_gt = (xa, ya, z, fz, strain_act_pct, value_act)

        if self._recording:
            self._rec_rows.append([
                round(t, 4), dL, dR, dV, idrive, status,
                round(strain, 4), round(value, 4), mode,
                round(gate_proba, 4), round(latency_us, 2),
                round(xa, 4), round(ya, 4), round(z, 4), round(fz, 4),
                round(strain_act_pct, 4), round(value_act, 4),
            ])
            self._lbl_rec_count.setText(f"{len(self._rec_rows)}행")

    # ── 화면 갱신 ─────────────────────────────────────────────────────────────

    def _refresh(self):
        # 리더 스레드가 쌓아둔 항목을 한 번에 걷어와서 처리 — 샘플마다 시그널을
        # emit하던 방식보다 스레드 전환 비용이 훨씬 적다.
        for ts, vals in self._reader.drain():
            self._ingest(ts, vals)

        n = len(self._ts)
        if n < 2:
            return

        ts_arr = np.array(self._ts)

        for key, curve in self._curves.items():
            buf = self._bufs[key]
            if len(buf) != n:
                continue
            arr = np.array([v if v is not None else np.nan for v in buf])
            curve.setData(ts_arr, arr)

        # X축 슬라이딩 윈도우를 수동으로 세팅 (auto-range 재계산을 안 쓰는 대신 여기서
        # 한 번만 계산 — 나머지 4개 플롯은 setXLink로 자동으로 따라옴)
        if self._first_plot is not None:
            t_now = ts_arr[-1]
            t_lo = ts_arr[0] if (t_now - ts_arr[0]) < XWINDOW_S else t_now - XWINDOW_S
            self._first_plot.setXRange(t_lo, t_now, padding=0)

        self._cards["dL"].update(self._bufs["dL"][-1] if self._bufs["dL"] else None)
        self._cards["dR"].update(self._bufs["dR"][-1] if self._bufs["dR"] else None)
        self._cards["dV"].update(self._bufs["dV"][-1] if self._bufs["dV"] else None)
        self._cards["strain"].update(self._bufs["strain"][-1] if self._bufs["strain"] else None)

        last_value = self._bufs["value"][-1] if self._bufs["value"] else None
        self._cards["dist"].update(last_value if self._last_mode == 0 else None)
        self._cards["force"].update(last_value if self._last_mode == 1 else None)
        self._cards["gate"].update(self._bufs["gate"][-1] if self._bufs["gate"] else None)

        if self._last_mode is not None:
            name = MODE_NAMES.get(self._last_mode, "?")
            col = MODE_COLORS.get(self._last_mode, C["text2"])
            self._lbl_mode.setText(f"모드: {name}")
            self._lbl_mode.setStyleSheet(
                f"color:{col}; font-size:13px; font-weight:700; font-family:Consolas; "
                f"padding:4px 10px; border:1px solid {col}; border-radius:5px;")
            self._cards["idrive"].update(getattr(self, "_last_idrive", None))
            self._cards["latency"].update(getattr(self, "_last_latency", None))
            # value 커브 색을 현재 모드에 맞춰 갱신 (끊긴 선 대신 이어진 선 + 색으로 모드 구분)
            self._curves["value"].setPen(pg.mkPen(col, width=1.8))

        if len(self._freq_ts) >= 2:
            elapsed = self._freq_ts[-1] - self._freq_ts[0]
            if elapsed > 0:
                self._lbl_hz.setText(f"{(len(self._freq_ts) - 1) / elapsed:.1f} Hz")

        gt = getattr(self, "_last_gt", None)
        if gt is not None:
            xa, ya, z, fz, strain_act, value_act = gt
            self._lbl_gt_pos.setText(f"XA:{xa:+.2f}  YA:{ya:+.2f}  Z:{z:+.2f}  Fz:{fz:+.2f}N")
            self._lbl_gt_act.setText(f"strain_act:{strain_act:.2f}%  value_act:{value_act:+.2f}")

    # ── 포트 관리 ─────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        cur = self._cb_port.currentText()
        self._cb_port.clear()
        self._cb_port.addItems(ports)
        if cur in ports:
            self._cb_port.setCurrentText(cur)

    def _refresh_gt_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for cb in (self._cb_arduino, self._cb_rft):
            cur = cb.currentText()
            cb.clear()
            cb.addItems(ports)
            if cur in ports:
                cb.setCurrentText(cur)

    def _toggle_arduino(self):
        if self._arduino.isRunning():
            self._arduino.disconnect()
            self._arduino.quit()
            self._arduino.wait(1000)
            self._btn_arduino.setText("연결")
            self._ind_arduino.setStyleSheet(f"color:{C['red']}; font-size:14px;")
            self._last_pos = {ax: 0.0 for ax in AXES}
            self._pos_hist.clear()   # 재연결 후 이력이 끊겨 엉뚱한 과거값과 보간되는 것 방지
            self._update_status("Arduino 연결 해제")
        else:
            port = self._cb_arduino.currentText()
            if not port:
                self._update_status("Arduino 포트를 선택하세요")
                return
            try:
                self._arduino.connect(port)
                self._arduino.start()
                self._btn_arduino.setText("해제")
                self._ind_arduino.setStyleSheet(f"color:{C['green']}; font-size:14px;")
                self._update_status(f"Arduino {port} 연결됨")
            except Exception as e:
                self._update_status(f"Arduino 연결 실패: {e}")

    def _toggle_rft(self):
        if self._rft.isRunning():
            self._rft.disconnect()
            self._rft.quit()
            self._rft.wait(1000)
            self._btn_rft.setText("연결")
            self._ind_rft.setStyleSheet(f"color:{C['red']}; font-size:14px;")
            self._rft_hist.clear()   # 재연결 후 이력이 끊겨 엉뚱한 과거값과 보간되는 것 방지
            self._update_status("RFT 연결 해제")
        else:
            port = self._cb_rft.currentText()
            if not port:
                self._update_status("RFT 포트를 선택하세요")
                return
            try:
                self._rft.connect(port)
                self._rft.start()
                self._btn_rft.setText("해제")
                self._ind_rft.setStyleSheet(f"color:{C['green']}; font-size:14px;")
                self._update_status(f"RFT {port} 연결됨")
            except Exception as e:
                self._update_status(f"RFT 연결 실패: {e}")

    def _on_arduino_pos(self, ts: float, pos: dict):
        self._last_pos.update(pos)
        self._pos_hist.append((ts, dict(self._last_pos)))

    def _on_rft_data(self, ts: float, vals: list):
        self._last_rft = vals
        self._cal_buf_Fz.append(vals[2])
        self._rft_hist.append((ts, list(vals)))

    @staticmethod
    def _lookup_nearest(history: deque, ts: float):
        """history: [(ts, value), ...] 시간순으로 append된 이력. ts에 가장 가까운
        시점의 value를 반환한다(과거 STM32 샘플에 "지금" 값이 아니라 "그 시점" 값을
        붙이기 위함). 이력이 비었으면 None."""
        if not history:
            return None
        times = [h[0] for h in history]
        idx = bisect.bisect_left(times, ts)
        if idx <= 0:
            return history[0][1]
        if idx >= len(history):
            return history[-1][1]
        before_ts, before_val = history[idx - 1]
        after_ts, after_val = history[idx]
        return before_val if (ts - before_ts) <= (after_ts - ts) else after_val

    def _tare_fz(self):
        if len(self._cal_buf_Fz) < 10:
            self._update_status("Fz Tare 실패: RFT 데이터 부족 (최소 10샘플)")
            return
        self._Fz0 = float(np.mean(self._cal_buf_Fz))
        self._update_status(f"Fz Tare 완료 — Fz0={self._Fz0:+.3f}N")

    # ── 모터 / 시퀀스 파일 실행 ──────────────────────────────────────────────────

    def _toggle_motor(self):
        self._set_motor_enabled_ui(not self._motor_enabled)
        self._arduino.send("EN:1" if self._motor_enabled else "EN:0")

    def _set_motor_enabled_ui(self, on: bool):
        self._motor_enabled = on
        self._btn_motor.setText("DISABLE" if on else "ENABLE")
        self._btn_motor.setStyleSheet(
            f"background:{C['yellow'] if on else C['green']}; color:{C['bg']}; "
            f"font-weight:700; border-radius:4px;")

    def _set_zero(self):
        self._arduino.zero()
        self._update_status("원점 설정 (ZERO)")

    def _do_jog(self, axis: str, dist_mm: float):
        if not self._arduino.isRunning():
            self._update_status("Arduino 미연결")
            return
        if not self._motor_enabled:
            self._update_status("모터 ENABLE 필요")
            return
        self._arduino.jog(axis, dist_mm, self._jog_speed)
        self._jog_log_append(f"JOG {axis} {dist_mm:+.2f}mm @ {self._jog_speed:.1f}mm/s")

    def _go_z_abs(self):
        if not self._arduino.isRunning():
            self._update_status("Arduino 미연결")
            return
        if not self._motor_enabled:
            self._update_status("모터 ENABLE 필요")
            return
        tgt = self._spin_z_abs.value()
        tgt_steps = int(tgt * self._arduino.steps_per_mm)
        spd_steps = max(1, int(self._jog_speed * self._arduino.steps_per_mm))
        self._arduino.send(f"ABS:Z:{tgt_steps}:{spd_steps}")
        self._jog_log_append(f"Z → {tgt:.2f}mm")

    def _jog_log_append(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._jog_log.append(f"[{ts}] {text}")

    def _load_sequence_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "시퀀스 파일 선택", self._save_dir, "시퀀스 파일 (*.txt *.seq);;모든 파일 (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            instrs = parse_sequence_text(text)
        except Exception as e:
            self._update_status(f"시퀀스 파싱 실패: {e}")
            return
        if not instrs:
            self._update_status("시퀀스 파일이 비어 있습니다")
            return
        self._seq_path = path
        self._seq_instrs = instrs
        self._lbl_seq_file.setText(f"{Path(path).name}  ({len(instrs)} steps)")
        self._btn_seq_run.setEnabled(True)
        self._lbl_seq_progress.setText("")
        self._update_status(f"시퀀스 로드: {Path(path).name} — {len(instrs)} steps")

    def _run_sequence_file(self):
        if not self._seq_instrs:
            self._update_status("시퀀스가 로드되지 않았습니다")
            return
        if not self._arduino.isRunning():
            self._update_status("Arduino 미연결 — 시퀀스 실행 불가")
            return
        if self._seq_running:
            return
        self._seq_running = True
        self._btn_seq_run.setEnabled(False)
        threading.Thread(target=self._exec_sequence, daemon=True).start()

    def _stop_sequence_file(self):
        if self._seq_running:
            self._update_status("시퀀스 정지 요청")
        self._seq_running = False
        self._seq_done_event.set()

    def _on_seq_done(self):
        self._seq_done_event.set()

    def _on_seq_alarm(self, msg: str):
        self._seq_running = False
        self._seq_done_event.set()
        self._update_status(f"[ALARM] {msg} — 시퀀스 중단")

    def _exec_sequence(self):
        """백그라운드 스레드에서 시퀀스 명령을 순서대로 실행. Qt 위젯 갱신은 전부
        QTimer.singleShot(0, ...)으로 GUI 스레드에 넘긴다."""
        instrs = self._seq_instrs
        total = len(instrs)
        try:
            for idx, (op, args) in enumerate(instrs):
                if not self._seq_running:
                    break
                QTimer.singleShot(
                    0, lambda i=idx, o=op: self._lbl_seq_progress.setText(f"{i + 1}/{total}  {o}"))

                if op == "ZERO":
                    self._arduino.zero()

                elif op == "ENABLE":
                    self._arduino.send("EN:1")
                    QTimer.singleShot(0, lambda: self._set_motor_enabled_ui(True))

                elif op == "DISABLE":
                    self._arduino.send("EN:0")
                    QTimer.singleShot(0, lambda: self._set_motor_enabled_ui(False))

                elif op == "WAIT":
                    ms = float(args[0])
                    t_end = time.time() + ms / 1000.0
                    while self._seq_running and time.time() < t_end:
                        time.sleep(0.02)

                elif op == "TARE_FZ":
                    QTimer.singleShot(0, self._tare_fz)
                    time.sleep(0.3)   # tare가 GUI 스레드에서 처리될 시간 확보

                elif op == "RECORD":
                    on = args[0].upper() == "ON"
                    QTimer.singleShot(0, lambda o=on: self._set_recording(o))

                elif op == "MOVE":
                    try:
                        moves = []
                        max_t = 0.0
                        for tok in args:
                            axis, rest = tok.split("=", 1)
                            delta_s, spd_s = rest.split("@", 1)
                            delta, spd = float(delta_s), float(spd_s)
                            moves.append((axis, delta, spd))
                            max_t = max(max_t, abs(delta) / max(spd, 0.01))
                    except Exception:
                        QTimer.singleShot(
                            0, lambda a=args: self._update_status(f"MOVE 파싱 실패: {a}"))
                        continue
                    self._seq_done_event.clear()
                    self._arduino.move_abs(moves)
                    timeout = max_t * 1.5 + 2.0
                    t_start = time.time()
                    while self._seq_running:
                        if time.time() - t_start > timeout:
                            QTimer.singleShot(
                                0, lambda: self._update_status("[경고] DONE 미수신 — 타임아웃 후 진행"))
                            break
                        if self._seq_done_event.wait(timeout=0.05):
                            self._seq_done_event.clear()
                            break

                else:
                    QTimer.singleShot(0, lambda o=op: self._update_status(f"알 수 없는 명령: {o}"))
        finally:
            self._seq_running = False
            QTimer.singleShot(0, lambda: self._btn_seq_run.setEnabled(True))
            QTimer.singleShot(0, lambda: self._update_status("시퀀스 종료"))
            QTimer.singleShot(0, lambda: self._lbl_seq_progress.setText(f"완료 ({total}/{total})"))

    def _toggle_connect(self):
        if self._reader.isRunning():
            self._reader.disconnect()
            self._reader.quit()
            self._reader.wait(1000)
            self._btn_connect.setText("연결")
            self._ind.setStyleSheet(f"color:{C['red']}; font-size:16px;")
            self._update_status("연결 해제")
        else:
            port = self._cb_port.currentText()
            baud = int(self._cb_baud.currentText())
            if not port:
                self._update_status("포트를 선택하세요")
                return
            try:
                self._reader.connect(port, baud)
                self._reader.start()
                self._btn_connect.setText("해제")
                self._ind.setStyleSheet(f"color:{C['green']}; font-size:16px;")
                self._update_status(f"{port} @ {baud} baud 연결됨")
            except Exception as e:
                self._update_status(f"연결 실패: {e}")

    # ── 녹화 ─────────────────────────────────────────────────────────────────

    def _toggle_record(self, checked: bool):
        self._set_recording(checked)

    def _set_recording(self, on: bool):
        """RECORD 버튼 클릭과 시퀀스 파일의 RECORD ON/OFF 둘 다 여기로 모인다."""
        if on:
            self._rec_rows.clear()
            self._btn_rec.setChecked(True)
            self._btn_rec.setText("■ STOP")
            self._recording = True
            self._update_status("녹화 시작")
        else:
            self._recording = False
            self._btn_rec.setChecked(False)
            self._btn_rec.setText("● RECORD")
            self._update_status(f"녹화 중지 — {len(self._rec_rows)}행")
            self._save_csv()

    def _save_csv(self):
        if not self._rec_rows:
            self._update_status("저장할 데이터 없음")
            return
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(Path(self._save_dir) / f"moe_monitor_{now}.csv")
        hdr = ["t_s", "dL_pct", "dR_pct", "dV_pct", "IDRIVE", "STATUS",
               "strain_pct", "value", "mode", "gate_proba", "latency_us",
               "XA_mm", "YA_mm", "Z_mm", "Fz_act_N", "strain_act_pct", "value_act"]
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(hdr)
                w.writerows(self._rec_rows)
            self._update_status(f"저장 완료: {path}")
        except Exception as e:
            self._update_status(f"저장 실패: {e}")

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", self._save_dir)
        if d:
            self._save_dir = d
            self._lbl_dir.setText(d)

    # ── 상태 바 ───────────────────────────────────────────────────────────────

    def _update_status(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._sb.showMessage(f"[{ts}]  {msg}")

    def closeEvent(self, event):
        self._seq_running = False
        self._seq_done_event.set()
        self._ui_timer.stop()
        self._reader.disconnect()
        self._reader.quit()
        self._reader.wait(1000)
        self._arduino.disconnect()
        self._arduino.quit()
        self._arduino.wait(1000)
        self._rft.disconnect()
        self._rft.quit()
        self._rft.wait(1000)
        event.accept()


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("[moe_realtime_monitor] sync-fix build 2026-08-19a "
          f"(ts-lookup ground truth + STM32 decimation 1/{STM32_KEEP_EVERY_N} active)")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(C["bg"]))
    palette.setColor(QPalette.WindowText, QColor(C["text"]))
    palette.setColor(QPalette.Base, QColor(C["bg2"]))
    palette.setColor(QPalette.Text, QColor(C["text"]))
    palette.setColor(QPalette.Button, QColor(C["bg3"]))
    palette.setColor(QPalette.ButtonText, QColor(C["text"]))
    palette.setColor(QPalette.Highlight, QColor(C["blue"]))
    palette.setColor(QPalette.HighlightedText, QColor(C["bg"]))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
