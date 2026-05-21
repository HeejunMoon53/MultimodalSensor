"""
sync_acquisition.py
동기화 데이터 취득 시스템

- Arduino: 포지셔닝 스테이지 제어 (인장 XA/XB + 근접 Z)
- STM32:  센서 신호 수신 (ldc_raw, r_filtered, teng_filtered, r_raw, teng_raw)
- PC:     두 신호 타임스탬프 동기화 + 가감속 구간 자동 태깅 + CSV 저장

실행:
    C:/ml_env/Scripts/python nn_decoupling/sync_acquisition.py

데이터 저장 위치:
    nn_decoupling/data/{metal|hand}/{p1_strain_discrete|p2_proximity_discrete}/

CSV 컬럼:
    t_s, xa_mm, xb_mm, ya_mm, yb_mm, z_mm,
    ldc_raw, r_raw, teng_raw, is_steady
"""

import sys, os, time, csv, queue, copy, threading, json
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import serial
import serial.tools.list_ports

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QGroupBox, QSplitter, QStatusBar, QFrame,
    QTabWidget, QLineEdit, QCheckBox, QDoubleSpinBox, QSpinBox,
    QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox, QTextEdit,
    QRadioButton, QButtonGroup, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QPalette, QFont

import pyqtgraph as pg

# ── 경로 / 상수 ───────────────────────────────────────────────────────────────
HERE        = Path(__file__).parent
DATA_ROOT   = HERE / "data"      # 기본값 (설정 없을 때 fallback)
CONFIG_PATH = HERE / "sync_config.json"

BAUD_DEFAULT = 115200
MAX_POINTS   = 500
CAL_SAMPLES  = 80
FIRMWARE_ACCEL_STEPS_S2 = 500   # Arduino firmware: setAcceleration(500)
LIMIT_MIN_MM = -200.0
LIMIT_MAX_MM  =  200.0

C = {
    "bg": "#1e1e2e", "bg2": "#181825", "bg3": "#313244",
    "text": "#cdd6f4", "text2": "#a6adc8",
    "blue": "#89b4fa", "green": "#a6e3a1", "yellow": "#f9e2af",
    "mauve": "#cba6f7", "red": "#f38ba8", "teal": "#94e2d5",
    "border": "#45475a", "orange": "#fab387",
}

def _load_data_root() -> Path:
    """sync_config.json에서 data_root 경로를 로드. 없으면 기본값 반환."""
    try:
        if CONFIG_PATH.exists():
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            p = Path(cfg.get("data_root", ""))
            if p and p.exists():
                return p
    except Exception:
        pass
    return DATA_ROOT

def _save_data_root(path: Path):
    """data_root 경로를 sync_config.json에 저장."""
    try:
        cfg = {}
        if CONFIG_PATH.exists():
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cfg["data_root"] = str(path)
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _init_data_dirs(root: Path):
    """root 아래에 metal/hand × 두 프로토콜 폴더를 생성."""
    for _o in ("metal", "hand"):
        for _p in ("p1_strain_discrete", "p2_proximity_discrete"):
            (root / _o / _p).mkdir(parents=True, exist_ok=True)

# 기본 data 폴더 초기 생성
_init_data_dirs(DATA_ROOT)


def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color:{C['border']};")
    return f

def _lbl(text, bold=False, color=None):
    l = QLabel(text)
    col = color or C["text2"]
    w = "700" if bold else "600"
    l.setStyleSheet(f"color:{col}; font-weight:{w};")
    return l


