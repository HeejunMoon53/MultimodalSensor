"""arch_search 결과로 edge_ai_report.html 섹션 생성 + 삽입."""
import json, base64, io, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
CKPT = os.path.join(HERE, "checkpoints")
DATA = os.path.join(HERE, "data_acquisition", "dataset")
HTML = os.path.join(HERE, "edge_ai_report.html")

# ── 결과 로드 + step_eps 버그(×100) 수정 ───────────────────────────────────
with open(os.path.join(CKPT, "arch_search_results.json"), encoding="utf-8") as f:
    results = json.load(f)

for r in results:
    v = r["int8"]["step_eps_pct"]
    if v > 1.0:   # 아직 수정 전이면 (>1% → 버그값)
        r["int8"]["step_eps_pct"] = round(v / 100.0, 4)

# ── Pareto PNG → base64 ───────────────────────────────────────────────────
with open(os.path.join(DATA, "arch_search_pareto.png"), "rb") as f:
    b64_pareto = base64.b64encode(f.read()).decode()

# ── INT8 해상도 비교 그래프 ────────────────────────────────────────────────
rs = sorted(results, key=lambda x: x["params"])
names    = [r["name"]                 for r in rs]
params   = [r["params"]               for r in rs]
step_eps = [r["int8"]["step_eps_pct"] for r in rs]
step_d   = [r["int8"]["step_d_mm"]    for r in rs]

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
x = np.arange(len(names))
colors_eps = ["#FF8C00" if n == "base" else "#1F77B4" for n in names]
colors_d   = ["#FF8C00" if n == "base" else "#2CA02C" for n in names]

ax = axes[0]
ax.bar(x, step_eps, color=colors_eps, alpha=0.8)
ax.set_xticks(x); ax.set_xticklabels(names, rotation=40, ha="right", fontsize=8.5)
ax.set_ylabel("ε output 1-step [%]", fontsize=10)
ax.set_title("INT8 ε 출력 해상도 (1-step 크기)\n낮을수록 세밀한 분해능", fontweight="bold")
ax.axhline(0.1212, color="red", ls="--", lw=1.5, label="현재 배포 (0.121%)")
ax.legend(fontsize=9); ax.grid(True, alpha=0.3, axis="y")
for xi, (p, v) in enumerate(zip(params, step_eps)):
    ax.text(xi, v + 0.0003, f"{p}p", ha="center", va="bottom", fontsize=7)

ax2 = axes[1]
ax2.bar(x, step_d, color=colors_d, alpha=0.8)
ax2.set_xticks(x); ax2.set_xticklabels(names, rotation=40, ha="right", fontsize=8.5)
ax2.set_ylabel("d output 1-step [mm]", fontsize=10)
ax2.set_title("INT8 d 출력 해상도 (1-step 크기)\n낮을수록 세밀한 분해능", fontweight="bold")
ax2.axhline(0.139, color="red", ls="--", lw=1.5, label="현재 배포 (0.139mm)")
ax2.legend(fontsize=9); ax2.grid(True, alpha=0.3, axis="y")
for xi, (p, v) in enumerate(zip(params, step_d)):
    ax2.text(xi, v + 0.001, f"{p}p", ha="center", va="bottom", fontsize=7)

plt.suptitle("INT8 출력 해상도 비교 (아키텍처별)", fontsize=12, fontweight="bold")
plt.tight_layout()
buf = io.BytesIO()
plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
plt.close(fig)
b64_res = base64.b64encode(buf.getvalue()).decode()

# ── HTML 테이블 행 생성 ────────────────────────────────────────────────────
BASE_d   = 1.7822
BASE_eps = 0.3491
BASE_p   = 818

def pct_badge(v, ref, lower_better=True):
    diff = (v - ref) / ref * 100
    if abs(diff) < 0.5:
        return ""
    good = (diff < 0 and lower_better) or (diff > 0 and not lower_better)
    col  = "#27ae60" if good else "#c0392b"
    return f'<span style="color:{col};font-size:.82em"> ({diff:+.1f}%)</span>'

