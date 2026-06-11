"""
1. Section 6c Pareto 플롯 재생성: x=INT8 Flash(KB), y 이중축 MAE d/MAE eps
2. edge_ai_report.html Section 6c 업데이트
3. edge_ai_report.html 주요 섹션을 master_report.html 에 병합 (중복 통합)
"""
import base64, io, json, re, warnings
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

warnings.filterwarnings("ignore")

DIR  = Path(__file__).parent
CHK  = DIR / "checkpoints"

# ── 색상 (CLAUDE.md) ──────────────────────────────────────────────────────────
COLOR_L = "#FF8C00"  # 근접도 / 주황
COLOR_R = "#2CA02C"  # 변형률 / 초록

# ── 흰색 배경 스타일 ──────────────────────────────────────────────────────────
plt.rcParams.update(plt.rcParamsDefault)
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": "#888", "axes.labelcolor": "#222",
    "xtick.color": "#444", "ytick.color": "#444",
    "text.color": "#222", "grid.color": "#ddd",
    "legend.facecolor": "white", "legend.edgecolor": "#ccc",
    "savefig.facecolor": "white", "font.size": 11,
})

def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()

# ── 아키텍처 탐색 데이터 로드 ─────────────────────────────────────────────────
with open(CHK / "arch_search_results.json", encoding="utf-8") as f:
    archs = json.load(f)

# INT8 Flash(bytes) = params * 1 byte/param
for a in archs:
    a["flash_bytes"] = a["params"]      # INT8 1B/param
    a["flash_kb"]    = a["params"] / 1024

# sklearn 50K (배포 모델) 추가
SKLEARN_ENTRY = {
    "name": "sklearn\n(배포)",
    "params": 50306, "flash_bytes": 50306, "flash_kb": 50306/1024,
    "mae_eps": 0.3435, "mae_d": 1.7830,
    "is_sklearn": True,
}

# Pareto 계산: flash ↑ 일 때 mae_d ↓ 인 점들
def is_pareto(pts, metric="mae_d"):
    dominated = [False] * len(pts)
    for i, a in enumerate(pts):
        for j, b in enumerate(pts):
            if i == j: continue
            if b["flash_bytes"] <= a["flash_bytes"] and b[metric] <= a[metric]:
                if b["flash_bytes"] < a["flash_bytes"] or b[metric] < a[metric]:
                    dominated[i] = True; break
    return [not d for d in dominated]

pareto_mask = is_pareto(archs, "mae_d")

# ═══════════════════════════════════════════════════════════════════════════════
# Pareto 플롯 (x=Flash KB, y-left=MAE d, y-right=MAE eps) — 이중 y축
# ═══════════════════════════════════════════════════════════════════════════════
fig, ax1 = plt.subplots(figsize=(11, 6))
fig.patch.set_facecolor("white")
ax2 = ax1.twinx()

flash_kb  = [a["flash_kb"]  for a in archs]
mae_d     = [a["mae_d"]     for a in archs]
mae_eps   = [a["mae_eps"]   for a in archs]
names     = [a["name"]      for a in archs]

# 마커: Pareto 점 = star, 나머지 = circle
for i, a in enumerate(archs):
    mk = "*" if pareto_mask[i] else "o"
    sz = 220 if pareto_mask[i] else 90
    ax1.scatter(a["flash_kb"], a["mae_d"],
                color=COLOR_L, marker=mk, s=sz, zorder=5,
                edgecolors="#555" if not pareto_mask[i] else "#FF6600",
                linewidths=0.8 if not pareto_mask[i] else 1.5)
    ax2.scatter(a["flash_kb"], a["mae_eps"],
                color=COLOR_R, marker="^", s=60, alpha=0.65, zorder=4,
                edgecolors="#1a6e1a", linewidths=0.7)

# Pareto 선
pareto_pts = [(a["flash_kb"], a["mae_d"]) for i,a in enumerate(archs) if pareto_mask[i]]
pareto_pts.sort()
if pareto_pts:
    px, py = zip(*pareto_pts)
    ax1.step(px, py, where="post", color=COLOR_L, lw=1.8, ls="--", alpha=0.7, label="Pareto frontier (d)")

