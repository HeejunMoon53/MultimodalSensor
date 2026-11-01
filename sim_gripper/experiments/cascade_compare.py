"""기존 제어기(u 직접) vs 캐스케이드(인장 내부 루프 + 근접·힘 외부 루프) 비교 — 시뮬레이션.

python -m sim_gripper.experiments.cascade_compare  →  sim_gripper/out/cascade/
판형 95A 손가락만 (벨로즈는 센서가 중립축 근처 h = 0.5 mm라 굽힘 인장 변화 ~0.5 % → 내부 루프 불가).
"""
import json
import pickle
from dataclasses import replace
from pathlib import Path

import numpy as np

from sim_gripper.experiments.calibrated import make_gripper_moe
from sim_gripper.experiments.run_all import compute_metrics
from sim_gripper.perception.moe import DEFAULT_PKL
from sim_gripper.sim.loop import CONTACT_F, run
from sim_gripper.sim.scenarios import SCENARIOS, Scenario

OUT = Path(__file__).resolve().parents[1] / "out" / "cascade"
OFFSET = (0.008, 0.0)          # 물체 중심 오프셋 [m] — 정렬 비교
GRID = {"E1_metal": SCENARIOS["E1_metal"],
        "E2_egg": SCENARIOS["E2_egg"],
        "E3_sponge": SCENARIOS["E3_sponge"],
        "E4_disturb": SCENARIOS["E4_disturb"],
        "E7_offset_metal": Scenario("E7_offset_metal", replace(SCENARIOS["E1_metal"].obj, xy=OFFSET)),
        "E7_offset_egg": Scenario("E7_offset_egg", replace(SCENARIOS["E2_egg"].obj, xy=OFFSET))}
MODES = ("baseline", "sync", "cascade")


def grasp_metrics(df):
    """정렬: 세 손가락 실제 접촉 시각 차(arrival_spread_s), 접촉까지 물체가 밀린 거리(push_mm)."""
    m = compute_metrics(df)
    t_touch = [df.t[df[f"F_true_{i}"] > CONTACT_F] for i in range(3)]
    if all(len(t) for t in t_touch):
        first = [float(t.iloc[0]) for t in t_touch]
        m["arrival_spread_s"] = max(first) - min(first)
        k = df.index[df.t >= max(first)][0]
        xy0 = np.array([df.obj_x.iloc[0], df.obj_y.iloc[0]])
        m["push_mm"] = float(np.linalg.norm(np.array([df.obj_x[k], df.obj_y[k]]) - xy0) * 1000)
    else:
        m["arrival_spread_s"], m["push_mm"] = float("nan"), float("nan")
    return m