rows = ""
for r in sorted(results, key=lambda x: x["params"]):
    i8   = r["int8"]
    d15s = f"{r['mae_d15']:.4f}" if r["mae_d15"] else "-"
    d10s = f"{r['mae_d10']:.4f}" if r["mae_d10"] else "-"
    bg   = "background:#fff8ee;font-weight:bold;" if r["name"] == "base" else ""
    if r["name"] == "base":
        note = "<b>← 현재 배포</b>"
    elif r["name"] == "medium-deep":
        note = '<span style="color:#2CA02C">★ 정확도 추천</span>'
    elif r["name"] == "small":
        note = '<span style="color:#9467BD">◆ 경량화 추천</span>'
    else:
        note = ""
    rows += (
        f'<tr style="{bg}">'
        f"<td>{r['name']}</td>"
        f"<td style='text-align:center'>{r['s1_hidden']}</td>"
        f"<td style='text-align:center'>{r['s2_hidden']}</td>"
        f"<td style='text-align:right'>{r['params']:,}{pct_badge(r['params'], BASE_p)}</td>"
        f"<td style='text-align:right'>{r['macs']:,}</td>"
        f"<td style='text-align:right'>{r['mae_eps']:.4f}{pct_badge(r['mae_eps'], BASE_eps)}</td>"
        f"<td style='text-align:right'>{r['mae_d']:.4f}{pct_badge(r['mae_d'], BASE_d)}</td>"
        f"<td style='text-align:right'>{d15s}</td>"
        f"<td style='text-align:right'>{d10s}</td>"
        f"<td style='text-align:right'>{i8['dz_dR_pct']:.4f}</td>"
        f"<td style='text-align:right'>{i8['step_eps_pct']:.4f}</td>"
        f"<td style='text-align:right'>{i8['step_d_mm']:.4f}</td>"
        f"<td>{note}</td>"
        "</tr>\n"
    )