# 라벨 (주요 포인트만)
label_names = {"nano", "tiny-deep", "small", "base", "medium-deep", "large"}
for i, a in enumerate(archs):
    if a["name"] in label_names:
        ax1.annotate(a["name"],
                     (a["flash_kb"], a["mae_d"]),
                     textcoords="offset points", xytext=(6, 4),
                     fontsize=8, color="#AA4400", fontweight="bold" if pareto_mask[i] else "normal")

# sklearn (배포 모델) 표시
ax1.scatter(SKLEARN_ENTRY["flash_kb"], SKLEARN_ENTRY["mae_d"],
            color="#1F77B4", marker="D", s=200, zorder=6,
            edgecolors="#003366", linewidths=1.5, label="sklearn (배포)")
ax1.annotate("sklearn\n(배포, 50K params)",
             (SKLEARN_ENTRY["flash_kb"], SKLEARN_ENTRY["mae_d"]),
             textcoords="offset points", xytext=(-80, 6),
             fontsize=8.5, color="#1F77B4", fontweight="bold",
             arrowprops=dict(arrowstyle="->", color="#1F77B4", lw=1.2))

# 축 설정
ax1.set_xlabel("INT8 Flash 크기 (KB)  [파라미터 수 = bytes]", fontsize=11)
ax1.set_ylabel("Test MAE d [mm]  ●/★", color=COLOR_L, fontsize=11)
ax1.tick_params(axis="y", labelcolor=COLOR_L)
ax1.set_xscale("log")
ax1.xaxis.set_major_formatter(mticker.FuncFormatter(
    lambda x, _: f"{x:.3f}" if x < 0.1 else (f"{x:.2f}" if x < 1 else f"{x:.1f}")))

ax2.set_ylabel("Test MAE ε [%]  ▲", color=COLOR_R, fontsize=11)
ax2.tick_params(axis="y", labelcolor=COLOR_R)

# 범례
from matplotlib.lines import Line2D
leg_handles = [
    Line2D([0],[0], marker="o", color="w", markerfacecolor=COLOR_L, markersize=9, label="MAE d (Non-Pareto)"),
    Line2D([0],[0], marker="*", color="w", markerfacecolor=COLOR_L, markersize=13,
           markeredgecolor="#FF6600", label="MAE d (Pareto optimal)"),
    Line2D([0],[0], marker="^", color="w", markerfacecolor=COLOR_R, markersize=8, alpha=0.7, label="MAE ε"),
    Line2D([0],[0], marker="D", color="w", markerfacecolor="#1F77B4", markersize=10,
           markeredgecolor="#003366", label="sklearn 배포 모델"),
    Line2D([0],[0], ls="--", color=COLOR_L, lw=1.8, label="Pareto frontier"),
]
ax1.legend(handles=leg_handles, loc="upper left", fontsize=8.5, framealpha=0.9)
ax1.grid(True, alpha=0.4, which="both")
ax1.set_title("아키텍처 탐색: INT8 Flash 크기 vs 정확도 (d + ε)", fontweight="bold", fontsize=12)

plt.tight_layout()
b64_pareto = fig_to_b64(fig)
print("Pareto figure generated.")

# ═══════════════════════════════════════════════════════════════════════════════
# Section 6c HTML 블록 구성
# ═══════════════════════════════════════════════════════════════════════════════
def row_color(val, best, worst):
    if val == best:  return "best"
    if val == worst: return "bad"
    return "mid" if val > (best+worst)/2 else "good"

