"""
realtime_monitor.py
STM32 실시간 센서 데이터 모니터링 + ONNX 디커플링 추론 UI

실행:
    C:/ml_env/Scripts/python realtime_monitor.py

시리얼 포맷 (TDM_Print_Filter_Comparison):
    ldc_raw, r_filtered, teng_filtered, r_raw, teng_raw   (정수 5개, 115200 baud)
"""

import sys, os, time, csv, threading
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import serial
import serial.tools.list_ports
import pickle

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QGroupBox, QFileDialog,
    QSplitter, QStatusBar, QFrame, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette

import pyqtgraph as pg

# ── 경로 ─────────────────────────────────────────────────────────────────────
HERE      = Path(__file__).parent
ONNX_PATH = HERE / "checkpoints" / "decoupler.onnx"
PKL_PATH  = HERE / "checkpoints" / "scalers.pkl"

MAX_POINTS   = 600
BAUD_DEFAULT = 115200
CAL_SAMPLES  = 50

# ── 물체 판별 임계값 ────────────────────────────────────────────────────────────
OBJ_METAL_THR  = -0.25   # ΔL% 이하 → 금속 (도체)
OBJ_HAND_THR   =  0.15   # ΔL% 이상 → 손 (유전체)
OBJ_HAND_SCALE = -10.0   # 손 ΔL → 금속 등가 변환 (반대 부호, 10배 진폭)
TENG_CONTACT_SIGMA = 6.0  # 엣지 임계값 = N × σ(dV)  (Calibrate 시 자동 계산)
TENG_CONTACT_HOLD  = 60   # 접촉 래치 유지 샘플 수 (~0.6s @ 100Hz)

# Catppuccin Mocha 색상
C = {
    "bg":     "#1e1e2e",
    "bg2":    "#181825",
    "bg3":    "#313244",
    "text":   "#cdd6f4",
    "text2":  "#a6adc8",
    "blue":   "#89b4fa",
    "green":  "#a6e3a1",
    "yellow": "#f9e2af",
    "mauve":  "#cba6f7",
    "red":    "#f38ba8",
    "teal":   "#94e2d5",
    "border": "#45475a",
}


# ══════════════════════════════════════════════════════════════════════════════
# ONNX 추론 래퍼
# ══════════════════════════════════════════════════════════════════════════════

_D_SMOOTH_ALPHA = 0.4   # d̂ 출력 스무딩 — τ≈15ms @ 100Hz, 과도 스파이크 완화


