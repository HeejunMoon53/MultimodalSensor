"""
realtime_monitor.py
STM32 실시간 + 2-Stage sklearn MLP 디커플링 + 랜덤 테스트 시퀀스

STM32 포맷:  ldc_raw, r_filt, teng_filt, r_raw, teng_raw  (115200 baud)
Arduino 포맷: ABS:axis:steps:speed → DONE  /  POS? → POS:xa:xb:ya:yb:z:...

proximity 유효범위: d ≤ 15 mm  (이 이상은 OUT 표시, 오차 집계 제외)
"""
import sys, time, csv, threading
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import pickle
import serial
import serial.tools.list_ports

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFileDialog, QSplitter, QStatusBar,
    QFrame, QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QCheckBox, QHeaderView, QAbstractItemView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint
from PyQt5.QtGui import QColor, QPalette, QBrush, QPainter, QPen, QFont, QPolygon

import pyqtgraph as pg

# ─── 경로 ────────────────────────────────────────────────────────────────────
HERE     = Path(__file__).parent
DATA_DIR = HERE / "data_acquisition" / "dataset"

# ─── 상수 ────────────────────────────────────────────────────────────────────
MAX_POINTS    = 600
BAUD_DEFAULT  = 115200
CAL_SAMPLES   = 50
PROX_VALID_MM = 15.0   # proximity 유효 범위 (mm)
TEST_SPEED    = 5.0    # mm/s
D_SMOOTH_A    = 0.4    # d̂ EMA 계수

C = {
    "bg":     "#1e1e2e", "bg2":   "#181825", "bg3":  "#313244",
    "text":   "#cdd6f4", "text2": "#a6adc8",
    "blue":   "#89b4fa", "green": "#a6e3a1", "yellow":"#f9e2af",
    "mauve":  "#cba6f7", "red":   "#f38ba8", "teal": "#94e2d5",
    "peach":  "#fab387", "border":"#45475a",
}


# ══════════════════════════════════════════════════════════════════════════════
# MLPInferencer — 2-Stage sklearn MLP (dR→ε, (dL,ε̂)→d)
# ══════════════════════════════════════════════════════════════════════════════
class MLPInferencer:
    def __init__(self):
        self.ready      = False
        self.load_error = None
        self.L0 = self.R0 = None
        self._s1 = self._s2 = None
        self._sc_dR = self._sc_dL = self._sc_eps = self._sc_d = None
        self._log_d    = False
        self._d_smooth = None
        self._load()

    def _load(self):
        p_sc = DATA_DIR / "scalers_linear.pkl"
        p_s1 = DATA_DIR / "model_stage1_linear.pkl"
        p_s2 = DATA_DIR / "model_stage2_linear.pkl"
        missing = [p.name for p in [p_sc, p_s1, p_s2] if not p.exists()]
        if missing:
            self.load_error = f"파일 없음: {', '.join(missing)} → train_model.py 먼저 실행"
            return
        try:
            with open(p_sc, "rb") as f: s = pickle.load(f)
            with open(p_s1, "rb") as f: self._s1 = pickle.load(f)
            with open(p_s2, "rb") as f: self._s2 = pickle.load(f)
            self._sc_dR  = s["sc_dR"]
            self._sc_dL  = s["sc_dL"]
            self._sc_eps = s["sc_eps"]
            self._sc_d   = s["sc_d"]
            self._log_d  = s.get("log_d", False)
            self.ready   = True
        except Exception as e:
            self.load_error = f"로드 실패: {e}"

    def set_baseline(self, L0: float, R0: float):
        self.L0, self.R0 = L0, R0
        self._d_smooth = None

    def run(self, ldc_raw: float, r_raw: float):
        """Returns (dL_pct, dR_pct, eps_pct, d_mm, d_valid)"""
        if self.L0 is None:
            return 0.0, 0.0, None, None, False
        ldc = float(ldc_raw) if ldc_raw > 0 else float(self.L0)
        dL  = ((self.L0 / ldc) ** 2 - 1.0) * 100.0 if ldc > 0 else 0.0
        dR  = ((r_raw - self.R0) / self.R0) * 100.0 if self.R0 != 0 else 0.0
        if not self.ready:
            return dL, dR, None, None, False
        try:
            dR_n  = self._sc_dR.transform([[dR]])
            eps_n = self._s1.predict(dR_n).reshape(-1, 1)
            eps   = float(np.clip(self._sc_eps.inverse_transform(eps_n)[0, 0], 0, 30))

            dL_n  = self._sc_dL.transform([[dL]])
            d_n   = self._s2.predict(np.hstack([dL_n, eps_n])).reshape(-1, 1)
            d_sc  = self._sc_d.inverse_transform(d_n)[0, 0]
            d_raw = float(np.expm1(d_sc) if self._log_d else d_sc)
            d_raw = float(np.clip(d_raw, 0.0, 50.0))

            if self._d_smooth is None:
                self._d_smooth = d_raw
            self._d_smooth = D_SMOOTH_A * d_raw + (1 - D_SMOOTH_A) * self._d_smooth
            return dL, dR, eps, self._d_smooth, self._d_smooth <= PROX_VALID_MM
        except Exception as e:
            self.load_error = f"추론 오류: {e}"
            return dL, dR, None, None, False