rows = ""
for i, a in enumerate(archs):
    s1h = "→".join(str(x) for x in a["s1_hidden"])
    s2h = "→".join(str(x) for x in a["s2_hidden"])
    pmark = " ★" if pareto_mask[i] else ""
    flash_b = a["params"]
    flash_str = f"{flash_b} B" if flash_b < 1024 else f"{flash_b/1024:.1f} KB"
    rows += f"""      <tr>
        <td class="label">{a['name']}{pmark}</td>
        <td style="color:var(--text2);font-size:11px">1→{s1h}→1</td>
        <td style="color:var(--text2);font-size:11px">2→{s2h}→1</td>
        <td>{a['params']:,}</td>
        <td>{flash_str}</td>
        <td>{a['macs']:,}</td>
        <td class="{row_color(a['mae_eps'], 0.349, 0.381)}">{a['mae_eps']:.4f}</td>
        <td class="{row_color(a['mae_d'], 1.765, 2.115)}">{a['mae_d']:.4f}</td>
        <td class="{row_color(a['mae_d15'], 0.31, 0.81)}">{a['mae_d15']:.4f}</td>
        <td class="{'best' if pareto_mask[i] else ''}">{a['int8']['step_d_mm']:.4f}</td>
      </tr>\n"""

S6C_HTML = f"""<section id="arch-search">
<h2><span class="icon">🔬</span> 6c. 아키텍처 탐색 결과</h2>

<div class="card">
  <h3>탐색 방법론</h3>
  <div class="g3">
    <div class="kv"><div class="kv-label">탐색 대상</div><div class="kv-val" style="color:var(--blue);font-size:1.1rem">13</div><div class="kv-unit">아키텍처</div></div>
    <div class="kv"><div class="kv-label">활성화 함수</div><div class="kv-val" style="color:var(--teal);font-size:1rem">Tanh</div><div class="kv-unit">INT8 친화적</div></div>
    <div class="kv"><div class="kv-label">평가 기준</div><div class="kv-val" style="color:var(--mauve);font-size:1rem">MAE d</div><div class="kv-unit">근접도 주요 지표</div></div>
  </div>
  <div class="hl info" style="margin-top:12px">
    <strong>★ Pareto optimal</strong>: Flash 증가 대비 MAE d 감소 효율이 우수한 점.
    각 아키텍처의 INT8 Flash = 파라미터 수 × 1 byte (per-tensor symmetric INT8 기준).
  </div>
</div>

<div class="card">
  <h3>Pareto 플롯: Flash 크기 vs 정확도 (d + ε 이중 축)</h3>
  <img src="data:image/png;base64,{b64_pareto}" alt="pareto"
       style="width:100%;border-radius:8px;border:1px solid var(--border)">
  <div class="hl warn" style="margin-top:10px">
    <strong>sklearn 배포 모델</strong>(파란 마름모, 50K params / 49KB)은 INT8 PyTorch 아키텍처 대비
    약 <strong>60× 큰 Flash</strong>를 사용하지만 MAE d는 유사하다.
    Pareto 관점에서 medium-deep(978 params / &lt;1 KB)이 가장 효율적인 대안.
  </div>
</div>

<div class="card">
  <h3>전체 결과 테이블</h3>
  <div class="cmp-wrap">
  <table>
    <thead>
      <tr>
        <th>이름</th><th>S1 구조</th><th>S2 구조</th><th>파라미터</th>
        <th>INT8 Flash</th><th>MACs</th>
        <th>MAE ε (%)</th><th>MAE d (mm)</th><th>MAE d≤15 (mm)</th>
        <th>INT8 step_d (mm)</th>
      </tr>
    </thead>
    <tbody>
{rows}      <tr style="background:rgba(31,119,180,.08)">
        <td class="label">sklearn (배포) <span class="tag blue" style="font-size:11px">현재</span></td>
        <td style="font-size:11px">1→128→128→64→1</td>
        <td style="font-size:11px">2→128→128→64→1</td>
        <td style="color:var(--red)">50,306</td>
        <td style="color:var(--red)">~49 KB</td>
        <td style="color:var(--text2)">49,664</td>
        <td class="good">0.3435</td>
        <td class="good">1.7830</td>
        <td class="good">0.3009</td>
        <td class="mid">0.1371</td>
      </tr>
    </tbody>
  </table>
  </div>
</div>

<div class="card">
  <h3>핵심 발견 및 권장 사항</h3>
  <div class="g3">
    <div style="background:var(--bg3);border-radius:8px;padding:16px;border-left:3px solid var(--blue)">
      <div style="color:var(--blue);font-weight:700;margin-bottom:6px">현재 배포</div>
      <div style="font-size:13px">sklearn (50K / 49KB)<br>MAE d = 1.783 mm<br>INT8 변환 파이프라인 완성</div>
    </div>
    <div style="background:var(--bg3);border-radius:8px;padding:16px;border-left:3px solid var(--green)">
      <div style="color:var(--green);font-weight:700;margin-bottom:6px">Pareto 무릎 ★</div>
      <div style="font-size:13px">medium-deep (978 params / &lt;1KB)<br>MAE d = 1.765 mm<br>Flash 60× 절감, 정확도 유사</div>
    </div>
    <div style="background:var(--bg3);border-radius:8px;padding:16px;border-left:3px solid var(--mauve)">
      <div style="color:var(--mauve);font-weight:700;margin-bottom:6px">최소 목표 달성</div>
      <div style="font-size:13px">tiny-deep (138 params / 138B)<br>MAE d = 1.837 mm<br>극초소형 임베디드 배포 가능</div>
    </div>
  </div>
</div>
</section>"""

