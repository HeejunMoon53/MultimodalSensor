"""
simple_monitor.py
STM32 실시간 모니터링 — 금속 전용 (strain + proximity)

실행:
    C:/ml_env/Scripts/python nn_decoupling/simple_monitor.py

시리얼 포맷 (TDM_Print_Filter_Comparison):
    ldc_raw, r_filtered, teng_filtered, r_raw, teng_raw  (정수 5개, 115200 baud)

이 파일은 realtime_monitor.py를 단순화한 버전이다.
- 물체 판별 / 접촉 감지 없음
- r_filtered (IIR 필터 적용값) 기준으로 dR 계산 및 ONNX 추론
- 금속 단일 모델만 사용
"""

import sys, os, time, csv, pickle
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import serial
import serial.tools.list_ports

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFileDialog,
    QSplitter, QStatusBar, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QPalette

import pyqtgraph as pg

# ── 경로 ──────────────────────────────────────────────────────────────────────
HERE      = Path(__file__).parent
ONNX_PATH = HERE / "checkpoints" / "decoupler.onnx"
PKL_PATH  = HERE / "checkpoints" / "scalers.pkl"

MAX_POINTS   = 600
BAUD_DEFAULT = 115200
CAL_SAMPLES  = 50

# Catppuccin Mocha
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

_D_SMOOTH_ALPHA = 0.4   # proximity d 출력 스무딩


# ══════════════════════════════════════════════════════════════════════════════
# ONNX 추론 래퍼 (금속 전용)
# ══════════════════════════════════════════════════════════════════════════════

class Inferencer:
    """ONNX 모델 + StandardScaler 래퍼 (금속 단일 모드).
    모델 파일이 없으면 dL/dR 변환값만 반환한다.
    dR은 r_filtered 기준으로 계산한다.
    """

    def __init__(self):
        self.ready      = False
        self.load_error = None
        self.L0 = None
        self.R0 = None          # r_filtered 기준 베이스라인
        self._in_sc  = None
        self._out_sc = None
        self._sess   = None
        self._d_smooth = None
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
            self.L0      = float(s["L0"])
            self.R0      = float(s["R0"])
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

    def set_baseline(self, L0: float, R0: float):
        """Calibrate 후 베이스라인 업데이트."""
        self.L0, self.R0 = L0, R0
        self._d_smooth = None

    def run(self, ldc_raw: float, r_filtered: float) -> tuple:
        """
        Returns: (dL_pct, dR_pct, eps_ratio_or_None, d_mm_or_None)
        - dL: (L0/L)² − 1  [%]
        - dR: (r_filtered − R0) / R0  [%]
        """
        if self.L0 is None or self.R0 is None:
            return 0.0, 0.0, None, None

        ldc = float(ldc_raw) if ldc_raw > 0 else float(self.L0)
        dL  = ((self.L0 / ldc) ** 2 - 1.0) * 100.0 if ldc > 0 else 0.0
        dR  = ((r_filtered - self.R0) / self.R0) * 100.0 if self.R0 != 0 else 0.0

        if not self.ready:
            return dL, dR, None, None

        try:
            x      = self._in_sc.transform([[dL, dR]]).astype(np.float32)
            y      = self._sess.run(None, {"sensor_input": x})[0]
            y_phys = self._out_sc.inverse_transform(y)
            eps    = float(np.clip(y_phys[0, 0], 0.0, 0.30))
            d_raw  = float(np.clip(y_phys[0, 1], 0.0, 50.0))

            if self._d_smooth is None:
                self._d_smooth = d_raw
            self._d_smooth = (_D_SMOOTH_ALPHA * d_raw
                              + (1.0 - _D_SMOOTH_ALPHA) * self._d_smooth)
            return dL, dR, eps, self._d_smooth

        except Exception as e:
            self.load_error = f"추론 오류: {e}"
            return dL, dR, None, None


# ══════════════════════════════════════════════════════════════════════════════
# 시리얼 읽기 스레드
# ══════════════════════════════════════════════════════════════════════════════

