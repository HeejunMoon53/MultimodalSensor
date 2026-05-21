"""
sync_decoupler_monitor.py
STM32 ONNX 추론 + Arduino 인장머신 동기화 — 예측 vs 실제 비교 + 시퀀스 제어 UI

실행:
    C:/ml_env/Scripts/python nn_decoupling/sync_decoupler_monitor.py

STM32: ldc_raw, r_filtered, teng_filtered, r_raw, teng_raw  (115200 baud)
Arduino: POS? → POS:xa:xb:ya:yb:z:...  (100ms 폴링)
         ABS/JOG/ZERO/EN 명령 송신
"""

import sys, os, time, csv, copy, threading
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np

# numpy 1.x에서 numpy 2.x 포맷으로 저장된 pkl 로드 호환성 패치
if not hasattr(np, '_core'):
    import numpy.core as _np_core
    np._core = _np_core
    import sys as _sys
    for _k, _v in list(_sys.modules.items()):
        if _k.startswith('numpy.core'):
            _alias = _k.replace('numpy.core', 'numpy._core', 1)
            if _alias not in _sys.modules:
                _sys.modules[_alias] = _v

import serial
import serial.tools.list_ports
import pickle

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QFileDialog, QSplitter, QStatusBar,
    QFrame, QDoubleSpinBox, QSpinBox, QGroupBox, QTabWidget, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QCheckBox, QMessageBox,
    QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette

import pyqtgraph as pg

# ── 경로 ─────────────────────────────────────────────────────────────────────
HERE      = Path(__file__).parent
ONNX_PATH = HERE / "decoupler.onnx"
PKL_PATH  = HERE / "scalers.pkl"

# ── 상수 ─────────────────────────────────────────────────────────────────────
AXES           = ["XA", "XB", "YA", "YB", "Z"]
STEPS_PER_REV  = 200
DEF_MICROSTEP  = 8
DEF_PITCH_MM   = 5.0
MAX_POINTS     = 600
BAUD_STM32     = 115200
BAUD_ARDUINO   = 115200
CAL_SAMPLES    = 50
ARDUINO_POLL   = 0.1

SENSOR_L0      = 120.0
PROX_OFFSET    = 52.0

OBJ_METAL_THR  = -0.25
OBJ_HAND_THR   =  0.15
OBJ_HAND_SCALE = -10.0
TENG_CONTACT_SIGMA = 6.0
TENG_CONTACT_HOLD  = 60

C = {
    "bg":     "#1e1e2e", "bg2":   "#181825", "bg3":   "#313244",
    "text":   "#cdd6f4", "text2": "#a6adc8",
    "blue":   "#89b4fa", "green": "#a6e3a1", "yellow":"#f9e2af",
    "mauve":  "#cba6f7", "red":   "#f38ba8", "teal":  "#94e2d5",
    "border": "#45475a", "peach": "#fab387",
}
_D_SMOOTH_ALPHA = 0.4


def _fmt_time(s: float) -> str:
    s = max(0, int(s))
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"


# ══════════════════════════════════════════════════════════════════════════════
# Inferencer
# ══════════════════════════════════════════════════════════════════════════════

class Inferencer:
    def __init__(self):
        self.ready = False; self.load_error = None
        self.L0 = None; self.R0 = None
        self._in_sc = None; self._out_sc = None; self._sess = None
        self._d_smooth = None; self._d_smooth_hand = None; self._prev_obj_type = None
        self.teng_thr = 300.0; self._teng_prev = None; self._contact_latch = 0
        self.strain_ratio = 0.36
        self.obj_metal_thr = OBJ_METAL_THR
        self.obj_hand_thr  = OBJ_HAND_THR
        self.obj_hand_scale = OBJ_HAND_SCALE
        self._load()

    def _load(self):
        if not PKL_PATH.exists():
            self.load_error = "scalers.pkl 없음"; return
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with open(PKL_PATH, "rb") as f: s = pickle.load(f)
        except Exception as e:
            self.load_error = f"pkl 로드 실패: {e}"; return
        if "L0" in s: self.L0 = float(s["L0"])
        if "R0" in s: self.R0 = float(s["R0"])
        if "input" not in s or "output" not in s:
            self.load_error = "스케일러 없음 (raw only — Calibrate 후 사용 가능)"; return
        self._in_sc = s["input"]; self._out_sc = s["output"]
        if not ONNX_PATH.exists():
            self.load_error = "decoupler.onnx 없음"; return
        try:
            import onnxruntime as ort
            self._sess = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
            self.ready = True
        except Exception as e:
            self.load_error = f"ONNX 로드 실패: {e}"

    def set_baseline(self, L0, R0, teng_0=None, teng_sigma=None):
        self.L0, self.R0 = L0, R0
        if teng_0 is not None:
            self.teng_thr = teng_sigma * TENG_CONTACT_SIGMA if teng_sigma else self.teng_thr
        self._d_smooth = self._d_smooth_hand = self._prev_obj_type = self._teng_prev = None
        self._contact_latch = 0

    def update_strain_ratio_auto(self, dL, dR, alpha=0.005):
        if abs(dR) < 1e-9: return
        k = dL / dR
        if not (-1.0 < k < 5.0): return
        self.strain_ratio = (1.0 - alpha) * self.strain_ratio + alpha * k

    def classify(self, dL, teng_raw):
        obj = ("METAL" if dL < self.obj_metal_thr
               else "HAND" if dL > self.obj_hand_thr else "NONE")
        if self._teng_prev is not None and abs(teng_raw - self._teng_prev) > self.teng_thr:
            self._contact_latch = TENG_CONTACT_HOLD
        self._teng_prev = teng_raw
        if self._contact_latch > 0:
            self._contact_latch -= 1; return obj, True
        return obj, False

    def run(self, ldc_raw, r_raw, obj_type="METAL", dL_corrected=None):
        if self.L0 is None: return 0.0, 0.0, None, None
        ldc = float(ldc_raw) if ldc_raw > 0 else float(self.L0)
        dL  = ((self.L0 / ldc) ** 2 - 1.0) * 100.0 if ldc > 0 else 0.0
        dR  = ((r_raw - self.R0) / self.R0) * 100.0 if self.R0 != 0 else 0.0
        if not self.ready or obj_type == "NONE": return dL, dR, None, None
        if obj_type != self._prev_obj_type:
            self._d_smooth = self._d_smooth_hand = None
            self._prev_obj_type = obj_type
        dL_model = dL if obj_type == "METAL" else (
            (dL_corrected if dL_corrected is not None else dL) * self.obj_hand_scale)
        try:
            x = self._in_sc.transform([[dL_model, dR]]).astype(np.float32)
            y = self._sess.run(None, {"sensor_input": x})[0]
            yp = self._out_sc.inverse_transform(y)
            eps   = float(np.clip(yp[0, 0], 0.0, 0.30))
            d_raw = float(np.clip(yp[0, 1], 0.0, 50.0))
            if obj_type == "METAL":
                if self._d_smooth is None: self._d_smooth = d_raw
                self._d_smooth = _D_SMOOTH_ALPHA * d_raw + (1 - _D_SMOOTH_ALPHA) * self._d_smooth
                return dL, dR, eps, self._d_smooth
            else:
                if self._d_smooth_hand is None: self._d_smooth_hand = d_raw
                self._d_smooth_hand = _D_SMOOTH_ALPHA * d_raw + (1 - _D_SMOOTH_ALPHA) * self._d_smooth_hand
                return dL, dR, eps, self._d_smooth_hand
        except Exception as e:
            self.load_error = f"추론 오류: {e}"; return dL, dR, None, None


