"""
arch_search.py — PyTorch 2-Stage MLP 아키텍처 탐색

Stage1: dR_pct → eps_act_pct  (1 → hidden → 1)
Stage2: (dL_pct, eps_hat) → d_act_mm  (2 → hidden → 1)

활성화: Tanh (bounded → INT8 친화적)
손실:   MSE only (물리 손실 없음 → 아키텍처 영향 순수 분리)
선택:   val d MAE 기준 best checkpoint

출력:
  checkpoints/arch_search_results.json   — 모든 결과
  data_acquisition/dataset/arch_search_pareto.png — Pareto 그래프

Usage:
    C:/ml_env/Scripts/python nn_decoupling/arch_search.py
"""
import os, sys, json, time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.preprocessing import StandardScaler
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

HERE        = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(HERE, 'data_acquisition', 'dataset')
CKPT_DIR    = os.path.join(HERE, 'checkpoints')
os.makedirs(CKPT_DIR, exist_ok=True)

# ─── 학습 하이퍼파라미터 ────────────────────────────────────────────────────
EPOCHS   = 300
PATIENCE = 40
LR       = 1e-3
WD       = 1e-4
BATCH    = 256
SEED     = 42

# ─── 탐색 아키텍처 정의 ──────────────────────────────────────────────────────
# (이름, s1_hidden_tuple, s2_hidden_tuple)
# Stage2가 Stage1보다 복잡한 함수를 근사 → 비대칭 설계 포함
CONFIGS = [
    # ── Nano / Tiny ──────────────────────────────────────────
    ("nano",          (4,),        (8,)),
    ("tiny",          (8,),        (16,)),
    ("tiny-asym",     (8,),        (32,)),
    ("tiny-deep",     (4, 4),      (8, 8)),
    # ── Small ───────────────────────────────────────────────
    ("small",         (16,),       (16, 8)),
    ("small-sym",     (16, 8),     (16, 8)),
    # ── Base (현재 배포 PINN) ────────────────────────────────
    ("base",          (16, 8),     (32, 16)),
    ("base-asym",     (8,),        (32, 16)),
    ("base-s2+",      (16, 8),     (64, 32)),
    # ── Medium ──────────────────────────────────────────────
    ("medium",        (32, 16),    (64, 32)),
    ("medium-deep",   (16, 8, 4),  (32, 16, 8)),
    ("medium-asym",   (16, 8),     (128, 64)),
    # ── Large ───────────────────────────────────────────────
    ("large",         (64, 32),    (128, 64)),
]


# ─── 유틸 ───────────────────────────────────────────────────────────────────
def make_net(in_dim: int, hidden: tuple, out_dim: int) -> nn.Sequential:
    layers, d = [], in_dim
    for h in hidden:
        layers += [nn.Linear(d, h), nn.Tanh()]
        d = h
    layers.append(nn.Linear(d, out_dim))
    return nn.Sequential(*layers)


def count_params(net: nn.Module) -> int:
    return sum(p.numel() for p in net.parameters())


def compute_macs(in_dim: int, hidden: tuple, out_dim: int) -> int:
    """MAC = multiply-accumulate, linear layer only."""
    dims = [in_dim] + list(hidden) + [out_dim]
    return sum(dims[i] * dims[i+1] for i in range(len(dims) - 1))


# ─── 데이터 로드 (한 번만) ────────────────────────────────────────────────────
def load_data():
    train = pd.read_csv(os.path.join(DATASET_DIR, 'train.csv'))
    val   = pd.read_csv(os.path.join(DATASET_DIR, 'val.csv'))
    test  = pd.read_csv(os.path.join(DATASET_DIR, 'test.csv'))

    sc_dR  = StandardScaler().fit(train[['dR_pct']].values)
    sc_dL  = StandardScaler().fit(train[['dL_pct']].values)
    sc_eps = StandardScaler().fit(train[['eps_act_pct']].values)
    sc_d   = StandardScaler().fit(train[['d_act_mm']].values)

    def prep(df):
        dR_n  = sc_dR.transform(df[['dR_pct']].values).astype(np.float32)
        dL_n  = sc_dL.transform(df[['dL_pct']].values).astype(np.float32)
        eps_n = sc_eps.transform(df[['eps_act_pct']].values).astype(np.float32)
        d_n   = sc_d.transform(df[['d_act_mm']].values).astype(np.float32)
        d_raw = df['d_act_mm'].values.astype(np.float32)
        return (torch.from_numpy(dR_n), torch.from_numpy(dL_n),
                torch.from_numpy(eps_n), torch.from_numpy(d_n), d_raw)

    return prep(train), prep(val), prep(test), sc_dR, sc_dL, sc_eps, sc_d


