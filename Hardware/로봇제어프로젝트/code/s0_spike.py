"""스파이크 S0 (스펙 2.2·6절): flex 손가락 보정과 모델 결정.

1) young 이분 탐색: 30 kPa 정상 상태 끝단 굽힘 300 ± 15°
2) p = 0..30 kPa(5 간격) 굽힘·체적·센서 ε (센서 깊이 0.5 / 2.0 / 3.5 mm)
3) 판정: 발산 없음 + 1 s 시뮬 ≤ 20 s 벽시계 → flex, 아니면 prbm
결과 → params.json["plant"], 그림 → out/S0_calib.png  (시뮬레이션)
"""
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mujoco
import numpy as np

from finger_flex import FlexFinger, build_single
from paths import OUT, load_params, save_params

DT = 2e-3
TARGET, TOL = 300.0, 15.0


def hold(f, m, d, p, sec):
    for _ in range(int(sec / DT)):
        f.apply_pressure(d, p)
        mujoco.mj_step(m, d)
    if not np.isfinite(f._X(d)).all():
        raise FloatingPointError("flex diverged")


def ramp_to(f, m, d, p0, p1, sec=1.0):
    n = int(sec / DT)
    for k in range(n):
        f.apply_pressure(d, p0 + (p1 - p0) * (k + 1) / n)
        mujoco.mj_step(m, d)


def angle_at_30(E):
    f = FlexFinger(young_pa=E); m, d = build_single(f, dt=DT)
    ramp_to(f, m, d, 0, 30); hold(f, m, d, 30, 1.5)
    return f.tip_angle(d)


def calibrate(grid=(3.6e4, 4.0e4, 4.5e4, 5.0e4)):
    """격자 탐색. 이분 탐색은 young < 약 35 kPa 에서 좌굴(비단조)로 실패해 쓰지 않는다."""
    log = []
    for E in grid:
        a = angle_at_30(E)
        log.append((E, a))
        print(f"  young {E:9.0f} Pa → {a:6.1f}°", flush=True)
    ok = [r for r in log if 0 < r[1] < 400]
    return min(ok or log, key=lambda r: abs(r[1] - TARGET))[0], log


def curve(E, sensor_z):
    f = FlexFinger(young_pa=E, sensor_z_mm=sensor_z); m, d = build_single(f, dt=DT)
    rows, p_prev = [], 0.0
    t0, sim = time.time(), 0.0
    for p in range(0, 31, 5):
        ramp_to(f, m, d, p_prev, p, 0.5); hold(f, m, d, p, 1.0)
        sim += 1.5; p_prev = p
        rows.append((p, f.tip_angle(d), f.chamber_volume(d), f.sensor_strain(d)))
    return np.array(rows), (time.time() - t0) / sim


def main():
    print("S0: young 보정 (30 kPa → 300°)")
    E, log = calibrate()
    curves, speed, diverged = {}, [], False
    for z in (0.5, 2.0, 3.5):
        try:
            c, s = curve(E, z)
        except FloatingPointError:
            diverged = True
            break
        curves[z], _ = c, speed.append(s)
        print(f"  sensor_z {z} mm: ε(30 kPa) = {c[-1, 3]:.2f} %, 벽시계/시뮬 = {s:.1f}", flush=True)
    model = "flex" if (not diverged and max(speed) <= 20.0) else "prbm"
    c2 = curves.get(2.0)
    plant = load_params().get("plant", {})
    plant.update(young_pa=float(E), poisson=0.3, sensor_z_mm=2.0, dt_sim=DT, model=model,
                 calib_log=[[float(a), float(b)] for a, b in log],
                 V_of_p=c2[:, [0, 2]].tolist() if c2 is not None else [],
                 angle_of_p=c2[:, [0, 1]].tolist() if c2 is not None else [],
                 eps_of_p={str(z): c[:, [0, 3]].tolist() for z, c in curves.items()},
                 wall_per_sim_s=float(max(speed)) if speed else None)
    eps_min = min(float(c[:, 3].min()) for c in curves.values()) if curves else 0.0
    plant["eps_prestrain"] = float(-eps_min + 1.0) if eps_min < 0 else 0.0
    save_params("plant", plant)

    if c2 is not None:
        fig, ax = plt.subplots(1, 3, figsize=(12, 3.4))
        ax[0].plot(c2[:, 0], c2[:, 1], "o-", color="#444"); ax[0].axhline(TARGET, ls="--", c="gray")
        ax[0].set(xlabel="압력 p [kPa]", ylabel="끝단 굽힘 [°]")
        ax[1].plot(c2[:, 0], c2[:, 2] / 1e3, "o-", color="#7a4ea3")
        ax[1].set(xlabel="압력 p [kPa]", ylabel="방 체적 V [cm³]")
        for z, c in curves.items():
            ax[2].plot(c[:, 0], c[:, 3], "o-", label=f"센서 깊이 {z} mm")
        ax[2].set(xlabel="압력 p [kPa]", ylabel="센서 변형률 ε [%]"); ax[2].legend(fontsize=8)
        fig.suptitle(f"S0 flex 보정 (시뮬레이션): young = {E/1e3:.0f} kPa, ν = 0.3", fontsize=10)
        plt.rcParams["font.family"] = "Malgun Gothic"
        fig.tight_layout(); OUT.mkdir(exist_ok=True); fig.savefig(OUT / "S0_calib.png", dpi=150)
    print(f"S0 판정: model={model}, young={E:.0f} Pa, 벽시계/시뮬={plant['wall_per_sim_s']}, "
          f"prestrain={plant['eps_prestrain']:.2f} %")


if __name__ == "__main__":
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    main()
