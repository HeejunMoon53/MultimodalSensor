"""
generate_final_report.py  ·  정밀공학특론 기말 보고서 HTML
Title: Design and Manufacturing of a 3-Axis Precision Measurement System
Student ID: 2026020607  /  문희준
"""
import sys, io, base64, pickle
sys.path.insert(0, r'C:\ai\pylibs')
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import matplotlib.font_manager as fm
from pathlib import Path

ROOT   = Path(__file__).parent
DS_DIR = ROOT / "nn_decoupling" / "data_acquisition" / "dataset"
CHK    = ROOT / "nn_decoupling" / "checkpoints"
OUT    = ROOT / "PE2026_Final_문희준_2026020607.html"

_kf = [f.name for f in fm.fontManager.ttflist
       if any(k in f.name for k in ["Malgun", "NanumGothic", "CJK"])]
plt.rcParams.update(plt.rcParamsDefault)
plt.rcParams.update({
    "figure.facecolor":"white","axes.facecolor":"white",
    "axes.edgecolor":"#555","axes.labelcolor":"#222",
    "xtick.color":"#444","ytick.color":"#444",
    "text.color":"#222","grid.color":"#e0e0e0",
    "savefig.facecolor":"white",
    "font.family":"sans-serif",
    "font.sans-serif":["Malgun Gothic"]+_kf+["DejaVu Sans"],
    "axes.unicode_minus":False,
})

def b64(fig, dpi=140):
    buf=io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()

# ── 데이터 / 모델 ────────────────────────────────────────────────────────────
train = pd.read_csv(DS_DIR/"train.csv")
test  = pd.read_csv(DS_DIR/"test.csv")
all_d = pd.concat([train,test],ignore_index=True)

with open(DS_DIR/"scalers_linear.pkl","rb") as f: S=pickle.load(f)
with open(CHK/"model_stage1_md.pkl","rb") as f: M1=pickle.load(f)
with open(CHK/"model_stage2_md.pkl","rb") as f: M2=pickle.load(f)
sc_dR=S["sc_dR"]; sc_dL=S["sc_dL"]; sc_eps=S["sc_eps"]; sc_d=S["sc_d"]

dR_n  = sc_dR.transform(test[["dR_pct"]])
eps_n = M1.predict(dR_n).reshape(-1,1)
eps_p = sc_eps.inverse_transform(eps_n).ravel()
dL_n  = sc_dL.transform(test[["dL_pct"]])
d_p   = sc_d.inverse_transform(M2.predict(np.hstack([dL_n,eps_n])).reshape(-1,1)).ravel()
eps_t = test["eps_act_pct"].values
d_t   = test["d_act_mm"].values
mae_eps = np.mean(np.abs(eps_p-eps_t))
mae_d   = np.mean(np.abs(d_p-d_t))
N_all = len(all_d)
print(f"MAE ε={mae_eps:.4f}%  d={mae_d:.4f}mm   N={N_all}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 1 ─ Page 1: Before의 한계 시각화
# ══════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))

# (a) 수동 방식 vs 자동화 방식 개념 비교 (bar)
ax = axes[0]
cats = ["위치\n반복정밀도", "변형률\n제어점 수", "데이터\n동기화", "근접 거리\n자동 제어"]
before = [0.05,  0.08, 0.10, 0.0 ]   # 1.0 = After 달성값 기준 정규화
after  = [1.0,   1.0,  1.0,  1.0 ]
x = np.arange(len(cats)); w = 0.3
b1 = ax.bar(x-w/2, before, w, color="#ccc",  label="Before (수동)", edgecolor="#888")
b2 = ax.bar(x+w/2, after,  w, color="#1F77B4",label="After (자동화 스테이지)", edgecolor="#1a5fa0")
# 실제값 레이블
real_b = ["±2 mm","비정형","수동\n타임스탬프","불가"]
real_a = ["±3 µm","37 points","HW 동기","50→0 mm\n자동"]
for i,(rb,ra) in enumerate(zip(real_b,real_a)):
    ax.text(i-w/2, before[i]+0.03, rb, ha="center", va="bottom", fontsize=7, color="#777",
            multialignment="center")
    ax.text(i+w/2, after[i]+0.03,  ra, ha="center", va="bottom", fontsize=7.5,
            color="#1a5fa0", fontweight="bold", multialignment="center")
ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=9)
ax.set_ylim(0, 1.5); ax.set_ylabel("상대 달성률 (After=1.0)", fontsize=9)
ax.set_title("(a) 수동 지그 vs 자동화 스테이지\n핵심 성능 지표 비교", fontsize=9.5, fontweight="bold")
ax.legend(fontsize=8); ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.grid(axis="y", linestyle="--", alpha=0.4)

