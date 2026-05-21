import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import glob
import re

# 1. 파일명에서 숫자 추출 (예: strain12.txt -> 12)
def extract_number(filename):
    # 경로를 제외한 순수 파일명에서 숫자만 추출
    basename = os.path.basename(filename)
    match = re.search(r'\d+', basename)
    return int(match.group()) if match else -1

# [수정] 스크립트가 실행되는 위치를 자동으로 찾아 절대 경로로 변환 (경로 오류 원천 차단)
script_dir = os.path.dirname(os.path.abspath(__file__))
file_pattern = os.path.join(script_dir, "strain*.txt")

file_list = sorted(glob.glob(file_pattern), key=extract_number)

# 파일이 제대로 찾아졌는지 확인
if not file_list:
    print(f"❌ 에러: '{script_dir}' 폴더 안에서 strain*.txt 파일을 찾을 수 없습니다.")
    print("스크립트 파일과 txt 파일들이 같은 폴더에 있는지 확인해 주세요.")
    exit()
else:
    print(f"✅ 총 {len(file_list)}개의 파일을 찾았습니다. 데이터 처리를 시작합니다...")

# 2. 비선형 가감속 거리 보정 함수 (AccelStepper Kinematics)
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
ref_file = file_list[-1] # 자동으로 가장 마지막 번호의 파일을 기준(ref)으로 삼음
df_ref = pd.read_csv(ref_file)
peak_idx_ref = df_ref['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax()
N_half = len(df_ref) - peak_idx_ref

proximity_x = get_proximity_array(N_half)
total_len = len(proximity_x)

# 4. 초기값 (Baseline L0, R0) 추출 (strain0.txt 사용)
df0 = pd.read_csv(file_list[0]) # 첫 번째 파일 (strain0.txt)
peak0 = df0['Channel 1'].rolling(20, center=True, min_periods=1).mean().idxmax()
start0 = max(0, peak0 - N_half + 1)

# 50mm 근방의 평균값을 초기값으로 안정적으로 확보
L0 = df0['Channel 1'].iloc[start0:start0+50].mean()
# [수정 완료] 저항값이 Channel 2에 있으므로 Channel 2 사용
R0 = df0['Channel 2'].iloc[start0:start0+50].mean() 
print(f"✅ Baseline 산출 완료 -> L0: {L0:.2f}, R0: {R0:.2f}")

# 5. 데이터 처리 및 변화율(%) 계산
plot_data = []
for file in file_list:
    try:
        df = pd.read_csv(file)
        
        # 피크 탐색 (0mm 지점)
        smoothed = df['Channel 1'].rolling(20, center=True, min_periods=1).mean()
        peak_idx = smoothed.idxmax()
        
        start_idx = peak_idx - N_half + 1
        end_idx = peak_idx + N_half
        
        # 길이가 부족한 에러 파일은 건너뜀
        if start_idx < 0 or end_idx > len(df):
            print(f"⚠️ {os.path.basename(file)}: 데이터 길이가 짧아 제외합니다.")
            continue
            
        ldc_raw = df['Channel 1'].values[start_idx:end_idx]
        # [수정 완료] 저항 채널을 원본(Channel 2)으로 맞춤
        r_raw = df['Channel 2'].values[start_idx:end_idx] 
        
        # --- 변화율(%) 변환 ---
        # 인덕턴스(L) 변화율 (%) : L ∝ 1/f^2 공식을 이용
        ldc_pct = ((L0 / ldc_raw)**2 - 1.0) * 100.0
        
        # 저항(R) 변화율 (%)
        r_pct = ((r_raw - R0) / R0) * 100.0
        
        strain_val = extract_number(file) # 0, 1, ..., 36
        strain_y = np.full(total_len, strain_val)
        
        plot_data.append({
            'strain': strain_y,
            'proximity': proximity_x,
            'ldc_pct': ldc_pct,
            'r_pct': r_pct
        })
    except Exception as e:
        print(f"❌ Error reading {file}: {e}")

# 6. 3D 시각화 (3개 그래프)
fig = plt.figure(figsize=(20, 7))

# --- Graph 1: Inductance Change (%) ---
ax1 = fig.add_subplot(131, projection='3d')
for d in plot_data:
    ax1.plot(d['proximity'], d['strain'], d['ldc_pct'], color='red', alpha=0.6)
ax1.set_title('Graph 1: Inductance Change')
ax1.set_xlabel('Proximity (mm)')
ax1.set_ylabel('Strain (%)')
ax1.set_zlabel('\u0394L / L0 (%)')

# --- Graph 2: Resistance Change (%) ---
ax2 = fig.add_subplot(132, projection='3d')
for d in plot_data:
    ax2.plot(d['proximity'], d['strain'], d['r_pct'], color='green', alpha=0.6)
ax2.set_title('Graph 2: Resistance Change')
ax2.set_xlabel('Proximity (mm)')
ax2.set_ylabel('Strain (%)')
ax2.set_zlabel('\u0394R / R0 (%)')

# --- Graph 3: Overlapped (%) ---
ax3 = fig.add_subplot(133, projection='3d')
for d in plot_data:
    ax3.plot(d['proximity'], d['strain'], d['ldc_pct'], color='red', alpha=0.5)
    ax3.plot(d['proximity'], d['strain'], d['r_pct'], color='green', alpha=0.5)

# 겹친 그래프 범례 생성
from matplotlib.lines import Line2D
custom_lines = [Line2D([0], [0], color='red', lw=2),
                Line2D([0], [0], color='green', lw=2)]
ax3.legend(custom_lines, ['Inductance Change', 'Resistance Change'])

ax3.set_title('Graph 3: Overlapped Responses')
ax3.set_xlabel('Proximity (mm)')
ax3.set_ylabel('Strain (%)')
ax3.set_zlabel('Change Ratio (%)')

plt.tight_layout()
plt.show()