# ── HTML 섹션 조립 ────────────────────────────────────────────────────────
SECTION = f"""
<!-- ═══════════════════════════════════════════ 6c. ARCH SEARCH ═ -->
<section id="arch-search">
  <h2><span class="icon">🔬</span> 6c. 아키텍처 탐색 결과</h2>

  <div class="highlight info">
    <strong>목적</strong>: INT8 배포 최적화를 위해 파라미터 수 대비 정확도 Pareto frontier 탐색.
    현재 배포 모델(818p)이 최적인지 검증하고, 더 작은/큰 모델로 교체 가능성 평가.
  </div>

  <h3>탐색 방법론</h3>
  <table>
    <tr><th>항목</th><th>설정</th></tr>
    <tr><td>탐색 아키텍처</td><td>13개 (nano 46p ~ large 10,946p)</td></tr>
    <tr><td>활성화 함수</td><td>Tanh — bounded, INT8 친화적 (출력 [-1, 1] 보장)</td></tr>
    <tr><td>손실 함수</td><td>MSE only — 물리 손실 제외 → 아키텍처 효과 순수 분리</td></tr>
    <tr><td>최적화</td><td>AdamW (lr=1e-3, wd=1e-4) + CosineAnnealingLR (T_max=300)</td></tr>
    <tr><td>Early stopping</td><td>patience=40 (val d MAE 기준)</td></tr>
    <tr><td>데이터 분할</td><td>train 23,415 / val 5,017 / test 5,018 (동일 random_state=42)</td></tr>
    <tr><td>INT8 스케일 추정</td><td>train+val 전체를 calibration 데이터로 사용,
        per-tensor scale = max|activation|/127</td></tr>
    <tr><td>랜덤 시드</td><td>42 (모든 config 동일 → 공정 비교)</td></tr>
  </table>

  <h3>전체 결과 (파라미터 수 오름차순)</h3>
  <p style="font-size:.85em;color:#888;margin:-8px 0 10px">
    ε/d MAE: test set 기준. INT8 dead-zone/step: calibration 추정값 (실측 오차 ±10% 수준).
    괄호 %는 현재 배포 base(818p) 대비 변화량.
    <span style="color:#27ae60">초록=개선</span> /
    <span style="color:#c0392b">빨강=악화</span>.
  </p>
  <div style="overflow-x:auto">
  <table style="font-size:.87em;min-width:960px">
    <tr>
      <th rowspan="2">이름</th>
      <th colspan="2">아키텍처</th>
      <th rowspan="2">파라미터</th>
      <th rowspan="2">MACs</th>
      <th colspan="4">정확도 (test set)</th>
      <th colspan="3">INT8 해상도 추정</th>
      <th rowspan="2">비고</th>
    </tr>
    <tr>
      <th>S1 hidden</th><th>S2 hidden</th>
      <th>ε MAE [%]</th><th>d MAE [mm]</th>
      <th>d≤15mm [mm]</th><th>d≤10mm [mm]</th>
      <th>dR dead-zone [%]</th><th>ε step [%]</th><th>d step [mm]</th>
    </tr>
    {rows}
  </table>
  </div>

  <h3>Pareto Frontier — 파라미터 수 vs 근접도 MAE</h3>
  <p style="font-size:.85em;color:#888;margin:-8px 0 10px">
    주황 점 = 현재 배포(base, 818p). 빨간 점선 = Pareto frontier
    (같은 파라미터 예산으로 달성 가능한 최저 오차 경계선).
  </p>
  <img src="data:image/png;base64,{b64_pareto}" alt="arch_search_pareto">

  <h3>INT8 출력 해상도 비교 (아키텍처별)</h3>
  <p style="font-size:.85em;color:#888;margin:-8px 0 10px">
    빨간 점선 = 현재 배포 값. 주황 막대 = base(현재). 파란/초록 막대 = 비교 후보.
    dR 입력 dead-zone은 StandardScaler 정규화에 의해 모든 아키텍처에서 동일(0.085%).
  </p>
  <img src="data:image/png;base64,{b64_res}" alt="arch_search_int8_resolution">

  <h3>핵심 발견사항</h3>
  <table>
    <tr><th>관찰</th><th>내용</th></tr>
    <tr>
      <td>✅ dR dead-zone 아키텍처 무관</td>
      <td>0.0849%로 전 모델 동일. StandardScaler 정규화 → 입력 범위 고정.
          입력 해상도는 어떤 아키텍처로 교체해도 개선 불가.</td>
    </tr>
    <tr>
      <td>📌 Pareto knee: <b>tiny-deep (138p)</b></td>
      <td>nano(46p)→tiny(90p) 구간에서 d MAE 2.11mm로 정체.
          tiny-deep(138p)에서 1.84mm로 급감 — 2층(depth)이 1층 wide보다 효과적.
          138p 이상부터는 수익체감 구간 진입.</td>
    </tr>
    <tr>
      <td>📌 현재 base(818p) = <b>합리적 선택</b></td>
      <td>small(242p) 대비 파라미터 3.4× 많으나 d MAE 0.02mm 개선(1.80→1.78mm).
          near-field(d≤10mm)는 0.222→0.186mm — 0.036mm 의미 있는 개선.
          base-asym(666p) · base-s2+(2,482p)는 Pareto 비우세 (base와 유사 성능, 다른 규모).</td>
    </tr>
    <tr>
      <td>🔄 교체 후보: <b>medium-deep (978p)</b></td>
      <td>Stage1 (16,8,4), Stage2 (32,16,8) 3층 구조.
          d MAE 1.765mm, d≤10 0.176mm로 전 구간 base(818p) 우세.
          파라미터 20% 증가(818→978p), Flash ≈ 4KB, INT8 d step 동일(0.137mm).</td>
    </tr>
    <tr>
      <td>⚠️ 소형 모델 d step 악화</td>
      <td>nano/tiny: d step 0.20mm (base 0.14mm 대비 43% 악화).
          tiny-deep(138p)부터 0.146mm로 안정화.
          ε step은 전 모델 ~0.129-0.133%로 유사 (Tanh bounded output으로 범위 비슷).</td>
    </tr>
  </table>

  <h3>권고사항</h3>
  <div class="highlight info" style="margin-bottom:8px">
    <strong>현행 유지</strong>: base (818p) — d MAE 1.782mm, d≤10 0.186mm, Flash 3.4KB.
    충분한 정확도, near-field 우수, INT8 step 0.137mm.
  </div>
  <div class="highlight" style="margin-bottom:8px;border-color:#2CA02C;background:#f0fff4">
    <strong>★ 정확도 최우선</strong>: medium-deep (978p) — d MAE 1.765mm (−0.017mm), d≤10 0.176mm (−0.010mm).
    아키텍처: S1(16,8,4) + S2(32,16,8). 파라미터 20% 증가, Flash ≈ 4KB.
  </div>
  <div class="highlight" style="margin-bottom:8px;border-color:#9467BD;background:#f8f0ff">
    <strong>◆ 극한 경량화</strong>: small (242p) — d MAE 1.802mm (+0.020mm), Flash ≈ 1KB.
    d≤10mm 오차 0.222mm (base 대비 +0.036mm 감수 필요).
    INT8 d step 0.139mm ≈ base와 동일.
  </div>
</section>

"""

# ── edge_ai_report.html 에 삽입 ───────────────────────────────────────────
MARKER = "<!-- ═══════════════════════════════════════════ 7. COMPUTE ══ -->"

with open(HTML, encoding="utf-8") as f:
    html = f.read()

if "arch-search" in html:
    print("이미 삽입되어 있습니다.")
else:
    if MARKER not in html:
        print(f"ERROR: 삽입 마커를 찾을 수 없습니다: {MARKER}")
    else:
        html = html.replace(MARKER, SECTION + MARKER)
        with open(HTML, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"삽입 완료: {HTML}")
        print(f"새 파일 크기: {len(html):,} bytes")

# ── JSON 수정본 재저장 ────────────────────────────────────────────────────
with open(os.path.join(CKPT, "arch_search_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("arch_search_results.json (step_eps 수정) 재저장 완료")
