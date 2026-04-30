import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as PathEffects
import glob
import re

def extract_number(filename):
    basename = os.path.basename(filename)
    match = re.search(r'\d+', basename)
    return int(match.group()) if match else -1

script_dir = os.path.dirname(os.path.abspath(__file__))
file_pattern = os.path.join(script_dir, "strain*.txt")
file_list = sorted(glob.glob(file_pattern), key=extract_number)

if not file_list:
    print("❌ 에러: 파일을 찾을 수 없습니다.")
    exit()

def get_proximity_array_half(n_half):
    V_max = 5.0 
    A = 2.5
    D_total = 50.0
    t_accel = V_max / A
    d_accel = 0.5 * A * (t_accel**2)
    d_coast = D_total - 2 * d_accel
    t_coast = d_coast / V_max
    T_one_way = t_accel + t_coast + t_accel
    
    def pos_at_time(t):
        if t <= t_accel: return 0.5 * A * (t**2)
        elif t <= t_accel + t_coast: return d_accel + V_max * (t - t_accel)
        else:
            t_decel = t - (t_accel + t_coast)
            return (d_accel + d_coast) + (V_max * t_decel - 0.5 * A * (t_decel**2))
            
    time_array = np.linspace(0, T_one_way, n_half)
    pos_half = np.array([pos_at_time(t) for t in time_array])
    return pos_half[::-1] # 다가오는 구간 (50 -> 0)

ref_file = file_list[-1]
df_ref = pd.read_csv(ref_file)
peak_idx_ref = df_ref['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax()
N_half = len(df_ref) - peak_idx_ref

proximity_x = get_proximity_array_half(N_half)
total_len = len(proximity_x)

df0 = pd.read_csv(file_list[0])
peak0 = df0['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax()
start0 = max(0, peak0 - N_half + 1)
L0 = df0['Channel 1'].iloc[start0:start0+50].mean()
R0 = df0['Channel 2'].iloc[start0:start0+50].mean() 

plot_data = []
for file in file_list:
    try:
        df = pd.read_csv(file)
        smoothed = df['Channel 1'].rolling(20, center=True, min_periods=1).mean()
        peak_idx = smoothed.idxmax()
        
        start_idx = peak_idx - N_half + 1
        
        if start_idx < 0:
            continue
            
        ldc_raw = df['Channel 1'].values[start_idx:peak_idx+1]
        r_raw = df['Channel 2'].values[start_idx:peak_idx+1] 
        
        ldc_pct = ((L0 / ldc_raw)**2 - 1.0) * 100.0
        r_pct = ((r_raw - R0) / R0) * 100.0
        strain_val = extract_number(file)
        
        plot_data.append({'strain': strain_val, 'ldc_pct': ldc_pct, 'r_pct': r_pct})
    except Exception as e:
        pass

plot_data.sort(key=lambda x: x['strain'])
strains = [d['strain'] for d in plot_data]
Z_ldc = np.array([d['ldc_pct'] for d in plot_data])
Z_r = np.array([d['r_pct'] for d in plot_data])
X = np.arange(total_len)
Y = strains              

fig, axes = plt.subplots(1, 3, figsize=(22, 6))

# --- Graph 1: Inductance Heatmap ---
c1 = axes[0].pcolormesh(X, Y, Z_ldc, shading='auto', cmap='Reds')
axes[0].set_title('Graph 1: Inductance Change', fontsize=14)
fig.colorbar(c1, ax=axes[0], label='\u0394L / L0 (%)')

# --- Graph 2: Resistance Heatmap ---
c2 = axes[1].pcolormesh(X, Y, Z_r, shading='auto', cmap='Greens')
axes[1].set_title('Graph 2: Resistance Change', fontsize=14)
fig.colorbar(c2, ax=axes[1], label='\u0394R / R0 (%)')

# --- Graph 3: Overlapped Contours (1% 선, 5% 라벨, 테두리 유지, 작은 글씨/bold 제거) ---
# 음수 포함 1% 단위 배열 생성
min_pct = np.floor(min(Z_ldc.min(), Z_r.min()))
max_pct = np.ceil(max(Z_ldc.max(), Z_r.max()))
levels_1pct = np.arange(min_pct, max_pct + 1, 1)

# 라벨용 5% 단위 추출
levels_5pct = [lvl for lvl in levels_1pct if lvl % 5 == 0]

# 등고선을 1% 간격으로 렌더링
cs1 = axes[2].contour(X, Y, Z_ldc, levels=levels_1pct, colors='red', alpha=0.6, linewidths=1.2)
cs2 = axes[2].contour(X, Y, Z_r, levels=levels_1pct, colors='green', alpha=0.6, linewidths=1.2)

# 인덕턴스 라벨 (빨간 글씨 + 검은 테두리, 작게)
texts1 = axes[2].clabel(cs1, levels=levels_5pct, inline=True, fontsize=9, fmt='%1.0f%%')
for txt in texts1:
    txt.set_color('red')
    txt.set_rotation(0)
    # 폰트가 작아졌으므로 테두리 두께도 1.5로 줄임 (기존 2.5)
    txt.set_path_effects([PathEffects.withStroke(linewidth=1.5, foreground='white')])

# 저항 라벨 (초록(lime) 글씨 + 검은 테두리, 작게)
texts2 = axes[2].clabel(cs2, levels=levels_5pct, inline=True, fontsize=9, fmt='%1.0f%%')
for txt in texts2:
    txt.set_color('green')
    txt.set_rotation(0)
    txt.set_path_effects([PathEffects.withStroke(linewidth=1.5, foreground='white')])

from matplotlib.lines import Line2D
custom_lines = [Line2D([0], [0], color='red', lw=2), Line2D([0], [0], color='green', lw=2)]
axes[2].legend(custom_lines, ['Inductance', 'Resistance'])
axes[2].set_title('Graph 3: Overlapped Contours', fontsize=14)

# X축 눈금 설정 (0mm가 왼쪽, 50mm가 오른쪽)
xticks = [0, total_len // 2, total_len - 1]
xticklabels = ['50', '25', '0']

for ax in axes:
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels)
    ax.invert_xaxis()
    ax.set_xlabel('Proximity (mm)', fontsize=12)
    ax.set_ylabel('Strain (%)', fontsize=12)

plt.tight_layout()
plt.show()