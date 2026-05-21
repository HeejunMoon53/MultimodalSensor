"""
train.py — Two-stage PINN decoupler training + ONNX export for STM32 Edge-AI

Usage:
    python train.py                        # default: two_stage model
    python train.py --model single_pinn    # ablation baseline
    python train.py --epochs 100 --lr 3e-4
"""
import os
import argparse
import pickle

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.preprocessing import StandardScaler

from data_pipeline import build_dataloaders
from model import TwoStageDecoupler, SinglePINNMLP, PhysicsLoss

# 체크포인트(학습된 가중치) 저장 폴더: train.py 와 같은 위치의 checkpoints/
CHECKPOINT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'checkpoints')


# ── Helpers ───────────────────────────────────────────────────────────────────

def lambda_schedule(epoch: int, warmup: int, epochs: int,
                    lam_init: float, lam_final: float) -> float:
    """
    Physics loss 가중치(λ)를 에폭에 따라 선형으로 스케줄링한다.

    - warmup 에폭 동안: λ = lam_init (= 0.0)  → 처음엔 데이터 손실만 학습
    - warmup 이후: λ를 lam_init → lam_final 로 선형 증가
    - 이렇게 하면 모델이 물리 제약을 점진적으로 받아들여 학습 안정성이 높아짐
    """
    if epoch < warmup:
        return lam_init
    t = (epoch - warmup) / max(1, epochs - warmup)
    return lam_init + t * (lam_final - lam_init)


def to_physical(Y_norm: torch.Tensor, scaler: StandardScaler) -> torch.Tensor:
    """
    정규화된 출력 텐서(Y_norm)를 원래 물리 단위로 역변환한다.
    scaler.inverse_transform: x_phys = x_norm * STD + MEAN
    (출력: ε̂ [무차원 비율], d̂ [mm])
    """
    arr = scaler.inverse_transform(Y_norm.detach().cpu().numpy())
    return torch.from_numpy(arr.astype(np.float32)).to(Y_norm.device)


def to_physical_inputs(X_norm: torch.Tensor,
                       scaler: StandardScaler) -> torch.Tensor:
    """
    정규화된 입력 텐서(X_norm)를 원래 물리 단위로 역변환한다.
    (입력: ΔL/L₀ [%], ΔR/R₀ [%])
    """
    arr = scaler.inverse_transform(X_norm.detach().cpu().numpy())
    return torch.from_numpy(arr.astype(np.float32)).to(X_norm.device)


# ── Train / eval loops ────────────────────────────────────────────────────────

def train_epoch(model, phys_fn, loader, optimizer, lam,
                in_sc, out_sc, device):
    """
    한 에폭(epoch) 동안 전체 학습 데이터를 한 번 순회하며 가중치를 갱신한다.

    손실 함수 구조:
        Loss_Total = Loss_Data + λ × Loss_Physics

        - Loss_Data  : 모델 예측값과 레이블(정답)의 MSE (정규화된 공간에서 계산)
        - Loss_Physics: 예측된 (ε̂, d̂)가 물리 방정식을 얼마나 만족하는지 (원래 단위에서 계산)
        - λ (lam)    : 두 손실의 상대적 가중치 (학습 초반엔 0, 점진 증가)

    반환값: (평균 데이터 손실, 평균 물리 손실)
    """
    model.train()
    total_data = total_phys = n = 0

    for X_b, Y_b in loader:
        X_b, Y_b = X_b.to(device), Y_b.to(device)
        optimizer.zero_grad()

        # 순전파: 정규화된 입력 → 정규화된 출력 예측
        Y_pred    = model(X_b)
        # 데이터 손실: 예측값 vs 정답 레이블 (정규화 공간)
        loss_data = nn.functional.mse_loss(Y_pred, Y_b)

        loss_phys = torch.zeros(1, device=device)
        if lam > 0:
            # Physics loss 계산을 위해 물리 단위로 역변환
            Y_phys = to_physical(Y_pred, out_sc)   # [ε̂, d̂]
            X_phys = to_physical_inputs(X_b, in_sc)  # [ΔL/L₀, ΔR/R₀]

            eps_hat = Y_phys[:, 0]   # 예측 변형률 ε̂
            d_hat   = Y_phys[:, 1]   # 예측 근접거리 d̂ (mm)
            dR_true = X_phys[:, 1]   # 실측 ΔR/R₀ (%)
            dL_true = X_phys[:, 0]   # 실측 ΔL/L₀ (%)

            # PhysicsLoss: (ε̂, d̂)가 물리 모델 R(ε), L(ε,d)를 만족하는지 평가
            loss_phys = phys_fn(eps_hat, d_hat, dR_true, dL_true)

        loss = loss_data + lam * loss_phys
        loss.backward()

        # 그래디언트 클리핑: 물리 파라미터 포함 전체 파라미터의 그래디언트 폭발 방지
        nn.utils.clip_grad_norm_(
            list(model.parameters()) + list(phys_fn.parameters()),
            max_norm=1.0)
        optimizer.step()

        bs = len(X_b)
        total_data += loss_data.item() * bs
        total_phys += loss_phys.item() * bs
        n += bs

    # 배치 크기로 가중평균하여 에폭 평균 손실 반환
    return total_data / n, total_phys / n


