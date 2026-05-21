import os
import re
import glob
import pickle

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import torch
from torch.utils.data import Dataset, DataLoader

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', '0332_DecouplingTest_TXTFiles')
SENSOR_BASELINE_MM = 120.0
L_BASELINE_SAMPLES = 50

# AccelStepper kinematics (from tensile tester firmware)
V_MAX   = 5.0   # mm/s
ACCEL   = 2.5   # mm/s²
D_TOTAL = 50.0  # mm

# File-level train/val/test split (strain index = mm extension, 0..36)
TEST_INDICES = {0, 9, 18, 27, 36}
VAL_INDICES  = {4, 13, 22, 31}


def _extract_number(path: str) -> int:
    return int(re.search(r'\d+', os.path.basename(path)).group())


def compute_proximity_array(n_half: int) -> np.ndarray:
    """
    Maps sample index within the trimmed window to physical proximity (mm).

    The motor runs a trapezoidal velocity profile:
      accel phase: 0 → V_max over t_accel seconds
      coast phase: V_max constant
      decel phase: V_max → 0 over t_accel seconds

    The recorded window covers 50mm→0mm (approach) then 0mm→50mm (retract).
    n_half samples covers one direction; the full array has shape (2*n_half-1,).
    """
    t_accel   = V_MAX / ACCEL
    d_accel   = 0.5 * ACCEL * t_accel ** 2
    d_coast   = D_TOTAL - 2 * d_accel
    t_coast   = d_coast / V_MAX
    T_one_way = t_accel + t_coast + t_accel

    def pos_at_time(t):
        if t <= t_accel:
            return 0.5 * ACCEL * t ** 2
        elif t <= t_accel + t_coast:
            return d_accel + V_MAX * (t - t_accel)
        else:
            td = t - (t_accel + t_coast)
            return (d_accel + d_coast) + V_MAX * td - 0.5 * ACCEL * td ** 2

    times    = np.linspace(0, T_one_way, n_half)
    pos_half = np.array([pos_at_time(t) for t in times])
    return np.concatenate([pos_half[::-1], pos_half[1:]])  # 50→0→50 mm


def _compute_global_baseline(file_list: list, n_half: int):
    """Global L0, R0 from strain0.txt (ε=0, d≈50mm)."""
    df0    = pd.read_csv(file_list[0])
    peak0  = df0['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax()
    start0 = max(0, peak0 - n_half + 1)
    L0 = float(df0['Channel 1'].iloc[start0: start0 + L_BASELINE_SAMPLES].mean())
    R0 = float(df0['Channel 4'].iloc[start0: start0 + L_BASELINE_SAMPLES].mean())
    return L0, R0


def _load_file(path: str, n_half: int, prox_arr: np.ndarray,
               L0: float, R0: float) -> dict | None:
    """
    Trims one file to the symmetric proximity-sweep window and computes
    ΔL/L₀(%) and ΔR/R₀(%).

    Returns dict with arrays of shape (2*n_half-1,), or None if file is too short.
    """
    df       = pd.read_csv(path)
    smoothed = df['Channel 1'].rolling(20, center=True, min_periods=1).mean()
    peak_idx = int(smoothed.idxmax())

    start = peak_idx - n_half + 1
    end   = peak_idx + n_half       # exclusive

    if start < 0 or end > len(df):
        return None

    ldc_raw = df['Channel 1'].values[start:end].astype(np.float64)
    r_raw   = df['Channel 4'].values[start:end].astype(np.float64)  # R_DC_raw

    dL_pct = ((L0 / ldc_raw) ** 2 - 1.0) * 100.0
    dR_pct = ((r_raw - R0) / R0) * 100.0

    strain_idx = _extract_number(path)
    epsilon    = strain_idx / SENSOR_BASELINE_MM   # ratio 0..0.30

    return {
        'dL_pct':     dL_pct.astype(np.float32),
        'dR_pct':     dR_pct.astype(np.float32),
        'd_mm':       prox_arr.astype(np.float32),
        'epsilon':    np.full(len(prox_arr), epsilon, dtype=np.float32),
        'strain_idx': strain_idx,
    }


class SensorDataset(Dataset):
    """
    Flat dataset of (ΔL_norm, ΔR_norm) → (ε_norm, d_norm) pairs.

    Pass fit=True for the training split to fit the StandardScalers;
    pass pre-fitted scalers for val/test splits.
    """
    def __init__(self, samples: list,
                 input_scaler: StandardScaler | None = None,
                 output_scaler: StandardScaler | None = None,
                 fit: bool = False):
        dL  = np.concatenate([s['dL_pct']  for s in samples])
        dR  = np.concatenate([s['dR_pct']  for s in samples])
        eps = np.concatenate([s['epsilon'] for s in samples])
        d   = np.concatenate([s['d_mm']    for s in samples])

        X_raw = np.stack([dL, dR], axis=1)   # (N, 2)
        Y_raw = np.stack([eps, d], axis=1)   # (N, 2)

        if fit:
            self.input_scaler  = StandardScaler()
            self.output_scaler = StandardScaler()
            self.X = self.input_scaler.fit_transform(X_raw).astype(np.float32)
            self.Y = self.output_scaler.fit_transform(Y_raw).astype(np.float32)
        else:
            self.input_scaler  = input_scaler
            self.output_scaler = output_scaler
            self.X = input_scaler.transform(X_raw).astype(np.float32)
            self.Y = output_scaler.transform(Y_raw).astype(np.float32)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, i):
        return torch.from_numpy(self.X[i]), torch.from_numpy(self.Y[i])


