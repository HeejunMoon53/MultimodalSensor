"""
candidate6_option3_hybrid.py
"옵션 3" 실제 end-to-end 평가: 게이트 + Expert A(근접)는 EMA 4-input(후보 2 방식 그대로),
Expert B(압력)만 GRU 2-input(후보 5b 방식)으로 교체.

지금까지 candidate5b는 "게이트가 항상 정답으로 보내준다"고 가정한 oracle routing으로만
평가했다. 여기서는 실제로 학습된 게이트의 예측 라벨로 라우팅하고, 게이트가 "접촉"이라고
예측한 연속 구간(run)만 골라 GRU에 시퀀스로 흘려보내는 진짜 파이프라인을 만든다.
"""
import os
import sys

import numpy as np
import torch
import torch.nn as nn
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

SEED = 0
TAU_OVERALL_S = 1.0125
EMA_HALFLIFE_S = TAU_OVERALL_S * 0.6931
HIDDEN_EXPERT = (24, 16, 8)
HIDDEN_GATE = (8, 4)
GRU_HIDDEN = 8
GRU_EPOCHS = 400
GRU_LR = 5e-3

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


def build_gate():
    return make_pipeline(
        StandardScaler(),
        MLPClassifier(hidden_layer_sizes=HIDDEN_GATE, activation="tanh", solver="adam",
                      max_iter=3000, random_state=0, early_stopping=True, n_iter_no_change=30),
    )


def build_expert():
    return make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=HIDDEN_EXPERT, activation="tanh", solver="adam",
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
        total_loss = 0.0
        for i in perm:
            xb, yb = train_tensors[i]
            opt.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()
            total_loss += loss.item()
        if (epoch + 1) % 100 == 0 or epoch == 0:
            print(f"  [GRU] epoch {epoch+1:4d}/{GRU_EPOCHS}  avg_loss={total_loss/len(train_tensors):.4f}")

    return model, x_mean, x_std, y_mean, y_std


def gru_predict_sequence(model, X, x_mean, x_std, y_mean, y_std):
    """X: (T,2) raw dL/dR -> (T,2) physical-unit (strain, force) predictions."""
    model.eval()
    with torch.no_grad():
        xb = torch.tensor(((X - x_mean) / x_std).astype(np.float32)).unsqueeze(0)
        pred = model(xb).squeeze(0).numpy()
    return pred * y_std + y_mean


def find_runs(mask):
    """mask: bool array -> [(start,end_exclusive), ...] for contiguous True runs."""
    runs = []
    n = len(mask)
    i = 0
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    return runs