# ══════════════════════════════════════════════════════════════════════════════
# STM32 리더
# ══════════════════════════════════════════════════════════════════════════════

class STM32Reader(QThread):
    data_received = pyqtSignal(float, list)
    error_msg     = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser = None; self._running = False

    def connect(self, port, baud=BAUD_STM32):
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
                        if line:
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
            return vals[:5] if len(vals) >= 5 else None
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# Arduino 컨트롤러
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
        steps = int(abs(dist_mm) * self.steps_per_mm)
        spd   = max(1, int(speed_mms * self.steps_per_mm))
        self.send(f"JOG:{axis}:{-steps if dist_mm < 0 else steps}:{spd}")

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
    def __init__(self, label, unit, color, fmt="{:.2f}"):
        super().__init__()
        self._fmt = fmt
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 5, 10, 5); vbox.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{C['text2']}; font-size:10px; font-weight:600; letter-spacing:1px;")
        vbox.addWidget(lbl)
        row = QHBoxLayout()
        self._val = QLabel("—")
        self._val.setStyleSheet(f"color:{color}; font-size:24px; font-weight:700; font-family:Consolas;")
        row.addWidget(self._val); row.addStretch()
        u = QLabel(unit); u.setStyleSheet(f"color:{C['text2']}; font-size:12px; margin-top:6px;")
        row.addWidget(u); vbox.addLayout(row)
        self.setStyleSheet(f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;")

    def update(self, val):
        self._val.setText("—" if val is None else self._fmt.format(val))


class CompareCard(QWidget):
    """예측 / 실제 / 오차 3단 카드."""
    def __init__(self, label, unit, pred_color, fmt="{:.2f}", err_fmt="{:+.2f}"):
        super().__init__()
        self._fmt = fmt; self._err_fmt = err_fmt
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 5, 10, 5); vbox.setSpacing(2)
        vbox.addWidget(self._small_lbl(label))
        row_p = QHBoxLayout()
        row_p.addWidget(self._small_lbl("PRED"))
        self._pred = QLabel("—")
        self._pred.setStyleSheet(f"color:{pred_color}; font-size:22px; font-weight:700; font-family:Consolas;")
        row_p.addWidget(self._pred); row_p.addStretch()
        row_p.addWidget(QLabel(unit))
        vbox.addLayout(row_p)
        row_a = QHBoxLayout()
        row_a.addWidget(self._small_lbl("ACT "))
        self._act = QLabel("—")
        self._act.setStyleSheet(f"color:{C['text2']}; font-size:15px; font-family:Consolas;")
        row_a.addWidget(self._act); row_a.addStretch()
        row_a.addWidget(self._small_lbl("ERR "))
        self._err = QLabel("—")
        self._err.setStyleSheet(f"font-size:15px; font-family:Consolas; font-weight:600;")
        row_a.addWidget(self._err)
        vbox.addLayout(row_a)
        self.setStyleSheet(f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;")

    def _small_lbl(self, t):
        l = QLabel(t); l.setStyleSheet(f"color:{C['text2']}; font-size:9px; font-weight:700;"); return l

    def update(self, pred, actual):
        if pred is None:
            self._pred.setText("—")
            self._err.setText("—")
            self._err.setStyleSheet(f"font-size:15px; font-family:Consolas; color:{C['text2']};")
        else:
            self._pred.setText(self._fmt.format(pred))
            if actual is not None:
                err = pred - actual
                self._err.setText(self._err_fmt.format(err))
                col = C["green"] if abs(err) < 2.0 else (C["yellow"] if abs(err) < 5.0 else C["red"])
                self._err.setStyleSheet(f"font-size:15px; font-family:Consolas; font-weight:600; color:{col};")
            else:
                self._err.setText("—")
                self._err.setStyleSheet(f"font-size:15px; font-family:Consolas; color:{C['text2']};")
        if actual is None:
            self._act.setText("—")
        else:
            self._act.setText(self._fmt.format(actual))


# ══════════════════════════════════════════════════════════════════════════════
# 메인 윈도우
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    _seq_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sync Decoupler Monitor — 예측 vs 실제 + 시퀀스 제어")
        self.resize(1500, 900)

        self._stm32      = STM32Reader()
        self._arduino    = ArduinoController()
        self._inferencer = Inferencer()

        # 센서 버퍼
        self._t0   = None
        self._ts   = deque(maxlen=MAX_POINTS)
        self._bufs = {k: deque(maxlen=MAX_POINTS)
                      for k in ["dL","dR","teng","eps_pred","d_pred","eps_act","d_act"]}
        self._cal_buf_ldc  = deque(maxlen=CAL_SAMPLES)
        self._cal_buf_r    = deque(maxlen=CAL_SAMPLES)
        self._cal_buf_teng = deque(maxlen=CAL_SAMPLES)

        # 상태
        self._last_obj     = "NONE"
        self._last_contact = False
        self._last_pos     = {ax: 0.0 for ax in AXES}

        # 모터 / 시퀀스 상태
        self._motor_enabled  = False
        self._is_running_seq = False
        self._done_event     = threading.Event()
        self._seq_data       = []
        self._clipboard      = []
        self._editing_idx    = None

        # 설정
        self._settings = {
            "microstep": DEF_MICROSTEP, "pitch_mm": DEF_PITCH_MM,
            "jog_small": 0.5, "jog_mid": 2.0, "jog_large": 10.0,
            "jog_speed": 5.0,
        }
        self._apply_settings()

        # 기타
        self._prox_offset = PROX_OFFSET
        self._recording   = False

        # 데이터 수집 상태
        self._coll_mode     = False
        self._coll_total    = 0
        self._coll_current  = 0
        self._coll_start_ts = None
        self._rec_rows    = []
        self._save_dir    = str(Path.home())
        self._freq_ts     = deque(maxlen=100)

        self._build_ui()
        self._connect_signals()
        self._seq_finished.connect(lambda: self._btn_run_seq.setEnabled(True))

        self._ui_timer = QTimer()
        self._ui_timer.timeout.connect(self._refresh)
        self._ui_timer.start(40)

    def _apply_settings(self):
        spm = (STEPS_PER_REV * self._settings["microstep"]) / self._settings["pitch_mm"]
        self._arduino.steps_per_mm = spm

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
        splitter.setSizes([400, 1100])
        root.addWidget(splitter, stretch=1)

        root.addWidget(_hline())
        root.addWidget(self._build_record_bar())

        sb = QStatusBar()
        sb.setStyleSheet(f"color:{C['text2']}; font-size:12px;")
        self.setStatusBar(sb)
        self._sb = sb
        self._update_status("미연결")

    # ── 상단 바 ───────────────────────────────────────────────────────────────

    def _build_top_bar(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0); lay.setSpacing(6)

        # STM32
        lay.addWidget(self._lbl("STM32"))
        self._cb_stm32 = QComboBox(); self._cb_stm32.setMinimumWidth(100)
        lay.addWidget(self._cb_stm32)
        self._btn_stm32 = QPushButton("연결")
        self._btn_stm32.setFixedSize(60, 30); self._btn_stm32.clicked.connect(self._toggle_stm32)
        lay.addWidget(self._btn_stm32)
        self._ind_stm32 = QLabel("●"); self._ind_stm32.setStyleSheet(f"color:{C['red']}; font-size:15px;")
        lay.addWidget(self._ind_stm32)

        lay.addWidget(_vline())

        # Arduino
        lay.addWidget(self._lbl("Arduino"))
        self._cb_arduino = QComboBox(); self._cb_arduino.setMinimumWidth(100)
        lay.addWidget(self._cb_arduino)
        self._btn_arduino = QPushButton("연결")
        self._btn_arduino.setFixedSize(60, 30); self._btn_arduino.clicked.connect(self._toggle_arduino)
        lay.addWidget(self._btn_arduino)
        self._ind_arduino = QLabel("●"); self._ind_arduino.setStyleSheet(f"color:{C['red']}; font-size:15px;")
        lay.addWidget(self._ind_arduino)

        btn_ref = QPushButton("⟳"); btn_ref.setFixedSize(30, 30)
        btn_ref.setToolTip("포트 목록 새로고침"); btn_ref.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_ref)

        lay.addWidget(_vline())

        # 모터 Enable
        self._btn_motor = QPushButton("ENABLE")
        self._btn_motor.setFixedHeight(30)
        self._btn_motor.setStyleSheet(f"background:{C['green']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
        self._btn_motor.clicked.connect(self._toggle_motor)
        lay.addWidget(self._btn_motor)

        btn_zero = QPushButton("ZERO")
        btn_zero.setFixedHeight(30)
        btn_zero.clicked.connect(self._set_zero)
        lay.addWidget(btn_zero)

        lay.addWidget(_vline())

        # Calibrate
        self._btn_cal = QPushButton("Calibrate")
        self._btn_cal.setFixedHeight(30)
        self._btn_cal.setStyleSheet(
            f"background:{C['bg3']}; color:{C['yellow']}; "
            f"border:1px solid {C['yellow']}; border-radius:5px; font-weight:600;")
        self._btn_cal.clicked.connect(self._calibrate)
        lay.addWidget(self._btn_cal)

        lay.addSpacing(6)
        self._lbl_sr = QLabel(f"k={self._inferencer.strain_ratio:.3f}")
        self._lbl_sr.setStyleSheet(f"color:{C['teal']}; font-size:12px; font-family:Consolas;")
        lay.addWidget(self._lbl_sr)

        lay.addSpacing(6)
        self._lbl_baseline = QLabel()
        self._lbl_baseline.setStyleSheet(f"color:{C['text2']}; font-size:12px; font-family:Consolas;")
        lay.addWidget(self._lbl_baseline)
        self._update_baseline_label()

        lay.addStretch()

        self._lbl_hz = QLabel("— Hz")
        self._lbl_hz.setStyleSheet(f"color:{C['teal']}; font-size:13px; font-weight:700; font-family:Consolas;")
        lay.addWidget(self._lbl_hz)

        self._refresh_ports()
        return bar

    # ── 위치 표시 바 ──────────────────────────────────────────────────────────

    def _build_pos_bar(self):
        bar = QGroupBox("현재 위치 (mm)")
        bar.setMaximumHeight(60)
        grid = QGridLayout(bar)
        grid.setContentsMargins(8, 2, 8, 2); grid.setSpacing(4)
        self._pos_labels = {}
        for i, ax in enumerate(AXES):
            grid.addWidget(QLabel(ax, alignment=Qt.AlignCenter), 0, i)
            lbl = QLabel("0.000", alignment=Qt.AlignCenter)
            lbl.setStyleSheet(f"font-size:18px; font-weight:700; color:{C['blue']}; font-family:Consolas;")
            grid.addWidget(lbl, 1, i)
            self._pos_labels[ax] = lbl
        return bar

    # ── 좌측 패널: 탭 (센서 / 수동 조그 / 시퀀스) ──────────────────────────────

    def _build_left_panel(self):
        tabs = QTabWidget()
        tabs.addTab(self._build_sensor_panel(),    "센서")
        tabs.addTab(self._build_manual_tab(),      "수동 조그")
        tabs.addTab(self._build_sequence_tab(),    "시퀀스 프로그램")
        tabs.addTab(self._build_collection_tab(),  "데이터 수집")
        return tabs

    def _build_sensor_panel(self):
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setSpacing(4); vbox.setContentsMargins(4, 4, 4, 4)

        vbox.addWidget(self._section("RAW INPUTS"))
        self._cards = {
            "dL":   ValueCard("ΔL / L₀",  "%",   C["blue"],   "{:+.3f}"),
            "dR":   ValueCard("ΔR / R₀",  "%",   C["green"],  "{:+.3f}"),
            "teng": ValueCard("V_TENG",   "ADC", C["yellow"], "{:.0f}"),
        }
        for k in ["dL","dR","teng"]: vbox.addWidget(self._cards[k])

        vbox.addWidget(_hline())
        vbox.addWidget(self._section("GROUND TRUTH (Arduino)"))

        row_gt = QHBoxLayout()
        self._lbl_xa      = self._mono("XA: —mm")
        self._lbl_z       = self._mono("Z:  —mm")
        self._lbl_eps_act = self._mono("e_act: —%")
        self._lbl_d_act   = self._mono("d_act: —mm")
        for w_ in [self._lbl_xa, self._lbl_z]: row_gt.addWidget(w_)
        vbox.addLayout(row_gt)
        row_gt2 = QHBoxLayout()
        for w_ in [self._lbl_eps_act, self._lbl_d_act]: row_gt2.addWidget(w_)
        vbox.addLayout(row_gt2)

        row_off = QHBoxLayout()
        lbl_off = QLabel("Z=0 기준거리 (mm)")
        lbl_off.setStyleSheet(f"color:{C['text2']}; font-size:11px;")
        row_off.addWidget(lbl_off)
        self._spin_prox = QDoubleSpinBox()
        self._spin_prox.setRange(0, 200); self._spin_prox.setSingleStep(1)
        self._spin_prox.setDecimals(1); self._spin_prox.setValue(PROX_OFFSET)
        self._spin_prox.setFixedWidth(80)
        self._spin_prox.setStyleSheet(f"background:{C['bg3']}; color:{C['peach']}; border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;")
        self._spin_prox.setToolTip("Z=0일 때 물체까지 실제 거리\n금속=52, 손=30")
        self._spin_prox.valueChanged.connect(lambda v: setattr(self, '_prox_offset', v))
        row_off.addWidget(self._spin_prox)
        vbox.addLayout(row_off)

        vbox.addWidget(_hline())
        vbox.addWidget(self._section("OBJECT"))
        self._lbl_object = QLabel("—")
        self._lbl_object.setAlignment(Qt.AlignCenter); self._lbl_object.setFixedHeight(38)
        self._lbl_object.setStyleSheet(f"color:{C['text2']}; font-size:18px; font-weight:700; font-family:Consolas; background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;")
        vbox.addWidget(self._lbl_object)
        self._lbl_contact = QLabel("NON-CONTACT")
        self._lbl_contact.setAlignment(Qt.AlignCenter); self._lbl_contact.setFixedHeight(26)
        self._lbl_contact.setStyleSheet(f"color:{C['text2']}; font-size:12px; font-weight:600; font-family:Consolas; background:{C['bg2']}; border:1px solid {C['border']}; border-radius:6px;")
        vbox.addWidget(self._lbl_contact)

        vbox.addWidget(_hline())
        vbox.addWidget(self._section("DECOUPLED  (pred / actual / error)"))
        self._ccard_eps = CompareCard("Strain  ε",    "%",  C["mauve"], "{:.2f}", "{:+.2f}")
        self._ccard_d   = CompareCard("Proximity  d", "mm", C["red"],   "{:.1f}", "{:+.1f}")
        vbox.addWidget(self._ccard_eps)
        vbox.addWidget(self._ccard_d)

        vbox.addWidget(_hline())
        vbox.addWidget(self._section("HAND SENSITIVITY"))

        row_thr = QHBoxLayout()
        row_thr.addWidget(self._small_lbl("감지 THR (dL%)"))
        self._spin_hand_thr = QDoubleSpinBox()
        self._spin_hand_thr.setRange(0.01, 5.0); self._spin_hand_thr.setSingleStep(0.05)
        self._spin_hand_thr.setDecimals(2); self._spin_hand_thr.setValue(OBJ_HAND_THR)
        self._spin_hand_thr.setFixedWidth(80)
        self._spin_hand_thr.setStyleSheet(f"background:{C['bg3']}; color:{C['green']}; border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;")
        self._spin_hand_thr.valueChanged.connect(self._on_hand_thr_changed)
        row_thr.addWidget(self._spin_hand_thr)
        vbox.addLayout(row_thr)

        row_sc = QHBoxLayout()
        row_sc.addWidget(self._small_lbl("증폭 |SCALE|"))
        self._spin_hand_scale = QDoubleSpinBox()
        self._spin_hand_scale.setRange(1.0, 200.0); self._spin_hand_scale.setSingleStep(1.0)
        self._spin_hand_scale.setDecimals(1); self._spin_hand_scale.setValue(abs(OBJ_HAND_SCALE))
        self._spin_hand_scale.setFixedWidth(80)
        self._spin_hand_scale.setStyleSheet(f"background:{C['bg3']}; color:{C['mauve']}; border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;")
        self._spin_hand_scale.valueChanged.connect(self._on_hand_scale_changed)
        row_sc.addWidget(self._spin_hand_scale)
        vbox.addLayout(row_sc)

        self._lbl_model = QLabel()
        self._lbl_model.setAlignment(Qt.AlignCenter)
        self._lbl_model.setStyleSheet(f"font-size:11px; color:{C['text2']}; margin-top:2px;")
        self._update_model_label()
        vbox.addWidget(self._lbl_model)
        vbox.addStretch()
        return w

    # ── 수동 조그 탭 ──────────────────────────────────────────────────────────

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

        # 조그 속도
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

    # ── 시퀀스 탭 ─────────────────────────────────────────────────────────────

    def _build_sequence_tab(self):
        w = QWidget(); vbox = QVBoxLayout(w)

        # 입력 그룹
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

        btn_add = QPushButton("스텝 추가"); btn_add.clicked.connect(self._add_seq_step)
        btn_cancel = QPushButton("편집 취소"); btn_cancel.clicked.connect(self._cancel_edit)
        inp_lay.addWidget(btn_add, 3, 0, 1, 2)
        inp_lay.addWidget(btn_cancel, 3, 2, 1, 2)
        vbox.addWidget(inp_grp)

        # 트리
        self._seq_tree = QTreeWidget()
        self._seq_tree.setHeaderLabels(["#", "유형", "내용", "속도"])
        self._seq_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self._seq_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._seq_tree.itemDoubleClicked.connect(self._load_for_edit)
        vbox.addWidget(self._seq_tree, stretch=1)

        # 관리 버튼 행
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
        self._spin_repeat.setStyleSheet(f"background:{C['bg3']}; color:{C['peach']}; border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;")
        run_row.addWidget(self._spin_repeat)
        run_row.addWidget(self._small_lbl("회  (0=∞)"))
        vbox.addLayout(run_row)

        # 로그
        self._log_box = QTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setMaximumHeight(80)
        self._log_box.setStyleSheet(f"background:{C['bg2']}; color:{C['text2']}; font-size:11px; font-family:Consolas;")
        vbox.addWidget(self._log_box)

        self._update_seq_inputs()
        return w

    # ── 우측: 그래프 패널 ─────────────────────────────────────────────────────

    def _build_right_panel(self):
        pw = pg.GraphicsLayoutWidget()
        first_plot = None

        specs = [
            ("dL/L₀ (%)",         C["blue"],   None,      "dL",       None),
            ("dR/R₀ (%)",         C["green"],  None,      "dR",       None),
            ("V_TENG  (ADC)",     C["yellow"], None,      "teng",     None),
            ("Strain  e  (%)",    C["mauve"],  "#6e5b8f", "eps_pred", "eps_act"),
            ("Proximity  d (mm)", C["red"],    "#6e3040", "d_pred",   "d_act"),
        ]
        self._curves = {}

        for i, (title, pc, ac, kp, ka) in enumerate(specs):
            p = pw.addPlot(row=i, col=0, title=title)
            p.getAxis("left").setWidth(54)
            p.showGrid(x=False, y=True, alpha=0.15)
            p.titleLabel.setAttr("color", C["text2"])
            p.titleLabel.setAttr("size", "11pt")

            self._curves[kp] = p.plot(pen=pg.mkPen(pc, width=2.0))
            if ka is not None:
                self._curves[ka] = p.plot(pen=pg.mkPen(ac, width=1.5, style=Qt.DashLine))
                p.addLegend(offset=(5, 5))
                self._curves[kp].setData(name="Pred")
                self._curves[ka].setData(name="Actual")

            if i == 0: first_plot = p
            else: p.setXLink(first_plot)

            if i == len(specs) - 1: p.setLabel("bottom", "시간 (s)")
            else: p.getAxis("bottom").setStyle(showValues=False)

        pw.getItem(3, 0).setYRange(0, 30, padding=0.05)
        pw.getItem(4, 0).setYRange(0, 60, padding=0.05)

        p_dl = pw.getItem(0, 0)
        self._line_metal = pg.InfiniteLine(
            pos=OBJ_METAL_THR, angle=0,
            pen=pg.mkPen(C["teal"], width=1, style=Qt.DashLine),
            label=f"METAL ({OBJ_METAL_THR}%)",
            labelOpts={"color": C["teal"], "position": 0.02, "anchors": [(0,0),(0,0)]}
        )
        self._line_hand = pg.InfiniteLine(
            pos=OBJ_HAND_THR, angle=0,
            pen=pg.mkPen(C["green"], width=1, style=Qt.DashLine),
            label=f"HAND ({OBJ_HAND_THR}%)",
            labelOpts={"color": C["green"], "position": 0.02, "anchors": [(0,0),(0,0)]}
        )
        p_dl.addItem(self._line_metal); p_dl.addItem(self._line_hand)
        return pw

    # ── 데이터 수집 탭 ────────────────────────────────────────────────────────

    def _build_collection_tab(self):
        w = QWidget(); vbox = QVBoxLayout(w)
        vbox.setSpacing(6); vbox.setContentsMargins(8, 8, 8, 8)

        # ── 스트레인 설정 ─────────────────────────────────────────────────────
        sg = QGroupBox("스트레인 설정"); sg_lay = QGridLayout(sg)
        sg_lay.addWidget(QLabel("총 범위 (mm)"), 0, 0)
        self._sp_col_strain_mm = QDoubleSpinBox()
        self._sp_col_strain_mm.setRange(1, 200); self._sp_col_strain_mm.setValue(36)
        self._sp_col_strain_mm.setSingleStep(1); self._sp_col_strain_mm.setDecimals(1)
        sg_lay.addWidget(self._sp_col_strain_mm, 0, 1)
        sg_lay.addWidget(QLabel("스텝 수"), 0, 2)
        self._sp_col_strain_n = QSpinBox()
        self._sp_col_strain_n.setRange(2, 200); self._sp_col_strain_n.setValue(10)
        sg_lay.addWidget(self._sp_col_strain_n, 0, 3)
        vbox.addWidget(sg)

        # ── 근접도 설정 ───────────────────────────────────────────────────────
        pg = QGroupBox("근접도 설정"); pg_lay = QGridLayout(pg)
        pg_lay.addWidget(QLabel("최대거리 (Z=0, mm)"), 0, 0)
        self._sp_col_prox_max = QDoubleSpinBox()
        self._sp_col_prox_max.setRange(1, 500); self._sp_col_prox_max.setValue(52)
        self._sp_col_prox_max.setDecimals(1)
        pg_lay.addWidget(self._sp_col_prox_max, 0, 1)
        pg_lay.addWidget(QLabel("최소거리 (mm)"), 0, 2)
        self._sp_col_prox_min = QDoubleSpinBox()
        self._sp_col_prox_min.setRange(0, 100); self._sp_col_prox_min.setValue(0)
        self._sp_col_prox_min.setDecimals(1)
        pg_lay.addWidget(self._sp_col_prox_min, 0, 3)
        pg_lay.addWidget(QLabel("스텝 수 (역지그재그)"), 1, 0)
        self._sp_col_prox_n = QSpinBox()
        self._sp_col_prox_n.setRange(2, 200); self._sp_col_prox_n.setValue(10)
        self._sp_col_prox_n.setEnabled(False)
        pg_lay.addWidget(self._sp_col_prox_n, 1, 1)
        vbox.addWidget(pg)

        # ── 패턴 및 속도 ──────────────────────────────────────────────────────
        opt_g = QGroupBox("패턴 및 속도"); opt_lay = QGridLayout(opt_g)
        opt_lay.addWidget(QLabel("패턴"), 0, 0)
        self._cb_col_pattern = QComboBox()
        self._cb_col_pattern.addItems([
            "지그재그 (Strain 고정→Z 왕복)",
            "동시 스윕 (Strain+Z 동시)",
            "역지그재그 (Z 고정→Strain 왕복)",
        ])
        self._cb_col_pattern.currentIndexChanged.connect(self._on_col_pattern_changed)
        opt_lay.addWidget(self._cb_col_pattern, 0, 1, 1, 3)

        opt_lay.addWidget(QLabel("진동 횟수 (동시 스윕)"), 1, 0)
        self._sp_col_n_osc = QSpinBox()
        self._sp_col_n_osc.setRange(1, 50); self._sp_col_n_osc.setValue(5)
        self._sp_col_n_osc.setEnabled(False)
        opt_lay.addWidget(self._sp_col_n_osc, 1, 1)

        opt_lay.addWidget(QLabel("Strain 속도 (mm/s)"), 2, 0)
        self._sp_col_strain_spd = QDoubleSpinBox()
        self._sp_col_strain_spd.setRange(0.1, 50); self._sp_col_strain_spd.setValue(2.0)
        self._sp_col_strain_spd.setSingleStep(0.5)
        opt_lay.addWidget(self._sp_col_strain_spd, 2, 1)

        opt_lay.addWidget(QLabel("Z 속도 (mm/s)"), 2, 2)
        self._sp_col_z_spd = QDoubleSpinBox()
        self._sp_col_z_spd.setRange(0.1, 50); self._sp_col_z_spd.setValue(8.0)
        self._sp_col_z_spd.setSingleStep(0.5)
        opt_lay.addWidget(self._sp_col_z_spd, 2, 3)
        vbox.addWidget(opt_g)

        # ── 미리보기 및 생성 ──────────────────────────────────────────────────
        prev_row = QHBoxLayout()
        self._btn_col_gen = QPushButton("시퀀스 생성")
        self._btn_col_gen.setFixedHeight(30)
        self._btn_col_gen.setStyleSheet(
            f"background:{C['bg3']}; color:{C['blue']}; border:1px solid {C['blue']}; border-radius:4px; font-weight:600;")
        self._btn_col_gen.clicked.connect(self._preview_collection_seq)
        prev_row.addWidget(self._btn_col_gen)
        self._lbl_col_preview = QLabel("—")
        self._lbl_col_preview.setStyleSheet(f"color:{C['teal']}; font-family:Consolas; font-size:12px;")
        prev_row.addWidget(self._lbl_col_preview, stretch=1)
        vbox.addLayout(prev_row)

        vbox.addWidget(_hline())

        # ── 실행 ──────────────────────────────────────────────────────────────
        run_row = QHBoxLayout()
        self._btn_col_start = QPushButton("▶ 수집 시작")
        self._btn_col_start.setFixedHeight(34)
        self._btn_col_start.setStyleSheet(
            f"background:{C['green']}; color:{C['bg']}; font-weight:700; border-radius:4px; font-size:13px;")
        self._btn_col_start.clicked.connect(self._start_collection)
        self._btn_col_stop = QPushButton("■ 수집 정지")
        self._btn_col_stop.setFixedHeight(34)
        self._btn_col_stop.clicked.connect(self._stop_collection)
        run_row.addWidget(self._btn_col_start); run_row.addWidget(self._btn_col_stop)
        vbox.addLayout(run_row)

        # 진행 표시
        self._prog_col = QLabel("0 / 0")
        self._prog_col.setAlignment(Qt.AlignCenter)
        self._prog_col.setStyleSheet(
            f"font-size:20px; font-weight:700; font-family:Consolas; color:{C['blue']};"
            f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:6px; padding:4px;")
        vbox.addWidget(self._prog_col)

        self._lbl_col_time = QLabel("경과: --:--:--   남은: --:--:--")
        self._lbl_col_time.setAlignment(Qt.AlignCenter)
        self._lbl_col_time.setStyleSheet(f"color:{C['text2']}; font-family:Consolas; font-size:12px;")
        vbox.addWidget(self._lbl_col_time)

        self._lbl_col_file = QLabel("저장 파일: —")
        self._lbl_col_file.setAlignment(Qt.AlignCenter)
        self._lbl_col_file.setWordWrap(True)
        self._lbl_col_file.setStyleSheet(f"color:{C['peach']}; font-size:11px; font-family:Consolas;")
        vbox.addWidget(self._lbl_col_file)

        vbox.addStretch()
        return w

    def _on_col_pattern_changed(self, idx):
        self._sp_col_n_osc.setEnabled(idx == 1)
        self._sp_col_prox_n.setEnabled(idx == 2)

    # ── 녹화 바 ───────────────────────────────────────────────────────────────

    def _build_record_bar(self):
        bar = QWidget(); lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0)
        self._btn_rec = QPushButton("● RECORD")
        self._btn_rec.setFixedSize(130, 34); self._btn_rec.setCheckable(True)
        self._btn_rec.setStyleSheet(
            "QPushButton{background:#f38ba8; color:#1e1e2e; font-weight:700; font-size:13px; border-radius:5px;}"
            "QPushButton:checked{background:#a6e3a1; color:#1e1e2e;}")
        self._btn_rec.clicked.connect(self._toggle_record)
        lay.addWidget(self._btn_rec)
        lay.addSpacing(12); lay.addWidget(self._lbl("저장 폴더:"))
        self._lbl_dir = QLabel(self._save_dir)
        self._lbl_dir.setStyleSheet(f"color:{C['blue']};")
        lay.addWidget(self._lbl_dir, stretch=1)
        btn_browse = QPushButton("폴더 선택"); btn_browse.setFixedHeight(30)
        btn_browse.clicked.connect(self._browse_dir); lay.addWidget(btn_browse)
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
        l.setStyleSheet(f"color:{C['text2']}; font-size:10px; font-weight:700; letter-spacing:2px; margin-top:2px;")
        return l

    def _mono(self, t):
        l = QLabel(t)
        l.setStyleSheet(f"color:{C['teal']}; font-size:11px; font-family:Consolas; background:{C['bg2']}; border:1px solid {C['border']}; border-radius:4px; padding:1px 5px;")
        return l

    def _update_baseline_label(self):
        if self._inferencer.L0:
            self._lbl_baseline.setText(f"L0={self._inferencer.L0:.0f}  R0={self._inferencer.R0:.2f}")
        else:
            self._lbl_baseline.setText("baseline: 미로드")

    def _update_model_label(self):
        if self._inferencer.ready: txt, col = f"ONNX: {ONNX_PATH.name}", C["green"]
        elif self._inferencer.load_error: txt, col = f"[오류] {self._inferencer.load_error}", C["red"]
        else: txt, col = "모델 없음 (raw only)", C["yellow"]
        self._lbl_model.setText(txt)
        self._lbl_model.setStyleSheet(f"font-size:11px; color:{col}; margin-top:2px;")

    # ── 시그널 연결 ───────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._stm32.data_received.connect(self._on_stm32_data)
        self._stm32.error_msg.connect(lambda m: self._update_status(f"STM32: {m}"))
        self._arduino.position_updated.connect(self._on_arduino_pos)
        self._arduino.done_received.connect(self._on_done)
        self._arduino.alarm_received.connect(lambda m: self._log(f"[ALARM] {m}"))
        self._arduino.error_msg.connect(lambda m: self._update_status(f"Arduino: {m}"))

    # ── 데이터 핸들러 ─────────────────────────────────────────────────────────

    def _on_stm32_data(self, ts, vals):
        ldc = vals[0]; r = vals[3]; teng = vals[2]
        self._cal_buf_ldc.append(ldc); self._cal_buf_r.append(r)
        self._cal_buf_teng.append(teng)

        dL, dR, eps, d = self._inferencer.run(ldc, r, "METAL")
        if d is not None and d > 35.0 and abs(dR) > 0.3:
            self._inferencer.update_strain_ratio_auto(dL, dR)
        dL_corr = dL - self._inferencer.strain_ratio * dR
        obj_type, is_contact = self._inferencer.classify(dL_corr, teng)
        self._last_obj = obj_type; self._last_contact = is_contact
        if obj_type == "HAND" and self._inferencer.ready:
            _, _, eps, d = self._inferencer.run(ldc, r, "HAND", dL_corrected=dL_corr)

        xa = self._last_pos.get("XA"); z = self._last_pos.get("Z")
        eps_act = abs(xa) * 2.0 / SENSOR_L0 if xa is not None else None
        d_act   = max(0.0, self._prox_offset + z) if z is not None else None

        if self._t0 is None: self._t0 = ts
        t = ts - self._t0
        self._ts.append(t)
        self._bufs["dL"].append(dL); self._bufs["dR"].append(dR)
        self._bufs["teng"].append(teng)
        self._bufs["eps_pred"].append(eps * 100.0 if eps is not None else None)
        self._bufs["d_pred"].append(d)
        self._bufs["eps_act"].append(eps_act * 100.0 if eps_act is not None else None)
        self._bufs["d_act"].append(d_act)
        self._freq_ts.append(ts)

        if self._recording:
            xa_v = xa if xa is not None else ""
            z_v  = z  if z  is not None else ""
            self._rec_rows.append([
                round(t, 4), ldc, r, teng, xa_v, z_v,
                round(dL, 4), round(dR, 4),
                round(eps * 100.0, 4) if eps is not None else "",
                round(d, 2)           if d   is not None else "",
                round(eps_act * 100.0, 4) if eps_act is not None else "",
                round(d_act, 2)           if d_act   is not None else "",
            ])
            self._lbl_rec_count.setText(f"{len(self._rec_rows)}행")

    def _on_arduino_pos(self, ts, pos):
        self._last_pos.update(pos)

    def _on_done(self):
        self._done_event.set()

    # ── 화면 갱신 ─────────────────────────────────────────────────────────────

    def _refresh(self):
        n = len(self._ts)
        if n < 2: return
        ts_arr = np.array(self._ts)

        for key, curve in self._curves.items():
            buf = self._bufs.get(key)
            if buf is None or len(buf) != n: continue
            curve.setData(ts_arr, np.array([v if v is not None else np.nan for v in buf]))

        def last(k): return self._bufs[k][-1] if self._bufs[k] else None
        self._cards["dL"].update(last("dL"))
        self._cards["dR"].update(last("dR"))
        self._cards["teng"].update(last("teng"))
        self._ccard_eps.update(last("eps_pred"), last("eps_act"))
        self._ccard_d.update(last("d_pred"), last("d_act"))

        xa = self._last_pos.get("XA"); z = self._last_pos.get("Z")
        if xa is not None:
            self._lbl_xa.setText(f"XA:{xa:+7.3f}mm")
            self._lbl_eps_act.setText(f"e_act:{abs(xa)*2/SENSOR_L0*100:.2f}%")
        if z is not None:
            self._lbl_z.setText(f"Z:{z:+7.3f}mm")
            self._lbl_d_act.setText(f"d_act:{max(0.0,self._prox_offset+z):.1f}mm")

        for ax, lbl in self._pos_labels.items():
            lbl.setText(f"{self._last_pos.get(ax, 0):.3f}")

        if len(self._freq_ts) >= 2:
            elapsed = self._freq_ts[-1] - self._freq_ts[0]
            if elapsed > 0:
                self._lbl_hz.setText(f"{(len(self._freq_ts)-1)/elapsed:.1f} Hz")

        obj = self._last_obj
        col = {"METAL": C["teal"], "HAND": C["green"], "NONE": C["text2"]}[obj]
        bg  = {"METAL": C["bg3"],  "HAND": C["bg3"],   "NONE": C["bg2"]}[obj]
        self._lbl_object.setText(obj)
        self._lbl_object.setStyleSheet(
            f"color:{col}; font-size:18px; font-weight:700; font-family:Consolas;"
            f"background:{bg}; border:1px solid {col}; border-radius:8px;")

        if self._last_contact:
            self._lbl_contact.setText("● CONTACT")
            self._lbl_contact.setStyleSheet(
                f"color:{C['bg']}; font-size:12px; font-weight:700; font-family:Consolas;"
                f"background:{C['red']}; border:1px solid {C['red']}; border-radius:6px;")
        else:
            self._lbl_contact.setText("NON-CONTACT")
            self._lbl_contact.setStyleSheet(
                f"color:{C['text2']}; font-size:12px; font-weight:600; font-family:Consolas;"
                f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:6px;")

        self._lbl_sr.setText(f"k={self._inferencer.strain_ratio:.3f}")
        self._update_model_label()

    # ── 포트 관리 ─────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for cb in [self._cb_stm32, self._cb_arduino]:
            cur = cb.currentText(); cb.clear(); cb.addItems(ports)
            if cur in ports: cb.setCurrentText(cur)

    def _toggle_stm32(self):
        if self._stm32.isRunning():
            self._stm32.disconnect(); self._stm32.quit(); self._stm32.wait(1000)
            self._btn_stm32.setText("연결")
            self._ind_stm32.setStyleSheet(f"color:{C['red']}; font-size:15px;")
            self._update_status("STM32 해제")
        else:
            port = self._cb_stm32.currentText()
            if not port: self._update_status("STM32 포트 선택 필요"); return
            try:
                self._stm32.connect(port); self._stm32.start()
                self._btn_stm32.setText("해제")
                self._ind_stm32.setStyleSheet(f"color:{C['green']}; font-size:15px;")
                self._update_status(f"STM32 연결: {port}")
            except Exception as e:
                self._update_status(f"STM32 연결 실패: {e}")

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
                self._apply_settings()
                self._arduino.connect(port)
                self._arduino.start()
                self._btn_arduino.setText("해제")
                self._ind_arduino.setStyleSheet(f"color:{C['green']}; font-size:15px;")
                self._update_status(f"Arduino 연결: {port}")
            except Exception as e:
                self._update_status(f"Arduino 연결 실패: {e}")

    # ── Calibrate ─────────────────────────────────────────────────────────────

    def _calibrate(self):
        if len(self._cal_buf_ldc) < 10:
            self._update_status("재보정 실패: 데이터 부족"); return
        L0 = float(np.mean(self._cal_buf_ldc)); R0 = float(np.mean(self._cal_buf_r))
        ta = np.array(self._cal_buf_teng, dtype=np.float64)
        sig = float(np.diff(ta).std()) if len(ta) > 2 else 50.0
        self._inferencer.set_baseline(L0, R0, float(ta.mean()), sig)
        self._update_baseline_label()
        for k in ["dL","dR","eps_pred","d_pred","eps_act","d_act"]: self._bufs[k].clear()
        self._last_obj = "NONE"; self._last_contact = False
        self._save_baseline_to_pkl(L0, R0)
        self._update_status(f"재보정 완료: L0={L0:.0f}  R0={R0:.2f}  dV_thr={self._inferencer.teng_thr:.0f}")

    def _save_baseline_to_pkl(self, L0, R0):
        try:
            s = {}
            if PKL_PATH.exists():
                with open(PKL_PATH, "rb") as f: s = pickle.load(f)
            s["L0"] = L0; s["R0"] = R0
            PKL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(PKL_PATH, "wb") as f: pickle.dump(s, f)
        except Exception as e:
            self._update_status(f"pkl 저장 실패: {e}")

    # ── HAND 감도 ─────────────────────────────────────────────────────────────

    def _on_hand_thr_changed(self, val):
        self._inferencer.obj_hand_thr = val; self._line_hand.setValue(val)

    def _on_hand_scale_changed(self, val):
        self._inferencer.obj_hand_scale = -abs(val)

    # ── 모터 제어 ─────────────────────────────────────────────────────────────

    def _toggle_motor(self):
        if self._motor_enabled:
            self._arduino.send("EN:0")
            self._motor_enabled = False
            self._btn_motor.setText("ENABLE")
            self._btn_motor.setStyleSheet(f"background:{C['green']}; color:{C['bg']}; font-weight:700; border-radius:4px;")
            self._log("모터 DISABLED")
        else:
            self._arduino.send("EN:1")
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
            raw = [("XA", tx/2, xs), ("XB", -tx/2, xs),
                   ("YA", ty/2, ys), ("YB", -ty/2, ys), ("Z", z_, zs)]
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
                lbl = hint_map.get(step.get("hint",""), "이동")
                if step.get("sync"): lbl += "+동기"
                spd = " / ".join(f"{s:.1f}" for _, _, s in step.get("cmds",[]))
            else:
                lbl = "대기"; spd = "-"
            self._seq_tree.addTopLevelItem(
                QTreeWidgetItem([str(i+1), lbl, step.get("desc",""), spd]))

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
                self._seq_spins["tot_x"].setValue(cmds_dict.get("XA",(0,5))[0] * 2)
                self._seq_spins["tot_y"].setValue(cmds_dict.get("YA",(0,5))[0] * 2)
                self._seq_spins["z"].setValue(cmds_dict.get("Z",(0,5))[0])
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
                        self._log(f"  [스텝 {i+1}] {step['desc']}")

                        if step["type"] == "WAIT":
                            t_end = time.time() + step["val"] / 1000.0
                            while self._is_running_seq and time.time() < t_end:
                                time.sleep(0.02)

                        elif step["type"] == "MOVE":
                            cmds = [(ax, d, s) for ax, d, s in step.get("cmds", []) if abs(d) >= 1e-6]
                            if cmds:
                                parts = []
                                for ax, dist, spd in cmds:
                                    steps = int(abs(dist) * self._arduino.steps_per_mm)
                                    spd_s = max(1, int(spd * self._arduino.steps_per_mm))
                                    parts += [ax, str(-steps if dist < 0 else steps), str(spd_s)]
                                expected_t = max(abs(d) / max(s, 0.01) for _, d, s in cmds)
                                move_timeout = expected_t * 1.5 + 2.0
                                self._done_event.clear()
                                self._arduino.send("JOG:" + ":".join(parts))
                                t_start = time.time()
                                while self._is_running_seq:
                                    if time.time() - t_start > move_timeout:
                                        self._log(f"  [경고] DONE 미수신 — 타임아웃 후 진행")
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

    # ── 데이터 수집 시퀀스 생성 ────────────────────────────────────────────────

    def _generate_collection_seq(self):
        """지그재그 또는 동시 스윕 시퀀스를 생성해 _seq_data 포맷 리스트로 반환."""
        strain_mm  = self._sp_col_strain_mm.value()
        n_strain   = self._sp_col_strain_n.value()
        prox_max   = self._sp_col_prox_max.value()
        prox_min   = self._sp_col_prox_min.value()
        strain_spd = self._sp_col_strain_spd.value()
        z_spd      = self._sp_col_z_spd.value()
        pattern    = self._cb_col_pattern.currentIndex()
        n_osc      = self._sp_col_n_osc.value()
        n_prox     = self._sp_col_prox_n.value()

        xa_max  = strain_mm / 2.0           # XA 최대 이동량 (대칭)
        z_close = -(prox_max - prox_min)    # Z 접근 방향 (음수)

        def move(cmds, desc):
            return {"type": "MOVE", "hint": "ind", "cmds": cmds, "desc": desc,
                    "sync": False, "sync_time": 0.0}

        seq = []
        # 홈 복귀
        seq.append(move([("XA", 0.0, strain_spd), ("XB", 0.0, strain_spd), ("Z", 0.0, z_spd)],
                        "홈 이동"))

        if pattern == 0:  # ── 지그재그 ───────────────────────────────────────
            for i in range(n_strain):
                xa = xa_max * i / max(1, n_strain - 1)
                seq.append(move([("XA", xa, strain_spd), ("XB", -xa, strain_spd),
                                 ("Z", 0.0, z_spd)],
                                f"[{i+1}/{n_strain}] 스트레인 {xa*2:.1f}mm 설정"))
                seq.append(move([("Z", z_close, z_spd)],
                                f"[{i+1}/{n_strain}] Z 접근"))
                seq.append(move([("Z", 0.0, z_spd)],
                                f"[{i+1}/{n_strain}] Z 후퇴"))

        elif pattern == 1:  # ── 동시 스윕 ────────────────────────────────────
            n_steps = n_osc * 2
            xa_per  = xa_max / max(1, n_steps)
            z_range = abs(z_close)

            for i in range(n_steps):
                xa_tgt = xa_per * (i + 1)
                z_tgt  = z_close if i % 2 == 0 else 0.0

                xa_delta = xa_per
                z_delta  = z_range
                T = max(xa_delta / strain_spd, z_delta / z_spd)
                xa_spd_i = max(0.01, xa_delta / T)
                z_spd_i  = max(0.01, z_delta  / T)

                label = "접근" if i % 2 == 0 else "후퇴"
                seq.append(move(
                    [("XA", xa_tgt, xa_spd_i), ("XB", -xa_tgt, xa_spd_i),
                     ("Z",  z_tgt,  z_spd_i)],
                    f"[{i+1}/{n_steps}] 동시 {label} — ε={xa_tgt*2:.1f}mm"))

        else:              # ── 역지그재그: Z 고정 → Strain 왕복 ───────────────
            for j in range(n_prox):
                z_j = z_close * j / max(1, n_prox - 1)
                seq.append(move([("Z", z_j, z_spd)],
                                f"[{j+1}/{n_prox}] Z={-z_j:.1f}mm 근접도 설정"))
                seq.append(move([("XA", xa_max, strain_spd), ("XB", -xa_max, strain_spd)],
                                f"[{j+1}/{n_prox}] 스트레인 증가 → {strain_mm:.0f}mm"))
                seq.append(move([("XA", 0.0, strain_spd), ("XB", 0.0, strain_spd)],
                                f"[{j+1}/{n_prox}] 스트레인 복귀 → 0mm"))

        # 홈 복귀
        seq.append(move([("XA", 0.0, strain_spd), ("XB", 0.0, strain_spd), ("Z", 0.0, z_spd)],
                        "홈 복귀"))
        return seq

    def _preview_collection_seq(self):
        """시퀀스 생성 후 예상 시간을 미리보기 레이블에 표시."""
        seq = self._generate_collection_seq()
        n = len(seq)

        strain_spd = self._sp_col_strain_spd.value()
        z_spd      = self._sp_col_z_spd.value()
        xa_max     = self._sp_col_strain_mm.value() / 2.0
        prox_range = self._sp_col_prox_max.value() - self._sp_col_prox_min.value()
        n_strain   = self._sp_col_strain_n.value()
        n_prox     = self._sp_col_prox_n.value()
        pattern    = self._cb_col_pattern.currentIndex()
        n_osc      = self._sp_col_n_osc.value()

        if pattern == 0:
            est_s = xa_max / strain_spd + n_strain * 2 * prox_range / z_spd
        elif pattern == 1:
            n_steps = n_osc * 2
            xa_per  = xa_max / max(1, n_steps)
            T_step  = max(xa_per / strain_spd, prox_range / z_spd)
            est_s   = n_steps * T_step
        else:
            est_s = n_prox * (prox_range / z_spd + 2 * xa_max / strain_spd)

        self._lbl_col_preview.setText(
            f"총 {n} 스텝 · 약 {_fmt_time(est_s)} (예상)")

    # ── 데이터 수집 실행 ───────────────────────────────────────────────────────

    def _start_collection(self):
        if not self._arduino.isRunning():
            self._update_status("Arduino 미연결"); return
        if not self._motor_enabled:
            QMessageBox.warning(self, "모터 비활성화", "ENABLE 버튼을 먼저 누르세요."); return
        if self._is_running_seq:
            self._update_status("이미 시퀀스 실행 중"); return

        seq = self._generate_collection_seq()

        self._coll_mode     = True
        self._coll_total    = len(seq)
        self._coll_current  = 0
        self._coll_start_ts = time.time()

        fname = f"collect_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._lbl_col_file.setText(f"저장: {fname}")
        self._prog_col.setText(f"0 / {self._coll_total}")
        self._lbl_col_time.setText("경과: --:--:--   남은: --:--:--")

        self._rec_rows.clear()
        self._recording = True
        self._is_running_seq = True
        self._btn_col_start.setEnabled(False)
        self._log(f"[수집] 시작 — {self._coll_total} 스텝")

        def execute():
            try:
                for i, step in enumerate(seq):
                    if not self._is_running_seq: break

                    self._coll_current = i + 1
                    QTimer.singleShot(0, self._update_collection_progress)
                    self._log(f"  [수집 {i+1}/{self._coll_total}] {step['desc']}")

                    if step["type"] == "WAIT":
                        t_end = time.time() + step["val"] / 1000.0
                        while self._is_running_seq and time.time() < t_end:
                            time.sleep(0.02)

                    elif step["type"] == "MOVE":
                        cmds = [(ax, d, s) for ax, d, s in step.get("cmds", []) if abs(d) >= 1e-6]
                        if cmds:
                            parts = []
                            for ax, dist, spd in cmds:
                                steps_val = int(abs(dist) * self._arduino.steps_per_mm)
                                spd_s = max(1, int(spd * self._arduino.steps_per_mm))
                                parts += [ax, str(-steps_val if dist < 0 else steps_val), str(spd_s)]
                            expected_t = max(abs(d) / max(s, 0.01) for _, d, s in cmds)
                            move_timeout = expected_t * 1.5 + 5.0
                            self._done_event.clear()
                            self._arduino.send("ABS:" + ":".join(parts))
                            t_start = time.time()
                            while self._is_running_seq:
                                if time.time() - t_start > move_timeout:
                                    self._log(f"  [경고] DONE 미수신 — 타임아웃 후 진행")
                                    break
                                if self._done_event.wait(timeout=0.05):
                                    self._done_event.clear(); break
            except Exception as e:
                self._log(f"[수집] 오류: {e}")
            finally:
                self._is_running_seq = False
                QTimer.singleShot(0, self._on_collection_done)

        threading.Thread(target=execute, daemon=True).start()

    def _stop_collection(self):
        self._is_running_seq = False; self._done_event.set()
        if self._coll_mode:
            self._recording = False; self._coll_mode = False
            self._btn_col_start.setEnabled(True)
            self._log("[수집] 정지 요청")

    def _on_collection_done(self):
        self._recording = False; self._coll_mode = False
        fname = self._lbl_col_file.text().replace("저장: ", "")
        self._save_csv_to(Path(self._save_dir) / fname)
        self._log(f"[수집] 완료 — {len(self._rec_rows)}행 저장")
        self._btn_col_start.setEnabled(True)

    def _update_collection_progress(self):
        cur = self._coll_current; tot = self._coll_total
        self._prog_col.setText(f"{cur} / {tot}")
        if self._coll_start_ts and cur > 0:
            elapsed   = time.time() - self._coll_start_ts
            remaining = elapsed / cur * (tot - cur)
            self._lbl_col_time.setText(
                f"경과: {_fmt_time(elapsed)}   남은: {_fmt_time(remaining)}")

    # ── 녹화 ─────────────────────────────────────────────────────────────────

    def _toggle_record(self, checked):
        if checked:
            self._rec_rows.clear(); self._btn_rec.setText("■ STOP")
            self._recording = True; self._update_status("녹화 시작")
        else:
            self._recording = False; self._btn_rec.setText("● RECORD")
            self._update_status(f"녹화 중지 — {len(self._rec_rows)}행"); self._save_csv()

    def _save_csv_to(self, path: Path):
        hdr = ["t_s","ldc_raw","r_raw","teng_raw","xa_mm","z_mm",
               "dL_pct","dR_pct","eps_pred_pct","d_pred_mm","eps_act_pct","d_act_mm"]
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows([hdr] + self._rec_rows)
            self._update_status(f"저장 완료: {path}")
        except Exception as e:
            self._update_status(f"저장 실패: {e}")

    def _save_csv(self):
        if not self._rec_rows: self._update_status("저장할 데이터 없음"); return
        path = Path(self._save_dir) / f"sync_decoupler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._save_csv_to(path)

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "저장 폴더", self._save_dir)
        if d: self._save_dir = d; self._lbl_dir.setText(d)

    # ── 로그 / 상태 ───────────────────────────────────────────────────────────

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        QTimer.singleShot(0, lambda: (
            self._log_box.append(f"[{ts}] {msg}"),
            self._log_box.verticalScrollBar().setValue(
                self._log_box.verticalScrollBar().maximum())
        ))

    def _update_status(self, msg: str):
        self._sb.showMessage(f"[{datetime.now().strftime('%H:%M:%S')}]  {msg}")

    def closeEvent(self, event):
        self._ui_timer.stop()
        self._is_running_seq = False; self._done_event.set()
        self._stm32.disconnect(); self._stm32.quit(); self._stm32.wait(1000)
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