# ─── INT8 스케일 추정 ────────────────────────────────────────────────────────
def estimate_int8_scales(s1, s2, calib_dR, calib_dL, sc_dR, sc_dL, sc_eps, sc_d):
    """
    Calibration 데이터로 per-tensor 대칭 INT8 스케일 추정.
    scale = max|activation| / 127

    반환:
      s1_in_scale  : Stage1 입력 스케일 (normalized 단위)
      s1_out_scale : Stage1 출력 스케일 (normalized 단위)
      s2_in_scale  : Stage2 입력 스케일 (normalized 단위, 두 입력 중 max)
      s2_out_scale : Stage2 출력 스케일 (normalized 단위)
      dz_dR_pct    : dR 입력 dead-zone (% 물리 단위)
      step_eps_pct : ε 출력 1-step 크기 (% 물리 단위)
      s2_in_dL_scale: Stage2 dL 입력 스케일
      step_d_mm    : d 출력 1-step 크기 (mm 물리 단위)
    """
    s1.eval(); s2.eval()
    with torch.no_grad():
        eps_hat = s1(calib_dR)                               # Stage1 output
        X2      = torch.cat([calib_dL, eps_hat], dim=1)
        d_hat   = s2(X2)                                     # Stage2 output

    max_dR_n   = float(calib_dR.abs().max())
    max_dL_n   = float(calib_dL.abs().max())
    max_eps_n  = float(eps_hat.abs().max())
    max_eps2_n = float(eps_hat.abs().max())   # Stage2 eps 입력 = Stage1 출력
    max_d_n    = float(d_hat.abs().max())
    max_s2_in  = max(max_dL_n, max_eps2_n)   # per-tensor: 두 입력 공유 스케일

    s1_in_scale  = max_dR_n  / 127.0
    s1_out_scale = max_eps_n / 127.0
    s2_in_scale  = max_s2_in / 127.0
    s2_in_dL_scale = max_dL_n / 127.0
    s2_out_scale = max_d_n   / 127.0

    # 물리 단위 변환
    dz_dR_pct   = s1_in_scale  * float(sc_dR.scale_[0])   # dR dead-zone [%]
    step_eps_pct = s1_out_scale * float(sc_eps.scale_[0]) * 100.0  # ε step [%]
    step_d_mm   = s2_out_scale * float(sc_d.scale_[0])    # d step [mm]

    return {
        's1_in_scale':   round(s1_in_scale, 6),
        's1_out_scale':  round(s1_out_scale, 6),
        's2_in_scale':   round(s2_in_scale, 6),
        's2_out_scale':  round(s2_out_scale, 6),
        'dz_dR_pct':     round(dz_dR_pct,  4),
        'step_eps_pct':  round(step_eps_pct, 4),
        'step_d_mm':     round(step_d_mm,  4),
    }


