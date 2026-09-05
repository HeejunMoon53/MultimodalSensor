"""
학습 데이터셋 전처리 및 분할

처리 순서:
  1. baseline 계산 → dL_pct, dR_pct 재계산
  2. 아웃라이어 필터링
  3. 과대표집 보정 (cap_axis_visits)
     - 140039: d 왕복 스윔 → d 축 cap
     - 143611: eps 왕복 진동 → eps 축 cap
  4. 두 데이터셋 병합
  5. 랜덤 셔플 → train 70 / val 15 / test 15 분할

출력: dataset/train.csv, dataset/val.csv, dataset/test.csv
      dataset/preprocessing_report.html
컬럼: eps_act_pct, d_act_mm, dL_pct, dR_pct
"""
import base64, io
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from pathlib import Path

DIR = Path(__file__).parent
OUT = DIR / "dataset"
OUT.mkdir(exist_ok=True)

TRAIN_RATIO = 0.70
VAL_RATIO   = 0.15
CAP         = 30
COLOR_L     = "#FF8C00"
COLOR_R     = "#2CA02C"
COLOR_A     = "#1F77B4"
COLOR_B     = "#E377C2"

# ── 1. 데이터 로드 ────────────────────────────────────────────────────────────
dfA = pd.read_csv(DIR / "collect_20260519_140039.csv")
dfB = pd.read_csv(DIR / "collect_20260519_143611.csv")
n_raw_A, n_raw_B = len(dfA), len(dfB)
print(f"[load]  140039: {n_raw_A:,}   143611: {n_raw_B:,}")

# ── 2. baseline 계산 & dL/dR 재계산 & 아웃라이어 필터 ────────────────────────
def estimate_baseline(df, n=200):
    ref = df[(df["eps_act_pct"] < 0.5) & (df["d_act_mm"] > 35)].head(n)
    return ref["ldc_raw"].median(), ref["r_raw"].median()

def recompute(df, L0, R0):
    df = df.copy()
    df["dL_pct"] = ((L0 / df["ldc_raw"]) ** 2 - 1.0) * 100.0
    df["dR_pct"] = ((df["r_raw"] - R0) / R0) * 100.0
    mask = (df["dL_pct"].abs() < 30) & (df["dR_pct"] > -5) & (df["dR_pct"] < 30)
    return df[mask].reset_index(drop=True)

L0_A, R0_A = estimate_baseline(dfA)
L0_B, R0_B = estimate_baseline(dfB)
dfA = recompute(dfA, L0_A, R0_A)
dfB = recompute(dfB, L0_B, R0_B)
n_filter_A, n_filter_B = len(dfA), len(dfB)
print(f"[filter] 140039: {n_filter_A:,}   143611: {n_filter_B:,}")

# ── 3. 과대표집 보정 — eps×d 2D bin 균등 샘플링 ──────────────────────────────
# per-visit 방식은 끝 구간(0%,30%)이 중간보다 방문 횟수 적어 결과적으로 과소표집됨.
# 해결: (eps_bin, d_bin) 각 셀마다 최대 CAP개 균등 선택 → 어느 구간도 동등 대우.
EPS_EDGES = np.linspace(0, 30, 25)   # 24 bins, 1.25%/bin
D_EDGES   = np.linspace(0, 36, 25)   # 24 bins, 1.5mm/bin

def uniform_2d_sample(df, n_per_cell):
    """eps×d 2D grid 각 셀에서 최대 n_per_cell개 균등 선택."""
    ei = np.clip(np.digitize(df["eps_act_pct"].values, EPS_EDGES) - 1, 0, 23)
    di = np.clip(np.digitize(df["d_act_mm"].values,   D_EDGES)   - 1, 0, 23)
    keep = []
    for b_e in range(24):
        for b_d in range(24):
            idx = np.where((ei == b_e) & (di == b_d))[0]
            if len(idx) == 0:
                continue
            if len(idx) <= n_per_cell:
                keep.extend(idx.tolist())
            else:
                sel = idx[np.round(np.linspace(0, len(idx) - 1, n_per_cell)).astype(int)]
                keep.extend(sel.tolist())
    return df.iloc[sorted(keep)].reset_index(drop=True)

dfA = uniform_2d_sample(dfA, CAP)
dfB = uniform_2d_sample(dfB, CAP)
n_cap_A, n_cap_B = len(dfA), len(dfB)
print(f"[2d-cap] 140039: {n_cap_A:,}   143611: {n_cap_B:,}")

