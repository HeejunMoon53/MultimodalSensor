"""
moe_realtime_monitor.py
STM32 실시간 모니터링 — 후보 2(게이트+EMA MLP) MoE 디커플러 (TDMFirmware/moe_inference.c)

추론은 보드 위(STM32)에서 이미 끝나서 오는 값이라, 이 스크립트는 PC에서 추가로
모델을 돌리지 않는다 — 순수 시각화/기록 툴이다.

sync_decoupler_monitor.py의 아두이노 리니어스테이지 조그/시퀀스 제어를 그대로
가져왔고, pressure_lr_monitor.py의 RFT F/T센서 리더를 더해서 "실제값(ground truth)"을
같이 표시한다. 그래프 대신: L/R/V/게이트/진단값은 숫자 카드로, strain/근접도/압력은
실시간 막대(bar) 게이지로 보여주고, 그 막대 위에 아두이노 위치·F/T센서 기반 실제값을
선(마커)으로 같이 그려서 예측-실제를 한눈에 비교한다.

실행:
    C:/ml_env/Scripts/python moe_realtime_monitor.py

시리얼 포맷:
    STM32 (TDMFirmware/Core/Src/main.c, 115200 baud):
        dL_pct, dR_pct, dV_pct, IDRIVE, STATUS,
        strain_pct, value, mode, gate_proba, latency_us
        (실수 8개 + 정수 2개, 총 10개 컬럼)
        value : mode==0(근접) -> distance_mm / mode==1(압력) -> force_N
        mode  : moe_inference.h의 MoeMode (0=PROXIMITY, 1=PRESSURE)

    Arduino (인장/근접 스테이지, 115200 baud):
        POS? -> POS:xa:xb:ya:yb:z:...  (100ms 폴링), JOG/ZERO/EN 명령 송신

    F/T 센서 (RFT, 115200 baud):
        Fx,Fy,Fz,Tx,Ty,Tz  (N / N·m)
"""

import sys
import time
import csv
import copy
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import serial
import serial.tools.list_ports

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QFileDialog, QSplitter, QStatusBar, QFrame,
    QDoubleSpinBox, QSpinBox, QGroupBox, QTabWidget, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QCheckBox, QMessageBox,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QPalette, QPainter, QPen

BAUD_DEFAULT = 460800
BAUD_ARDUINO = 115200
BAUD_RFT     = 115200

# ── 아두이노 리니어스테이지 (sync_decoupler_monitor.py와 동일) ──────────────────
AXES          = ["XA", "XB", "YA", "YB", "Z"]
STEPS_PER_REV = 200
DEF_MICROSTEP = 8
DEF_PITCH_MM  = 5.0
ARDUINO_POLL  = 0.1
CAL_SAMPLES   = 50

# ── 실제값(ground truth) 환산 기준 ──────────────────────────────────────────
SENSOR_L0      = 120.0   # 스트레인 실제값 계산 기준 길이 (mm)
PROX_OFFSET_DEF = 0.0   # Z=0일 때 실제 거리 (mm) 기본값

# CLAUDE.md 색상 컨벤션: L=주황, R=초록, Force/TENG=파랑
COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"
COLOR_FORCE = "#1F77B4"
COLOR_DIST  = "#94e2d5"   # 거리(근접)는 컨벤션 외 채널이라 별도 teal 사용

# Catppuccin Mocha
C = {
    "bg": "#1e1e2e", "bg2": "#181825", "bg3": "#313244",
    "text": "#cdd6f4", "text2": "#a6adc8",
    "blue": COLOR_FORCE, "green": COLOR_R, "orange": COLOR_L,
    "yellow": "#f9e2af", "mauve": "#cba6f7", "red": "#f38ba8",
    "teal": COLOR_DIST, "border": "#45475a", "peach": "#fab387",
}

MODE_NAMES  = {0: "근접", 1: "압력"}
MODE_TITLES = {0: "근접 거리 PROXIMITY", 1: "압력 힘 PRESSURE"}
MODE_COLORS = {0: COLOR_DIST, 1: COLOR_FORCE}
MODE_UNITS  = {0: "mm", 1: "N"}
MODE_RANGES = {0: (0.0, 30.0), 1: (0.0, 30.0)}


# ══════════════════════════════════════════════════════════════════════════════
# 시리얼 리더 / 컨트롤러
# ══════════════════════════════════════════════════════════════════════════════

