"""
train_pinn_csv.py — PyTorch PINN 재학습 (새 CSV 데이터셋)

data_pipeline.py (0332 구형 데이터) 대신 data_acquisition/dataset/train.csv 사용.
train.py 의 학습 루프·모델을 그대로 재사용.

Usage:
    C:/ml_env/Scripts/python nn_decoupling/train_pinn_csv.py
    C:/ml_env/Scripts/python nn_decoupling/train_pinn_csv.py --epochs 300 --patience 40
"""
import os, sys, argparse, pickle, json
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.preprocessing import StandardScaler

# ─── 경로 설정 ─────────────────────────────────────────────────────────────────
HERE        = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(HERE, 'data_acquisition', 'dataset')
CKPT_DIR    = os.path.join(HERE, 'checkpoints')
os.makedirs(CKPT_DIR, exist_ok=True)

# model.py 가 같은 디렉터리에 있으므로 sys.path 추가
sys.path.insert(0, HERE)
from model import TwoStageDecoupler, PhysicsLoss

# train.py 의 헬퍼 함수들 재사용
from train import (lambda_schedule, to_physical, to_physical_inputs,
                   train_epoch, evaluate)


# ─── CSV 데이터셋 ──────────────────────────────────────────────────────────────

class CsvSensorDataset(Dataset):
    """
    data_acquisition/dataset/{train,val,test}.csv 를 로드하는 Dataset.

    컬럼: eps_act_pct, d_act_mm, dL_pct, dR_pct
      X = [dL_pct, dR_pct]          (입력: 인덕턴스/저항 변화율 %)
      Y = [eps_ratio, d_act_mm]     (출력: 변형률 비율(0..0.3), 근접거리 mm)

    eps_act_pct → eps_ratio = eps_act_pct / 100  ← train.py 의 evaluate() × 100 과 대응
    """
    def __init__(self, df: pd.DataFrame,
                 scaler_x: StandardScaler,
                 scaler_y: StandardScaler,
                 fit: bool = False):
        X_raw = df[['dL_pct', 'dR_pct']].values.astype(np.float32)
        Y_raw = np.column_stack([
            df['eps_act_pct'].values / 100.0,   # % → ratio
            df['d_act_mm'].values,
        ]).astype(np.float32)

        if fit:
            scaler_x.fit(X_raw)
            scaler_y.fit(Y_raw)

        self.X = torch.from_numpy(scaler_x.transform(X_raw))
        self.Y = torch.from_numpy(scaler_y.transform(Y_raw))

    def __len__(self):  return len(self.X)
    def __getitem__(self, i): return self.X[i], self.Y[i]


def build_csv_loaders(batch_size: int = 256):
    train_df = pd.read_csv(os.path.join(DATASET_DIR, 'train.csv'))
    val_df   = pd.read_csv(os.path.join(DATASET_DIR, 'val.csv'))
    test_df  = pd.read_csv(os.path.join(DATASET_DIR, 'test.csv'))

    scaler_x = StandardScaler()
    scaler_y = StandardScaler()

    train_ds = CsvSensorDataset(train_df, scaler_x, scaler_y, fit=True)
    val_ds   = CsvSensorDataset(val_df,   scaler_x, scaler_y, fit=False)
    test_ds  = CsvSensorDataset(test_df,  scaler_x, scaler_y, fit=False)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  drop_last=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False)
    test_loader  = DataLoader(test_ds,  batch_size=batch_size, shuffle=False)

    print(f"  Train: {len(train_ds):,}  Val: {len(val_ds):,}  Test: {len(test_ds):,}")
    return train_loader, val_loader, test_loader, scaler_x, scaler_y


# ─── d≤15mm / d≤10mm 세분화 MAE ───────────────────────────────────────────────

@torch.no_grad()
def evaluate_detail(model, loader, scaler_y, device):
    """전체/d≤15/d≤10 세 구간별 MAE 반환."""
    model.eval()
    eps_err_all, d_err_all, d_true_all = [], [], []

    for X_b, Y_b in loader:
        Y_pred = model(X_b.to(device)).cpu()
        Y_pred_phys = torch.from_numpy(
            scaler_y.inverse_transform(Y_pred.numpy()).astype(np.float32))
        Y_true_phys = torch.from_numpy(
            scaler_y.inverse_transform(Y_b.numpy()).astype(np.float32))

        eps_err_all.append((Y_pred_phys[:, 0] - Y_true_phys[:, 0]).abs())
        d_err_all.append(  (Y_pred_phys[:, 1] - Y_true_phys[:, 1]).abs())
        d_true_all.append(Y_true_phys[:, 1])

    eps_err = torch.cat(eps_err_all)
    d_err   = torch.cat(d_err_all)
    d_true  = torch.cat(d_true_all)

    mae_eps  = eps_err.mean().item() * 100       # → %
    mae_d    = d_err.mean().item()               # mm
    mae_d15  = d_err[d_true <= 15].mean().item() if (d_true <= 15).any() else float('nan')
    mae_d10  = d_err[d_true <= 10].mean().item() if (d_true <= 10).any() else float('nan')
    return mae_eps, mae_d, mae_d15, mae_d10