class Inferencer:
    """ONNX 모델 + StandardScaler 래퍼. 모델 파일이 없으면 raw 값만 반환."""

    def __init__(self):
        self.ready = False
        self.load_error = None
        self.L0 = None
        self.R0 = None
        self.teng_0 = None         # TENG 기준값 (접촉 판별용)
        self._in_sc  = None
        self._out_sc = None
        self._sess   = None
        self._d_smooth      = None
        self._d_smooth_hand = None
        self._prev_obj_type = None
        self.teng_thr       = 300.0   # Calibrate 전 기본값 (dV 기준)
        self._teng_prev     = None    # 이전 샘플 TENG 값
        self._contact_latch = 0       # 래치 카운트다운 (>0 이면 CONTACT)
        self.obj_metal_thr  = OBJ_METAL_THR
        self.obj_hand_thr   = OBJ_HAND_THR
        self.obj_hand_scale = OBJ_HAND_SCALE
        self._load()

    def _load(self):
        if not PKL_PATH.exists():
            self.load_error = "scalers.pkl 없음"
            return
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with open(PKL_PATH, "rb") as f:
                    s = pickle.load(f)
            self.L0     = float(s["L0"])
            self.R0     = float(s["R0"])
            self._in_sc  = s["input"]
            self._out_sc = s["output"]
        except Exception as e:
            self.load_error = f"pkl 로드 실패: {e}"
            return

        if not ONNX_PATH.exists():
            self.load_error = "decoupler.onnx 없음"
            return
        try:
            import onnxruntime as ort
            self._sess = ort.InferenceSession(
                str(ONNX_PATH), providers=["CPUExecutionProvider"])
            self.ready = True
            self.load_error = None
        except Exception as e:
            self.load_error = f"ONNX 로드 실패: {e}"

    def set_baseline(self, L0: float, R0: float,
                     teng_0: float = None, teng_sigma: float = None):
        self.L0, self.R0 = L0, R0
        if teng_0 is not None:
            self.teng_0   = teng_0
            # 엣지 임계값 = N × σ(dV)  (차분 신호의 표준편차 기반)
            self.teng_thr = (teng_sigma * TENG_CONTACT_SIGMA
                             if teng_sigma is not None else getattr(self, 'teng_thr', 300.0))
        self._d_smooth      = None
        self._d_smooth_hand = None
        self._prev_obj_type = None
        self._teng_prev     = None
        self._contact_latch = 0

    # dL = strain_ratio × dR 관계를 자동 학습
    strain_ratio: float = 0.36   # 기본값 (β₁/α₁ 추정), 실시간 자동 갱신됨

    def update_strain_ratio_auto(self, dL: float, dR: float, alpha: float = 0.005):
        """물체 없음 + 인장 있음 조건에서 EMA로 k를 자동 갱신.
        alpha=0.005 → 반감기 ≈ 1.4s @100Hz.
        """
        if abs(dR) < 1e-9:
            return
        k_sample = dL / dR
        if not (-1.0 < k_sample < 5.0):   # 물리적 범위 밖 노이즈 제외
            return
        self.strain_ratio = (1.0 - alpha) * self.strain_ratio + alpha * k_sample

    def classify(self, dL: float, teng_raw: float):
        """물체 종류 + 접촉 여부 판별.
        TENG 접촉: |dV/dt| 엣지 감지 후 TENG_CONTACT_HOLD 샘플간 래치 유지.
        Returns: (obj_type: str, is_contact: bool)
        """
        if dL < self.obj_metal_thr:
            obj = "METAL"
        elif dL > self.obj_hand_thr:
            obj = "HAND"
        else:
            obj = "NONE"

        # 엣지 트리거: 이전 샘플 대비 변화량이 임계값 초과 시 래치 세트
        if self._teng_prev is not None:
            d_teng = abs(teng_raw - self._teng_prev)
            if d_teng > self.teng_thr:
                self._contact_latch = TENG_CONTACT_HOLD
        self._teng_prev = teng_raw

        # 래치 카운트다운
        if self._contact_latch > 0:
            self._contact_latch -= 1
            is_contact = True
        else:
            is_contact = False

        return obj, is_contact

    def run(self, ldc_raw: float, r_raw: float,
            obj_type: str = "METAL", dL_corrected: float = None) -> tuple:
        """
        Returns: (dL_pct, dR_pct, eps_ratio, d_mm)
        obj_type="HAND" 시 dL_corrected(strain 제거된 proximity ΔL)를 받아
          × OBJ_HAND_SCALE 로 금속 등가 변환 후 추론.
        """
        if self.L0 is None or self.R0 is None:
            return 0.0, 0.0, None, None

        ldc = float(ldc_raw) if ldc_raw > 0 else float(self.L0)
        dL  = ((self.L0 / ldc) ** 2 - 1.0) * 100.0 if ldc > 0 else 0.0
        dR  = ((r_raw - self.R0) / self.R0) * 100.0 if self.R0 != 0 else 0.0

        if not self.ready or obj_type == "NONE":
            return dL, dR, None, None

        # 모드 전환 시 스무딩 리셋
        if obj_type != self._prev_obj_type:
            self._d_smooth      = None
            self._d_smooth_hand = None
            self._prev_obj_type = obj_type

        if obj_type == "METAL":
            dL_model = dL
        else:  # HAND: strain-corrected proximity ΔL → 금속 등가 스케일
            dL_prox  = dL_corrected if dL_corrected is not None else dL
            dL_model = dL_prox * self.obj_hand_scale

        try:
            x      = self._in_sc.transform([[dL_model, dR]]).astype(np.float32)
            y      = self._sess.run(None, {"sensor_input": x})[0]
            y_phys = self._out_sc.inverse_transform(y)
            eps    = float(np.clip(y_phys[0, 0], 0.0, 0.30))
            d_raw  = float(np.clip(y_phys[0, 1], 0.0, 50.0))

            if obj_type == "METAL":
                if self._d_smooth is None:
                    self._d_smooth = d_raw
                self._d_smooth = (_D_SMOOTH_ALPHA * d_raw
                                  + (1.0 - _D_SMOOTH_ALPHA) * self._d_smooth)
                return dL, dR, eps, self._d_smooth
            else:
                if self._d_smooth_hand is None:
                    self._d_smooth_hand = d_raw
                self._d_smooth_hand = (_D_SMOOTH_ALPHA * d_raw
                                       + (1.0 - _D_SMOOTH_ALPHA) * self._d_smooth_hand)
                return dL, dR, eps, self._d_smooth_hand

        except Exception as e:
            self.load_error = f"추론 오류: {e}"
            return dL, dR, None, None


