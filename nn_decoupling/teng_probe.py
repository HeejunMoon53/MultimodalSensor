"""
teng_probe.py — TENG 신호 대역 분리 + 분류 테스트 (v2)
대역별 필터링 + FFT 스펙트럼 특징으로 접촉/압력/슬라이딩/진동을 구별

시리얼 포맷: ldc_raw, r_filtered, teng_filtered, r_raw, teng_raw  (115200 baud)
실행: C:/ml_env/Scripts/python teng_probe.py [COM포트]
"""
import sys, time
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.signal import butter, filtfilt, find_peaks, iirnotch
import serial, serial.tools.list_ports

# ── 설정 ─────────────────────────────────────────────────────────────────────
BAUD         = 115200
FS           = 100          # 샘플링 주파수 (Hz)
TENG_COL     = 4            # teng_raw 열 인덱스
RECORD_SEC   = 3.0          # 동작당 녹화 시간
N_REPS       = 3            # 반복 횟수

# 대역 정의 (Hz) — Nyquist = 50Hz
BAND_SLIDE   = (0.5,  8.0)  # 손 움직임 / 슬라이딩
BAND_VIB     = (8.0, 45.0)  # 진동 / 빠른 문지름
FILT_ORDER   = 2            # 저주파 안정성을 위해 2차

# 전원 노이즈 노치 필터
AUTO_NOTCH   = True   # none 녹화에서 피크 자동 검출 후 적용
NOTCH_Q      = 8.0    # 품질 계수: 낮을수록 대역폭 넓음 (f0/Q Hz)
NOTCH_N_PEAK = 4      # 검출할 최대 피크 수
NOTCH_MIN_HZ = 5.0    # 이 주파수 이하는 무시 (DC/슬라이드 대역 보호)

# Catppuccin Mocha
C = {
    "bg":    "#1e1e2e", "bg2": "#181825", "bg3": "#313244",
    "text":  "#cdd6f4", "text2": "#a6adc8",
    "blue":  "#89b4fa", "green": "#a6e3a1", "yellow": "#f9e2af",
    "mauve": "#cba6f7", "red":   "#f38ba8", "teal":   "#94e2d5",
    "peach": "#fab387", "sky":   "#89dceb", "pink":   "#f5c2e7",
}

# ── 동작 정의 ─────────────────────────────────────────────────────────────────
ACTIONS = [
    ("none",
     "손을 센서에서 15cm 이상 멀리 두세요\n   아무것도 하지 마세요",
     "모든 대역 낮음 (baseline)"),

    ("tap",
     "손가락 끝으로 센서를 한 번 가볍게 탭 하고\n   즉시 떼세요",
     "임펄스 대역 → 짧은 스파이크"),

    ("press",
     "손바닥/손가락을 센서에 천천히 대고\n   3초간 꾹 누르고 유지하세요",
     "초기 스파이크 → 침묵 (전반부 에너지 집중)"),

    ("slide",
     "손가락을 센서 위에 댄 채로\n   5cm 구간을 천천히 왕복 슬라이드 (2~3회)",
     "저주파 AC (0.5~8Hz 대역)"),

    ("vibration",
     "손가락 끝이나 손톱으로 센서 표면을\n   빠르게 문지르세요 (긁듯이)",
     "중주파 대역 (8~45Hz)"),

    ("flick",
     "손가락으로 센서 기판 가장자리를\n   가볍게 튕기세요 (딱 한번)",
     "고주파 링잉 → 감쇠 진동"),
]

ACT_COLORS = ["blue", "green", "yellow", "mauve", "teal", "peach"]

# ── 시리얼 ────────────────────────────────────────────────────────────────────

def find_port():
    ports = serial.tools.list_ports.comports()
    stm = [p for p in ports if any(k in p.description.upper()
           for k in ('STM', 'ST-LINK', 'USB SERIAL', 'USB2UART', 'CP210', 'CH340'))]
    return (stm or ports or [None])[0]

