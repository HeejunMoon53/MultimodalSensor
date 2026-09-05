"""
mms_collector.py
TDM 센서(dL,dR,dV) + RFT F/T + Arduino 5축 동기화 데이터 수집 UI

실행:
    python MMS_Notebook_test/mms_collector.py

TDM  (STM32 TDMFirmware): dL_pct, dR_pct, dV
RFT  (STM32 FTSensorCAN): Fx, Fy, Fz, Tx, Ty, Tz  (N / N·m)
Arduino: POS? / JOG / ZERO / EN  (5축: XA, XB, YA, YB, Z)

CSV 열: t_s | dL_pct | dR_pct | dV | xa_mm | xb_mm | ya_mm | yb_mm | z_mm
        | eps_act_pct | d_act_mm | Fx_N | Fy_N | Fz_N | Tx_Nm | Ty_Nm | Tz_Nm
"""

import sys, copy, time, csv, threading
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import serial
import serial.tools.list_ports

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QFileDialog, QSplitter, QStatusBar,
    QFrame, QDoubleSpinBox, QSpinBox, QGroupBox, QTabWidget, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QCheckBox, QMessageBox,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QPalette

import pyqtgraph as pg

# ── 색상 ──────────────────────────────────────────────────────────────────────
COLOR_L  = "#FF8C00"   # dL — 주황
COLOR_R  = "#2CA02C"   # dR — 초록
COLOR_FZ = "#1F77B4"   # Fz — 파랑
COLOR_V  = "#9B59B6"   # dV — 보라

C = {
    "bg":     "#1e1e2e", "bg2":   "#181825", "bg3":   "#313244",
    "text":   "#cdd6f4", "text2": "#a6adc8",
    "blue":   "#89b4fa", "green": "#a6e3a1", "yellow": "#f9e2af",
    "red":    "#f38ba8", "teal":  "#94e2d5",
    "border": "#45475a", "peach": "#fab387", "mauve": "#cba6f7",
}

# ── 상수 ──────────────────────────────────────────────────────────────────────
AXES          = ["XA", "XB", "YA", "YB", "Z"]
STEPS_PER_REV = 200
DEF_MICROSTEP = 8
DEF_PITCH_MM  = 5.0
MAX_POINTS    = 3000
BAUD          = 115200
CAL_SAMPLES   = 100
ARDUINO_POLL  = 0.1
SENSOR_L0     = 120.0   # 센서 초기 길이 (mm) — eps_act 계산용
PROX_OFFSET   = 52.0    # Z=0일 때 물체까지 거리 (mm)


def _hline():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color:{C['border']};"); return f

def _vline():
    f = QFrame(); f.setFrameShape(QFrame.VLine)
    f.setStyleSheet(f"color:{C['border']};"); return f


# ══════════════════════════════════════════════════════════════════════════════
# TDM 리더  —  dL_pct, dR_pct, dV
# ══════════════════════════════════════════════════════════════════════════════

class TDMReader(QThread):
    data_received = pyqtSignal(float, list)
    error_msg     = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser = None; self._running = False

    def connect(self, port):
        self._ser = serial.Serial(port, BAUD, timeout=0.1)
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
            return vals[:3] if len(vals) >= 3 else None
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# RFT 리더  —  Fx, Fy, Fz, Tx, Ty, Tz
# ══════════════════════════════════════════════════════════════════════════════

class RFTReader(QThread):
    data_received = pyqtSignal(float, list)
    error_msg     = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser = None; self._running = False

    def connect(self, port):
        self._ser = serial.Serial(port, BAUD, timeout=0.1)
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
# Arduino 컨트롤러  —  5축 스테이지
# ══════════════════════════════════════════════════════════════════════════════

class ArduinoController(QThread):
    position_updated = pyqtSignal(float, dict)
    done_received    = pyqtSignal()
    alarm_received   = pyqtSignal(str)
    error_msg        = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser = None; self._running = False
        self._lock = threading.Lock()
        self._cmd_queue = deque()
        self.steps_per_mm = (STEPS_PER_REV * DEF_MICROSTEP) / DEF_PITCH_MM
        self._cur_pos = {ax: 0.0 for ax in AXES}   # move_abs 용 현재 위치 (mm)

    def connect(self, port):
        self._ser = serial.Serial(port, BAUD, timeout=0.2)
        time.sleep(2.0); self._running = True

    def disconnect(self):
        self._running = False
        if self._ser and self._ser.is_open: self._ser.close()

    def send(self, cmd: str):
        with self._lock: self._cmd_queue.append(cmd)

    def jog(self, axis: str, dist_mm: float, speed_mms: float = 5.0):
        steps = int(dist_mm * self.steps_per_mm)   # 부호 그대로 유지, 속도 미포함
        self.send(f"JOG:{axis}:{steps}")

    def move_abs(self, axis_delta_spd: list):
        """ABS:{ax}:{target_steps}:{spd}:... 형식 절대 이동 (시퀀스용)."""
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
            pos = {ax: round(vals[i] / self.steps_per_mm, 3)
                   for i, ax in enumerate(AXES) if i < len(vals)}
            self._cur_pos.update(pos)
            return pos
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# 값 표시 카드
# ══════════════════════════════════════════════════════════════════════════════