# ══════════════════════════════════════════════════════════════════════════════
# 시리얼 읽기 스레드
# ══════════════════════════════════════════════════════════════════════════════

class STM32Reader(QThread):
    # (timestamp, [ldc, r_filt, teng_filt, r_raw, teng_raw])
    data_received = pyqtSignal(float, list)
    error_msg     = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._ser     = None
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
                time.sleep(0.1)

    @staticmethod
    def _parse(line: str):
        try:
            vals = [float(v.strip()) for v in line.split(",")]
            return vals[:5] if len(vals) >= 5 else None
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# UI 컴포넌트 헬퍼
# ══════════════════════════════════════════════════════════════════════════════

def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color: {C['border']};")
    return f


class ValueCard(QWidget):
    """큰 숫자 + 단위 + 레이블 카드."""

    def __init__(self, label: str, unit: str, color: str, fmt: str = "{:.2f}"):
        super().__init__()
        self._fmt = fmt
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(12, 8, 12, 8)
        vbox.setSpacing(2)

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color:{C['text2']}; font-size:11px; font-weight:600; letter-spacing:1px;")
        vbox.addWidget(self._lbl)

        row = QHBoxLayout()
        self._val = QLabel("—")
        self._val.setStyleSheet(f"color:{color}; font-size:30px; font-weight:700; font-family:Consolas;")
        row.addWidget(self._val)
        row.addStretch()
        self._unit = QLabel(unit)
        self._unit.setStyleSheet(f"color:{C['text2']}; font-size:13px; margin-top:10px;")
        row.addWidget(self._unit)
        vbox.addLayout(row)

        self.setStyleSheet(
            f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;"
        )

    def update(self, val):
        if val is None:
            self._val.setText("—")
        else:
            self._val.setText(self._fmt.format(val))