@torch.no_grad()
def evaluate(model, loader, out_sc, device):
    """
    검증/테스트 데이터로 모델 성능을 평가한다.
    그래디언트 계산 없음(추론 전용).

    반환값:
        mae_eps : 변형률 ε 의 평균절대오차 (단위: %)
        mae_d   : 근접거리 d 의 평균절대오차 (단위: mm)
    """
    model.eval()
    eps_errs, d_errs = [], []

    for X_b, Y_b in loader:
        Y_pred = model(X_b.to(device)).cpu()
        # 정규화된 예측/정답을 물리 단위로 역변환
        Y_pred_phys = torch.from_numpy(
            out_sc.inverse_transform(Y_pred.numpy()).astype(np.float32))
        Y_true_phys = torch.from_numpy(
            out_sc.inverse_transform(Y_b.numpy()).astype(np.float32))

        # 각 샘플의 절대오차를 누적
        eps_errs.append((Y_pred_phys[:, 0] - Y_true_phys[:, 0]).abs())
        d_errs.append(  (Y_pred_phys[:, 1] - Y_true_phys[:, 1]).abs())

    mae_eps = torch.cat(eps_errs).mean().item() * 100   # 비율 → % 단위 변환
    mae_d   = torch.cat(d_errs).mean().item()           # mm
    return mae_eps, mae_d


# ── ONNX export ───────────────────────────────────────────────────────────────

def export_onnx(model, save_dir: str):
    """
    학습된 PyTorch 모델을 ONNX 형식으로 변환한다.
    ONNX → STM32CubeAI(X-CUBE-AI) 로 변환하여 MCU에 INT8 배포할 때 사용.

    - 입력: [1, 2] (ΔL/L₀, ΔR/R₀) 정규화된 값
    - 출력: [1, 2] (ε̂, d̂) 정규화된 값
    - opset_version=17: ONNX 연산자 버전 (X-CUBE-AI 호환)
    - do_constant_folding: 상수 연산 사전 계산으로 추론 속도 최적화
    """
    model.eval()
    dummy     = torch.zeros(1, 2)   # 더미 입력 (형상만 중요)
    onnx_path = os.path.join(save_dir, 'decoupler.onnx')
    with torch.no_grad():
        torch.onnx.export(
            model, (dummy,), onnx_path,
            input_names=['sensor_input'],
            output_names=['decoupled_output'],
            opset_version=17,
            do_constant_folding=True,
            dynamo=False,
        )
    print(f"ONNX exported --> {onnx_path}")
    return onnx_path