def open_serial(port=None):
    if port is None:
        dev = find_port()
        port = dev.device if dev else None
    if port is None:
        print("  [오류] 포트를 찾지 못했습니다. python teng_probe.py COM3")
        sys.exit(1)
    ser = serial.Serial(port, BAUD, timeout=0.05)
    ser.reset_input_buffer()
    print(f"  포트: {port} @ {BAUD} baud")
    return ser

def parse(line):
    try:
        v = [float(x) for x in line.strip().split(',')]
        return v if len(v) >= 5 else None
    except Exception:
        return None

def record(ser, duration):
    buf = []
    ser.reset_input_buffer()
    t_end = time.time() + duration
    while time.time() < t_end:
        vals = parse(ser.readline().decode('utf-8', errors='ignore'))
        if vals:
            buf.append(vals[TENG_COL])
    return np.array(buf, dtype=np.float32)

# ── 신호 처리 ─────────────────────────────────────────────────────────────────

def remove_dc(data):
    return data - np.median(data)

def bandpass(data, lo, hi, fs=FS, order=FILT_ORDER):
    nyq = fs / 2.0
    lo_n, hi_n = lo / nyq, hi / nyq
    lo_n = max(lo_n, 1e-4)
    hi_n = min(hi_n, 0.999)
    if lo_n >= hi_n:
        return np.zeros_like(data)
    try:
        b, a = butter(order, [lo_n, hi_n], btype='band')
        return filtfilt(b, a, data)
    except Exception:
        return np.zeros_like(data)

def detect_noise_freqs(data_list, fs=FS):
    """none 녹화 목록에서 노이즈 피크 주파수를 자동 검출."""
    combined = np.concatenate([remove_dc(d) for d in data_list])
    freqs, amps = compute_fft(combined)
    mask = (freqs >= NOTCH_MIN_HZ) & (freqs < fs / 2 - 0.5)
    if not mask.any():
        return []
    fa, aa = freqs[mask], amps[mask]
    threshold = aa.mean() + aa.std() * 2.0
    peaks, _ = find_peaks(aa, height=threshold, distance=3)
    if len(peaks) == 0:
        return []
    top = sorted(peaks, key=lambda p: -aa[p])[:NOTCH_N_PEAK]
    return sorted([float(fa[p]) for p in top])

def apply_notch(data, notch_freqs, fs=FS):
    """notch_freqs에 지정된 주파수를 제거."""
    if not notch_freqs:
        return data
    out = data.astype(np.float64).copy()
    for f0 in notch_freqs:
        if 0 < f0 < fs / 2:
            b, a = iirnotch(f0, NOTCH_Q, fs)
            out = filtfilt(b, a, out)
    return out.astype(np.float32)

def highpass(data, cutoff, fs=FS, order=FILT_ORDER):
    nyq = fs / 2.0
    b, a = butter(order, cutoff / nyq, btype='high')
    return filtfilt(b, a, data)

def compute_fft(data, fs=FS):
    n     = len(data)
    freqs = np.fft.rfftfreq(n, d=1/fs)
    amps  = np.abs(np.fft.rfft(data)) / n * 2
    return freqs, amps

def band_power(freqs, amps, lo, hi):
    mask = (freqs >= lo) & (freqs <= hi)
    return float(np.sum(amps[mask] ** 2)) if mask.any() else 0.0

# ── 특징 추출 ─────────────────────────────────────────────────────────────────

