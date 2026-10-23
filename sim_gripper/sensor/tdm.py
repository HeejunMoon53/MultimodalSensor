"""TDM 샘플러 (M2): 1 kHz 샘플에 실측 수준 가우시안 노이즈."""
import numpy as np
import pandas as pd

from sim_gripper.sensor.build_tables import NEW_DIR


def noise_from_data():
    """세션 214746 원시 dL_pct, dR_pct의 std(diff)/√2 (느린 변화 제거한 샘플 노이즈)."""
    d = pd.read_csv(NEW_DIR / "moe_monitor_20260909_214746.csv")
    d = d[d["mode"].isin([0, 1]) & (d.dL_pct.abs() < 150) & (d.dR_pct.abs() < 150)]
    return tuple(float(np.diff(d[c].values).std() / np.sqrt(2)) for c in ("dL_pct", "dR_pct"))


class TdmSampler:
    def __init__(self, sigma_L, sigma_R, seed=0):
        self.sL, self.sR = sigma_L, sigma_R
        self.rng = np.random.default_rng(seed)

    def sample(self, dL, dR):
        nL, nR = self.rng.normal(size=2)
        return dL + self.sL * nL, dR + self.sR * nR
