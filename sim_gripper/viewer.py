"""실시간 3D 뷰어 (오버레이는 MuJoCo 폰트 제약으로 ASCII): 폐루프 시뮬레이션을 MuJoCo 창에서 재생.

python -m sim_gripper.viewer E1_metal                  # 텐던, 실제 파이프라인
python -m sim_gripper.viewer E2_egg --actuator pneumatic --speed 0.5
python -m sim_gripper.viewer --list
마우스: 왼쪽 드래그 회전, 오른쪽 드래그 이동, 휠 확대. 스페이스 일시정지는 지원 안 함(창 닫으면 종료).
"""
import argparse
import time

import mujoco
import mujoco.viewer

from sim_gripper.sim.loop import run
from sim_gripper.sim.scenarios import SCENARIOS

FRAME_TICKS = 16          # 1 ms 틱 16개마다 화면 갱신 (~60 Hz)


class _Closed(Exception):
    pass


def _overlay(row):
    left = "\n".join(["t", "phase"] + [f"finger {i}" for i in range(3)])
    right = [f"{row['t']:.2f} s", row["phase"]]
    for i in range(3):
        est = f"F_hat {row[f'value_{i}']:.2f} N" if row[f"contact_{i}"] else f"d_hat {row[f'value_{i}']:.1f} mm"
        right.append(f"F {row[f'F_true_{i}']:.2f} N | {est} | eps_hat {row[f'eps_hat_{i}']:.1f}% | {row[f'material_{i}']}"
                     + (" | SAFETY" if row[f"safety_{i}"] else ""))
    return left, "\n".join(right)


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

    state = {"viewer": None, "t0": None}

    def on_step(sim, row):
        k = round(row["t"] * 1000)
        if k % FRAME_TICKS:
            return
        v = state["viewer"]
        if v is None:
            v = state["viewer"] = mujoco.viewer.launch_passive(sim.model, sim.data)
            v.cam.lookat[:] = (0, 0, 0.05)
            v.cam.distance, v.cam.elevation, v.cam.azimuth = 0.35, -20, 60
            state["t0"] = time.perf_counter()
        if not v.is_running():
            raise _Closed
        with v.lock():
            v.set_texts((mujoco.mjtFontScale.mjFONTSCALE_150, mujoco.mjtGridPos.mjGRID_TOPLEFT, *_overlay(row)))
        v.sync()
        lag = row["t"] / a.speed - (time.perf_counter() - state["t0"])
        if lag > 0:
            time.sleep(lag)

    try:
        run(SCENARIOS[a.scenario], actuator=a.actuator, sensor_mode=a.sensor, on_step=on_step)
        print("시뮬레이션 끝: 창을 닫으면 종료")
        while state["viewer"] is not None and state["viewer"].is_running():
            time.sleep(0.1)
    except _Closed:
        pass
    finally:
        if state["viewer"] is not None:
            state["viewer"].close()


if __name__ == "__main__":
    main()
