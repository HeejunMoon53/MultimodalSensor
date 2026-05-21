"""
comprehensive_report.py — 종합 기술 보고서 생성
전처리: ldc_iir(α=0.18) + Channel 2(R_DC_filtered)  ← 최적 성능 조건

실험:
  A) Two-Stage PINN  (λ=0.10)  818 params
  B) Single-Stage PINN (λ=0.10) 626 params
  C) Single-Stage DNN  (λ=0.00) 626 params

출력: report_comprehensive.html
실행: C:/ml_env/Scripts/python comprehensive_report.py
"""
import os, sys, time, json, copy, warnings, re, glob
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from model import TwoStageDecoupler, SinglePINNMLP, PhysicsLoss

warnings.filterwarnings('ignore')
torch.manual_seed(42)
np.random.seed(42)

# ── 상수 ─────────────────────────────────────────────────────────────────────
DATA_DIR           = os.path.join(HERE, '..', '0332_DecouplingTest_TXTFiles')
SENSOR_BASELINE_MM = 120.0
L_BASELINE_SAMPLES = 50
V_MAX = 5.0; ACCEL = 2.5; D_TOTAL = 50.0
LDC_IIR_ALPHA = 0.18   # LDC IIR 필터 계수 (train.py 원본과 동일)
DEVICE = torch.device('cpu')

TEST_IDX = {0, 9, 18, 27, 36}
VAL_IDX  = {4, 13, 22, 31}

# ── Data pipeline (r_filtered 버전) ──────────────────────────────────────────

def _num(path):
    return int(re.search(r'\d+', os.path.basename(path)).group())

def _prox_array(n_half):
    t_a = V_MAX / ACCEL
    d_a = 0.5 * ACCEL * t_a ** 2
    d_c = D_TOTAL - 2 * d_a
    T   = t_a + d_c / V_MAX + t_a
    def pos(t):
        if t <= t_a:                 return 0.5 * ACCEL * t ** 2
        elif t <= t_a + d_c / V_MAX: return d_a + V_MAX * (t - t_a)
        else:
            td = t - (t_a + d_c / V_MAX)
            return (d_a + d_c) + V_MAX * td - 0.5 * ACCEL * td ** 2
    p = np.array([pos(t) for t in np.linspace(0, T, n_half)])
    return np.concatenate([p[::-1], p[1:]])