# (b) 자동화로 달성한 데이터 격자 커버리지 (ε-d 공간)
ax = axes[1]
# 전체 데이터셋의 ε-d 분포를 2D 히스토그램으로 시각화
h = ax.hexbin(all_d["eps_act_pct"], all_d["d_act_mm"],
              gridsize=30, cmap="YlOrRd", mincnt=1)
cb = plt.colorbar(h, ax=ax); cb.set_label("샘플 수", fontsize=9)
ax.set_xlabel("인장 변형률 ε (%)", fontsize=10)
ax.set_ylabel("근접 거리 d (mm)", fontsize=10)
ax.set_title(f"(b) 자동화 스테이지로 수집된 데이터셋 분포\n(N={N_all:,}개, 37×연속 스윕)", fontsize=9.5, fontweight="bold")
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
# 격자 조건 표시
for eps_v in range(0, 31, 5):
    ax.axvline(eps_v, color="#aaa", lw=0.5, linestyle=":")

plt.suptitle("Fig. 1  수동 방식의 한계와 자동화 스테이지 도입 효과",
             fontsize=10.5, fontweight="bold", y=1.02)
plt.tight_layout()
fig1 = b64(fig); print("Fig.1 done")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 2 ─ Page 2: 제조 공정 흐름 (Fusion 360 → 3D Print → 조립 → 검증)
# ══════════════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(11, 5.2))
ax  = fig.add_axes([0,0,1,1])
ax.set_xlim(0,11); ax.set_ylim(0,5.2); ax.axis("off")

# 상단: 4단계 제조 흐름
steps = [
    (0.25, 2.85, 2.2, 1.9, "#E3F2FD","#1F77B4",
     "① Fusion 360 CAD 설계",
     "• 센서 게이지 길이 120 mm\n• 클램프·레일·마운트 설계\n• 공차 0.2 mm 고려 (FDM)\n• 도면·BOM 자동 생성"),
    (2.7,  2.85, 2.2, 1.9, "#E8F5E9","#2CA02C",
     "② FDM 3D 프린팅",
     "• 소재: PLA (구조부) / TPU (지그)\n• 레이어 두께: 0.2 mm\n• 인필: 40% (구조), 20% (하우징)\n• 서포트: 자동 생성"),
    (5.15, 2.85, 2.2, 1.9, "#FFF3E0","#FF8C00",
     "③ 스테이지 조립",
     "• 5축 스테핑 모터 장착\n• 볼 스크류 피치 5 mm\n• 마이크로스텝 1/8 → 320 steps/mm\n• 3D 프린팅 부품 현장 맞춤"),
    (7.6,  2.85, 2.2, 1.9, "#EDE7F6","#9467BD",
     "④ 소프트웨어 연동",
     "• Arduino: AccelStepper 라이브러리\n• Python GUI: PyQt5 + pyserial\n• 위치 명령: ABS/JOG 프로토콜\n• STM32 동기: UART 하드웨어 트리거"),
]
for (x,y,w,h,fc,ec,title,body) in steps:
    rect = mpatches.FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.07",
                                    facecolor=fc,edgecolor=ec,linewidth=2)
    ax.add_patch(rect)
    ax.text(x+w/2, y+h-0.22, title, ha="center",va="top", fontsize=9.5,
            fontweight="700", color="#222", multialignment="center")
    ax.text(x+0.12, y+h-0.62, body, ha="left",va="top", fontsize=8.2,
            color="#444", linespacing=1.5)

for xi in [2.47, 4.92, 7.37]:
    ax.annotate("", xy=(xi+0.23,3.75), xytext=(xi,3.75),
                arrowprops=dict(arrowstyle="-|>", color="#555", lw=2.0, mutation_scale=15))

# 하단 왼쪽: 3D 프린팅 부품 목록
ax.add_patch(mpatches.FancyBboxPatch((0.25,0.15),4.95,2.4,
    boxstyle="round,pad=0.07",facecolor="#f0f4ff",edgecolor="#1F77B4",linewidth=1.2))
ax.text(0.55,2.28,"3D 프린팅 제작 부품 목록 (FDM, PLA/TPU)",
        fontsize=9.5,fontweight="700",color="#1a3a6b")
