"""장착 도메인 시프트 + 적응 방법 비교 (M7). 시뮬레이션 내 방법론 시연이며 실물 근거 아님.

시프트: ε 오프셋 δε, 굽힘 결합 γ·κ̄ (ΔL), 감도 스케일 s.
적응: recal(스케일러+선형 보정) / finetune(warm start) / mixed(+0909 동량) / scratch(처음부터).
평가: 홀드아웃 그리퍼 데이터 R² + 0909 test 셋 R²(망각).
python -m sim_gripper.experiments.domain_shift
"""
import copy
import json
import pickle
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler

from sim_gripper.experiments.run_all import OUT, compute_metrics
from sim_gripper.perception.moe import DEFAULT_PKL, EMA_ALPHA, mlp_forward
from sim_gripper.sensor.build_tables import NEW_DIR
from sim_gripper.sensor.forward import DomainShift
from sim_gripper.sim.loop import run
from sim_gripper.sim.scenarios import SCENARIOS
from sim_gripper.viz import plots  # noqa: F401  (한글 폰트 rcParams)

DEFAULT_SHIFT = DomainShift(d_eps=3.0, gamma=0.2, scale=1.1)
SIM_SCENARIOS = ("E1_metal", "E2_hand", "E3_small")
FEAT = ["dL", "dR", "dL_ema", "dR_ema"]
DOWNSAMPLE = 10            # 1 kHz → 100 Hz
METHODS = ("recal", "finetune", "mixed", "scratch")
METHOD_COLORS = {"recal": "#8C564B", "finetune": "#7B4FBF", "mixed": "#D62728", "scratch": "#17BECF"}


# ── 데이터 ────────────────────────────────────────────────────────────────
def _finger_frame(df, i):
    f = pd.DataFrame({"dL": df[f"dL_{i}"].values, "dR": df[f"dR_{i}"].values,
                      "strain": df[f"eps_true_{i}"].values, "dist": df[f"d_true_{i}"].clip(upper=24.0).values,
                      "force": df[f"F_true_{i}"].values, "contact": (df[f"F_true_{i}"] > 0.05).astype(int).values})
    # 펌웨어 EMA (1 kHz, 접촉 상태 전이 시 리셋) — 다운샘플 전에 계산
    ema = np.empty((len(f), 2))
    x, c = f[["dL", "dR"]].values, f.contact.values
    for k in range(len(f)):
        ema[k] = x[k] if k == 0 or c[k] != c[k - 1] else ema[k - 1] + EMA_ALPHA * (x[k] - ema[k - 1])
    f["dL_ema"], f["dR_ema"] = ema[:, 0], ema[:, 1]
    return f.iloc[::DOWNSAMPLE]


def collect_sim_data(shift, n_samples, seed):
    frames, s = [], seed
    while sum(len(f) for f in frames) < n_samples:
        for name in SIM_SCENARIOS:
            df, _ = run(SCENARIOS[name], shift=shift, seed=s)
            frames += [_finger_frame(df, i) for i in range(3)]
        s += 1
    data = pd.concat(frames, ignore_index=True)
    return data.sample(n=n_samples, random_state=seed).reset_index(drop=True)