# ══════════════════════════════════════════════════════════════════════════════
# 메인 윈도우
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NN Decoupler — Real-time Monitor")
        self.resize(1320, 820)

        self._reader     = STM32Reader()
        self._inferencer = Inferencer()

        # 데이터 버퍼 (ts, dL%, dR%, teng, eps, d_mm)
        self._t0   = None
        self._ts   = deque(maxlen=MAX_POINTS)
        self._bufs = {k: deque(maxlen=MAX_POINTS)
                      for k in ["dL", "dR", "teng", "eps", "d"]}

        # 재보정용 누적
        self._cal_buf_ldc  = deque(maxlen=CAL_SAMPLES)
        self._cal_buf_r    = deque(maxlen=CAL_SAMPLES)
        self._cal_buf_teng = deque(maxlen=CAL_SAMPLES)

        # 물체 인식 / 접촉 상태
        self._last_obj     = "NONE"
        self._last_contact = False

        # 기록
        self._recording  = False
        self._rec_rows   = []
        self._save_dir   = str(Path.home())
        self._freq_ts    = deque(maxlen=100)

        self._build_ui()
        self._connect_signals()

        self._ui_timer = QTimer()
        self._ui_timer.timeout.connect(self._refresh)
        self._ui_timer.start(40)   # ~25 fps

    # ── UI 구성 ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        pg.setConfigOption("background", C["bg"])
        pg.setConfigOption("foreground", C["text"])

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 6)

        root.addWidget(self._build_top_bar())
        root.addWidget(_hline())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([300, 1020])
        root.addWidget(splitter, stretch=1)

        root.addWidget(_hline())
        root.addWidget(self._build_record_bar())

        sb = QStatusBar()
        sb.setStyleSheet(f"color:{C['text2']}; font-size:12px;")
        self.setStatusBar(sb)
        self._sb = sb
        self._update_status("시리얼 미연결")

    # ── 상단 접속 바 ──────────────────────────────────────────────────────────

    def _build_top_bar(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0)

        # 포트
        lay.addWidget(self._label("포트"))
        self._cb_port = QComboBox()
        self._cb_port.setMinimumWidth(100)
        lay.addWidget(self._cb_port)

        # 보드레이트
        lay.addWidget(self._label("Baud"))
        self._cb_baud = QComboBox()
        self._cb_baud.addItems(["9600", "115200", "230400", "460800"])
        self._cb_baud.setCurrentText("115200")
        lay.addWidget(self._cb_baud)

        # 연결 버튼 + 인디케이터
        self._btn_connect = QPushButton("연결")
        self._btn_connect.setFixedWidth(64)
        self._btn_connect.setFixedHeight(30)
        self._btn_connect.clicked.connect(self._toggle_connect)
        lay.addWidget(self._btn_connect)

        self._ind = QLabel("●")
        self._ind.setStyleSheet(f"color:{C['red']}; font-size:16px;")
        lay.addWidget(self._ind)

        btn_refresh = QPushButton("⟳")
        btn_refresh.setFixedWidth(30)
        btn_refresh.setFixedHeight(30)
        btn_refresh.setToolTip("포트 목록 새로고침")
        btn_refresh.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_refresh)

        lay.addSpacing(20)

        # 재보정 버튼
        self._btn_cal = QPushButton("Calibrate (Re-baseline)")
        self._btn_cal.setFixedHeight(30)
        self._btn_cal.setStyleSheet(
            f"background:{C['bg3']}; color:{C['yellow']}; "
            f"border:1px solid {C['yellow']}; border-radius:5px; font-weight:600;"
        )
        self._btn_cal.setToolTip(f"현재 {CAL_SAMPLES}샘플 평균으로 L0·R0 재설정")
        self._btn_cal.clicked.connect(self._calibrate)
        lay.addWidget(self._btn_cal)

        # strain_ratio 자동 학습 표시
        self._lbl_strain_ratio = QLabel(f"k={self._inferencer.strain_ratio:.3f} (auto)")
        self._lbl_strain_ratio.setStyleSheet(
            f"color:{C['teal']}; font-size:12px; font-family:Consolas;"
        )
        self._lbl_strain_ratio.setToolTip(
            "물체 없음(d>35mm) + 인장(|ΔR|>0.3%) 조건에서 자동 갱신\n"
            "dL = k × dR 비율"
        )
        lay.addWidget(self._lbl_strain_ratio)

        lay.addSpacing(8)

        # 베이스라인 표시
        self._lbl_baseline = QLabel()
        self._lbl_baseline.setStyleSheet(f"color:{C['text2']}; font-size:12px; font-family:Consolas;")
        lay.addWidget(self._lbl_baseline)
        self._update_baseline_label()

        lay.addStretch()

        # Hz 표시
        self._lbl_hz = QLabel("— Hz")
        self._lbl_hz.setStyleSheet(f"color:{C['teal']}; font-size:13px; font-weight:700; font-family:Consolas;")
        lay.addWidget(self._lbl_hz)

        self._refresh_ports()
        return bar

    # ── 좌측: 값 카드 패널 ────────────────────────────────────────────────────

    def _build_left_panel(self):
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setSpacing(8)
        vbox.setContentsMargins(4, 4, 4, 4)

        vbox.addWidget(self._section_label("RAW INPUTS"))

        self._cards = {
            "dL":   ValueCard("ΔL / L₀",   "%",  C["blue"],   "{:+.3f}"),
            "dR":   ValueCard("ΔR / R₀",   "%",  C["green"],  "{:+.3f}"),
            "teng": ValueCard("V_TENG",     "ADC",C["yellow"], "{:.0f}"),
        }
        for c in list(self._cards.values())[:3]:
            vbox.addWidget(c)

        vbox.addSpacing(4)
        vbox.addWidget(_hline())
        vbox.addWidget(self._section_label("OBJECT RECOGNITION"))

        # 물체 종류 배지
        self._lbl_object = QLabel("—")
        self._lbl_object.setAlignment(Qt.AlignCenter)
        self._lbl_object.setFixedHeight(52)
        self._lbl_object.setStyleSheet(
            f"color:{C['text2']}; font-size:22px; font-weight:700; font-family:Consolas;"
            f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;"
        )
        vbox.addWidget(self._lbl_object)

        # 접촉 배지
        self._lbl_contact = QLabel("NON-CONTACT")
        self._lbl_contact.setAlignment(Qt.AlignCenter)
        self._lbl_contact.setFixedHeight(32)
        self._lbl_contact.setStyleSheet(
            f"color:{C['text2']}; font-size:13px; font-weight:600; font-family:Consolas;"
            f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:6px;"
        )
        vbox.addWidget(self._lbl_contact)

        vbox.addSpacing(4)
        vbox.addWidget(_hline())
        vbox.addWidget(self._section_label("DECOUPLED OUTPUTS"))

        self._cards["eps"] = ValueCard("Strain  ε",  "%",   C["mauve"], "{:.2f}")
        self._cards["d"]   = ValueCard("Proximity d", "mm",  C["red"],   "{:.1f}")
        for c in list(self._cards.values())[3:]:
            vbox.addWidget(c)

        # 모델 상태
        self._lbl_model = QLabel()
        self._lbl_model.setAlignment(Qt.AlignCenter)
        self._lbl_model.setStyleSheet(f"font-size:11px; color:{C['text2']}; margin-top:4px;")
        self._update_model_label()
        vbox.addWidget(self._lbl_model)

        vbox.addSpacing(4)
        vbox.addWidget(_hline())
        vbox.addWidget(self._section_label("HAND SENSITIVITY"))

        # HAND 감지 임계값
        row_thr = QHBoxLayout()
        lbl_thr = QLabel("감지 THR (dL%)")
        lbl_thr.setStyleSheet(f"color:{C['text2']}; font-size:11px;")
        row_thr.addWidget(lbl_thr)
        self._spin_hand_thr = QDoubleSpinBox()
        self._spin_hand_thr.setRange(0.01, 5.0)
        self._spin_hand_thr.setSingleStep(0.05)
        self._spin_hand_thr.setDecimals(2)
        self._spin_hand_thr.setValue(OBJ_HAND_THR)
        self._spin_hand_thr.setFixedWidth(80)
        self._spin_hand_thr.setStyleSheet(
            f"background:{C['bg3']}; color:{C['green']}; "
            f"border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;"
        )
        self._spin_hand_thr.setToolTip(
            "손 감지 임계값 (dL%)\n"
            "낮을수록 민감 (오탐 증가)\n"
            "높을수록 둔감 (미탐 증가)"
        )
        self._spin_hand_thr.valueChanged.connect(self._on_hand_thr_changed)
        row_thr.addWidget(self._spin_hand_thr)
        vbox.addLayout(row_thr)

        # HAND 신호 증폭 배율
        row_scale = QHBoxLayout()
        lbl_scale = QLabel("신호 증폭 |SCALE|")
        lbl_scale.setStyleSheet(f"color:{C['text2']}; font-size:11px;")
        row_scale.addWidget(lbl_scale)
        self._spin_hand_scale = QDoubleSpinBox()
        self._spin_hand_scale.setRange(1.0, 200.0)
        self._spin_hand_scale.setSingleStep(1.0)
        self._spin_hand_scale.setDecimals(1)
        self._spin_hand_scale.setValue(abs(OBJ_HAND_SCALE))
        self._spin_hand_scale.setFixedWidth(80)
        self._spin_hand_scale.setStyleSheet(
            f"background:{C['bg3']}; color:{C['mauve']}; "
            f"border:1px solid {C['border']}; border-radius:4px; font-family:Consolas;"
        )
        self._spin_hand_scale.setToolTip(
            "손 dL 신호 증폭 배율\n"
            "크게 → 가까운 거리 추정 더 민감\n"
            "작게 → 거리 추정 범위 넓어짐"
        )
        self._spin_hand_scale.valueChanged.connect(self._on_hand_scale_changed)
        row_scale.addWidget(self._spin_hand_scale)
        vbox.addLayout(row_scale)

        vbox.addStretch()
        return w

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{C['text2']}; font-size:10px; font-weight:700; "
            f"letter-spacing:2px; margin-top:4px;"
        )
        return lbl

    # ── 우측: 그래프 패널 ─────────────────────────────────────────────────────

    def _build_right_panel(self):
        pw = pg.GraphicsLayoutWidget()

        specs = [
            ("ΔL/L₀ (%)",       C["blue"],   "dL"),
            ("ΔR/R₀ (%)",       C["green"],  "dR"),
            ("V_TENG  (ADC)",   C["yellow"], "teng"),
            ("Strain  ε  (%)",  C["mauve"],  "eps"),
            ("Proximity  d (mm)", C["red"],  "d"),
        ]

        self._plots  = {}
        self._curves = {}
        first_plot   = None

        for i, (title, color, key) in enumerate(specs):
            p = pw.addPlot(row=i, col=0, title=title)
            p.setLabel("left", "")
            p.getAxis("left").setWidth(54)
            p.showGrid(x=False, y=True, alpha=0.15)

            # 타이틀 폰트
            p.titleLabel.setAttr("color", C["text2"])
            p.titleLabel.setAttr("size",  "11pt")

            curve = p.plot(pen=pg.mkPen(color, width=1.8))
            self._plots[key]  = p
            self._curves[key] = curve

            if i == 0:
                first_plot = p
            else:
                p.setXLink(first_plot)

            # 마지막 플롯에만 X축 레이블
            if i == len(specs) - 1:
                p.setLabel("bottom", "시간 (s)")
            else:
                p.getAxis("bottom").setStyle(showValues=False)

        # ε는 0~30% 고정 범위 표시
        self._plots["eps"].setYRange(0, 30, padding=0.05)
        # d는 0~50mm 고정 범위
        self._plots["d"].setYRange(0, 50, padding=0.05)

        # dL 그래프에 물체 판별 임계값 선 표시
        p_dl = self._plots["dL"]
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
        p_dl.addItem(self._line_metal)
        p_dl.addItem(self._line_hand)

        return pw

    # ── 하단 녹화 바 ──────────────────────────────────────────────────────────

    def _build_record_bar(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0)

        self._btn_rec = QPushButton("● RECORD")
        self._btn_rec.setFixedHeight(34)
        self._btn_rec.setFixedWidth(130)
        self._btn_rec.setCheckable(True)
        self._btn_rec.setStyleSheet(
            "QPushButton{background:#f38ba8; color:#1e1e2e; font-weight:700; "
            "font-size:13px; border-radius:5px;}"
            "QPushButton:checked{background:#a6e3a1; color:#1e1e2e;}"
        )
        self._btn_rec.clicked.connect(self._toggle_record)
        lay.addWidget(self._btn_rec)

        lay.addSpacing(12)
        lay.addWidget(self._label("저장 폴더:"))

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

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{C['text2']}; font-weight:600;")
        return lbl

    def _update_baseline_label(self):
        if self._inferencer.L0:
            self._lbl_baseline.setText(
                f"L0={self._inferencer.L0:.0f}  R0={self._inferencer.R0:.2f}"
            )
        else:
            self._lbl_baseline.setText("baseline: 미로드")

    def _update_model_label(self):
        if self._inferencer.ready:
            txt = f"ONNX ready: {ONNX_PATH.name}"
            col = C["green"]
        elif self._inferencer.load_error:
            txt = f"[오류] {self._inferencer.load_error}"
            col = C["red"]
        elif PKL_PATH.exists():
            txt = "ONNX 없음 — 변환값만 표시"
            col = C["yellow"]
        else:
            txt = "모델 파일 없음 (raw only)"
            col = C["red"]
        self._lbl_model.setText(txt)
        self._lbl_model.setStyleSheet(f"font-size:11px; color:{col}; margin-top:4px;")

    # ── 시그널 연결 ───────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._reader.data_received.connect(self._on_data)
        self._reader.error_msg.connect(lambda m: self._update_status(f"오류: {m}"))

    # ── 이벤트 핸들러 ─────────────────────────────────────────────────────────

    def _on_data(self, ts: float, vals: list):
        ldc  = vals[0]
        r    = vals[3]   # r_raw
        teng = vals[2]

        # 재보정 누적
        self._cal_buf_ldc.append(ldc)
        self._cal_buf_r.append(r)
        self._cal_buf_teng.append(teng)

        # ① METAL 모드로 항상 먼저 실행 — strain_ratio 자동 교정 기준값
        dL, dR, eps, d = self._inferencer.run(ldc, r, "METAL")

        # ② strain_ratio 자동 갱신: 물체 없음(d>35mm) + 인장 있음(|ΔR|>0.3%)
        if d is not None and d > 35.0 and abs(dR) > 0.3:
            self._inferencer.update_strain_ratio_auto(dL, dR)

        # ③ 물체 판별: strain 기여 제거 후 분류
        dL_corrected = dL - self._inferencer.strain_ratio * dR
        obj_type, is_contact = self._inferencer.classify(dL_corrected, teng)
        self._last_obj     = obj_type
        self._last_contact = is_contact

        # ④ HAND이면 strain-corrected ΔL로 재추론 (× OBJ_HAND_SCALE 스케일 변환)
        if obj_type == "HAND" and self._inferencer.ready:
            _, _, eps, d = self._inferencer.run(ldc, r, "HAND",
                                                dL_corrected=dL_corrected)

        # 버퍼
        if self._t0 is None:
            self._t0 = ts
        t = ts - self._t0
        self._ts.append(t)
        self._bufs["dL"].append(dL)
        self._bufs["dR"].append(dR)
        self._bufs["teng"].append(teng)
        self._bufs["eps"].append(eps * 100.0 if eps is not None else None)
        self._bufs["d"].append(d)
        self._freq_ts.append(ts)

        # 녹화
        if self._recording:
            self._rec_rows.append([
                round(t, 4), ldc, r, teng,
                round(dL, 4), round(dR, 4),
                round(eps * 100.0, 4) if eps is not None else "",
                round(d, 2) if d is not None else "",
            ])
            self._lbl_rec_count.setText(f"{len(self._rec_rows)}행")

    def _refresh(self):
        n = len(self._ts)
        if n < 2:
            return

        ts_arr = np.array(self._ts)

        # 그래프 업데이트
        for key, curve in self._curves.items():
            buf = self._bufs[key]
            if len(buf) != n:
                continue
            arr = np.array([v if v is not None else np.nan for v in buf])
            curve.setData(ts_arr, arr)

        # 값 카드 업데이트 (최신값)
        self._cards["dL"].update(  self._bufs["dL"][-1]   if self._bufs["dL"]   else None)
        self._cards["dR"].update(  self._bufs["dR"][-1]   if self._bufs["dR"]   else None)
        self._cards["teng"].update(self._bufs["teng"][-1] if self._bufs["teng"] else None)
        self._cards["eps"].update( self._bufs["eps"][-1]  if self._bufs["eps"]  else None)
        self._cards["d"].update(   self._bufs["d"][-1]    if self._bufs["d"]    else None)

        # Hz
        if len(self._freq_ts) >= 2:
            elapsed = self._freq_ts[-1] - self._freq_ts[0]
            if elapsed > 0:
                hz = (len(self._freq_ts) - 1) / elapsed
                self._lbl_hz.setText(f"{hz:.1f} Hz")

        # 물체 인식 배지 갱신
        obj = self._last_obj
        obj_color = {"METAL": C["teal"], "HAND": C["green"], "NONE": C["text2"]}[obj]
        obj_bg    = {"METAL": C["bg3"],  "HAND": C["bg3"],   "NONE": C["bg2"]}[obj]
        self._lbl_object.setText(obj)
        self._lbl_object.setStyleSheet(
            f"color:{obj_color}; font-size:22px; font-weight:700; font-family:Consolas;"
            f"background:{obj_bg}; border:1px solid {obj_color}; border-radius:8px;"
        )

        # 접촉 배지 갱신
        if self._last_contact:
            self._lbl_contact.setText("● CONTACT")
            self._lbl_contact.setStyleSheet(
                f"color:{C['bg']}; font-size:13px; font-weight:700; font-family:Consolas;"
                f"background:{C['red']}; border:1px solid {C['red']}; border-radius:6px;"
            )
        else:
            self._lbl_contact.setText("NON-CONTACT")
            self._lbl_contact.setStyleSheet(
                f"color:{C['text2']}; font-size:13px; font-weight:600; font-family:Consolas;"
                f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:6px;"
            )

        # strain_ratio 실시간 표시 갱신
        k = self._inferencer.strain_ratio
        self._lbl_strain_ratio.setText(f"k={k:.3f} (auto)")

        # 모델 상태 레이블 갱신 (오류 발생 시 즉시 반영)
        self._update_model_label()

    # ── 포트 관리 ─────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        cur   = self._cb_port.currentText()
        self._cb_port.clear()
        self._cb_port.addItems(ports)
        if cur in ports:
            self._cb_port.setCurrentText(cur)

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

    # ── 재보정 ────────────────────────────────────────────────────────────────

    def _calibrate(self):
        if len(self._cal_buf_ldc) < 10:
            self._update_status("재보정 실패: 데이터 부족 (연결 후 잠시 기다리세요)")
            return
        L0         = float(np.mean(self._cal_buf_ldc))
        R0         = float(np.mean(self._cal_buf_r))
        teng_a     = np.array(self._cal_buf_teng, dtype=np.float64)
        teng_0     = float(teng_a.mean())
        # 엣지 감지용: 차분 신호의 σ (노이즈 dV/dt 기준)
        teng_sigma = float(np.diff(teng_a).std()) if len(teng_a) > 2 else 50.0
        self._inferencer.set_baseline(L0, R0, teng_0, teng_sigma)
        self._update_baseline_label()
        # 버퍼 초기화 (새 기준으로 ΔL, ΔR 재계산)
        for k in ["dL", "dR", "eps", "d"]:
            self._bufs[k].clear()
        self._last_obj     = "NONE"
        self._last_contact = False
        self._save_baseline_to_pkl(L0, R0)
        thr = self._inferencer.teng_thr
        self._update_status(
            f"재보정 완료: L0={L0:.0f}  R0={R0:.2f}  "
            f"TENG dV_σ={teng_sigma:.0f}  엣지임계={thr:.0f} ADC/sample"
        )

    def _on_hand_thr_changed(self, val: float):
        self._inferencer.obj_hand_thr = val
        self._line_hand.setValue(val)

    def _on_hand_scale_changed(self, val: float):
        self._inferencer.obj_hand_scale = -abs(val)

    def _save_baseline_to_pkl(self, L0: float, R0: float):
        if not PKL_PATH.exists():
            return
        try:
            with open(PKL_PATH, "rb") as f:
                s = pickle.load(f)
            s["L0"] = L0
            s["R0"] = R0
            with open(PKL_PATH, "wb") as f:
                pickle.dump(s, f)
        except Exception as e:
            self._update_status(f"pkl 저장 실패: {e}")

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
        now  = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(Path(self._save_dir) / f"nn_monitor_{now}.csv")
        hdr  = ["t_s", "ldc_raw", "r_raw", "teng_raw",
                "dL_pct", "dR_pct", "eps_pct", "d_mm"]
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
        self._reader.disconnect()
        self._reader.quit()
        self._reader.wait(1000)
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