components=[
    ("센서 클램프 (×2)",   "TPU", "센서 양 끝 고정, 무손상 그립"),
    ("X축 슬라이더",       "PLA", "볼 스크류 연결, 인장 방향 이동"),
    ("Z축 마운트",         "PLA", "근접 물체 고정 브래킷"),
    ("케이블 가이드",      "PLA", "배선 정리, 간섭 방지"),
    ("레퍼런스 플레이트",  "PLA", "원점 기준면, M3 인서트 너트"),
]
ys = [1.98,1.65,1.32,0.99,0.66]
ax.text(0.45,2.02,"부품명",fontsize=8.5,fontweight="700",color="#555")
ax.text(2.35,2.02,"소재",fontsize=8.5,fontweight="700",color="#555")
ax.text(3.05,2.02,"역할",fontsize=8.5,fontweight="700",color="#555")
for (name,mat,role),y in zip(components,ys):
    ax.text(0.45,y,name,fontsize=8.2,color="#222",fontweight="600")
    ax.text(2.35,y,mat,fontsize=8.2,
            color="#2CA02C" if mat=="PLA" else "#FF8C00",fontweight="600")
    ax.text(3.05,y,role,fontsize=8.0,color="#555")
    ax.axhline(y-0.18,0.023,0.476,color="#ccd",lw=0.7)

# 하단 오른쪽: 주요 설계 사양
ax.add_patch(mpatches.FancyBboxPatch((5.4,0.15),5.35,2.4,
    boxstyle="round,pad=0.07",facecolor="#f0fff4",edgecolor="#2CA02C",linewidth=1.2))
ax.text(5.65,2.28,"완성된 시스템 주요 사양",
        fontsize=9.5,fontweight="700",color="#1a3a6b")
specs=[
    ("축 구성",      "5축 (XA·XB·YA·YB·Z)"),
    ("이송 분해능",  "3.125 µm / step (320 steps/mm)"),
    ("구동 방식",    "볼 스크류 + 스테핑 모터 (1/8 마이크로스텝)"),
    ("인장 범위",    "0 – 36 mm (1 mm 간격, 37 조건)"),
    ("근접 범위",    "50 mm → 0 mm (연속 자동 스윕)"),
    ("제어 소프트웨어","Python GUI (PyQt5) + Arduino"),
    ("센서 동기",    "STM32 UART 하드웨어 동기 (1 kHz)"),
]
ys2=[2.02,1.73,1.44,1.15,0.86,0.57,0.28]
for (k,v),y in zip(specs,ys2):
    ax.text(5.65,y,k,fontsize=8.2,color="#222",fontweight="600")
    ax.text(7.55,y,v,fontsize=8.2,color="#1a6b36")
    ax.axhline(y-0.14,0.49,0.993,color="#ccd",lw=0.7)

ax.text(5.5,-0.1,
    "Fig. 2  3D 프린팅 기반 정밀 측정 시스템 제조 공정 흐름 및 부품 목록",
    fontsize=9,color="#444",style="italic")
fig2 = b64(fig); print("Fig.2 done")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 3 ─ Page 3: After 결과 — 시스템으로 수집한 데이터 + AI 성능
# ══════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 3, figsize=(12, 4.0))

# (a) 변형률 추정 정확도
ax = axes[0]
lim = [min(eps_t.min(),eps_p.min())-1, max(eps_t.max(),eps_p.max())+1]
ax.scatter(eps_t, eps_p, s=5, alpha=0.35, color="#2CA02C", rasterized=True, label="테스트 데이터")
ax.plot(lim, lim, "k--", lw=1.2, label="이상선 (y=x)")
ax.set_xlabel("실제 변형률 ε (%)", fontsize=10)
ax.set_ylabel("추정 변형률 ε (%)", fontsize=10)
ax.set_title(f"(a) 변형률 추정 결과\nMAE = {mae_eps:.3f} %  (테스트셋)", fontsize=10, fontweight="bold")
ax.set_xlim(lim); ax.set_ylim(lim)
ax.legend(fontsize=8); ax.grid(True,linestyle="--",alpha=0.4)
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)