def main():
    df = common.load_raw()
    df = common.add_labels(df)
    df, ema_cols = common.add_ema_features(df, halflife_s=EMA_HALFLIFE_S)
    feature_cols = common.FEATURE_COLS_BASE + ema_cols  # [dL_pct, dR_pct, dL_ema, dR_ema]

    train_df, test_df = common.split_by_cycle(df)
    test_df = test_df.reset_index(drop=True)
    print(f"train rows={len(train_df)}  test rows={len(test_df)}  test cycles={sorted(test_df.cycle_id.unique())}")

    # ── 1) 게이트 + Expert A (4-input EMA, 후보 2 방식) ──────────────────────
    gate = build_gate()
    gate.fit(train_df[feature_cols].values, train_df["contact"].values)

    expert_a = build_expert()
    tr_a = train_df[train_df.phase == "proximity"]
    expert_a.fit(tr_a[feature_cols].values, tr_a[["strain_pct", "z_mm"]].values)

    # ── 2) GRU Expert B (2-input raw, 후보 5b 방식) ──────────────────────────
    print("[GRU] training pressure expert...")
    gru_model, x_mean, x_std, y_mean, y_std = train_gru(train_df)
    gru_params = gru_model.param_count()
    print(f"[GRU] params={gru_params}")

    # ── 3) 진짜 end-to-end: 게이트 예측 라우팅 -> (Expert A | GRU 시퀀스) ──────
    gate_pred_full = gate.predict(test_df[feature_cols].values)
    gate_metrics = common.classification_metrics(test_df["contact"].values, gate_pred_full)
    print(f"[Gate] acc={gate_metrics['acc']:.4f}  f1={gate_metrics['f1']:.4f}")

    test_df["_gate_pred"] = gate_pred_full
    test_df["_pos"] = np.arange(len(test_df))

    strain_pred_all = np.zeros(len(test_df))
    force_true_list, force_pred_list = [], []
    dist_true_list, dist_pred_list = [], []
    n_misrouted_pressure = 0
    n_true_pressure = 0

    for cid, g in test_df.groupby("cycle_id"):
        g = g.sort_values("t_s")
        pos = g["_pos"].values
        gate_pred = g["_gate_pred"].values  # 0=no-contact(proximity), 1=contact(pressure)
        phase = g["phase"].values

        # ── no-contact 예측 -> Expert A ──
        no_contact_idx = np.where(gate_pred == 0)[0]
        if len(no_contact_idx) > 0:
            Xa = g.iloc[no_contact_idx][feature_cols].values
            pred_a = expert_a.predict(Xa)
            strain_pred_all[pos[no_contact_idx]] = pred_a[:, 0]

            true_prox_sub = phase[no_contact_idx] == "proximity"
            if true_prox_sub.any():
                dist_true_list.append(g.iloc[no_contact_idx]["z_mm"].values[true_prox_sub])
                dist_pred_list.append(pred_a[true_prox_sub, 1])

        # ── contact 예측(연속 run) -> GRU 시퀀스 ──
        contact_mask = gate_pred == 1
        n_true_pressure += int((phase == "pressure").sum())
        n_misrouted_pressure += int(((phase == "pressure") & (gate_pred == 0)).sum())

        for start, end in find_runs(contact_mask):
            Xg = g.iloc[start:end][["dL_pct", "dR_pct"]].values.astype(np.float32)
            pred_g = gru_predict_sequence(gru_model, Xg, x_mean, x_std, y_mean, y_std)
            strain_pred_all[pos[start:end]] = pred_g[:, 0]

            sub_phase = phase[start:end]
            true_press_sub = sub_phase == "pressure"
            if true_press_sub.any():
                force_true_list.append(g.iloc[start:end]["Force_N"].values[true_press_sub])
                force_pred_list.append(pred_g[true_press_sub, 1])

    # ── strain: 전체 test set (근접+압력 합쳐서) ──
    m_e2e_strain = common.regression_metrics(test_df["strain_pct"].values, strain_pred_all)
    print(f"[E2E] strain(전체) R2={m_e2e_strain['r2']:.4f} RMSE={m_e2e_strain['rmse']:.3f}%p")

    # ── strain: phase별 분리 (진짜 근접 샘플만 / 진짜 압력 샘플만) ──
    is_press = (test_df["phase"].values == "pressure")
    is_prox = (test_df["phase"].values == "proximity")
    m_strain_press = common.regression_metrics(test_df["strain_pct"].values[is_press], strain_pred_all[is_press])
    m_strain_prox = common.regression_metrics(test_df["strain_pct"].values[is_prox], strain_pred_all[is_prox])
    print(f"[E2E] strain(진짜 압력만) R2={m_strain_press['r2']:.4f} RMSE={m_strain_press['rmse']:.3f}%p")
    print(f"[E2E] strain(진짜 근접만) R2={m_strain_prox['r2']:.4f} RMSE={m_strain_prox['rmse']:.3f}%p")

    # ── force: 실제 압력 샘플 중 GRU로 라우팅된 것만 ──
    force_true = np.concatenate(force_true_list)
    force_pred = np.concatenate(force_pred_list)
    m_e2e_force = common.regression_metrics(force_true, force_pred)
    print(f"[E2E] force(진짜 압력 샘플, GRU 라우팅분) R2={m_e2e_force['r2']:.4f} "
          f"RMSE={m_e2e_force['rmse']:.3f}N  n={len(force_true)}")

    dist_true = np.concatenate(dist_true_list) if dist_true_list else np.array([])
    dist_pred = np.concatenate(dist_pred_list) if dist_pred_list else np.array([])
    m_e2e_dist = None
    if len(dist_true) > 0:
        m_e2e_dist = common.regression_metrics(dist_true, dist_pred)
        print(f"[E2E] distance(진짜 근접 샘플) R2={m_e2e_dist['r2']:.4f} "
              f"RMSE={m_e2e_dist['rmse']:.3f}mm  n={len(dist_true)}")

    print(f"[routing] 진짜 압력 샘플 중 게이트가 근접으로 잘못 보낸 수: "
          f"{n_misrouted_pressure}/{n_true_pressure}")

    total_params = 81 + 674 + gru_params  # gate(4-in) + expertA(4-in) + GRU
    print(f"[params] gate=81 expertA=674 GRU={gru_params} total={total_params}")

    result = dict(
        option="option3_gate_expertA_ema_expertB_gru",
        gate=gate_metrics,
        end_to_end_strain=m_e2e_strain,
        end_to_end_strain_pressure_subset=m_strain_press,
        end_to_end_strain_proximity_subset=m_strain_prox,
        pressure_force_realistic_routing=m_e2e_force,
        proximity_distance_realistic_routing=m_e2e_dist,
        n_true_pressure=n_true_pressure,
        n_misrouted_pressure=n_misrouted_pressure,
        params=dict(gate=81, expert_a=674, gru_expert_b=gru_params, total=total_params),
    )
    common.save_result("candidate6_option3_hybrid", result)


if __name__ == "__main__":
    main()