# ─── 단일 아키텍처 학습 + 평가 ────────────────────────────────────────────────
def run_one(name, s1_hidden, s2_hidden,
            train_data, val_data, test_data,
            sc_dR, sc_dL, sc_eps, sc_d):

    torch.manual_seed(SEED)

    dR_tr, dL_tr, eps_tr, d_tr, _         = train_data
    dR_va, dL_va, eps_va, d_va, _         = val_data
    dR_te, dL_te, eps_te, d_te, d_te_raw  = test_data

    s1 = make_net(1, s1_hidden, 1)
    s2 = make_net(2, s2_hidden, 1)
    p1, p2   = count_params(s1), count_params(s2)
    mac1, mac2 = compute_macs(1, s1_hidden, 1), compute_macs(2, s2_hidden, 1)

    opt   = optim.AdamW(list(s1.parameters()) + list(s2.parameters()), lr=LR, weight_decay=WD)
    sched = CosineAnnealingLR(opt, T_max=EPOCHS, eta_min=1e-5)

    best_val_d  = float('inf')
    patience_cnt = 0
    best_state  = None
    n = len(dR_tr)
    t0 = time.time()

    for epoch in range(EPOCHS):
        s1.train(); s2.train()
        perm = torch.randperm(n)
        for start in range(0, n, BATCH):
            bi = perm[start:start + BATCH]
            eps_hat = s1(dR_tr[bi])
            d_hat   = s2(torch.cat([dL_tr[bi], eps_hat], dim=1))
            loss = (nn.functional.mse_loss(eps_hat, eps_tr[bi]) +
                    nn.functional.mse_loss(d_hat,   d_tr[bi]))
            opt.zero_grad(); loss.backward(); opt.step()
        sched.step()

        with torch.no_grad():
            s1.eval(); s2.eval()
            eps_va_hat = s1(dR_va)
            d_va_hat   = s2(torch.cat([dL_va, eps_va_hat], dim=1))

        d_va_phys = d_va_hat.numpy().ravel() * sc_d.scale_[0] + sc_d.mean_[0]
        d_va_true = d_va.numpy().ravel()     * sc_d.scale_[0] + sc_d.mean_[0]
        mae_val = float(np.mean(np.abs(d_va_phys - d_va_true)))

        if mae_val < best_val_d:
            best_val_d  = mae_val
            best_state  = ({k: v.clone() for k, v in s1.state_dict().items()},
                           {k: v.clone() for k, v in s2.state_dict().items()})
            patience_cnt = 0
        else:
            patience_cnt += 1
            if patience_cnt >= PATIENCE:
                break

    elapsed = time.time() - t0

    # ── 베스트 체크포인트 로드 & 테스트 평가 ───────────────────────────────────
    s1.load_state_dict(best_state[0]); s1.eval()
    s2.load_state_dict(best_state[1]); s2.eval()

    with torch.no_grad():
        eps_te_hat = s1(dR_te)
        d_te_hat   = s2(torch.cat([dL_te, eps_te_hat], dim=1))

    eps_pred = eps_te_hat.numpy().ravel() * sc_eps.scale_[0] + sc_eps.mean_[0]
    d_pred   = d_te_hat.numpy().ravel()   * sc_d.scale_[0]   + sc_d.mean_[0]
    eps_true = eps_te.numpy().ravel()     * sc_eps.scale_[0] + sc_eps.mean_[0]

    mae_eps = float(np.mean(np.abs(eps_pred - eps_true)))
    mae_d   = float(np.mean(np.abs(d_pred - d_te_raw)))
    m15 = d_te_raw <= 15;  m10 = d_te_raw <= 10
    mae_d15 = float(np.mean(np.abs(d_pred[m15] - d_te_raw[m15]))) if m15.any() else None
    mae_d10 = float(np.mean(np.abs(d_pred[m10] - d_te_raw[m10]))) if m10.any() else None

    # ── INT8 스케일 추정 (train 전체를 calibration으로) ──────────────────────
    calib_dR = torch.cat([dR_tr, dR_va], dim=0)
    calib_dL = torch.cat([dL_tr, dL_va], dim=0)
    int8 = estimate_int8_scales(s1, s2, calib_dR, calib_dL, sc_dR, sc_dL, sc_eps, sc_d)

    return {
        'name':        name,
        's1_hidden':   list(s1_hidden),
        's2_hidden':   list(s2_hidden),
        'params_s1':   p1,
        'params_s2':   p2,
        'params':      p1 + p2,
        'macs_s1':     mac1,
        'macs_s2':     mac2,
        'macs':        mac1 + mac2,
        'mae_eps':     round(mae_eps, 4),
        'mae_d':       round(mae_d,   4),
        'mae_d15':     round(mae_d15, 4) if mae_d15 is not None else None,
        'mae_d10':     round(mae_d10, 4) if mae_d10 is not None else None,
        'best_val_d':  round(best_val_d, 4),
        'train_sec':   round(elapsed, 1),
        'int8':        int8,
    }


# ─── Pareto 그래프 생성 ──────────────────────────────────────────────────────
def save_pareto_plot(results, out_path):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    params = [r['params'] for r in results]
    mae_d  = [r['mae_d']  for r in results]
    mae_eps = [r['mae_eps'] for r in results]
    names  = [r['name']   for r in results]

    # Pareto frontier (d MAE)
    sorted_idx = sorted(range(len(params)), key=lambda i: params[i])
    pareto_params, pareto_d = [], []
    best_d = float('inf')
    for i in sorted_idx:
        if mae_d[i] < best_d:
            best_d = mae_d[i]
            pareto_params.append(params[i])
            pareto_d.append(mae_d[i])

    ax = axes[0]
    ax.scatter(params, mae_d, s=60, color='#1F77B4', zorder=3)
    ax.plot(pareto_params, pareto_d, 'r--o', lw=1.5, ms=5, label='Pareto frontier', zorder=4)

    # 현재 base 강조
    for r in results:
        offset = (8, 4)
        if r['name'] == 'base':
            ax.scatter(r['params'], r['mae_d'], s=120, color='#FF8C00',
                       edgecolors='black', linewidths=1.5, zorder=5)
            offset = (8, -12)
        ax.annotate(r['name'], (r['params'], r['mae_d']),
                    textcoords='offset points', xytext=offset,
                    fontsize=7.5, color='#333')

    ax.set_xscale('log')
    ax.set_xlabel('Total Parameters (log scale)', fontsize=10)
    ax.set_ylabel('Proximity MAE [mm]', fontsize=10)
    ax.set_title('Architecture Search: Params vs d MAE\n(Pareto frontier = red dashed)',
                 fontweight='bold')
    ax.legend(fontsize=9); ax.grid(True, alpha=0.3)
    ax.axhline(1.80, color='gray', ls=':', lw=1, label='base baseline')

    # MACs vs d MAE
    macs = [r['macs'] for r in results]
    ax2 = axes[1]
    sc = ax2.scatter(macs, mae_d, c=params, cmap='viridis', s=60,
                     norm=plt.matplotlib.colors.LogNorm(), zorder=3)
    plt.colorbar(sc, ax=ax2, label='Total Parameters')
    for r in results:
        ax2.annotate(r['name'], (r['macs'], r['mae_d']),
                     textcoords='offset points', xytext=(5, 3), fontsize=7.5, color='#333')
    ax2.set_xlabel('Total MACs (multiply-accumulate)', fontsize=10)
    ax2.set_ylabel('Proximity MAE [mm]', fontsize=10)
    ax2.set_title('Architecture Search: MACs vs d MAE\n(color = param count)',
                  fontweight='bold')
    ax2.grid(True, alpha=0.3)

    plt.suptitle('2-Stage MLP Architecture Search Results', fontsize=12, fontweight='bold')
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Pareto 그래프 저장: {out_path}')


