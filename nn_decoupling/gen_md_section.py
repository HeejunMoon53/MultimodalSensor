"""
gen_md_section.py
medium-deep 임베딩 비교 섹션을 master_report.html 에 추가
"""
import sys, json, io, base64, re
sys.path.insert(0, r'C:\ai\pylibs')
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path

DIR = Path(__file__).parent
CHK = DIR / "checkpoints"

# ── 한글 폰트 ──────────────────────────────────────────────────────────────────
_kf = [f.name for f in fm.fontManager.ttflist
       if any(k in f.name for k in ["Malgun", "NanumGothic", "CJK"])]
plt.rcParams.update(plt.rcParamsDefault)
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": "#888", "axes.labelcolor": "#222",
    "xtick.color": "#444", "ytick.color": "#444",
    "text.color": "#222", "grid.color": "#ddd",
    "legend.facecolor": "white", "legend.edgecolor": "#ccc",
    "savefig.facecolor": "white", "font.size": 11,
    "font.family": "sans-serif",
    "font.sans-serif": ["Malgun Gothic"] + _kf + ["DejaVu Sans"],
    "axes.unicode_minus": False,
})

COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"
COLOR_B = "#1F77B4"

def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()

# ── 결과 로드 ─────────────────────────────────────────────────────────────────
with open(CHK / "medium_deep_deploy_results.json", encoding="utf-8") as f:
    R = json.load(f)
MD = R["medium_deep"]
SK = R["sklearn"]

# ═══════════════════════════════════════════════════════════════════════════════
# 그래프 1: 비교 바차트 (4가지 지표)
# ═══════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 4, figsize=(14, 4))
fig.patch.set_facecolor("white")

metrics = [
    ("가중치 ROM (B)", SK["flash_b_meas"], MD["flash_b_weights"], "B"),
    ("SRAM (B)",       SK["sram_b_meas"], MD["sram_b_est"],        "B"),
    ("MACs",           SK["macs"],        MD["macs"],              ""),
    ("Latency (µs)",   SK["latency_us_meas"], MD["latency_us_est"], "µs"),
]

for ax, (title, v_sk, v_md, unit) in zip(axes, metrics):
    bars = ax.bar(["sklearn\n(현재)", "medium-\ndeep"],
                  [v_sk, v_md], color=[COLOR_B, COLOR_L],
                  edgecolor="#555", linewidth=0.8, width=0.5)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_ylabel(unit, fontsize=9, color="#555")
    ax.tick_params(labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    # 값 표시
    for bar, v in zip(bars, [v_sk, v_md]):
        if v >= 1000:
            label = f"{v/1000:.1f}K" if v < 1e6 else f"{v:.0f}"
        elif v < 1:
            label = f"{v:.2f}"
        else:
            label = f"{v:.1f}"
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.02,
                label, ha="center", va="bottom", fontsize=8.5, fontweight="600")
    # 개선 배율 표시
    ratio = v_sk / v_md if v_md > 0 else 0
    ax.text(0.98, 0.97, f"{ratio:.0f}× 개선",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=9, color=COLOR_L, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff8ee", edgecolor=COLOR_L, linewidth=0.8))

plt.suptitle("sklearn (현재 배포) vs medium-deep: STM32 임베딩 비교", fontsize=12, fontweight="bold", y=1.02)
plt.tight_layout()
b64_bar = fig_to_b64(fig)
print("Bar chart generated.")

# ═══════════════════════════════════════════════════════════════════════════════
# 그래프 2: 정확도 비교 (MAE 점 비교)
# ═══════════════════════════════════════════════════════════════════════════════
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))
fig.patch.set_facecolor("white")

# MAE ε
cats = ["sklearn\n(F32)", "sklearn\n(INT8)", "medium-deep\n(F32)", "medium-deep\n(INT8)"]
eps_vals = [SK["mae_eps_f32"], SK["mae_eps_f32"]+0.020,
            MD["mae_eps_f32"], MD["mae_eps_i8"]]
