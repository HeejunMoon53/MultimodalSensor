import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
import re

# 1. 파일명에서 숫자 추출 (예: strain12.txt -> 12)
def extract_number(filename):
    basename = os.path.basename(filename)
    match = re.search(r'\d+', basename)
    return int(match.group()) if match else -1

# 스크립트 실행 위치 기준 파일 탐색
script_dir = os.path.dirname(os.path.abspath(__file__))
file_pattern = os.path.join(script_dir, "strain*.txt")

file_list = sorted(glob.glob(file_pattern), key=extract_number)

if not file_list:
    print(f"❌ 에러: '{script_dir}' 폴더 안에서 strain*.txt 파일을 찾을 수 없습니다.")
    exit()
else:
    print(f"✅ 총 {len(file_list)}개의 파일을 찾았습니다.")

# 2. 비선형 가감속 거리 보정 함수
def get_proximity_array(n_half):
    V_max = 5.0 
    A = 2.5
    D_total = 50.0
    
    t_accel = V_max / A
    d_accel = 0.5 * A * (t_accel**2)
    d_coast = D_total - 2 * d_accel
    t_coast = d_coast / V_max
    T_one_way = t_accel + t_coast + t_accel
    
    def pos_at_time(t):
        if t <= t_accel:
            return 0.5 * A * (t**2)
        elif t <= t_accel + t_coast:
            return d_accel + V_max * (t - t_accel)
        else:
            t_decel = t - (t_accel + t_coast)
            return (d_accel + d_coast) + (V_max * t_decel - 0.5 * A * (t_decel**2))
            
    time_array = np.linspace(0, T_one_way, n_half)
    pos_half = np.array([pos_at_time(t) for t in time_array])
    
    # 50mm -> 0mm -> 50mm 배열 생성
    proximity = np.concatenate((pos_half[::-1], pos_half[1:]))
    return proximity

# 3. 데이터 자르기 기준 (N_half) 구하기
ref_file = file_list[-1]
df_ref = pd.read_csv(ref_file)
peak_idx_ref = df_ref['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax()
N_half = len(df_ref) - peak_idx_ref

proximity_x = get_proximity_array(N_half)
total_len = len(proximity_x)

# 4. 초기값 (Baseline L0, R0) 추출 (strain0.txt 사용)
df0 = pd.read_csv(file_list[0])
peak0 = df0['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax()
start0 = max(0, peak0 - N_half + 1)

L0 = df0['Channel 1'].iloc[start0:start0+50].mean()
R0 = df0['Channel 2'].iloc[start0:start0+50].mean() 
print(f"✅ Baseline 산출 완료 -> L0: {L0:.2f}, R0: {R0:.2f}")

# 5. 데이터 처리 및 2D 매트릭스화
plot_data = []
for file in file_list:
    try:
        df = pd.read_csv(file)
        
        smoothed = df['Channel 1'].rolling(20, center=True, min_periods=1).mean()
        peak_idx = smoothed.idxmax()
        
        start_idx = peak_idx - N_half + 1
        end_idx = peak_idx + N_half
        
        if start_idx < 0 or end_idx > len(df):
            continue
            
        ldc_raw = df['Channel 1'].values[start_idx:end_idx]
        r_raw = df['Channel 2'].values[start_idx:end_idx] 
        
        # 변화율(%) 변환
        ldc_pct = ((L0 / ldc_raw)**2 - 1.0) * 100.0
        r_pct = ((r_raw - R0) / R0) * 100.0
        
        strain_val = extract_number(file)
        
        plot_data.append({
            'strain': strain_val, # 스칼라 값 저장 (정렬 및 Y축용)
            'ldc_pct': ldc_pct,
            'r_pct': r_pct
        })
    except Exception as e:
        print(f"❌ Error reading {file}: {e}")

# 데이터를 Strain 크기 순으로 정렬 (Y축이 아래에서 위로 정상적으로 커지도록)
plot_data.sort(key=lambda x: x['strain'])

# 2D 맵핑을 위한 그리드 데이터 추출
strains = [d['strain'] for d in plot_data]
Z_ldc = np.array([d['ldc_pct'] for d in plot_data])
Z_r = np.array([d['r_pct'] for d in plot_data])

X = np.arange(total_len) # X축 (시간/순서 흐름)
Y = strains              # Y축 (Strain)

# 6. 2D 색깔맵(Heatmap) 시각화
fig, axes = plt.subplots(1, 3, figsize=(22, 6))

# --- Graph 1: Inductance Heatmap (Reds) ---
# cmap='Reds'는 값이 클수록 진한 붉은색을 띱니다.
c1 = axes[0].pcolormesh(X, Y, Z_ldc, shading='auto', cmap='Reds')
axes[0].set_title('Graph 1: Inductance Change Map', fontsize=14)
fig.colorbar(c1, ax=axes[0], label='\u0394L / L0 (%)')

# --- Graph 2: Resistance Heatmap (Greens) ---
# cmap='Greens'는 값이 클수록 진한 녹색을 띱니다.
c2 = axes[1].pcolormesh(X, Y, Z_r, shading='auto', cmap='Greens')
axes[1].set_title('Graph 2: Resistance Change Map', fontsize=14)
fig.colorbar(c2, ax=axes[1], label='\u0394R / R0 (%)')

# --- Graph 3: Overlapped Contours ---
# 두 Heatmap을 깔끔하게 겹치기 위해 등고선(Contour)을 사용
cs1 = axes[2].contour(X, Y, Z_ldc, levels=8, colors='red', alpha=0.7, linewidths=2)
cs2 = axes[2].contour(X, Y, Z_r, levels=8, colors='green', alpha=0.7, linewidths=2)

from matplotlib.lines import Line2D
custom_lines = [Line2D([0], [0], color='red', lw=2),
                Line2D([0], [0], color='green', lw=2)]
axes[2].legend(custom_lines, ['Inductance', 'Resistance'])
axes[2].set_title('Graph 3: Overlapped Responses (Contours)', fontsize=14)

# 공통 X, Y축 설정 (Proximity 이동 표시)
mid_idx = total_len // 2
# X축 눈금을 5등분하여 Proximity 거리로 매핑
xticks = [0, mid_idx // 2, mid_idx, mid_idx + (total_len - mid_idx) // 2, total_len - 1]
xticklabels = ['50', '25', '0', '25', '50']

for ax in axes:
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels)
    ax.set_xlabel('Proximity (mm) [ Approach \u2192 0 \u2192 Retract ]', fontsize=12)
    ax.set_ylabel('Strain (%)', fontsize=12)

plt.tight_layout()
plt.show()