def extract_features(data):
    """12개 특징: 시간 도메인 4 + 주파수 도메인 8"""
    if len(data) < 20:
        return {k: 0.0 for k in [
            'rms', 'max_abs', 'energy_ratio', 'impulse_rms',
            'slide_power', 'vib_power', 'dominant_freq',
            'spectral_entropy', 'slide_ratio', 'vib_ratio',
            'n_vib_peaks', 'zc_rate']}

    d = remove_dc(data)

    # ── 시간 도메인 ──────────────────────────────────────────────────────────
    rms     = float(np.sqrt(np.mean(d ** 2)))
    max_abs = float(np.max(np.abs(d)))

    # 에너지 비율: 전반부 vs 전체 (press 패턴 = 1에 가까움)
    mid = len(d) // 2
    e1  = float(np.mean(d[:mid] ** 2)) + 1e-9
    e2  = float(np.mean(d[mid:] ** 2)) + 1e-9
    energy_ratio = e1 / (e1 + e2)

    # 임펄스 RMS (하이패스 8Hz → 고주파 에너지)
    imp = highpass(d, 8.0)
    impulse_rms = float(np.sqrt(np.mean(imp ** 2)))

    # ── 주파수 도메인 ─────────────────────────────────────────────────────────
    freqs, amps = compute_fft(d)

    slide_power = band_power(freqs, amps, *BAND_SLIDE)
    vib_power   = band_power(freqs, amps, *BAND_VIB)
    total_power = band_power(freqs, amps, 0.1, 45) + 1e-9
    slide_ratio = slide_power / total_power
    vib_ratio   = vib_power   / total_power

    # 지배 주파수 (0.5~45Hz 구간)
    mask = (freqs >= 0.5) & (freqs <= 45)
    if mask.any():
        dominant_freq = float(freqs[mask][np.argmax(amps[mask])])
    else:
        dominant_freq = 0.0

    # 스펙트럼 엔트로피 (에너지 분포 균일성: 높을수록 광대역)
    p = amps[mask] ** 2 + 1e-12
    p /= p.sum()
    spectral_entropy = float(-np.sum(p * np.log2(p)))

    # 진동 대역 피크 수
    vib_sig = bandpass(d, *BAND_VIB)
    thr = max(np.std(vib_sig) * 2, 1e-3)
    vib_peaks, _ = find_peaks(np.abs(vib_sig), height=thr, distance=3)
    n_vib_peaks = float(len(vib_peaks))

    # 영점 교차율 (단위: 초당 교차 횟수)
    zc_rate = float(np.sum(np.diff(np.sign(d)) != 0)) / (len(d) / FS)

    return {
        'rms':              rms,
        'max_abs':          max_abs,
        'energy_ratio':     energy_ratio,
        'impulse_rms':      impulse_rms,
        'slide_power':      slide_power,
        'vib_power':        vib_power,
        'dominant_freq':    dominant_freq,
        'spectral_entropy': spectral_entropy,
        'slide_ratio':      slide_ratio,
        'vib_ratio':        vib_ratio,
        'n_vib_peaks':      n_vib_peaks,
        'zc_rate':          zc_rate,
    }

FEAT_LABELS = {
    'rms':              'RMS',
    'max_abs':          'Max |amp|',
    'energy_ratio':     'Energy Ratio\n(front/total)',
    'impulse_rms':      'Impulse RMS\n(>8Hz)',
    'slide_power':      'Slide Power\n(0.5-8Hz)',
    'vib_power':        'Vibration Power\n(8-45Hz)',
    'dominant_freq':    'Dominant Freq\n(Hz)',
    'spectral_entropy': 'Spectral\nEntropy',
    'slide_ratio':      'Slide Ratio',
    'vib_ratio':        'Vib Ratio',
    'n_vib_peaks':      'Vib Peaks\n(count)',
    'zc_rate':          'ZC Rate\n(/s)',
}

# ── 분류 ─────────────────────────────────────────────────────────────────────

def classify_loo(all_feats, all_labels):
    """Leave-One-Out Nearest Centroid, 정규화된 특징 공간에서."""
    keys    = sorted(all_feats[0].keys())
    act_ids = list(dict.fromkeys(all_labels))
    mat     = np.array([[f[k] for k in keys] for f in all_feats])

    # min-max 정규화
    vmin  = mat.min(0); vmax = mat.max(0)
    denom = np.where(vmax - vmin > 1e-9, vmax - vmin, 1.0)
    mat_n = (mat - vmin) / denom

    preds = []
    for i in range(len(mat_n)):
        templates = {}
        for act in act_ids:
            idxs = [j for j, l in enumerate(all_labels) if l == act and j != i]
            templates[act] = mat_n[idxs].mean(0) if idxs else mat_n[i]
        dists = {a: float(np.linalg.norm(templates[a] - mat_n[i])) for a in act_ids}
        pred = min(dists, key=dists.get)
        preds.append((all_labels[i], pred, all_labels[i] == pred))

    acc = sum(ok for _, _, ok in preds) / len(preds)
    return acc, preds

