import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from pathlib import Path

DIR = Path(__file__).parent
OUT = DIR  

COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"

train = pd.read_csv(OUT / "train.csv")
val   = pd.read_csv(OUT / "val.csv")
test  = pd.read_csv(OUT / "test.csv")

splits = [
    (train, "train", "o", 0.1, 5),
    (val,   "val",   "s", 0.1, 5),
    (test,  "test",  "^", 0.1, 5),
]

fig = plt.figure(figsize=(14, 6))

for plot_i, (zcol, zlabel, color) in enumerate([
    ("dL_pct", "ΔL / L₀ [%]", COLOR_L),
    ("dR_pct", "ΔR / R₀ [%]", COLOR_R),
]):
    ax = fig.add_subplot(1, 2, plot_i + 1, projection="3d")
    for split_df, name, marker, alpha, ms in splits:
        ax.scatter(
            split_df["d_act_mm"],
            split_df["eps_act_pct"],
            split_df[zcol],
            c=color, marker=marker, s=ms,
            alpha=alpha, label=name, edgecolors="none",
        )
    ax.set_xlabel("Proximity [mm]", fontsize=8, labelpad=2)
    ax.set_ylabel("Strain [%]",     fontsize=8, labelpad=2)
    ax.set_zlabel(zlabel,           fontsize=8, labelpad=2)
    ax.set_title(zlabel, fontsize=10, fontweight="bold")
    ax.tick_params(labelsize=6)
    ax.view_init(elev=22, azim=-55)
    ax.legend(fontsize=7, markerscale=1.5, loc="upper right")

plt.tight_layout()
fig.savefig(OUT / "scatter_3d.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("Saved → dataset/scatter_3d.png")
