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

def trim_return(df: pd.DataFrame) -> pd.DataFrame:
    """복귀 구간을 제거한다.
    1) d_act_mm이 복귀 임계값 아래인 마지막 지점을 찾는다.
    2) 그 지점에서 xa_mm이 0 근처로 돌아온 마지막 완전한 사이클 끝을 찾아 자른다.
    """
    d = df["d_act_mm"].values
    xa = df["xa_mm"].values
    d_initial = d[0]
    d_min = d.min()
    if d_initial - d_min < 5.0:
        return df
    threshold = d_min + 0.7 * (d_initial - d_min)
    below = np.where(d < threshold)[0]
    if len(below) == 0:
        return df
    last_below = below[-1]
    # xa가 왕복하는 프로토콜인지 확인 (피크 이후 0 근처로 돌아오는 횟수)
    xa_peak_idx = int(np.argmax(xa))
    xa_after_peak = xa[xa_peak_idx:last_below + 1]
    oscillating = (xa_after_peak < 1.0).sum() > 5
    if oscillating:
        xa_home = np.where(xa[:last_below + 1] < 1.0)[0]
        cut = xa_home[-1] if len(xa_home) > 0 else last_below
    else:
        cut = last_below
    return df.iloc[: cut + 1]


def plot_file(csv_path: Path):
    df = pd.read_csv(csv_path)
    df = trim_return(df)

    # 시간을 0 기준으로 정규화
    t = df["t_s"].values - df["t_s"].values[0]

    # 끝 10초 추가 제거
    mask = t <= t[-1] - 10.0
    df = df.iloc[mask]
    t = t[mask]

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
    fig.suptitle(f"Strain:Continuous & Proximity:Discrete", fontsize=13, fontweight="bold")

    # ── Panel 1: 인장 변형률 (eps_act_pct = xa_mm×2/120×100) ────────────
    ax = axes[0]
    ax.plot(t, df["eps_act_pct"], color=COLORS["xa"], lw=0.8)
    ax.set_ylabel("Strain\n[%]", fontsize=9)
    ax.set_ylim(-1, 32)
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, which="major", ls="--", alpha=0.4)

    # ── Panel 2: 근접 거리 (d_act_mm) ───────────────────────────────────
    ax = axes[1]
    ax.plot(t, df["d_act_mm"], color=COLORS["d"], lw=0.8)
    ax.set_ylabel("Proximity\n[mm]", fontsize=9)
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, which="major", ls="--", alpha=0.4)

    # ── Panel 3: ΔL/L₀ (%) ─────────────────────────────────────────────
    ax = axes[2]
    ax.plot(t, df["dL_pct"], color=COLORS["dL"], lw=0.4, alpha=0.35)
    ax.plot(t, dL_sm,        color=COLORS["dL"], lw=1.2           )
    ax.axhline(0, color="gray", lw=0.6, ls=":")
    ax.set_ylabel("ΔL / L₀\n[%]", fontsize=9)
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, which="major", ls="--", alpha=0.4)

    # ── Panel 4: ΔR/R₀ (%) ─────────────────────────────────────────────
    ax = axes[3]
    ax.plot(t, df["dR_pct"], color=COLORS["dR"], lw=0.4, alpha=0.35)
    ax.plot(t, dR_sm,        color=COLORS["dR"], lw=1.2          )
    ax.axhline(0, color="gray", lw=0.6, ls=":")
    ax.set_ylabel("ΔR / R₀\n[%]", fontsize=9)
    ax.set_xlabel("Time [s]", fontsize=10)
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, which="major", ls="--", alpha=0.4)

    for ax in axes:
        ax.set_xlim(t[0], t[-1])

    fig.align_ylabels(axes)
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    out = csv_path.with_suffix(".png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved → {out.name}")


for f in FILES:
    plot_file(f)

print("Done.")
