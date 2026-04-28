"""
SyncAcquisition_UI.py
STM32(UART) + Arduino(인장 머신) 동기화 데이터 취득 UI
기존 Positioning_Stage_Controller_V3.2.py 기능 전체 포함 + STM32 실시간 그래프 + RECORD
"""

import sys, time, csv, copy, threading
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import serial
import serial.tools.list_ports

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QComboBox, QGroupBox,
    QFileDialog, QSplitter, QStatusBar, QDoubleSpinBox, QSpinBox,
    QTabWidget, QTextEdit, QSizePolicy, QDialog, QFormLayout,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QCheckBox,
    QDialogButtonBox, QMessageBox, QFrame, QLineEdit, QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette

import pyqtgraph as pg
import openpyxl


# ── 상수 ──────────────────────────────────────────────────────────────
AXES            = ["XA", "XB", "YA", "YB", "Z"]
STEPS_PER_REV   = 200
DEFAULT_MICROSTEP = 8
DEFAULT_PITCH_MM  = 5.0
LIMIT_MIN_MM      = -200.0
LIMIT_MAX_MM      =  200.0
MAX_POINTS        = 500
ARDUINO_POLL_MS   = 100
STM32_BAUD        = 115200
ARDUINO_BAUD      = 115200


# ══════════════════════════════════════════════════════════════════════
# Worker Threads
# ══════════════════════════════════════════════════════════════════════

class STM32Reader(QThread):
    data_received = pyqtSignal(float, list)
    log_msg       = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ser = None
        self._running = False

    def connect(self, port, baud=STM32_BAUD):
        self.ser = serial.Serial(port, baud, timeout=0.1)
        time.sleep(0.5)
        self._running = True

    def disconnect(self):
        self._running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

    def run(self):
        buf = ""
        while self._running:
            try:
                if self.ser and self.ser.in_waiting:
                    raw = self.ser.read(self.ser.in_waiting).decode("utf-8", errors="ignore")
                    buf += raw
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            vals = self._parse(line)
                            if vals:
                                self.data_received.emit(time.time(), vals)
                else:
                    time.sleep(0.001)
            except Exception as e:
                self.log_msg.emit(f"[STM32 오류] {e}")
                time.sleep(0.1)

    @staticmethod
    def _parse(line):
        try:
            vals = [float(v.strip()) for v in line.split(",")]
            return vals[:5] if len(vals) >= 5 else None
        except Exception:
            return None


class ArduinoController(QThread):
    position_updated = pyqtSignal(float, dict)
    log_msg          = pyqtSignal(str)
    done_received    = pyqtSignal()
    alarm_received   = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ser          = None
        self._running     = False
        self._lock        = threading.Lock()
        self._cmd_queue   = deque()
        self.steps_per_mm = (STEPS_PER_REV * DEFAULT_MICROSTEP) / DEFAULT_PITCH_MM
        self._last_pos    = {ax: 0.0 for ax in AXES}
        self._limit_hits  = {}

    def connect(self, port, baud=ARDUINO_BAUD):
        self.ser = serial.Serial(port, baud, timeout=0.1)
        time.sleep(2.0)
        self._running = True

    def disconnect(self):
        self._running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send(self, cmd: str):
        with self._lock:
            self._cmd_queue.append(cmd)

    def jog(self, axis: str, dist_mm: float, speed_mms: float = 5.0):
        steps = int(abs(dist_mm) * self.steps_per_mm)
        spd   = int(speed_mms * self.steps_per_mm)
        self.send(f"JOG:{axis}:{-steps if dist_mm < 0 else steps}:{spd}")

    def run(self):
        poll_t = ARDUINO_POLL_MS / 1000.0
        last   = 0.0
        while self._running:
            try:
                with self._lock:
                    if self._cmd_queue:
                        cmd = self._cmd_queue.popleft()
                        if self.ser and self.ser.is_open:
                            self.ser.write((cmd + "\n").encode())

                now = time.time()
                if now - last >= poll_t:
                    if self.ser and self.ser.is_open:
                        self.ser.write(b"POS?\n")
                    last = now

                if self.ser and self.ser.in_waiting:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line.startswith("POS:"):
                        pos, limits = self._parse_pos(line)
                        if pos:
                            self._last_pos.update(pos)
                            self._limit_hits = limits
                            self.position_updated.emit(time.time(), pos)
                    elif line == "DONE":
                        self.done_received.emit()
                    elif "ALARM" in line:
                        self.alarm_received.emit(line)
                else:
                    time.sleep(0.005)
            except Exception as e:
                self.log_msg.emit(f"[Arduino 오류] {e}")
                time.sleep(0.1)

    def _parse_pos(self, line):
        try:
            parts = line.split(":")[1:]
            vals  = [float(v) for v in parts]
            pos   = {ax: round(vals[i] / self.steps_per_mm, 3) for i, ax in enumerate(AXES)}
            limits = {}
            if len(vals) >= 11:
                sw_names = ["XA_in","XA_out","YA_in","YA_out","Z_in","Z_out"]
                for i, name in enumerate(sw_names):
                    limits[name] = (vals[6+i] == 0)
            return pos, limits
        except Exception:
            return None, {}