d_vals   = [SK["mae_d_f32"],   SK["mae_d_f32"]+0.032,
            MD["mae_d_f32"],   MD["mae_d_i8"]]

colors_4 = [COLOR_B, "#6baed6", COLOR_L, "#fd8d3c"]
for ax, vals, ylabel, title in [
    (ax1, eps_vals, "MAE ε (%)", "변형률 정확도"),
    (ax2, d_vals,   "MAE d (mm)", "근접도 정확도"),
]:
    bars = ax.bar(cats, vals, color=colors_4, edgecolor="#555", linewidth=0.7, width=0.6)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.tick_params(axis="x", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ymin = min(vals) * 0.97
    ymax = max(vals) * 1.06
    ax.set_ylim(ymin, ymax)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (ymax-ymin)*0.005,
                f"{v:.4f}", ha="center", va="bottom", fontsize=7.5, fontweight="600")

plt.tight_layout()
b64_acc = fig_to_b64(fig)
print("Accuracy chart generated.")

# ═══════════════════════════════════════════════════════════════════════════════
# HTML 섹션 생성
# ═══════════════════════════════════════════════════════════════════════════════
CELL_BEST = "background:#e6f4ea;color:#1a6b36;font-weight:600"
CELL_WARN = "background:#fff8e8;color:#b45000"
CELL_BAD  = "background:#fff0f0;color:#cc0000"

P = "padding:8px 12px"