# ══════════════════════════════════════════════════════════════════════════════
# STM32Reader
# ══════════════════════════════════════════════════════════════════════════════
class STM32Reader(QThread):
    data_received = pyqtSignal(float, list)
    error_msg     = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser = None
        self._running = False

    def connect(self, port, baud=BAUD_DEFAULT):
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
                        if not line: continue
                        vals = self._parse(line)
                        if vals:
                            self.data_received.emit(time.time(), vals)
                else:
                    time.sleep(0.001)
            except Exception as e:
                self.error_msg.emit(str(e))
                time.sleep(0.1)

    @staticmethod
    def _parse(line):
        try:
            vals = [float(v.strip()) for v in line.split(",")]
            return vals[:5] if len(vals) >= 5 else None
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# ArduinoController — Tensile Tester 제어 + 위치 읽기
# ══════════════════════════════════════════════════════════════════════════════
class ArduinoController(QThread):
    position_updated = pyqtSignal(dict)
    move_done        = pyqtSignal()
    error_msg        = pyqtSignal(str)

    AXES = ["XA", "XB", "YA", "YB", "Z"]

    def __init__(self):
        super().__init__()
        self._ser      = None
        self._running  = False
        self._lock     = threading.Lock()
        self._pos      = {}
        self._done_evt = threading.Event()
        self._buf      = ""

    def connect(self, port, baud=BAUD_DEFAULT):
        self._ser = serial.Serial(port, baud, timeout=0.1)
        time.sleep(1.0)
        self._running = True

    def disconnect(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()

    @property
    def is_connected(self):
        return self._ser is not None and self._ser.is_open

    def send(self, cmd: str):
        if self.is_connected:
            self._ser.write((cmd + "\n").encode())

    def send_wait_done(self, cmd: str, timeout=60.0) -> bool:
        self._done_evt.clear()
        self.send(cmd)
        return self._done_evt.wait(timeout=timeout)

    def query_pos(self):
        self.send("POS?")

    def zero_all(self):
        self.send("ZERO:0")

    def get_pos(self) -> dict:
        with self._lock:
            return dict(self._pos)

    def run(self):
        last_poll = 0.0
        while self._running:
            try:
                now = time.time()
                if self.is_connected and now - last_poll > 0.15:
                    self.query_pos()
                    last_poll = now
                if self._ser and self._ser.in_waiting:
                    self._buf += self._ser.read(self._ser.in_waiting).decode("utf-8", errors="ignore")
                    while "\n" in self._buf:
                        line, self._buf = self._buf.split("\n", 1)
                        line = line.strip()
                        if not line: continue
                        if line.startswith("POS:"):
                            self._parse_pos(line)
                        elif line == "DONE":
                            self._done_evt.set()
                            self.move_done.emit()
                else:
                    time.sleep(0.005)
            except Exception as e:
                self.error_msg.emit(f"Arduino: {e}")
                time.sleep(0.1)

    def _parse_pos(self, line):
        try:
            parts = line[4:].split(":")
            with self._lock:
                for i, ax in enumerate(self.AXES):
                    if i < len(parts):
                        try:
                            self._pos[ax] = int(parts[i])
                        except ValueError:
                            pass
            self.position_updated.emit(self.get_pos())
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# TestSequenceRunner — 랜덤 시퀀스 (5mm/s, strain/proximity 무작위 이동)
# ══════════════════════════════════════════════════════════════════════════════
def generate_sequence(n_steps=10, max_eps=27.0, max_d=14.0, seed=None):
    """랜덤 (move_type, target_eps%, target_d_mm) 리스트 생성."""
    rng   = np.random.default_rng(seed)
    types = ["both", "strain_only", "prox_only"]
    seq   = []
    cur_eps, cur_d = 0.0, 0.0
    for _ in range(n_steps):
        mt = str(rng.choice(types))
        if mt == "strain_only":
            eps = float(rng.uniform(0, max_eps))
            d   = cur_d
        elif mt == "prox_only":
            eps = cur_eps
            d   = float(rng.uniform(0, max_d))
        else:
            eps = float(rng.uniform(0, max_eps))
            d   = float(rng.uniform(0, max_d))
        seq.append((mt, eps, d))
        cur_eps, cur_d = eps, d
    return seq


class TestSequenceRunner(QThread):
    step_started = pyqtSignal(int, str, float, float)          # idx, type, t_eps, t_d
    step_result  = pyqtSignal(int, float, float, float, float, bool)
    # idx, act_eps, act_d, pred_eps, pred_d, d_valid
    seq_finished = pyqtSignal()
    status_msg   = pyqtSignal(str)

    def __init__(self, arduino: ArduinoController):
        super().__init__()
        self._ard      = arduino
        self._seq      = []
        self._running  = False
        self._get_pred = None   # callback → (eps, d, d_valid) or None

        # 설정값 (MainWindow에서 세팅)
        self.strain_axis      = "XA"
        self.prox_axis        = "YA"
        self.steps_per_mm     = 320
        self.sensor_length_mm = 120.0
        self.sync_xb          = False   # XA 이동 시 XB도 반대 방향 동기

    def set_sequence(self, seq):   self._seq = seq
    def set_pred_cb(self, fn):     self._get_pred = fn
    def stop(self):                self._running = False

    def run(self):
        self._running = True
        spm   = self.steps_per_mm
        speed = int(TEST_SPEED * spm)
        n     = len(self._seq)

        for i, (mt, t_eps, t_d) in enumerate(self._seq):
            if not self._running:
                break

            s_strain = int(t_eps / 100.0 * self.sensor_length_mm * spm)
            s_prox   = int(t_d * spm)

            parts = []
            if mt in ("both", "strain_only"):
                parts += [self.strain_axis, str(s_strain), str(speed)]
                if self.sync_xb and self.strain_axis == "XA":
                    parts += ["XB", str(s_strain), str(speed)]
            if mt in ("both", "prox_only"):
                parts += [self.prox_axis, str(s_prox), str(speed)]

            self.step_started.emit(i, mt, t_eps, t_d)
            self.status_msg.emit(f"[{i+1}/{n}] {mt} → ε={t_eps:.1f}%  d={t_d:.1f}mm ...")

            ok = self._ard.send_wait_done("ABS:" + ":".join(parts), timeout=90.0)
            if not ok:
                self.status_msg.emit(f"  ⚠ 스텝 {i+1} 이동 타임아웃")
                continue

            time.sleep(0.5)   # 정착 대기

            pos     = self._ard.get_pos()
            act_eps = pos.get(self.strain_axis, 0) / spm / self.sensor_length_mm * 100.0
            act_d   = pos.get(self.prox_axis, 0) / spm

            pred_eps, pred_d, d_valid = 0.0, 0.0, False
            if self._get_pred:
                try:
                    pred_eps, pred_d, d_valid = self._get_pred()
                except Exception:
                    pass

            self.step_result.emit(i, act_eps, act_d, pred_eps, pred_d, d_valid)

        self.seq_finished.emit()
        self._running = False


# ══════════════════════════════════════════════════════════════════════════════
# UI 헬퍼
# ══════════════════════════════════════════════════════════════════════════════
def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color:{C['border']};")
    return f

def _lbl(text, color=None, size=11, bold=False, mono=False):
    w = QLabel(text)
    col  = color or C["text2"]
    fam  = "font-family:Consolas;" if mono else ""
    wt   = "font-weight:700;" if bold else ""
    w.setStyleSheet(f"color:{col};font-size:{size}px;{wt}{fam}")
    return w


class ValueCard(QWidget):
    def __init__(self, label, unit, color, fmt="{:.2f}"):
        super().__init__()
        self._fmt   = fmt
        self._color = color
        vb = QVBoxLayout(self)
        vb.setContentsMargins(10, 5, 10, 5)
        vb.setSpacing(1)
        vb.addWidget(_lbl(label, size=10, bold=True))
        row = QHBoxLayout()
        self._val = QLabel("—")
        self._val.setStyleSheet(
            f"color:{color};font-size:24px;font-weight:700;font-family:Consolas;")
        row.addWidget(self._val)
        row.addStretch()
        row.addWidget(_lbl(unit, size=12))
        vb.addLayout(row)
        self.setStyleSheet(
            f"background:{C['bg2']};border:1px solid {C['border']};border-radius:7px;")

    def update(self, val):
        self._val.setText("—" if val is None else self._fmt.format(val))

    def highlight(self, color=None):
        c = color or self._color
        self._val.setStyleSheet(
            f"color:{c};font-size:24px;font-weight:700;font-family:Consolas;")


class PositionGauge(QWidget):
    """현재 위치(채워진 바) + 목표 위치(▼ 마커) + 임계값(점선) 시각화."""

    def __init__(self, label: str, unit: str,
                 min_val: float, max_val: float,
                 bar_color: str,
                 threshold: float = None,
                 th_color: str = "#f9e2af"):
        super().__init__()
        self._label   = label
        self._unit    = unit
        self._min     = float(min_val)
        self._max     = float(max_val)
        self._val     = None    # 실제 위치 (Arduino)
        self._target  = None   # 목표 위치 (시퀀스 중)
        self._bar_col = QColor(bar_color)
        self._thr     = threshold
        self._th_col  = QColor(th_color)
        self.setFixedHeight(64)
        self.setMinimumWidth(160)
        self.setStyleSheet(
            f"background:{C['bg2']};border:1px solid {C['border']};border-radius:7px;")

    def set_value(self, val):
        self._val = float(val) if val is not None else None
        self.update()

    def set_target(self, target):
        self._target = float(target) if target is not None else None
        self.update()

    def clear_target(self):
        self._target = None
        self.update()

    def _ratio(self, v: float) -> float:
        return max(0.0, min(1.0, (v - self._min) / (self._max - self._min)))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        W      = self.width()
        px     = 10          # horizontal padding
        bar_y  = 30          # bar top
        bar_h  = 16          # bar height
        bar_w  = W - px * 2

        # ── 레이블 ──────────────────────────────────────────────
        p.setPen(QColor(C["text2"]))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(px, 14, self._label)

        # ── 숫자 값 (우측 정렬) ──────────────────────────────────
        val_text = f"{self._val:.1f} {self._unit}" if self._val is not None else "—"
        p.setPen(QColor(C["text"]))
        p.setFont(QFont("Consolas", 11, QFont.Bold))
        fm = p.fontMetrics()
        p.drawText(W - px - fm.horizontalAdvance(val_text), 14, val_text)

        # ── 바 배경 ──────────────────────────────────────────────
        p.setPen(QColor(C["border"]))
        p.setBrush(QColor(C["bg3"]))
        p.drawRoundedRect(px, bar_y, bar_w, bar_h, 3, 3)

        # ── 채움 (threshold 초과 시 빨간색) ─────────────────────
        if self._val is not None:
            if self._thr is not None and self._val > self._thr:
                # 0 ~ threshold: 정상 색
                thr_w = int(bar_w * self._ratio(self._thr))
                if thr_w > 0:
                    p.setPen(Qt.NoPen)
                    p.setBrush(self._bar_col)
                    p.drawRoundedRect(px, bar_y, thr_w, bar_h, 3, 3)
                # threshold ~ val: 빨간색
                val_w = int(bar_w * self._ratio(self._val))
                if val_w > thr_w:
                    p.setBrush(QColor(C["red"]))
                    p.drawRect(px + thr_w, bar_y, val_w - thr_w, bar_h)
            else:
                val_w = int(bar_w * self._ratio(self._val))
                if val_w > 0:
                    p.setPen(Qt.NoPen)
                    p.setBrush(self._bar_col)
                    p.drawRoundedRect(px, bar_y, val_w, bar_h, 3, 3)

        # ── 임계값 점선 ──────────────────────────────────────────
        if self._thr is not None:
            tx = px + int(bar_w * self._ratio(self._thr))
            p.setPen(QPen(self._th_col, 2, Qt.DashLine))
            p.drawLine(tx, bar_y - 4, tx, bar_y + bar_h + 4)

        # ── 목표 마커 ▼ ──────────────────────────────────────────
        if self._target is not None:
            mx = px + int(bar_w * self._ratio(self._target))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["blue"]))
            tri = QPolygon([
                QPoint(mx - 5, bar_y - 7),
                QPoint(mx + 5, bar_y - 7),
                QPoint(mx,     bar_y - 1),
            ])
            p.drawPolygon(tri)
            # 마커 수직선
            p.setPen(QPen(QColor(C["blue"]), 1, Qt.DotLine))
            p.drawLine(mx, bar_y, mx, bar_y + bar_h)

        # ── min / max 레이블 ─────────────────────────────────────
        p.setPen(QColor(C["text2"]))
        p.setFont(QFont("Consolas", 7))
        p.drawText(px, bar_y + bar_h + 11, f"{self._min:.0f}")
        max_txt = f"{self._max:.0f}{self._unit}"
        fm2 = p.fontMetrics()
        p.drawText(W - px - fm2.horizontalAdvance(max_txt),
                   bar_y + bar_h + 11, max_txt)

        p.end()