# ══════════════════════════════════════════════════════════════════════
# DataLogger
# ══════════════════════════════════════════════════════════════════════

class DataLogger:
    HEADERS = ["timestamp_s","XA_mm","XB_mm","YA_mm","YB_mm","Z_mm",
               "LDC","R_DC","TENG","R_raw","TENG_raw"]

    def __init__(self):
        self._rows      = []
        self._recording = False
        self._last_pos  = {ax: 0.0 for ax in AXES}
        self._lock      = threading.Lock()
        self._t0        = None

    def start(self, t0):
        with self._lock:
            self._rows = []; self._recording = True; self._t0 = t0

    def stop(self):
        with self._lock:
            self._recording = False

    def update_position(self, pos):
        with self._lock:
            self._last_pos.update(pos)

    def add_sensor(self, ts, vals):
        if not self._recording: return
        with self._lock:
            pos = dict(self._last_pos)
            rel = round(ts - self._t0, 4)
            self._rows.append([rel, pos["XA"],pos["XB"],pos["YA"],pos["YB"],pos["Z"], *vals])

    def row_count(self):
        with self._lock: return len(self._rows)

    def save(self, path):
        with self._lock: rows = list(self._rows)
        if path.endswith(".xlsx"):
            wb = openpyxl.Workbook(); ws = wb.active; ws.title = "SyncData"
            ws.append(self.HEADERS)
            for r in rows: ws.append(r)
            wb.save(path)
        else:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f); w.writerow(self.HEADERS); w.writerows(rows)


# ══════════════════════════════════════════════════════════════════════
# Settings Dialog
# ══════════════════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setMinimumWidth(360)
        self.result_settings = None
        form = QFormLayout(self)

        self.sp_baud_ard  = QComboBox(); self.sp_baud_ard.addItems(["9600","115200","250000"])
        self.sp_baud_ard.setCurrentText(str(settings["baud_arduino"]))
        self.sp_baud_stm  = QComboBox(); self.sp_baud_stm.addItems(["9600","115200","250000"])
        self.sp_baud_stm.setCurrentText(str(settings["baud_stm32"]))
        self.sp_microstep = QComboBox(); self.sp_microstep.addItems(["1","2","4","8","16","32"])
        self.sp_microstep.setCurrentText(str(settings["microstep"]))
        self.sp_pitch = QDoubleSpinBox(); self.sp_pitch.setRange(0.1,100); self.sp_pitch.setSingleStep(0.5)
        self.sp_pitch.setValue(settings["pitch_mm"])
        self.sp_jog_s = QDoubleSpinBox(); self.sp_jog_s.setRange(0.01,10); self.sp_jog_s.setValue(settings["jog_small"])
        self.sp_jog_m = QDoubleSpinBox(); self.sp_jog_m.setRange(0.1,50);  self.sp_jog_m.setValue(settings["jog_mid"])
        self.sp_jog_l = QDoubleSpinBox(); self.sp_jog_l.setRange(1,200);   self.sp_jog_l.setValue(settings["jog_large"])
        self.sp_jog_spd = QDoubleSpinBox(); self.sp_jog_spd.setRange(0.1,50); self.sp_jog_spd.setValue(settings["jog_speed"])
        self.sp_lim_dist = QDoubleSpinBox(); self.sp_lim_dist.setRange(1,500); self.sp_lim_dist.setValue(settings["limit_dist"])
        self.sp_lim_spd  = QDoubleSpinBox(); self.sp_lim_spd.setRange(0.1,100); self.sp_lim_spd.setValue(settings["limit_speed"])
        self.chk_limits  = QCheckBox("소프트웨어 이동 한계 활성화")
        self.chk_limits.setChecked(settings["enable_limits"])

        form.addRow("Arduino 보드레이트", self.sp_baud_ard)
        form.addRow("STM32 보드레이트",   self.sp_baud_stm)
        form.addRow("마이크로스텝",        self.sp_microstep)
        form.addRow("스크류 피치 (mm/rev)",self.sp_pitch)
        form.addRow("조그 소 (mm)",        self.sp_jog_s)
        form.addRow("조그 중 (mm)",        self.sp_jog_m)
        form.addRow("조그 대 (mm)",        self.sp_jog_l)
        form.addRow("조그 속도 (mm/s)",    self.sp_jog_spd)
        form.addRow(self.chk_limits)
        form.addRow("최대 이동 거리 (mm)", self.sp_lim_dist)
        form.addRow("최대 속도 (mm/s)",    self.sp_lim_spd)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _accept(self):
        self.result_settings = {
            "baud_arduino": int(self.sp_baud_ard.currentText()),
            "baud_stm32":   int(self.sp_baud_stm.currentText()),
            "microstep":    int(self.sp_microstep.currentText()),
            "pitch_mm":     self.sp_pitch.value(),
            "jog_small":    self.sp_jog_s.value(),
            "jog_mid":      self.sp_jog_m.value(),
            "jog_large":    self.sp_jog_l.value(),
            "jog_speed":    self.sp_jog_spd.value(),
            "enable_limits":self.chk_limits.isChecked(),
            "limit_dist":   self.sp_lim_dist.value(),
            "limit_speed":  self.sp_lim_spd.value(),
        }
        self.accept()


