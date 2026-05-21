"""
PINN 없이 Two-Stage 훈련, 결과를 training_history.json에 추가.
"""
import os, json, sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_pipeline import build_dataloaders
from model import TwoStageDecoupler, PhysicsLoss
from train import train_epoch, evaluate, lambda_schedule

CHECKPOINT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'checkpoints')
HIST_PATH      = os.path.join(CHECKPOINT_DIR, 'training_history.json')

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device} | No-PINN Two-Stage training")

    (train_loader, val_loader, test_loader,
     in_sc, out_sc, _, _, _, _) = build_dataloaders(batch_size=256)

    model   = TwoStageDecoupler().to(device)
    phys_fn = PhysicsLoss().to(device)           # 가중치 0이라도 파라미터 필요
    all_params = list(model.parameters()) + list(phys_fn.parameters())
    optimizer  = optim.AdamW(all_params, lr=1e-3, weight_decay=1e-4)
    scheduler  = CosineAnnealingLR(optimizer, T_max=300, eta_min=1e-5)

    epochs, patience = 300, 30
    best_mae_d, patience_count = float('inf'), 0
    best_path = os.path.join(CHECKPOINT_DIR, 'best_model_nopinn.pt')

    hist = dict(epoch=[], loss_data=[], val_mae_eps=[], val_mae_d=[], lr=[])

    for ep in range(1, epochs + 1):
        l_data, _ = train_epoch(model, phys_fn, train_loader, optimizer,
                                lam=0.0, in_sc=in_sc, out_sc=out_sc, device=device)
        mae_eps, mae_d = evaluate(model, val_loader, out_sc, device)
        scheduler.step()

        hist['epoch'].append(ep)
        hist['loss_data'].append(l_data)
        hist['val_mae_eps'].append(mae_eps)
        hist['val_mae_d'].append(mae_d)
        hist['lr'].append(optimizer.param_groups[0]['lr'])

        if ep % 10 == 0 or ep == 1:
            print(f"Epoch {ep:3d}/{epochs}  "
                  f"L_data={l_data:.5f}  Val MAE: eps={mae_eps:.3f}%  d={mae_d:.2f}mm")

        if mae_d < best_mae_d:
            best_mae_d = mae_d
            torch.save({'epoch': ep, 'model_state': model.state_dict()}, best_path)
            patience_count = 0
        else:
            patience_count += 1
            if patience_count >= patience:
                print(f"Early stopping at epoch {ep}  (best val MAE d = {best_mae_d:.2f}mm)")
                break

    ckpt = torch.load(best_path, map_location=device)
    model.load_state_dict(ckpt['model_state'])
    test_eps, test_d = evaluate(model, test_loader, out_sc, device)
    print(f"\nTest MAE: eps={test_eps:.3f}%  d={test_d:.2f}mm  (best epoch: {ckpt['epoch']})")

    # training_history.json 업데이트
    with open(HIST_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data['hist_nopinn'] = hist
    data['test_nopinn'] = {
        'eps': test_eps, 'd': test_d, 'best_epoch': int(ckpt['epoch'])
    }

    with open(HIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f)

    print(f"Saved to {HIST_PATH}")


if __name__ == '__main__':
    main()