# ══════════════════════════════════════════════════════════════════════════════
# Arduino 시리얼 스레드
# ══════════════════════════════════════════════════════════════════════════════
class ArduinoReader(QThread):
    pos_updated   = pyqtSignal(dict)   # {XA,XB,YA,YB,Z(steps), lims[6]}
    done_received = pyqtSignal()
    alarm_signal  = pyqtSignal(str)    # "LIMIT" or "CLEARED"
    error_msg     = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser     = None
        self._running = False
        self._cmd_q   = queue.Queue()

    def connect_port(self, port: str, baud: int = BAUD_DEFAULT):
        self._ser = serial.Serial(port, baud, timeout=0.05)
        time.sleep(2.0)
        self._running = True

    def disconnect_port(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()

    def send(self, cmd: str):
        self._cmd_q.put(cmd)

    def run(self):
        buf = ""
        last_q = 0
        while self._running:
            while not self._cmd_q.empty():
                try:
                    c = self._cmd_q.get_nowait()
                    if self._ser and self._ser.is_open:
                        self._ser.write((c + "\n").encode())
                except queue.Empty:
                    break
            if time.time() - last_q > 0.2:
                try:
                    if self._ser and self._ser.is_open:
                        self._ser.write(b"POS?\n")
                except Exception:
                    pass
                last_q = time.time()
            try:
                if self._ser and self._ser.in_waiting:
                    raw = self._ser.read(self._ser.in_waiting).decode("utf-8", errors="ignore")
                    buf += raw
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("POS:"):
                            self._parse_pos(line)
                        elif line == "DONE":
                            self.done_received.emit()
                        elif line == "ALARM:LIMIT":
                            self.alarm_signal.emit("LIMIT")
                        elif line == "ALARM:CLEARED":
                            self.alarm_signal.emit("CLEARED")
                else:
                    time.sleep(0.005)
            except Exception as e:
                self.error_msg.emit(str(e))
                time.sleep(0.05)

    def _parse_pos(self, line: str):
        try:
            p = line.split(":")
            if len(p) >= 12:
                self.pos_updated.emit({
                    "XA": int(p[1]), "XB": int(p[2]),
                    "YA": int(p[3]), "YB": int(p[4]),
                    "Z":  int(p[5]),
                    "lims": [int(p[i]) for i in range(6, 12)],
                })
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# STM32 시리얼 스레드
# ══════════════════════════════════════════════════════════════════════════════
class STM32Reader(QThread):
    data_received = pyqtSignal(float, list)
    error_msg     = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser     = None
        self._running = False

    def connect_port(self, port: str, baud: int = BAUD_DEFAULT):
        self._ser = serial.Serial(port, baud, timeout=0.05)
        time.sleep(0.5)
        self._running = True

    def disconnect_port(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()

    def run(self):
        buf = ""
        while self._running:
            try:
                if self._ser and self._ser.in_waiting:
                    raw = self._ser.read(self._ser.in_waiting).decode("utf-8", errors="ignore")
                    buf += raw
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        vals = self._parse(line)
                        if vals:
                            self.data_received.emit(time.time(), vals)
                else:
                    time.sleep(0.001)
            except Exception as e:
                self.error_msg.emit(str(e))
                time.sleep(0.05)

    @staticmethod
    def _parse(line: str):
        try:
            vals = [float(v.strip()) for v in line.split(",")]
            return vals[:5] if len(vals) >= 5 else None
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# 자동 취득 스레드
# ══════════════════════════════════════════════════════════════════════════════
class AcquisitionRunner(QThread):
    step_started  = pyqtSignal(int, int, str)   # (current, total, desc)
    step_done     = pyqtSignal(str, int)         # (filename, row_count)
    acq_finished  = pyqtSignal()
    acq_aborted   = pyqtSignal()
    log_msg       = pyqtSignal(str)

    def __init__(self, arduino: ArduinoReader):
        super().__init__()
        self._arduino    = arduino
        self._done_evt   = threading.Event()
        self._abort      = False
        self.plan        = []           # list of step dicts
        self.steps_per_mm = 320.0
        self.save_dir    = DATA_ROOT / "metal" / "p1_strain_discrete"
        # MainWindow가 주입: 현재 기록 버퍼 반환 콜백
        self.flush_rows  = None         # () → list[list]
        self.start_rec   = None         # () → None
        self.stop_rec    = None         # () → None
        self.set_sweep_ctx = None       # (ctx dict) → None

    def abort(self):
        self._abort = True
        self._done_evt.set()

    def _on_done(self):
        self._done_evt.set()

    def _wait_done(self, timeout=180):
        self._done_evt.clear()
        self._arduino.done_received.connect(self._on_done)
        ok = self._done_evt.wait(timeout=timeout)
        try:
            self._arduino.done_received.disconnect(self._on_done)
        except Exception:
            pass
        return ok

    def _move(self, axes_mm: dict, speed_mms: float):
        spd = int(speed_mms * self.steps_per_mm)
        cmd = "ABS"
        for ax, mm in axes_mm.items():
            cmd += f":{ax}:{int(mm * self.steps_per_mm)}:{spd}"
        self._arduino.send(cmd)
        return self._wait_done()

    def run(self):
        total = len(self.plan)
        for i, step in enumerate(self.plan):
            if self._abort:
                self.acq_aborted.emit()
                return

            desc = step.get("desc", f"Step {i+1}")
            self.step_started.emit(i + 1, total, desc)
            self.log_msg.emit(f"[{i+1}/{total}] {desc}")

            # 1) 준비 위치로 이동 (기록 없음)
            if "pre_move" in step:
                if self.set_sweep_ctx:
                    self.set_sweep_ctx(None)
                if not self._move(step["pre_move"], step.get("pre_speed", 10.0)):
                    self.log_msg.emit("  준비 이동 타임아웃, 스킵")
                    continue
                time.sleep(0.3)   # settling

            if self._abort:
                self.acq_aborted.emit()
                return

            # 2) 스윕 시작: accel context 설정 → 기록 시작
            ctx = step.get("sweep_ctx")
            if ctx and self.set_sweep_ctx:
                self.set_sweep_ctx(ctx)
            if self.start_rec:
                self.start_rec()

            # 3) 스윕 이동
            if "sweep_move" in step:
                if not self._move(step["sweep_move"], step["sweep_speed"]):
                    self.log_msg.emit("  스윕 타임아웃")

            time.sleep(0.1)

            # 4) 기록 중지 + 파일 저장
            if self.stop_rec:
                self.stop_rec()
            if self.set_sweep_ctx:
                self.set_sweep_ctx(None)

            rows = self.flush_rows() if self.flush_rows else []
            if rows:
                fname = step.get("filename", f"step_{i+1:03d}.csv")
                fpath = self.save_dir / fname
                hdr = ["t_s", "xa_mm", "xb_mm", "ya_mm", "yb_mm", "z_mm",
                       "ldc_raw", "r_raw", "teng_raw", "is_steady"]
                with open(fpath, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(hdr)
                    w.writerows(rows)
                self.step_done.emit(str(fpath), len(rows))
                self.log_msg.emit(f"  → {fpath.name}  ({len(rows)}행)")
            else:
                self.log_msg.emit("  데이터 없음, 파일 미저장")

            # 5) 복귀
            if "return_move" in step:
                self._move(step["return_move"], step.get("return_speed", 10.0))

        if not self._abort:
            self.acq_finished.emit()
        else:
            self.acq_aborted.emit()


# ══════════════════════════════════════════════════════════════════════════════
# 센서 표시 패널 (오른쪽 고정)
# ══════════════════════════════════════════════════════════════════════════════
class SensorPanel(QWidget):
    def __init__(self):
        super().__init__()
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.setSpacing(4)

        vbox.addWidget(_lbl("SENSOR SIGNALS", bold=True))

        # 수치 카드
        self._vals = {}
        for key, label, unit, col in [
            ("dL",   "LDC raw",   "cnt",  C["blue"]),
            ("dR",   "R raw",     "ADC",  C["green"]),
            ("teng", "TENG raw",  "ADC",  C["yellow"]),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}")
            lbl.setStyleSheet(f"color:{C['text2']}; font-size:11px; font-weight:600;")
            lbl.setFixedWidth(110)
            row.addWidget(lbl)
            v = QLabel("—")
            v.setStyleSheet(
                f"color:{col}; font-size:20px; font-weight:700; font-family:Consolas;")
            row.addWidget(v)
            u = QLabel(unit)
            u.setStyleSheet(f"color:{C['text2']}; font-size:11px;")
            row.addWidget(u)
            vbox.addLayout(row)
            self._vals[key] = v

        vbox.addWidget(_hline())

        # 그래프
        pg.setConfigOption("background", C["bg"])
        pg.setConfigOption("foreground", C["text"])
        pw = pg.GraphicsLayoutWidget()
        pw.setMinimumHeight(260)
        specs = [
            ("LDC raw (cnt)",  C["blue"],   "dL"),
            ("R raw (ADC)",    C["green"],  "dR"),
            ("TENG raw (ADC)", C["yellow"], "teng"),
        ]
        self._curves = {}
        self._bufs   = {k: deque(maxlen=MAX_POINTS) for k in ["dL","dR","teng"]}
        self._ts_buf  = deque(maxlen=MAX_POINTS)
        self._t0      = None
        first = None
        for i, (title, col, key) in enumerate(specs):
            p = pw.addPlot(row=i, col=0, title=title)
            p.getAxis("left").setWidth(48)
            p.showGrid(x=False, y=True, alpha=0.15)
            p.titleLabel.setAttr("color", C["text2"])
            p.titleLabel.setAttr("size",  "10pt")
            curve = p.plot(pen=pg.mkPen(col, width=1.6))
            self._curves[key] = curve
            if first is None:
                first = p
            else:
                p.setXLink(first)
            if i < 2:
                p.getAxis("bottom").setStyle(showValues=False)
            else:
                p.setLabel("bottom", "t (s)")
        vbox.addWidget(pw, stretch=1)

        # Hz 표시
        self._lbl_hz = QLabel("— Hz")
        self._lbl_hz.setStyleSheet(
            f"color:{C['teal']}; font-size:12px; font-weight:700; font-family:Consolas;")
        vbox.addWidget(self._lbl_hz)
        self._freq_ts = deque(maxlen=100)

        self.setStyleSheet(f"background:{C['bg2']};")

    def push(self, ts: float, dL: float, dR: float, teng: float):
        if self._t0 is None:
            self._t0 = ts
        t = ts - self._t0
        self._ts_buf.append(t)
        self._bufs["dL"].append(dL)
        self._bufs["dR"].append(dR)
        self._bufs["teng"].append(teng)
        self._freq_ts.append(ts)

    def refresh(self):
        n = len(self._ts_buf)
        if n < 2:
            return
        ts_arr = np.array(self._ts_buf)
        for key, curve in self._curves.items():
            arr = np.array(list(self._bufs[key]))
            if len(arr) == n:
                curve.setData(ts_arr, arr)

        for key, lbl in self._vals.items():
            buf = self._bufs[key]
            lbl.setText(f"{buf[-1]:+.2f}" if buf else "—")

        if len(self._freq_ts) >= 2:
            e = self._freq_ts[-1] - self._freq_ts[0]
            if e > 0:
                self._lbl_hz.setText(f"{(len(self._freq_ts)-1)/e:.1f} Hz")

    def reset_time(self):
        self._t0 = None
        self._ts_buf.clear()
        for b in self._bufs.values():
            b.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 메인 윈도우
# ══════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sync Acquisition — Positioning Stage + Sensor")
        self.resize(1400, 900)

        # --- 데이터 루트 (설정 파일에서 로드) ---
        self._data_root = _load_data_root()
        _init_data_dirs(self._data_root)

        # --- 설정 변수 ---
        self.steps_per_mm   = 320.0    # 200step×8ustep / 5mm
        self.microstep      = 8
        self.screw_pitch    = 5.0
        self.enable_limits  = True
        self.limit_dist_mm  = 100.0
        self.limit_speed_mms = 20.0
        self.jog_small      = 0.1
        self.jog_mid        = 1.0
        self.jog_large      = 5.0
        self.jog_speed_mms  = 5.0

        # --- 통신 ---
        self._ard  = ArduinoReader()
        self._stm  = STM32Reader()
        self._ard_connected = False
        self._stm_connected = False

        # --- 위치 (steps) ---
        self._pos = {ax: 0 for ax in ("XA","XB","YA","YB","Z")}
        self._emg = False
        self._motor_locked = True

        # --- 기록 ---
        self._recording     = False
        self._rec_rows: list = []
        self._latest_pos    = {ax: 0.0 for ax in ("XA","XB","YA","YB","Z")}
        self._t0_rec        = None

        # --- 가감속 컨텍스트 ---
        self._sweep_ctx = None   # None = 태깅 없음

        # --- 시퀀스 ---
        self._seq_data  = []
        self._seq_clip  = []
        self._editing_idx = None
        self._runner    = None

        # --- UI 구성 ---
        self._build_ui()
        self._connect_signals()

        self._ui_timer = QTimer()
        self._ui_timer.timeout.connect(self._refresh)
        self._ui_timer.start(40)

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(4)
        root.setContentsMargins(8, 8, 8, 4)

        root.addWidget(self._build_pos_monitor())
        root.addWidget(self._build_top_bar())
        root.addWidget(_hline())

        splitter = QSplitter(Qt.Horizontal)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabBar::tab{font-size:12px; font-weight:bold; padding:6px 14px;}")
        tabs.addTab(self._build_calib_tab(),  "1. Calibration (Manual)")
        tabs.addTab(self._build_seq_tab(),    "2. Sequence")
        tabs.addTab(self._build_acq_tab(),    "3. Data Acquisition")
        splitter.addWidget(tabs)

        self._sensor_panel = SensorPanel()
        self._sensor_panel.setMinimumWidth(320)
        self._sensor_panel.setMaximumWidth(400)
        splitter.addWidget(self._sensor_panel)
        splitter.setSizes([1000, 360])
        root.addWidget(splitter, stretch=1)

        root.addWidget(_hline())

        # 로그
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(110)
        self._log.setStyleSheet(
            f"background:{C['bg2']}; color:{C['green']}; "
            f"font-family:Consolas; font-size:11px;")
        root.addWidget(self._log)

        sb = QStatusBar()
        sb.setStyleSheet(f"color:{C['text2']}; font-size:11px;")
        self.setStatusBar(sb)
        self._sb = sb

    # ── 위치 모니터 ───────────────────────────────────────────────────────────

    def _build_pos_monitor(self):
        w = QWidget()
        w.setStyleSheet(f"background:#111;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.addWidget(QLabel("POSITION (mm):", styleSheet="color:#fff;font-size:10px;"))
        self._pos_lbls = {}
        for ax in ("XA","XB","YA","YB","Z"):
            lbl = QLabel(f"{ax}: 0.000")
            lbl.setStyleSheet(
                "color:#00ff00; font-family:Consolas; font-size:16px; font-weight:bold;"
                "background:black; padding:2px 8px; border:1px solid #333;")
            lay.addWidget(lbl)
            self._pos_lbls[ax] = lbl
        lay.addStretch()
        # 기록 상태 표시
        self._lbl_rec_badge = QLabel("● REC")
        self._lbl_rec_badge.setStyleSheet(
            f"color:{C['red']}; font-family:Consolas; font-size:14px; font-weight:700;")
        self._lbl_rec_badge.setVisible(False)
        lay.addWidget(self._lbl_rec_badge)
        self._lbl_row_count = QLabel("0행")
        self._lbl_row_count.setStyleSheet(
            f"color:{C['text2']}; font-family:Consolas; font-size:12px;")
        lay.addWidget(self._lbl_row_count)
        return w

    # ── 상단 컨트롤 바 ────────────────────────────────────────────────────────

    def _build_top_bar(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 2, 4, 2)

        # Arduino 포트
        lay.addWidget(_lbl("Arduino:"))
        self._cb_ard = QComboBox(); self._cb_ard.setMinimumWidth(90)
        lay.addWidget(self._cb_ard)
        self._btn_ard = QPushButton("연결")
        self._btn_ard.setFixedSize(60, 28)
        self._btn_ard.clicked.connect(self._toggle_ard)
        lay.addWidget(self._btn_ard)
        self._ind_ard = QLabel("●")
        self._ind_ard.setStyleSheet(f"color:{C['red']}; font-size:14px;")
        lay.addWidget(self._ind_ard)

        lay.addSpacing(8)

        # STM32 포트
        lay.addWidget(_lbl("STM32:"))
        self._cb_stm = QComboBox(); self._cb_stm.setMinimumWidth(90)
        lay.addWidget(self._cb_stm)
        self._btn_stm = QPushButton("연결")
        self._btn_stm.setFixedSize(60, 28)
        self._btn_stm.clicked.connect(self._toggle_stm)
        lay.addWidget(self._btn_stm)
        self._ind_stm = QLabel("●")
        self._ind_stm.setStyleSheet(f"color:{C['red']}; font-size:14px;")
        lay.addWidget(self._ind_stm)

        btn_ref = QPushButton("⟳"); btn_ref.setFixedSize(28, 28)
        btn_ref.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_ref)

        lay.addSpacing(16)

        self._btn_lock = QPushButton("Motor LOCKED")
        self._btn_lock.setFixedHeight(28)
        self._btn_lock.setStyleSheet(
            "background:orange; color:#111; font-weight:700; border-radius:4px;")
        self._btn_lock.clicked.connect(self._toggle_lock)
        lay.addWidget(self._btn_lock)

        self._btn_emg = QPushButton("EMG NORMAL")
        self._btn_emg.setFixedHeight(28)
        self._btn_emg.setStyleSheet(
            "background:#555; color:#fff; font-weight:700; border-radius:4px;")
        self._btn_emg.clicked.connect(self._send_emg_reset)
        lay.addWidget(self._btn_emg)

        btn_set = QPushButton("⚙ Settings")
        btn_set.setFixedHeight(28)
        btn_set.clicked.connect(self._open_settings)
        lay.addWidget(btn_set)

        lay.addStretch()

        # Baud (공통)
        lay.addWidget(_lbl("Baud:"))
        self._cb_baud = QComboBox()
        self._cb_baud.addItems(["9600","115200","230400","460800"])
        self._cb_baud.setCurrentText("115200")
        self._cb_baud.setFixedWidth(80)
        lay.addWidget(self._cb_baud)

        self._refresh_ports()
        return bar

    # ── Calibration 탭 ───────────────────────────────────────────────────────

    def _build_calib_tab(self):
        w = QScrollArea(); w.setWidgetResizable(True)
        inner = QWidget(); vbox = QVBoxLayout(inner)
        vbox.setSpacing(6)

        title = QLabel("Manual Position Adjustment (mm)")
        title.setStyleSheet("font-size:15px; font-weight:bold;")
        title.setAlignment(Qt.AlignCenter)
        vbox.addWidget(title)

        self._jog_btns = {ax: {"in":[], "out":[]} for ax in ("XA","XB","YA","YB","Z")}
        axes = [("XA","XB","YA","YB","Z")]

        for ax in ("XA","XB","YA","YB","Z"):
            grp = QGroupBox(f"Motor {ax}")
            grp.setStyleSheet("QGroupBox{font-weight:bold;}")
            row = QHBoxLayout(grp)

            bm5 = QPushButton("<<<"); bm1 = QPushButton("<<"); bm01 = QPushButton("<")
            bp01= QPushButton(">");  bp1 = QPushButton(">>"); bp5  = QPushButton(">>>")
            for b in (bm5, bm1, bm01, bp01, bp1, bp5):
                b.setFixedSize(54, 36)

            bm5.clicked.connect(lambda _, a=ax: self._jog(a, -self.jog_large))
            bm1.clicked.connect(lambda _, a=ax: self._jog(a, -self.jog_mid))
            bm01.clicked.connect(lambda _, a=ax: self._jog(a, -self.jog_small))
            bp01.clicked.connect(lambda _, a=ax: self._jog(a,  self.jog_small))
            bp1.clicked.connect(lambda _, a=ax: self._jog(a,  self.jog_mid))
            bp5.clicked.connect(lambda _, a=ax: self._jog(a,  self.jog_large))

            for b in (bm5, bm1, bm01): row.addWidget(b)
            row.addWidget(_lbl(" | "))
            for b in (bp01, bp1, bp5): row.addWidget(b)

            self._jog_btns[ax]["in"]  = [bm5, bm1, bm01]
            self._jog_btns[ax]["out"] = [bp01, bp1, bp5]
            vbox.addWidget(grp)

        btn_zero = QPushButton("SET CURRENT POSITION AS ZERO (0.000 mm)")
        btn_zero.setFixedHeight(44)
        btn_zero.setStyleSheet(
            "background:#89b4fa; color:#1e1e2e; font-size:13px; font-weight:700; border-radius:6px;")
        btn_zero.clicked.connect(self._set_zero)
        vbox.addWidget(btn_zero)
        vbox.addStretch()
        w.setWidget(inner)
        return w

    # ── Sequence 탭 ──────────────────────────────────────────────────────────

    def _build_seq_tab(self):
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setSpacing(6)

        # 입력 영역
        self._seq_input_grp = QGroupBox("Add / Edit Sequence Step")
        self._seq_input_grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        self._seq_input_lay = QHBoxLayout(self._seq_input_grp)

        self._seq_mode = QComboBox()
        self._seq_mode.addItems(["1. Symmetric Move","2. Individual Move","3. Delay"])
        self._seq_mode.currentIndexChanged.connect(self._update_seq_input)
        self._seq_input_lay.addWidget(self._seq_mode)

        self._seq_param_w = QWidget()
        self._seq_param_lay = QHBoxLayout(self._seq_param_w)
        self._seq_param_lay.setContentsMargins(0,0,0,0)
        self._seq_input_lay.addWidget(self._seq_param_w, stretch=1)
        vbox.addWidget(self._seq_input_grp)
        self._update_seq_input()

        # 리스트
        list_grp = QGroupBox("Action List")
        list_grp.setStyleSheet("QGroupBox{font-weight:bold; color:green;}")
        list_lay = QHBoxLayout(list_grp)

        self._seq_tree = QTreeWidget()
        self._seq_tree.setHeaderLabels(["#","Type","Parameters"])
        self._seq_tree.setColumnWidth(0, 40)
        self._seq_tree.setColumnWidth(1, 130)
        self._seq_tree.setColumnWidth(2, 600)
        self._seq_tree.itemDoubleClicked.connect(lambda: self._seq_load_edit())
        list_lay.addWidget(self._seq_tree, stretch=1)

        btn_col = QWidget()
        btn_vbox = QVBoxLayout(btn_col)
        for txt, fn in [("EDIT", self._seq_load_edit), ("▲", self._seq_up),
                        ("▼", self._seq_down), ("DEL", self._seq_del),
                        ("CLR", self._seq_clear)]:
            b = QPushButton(txt); b.setFixedWidth(50)
            b.clicked.connect(fn)
            if txt == "DEL": b.setStyleSheet("background:#ffcccc;")
            if txt == "CLR": b.setStyleSheet("background:#f38ba8; color:#1e1e2e;")
            btn_vbox.addWidget(b)
        btn_vbox.addStretch()
        list_lay.addWidget(btn_col)
        vbox.addWidget(list_grp, stretch=1)

        btn_run = QPushButton("▶ RUN SEQUENCE")
        btn_run.setFixedHeight(40)
        btn_run.setStyleSheet(
            "background:#4CAF50; color:white; font-size:14px; font-weight:700; border-radius:5px;")
        btn_run.clicked.connect(self._run_sequence)
        vbox.addWidget(btn_run)
        return w

    def _update_seq_input(self):
        for i in reversed(range(self._seq_param_lay.count())):
            w = self._seq_param_lay.itemAt(i).widget()
            if w: w.deleteLater()

        mode = self._seq_mode.currentText()
        is_edit = self._editing_idx is not None
        btn_txt = "Update" if is_edit else "+ Add"
        btn_bg  = "#89b4fa" if is_edit else "#ddd"

        if is_edit:
            btn_cancel = QPushButton("Cancel")
            btn_cancel.setStyleSheet("background:pink;")
            btn_cancel.clicked.connect(self._seq_cancel_edit)
            self._seq_param_lay.addWidget(btn_cancel)

        if mode.startswith("1."):
            self._e = {}
            for lbl in ("TotX(mm)","TotY(mm)","Z(mm)","Speed(mm/s)"):
                self._seq_param_lay.addWidget(QLabel(lbl))
                e = QLineEdit(); e.setFixedWidth(60)
                self._seq_param_lay.addWidget(e)
                self._e[lbl] = e
            self._e["Speed(mm/s)"].setText("5.0")
            btn = QPushButton(btn_txt)
            btn.setStyleSheet(f"background:{btn_bg}; font-weight:700;")
            btn.clicked.connect(self._seq_add_sym)
            self._seq_param_lay.addWidget(btn)

        elif mode.startswith("2."):
            self._e = {}
            for ax in ("XA","XB","YA","YB","Z"):
                self._seq_param_lay.addWidget(QLabel(ax+":"))
                e = QLineEdit(); e.setFixedWidth(48)
                self._seq_param_lay.addWidget(e)
                self._e[ax] = e
            self._seq_param_lay.addWidget(QLabel("Speed:"))
            e = QLineEdit("5.0"); e.setFixedWidth(48)
            self._seq_param_lay.addWidget(e)
            self._e["spd"] = e
            btn = QPushButton(btn_txt)
            btn.setStyleSheet(f"background:{btn_bg}; font-weight:700;")
            btn.clicked.connect(self._seq_add_indiv)
            self._seq_param_lay.addWidget(btn)

        elif mode.startswith("3."):
            self._seq_param_lay.addWidget(QLabel("Time(ms):"))
            self._e_delay = QLineEdit(); self._e_delay.setFixedWidth(80)
            self._seq_param_lay.addWidget(self._e_delay)
            btn = QPushButton(btn_txt)
            btn.setStyleSheet(f"background:{btn_bg}; font-weight:700;")
            btn.clicked.connect(self._seq_add_delay)
            self._seq_param_lay.addWidget(btn)

        self._seq_param_lay.addStretch()

    def _seq_save_step(self, mode_str, desc, data):
        if self._editing_idx is not None:
            self._seq_data[self._editing_idx] = data
            item = self._seq_tree.topLevelItem(self._editing_idx)
            item.setText(1, mode_str); item.setText(2, desc)
            self._seq_cancel_edit()
        else:
            self._seq_data.append(data)
            n = self._seq_tree.topLevelItemCount() + 1
            self._seq_tree.addTopLevelItem(
                QTreeWidgetItem([str(n), mode_str, desc]))

    def _seq_renumber(self):
        for i in range(self._seq_tree.topLevelItemCount()):
            self._seq_tree.topLevelItem(i).setText(0, str(i+1))

    def _seq_add_sym(self):
        try:
            x  = float(self._e["TotX(mm)"].text() or "0")
            y  = float(self._e["TotY(mm)"].text() or "0")
            z  = float(self._e["Z(mm)"].text() or "0")
            sp = float(self._e["Speed(mm/s)"].text())
            cmds = [("XA",x/2),("XB",x/2),("YA",y/2),("YB",y/2),("Z",z)]
            if not self._check_limits(cmds, sp): return
            desc = f"TotX:{x}mm TotY:{y}mm Z:{z}mm @ {sp}mm/s"
            self._seq_save_step("Symmetric", desc, {"type":"MOVE","cmds_mm":cmds,"spd_mm":sp})
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "숫자를 입력하세요")

    def _seq_add_indiv(self):
        try:
            cmds = []
            sp   = float(self._e["spd"].text())
            for ax in ("XA","XB","YA","YB","Z"):
                t = self._e[ax].text().strip()
                if t: cmds.append((ax, float(t)))
            if not self._check_limits(cmds, sp): return
            desc = ", ".join(f"{a}:{v}" for a,v in cmds) + f"mm @ {sp}mm/s"
            self._seq_save_step("Individual", desc, {"type":"MOVE","cmds_mm":cmds,"spd_mm":sp})
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "숫자를 입력하세요")

    def _seq_add_delay(self):
        try:
            ms = int(self._e_delay.text())
            self._seq_save_step("Delay", f"Wait {ms}ms", {"type":"WAIT","val":ms})
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "정수를 입력하세요")

    def _seq_load_edit(self):
        items = self._seq_tree.selectedItems()
        if not items: return
        idx = self._seq_tree.indexOfTopLevelItem(items[0])
        self._editing_idx = idx
        data = self._seq_data[idx]
        self._seq_input_grp.setTitle(f"EDITING Step #{idx+1}")
        if data["type"] == "WAIT":
            self._seq_mode.setCurrentIndex(2)
            self._update_seq_input()
            self._e_delay.setText(str(data["val"]))
        elif data["type"] == "MOVE":
            cmds = dict(data["cmds_mm"])
            item = items[0]
            if item.text(1) == "Symmetric":
                self._seq_mode.setCurrentIndex(0)
                self._update_seq_input()
                xa = cmds.get("XA",0)
                self._e["TotX(mm)"].setText(str(xa*2))
                ya = cmds.get("YA",0)
                self._e["TotY(mm)"].setText(str(ya*2))
                self._e["Z(mm)"].setText(str(cmds.get("Z",0)))
                self._e["Speed(mm/s)"].setText(str(data["spd_mm"]))
            else:
                self._seq_mode.setCurrentIndex(1)
                self._update_seq_input()
                for ax, v in cmds.items():
                    if ax in self._e: self._e[ax].setText(str(v))
                self._e["spd"].setText(str(data["spd_mm"]))

    def _seq_cancel_edit(self):
        self._editing_idx = None
        self._seq_input_grp.setTitle("Add / Edit Sequence Step")
        self._update_seq_input()

    def _seq_up(self):
        items = self._seq_tree.selectedItems()
        for item in items:
            idx = self._seq_tree.indexOfTopLevelItem(item)
            if idx > 0:
                self._seq_data[idx], self._seq_data[idx-1] = self._seq_data[idx-1], self._seq_data[idx]
                self._seq_tree.takeTopLevelItem(idx)
                self._seq_tree.insertTopLevelItem(idx-1, item)
                self._seq_tree.setCurrentItem(item)
        self._seq_renumber()

    def _seq_down(self):
        items = self._seq_tree.selectedItems()
        for item in reversed(items):
            idx = self._seq_tree.indexOfTopLevelItem(item)
            if idx < self._seq_tree.topLevelItemCount()-1:
                self._seq_data[idx], self._seq_data[idx+1] = self._seq_data[idx+1], self._seq_data[idx]
                self._seq_tree.takeTopLevelItem(idx)
                self._seq_tree.insertTopLevelItem(idx+1, item)
                self._seq_tree.setCurrentItem(item)
        self._seq_renumber()

    def _seq_del(self):
        if self._editing_idx is not None:
            self._seq_cancel_edit()
        for item in reversed(self._seq_tree.selectedItems()):
            idx = self._seq_tree.indexOfTopLevelItem(item)
            del self._seq_data[idx]
            self._seq_tree.takeTopLevelItem(idx)
        self._seq_renumber()

    def _seq_clear(self):
        self._seq_cancel_edit()
        self._seq_data.clear()
        self._seq_tree.clear()

    def _check_limits(self, cmds, spd):
        if not self.enable_limits: return True
        if spd > self.limit_speed_mms:
            QMessageBox.warning(self,"Limit",f"속도 제한({self.limit_speed_mms}mm/s) 초과")
            return False
        for ax, val in cmds:
            if abs(val) > self.limit_dist_mm:
                QMessageBox.warning(self,"Limit",f"{ax} 거리 제한({self.limit_dist_mm}mm) 초과")
                return False
        return True

    # ── Data Acquisition 탭 ──────────────────────────────────────────────────

    def _build_acq_tab(self):
        w = QScrollArea(); w.setWidgetResizable(True)
        inner = QWidget()
        vbox = QVBoxLayout(inner)
        vbox.setSpacing(8)

        # ---- 물체 / 프로토콜 선택 ----
        top = QHBoxLayout()
        obj_grp = QGroupBox("물체 종류")
        obj_lay = QHBoxLayout(obj_grp)
        self._rb_metal = QRadioButton("Metal"); self._rb_metal.setChecked(True)
        self._rb_hand  = QRadioButton("Hand")
        bg = QButtonGroup(self); bg.addButton(self._rb_metal); bg.addButton(self._rb_hand)
        obj_lay.addWidget(self._rb_metal); obj_lay.addWidget(self._rb_hand)
        top.addWidget(obj_grp)

        prot_grp = QGroupBox("프로토콜")
        prot_lay = QHBoxLayout(prot_grp)
        self._rb_p1 = QRadioButton("P1: 변형률 고정 → 근접 스윕"); self._rb_p1.setChecked(True)
        self._rb_p2 = QRadioButton("P2: 근접 고정 → 변형률 스윕")
        bg2 = QButtonGroup(self); bg2.addButton(self._rb_p1); bg2.addButton(self._rb_p2)
        prot_lay.addWidget(self._rb_p1); prot_lay.addWidget(self._rb_p2)
        top.addWidget(prot_grp, stretch=1)
        vbox.addLayout(top)

        # ---- P1 설정 ----
        self._p1_grp = QGroupBox("P1 — 변형률 고정, Z 근접 스윕")
        self._p1_grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        g = QGridLayout(self._p1_grp)

        g.addWidget(QLabel("변형률 레벨 (mm, 쉼표 or 시작:간격:끝):"), 0, 0)
        self._p1_strains = QLineEdit("0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36")
        self._p1_strains.setMinimumWidth(400)
        g.addWidget(self._p1_strains, 0, 1, 1, 3)

        g.addWidget(QLabel("Z 스윕: 시작 (mm)"), 1, 0)
        self._p1_z_start = QDoubleSpinBox(); self._p1_z_start.setRange(-200,200); self._p1_z_start.setValue(52)
        g.addWidget(self._p1_z_start, 1, 1)
        g.addWidget(QLabel("끝 (mm)"), 1, 2)
        self._p1_z_end   = QDoubleSpinBox(); self._p1_z_end.setRange(-200,200); self._p1_z_end.setValue(2)
        g.addWidget(self._p1_z_end, 1, 3)

        g.addWidget(QLabel("스윕 속도 (mm/s)"), 2, 0)
        self._p1_spd = QDoubleSpinBox(); self._p1_spd.setRange(0.1,50); self._p1_spd.setValue(5.0)
        g.addWidget(self._p1_spd, 2, 1)
        g.addWidget(QLabel("반복 횟수"), 2, 2)
        self._p1_reps = QSpinBox(); self._p1_reps.setRange(1,10); self._p1_reps.setValue(1)
        g.addWidget(self._p1_reps, 2, 3)

        g.addWidget(QLabel("복귀 속도 (mm/s)"), 3, 0)
        self._p1_ret_spd = QDoubleSpinBox(); self._p1_ret_spd.setRange(0.1,50); self._p1_ret_spd.setValue(10.0)
        g.addWidget(self._p1_ret_spd, 3, 1)
        vbox.addWidget(self._p1_grp)

        # ---- P2 설정 ----
        self._p2_grp = QGroupBox("P2 — 근접 고정, XA/XB 변형률 스윕")
        self._p2_grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        g2 = QGridLayout(self._p2_grp)

        g2.addWidget(QLabel("근접 레벨 (mm, 쉼표 or 시작:간격:끝):"), 0, 0)
        self._p2_prox = QLineEdit("50,40,30,20,15,10,5,2")
        g2.addWidget(self._p2_prox, 0, 1, 1, 3)

        g2.addWidget(QLabel("XA+XB 변형률 스윕: 시작 (mm/axis)"), 1, 0)
        self._p2_x_start = QDoubleSpinBox(); self._p2_x_start.setRange(0,100); self._p2_x_start.setValue(0)
        g2.addWidget(self._p2_x_start, 1, 1)
        g2.addWidget(QLabel("끝 (mm/axis)"), 1, 2)
        self._p2_x_end   = QDoubleSpinBox(); self._p2_x_end.setRange(0,100); self._p2_x_end.setValue(18)
        g2.addWidget(self._p2_x_end, 1, 3)

        g2.addWidget(QLabel("스윕 속도 (mm/s)"), 2, 0)
        self._p2_spd = QDoubleSpinBox(); self._p2_spd.setRange(0.1,20); self._p2_spd.setValue(2.0)
        g2.addWidget(self._p2_spd, 2, 1)
        g2.addWidget(QLabel("반복 횟수"), 2, 2)
        self._p2_reps = QSpinBox(); self._p2_reps.setRange(1,10); self._p2_reps.setValue(2)
        g2.addWidget(self._p2_reps, 2, 3)

        g2.addWidget(QLabel("복귀 속도 (mm/s)"), 3, 0)
        self._p2_ret_spd = QDoubleSpinBox(); self._p2_ret_spd.setRange(0.1,50); self._p2_ret_spd.setValue(10.0)
        g2.addWidget(self._p2_ret_spd, 3, 1)
        vbox.addWidget(self._p2_grp)

        # ---- 가감속 제외 설정 ----
        accel_grp = QGroupBox("가감속 구간 제외")
        accel_grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        a_lay = QHBoxLayout(accel_grp)
        self._chk_accel = QCheckBox("자동 제외 (firmware accel 기준)")
        self._chk_accel.setChecked(True)
        a_lay.addWidget(self._chk_accel)
        a_lay.addWidget(QLabel("  마진 (mm, 0=자동):"))
        self._accel_margin = QDoubleSpinBox(); self._accel_margin.setRange(0,50); self._accel_margin.setValue(0)
        a_lay.addWidget(self._accel_margin)
        self._lbl_accel_auto = QLabel("")
        self._lbl_accel_auto.setStyleSheet(f"color:{C['teal']}; font-family:Consolas;")
        a_lay.addWidget(self._lbl_accel_auto)
        a_lay.addStretch()
        vbox.addWidget(accel_grp)

        # ---- 저장 위치 ----
        save_grp = QGroupBox("저장 설정")
        save_grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        s_lay = QGridLayout(save_grp)

        # Data Root 행
        s_lay.addWidget(_lbl("Data Root:"), 0, 0)
        self._lbl_data_root = QLabel(str(self._data_root))
        self._lbl_data_root.setStyleSheet(
            f"color:{C['teal']}; font-family:Consolas; font-size:11px;")
        self._lbl_data_root.setWordWrap(True)
        s_lay.addWidget(self._lbl_data_root, 0, 1, 1, 2)
        btn_root = QPushButton("루트 변경")
        btn_root.setStyleSheet(
            f"background:{C['bg3']}; color:{C['teal']}; border:1px solid {C['teal']}; border-radius:4px;")
        btn_root.clicked.connect(self._browse_data_root)
        s_lay.addWidget(btn_root, 0, 3)

        # 서브폴더 행 (자동 결정)
        s_lay.addWidget(_lbl("저장 폴더:"), 1, 0)
        self._lbl_save_dir = QLabel(
            str(self._data_root / "metal" / "p1_strain_discrete"))
        self._lbl_save_dir.setStyleSheet(
            f"color:{C['blue']}; font-family:Consolas; font-size:11px;")
        self._lbl_save_dir.setWordWrap(True)
        s_lay.addWidget(self._lbl_save_dir, 1, 1, 1, 2)
        btn_browse = QPushButton("직접 선택")
        btn_browse.clicked.connect(self._browse_save_dir)
        s_lay.addWidget(btn_browse, 1, 3)

        s_lay.addWidget(QLabel("파일 접두사:"), 2, 0)
        self._e_prefix = QLineEdit("metal_p1")
        s_lay.addWidget(self._e_prefix, 2, 1)
        vbox.addWidget(save_grp)

        # 폴더 자동 업데이트
        self._rb_metal.toggled.connect(self._update_save_dir_auto)
        self._rb_p1.toggled.connect(self._update_save_dir_auto)

        # ---- 실행 버튼 ----
        run_lay = QHBoxLayout()
        self._btn_gen = QPushButton("📋 Preview Plan")
        self._btn_gen.setFixedHeight(36)
        self._btn_gen.setStyleSheet(
            f"background:{C['bg3']}; color:{C['teal']}; font-weight:700; border-radius:5px;")
        self._btn_gen.clicked.connect(self._preview_plan)
        run_lay.addWidget(self._btn_gen)

        self._btn_run_acq = QPushButton("▶ START AUTO-ACQUISITION")
        self._btn_run_acq.setFixedHeight(36)
        self._btn_run_acq.setStyleSheet(
            "background:#4CAF50; color:#fff; font-size:13px; font-weight:700; border-radius:5px;")
        self._btn_run_acq.clicked.connect(self._start_acquisition)
        run_lay.addWidget(self._btn_run_acq)

        self._btn_stop_acq = QPushButton("■ STOP")
        self._btn_stop_acq.setFixedHeight(36)
        self._btn_stop_acq.setStyleSheet(
            "background:#f38ba8; color:#1e1e2e; font-weight:700; border-radius:5px;")
        self._btn_stop_acq.setEnabled(False)
        self._btn_stop_acq.clicked.connect(self._stop_acquisition)
        run_lay.addWidget(self._btn_stop_acq)
        vbox.addLayout(run_lay)

        # 진행 표시
        self._lbl_acq_prog = QLabel("대기 중")
        self._lbl_acq_prog.setStyleSheet(
            f"color:{C['yellow']}; font-family:Consolas; font-size:12px;")
        vbox.addWidget(self._lbl_acq_prog)

        # ---- 수동 기록 ----
        vbox.addWidget(_hline())
        man_grp = QGroupBox("수동 기록")
        man_grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        m_lay = QHBoxLayout(man_grp)
        self._btn_man_rec = QPushButton("● REC")
        self._btn_man_rec.setCheckable(True)
        self._btn_man_rec.setFixedHeight(34)
        self._btn_man_rec.setStyleSheet(
            "QPushButton{background:#f38ba8; color:#1e1e2e; font-weight:700; border-radius:5px;}"
            "QPushButton:checked{background:#a6e3a1; color:#1e1e2e;}")
        self._btn_man_rec.clicked.connect(self._toggle_manual_rec)
        m_lay.addWidget(self._btn_man_rec)
        m_lay.addWidget(_lbl("  파일명:"))
        self._e_man_fname = QLineEdit("manual_001.csv")
        self._e_man_fname.setFixedWidth(180)
        m_lay.addWidget(self._e_man_fname)
        m_lay.addStretch()
        vbox.addWidget(man_grp)

        vbox.addStretch()
        w.setWidget(inner)
        return w

    def _update_save_dir_auto(self):
        obj  = "metal" if self._rb_metal.isChecked() else "hand"
        prot = "p1_strain_discrete" if self._rb_p1.isChecked() else "p2_proximity_discrete"
        d = self._data_root / obj / prot
        self._lbl_save_dir.setText(str(d))
        pre = f"{obj}_{'p1' if self._rb_p1.isChecked() else 'p2'}"
        self._e_prefix.setText(pre)

    def _browse_data_root(self):
        """Data Root 디렉토리 변경 + 서브폴더 자동 생성 + 설정 저장."""
        d = QFileDialog.getExistingDirectory(
            self, "Data Root 폴더 선택", str(self._data_root))
        if not d:
            return
        self._data_root = Path(d)
        _init_data_dirs(self._data_root)
        _save_data_root(self._data_root)
        self._lbl_data_root.setText(str(self._data_root))
        self._update_save_dir_auto()
        self._log_msg(f"Data Root 변경: {self._data_root}")

    def _browse_save_dir(self):
        """저장 폴더 직접 선택 (Data Root와 무관하게 지정)."""
        d = QFileDialog.getExistingDirectory(self, "저장 폴더 선택",
                                             self._lbl_save_dir.text())
        if d:
            self._lbl_save_dir.setText(d)

    # ── 시그널 연결 ──────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._ard.pos_updated.connect(self._on_pos)
        self._ard.done_received.connect(self._on_done)
        self._ard.alarm_signal.connect(self._on_alarm)
        self._ard.error_msg.connect(lambda m: self._log_msg(f"[Arduino 오류] {m}"))
        self._stm.data_received.connect(self._on_sensor)
        self._stm.error_msg.connect(lambda m: self._log_msg(f"[STM32 오류] {m}"))

    # ── 이벤트 핸들러 ─────────────────────────────────────────────────────────

    def _on_pos(self, d: dict):
        for ax in ("XA","XB","YA","YB","Z"):
            self._pos[ax] = d[ax]
            mm = d[ax] / self.steps_per_mm
            self._latest_pos[ax] = mm
            self._pos_lbls[ax].setText(f"{ax}: {mm:.3f}")
        lims = d.get("lims", [1]*6)
        hits = [lims[i] == 0 for i in range(6)]
        self._update_jog_btns("XA", hits[0], hits[1])
        self._update_jog_btns("XB", hits[0], hits[1])
        self._update_jog_btns("YA", hits[2], hits[3])
        self._update_jog_btns("YB", hits[2], hits[3])
        self._update_jog_btns("Z",  hits[4], hits[5])

    def _on_done(self):
        self._log_msg("DONE")

    def _on_alarm(self, kind: str):
        if kind == "LIMIT":
            self._emg = True
            self._btn_emg.setText("EMERGENCY RESET")
            self._btn_emg.setStyleSheet(
                "background:red; color:white; font-weight:700; border-radius:4px;")
            self._log_msg("[ALARM] LIMIT SWITCH HIT!")
        elif kind == "CLEARED":
            self._emg = False
            self._btn_emg.setText("EMG NORMAL")
            self._btn_emg.setStyleSheet(
                "background:#555; color:#fff; font-weight:700; border-radius:4px;")
            self._log_msg("[OK] Limit cleared")

    def _on_sensor(self, ts: float, vals: list):
        ldc, _, _, r_raw, teng_raw = vals

        # 센서 패널: raw 값으로 표시
        self._sensor_panel.push(ts, float(ldc), float(r_raw), float(teng_raw))

        # 기록
        if self._recording:
            if self._t0_rec is None:
                self._t0_rec = ts
            t = ts - self._t0_rec
            p = self._latest_pos
            steady = self._compute_steady(p["Z"])
            self._rec_rows.append([
                round(t, 5),
                round(p["XA"], 4), round(p["XB"], 4),
                round(p["YA"], 4), round(p["YB"], 4),
                round(p["Z"],  4),
                int(ldc), int(r_raw), int(teng_raw),
                1 if steady else 0,
            ])

    def _compute_steady(self, z_mm: float) -> bool:
        ctx = self._sweep_ctx
        if ctx is None or not self._chk_accel.isChecked():
            return True
        d_start = abs(z_mm - ctx["start_mm"])
        d_end   = abs(ctx["end_mm"] - z_mm)
        margin  = ctx["margin_mm"]
        return d_start > margin and d_end > margin

    # ── 화면 갱신 ────────────────────────────────────────────────────────────

    def _refresh(self):
        self._sensor_panel.refresh()
        # 가감속 자동 마진 표시 갱신
        if self._rb_p1.isChecked():
            spd = self._p1_spd.value()
        else:
            spd = self._p2_spd.value()
        accel_mm_s2 = FIRMWARE_ACCEL_STEPS_S2 / self.steps_per_mm
        d_auto = spd**2 / (2 * accel_mm_s2)
        self._lbl_accel_auto.setText(f"(auto: {d_auto:.1f} mm @ {spd}mm/s)")

        # 기록 상태
        self._lbl_rec_badge.setVisible(self._recording)
        self._lbl_row_count.setText(f"{len(self._rec_rows)}행")

    # ── 포트 관리 ────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for cb in (self._cb_ard, self._cb_stm):
            cur = cb.currentText()
            cb.clear()
            cb.addItems(ports)
            if cur in ports:
                cb.setCurrentText(cur)

    def _toggle_ard(self):
        if self._ard_connected:
            self._ard.disconnect_port()
            self._ard.quit(); self._ard.wait(1000)
            self._ard_connected = False
            self._btn_ard.setText("연결")
            self._ind_ard.setStyleSheet(f"color:{C['red']}; font-size:14px;")
            self._log_msg("Arduino 연결 해제")
        else:
            port = self._cb_ard.currentText()
            if not port: return
            try:
                baud = int(self._cb_baud.currentText())
                self._ard.connect_port(port, baud)
                self._ard.start()
                self._ard_connected = True
                self._btn_ard.setText("해제")
                self._ind_ard.setStyleSheet(f"color:{C['green']}; font-size:14px;")
                self._log_msg(f"Arduino 연결: {port}")
            except Exception as e:
                self._log_msg(f"Arduino 연결 실패: {e}")

    def _toggle_stm(self):
        if self._stm_connected:
            self._stm.disconnect_port()
            self._stm.quit(); self._stm.wait(1000)
            self._stm_connected = False
            self._btn_stm.setText("연결")
            self._ind_stm.setStyleSheet(f"color:{C['red']}; font-size:14px;")
            self._log_msg("STM32 연결 해제")
        else:
            port = self._cb_stm.currentText()
            if not port: return
            try:
                baud = int(self._cb_baud.currentText())
                self._stm.connect_port(port, baud)
                self._stm.start()
                self._stm_connected = True
                self._btn_stm.setText("해제")
                self._ind_stm.setStyleSheet(f"color:{C['green']}; font-size:14px;")
                self._log_msg(f"STM32 연결: {port}")
            except Exception as e:
                self._log_msg(f"STM32 연결 실패: {e}")

    # ── 모터 / EMG ───────────────────────────────────────────────────────────

    def _toggle_lock(self):
        if self._motor_locked:
            self._ard.send("EN:0")
            self._motor_locked = False
            self._btn_lock.setText("Motor FREE")
            self._btn_lock.setStyleSheet(
                "background:#f9e2af; color:#111; font-weight:700; border-radius:4px;")
        else:
            self._ard.send("EN:1")
            self._motor_locked = True
            self._btn_lock.setText("Motor LOCKED")
            self._btn_lock.setStyleSheet(
                "background:orange; color:#111; font-weight:700; border-radius:4px;")

    def _send_emg_reset(self):
        self._ard.send("RESET_EMG")
        self._log_msg("EMG Reset 전송. 반대 방향으로 수동 조그 후 복귀하세요.")

    def _set_zero(self):
        self._ard.send("ZERO:0")
        self._log_msg("Zero 설정")

    def _update_jog_btns(self, ax, in_hit, out_hit):
        for b in self._jog_btns[ax]["in"]:
            b.setEnabled(not in_hit)
            b.setStyleSheet("background:#ff8888;" if in_hit else "background:#f0f0f0;")
        for b in self._jog_btns[ax]["out"]:
            b.setEnabled(not out_hit)
            b.setStyleSheet("background:#ff8888;" if out_hit else "background:#f0f0f0;")

    def _jog(self, ax: str, dist_mm: float):
        if not self._motor_locked:
            self._log_msg(f"[JOG 차단] 모터 FREE 상태. LOCK 후 조그하세요.")
            return
        if self.enable_limits and abs(dist_mm) > self.limit_dist_mm:
            QMessageBox.warning(self,"Limit","이동 거리 제한 초과")
            return
        spd = int(self.jog_speed_mms * self.steps_per_mm)
        dist = int(dist_mm * self.steps_per_mm)
        self._ard.send(f"JOG:{ax}:{dist}:{spd}")

    # ── 시퀀스 실행 ──────────────────────────────────────────────────────────

    def _run_sequence(self):
        if self._emg:
            QMessageBox.warning(self,"EMG","리밋 스위치 활성화! 먼저 EMG Reset 하세요.")
            return
        if not self._motor_locked:
            QMessageBox.warning(self,"Lock","모터가 FREE입니다. LOCK 후 실행하세요.")
            return
        if not self._seq_data:
            return
        runner = AcquisitionRunner(self._ard)
        # 시퀀스를 plan으로 변환
        plan = []
        for step in self._seq_data:
            if step["type"] == "WAIT":
                plan.append({"wait_ms": step["val"]})
            elif step["type"] == "MOVE":
                axes_mm = dict(step["cmds_mm"])
                plan.append({"sweep_move": axes_mm, "sweep_speed": step["spd_mm"]})
        runner.plan = plan
        runner.steps_per_mm = self.steps_per_mm
        runner.save_dir = Path(self._lbl_save_dir.text())
        runner.flush_rows = lambda: []    # 시퀀스 탭은 기록 없이 이동만
        runner.start_rec  = lambda: None
        runner.stop_rec   = lambda: None
        runner.set_sweep_ctx = lambda _: None
        runner.log_msg.connect(self._log_msg)
        runner.acq_finished.connect(lambda: self._log_msg(">>> 시퀀스 완료"))
        runner.start()
        self._log_msg(">>> 시퀀스 시작")

    # ── 자동 취득 ────────────────────────────────────────────────────────────

    def _parse_level_str(self, s: str) -> list:
        s = s.strip()
        if ":" in s:
            parts = s.split(":")
            start, step, end = float(parts[0]), float(parts[1]), float(parts[2])
            vals = []
            v = start
            while (step > 0 and v <= end + 1e-9) or (step < 0 and v >= end - 1e-9):
                vals.append(round(v, 4))
                v += step
            return vals
        return [float(x.strip()) for x in s.split(",") if x.strip()]

    def _accel_margin_mm(self, speed_mms: float) -> float:
        user = self._accel_margin.value()
        if user > 0:
            return user
        accel = FIRMWARE_ACCEL_STEPS_S2 / self.steps_per_mm
        return speed_mms**2 / (2 * accel)

    def _preview_plan(self):
        plan = self._build_plan()
        if plan is None:
            return
        msg = f"총 {len(plan)}개 스텝:\n"
        for i, s in enumerate(plan[:8]):
            msg += f"  {i+1}. {s.get('desc','')}\n"
        if len(plan) > 8:
            msg += f"  ... (총 {len(plan)}개)\n"
        msg += f"\n저장 위치: {self._lbl_save_dir.text()}"
        QMessageBox.information(self, "Plan Preview", msg)

    def _build_plan(self):
        save_dir = Path(self._lbl_save_dir.text())
        save_dir.mkdir(parents=True, exist_ok=True)
        prefix = self._e_prefix.text().strip() or "data"
        plan = []

        if self._rb_p1.isChecked():
            # P1: 변형률 고정, Z 스윕
            try:
                strain_levels = self._parse_level_str(self._p1_strains.text())
            except Exception as e:
                QMessageBox.warning(self,"입력 오류", f"변형률 파싱 실패: {e}"); return None
            z_start  = self._p1_z_start.value()
            z_end    = self._p1_z_end.value()
            spd      = self._p1_spd.value()
            reps     = self._p1_reps.value()
            ret_spd  = self._p1_ret_spd.value()
            margin   = self._accel_margin_mm(spd)

            for s_mm in strain_levels:
                xa = s_mm / 2.0   # symmetric: total = 2×XA
                for rep in range(1, reps+1):
                    fname = f"{prefix}_strain{int(s_mm):03d}mm_r{rep:02d}.csv"
                    plan.append({
                        "desc": f"변형률={s_mm}mm  Z: {z_start}→{z_end}mm  rep{rep}",
                        "pre_move":  {"XA": xa, "XB": xa, "Z": z_start},
                        "pre_speed": ret_spd,
                        "sweep_move": {"Z": z_end},
                        "sweep_speed": spd,
                        "sweep_ctx": {
                            "axis": "Z",
                            "start_mm": z_start,
                            "end_mm":   z_end,
                            "margin_mm": margin,
                        },
                        "return_move": {"Z": z_start},
                        "return_speed": ret_spd,
                        "filename": fname,
                    })
        else:
            # P2: 근접 고정, XA+XB 스윕
            try:
                prox_levels = self._parse_level_str(self._p2_prox.text())
            except Exception as e:
                QMessageBox.warning(self,"입력 오류", f"근접 파싱 실패: {e}"); return None
            x_start = self._p2_x_start.value()
            x_end   = self._p2_x_end.value()
            spd     = self._p2_spd.value()
            reps    = self._p2_reps.value()
            ret_spd = self._p2_ret_spd.value()
            margin  = self._accel_margin_mm(spd)

            for z_mm in prox_levels:
                for rep in range(1, reps+1):
                    fname = f"{prefix}_prox{int(z_mm):03d}mm_r{rep:02d}.csv"
                    plan.append({
                        "desc": f"근접Z={z_mm}mm  X: {x_start}→{x_end}mm/axis  rep{rep}",
                        "pre_move":  {"XA": x_start, "XB": x_start, "Z": z_mm},
                        "pre_speed": ret_spd,
                        "sweep_move": {"XA": x_end, "XB": x_end},
                        "sweep_speed": spd,
                        "sweep_ctx": {
                            "axis": "XA",
                            "start_mm": x_start,
                            "end_mm":   x_end,
                            "margin_mm": margin,
                        },
                        "return_move": {"XA": x_start, "XB": x_start},
                        "return_speed": ret_spd,
                        "filename": fname,
                    })

        return plan

    def _start_acquisition(self):
        if self._emg or not self._motor_locked:
            QMessageBox.warning(self,"오류","EMG 또는 모터 FREE 상태")
            return
        if not self._ard_connected:
            QMessageBox.warning(self,"오류","Arduino 미연결"); return

        plan = self._build_plan()
        if plan is None or len(plan) == 0:
            QMessageBox.warning(self,"플랜 오류","스텝 없음"); return

        save_dir = Path(self._lbl_save_dir.text())
        save_dir.mkdir(parents=True, exist_ok=True)

        self._runner = AcquisitionRunner(self._ard)
        self._runner.plan        = plan
        self._runner.steps_per_mm = self.steps_per_mm
        self._runner.save_dir    = save_dir
        self._runner.flush_rows  = self._flush_rec_rows
        self._runner.start_rec   = self._start_rec_internal
        self._runner.stop_rec    = self._stop_rec_internal
        self._runner.set_sweep_ctx = self._set_sweep_ctx

        self._runner.step_started.connect(
            lambda c, t, d: self._lbl_acq_prog.setText(f"Step {c}/{t}: {d}"))
        self._runner.step_done.connect(
            lambda fn, n: self._log_msg(f"저장: {Path(fn).name} ({n}행)"))
        self._runner.log_msg.connect(self._log_msg)
        self._runner.acq_finished.connect(self._on_acq_done)
        self._runner.acq_aborted.connect(lambda: self._log_msg("취득 중단됨"))
        self._runner.acq_aborted.connect(self._on_acq_done)

        self._btn_run_acq.setEnabled(False)
        self._btn_stop_acq.setEnabled(True)
        self._runner.start()
        self._log_msg(f"▶ 자동 취득 시작: {len(plan)}개 스텝")

    def _stop_acquisition(self):
        if self._runner and self._runner.isRunning():
            self._runner.abort()

    def _on_acq_done(self):
        self._btn_run_acq.setEnabled(True)
        self._btn_stop_acq.setEnabled(False)
        self._lbl_acq_prog.setText("완료")

    def _start_rec_internal(self):
        self._rec_rows.clear()
        self._t0_rec = None
        self._recording = True

    def _stop_rec_internal(self):
        self._recording = False

    def _flush_rec_rows(self):
        rows = list(self._rec_rows)
        self._rec_rows.clear()
        return rows

    def _set_sweep_ctx(self, ctx):
        self._sweep_ctx = ctx

    # ── 수동 기록 ────────────────────────────────────────────────────────────

    def _toggle_manual_rec(self, checked: bool):
        if checked:
            self._rec_rows.clear()
            self._t0_rec = None
            self._sweep_ctx = None
            self._recording = True
            self._btn_man_rec.setText("■ STOP")
            self._log_msg("수동 기록 시작")
        else:
            self._recording = False
            self._btn_man_rec.setText("● REC")
            self._log_msg(f"수동 기록 중지 — {len(self._rec_rows)}행")
            self._save_manual_csv()

    def _save_manual_csv(self):
        if not self._rec_rows:
            self._log_msg("저장할 데이터 없음")
            return
        save_dir = Path(self._lbl_save_dir.text())
        save_dir.mkdir(parents=True, exist_ok=True)
        fname = self._e_man_fname.text().strip() or "manual.csv"
        fpath = save_dir / fname
        hdr = ["t_s","xa_mm","xb_mm","ya_mm","yb_mm","z_mm",
               "ldc_raw","r_filtered","teng_filtered","r_raw","teng_raw","is_steady"]
        with open(fpath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(hdr)
            w.writerows(self._rec_rows)
        self._log_msg(f"수동 저장: {fpath}")
        self._rec_rows.clear()

    # ── Settings 창 ──────────────────────────────────────────────────────────

    def _open_settings(self):
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("System Settings")
        dlg.setFixedWidth(380)
        vbox = QVBoxLayout(dlg)

        hw = QGroupBox("Hardware & Comm")
        g = QGridLayout(hw)
        g.addWidget(QLabel("Microstep:"), 0, 0)
        e_ms = QSpinBox(); e_ms.setRange(1,32); e_ms.setValue(self.microstep)
        g.addWidget(e_ms, 0, 1)
        g.addWidget(QLabel("Screw Pitch (mm/rev):"), 1, 0)
        e_sp = QDoubleSpinBox(); e_sp.setRange(0.1,50); e_sp.setValue(self.screw_pitch)
        g.addWidget(e_sp, 1, 1)
        vbox.addWidget(hw)

        lim = QGroupBox("Software Limits")
        g2 = QGridLayout(lim)
        chk = QCheckBox("Enable"); chk.setChecked(self.enable_limits)
        g2.addWidget(chk, 0, 0, 1, 2)
        g2.addWidget(QLabel("Max Distance (mm):"), 1, 0)
        e_ld = QDoubleSpinBox(); e_ld.setRange(1,500); e_ld.setValue(self.limit_dist_mm)
        g2.addWidget(e_ld, 1, 1)
        g2.addWidget(QLabel("Max Speed (mm/s):"), 2, 0)
        e_ls = QDoubleSpinBox(); e_ls.setRange(0.1,200); e_ls.setValue(self.limit_speed_mms)
        g2.addWidget(e_ls, 2, 1)
        vbox.addWidget(lim)

        jog = QGroupBox("Jog Steps (mm)")
        g3 = QGridLayout(jog)
        g3.addWidget(QLabel("Small (<, >):"), 0, 0)
        e_js = QDoubleSpinBox(); e_js.setRange(0.001,100); e_js.setValue(self.jog_small)
        g3.addWidget(e_js, 0, 1)
        g3.addWidget(QLabel("Mid (<<, >>):"), 1, 0)
        e_jm = QDoubleSpinBox(); e_jm.setRange(0.001,100); e_jm.setValue(self.jog_mid)
        g3.addWidget(e_jm, 1, 1)
        g3.addWidget(QLabel("Large (<<<, >>>):"), 2, 0)
        e_jl = QDoubleSpinBox(); e_jl.setRange(0.001,100); e_jl.setValue(self.jog_large)
        g3.addWidget(e_jl, 2, 1)
        g3.addWidget(QLabel("Jog Speed (mm/s):"), 3, 0)
        e_jspd = QDoubleSpinBox(); e_jspd.setRange(0.01,100); e_jspd.setValue(self.jog_speed_mms)
        g3.addWidget(e_jspd, 3, 1)
        vbox.addWidget(jog)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        vbox.addWidget(bb)

        if dlg.exec_() == QDialog.Accepted:
            self.microstep       = e_ms.value()
            self.screw_pitch     = e_sp.value()
            self.steps_per_mm    = (200.0 * self.microstep) / self.screw_pitch
            self.enable_limits   = chk.isChecked()
            self.limit_dist_mm   = e_ld.value()
            self.limit_speed_mms = e_ls.value()
            self.jog_small       = e_js.value()
            self.jog_mid         = e_jm.value()
            self.jog_large       = e_jl.value()
            self.jog_speed_mms   = e_jspd.value()
            self._log_msg(f"설정 변경: steps/mm={self.steps_per_mm:.2f}")

    # ── 로그 / 상태 ──────────────────────────────────────────────────────────

    def _log_msg(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(f"[{ts}] {msg}")

    def _status(self, msg: str):
        self._sb.showMessage(msg)

    def closeEvent(self, event):
        self._ui_timer.stop()
        if self._runner and self._runner.isRunning():
            self._runner.abort()
            self._runner.wait(2000)
        self._ard.disconnect_port(); self._ard.quit(); self._ard.wait(1000)
        self._stm.disconnect_port(); self._stm.quit(); self._stm.wait(1000)
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