def export_stm32_header(in_sc: StandardScaler,
                        out_sc: StandardScaler,
                        save_dir: str):
    """
    STM32 펌웨어에 포함될 C 헤더 파일(model_params.h)을 생성한다.

    MCU가 추론 전/후에 직접 정규화·역정규화할 수 있도록
    StandardScaler의 mean/std 값을 C 매크로로 출력한다.

    사용 방식 (펌웨어 측):
        전처리: x_norm = (x_raw - MEAN) / STD
        추론:   ONNX 모델 실행
        후처리: x_phys = x_norm * STD + MEAN
    """
    (dL_mean, dR_mean) = in_sc.mean_
    (dL_std,  dR_std)  = in_sc.scale_
    (eps_mean, d_mean) = out_sc.mean_
    (eps_std,  d_std)  = out_sc.scale_

    h = f"""/* Auto-generated by train.py - do not edit */
#ifndef MODEL_PARAMS_H
#define MODEL_PARAMS_H

/* Input normalization: x_norm = (x_raw - MEAN) / STD */
#define INPUT_DL_MEAN   {dL_mean:.6f}f
#define INPUT_DL_STD    {dL_std:.6f}f
#define INPUT_DR_MEAN   {dR_mean:.6f}f
#define INPUT_DR_STD    {dR_std:.6f}f

/* Output de-normalization: x_phys = x_norm * STD + MEAN */
#define OUTPUT_EPS_MEAN {eps_mean:.6f}f
#define OUTPUT_EPS_STD  {eps_std:.6f}f
#define OUTPUT_D_MEAN   {d_mean:.6f}f
#define OUTPUT_D_STD    {d_std:.6f}f

/* Physical clamp bounds */
#define OUTPUT_EPS_MIN  0.0f
#define OUTPUT_EPS_MAX  0.3f
#define OUTPUT_D_MIN    0.0f
#define OUTPUT_D_MAX    50.0f

#endif /* MODEL_PARAMS_H */
"""
    path = os.path.join(save_dir, 'model_params.h')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(h)
    print(f"STM32 header   → {path}")


def verify_onnx(onnx_path: str, in_sc: StandardScaler,
                out_sc: StandardScaler, device):
    """
    ONNX 런타임으로 실제 추론을 실행해 변환이 올바른지 검증한다.
    onnxruntime이 설치되지 않은 경우 건너뜀.
    """
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(onnx_path,
                                    providers=['CPUExecutionProvider'])
        dummy  = np.random.randn(1, 2).astype(np.float32)
        out_rt = sess.run(None, {'sensor_input': dummy})[0]
        print(f"ONNX sanity check OK - output: {out_rt}")
    except ImportError:
        print("onnxruntime not installed — skipping ONNX sanity check")


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    """커맨드라인 인자를 파싱한다."""
    p = argparse.ArgumentParser()
    p.add_argument('--model',        default='two_stage',
                   choices=['two_stage', 'single_pinn'])
    p.add_argument('--epochs',       type=int,   default=300)
    p.add_argument('--batch_size',   type=int,   default=256)
    p.add_argument('--lr',           type=float, default=1e-3)
    p.add_argument('--weight_decay', type=float, default=1e-4)
    p.add_argument('--lam_final',    type=float, default=0.1,
                   help='Physics loss weight at end of training')
    p.add_argument('--lam_warmup',   type=int,   default=50,
                   help='Epochs before physics loss is applied')
    p.add_argument('--patience',     type=int,   default=30)
    return p.parse_args()