class STM32Reader(QThread):
    """MoE 디커플러 보드 시리얼 리더.

    100Hz로 매 줄마다 pyqtSignal을 emit하면 스레드 간 큐잉(marshalling) 비용이
    쌓여서 UI가 느려진다 — 대신 파싱한 값을 잠금 없는 deque에 쌓아두기만 하고,
    UI 타이머가 한 번에 다 걷어가는(drain) 방식으로 처리한다.
    """
    error_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser = None
        self._running = False
        self._queue = deque()

    def connect(self, port: str, baud: int = BAUD_DEFAULT):
        self._ser = serial.Serial(port, baud, timeout=0.2)
        time.sleep(0.5)
        self._running = True

    def disconnect(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()

    def drain(self):
        """누적된 (ts, vals) 항목을 전부 가져오고 큐를 비운다. UI 타이머에서 호출."""
        old, self._queue = self._queue, deque()
        return old

    def run(self):
        while self._running:
            try:
                if not self._ser:
                    time.sleep(0.05)
                    continue
                raw = self._ser.readline()   # timeout(0.2s) 안에 '\n' 못 만나면 빈 bytes 반환
                if not raw:
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


class ArduinoController(QThread):
    """인장/근접 리니어스테이지 컨트롤러 (sync_decoupler_monitor.py에서 그대로 이식)."""
    position_updated = pyqtSignal(float, dict)
    done_received    = pyqtSignal()
    alarm_received    = pyqtSignal(str)
    error_msg        = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser = None; self._running = False
        self._lock = threading.Lock()
        self._cmd_queue = deque()
        self.steps_per_mm = (STEPS_PER_REV * DEF_MICROSTEP) / DEF_PITCH_MM

    def connect(self, port, baud=BAUD_ARDUINO, steps_per_mm=None):
        if steps_per_mm: self.steps_per_mm = steps_per_mm
        self._ser = serial.Serial(port, baud, timeout=0.2)
        time.sleep(2.0); self._running = True

    def disconnect(self):
        self._running = False
        if self._ser and self._ser.is_open: self._ser.close()

    def send(self, cmd: str):
        with self._lock: self._cmd_queue.append(cmd)

    def jog(self, axis: str, dist_mm: float, speed_mms: float = 5.0):
        steps = int(dist_mm * self.steps_per_mm)   # 부호 유지, 속도 미포함
        self.send(f"JOG:{axis}:{steps}")

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
                        if pos: self.position_updated.emit(time.time(), pos)
                    elif line == "DONE":
                        self.done_received.emit()
                    elif "ALARM" in line:
                        self.alarm_received.emit(line)
                else:
                    time.sleep(0.005)
            except Exception as e:
                self.error_msg.emit(str(e)); time.sleep(0.1)

    def _parse_pos(self, line):
        try:
            vals = [float(v) for v in line.split(":")[1:]]
            return {ax: round(vals[i] / self.steps_per_mm, 3)
                    for i, ax in enumerate(AXES) if i < len(vals)}
        except Exception:
            return None


class RFTReader(QThread):
    """RFT F/T 센서 리더 (pressure_lr_monitor.py에서 그대로 이식). Fx,Fy,Fz,Tx,Ty,Tz."""
    data_received = pyqtSignal(float, list)
    error_msg     = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser = None; self._running = False

    def connect(self, port, baud=BAUD_RFT):
        self._ser = serial.Serial(port, baud, timeout=0.1)
        time.sleep(0.5); self._running = True

    def disconnect(self):
        self._running = False
        if self._ser and self._ser.is_open: self._ser.close()

    def run(self):
        buf = ""
        while self._running:
            try:
                if self._ser and self._ser.in_waiting:
                    buf += self._ser.read(self._ser.in_waiting).decode("utf-8", errors="ignore")
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if not line or line.startswith("#"): continue
                        vals = self._parse(line)
                        if vals: self.data_received.emit(time.time(), vals)
                else:
                    time.sleep(0.001)
            except Exception as e:
                self.error_msg.emit(str(e)); time.sleep(0.1)

    @staticmethod
    def _parse(line):
        try:
            vals = [float(v.strip()) for v in line.split(",")]
            return vals[:6] if len(vals) >= 6 else None
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# UI 헬퍼 위젯
# ══════════════════════════════════════════════════════════════════════════════

def _hline():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color:{C['border']};"); return f


def _vline():
    f = QFrame(); f.setFrameShape(QFrame.VLine)
    f.setStyleSheet(f"color:{C['border']};"); return f


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
        self._val.setStyleSheet(f"color:{color}; font-size:26px; font-weight:700; font-family:Consolas;")
        row.addWidget(self._val)
        row.addStretch()
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet(f"color:{C['text2']}; font-size:12px; margin-top:8px;")
        row.addWidget(unit_lbl)
        vbox.addLayout(row)

        self.setStyleSheet(f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;")

    def update(self, val, color: str = None):
        if val is None:
            self._val.setText("—")
        else:
            self._val.setText(self._fmt.format(val))
        self._val.setStyleSheet(
            f"color:{color or self._base_color}; font-size:26px; font-weight:700; font-family:Consolas;")


class _BarCanvas(QWidget):
    """BarGauge 안에서 실제로 막대를 그리는 캔버스. 예측값 채움막대 + 실제값 세로선 마커."""

    def __init__(self):
        super().__init__()
        self._lo, self._hi = 0.0, 1.0
        self._pred = None
        self._pred_color = C["text2"]
        self._actual = None
        self.setMinimumHeight(34)

    def set_range(self, lo, hi):
        self._lo, self._hi = lo, hi
        self.update()

    def set_predicted(self, val, color=None):
        self._pred = val
        if color: self._pred_color = color
        self.update()

    def set_actual(self, val):
        self._actual = val
        self.update()

    def _frac(self, val):
        span = max(1e-9, self._hi - self._lo)
        return max(0.0, min(1.0, (val - self._lo) / span))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["bg3"]))
        p.drawRoundedRect(0, 0, w, h, 6, 6)

        if self._pred is not None:
            frac = self._frac(self._pred)
            p.setBrush(QColor(self._pred_color))
            fw = max(6, int(w * frac))
            p.drawRoundedRect(0, 0, fw, h, 6, 6)

        if self._actual is not None:
            x = int(w * self._frac(self._actual))
            x = max(1, min(w - 1, x))
            pen = QPen(QColor(C["text"]))
            pen.setWidth(3)
            p.setPen(pen)
            p.drawLine(x, -2, x, h + 2)

        p.end()


