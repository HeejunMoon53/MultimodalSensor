import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from pathlib import Path

CSV_DIR = Path(__file__).parent
FILES = sorted(CSV_DIR.glob("collect_*.csv"))

COLOR_L    = "#FF8C00"  # 인덕턴스 L — 주황
COLOR_R    = "#2CA02C"  # DC 저항 R  — 초록
COLOR_TENG = "#1F77B4"  # TENG 전압  — 파랑

COLORS = {
    "xa": "#555555",
    "d":  "#888888",
    "dL": COLOR_L,
    "dR": COLOR_R,
}

def plot_file(csv_path: Path):
    df = pd.read_csv(csv_path)

    # 시간을 0 기준으로 정규화
    t = df["t_s"].values - df["t_s"].values[0]

    # 1초 이동평균 (샘플레이트 추정 — 고유 타임스탬프 기준)
    t_unique = np.unique(t)
    if len(t_unique) > 1:
        dt_median = np.median(np.diff(t_unique))
        win = max(1, int(round(1.0 / dt_median))) if dt_median > 0 else 300
    else:
        win = 300
    dL_sm = pd.Series(df["dL_pct"].values).rolling(win, center=True, min_periods=1).mean().values
    dR_sm = pd.Series(df["dR_pct"].values).rolling(win, center=True, min_periods=1).mean().values

    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
    fig.suptitle(f"Timeseries — {csv_path.name}", fontsize=13, fontweight="bold")

    # ── Panel 1: 인장 변형률 (eps_act_pct = xa_mm×2/120×100) ────────────
    ax = axes[0]
    ax.plot(t, df["eps_act_pct"], color=COLORS["xa"], lw=0.8, label="strain (actual)")
    ax.set_ylabel("Strain\n[%]", fontsize=9)
    ax.set_ylim(-1, 32)
    ax.legend(loc="upper left", fontsize=8)
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, which="major", ls="--", alpha=0.4)

    # ── Panel 2: 근접 거리 (d_act_mm) ───────────────────────────────────
    ax = axes[1]
    ax.plot(t, df["d_act_mm"], color=COLORS["d"], lw=0.8, label="d_act_mm (proximity)")
    ax.set_ylabel("Proximity dist.\n[mm]", fontsize=9)
    ax.legend(loc="upper left", fontsize=8)
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, which="major", ls="--", alpha=0.4)

    # ── Panel 3: ΔL/L₀ (%) ─────────────────────────────────────────────
    ax = axes[2]
    ax.plot(t, df["dL_pct"], color=COLORS["dL"], lw=0.4, alpha=0.35, label="raw")
    ax.plot(t, dL_sm,        color=COLORS["dL"], lw=1.2,             label="1 s moving avg")
    ax.axhline(0, color="gray", lw=0.6, ls=":")
    ax.set_ylabel("ΔL / L₀\n[%]", fontsize=9)
    ax.legend(loc="upper left", fontsize=8)
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, which="major", ls="--", alpha=0.4)

    # ── Panel 4: ΔR/R₀ (%) ─────────────────────────────────────────────
    ax = axes[3]
    ax.plot(t, df["dR_pct"], color=COLORS["dR"], lw=0.4, alpha=0.35, label="raw")
    ax.plot(t, dR_sm,        color=COLORS["dR"], lw=1.2,             label="1 s moving avg")
    ax.axhline(0, color="gray", lw=0.6, ls=":")
    ax.set_ylabel("ΔR / R₀\n[%]", fontsize=9)
    ax.set_xlabel("Time [s]", fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, which="major", ls="--", alpha=0.4)

    fig.align_ylabels(axes)
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    out = csv_path.with_suffix(".png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved → {out.name}")


for f in FILES:
    plot_file(f)

print("Done.")
