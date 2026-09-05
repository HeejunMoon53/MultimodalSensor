"""
plot_test0805.py
0805 압력/근접 테스트 시각화 (test0805_dataset/mms_*.csv)

CSV 열: t_s | dL_pct dR_pct dV | xa_mm xb_mm ya_mm yb_mm z_mm
        | eps_act_pct d_act_mm | Fx_N Fy_N Fz_N Tx_Nm Ty_Nm Tz_Nm

z_mm : 근접+압력 위치 (25mm -> 0mm -> -1.2mm(압축) -> 0mm -> 25mm 연속 스윕)
       z_mm >= 0  : 비접촉 근접 구간 (Proximity)
       z_mm <  0  : 접촉 압축 구간   (Pressure)

주의: 이 실험에서는 인장(strain) 축으로 Y모터(ya_mm/yb_mm)를 사용했다
      (X모터 기준인 eps_act_pct 열은 xa_mm=0 고정이라 항상 0 — 사용 불가).
      Strain[%] = (ya_mm + yb_mm) / SENSOR_L0 * 100 으로 재계산한다.

출력 (파일 미지정 시 output/, 지정 시 output/<파일명>/ 밑에 저장):
  timeseries_test0805.png       - 시간에 대한 5-패널 그래프
  3d_proximity_strain_L.png     - Proximity-Strain-L        3D (z_mm>=0 구간만)
  3d_proximity_strain_R.png     - Proximity-Strain-R        3D (z_mm>=0 구간만)
  3d_force_strain_L.png         - Force-Strain-L            3D (z_mm<0 구간만)
  3d_force_strain_R.png         - Force-Strain-R            3D (z_mm<0 구간만)
  3d_position_strain_L.png      - Proximity+Pressure-Strain-L 3D (전 구간 이어붙임)
  3d_position_strain_R.png      - Proximity+Pressure-Strain-R 3D (전 구간 이어붙임)
  3d_force_strain_L_oversampled.png - Force(오버샘플링)-Strain-L 3D
  3d_force_strain_R_oversampled.png - Force(오버샘플링)-Strain-R 3D

사용법:
  python plot_test0805.py                                  # test0805_dataset/ 안의 mms_*.csv 전부 합쳐서 사용 (기존 동작)
  python plot_test0805.py mms_20260805_172956.csv           # 파일명만 지정 (test0805_dataset/ 기준)
  python plot_test0805.py mms_20260805_172956.csv mms_20260806_200653.csv   # 여러 개 지정 시 그 파일들만 합침
  python plot_test0805.py "C:/path/to/other.csv"             # 절대/상대 경로도 가능
"""

import argparse
import glob
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (3D projection 등록)

# ── 색상 컨벤션 (CLAUDE.md) ──────────────────────────────────────────────────
COLOR_L = "#FF8C00"     # 인덕턴스 L — 주황
COLOR_R = "#2CA02C"     # DC 저항 R  — 초록
COLOR_POS = "#7F7F7F"   # Strain / Position (자극) — 회색
COLOR_FORCE = "#1F77B4"  # Force (Fz) — 파랑

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "test0805_dataset")
BASE_OUT_DIR = os.path.join(SCRIPT_DIR, "output")

MIN_SEGMENT_LEN = 5   # 너무 짧은(노이즈성) 구간 제외
SMOOTH_WINDOW = 15    # 3D 그래프용 이동평균 창 크기 (원본 데이터는 그대로 유지)
FORCE_OVERSAMPLE_WINDOW = 41  # Force_N 전용 오버샘플링 창 (~450ms @ ~91Hz).
                              # 노이즈 std는 대략 1/sqrt(N)로 줄어듦(0.19N -> ~0.03N 기대).
SENSOR_L0 = 120.0     # 센서 초기 길이 (mm) — Strain 계산용 (mms_collector.py와 동일)


# ── 1. 데이터 로드 ────────────────────────────────────────────────────────────