MD_SECTION = f"""<!-- ══ medium-deep deployment comparison ══ -->
<section id="md-deploy">
<h2><span class="icon">⚡</span> 10b. medium-deep 임베딩 비교</h2>

<div class="card">
  <h3>개요</h3>
  <p style="color:#444;line-height:1.7">
    현재 배포 모델(sklearn, 50K params)을 Pareto 최적 아키텍처인
    <strong>medium-deep (978 params)</strong>으로 교체했을 때의 STM32G473CBT6 임베딩 효과를 분석한다.
    모델 크기가 대폭 줄어 가중치가 <strong>I-Cache(32KB)에 완전 수용</strong>되므로
    Flash 대기 사이클 없이 추론 가능하다 (X-CUBE-AI 런타임 유지).
    stedgeai가 생성한 float32 C 코드 기준: 가중치 ROM 3,912 B, 활성화 SRAM 288 B, 총 MACs 1,062.
  </p>
  <div class="g4" style="margin-top:14px">
    <div class="kv"><div class="kv-label">가중치 ROM 절감</div>
      <div class="kv-val" style="color:var(--green);font-size:1.4rem">{R['flash_reduction']:.0f}×</div>
      <div class="kv-unit">109KB → 3.8KB</div></div>
    <div class="kv"><div class="kv-label">SRAM 절감</div>
      <div class="kv-val" style="color:var(--green);font-size:1.4rem">{R['sram_reduction']:.0f}×</div>
      <div class="kv-unit">15KB → 288B</div></div>
    <div class="kv"><div class="kv-label">추론 속도</div>
      <div class="kv-val" style="color:var(--orange);font-size:1.4rem">{R['speedup']:.0f}×</div>
      <div class="kv-unit">1,068µs → ~18µs</div></div>
    <div class="kv"><div class="kv-label">MAE d 차이</div>
      <div class="kv-val" style="color:var(--blue);font-size:1.2rem">+0.09mm</div>
      <div class="kv-unit">1.783 → 1.868mm</div></div>
  </div>
</div>

<div class="card">
  <h3>지표 비교 차트</h3>
  <img src="data:image/png;base64,{b64_bar}" style="width:100%;border-radius:8px;border:1px solid #ddd">
</div>

<div class="card">
  <h3>정확도 비교 (F32 vs INT8)</h3>
  <img src="data:image/png;base64,{b64_acc}" style="width:100%;border-radius:8px;border:1px solid #ddd">
  <div class="hl info" style="margin-top:10px">
    INT8 PTQ 적용 후 medium-deep의 MAE 변화:
    Δε = <strong>{MD['delta_eps_i8']:+.4f}%</strong>,
    Δd = <strong>{MD['delta_d_i8']:+.4f}mm</strong> — 센서 노이즈 수준 이하.
  </div>
</div>

<div class="card">
  <h3>상세 비교 테이블</h3>
  <div style="overflow-x:auto">
  <table style="width:100%;border-collapse:collapse;background:white;color:#222;font-size:13px">
    <thead>
      <tr style="background:#f0f2f5;border-bottom:2px solid #ccc">
        <th style="{P};text-align:left;font-weight:700;color:#333">지표</th>
        <th style="{P};text-align:center;font-weight:700;color:{COLOR_B}">sklearn (현재)</th>
        <th style="{P};text-align:center;font-weight:700;color:{COLOR_L}">medium-deep (신규)</th>
        <th style="{P};text-align:center;font-weight:700;color:#555">개선</th>
      </tr>
    </thead>
    <tbody>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">아키텍처</td>
        <td style="{P};text-align:center;font-size:11px;color:#555">1→128→128→64→1<br>2→128→128→64→1</td>
        <td style="{P};text-align:center;font-size:11px;color:#555">1→16→8→4→1<br>2→32→16→8→1</td>
        <td style="{P};text-align:center">—</td>
      </tr>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">파라미터 수</td>
        <td style="{P};text-align:center;{CELL_BAD}">50,306</td>
        <td style="{P};text-align:center;{CELL_BEST}">978</td>
        <td style="{P};text-align:center;font-weight:600;color:#1a6b36">{R['macs_reduction']:.0f}× 감소</td>
      </tr>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">MACs (총)</td>
        <td style="{P};text-align:center;{CELL_BAD}">50,306</td>
        <td style="{P};text-align:center;{CELL_BEST}">1,062<br><span style="font-size:11px;color:#666">S1: 237 / S2: 825 (stedgeai 실측)</span></td>
        <td style="{P};text-align:center;font-weight:600;color:#1a6b36">{R['macs_reduction']:.0f}× 감소</td>
      </tr>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">가중치 ROM</td>
        <td style="{P};text-align:center;{CELL_BAD}">~50 KB (INT8)<br><span style="font-size:11px;color:#888">I-Cache(32KB) 미수용 → wait-state</span></td>
        <td style="{P};text-align:center;{CELL_BEST}">3,912 B (float32)<br><span style="font-size:11px;color:#888">S1:836B + S2:3,076B (stedgeai 실측)</span></td>
        <td style="{P};text-align:center;font-weight:600;color:#1a6b36">{R['flash_reduction']:.0f}× 감소</td>
      </tr>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">전체 Flash 사용</td>
        <td style="{P};text-align:center;{CELL_BAD}">112,488 B (109.9 KB)<br><span style="font-size:11px;color:#666">실측 (STM32CubeIDE)</span></td>
        <td style="{P};text-align:center;{CELL_WARN}">~68 KB 추정<br><span style="font-size:11px;color:#666">가중치 3.9KB + X-CUBE-AI 런타임 동일</span></td>
        <td style="{P};text-align:center;font-weight:600;color:#1a6b36">가중치만 {R['flash_reduction']:.0f}× 감소</td>
      </tr>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">활성화 SRAM</td>
        <td style="{P};text-align:center;{CELL_BAD}">15,312 B (15.0 KB)<br><span style="font-size:11px;color:#666">실측</span></td>
        <td style="{P};text-align:center;{CELL_BEST}">288 B<br><span style="font-size:11px;color:#666">S1:96B + S2:192B (stedgeai 실측)</span></td>
        <td style="{P};text-align:center;font-weight:600;color:#1a6b36">{R['sram_reduction']:.0f}× 감소</td>
      </tr>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">추론 지연</td>
        <td style="{P};text-align:center;{CELL_BAD}">1,068 µs<br><span style="font-size:11px;color:#666">DWT 실측, 3.56 cycles/MAC</span></td>
        <td style="{P};text-align:center;{CELL_BEST}">~18 µs<br><span style="font-size:11px;color:#666">추정, ~2.9 cycles/MAC (I-Cache hit)</span></td>
        <td style="{P};text-align:center;font-weight:600;color:#1a6b36">{R['speedup']:.0f}× 빠름</td>
      </tr>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">cycles/MAC</td>
        <td style="{P};text-align:center;{CELL_WARN}">3.56<br><span style="font-size:11px;color:#666">Flash 4~5 wait-state 병목</span></td>
        <td style="{P};text-align:center;{CELL_BEST}">~2.9 (추정)<br><span style="font-size:11px;color:#666">가중치 3.9KB → I-Cache 완전 수용</span></td>
        <td style="{P};text-align:center;font-weight:600;color:#1a6b36">1.2× 개선</td>
      </tr>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">MAE ε (F32)</td>
        <td style="{P};text-align:center">{SK['mae_eps_f32']:.4f} %</td>
        <td style="{P};text-align:center">{MD['mae_eps_f32']:.4f} %</td>
        <td style="{P};text-align:center;color:#888">{MD['mae_eps_f32']-SK['mae_eps_f32']:+.4f} %</td>
      </tr>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">MAE d (F32)</td>
        <td style="{P};text-align:center">{SK['mae_d_f32']:.4f} mm</td>
        <td style="{P};text-align:center">{MD['mae_d_f32']:.4f} mm</td>
        <td style="{P};text-align:center;color:#b45000">{MD['mae_d_f32']-SK['mae_d_f32']:+.4f} mm</td>
      </tr>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">MAE d (INT8)</td>
        <td style="{P};text-align:center">{SK['mae_d_f32']+0.032:.4f} mm<br><span style="font-size:11px;color:#888">Δ+0.032 (이전 측정)</span></td>
        <td style="{P};text-align:center">{MD['mae_d_i8']:.4f} mm<br><span style="font-size:11px;color:#888">Δ{MD['delta_d_i8']:+.4f}</span></td>
        <td style="{P};text-align:center;color:#888">—</td>
      </tr>
      <tr style="border-bottom:1px solid #eee">
        <td style="{P};font-weight:600">모델 포맷</td>
        <td style="{P};text-align:center;{CELL_WARN}">INT8 (per-tensor symmetric)<br><span style="font-size:11px;color:#666">SMLAD DSP 가속</span></td>
        <td style="{P};text-align:center;{CELL_WARN}">float32<br><span style="font-size:11px;color:#666">Cortex-M4F FPU (VMLA.F32)</span></td>
        <td style="{P};text-align:center;color:#888">—</td>
      </tr>
      <tr>
        <td style="{P};font-weight:600">X-CUBE-AI 의존</td>
        <td style="{P};text-align:center">필요 (runtime ~60KB)</td>
        <td style="{P};text-align:center">필요 (동일 런타임)<br><span style="font-size:11px;color:#888">가중치만 교체</span></td>
        <td style="{P};text-align:center;color:#888">동일</td>
      </tr>
    </tbody>
  </table>
  </div>
</div>

<div class="card">
  <h3>cycles/MAC 개선 원인 분석</h3>
  <div class="g2">
    <div style="background:#fff8ee;border-radius:8px;padding:16px;border-left:3px solid {COLOR_L}">
      <div style="font-weight:700;color:{COLOR_L};margin-bottom:8px">sklearn (현재) — Flash 병목</div>
      <ul style="font-size:13px;color:#444;line-height:1.8;margin:0;padding-left:18px">
        <li>INT8 가중치 ~52 KB → STM32G4 I-Cache(16KB)에 미수용</li>
        <li>Flash 접근 시 4~5 wait-states @ 170 MHz</li>
        <li>실측 3.56 cycles/MAC (이론 1~2의 2~3배)</li>
      </ul>
    </div>
    <div style="background:#f0f8f0;border-radius:8px;padding:16px;border-left:3px solid {COLOR_R}">
      <div style="font-weight:700;color:{COLOR_R};margin-bottom:8px">medium-deep — I-Cache 최적화</div>
      <ul style="font-size:13px;color:#444;line-height:1.8;margin:0;padding-left:18px">
        <li>float32 가중치 3,912 B → I-Cache(32KB)에 완전 수용</li>
        <li>반복 추론 시 cache hit률 ~100% → wait-state 제거</li>
        <li>예상 ~2.9 cycles/MAC (Cortex-M4F FPU, VMLA.F32)</li>
        <li>INT8 양자화 시 SMLAD로 ~1.5 cycles/MAC 추가 개선 가능</li>
      </ul>
    </div>
  </div>
</div>

<div class="card">
  <h3>stedgeai 생성 파일 (TDMFirmware/X-CUBE-AI/App/)</h3>
  <div style="background:#f8f9fa;border-radius:6px;padding:14px;font-family:monospace;font-size:12px;color:#333">
    <div><strong>stage1.c / stage1.h</strong>  — float32 추론 커널 (21,759 B)</div>
    <div style="margin-top:4px"><strong>stage1_data.c / stage1_data.h</strong>  — 가중치 (836 B ROM)</div>
    <div style="margin-top:4px"><strong>stage1_data_params.h</strong>  — AI_STAGE1_DATA_ACTIVATIONS_SIZE = 96</div>
    <div style="margin-top:8px"><strong>stage2.c / stage2.h</strong>  — float32 추론 커널 (21,791 B)</div>
    <div style="margin-top:4px"><strong>stage2_data.c / stage2_data.h</strong>  — 가중치 (3,076 B ROM)</div>
    <div style="margin-top:4px"><strong>stage2_data_params.h</strong>  — AI_STAGE2_DATA_ACTIVATIONS_SIZE = 192</div>
    <div style="margin-top:10px;color:#777;font-size:11px">
      nn_inference.c: ai_float 버퍼 사용, INT8 스케일 제거, X-CUBE-AI api 유지<br>
      STM32CubeIDE에서 Ctrl+B → flash
    </div>
  </div>
</div>

</section>
<!-- ══ end medium-deep deployment comparison ══ -->"""

