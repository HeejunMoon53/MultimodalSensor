import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import glob
import re

# 1. 파일명에서 숫자 추출
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
    
    # 50mm -> 0mm -> 50mm
    proximity = np.concatenate((pos_half[::-1], pos_half[1:]))
    return proximity

# 3. 데이터 자르기 기준 (N_half) 구하기
ref_file = file_list[-1]
df_ref = pd.read_csv(ref_file)
# 정렬을 위한 피크점은 가장 변화가 뚜렷한 Channel 1(LDC)을 사용
peak_idx_ref = df_ref['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax()
N_half = len(df_ref) - peak_idx_ref

proximity_x = get_proximity_array(N_half)
total_len = len(proximity_x)

# 4. 초기값 (Baseline) 추출 (strain0.txt 사용)
df0 = pd.read_csv(file_list[0])
peak0 = df0['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax()
start0 = max(0, peak0 - N_half + 1)

R2_0 = df0['Channel 2'].iloc[start0:start0+50].mean() # 필터된 저항 초기값
R4_0 = df0['Channel 4'].iloc[start0:start0+50].mean() # 원본(Raw) 저항 초기값

print(f"✅ Baseline 산출 -> Ch2_Filtered_0: {R2_0:.2f}, Ch4_Raw_0: {R4_0:.2f}")

# 5. 데이터 처리 및 변화율(%) 계산
plot_data = []
for file in file_list:
    try:
        df = pd.read_csv(file)
        
        # 피크 기준점 탐색 (정렬용)
        smoothed = df['Channel 1'].rolling(20, center=True, min_periods=1).mean()
        peak_idx = smoothed.idxmax()
        
        start_idx = peak_idx - N_half + 1
        end_idx = peak_idx + N_half
        
        if start_idx < 0 or end_idx > len(df):
            continue
            
        r2_filtered = df['Channel 2'].values[start_idx:end_idx]
        r4_raw = df['Channel 4'].values[start_idx:end_idx] 
        
        # 변화율(%) 계산
        r2_pct = ((r2_filtered - R2_0) / R2_0) * 100.0
        r4_pct = ((r4_raw - R4_0) / R4_0) * 100.0 
        
        strain_val = extract_number(file)
        strain_y = np.full(total_len, strain_val)
        
        plot_data.append({
            'strain': strain_y,
            'proximity': proximity_x,
            'r2_pct': r2_pct,
            'r4_pct': r4_pct
        })
    except Exception as e:
        print(f"❌ Error reading {file}: {e}")

# --- [추가됨] 축 범위 통일을 위한 Global Min/Max 계산 ---
all_prox = np.concatenate([d['proximity'] for d in plot_data])
all_strain = np.concatenate([d['strain'] for d in plot_data])
all_r2 = np.concatenate([d['r2_pct'] for d in plot_data])
all_r4 = np.concatenate([d['r4_pct'] for d in plot_data])

x_min, x_max = all_prox.min(), all_prox.max()
y_min, y_max = all_strain.min(), all_strain.max()
# Z축은 노이즈가 심한 Raw 데이터(R4)와 Filtered 데이터(R2) 중 가장 작고/큰 값을 기준으로 설정
z_min = min(all_r2.min(), all_r4.min())
z_max = max(all_r2.max(), all_r4.max())

# 그래프 상단/하단 여백 약간 추가 (5%)
z_margin = (z_max - z_min) * 0.05
z_min -= z_margin
z_max += z_margin

# 축 범위를 똑같이 설정해주는 헬퍼 함수
def set_identical_axes(ax):
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_zlim(z_min, z_max)
    ax.set_xlabel('Proximity (mm)')
    ax.set_ylabel('Strain (mm)')
    ax.set_zlabel('\u0394R / R0 (%)')
# ----------------------------------------------------

# 6. 3D 시각화 (1x3 배열로 Raw, Filtered, Overlapped 비교)
fig = plt.figure(figsize=(24, 8)) 

# --- Graph 1: Channel 4 (Raw Resistance) ---
ax1 = fig.add_subplot(131, projection='3d')
for d in plot_data:
    ax1.plot(d['proximity'], d['strain'], d['r4_pct'], color='lightgreen', alpha=0.8)
ax1.set_title('Graph 1: Channel 4 (Raw Resistance %)')
set_identical_axes(ax1)

# --- Graph 2: Channel 2 (Filtered Resistance) ---
ax2 = fig.add_subplot(132, projection='3d')
for d in plot_data:
    ax2.plot(d['proximity'], d['strain'], d['r2_pct'], color='darkgreen', alpha=0.8)
ax2.set_title('Graph 2: Channel 2 (Filtered Resistance %)')
set_identical_axes(ax2)

# --- Graph 3: Overlapped Comparison ---
ax3 = fig.add_subplot(133, projection='3d')
for d in plot_data:
    # 필터링 전(연한 녹색)과 후(진한 녹색)를 겹쳐 그림
    ax3.plot(d['proximity'], d['strain'], d['r4_pct'], color='lightgreen', alpha=0.5)
    ax3.plot(d['proximity'], d['strain'], d['r2_pct'], color='darkgreen', alpha=0.8)

from matplotlib.lines import Line2D
custom_lines = [Line2D([0], [0], color='lightgreen', lw=2),
                Line2D([0], [0], color='darkgreen', lw=2)]
ax3.legend(custom_lines, ['Ch4: Raw', 'Ch2: Filtered'])
ax3.set_title('Graph 3: Filtering Effect Comparison')
set_identical_axes(ax3)

plt.tight_layout()
plt.show()