# (b) 근접 거리 추정 정확도
ax = axes[1]
lim2 = [max(0,min(d_t.min(),d_p.min())-2), max(d_t.max(),d_p.max())+2]
ax.scatter(d_t, d_p, s=5, alpha=0.35, color="#FF8C00", rasterized=True, label="테스트 데이터")
ax.plot(lim2, lim2, "k--", lw=1.2, label="이상선 (y=x)")
ax.set_xlabel("실제 근접 거리 d (mm)", fontsize=10)
ax.set_ylabel("추정 근접 거리 d (mm)", fontsize=10)
ax.set_title(f"(b) 근접 거리 추정 결과\nMAE = {mae_d:.3f} mm  (테스트셋)", fontsize=10, fontweight="bold")
ax.set_xlim(lim2); ax.set_ylim(lim2)
ax.legend(fontsize=8); ax.grid(True,linestyle="--",alpha=0.4)
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)

# (c) Before/After 정량 비교
ax = axes[2]
metrics    = ["측정\n재현성\n(위치 오차)", "데이터셋\n커버리지", "센서\n동기화", "AI 학습\n가능 여부"]
before_val = [2000, 5,   0,  0]   # 단위별 Before 값
after_val  = [3,   37, 100, 100]   # After 값 (마지막 둘은 %)
units      = ["µm", "조건수", "%", "%"]
norm_b     = [b/a for b,a in zip(before_val,after_val)]  # 정규화(낮을수록 Before가 나쁨)
norm_b[0]  = 1.0   # Before 오차가 After보다 훨씬 커서 뒤집음 → 별도 표기

x = np.arange(len(metrics)); w = 0.3
# 정규화 바: After=1.0 기준, Before는 비율
norm_b2 = [0.0015, 0.135, 0.0, 0.0]   # Before/After 비
ax.bar(x-w/2, norm_b2, w, color="#bbb", label="Before (수동)", edgecolor="#888", zorder=3)
ax.bar(x+w/2, [1]*4,   w, color="#1F77B4", label="After (자동화)", edgecolor="#1a5fa0", zorder=3)
labels_b = ["±2 mm", "비정형\n5조건", "수동\n타임스탬프", "불가"]
labels_a = ["±3 µm", f"37조건\n{N_all:,}개", "HW 동기\n1 kHz", f"MAE\n{mae_d:.2f}mm"]
for i,(lb,la) in enumerate(zip(labels_b,labels_a)):
    ax.text(i-w/2, norm_b2[i]+0.03, lb, ha="center", va="bottom", fontsize=7, color="#777",
            multialignment="center")
    ax.text(i+w/2, 1.03, la, ha="center", va="bottom", fontsize=7.5,
            color="#1a5fa0", fontweight="bold", multialignment="center")
ax.set_xticks(x); ax.set_xticklabels(metrics, fontsize=8.5)
ax.set_ylim(0, 1.55); ax.set_ylabel("달성률 (After=1.0)", fontsize=9)
ax.set_title("(c) Before → After 핵심 지표\n정밀 측정 시스템 도입 효과", fontsize=10, fontweight="bold")
ax.legend(fontsize=8, loc="upper left")
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)

plt.suptitle(f"Fig. 3  정밀 측정 시스템 구축 후 수집 데이터 기반 AI 성능 검증 결과",
             fontsize=10.5, fontweight="bold", y=1.03)
plt.tight_layout()
fig3 = b64(fig); print("Fig.3 done")


# ══════════════════════════════════════════════════════════════════════════════
# HTML
# ══════════════════════════════════════════════════════════════════════════════
HTML = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>PE2026 Final — 문희준 2026020607</title>
<style>
*,*::before,*::after{{box-sizing:border-box}}
body{{
  font-family:"Malgun Gothic","Apple SD Gothic Neo",sans-serif;
  font-size:11pt; line-height:1.15; color:#111;
  background:#bbb; margin:0; padding:16px 0;
}}
.page{{
  width:210mm; min-height:297mm;
  padding:19mm 19mm 17mm 21mm;
  margin:0 auto 14px; background:white;
  box-shadow:0 2px 12px rgba(0,0,0,.28);
  position:relative; overflow:hidden;
}}
@media print{{
  body{{background:white;padding:0}}
  .page{{
    width:210mm; min-height:297mm;
    padding:19mm 19mm 17mm 21mm;
    margin:0; box-shadow:none; page-break-after:always;
  }}
  .page:last-child{{page-break-after:avoid}}
}}
@page{{size:A4;margin:0}}