def load_flat():
    """0909 평면 데이터: retrain_moe_v4.py 1~3단계 재현 → (train, test)."""
    sessions = {"214746": "moe_monitor_20260909_214746.csv", "222022": "moe_monitor_20260909_222022.csv",
                "220210": "moe_monitor_20260909_220210.csv"}
    frames = []
    for sid, fn in sessions.items():
        d = pd.read_csv(NEW_DIR / fn)
        d = d[d["mode"].isin([0, 1])].reset_index(drop=True)
        ok = np.where(d["mode"] == 1, d["value"].between(-20, 20), d["value"].between(-20, 30))
        d = d[d.gate_proba.between(0, 1) & (d.dL_pct.abs() < 50) & (d.dR_pct.abs() < 50)
              & (d.dV_pct.abs() < 200) & d.strain_act_pct.between(-5, 35) & ok].reset_index(drop=True)
        d["session_id"] = sid
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    prox = df.Z_mm + 24.0
    df["contact"] = (prox <= 0.3).astype(int)
    off = df.loc[df.contact == 0, "Fz_act_N"].mean()
    df = df.assign(dL=df.dL_pct, dR=df.dR_pct, strain=df.strain_act_pct, dist=prox, force=-(df.Fz_act_N - off))
    df = df[~((df.contact == 1) & (df.strain >= 14.0))].reset_index(drop=True)
    seg = ((df.contact != df.contact.shift(1)) | (df.session_id != df.session_id.shift(1))).cumsum()
    hl = pd.Timedelta(seconds=1.0125 * 0.6931)
    for col in ("dL", "dR"):
        df[f"{col}_ema"] = 0.0
        for _, g in df.groupby(seg):
            times = pd.to_datetime(g.t_s.values, unit="s")
            df.loc[g.index, f"{col}_ema"] = pd.Series(g[col].values, index=times).ewm(halflife=hl, times=times).mean().values
    cyc = df.session_id + "_" + (df.t_s // 10.0).astype(int).astype(str)
    test_ids = set(sorted(cyc.unique())[4::5])
    cols = FEAT + ["strain", "dist", "force", "contact"]
    return df.loc[~cyc.isin(test_ids), cols].reset_index(drop=True), df.loc[cyc.isin(test_ids), cols].reset_index(drop=True)


# ── 예측·평가 ──────────────────────────────────────────────────────────────
def _expert(models, k, X):
    y = mlp_forward(models[f"expert_{k}"], (X - models[f"sc_{k}"].mean_) / models[f"sc_{k}"].scale_)
    return models[f"lin_{k}"].predict(y) if f"lin_{k}" in models else y


def _r2(y, p):
    ss = np.sum((y - y.mean()) ** 2)
    return float(1 - np.sum((y - p) ** 2) / ss) if len(y) > 1 and ss > 0 else float("nan")


def evaluate(models, data):
    X = data[FEAT].values
    sg = models["sc_gate"]
    gate = (mlp_forward(models["gate"], (X[:, :2] - sg.mean_) / sg.scale_).ravel() >= 0.5).astype(int)
    ya, yb = _expert(models, "a", X), _expert(models, "b", X)
    strain = np.where(gate == 1, yb[:, 0], ya[:, 0])
    c = data.contact.values.astype(bool)
    return {"strain_r2": _r2(data.strain.values, strain),
            "dist_r2": _r2(data.dist.values[~c], ya[~c, 1]),
            "force_r2": _r2(data.force.values[c], yb[c, 1]),
            "gate_acc": float(np.mean(gate == data.contact.values))}


# ── 적응 ──────────────────────────────────────────────────────────────────
def _parts(data):
    a, b = data[data.contact == 0], data[data.contact == 1]
    return {"gate": (data[["dL", "dR"]].values, data.contact.values),
            "expert_a": (a[FEAT].values, a[["strain", "dist"]].values),
            "expert_b": (b[FEAT].values, b[["strain", "force"]].values)}


SCALER = {"gate": "sc_gate", "expert_a": "sc_a", "expert_b": "sc_b"}


def adapt(method, base, data, flat=None):
    m = copy.deepcopy(base)
    if method == "mixed":
        data = pd.concat([data, flat.sample(n=len(data), random_state=0)], ignore_index=True)
    parts = _parts(data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        for key, (X, Y) in parts.items():
            if len(X) < 10 or (key == "gate" and len(np.unique(Y)) < 2):
                continue
            sk = SCALER[key]
            if method == "recal":
                m[sk] = StandardScaler().fit(X)
                if key != "gate":
                    k = key[-1]
                    raw = mlp_forward(m[key], m[sk].transform(X))
                    m[f"lin_{k}"] = LinearRegression().fit(raw, Y)
            elif method in ("finetune", "mixed"):
                m[key].set_params(warm_start=True, learning_rate_init=1e-4, max_iter=200, early_stopping=False)
                if getattr(m[key], "best_loss_", None) is None:   # early_stopping으로 학습된 모델은 None
                    m[key].best_loss_ = np.inf
                m[key].fit(m[sk].transform(X), Y)
            elif method == "scratch":
                cls = MLPClassifier if key == "gate" else MLPRegressor
                m[sk] = StandardScaler().fit(X)
                m[key] = cls(hidden_layer_sizes=base[key].hidden_layer_sizes, activation="tanh", solver="adam",
                             max_iter=2000, random_state=0, early_stopping=True, n_iter_no_change=30)
                m[key].fit(m[sk].transform(X), Y)
            else:
                raise ValueError(method)
    return m


# ── 실험 ──────────────────────────────────────────────────────────────────
def run_domain_shift(out_dir=OUT, n_list=(500, 2000, 8000, 20000)):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_PKL, "rb") as f:
        base = pickle.load(f)
    flat_train, flat_test = load_flat()
    pool = collect_sim_data(DEFAULT_SHIFT, max(n_list), seed=0)
    test_shift = collect_sim_data(DEFAULT_SHIFT, 3000, seed=50)
    test_clean = collect_sim_data(DomainShift(), 3000, seed=50)
    res = {"shift": DEFAULT_SHIFT.__dict__, "v4_clean": evaluate(base, test_clean),
           "v4_shift": evaluate(base, test_shift), "v4_flat": evaluate(base, flat_test), "methods": {}}
    adapted = {}
    for meth in METHODS:
        res["methods"][meth] = {}
        for n in n_list:
            m = adapt(meth, base, pool.iloc[:n], flat_train)
            res["methods"][meth][n] = {"sim": evaluate(m, test_shift), "flat": evaluate(m, flat_test)}
            adapted[(meth, n)] = m
            print(meth, n, res["methods"][meth][n], flush=True)
    # 폐루프 시연: 시프트된 E1 금속 — v4 vs finetune(n=8000)
    demo_n = 8000 if 8000 in n_list else n_list[-1]
    res["closed_loop_E1_shift"] = {
        "v4": compute_metrics(run(SCENARIOS["E1_metal"], shift=DEFAULT_SHIFT, moe_models=base)[0]),
        f"finetune_{demo_n}": compute_metrics(run(SCENARIOS["E1_metal"], shift=DEFAULT_SHIFT,
                                                  moe_models=adapted[("finetune", demo_n)])[0])}
    (out_dir / "domain_shift.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    plot_recovery(res, n_list, out_dir / "domain_shift_recovery.png")
    return res


def plot_recovery(res, n_list, path):
    panels = [("sim", "strain_r2", "그리퍼 ε R²"), ("sim", "dist_r2", "그리퍼 d R²"),
              ("sim", "force_r2", "그리퍼 F R²"), ("flat", "strain_r2", "0909 평면 ε R² (망각)")]
    fig, axs = plt.subplots(1, 4, figsize=(14, 3.6), sharex=True)
    for ax, (dom, key, title) in zip(axs, panels):
        for meth in METHODS:
            ys = [res["methods"][meth][n][dom][key] for n in n_list]
            ax.plot(n_list, ys, marker="o", ms=4, lw=1.5, color=METHOD_COLORS[meth], label=meth)
        ref = res["v4_flat"][key] if dom == "flat" else res["v4_shift"][key]
        ax.axhline(ref, color="#333333", ls="--", lw=1, label="v4 (시프트)" if dom == "sim" else "v4")
        if dom == "sim":
            ax.axhline(res["v4_clean"][key], color="#333333", ls=":", lw=1, label="v4 (시프트 없음)")
        ax.set_xscale("log")
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("그리퍼 보정 샘플 수 N")
        lo = min(0.0, ax.get_ylim()[0])
        ax.set_ylim(max(lo, -1.0), 1.02)
    axs[0].set_ylabel("R²")
    axs[0].legend(frameon=False, fontsize=7)
    fig.suptitle(f"장착 도메인 시프트 (δε={res['shift']['d_eps']}%, γ={res['shift']['gamma']}, "
                 f"s={res['shift']['scale']}) 적응 방법별 회복 — 시뮬레이션 내 방법론 시연", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    run_domain_shift()
