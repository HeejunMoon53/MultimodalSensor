import numpy as np, pandas as pd
rng = np.random.default_rng(0)
df = pd.DataFrame({
    "dR_norm": rng.uniform(-1.5, 2.5, 100).astype("float32"),  # 정규화된 범위
})
df.to_csv("val_stage1.csv", index=False)