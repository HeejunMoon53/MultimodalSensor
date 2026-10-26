"""시뮬레이션 설정 패널: 시나리오·액추에이터·센서·배속을 고르고 MuJoCo 창에서 재생.

python -m sim_gripper.panel
[실행/재시작]은 현재 설정으로 처음부터 다시, [일시정지]는 토글, 배속은 재생 중에도 바로 반영.
"""
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim_gripper.sim.scenarios import SCENARIOS
from sim_gripper.viewer import PlayControl, play

DESC = {
    "E1_metal": "금속 원통 (도체, 0.2 kg)", "E2_hand": "손 (유전체, 말랑함)", "E2_egg": "계란 (3.5 N 넘으면 파손)",
    "E3_sponge": "스펀지 (유전체, 말랑함)", "E3_small": "작은 금속 원통 (지름 30 mm)",
    "E3_large": "큰 금속 원통 (지름 70 mm)", "E4_disturb": "금속 원통 + 6~7 s 수평 3 N 외란",
}
PHASE_KO = {"OPEN": "개방", "APPROACH": "접근", "GRASP": "파지", "HOLD": "리프트·유지", "RELEASE": "해제"}
MAT_KO = {"unknown": "미정", "conductor": "도체", "dielectric": "유전체"}


class Panel:
    def __init__(self, root):
        self.root, self.ctrl, self.thread = root, None, None
        root.title("소프트 그리퍼 시뮬레이션")
        root.resizable(False, False)
        f = ttk.Frame(root, padding=12)
        f.grid()

        self.scen = tk.StringVar(value="E1_metal")
        self.act = tk.StringVar(value="tendon")
        self.sens = tk.StringVar(value="pipeline")
        self.speed = tk.DoubleVar(value=1.0)

        ttk.Label(f, text="시나리오").grid(row=0, column=0, sticky="w")
        names = list(SCENARIOS)
        cb = ttk.Combobox(f, values=[f"{n} — {DESC.get(n, '')}" for n in names], state="readonly", width=42)
        cb.current(0)
        cb.bind("<<ComboboxSelected>>", lambda e: self.scen.set(names[cb.current()]))
        cb.grid(row=0, column=1, columnspan=3, sticky="we", pady=2)

        ttk.Label(f, text="액추에이터").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(f, text="텐던", variable=self.act, value="tendon").grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(f, text="공압", variable=self.act, value="pneumatic").grid(row=1, column=2, sticky="w")

        ttk.Label(f, text="센서").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(f, text="전체 파이프라인 (v4 MoE)", variable=self.sens, value="pipeline").grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(f, text="이상 센서", variable=self.sens, value="ideal").grid(row=2, column=2, sticky="w")

        ttk.Label(f, text="배속").grid(row=3, column=0, sticky="w")
        ttk.Scale(f, from_=0.1, to=3.0, variable=self.speed, command=self._speed_changed,
                  length=220).grid(row=3, column=1, columnspan=2, sticky="we")
        self.speed_lbl = ttk.Label(f, text="1.0×", width=6)
        self.speed_lbl.grid(row=3, column=3, sticky="w")

        b = ttk.Frame(f)
        b.grid(row=4, column=0, columnspan=4, pady=(8, 6), sticky="we")
        ttk.Button(b, text="▶ 실행 / 재시작", command=self.start).pack(side="left", expand=True, fill="x", padx=2)
        self.pause_btn = ttk.Button(b, text="⏸ 일시정지", command=self.toggle_pause)
        self.pause_btn.pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(b, text="■ 정지", command=self.stop).pack(side="left", expand=True, fill="x", padx=2)

        self.status = ttk.Label(f, text="설정을 고르고 [실행]을 누르세요.", font=("맑은 고딕", 10, "bold"))
        self.status.grid(row=5, column=0, columnspan=4, sticky="w", pady=(4, 2))
        self.rows = []
        hdr = ["손가락", "실제 F [N]", "센서 추정", "ε̂ [%]", "재질", "안전"]
        for c, h in enumerate(hdr):
            ttk.Label(f, text=h, foreground="#555").grid(row=6, column=c if c < 4 else c, sticky="w", padx=3)
        for i in range(3):
            labels = [ttk.Label(f, text=str(i), width=w) for w in (6, 10, 14, 8, 8, 6)]
            for c, l in enumerate(labels):
                l.grid(row=7 + i, column=c, sticky="w", padx=3)
            self.rows.append(labels)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._poll()

    def _speed_changed(self, _=None):
        v = round(self.speed.get(), 1)
        self.speed_lbl.config(text=f"{v}×")
        if self.ctrl:
            self.ctrl.speed = v

    def start(self):
        self.stop()
        cam = self.ctrl.cam if self.ctrl else None
        self.ctrl = PlayControl(round(self.speed.get(), 1))
        self.ctrl.cam = cam
        args = (self.scen.get(), self.act.get(), self.sens.get(), self.ctrl)
        self.thread = threading.Thread(target=play, args=args, daemon=True)
        self.thread.start()
        self.pause_btn.config(text="⏸ 일시정지")

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.ctrl.stop.set()
            self.thread.join(timeout=5)
        self.thread = None

    def toggle_pause(self):
        if not self.ctrl:
            return
        if self.ctrl.paused.is_set():
            self.ctrl.paused.clear()
            self.pause_btn.config(text="⏸ 일시정지")
        else:
            self.ctrl.paused.set()
            self.pause_btn.config(text="▶ 계속")

    def _poll(self):
        c = self.ctrl
        row = c.latest if c else None
        if row is not None:
            state = "끝 (창은 열려 있음)" if c.done else ("일시정지" if c.paused.is_set() else "재생 중")
            if not (self.thread and self.thread.is_alive()):
                state = "정지됨"
            self.status.config(text=f"{self.scen.get()} | t = {row['t']:.2f} s | {PHASE_KO.get(row['phase'], row['phase'])}"
                                    f" | {state}" + (" | 계란 파손!" if row["broken"] else ""))
            for i, labels in enumerate(self.rows):
                v = row[f"value_{i}"]
                est = f"F̂ {v:.2f} N" if row[f"contact_{i}"] else f"d̂ {v:.1f} mm"
                vals = [str(i), f"{row[f'F_true_{i}']:.2f}", est, f"{row[f'eps_hat_{i}']:.1f}",
                        MAT_KO.get(row[f"material_{i}"], row[f"material_{i}"]), "작동" if row[f"safety_{i}"] else "-"]
                for l, t in zip(labels, vals):
                    l.config(text=t)
        self.root.after(100, self._poll)

    def close(self):
        self.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    Panel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