def resolve_files(file_args):
    """CLI로 받은 파일명/경로 목록을 실제 CSV 경로 목록으로 변환.
    인자가 없으면 기존 동작대로 test0805_dataset/ 안의 mms_*.csv 전부."""
    if not file_args:
        files = sorted(glob.glob(os.path.join(DATA_DIR, "mms_*.csv")))
        if not files:
            raise FileNotFoundError(f"'{DATA_DIR}' 안에서 mms_*.csv 파일을 찾을 수 없습니다.")
        return files, None

    resolved = []
    for f in file_args:
        path = f if os.path.isabs(f) or os.path.exists(f) else os.path.join(DATA_DIR, f)
        if not os.path.exists(path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {f} (확인한 경로: {path})")
        resolved.append(path)
    # 출력 폴더를 파일별로 구분 (여러 CSV가 섞여서 그려지는 걸 방지)
    out_suffix = "+".join(os.path.splitext(os.path.basename(p))[0] for p in resolved)
    return resolved, out_suffix


def load_data(files):
    print(f"[load] {len(files)}개 파일 로드: {[os.path.basename(f) for f in files]}")
    dfs = []
    for f in files:
        d = pd.read_csv(f)
        d["Force_N"] = -d["Fz_N"]  # 압축 시 양수가 되도록 부호 반전
        # F/T 센서가 세션마다 영점(taring)이 살짝 안 맞아 있어서, 비접촉 구간(z_mm>=0)의
        # 평균이 0이 아니었다 — 파일별로 그 오프셋을 구해서 빼준다.
        offset = d.loc[d["z_mm"] >= 0, "Force_N"].mean()
        d["Force_N"] = d["Force_N"] - offset
        print(f"[tare] {os.path.basename(f)}: Force_N 오프셋 {offset:+.4f}N 보정")
        dfs.append(d)
    df = pd.concat(dfs, ignore_index=True)
    # Y모터(ya/yb)가 실제 인장 축 — eps_act_pct(X축 기준)는 사용하지 않는다.
    df["strain_pct"] = (df["ya_mm"] + df["yb_mm"]) / SENSOR_L0 * 100.0
    return df


# ── 2. 근접(proximity) / 압력(pressure) 구간 분리 ────────────────────────────

def add_phase_segments(df):
    """z_mm 부호가 바뀔 때마다 새 구간(segment)을, strain 스텝이 바뀔 때마다
    새 사이클(cycle = 근접+압력 전체 1회 스윕)을 부여한다."""
    phase = np.where(df["z_mm"].values >= 0, "proximity", "pressure")
    seg_id = (phase != np.roll(phase, 1)).cumsum()
    seg_id[0] = 0
    df = df.copy()
    df["phase"] = phase
    df["segment_id"] = seg_id

    strain_r = df["strain_pct"].round(3).values
    cycle_id = (strain_r != np.roll(strain_r, 1)).cumsum()
    cycle_id[0] = 0
    df["cycle_id"] = cycle_id

    # 3D 그래프 전용 이동평균 스무딩 — 근접/압력 구간별(segment_id) + 전체 사이클별(cycle_id)
    for col in ("dL_pct", "dR_pct", "Force_N"):
        df[f"{col}_smooth"] = (
            df.groupby("segment_id")[col]
            .transform(lambda s: s.rolling(SMOOTH_WINDOW, center=True, min_periods=1).mean())
        )
        df[f"{col}_smooth_cycle"] = (
            df.groupby("cycle_id")[col]
            .transform(lambda s: s.rolling(SMOOTH_WINDOW, center=True, min_periods=1).mean())
        )

    # Force_N 전용 오버샘플링(더 큰 창) — 힘 축 자체의 노이즈/좁은 동적범위(SNR) 완화용
    df["Force_N_oversampled"] = (
        df.groupby("segment_id")["Force_N"]
        .transform(lambda s: s.rolling(FORCE_OVERSAMPLE_WINDOW, center=True, min_periods=1).mean())
    )
    return df


# ── 3. 시간 도메인 그래프 (5 패널) ────────────────────────────────────────────

def plot_timeseries(df, out_dir):
    t = df["t_s"].values - df["t_s"].values[0]

    fig, axes = plt.subplots(5, 1, figsize=(13, 12), sharex=True)
    fig.suptitle("Strain:Fixed & Proximity+Pressure:Continuous", fontsize=13, fontweight="bold")

    panels = [
        ("Strain\n[%]",        df["strain_pct"],  COLOR_POS,   1.0),
        ("Position\n[mm]",     df["z_mm"],         COLOR_POS,   1.0),
        ("Force\n[N]",         df["Force_N"],       COLOR_FORCE, 0.9),
        ("$\\Delta$L / L$_0$\n[%]", df["dL_pct"],   COLOR_L,     0.9),
        ("$\\Delta$R / R$_0$\n[%]", df["dR_pct"],   COLOR_R,     0.9),
    ]

    for ax, (label, y, color, lw) in zip(axes, panels):
        ax.plot(t, y, color=color, linewidth=lw)
        ax.set_ylabel(label, fontsize=10)
        ax.grid(True, alpha=0.25)
        ax.axhline(0, color="black", linewidth=0.5, alpha=0.3)

    axes[1].axhline(0, color="red", linewidth=0.8, alpha=0.5, linestyle="--")
    axes[-1].set_xlabel("Time [s]")

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    out = os.path.join(out_dir, "timeseries_test0805.png")
    fig.savefig(out, dpi=160)
    print(f"[save] {out}")
    plt.close(fig)


# ── 4. 3D 그래프 (Proximity/Force - Strain - L/R) ───────────────────────────

def _iter_segments(df, group_col, phase=None):
    sub = df if phase is None else df[df["phase"] == phase]
    for _, seg in sub.groupby(group_col):
        if len(seg) >= MIN_SEGMENT_LEN:
            yield seg


def plot_3d(df, group_col, x_col, x_label, z_col, color, title, out_name, out_dir,
            phase=None, invert_x=False):
    fig = plt.figure(figsize=(9, 8))
    ax = fig.add_subplot(111, projection="3d")

    for seg in _iter_segments(df, group_col, phase):
        ax.plot(seg[x_col], seg["strain_pct"], seg[z_col],
                 color=color, alpha=0.6, linewidth=1.2)

    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel(x_label)
    ax.set_ylabel("Strain [%]")
    z_label = "$\\Delta$L / L$_0$ [%]" if z_col.startswith("dL_pct") else "$\\Delta$R / R$_0$ [%]"
    ax.set_zlabel(z_label)
    if invert_x:
        ax.invert_xaxis()  # 왼쪽이 더 큰 힘이 되도록 반전

    out = os.path.join(out_dir, out_name)
    fig.savefig(out, dpi=160)
    print(f"[save] {out}")
    plt.close(fig)


# ── main ─────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="0805 압력/근접 테스트 시각화")
    p.add_argument("files", nargs="*",
                    help="사용할 CSV 파일명(들). test0805_dataset/ 기준 파일명 또는 절대/상대 경로. "
                         "생략 시 test0805_dataset/ 안의 mms_*.csv 전부를 합쳐서 사용.")
    return p.parse_args()


def main():
    args = parse_args()
    files, out_suffix = resolve_files(args.files)
    out_dir = os.path.join(BASE_OUT_DIR, out_suffix) if out_suffix else BASE_OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    print(f"[out] {out_dir}")

    df = load_data(files)
    df = add_phase_segments(df)

    plot_timeseries(df, out_dir)

    plot_3d(df, "segment_id", "z_mm", "Proximity [mm]", "dL_pct_smooth", COLOR_L,
            "Proximity - Strain - $\\Delta$L", "3d_proximity_strain_L.png", out_dir, phase="proximity")
    plot_3d(df, "segment_id", "z_mm", "Proximity [mm]", "dR_pct_smooth", COLOR_R,
            "Proximity - Strain - $\\Delta$R", "3d_proximity_strain_R.png", out_dir, phase="proximity")
    plot_3d(df, "segment_id", "Force_N_smooth", "Force [N]", "dL_pct_smooth", COLOR_L,
            "Force - Strain - $\\Delta$L", "3d_force_strain_L.png", out_dir, phase="pressure", invert_x=True)
    plot_3d(df, "segment_id", "Force_N_smooth", "Force [N]", "dR_pct_smooth", COLOR_R,
            "Force - Strain - $\\Delta$R", "3d_force_strain_R.png", out_dir, phase="pressure", invert_x=True)

    # Force 오버샘플링(창 크게) 버전 — Force 축 자체의 노이즈를 줄인 그래프
    plot_3d(df, "segment_id", "Force_N_oversampled", "Force (oversampled) [N]", "dL_pct_smooth", COLOR_L,
            "Force(oversampled) - Strain - $\\Delta$L", "3d_force_strain_L_oversampled.png", out_dir,
            phase="pressure", invert_x=True)
    plot_3d(df, "segment_id", "Force_N_oversampled", "Force (oversampled) [N]", "dR_pct_smooth", COLOR_R,
            "Force(oversampled) - Strain - $\\Delta$R", "3d_force_strain_R_oversampled.png", out_dir,
            phase="pressure", invert_x=True)

    # 근접(z_mm>=0) + 압력(z_mm<0) 구간을 하나로 이어붙인 그래프 (사이클 전체 = z_mm 축)
    plot_3d(df, "cycle_id", "z_mm", "Position (Proximity + Pressure) [mm]",
            "dL_pct_smooth_cycle", COLOR_L,
            "Proximity+Pressure - Strain - $\\Delta$L", "3d_position_strain_L.png", out_dir)
    plot_3d(df, "cycle_id", "z_mm", "Position (Proximity + Pressure) [mm]",
            "dR_pct_smooth_cycle", COLOR_R,
            "Proximity+Pressure - Strain - $\\Delta$R", "3d_position_strain_R.png", out_dir)

    print("완료.")


if __name__ == "__main__":
    main()
