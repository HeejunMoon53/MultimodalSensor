"""
export_model_new.py — Metal + Hand PINN 재학습 후 ONNX + PKL 저장

실행: C:/ml_env/Scripts/python nn_decoupling/export_model_new.py
출력:
  nn_decoupling/checkpoints/decoupler_metal.onnx
  nn_decoupling/checkpoints/decoupler_hand.onnx
  nn_decoupling/checkpoints/scalers_metal.pkl
  nn_decoupling/checkpoints/scalers_hand.pkl
"""
import os, sys, time, copy, glob, pickle, warnings
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.preprocessing import StandardScaler
from torch.utils.data import Dataset, DataLoader

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from model import TwoStageDecoupler, PhysicsLoss

warnings.filterwarnings('ignore')

DATA_ROOT  = os.path.join(HERE, 'data', 'metal')
METAL_P1   = os.path.join(DATA_ROOT, 'metal', 'p1_strain_discrete')
METAL_P2   = os.path.join(DATA_ROOT, 'metal', 'p2_proximity_discrete')
HAND_P1    = os.path.join(DATA_ROOT, 'hand',  'p1_strain_discrete')
HAND_P2    = os.path.join(DATA_ROOT, 'hand',  'p2_proximity_discrete')
CKPT_DIR   = os.path.join(HERE, 'checkpoints')

L0_METAL, R0_METAL = 11953766.0, 25350.0
L0_HAND,  R0_HAND  = 11829854.0, 25614.0
PROX_METAL, PROX_HAND = 52.0, 30.0
SENSOR_L0 = 120.0


# ── 데이터 로드 ───────────────────────────────────────────────────────────────

def load_csv_file(path, prox_offset, L0, R0):
    df = pd.read_csv(path)
    df['strain_mm']    = (df['xa_mm'].abs() * 2).round(2)
    df['proximity_mm'] = (prox_offset + df['z_mm']).round(2)
    df = df[df['proximity_mm'] >= 0].reset_index(drop=True)
    if len(df) < 10:
        return None
    dL  = ((L0 / df['ldc_raw'].clip(lower=1)) ** 2 - 1.0) * 100.0
    dR  = (df['r_raw'] - R0) / R0 * 100.0
    eps = df['strain_mm'] / SENSOR_L0
    d   = df['proximity_mm']
    return dict(dL=dL.values.astype(np.float32), dR=dR.values.astype(np.float32),
                eps=eps.values.astype(np.float32), d=d.values.astype(np.float32))


def load_dir(directory, prox_offset, L0, R0):
    return [s for f in sorted(glob.glob(os.path.join(directory, '*.csv')))
            if (s := load_csv_file(f, prox_offset, L0, R0)) is not None]


def split_samples(samples, test_frac=0.15, val_frac=0.15, seed=42):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(samples))
    n_te = max(1, round(len(samples) * test_frac))
    n_va = max(1, round(len(samples) * val_frac))
    tr_idx = set(idx[n_te + n_va:].tolist())
    va_idx = set(idx[n_te:n_te + n_va].tolist())
    te_idx = set(idx[:n_te].tolist())
    return ([samples[i] for i in range(len(samples)) if i in tr_idx],
            [samples[i] for i in range(len(samples)) if i in va_idx],
            [samples[i] for i in range(len(samples)) if i in te_idx])


class SensorDS(Dataset):
    def __init__(self, samples, in_sc=None, out_sc=None, fit=False):
        dL  = np.concatenate([s['dL']  for s in samples])
        dR  = np.concatenate([s['dR']  for s in samples])
        eps = np.concatenate([s['eps'] for s in samples])
        d   = np.concatenate([s['d']   for s in samples])
        X   = np.stack([dL, dR], axis=1).astype(np.float32)
        Y   = np.stack([eps, d], axis=1).astype(np.float32)
        if fit:
            self.in_sc  = StandardScaler().fit(X)
            self.out_sc = StandardScaler().fit(Y)
        else:
            self.in_sc, self.out_sc = in_sc, out_sc
        self.X = self.in_sc.transform(X).astype(np.float32)
        self.Y = self.out_sc.transform(Y).astype(np.float32)

    def __len__(self): return len(self.X)
    def __getitem__(self, i):
        return torch.from_numpy(self.X[i]), torch.from_numpy(self.Y[i])


# ── 학습 + ONNX 내보내기 ─────────────────────────────────────────────────────

def _inv(Y, sc):
    return torch.from_numpy(sc.inverse_transform(Y.detach().cpu().numpy()).astype(np.float32))