# ═══════════════════════════════════════════════════════════════════════════════
# master_report.html에 삽입
# ═══════════════════════════════════════════════════════════════════════════════
MASTER = DIR / "master_report.html"
with open(MASTER, encoding="utf-8") as f:
    ms = f.read()

START_TAG = "<!-- ══ medium-deep deployment comparison ══ -->"
END_TAG   = "<!-- ══ end medium-deep deployment comparison ══ -->"

if START_TAG in ms:
    si = ms.find(START_TAG)
    ei = ms.find(END_TAG) + len(END_TAG)
    ms = ms[:si] + MD_SECTION + ms[ei:]
    print("md-deploy section replaced.")
else:
    # Section 10 (실시간 테스트) 앞에 삽입
    INSERT_BEFORE = "<!-- ══════════════════════ 10. 실시간 테스트 ══════════════════════ -->"
    if INSERT_BEFORE in ms:
        ms = ms.replace(INSERT_BEFORE, MD_SECTION + "\n\n" + INSERT_BEFORE, 1)
        print("md-deploy section inserted before Section 10.")
    else:
        # fallback: </body> 앞에 삽입
        ms = ms.replace("</body>", MD_SECTION + "\n</body>", 1)
        print("md-deploy section inserted before </body>.")

# TOC에 링크 추가
OLD_TOC = '<a href="#arch-search" style="padding-left:20px;font-size:11px">↳ 6c. 탐색 결과</a>'
NEW_TOC = (OLD_TOC +
           '\n  <a href="#md-deploy" style="padding-left:20px;font-size:11px">↳ 10b. medium-deep 임베딩</a>')
if OLD_TOC in ms and 'href="#md-deploy"' not in ms:
    ms = ms.replace(OLD_TOC, NEW_TOC, 1)
    print("TOC updated.")

with open(MASTER, "w", encoding="utf-8") as f:
    f.write(ms)
print(f"Saved master_report.html ({len(ms):,} bytes)")
print("Done.")