def judge(acc, n):
    chance = 1.0 / n
    if   acc >= 0.85:              return "우수 ✓ (분리 가능)",     C['green']
    elif acc >= 0.65:              return "보통 △ (일부 혼동)",     C['yellow']
    elif acc >= chance + 0.1:      return "불량 ✗ (신호 불안정)",   C['peach']
    else:                          return "불가 ✗✗ (무작위 수준)", C['red']

# ── 시각화 ────────────────────────────────────────────────────────────────────

def plot_all(recordings, raw_recs, feat_all, acc, preds, verdict, v_color):
    n_act = len(ACTIONS)
    colors = [C[c] for c in ACT_COLORS]
    act_ids = [a[0] for a in ACTIONS]
    t_ax = np.linspace(0, RECORD_SEC, int(RECORD_SEC * FS))

    plt.rcParams.update({
        'figure.facecolor': C['bg'], 'axes.facecolor': C['bg2'],
        'axes.edgecolor': C['text2'], 'text.color': C['text'],
        'xtick.color': C['text2'], 'ytick.color': C['text2'],
        'axes.labelcolor': C['text2'], 'grid.color': C['bg3'],
        'grid.linestyle': '--', 'grid.alpha': 0.5,
    })

    fig = plt.figure(figsize=(22, 18), facecolor=C['bg'])
    fig.suptitle('TENG 대역 분리 분류 테스트 — Claude 자동 판단',
                 fontsize=15, color=C['blue'], fontweight='bold', y=0.99)

    gs = gridspec.GridSpec(4, n_act, figure=fig,
                           hspace=0.6, wspace=0.35,
                           top=0.96, bottom=0.04)

    # ── 행 0: 원시 파형 (raw 흐릿 + 노치 후 선명) ────────────────────────────
    for i, (act_id, _, desc) in enumerate(ACTIONS):
        ax = fig.add_subplot(gs[0, i])
        for j, (raw, clean) in enumerate(zip(raw_recs.get(act_id, []),
                                              recordings.get(act_id, []))):
            n = min(len(raw), len(t_ax))
            ax.plot(t_ax[:n], remove_dc(raw[:n]),   color=colors[i],
                    alpha=0.18, linewidth=0.7)
            ax.plot(t_ax[:n], remove_dc(clean[:n]), color=colors[i],
                    alpha=0.5 + 0.5 * j / max(N_REPS-1, 1), linewidth=1.1)
        ax.set_title(act_id, fontsize=9, color=colors[i], fontweight='bold', pad=3)
        if i == 0:
            ax.set_ylabel('TENG\n(흐릿=raw, 선명=notch)', fontsize=6)
        ax.set_xlabel('s', fontsize=7); ax.grid(True); ax.tick_params(labelsize=6)

    # ── 행 1: FFT 스펙트럼 ────────────────────────────────────────────────────
    for i, (act_id, _, _) in enumerate(ACTIONS):
        ax = fig.add_subplot(gs[1, i])
        for j, rep in enumerate(recordings.get(act_id, [])):
            d = remove_dc(rep)
            freqs, amps = compute_fft(d)
            mask = freqs <= 50
            ax.plot(freqs[mask], amps[mask], color=colors[i],
                    alpha=0.4 + 0.6 * j / max(N_REPS-1, 1), linewidth=1.0)
        # 대역 표시
        ax.axvspan(*BAND_SLIDE, alpha=0.08, color=C['blue'],  label='slide')
        ax.axvspan(*BAND_VIB,   alpha=0.08, color=C['mauve'], label='vib')
        ax.set_title('FFT', fontsize=8, color=C['text2'], pad=2)
        if i == 0: ax.set_ylabel('Amplitude', fontsize=7)
        ax.set_xlabel('Hz', fontsize=7); ax.grid(True); ax.tick_params(labelsize=6)
        if i == 0:
            ax.legend(fontsize=5, loc='upper right',
                      facecolor=C['bg3'], edgecolor=C['bg3'])

    # ── 행 2: 대역 분리 파형 (마지막 rep 기준) ────────────────────────────────
    for i, (act_id, _, _) in enumerate(ACTIONS):
        ax = fig.add_subplot(gs[2, i])
        reps = recordings.get(act_id, [])
        if not reps:
            continue
        d = remove_dc(reps[-1])
        n = min(len(d), len(t_ax))
        d = d[:n]; tx = t_ax[:n]

        slide_sig = bandpass(d, *BAND_SLIDE)
        vib_sig   = bandpass(d, *BAND_VIB)
        imp_sig   = highpass(d, 8.0)

        ax.plot(tx, d,         color=colors[i],  alpha=0.25, linewidth=0.8, label='raw')
        ax.plot(tx, slide_sig, color=C['blue'],   alpha=0.9,  linewidth=1.2, label='slide')
        ax.plot(tx, vib_sig,   color=C['mauve'],  alpha=0.9,  linewidth=1.0, label='vib')
        ax.set_title('대역 분리', fontsize=8, color=C['text2'], pad=2)
        if i == 0:
            ax.set_ylabel('Band signals', fontsize=7)
            ax.legend(fontsize=5, loc='upper right',
                      facecolor=C['bg3'], edgecolor=C['bg3'])
        ax.set_xlabel('s', fontsize=7); ax.grid(True); ax.tick_params(labelsize=6)

    # ── 행 3: 핵심 특징 비교 4개 + 혼동 행렬 + 판정 ─────────────────────────
    key_feats = ['slide_power', 'vib_power', 'dominant_freq', 'energy_ratio']
    for fi, fkey in enumerate(key_feats):
        ax = fig.add_subplot(gs[3, fi])
        means, stds = [], []
        for act_id in act_ids:
            v = [f[fkey] for f in feat_all.get(act_id, [{}])]
            means.append(np.mean(v) if v else 0)
            stds.append(np.std(v) if len(v) > 1 else 0)
        ax.bar(range(n_act), means, color=colors, alpha=0.8, width=0.6)
        ax.errorbar(range(n_act), means, yerr=stds,
                    fmt='none', color=C['text2'], capsize=3, lw=1)
        ax.set_title(FEAT_LABELS[fkey], fontsize=8, color=C['text'], pad=3)
        ax.set_xticks(range(n_act))
        ax.set_xticklabels([a[0][:7] for a in ACTIONS], fontsize=6, rotation=35)
        ax.grid(True, axis='y'); ax.tick_params(labelsize=6)

    # 혼동 행렬
    ax_conf = fig.add_subplot(gs[3, 4])
    conf = np.zeros((n_act, n_act))
    for true_id, pred_id, _ in preds:
        if true_id in act_ids and pred_id in act_ids:
            conf[act_ids.index(true_id), act_ids.index(pred_id)] += 1
    row_sum = conf.sum(1, keepdims=True)
    conf_n  = np.where(row_sum > 0, conf / row_sum, 0)
    im = ax_conf.imshow(conf_n, cmap='Blues', vmin=0, vmax=1, aspect='auto')
    ax_conf.set_xticks(range(n_act)); ax_conf.set_yticks(range(n_act))
    sh = [a[0][:8] for a in ACTIONS]
    ax_conf.set_xticklabels(sh, fontsize=6, rotation=35)
    ax_conf.set_yticklabels(sh, fontsize=6)
    ax_conf.set_xlabel('예측', fontsize=7); ax_conf.set_ylabel('실제', fontsize=7)
    ax_conf.set_title(f'혼동 행렬  Acc={acc:.0%}', fontsize=8, color=C['teal'])
    for i in range(n_act):
        for j in range(n_act):
            clr = 'black' if conf_n[i, j] > 0.5 else C['text2']
            ax_conf.text(j, i, f'{conf_n[i,j]:.1f}',
                         ha='center', va='center', fontsize=6, color=clr)
    plt.colorbar(im, ax=ax_conf, fraction=0.04, pad=0.02)

    # 판정 텍스트
    ax_j = fig.add_subplot(gs[3, 5])
    ax_j.set_facecolor(C['bg2']); ax_j.axis('off')
    lines = [
        ("Claude 판정", C['blue'],   11, 'bold'),
        ("", C['text'], 8, 'normal'),
        (verdict,       v_color,     12, 'bold'),
        (f"Acc = {acc:.1%}", C['yellow'], 11, 'bold'),
        ("", C['text'], 7, 'normal'),
    ]
    for true_id, pred_id, ok in preds:
        icon  = "✓" if ok else "✗"
        color = C['green'] if ok else C['red']
        lines.append((f"{icon} {true_id[:7]:<8}→{pred_id[:8]}", color, 7, 'normal'))
    y = 0.97
    for txt, clr, sz, wt in lines:
        ax_j.text(0.04, y, txt, transform=ax_j.transAxes,
                  fontsize=sz, color=clr, fontweight=wt,
                  va='top', fontfamily='monospace')
        y -= (sz + 1.5) * 0.022

    plt.savefig('teng_probe_result.png', dpi=130,
                bbox_inches='tight', facecolor=C['bg'])
    print("  → teng_probe_result.png 저장")
    plt.show()