def train_and_export(label, tr, va, te,
                     lam_final, epochs, patience, beta2_init,
                     onnx_path, pkl_path, L0, R0):
    tr_ds = SensorDS(tr, fit=True)
    va_ds = SensorDS(va, tr_ds.in_sc, tr_ds.out_sc)
    te_ds = SensorDS(te, tr_ds.in_sc, tr_ds.out_sc)
    mk = lambda ds, sh: DataLoader(ds, batch_size=256, shuffle=sh, num_workers=0)
    trl, val, tel = mk(tr_ds, True), mk(va_ds, False), mk(te_ds, False)

    model = TwoStageDecoupler()
    phys  = PhysicsLoss()
    phys.beta2 = nn.Parameter(torch.tensor(float(beta2_init)))
    params = list(model.parameters()) + list(phys.parameters())
    opt   = optim.AdamW(params, lr=1e-3, weight_decay=1e-4)
    sched = CosineAnnealingLR(opt, T_max=epochs, eta_min=1e-5)

    best_d = float('inf'); best_ep = 0; best_st = None; pc = 0
    t0 = time.time()

    for ep in range(1, epochs + 1):
        lam = 0.0 if ep < 30 else (ep - 30) / max(1, epochs - 30) * lam_final
        model.train()
        for X, Y in trl:
            opt.zero_grad()
            Yp = model(X)
            loss = nn.functional.mse_loss(Yp, Y)
            if lam > 0:
                Yph = _inv(Yp, tr_ds.out_sc); Xph = _inv(X, tr_ds.in_sc)
                loss = loss + lam * phys(Yph[:, 0], Yph[:, 1], Xph[:, 1], Xph[:, 0])
            loss.backward()
            nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
        sched.step()

        model.eval()
        with torch.no_grad():
            de = [(_inv(model(X), tr_ds.out_sc)[:, 1] -
                   torch.from_numpy(tr_ds.out_sc.inverse_transform(Y.numpy()).astype(np.float32))[:, 1]).abs()
                  for X, Y in val]
        mae_d = torch.cat(de).mean().item()

        if ep % 50 == 0 or ep == 1:
            print(f"  ep{ep:3d} lam={lam:.3f} val_d={mae_d:.2f}mm")
        if mae_d < best_d:
            best_d = mae_d; best_ep = ep; best_st = copy.deepcopy(model.state_dict()); pc = 0
        else:
            pc += 1
            if pc >= patience:
                print(f"  EarlyStop @ep{ep}  best d={best_d:.2f}mm @ep{best_ep}")
                break

    model.load_state_dict(best_st)
    model.eval()

    # Test MAE
    with torch.no_grad():
        de = [(_inv(model(X), tr_ds.out_sc)[:, 1] -
               torch.from_numpy(tr_ds.out_sc.inverse_transform(Y.numpy()).astype(np.float32))[:, 1]).abs()
              for X, Y in tel]
    print(f"  Test MAE d = {torch.cat(de).mean().item():.2f}mm  ({time.time()-t0:.1f}s)")

    # ── ONNX 내보내기 ─────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(onnx_path), exist_ok=True)
    dummy = torch.zeros(1, 2)
    torch.onnx.export(
        model, dummy, onnx_path,
        input_names=["sensor_input"], output_names=["output"],
        dynamic_axes={"sensor_input": {0: "batch"}, "output": {0: "batch"}},
        opset_version=17, verbose=False,
    )
    print(f"  ONNX -> {onnx_path}")

    # ── Scalers PKL ───────────────────────────────────────────────────────────
    with open(pkl_path, 'wb') as f:
        pickle.dump({'input': tr_ds.in_sc, 'output': tr_ds.out_sc,
                     'L0': L0, 'R0': R0}, f)
    print(f"  PKL  -> {pkl_path}")


def main():
    os.makedirs(CKPT_DIR, exist_ok=True)
    torch.manual_seed(42); np.random.seed(42)

    print("▶ 데이터 로드...")
    mp1 = load_dir(METAL_P1, PROX_METAL, L0_METAL, R0_METAL)
    mp2 = load_dir(METAL_P2, PROX_METAL, L0_METAL, R0_METAL)
    hp1 = load_dir(HAND_P1,  PROX_HAND,  L0_HAND,  R0_HAND)
    hp2 = load_dir(HAND_P2,  PROX_HAND,  L0_HAND,  R0_HAND)
    print(f"  Metal P1:{len(mp1)} P2:{len(mp2)}  Hand P1:{len(hp1)} P2:{len(hp2)}")

    mp1_tr, mp1_va, mp1_te = split_samples(mp1)
    mp2_tr, mp2_va, mp2_te = split_samples(mp2)
    hp1_tr, hp1_va, hp1_te = split_samples(hp1)
    hp2_tr, hp2_va, hp2_te = split_samples(hp2)

    print("\n[Metal PINN] 학습 + ONNX 내보내기")
    train_and_export(
        "Metal",
        mp1_tr + mp2_tr, mp1_va + mp2_va, mp1_te + mp2_te,
        lam_final=0.10, epochs=300, patience=30, beta2_init=-8.0,
        onnx_path=os.path.join(CKPT_DIR, 'decoupler_metal.onnx'),
        pkl_path=os.path.join(CKPT_DIR, 'scalers_metal.pkl'),
        L0=L0_METAL, R0=R0_METAL,
    )

    print("\n[Hand PINN] 학습 + ONNX 내보내기")
    train_and_export(
        "Hand",
        hp1_tr + hp2_tr, hp1_va + hp2_va, hp1_te + hp2_te,
        lam_final=0.10, epochs=300, patience=30, beta2_init=8.0,
        onnx_path=os.path.join(CKPT_DIR, 'decoupler_hand.onnx'),
        pkl_path=os.path.join(CKPT_DIR, 'scalers_hand.pkl'),
        L0=L0_HAND, R0=R0_HAND,
    )
    print("\n완료!")


if __name__ == '__main__':
    main()