# ─── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--epochs',       type=int,   default=300)
    p.add_argument('--batch_size',   type=int,   default=256)
    p.add_argument('--lr',           type=float, default=1e-3)
    p.add_argument('--weight_decay', type=float, default=1e-4)
    p.add_argument('--lam_final',    type=float, default=0.10)
    p.add_argument('--lam_warmup',   type=int,   default=50)
    p.add_argument('--patience',     type=int,   default=40)
    return p.parse_args()


def main():
    args   = parse_args()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")

    # 데이터 로드
    print("▶ 데이터 로드...")
    (train_loader, val_loader, test_loader,
     scaler_x, scaler_y) = build_csv_loaders(args.batch_size)

    # 모델 초기화
    model   = TwoStageDecoupler().to(device)
    phys_fn = PhysicsLoss().to(device)
    n_net   = model.param_count()
    n_phys  = sum(p.numel() for p in phys_fn.parameters())
    print(f"▶ 모델: TwoStageDecoupler {n_net}p + PhysicsLoss {n_phys}p")

    all_params = list(model.parameters()) + list(phys_fn.parameters())
    optimizer  = optim.AdamW(all_params, lr=args.lr, weight_decay=args.weight_decay)
    scheduler  = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)

    best_mae_d     = float('inf')
    patience_count = 0
    best_path      = os.path.join(CKPT_DIR, 'best_pinn_csv.pt')
    history        = []

    print("▶ 학습 시작...")
    for epoch in range(1, args.epochs + 1):
        lam = lambda_schedule(epoch, args.lam_warmup, args.epochs, 0.0, args.lam_final)
        l_data, l_phys = train_epoch(model, phys_fn, train_loader, optimizer,
                                     lam, scaler_x, scaler_y, device)
        mae_eps, mae_d = evaluate(model, val_loader, scaler_y, device)
        scheduler.step()

        history.append({'epoch': epoch, 'val_mae_eps': mae_eps, 'val_mae_d': mae_d,
                        'l_data': l_data, 'l_phys': l_phys})

        if epoch % 10 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d}/{args.epochs}  lam={lam:.3f}  "
                  f"L_data={l_data:.5f} L_phys={l_phys:.5f}  "
                  f"Val eps={mae_eps:.3f}%  d={mae_d:.2f}mm")

        if mae_d < best_mae_d:
            best_mae_d = mae_d
            torch.save({'epoch': epoch, 'model_state': model.state_dict(),
                        'phys_state': phys_fn.state_dict()}, best_path)
            patience_count = 0
        else:
            patience_count += 1
            if patience_count >= args.patience:
                print(f"  Early stop at epoch {epoch}  (best val d={best_mae_d:.2f}mm)")
                break

    # 테스트 평가
    ckpt = torch.load(best_path, map_location=device)
    model.load_state_dict(ckpt['model_state'])
    phys_fn.load_state_dict(ckpt['phys_state'])

    mae_eps_t, mae_d_t, mae_d15_t, mae_d10_t = evaluate_detail(model, test_loader, scaler_y, device)
    best_epoch = ckpt['epoch']
    print(f"\n▶ Test 결과 (epoch {best_epoch}):")
    print(f"   ε MAE  = {mae_eps_t:.4f} %")
    print(f"   d MAE  = {mae_d_t:.4f} mm  (d≤15: {mae_d15_t:.4f}  d≤10: {mae_d10_t:.4f})")

    # 학습된 물리 파라미터
    print("\n▶ 학습된 물리 파라미터:")
    print(f"   α₁={phys_fn.alpha1.item():.4f}  α₂={phys_fn.alpha2.item():.4f}")
    print(f"   β₁={phys_fn.beta1.item():.4f}   β₂={phys_fn.beta2.item():.4f}")
    print(f"   b3={phys_fn.beta3.item():.4f}   d0={phys_fn.d0.item():.4f}mm  k={phys_fn.k.item():.4f}")

    # 결과 JSON 저장
    results = {
        'model':       'TwoStageDecoupler (PyTorch PINN)',
        'params_net':  n_net,
        'params_phys': n_phys,
        'dataset':     'data_acquisition/dataset/train+val+test.csv',
        'best_epoch':  best_epoch,
        'val_mae_d_best': best_mae_d,
        'test_mae_eps':  round(mae_eps_t, 4),
        'test_mae_d':    round(mae_d_t,   4),
        'test_mae_d15':  round(mae_d15_t, 4),
        'test_mae_d10':  round(mae_d10_t, 4),
        'train_epochs':  len(history),
        'physics': {
            'alpha1': round(phys_fn.alpha1.item(), 4),
            'alpha2': round(phys_fn.alpha2.item(), 4),
            'beta1':  round(phys_fn.beta1.item(),  4),
            'beta2':  round(phys_fn.beta2.item(),  4),
            'beta3':  round(phys_fn.beta3.item(),  4),
            'd0':     round(phys_fn.d0.item(),     4),
            'k':      round(phys_fn.k.item(),      4),
        }
    }
    json_path = os.path.join(CKPT_DIR, 'pinn_csv_results.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n▶ 결과 저장: {json_path}")

    # scaler 저장 (향후 추론용)
    sc_path = os.path.join(CKPT_DIR, 'scalers_pinn_csv.pkl')
    with open(sc_path, 'wb') as f:
        pickle.dump({'scaler_x': scaler_x, 'scaler_y': scaler_y}, f)
    print(f"▶ Scaler 저장: {sc_path}")


if __name__ == '__main__':
    main()