# ══════════════════════════════════════════════════════════════════════════════
# MainWindow
# ══════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("2-Stage MLP Monitor — Real-time Decoupler")
        self.resize(1500, 920)

        self._infer   = MLPInferencer()
        self._reader  = STM32Reader()
        self._arduino = ArduinoController()
        self._seq_runner = TestSequenceRunner(self._arduino)
        self._seq_runner.set_pred_cb(self._get_latest_pred)

        # 데이터 버퍼
        self._t0      = None
        self._ts      = deque(maxlen=MAX_POINTS)
        self._bufs    = {k: deque(maxlen=MAX_POINTS)
                         for k in ["dL", "dR", "eps", "d"]}
        self._cal_ldc = deque(maxlen=CAL_SAMPLES)
        self._cal_r   = deque(maxlen=CAL_SAMPLES)
        self._freq_ts = deque(maxlen=100)

        # 최신 예측값
        self._last_pred = (None, None, False)   # (eps, d, d_valid)

        # 실제 위치 (Arduino)
        self._act_eps = None
        self._act_d   = None

        # 오차 누적 (테스트 시퀀스)
        self._err_eps_list = []
        self._err_d_list   = []   # d_valid인 것만

        # 녹화
        self._recording = False
        self._rec_rows  = []
        self._save_dir  = str(Path.home())

        self._build_ui()
        self._connect_signals()

        self._ui_timer = QTimer()
        self._ui_timer.timeout.connect(self._refresh_ui)
        self._ui_timer.start(40)

    # ── UI 구성 ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        pg.setConfigOption("background", C["bg"])
        pg.setConfigOption("foreground", C["text"])

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(5)
        root.setContentsMargins(8, 8, 8, 5)

        root.addWidget(self._build_top_bar())
        root.addWidget(_hline())

        mid = QSplitter(Qt.Horizontal)
        mid.addWidget(self._build_left_panel())
        mid.addWidget(self._build_right_panel())
        mid.setSizes([340, 1160])
        root.addWidget(mid, stretch=1)

        root.addWidget(_hline())
        root.addWidget(self._build_seq_panel())
        root.addWidget(_hline())
        root.addWidget(self._build_record_bar())

        sb = QStatusBar()
        sb.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        self.setStatusBar(sb)
        self._sb = sb
        self._status("STM32 미연결")

    # ── 상단 바 ───────────────────────────────────────────────────────────────

    def _build_top_bar(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0)

        # STM32
        lay.addWidget(_lbl("STM32"))
        self._cb_port = QComboBox(); self._cb_port.setMinimumWidth(90)
        lay.addWidget(self._cb_port)
        lay.addWidget(_lbl("Baud"))
        self._cb_baud = QComboBox()
        self._cb_baud.addItems(["115200", "230400", "460800"])
        lay.addWidget(self._cb_baud)
        self._btn_con = QPushButton("연결")
        self._btn_con.setFixedSize(64, 30)
        self._btn_con.clicked.connect(self._toggle_stm32)
        lay.addWidget(self._btn_con)
        self._ind_stm = QLabel("●")
        self._ind_stm.setStyleSheet(f"color:{C['red']};font-size:16px;")
        lay.addWidget(self._ind_stm)
        btn_ref = QPushButton("⟳")
        btn_ref.setFixedSize(28, 28)
        btn_ref.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_ref)

        lay.addSpacing(16)

        # Arduino
        lay.addWidget(_lbl("Arduino", bold=True))
        self._cb_ard_port = QComboBox(); self._cb_ard_port.setMinimumWidth(90)
        lay.addWidget(self._cb_ard_port)
        self._btn_ard_con = QPushButton("연결")
        self._btn_ard_con.setFixedSize(64, 30)
        self._btn_ard_con.clicked.connect(self._toggle_arduino)
        lay.addWidget(self._btn_ard_con)
        self._ind_ard = QLabel("●")
        self._ind_ard.setStyleSheet(f"color:{C['red']};font-size:16px;")
        lay.addWidget(self._ind_ard)

        btn_zero = QPushButton("ZERO")
        btn_zero.setFixedSize(58, 28)
        btn_zero.setStyleSheet(
            f"background:{C['bg3']};color:{C['yellow']};"
            f"border:1px solid {C['yellow']};border-radius:4px;font-weight:700;")
        btn_zero.clicked.connect(lambda: self._arduino.zero_all())
        btn_zero.setToolTip("Arduino 전 축 원점 리셋 (ZERO:0)")
        lay.addWidget(btn_zero)

        lay.addSpacing(16)

        # Calibrate
        btn_cal = QPushButton("Calibrate (Re-baseline)")
        btn_cal.setFixedHeight(30)
        btn_cal.setStyleSheet(
            f"background:{C['bg3']};color:{C['teal']};"
            f"border:1px solid {C['teal']};border-radius:5px;font-weight:700;")
        btn_cal.clicked.connect(self._calibrate)
        lay.addWidget(btn_cal)

        lay.addSpacing(8)
        self._lbl_baseline = _lbl("baseline: —", mono=True)
        lay.addWidget(self._lbl_baseline)

        lay.addStretch()

        # 모델 상태
        self._lbl_model = _lbl("", size=11)
        self._refresh_model_label()
        lay.addWidget(self._lbl_model)

        lay.addSpacing(12)
        self._lbl_hz = _lbl("— Hz", C["teal"], size=13, bold=True, mono=True)
        lay.addWidget(self._lbl_hz)

        self._refresh_ports()
        return bar

    # ── 좌측 패널 ─────────────────────────────────────────────────────────────

    def _build_left_panel(self):
        w = QWidget()
        vb = QVBoxLayout(w)
        vb.setSpacing(6)
        vb.setContentsMargins(4, 4, 4, 4)

        def sec(text):
            l = _lbl(text, size=9, bold=True)
            l.setStyleSheet(
                f"color:{C['text2']};font-size:9px;font-weight:700;"
                f"letter-spacing:2px;margin-top:6px;")
            return l

        # RAW INPUTS
        vb.addWidget(sec("RAW INPUTS"))
        self._c_dL = ValueCard("ΔL / L₀",   "%",   C["blue"],  "{:+.3f}")
        self._c_dR = ValueCard("ΔR / R₀",   "%",   C["green"], "{:+.3f}")
        vb.addWidget(self._c_dL)
        vb.addWidget(self._c_dR)

        vb.addWidget(_hline())
        vb.addWidget(sec("PREDICTED  (2-Stage MLP)"))
        self._c_eps = ValueCard("Strain  ε",   "%",  C["mauve"], "{:.2f}")
        self._c_d   = ValueCard("Proximity d", "mm", C["red"],   "{:.1f}")
        vb.addWidget(self._c_eps)
        vb.addWidget(self._c_d)

        # proximity 유효 배지
        self._lbl_valid = QLabel("d VALID  (≤ 15 mm)")
        self._lbl_valid.setAlignment(Qt.AlignCenter)
        self._lbl_valid.setFixedHeight(24)
        self._lbl_valid.setStyleSheet(
            f"color:{C['text2']};font-size:11px;font-weight:600;"
            f"background:{C['bg3']};border:1px solid {C['border']};border-radius:5px;")
        vb.addWidget(self._lbl_valid)

        vb.addWidget(_hline())
        vb.addWidget(sec("POSITION  (Arduino 실제 위치)"))

        self._g_eps = PositionGauge(
            "Strain  ε", "%", 0, 30, C["yellow"], threshold=None)
        self._g_d = PositionGauge(
            "Proximity  d", "mm", 0, 36, C["peach"],
            threshold=PROX_VALID_MM, th_color=C["yellow"])
        vb.addWidget(self._g_eps)
        vb.addWidget(self._g_d)

        # 목표 위치 범례
        legend = QHBoxLayout()
        for col, txt in [(C["yellow"], "▌ 실제"), (C["blue"], "▼ 목표"),
                         (C["yellow"], "⋯ 유효한계")]:
            l = _lbl(txt, col, size=9)
            legend.addWidget(l)
        legend.addStretch()
        vb.addLayout(legend)

        vb.addWidget(_hline())
        vb.addWidget(sec("LIVE ERROR"))
        self._c_err_eps = ValueCard("Δε  (pred−act)",  "%",  C["red"],   "{:+.2f}")
        self._c_err_d   = ValueCard("Δd  (pred−act)",  "mm", C["red"],   "{:+.2f}")
        vb.addWidget(self._c_err_eps)
        vb.addWidget(self._c_err_d)

        vb.addStretch()
        return w

    # ── 우측 그래프 패널 ───────────────────────────────────────────────────────

    def _build_right_panel(self):
        pw = pg.GraphicsLayoutWidget()
        specs = [
            ("ΔL/L₀ (%)",        C["blue"],  "dL"),
            ("ΔR/R₀ (%)",        C["green"], "dR"),
            ("Strain  ε  (%)",   C["mauve"], "eps"),
            ("Proximity  d (mm)",C["red"],   "d"),
        ]
        self._plots  = {}
        self._curves = {}
        self._act_curves = {}
        first = None
        for i, (title, color, key) in enumerate(specs):
            p = pw.addPlot(row=i, col=0, title=title)
            p.getAxis("left").setWidth(54)
            p.showGrid(x=False, y=True, alpha=0.15)
            p.titleLabel.setAttr("color", C["text2"])
            p.titleLabel.setAttr("size",  "10pt")
            curve = p.plot(pen=pg.mkPen(color, width=1.8))
            self._plots[key]  = p
            self._curves[key] = curve
            if first is None:
                first = p
            else:
                p.setXLink(first)
            if i < len(specs) - 1:
                p.getAxis("bottom").setStyle(showValues=False)
            else:
                p.setLabel("bottom", "시간 (s)")

        self._plots["eps"].setYRange(0, 30, padding=0.05)
        self._plots["d"].setYRange(0, 20, padding=0.05)

        # d 그래프: actual 오버레이 + 유효범위 라인
        p_d = self._plots["d"]
        self._act_curves["eps"] = self._plots["eps"].plot(
            pen=pg.mkPen(C["yellow"], width=1.2, style=Qt.DashLine))
        self._act_curves["d"] = p_d.plot(
            pen=pg.mkPen(C["peach"], width=1.2, style=Qt.DashLine))
        p_d.addItem(pg.InfiniteLine(
            pos=PROX_VALID_MM, angle=0,
            pen=pg.mkPen(C["yellow"], width=1, style=Qt.DashLine),
            label=f"Valid ≤ {PROX_VALID_MM}mm",
            labelOpts={"color": C["yellow"], "position": 0.95}))

        return pw

    # ── 테스트 시퀀스 패널 ────────────────────────────────────────────────────

    def _build_seq_panel(self):
        w = QWidget()
        w.setStyleSheet(f"background:{C['bg2']};")
        h = QHBoxLayout(w)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(12)

        # ─ 축 설정 ─
        box_ax = QWidget()
        box_ax.setStyleSheet(
            f"background:{C['bg3']};border:1px solid {C['border']};border-radius:6px;")
        vb = QVBoxLayout(box_ax)
        vb.setContentsMargins(8, 4, 8, 4)
        vb.setSpacing(3)
        vb.addWidget(_lbl("AXIS CONFIG", size=9, bold=True))

        def ax_row(label, default, attr):
            r = QHBoxLayout()
            r.addWidget(_lbl(label, size=10))
            cb = QComboBox()
            cb.addItems(["XA", "XB", "YA", "YB", "Z"])
            cb.setCurrentText(default)
            cb.setFixedWidth(60)
            cb.currentTextChanged.connect(lambda v, a=attr: setattr(self._seq_runner, a, v))
            r.addWidget(cb)
            vb.addLayout(r)
            return cb

        self._cb_strain_ax = ax_row("Strain 축", "XA", "strain_axis")
        self._cb_prox_ax   = ax_row("Prox 축",   "YA", "prox_axis")

        r = QHBoxLayout()
        r.addWidget(_lbl("steps/mm", size=10))
        sp_spm = QSpinBox(); sp_spm.setRange(1, 9999); sp_spm.setValue(320); sp_spm.setFixedWidth(70)
        sp_spm.valueChanged.connect(lambda v: setattr(self._seq_runner, "steps_per_mm", v))
        r.addWidget(sp_spm)
        vb.addLayout(r)

        r2 = QHBoxLayout()
        r2.addWidget(_lbl("길이 mm", size=10))
        sp_sl = QDoubleSpinBox(); sp_sl.setRange(10, 500); sp_sl.setValue(120); sp_sl.setFixedWidth(70)
        sp_sl.valueChanged.connect(lambda v: setattr(self._seq_runner, "sensor_length_mm", v))
        r2.addWidget(sp_sl)
        vb.addLayout(r2)

        chk_xb = QCheckBox("XB 동기")
        chk_xb.stateChanged.connect(
            lambda s: setattr(self._seq_runner, "sync_xb", bool(s)))
        vb.addWidget(chk_xb)
        h.addWidget(box_ax)

        # ─ 시퀀스 제어 ─
        box_ctrl = QWidget()
        box_ctrl.setStyleSheet(
            f"background:{C['bg3']};border:1px solid {C['border']};border-radius:6px;")
        vb2 = QVBoxLayout(box_ctrl)
        vb2.setContentsMargins(8, 4, 8, 4)
        vb2.setSpacing(4)
        vb2.addWidget(_lbl("TEST SEQUENCE", size=9, bold=True))

        r3 = QHBoxLayout()
        r3.addWidget(_lbl("스텝 수", size=10))
        self._sp_nsteps = QSpinBox()
        self._sp_nsteps.setRange(1, 50); self._sp_nsteps.setValue(10); self._sp_nsteps.setFixedWidth(60)
        r3.addWidget(self._sp_nsteps)
        r3.addSpacing(8)
        r3.addWidget(_lbl("속도 5mm/s (고정)", size=10))
        vb2.addLayout(r3)

        r4 = QHBoxLayout()
        self._btn_start = QPushButton("▶  START")
        self._btn_start.setFixedHeight(32)
        self._btn_start.setStyleSheet(
            f"background:{C['green']};color:{C['bg']};font-weight:700;"
            f"font-size:13px;border-radius:5px;")
        self._btn_start.clicked.connect(self._start_sequence)
        r4.addWidget(self._btn_start)

        self._btn_stop = QPushButton("■  STOP")
        self._btn_stop.setFixedHeight(32)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setStyleSheet(
            f"background:{C['red']};color:{C['bg']};font-weight:700;"
            f"font-size:13px;border-radius:5px;")
        self._btn_stop.clicked.connect(self._stop_sequence)
        r4.addWidget(self._btn_stop)
        vb2.addLayout(r4)

        self._progress = QProgressBar()
        self._progress.setRange(0, 10)
        self._progress.setValue(0)
        self._progress.setFixedHeight(14)
        self._progress.setTextVisible(False)
        vb2.addWidget(self._progress)

        self._lbl_seq_status = _lbl("준비", size=10, mono=True)
        self._lbl_seq_status.setWordWrap(True)
        vb2.addWidget(self._lbl_seq_status)

        h.addWidget(box_ctrl)

        # ─ 오차 통계 ─
        box_stat = QWidget()
        box_stat.setStyleSheet(
            f"background:{C['bg3']};border:1px solid {C['border']};border-radius:6px;")
        vb3 = QVBoxLayout(box_stat)
        vb3.setContentsMargins(8, 4, 8, 4)
        vb3.setSpacing(3)
        vb3.addWidget(_lbl("ERROR STATS", size=9, bold=True))

        self._lbl_mae_eps = _lbl("MAE ε :  — %",  C["mauve"], size=12, mono=True)
        self._lbl_mae_d   = _lbl("MAE d :  — mm (valid)", C["peach"], size=12, mono=True)
        self._lbl_n_valid = _lbl("Valid steps : —", size=11, mono=True)
        vb3.addWidget(self._lbl_mae_eps)
        vb3.addWidget(self._lbl_mae_d)
        vb3.addWidget(self._lbl_n_valid)

        btn_clear = QPushButton("Clear")
        btn_clear.setFixedSize(60, 24)
        btn_clear.clicked.connect(self._clear_stats)
        vb3.addWidget(btn_clear)
        h.addWidget(box_stat)

        # ─ 결과 테이블 ─
        self._tbl = QTableWidget(0, 10)
        self._tbl.setHorizontalHeaderLabels([
            "#", "Type", "T-ε%", "T-d", "Act-ε%", "Act-d",
            "Pred-ε%", "Pred-d", "Δε", "Δd(valid)"
        ])
        self._tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setFixedHeight(120)
        self._tbl.setStyleSheet(
            f"background:{C['bg2']};color:{C['text']};font-size:11px;"
            f"gridline-color:{C['border']};")
        h.addWidget(self._tbl, stretch=1)

        return w

    # ── 녹화 바 ───────────────────────────────────────────────────────────────

    def _build_record_bar(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0)
        self._btn_rec = QPushButton("● RECORD")
        self._btn_rec.setFixedSize(130, 32)
        self._btn_rec.setCheckable(True)
        self._btn_rec.setStyleSheet(
            "QPushButton{background:#f38ba8;color:#1e1e2e;font-weight:700;"
            "font-size:13px;border-radius:5px;}"
            "QPushButton:checked{background:#a6e3a1;color:#1e1e2e;}")
        self._btn_rec.clicked.connect(self._toggle_record)
        lay.addWidget(self._btn_rec)
        lay.addSpacing(10)
        lay.addWidget(_lbl("저장 폴더:"))
        self._lbl_dir = _lbl(self._save_dir, C["blue"])
        lay.addWidget(self._lbl_dir, stretch=1)
        btn_br = QPushButton("폴더 선택")
        btn_br.setFixedHeight(28)
        btn_br.clicked.connect(self._browse_dir)
        lay.addWidget(btn_br)
        lay.addSpacing(8)
        self._lbl_rc = _lbl("0행", mono=True)
        lay.addWidget(self._lbl_rc)
        return bar

    # ── 시그널 연결 ───────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._reader.data_received.connect(self._on_stm32_data)
        self._reader.error_msg.connect(lambda m: self._status(f"STM32 오류: {m}"))
        self._arduino.position_updated.connect(self._on_pos)
        self._arduino.error_msg.connect(lambda m: self._status(m))
        self._arduino.move_done.connect(lambda: self._status("이동 완료"))
        self._seq_runner.step_started.connect(self._on_step_started)
        self._seq_runner.step_result.connect(self._on_step_result)
        self._seq_runner.seq_finished.connect(self._on_seq_finished)
        self._seq_runner.status_msg.connect(self._status)

    # ── 데이터 수신 ───────────────────────────────────────────────────────────

    def _on_stm32_data(self, ts: float, vals: list):
        ldc  = vals[0]
        r    = vals[3]
        self._cal_ldc.append(ldc)
        self._cal_r.append(r)

        dL, dR, eps, d, d_valid = self._infer.run(ldc, r)
        self._last_pred = (eps, d, d_valid)

        if self._t0 is None:
            self._t0 = ts
        t = ts - self._t0
        self._ts.append(t)
        self._bufs["dL"].append(dL)
        self._bufs["dR"].append(dR)
        self._bufs["eps"].append(eps)
        self._bufs["d"].append(d)
        self._freq_ts.append(ts)

        if self._recording:
            self._rec_rows.append([
                round(t, 4), ldc, r,
                round(dL, 4), round(dR, 4),
                round(eps, 4) if eps is not None else "",
                round(d, 2)   if d   is not None else "",
                1 if d_valid else 0,
                round(self._act_eps, 4) if self._act_eps is not None else "",
                round(self._act_d,   2) if self._act_d   is not None else "",
            ])
            self._lbl_rc.setText(f"{len(self._rec_rows)}행")

    def _on_pos(self, pos: dict):
        spm  = self._seq_runner.steps_per_mm
        sl   = self._seq_runner.sensor_length_mm
        s_ax = self._seq_runner.strain_axis
        p_ax = self._seq_runner.prox_axis
        self._act_eps = pos.get(s_ax, 0) / spm / sl * 100.0
        self._act_d   = pos.get(p_ax, 0) / spm
        self._g_eps.set_value(self._act_eps)
        self._g_d.set_value(self._act_d)

    # ── UI 갱신 ───────────────────────────────────────────────────────────────

    def _refresh_ui(self):
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

        # 실제 위치 오버레이 (일정 길이 수평선)
        if self._act_eps is not None:
            self._act_curves["eps"].setData(
                [ts_arr[0], ts_arr[-1]], [self._act_eps, self._act_eps])
        if self._act_d is not None:
            self._act_curves["d"].setData(
                [ts_arr[0], ts_arr[-1]], [self._act_d, self._act_d])

        # 값 카드
        eps, d, d_valid = self._last_pred
        self._c_dL.update(self._bufs["dL"][-1] if self._bufs["dL"] else None)
        self._c_dR.update(self._bufs["dR"][-1] if self._bufs["dR"] else None)
        self._c_eps.update(eps)
        self._c_d.update(d)

        # validity 배지
        if d is not None:
            if d_valid:
                self._lbl_valid.setText(f"✓  d VALID  ({d:.1f} ≤ {PROX_VALID_MM}mm)")
                self._lbl_valid.setStyleSheet(
                    f"color:{C['bg']};font-size:11px;font-weight:700;"
                    f"background:{C['green']};border:1px solid {C['green']};border-radius:5px;")
            else:
                self._lbl_valid.setText(f"✗  OUT OF RANGE  ({d:.1f}mm > {PROX_VALID_MM}mm)")
                self._lbl_valid.setStyleSheet(
                    f"color:{C['text2']};font-size:11px;font-weight:600;"
                    f"background:{C['bg3']};border:1px solid {C['border']};border-radius:5px;")

        # 실시간 오차
        if eps is not None and self._act_eps is not None:
            self._c_err_eps.update(eps - self._act_eps)
        else:
            self._c_err_eps.update(None)

        if d is not None and self._act_d is not None and d_valid:
            self._c_err_d.update(d - self._act_d)
            self._c_err_d.highlight(C["red"])
        else:
            self._c_err_d.update(None)
            self._c_err_d.highlight(C["text2"])

        # Hz
        if len(self._freq_ts) >= 2:
            el = self._freq_ts[-1] - self._freq_ts[0]
            if el > 0:
                self._lbl_hz.setText(f"{(len(self._freq_ts)-1)/el:.1f} Hz")

    # ── 테스트 시퀀스 ─────────────────────────────────────────────────────────

    def _get_latest_pred(self):
        return self._last_pred   # (eps, d, d_valid)

    def _start_sequence(self):
        if not self._arduino.is_connected:
            self._status("Arduino 미연결 — 시퀀스 시작 불가")
            return
        n = self._sp_nsteps.value()
        seq = generate_sequence(n_steps=n)
        self._seq_runner.set_sequence(seq)
        self._progress.setMaximum(n)
        self._progress.setValue(0)
        self._tbl.setRowCount(0)
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._seq_runner.start()
        self._status(f"테스트 시퀀스 시작 ({n}스텝, 5mm/s)")

    def _stop_sequence(self):
        self._seq_runner.stop()
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._status("시퀀스 중단")

    def _on_step_started(self, idx, move_type, t_eps, t_d):
        self._progress.setValue(idx)
        self._lbl_seq_status.setText(
            f"[{idx+1}] {move_type}: ε={t_eps:.1f}%  d={t_d:.1f}mm")
        # 목표 마커 표시
        if move_type in ("both", "strain_only"):
            self._g_eps.set_target(t_eps)
        else:
            self._g_eps.clear_target()
        if move_type in ("both", "prox_only"):
            self._g_d.set_target(t_d)
        else:
            self._g_d.clear_target()

    def _on_step_result(self, idx, act_eps, act_d, pred_eps, pred_d, d_valid):
        self._progress.setValue(idx + 1)
        err_eps = pred_eps - act_eps
        err_d   = pred_d   - act_d

        self._err_eps_list.append(abs(err_eps))
        if d_valid:
            self._err_d_list.append(abs(err_d))

        # 테이블 행 추가
        row = self._tbl.rowCount()
        self._tbl.insertRow(row)
        seq = self._seq_runner._seq
        t_eps = seq[idx][1] if idx < len(seq) else 0
        t_d   = seq[idx][2] if idx < len(seq) else 0
        mt    = seq[idx][0] if idx < len(seq) else ""

        vals = [str(idx+1), mt,
                f"{t_eps:.1f}", f"{t_d:.1f}",
                f"{act_eps:.2f}", f"{act_d:.2f}",
                f"{pred_eps:.2f}", f"{pred_d:.2f}",
                f"{err_eps:+.2f}",
                f"{err_d:+.2f}" if d_valid else "N/A"]

        for col, v in enumerate(vals):
            item = QTableWidgetItem(v)
            item.setTextAlignment(Qt.AlignCenter)
            if col == 9 and not d_valid:
                item.setForeground(QBrush(QColor(C["text2"])))
            elif col in (8, 9):
                color = C["red"] if abs(float(v.replace("N/A","0"))) > 2.0 else C["green"]
                item.setForeground(QBrush(QColor(color)))
            self._tbl.setItem(row, col, item)

        self._tbl.scrollToBottom()
        self._update_stats()

    def _on_seq_finished(self):
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._g_eps.clear_target()
        self._g_d.clear_target()
        self._update_stats()
        self._status("시퀀스 완료")

    def _update_stats(self):
        if self._err_eps_list:
            mae_e = np.mean(self._err_eps_list)
            self._lbl_mae_eps.setText(f"MAE ε :  {mae_e:.3f} %")
        if self._err_d_list:
            mae_d = np.mean(self._err_d_list)
            self._lbl_mae_d.setText(f"MAE d :  {mae_d:.3f} mm (valid)")
        n_v = len(self._err_d_list)
        n_t = len(self._err_eps_list)
        self._lbl_n_valid.setText(f"Valid steps : {n_v} / {n_t}")

    def _clear_stats(self):
        self._err_eps_list.clear()
        self._err_d_list.clear()
        self._tbl.setRowCount(0)
        self._lbl_mae_eps.setText("MAE ε :  — %")
        self._lbl_mae_d.setText("MAE d :  — mm (valid)")
        self._lbl_n_valid.setText("Valid steps : —")

    # ── 포트 / 연결 ───────────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for cb in (self._cb_port, self._cb_ard_port):
            cur = cb.currentText()
            cb.clear(); cb.addItems(ports)
            if cur in ports: cb.setCurrentText(cur)

    def _toggle_stm32(self):
        if self._reader.isRunning():
            self._reader.disconnect(); self._reader.quit(); self._reader.wait(1000)
            self._btn_con.setText("연결")
            self._ind_stm.setStyleSheet(f"color:{C['red']};font-size:16px;")
            self._status("STM32 해제")
        else:
            port = self._cb_port.currentText()
            baud = int(self._cb_baud.currentText())
            if not port:
                self._status("포트 선택 필요"); return
            try:
                self._reader.connect(port, baud)
                self._reader.start()
                self._btn_con.setText("해제")
                self._ind_stm.setStyleSheet(f"color:{C['green']};font-size:16px;")
                self._status(f"STM32 연결: {port} @ {baud}")
            except Exception as e:
                self._status(f"STM32 연결 실패: {e}")

    def _toggle_arduino(self):
        if self._arduino.isRunning():
            self._arduino.disconnect(); self._arduino.quit(); self._arduino.wait(1000)
            self._btn_ard_con.setText("연결")
            self._ind_ard.setStyleSheet(f"color:{C['red']};font-size:16px;")
            self._status("Arduino 해제")
        else:
            port = self._cb_ard_port.currentText()
            if not port:
                self._status("Arduino 포트 선택 필요"); return
            try:
                self._arduino.connect(port)
                self._arduino.start()
                self._btn_ard_con.setText("해제")
                self._ind_ard.setStyleSheet(f"color:{C['green']};font-size:16px;")
                self._status(f"Arduino 연결: {port}")
            except Exception as e:
                self._status(f"Arduino 연결 실패: {e}")

    # ── Calibrate ─────────────────────────────────────────────────────────────

    def _calibrate(self):
        if len(self._cal_ldc) < 10:
            self._status("재보정 실패: 데이터 부족"); return
        L0 = float(np.mean(self._cal_ldc))
        R0 = float(np.mean(self._cal_r))
        self._infer.set_baseline(L0, R0)
        self._lbl_baseline.setText(f"L0={L0:.0f}  R0={R0:.2f}")
        for k in ["dL", "dR", "eps", "d"]:
            self._bufs[k].clear()
        self._status(f"재보정 완료: L0={L0:.0f}  R0={R0:.2f}")

    # ── 녹화 ─────────────────────────────────────────────────────────────────

    def _toggle_record(self, checked):
        if checked:
            self._rec_rows.clear()
            self._btn_rec.setText("■ STOP")
            self._recording = True
            self._status("녹화 시작")
        else:
            self._recording = False
            self._btn_rec.setText("● RECORD")
            self._save_csv()

    def _save_csv(self):
        if not self._rec_rows:
            self._status("저장할 데이터 없음"); return
        now  = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(Path(self._save_dir) / f"mlp_monitor_{now}.csv")
        hdr  = ["t_s", "ldc_raw", "r_raw", "dL_pct", "dR_pct",
                "pred_eps_pct", "pred_d_mm", "d_valid",
                "act_eps_pct", "act_d_mm"]
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows([hdr] + self._rec_rows)
            self._status(f"저장 완료: {path}")
        except Exception as e:
            self._status(f"저장 실패: {e}")

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "저장 폴더", self._save_dir)
        if d:
            self._save_dir = d
            self._lbl_dir.setText(d)

    # ── 기타 ──────────────────────────────────────────────────────────────────

    def _status(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self._sb.showMessage(f"[{ts}]  {msg}")

    def _refresh_model_label(self):
        if self._infer.ready:
            txt, col = "2-Stage MLP ready", C["green"]
        elif self._infer.load_error:
            txt, col = self._infer.load_error, C["red"]
        else:
            txt, col = "모델 로드 중...", C["yellow"]
        self._lbl_model.setText(txt)
        self._lbl_model.setStyleSheet(f"color:{col};font-size:11px;")

    def closeEvent(self, event):
        self._ui_timer.stop()
        self._seq_runner.stop()
        self._reader.disconnect(); self._reader.quit(); self._reader.wait(500)
        self._arduino.disconnect(); self._arduino.quit(); self._arduino.wait(500)
        event.accept()


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(C["bg"]))
    pal.setColor(QPalette.WindowText,      QColor(C["text"]))
    pal.setColor(QPalette.Base,            QColor(C["bg2"]))
    pal.setColor(QPalette.Text,            QColor(C["text"]))
    pal.setColor(QPalette.Button,          QColor(C["bg3"]))
    pal.setColor(QPalette.ButtonText,      QColor(C["text"]))
    pal.setColor(QPalette.Highlight,       QColor(C["blue"]))
    pal.setColor(QPalette.HighlightedText, QColor(C["bg"]))
    app.setPalette(pal)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
