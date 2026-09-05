"""
candidate5b_true_rnn.py
후보 5의 "진짜" 버전 — 손으로 고른 다중 시간상수 EMA 뱅크 대신, 작은 GRU(순환신경망) 하나가
이력(메모리)을 직접 학습하도록 한다. 이전 환경에서는 torch가 DLL 로드 오류로 동작하지 않아
EMA 뱅크로 근사했는데, 짧은 경로의 venv(C:\\ml_env)에 torch를 새로 설치해서 실제로 학습해본다.

구조:
  각 압력(pressure) 사이클 = 하나의 시퀀스 (길이 ~400~650 스텝)
  입력: (dL_pct, dR_pct) 시퀀스   ->  GRU(hidden=8)  ->  Linear(8,2)
  출력: 매 스텝마다 (strain, force) 동시 예측 (many-to-many)

게이트는 그대로 두고(이미 99%대), 압력 모드 "전문가"만 GRU로 교체해서
EMA 피처 버전(candidate2/5)과 직접 비교 가능하게 만든다.
"""

import os
import sys

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

SEED = 0
HIDDEN = 8
EPOCHS = 400
LR = 5e-3

torch.manual_seed(SEED)
np.random.seed(SEED)


class GRUExpert(nn.Module):
    def __init__(self, input_size=2, hidden_size=HIDDEN, output_size=2):
        super().__init__()
        self.gru = nn.GRU(input_size, hidden_size, num_layers=1, batch_first=True)
        self.head = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        out, _ = self.gru(x)          # (B, T, hidden)
        return self.head(out)          # (B, T, 2)

    def param_count(self):
        return sum(p.numel() for p in self.parameters())


def build_sequences(df, cycle_ids):
    """cycle_id별 pressure-phase 시퀀스를 (dL,dR) 입력과 (strain,force) 타깃으로 분리."""
    seqs_X, seqs_Y = [], []
    for cid in cycle_ids:
        g = df[(df.cycle_id == cid) & (df.phase == "pressure")].sort_values("t_s")
        if len(g) < common.MIN_SEGMENT_LEN:
            continue
        X = g[["dL_pct", "dR_pct"]].values.astype(np.float32)
        Y = g[["strain_pct", "Force_N"]].values.astype(np.float32)
        seqs_X.append(X)
        seqs_Y.append(Y)
    return seqs_X, seqs_Y


def main():
    df = common.load_raw()
    df = common.add_labels(df)
    train_df, test_df = common.split_by_cycle(df)

    train_cycles = sorted(train_df.cycle_id.unique())
    test_cycles = sorted(test_df.cycle_id.unique())

    Xtr_list, Ytr_list = build_sequences(df, train_cycles)
    Xte_list, Yte_list = build_sequences(df, test_cycles)
    print(f"train sequences: {len(Xtr_list)}  test sequences: {len(Xte_list)}")

    # 정규화 통계는 학습 시퀀스에서만 계산 (누수 방지)
    X_all = np.concatenate(Xtr_list, axis=0)
    Y_all = np.concatenate(Ytr_list, axis=0)
    x_mean, x_std = X_all.mean(0), X_all.std(0) + 1e-8
    y_mean, y_std = Y_all.mean(0), Y_all.std(0) + 1e-8

    def norm_x(a):
        return (a - x_mean) / x_std

    def norm_y(a):
        return (a - y_mean) / y_std

    def denorm_y(a):
        return a * y_std + y_mean

    device = "cpu"
    model = GRUExpert().to(device)
    print(f"GRU expert params: {model.param_count()}")

    opt = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = nn.MSELoss()

    train_tensors = [(torch.tensor(norm_x(X)).unsqueeze(0).to(device),
                       torch.tensor(norm_y(Y)).unsqueeze(0).to(device))
                      for X, Y in zip(Xtr_list, Ytr_list)]

    model.train()
    for epoch in range(EPOCHS):
        perm = np.random.permutation(len(train_tensors))
        total_loss = 0.0
        for i in perm:
            xb, yb = train_tensors[i]
            opt.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()
            total_loss += loss.item()
        if (epoch + 1) % 50 == 0 or epoch == 0:
            print(f"  epoch {epoch+1:4d}/{EPOCHS}  avg_loss={total_loss/len(train_tensors):.4f}")

    # ── 평가 (held-out test 시퀀스, 전체 타임스텝 pooled) ─────────────────────
    model.eval()
    all_true, all_pred = [], []
    with torch.no_grad():
        for X, Y in zip(Xte_list, Yte_list):
            xb = torch.tensor(norm_x(X)).unsqueeze(0).to(device)
            pred = model(xb).squeeze(0).numpy()
            pred_phys = denorm_y(pred)
            all_true.append(Y)
            all_pred.append(pred_phys)
    all_true = np.concatenate(all_true, axis=0)
    all_pred = np.concatenate(all_pred, axis=0)

    m_strain = common.regression_metrics(all_true[:, 0], all_pred[:, 0])
    m_force = common.regression_metrics(all_true[:, 1], all_pred[:, 1])
    print(f"[GRU expert, held-out] strain R2={m_strain['r2']:.4f} RMSE={m_strain['rmse']:.3f}%p | "
          f"force R2={m_force['r2']:.4f} RMSE={m_force['rmse']:.3f}N")

    result = dict(
        model="GRU(hidden=8) many-to-many, per-cycle full sequence",
        params=model.param_count(),
        epochs=EPOCHS,
        strain=m_strain,
        force=m_force,
    )
    common.save_result("candidate5b_true_rnn", result)

    # ── 시각화: 대표 테스트 시퀀스 하나 ─────────────────────────────────────
    import matplotlib.pyplot as plt
    mid = test_cycles[len(test_cycles)//2]
    g = df[(df.cycle_id == mid) & (df.phase == "pressure")].sort_values("t_s")
    Xs = g[["dL_pct", "dR_pct"]].values.astype(np.float32)
    Ys = g[["strain_pct", "Force_N"]].values.astype(np.float32)
    with torch.no_grad():
        pred = model(torch.tensor(norm_x(Xs)).unsqueeze(0)).squeeze(0).numpy()
    pred_phys = denorm_y(pred)
    t = g["t_s"].values - g["t_s"].values[0]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(t, Ys[:, 1], color="black", linewidth=2.0, label="Actual force (N)")
    ax.plot(t, pred_phys[:, 1], color="#D62728", linewidth=1.6, label=f"GRU prediction (R2={m_force['r2']:.3f})")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Force [N]")
    ax.set_title(f"True RNN (GRU) — held-out test cycle (strain={g.strain_pct.iloc[0]:.1f}%)")
    ax.legend(); ax.grid(alpha=0.25)
    plt.tight_layout()
    out = os.path.join(common.OUT_DIR, "candidate5b_true_rnn.png")
    fig.savefig(out, dpi=160)
    print(f"[save] {out}")


if __name__ == "__main__":
    main()
