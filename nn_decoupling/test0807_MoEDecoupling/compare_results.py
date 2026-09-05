"""
compare_results.py
5개 후보 결과를 하나의 표/그래프로 정리하고 파라미터 수(임베딩 비용)까지 비교.
"""

import json
import os

import matplotlib.pyplot as plt
import numpy as np

import common

COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"
COLOR_GATE = "#7F7F7F"


def mlp_params(n_in, hidden, n_out):
    layers = [n_in] + list(hidden) + [n_out]
    return sum(layers[i] * layers[i + 1] + layers[i + 1] for i in range(len(layers) - 1))


def estimate_param_counts():
    # 각 후보의 실제 구조 그대로 계산 (embedding 비용 참고용)
    gate_hidden, expert_hidden = (8, 4), (24, 16, 8)
    counts = {}

    counts["candidate1_baseline_gate"] = (
        mlp_params(2, gate_hidden, 1) + 2 * mlp_params(2, expert_hidden, 2))
    counts["candidate2_gate_ema"] = (
        mlp_params(4, gate_hidden, 1) + 2 * mlp_params(4, expert_hidden, 2))
    counts["candidate3_unified_mlp"] = mlp_params(4, (32, 24, 16, 8), 2)
    counts["candidate4_physics_residual"] = (
        6 +  # 물리 파라미터 (R 3개 + L 3개)
        mlp_params(5, expert_hidden, 2))  # pressure 잔차 MLP만 (proximity는 candidate2 재사용 가정)
    counts["candidate5_multiscale_ema"] = (
        mlp_params(10, gate_hidden, 1) + 2 * mlp_params(10, expert_hidden, 2))
    return counts


def main():
    with open(common.RESULTS_JSON, encoding="utf-8") as f:
        R = json.load(f)
    params = estimate_param_counts()

    rows = []
    for name in ["candidate1_baseline_gate", "candidate2_gate_ema", "candidate3_unified_mlp",
                 "candidate4_physics_residual", "candidate5_multiscale_ema", "candidate5b_true_rnn"]:
        if name not in R:
            print(f"[skip] {name} not found in results yet")
            continue
        r = R[name]
        if name == "candidate3_unified_mlp":
            gate_acc = None
            strain_r2 = r["overall"]["strain"]["r2"]
            press_strain_r2 = r["pressure_subset"]["strain"]["r2"]
            # candidate3은 force(N)가 아니라 통합 position(mm)으로 평가했으므로 별도 표기
            press_other_r2 = r["pressure_subset"]["position"]["r2"]
            press_other_label = "position(mm)"
            prox_dist_r2 = r["proximity_subset"]["position"]["r2"]
        elif name == "candidate4_physics_residual":
            gate_acc = None
            strain_r2 = r["hybrid"]["strain"]["r2"]
            press_strain_r2 = r["hybrid"]["strain"]["r2"]
            press_other_r2 = r["hybrid"]["force"]["r2"]
            press_other_label = "force(N)"
            prox_dist_r2 = None  # candidate4는 proximity 모드를 별도 구현하지 않음
        elif name == "candidate5b_true_rnn":
            gate_acc = None
            strain_r2 = r["strain"]["r2"]
            press_strain_r2 = r["strain"]["r2"]
            press_other_r2 = r["force"]["r2"]
            press_other_label = "force(N)"
            prox_dist_r2 = None  # 압력 모드 GRU만 구현, proximity는 별도 구현하지 않음
        else:
            gate_acc = r["gate"]["acc"]
            strain_r2 = r["end_to_end_strain"]["r2"]
            press_strain_r2 = r["expert_b_oracle"]["strain"]["r2"]
            press_other_r2 = r["expert_b_oracle"]["force"]["r2"]
            press_other_label = "force(N)"
            prox_dist_r2 = r["expert_a_oracle"]["distance"]["r2"]

        param_count = r.get("params", params.get(name))
        rows.append(dict(name=name, gate_acc=gate_acc, e2e_strain_r2=strain_r2,
                          press_strain_r2=press_strain_r2, press_other_r2=press_other_r2,
                          press_other_label=press_other_label, prox_dist_r2=prox_dist_r2,
                          params=param_count))

    # ── 표 출력 ──────────────────────────────────────────────────────────────
    print(f"{'candidate':30s} {'gate_acc':>9s} {'e2e_strain_R2':>14s} {'press_strain_R2':>16s} "
          f"{'press_other_R2':>16s} {'prox_dist_R2':>13s} {'params':>8s}")
    for row in rows:
        ga = f"{row['gate_acc']:.4f}" if row['gate_acc'] is not None else "N/A"
        pd_ = f"{row['prox_dist_r2']:.4f}" if row['prox_dist_r2'] is not None else "N/A"
        label = f"{row['press_other_r2']:.4f}({row['press_other_label']})"
        print(f"{row['name']:30s} {ga:>9s} {row['e2e_strain_r2']:>14.4f} "
              f"{row['press_strain_r2']:>16.4f} {label:>16s} {pd_:>13s} {row['params']:>8d}")

    # ── 그래프 ──────────────────────────────────────────────────────────────
    labels = [r["name"].replace("candidate", "C").replace("_", "\n") for r in rows]
    x = np.arange(len(rows))
    w = 0.35

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))

    ax = axes[0]
    press_strain = [r["press_strain_r2"] for r in rows]
    press_other = [r["press_other_r2"] for r in rows]
    ax.bar(x - w / 2, press_strain, width=w, color=COLOR_R, label="pressure-mode strain R2")
    ax.bar(x + w / 2, press_other, width=w, color=COLOR_L, label="pressure-mode force/position R2")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("R2 (held-out test)")
    ax.set_title("Pressure-mode performance (most hysteresis-affected regime)")
    ax.legend(fontsize=9); ax.grid(alpha=0.25, axis="y")

    ax = axes[1]
    ax.bar(x, [r["params"] for r in rows], color=COLOR_GATE)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Parameter count (embedding cost proxy)")
    ax.set_title("Model size (INT8 quantized ~= 1 byte/param)")
    ax.grid(alpha=0.25, axis="y")

    plt.tight_layout()
    out = os.path.join(common.OUT_DIR, "candidates_comparison.png")
    fig.savefig(out, dpi=160)
    print(f"\n[save] {out}")


if __name__ == "__main__":
    main()