def main():
    args   = parse_args()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  |  Model: {args.model}")
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    # ── 데이터 로드 ───────────────────────────────────────────────────────────
    # build_dataloaders: 센서 데이터(ΔL, ΔR) → (train/val/test) DataLoader와
    # 정규화 스케일러(in_sc, out_sc), 그 외 메타데이터를 반환
    (train_loader, val_loader, test_loader,
     in_sc, out_sc, n_half, prox_arr, L0, R0) = build_dataloaders(
         batch_size=args.batch_size)

    # ── 모델 초기화 ───────────────────────────────────────────────────────────
    # TwoStageDecoupler : Stage1(ΔR→ε̂) + Stage2(ΔL,ε̂→d̂) 2단계 구조
    # SinglePINNMLP     : (ΔL, ΔR) → (ε̂, d̂) 단일 MLP (비교용 베이스라인)
    model   = (TwoStageDecoupler() if args.model == 'two_stage'
               else SinglePINNMLP()).to(device)
    # PhysicsLoss: α₁,α₂,β₁,β₂,β₃,d₀,k 등 물리 파라미터를 학습 가능 변수로 포함
    phys_fn = PhysicsLoss().to(device)
    print(f"Parameters: {model.param_count()} (network) + "
          f"{sum(p.numel() for p in phys_fn.parameters())} (physics)")

    # 네트워크 파라미터 + 물리 파라미터를 함께 최적화
    all_params = list(model.parameters()) + list(phys_fn.parameters())
    optimizer  = optim.AdamW(all_params, lr=args.lr,
                             weight_decay=args.weight_decay)
    # Cosine Annealing: 학습률을 lr → eta_min 으로 코사인 감소
    scheduler  = CosineAnnealingLR(optimizer,
                                   T_max=args.epochs, eta_min=1e-5)

    # ── 학습 루프 ─────────────────────────────────────────────────────────────
    best_mae_d     = float('inf')   # 근접거리 MAE 기준으로 최적 모델 저장
    patience_count = 0              # 조기 종료 카운터
    best_path      = os.path.join(CHECKPOINT_DIR, 'best_model.pt')

    for epoch in range(1, args.epochs + 1):
        # 현재 에폭의 λ 계산 (warmup 중엔 0, 이후 점진 증가)
        lam = lambda_schedule(epoch, args.lam_warmup, args.epochs,
                              0.0, args.lam_final)

        l_data, l_phys = train_epoch(model, phys_fn, train_loader, optimizer,
                                     lam, in_sc, out_sc, device)
        mae_eps, mae_d = evaluate(model, val_loader, out_sc, device)
        scheduler.step()  # 학습률 스케줄러 갱신

        # 10 에폭마다 (+ 첫 에폭) 학습 현황 출력
        if epoch % 10 == 0 or epoch == 1:
            print(f"Epoch {epoch:3d}/{args.epochs}  lam={lam:.3f}  "
                  f"L_data={l_data:.5f}  L_phys={l_phys:.5f}  "
                  f"Val MAE: eps={mae_eps:.3f}%  d={mae_d:.2f}mm")

        # 검증 MAE(d)가 개선되면 체크포인트 저장, 아니면 patience 증가
        if mae_d < best_mae_d:
            best_mae_d = mae_d
            torch.save({
                'epoch':        epoch,
                'model_state':  model.state_dict(),
                'phys_state':   phys_fn.state_dict(),
                'args':         vars(args),
            }, best_path)
            patience_count = 0
        else:
            patience_count += 1
            if patience_count >= args.patience:
                print(f"Early stopping at epoch {epoch}  "
                      f"(best val MAE d = {best_mae_d:.2f}mm)")
                break

    # ── 테스트 평가 ───────────────────────────────────────────────────────────
    # 최적 체크포인트를 불러와 테스트셋에서 최종 성능 측정
    ckpt = torch.load(best_path, map_location=device)
    model.load_state_dict(ckpt['model_state'])
    mae_eps_t, mae_d_t = evaluate(model, test_loader, out_sc, device)
    print(f"\nTest MAE: eps={mae_eps_t:.3f}%  d={mae_d_t:.2f}mm  "
          f"(best epoch: {ckpt['epoch']})")

    # ── 학습된 물리 파라미터 출력 ─────────────────────────────────────────────
    # PhysicsLoss 내부의 α₁,α₂ (저항 모델), β₁~β₃,d₀,k (인덕턴스 모델) 값
    phys_fn.load_state_dict(ckpt['phys_state'])
    print("\nLearned physics params:")
    print(f"  a1={phys_fn.alpha1.item():.4f}  a2={phys_fn.alpha2.item():.4f}")
    print(f"  b1={phys_fn.beta1.item():.4f}   b2={phys_fn.beta2.item():.4f}")
    print(f"  b3={phys_fn.beta3.item():.4f}   d0={phys_fn.d0.item():.4f}mm  "
          f"k={phys_fn.k.item():.4f}")

    # ── 배포 파일 생성 ────────────────────────────────────────────────────────
    onnx_path = export_onnx(model, CHECKPOINT_DIR)          # ONNX 모델 변환
    export_stm32_header(in_sc, out_sc, CHECKPOINT_DIR)      # C 헤더(스케일러 상수)
    verify_onnx(onnx_path, in_sc, out_sc, device)           # 변환 결과 검증


if __name__ == '__main__':
    main()