def build_dataloaders(data_dir: str = DATA_DIR, batch_size: int = 256):
    """
    Loads all strain*.txt files and returns train/val/test DataLoaders plus
    fitted scalers and proximity metadata.

    Returns:
        train_loader, val_loader, test_loader,
        input_scaler, output_scaler,
        n_half (int), prox_arr (np.ndarray),
        L0 (float), R0 (float)
    """
    file_list = sorted(
        glob.glob(os.path.join(data_dir, 'strain*.txt')),
        key=_extract_number,
    )
    assert len(file_list) == 37, f"Expected 37 files, found {len(file_list)}"

    # N_half from the file with the fewest samples after the LDC peak
    ref_file  = max(file_list, key=_extract_number)  # strain36.txt
    df_ref    = pd.read_csv(ref_file)
    peak_ref  = int(df_ref['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax())
    n_half    = len(df_ref) - peak_ref
    prox_arr  = compute_proximity_array(n_half)

    L0, R0 = _compute_global_baseline(file_list, n_half)
    print(f"Baseline: L0={L0:.2f}, R0={R0:.2f}, N_half={n_half}, "
          f"window={2*n_half-1} samples/file")

    train_samples, val_samples, test_samples = [], [], []
    skipped = []

    for path in file_list:
        idx  = _extract_number(path)
        data = _load_file(path, n_half, prox_arr, L0, R0)
        if data is None:
            skipped.append(idx)
            continue
        if idx in TEST_INDICES:
            test_samples.append(data)
        elif idx in VAL_INDICES:
            val_samples.append(data)
        else:
            train_samples.append(data)

    if skipped:
        print(f"Skipped (too short): strain indices {skipped}")

    train_ds = SensorDataset(train_samples, fit=True)
    val_ds   = SensorDataset(val_samples,
                             input_scaler=train_ds.input_scaler,
                             output_scaler=train_ds.output_scaler)
    test_ds  = SensorDataset(test_samples,
                             input_scaler=train_ds.input_scaler,
                             output_scaler=train_ds.output_scaler)

    print(f"Dataset sizes  train: {len(train_ds):,}  val: {len(val_ds):,}  "
          f"test: {len(test_ds):,}")

    scalers_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'checkpoints', 'scalers.pkl')
    os.makedirs(os.path.dirname(scalers_path), exist_ok=True)
    with open(scalers_path, 'wb') as f:
        pickle.dump({
            'input':  train_ds.input_scaler,
            'output': train_ds.output_scaler,
            'n_half': n_half,
            'L0': L0, 'R0': R0,
        }, f)

    train_loader = DataLoader(train_ds, batch_size=batch_size,
                              shuffle=True,  num_workers=0, pin_memory=False)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size,
                              shuffle=False, num_workers=0, pin_memory=False)
    test_loader  = DataLoader(test_ds,  batch_size=batch_size,
                              shuffle=False, num_workers=0, pin_memory=False)

    return (train_loader, val_loader, test_loader,
            train_ds.input_scaler, train_ds.output_scaler,
            n_half, prox_arr, L0, R0)


if __name__ == '__main__':
    (train_loader, val_loader, test_loader,
     in_sc, out_sc, n_half, prox_arr, L0, R0) = build_dataloaders()

    X, Y = next(iter(train_loader))
    print(f"Input batch shape : {X.shape}  dtype={X.dtype}")
    print(f"Output batch shape: {Y.shape}  dtype={Y.dtype}")
    print(f"Input  mean/std (normalized): {X.mean().item():.3f} / {X.std().item():.3f}")
    print(f"Output mean/std (normalized): {Y.mean().item():.3f} / {Y.std().item():.3f}")
    print(f"Input  scaler means  (ΔL%, ΔR%): {in_sc.mean_}")
    print(f"Output scaler means  (ε, d_mm) : {out_sc.mean_}")