class ValueCard(QWidget):
    def __init__(self, label, unit, color, fmt="{:.4f}"):
        super().__init__()
        self._fmt = fmt
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 5, 10, 5); vbox.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color:{C['text2']}; font-size:10px; font-weight:600; letter-spacing:1px;")
        vbox.addWidget(lbl)
        row = QHBoxLayout()
        self._val = QLabel("—")
        self._val.setStyleSheet(
            f"color:{color}; font-size:24px; font-weight:700; font-family:Consolas;")
        row.addWidget(self._val); row.addStretch()
        u = QLabel(unit)
        u.setStyleSheet(f"color:{C['text2']}; font-size:12px; margin-top:6px;")
        row.addWidget(u); vbox.addLayout(row)
        self.setStyleSheet(
            f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;")

    def update(self, val):
        self._val.setText("—" if val is None else self._fmt.format(val))


# ══════════════════════════════════════════════════════════════════════════════
# 메인 윈도우
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    _seq_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MMS Collector — TDM + RFT + Arduino 통합 데이터 수집")
        self.resize(1500, 920)

        self._tdm     = TDMReader()
        self._rft     = RFTReader()
        self._arduino = ArduinoController()

        # 데이터 버퍼
        self._t0   = None
        self._ts   = deque(maxlen=MAX_POINTS)
        self._bufs = {k: deque(maxlen=MAX_POINTS)
                      for k in ["dL", "dR", "dV", "Fz"]}

        # RFT 최신값 (TDM 샘플 타임스탬프에 붙임)
        self._last_rft    = [0.0] * 6   # [Fx, Fy, Fz, Tx, Ty, Tz]
        self._last_rft_ts = 0.0

        # 캘리브레이션 — TDM 영점 오프셋
        self._cal_buf_dL = deque(maxlen=CAL_SAMPLES)
        self._cal_buf_dR = deque(maxlen=CAL_SAMPLES)
        self._dL0 = 0.0
        self._dR0 = 0.0
        # FT 타어 오프셋 (Fz만)
        self._cal_buf_Fz = deque(maxlen=CAL_SAMPLES)
        self._Fz0 = 0.0

        # Arduino 상태
        self._last_pos      = {ax: 0.0 for ax in AXES}
        self._motor_enabled = False
        self._jog_speed     = 5.0
        self._prox_offset   = PROX_OFFSET

        # 시퀀스 상태
        self._is_running_seq = False
        self._done_event     = threading.Event()
        self._seq_data       = []
        self._clipboard      = []
        self._editing_idx    = None

        # 녹화
        self._recording = False
        self._rec_rows  = []
        self._save_dir  = str(Path.home())

        # Hz 측정
        self._freq_ts = deque(maxlen=100)

        self._build_ui()
        self._connect_signals()
        self._seq_finished.connect(lambda: self._btn_run_seq.setEnabled(True))

        self._ui_timer = QTimer()
        self._ui_timer.timeout.connect(self._refresh)
        self._ui_timer.start(40)

    # ── UI 구성 ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        pg.setConfigOption("background", C["bg"])
        pg.setConfigOption("foreground", C["text"])

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(4); root.setContentsMargins(8, 8, 8, 6)

        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_pos_bar())
        root.addWidget(_hline())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([360, 1140])
        root.addWidget(splitter, stretch=1)

        root.addWidget(_hline())
        root.addWidget(self._build_record_bar())

        sb = QStatusBar()
        sb.setStyleSheet(f"color:{C['text2']}; font-size:12px;")
        self.setStatusBar(sb); self._sb = sb
        self._update_status("미연결")

    # ── 상단 바 ───────────────────────────────────────────────────────────────

    def _build_top_bar(self):
        bar = QWidget(); lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0); lay.setSpacing(6)

        def _port_group(label, cb_attr, btn_attr, ind_attr, toggle_fn):
            lay.addWidget(self._lbl(label))
            cb = QComboBox(); cb.setMinimumWidth(110)
            setattr(self, cb_attr, cb); lay.addWidget(cb)
            btn = QPushButton("연결"); btn.setFixedSize(60, 30)
            btn.clicked.connect(toggle_fn)
            setattr(self, btn_attr, btn); lay.addWidget(btn)
            ind = QLabel("●")
            ind.setStyleSheet(f"color:{C['red']}; font-size:15px;")
            setattr(self, ind_attr, ind); lay.addWidget(ind)

        _port_group("TDM",     "_cb_tdm",     "_btn_tdm",     "_ind_tdm",     self._toggle_tdm)
        lay.addWidget(_vline())
        _port_group("RFT F/T", "_cb_rft",     "_btn_rft",     "_ind_rft",     self._toggle_rft)
        lay.addWidget(_vline())
        _port_group("Arduino", "_cb_arduino", "_btn_arduino", "_ind_arduino", self._toggle_arduino)

        btn_ref = QPushButton("⟳"); btn_ref.setFixedSize(30, 30)
        btn_ref.setToolTip("포트 새로고침"); btn_ref.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_ref)

        lay.addWidget(_vline())

        self._btn_motor = QPushButton("ENABLE"); self._btn_motor.setFixedHeight(30)
        self._btn_motor.setStyleSheet(
            f"background:{C['green']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
        self._btn_motor.clicked.connect(self._toggle_motor)
        lay.addWidget(self._btn_motor)

        btn_zero = QPushButton("ZERO"); btn_zero.setFixedHeight(30)
        btn_zero.clicked.connect(self._set_zero)
        lay.addWidget(btn_zero)

        lay.addWidget(_vline())

        # TDM 영점
        self._btn_cal_tdm = QPushButton("영점 L/R"); self._btn_cal_tdm.setFixedHeight(30)
        self._btn_cal_tdm.setStyleSheet(
            f"background:{C['bg3']}; color:{C['yellow']}; "
            f"border:1px solid {C['yellow']}; border-radius:5px; font-weight:600;")
        self._btn_cal_tdm.clicked.connect(self._calibrate_tdm)
        lay.addWidget(self._btn_cal_tdm)

        # FT 타어
        self._btn_cal_ft = QPushButton("Tare Fz"); self._btn_cal_ft.setFixedHeight(30)
        self._btn_cal_ft.setStyleSheet(
            f"background:{C['bg3']}; color:{C['blue']}; "
            f"border:1px solid {C['blue']}; border-radius:5px; font-weight:600;")
        self._btn_cal_ft.clicked.connect(self._tare_fz)
        lay.addWidget(self._btn_cal_ft)

        self._lbl_baseline = QLabel("baseline: 미설정")
        self._lbl_baseline.setStyleSheet(
            f"color:{C['text2']}; font-size:11px; font-family:Consolas;")
        lay.addWidget(self._lbl_baseline)

        lay.addWidget(_vline())

        btn_clear = QPushButton("데이터 지우기"); btn_clear.setFixedHeight(30)
        btn_clear.setStyleSheet(
            f"background:{C['bg3']}; color:{C['red']}; "
            f"border:1px solid {C['red']}; border-radius:4px;")
        btn_clear.clicked.connect(self._clear_data)
        lay.addWidget(btn_clear)

        lay.addStretch()

        self._lbl_hz = QLabel("— Hz")
        self._lbl_hz.setStyleSheet(
            f"color:{C['teal']}; font-size:13px; font-weight:700; font-family:Consolas;")
        lay.addWidget(self._lbl_hz)

        self._refresh_ports()
        return bar

    # ── 위치 바 ───────────────────────────────────────────────────────────────

    def _build_pos_bar(self):
        bar = QGroupBox("현재 위치 (mm)")
        bar.setMaximumHeight(60)
        grid = QGridLayout(bar)
        grid.setContentsMargins(8, 2, 8, 2); grid.setSpacing(4)
        self._pos_labels = {}
        for i, ax in enumerate(AXES):
            grid.addWidget(QLabel(ax, alignment=Qt.AlignCenter), 0, i)
            lbl = QLabel("0.000", alignment=Qt.AlignCenter)
            lbl.setStyleSheet(
                f"font-size:18px; font-weight:700; color:{C['blue']}; font-family:Consolas;")
            grid.addWidget(lbl, 1, i)
            self._pos_labels[ax] = lbl

        # Ground truth 표시
        grid.addWidget(_vline(), 0, len(AXES), 2, 1)
        self._lbl_eps_act = QLabel("eps_act: —%", alignment=Qt.AlignCenter)
        self._lbl_eps_act.setStyleSheet(
            f"color:{C['mauve']}; font-size:12px; font-family:Consolas; font-weight:600;")
        grid.addWidget(self._lbl_eps_act, 0, len(AXES)+1, 2, 1)
        self._lbl_d_act = QLabel("d_act: —mm", alignment=Qt.AlignCenter)
        self._lbl_d_act.setStyleSheet(
            f"color:{C['teal']}; font-size:12px; font-family:Consolas; font-weight:600;")
        grid.addWidget(self._lbl_d_act, 0, len(AXES)+2, 2, 1)
        return bar

    # ── 좌측 패널 ─────────────────────────────────────────────────────────────

    def _build_left_panel(self):
        tabs = QTabWidget()
        tabs.addTab(self._build_sensor_tab(),   "센서값")
        tabs.addTab(self._build_jog_tab(),      "수동 조그")
        tabs.addTab(self._build_sequence_tab(), "시퀀스")
        return tabs

    def _build_sensor_tab(self):
        w = QWidget(); vbox = QVBoxLayout(w)
        vbox.setSpacing(5); vbox.setContentsMargins(6, 6, 6, 6)

        vbox.addWidget(self._section("TDM 센서"))
        self._card_dL = ValueCard("dL / L0", "%",  COLOR_L, "{:+.4f}")
        self._card_dR = ValueCard("dR / R0", "%",  COLOR_R, "{:+.4f}")
        self._card_dV = ValueCard("dV",       "",   COLOR_V, "{:+.4f}")
        vbox.addWidget(self._card_dL)
        vbox.addWidget(self._card_dR)
        vbox.addWidget(self._card_dV)

        vbox.addWidget(_hline())
        vbox.addWidget(self._section("RFT F/T 센서"))
        self._card_Fx = ValueCard("Fx", "N",  C["text2"], "{:+.3f}")
        self._card_Fy = ValueCard("Fy", "N",  C["text2"], "{:+.3f}")
        self._card_Fz = ValueCard("Fz", "N",  COLOR_FZ,   "{:+.3f}")
        self._card_Tx = ValueCard("Tx", "Nm", C["text2"], "{:+.4f}")
        self._card_Ty = ValueCard("Ty", "Nm", C["text2"], "{:+.4f}")
        self._card_Tz = ValueCard("Tz", "Nm", C["text2"], "{:+.4f}")
        for c in [self._card_Fx, self._card_Fy, self._card_Fz,
                  self._card_Tx, self._card_Ty, self._card_Tz]:
            vbox.addWidget(c)

        vbox.addWidget(_hline())
        vbox.addWidget(self._section("근접도 기준거리"))
        row_prox = QHBoxLayout()
        row_prox.addWidget(self._lbl("Z=0 기준 (mm)"))
        self._spin_prox = QDoubleSpinBox()
        self._spin_prox.setRange(0, 500); self._spin_prox.setSingleStep(1)
        self._spin_prox.setDecimals(1); self._spin_prox.setValue(PROX_OFFSET)
        self._spin_prox.setFixedWidth(90)
        self._spin_prox.setStyleSheet(
            f"background:{C['bg3']}; color:{C['peach']}; "
            f"border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;")
        self._spin_prox.valueChanged.connect(lambda v: setattr(self, "_prox_offset", v))
        row_prox.addWidget(self._spin_prox); row_prox.addStretch()
        vbox.addLayout(row_prox)

        vbox.addStretch()
        return w

    def _build_jog_tab(self):
        w = QWidget(); vbox = QVBoxLayout(w)
        vbox.setSpacing(8); vbox.setContentsMargins(8, 8, 8, 8)

        # 조그 속도
        row_spd = QHBoxLayout()
        row_spd.addWidget(self._lbl("속도 (mm/s)"))
        self._spin_jog_spd = QDoubleSpinBox()
        self._spin_jog_spd.setRange(0.1, 50); self._spin_jog_spd.setSingleStep(0.5)
        self._spin_jog_spd.setValue(5.0); self._spin_jog_spd.setFixedWidth(80)
        self._spin_jog_spd.setStyleSheet(
            f"background:{C['bg3']}; color:{C['peach']}; "
            f"border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;")
        self._spin_jog_spd.valueChanged.connect(lambda v: setattr(self, "_jog_speed", v))
        row_spd.addWidget(self._spin_jog_spd); row_spd.addStretch()
        vbox.addLayout(row_spd)

        # 전체 축 조그 버튼
        jog_grp = QGroupBox("축별 조그")
        jog_grid = QGridLayout(jog_grp); jog_grid.setSpacing(3)

        jog_defs = [("<<<\n10mm", -10.0), ("<<\n5mm", -5.0), ("<\n1mm", -1.0),
                    (">\n1mm",     1.0),  (">>\n5mm",  5.0), (">>>\n10mm", 10.0)]

        for col, (h, _) in enumerate(jog_defs):
            lbl = QLabel(h, alignment=Qt.AlignCenter)
            lbl.setStyleSheet("font-size:9px;")
            jog_grid.addWidget(lbl, 0, col+1)

        for row, ax in enumerate(AXES):
            jog_grid.addWidget(QLabel(ax), row+1, 0)
            for col, (_, dist) in enumerate(jog_defs):
                btn = QPushButton("←→"[col >= 3])
                btn.setFixedSize(46, 26)
                d = dist
                btn.clicked.connect(lambda _, a=ax, d=d: self._do_jog(a, d))
                jog_grid.addWidget(btn, row+1, col+1)

        vbox.addWidget(jog_grp)

        # 절대 이동 (Z 전용)
        abs_grp = QGroupBox("Z 절대 이동")
        abs_lay = QHBoxLayout(abs_grp)
        abs_lay.addWidget(self._lbl("목표 Z (mm)"))
        self._spin_z_abs = QDoubleSpinBox()
        self._spin_z_abs.setRange(-500, 500); self._spin_z_abs.setSingleStep(0.5)
        self._spin_z_abs.setValue(0.0); self._spin_z_abs.setDecimals(2)
        self._spin_z_abs.setFixedWidth(90)
        self._spin_z_abs.setStyleSheet(
            f"background:{C['bg3']}; color:{C['peach']}; "
            f"border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;")
        abs_lay.addWidget(self._spin_z_abs)
        btn_go = QPushButton("이동"); btn_go.setFixedHeight(30)
        btn_go.clicked.connect(self._go_z_abs)
        abs_lay.addWidget(btn_go)
        vbox.addWidget(abs_grp)

        # 로그
        self._jog_log = QTextEdit()
        self._jog_log.setReadOnly(True); self._jog_log.setMaximumHeight(120)
        self._jog_log.setStyleSheet(
            f"background:{C['bg2']}; color:{C['text2']}; font-size:11px; font-family:Consolas;")
        vbox.addWidget(self._jog_log)
        vbox.addStretch()
        return w

    def _build_sequence_tab(self):
        w = QWidget(); vbox = QVBoxLayout(w)

        # 스텝 입력
        inp_grp = QGroupBox("스텝 입력")
        inp_lay = QGridLayout(inp_grp)

        self._cb_mode = QComboBox()
        self._cb_mode.addItems(["대칭 이동 (Symmetric)", "개별 이동 (Individual)", "대기 (Delay)"])
        self._cb_mode.currentIndexChanged.connect(self._update_seq_inputs)
        inp_lay.addWidget(QLabel("유형:"), 0, 0)
        inp_lay.addWidget(self._cb_mode, 0, 1, 1, 3)

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

        btn_add    = QPushButton("스텝 추가");  btn_add.clicked.connect(self._add_seq_step)
        btn_cancel = QPushButton("편집 취소"); btn_cancel.clicked.connect(self._cancel_edit)
        inp_lay.addWidget(btn_add,    3, 0, 1, 2)
        inp_lay.addWidget(btn_cancel, 3, 2, 1, 2)
        vbox.addWidget(inp_grp)

        # 트리
        self._seq_tree = QTreeWidget()
        self._seq_tree.setHeaderLabels(["#", "유형", "내용", "속도"])
        self._seq_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self._seq_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._seq_tree.itemDoubleClicked.connect(self._load_for_edit)
        vbox.addWidget(self._seq_tree, stretch=1)

        # 관리 버튼
        btn_row = QHBoxLayout()
        for label, slot in [("▲", self._seq_up), ("▼", self._seq_down),
                             ("삭제", self._seq_delete), ("전체삭제", self._seq_clear),
                             ("복사", self._seq_copy), ("붙여넣기", self._seq_paste)]:
            b = QPushButton(label); b.setFixedHeight(28); b.clicked.connect(slot)
            btn_row.addWidget(b)
        vbox.addLayout(btn_row)

        # 실행 행
        run_row = QHBoxLayout()
        self._btn_run_seq = QPushButton("▶ 시퀀스 실행")
        self._btn_run_seq.setFixedHeight(32)
        self._btn_run_seq.setStyleSheet(
            f"background:{C['blue']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
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
        self._spin_repeat.setToolTip("반복 횟수 (0 = 무한)")
        self._spin_repeat.setStyleSheet(
            f"background:{C['bg3']}; color:{C['peach']}; "
            f"border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;")
        run_row.addWidget(self._spin_repeat)
        run_row.addWidget(self._small_lbl("회  (0=∞)"))
        vbox.addLayout(run_row)

        # 시퀀스 로그
        self._seq_log = QTextEdit()
        self._seq_log.setReadOnly(True); self._seq_log.setMaximumHeight(80)
        self._seq_log.setStyleSheet(
            f"background:{C['bg2']}; color:{C['text2']}; font-size:11px; font-family:Consolas;")
        vbox.addWidget(self._seq_log)

        self._update_seq_inputs()
        return w

    # ── 우측 패널: 4개 시계열 그래프 ─────────────────────────────────────────

    def _build_right_panel(self):
        pw = pg.GraphicsLayoutWidget()
        self._curves = {}
        first_plot = None

        specs = [
            ("dL / L0 (%)",  COLOR_L,  "dL"),
            ("dR / R0 (%)",  COLOR_R,  "dR"),
            ("Fz (N)",        COLOR_FZ, "Fz"),
            ("dV",            COLOR_V,  "dV"),
        ]
        for i, (title, color, key) in enumerate(specs):
            p = pw.addPlot(row=i, col=0, title=title)
            p.getAxis("left").setWidth(58)
            p.showGrid(x=False, y=True, alpha=0.15)
            p.titleLabel.setAttr("color", C["text2"])
            p.titleLabel.setAttr("size", "11pt")
            self._curves[key] = p.plot(pen=pg.mkPen(color, width=2.0))
            if i == 0: first_plot = p
            else: p.setXLink(first_plot)
            p.getAxis("bottom").setStyle(showValues=(i == len(specs) - 1))
            if i == len(specs) - 1:
                p.setLabel("bottom", "시간 (s)")

        return pw

    # ── 녹화 바 ───────────────────────────────────────────────────────────────

    def _build_record_bar(self):
        bar = QWidget(); lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0)

        self._btn_rec = QPushButton("● RECORD")
        self._btn_rec.setFixedSize(130, 34); self._btn_rec.setCheckable(True)
        self._btn_rec.setStyleSheet(
            "QPushButton{background:#f38ba8; color:#1e1e2e; font-weight:700;"
            " font-size:13px; border-radius:5px;}"
            "QPushButton:checked{background:#a6e3a1; color:#1e1e2e;}")
        self._btn_rec.clicked.connect(self._toggle_record)
        lay.addWidget(self._btn_rec)

        lay.addSpacing(12)
        lay.addWidget(self._lbl("저장 폴더:"))
        self._lbl_dir = QLabel(self._save_dir)
        self._lbl_dir.setStyleSheet(f"color:{C['blue']};")
        lay.addWidget(self._lbl_dir, stretch=1)

        btn_browse = QPushButton("폴더 선택"); btn_browse.setFixedHeight(30)
        btn_browse.clicked.connect(self._browse_dir)
        lay.addWidget(btn_browse)

        lay.addSpacing(8)
        self._lbl_rec_count = QLabel("0행")
        self._lbl_rec_count.setStyleSheet(f"color:{C['text2']}; font-family:Consolas;")
        lay.addWidget(self._lbl_rec_count)
        return bar

    # ── 헬퍼 ──────────────────────────────────────────────────────────────────

    def _lbl(self, t):
        l = QLabel(t); l.setStyleSheet(f"color:{C['text2']}; font-weight:600;"); return l

    def _small_lbl(self, t):
        l = QLabel(t); l.setStyleSheet(f"color:{C['text2']}; font-size:11px;"); return l

    def _section(self, t):
        l = QLabel(t)
        l.setStyleSheet(
            f"color:{C['text2']}; font-size:10px; font-weight:700; "
            f"letter-spacing:2px; margin-top:2px;")
        return l

    # ── 시그널 연결 ───────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._tdm.data_received.connect(self._on_tdm_data)
        self._tdm.error_msg.connect(lambda m: self._update_status(f"TDM: {m}"))
        self._rft.data_received.connect(self._on_rft_data)
        self._rft.error_msg.connect(lambda m: self._update_status(f"RFT: {m}"))
        self._arduino.position_updated.connect(self._on_arduino_pos)
        self._arduino.done_received.connect(self._on_done)
        self._arduino.alarm_received.connect(lambda m: self._log(f"[ALARM] {m}"))
        self._arduino.error_msg.connect(lambda m: self._update_status(f"Arduino: {m}"))

    # ── 데이터 핸들러 ─────────────────────────────────────────────────────────

    def _on_tdm_data(self, ts, vals):
        # vals: [dL_pct, dR_pct, dV]
        dL_raw = vals[0]; dR_raw = vals[1]; dV = vals[2]
        self._cal_buf_dL.append(dL_raw); self._cal_buf_dR.append(dR_raw)

        dL = dL_raw - self._dL0
        dR = dR_raw - self._dR0
        Fz = self._last_rft[2] - self._Fz0

        if self._t0 is None: self._t0 = ts
        t = ts - self._t0
        self._ts.append(t)
        self._bufs["dL"].append(dL)
        self._bufs["dR"].append(dR)
        self._bufs["dV"].append(dV)
        self._bufs["Fz"].append(Fz)
        self._freq_ts.append(ts)

        if self._recording:
            pos  = self._last_pos
            rft  = self._last_rft
            xa   = pos.get("XA", 0.0); xb = pos.get("XB", 0.0)
            ya   = pos.get("YA", 0.0); yb = pos.get("YB", 0.0)
            z    = pos.get("Z",  0.0)
            eps_act = abs(xa) * 2.0 / SENSOR_L0 * 100.0
            d_act   = max(0.0, self._prox_offset + z)
            self._rec_rows.append([
                round(t,      5),
                round(dL,     6), round(dR,     6), round(dV, 6),
                round(xa,     4), round(xb,     4), round(ya, 4), round(yb, 4), round(z, 4),
                round(eps_act, 4), round(d_act,  4),
                round(rft[0], 4), round(rft[1], 4), round(Fz, 4),
                round(rft[3], 5), round(rft[4], 5), round(rft[5], 5),
            ])
            self._lbl_rec_count.setText(f"{len(self._rec_rows)}행")

    def _on_rft_data(self, ts, vals):
        self._last_rft    = vals
        self._last_rft_ts = ts
        self._cal_buf_Fz.append(vals[2])

    def _on_arduino_pos(self, ts, pos):
        self._last_pos.update(pos)

    def _on_done(self):
        self._done_event.set()

    # ── 화면 갱신 ─────────────────────────────────────────────────────────────

    def _refresh(self):
        n = len(self._ts)
        if n >= 2:
            ts_arr = np.array(self._ts)
            for key, curve in self._curves.items():
                buf = self._bufs.get(key)
                if buf and len(buf) == n:
                    curve.setData(ts_arr, np.array(list(buf)))

        def last(k): return self._bufs[k][-1] if self._bufs[k] else None

        self._card_dL.update(last("dL"))
        self._card_dR.update(last("dR"))
        self._card_dV.update(last("dV"))
        self._card_Fz.update(last("Fz"))

        rft_ok = self._last_rft_ts > 0
        rft    = self._last_rft
        self._card_Fx.update(rft[0] if rft_ok else None)
        self._card_Fy.update(rft[1] if rft_ok else None)
        self._card_Tx.update(rft[3] if rft_ok else None)
        self._card_Ty.update(rft[4] if rft_ok else None)
        self._card_Tz.update(rft[5] if rft_ok else None)

        # 위치 표시
        for ax, lbl in self._pos_labels.items():
            lbl.setText(f"{self._last_pos.get(ax, 0.0):.3f}")

        # Ground truth
        xa = self._last_pos.get("XA", 0.0)
        z  = self._last_pos.get("Z",  0.0)
        self._lbl_eps_act.setText(f"eps_act: {abs(xa)*2.0/SENSOR_L0*100.0:.2f}%")
        self._lbl_d_act.setText(f"d_act: {max(0.0, self._prox_offset + z):.1f}mm")

        # Hz
        if len(self._freq_ts) >= 2:
            elapsed = self._freq_ts[-1] - self._freq_ts[0]
            if elapsed > 0:
                self._lbl_hz.setText(f"{(len(self._freq_ts)-1)/elapsed:.1f} Hz")

    # ── 포트 관리 ─────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for cb in [self._cb_tdm, self._cb_rft, self._cb_arduino]:
            cur = cb.currentText(); cb.clear(); cb.addItems(ports)
            if cur in ports: cb.setCurrentText(cur)

    def _toggle_tdm(self):
        if self._tdm.isRunning():
            self._tdm.disconnect(); self._tdm.quit(); self._tdm.wait(1000)
            self._btn_tdm.setText("연결")
            self._ind_tdm.setStyleSheet(f"color:{C['red']}; font-size:15px;")
            self._update_status("TDM 해제")
        else:
            port = self._cb_tdm.currentText()
            if not port: self._update_status("TDM 포트 선택 필요"); return
            try:
                self._tdm.connect(port); self._tdm.start()
                self._btn_tdm.setText("해제")
                self._ind_tdm.setStyleSheet(f"color:{C['green']}; font-size:15px;")
                self._update_status(f"TDM 연결: {port}")
            except Exception as e:
                self._update_status(f"TDM 연결 실패: {e}")

    def _toggle_rft(self):
        if self._rft.isRunning():
            self._rft.disconnect(); self._rft.quit(); self._rft.wait(1000)
            self._btn_rft.setText("연결")
            self._ind_rft.setStyleSheet(f"color:{C['red']}; font-size:15px;")
            self._update_status("RFT 해제")
        else:
            port = self._cb_rft.currentText()
            if not port: self._update_status("RFT 포트 선택 필요"); return
            try:
                self._rft.connect(port); self._rft.start()
                self._btn_rft.setText("해제")
                self._ind_rft.setStyleSheet(f"color:{C['green']}; font-size:15px;")
                self._update_status(f"RFT 연결: {port}")
            except Exception as e:
                self._update_status(f"RFT 연결 실패: {e}")

    def _toggle_arduino(self):
        if self._arduino.isRunning():
            self._is_running_seq = False; self._done_event.set()
            self._arduino.disconnect(); self._arduino.quit(); self._arduino.wait(2000)
            self._btn_arduino.setText("연결")
            self._ind_arduino.setStyleSheet(f"color:{C['red']}; font-size:15px;")
            self._last_pos = {ax: 0.0 for ax in AXES}
            self._update_status("Arduino 해제")
        else:
            port = self._cb_arduino.currentText()
            if not port: self._update_status("Arduino 포트 선택 필요"); return
            try:
                self._arduino.connect(port); self._arduino.start()
                self._btn_arduino.setText("해제")
                self._ind_arduino.setStyleSheet(f"color:{C['green']}; font-size:15px;")
                self._update_status(f"Arduino 연결: {port}")
            except Exception as e:
                self._update_status(f"Arduino 연결 실패: {e}")

    # ── 캘리브레이션 ──────────────────────────────────────────────────────────

    def _calibrate_tdm(self):
        if len(self._cal_buf_dL) < 10:
            self._update_status("TDM 영점 실패: 데이터 부족 (최소 10샘플)"); return
        self._dL0 = float(np.mean(self._cal_buf_dL))
        self._dR0 = float(np.mean(self._cal_buf_dR))
        self._lbl_baseline.setText(
            f"dL0={self._dL0:+.4f}%  dR0={self._dR0:+.4f}%  Fz0={self._Fz0:+.3f}N")
        for k in ["dL", "dR"]: self._bufs[k].clear()
        self._update_status(
            f"TDM 영점  dL0={self._dL0:+.4f}%  dR0={self._dR0:+.4f}%")

    def _tare_fz(self):
        if len(self._cal_buf_Fz) < 10:
            self._update_status("Fz Tare 실패: RFT 데이터 부족 (최소 10샘플)"); return
        self._Fz0 = float(np.mean(self._cal_buf_Fz))
        self._lbl_baseline.setText(
            f"dL0={self._dL0:+.4f}%  dR0={self._dR0:+.4f}%  Fz0={self._Fz0:+.3f}N")
        self._bufs["Fz"].clear()
        self._update_status(f"Fz Tare 완료  Fz0={self._Fz0:+.3f}N")

    def _clear_data(self):
        self._ts.clear()
        for k in self._bufs: self._bufs[k].clear()
        self._t0 = None; self._freq_ts.clear()
        self._update_status("데이터 버퍼 초기화")

    # ── 모터 / 조그 ───────────────────────────────────────────────────────────

    def _toggle_motor(self):
        if self._motor_enabled:
            self._arduino.send("EN:0"); self._motor_enabled = False
            self._btn_motor.setText("ENABLE")
            self._btn_motor.setStyleSheet(
                f"background:{C['green']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
            self._log("모터 DISABLED")
        else:
            self._arduino.send("EN:1"); self._motor_enabled = True
            self._btn_motor.setText("DISABLE")
            self._btn_motor.setStyleSheet(
                f"background:{C['yellow']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
            self._log("모터 ENABLED")

    def _set_zero(self):
        self._arduino.send("ZERO:0"); self._log("원점 설정")

    def _do_jog(self, axis: str, dist_mm: float):
        if not self._arduino.isRunning():
            self._update_status("Arduino 미연결"); return
        if not self._motor_enabled:
            self._update_status("모터 ENABLE 필요"); return
        self._arduino.jog(axis, dist_mm, self._jog_speed)
        self._log(f"JOG {axis} {dist_mm:+.2f}mm @ {self._jog_speed:.1f}mm/s")

    def _go_z_abs(self):
        if not self._arduino.isRunning():
            self._update_status("Arduino 미연결"); return
        if not self._motor_enabled:
            self._update_status("모터 ENABLE 필요"); return
        tgt       = self._spin_z_abs.value()
        tgt_steps = int(tgt * self._arduino.steps_per_mm)
        spd_steps = max(1, int(self._jog_speed * self._arduino.steps_per_mm))
        self._arduino.send(f"ABS:Z:{tgt_steps}:{spd_steps}")
        self._log(f"Z → {tgt:.2f}mm")

    # ── 시퀀스 입력 관리 ──────────────────────────────────────────────────────

    def _update_seq_inputs(self):
        for i in reversed(range(self._seq_input_layout.count())):
            w = self._seq_input_layout.itemAt(i).widget()
            if w: w.deleteLater()

        mode = self._cb_mode.currentIndex()
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
                lay.addWidget(QLabel(label), row+1, 0)
                sp_d = QDoubleSpinBox(); sp_d.setRange(-500, 500); sp_d.setSingleStep(1)
                lay.addWidget(sp_d, row+1, 1)
                sp_s = QDoubleSpinBox(); sp_s.setRange(0.1, 50); sp_s.setValue(5.0)
                lay.addWidget(sp_s, row+1, 2)
                self._seq_spins[dk] = sp_d; self._seq_spins[sk] = sp_s

        elif mode == 1:  # 개별
            for col, h in enumerate(["축", "거리 (mm)", "속도 (mm/s)"]):
                lay.addWidget(QLabel(h), 0, col)
            for i, ax in enumerate(AXES):
                lay.addWidget(QLabel(ax), i+1, 0)
                sp_d = QDoubleSpinBox(); sp_d.setRange(-500, 500); sp_d.setSingleStep(1)
                lay.addWidget(sp_d, i+1, 1)
                sp_s = QDoubleSpinBox(); sp_s.setRange(0.1, 50); sp_s.setValue(5.0)
                lay.addWidget(sp_s, i+1, 2)
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
        mode = self._cb_mode.currentIndex()
        sp   = self._seq_spins
        sync_on   = self._chk_sync.isChecked()
        sync_time = self._sp_sync_t.value()

        if mode == 0:
            tx, ty, z_ = sp["tot_x"].value(), sp["tot_y"].value(), sp["z"].value()
            xs, ys, zs = sp["x_spd"].value(), sp["y_spd"].value(), sp["z_spd"].value()
            # 참조 파일 기준: XA/XB, YA/YB 모두 같은 방향 (+ = 바깥쪽)
            raw = [("XA", tx/2, xs), ("XB", tx/2, xs),
                   ("YA", ty/2, ys), ("YB", ty/2, ys), ("Z", z_, zs)]
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
                QTreeWidgetItem([str(i+1), lbl, step.get("desc", ""), spd]))

    def _load_for_edit(self, item):
        idx = self._seq_tree.indexOfTopLevelItem(item)
        if idx < 0: return
        self._editing_idx = idx
        step = self._seq_data[idx]
        if step["type"] == "WAIT":
            self._cb_mode.setCurrentIndex(2)
            QTimer.singleShot(50, lambda: self._seq_spins["delay"].setValue(step["val"]))
            return
        hint = step.get("hint", "ind")
        cmds_dict = {ax: (d, s) for ax, d, s in step.get("cmds", [])}
        if hint == "sym":
            self._cb_mode.setCurrentIndex(0)
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
            self._cb_mode.setCurrentIndex(1)
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
            self._seq_data[idx-1], self._seq_data[idx] = self._seq_data[idx], self._seq_data[idx-1]
            self._rebuild_tree()

    def _seq_down(self):
        items = self._seq_tree.selectedItems()
        if not items: return
        idx = self._seq_tree.indexOfTopLevelItem(items[0])
        if idx < len(self._seq_data)-1:
            self._seq_data[idx], self._seq_data[idx+1] = self._seq_data[idx+1], self._seq_data[idx]
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

    # ── 시퀀스 실행 ───────────────────────────────────────────────────────────

    def _run_sequence(self):
        if not self._seq_data:
            self._log("[시퀀스] 비어 있음"); return
        if not self._arduino.isRunning():
            self._log("[시퀀스] Arduino 미연결"); return
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
                    lbl = f"{run_count}/{repeat}" if repeat > 0 else f"{run_count} (무한)"
                    self._log(f"[시퀀스] {lbl} 회차 시작")

                    for i, step in enumerate(self._seq_data):
                        if not self._is_running_seq: break
                        self._log(f"  [스텝 {i+1}] {step['desc']}")

                        if step["type"] == "WAIT":
                            t_end = time.time() + step["val"] / 1000.0
                            while self._is_running_seq and time.time() < t_end:
                                time.sleep(0.02)

                        elif step["type"] == "MOVE":
                            cmds = [(ax, d, s) for ax, d, s in step.get("cmds", [])
                                    if abs(d) >= 1e-6]
                            if not cmds: continue
                            # ABS:{ax}:{target_steps}:{spd}:... 형식으로 절대 이동
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

    # ── 녹화 / 저장 ───────────────────────────────────────────────────────────

    def _toggle_record(self, checked):
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
            self._update_status("저장할 데이터 없음"); return
        path = Path(self._save_dir) / \
               f"mms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        hdr = ["t_s",
               "dL_pct", "dR_pct", "dV",
               "xa_mm", "xb_mm", "ya_mm", "yb_mm", "z_mm",
               "eps_act_pct", "d_act_mm",
               "Fx_N", "Fy_N", "Fz_N", "Tx_Nm", "Ty_Nm", "Tz_Nm"]
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows([hdr] + self._rec_rows)
            self._update_status(f"저장 완료: {path}")
        except Exception as e:
            self._update_status(f"저장 실패: {e}")

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "저장 폴더", self._save_dir)
        if d: self._save_dir = d; self._lbl_dir.setText(d)

    # ── 로그 / 상태 ───────────────────────────────────────────────────────────

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        text = f"[{ts}] {msg}"
        QTimer.singleShot(0, lambda: (
            self._seq_log.append(text),
            self._jog_log.append(text),
            self._seq_log.verticalScrollBar().setValue(
                self._seq_log.verticalScrollBar().maximum()),
            self._jog_log.verticalScrollBar().setValue(
                self._jog_log.verticalScrollBar().maximum()),
        ))

    def _update_status(self, msg: str):
        self._sb.showMessage(f"[{datetime.now().strftime('%H:%M:%S')}]  {msg}")

    def closeEvent(self, event):
        self._ui_timer.stop()
        self._is_running_seq = False; self._done_event.set()
        self._tdm.disconnect();     self._tdm.quit();     self._tdm.wait(1000)
        self._rft.disconnect();     self._rft.quit();     self._rft.wait(1000)
        self._arduino.disconnect(); self._arduino.quit(); self._arduino.wait(2000)
        event.accept()


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor(C["bg"]))
    palette.setColor(QPalette.WindowText,      QColor(C["text"]))
    palette.setColor(QPalette.Base,            QColor(C["bg2"]))
    palette.setColor(QPalette.Text,            QColor(C["text"]))
    palette.setColor(QPalette.Button,          QColor(C["bg3"]))
    palette.setColor(QPalette.ButtonText,      QColor(C["text"]))
    palette.setColor(QPalette.Highlight,       QColor(C["blue"]))
    palette.setColor(QPalette.HighlightedText, QColor(C["bg"]))
    app.setPalette(palette)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
