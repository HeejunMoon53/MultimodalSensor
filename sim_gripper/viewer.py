"""실시간 3D 뷰어 (오버레이는 MuJoCo 폰트 제약으로 ASCII): 폐루프 시뮬레이션을 MuJoCo 창에서 재생.

python -m sim_gripper.viewer E1_metal                  # 텐던, 실제 파이프라인
python -m sim_gripper.viewer E2_egg --actuator pneumatic --speed 0.5
python -m sim_gripper.viewer --list
python -m sim_gripper.panel                            # 설정 패널(시나리오·옵션 선택, 재시작, 일시정지)
마우스: 왼쪽 드래그 회전, 오른쪽 드래그 이동, 휠 확대. 창 닫으면 종료.
"""
import argparse
import sys
import threading
import time
from pathlib import Path

if __package__ in (None, ""):          # VS Code ▶ 등으로 파일을 직접 실행한 경우
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mujoco
import mujoco.viewer

from sim_gripper.sim.loop import run
from sim_gripper.sim.scenarios import SCENARIOS

FRAME_TICKS = 16          # 1 ms 틱 16개마다 화면 갱신 (~60 Hz)
FRAME_S = FRAME_TICKS / 1000


class _Closed(Exception):
    pass


class PlayControl:
    """재생 제어 상태 — 패널(메인 스레드)과 재생 스레드가 공유."""

    def __init__(self, speed=1.0):
        self.stop, self.paused = threading.Event(), threading.Event()
        self.speed = speed
        self.latest = None        # 마지막 로그 행
        self.done = False
        self.cam = None           # 재시작 시 카메라 유지


def _overlay(row):
    left = "\n".join(["t", "phase"] + [f"finger {i}" for i in range(3)])
    right = [f"{row['t']:.2f} s", row["phase"]]
    for i in range(3):
        est = f"F_hat {row[f'value_{i}']:.2f} N" if row[f"contact_{i}"] else f"d_hat {row[f'value_{i}']:.1f} mm"
        right.append(f"F {row[f'F_true_{i}']:.2f} N | {est} | eps_hat {row[f'eps_hat_{i}']:.1f}% | {row[f'material_{i}']}"
                     + (" | SAFETY" if row[f"safety_{i}"] else ""))
    return left, "\n".join(right)


def play(scenario, actuator="tendon", sensor="pipeline", ctrl=None, keep_open=True):
    """시나리오 하나를 MuJoCo 창에서 재생. ctrl.stop으로 중단, ctrl.paused로 일시정지, ctrl.speed 실시간 변경."""
    ctrl = ctrl or PlayControl()
    st = {"v": None, "next": None}

    def wait_until():
        now = time.perf_counter()
        if st["next"] is None or now - st["next"] > 0.1:     # 처음·지연 누적 시 기준 재설정
            st["next"] = now
        st["next"] += FRAME_S / max(ctrl.speed, 0.05)
        while time.perf_counter() < st["next"]:
            time.sleep(min(0.005, max(0.0, st["next"] - time.perf_counter())))

    def on_step(sim, row):
        if round(row["t"] * 1000) % FRAME_TICKS:
            return
        v = st["v"]
        if v is None:
            v = st["v"] = mujoco.viewer.launch_passive(sim.model, sim.data)
            if ctrl.cam:
                v.cam.lookat[:], (v.cam.distance, v.cam.azimuth, v.cam.elevation) = ctrl.cam
            else:
                v.cam.lookat[:] = (0, 0, 0.05)
                v.cam.distance, v.cam.elevation, v.cam.azimuth = 0.35, -20, 60
        ctrl.latest = row
        while ctrl.paused.is_set() and not ctrl.stop.is_set() and v.is_running():
            v.sync()
            time.sleep(0.03)
            st["next"] = None
        if ctrl.stop.is_set() or not v.is_running():
            raise _Closed
        with v.lock():
            v.set_texts((mujoco.mjtFontScale.mjFONTSCALE_150, mujoco.mjtGridPos.mjGRID_TOPLEFT, *_overlay(row)))
        v.sync()
        wait_until()

    try:
        run(SCENARIOS[scenario], actuator=actuator, sensor_mode=sensor, on_step=on_step)
        ctrl.done = True
        while keep_open and st["v"] is not None and st["v"].is_running() and not ctrl.stop.is_set():
            time.sleep(0.1)
    except _Closed:
        pass
    finally:
        v = st["v"]
        if v is not None:
            ctrl.cam = (v.cam.lookat.copy(), (v.cam.distance, v.cam.azimuth, v.cam.elevation))
            v.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", nargs="?", default="E1_metal")
    ap.add_argument("--actuator", default="tendon", choices=["tendon", "pneumatic"])
    ap.add_argument("--sensor", default="pipeline", choices=["pipeline", "ideal"])
    ap.add_argument("--speed", type=float, default=1.0, help="재생 배속 (1 = 실시간)")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        print("\n".join(SCENARIOS))
        return
    play(a.scenario, a.actuator, a.sensor, PlayControl(a.speed))
    print("종료")


if __name__ == "__main__":
    main()