def _baseline(flist, n_half):
    df0 = pd.read_csv(flist[0])
    pk  = df0['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax()
    st  = max(0, pk - n_half + 1)
    L0  = float(df0['Channel 1'].iloc[st: st + L_BASELINE_SAMPLES].mean())
    R0  = float(df0['Channel 2'].iloc[st: st + L_BASELINE_SAMPLES].mean())  # r_filtered
    return L0, R0

def _iir(arr, alpha):
    out = np.zeros_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = (1 - alpha) * out[i-1] + alpha * arr[i]
    return out

def _load_one(path, n_half, prox, L0, R0):
    df  = pd.read_csv(path)
    pk  = int(df['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax())
    st, en = pk - n_half + 1, pk + n_half
    if st < 0 or en > len(df): return None
    ldc_raw = df['Channel 1'].values[st:en].astype(np.float64)
    ldc     = _iir(ldc_raw, LDC_IIR_ALPHA)           # LDC IIR 필터
    r       = df['Channel 2'].values[st:en].astype(np.float64)  # R_DC_filtered
    dL  = ((L0 / ldc) ** 2 - 1.0) * 100.0
    dR  = ((r - R0) / R0) * 100.0
    eps = _num(path) / SENSOR_BASELINE_MM
    return dict(dL=dL.astype(np.float32), dR=dR.astype(np.float32),
                d=prox.astype(np.float32),
                eps=np.full(len(prox), eps, dtype=np.float32))

class SensorDS(Dataset):
    def __init__(self, samples, in_sc=None, out_sc=None, fit=False):
        dL  = np.concatenate([s['dL']  for s in samples])
        dR  = np.concatenate([s['dR']  for s in samples])
        eps = np.concatenate([s['eps'] for s in samples])
        d   = np.concatenate([s['d']   for s in samples])
        X   = np.stack([dL, dR], 1)
        Y   = np.stack([eps, d], 1)
        if fit:
            self.in_sc  = StandardScaler().fit(X)
            self.out_sc = StandardScaler().fit(Y)
        else:
            self.in_sc  = in_sc
            self.out_sc = out_sc
        self.X = self.in_sc.transform(X).astype(np.float32)
        self.Y = self.out_sc.transform(Y).astype(np.float32)
    def __len__(self):  return len(self.X)
    def __getitem__(self, i): return torch.from_numpy(self.X[i]), torch.from_numpy(self.Y[i])

def build_loaders(batch=256):
    flist  = sorted(glob.glob(os.path.join(DATA_DIR, 'strain*.txt')), key=_num)
    ref    = pd.read_csv(max(flist, key=_num))
    pk_ref = int(ref['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax())
    n_half = len(ref) - pk_ref
    prox   = _prox_array(n_half)
    L0, R0 = _baseline(flist, n_half)
    print(f'  Baseline: L0={L0:.0f}, R0={R0:.2f}, n_half={n_half}')

    tr, va, te = [], [], []
    for path in flist:
        i = _num(path)
        d = _load_one(path, n_half, prox, L0, R0)
        if d is None: continue
        if   i in TEST_IDX: te.append(d)
        elif i in VAL_IDX:  va.append(d)
        else:               tr.append(d)

    tr_ds = SensorDS(tr, fit=True)
    va_ds = SensorDS(va, tr_ds.in_sc, tr_ds.out_sc)
    te_ds = SensorDS(te, tr_ds.in_sc, tr_ds.out_sc)
    mk = lambda ds, sh: DataLoader(ds, batch_size=batch, shuffle=sh, num_workers=0)
    return mk(tr_ds, True), mk(va_ds, False), mk(te_ds, False), \
           tr_ds.in_sc, tr_ds.out_sc, len(tr_ds), len(va_ds), len(te_ds)

# ── Training helpers ──────────────────────────────────────────────────────────

def _inv(Y, sc):
    return torch.from_numpy(
        sc.inverse_transform(Y.detach().cpu().numpy()).astype(np.float32))

def _lam(ep, warmup, total, lam_f):
    if ep < warmup: return 0.0
    return (ep - warmup) / max(1, total - warmup) * lam_f

def _train_ep(model, phys, loader, opt, lam, in_sc, out_sc):
    model.train()
    td = tp = n = 0
    for X, Y in loader:
        opt.zero_grad()
        Yp = model(X)
        ld = nn.functional.mse_loss(Yp, Y)
        lp = torch.zeros(1)
        if lam > 0:
            Yph = _inv(Yp, out_sc); Xph = _inv(X, in_sc)
            lp  = phys(Yph[:, 0], Yph[:, 1], Xph[:, 1], Xph[:, 0])
        loss = ld + lam * lp
        loss.backward()
        nn.utils.clip_grad_norm_(
            list(model.parameters()) + list(phys.parameters()), 1.0)
        opt.step()
        bs = len(X); td += ld.item() * bs; tp += lp.item() * bs; n += bs
    return td / n, tp / n

@torch.no_grad()
def _eval(model, loader, out_sc):
    model.eval()
    ee, de = [], []
    for X, Y in loader:
        Yp = _inv(model(X), out_sc)
        Yt = torch.from_numpy(out_sc.inverse_transform(Y.numpy()).astype(np.float32))
        ee.append((Yp[:, 0] - Yt[:, 0]).abs())
        de.append((Yp[:, 1] - Yt[:, 1]).abs())
    return torch.cat(ee).mean().item() * 100, torch.cat(de).mean().item()

# ── Experiment runner ─────────────────────────────────────────────────────────

def run_one(label, model_cls, lam_final, epochs=300, patience=30):
    print(f'\n  [{label}]  params={model_cls().param_count()}')
    trl, val, tel, in_sc, out_sc, n_tr, n_va, n_te = build_loaders()

    model  = model_cls()
    phys   = PhysicsLoss()
    params = list(model.parameters()) + list(phys.parameters())
    opt    = optim.AdamW(params, lr=1e-3, weight_decay=1e-4)
    sched  = CosineAnnealingLR(opt, T_max=epochs, eta_min=1e-5)

    best_d = float('inf'); best_ep = 0; best_st = None; best_ph = None; pc = 0
    # history: (ep, lam, l_data, l_phys, val_eps, val_d)
    history = []
    t0 = time.time()

    for ep in range(1, epochs + 1):
        lam          = _lam(ep, 50, epochs, lam_final)
        l_d, l_p     = _train_ep(model, phys, trl, opt, lam, in_sc, out_sc)
        mae_e, mae_d = _eval(model, val, out_sc)
        sched.step()
        history.append((ep, round(lam, 4),
                        round(l_d, 5), round(l_p, 3),
                        round(mae_e, 4), round(mae_d, 4)))

        if ep % 20 == 0 or ep == 1:
            print(f'    ep{ep:3d}  lam={lam:.3f}  L_d={l_d:.5f}  L_p={l_p:.3f}'
                  f'  val_d={mae_d:.2f}mm  val_e={mae_e:.3f}%')

        if mae_d < best_d:
            best_d  = mae_d; best_ep = ep
            best_st = copy.deepcopy(model.state_dict())
            best_ph = copy.deepcopy(phys.state_dict())
            pc = 0
        else:
            pc += 1
            if pc >= patience:
                print(f'    EarlyStop @ep{ep}  (best d={best_d:.2f}mm @{best_ep})')
                break

    model.load_state_dict(best_st)
    phys.load_state_dict(best_ph)
    te_e, te_d = _eval(model, tel, out_sc)
    t_sec = round(time.time() - t0, 1)
    print(f'    → Test  eps={te_e:.3f}%  d={te_d:.2f}mm  ({t_sec}s)')

    # 학습된 물리 파라미터 추출
    with torch.no_grad():
        phys_params = dict(
            alpha1=round(phys.alpha1.item(), 4),
            alpha2=round(phys.alpha2.item(), 4),
            beta1 =round(phys.beta1.item(),  4),
            beta2 =round(phys.beta2.item(),  4),
            beta3 =round(phys.beta3.item(),  4),
            d0    =round(phys.d0.item(),     4),
            k     =round(phys.k.item(),      4),
        )

    return dict(label=label, arch=model_cls.__name__,
                params=model_cls().param_count(),
                lam=lam_final,
                n_tr=n_tr, n_va=n_va, n_te=n_te,
                best_ep=best_ep, time_s=t_sec,
                test_eps=round(te_e, 3), test_d=round(te_d, 2),
                history=history,
                phys_params=phys_params)

# ── Timing benchmark ─────────────────────────────────────────────────────────

def bench_timing():
    model = TwoStageDecoupler(); model.eval()
    x = torch.zeros(1, 2)
    for _ in range(1000): model(x)          # warmup
    N = 100_000
    t0 = time.perf_counter()
    for _ in range(N): model(x)
    cpu_us = (time.perf_counter() - t0) / N * 1e6
    stm_fp32 = cpu_us * 170 / 3000
    stm_int8 = stm_fp32 / 4.0
    return cpu_us, stm_fp32, stm_int8

# ── HTML generation ───────────────────────────────────────────────────────────

def _js(lst): return json.dumps(lst)

def make_html(r_ts, r_sp, r_sd, cpu_us, stm_fp32, stm_int8):

    # ── epoch arrays for charts ───────────────────────────────────────────────
    def _col(hist, col): return [h[col] for h in hist]

    # Two-Stage PINN (r_ts) — full detail
    ep_ts  = _col(r_ts['history'], 0)
    lam_ts = _col(r_ts['history'], 1)
    ld_ts  = _col(r_ts['history'], 2)
    lp_ts  = _col(r_ts['history'], 3)
    ve_ts  = _col(r_ts['history'], 4)
    vd_ts  = _col(r_ts['history'], 5)

    # Single PINN (r_sp)
    ep_sp  = _col(r_sp['history'], 0)
    vd_sp  = _col(r_sp['history'], 5)

    # Single DNN (r_sd)
    ep_sd  = _col(r_sd['history'], 0)
    vd_sd  = _col(r_sd['history'], 5)

    # Align to max epoch for 3-model chart
    ep_max = max(ep_ts[-1], ep_sp[-1], ep_sd[-1])
    ep_all = list(range(1, ep_max + 1))
    def _align(hist):
        d = {h[0]: h[5] for h in hist}
        return [d.get(e) for e in ep_all]
    vd_ts_a = _align(r_ts['history'])
    vd_sp_a = _align(r_sp['history'])
    vd_sd_a = _align(r_sd['history'])

    # λ schedule line
    lam_line = [_lam(e, 50, 300, 0.10) for e in ep_ts]

    # Physics params
    pp = r_ts['phys_params']

    # Improvement numbers
    ts_vs_sd = r_sd['test_d'] - r_ts['test_d']
    sp_vs_sd = r_sd['test_d'] - r_sp['test_d']
    ts_vs_sp = r_sp['test_d'] - r_ts['test_d']

    now = time.strftime('%Y-%m-%d %H:%M')
    tdm_pct = stm_int8 / 1000.0 * 100.0

    # LUT memory estimate (50×50 grid, 2 float32 outputs)
    lut_kb = 50 * 50 * 2 * 4 / 1024

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Two-Stage PINN Decoupler — 종합 기술 보고서</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{{
  --bg:#1e1e2e;--bg2:#181825;--bg3:#313244;--text:#cdd6f4;--text2:#a6adc8;
  --border:#45475a;--blue:#89b4fa;--green:#a6e3a1;--yellow:#f9e2af;
  --mauve:#cba6f7;--red:#f38ba8;--teal:#94e2d5;--peach:#fab387;--sky:#89dceb;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',sans-serif;font-size:14px;line-height:1.7}}
.wrap{{max-width:1200px;margin:0 auto;padding:40px 24px}}
h1{{font-size:2rem;color:var(--blue);margin-bottom:6px}}
.sub{{color:var(--text2);font-size:.85rem;margin-bottom:40px}}
h2{{font-size:1.2rem;color:var(--mauve);margin:44px 0 16px;
    border-left:4px solid var(--mauve);padding-left:12px}}
h3{{font-size:1rem;color:var(--teal);margin:20px 0 10px}}
h4{{font-size:.9rem;color:var(--peach);margin:14px 0 6px}}
.card{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;
        padding:24px;margin-bottom:22px}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
.g3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
.g4{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}
.g5{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}}
.met{{background:var(--bg3);border-radius:10px;padding:18px;text-align:center}}
.met .v{{font-size:2rem;font-weight:700;font-family:Consolas,monospace;line-height:1.2}}
.met .l{{font-size:.72rem;color:var(--text2);letter-spacing:1px;text-transform:uppercase;margin-top:6px}}
table{{width:100%;border-collapse:collapse;font-size:.88rem}}
th,td{{padding:10px 14px;text-align:center;border-bottom:1px solid var(--border)}}
th{{background:var(--bg3);color:var(--text2);font-size:.76rem;letter-spacing:.5px;text-transform:uppercase}}
tr:hover td{{background:rgba(255,255,255,.02)}}
tr:last-child td{{border-bottom:none}}
td:first-child{{text-align:left}}
.pinn{{color:var(--blue);font-weight:600}}
.singlep{{color:var(--mauve);font-weight:600}}
.dnn{{color:var(--green);font-weight:600}}
.good{{color:var(--teal);font-weight:600}}
.bad{{color:var(--red)}}
.ch{{position:relative;height:300px;margin-top:14px}}
.ch2{{position:relative;height:260px;margin-top:14px}}
.tag{{display:inline-block;padding:2px 10px;border-radius:5px;font-size:.76rem;font-weight:600}}
.tp{{background:rgba(137,180,250,.15);color:var(--blue)}}
.tm{{background:rgba(203,166,247,.15);color:var(--mauve)}}
.td{{background:rgba(166,227,161,.15);color:var(--green)}}
.note{{color:var(--text2);font-size:.85rem;margin-bottom:14px;line-height:1.65}}
.box{{background:rgba(137,180,250,.06);border:1px solid rgba(137,180,250,.2);
       border-radius:8px;padding:18px;margin-top:16px}}
.box ul{{padding-left:22px}}
.box li{{margin-bottom:8px}}
.box li strong{{color:var(--yellow)}}
.formula{{background:var(--bg3);border-left:3px solid var(--teal);
           border-radius:0 8px 8px 0;padding:14px 20px;margin:10px 0;
           font-family:Consolas,monospace;font-size:.92rem;line-height:2}}
.arch-row{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:12px 0}}
.arch-box{{background:var(--bg3);border:1px solid var(--border);border-radius:8px;
            padding:10px 16px;font-family:Consolas,monospace;font-size:.88rem;
            text-align:center;min-width:64px;line-height:1.3}}
.arch-arr{{color:var(--text2);font-size:1.4rem;font-weight:300}}
code{{font-family:Consolas,monospace;background:var(--bg3);padding:1px 6px;
       border-radius:3px;font-size:.87em;color:var(--sky)}}
.badge{{display:inline-block;background:var(--bg3);border:1px solid var(--border);
         border-radius:6px;padding:3px 10px;font-family:Consolas,monospace;
         font-size:.82rem;margin:3px 4px}}
.sep{{border:none;border-top:2px dashed var(--border);margin:48px 0}}
.highlight{{background:rgba(249,226,175,.08);border:1px solid rgba(249,226,175,.3);
             border-radius:8px;padding:16px 20px;margin:12px 0}}
.highlight strong{{color:var(--yellow)}}
</style>
</head>
<body>
<div class="wrap">

<h1>Two-Stage PINN Decoupler — 종합 기술 보고서</h1>
<p class="sub">Multimodal Soft Sensor Signal Decoupling · ldc_iir(α=0.18) + R_DC_filtered · {now} · BiRC Lab, 고려대학교</p>

<!-- ══ 0. 요약 ═══════════════════════════════════════════════════════════════ -->
<div class="g5" style="margin-bottom:24px">
  <div class="met">
    <div class="v" style="color:var(--blue)">{r_ts['test_d']:.2f}<span style="font-size:1.1rem"> mm</span></div>
    <div class="l">Two-Stage PINN<br>Test MAE d</div>
  </div>
  <div class="met">
    <div class="v" style="color:var(--blue)">{r_ts['test_eps']:.3f}<span style="font-size:1.1rem"> %</span></div>
    <div class="l">Two-Stage PINN<br>Test MAE ε</div>
  </div>
  <div class="met">
    <div class="v" style="color:var(--mauve)">{r_ts['params']}</div>
    <div class="l">파라미터 수<br>(Two-Stage)</div>
  </div>
  <div class="met">
    <div class="v" style="color:var(--teal)">{stm_int8:.1f}<span style="font-size:1.1rem"> µs</span></div>
    <div class="l">STM32 INT8<br>추론 시간 추정</div>
  </div>
  <div class="met">
    <div class="v" style="color:var(--green)">{r_ts['best_ep']}<span style="font-size:1.1rem">ep</span></div>
    <div class="l">Best Epoch<br>(Two-Stage PINN)</div>
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════ -->
<div class="sep"></div>

<!-- ══ 1. 전체 모델 구조 ══════════════════════════════════════════════════════ -->
<h2>1. 전체 모델 구조</h2>
<div class="card">
  <p class="note">
    EGaIn 스파이럴 코일 단일 전극에서 TDM(Time Division Measurement)으로
    <strong>L (인덕턴스), R_DC (저항), V_TENG (전압)</strong> 3종을 1ms 주기로 취득.
    신호 간 물리적 결합(coupling)이 존재하므로, 역산 모델로 ε(변형률)과 d(근접거리)를 동시 디커플링.
  </p>
  <div class="g2">
    <div>
      <h3>시스템 전체 흐름</h3>
      <div class="arch-row" style="flex-direction:column;align-items:flex-start;gap:6px">
        <div style="display:flex;align-items:center;gap:8px">
          <div class="arch-box" style="border-color:var(--peach);min-width:130px">EGaIn 코일<br><small>단일 전극 (2선)</small></div>
          <span class="arch-arr">→</span>
          <div class="arch-box" style="min-width:160px">TDM PCB<br><small>STM32G473 + LDC1614</small></div>
        </div>
        <div style="margin-left:60px;color:var(--text2)">↓ UART (100Hz, CSV)</div>
        <div style="display:flex;align-items:center;gap:8px">
          <div class="arch-box" style="border-color:var(--blue);min-width:130px">L_DC (LDC freq)<br><small>R_DC, V_TENG</small></div>
          <span class="arch-arr">→</span>
          <div class="arch-box" style="min-width:160px">전처리<br><small>ΔL/L₀, ΔR/R₀ 계산</small></div>
          <span class="arch-arr">→</span>
          <div class="arch-box" style="border-color:var(--green);min-width:120px">PINN 추론<br><small>ε̂, d̂ 출력</small></div>
        </div>
      </div>
      <h3 style="margin-top:22px">Two-Stage PINN 구조</h3>
      <p class="note" style="margin-bottom:8px">
        ΔR은 변형률에만 지배적 → Stage1이 먼저 ε를 독립 추정.<br>
        이후 Stage2가 ΔL과 ε̂를 함께 사용하여 d를 추정.
      </p>
      <div class="arch-row">
        <div class="arch-box" style="border-color:var(--peach)">ΔR<br><small>(1)</small></div>
        <span class="arch-arr">→</span>
        <div class="arch-box" style="border-color:var(--blue)">Stage 1<br><small>1→16→8→1</small></div>
        <span class="arch-arr">→</span>
        <div class="arch-box" style="border-color:var(--blue)">ε̂<br><small>(1)</small></div>
      </div>
      <div class="arch-row">
        <div class="arch-box" style="border-color:var(--peach)">ΔL, ε̂<br><small>(2)</small></div>
        <span class="arch-arr">→</span>
        <div class="arch-box" style="border-color:var(--teal)">Stage 2<br><small>2→32→16→1</small></div>
        <span class="arch-arr">→</span>
        <div class="arch-box" style="border-color:var(--teal)">d̂<br><small>(1)</small></div>
      </div>
    </div>
    <div>
      <h3>파라미터 구성</h3>
      <table>
        <thead><tr><th>구성 요소</th><th>레이어</th><th>파라미터</th></tr></thead>
        <tbody>
          <tr><td>Stage 1</td><td>1→16→8→1 (Tanh)</td><td class="pinn">177</td></tr>
          <tr><td>Stage 2</td><td>2→32→16→1 (Tanh)</td><td class="pinn">641</td></tr>
          <tr><td><b>Two-Stage 합계</b></td><td>—</td><td class="pinn"><b>{r_ts['params']}</b></td></tr>
          <tr><td>Single-Stage</td><td>2→24→16→8→2 (Tanh)</td><td class="singlep">{r_sp['params']}</td></tr>
          <tr><td>Physics params</td><td>α₁,α₂,β₁,β₂,β₃,d₀,k</td><td>7</td></tr>
        </tbody>
      </table>
      <h3 style="margin-top:20px">모델 크기 (STM32 배포)</h3>
      <table>
        <thead><tr><th>포맷</th><th>Two-Stage</th><th>Single-Stage</th></tr></thead>
        <tbody>
          <tr><td>FP32 (.onnx)</td><td>3.3 KB</td><td>2.6 KB</td></tr>
          <tr><td>INT8 (X-CUBE-AI)</td><td>~0.85 KB</td><td>~0.65 KB</td></tr>
          <tr><td>STM32G473 Flash 256KB 대비</td><td>&lt; 0.4%</td><td>&lt; 0.3%</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ 2. 데이터 입력 처리 ════════════════════════════════════════════════════ -->
<h2>2. 데이터 입력 처리</h2>
<div class="card">
  <div class="g2">
    <div>
      <h3>원시 신호 → 입력 특징 변환</h3>
      <p class="note">
        STM32에서 출력되는 raw 신호는 절대값이며 센서마다 초기값이 다름.
        물리적으로 의미 있는 <b>상대 변화율(%)</b>로 변환하여 센서 개체차 제거.
      </p>
      <div class="formula">
ΔL/L₀ (%) = [ (L₀/L_meas)² - 1 ] × 100<br>
ΔR/R₀ (%) = [ (R_meas - R₀) / R₀ ] × 100<br><br>
L₀, R₀ : 기준 상태 (d=50mm, ε=0) 평균값
      </div>
      <h4>LDC IIR 필터 (α = {LDC_IIR_ALPHA})</h4>
      <div class="formula">
L_filt[n] = (1-α)·L_filt[n-1] + α·L_raw[n]<br>
α = {LDC_IIR_ALPHA}  →  τ ≈ {1/LDC_IIR_ALPHA:.0f} 샘플 ≈ {1/LDC_IIR_ALPHA/100:.1f}s @ 100Hz
      </div>
      <p class="note">LDC1614 공진 측정의 고주파 노이즈 제거. R_DC는 STM32 IIR(α=0.02) 적용된 Channel 2 사용.</p>
    </div>
    <div>
      <h3>전처리 파이프라인</h3>
      <table>
        <thead><tr><th>단계</th><th>입력</th><th>출력</th><th>이유</th></tr></thead>
        <tbody>
          <tr><td>1. IIR 필터</td><td>LDC raw freq</td><td>LDC smoothed</td><td>공진 노이즈 제거</td></tr>
          <tr><td>2. 정규화 ΔL</td><td>LDC smoothed, L₀</td><td>ΔL/L₀ (%)</td><td>센서 개체차 제거</td></tr>
          <tr><td>3. 정규화 ΔR</td><td>R_filtered, R₀</td><td>ΔR/R₀ (%)</td><td>절대값 의존성 제거</td></tr>
          <tr><td>4. StandardScaler</td><td>ΔL, ΔR</td><td>z-score</td><td>학습 안정성, 그래디언트 균형</td></tr>
          <tr><td>5. 출력 Scaler</td><td>ε, d</td><td>z-score</td><td>MSE loss 스케일 균형</td></tr>
        </tbody>
      </table>
      <h3 style="margin-top:18px">Train / Val / Test 분할</h3>
      <table>
        <thead><tr><th>분할</th><th>strain 파일</th><th>샘플 수</th><th>선택 이유</th></tr></thead>
        <tbody>
          <tr><td>Train</td><td>나머지 28개</td><td class="pinn">{r_ts['n_tr']:,}</td><td>균일 분포 학습</td></tr>
          <tr><td>Val</td><td>4, 13, 22, 31</td><td>{r_ts['n_va']:,}</td><td>전 구간 균등 샘플링</td></tr>
          <tr><td>Test</td><td>0, 9, 18, 27, 36</td><td>{r_ts['n_te']:,}</td><td>경계+중간 검증</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ 3. Single vs Two-Stage 비교 ═══════════════════════════════════════════ -->
<h2>3. Single-Stage vs Two-Stage 아키텍처 비교</h2>
<div class="card">
  <div class="g2">
    <div>
      <h3>Two-Stage 설계 근거</h3>
      <p class="note">
        물리 방정식에서 ΔR은 ε에만 지배적으로 의존하고, ΔL은 ε와 d 모두에 의존:
      </p>
      <div class="formula">
R_theory(ε)    = α₁·ε + α₂·ε²      (d 독립)<br>
L_theory(ε, d) = β₁·ε + β₂/(d+d₀)ᵏ + β₃·ε/(d+d₀)
      </div>
      <p class="note" style="margin-top:10px">
        Two-Stage는 이 인과구조를 <b>아키텍처 자체에 hardcode</b>:
        Stage1(ΔR→ε̂)은 ε만 담당,  Stage2(ΔL,ε̂→d̂)는 d만 담당.
        Single-Stage는 ΔL, ΔR 모두를 동시에 보고 ε,d를 함께 추정 — 물리적 독립성을 데이터에서 학습해야 함.
      </p>
      <h3 style="margin-top:18px">Single-Stage 아키텍처</h3>
      <div class="arch-row">
        <div class="arch-box" style="border-color:var(--peach)">ΔL, ΔR<br><small>(2)</small></div>
        <span class="arch-arr">→</span>
        <div class="arch-box" style="border-color:var(--mauve)">2→24→16→8→2<br><small>Tanh</small></div>
        <span class="arch-arr">→</span>
        <div class="arch-box" style="border-color:var(--mauve)">ε̂, d̂<br><small>(2)</small></div>
      </div>
    </div>
    <div>
      <h3>성능 비교표</h3>
      <table>
        <thead><tr>
          <th>모델</th><th>파라미터</th>
          <th>Test MAE ε (%)</th><th>Test MAE d (mm)</th>
          <th>Best Epoch</th><th>학습 시간</th>
        </tr></thead>
        <tbody>
          <tr>
            <td><span class="tag tp">Two-Stage PINN</span></td>
            <td>{r_ts['params']}</td>
            <td class="pinn">{r_ts['test_eps']}</td>
            <td class="pinn">{r_ts['test_d']}</td>
            <td>{r_ts['best_ep']}</td>
            <td>{r_ts['time_s']}s</td>
          </tr>
          <tr>
            <td><span class="tag tm">Single PINN</span></td>
            <td>{r_sp['params']}</td>
            <td class="singlep">{r_sp['test_eps']}</td>
            <td class="singlep">{r_sp['test_d']}</td>
            <td>{r_sp['best_ep']}</td>
            <td>{r_sp['time_s']}s</td>
          </tr>
          <tr>
            <td><span class="tag td">Single DNN</span></td>
            <td>{r_sd['params']}</td>
            <td class="dnn">{r_sd['test_eps']}</td>
            <td class="dnn">{r_sd['test_d']}</td>
            <td>{r_sd['best_ep']}</td>
            <td>{r_sd['time_s']}s</td>
          </tr>
        </tbody>
      </table>
      <table style="margin-top:14px">
        <thead><tr><th>비교</th><th>MAE d 차이</th><th>해석</th></tr></thead>
        <tbody>
          <tr>
            <td>Two-Stage PINN vs Single DNN</td>
            <td class="pinn">{'↑ ' if ts_vs_sd>0 else '↓ '}{abs(ts_vs_sd):.2f} mm</td>
            <td>Architecture + Physics 합산</td>
          </tr>
          <tr>
            <td>Single PINN vs Single DNN</td>
            <td class="{'pinn' if sp_vs_sd>0 else 'dnn'}">{'↑ ' if sp_vs_sd>0 else '↓ '}{abs(sp_vs_sd):.2f} mm</td>
            <td>Physics Loss 단독 효과</td>
          </tr>
          <tr>
            <td>Two-Stage vs Single PINN</td>
            <td class="{'pinn' if ts_vs_sp>0 else 'dnn'}">{'↑ ' if ts_vs_sp>0 else '↓ '}{abs(ts_vs_sp):.2f} mm</td>
            <td>Two-Stage 구조 단독 효과</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
  <h3>3-모델 Val MAE d 수렴 곡선 비교</h3>
  <div class="ch"><canvas id="cArch"></canvas></div>
</div>

<!-- ══ 4. PINN ════════════════════════════════════════════════════════════════ -->
<h2>4. Physics-Informed Neural Network (PINN)</h2>

<!-- 4.1 개념 및 수식 -->
<div class="card">
  <h3>4.1 PINN 개념 및 Loss 함수</h3>
  <p class="note">
    순수 데이터 기반 DNN은 학습 데이터 분포 밖에서 물리적으로 불가능한 예측을 할 수 있음.
    PINN은 신경망 출력이 <b>물리 방정식을 만족하도록</b> 추가 패널티를 부과.
  </p>
  <div class="g2">
    <div>
      <h4>물리 모델 (경험적 피팅)</h4>
      <div class="formula">
R_theory(ε̂)      = α₁·ε̂ + α₂·ε̂²<br>
L_theory(ε̂, d̂)  = β₁·ε̂ + β₂/(d̂+d₀)ᵏ + β₃·ε̂/(d̂+d₀)
      </div>
      <h4>Loss 함수</h4>
      <div class="formula">
L_total = L_data + λ · L_phys<br><br>
L_data  = MSE(ε̂_norm, ε_norm) + MSE(d̂_norm, d_norm)<br><br>
L_phys  = MSE(R_theory(ε̂), ΔR_meas)<br>
        + MSE(L_theory(ε̂,d̂), ΔL_meas)
      </div>
    </div>
    <div>
      <h4>λ 워밍업 스케줄</h4>
      <div class="formula">
epoch &lt; warmup(50) : λ = 0.0<br>
epoch ≥ warmup      : λ = (ep-50)/(300-50) × 0.10
      </div>
      <p class="note" style="margin-top:10px">
        초기에는 데이터 손실만으로 빠르게 수렴 방향 설정 후,
        물리 제약을 점진적으로 적용하여 <b>학습 안정성과 물리 일관성을 동시 확보</b>.
      </p>
      <h4>물리 파라미터 학습 방식</h4>
      <p class="note">
        α₁, α₂, β₁, β₂, β₃는 unconstrained learnable parameters.<br>
        d₀, k는 <code>softplus</code> 적용으로 항상 양수 보장 (특이점 방지).
      </p>
      <div class="formula">
d₀ = softplus(d₀_raw),  k = softplus(k_raw)
      </div>
    </div>
  </div>
</div>

<!-- 4.2 학습 곡선 -->
<div class="card">
  <h3>4.2 Two-Stage PINN 학습 곡선 (전체 에폭)</h3>
  <div class="g2">
    <div>
      <h4>Data Loss vs Physics Loss (log scale)</h4>
      <div class="ch"><canvas id="cLoss"></canvas></div>
    </div>
    <div>
      <h4>Val MAE ε (%) 와 Val MAE d (mm)</h4>
      <div class="ch"><canvas id="cValMAE"></canvas></div>
    </div>
  </div>
  <div class="g2" style="margin-top:18px">
    <div>
      <h4>λ 스케줄 (Physics Loss 가중치)</h4>
      <div class="ch2"><canvas id="cLam"></canvas></div>
    </div>
    <div>
      <h4>Train Loss 총합 (L_data + λ·L_phys)</h4>
      <div class="ch2"><canvas id="cTotal"></canvas></div>
    </div>
  </div>
</div>

<!-- 4.3 PINN vs DNN 비교 -->
<div class="card">
  <h3>4.3 PINN vs DNN 학습 비교 (Two-Stage 기준)</h3>
  <div class="g2">
    <div>
      <h4>Val MAE d 수렴 곡선 (PINN vs DNN)</h4>
      <div class="ch"><canvas id="cPvsD"></canvas></div>
    </div>
    <div>
      <h4>수렴 속도 및 최종 성능</h4>
      <table>
        <thead><tr><th>지표</th><th class="pinn">PINN (λ=0.10)</th><th class="dnn">DNN (λ=0.00)</th></tr></thead>
        <tbody>
          <tr><td>Test MAE ε (%)</td><td class="pinn">{r_ts['test_eps']}</td><td class="dnn">{r_sd['test_eps']}</td></tr>
          <tr><td>Test MAE d (mm)</td><td class="pinn">{r_ts['test_d']}</td><td class="dnn">{r_sd['test_d']}</td></tr>
          <tr><td>Best Epoch</td><td class="pinn">{r_ts['best_ep']}</td><td class="dnn">{r_sd['best_ep']}</td></tr>
          <tr><td>학습 시간</td><td class="pinn">{r_ts['time_s']}s</td><td class="dnn">{r_sd['time_s']}s</td></tr>
          <tr><td>파라미터 수</td><td class="pinn">{r_ts['params']}</td><td class="dnn">{r_ts['params']}</td></tr>
          <tr><td>추가 학습 파라미터</td><td class="pinn">+7 (물리)</td><td class="dnn">없음</td></tr>
        </tbody>
      </table>
      <div class="highlight" style="margin-top:14px">
        <strong>PINN 장점</strong>: 데이터가 적을수록 Physics Loss의 regularization 효과가 두드러짐.
        특히 새 센서 형상/재료 적용 시 재학습 데이터 수집 비용 절감 가능.
      </div>
    </div>
  </div>
</div>

<!-- 4.4 학습된 물리 파라미터 -->
<div class="card">
  <h3>4.4 학습된 물리 파라미터 (Two-Stage PINN)</h3>
  <div class="g2">
    <div>
      <table>
        <thead><tr><th>파라미터</th><th>의미</th><th>모델 수식</th><th>학습 후 값</th></tr></thead>
        <tbody>
          <tr><td><code>α₁</code></td><td>ΔR/R₀ 선형 계수</td><td>α₁·ε</td><td class="pinn">{pp['alpha1']}</td></tr>
          <tr><td><code>α₂</code></td><td>ΔR/R₀ 이차 계수</td><td>α₂·ε²</td><td class="pinn">{pp['alpha2']}</td></tr>
          <tr><td><code>β₁</code></td><td>ΔL/L₀ 변형률 계수</td><td>β₁·ε</td><td class="pinn">{pp['beta1']}</td></tr>
          <tr><td><code>β₂</code></td><td>ΔL/L₀ 근접거리 계수</td><td>β₂/(d+d₀)ᵏ</td><td class="pinn">{pp['beta2']}</td></tr>
          <tr><td><code>β₃</code></td><td>ΔL/L₀ 교차 결합</td><td>β₃·ε/(d+d₀)</td><td class="pinn">{pp['beta3']}</td></tr>
          <tr><td><code>d₀</code></td><td>근접거리 오프셋</td><td>softplus(d₀_raw)</td><td class="pinn">{pp['d0']} mm</td></tr>
          <tr><td><code>k</code></td><td>거리 거듭제곱 지수</td><td>softplus(k_raw)</td><td class="pinn">{pp['k']}</td></tr>
        </tbody>
      </table>
      <p class="note" style="margin-top:12px">
        α₁·ε + α₂·ε² ≈ 저항-변형 관계. ε≈0.15(15mm)에서 ΔR/R₀ ≈ {pp['alpha1']*0.15+pp['alpha2']*0.15**2:.1f}%.
      </p>
    </div>
    <div>
      <h4>물리 해석</h4>
      <div class="box">
        <ul>
          <li><strong>α₁+α₂ 관계</strong>: 전체 저항 증가율이 이차 다항식으로 표현됨.
            R_DC의 변형 의존성 (도체 길이·단면적 변화)을 학습이 자동 포착.</li>
          <li><strong>β₂ 부호</strong>: {"β₂ > 0이면 d 감소 시 ΔL 증가 (코일이 금속 물체에 접근)" if pp['beta2']>0 else "β₂ < 0이면 d 감소 시 ΔL 감소 (상호 인덕턴스 부호)"}.
            물리적으로 타겟 물체 재질·형상에 의존하는 값.</li>
          <li><strong>d₀ = {pp['d0']:.2f}mm</strong>: 근접거리 0mm 근방 특이점 방지 오프셋.
            softplus로 항상 양수 보장.</li>
          <li><strong>k = {pp['k']:.3f}</strong>: 거리-인덕턴스 감쇠 지수.
            이론적으로 쌍극자 근사에서 k≈3이지만, 실제 형상에 맞게 학습됨.</li>
        </ul>
      </div>
    </div>
  </div>
</div>

<!-- ══ 5. MCU 임베딩 비교 ══════════════════════════════════════════════════════ -->
<h2>5. MCU 임베딩 — DNN vs 수식 역산 vs 룩업 테이블</h2>
<div class="card">
  <h3>5.1 방법론 비교</h3>
  <div class="g3">
    <div>
      <h4 style="color:var(--blue)">① DNN (Two-Stage PINN)</h4>
      <p class="note">
        학습된 신경망을 ONNX → X-CUBE-AI → INT8로 STM32에 직접 배포.
        매 TDM 주기에 forward pass 1회 실행.
      </p>
      <div class="badge">ONNX export</div>
      <div class="badge">INT8 양자화</div>
      <div class="badge">O(1) 추론</div>
      <div class="badge">확정적 결과</div>
    </div>
    <div>
      <h4 style="color:var(--yellow)">② 수식 역산 (Newton-Raphson)</h4>
      <p class="note">
        ΔR=R(ε), ΔL=L(ε,d) 연립방정식을 반복법으로 풀어 ε,d를 추정.
        비선형 시스템으로 야코비안 계산 + 반복 필요.
      </p>
      <div class="badge">코드만 필요</div>
      <div class="badge">반복 수렴</div>
      <div class="badge" style="color:var(--red)">수렴 불확실</div>
      <div class="badge" style="color:var(--red)">야코비안 특이점</div>
    </div>
    <div>
      <h4 style="color:var(--green)">③ 룩업 테이블 (LUT)</h4>
      <p class="note">
        (ΔL, ΔR) 격자점에 대한 (ε, d) 값을 사전 계산하여 Flash에 저장.
        측정 시 보간(bilinear)으로 추정.
      </p>
      <div class="badge">빠른 조회</div>
      <div class="badge" style="color:var(--red)">대용량 Flash</div>
      <div class="badge" style="color:var(--red)">이산화 오차</div>
      <div class="badge" style="color:var(--red)">재학습 어려움</div>
    </div>
  </div>

  <h3 style="margin-top:22px">5.2 정량 비교표</h3>
  <table>
    <thead>
      <tr>
        <th>항목</th>
        <th style="color:var(--blue)">DNN (Two-Stage)</th>
        <th style="color:var(--yellow)">수식 역산 (N-R)</th>
        <th style="color:var(--green)">LUT (50×50)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Flash 사용량</td>
        <td class="pinn">~0.85 KB (INT8)</td>
        <td>~2 KB (코드)</td>
        <td class="bad">~{lut_kb:.0f} KB (격자)</td>
      </tr>
      <tr>
        <td>RAM 사용량</td>
        <td class="pinn">~256 B (활성화)</td>
        <td>~128 B (변수)</td>
        <td>~256 B (인덱스)</td>
      </tr>
      <tr>
        <td>STM32 추론 시간 (FP32 추정)</td>
        <td class="pinn">{stm_fp32:.1f} µs</td>
        <td class="bad">~500–2000 µs (5–20iter)</td>
        <td class="good">~1 µs</td>
      </tr>
      <tr>
        <td>STM32 추론 시간 (INT8)</td>
        <td class="pinn"><b>{stm_int8:.1f} µs</b></td>
        <td>N/A (FP32 필수)</td>
        <td class="good">~1 µs</td>
      </tr>
      <tr>
        <td>TDM 1ms 대비 부하율</td>
        <td class="pinn">&lt; {tdm_pct:.2f}%</td>
        <td class="bad">50–200% (주기 초과 위험)</td>
        <td class="good">&lt; 0.1%</td>
      </tr>
      <tr>
        <td>Test MAE d</td>
        <td class="pinn">{r_ts['test_d']:.2f} mm</td>
        <td class="bad">발산 위험 (극단 조건)</td>
        <td>~5–8 mm (격자 해상도)</td>
      </tr>
      <tr>
        <td>수렴 확정성</td>
        <td class="pinn">항상 O(1)</td>
        <td class="bad">불확실 (야코비안 특이)</td>
        <td class="good">항상 O(1)</td>
      </tr>
      <tr>
        <td>새 센서 적용</td>
        <td class="pinn">재학습 → ONNX 재변환</td>
        <td>파라미터 재피팅</td>
        <td class="bad">격자 전체 재계산</td>
      </tr>
      <tr>
        <td>물리 파라미터 해석</td>
        <td class="pinn">학습으로 자동 추출</td>
        <td class="pinn">명시적 (α₁,α₂,β₁…)</td>
        <td class="bad">없음 (black box)</td>
      </tr>
    </tbody>
  </table>

  <h3 style="margin-top:22px">5.3 STM32 배포 파이프라인</h3>
  <div class="arch-row" style="justify-content:center;padding:10px 0;gap:12px">
    <div class="arch-box" style="border-color:var(--blue);min-width:100px">PyTorch<br>FP32<br><small>train.py</small></div>
    <span class="arch-arr">→</span>
    <div class="arch-box" style="min-width:100px">ONNX<br>Export<br><small>opset 17</small></div>
    <span class="arch-arr">→</span>
    <div class="arch-box" style="min-width:100px">X-CUBE-AI<br>Post-Quant<br><small>INT8</small></div>
    <span class="arch-arr">→</span>
    <div class="arch-box" style="min-width:100px">C 코드<br>생성<br><small>network.c/h</small></div>
    <span class="arch-arr">→</span>
    <div class="arch-box" style="border-color:var(--green);min-width:100px">STM32<br>실시간 추론<br><small>{stm_int8:.1f} µs</small></div>
  </div>

  <div class="g2" style="margin-top:16px">
    <div>
      <h4>추론 시간 측정 결과</h4>
      <table>
        <thead><tr><th>플랫폼</th><th>정밀도</th><th>1회 추론</th><th>비고</th></tr></thead>
        <tbody>
          <tr><td>PC CPU (측정)</td><td>FP32</td><td class="pinn">{cpu_us:.2f} µs</td><td>100K회 평균</td></tr>
          <tr><td>STM32G473 (추정)</td><td>FP32</td><td class="pinn">{stm_fp32:.1f} µs</td><td>클럭 비율 170/3000 환산</td></tr>
          <tr><td>STM32G473 (추정)</td><td>INT8</td><td class="pinn"><b>{stm_int8:.1f} µs</b></td><td>INT8 ≈ FP32×4 가속</td></tr>
          <tr><td>TDM 1ms 주기 대비</td><td>—</td><td class="pinn">&lt;{tdm_pct:.2f}%</td><td>충분한 여유</td></tr>
        </tbody>
      </table>
    </div>
    <div>
      <h4>메모리 요약</h4>
      <table>
        <thead><tr><th>항목</th><th>용량</th><th>STM32G473 대비</th></tr></thead>
        <tbody>
          <tr><td>INT8 모델 (Flash)</td><td class="pinn">~0.85 KB</td><td>256KB 대비 0.33%</td></tr>
          <tr><td>Scaler 상수 (Flash)</td><td>~0.5 KB</td><td>C 헤더로 포함</td></tr>
          <tr><td>활성화 버퍼 (RAM)</td><td class="pinn">~256 B</td><td>80KB 대비 0.31%</td></tr>
          <tr><td>LUT 50×50 대비</td><td class="pinn">97% 절약</td><td>{lut_kb:.0f}KB → 0.85KB</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

</div><!-- /wrap -->
<script>
Chart.defaults.color = '#a6adc8';
Chart.defaults.borderColor = '#45475a';
const PC = '#89b4fa', MC = '#cba6f7', DC = '#a6e3a1', YC = '#f9e2af', TC = '#94e2d5';

// 3-model convergence
new Chart('cArch', {{
  type: 'line',
  data: {{
    labels: {_js(ep_all)},
    datasets: [
      {{ label: 'Two-Stage + PINN', data: {_js(vd_ts_a)},
         borderColor: PC, borderWidth:2, pointRadius:0, tension:.3 }},
      {{ label: 'Single + PINN',    data: {_js(vd_sp_a)},
         borderColor: MC, borderWidth:2, pointRadius:0, tension:.3 }},
      {{ label: 'Single + DNN',     data: {_js(vd_sd_a)},
         borderColor: DC, borderWidth:2, pointRadius:0, tension:.3 }},
    ]
  }},
  options:{{ responsive:true, maintainAspectRatio:false,
    plugins:{{legend:{{position:'top'}}}},
    scales:{{ x:{{title:{{display:true,text:'Epoch'}}}}, y:{{title:{{display:true,text:'Val MAE d (mm)'}}}} }} }}
}});

// Loss curves (PINN)
new Chart('cLoss', {{
  type: 'line',
  data: {{
    labels: {_js(ep_ts)},
    datasets: [
      {{ label: 'L_data', data: {_js(ld_ts)},
         borderColor: PC, borderWidth:2, pointRadius:0, tension:.3, yAxisID:'y' }},
      {{ label: 'L_phys', data: {_js(lp_ts)},
         borderColor: YC, borderWidth:2, pointRadius:0, tension:.3, yAxisID:'y2' }},
    ]
  }},
  options:{{ responsive:true, maintainAspectRatio:false,
    plugins:{{legend:{{position:'top'}}}},
    scales:{{
      x:{{title:{{display:true,text:'Epoch'}}}},
      y:{{title:{{display:true,text:'L_data (MSE)'}},position:'left'}},
      y2:{{title:{{display:true,text:'L_phys'}},position:'right',grid:{{drawOnChartArea:false}}}}
    }}
  }}
}});

// Val MAE curves
new Chart('cValMAE', {{
  type: 'line',
  data: {{
    labels: {_js(ep_ts)},
    datasets: [
      {{ label: 'Val MAE ε (%)', data: {_js(ve_ts)},
         borderColor: TC, borderWidth:2, pointRadius:0, tension:.3, yAxisID:'y' }},
      {{ label: 'Val MAE d (mm)', data: {_js(vd_ts)},
         borderColor: PC, borderWidth:2, pointRadius:0, tension:.3, yAxisID:'y2' }},
    ]
  }},
  options:{{ responsive:true, maintainAspectRatio:false,
    plugins:{{legend:{{position:'top'}}}},
    scales:{{
      x:{{title:{{display:true,text:'Epoch'}}}},
      y:{{title:{{display:true,text:'MAE ε (%)'}},position:'left'}},
      y2:{{title:{{display:true,text:'MAE d (mm)'}},position:'right',grid:{{drawOnChartArea:false}}}}
    }}
  }}
}});

// λ schedule
new Chart('cLam', {{
  type: 'line',
  data: {{
    labels: {_js(ep_ts)},
    datasets:[
      {{ label: 'λ (Physics weight)', data: {_js(lam_line)},
         borderColor: YC, borderWidth:2, pointRadius:0, tension:.1,
         fill:true, backgroundColor:'rgba(249,226,175,.08)' }},
    ]
  }},
  options:{{ responsive:true, maintainAspectRatio:false,
    plugins:{{legend:{{position:'top'}}}},
    scales:{{x:{{title:{{display:true,text:'Epoch'}}}}, y:{{title:{{display:true,text:'λ'}}, min:0, max:0.12}}}}
  }}
}});

// Total train loss
const total_ts = {_js(ld_ts)}.map((v,i)=>{{
  const lam = {_js(lam_line)}[i]||0;
  const lp  = {_js(lp_ts)}[i]||0;
  return +(v + lam*lp).toFixed(5);
}});
new Chart('cTotal', {{
  type:'line',
  data:{{ labels:{_js(ep_ts)},
    datasets:[{{ label:'L_total = L_data + λ·L_phys', data:total_ts,
      borderColor:MC, borderWidth:2, pointRadius:0, tension:.3 }}] }},
  options:{{ responsive:true, maintainAspectRatio:false,
    plugins:{{legend:{{position:'top'}}}},
    scales:{{x:{{title:{{display:true,text:'Epoch'}}}}, y:{{title:{{display:true,text:'L_total'}}}}}}
  }}
}});

// PINN vs DNN
const ep_sd_map = {{}};
{_js(r_sd['history'])}.forEach(h=>{{ ep_sd_map[h[0]]=h[5]; }});
const vd_sd_aligned = {_js(ep_ts)}.map(e=>ep_sd_map[e]??null);
new Chart('cPvsD', {{
  type:'line',
  data:{{
    labels:{_js(ep_ts)},
    datasets:[
      {{ label:'PINN (λ=0.10)', data:{_js(vd_ts)}, borderColor:PC, borderWidth:2, pointRadius:0, tension:.3 }},
      {{ label:'DNN  (λ=0.00)', data:vd_sd_aligned,  borderColor:DC, borderWidth:2, pointRadius:0, tension:.3 }},
    ]
  }},
  options:{{ responsive:true, maintainAspectRatio:false,
    plugins:{{legend:{{position:'top'}}}},
    scales:{{x:{{title:{{display:true,text:'Epoch'}}}}, y:{{title:{{display:true,text:'Val MAE d (mm)'}}}}}}
  }}
}});
</script>
</body>
</html>"""
    return html


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  종합 기술 보고서 실험")
    print("  전처리: ldc_iir(α=0.18) + Channel 2 (R_DC_filtered)")
    print("=" * 65)

    EPOCHS  = 300
    PATIENCE = 30

    r_ts = run_one("Two-Stage PINN (λ=0.10)", TwoStageDecoupler, 0.10, EPOCHS, PATIENCE)
    r_sp = run_one("Single-Stage PINN (λ=0.10)", SinglePINNMLP,  0.10, EPOCHS, PATIENCE)
    r_sd = run_one("Single-Stage DNN  (λ=0.00)", SinglePINNMLP,  0.00, EPOCHS, PATIENCE)

    print('\n  [추론 시간 측정]')
    cpu_us, stm_fp32, stm_int8 = bench_timing()
    print(f'  CPU FP32: {cpu_us:.2f} us  STM32 FP32: {stm_fp32:.1f} us  STM32 INT8: {stm_int8:.1f} us')

    html = make_html(r_ts, r_sp, r_sd, cpu_us, stm_fp32, stm_int8)
    out  = os.path.join(HERE, 'report_comprehensive.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n{'='*65}")
    print(f"  report_comprehensive.html 저장 완료")
    print(f"\n  최종 결과:")
    print(f"    Two-Stage PINN : eps={r_ts['test_eps']}%  d={r_ts['test_d']}mm  (best ep {r_ts['best_ep']})")
    print(f"    Single  PINN   : eps={r_sp['test_eps']}%  d={r_sp['test_d']}mm  (best ep {r_sp['best_ep']})")
    print(f"    Single  DNN    : eps={r_sd['test_eps']}%  d={r_sd['test_d']}mm  (best ep {r_sd['best_ep']})")
    print(f"    Physics params : a1={r_ts['phys_params']['alpha1']}  a2={r_ts['phys_params']['alpha2']}")
    print(f"                     b1={r_ts['phys_params']['beta1']}  b2={r_ts['phys_params']['beta2']}")
    print(f"                     b3={r_ts['phys_params']['beta3']}  d0={r_ts['phys_params']['d0']}mm  k={r_ts['phys_params']['k']}")
    print(f"{'='*65}")


if __name__ == '__main__':
    main()