# ─── 메인 ────────────────────────────────────────────────────────────────────
def main():
    print('데이터 로드 중...')
    train_data, val_data, test_data, sc_dR, sc_dL, sc_eps, sc_d = load_data()
    print(f'  train={len(train_data[0]):,}  val={len(val_data[0]):,}  test={len(test_data[0]):,}')

    results = []
    total = len(CONFIGS)
    for i, (name, s1_h, s2_h) in enumerate(CONFIGS):
        # 파라미터 수 미리 계산 (표시용)
        _s1 = make_net(1, s1_h, 1)
        _s2 = make_net(2, s2_h, 1)
        est_p = count_params(_s1) + count_params(_s2)
        del _s1, _s2

        print(f'[{i+1:2d}/{total}] {name:<20s}  s1={str(s1_h):<12s} s2={str(s2_h):<16s}  ~{est_p}p', end='  ')
        sys.stdout.flush()

        r = run_one(name, s1_h, s2_h,
                    train_data, val_data, test_data,
                    sc_dR, sc_dL, sc_eps, sc_d)
        results.append(r)
        print(f'eps={r["mae_eps"]:.4f}%  d={r["mae_d"]:.4f}mm  '
              f'd≤15={r["mae_d15"]:.4f}mm  dz={r["int8"]["dz_dR_pct"]:.4f}%  ({r["train_sec"]:.0f}s)')

    # ── 저장 ───────────────────────────────────────────────────────────────
    out_json = os.path.join(CKPT_DIR, 'arch_search_results.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f'\n결과 저장: {out_json}')

    out_png = os.path.join(DATASET_DIR, 'arch_search_pareto.png')
    save_pareto_plot(results, out_png)

    # ── 요약 출력 ──────────────────────────────────────────────────────────
    print('\n=== 결과 요약 (params 오름차순) ===')
    print(f'{"이름":<18} {"params":>6} {"MACs":>6} {"ε MAE":>7} {"d MAE":>7} '
          f'{"d≤15":>6} {"d≤10":>6} {"dz_dR":>7} {"step_ε":>7} {"step_d":>7}')
    print('-' * 100)
    for r in sorted(results, key=lambda x: x['params']):
        i8 = r['int8']
        d15 = f"{r['mae_d15']:.4f}" if r['mae_d15'] else ' N/A '
        d10 = f"{r['mae_d10']:.4f}" if r['mae_d10'] else ' N/A '
        mark = ' ← 현재' if r['name'] == 'base' else ''
        print(f"{r['name']:<18} {r['params']:>6d} {r['macs']:>6d} "
              f"{r['mae_eps']:>7.4f} {r['mae_d']:>7.4f} "
              f"{d15:>6} {d10:>6} "
              f"{i8['dz_dR_pct']:>7.4f} {i8['step_eps_pct']:>7.4f} {i8['step_d_mm']:>7.4f}"
              f"{mark}")

    best = min(results, key=lambda x: x['mae_d'])
    print(f'\n최고 d MAE: {best["name"]} ({best["params"]}p) → {best["mae_d"]:.4f}mm')

    # Pareto: 가장 작은 params로 d MAE ≤ 1.85mm 달성
    threshold = 1.85
    pareto_cands = [r for r in results if r['mae_d'] <= threshold]
    if pareto_cands:
        rec = min(pareto_cands, key=lambda x: x['params'])
        print(f'추천 (d≤{threshold}mm 조건의 최소 params): {rec["name"]} ({rec["params"]}p) → {rec["mae_d"]:.4f}mm')


if __name__ == '__main__':
    main()
