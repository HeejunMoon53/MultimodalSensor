"""
plot_test0909.py
0909 실기 실시간 검증 3세션 시각화 (moe_monitor_2026 0909_*.csv)

CSV 열 (moe_realtime_monitor.py 로 취득한 온보드 실시간 로그):
  t_s, dL_pct, dR_pct, dV_pct, IDRIVE, STATUS,
  strain_pct, value, mode, gate_proba, latency_us,
  XA_mm, YA_mm, Z_mm, Fz_act_N, strain_act_pct, value_act

  strain_pct / value : 온보드 모델의 실시간 추정치 (value 는 mode==0일 때 근접거리 mm,
                        mode==1일 때 접촉력 N)
  strain_act_pct / Z_mm / Fz_act_N : 스테이지·F/T 센서 기준 실측 정답값
  mode : 게이트가 판정한 접촉 여부 (0=비접촉/근접 전문가, 1=접촉/압력 전문가)

3개 세션:
  moe_monitor_20260909_142710.csv  - 인장 연속 스윕 & 근접 이산 스텝
  moe_monitor_20260909_143454.csv  - 인장 이산 스텝 & 근접 연속 스윕
  moe_monitor_20260909_193809.csv  - 압력 연속 스윕 & 인장 이산 스텝
                                      (인장 >= 14% 구간은 압력 시 인덕턴스 saturation
                                       발생 -> 압력(mode==1) 관련 3D/정확도 분석에서 제외)

출력: output/<csv 파일명>/ 아래에
  timeseries.png                         - 시간 도메인 6패널(변형률·근접·힘·dL·dR·TENG)
  3d_proximity_strain_L.png / _R.png     - 근접 구간 Strain-Proximity-dL/dR 3D
  3d_force_strain_L.png / _R.png         - 압력 구간 Strain-Force-dL/dR 3D (있는 세션만)
  parity_strain.png                      - 변형률 추정 vs 실측 산점도 (R²/RMSE)
  parity_proximity.png                   - 근접거리 추정 vs 실측 산점도 (있는 세션만)
  parity_force.png                       - 접촉력 추정 vs 실측 산점도 (있는 세션만, 압력
                                            세션은 saturation 구간 제외 버전)
  stats.json                             - 세션별 R²/RMSE/샘플 수 요약

사용법:
  python plot_test0909.py                 # 3개 CSV 전부
  python plot_test0909.py moe_monitor_20260909_193809.csv   # 특정 파일만
"""

import argparse
import glob
import json
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (3D projection 등록)

# ── 색상 컨벤션 (CLAUDE.md) ──────────────────────────────────────────────────
COLOR_L = "#FF8C00"      # 인덕턴스 L — 주황
COLOR_R = "#2CA02C"      # DC 저항 R  — 초록
COLOR_TENG = "#1F77B4"   # TENG 전압  — 파랑
COLOR_POS = "#7F7F7F"    # Strain / Position (자극, 실측) — 회색
COLOR_PRED = "#8C1D40"   # 온보드 추정치 — 마룬
COLOR_FORCE = "#D62728"  # Force — 빨강

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_OUT_DIR = os.path.join(SCRIPT_DIR, "output")

MIN_SEGMENT_LEN = 5
SMOOTH_WINDOW = 15
SATURATION_STRAIN_PCT = 14.0   # 압력 시 인덕턴스 saturation 시작점 (사용자 지정)


# ── 1. 데이터 로드 ────────────────────────────────────────────────────────────

def load(path):
    d = pd.read_csv(path)
    d = d[d["mode"].isin([0, 1])].copy()
    d = d[(d.strain_act_pct.between(-2, 35)) & (d.dL_pct.abs() < 150)
          & (d.dR_pct.abs() < 150) & (d.gate_proba.between(0, 1))]
    d = d[np.where(d["mode"] == 1, d.value.between(-20, 20), d.value.between(-20, 30))]
    d = d.reset_index(drop=True)
    d["t"] = d.t_s - d.t_s.min()
    off = d.loc[d["mode"] == 0, "Fz_act_N"].mean()
    d["F_true"] = -(d.Fz_act_N - off)
    d["phase"] = np.where(d["mode"].values == 0, "proximity", "pressure")
    seg = (d["phase"].values != np.roll(d["phase"].values, 1)).cumsum()
    seg[0] = 0
    d["segment_id"] = seg
    sr = d["strain_act_pct"].round(2).values
    cyc = (sr != np.roll(sr, 1)).cumsum()
    cyc[0] = 0
    d["cycle_id"] = cyc
    for col in ("dL_pct", "dR_pct", "F_true"):
        d[f"{col}_smooth"] = (
            d.groupby("segment_id")[col]
            .transform(lambda s: s.rolling(SMOOTH_WINDOW, center=True, min_periods=1).mean()))
    return d


