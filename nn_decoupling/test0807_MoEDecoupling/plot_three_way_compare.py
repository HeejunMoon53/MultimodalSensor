"""
plot_three_way_compare.py
그림 7b 확장판: Model A(기준선, 2-input) / Model B(+EMA MLP, 4-input) / GRU(2-input 시퀀스)
세 모델을 같은 held-out 사이클(strain=15.0%, cycle_id=134) 위에서 동시에 비교한다.
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

SEED = 0
TAU_OVERALL_S = 1.0125
EMA_HALFLIFE_S = TAU_OVERALL_S * 0.6931
HIDDEN = (24, 16, 8)
GRU_HIDDEN = 8
GRU_EPOCHS = 400
GRU_LR = 5e-3

COLOR_A = "#1F77B4"   # Model A (기준선)
COLOR_B = "#D62728"   # Model B (+EMA MLP)
COLOR_GRU = "#9467BD"  # GRU

torch.manual_seed(SEED)
np.random.seed(SEED)


class GRUExpert(nn.Module):
    def __init__(self, input_size=2, hidden_size=GRU_HIDDEN, output_size=2):
        super().__init__()
        self.gru = nn.GRU(input_size, hidden_size, num_layers=1, batch_first=True)
        self.head = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        out, _ = self.gru(x)
        return self.head(out)

    def param_count(self):
        return sum(p.numel() for p in self.parameters())


def build_mlp():
    return make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=HIDDEN, activation="tanh", solver="adam",
                      max_iter=4000, random_state=0, early_stopping=True, n_iter_no_change=40),
    )


def train_gru(train_df):
    seqs_X, seqs_Y = [], []
    for cid, g in train_df[train_df.phase == "pressure"].groupby("cycle_id"):
        g = g.sort_values("t_s")
        if len(g) < common.MIN_SEGMENT_LEN:
            continue
        seqs_X.append(g[["dL_pct", "dR_pct"]].values.astype(np.float32))
        seqs_Y.append(g[["strain_pct", "Force_N"]].values.astype(np.float32))

    X_all = np.concatenate(seqs_X, axis=0)
    Y_all = np.concatenate(seqs_Y, axis=0)
    x_mean, x_std = X_all.mean(0), X_all.std(0) + 1e-8
    y_mean, y_std = Y_all.mean(0), Y_all.std(0) + 1e-8

    model = GRUExpert()
    opt = torch.optim.Adam(model.parameters(), lr=GRU_LR)
    loss_fn = nn.MSELoss()
    train_tensors = [(torch.tensor((X - x_mean) / x_std).unsqueeze(0),
                       torch.tensor((Y - y_mean) / y_std).unsqueeze(0))
                      for X, Y in zip(seqs_X, seqs_Y)]

    model.train()
    for epoch in range(GRU_EPOCHS):
        perm = np.random.permutation(len(train_tensors))
        for i in perm:
            xb, yb = train_tensors[i]
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
        if (epoch + 1) % 100 == 0 or epoch == 0:
            print(f"  [GRU] epoch {epoch+1}/{GRU_EPOCHS}")

    return model, x_mean, x_std, y_mean, y_std


def gru_predict(model, X, x_mean, x_std, y_mean, y_std):
    model.eval()
    with torch.no_grad():
        xb = torch.tensor(((X - x_mean) / x_std).astype(np.float32)).unsqueeze(0)
        pred = model(xb).squeeze(0).numpy()
    return pred * y_std + y_mean


def main():
    df = common.load_raw()
    df = common.add_labels(df)
    df, ema_cols = common.add_ema_features(df, halflife_s=EMA_HALFLIFE_S)
    feat_a = common.FEATURE_COLS_BASE
    feat_b = common.FEATURE_COLS_BASE + ema_cols

    train_df, test_df = common.split_by_cycle(df)
    test_cycles = sorted(test_df.cycle_id.unique())
    mid_cycle = test_cycles[len(test_cycles) // 2]
    print(f"test cycles={test_cycles}  using mid cycle={mid_cycle}")

    tr_press = train_df[train_df.phase == "pressure"]

    model_a = build_mlp()
    model_a.fit(tr_press[feat_a].values, tr_press["Force_N"].values)

    model_b = build_mlp()
    model_b.fit(tr_press[feat_b].values, tr_press["Force_N"].values)

    print("[GRU] training...")
    gru_model, x_mean, x_std, y_mean, y_std = train_gru(train_df)

    g = test_df[(test_df.cycle_id == mid_cycle) & (test_df.phase == "pressure")].sort_values("t_s")
    t = g["t_s"].values - g["t_s"].values[0]
    y_true = g["Force_N"].values
    strain_val = g["strain_pct"].iloc[0]

    pred_a = model_a.predict(g[feat_a].values)
    pred_b = model_b.predict(g[feat_b].values)
    Xg = g[["dL_pct", "dR_pct"]].values.astype(np.float32)
    pred_gru = gru_predict(gru_model, Xg, x_mean, x_std, y_mean, y_std)[:, 1]

    def rmse(a, b):
        return float(np.sqrt(np.mean((a - b) ** 2)))

    rmse_a, rmse_b, rmse_gru = rmse(y_true, pred_a), rmse(y_true, pred_b), rmse(y_true, pred_gru)
    print(f"RMSE  A(baseline)={rmse_a:.3f}N  B(+EMA)={rmse_b:.3f}N  GRU={rmse_gru:.3f}N")

    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    ax.plot(t, y_true, color="black", linewidth=2.2, label="Actual (F/T sensor)")
    ax.plot(t, pred_a, color=COLOR_A, linewidth=1.5, linestyle="--",
            label=f"Model A: baseline, 2-input (RMSE {rmse_a:.2f}N)")
    ax.plot(t, pred_b, color=COLOR_B, linewidth=1.5, linestyle="-.",
            label=f"Model B: +EMA MLP, 4-input (RMSE {rmse_b:.2f}N)")
    ax.plot(t, pred_gru, color=COLOR_GRU, linewidth=1.7,
            label=f"GRU: 2-input, learned memory (RMSE {rmse_gru:.2f}N)")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Force [N]")
    ax.set_title(f"Held-out test cycle (strain={strain_val:.1f}%) — Model A vs Model B vs GRU")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25)

    plt.tight_layout()
    out = os.path.join(common.OUT_DIR, "three_way_compare.png")
    fig.savefig(out, dpi=160)
    print(f"[save] {out}")


if __name__ == "__main__":
    main()