class BarGauge(QWidget):
    """실시간 막대 게이지: 예측값(채워진 막대) + 실제값(세로선 마커) + 숫자 오버레이.

    제목/단위/색/범위를 실행 중에 바꿀 수 있어서, 근접-압력처럼 모드에 따라
    의미가 바뀌는 채널을 색만 다르게 하나의 막대로 표현하는 데 쓴다.
    """

    def __init__(self, title: str, unit: str, lo: float, hi: float, color: str, fmt: str = "{:.2f}"):
        super().__init__()
        self._unit = unit
        self._color = color
        self._fmt = fmt

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(14, 10, 14, 10)
        vbox.setSpacing(6)

        head = QHBoxLayout()
        self._lbl_title = QLabel(title)
        self._lbl_title.setStyleSheet(
            f"color:{C['text2']}; font-size:12px; font-weight:700; letter-spacing:1px;")
        head.addWidget(self._lbl_title)
        head.addStretch()
        self._lbl_val = QLabel("—")
        self._lbl_val.setStyleSheet(
            f"color:{color}; font-size:26px; font-weight:700; font-family:Consolas;")
        head.addWidget(self._lbl_val)
        self._lbl_unit = QLabel(unit)
        self._lbl_unit.setStyleSheet(f"color:{C['text2']}; font-size:12px; margin-left:4px; margin-top:8px;")
        head.addWidget(self._lbl_unit)
        vbox.addLayout(head)

        self._canvas = _BarCanvas()
        self._canvas.set_range(lo, hi)
        self._canvas.set_predicted(None, color)
        vbox.addWidget(self._canvas)

        foot = QHBoxLayout()
        self._lbl_lo = QLabel(f"{lo:g}")
        self._lbl_lo.setStyleSheet(f"color:{C['text2']}; font-size:9px; font-family:Consolas;")
        foot.addWidget(self._lbl_lo)
        foot.addStretch()
        self._lbl_actual = QLabel("실제값: —")
        self._lbl_actual.setStyleSheet(f"color:{C['text']}; font-size:11px; font-family:Consolas; font-weight:600;")
        foot.addWidget(self._lbl_actual)
        foot.addStretch()
        self._lbl_hi = QLabel(f"{hi:g}")
        self._lbl_hi.setStyleSheet(f"color:{C['text2']}; font-size:9px; font-family:Consolas;")
        foot.addWidget(self._lbl_hi)
        vbox.addLayout(foot)

        self.setStyleSheet(f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:10px;")

    # ── 세터 ─────────────────────────────────────────────────────────────────

    def set_title(self, title: str):
        self._lbl_title.setText(title)

    def set_unit(self, unit: str):
        self._unit = unit
        self._lbl_unit.setText(unit)

    def set_range(self, lo: float, hi: float):
        self._canvas.set_range(lo, hi)
        self._lbl_lo.setText(f"{lo:g}")
        self._lbl_hi.setText(f"{hi:g}")

    def set_value(self, val, color: str = None):
        if color:
            self._color = color
            self._lbl_val.setStyleSheet(
                f"color:{color}; font-size:26px; font-weight:700; font-family:Consolas;")
        self._lbl_val.setText("—" if val is None else self._fmt.format(val))
        self._canvas.set_predicted(val, color)

    def set_actual(self, val):
        self._lbl_actual.setText(
            "실제값: —" if val is None else f"실제값: {self._fmt.format(val)} {self._unit}")
        self._canvas.set_actual(val)


# ══════════════════════════════════════════════════════════════════════════════
# 메인 윈도우
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    _seq_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MoE Decoupler Monitor — 게이트+EMA (후보 2)")
        self.resize(1500, 900)

        self._stm32   = STM32Reader()
        self._arduino = ArduinoController()
        self._rft     = RFTReader()

        # 최신값 저장(그래프를 없앴으므로 히스토리 버퍼 대신 마지막 값만 유지)
        self._t0 = None
        self._latest = {}
        self._freq_ts = deque(maxlen=100)

        self._last_pos = {ax: 0.0 for ax in AXES}
        self._prox_offset = PROX_OFFSET_DEF
        self._cal_buf_fz = deque(maxlen=CAL_SAMPLES)
        self._fz_offset = 0.0
        self._f_act = None       # F/T 기반 실제 힘 (영점 보정 완료)
        self._f_act_raw = None   # 영점 보정 전 값

        # 모터 / 시퀀스 상태
        self._motor_enabled  = False
        self._is_running_seq = False
        self._done_event = threading.Event()
        self._seq_data    = []
        self._clipboard   = []
        self._editing_idx = None

        self._settings = {
            "microstep": DEF_MICROSTEP, "pitch_mm": DEF_PITCH_MM,
            "jog_small": 0.5, "jog_mid": 2.0, "jog_large": 10.0,
            "jog_speed": 5.0,
        }
        self._apply_settings()

        self._recording = False
        self._rec_rows = []
        self._save_dir = str(Path.home())

        self._build_ui()
        self._connect_signals()
        self._seq_finished.connect(lambda: self._btn_run_seq.setEnabled(True))

        self._ui_timer = QTimer()
        self._ui_timer.setTimerType(Qt.PreciseTimer)
        self._ui_timer.timeout.connect(self._refresh)
        self._ui_timer.start(15)   # ~66 fps

    def _apply_settings(self):
        spm = (STEPS_PER_REV * self._settings["microstep"]) / self._settings["pitch_mm"]
        self._arduino.steps_per_mm = spm

    # ── UI 구성 ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 6)

        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_pos_bar())
        root.addWidget(_hline())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([420, 940])
        root.addWidget(splitter, stretch=1)

        root.addWidget(_hline())
        root.addWidget(self._build_record_bar())

        sb = QStatusBar()
        sb.setStyleSheet(f"color:{C['text2']}; font-size:12px;")
        self.setStatusBar(sb)
        self._sb = sb
        self._update_status("미연결")

    def _build_top_bar(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0); lay.setSpacing(6)

        def _port_group(label, cb_attr, btn_attr, ind_attr, toggle_fn):
            lay.addWidget(self._lbl(label))
            cb = QComboBox(); cb.setMinimumWidth(95)
            setattr(self, cb_attr, cb); lay.addWidget(cb)
            btn = QPushButton("연결"); btn.setFixedSize(56, 28)
            btn.clicked.connect(toggle_fn)
            setattr(self, btn_attr, btn); lay.addWidget(btn)
            ind = QLabel("●"); ind.setStyleSheet(f"color:{C['red']}; font-size:14px;")
            setattr(self, ind_attr, ind); lay.addWidget(ind)

        _port_group("STM32",   "_cb_stm32",   "_btn_stm32",   "_ind_stm32",   self._toggle_stm32)
        lay.addWidget(_vline())
        _port_group("Arduino", "_cb_arduino", "_btn_arduino", "_ind_arduino", self._toggle_arduino)
        lay.addWidget(_vline())
        _port_group("F/T",     "_cb_rft",     "_btn_rft",     "_ind_rft",     self._toggle_rft)

        btn_ref = QPushButton("⟳"); btn_ref.setFixedSize(28, 28)
        btn_ref.setToolTip("포트 목록 새로고침"); btn_ref.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_ref)

        lay.addWidget(_vline())

        self._btn_motor = QPushButton("ENABLE")
        self._btn_motor.setFixedHeight(28)
        self._btn_motor.setStyleSheet(f"background:{C['green']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
        self._btn_motor.clicked.connect(self._toggle_motor)
        lay.addWidget(self._btn_motor)

        btn_zero = QPushButton("ZERO")
        btn_zero.setFixedHeight(28)
        btn_zero.clicked.connect(self._set_zero)
        lay.addWidget(btn_zero)

        btn_zero_ft = QPushButton("Zero F/T")
        btn_zero_ft.setFixedHeight(28)
        btn_zero_ft.setStyleSheet(
            f"background:{C['bg3']}; color:{C['blue']}; border:1px solid {C['blue']}; border-radius:4px;")
        btn_zero_ft.clicked.connect(self._zero_ft)
        lay.addWidget(btn_zero_ft)

        lay.addStretch()

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

    def _build_pos_bar(self):
        bar = QGroupBox("현재 위치 (mm) / 실측 힘 (N)")
        bar.setMaximumHeight(60)
        grid = QGridLayout(bar)
        grid.setContentsMargins(8, 2, 8, 2); grid.setSpacing(4)
        self._pos_labels = {}
        cols = AXES + ["Fz"]
        for i, ax in enumerate(cols):
            grid.addWidget(QLabel(ax, alignment=Qt.AlignCenter), 0, i)
            lbl = QLabel("0.000", alignment=Qt.AlignCenter)
            col = C["blue"] if ax == "Fz" else C["text"]
            lbl.setStyleSheet(f"font-size:16px; font-weight:700; color:{col}; font-family:Consolas;")
            grid.addWidget(lbl, 1, i)
            self._pos_labels[ax] = lbl
        return bar

    # ── 좌측 패널: 탭 (센서 / 수동 조그 / 시퀀스) ───────────────────────────────

    def _build_left_panel(self):
        tabs = QTabWidget()
        tabs.addTab(self._build_sensor_tab(), "센서")
        tabs.addTab(self._build_manual_tab(), "수동 조그")
        tabs.addTab(self._build_sequence_tab(), "시퀀스 프로그램")
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

        vbox.addSpacing(2)
        vbox.addWidget(_hline())
        vbox.addWidget(self._sec_lbl("진단"))
        diag = QHBoxLayout()
        self._cards["idrive"]  = ValueCard("IDRIVE", "", C["text2"], "{:.0f}")
        self._cards["status"]  = ValueCard("STATUS", "", C["text2"], "{:.0f}")
        self._cards["latency"] = ValueCard("추론 지연", "µs", C["text2"], "{:.1f}")
        diag.addWidget(self._cards["idrive"])
        diag.addWidget(self._cards["status"])
        diag.addWidget(self._cards["latency"])
        vbox.addLayout(diag)
        self._cards["gate"] = ValueCard("게이트 P(접촉)", "", C["yellow"], "{:.3f}")
        vbox.addWidget(self._cards["gate"])

        vbox.addSpacing(2)
        vbox.addWidget(_hline())
        vbox.addWidget(self._sec_lbl("GROUND TRUTH (Arduino / F-T)"))

        row_gt = QHBoxLayout()
        self._lbl_xa_mono = self._mono("YA: —")
        self._lbl_z_mono  = self._mono("Z: —")
        row_gt.addWidget(self._lbl_xa_mono); row_gt.addWidget(self._lbl_z_mono)
        vbox.addLayout(row_gt)
        self._lbl_fz_mono = self._mono("Fz(실제): —")
        vbox.addWidget(self._lbl_fz_mono)

        row_off = QHBoxLayout()
        lbl_off = QLabel("Z=0 기준거리 (mm)")
        lbl_off.setStyleSheet(f"color:{C['text2']}; font-size:11px;")
        row_off.addWidget(lbl_off)
        self._spin_prox = QDoubleSpinBox()
        self._spin_prox.setRange(0, 200); self._spin_prox.setSingleStep(1)
        self._spin_prox.setDecimals(1); self._spin_prox.setValue(self._prox_offset)
        self._spin_prox.setFixedWidth(80)
        self._spin_prox.setStyleSheet(
            f"background:{C['bg3']}; color:{C['peach']}; border:1px solid {C['border']}; "
            f"border-radius:4px; font-family:Consolas;")
        self._spin_prox.valueChanged.connect(lambda v: setattr(self, "_prox_offset", v))
        row_off.addWidget(self._spin_prox)
        vbox.addLayout(row_off)

        vbox.addStretch()
        return w

    # ── 수동 조그 탭 (sync_decoupler_monitor.py에서 이식) ──────────────────────

    def _build_manual_tab(self):
        w = QWidget(); vbox = QVBoxLayout(w)
        s = self._settings

        jog_grp = QGroupBox("조그 제어")
        jog_grid = QGridLayout(jog_grp)
        jog_grid.setSpacing(3)

        jog_defs = [
            (f"<<<\n{s['jog_large']}mm", -s["jog_large"]),
            (f"<<\n{s['jog_mid']}mm",    -s["jog_mid"]),
            (f"<\n{s['jog_small']}mm",   -s["jog_small"]),
            (f">\n{s['jog_small']}mm",    s["jog_small"]),
            (f">>\n{s['jog_mid']}mm",     s["jog_mid"]),
            (f">>>\n{s['jog_large']}mm",  s["jog_large"]),
        ]

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

        row_spd = QHBoxLayout()
        row_spd.addWidget(self._small_lbl("조그 속도 (mm/s)"))
        self._spin_jog_spd = QDoubleSpinBox()
        self._spin_jog_spd.setRange(0.1, 50); self._spin_jog_spd.setSingleStep(0.5)
        self._spin_jog_spd.setValue(s["jog_speed"]); self._spin_jog_spd.setFixedWidth(80)
        self._spin_jog_spd.valueChanged.connect(lambda v: self._settings.update({"jog_speed": v}))
        row_spd.addWidget(self._spin_jog_spd); row_spd.addStretch()
        vbox.addLayout(row_spd)
        vbox.addStretch()
        return w

    # ── 시퀀스 탭 (sync_decoupler_monitor.py에서 이식) ─────────────────────────

    def _build_sequence_tab(self):
        w = QWidget(); vbox = QVBoxLayout(w)

        inp_grp = QGroupBox("스텝 입력")
        inp_lay = QGridLayout(inp_grp)

        self._cb_mode_seq = QComboBox()
        self._cb_mode_seq.addItems(["대칭 이동 (Symmetric)", "개별 이동 (Individual)", "대기 (Delay)"])
        self._cb_mode_seq.currentIndexChanged.connect(self._update_seq_inputs)
        inp_lay.addWidget(QLabel("유형:"), 0, 0)
        inp_lay.addWidget(self._cb_mode_seq, 0, 1, 1, 3)

        self._chk_sync = QCheckBox("동기 이동 (총 시간 지정)")
        self._lbl_sync_t = QLabel("총 시간 (s):")
        self._sp_sync_t = QDoubleSpinBox()
        self._sp_sync_t.setRange(0.01, 9999); self._sp_sync_t.setValue(5.0)
        self._sp_sync_t.setSingleStep(0.5); self._sp_sync_t.setEnabled(False)
        self._chk_sync.toggled.connect(self._on_sync_toggled)
        inp_lay.addWidget(self._chk_sync, 1, 0, 1, 2)
        inp_lay.addWidget(self._lbl_sync_t, 1, 2)
        inp_lay.addWidget(self._sp_sync_t, 1, 3)

        self._seq_input_widget = QWidget()
        self._seq_input_layout = QGridLayout(self._seq_input_widget)
        inp_lay.addWidget(self._seq_input_widget, 2, 0, 1, 4)

        btn_add = QPushButton("스텝 추가"); btn_add.clicked.connect(self._add_seq_step)
        btn_cancel = QPushButton("편집 취소"); btn_cancel.clicked.connect(self._cancel_edit)
        inp_lay.addWidget(btn_add, 3, 0, 1, 2)
        inp_lay.addWidget(btn_cancel, 3, 2, 1, 2)
        vbox.addWidget(inp_grp)

        self._seq_tree = QTreeWidget()
        self._seq_tree.setHeaderLabels(["#", "유형", "내용", "속도"])
        self._seq_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self._seq_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._seq_tree.itemDoubleClicked.connect(self._load_for_edit)
        vbox.addWidget(self._seq_tree, stretch=1)

        btn_row = QHBoxLayout()
        for label, slot in [("▲", self._seq_up), ("▼", self._seq_down),
                             ("삭제", self._seq_delete), ("전체삭제", self._seq_clear),
                             ("복사", self._seq_copy), ("붙여넣기", self._seq_paste)]:
            b = QPushButton(label); b.setFixedHeight(28); b.clicked.connect(slot)
            btn_row.addWidget(b)
        vbox.addLayout(btn_row)

        run_row = QHBoxLayout()
        self._btn_run_seq = QPushButton("▶ 시퀀스 실행")
        self._btn_run_seq.setFixedHeight(32)
        self._btn_run_seq.setStyleSheet(f"background:{C['blue']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
        self._btn_run_seq.clicked.connect(self._run_sequence)
        self._btn_stop_seq = QPushButton("■ 정지")
        self._btn_stop_seq.setFixedHeight(32)
        self._btn_stop_seq.clicked.connect(self._stop_sequence)
        run_row.addWidget(self._btn_run_seq); run_row.addWidget(self._btn_stop_seq)
        run_row.addSpacing(8)
        run_row.addWidget(self._small_lbl("반복"))
        self._spin_repeat = QSpinBox()
        self._spin_repeat.setRange(0, 9999); self._spin_repeat.setValue(1)
        self._spin_repeat.setFixedWidth(60)
        self._spin_repeat.setToolTip("반복 횟수 (0 = 무한 반복)")
        self._spin_repeat.setStyleSheet(
            f"background:{C['bg3']}; color:{C['peach']}; border:1px solid {C['border']}; "
            f"border-radius:4px; font-family:Consolas;")
        run_row.addWidget(self._spin_repeat)
        run_row.addWidget(self._small_lbl("회  (0=∞)"))
        vbox.addLayout(run_row)

        self._log_box = QTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setMaximumHeight(80)
        self._log_box.setStyleSheet(f"background:{C['bg2']}; color:{C['text2']}; font-size:11px; font-family:Consolas;")
        vbox.addWidget(self._log_box)

        self._update_seq_inputs()
        return w

    # ── 우측 패널: 실시간 막대 게이지 ────────────────────────────────────────────

    def _build_right_panel(self):
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.setSpacing(14)

        vbox.addWidget(self._sec_lbl("STRAIN / PROXIMITY / PRESSURE — 예측(막대) vs 실제(세로선)"))

        self._gauge_strain = BarGauge("STRAIN", "%", 0.0, 30.0, C["mauve"], "{:.2f}")
        vbox.addWidget(self._gauge_strain)

        self._gauge_pf = BarGauge(MODE_TITLES[0], MODE_UNITS[0], *MODE_RANGES[0], MODE_COLORS[0], "{:.2f}")
        vbox.addWidget(self._gauge_pf)

        for g in (self._gauge_strain, self._gauge_pf):
            g.setMinimumHeight(120)

        vbox.addStretch()
        return w

    # ── 녹화 바 ───────────────────────────────────────────────────────────────

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

    # ── 헬퍼 ──────────────────────────────────────────────────────────────────

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{C['text2']}; font-weight:600;")
        return lbl

    def _small_lbl(self, t):
        l = QLabel(t); l.setStyleSheet(f"color:{C['text2']}; font-size:11px;"); return l

    def _sec_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{C['text2']}; font-size:10px; font-weight:700; letter-spacing:2px; margin-top:4px;")
        return lbl

    def _mono(self, t):
        l = QLabel(t)
        l.setStyleSheet(
            f"color:{C['teal']}; font-size:11px; font-family:Consolas; background:{C['bg2']}; "
            f"border:1px solid {C['border']}; border-radius:4px; padding:1px 5px;")
        return l

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        QTimer.singleShot(0, lambda: (
            self._log_box.append(f"[{ts}] {msg}"),
            self._log_box.verticalScrollBar().setValue(
                self._log_box.verticalScrollBar().maximum())
        ))

    # ── 시그널 연결 ───────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._stm32.error_msg.connect(lambda m: self._update_status(f"STM32: {m}"))
        self._arduino.position_updated.connect(self._on_arduino_pos)
        self._arduino.done_received.connect(self._on_done)
        self._arduino.alarm_received.connect(lambda m: self._log(f"[ALARM] {m}"))
        self._arduino.error_msg.connect(lambda m: self._update_status(f"Arduino: {m}"))
        self._rft.data_received.connect(self._on_rft_data)
        self._rft.error_msg.connect(lambda m: self._update_status(f"F/T: {m}"))

    # ── 데이터 수신 ───────────────────────────────────────────────────────────

    def _ingest(self, ts: float, vals: list):
        dL, dR, dV, idrive, status, strain, value, mode, gate_proba, latency_us = vals

        if self._t0 is None:
            self._t0 = ts
        t = ts - self._t0

        self._latest.update({
            "dL": dL, "dR": dR, "dV": dV, "idrive": idrive, "status": status,
            "strain": strain, "value": value, "mode": mode,
            "gate": gate_proba, "latency": latency_us,
        })
        self._freq_ts.append(ts)

        if self._recording:
            ya = self._last_pos.get("YA"); yb = self._last_pos.get("YB")
            z  = self._last_pos.get("Z")
            if ya is not None and yb is not None:
                eps_act = (abs(ya) + abs(yb)) / SENSOR_L0 * 100.0
            elif ya is not None:
                eps_act = abs(ya) * 2.0 / SENSOR_L0 * 100.0
            else:
                eps_act = None
            if mode == 0:
                value_act = z if z is not None else None
            elif mode == 1:
                value_act = self._f_act
            else:
                value_act = None
            self._rec_rows.append([
                round(t, 4), dL, dR, dV, idrive, status,
                round(strain, 4), round(value, 4), mode,
                round(gate_proba, 4), round(latency_us, 2),
                ya if ya is not None else "", yb if yb is not None else "",
                z if z is not None else "",
                round(self._f_act, 4) if self._f_act is not None else "",
                round(eps_act, 4) if eps_act is not None else "",
                round(value_act, 4) if value_act is not None else "",
            ])
            self._lbl_rec_count.setText(f"{len(self._rec_rows)}행")

    def _on_arduino_pos(self, ts, pos):
        self._last_pos.update(pos)

    def _on_done(self):
        self._done_event.set()

    def _on_rft_data(self, ts, vals):
        # 센서 장착 방향 보정: 누르는 방향(아래)이 양수가 되도록 부호 반전
        fz = -vals[2]
        self._cal_buf_fz.append(fz)
        self._f_act_raw = fz
        self._f_act = fz - self._fz_offset

    # ── 화면 갱신 ─────────────────────────────────────────────────────────────

    def _refresh(self):
        for ts, vals in self._stm32.drain():
            self._ingest(ts, vals)

        L = self._latest
        self._cards["dL"].update(L.get("dL"))
        self._cards["dR"].update(L.get("dR"))
        self._cards["dV"].update(L.get("dV"))
        self._cards["gate"].update(L.get("gate"))
        self._cards["idrive"].update(L.get("idrive"))
        self._cards["status"].update(L.get("status"))
        self._cards["latency"].update(L.get("latency"))

        ya = self._last_pos.get("YA"); yb = self._last_pos.get("YB")
        z  = self._last_pos.get("Z")
        if ya is not None and yb is not None:
            eps_act = (abs(ya) + abs(yb)) / SENSOR_L0 * 100.0
        elif ya is not None:
            eps_act = abs(ya) * 2.0 / SENSOR_L0 * 100.0
        else:
            eps_act = None

        self._gauge_strain.set_value(L.get("strain"))
        self._gauge_strain.set_actual(eps_act)

        mode = L.get("mode")
        if mode is not None:
            name = MODE_NAMES.get(mode, "?")
            col  = MODE_COLORS.get(mode, C["text2"])
            self._lbl_mode.setText(f"모드: {name}")
            self._lbl_mode.setStyleSheet(
                f"color:{col}; font-size:13px; font-weight:700; font-family:Consolas; "
                f"padding:4px 10px; border:1px solid {col}; border-radius:5px;")

            self._gauge_pf.set_title(MODE_TITLES.get(mode, "VALUE"))
            self._gauge_pf.set_unit(MODE_UNITS.get(mode, ""))
            self._gauge_pf.set_range(*MODE_RANGES.get(mode, (0.0, 30.0)))
            self._gauge_pf.set_value(L.get("value"), color=col)
            if mode == 0:
                d_act = z if z is not None else None
                self._gauge_pf.set_actual(d_act)
            elif mode == 1:
                self._gauge_pf.set_actual(self._f_act)
            else:
                self._gauge_pf.set_actual(None)

        for ax in AXES:
            self._pos_labels[ax].setText(f"{self._last_pos.get(ax, 0.0):.3f}")
        self._pos_labels["Fz"].setText(
            f"{self._f_act:+.3f}" if self._f_act is not None else "—")

        self._lbl_xa_mono.setText(f"YA:{ya:+7.3f}mm" if ya is not None else "YA: —")
        self._lbl_z_mono.setText(f"Z:{z:+7.3f}mm" if z is not None else "Z: —")
        self._lbl_fz_mono.setText(
            f"Fz(실제):{self._f_act:+7.3f}N" if self._f_act is not None else "Fz(실제): —")

        if len(self._freq_ts) >= 2:
            elapsed = self._freq_ts[-1] - self._freq_ts[0]
            if elapsed > 0:
                self._lbl_hz.setText(f"{(len(self._freq_ts) - 1) / elapsed:.1f} Hz")

    # ── 포트 관리 ─────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for cb in [self._cb_stm32, self._cb_arduino, self._cb_rft]:
            cur = cb.currentText(); cb.clear(); cb.addItems(ports)
            if cur in ports: cb.setCurrentText(cur)

    def _toggle_stm32(self):
        if self._stm32.isRunning():
            self._stm32.disconnect(); self._stm32.quit(); self._stm32.wait(1000)
            self._btn_stm32.setText("연결")
            self._ind_stm32.setStyleSheet(f"color:{C['red']}; font-size:14px;")
            self._update_status("STM32 해제")
        else:
            port = self._cb_stm32.currentText()
            if not port:
                self._update_status("STM32 포트를 선택하세요"); return
            try:
                self._stm32.connect(port, BAUD_DEFAULT)
                self._stm32.start()
                self._btn_stm32.setText("해제")
                self._ind_stm32.setStyleSheet(f"color:{C['green']}; font-size:14px;")
                self._update_status(f"STM32 {port} 연결됨")
            except Exception as e:
                self._update_status(f"STM32 연결 실패: {e}")

    def _toggle_arduino(self):
        if self._arduino.isRunning():
            self._is_running_seq = False; self._done_event.set()
            self._arduino.disconnect(); self._arduino.quit(); self._arduino.wait(2000)
            self._btn_arduino.setText("연결")
            self._ind_arduino.setStyleSheet(f"color:{C['red']}; font-size:14px;")
            self._last_pos = {ax: 0.0 for ax in AXES}
            self._motor_enabled = False
            self._btn_motor.setText("ENABLE")
            self._btn_motor.setStyleSheet(f"background:{C['green']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
            self._update_status("Arduino 해제")
        else:
            port = self._cb_arduino.currentText()
            if not port:
                self._update_status("Arduino 포트를 선택하세요"); return
            try:
                self._apply_settings()
                self._arduino.connect(port, BAUD_ARDUINO)
                self._arduino.start()
                self._btn_arduino.setText("해제")
                self._ind_arduino.setStyleSheet(f"color:{C['green']}; font-size:14px;")
                self._update_status(f"Arduino {port} 연결됨")
            except Exception as e:
                self._update_status(f"Arduino 연결 실패: {e}")

    def _toggle_rft(self):
        if self._rft.isRunning():
            self._rft.disconnect(); self._rft.quit(); self._rft.wait(1000)
            self._btn_rft.setText("연결")
            self._ind_rft.setStyleSheet(f"color:{C['red']}; font-size:14px;")
            self._update_status("F/T 해제")
        else:
            port = self._cb_rft.currentText()
            if not port:
                self._update_status("F/T 포트를 선택하세요"); return
            try:
                self._rft.connect(port, BAUD_RFT)
                self._rft.start()
                self._btn_rft.setText("해제")
                self._ind_rft.setStyleSheet(f"color:{C['green']}; font-size:14px;")
                self._update_status(f"F/T {port} 연결됨")
            except Exception as e:
                self._update_status(f"F/T 연결 실패: {e}")

    def _zero_ft(self):
        if len(self._cal_buf_fz) < 5:
            self._update_status("F/T 영점 실패: 데이터 부족"); return
        self._fz_offset = float(np.mean(self._cal_buf_fz))
        self._update_status(f"F/T 영점 완료: offset={self._fz_offset:+.4f} N")

    # ── 모터 / 조그 ───────────────────────────────────────────────────────────

    def _toggle_motor(self):
        if not self._arduino.isRunning():
            self._update_status("Arduino 미연결"); return
        if self._motor_enabled:
            self._arduino.send("EN:0")   # FREE: motor releases, can rotate freely
            self._motor_enabled = False
            self._btn_motor.setText("ENABLE")
            self._btn_motor.setStyleSheet(f"background:{C['green']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
            self._log("모터 DISABLED")
        else:
            self._arduino.send("EN:1")   # LOCKED: motor energized, accepts commands
            self._motor_enabled = True
            self._btn_motor.setText("DISABLE")
            self._btn_motor.setStyleSheet(f"background:{C['yellow']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
            self._log("모터 ENABLED")

    def _set_zero(self):
        self._arduino.send("ZERO:0"); self._log("원점 설정")

    def _do_jog(self, axis: str, dist_mm: float):
        if not self._arduino.isRunning():
            self._update_status("Arduino 미연결"); return
        if not self._motor_enabled:
            self._update_status("모터 ENABLE 필요"); return
        self._arduino.jog(axis, dist_mm, self._settings["jog_speed"])

    # ── 시퀀스 입력 관리 (sync_decoupler_monitor.py에서 이식) ──────────────────

    def _update_seq_inputs(self):
        for i in reversed(range(self._seq_input_layout.count())):
            w = self._seq_input_layout.itemAt(i).widget()
            if w: w.deleteLater()

        mode = self._cb_mode_seq.currentIndex()
        self._seq_spins = {}
        lay = self._seq_input_layout

        is_delay = (mode == 2)
        self._chk_sync.setEnabled(not is_delay)
        if is_delay: self._chk_sync.setChecked(False)

        if mode == 0:  # 대칭
            for col, h in enumerate(["그룹", "거리 (mm)", "속도 (mm/s)"]):
                lay.addWidget(QLabel(h), 0, col)
            for row, (label, dk, sk) in enumerate([
                ("X (XA/XB)", "tot_x", "x_spd"),
                ("Y (YA/YB)", "tot_y", "y_spd"),
                ("Z",         "z",     "z_spd"),
            ]):
                lay.addWidget(QLabel(label), row + 1, 0)
                sp_d = QDoubleSpinBox(); sp_d.setRange(-500, 500); sp_d.setSingleStep(1)
                lay.addWidget(sp_d, row + 1, 1)
                sp_s = QDoubleSpinBox(); sp_s.setRange(0.1, 50); sp_s.setValue(5.0)
                lay.addWidget(sp_s, row + 1, 2)
                self._seq_spins[dk] = sp_d; self._seq_spins[sk] = sp_s

        elif mode == 1:  # 개별
            for col, h in enumerate(["축", "거리 (mm)", "속도 (mm/s)"]):
                lay.addWidget(QLabel(h), 0, col)
            for i, ax in enumerate(AXES):
                lay.addWidget(QLabel(ax), i + 1, 0)
                sp_d = QDoubleSpinBox(); sp_d.setRange(-500, 500); sp_d.setSingleStep(1)
                lay.addWidget(sp_d, i + 1, 1)
                sp_s = QDoubleSpinBox(); sp_s.setRange(0.1, 50); sp_s.setValue(5.0)
                lay.addWidget(sp_s, i + 1, 2)
                self._seq_spins[ax] = sp_d; self._seq_spins[f"{ax}_spd"] = sp_s

        else:  # 대기
            lay.addWidget(QLabel("대기 시간 (ms)"), 0, 0)
            sp = QSpinBox(); sp.setRange(0, 60000); sp.setValue(1000); sp.setSingleStep(100)
            lay.addWidget(sp, 0, 1)
            self._seq_spins["delay"] = sp

        self._on_sync_toggled(self._chk_sync.isChecked())

    def _on_sync_toggled(self, checked: bool):
        self._sp_sync_t.setEnabled(checked); self._lbl_sync_t.setEnabled(checked)
        for key, w in self._seq_spins.items():
            if key.endswith("_spd"): w.setEnabled(not checked)

    def _add_seq_step(self):
        mode = self._cb_mode_seq.currentIndex()
        sp   = self._seq_spins
        sync_on   = self._chk_sync.isChecked()
        sync_time = self._sp_sync_t.value()

        if mode == 0:
            tx, ty, z_ = sp["tot_x"].value(), sp["tot_y"].value(), sp["z"].value()
            xs, ys, zs = sp["x_spd"].value(), sp["y_spd"].value(), sp["z_spd"].value()
            raw = [("XA", tx / 2, xs), ("XB", tx / 2, xs),
                   ("YA", ty / 2, ys), ("YB", ty / 2, ys), ("Z", z_, zs)]
            if sync_on:
                active = [(ax, d) for ax, d, _ in raw if abs(d) >= 1e-6]
                cmds = [(ax, d, max(0.01, abs(d) / sync_time)) for ax, d in active]
            else:
                cmds = [(ax, d, s) for ax, d, s in raw if abs(d) >= 1e-6]
            desc = f"Sym X:{tx} Y:{ty} Z:{z_}" + (f" T:{sync_time}s" if sync_on else f" {xs:.1f}/{ys:.1f}/{zs:.1f}mm/s")
            step = {"type": "MOVE", "hint": "sym", "cmds": cmds, "desc": desc,
                    "x_spd": xs, "y_spd": ys, "z_spd": zs, "sync": sync_on, "sync_time": sync_time}

        elif mode == 1:
            cmds = []
            for ax in AXES:
                d_ = sp[ax].value(); s_ = sp[f"{ax}_spd"].value()
                if abs(d_) >= 1e-6:
                    cmds.append((ax, d_, max(0.01, abs(d_) / sync_time) if sync_on else s_))
            desc = "  ".join(f"{ax}:{d:.1f}@{s:.1f}" for ax, d, s in cmds)
            if sync_on: desc += f" T:{sync_time}s"
            step = {"type": "MOVE", "hint": "ind", "cmds": cmds, "desc": desc,
                    "sync": sync_on, "sync_time": sync_time}

        else:
            delay = sp["delay"].value()
            step  = {"type": "WAIT", "val": delay, "desc": f"대기 {delay}ms"}

        if self._editing_idx is not None:
            self._seq_data[self._editing_idx] = step
            self._editing_idx = None
        else:
            self._seq_data.append(step)
        self._rebuild_tree()

    def _cancel_edit(self):
        self._editing_idx = None

    def _rebuild_tree(self):
        self._seq_tree.clear()
        hint_map = {"sym": "대칭", "ind": "개별"}
        for i, step in enumerate(self._seq_data):
            if step["type"] == "MOVE":
                lbl = hint_map.get(step.get("hint", ""), "이동")
                if step.get("sync"): lbl += "+동기"
                spd = " / ".join(f"{s:.1f}" for _, _, s in step.get("cmds", []))
            else:
                lbl = "대기"; spd = "-"
            self._seq_tree.addTopLevelItem(
                QTreeWidgetItem([str(i + 1), lbl, step.get("desc", ""), spd]))

    def _load_for_edit(self, item):
        idx = self._seq_tree.indexOfTopLevelItem(item)
        if idx < 0: return
        self._editing_idx = idx
        step = self._seq_data[idx]
        if step["type"] == "WAIT":
            self._cb_mode_seq.setCurrentIndex(2)
            QTimer.singleShot(50, lambda: self._seq_spins["delay"].setValue(step["val"]))
            return
        hint = step.get("hint", "ind")
        cmds_dict = {ax: (d, s) for ax, d, s in step.get("cmds", [])}
        if hint == "sym":
            self._cb_mode_seq.setCurrentIndex(0)
            self._chk_sync.setChecked(step.get("sync", False))
            if step.get("sync"): self._sp_sync_t.setValue(step.get("sync_time", 5.0))
            def fill():
                self._seq_spins["tot_x"].setValue(cmds_dict.get("XA", (0, 5))[0] * 2)
                self._seq_spins["tot_y"].setValue(cmds_dict.get("YA", (0, 5))[0] * 2)
                self._seq_spins["z"].setValue(cmds_dict.get("Z", (0, 5))[0])
                self._seq_spins["x_spd"].setValue(step.get("x_spd", 5.0))
                self._seq_spins["y_spd"].setValue(step.get("y_spd", 5.0))
                self._seq_spins["z_spd"].setValue(step.get("z_spd", 5.0))
            QTimer.singleShot(50, fill)
        else:
            self._cb_mode_seq.setCurrentIndex(1)
            self._chk_sync.setChecked(step.get("sync", False))
            if step.get("sync"): self._sp_sync_t.setValue(step.get("sync_time", 5.0))
            def fill():
                for ax in AXES:
                    d, s = cmds_dict.get(ax, (0.0, 5.0))
                    self._seq_spins[ax].setValue(d)
                    self._seq_spins[f"{ax}_spd"].setValue(s)
            QTimer.singleShot(50, fill)

    def _seq_up(self):
        items = self._seq_tree.selectedItems()
        if not items: return
        idx = self._seq_tree.indexOfTopLevelItem(items[0])
        if idx > 0:
            self._seq_data[idx - 1], self._seq_data[idx] = self._seq_data[idx], self._seq_data[idx - 1]
            self._rebuild_tree()

    def _seq_down(self):
        items = self._seq_tree.selectedItems()
        if not items: return
        idx = self._seq_tree.indexOfTopLevelItem(items[0])
        if idx < len(self._seq_data) - 1:
            self._seq_data[idx], self._seq_data[idx + 1] = self._seq_data[idx + 1], self._seq_data[idx]
            self._rebuild_tree()

    def _seq_delete(self):
        idxs = sorted([self._seq_tree.indexOfTopLevelItem(i)
                       for i in self._seq_tree.selectedItems()], reverse=True)
        for i in idxs: del self._seq_data[i]
        self._rebuild_tree()

    def _seq_clear(self):
        self._seq_data.clear(); self._rebuild_tree()

    def _seq_copy(self):
        self._clipboard = copy.deepcopy([
            self._seq_data[self._seq_tree.indexOfTopLevelItem(i)]
            for i in self._seq_tree.selectedItems()])

    def _seq_paste(self):
        self._seq_data.extend(copy.deepcopy(self._clipboard)); self._rebuild_tree()

    # ── 시퀀스 실행 (sync_decoupler_monitor.py에서 이식) ───────────────────────

    def _run_sequence(self):
        if not self._seq_data:
            self._log("시퀀스가 비어 있습니다"); return
        if not self._arduino.isRunning():
            self._log("Arduino 미연결"); return
        if not self._motor_enabled:
            QMessageBox.warning(self, "모터 비활성화", "ENABLE 버튼을 먼저 누르세요.")
            return

        self._is_running_seq = True
        self._btn_run_seq.setEnabled(False)
        self._done_event.clear()

        def execute():
            run_count = 0
            try:
                repeat = self._spin_repeat.value()
                while self._is_running_seq:
                    run_count += 1
                    if repeat > 0:
                        self._log(f"[시퀀스] {run_count}/{repeat} 회차 시작")
                    else:
                        self._log(f"[시퀀스] {run_count}회차 시작 (무한)")

                    for i, step in enumerate(self._seq_data):
                        if not self._is_running_seq: break
                        self._log(f"  [스텝 {i + 1}] {step['desc']}")

                        if step["type"] == "WAIT":
                            t_end = time.time() + step["val"] / 1000.0
                            while self._is_running_seq and time.time() < t_end:
                                time.sleep(0.02)

                        elif step["type"] == "MOVE":
                            cmds = [(ax, d, s) for ax, d, s in step.get("cmds", []) if abs(d) >= 1e-6]
                            if cmds:
                                abs_parts = []
                                for ax, dist, spd in cmds:
                                    cur = self._last_pos.get(ax, 0.0)
                                    tgt = int((cur + dist) * self._arduino.steps_per_mm)
                                    spd_s = max(1, int(spd * self._arduino.steps_per_mm))
                                    abs_parts += [ax, str(tgt), str(spd_s)]
                                expected_t = max(abs(d) / max(s, 0.01) for _, d, s in cmds)
                                move_timeout = expected_t * 1.5 + 2.0
                                self._done_event.clear()
                                self._arduino.send("ABS:" + ":".join(abs_parts))
                                t_start = time.time()
                                while self._is_running_seq:
                                    if time.time() - t_start > move_timeout:
                                        self._log("  [경고] DONE 미수신 — 타임아웃 후 진행")
                                        break
                                    if self._done_event.wait(timeout=0.05):
                                        self._done_event.clear(); break

                    if repeat > 0 and run_count >= repeat:
                        break

            except Exception as e:
                self._log(f"[시퀀스] 오류: {e}")
            finally:
                self._is_running_seq = False
                self._seq_finished.emit()
                self._log(f"[시퀀스] 완료 (총 {run_count}회)")

        threading.Thread(target=execute, daemon=True).start()

    def _stop_sequence(self):
        self._is_running_seq = False; self._done_event.set()
        self._log("[시퀀스] 정지 요청")

    # ── 녹화 ─────────────────────────────────────────────────────────────────

    def _toggle_record(self, checked: bool):
        if checked:
            self._rec_rows.clear()
            self._btn_rec.setText("■ STOP")
            self._recording = True
            self._update_status("녹화 시작")
        else:
            self._recording = False
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
               "YA_mm", "YB_mm", "Z_mm", "Fz_act_N", "strain_act_pct", "value_act"]
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
        self._ui_timer.stop()
        self._is_running_seq = False; self._done_event.set()
        self._stm32.disconnect(); self._stm32.quit(); self._stm32.wait(1000)
        self._arduino.disconnect(); self._arduino.quit(); self._arduino.wait(1000)
        self._rft.disconnect(); self._rft.quit(); self._rft.wait(1000)
        event.accept()


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
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