def r2(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    s = ((y - y.mean()) ** 2).sum()
    return float(1 - ((y - p) ** 2).sum() / s) if s > 0 else float("nan")


def rmse(y, p):
    return float(np.sqrt(np.mean((np.asarray(y, float) - np.asarray(p, float)) ** 2)))


# ── 2. 시간 도메인 그래프 ─────────────────────────────────────────────────────

def plot_timeseries(d, title, out_dir):
    fig, axes = plt.subplots(6, 1, figsize=(13, 14), sharex=True)
    fig.suptitle(title, fontsize=13, fontweight="bold")

    axes[0].plot(d.t, d.strain_act_pct, color=COLOR_POS, lw=1.1, label="ground truth")
    axes[0].plot(d.t, d.strain_pct, color=COLOR_PRED, lw=0.6, alpha=0.85,
                 label="on-board estimate")
    axes[0].set_ylabel("Strain\n[%]", fontsize=10)
    axes[0].legend(fontsize=7.5, ncol=2, loc="upper right", framealpha=0.9)

    axes[1].plot(d.t, d.Z_mm, color=COLOR_POS, lw=1.0)
    a = d[d["mode"] == 0]
    axes[1].plot(a.t, a.value, ".", ms=1.2, color=COLOR_TENG, alpha=0.6,
                 label="on-board proximity estimate")
    axes[1].axhline(0, color="red", lw=0.8, alpha=0.5, ls="--")
    axes[1].set_ylabel("Position Z\n[mm]", fontsize=10)
    if len(a):
        axes[1].legend(fontsize=7.5, loc="upper right", framealpha=0.9)

    axes[2].plot(d.t, d.F_true, color=COLOR_POS, lw=1.0)
    b = d[d["mode"] == 1]
    axes[2].plot(b.t, b.value, ".", ms=1.2, color=COLOR_FORCE, alpha=0.6,
                 label="on-board force estimate")
    axes[2].set_ylabel("Force\n[N]", fontsize=10)
    if len(b):
        axes[2].legend(fontsize=7.5, loc="upper right", framealpha=0.9)

    panels = [
        ("$\\Delta$L / L$_0$\n[%]", d.dL_pct, COLOR_L),
        ("$\\Delta$R / R$_0$\n[%]", d.dR_pct, COLOR_R),
        ("$\\Delta$V (TENG)\n[%]", d.dV_pct, COLOR_TENG),
    ]
    for ax, (label, y, color) in zip(axes[3:], panels):
        ax.plot(d.t, y, color=color, lw=0.6)
        ax.set_ylabel(label, fontsize=10)
        ax.axhline(0, color="black", lw=0.5, alpha=0.3)

    for ax in axes:
        ax.grid(True, alpha=0.25)
    axes[-1].set_xlabel("Time [s]")

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    out = os.path.join(out_dir, "timeseries.png")
    fig.savefig(out, dpi=160)
    print(f"[save] {out}")
    plt.close(fig)


# ── 3. 3D 그래프 ──────────────────────────────────────────────────────────────

def _iter_segments(d, group_col, phase):
    sub = d[d["phase"] == phase]
    for _, seg in sub.groupby(group_col):
        if len(seg) >= MIN_SEGMENT_LEN:
            yield seg


def plot_3d(d, group_col, x_col, x_label, z_col, color, title, out_name, out_dir,
            phase, invert_x=False):
    segs = list(_iter_segments(d, group_col, phase))
    if not segs:
        print(f"[skip] {out_name}: no '{phase}' segments")
        return
    fig = plt.figure(figsize=(9, 8))
    ax = fig.add_subplot(111, projection="3d")
    for seg in segs:
        ax.plot(seg[x_col], seg["strain_act_pct"], seg[z_col],
                 color=color, alpha=0.6, linewidth=1.2)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel(x_label)
    ax.set_ylabel("Strain [%]")
    ax.set_zlabel("$\\Delta$L / L$_0$ [%]" if z_col.startswith("dL_pct")
                  else "$\\Delta$R / R$_0$ [%]")
    if invert_x:
        ax.invert_xaxis()
    out = os.path.join(out_dir, out_name)
    fig.savefig(out, dpi=160)
    print(f"[save] {out}")
    plt.close(fig)


# ── 4. 정확도(parity) 그래프 ──────────────────────────────────────────────────

def parity_plot(y_true, y_pred, label, color, out_name, out_dir):
    if len(y_true) < 2:
        print(f"[skip] {out_name}: not enough samples")
        return None
    R2, RMSE = r2(y_true, y_pred), rmse(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(4.6, 4.4))
    ax.plot(y_true, y_pred, ".", ms=2.5, color=color, alpha=0.4)
    lo, hi = float(min(y_true.min(), y_pred.min())), float(max(y_true.max(), y_pred.max()))
    ax.plot([lo, hi], [lo, hi], "k--", lw=1.0)
    ax.set_xlabel(f"true {label}")
    ax.set_ylabel(f"estimated {label}")
    ax.set_title(f"{label}  (R²={R2:.3f}, RMSE={RMSE:.3f}, n={len(y_true)})", fontsize=10)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out = os.path.join(out_dir, out_name)
    fig.savefig(out, dpi=160)
    print(f"[save] {out}")
    plt.close(fig)
    return dict(r2=R2, rmse=RMSE, n=int(len(y_true)))


# ── main ─────────────────────────────────────────────────────────────────────

SESSIONS = {
    "moe_monitor_20260909_142710.csv": "Strain:Continuous & Proximity:Discrete",
    "moe_monitor_20260909_143454.csv": "Strain:Discrete & Proximity:Continuous",
    "moe_monitor_20260909_193809.csv": "Pressure:Continuous & Strain:Discrete",
}


def process(fname, out_root):
    path = os.path.join(SCRIPT_DIR, fname)
    d = load(path)
    out_dir = os.path.join(out_root, os.path.splitext(fname)[0])
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n=== {fname}  (n={len(d)}) ===  out -> {out_dir}")

    title = SESSIONS.get(fname, fname)
    plot_timeseries(d, title, out_dir)

    plot_3d(d, "segment_id", "Z_mm", "Proximity [mm]", "dL_pct_smooth", COLOR_L,
            "Proximity - Strain - $\\Delta$L", "3d_proximity_strain_L.png", out_dir, "proximity")
    plot_3d(d, "segment_id", "Z_mm", "Proximity [mm]", "dR_pct_smooth", COLOR_R,
            "Proximity - Strain - $\\Delta$R", "3d_proximity_strain_R.png", out_dir, "proximity")

    is_pressure_session = fname == "moe_monitor_20260909_193809.csv"
    d_press3d = d
    if is_pressure_session:
        # 압력 시 인장 >= 14% 구간은 인덕턴스 saturation -> 3D/정확도 분석에서 제외
        keep = (d["phase"] != "pressure") | (d["strain_act_pct"] < SATURATION_STRAIN_PCT)
        d_press3d = d[keep].copy()
        n_excluded = int((~keep).sum())
        print(f"[filter] pressure phase, strain >= {SATURATION_STRAIN_PCT}%: "
              f"{n_excluded} rows excluded (saturation)")

    plot_3d(d_press3d, "segment_id", "F_true_smooth", "Force [N]", "dL_pct_smooth", COLOR_L,
            "Force - Strain - $\\Delta$L (strain < %g%% only)" % SATURATION_STRAIN_PCT
            if is_pressure_session else "Force - Strain - $\\Delta$L",
            "3d_force_strain_L.png", out_dir, "pressure", invert_x=True)
    plot_3d(d_press3d, "segment_id", "F_true_smooth", "Force [N]", "dR_pct_smooth", COLOR_R,
            "Force - Strain - $\\Delta$R (strain < %g%% only)" % SATURATION_STRAIN_PCT
            if is_pressure_session else "Force - Strain - $\\Delta$R",
            "3d_force_strain_R.png", out_dir, "pressure", invert_x=True)

    stats = {}
    stats["strain"] = parity_plot(d.strain_act_pct.values, d.strain_pct.values,
                                   "strain (%)", COLOR_L, "parity_strain.png", out_dir)

    a = d[d["mode"] == 0]
    if len(a) > 1:
        stats["proximity"] = parity_plot(a.Z_mm.values, a.value.values, "distance d (mm)",
                                          COLOR_TENG, "parity_proximity.png", out_dir)

    b = d[d["mode"] == 1]
    if is_pressure_session:
        b = b[b.strain_act_pct < SATURATION_STRAIN_PCT]
    if len(b) > 1:
        name = ("parity_force.png" if not is_pressure_session
                 else "parity_force_strain_lt14.png")
        stats["force"] = parity_plot(b.F_true.values, b.value.values, "force F (N)",
                                      COLOR_FORCE, name, out_dir)
        if is_pressure_session:
            stats["force_note"] = ("strain_act_pct < %g only; higher-strain pressure rows "
                                    "excluded due to inductance saturation"
                                    % SATURATION_STRAIN_PCT)

    with open(os.path.join(out_dir, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print("stats:", json.dumps(stats, indent=2))
    return stats


def main():
    p = argparse.ArgumentParser(description="0909 실기 실시간 검증 시각화")
    p.add_argument("files", nargs="*", help="처리할 CSV 파일명(들). 생략 시 3개 세션 전부.")
    args = p.parse_args()
    files = args.files or list(SESSIONS.keys())

    os.makedirs(BASE_OUT_DIR, exist_ok=True)
    all_stats = {}
    for fname in files:
        all_stats[fname] = process(fname, BASE_OUT_DIR)
    with open(os.path.join(BASE_OUT_DIR, "all_stats.json"), "w") as f:
        json.dump(all_stats, f, indent=2)
    print("\n완료.")


if __name__ == "__main__":
    main()