# ── 4. 병합 ──────────────────────────────────────────────────────────────────
KEEP = ["eps_act_pct", "d_act_mm", "dL_pct", "dR_pct"]
dfA_k = dfA[KEEP].copy(); dfA_k["source"] = "140039"
dfB_k = dfB[KEEP].copy(); dfB_k["source"] = "143611"
df_full = pd.concat([dfA_k, dfB_k], ignore_index=True)
n_merged = len(df_full)
print(f"[merged] total: {n_merged:,}")

# ── 5. 랜덤 셔플 & 분할 ──────────────────────────────────────────────────────
df_full = df_full.sample(frac=1, random_state=42).reset_index(drop=True)
n_train = int(n_merged * TRAIN_RATIO)
n_val   = int(n_merged * VAL_RATIO)

train = df_full.iloc[:n_train]
val   = df_full.iloc[n_train : n_train + n_val]
test  = df_full.iloc[n_train + n_val :]

train.drop(columns="source").to_csv(OUT / "train.csv", index=False)
val.drop(columns="source").to_csv(  OUT / "val.csv",   index=False)
test.drop(columns="source").to_csv( OUT / "test.csv",  index=False)
print(f"[split]  train: {len(train):,}  val: {len(val):,}  test: {len(test):,}")

# ═══════════════════════════════════════════════════════════════════════════════
# 그래프 생성 (base64 embed용)
# ═══════════════════════════════════════════════════════════════════════════════
def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()

# ── 3D 분산 그래프 ────────────────────────────────────────────────────────────
split_cfg = [
    (train, "train", "o", 0.45, 10),
    (val,   "val",   "s", 0.70, 16),
    (test,  "test",  "^", 0.90, 16),
]
fig = plt.figure(figsize=(14, 6))
for pi, (zcol, zlabel, color) in enumerate([("dL_pct", "ΔL / L₀ [%]", COLOR_L),
                                             ("dR_pct", "ΔR / R₀ [%]", COLOR_R)]):
    ax = fig.add_subplot(1, 2, pi + 1, projection="3d")
    for sp, name, marker, alpha, ms in split_cfg:
        ax.scatter(sp["d_act_mm"], sp["eps_act_pct"], sp[zcol],
                   c=color, marker=marker, s=ms, alpha=alpha, label=name, edgecolors="none")
    ax.set_xlabel("Proximity [mm]", fontsize=8, labelpad=2)
    ax.set_ylabel("Strain [%]",     fontsize=8, labelpad=2)
    ax.set_zlabel(zlabel,           fontsize=8, labelpad=2)
    ax.set_title(zlabel, fontsize=10, fontweight="bold")
    ax.tick_params(labelsize=6)
    ax.view_init(elev=22, azim=-55)
    ax.legend(fontsize=7, markerscale=1.5, loc="upper right")
plt.tight_layout()
b64_scatter = fig_to_b64(fig)