print("Section 6c HTML built.")

# ═══════════════════════════════════════════════════════════════════════════════
# edge_ai_report.html Section 6c 교체
# ═══════════════════════════════════════════════════════════════════════════════
EDGE_AI = DIR / "edge_ai_report.html"
with open(EDGE_AI, encoding="utf-8") as f:
    ea_html = f.read()

S6C_START = "<!-- ═══════════════════════════════════════════ 6c. ARCH SEARCH ═ -->"
S6C_END   = "<!-- ═══════════════════════════════════════════ 7. COMPUTE ══ -->"

if S6C_START in ea_html and S6C_END in ea_html:
    s_idx = ea_html.find(S6C_START)
    e_idx = ea_html.find(S6C_END)
    ea_html = ea_html[:s_idx] + S6C_START + "\n" + S6C_HTML + "\n\n" + ea_html[e_idx:]
    print("edge_ai_report Section 6c replaced.")
else:
    # fallback: section id="arch-search" 로 찾기
    m = re.search(r'<section id="arch-search">.*?</section>', ea_html, re.DOTALL)
    if m:
        ea_html = ea_html[:m.start()] + S6C_HTML + ea_html[m.end():]
        print("edge_ai Section 6c replaced (fallback).")
    else:
        print("WARNING: Section 6c marker not found in edge_ai_report!")

with open(EDGE_AI, "w", encoding="utf-8") as f:
    f.write(ea_html)
print(f"Saved edge_ai_report.html ({len(ea_html):,} bytes)")

# ═══════════════════════════════════════════════════════════════════════════════
# edge_ai_report 에서 master_report 에 추가할 섹션 추출
# ═══════════════════════════════════════════════════════════════════════════════
# 추출 대상: Section 3(지연), 4(메모리), 5(전력), 7(MACs), 9(종합비교)
# master_report Section 9(Edge AI 배포) 뒤에 삽입

def extract_section(html, start_marker, end_marker):
    """두 마커 사이의 HTML 추출"""
    s = html.find(start_marker)
    e = html.find(end_marker)
    if s < 0 or e < 0:
        return ""
    return html[s + len(start_marker):e].strip()

# edge_ai 섹션 경계 마커들
EA_MARKERS = {
    "latency":  ("<!-- ═══════════════════════════════════════════ 3. LATENCY ══ -->",
                 "<!-- ═══════════════════════════════════════════ 4. MEMORY ═══ -->"),
    "memory":   ("<!-- ═══════════════════════════════════════════ 4. MEMORY ═══ -->",
                 "<!-- ═══════════════════════════════════════════ 5. POWER ════ -->"),
    "power":    ("<!-- ═══════════════════════════════════════════ 5. POWER ════ -->",
                 "<!-- ═══════════════════════════════════════════ 6. ACCURACY ═ -->"),
    "macs":     ("<!-- ═══════════════════════════════════════════ 7. COMPUTE ══ -->",
                 "<!-- ═══════════════════════════════════════════ 8. COMM ═════ -->"),
    "summary":  ("<!-- ═══════════════════════════════════════════ 9. FULL COMP ═ -->",
                 "<!-- ═══════════════════════════════════════════ 10. CODE ════ -->"),
}