# ══════════════════════════════════════════════════════════════════════
# Main Window
# ══════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sync Acquisition — STM32 + Arduino")
        self.resize(1400, 860)

        self.stm32   = STM32Reader()
        self.arduino = ArduinoController()
        self.logger  = DataLogger()

        self._settings = {
            "baud_arduino": 115200, "baud_stm32": 115200,
            "microstep": 8, "pitch_mm": 5.0,
            "jog_small": 0.1, "jog_mid": 1.0, "jog_large": 5.0,
            "jog_speed": 5.0,
            "enable_limits": True, "limit_dist": 50.0, "limit_speed": 10.0,
        }
        self._apply_settings()

        self._save_dir      = str(Path.home())
        self._is_recording  = False
        self._emergency     = False
        self._seq_data      = []
        self._clipboard     = []
        self._editing_idx   = None
        self._is_running_seq = False

        # 그래프 버퍼
        self._t0      = None
        self._ts_buf  = deque(maxlen=MAX_POINTS)
        self._bufs    = [deque(maxlen=MAX_POINTS) for _ in range(5)]   # ldc,rdc,teng,r_raw,teng_raw

        self._build_ui()
        self._connect_signals()

        self._ui_timer = QTimer()
        self._ui_timer.timeout.connect(self._refresh_graph)
        self._ui_timer.start(50)

    def _apply_settings(self):
        s = self._settings
        self.steps_per_mm = (STEPS_PER_REV * s["microstep"]) / s["pitch_mm"]
        self.arduino.steps_per_mm = self.steps_per_mm

    # ──────────────────────────────────────────────────────────────────
    # UI 구성
    # ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        pg.setConfigOption("background", "#1e1e2e")
        pg.setConfigOption("foreground", "#cdd6f4")

        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setSpacing(4)

        vbox.addWidget(self._build_top_bar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([520, 880])
        vbox.addWidget(splitter, stretch=1)

        vbox.addWidget(self._build_record_bar())

    # ── 상단 바 ─────────────────────────────────────────────────────

    def _build_top_bar(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 4, 4, 4)

        # STM32 연결
        lay.addWidget(self._sep_label("STM32"))
        self.cb_stm32 = QComboBox(); self.cb_stm32.setMinimumWidth(90)
        lay.addWidget(self.cb_stm32)
        self.btn_stm32 = QPushButton("연결"); self.btn_stm32.setFixedWidth(60)
        self.btn_stm32.clicked.connect(self._toggle_stm32)
        lay.addWidget(self.btn_stm32)
        self.ind_stm32 = self._indicator()
        lay.addWidget(self.ind_stm32)

        lay.addSpacing(16)

        # Arduino 연결
        lay.addWidget(self._sep_label("Arduino"))
        self.cb_arduino = QComboBox(); self.cb_arduino.setMinimumWidth(90)
        lay.addWidget(self.cb_arduino)
        self.btn_arduino = QPushButton("연결"); self.btn_arduino.setFixedWidth(60)
        self.btn_arduino.clicked.connect(self._toggle_arduino)
        lay.addWidget(self.btn_arduino)
        self.ind_arduino = self._indicator()
        lay.addWidget(self.ind_arduino)

        btn_refresh = QPushButton("⟳"); btn_refresh.setFixedWidth(32)
        btn_refresh.setToolTip("포트 새로고침")
        btn_refresh.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_refresh)

        lay.addSpacing(16)

        # 비상정지
        self.btn_emg = QPushButton("⚠ EMERGENCY")
        self.btn_emg.setFixedHeight(32)
        self.btn_emg.setStyleSheet("background:#f38ba8; color:white; font-weight:bold; border-radius:4px;")
        self.btn_emg.clicked.connect(self._toggle_emergency)
        lay.addWidget(self.btn_emg)

        lay.addStretch()

        # 설정
        btn_cfg = QPushButton("⚙ 설정"); btn_cfg.setFixedWidth(72)
        btn_cfg.clicked.connect(self._open_settings)
        lay.addWidget(btn_cfg)

        self._refresh_ports()
        return bar

    def _sep_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight:bold;")
        return lbl

    def _indicator(self):
        lbl = QLabel("●")
        lbl.setStyleSheet("color:#f38ba8; font-size:16px;")
        return lbl

    def _set_indicator(self, lbl, on: bool):
        lbl.setStyleSheet(f"color:{'#a6e3a1' if on else '#f38ba8'}; font-size:16px;")

    # ── 좌측 패널 ────────────────────────────────────────────────────

    def _build_left_panel(self):
        tabs = QTabWidget()
        tabs.addTab(self._build_manual_tab(),   "수동 조그")
        tabs.addTab(self._build_sequence_tab(), "시퀀스 프로그램")
        tabs.addTab(self._build_log_tab(),      "로그")
        return tabs

    # ── 수동 조그 탭 ─────────────────────────────────────────────────

    def _build_manual_tab(self):
        w = QWidget(); vbox = QVBoxLayout(w)

        # 위치 표시
        pos_grp = QGroupBox("현재 위치 (mm)")
        grid = QGridLayout(pos_grp)
        self.pos_labels = {}
        for i, ax in enumerate(AXES):
            grid.addWidget(QLabel(ax, alignment=Qt.AlignCenter), 0, i)
            lbl = QLabel("0.000", alignment=Qt.AlignCenter)
            lbl.setStyleSheet("font-size:20px; font-weight:bold; color:#89b4fa;")
            grid.addWidget(lbl, 1, i)
            self.pos_labels[ax] = lbl
        vbox.addWidget(pos_grp)

        # 모터 제어 버튼
        ctrl_lay = QHBoxLayout()
        self.btn_lock = QPushButton("🔒 LOCK")
        self.btn_lock.setStyleSheet("background:#f9e2af; color:black;")
        self.btn_lock.clicked.connect(lambda: self.arduino.send("EN:1"))
        self.btn_free = QPushButton("🔓 FREE")
        self.btn_free.setStyleSheet("background:#a6e3a1; color:black;")
        self.btn_free.clicked.connect(lambda: self.arduino.send("EN:0"))
        btn_zero = QPushButton("원점(ZERO)")
        btn_zero.clicked.connect(self._set_zero)
        btn_emg_rst = QPushButton("EMG RESET")
        btn_emg_rst.clicked.connect(lambda: self.arduino.send("RESET_EMG"))
        for b in [self.btn_lock, self.btn_free, btn_zero, btn_emg_rst]:
            ctrl_lay.addWidget(b)
        vbox.addLayout(ctrl_lay)

        # 조그 버튼
        jog_grp = QGroupBox("조그 제어")
        jog_grid = QGridLayout(jog_grp)
        self._jog_btns = {}
        s = self._settings

        jog_defs = [
            ("<<<", -s["jog_large"]), ("<<", -s["jog_mid"]), ("<", -s["jog_small"]),
            (">",   s["jog_small"]),  (">>",  s["jog_mid"]), (">>>", s["jog_large"]),
        ]
        headers = [f"<<<\n{s['jog_large']}mm", f"<<\n{s['jog_mid']}mm", f"<\n{s['jog_small']}mm",
                   f">\n{s['jog_small']}mm", f">>\n{s['jog_mid']}mm", f">>>\n{s['jog_large']}mm"]

        for col, h in enumerate(headers):
            lbl = QLabel(h, alignment=Qt.AlignCenter); lbl.setStyleSheet("font-size:9px;")
            jog_grid.addWidget(lbl, 0, col+1)

        for row, ax in enumerate(AXES):
            jog_grid.addWidget(QLabel(ax), row+1, 0)
            self._jog_btns[ax] = []
            for col, (label, dist) in enumerate(jog_defs):
                btn = QPushButton(label); btn.setFixedWidth(46); btn.setFixedHeight(28)
                d = dist
                btn.clicked.connect(lambda _, a=ax, d=d: self._do_jog(a, d))
                jog_grid.addWidget(btn, row+1, col+1)
                self._jog_btns[ax].append(btn)
        vbox.addWidget(jog_grp)
        vbox.addStretch()
        return w

    # ── 시퀀스 탭 ────────────────────────────────────────────────────

    def _build_sequence_tab(self):
        w = QWidget(); vbox = QVBoxLayout(w)

        # 입력 영역
        inp_grp = QGroupBox("스텝 입력")
        inp_lay = QGridLayout(inp_grp)

        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["대칭 이동 (Symmetric)", "개별 이동 (Individual)", "대기 (Delay)"])
        self.cb_mode.currentIndexChanged.connect(self._update_seq_inputs)
        inp_lay.addWidget(QLabel("동작 유형:"), 0, 0)
        inp_lay.addWidget(self.cb_mode, 0, 1, 1, 3)

        # 동적 입력 컨테이너
        self.seq_input_widget = QWidget()
        self.seq_input_layout = QGridLayout(self.seq_input_widget)
        inp_lay.addWidget(self.seq_input_widget, 1, 0, 1, 4)

        btn_add = QPushButton("스텝 추가"); btn_add.clicked.connect(self._add_seq_step)
        btn_clr = QPushButton("편집 취소"); btn_clr.clicked.connect(self._cancel_edit)
        inp_lay.addWidget(btn_add, 2, 0, 1, 2)
        inp_lay.addWidget(btn_clr, 2, 2, 1, 2)
        vbox.addWidget(inp_grp)

        # 시퀀스 리스트
        self.seq_tree = QTreeWidget()
        self.seq_tree.setHeaderLabels(["#", "유형", "내용", "속도(mm/s)"])
        self.seq_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.seq_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.seq_tree.itemDoubleClicked.connect(self._load_for_edit)
        vbox.addWidget(self.seq_tree, stretch=1)

        # 리스트 조작 버튼
        btn_row = QHBoxLayout()
        for label, slot in [("▲ 위로", self._seq_up), ("▼ 아래", self._seq_down),
                             ("삭제", self._seq_delete), ("전체 삭제", self._seq_clear),
                             ("복사 Ctrl+C", self._seq_copy), ("붙여넣기 Ctrl+V", self._seq_paste)]:
            b = QPushButton(label); b.clicked.connect(slot); btn_row.addWidget(b)
        vbox.addLayout(btn_row)

        # 실행 버튼
        run_row = QHBoxLayout()
        self.btn_run_seq = QPushButton("▶ 시퀀스 실행")
        self.btn_run_seq.setStyleSheet("background:#89b4fa; color:#1e1e2e; font-weight:bold;")
        self.btn_run_seq.clicked.connect(self._run_sequence)
        self.btn_stop_seq = QPushButton("■ 정지")
        self.btn_stop_seq.clicked.connect(lambda: setattr(self, '_is_running_seq', False))
        run_row.addWidget(self.btn_run_seq)
        run_row.addWidget(self.btn_stop_seq)
        vbox.addLayout(run_row)

        self._update_seq_inputs()
        return w

    def _update_seq_inputs(self):
        # 동적 입력 위젯 초기화
        for i in reversed(range(self.seq_input_layout.count())):
            self.seq_input_layout.itemAt(i).widget().deleteLater()

        mode = self.cb_mode.currentIndex()
        self._seq_spins = {}
        lay = self.seq_input_layout

        if mode == 0:  # 대칭
            for col, (label, key) in enumerate([("총 X (mm)", "tot_x"), ("총 Y (mm)", "tot_y"), ("Z (mm)", "z")]):
                lay.addWidget(QLabel(label), 0, col*2)
                sp = QDoubleSpinBox(); sp.setRange(-500, 500); sp.setSingleStep(1)
                lay.addWidget(sp, 0, col*2+1)
                self._seq_spins[key] = sp
            lay.addWidget(QLabel("속도 (mm/s)"), 1, 0)
            sp = QDoubleSpinBox(); sp.setRange(0.1, 50); sp.setValue(5.0)
            lay.addWidget(sp, 1, 1)
            self._seq_spins["speed"] = sp

        elif mode == 1:  # 개별
            for i, ax in enumerate(AXES):
                lay.addWidget(QLabel(f"{ax} (mm)"), i//3, (i%3)*2)
                sp = QDoubleSpinBox(); sp.setRange(-500, 500); sp.setSingleStep(1)
                lay.addWidget(sp, i//3, (i%3)*2+1)
                self._seq_spins[ax] = sp
            lay.addWidget(QLabel("속도 (mm/s)"), 2, 0)
            sp = QDoubleSpinBox(); sp.setRange(0.1, 50); sp.setValue(5.0)
            lay.addWidget(sp, 2, 1)
            self._seq_spins["speed"] = sp

        else:  # 대기
            lay.addWidget(QLabel("대기 시간 (ms)"), 0, 0)
            sp = QSpinBox(); sp.setRange(0, 60000); sp.setValue(1000); sp.setSingleStep(100)
            lay.addWidget(sp, 0, 1)
            self._seq_spins["delay"] = sp

    def _add_seq_step(self):
        mode = self.cb_mode.currentIndex()
        sp   = self._seq_spins

        if mode == 0:
            tx, ty, z = sp["tot_x"].value(), sp["tot_y"].value(), sp["z"].value()
            spd = sp["speed"].value()
            cmds = [("XA", tx/2), ("XB", -tx/2), ("YA", ty/2), ("YB", -ty/2), ("Z", z)]
            desc = f"Sym X:{tx} Y:{ty} Z:{z} @ {spd}mm/s"
            step = {"type": "MOVE", "cmds_mm": cmds, "spd_mm": spd, "desc": desc}

        elif mode == 1:
            spd  = sp["speed"].value()
            cmds = [(ax, sp[ax].value()) for ax in AXES]
            desc = "  ".join(f"{ax}:{v:.1f}" for ax, v in cmds) + f" @ {spd}mm/s"
            step = {"type": "MOVE", "cmds_mm": cmds, "spd_mm": spd, "desc": desc}

        else:
            delay = sp["delay"].value()
            step  = {"type": "WAIT", "val": delay, "desc": f"대기 {delay}ms"}

        if self._editing_idx is not None:
            self._seq_data[self._editing_idx] = step
            self._editing_idx = None
        else:
            self._seq_data.append(step)
        self._rebuild_tree()

    def _rebuild_tree(self):
        self.seq_tree.clear()
        mode_names = ["대칭 이동", "개별 이동", "대기"]
        for i, step in enumerate(self._seq_data):
            desc = step.get("desc", "")
            spd  = str(step.get("spd_mm", "")) if step["type"] == "MOVE" else "-"
            item = QTreeWidgetItem([str(i+1), step["type"], desc, spd])
            self.seq_tree.addTopLevelItem(item)

    def _load_for_edit(self, item):
        idx = self.seq_tree.indexOfTopLevelItem(item)
        if idx < 0: return
        self._editing_idx = idx
        step = self._seq_data[idx]
        if step["type"] == "WAIT":
            self.cb_mode.setCurrentIndex(2)
            QTimer.singleShot(50, lambda: self._seq_spins["delay"].setValue(step["val"]))
        else:
            cmds = {ax: v for ax, v in step["cmds_mm"]}
            # 대칭인지 개별인지 추정
            is_sym = ("XA" in cmds and "XB" in cmds and abs(cmds["XA"] + cmds["XB"]) < 0.01)
            if is_sym:
                self.cb_mode.setCurrentIndex(0)
                def fill_sym():
                    self._seq_spins["tot_x"].setValue(cmds.get("XA",0)*2)
                    self._seq_spins["tot_y"].setValue(cmds.get("YA",0)*2)
                    self._seq_spins["z"].setValue(cmds.get("Z",0))
                    self._seq_spins["speed"].setValue(step["spd_mm"])
                QTimer.singleShot(50, fill_sym)
            else:
                self.cb_mode.setCurrentIndex(1)
                def fill_ind():
                    for ax in AXES:
                        self._seq_spins[ax].setValue(cmds.get(ax, 0))
                    self._seq_spins["speed"].setValue(step["spd_mm"])
                QTimer.singleShot(50, fill_ind)

    def _cancel_edit(self):
        self._editing_idx = None

    def _seq_up(self):
        items = self.seq_tree.selectedItems()
        if not items: return
        idx = self.seq_tree.indexOfTopLevelItem(items[0])
        if idx > 0:
            self._seq_data[idx-1], self._seq_data[idx] = self._seq_data[idx], self._seq_data[idx-1]
            self._rebuild_tree()

    def _seq_down(self):
        items = self.seq_tree.selectedItems()
        if not items: return
        idx = self.seq_tree.indexOfTopLevelItem(items[0])
        if idx < len(self._seq_data)-1:
            self._seq_data[idx], self._seq_data[idx+1] = self._seq_data[idx+1], self._seq_data[idx]
            self._rebuild_tree()

    def _seq_delete(self):
        idxs = sorted([self.seq_tree.indexOfTopLevelItem(i) for i in self.seq_tree.selectedItems()], reverse=True)
        for i in idxs:
            del self._seq_data[i]
        self._rebuild_tree()

    def _seq_clear(self):
        self._seq_data.clear(); self._rebuild_tree()

    def _seq_copy(self):
        self._clipboard = copy.deepcopy([
            self._seq_data[self.seq_tree.indexOfTopLevelItem(i)]
            for i in self.seq_tree.selectedItems()
        ])

    def _seq_paste(self):
        self._seq_data.extend(copy.deepcopy(self._clipboard))
        self._rebuild_tree()

    def _run_sequence(self):
        if not self._seq_data:
            self._log("시퀀스가 비어 있습니다"); return
        if not self.arduino.isRunning():
            self._log("Arduino 미연결"); return
        self._is_running_seq = True
        self.btn_run_seq.setEnabled(False)

        def execute():
            for i, step in enumerate(self._seq_data):
                if not self._is_running_seq or self._emergency: break
                self._log(f"[시퀀스] 스텝 {i+1}: {step['desc']}")

                if step["type"] == "WAIT":
                    time.sleep(step["val"] / 1000.0)

                elif step["type"] == "MOVE":
                    spd = step["spd_mm"]
                    cmd_parts = []
                    for ax, dist in step["cmds_mm"]:
                        if abs(dist) < 1e-6: continue
                        steps    = int(abs(dist) * self.steps_per_mm)
                        spd_step = int(spd * self.steps_per_mm)
                        if dist < 0: steps = -steps
                        cmd_parts += [ax, str(steps), str(spd_step)]
                    if cmd_parts:
                        self.arduino.send("ABS:" + ":".join(cmd_parts))
                        # DONE 또는 ALARM 대기
                        t_start = time.time()
                        while self._is_running_seq and not self._emergency:
                            if time.time() - t_start > 60: break
                            time.sleep(0.05)
                            # done_received 시그널이 대신 플래그 세팅하도록 처리
                            if getattr(self, '_done_flag', False):
                                self._done_flag = False; break

            self._is_running_seq = False
            QTimer.singleShot(0, lambda: self.btn_run_seq.setEnabled(True))
            self._log("[시퀀스] 완료")

        self.arduino.done_received.connect(self._on_done)
        t = threading.Thread(target=execute, daemon=True)
        t.start()

    def _on_done(self):
        self._done_flag = True

    # ── 로그 탭 ──────────────────────────────────────────────────────

    def _build_log_tab(self):
        w = QWidget(); vbox = QVBoxLayout(w)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet("background:#1e1e2e; color:#cdd6f4; font-family:Consolas; font-size:11px;")
        vbox.addWidget(self.log_edit)
        btn = QPushButton("지우기"); btn.clicked.connect(self.log_edit.clear)
        vbox.addWidget(btn)
        return w

    # ── 우측 패널 (그래프) ───────────────────────────────────────────

    def _build_right_panel(self):
        w = QWidget(); vbox = QVBoxLayout(w)

        self.pw = pg.GraphicsLayoutWidget()
        titles  = ["인덕턴스 (LDC)", "DC 저항 (R_DC)", "TENG 전압", "R_raw", "TENG_raw"]
        colors  = ["#89b4fa", "#a6e3a1", "#f9e2af", "#cba6f7", "#f38ba8"]
        self._curves = []
        self._plot_items = []

        for i, (title, color) in enumerate(zip(titles, colors)):
            p = self.pw.addPlot(row=i, col=0, title=title)
            p.setLabel("left", "값")
            curve = p.plot(pen=pg.mkPen(color, width=1.5))
            self._curves.append(curve)
            self._plot_items.append(p)
            if i > 0:
                p.setXLink(self._plot_items[0])

        self._plot_items[-1].setLabel("bottom", "시간 (s)")
        vbox.addWidget(self.pw, stretch=1)

        self.lbl_counts = QLabel("STM32 샘플: 0  |  기록: 0행")
        self.lbl_counts.setAlignment(Qt.AlignRight)
        vbox.addWidget(self.lbl_counts)
        return w

    # ── 하단 RECORD 바 ───────────────────────────────────────────────

    def _build_record_bar(self):
        bar = QGroupBox()
        lay = QHBoxLayout(bar)

        self.btn_record = QPushButton("● RECORD")
        self.btn_record.setFixedHeight(38)
        self.btn_record.setCheckable(True)
        self.btn_record.setStyleSheet(
            "QPushButton{background:#f38ba8;color:white;font-weight:bold;font-size:13px;border-radius:5px;}"
            "QPushButton:checked{background:#a6e3a1;color:#1e1e2e;}"
        )
        self.btn_record.clicked.connect(self._toggle_record)
        lay.addWidget(self.btn_record)

        lay.addWidget(QLabel("저장 폴더:"))
        self.lbl_savedir = QLabel(self._save_dir)
        self.lbl_savedir.setStyleSheet("color:#89b4fa;")
        lay.addWidget(self.lbl_savedir, stretch=1)

        btn_browse = QPushButton("폴더 선택")
        btn_browse.clicked.connect(self._browse_dir)
        lay.addWidget(btn_browse)

        lay.addWidget(QLabel("형식:"))
        self.cb_format = QComboBox()
        self.cb_format.addItems(["Excel (.xlsx)", "CSV (.csv)"])
        lay.addWidget(self.cb_format)
        return bar

    # ──────────────────────────────────────────────────────────────────
    # 시그널 연결
    # ──────────────────────────────────────────────────────────────────

    def _connect_signals(self):
        self.stm32.data_received.connect(self._on_stm32_data)
        self.stm32.log_msg.connect(self._log)
        self.arduino.position_updated.connect(self._on_position)
        self.arduino.log_msg.connect(self._log)
        self.arduino.alarm_received.connect(self._on_alarm)

    # ──────────────────────────────────────────────────────────────────
    # 이벤트 핸들러
    # ──────────────────────────────────────────────────────────────────

    def _on_stm32_data(self, ts: float, vals: list):
        if self._t0 is None: self._t0 = ts
        self._ts_buf.append(ts - self._t0)
        for i, v in enumerate(vals):
            self._bufs[i].append(v)
        self.logger.add_sensor(ts, vals)

    def _on_position(self, ts: float, pos: dict):
        self.logger.update_position(pos)
        for ax, mm in pos.items():
            if ax in self.pos_labels:
                self.pos_labels[ax].setText(f"{mm:.3f}")

    def _on_alarm(self, msg: str):
        self._log(f"⚠ {msg}")
        self._is_running_seq = False

    def _refresh_graph(self):
        if len(self._ts_buf) < 2: return
        ts = np.array(self._ts_buf)
        for i, curve in enumerate(self._curves):
            if len(self._bufs[i]) == len(ts):
                curve.setData(ts, np.array(self._bufs[i]))
        n = len(self._ts_buf)
        self.lbl_counts.setText(f"STM32 샘플: {n}  |  기록: {self.logger.row_count()}행")

    # ──────────────────────────────────────────────────────────────────
    # 포트 관리
    # ──────────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for cb in [self.cb_stm32, self.cb_arduino]:
            cur = cb.currentText()
            cb.clear(); cb.addItems(ports)
            if cur in ports: cb.setCurrentText(cur)

    def _toggle_stm32(self):
        if self.stm32.isRunning():
            self.stm32.disconnect(); self.stm32.quit()
            self.btn_stm32.setText("연결")
            self._set_indicator(self.ind_stm32, False)
        else:
            try:
                self.stm32.connect(self.cb_stm32.currentText(), self._settings["baud_stm32"])
                self.stm32.start()
                self.btn_stm32.setText("해제")
                self._set_indicator(self.ind_stm32, True)
                self._log(f"[STM32] {self.cb_stm32.currentText()} 연결됨")
            except Exception as e:
                self._log(f"[STM32 연결 실패] {e}")

    def _toggle_arduino(self):
        if self.arduino.isRunning():
            self.arduino.disconnect(); self.arduino.quit()
            self.btn_arduino.setText("연결")
            self._set_indicator(self.ind_arduino, False)
        else:
            try:
                self.arduino.connect(self.cb_arduino.currentText(), self._settings["baud_arduino"])
                self.arduino.start()
                self.btn_arduino.setText("해제")
                self._set_indicator(self.ind_arduino, True)
                self._log(f"[Arduino] {self.cb_arduino.currentText()} 연결됨")
            except Exception as e:
                self._log(f"[Arduino 연결 실패] {e}")

    # ──────────────────────────────────────────────────────────────────
    # 기능
    # ──────────────────────────────────────────────────────────────────

    def _toggle_emergency(self):
        self._emergency = not self._emergency
        self._is_running_seq = False
        if self._emergency:
            self.arduino.send("EN:0")
            self.btn_emg.setText("⚠ EMG — RESET 클릭")
            self.btn_emg.setStyleSheet("background:#cba6f7; color:white; font-weight:bold; border-radius:4px;")
            self._log("⚠ 비상정지 발동")
        else:
            self.arduino.send("RESET_EMG")
            self.btn_emg.setText("⚠ EMERGENCY")
            self.btn_emg.setStyleSheet("background:#f38ba8; color:white; font-weight:bold; border-radius:4px;")
            self._log("✅ 비상정지 해제")

    def _do_jog(self, axis: str, dist_mm: float):
        if self._emergency:
            self._log("비상정지 상태 — 이동 불가"); return
        s = self._settings
        if s["enable_limits"] and abs(dist_mm) > s["limit_dist"]:
            self._log(f"거리 한계 초과: {abs(dist_mm):.1f} > {s['limit_dist']}mm"); return
        self.arduino.jog(axis, dist_mm, s["jog_speed"])

    def _set_zero(self):
        self.arduino.send("ZERO:0")
        self._log("원점 설정 완료")

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_settings:
            self._settings = dlg.result_settings
            self._apply_settings()
            self._log("설정 적용됨")

    def _toggle_record(self, checked: bool):
        if checked:
            self.logger.start(time.time())
            self.btn_record.setText("■ STOP")
            self._log("▶ 기록 시작")
        else:
            self.logger.stop()
            self.btn_record.setText("● RECORD")
            self._log(f"■ 기록 중지 — {self.logger.row_count()}행")
            self._save_data()

    def _save_data(self):
        if self.logger.row_count() == 0:
            self._log("저장할 데이터 없음"); return
        now  = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext  = ".xlsx" if self.cb_format.currentIndex() == 0 else ".csv"
        path = str(Path(self._save_dir) / f"sync_data_{now}{ext}")
        try:
            self.logger.save(path)
            self._log(f"✅ 저장 완료: {path}")
        except Exception as e:
            self._log(f"❌ 저장 실패: {e}")

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", self._save_dir)
        if d:
            self._save_dir = d
            self.lbl_savedir.setText(d)

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_edit.append(f"[{ts}] {msg}")

    def closeEvent(self, event):
        self.stm32.disconnect(); self.arduino.disconnect()
        self._ui_timer.stop(); event.accept()


# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor("#1e1e2e"))
    palette.setColor(QPalette.WindowText,      QColor("#cdd6f4"))
    palette.setColor(QPalette.Base,            QColor("#181825"))
    palette.setColor(QPalette.Text,            QColor("#cdd6f4"))
    palette.setColor(QPalette.Button,          QColor("#313244"))
    palette.setColor(QPalette.ButtonText,      QColor("#cdd6f4"))
    palette.setColor(QPalette.Highlight,       QColor("#89b4fa"))
    palette.setColor(QPalette.HighlightedText, QColor("#1e1e2e"))
    app.setPalette(palette)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