# ── 분포 히스토그램 (eps / d) ─────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
for ax, col, label, edges in [
    (axes[0], "eps_act_pct", "Strain [%]",    EPS_EDGES),
    (axes[1], "d_act_mm",   "Proximity [mm]", D_EDGES),
]:
    for sp, name, color in [(train, "train", "#4C72B0"),
                             (val,   "val",   "#DD8452"),
                             (test,  "test",  "#55A868")]:
        ax.hist(sp[col], bins=edges, alpha=0.6, label=name, color=color, edgecolor="white", linewidth=0.4)
    ax.set_xlabel(label, fontsize=10)
    ax.set_ylabel("Sample count", fontsize=10)
    ax.set_title(f"{label} distribution", fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
plt.tight_layout()
b64_hist = fig_to_b64(fig)

# ── eps × d 커버리지 히트맵 ───────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
src_cfg = [(df_full, "All merged", "Blues"),
           (df_full[df_full["source"] == "140039"], "140039 (Ramp)", "Oranges"),
           (df_full[df_full["source"] == "143611"], "143611 (Oscillate)", "Greens")]
for ax, (sub, title, cmap) in zip(axes, src_cfg):
    ei = np.digitize(sub["eps_act_pct"].values, EPS_EDGES) - 1
    di = np.digitize(sub["d_act_mm"].values,   D_EDGES)   - 1
    cnt = np.zeros((len(EPS_EDGES)-1, len(D_EDGES)-1), dtype=int)
    for e, d in zip(np.clip(ei, 0, 23), np.clip(di, 0, 23)):
        cnt[e, d] += 1
    im = ax.imshow(cnt, origin="lower", aspect="auto", cmap=cmap,
                   extent=[D_EDGES[0], D_EDGES[-1], EPS_EDGES[0], EPS_EDGES[-1]])
    plt.colorbar(im, ax=ax, shrink=0.85).set_label("Count", fontsize=8)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_xlabel("Proximity [mm]", fontsize=9)
    ax.set_ylabel("Strain [%]", fontsize=9)
plt.tight_layout()
b64_coverage = fig_to_b64(fig)

# ═══════════════════════════════════════════════════════════════════════════════
# HTML 리포트 생성
# ═══════════════════════════════════════════════════════════════════════════════
def stats_table(df_split, title):
    s = df_split[["eps_act_pct", "d_act_mm", "dL_pct", "dR_pct"]].describe().round(3)
    rows = ""
    for stat in ["mean", "std", "min", "25%", "50%", "75%", "max"]:
        rows += f"<tr><td>{stat}</td>"
        for col in ["eps_act_pct", "d_act_mm", "dL_pct", "dR_pct"]:
            rows += f"<td>{s.loc[stat, col]}</td>"
        rows += "</tr>"
    return f"""
<h3>{title} ({len(df_split):,}개)</h3>
<table>
  <tr><th>통계</th><th>eps_act_pct [%]</th><th>d_act_mm [mm]</th><th>dL_pct [%]</th><th>dR_pct [%]</th></tr>
  {rows}
</table>"""

# 파이프라인 행
def pip_row(step, nA, nB, desc, prev_A, prev_B):
    remA = f"-{prev_A-nA:,}" if prev_A != nA else "—"
    remB = f"-{prev_B-nB:,}" if prev_B != nB else "—"
    pA = f"{nA:,} <span style='color:#888;font-size:0.85em'>({nA/n_raw_A*100:.1f}%)</span>"
    pB = f"{nB:,} <span style='color:#888;font-size:0.85em'>({nB/n_raw_B*100:.1f}%)</span>"
    return f"<tr><td>{step}</td><td>{pA}</td><td class='rem'>{remA}</td><td>{pB}</td><td class='rem'>{remB}</td><td>{desc}</td></tr>"

pip_html = (
    pip_row("① Load",              n_raw_A,    n_raw_B,    "원본 CSV 로드",
            n_raw_A, n_raw_B) +
    pip_row("② Outlier filter",    n_filter_A, n_filter_B, "|dL|<30%, dR∈(-5,30%) 범위 밖 제거",
            n_raw_A, n_raw_B) +
    pip_row("③ 2D-bin sampling",   n_cap_A,    n_cap_B,    f"eps×d 24×24 그리드 각 셀당 최대 {CAP}개 균등 선택",
            n_filter_A, n_filter_B) +
    f"<tr><td>④ Merge</td>"
    f"<td colspan='4' style='text-align:center'>{n_merged:,}개 (140039: {n_cap_A:,} + 143611: {n_cap_B:,})</td>"
    f"<td>두 데이터셋 병합</td></tr>"
)

now = datetime.now().strftime("%Y-%m-%d %H:%M")

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Preprocessing Report</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; margin: 40px; max-width: 1200px; color: #222; }}
  h1 {{ color: #333; border-bottom: 3px solid #FF8C00; padding-bottom: 8px; }}
  h2 {{ color: #333; margin-top: 40px; border-left: 4px solid #FF8C00; padding-left: 10px; }}
  h3 {{ color: #555; margin-top: 20px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; font-size: 0.93em; }}
  th {{ background: #f4f4f4; padding: 8px 12px; border: 1px solid #ccc; }}
  td {{ padding: 7px 12px; border: 1px solid #e0e0e0; }}
  tr:nth-child(even) td {{ background: #fafafa; }}
  .tag-A {{ color: #1F77B4; font-weight: bold; }}
  .tag-B {{ color: #E377C2; font-weight: bold; }}
  .rem {{ color: #c0392b; font-family: monospace; text-align: right; }}
  .note {{ font-size: 0.85em; color: #888; margin: -8px 0 16px; }}
  .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #f8f8f8; border: 1px solid #ddd; border-radius: 6px; padding: 16px; text-align: center; }}
  .card .num {{ font-size: 1.8em; font-weight: bold; color: #333; }}
  .card .label {{ font-size: 0.85em; color: #888; margin-top: 4px; }}
  img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 8px; }}
</style>
</head>
<body>
<h1>Preprocessing Report</h1>
<p style="color:#aaa; margin-top:-10px">Generated: {now} &nbsp;|&nbsp; random_state=42 &nbsp;|&nbsp; 2D-bin sampling: {CAP}/cell &nbsp;|&nbsp; grid=24×24 (eps×d)</p>

<div class="summary-grid">
  <div class="card"><div class="num">{n_raw_A+n_raw_B:,}</div><div class="label">원본 샘플 (합계)</div></div>
  <div class="card"><div class="num">{n_merged:,}</div><div class="label">전처리 후 (합계)</div></div>
  <div class="card"><div class="num">{len(train):,}</div><div class="label">Train</div></div>
  <div class="card"><div class="num">{len(val):,} / {len(test):,}</div><div class="label">Val / Test</div></div>
</div>

<h2>1. 데이터셋 개요</h2>
<table>
  <tr><th>파일</th><th>별칭</th><th>eps 프로파일</th><th>d 프로파일</th><th>원본 샘플</th><th>전처리 후</th><th>잔존율</th></tr>
  <tr>
    <td class="tag-A">collect_20260519_140039.csv</td>
    <td>Ramp</td><td>단조 증가 (0→30%)</td><td>왕복 스윔 (0↔36mm)</td>
    <td>{n_raw_A:,}</td><td>{n_cap_A:,}</td><td>{n_cap_A/n_raw_A*100:.1f}%</td>
  </tr>
  <tr>
    <td class="tag-B">collect_20260519_143611.csv</td>
    <td>Oscillate</td><td>왕복 진동 (0↔30%)</td><td>단계 하강 (36→0mm)</td>
    <td>{n_raw_B:,}</td><td>{n_cap_B:,}</td><td>{n_cap_B/n_raw_B*100:.1f}%</td>
  </tr>
</table>

<h2>2. 전처리 파이프라인</h2>
<p class="note">빨간 수치 = 해당 단계에서 제거된 샘플 수. 백분율은 원본 대비.</p>
<table>
  <tr>
    <th rowspan="2">단계</th>
    <th colspan="2" class="tag-A">140039 (Ramp)</th>
    <th colspan="2" class="tag-B">143611 (Oscillate)</th>
    <th rowspan="2">설명</th>
  </tr>
  <tr><th>잔존</th><th>제거</th><th>잔존</th><th>제거</th></tr>
  {pip_html}
</table>

<h3>2D Bin Sampling 방식</h3>
<p class="note">
  per-visit cap(축별 방문마다 제한)은 중간 구간이 양 끝보다 2배 많아지는 불균형 발생.<br>
  → eps×d 2D 그리드 각 셀에서 직접 최대 {CAP}개 균등 선택하는 방식으로 교체.
</p>
<table>
  <tr><th>항목</th><th>값</th></tr>
  <tr><td>eps 그리드</td><td>0~30%, 24 bins, 1.25%/bin</td></tr>
  <tr><td>d 그리드</td><td>0~36mm, 24 bins, 1.5mm/bin</td></tr>
  <tr><td>셀 수</td><td>24 × 24 = 576</td></tr>
  <tr><td>셀당 최대 샘플</td><td>{CAP}개</td></tr>
  <tr><td>이론적 최대</td><td>576 × {CAP} = {576*CAP:,}개 (데이터 없는 셀 제외 시 실제 더 적음)</td></tr>
</table>

<h2>3. Train / Val / Test 분할</h2>
<p class="note">전체 병합 후 random_state=42로 셔플 → 비율 분할. 소스 레이블 제거 후 저장.</p>
<table>
  <tr><th>Split</th><th>샘플 수</th><th>비율</th><th>파일</th></tr>
  <tr><td>Train</td><td>{len(train):,}</td><td>{len(train)/n_merged*100:.1f}%</td><td>train.csv</td></tr>
  <tr><td>Validation</td><td>{len(val):,}</td><td>{len(val)/n_merged*100:.1f}%</td><td>val.csv</td></tr>
  <tr><td>Test</td><td>{len(test):,}</td><td>{len(test)/n_merged*100:.1f}%</td><td>test.csv</td></tr>
  <tr><td><strong>Total</strong></td><td><strong>{n_merged:,}</strong></td><td>100%</td><td>—</td></tr>
</table>

<h2>4. 기술통계</h2>
{stats_table(train, "Train")}
{stats_table(val,   "Validation")}
{stats_table(test,  "Test")}

<h2>5. 분포 히스토그램</h2>
<p class="note">eps 및 d 축 기준 split별 샘플 분포.</p>
<img src="data:image/png;base64,{b64_hist}" alt="histogram">

<h2>6. eps × d 커버리지 (bin별 샘플 수)</h2>
<p class="note">24×24 그리드 기준. 색이 밝을수록 해당 셀 샘플 수 많음.</p>
<img src="data:image/png;base64,{b64_coverage}" alt="coverage">

<h2>7. 3D 분산 그래프 (Train / Val / Test)</h2>
<p class="note">원(●) = Train, 사각(■) = Val, 삼각(▲) = Test</p>
<img src="data:image/png;base64,{b64_scatter}" alt="scatter_3d">

</body>
</html>"""

report_path = OUT / "preprocessing_report.html"
report_path.write_text(html, encoding="utf-8")
print(f"Saved → {report_path}")