class STM32Reader(QThread):
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
# UI 헬퍼
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

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color:{C['text2']}; font-size:11px; font-weight:600; letter-spacing:1px;")
        vbox.addWidget(lbl)

        row = QHBoxLayout()
        self._val = QLabel("—")
        self._val.setStyleSheet(
            f"color:{color}; font-size:30px; font-weight:700; font-family:Consolas;")
        row.addWidget(self._val)
        row.addStretch()
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet(f"color:{C['text2']}; font-size:13px; margin-top:10px;")
        row.addWidget(unit_lbl)
        vbox.addLayout(row)

        self.setStyleSheet(
            f"background:{C['bg2']}; border:1px solid {C['border']}; border-radius:8px;")

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
        self.setWindowTitle("Simple Monitor — Strain & Proximity (Metal)")
        self.resize(1320, 780)

        self._reader     = STM32Reader()
        self._inferencer = Inferencer()

        self._t0   = None
        self._ts   = deque(maxlen=MAX_POINTS)
        self._bufs = {k: deque(maxlen=MAX_POINTS)
                      for k in ["dL", "dR", "teng", "eps", "d"]}

        self._cal_buf_ldc = deque(maxlen=CAL_SAMPLES)
        self._cal_buf_r   = deque(maxlen=CAL_SAMPLES)

        self._recording = False
        self._rec_rows  = []
        self._save_dir  = str(Path.home())
        self._freq_ts   = deque(maxlen=100)

        self._build_ui()
        self._reader.data_received.connect(self._on_data)
        self._reader.error_msg.connect(lambda m: self._update_status(f"오류: {m}"))

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
        splitter.setSizes([280, 1040])
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

        lay.addWidget(self._lbl("포트"))
        self._cb_port = QComboBox()
        self._cb_port.setMinimumWidth(100)
        lay.addWidget(self._cb_port)

        lay.addWidget(self._lbl("Baud"))
        self._cb_baud = QComboBox()
        self._cb_baud.addItems(["9600", "115200", "230400", "460800"])
        self._cb_baud.setCurrentText("115200")
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

        lay.addSpacing(20)

        self._btn_cal = QPushButton("Calibrate (Re-baseline)")
        self._btn_cal.setFixedHeight(30)
        self._btn_cal.setStyleSheet(
            f"background:{C['bg3']}; color:{C['yellow']}; "
            f"border:1px solid {C['yellow']}; border-radius:5px; font-weight:600;")
        self._btn_cal.setToolTip(f"현재 {CAL_SAMPLES}샘플 평균으로 L0·R0 재설정 (r_filtered 기준)")
        self._btn_cal.clicked.connect(self._calibrate)
        lay.addWidget(self._btn_cal)

        lay.addSpacing(8)

        self._lbl_baseline = QLabel()
        self._lbl_baseline.setStyleSheet(
            f"color:{C['text2']}; font-size:12px; font-family:Consolas;")
        lay.addWidget(self._lbl_baseline)
        self._update_baseline_label()

        lay.addStretch()

        self._lbl_hz = QLabel("— Hz")
        self._lbl_hz.setStyleSheet(
            f"color:{C['teal']}; font-size:13px; font-weight:700; font-family:Consolas;")
        lay.addWidget(self._lbl_hz)

        self._refresh_ports()
        return bar

    # ── 좌측 패널 ────────────────────────────────────────────────────────────

    def _build_left_panel(self):
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setSpacing(8)
        vbox.setContentsMargins(4, 4, 4, 4)

        vbox.addWidget(self._sec_lbl("RAW INPUTS"))
        self._cards = {
            "dL":   ValueCard("ΔL / L₀",         "%",    C["blue"],   "{:+.3f}"),
            "dR":   ValueCard("ΔR / R₀  (filt.)", "%",    C["green"],  "{:+.3f}"),
            "teng": ValueCard("V_TENG  (filt.)",  "ADC",  C["yellow"], "{:.0f}"),
        }
        for c in list(self._cards.values()):
            vbox.addWidget(c)

        vbox.addSpacing(4)
        vbox.addWidget(_hline())
        vbox.addWidget(self._sec_lbl("DECOUPLED OUTPUTS"))
        self._cards["eps"] = ValueCard("Strain  ε",   "%",  C["mauve"], "{:.2f}")
        self._cards["d"]   = ValueCard("Proximity d", "mm", C["red"],   "{:.1f}")
        vbox.addWidget(self._cards["eps"])
        vbox.addWidget(self._cards["d"])

        self._lbl_model = QLabel()
        self._lbl_model.setAlignment(Qt.AlignCenter)
        self._update_model_label()
        vbox.addWidget(self._lbl_model)

        vbox.addStretch()
        return w

    def _sec_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{C['text2']}; font-size:10px; font-weight:700; "
            f"letter-spacing:2px; margin-top:4px;")
        return lbl

    # ── 우측 그래프 패널 ──────────────────────────────────────────────────────

    def _build_right_panel(self):
        pw = pg.GraphicsLayoutWidget()

        specs = [
            ("ΔL/L₀ (%)",            C["blue"],   "dL"),
            ("ΔR/R₀ (%) — filtered", C["green"],  "dR"),
            ("V_TENG (ADC) — filt",  C["yellow"], "teng"),
            ("Strain  ε (%)",        C["mauve"],  "eps"),
            ("Proximity  d (mm)",    C["red"],    "d"),
        ]

        self._plots  = {}
        self._curves = {}
        first_plot   = None

        for i, (title, color, key) in enumerate(specs):
            p = pw.addPlot(row=i, col=0, title=title)
            p.getAxis("left").setWidth(54)
            p.showGrid(x=False, y=True, alpha=0.15)
            p.titleLabel.setAttr("color", C["text2"])
            p.titleLabel.setAttr("size",  "11pt")

            curve = p.plot(pen=pg.mkPen(color, width=1.8))
            self._plots[key]  = p
            self._curves[key] = curve

            if i == 0:
                first_plot = p
            else:
                p.setXLink(first_plot)

            if i == len(specs) - 1:
                p.setLabel("bottom", "시간 (s)")
            else:
                p.getAxis("bottom").setStyle(showValues=False)

        self._plots["eps"].setYRange(0, 30, padding=0.05)
        self._plots["d"].setYRange(0, 50, padding=0.05)

        return pw

    # ── 하단 녹화 바 ──────────────────────────────────────────────────────────

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
        self._lbl_rec_count.setStyleSheet(
            f"color:{C['text2']}; font-family:Consolas;")
        lay.addWidget(self._lbl_rec_count)

        return bar

    # ── 헬퍼 ──────────────────────────────────────────────────────────────────

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{C['text2']}; font-weight:600;")
        return lbl

    def _update_baseline_label(self):
        if self._inferencer.L0:
            self._lbl_baseline.setText(
                f"L0={self._inferencer.L0:.0f}  R0(filt)={self._inferencer.R0:.2f}")
        else:
            self._lbl_baseline.setText("baseline: 미로드")

    def _update_model_label(self):
        if self._inferencer.ready:
            txt = f"ONNX ready: {ONNX_PATH.name}"
            col = C["green"]
        elif self._inferencer.load_error:
            txt = f"[오류] {self._inferencer.load_error}"
            col = C["red"]
        else:
            txt = "모델 없음 (raw only)"
            col = C["yellow"]
        self._lbl_model.setText(txt)
        self._lbl_model.setStyleSheet(f"font-size:11px; color:{col}; margin-top:4px;")

    # ── 데이터 수신 ───────────────────────────────────────────────────────────

    def _on_data(self, ts: float, vals: list):
        ldc        = vals[0]   # ldc_raw
        r_filtered = vals[1]   # r_filtered (IIR)
        teng_filt  = vals[2]   # teng_filtered

        self._cal_buf_ldc.append(ldc)
        self._cal_buf_r.append(r_filtered)

        dL, dR, eps, d = self._inferencer.run(ldc, r_filtered)

        if self._t0 is None:
            self._t0 = ts
        t = ts - self._t0

        self._ts.append(t)
        self._bufs["dL"].append(dL)
        self._bufs["dR"].append(dR)
        self._bufs["teng"].append(teng_filt)
        self._bufs["eps"].append(eps * 100.0 if eps is not None else None)
        self._bufs["d"].append(d)
        self._freq_ts.append(ts)

        if self._recording:
            self._rec_rows.append([
                round(t, 4), ldc, r_filtered, teng_filt,
                round(dL, 4), round(dR, 4),
                round(eps * 100.0, 4) if eps is not None else "",
                round(d, 2)          if d   is not None else "",
            ])
            self._lbl_rec_count.setText(f"{len(self._rec_rows)}행")

    # ── 화면 갱신 ─────────────────────────────────────────────────────────────

    def _refresh(self):
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

        for key in ["dL", "dR", "teng", "eps", "d"]:
            buf = self._bufs[key]
            self._cards[key].update(buf[-1] if buf else None)

        if len(self._freq_ts) >= 2:
            elapsed = self._freq_ts[-1] - self._freq_ts[0]
            if elapsed > 0:
                self._lbl_hz.setText(f"{(len(self._freq_ts)-1)/elapsed:.1f} Hz")

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
        L0 = float(np.mean(self._cal_buf_ldc))
        R0 = float(np.mean(self._cal_buf_r))
        self._inferencer.set_baseline(L0, R0)
        self._update_baseline_label()
        for k in ["dL", "dR", "eps", "d"]:
            self._bufs[k].clear()
        self._save_baseline_to_pkl(L0, R0)
        self._update_status(f"재보정 완료: L0={L0:.0f}  R0(filt)={R0:.2f}")

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
        path = str(Path(self._save_dir) / f"simple_monitor_{now}.csv")
        hdr  = ["t_s", "ldc_raw", "r_filtered", "teng_filtered",
                "dL_pct", "dR_pct", "eps_pct", "d_mm"]
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                import csv
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
