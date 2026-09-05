import numpy as np, pandas as pd
import matplotlib.pyplot as plt

COLOR_L = "#FF8C00"
COLOR_R = "#2CA02C"

df = pd.read_csv('mms_20260806_200653.csv')
df['strain_pct'] = (df.ya_mm + df.yb_mm) / 120.0 * 100
df['Force_N'] = -df.Fz_N
_offset = df.loc[df.z_mm >= 0, 'Force_N'].mean()
df['Force_N'] = df['Force_N'] - _offset
print(f'[tare] Force_N 오프셋 {_offset:+.4f}N 보정')
phase = np.where(df.z_mm.values >= 0, 'proximity', 'pressure')
seg = (phase != np.roll(phase,1)).cumsum(); seg[0]=0
df['phase']=phase; df['segment_id']=seg
strain_r = df.strain_pct.round(3).values
cyc = (strain_r != np.roll(strain_r,1)).cumsum(); cyc[0]=0
df['cycle_id']=cyc
sizes = df.groupby('cycle_id').size()
real_cycles = sizes[sizes>500].index

def shoelace(x, y):
    x = np.asarray(x); y = np.asarray(y)
    return 0.5*abs(np.sum(x*np.roll(y,-1) - np.roll(x,-1)*y))

rows=[]
for cid in real_cycles:
    g = df[df.cycle_id==cid]
    press = g[g.phase=='pressure'].sort_values('t_s').reset_index(drop=True)
    if len(press) < 30: continue
    imin = press.z_mm.idxmin()
    load = press.iloc[:imin+1]; unload = press.iloc[imin:]
    Fc = np.linspace(0, press.Force_N.max()*0.98, 60)
    def interp_path(seg, col):
        F = seg.Force_N.values; y = seg[col].values
        order = np.argsort(F)
        return np.interp(Fc, F[order], y[order])
    for col, tag in [('dR_pct','R'), ('dL_pct','L')]:
        y_load = interp_path(load, col); y_unload = interp_path(unload, col)
        loop_x = np.concatenate([Fc, Fc[::-1]])
        loop_y = np.concatenate([y_load, y_unload[::-1]])
        area = shoelace(loop_x, loop_y)
        rows.append(dict(strain=press.strain_pct.iloc[0], sensor=tag, area=area,
                          swing=press[col].max()-press[col].iloc[0]))
res = pd.DataFrame(rows)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for tag, color in [('R', COLOR_R), ('L', COLOR_L)]:
    sub = res[res.sensor==tag].sort_values('strain')
    axes[0].plot(sub.strain, sub.swing, 'o-', color=color, label=f'{tag} swing', markersize=4)
    axes[1].plot(sub.strain, sub.area, 'o-', color=color, label=f'{tag} loop area', markersize=4)

axes[0].set_xlabel('Strain [%]'); axes[0].set_ylabel('Touch->max-compression swing [%p]')
axes[0].set_title('Pressure response amplitude vs strain')
axes[0].legend(); axes[0].grid(alpha=0.25)

axes[1].set_xlabel('Strain [%]'); axes[1].set_ylabel('Hysteresis loop area [N*%p]')
axes[1].set_title('Hysteresis loop area vs strain')
axes[1].legend(); axes[1].grid(alpha=0.25)

plt.tight_layout()
fig.savefig('../output/strain_sensitivity_growth.png', dpi=160)
print('saved')