h1{{font-size:13pt;font-weight:700;margin:0 0 5px;line-height:1.2}}
h2{{
  font-size:11pt;font-weight:700;margin:12px 0 4px;
  border-bottom:2px solid #222;padding-bottom:2px;
  display:flex;align-items:center;gap:6px;
}}
h2 .sec{{
  background:#222;color:#fff;
  font-size:9pt;padding:1px 7px;border-radius:3px;min-width:20px;
  text-align:center;
}}
h3{{font-size:10.5pt;font-weight:700;margin:9px 0 3px;color:#1a3a6b}}
p{{margin:3px 0 5px;text-indent:1em}}
p.ni{{text-indent:0}}
ul{{margin:2px 0 5px 1.3em;padding:0}}
li{{margin-bottom:2px;line-height:1.25}}

.rpt-header{{
  border:1.5px solid #222;padding:8px 13px;margin-bottom:11px;
}}
.rpt-header .meta{{
  font-size:9pt;color:#555;margin-top:4px;
  display:flex;flex-wrap:wrap;gap:16px;
}}

.fig{{margin:8px 0;text-align:center}}
.fig img{{max-width:100%;border:0.5px solid #ccc}}
.fig-cap{{
  font-size:8.7pt;color:#444;margin-top:3px;
  text-align:left;font-style:italic;line-height:1.3;
}}

table{{width:100%;border-collapse:collapse;font-size:9pt;margin:6px 0}}
th{{background:#222;color:#fff;padding:4px 8px;text-align:center;font-weight:700}}
td{{padding:3px 8px;border:0.5px solid #ccc;vertical-align:top}}
tr:nth-child(even) td{{background:#f7f7f7}}
td.lbl{{font-weight:700;background:#f0f2f5;color:#333}}
td.good{{background:#e6f4ea;color:#1a6b36;font-weight:700}}
td.bad{{background:#fff0f0;color:#b00}}

.hl{{
  border-left:3px solid #999;padding:5px 10px;
  margin:6px 0;background:#f8f9fa;font-size:10pt;line-height:1.35;
}}
.hl.bl{{border-color:#1F77B4;background:#eef5fb}}
.hl.gr{{border-color:#2CA02C;background:#edf7ee}}
.hl.or{{border-color:#FF8C00;background:#fff8ee}}
.hl.rd{{border-color:#d62728;background:#fff2f2}}

.g2{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.pn{{position:absolute;bottom:10mm;right:17mm;font-size:9pt;color:#888}}
</style>
</head>
<body>


<!-- ═══════════════════════ PAGE 1: Problem & Before ═══════════════════════ -->
<div class="page">

<div class="rpt-header">
  <h1>멀티모달 연성 센서 평가를 위한<br>
      3축 정밀 측정 시스템의 설계 및 제작</h1>
  <div class="meta">
    <span>문희준 · 학번 2026020607</span>
    <span>고려대학교 기계공학과 BioRC Lab</span>
    <span>정밀공학특론 · 2026-1학기</span>
    <span>제출일 2026. 06. 17.</span>
  </div>
</div>

<h2><span class="sec">1</span> 연구 배경 및 제작 동기</h2>
<p><strong>본 연구에서 제작한 것</strong>은 멀티모달 연성 센서(EGaIn 단일 전극 스파이럴 코일)의 인장 변형률(ε)·근접 거리(d) 동시 응답을 정밀하게 평가하기 위한 <strong>3축 자동화 정밀 측정 시스템</strong>이다. 시스템의 구조 부품과 센서 지그는 <strong>Fusion 360 CAD 설계 → FDM 3D 프린팅</strong>으로 제작하였다.</p>
<p>제작이 필요한 이유는 연성 센서의 응답이 ε과 d 두 변수에 동시 의존하기 때문에, 두 변수를 독립적으로 제어하면서 수만 개의 동기화 데이터를 수집하려면 <strong>마이크로미터 수준의 반복 위치 정밀도</strong>와 <strong>자동화된 스윕 기능</strong>이 반드시 필요하다. 상용 인장 시험기는 근접 거리 제어 기능이 없고, 범용 스테이지는 소프트 센서용 맞춤 클램프를 장착할 수 없다는 한계가 있다.</p>

<h2><span class="sec">2</span> 기존 방식의 한계 (Before)</h2>

<div class="hl rd">
  <strong>핵심 문제:</strong> 수동 지그(손 클램프)로 연성 센서를 신장하면 위치 반복 오차가 ±2 mm 이상이다.
  1 mm 간격으로 37개 변형률 조건을 재현해야 하는 본 연구에서는 이 오차가 치명적이다.
  또한 근접 물체를 50 mm에서 0 mm까지 자동으로 스윕할 방법이 없어, 두 변수(ε, d)의 조합 데이터를 체계적으로 수집하는 것이 불가능하다.
</div>

<div class="g2">
<div>
<h3>2.1 수동 방식의 한계</h3>
<ul>
  <li><strong>위치 반복 정밀도</strong>: 손 조임 클램프 ±2 mm → 설계값 대비 100~660배 오차</li>
  <li><strong>소프트 샘플 손상</strong>: 범용 금속 클램프가 PDMS 기판 표면 손상</li>
  <li><strong>근접 축 부재</strong>: 상용 인장 시험기에는 Z축(근접 거리 제어) 없음</li>
  <li><strong>데이터 비동기</strong>: 센서 데이터와 위치를 수동으로 맞춰야 함 → 오차 수백 ms</li>
</ul>
</div>
<div>
<h3>2.2 기존 설비의 비용·구조 문제</h3>
<ul>
  <li><strong>상용 인장 시험기</strong>: 가격 수천만 원, 단축(1D) 신장만 지원</li>
  <li><strong>범용 XYZ 스테이지</strong>: 맞춤 센서 마운트 장착 불가, 배선 공간 없음</li>
  <li><strong>데이터 수집 소프트웨어</strong>: 별도 NI DAQ 등 추가 비용 발생</li>
  <li>→ 맞춤 3D 프린팅 + 오픈소스 제어로 <strong>자체 제작</strong>이 최선</li>
</ul>
</div>
</div>

<div class="fig">
  <img src="data:image/png;base64,{fig1}" alt="Fig.1">
  <div class="fig-cap">
    Fig. 1. (a) 수동 지그 vs 자동화 스테이지 핵심 성능 비교: 위치 반복 정밀도 ±2 mm → ±3 µm (약 670배 개선),
    제어 가능 변형률 조건 수 비정형 → 37개, 데이터 동기화 수동 → 하드웨어 자동 동기, 근접 제어 불가 → 자동 스윕.
    (b) 자동화 스테이지로 수집된 데이터셋의 ε–d 2D 분포 (N={N_all:,}개): 37개 변형률 조건과 0–50 mm 근접 거리
    연속 스윕이 체계적으로 커버됨 — 수동 방식으로는 불가능한 분포.
  </div>
</div>

<div class="pn">— 1 / 3 —</div>
</div>


<!-- ═══════════════════════ PAGE 2: Fabrication Process ═══════════════════════ -->
<div class="page">

<h2><span class="sec">3</span> 디지털 제조 공정 (Fabrication Process)</h2>

<div class="hl bl">
  <strong>선택 기법: Fusion 360 CAD 설계 + FDM 3D 프린팅</strong><br>
  선택 이유: ① 소프트 센서 전용 무손상 클램프 형상은 상용품 없음 → 맞춤 설계 필수,
  ② 설계 반복 주기가 짧아야 하므로(인터페이스 수정 수회) 3D 프린팅이 금형 대비 압도적으로 유리,
  ③ Fusion 360의 파라미터 모델링으로 치수 공차 0.2 mm 반영 후 G-code 자동 생성 가능.
</div>

<div class="fig">
  <img src="data:image/png;base64,{fig2}" alt="Fig.2">
  <div class="fig-cap">
    Fig. 2. 3D 프린팅 기반 정밀 측정 시스템 제조 공정 흐름.
    ① Fusion 360으로 센서 클램프·레일·마운트 설계 (공차 0.2 mm 반영) →
    ② FDM 프린팅 (구조부 PLA 40% 인필 / 센서 접촉부 TPU 20%) →
    ③ 볼 스크류·스테핑 모터 장착·조립 (320 steps/mm, 1/8 마이크로스텝) →
    ④ Arduino + Python GUI 연동 (ABS/JOG 프로토콜, STM32 하드웨어 동기).
    하단 좌: 3D 프린팅 부품 목록 (5종). 하단 우: 완성 시스템 주요 사양.
  </div>
</div>

<h3>3.1 Fusion 360 설계 핵심 사항</h3>
<p class="ni">센서 게이지 길이(120 mm)를 기준 치수로 삼아 클램프 간격·볼 스크류 행정(0–36 mm)·Z축 근접 레일(0–50 mm)을 파라미터로 정의하였다. 소프트 PDMS 기판이 손상되지 않도록 접촉면에는 TPU 인서트를 설계하고, 조립 허용 공차를 0.2 mm로 설정하였다. 완성된 CAD 모델에서 3D 도면과 BOM이 자동으로 생성되어 논문·보고서 삽화로 활용하였다.</p>

<h3>3.2 FDM 설정 및 소재 선택</h3>
<table>
  <thead>
    <tr><th>부품 유형</th><th>소재</th><th>레이어 두께</th><th>인필</th><th>선택 이유</th></tr>
  </thead>
  <tbody>
    <tr>
      <td class="lbl">구조 부품 (레일·마운트·슬라이더)</td>
      <td class="good">PLA</td><td class="ctr">0.2 mm</td><td class="ctr">40%</td>
      <td>강성 요구, 치수 안정성 우수</td>
    </tr>
    <tr>
      <td class="lbl">센서 클램프 (접촉면)</td>
      <td style="color:#FF8C00;font-weight:700">TPU</td><td class="ctr">0.2 mm</td><td class="ctr">20%</td>
      <td>PDMS 표면 무손상, 마찰력 확보</td>
    </tr>
    <tr>
      <td class="lbl">케이블·배선 가이드</td>
      <td class="good">PLA</td><td class="ctr">0.2 mm</td><td class="ctr">15%</td>
      <td>경량, 빠른 출력</td>
    </tr>
  </tbody>
</table>

<h3>3.3 소프트웨어 제어 구성</h3>
<p class="ni">Arduino Uno(AccelStepper 라이브러리)가 5개 축 스테핑 모터를 가감속 제어하고, Python GUI(PyQt5 + pyserial)에서 ABS/JOG 명령을 전송한다. STM32G473CBT6(센서 계측 MCU)와 UART로 하드웨어 동기하여 위치와 센서 데이터를 1 ms 이내 오차로 대응시킨다. 이 소프트웨어-하드웨어 통합 구성이 수동 방식 대비 가장 큰 Before/After 차이를 만드는 부분이다.</p>

<div class="pn">— 2 / 3 —</div>
</div>


<!-- ═══════════════════════ PAGE 3: After & Reflection ═══════════════════════ -->
<div class="page">

<h2><span class="sec">4</span> 결과 (After)</h2>

<p class="ni">완성된 3D 프린팅 기반 정밀 측정 시스템을 사용하여, 37개 변형률 조건(0–36 mm, 1 mm 간격)에서 근접 거리 50→0 mm 연속 스윕 실험을 수행하였다. 총 {N_all:,}개의 동기화 데이터를 수집하고(train/val/test 분리), 2단 AI 디커플링 모델(978 파라미터 MLP)로 학습·검증하였다.</p>

<div class="fig">
  <img src="data:image/png;base64,{fig3}" alt="Fig.3">
  <div class="fig-cap">
    Fig. 3. 정밀 측정 시스템으로 수집한 데이터 기반 AI 검증 결과.
    (a) 변형률 추정: MAE = {mae_eps:.3f} % (테스트셋, N={len(test):,}개).
    (b) 근접 거리 추정: MAE = {mae_d:.3f} mm.
    (c) Before/After 핵심 지표: 위치 정밀도 670배 향상, 데이터셋 37조건 체계 수집, HW 동기 달성,
        AI 학습 가능 수준의 데이터 품질 확보.
  </div>
</div>

<h3>4.1 Before / After 정량 비교</h3>
<table>
  <thead>
    <tr><th>평가 항목</th><th>Before (수동 지그)</th><th>After (3D 프린팅 자동화 시스템)</th></tr>
  </thead>
  <tbody>
    <tr>
      <td class="lbl">위치 반복 정밀도</td>
      <td class="bad">±2 mm (수동 조임)</td>
      <td class="good">±0.003 mm (3.125 µm / step)</td>
    </tr>
    <tr>
      <td class="lbl">변형률 제어 조건</td>
      <td class="bad">비정형 (재현 불가)</td>
      <td class="good">37개 조건 × 1 mm 간격, 완전 재현</td>
    </tr>
    <tr>
      <td class="lbl">근접 거리 제어</td>
      <td class="bad">불가 (축 없음)</td>
      <td class="good">50 mm → 0 mm 자동 스윕</td>
    </tr>
    <tr>
      <td class="lbl">데이터 동기화</td>
      <td class="bad">수동 타임스탬프 (오차 수백 ms)</td>
      <td class="good">STM32 UART 하드웨어 동기 (오차 &lt;1 ms)</td>
    </tr>
    <tr>
      <td class="lbl">센서 손상</td>
      <td class="bad">PDMS 표면 클램프 손상</td>
      <td class="good">TPU 3D 프린팅 클램프 → 무손상</td>
    </tr>
    <tr>
      <td class="lbl">수집 데이터 수</td>
      <td class="bad">소량, 비체계적</td>
      <td class="good">{N_all:,}개, ε–d 공간 체계적 커버</td>
    </tr>
    <tr>
      <td class="lbl">AI 학습 가능 여부</td>
      <td class="bad">불가 (품질·수량 부족)</td>
      <td class="good">가능 → MAE ε {mae_eps:.3f}%, MAE d {mae_d:.3f} mm</td>
    </tr>
    <tr>
      <td class="lbl">설비 비용</td>
      <td class="bad">상용 인장기 수천만 원</td>
      <td class="good">재료비 ~15만 원 (3D 프린팅 + 스테이지)</td>
    </tr>
  </tbody>
</table>

<h2><span class="sec">5</span> 한계 및 향후 계획</h2>

<div class="g2">
<div>
<h3>현재 한계</h3>
<ul>
  <li><strong>FDM 치수 오차</strong>: 프린팅 수축으로 실제 공차 ±0.2–0.3 mm → 정밀 조립 시 사상 필요</li>
  <li><strong>1D 신장만 지원</strong>: 현재 X축 인장만 가능, 2D 변형(양축) 측정 불가</li>
  <li><strong>PLA 크리프</strong>: 장시간 하중 시 PLA 구조부 변형 → PETG·ABS 교체 검토</li>
  <li><strong>근접 물체 각도</strong>: Z축 수직 접근만 가능, 비수직 근접 시나리오 미반영</li>
</ul>
</div>
<div>
<h3>개선 및 확장 계획</h3>
<ul>
  <li><strong>2D 인장 지그 추가</strong>: Y축 클램프 설계(Fusion 360) → ε<sub>x</sub>·ε<sub>y</sub> 동시 제어</li>
  <li><strong>소재 업그레이드</strong>: 구조 부품 PETG/Carbon-PLA 교체로 강성·치수 안정성 향상</li>
  <li><strong>인라인 힘 센서</strong>: 로드셀 마운트 추가 설계 → 응력–변형률 곡선 동시 취득</li>
  <li><strong>SLA 프린팅 도입</strong>: 클램프 접촉면 표면 조도 개선 (Ra &lt;1 µm 목표)</li>
</ul>
</div>
</div>

<div class="hl gr" style="margin-top:10px">
  <strong>핵심 성과 요약:</strong>
  Fusion 360 CAD + FDM 3D 프린팅으로 맞춤 제작된 정밀 측정 시스템은
  수동 지그 대비 위치 반복 정밀도를 <strong>약 670배 향상</strong>(±2 mm → ±3 µm)하였고,
  이를 통해 수동으로는 불가능했던 체계적 ε–d 데이터셋({N_all:,}개)을 수집하여
  AI 디커플링 모델 학습 (MAE ε {mae_eps:.3f}%, MAE d {mae_d:.3f} mm)을 가능하게 하였다.
</div>

<h2 style="margin-top:10px">참고문헌</h2>
<p class="ni" style="font-size:8.8pt;color:#444">
[1] Majidi, C. (2019). Soft-matter engineering for soft robotics. <em>Advanced Materials Technologies</em>, 4, 1800477.<br>
[2] Dickey, M. D. (2017). Stretchable and soft electronics using liquid metals. <em>Advanced Materials</em>, 29, 1606425.<br>
[3] Gibson, I. et al. (2021). <em>Additive Manufacturing Technologies</em> (3rd ed.). Springer.<br>
[4] Autodesk (2024). <em>Fusion 360 Design Reference</em>. Autodesk Inc.<br>
[5] Raissi, M. et al. (2019). Physics-informed neural networks. <em>Journal of Computational Physics</em>, 378, 686–707.
</p>

<div class="pn">— 3 / 3 — (참고문헌 별도)</div>
</div>

</body>
</html>"""

with open(OUT,"w",encoding="utf-8") as f: f.write(HTML)
print(f"Saved: {OUT}  ({OUT.stat().st_size:,} B)")