# ── 메인 ─────────────────────────────────────────────────────────────────────

def countdown(sec, prefix=""):
    for i in range(sec, 0, -1):
        print(f"\r  {prefix}{i}초... ", end='', flush=True)
        time.sleep(1)
    print(f"\r  ▶ 녹화!           ", end='', flush=True)

def run(ser):
    recordings = {}   # 노치 필터 후 신호
    raw_recs   = {}   # 원본 신호 (시각화용)
    feat_all   = {}

    print()
    print("=" * 62)
    print("  TENG 대역 분리 분류 테스트  (v2)")
    print(f"  동작 {len(ACTIONS)}종  ×  {N_REPS}회  ×  {RECORD_SEC}s")
    print(f"  대역: slide {BAND_SLIDE}Hz  |  vib {BAND_VIB}Hz")
    print("=" * 62)
    input("\n  [Enter]로 시작 → ")

    active_notch = []  # run 중 확정된 노치 주파수

    for idx, (act_id, instruction, desc) in enumerate(ACTIONS):
        recordings[act_id] = []
        raw_recs[act_id]   = []
        feat_all[act_id]   = []
        print()
        print(f"{'─'*62}")
        print(f"  [{idx+1}/{len(ACTIONS)}] {act_id.upper()}")
        print(f"  예상: {desc}")
        print()
        for line in instruction.split('\n'):
            print(f"  >> {line.strip()}")
        print()

        for rep in range(N_REPS):
            input(f"  [Enter] {rep+1}/{N_REPS}회 준비 →")
            countdown(3, f"  ({rep+1}/{N_REPS}) ")
            print(f" ← {RECORD_SEC}s 동작 →", flush=True)
            data_raw = record(ser, RECORD_SEC)
            print(f"\r  ■ {len(data_raw)}샘플              ")

            if len(data_raw) < 10:
                data_raw = np.zeros(int(RECORD_SEC * FS))
                print("  [경고] 샘플 부족 — 연결 확인")

            raw_recs[act_id].append(data_raw)

        # none 녹화 완료 → 노이즈 주파수 자동 검출
        if act_id == 'none' and AUTO_NOTCH:
            active_notch = detect_noise_freqs(raw_recs['none'])
            if active_notch:
                print(f"\n  ★ 자동 검출 노이즈: {[f'{f:.1f}Hz' for f in active_notch]}"
                      f"  Q={NOTCH_Q}  BW≈{[f'{f/NOTCH_Q:.1f}Hz' for f in active_notch]}")
                # none 녹화도 소급 적용
                recordings['none'] = [apply_notch(d, active_notch) for d in raw_recs['none']]
                feat_all['none']   = [extract_features(d) for d in recordings['none']]
            else:
                print("\n  [주의] 뚜렷한 노이즈 피크 없음 — 노치 미적용")
                recordings['none'] = list(raw_recs['none'])
                feat_all['none']   = [extract_features(d) for d in recordings['none']]
            continue  # 이미 처리 완료

        # none 이외: active_notch 적용
        for data_raw in raw_recs[act_id]:
            data = apply_notch(data_raw, active_notch) if active_notch else data_raw.copy()
            recordings[act_id].append(data)
            feat = extract_features(data)
            feat_all[act_id].append(feat)

            # 즉시 피드백
            freqs_r, amps_r = compute_fft(remove_dc(data_raw))
            freqs_c, amps_c = compute_fft(remove_dc(data))
            dom_mask = (freqs_c >= 0.5) & (freqs_c <= 45)
            dom_f = freqs_c[dom_mask][np.argmax(amps_c[dom_mask])] if dom_mask.any() else 0
            notch_info = ""
            for fn in active_notch:
                m = np.argmin(np.abs(freqs_r - fn))
                notch_info += f" | {fn:.1f}Hz: {amps_r[m]:.0f}→{amps_c[m]:.0f}"
            print(f"  slide={feat['slide_power']:.1f}  vib={feat['vib_power']:.1f}  "
                  f"dom={dom_f:.1f}Hz  ent={feat['spectral_entropy']:.2f}{notch_info}")

    # ── 분류 ─────────────────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  분석 중...")

    all_feats  = [f for act_id, _ in [(a[0], None) for a in ACTIONS]
                    for f in feat_all[act_id]]
    all_labels = [act_id for act_id, _ in [(a[0], None) for a in ACTIONS]
                  for _ in feat_all[act_id]]

    acc, preds = classify_loo(all_feats, all_labels)
    verdict, v_color = judge(acc, len(ACTIONS))

    print(f"\n  ★ {verdict}")
    print(f"  ★ 분류 정확도: {acc:.1%}  ({sum(ok for _,_,ok in preds)}/{len(preds)})")

    # 특징 중요도 (클래스 간 분산 / 전체)
    print()
    print("  특징 중요도:")
    feat_keys = sorted(all_feats[0].keys())
    mat = np.array([[f[k] for k in feat_keys] for f in all_feats])
    vmin = mat.min(0); vmax = mat.max(0)
    denom = np.where(vmax - vmin > 1e-9, vmax - vmin, 1.0)
    mat_n = (mat - vmin) / denom
    act_ids = [a[0] for a in ACTIONS]
    scores = []
    for fi, fk in enumerate(feat_keys):
        class_means = [mat_n[[j for j, l in enumerate(all_labels) if l == a], fi].mean()
                       for a in act_ids]
        bv = float(np.var(class_means))
        wv = float(mat_n[:, fi].var()) + 1e-9
        scores.append((fk, bv / wv))
    scores.sort(key=lambda x: -x[1])
    for fk, sc in scores[:8]:
        bar = "█" * int(sc * 25)
        print(f"  {fk:<20} {bar:<25} {sc:.3f}")

    print()
    print("  동작별:")
    for true_id, pred_id, ok in preds:
        print(f"  {'✓' if ok else '✗'} {true_id:<12} → {pred_id}")

    print()
    print("  플롯 생성 중...")
    plot_all(recordings, raw_recs, feat_all, acc, preds, verdict, v_color)

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else None
    print()
    print("=" * 62)
    print("  teng_probe.py v2 — 대역 분리 + FFT 분류")
    print("=" * 62)
    ser = open_serial(port)
    time.sleep(2)
    test = record(ser, 1.0)
    if len(test) < 5:
        print(f"  [경고] 1s에 {len(test)}샘플 — 펌웨어 확인 필요")
    else:
        print(f"  OK: 1s에 {len(test)}샘플 수신")
    try:
        run(ser)
    except KeyboardInterrupt:
        print("\n  [중단]")
    finally:
        ser.close()

if __name__ == '__main__':
    main()