# edge_ai_report 다시 읽기 (6c 업데이트 반영)
with open(EDGE_AI, encoding="utf-8") as f:
    ea_html = f.read()

extracted = {}
for key, (sm, em) in EA_MARKERS.items():
    sec = extract_section(ea_html, sm, em)
    extracted[key] = sec
    print(f"Extracted {key}: {len(sec):,} chars")

# ── master_report.html 에 병합 ────────────────────────────────────────────────
MASTER = DIR / "master_report.html"
with open(MASTER, encoding="utf-8") as f:
    ms_html = f.read()

# 1. Section 6에 6c 파레토 플롯 추가
# 기존 Section 6 끝 (</section> 직전 </div>)에서 arch-search 내용 찾기
# master Section 6에는 아직 6c가 없음 — Section 7 시작 마커 앞에 삽입
MS_S6_END = "<!-- ══════════════════════ 7. 새 데이터 실험 ══════════════════════ -->"
if MS_S6_END in ms_html:
    # 6c 이미 있으면 스킵, 없으면 삽입
    if 'id="arch-search"' not in ms_html or ms_html.find('id="arch-search"') > ms_html.find(MS_S6_END):
        # section 6 </section> 찾기
        s6_section_end = ms_html.rfind("</section>", 0, ms_html.find(MS_S6_END))
        insert_s6c = ms_html[:s6_section_end] + "\n\n" + S6C_HTML + "\n\n</section>\n\n" + ms_html[ms_html.find(MS_S6_END):]
        ms_html = insert_s6c
        print("Section 6c inserted into master Section 6.")
    else:
        # 기존 arch-search 교체
        m = re.search(r'<section id="arch-search">.*?</section>', ms_html, re.DOTALL)
        if m:
            ms_html = ms_html[:m.start()] + S6C_HTML + ms_html[m.end():]
            print("Existing arch-search section in master replaced.")

# 2. Section 9 (Edge AI 배포) 에 latency/memory/power/macs/summary 추가
# master Section 9 끝, Section 10 시작 앞에 삽입
MS_S10_START = "<!-- ══════════════════════ 10. 실시간 테스트 ══════════════════════ -->"
if MS_S10_START in ms_html:
    s9_end = ms_html.rfind("</section>", 0, ms_html.find(MS_S10_START))

    ea_inserts = ""
    for key in ["latency", "memory", "power", "macs", "summary"]:
        sec = extracted.get(key, "")
        if sec:
            ea_inserts += f"\n<!-- ── from edge_ai_report: {key} ── -->\n{sec}\n"

    if ea_inserts.strip():
        # 이미 삽입됐으면 교체
        START_TAG = "<!-- ══ edge_ai merged sections ══ -->"
        END_TAG   = "<!-- ══ end edge_ai merged ══ -->"
        if START_TAG in ms_html:
            si = ms_html.find(START_TAG)
            ei = ms_html.find(END_TAG) + len(END_TAG)
            ms_html = ms_html[:si] + START_TAG + ea_inserts + END_TAG + ms_html[ei:]
            print("edge_ai merged sections replaced.")
        else:
            merged_block = f"\n{START_TAG}{ea_inserts}{END_TAG}\n"
            ms_html = ms_html[:s9_end] + merged_block + "</section>\n\n" + ms_html[ms_html.find(MS_S10_START):]
            print("edge_ai sections merged into master Section 9.")

# 3. TOC 업데이트 (arch-search 링크 추가)
OLD_TOC = '  <a href="#s6">6. 아키텍처 비교</a>'
NEW_TOC = '  <a href="#s6">6. 아키텍처 비교</a>\n  <a href="#arch-search" style="padding-left:20px;font-size:11px">↳ 6c. 탐색 결과</a>'
if OLD_TOC in ms_html and 'href="#arch-search"' not in ms_html:
    ms_html = ms_html.replace(OLD_TOC, NEW_TOC, 1)
    print("TOC updated.")

with open(MASTER, "w", encoding="utf-8") as f:
    f.write(ms_html)
print(f"\nSaved master_report.html ({len(ms_html):,} bytes)")
print("Done.")