def compare(out_dir=OUT, actuators=("tendon", "pneumatic"), grid=GRID, estimators=("calibrated", "v4"),
            modes=MODES):
    """estimators: "ideal"(참값 + 노이즈: 제어 구조만 비교) / "calibrated"(그리퍼 보정 MoE, 논문 메인) /
    "v4"(0909 실측 학습 그대로)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    models = {"v4": pickle.loads(DEFAULT_PKL.read_bytes()), "ideal": None}
    if "calibrated" in estimators:
        models["calibrated"] = make_gripper_moe()
    res = {}
    for est in estimators:
        for act in actuators:
            for name, sc in grid.items():
                for mode in modes:
                    key = f"{name}|{act}|{est}|{mode}"
                    df, _ = run(sc, actuator=act, moe_models=models[est] or models["v4"], ctrl_mode=mode,
                                sensor_mode="ideal" if est == "ideal" else "pipeline")
                    df.to_pickle(out_dir / f"log_{key.replace('|', '_')}.pkl")
                    res[key] = grasp_metrics(df)
                    print(key, {k: round(v, 3) if isinstance(v, float) else v for k, v in res[key].items()},
                          flush=True)
    (out_dir / "metrics.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


def seed_sweep(out_dir=OUT, actuators=("tendon", "pneumatic"), grid=GRID, modes=MODES, seeds=range(5)):
    """보정 MoE, TDM 노이즈 seed 반복 — 단일 런 성공/실패는 궤적 미세 차이에 민감 (금속 HOLD 중 Ḟ 트립)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    models = make_gripper_moe()
    res = {}
    for act in actuators:
        for name, sc in grid.items():
            for mode in modes:
                for seed in seeds:
                    df, _ = run(sc, actuator=act, moe_models=models, ctrl_mode=mode, seed=seed)
                    res[f"{name}|{act}|{mode}|{seed}"] = grasp_metrics(df)
                    print(name, act, mode, seed, int(res[f"{name}|{act}|{mode}|{seed}"]["success"]), flush=True)
    (out_dir / "seeds.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def summarize_seeds(seeds):
    """{(act, mode): (성공 수, 런 수)}"""
    out = {}
    for k, v in seeds.items():
        _, act, mode, _ = k.split("|")
        ok, n = out.get((act, mode), (0, 0))
        out[(act, mode)] = (ok + int(v["success"]), n + 1)
    return out


C_MODE = {"baseline": "#7F7F7F", "sync": "#9467BD", "cascade": "#8C564B"}   # 동기 = 근접(d̂) 보라, 캐스케이드 = 인장 갈색
LABEL = {"baseline": "baseline (u direct)", "sync": "baseline + sync approach",
         "cascade": "cascade (strain inner loop)"}


def plot_compare(res, out_dir=OUT, act="tendon", seeds=None, fig_dir=None):
    """F11: (a) 치우친 계란 접근 — 손가락별 거리 (보정 MoE), (b) 물체 밀림, (c) 추정기별 성공률.
    seeds가 있으면 (c)의 보정 MoE 막대는 seed 반복 성공률."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out_dir = Path(out_dir)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7, "axes.unicode_minus": False})
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.5), gridspec_kw=dict(width_ratios=[1.2, 1, 1.1]))
    ax = axs[0]
    for mode in ("baseline", "sync"):
        df = pd_read(out_dir / f"log_E7_offset_egg_{act}_calibrated_{mode}.pkl")
        win = df[(df.t > 0.4) & (df.t < 1.6)]
        for i in range(3):
            ax.plot(win.t, win[f"d_true_{i}"], color=C_MODE[mode], lw=1.0, ls=("-", "--", ":")[i],
                    label=LABEL[mode] if i == 0 else None)
    for i, ls in enumerate(("-", "--", ":")):
        ax.plot([], [], color="#333333", lw=0.8, ls=ls, label=f"finger {i}")
    ax.set_xlabel("time [s]"), ax.set_ylabel("pad–object distance [mm]")
    ax.set_title("(a) off-centre egg (8 mm), true distance", fontsize=7, loc="left")
    ax.legend(fontsize=5.2, frameon=False)
    ax = axs[1]
    names = ["E1_metal", "E2_egg", "E3_sponge", "E7_offset_metal", "E7_offset_egg"]
    x = np.arange(len(names))
    w = 0.8 / len(MODES)
    for k, mode in enumerate(MODES):
        v = [res[f"{n}|{act}|calibrated|{mode}"]["push_mm"] for n in names]
        ax.bar(x + (k - (len(MODES) - 1) / 2) * w, v, w * 0.95, color=C_MODE[mode], label=LABEL[mode],
               edgecolor="white", lw=1)
    ax.set_xticks(x, [n.split("_", 1)[1].replace("_", "\n") for n in names], fontsize=5.6)
    ax.set_ylabel("object push until all fingers touch [mm]")
    ax.set_title("(b) object push (calibrated MoE)", fontsize=7, loc="left")
    ax.legend(fontsize=5.2, frameon=False)
    ax = axs[2]
    ests = ["ideal", "calibrated", "v4"]
    ss = summarize_seeds(seeds) if seeds else {}
    for k, mode in enumerate(MODES):
        ok = [np.mean([res[f"{n}|{act}|{e}|{mode}"]["success"] for n in GRID]) * 100 for e in ests]
        if (act, mode) in ss:
            ok[1] = 100 * ss[(act, mode)][0] / ss[(act, mode)][1]
        xk = np.arange(3) + (k - (len(MODES) - 1) / 2) * w
        ax.bar(xk, ok, w * 0.95, color=C_MODE[mode], edgecolor="white", lw=1)
        for j, val in enumerate(ok):
            ax.text(xk[j], val + 2, f"{val:.0f}", ha="center", fontsize=5.0)
    n_seed = len({k.split("|")[3] for k in seeds}) if seeds else 1
    ax.set_xticks(range(3), ["ideal\n(true + noise)", f"calibrated MoE\n({n_seed} seeds)" if seeds else "calibrated\nMoE",
                             "v4 MoE\n(0909 only)"], fontsize=5.6)
    ax.set_ylabel("grasp success [%]"), ax.set_ylim(0, 115)
    ax.set_title(f"(c) success over {len(GRID)} scenarios", fontsize=7, loc="left")
    for a in axs:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig_dir = Path(fig_dir or out_dir)
    fig_dir.mkdir(parents=True, exist_ok=True)
    path = fig_dir / f"fig11_cascade_compare_{act}.png"
    fig.savefig(path, dpi=300)
    fig.savefig(path.with_suffix(".svg"))
    plt.close(fig)
    return path


def load():
    """저장된 결과 (compare, seed_sweep) — 그림만 다시 그릴 때."""
    res = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
    p = OUT / "seeds.json"
    return res, (json.loads(p.read_text(encoding="utf-8")) if p.exists() else None)


def pd_read(p):
    import pandas as pd
    return pd.read_pickle(p)


if __name__ == "__main__":
    r = compare(estimators=("ideal", "calibrated", "v4"))
    s = seed_sweep()
    for a in ("tendon", "pneumatic"):
        plot_compare(r, act=a, seeds=s)
