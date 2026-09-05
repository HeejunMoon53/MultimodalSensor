"""
gen_sequences.py
moe_realtime_monitor.py의 텍스트 시퀀스(G-code 스타일) 파일 2종을 생성한다:
    - train_dense_seq.txt   : 재학습용 촘촘한 데이터 수집 시퀀스
    - realtime_test_seq.txt : 재학습 후 실시간 검증용 짧은 시퀀스

물리적 가정 (실행 전 반드시 맞춰야 함):
    - YA/YB: 센서가 완전히 이완된 상태(변형률 0%)를 0mm으로 잡는다.
    - Z    : 물체(센서)에서 25mm 떨어진 "원위치"를 0mm으로 잡는다.
             즉 Z를 음의 방향으로 움직일수록 물체에 가까워지고, 눌러 들어간다.
    - 위 상태에서 모니터의 ZERO 버튼(또는 시퀀스의 첫 ZERO 명령)을 눌러 원점을
      잡은 뒤 시퀀스를 실행한다.

힘 측정 한계: Z=-1.2mm 부근에서 이미 ~10N에 도달하는 것을 확인했다(RFT 센서
실측 기준). 그 이상 누르지 않도록 압력 프로파일의 최대 press 깊이를 -1.2mm로
고정한다 (Z_FAR 대비 델타 -26.2mm).

train_dense_seq.txt 구성 (2026-08-16 밀도 상향):
    Block A  — discrete strain(10단계) x 압력 프로파일 5종(속도/정지 다양화)
               + 그 자리에서 근접도(비접촉) 연속 스윕을 3가지 속도로 반복
               (= "하나 discrete(strain) / 하나 continuous(Z), 여러 단계·속도")
    Block B  — discrete Z(6단계, 근접~접촉) x strain 연속 스윕을 3가지 속도로 반복
               (= 반대 방향: "하나 discrete(Z) / 하나 continuous(strain)")
    Block C  — strain·Z 동시 이동(대각선 왕복), 3가지 속도

실행: python nn_decoupling/test0816_RealtimeDecoupling/gen_sequences.py
"""

from pathlib import Path

HERE = Path(__file__).parent

SENSOR_L0 = 120.0
Z_FAR_TO_CONTACT = 25.0     # far(0) -> contact 까지 델타 크기(mm)
Z_MAX_PRESS_EXTRA = 1.2     # contact 이후 추가로 눌러 들어가는 깊이(mm) — 힘 10N 한계
Z_CONTACT_DELTA = -Z_FAR_TO_CONTACT                      # -25.0
Z_MAX_PRESS_DELTA = -(Z_FAR_TO_CONTACT + Z_MAX_PRESS_EXTRA)  # -26.2

# 인장 스트레인 단계 (YA=YB, mm) — strain% = |YA|*2/120*100
# 2mm 간격(이전 3mm 대비 촘촘하게) -> 0,3.3,6.7,...,30 %
STRAIN_STEPS_MM = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0]
STRAIN_MAX_MM = STRAIN_STEPS_MM[-1]

# 근접도 discrete 단계 (Z, far=0 기준 델타 누적) — 6단계, far~contact 균등 분할
Z_LEVEL_DELTAS = [0.0, -5.0, -5.0, -5.0, -5.0, -5.0]   # 누적: 0,-5,-10,-15,-20,-25

PRESS_SWEEP_SPEEDS = [3, 8, 15]     # Block A의 Z 연속 스윕 속도들 (mm/s)
STRAIN_SWEEP_SPEEDS = [3, 10, 20]   # Block B의 strain 연속 스윕 속도들 (mm/s)
DIAG_SPEED_PAIRS = [(4, 5.5), (8, 11), (15, 20)]   # Block C (strain_spd, z_spd)


def strain_pct(mm):
    return abs(mm) * 2.0 / SENSOR_L0 * 100.0


def header(title, extra=""):
    lines = [
        "# " + "=" * 70,
        f"# {title}",
        "#",
        "# 실행 전 물리적 준비:",
        "#   1) YA/YB: 센서가 완전히 이완된 상태(변형률 0%)로 맞춘다.",
        "#   2) Z    : 물체에서 약 25mm 떨어진 위치로 맞춘다.",
        "#   3) 모니터에서 ENABLE -> ZERO를 눌러 원점을 잡은 뒤 이 시퀀스를 실행한다.",
        "#      (아래 ZERO/ENABLE 명령은 안전을 위해 한 번 더 넣어뒀다.)",
        "#   4) Arduino/RFT 둘 다 연결돼 있어야 ground truth(YA_mm,Z_mm,Fz_act_N,",
        "#      strain_act_pct,value_act)가 정확히 기록된다.",
        "#",
        "# Z 부호 규약: 음수 = 물체 방향(누르는 방향). 최대 press 깊이는 -1.2mm",
        "# (= Z_FAR 대비 -26.2mm) — 이 부근에서 이미 ~10N에 도달함(RFT 실측 확인).",
    ]
    if extra:
        lines.append("#")
        lines.extend(f"# {l}" for l in extra.splitlines())
    lines.append("# " + "=" * 70)
    return "\n".join(lines) + "\n"


def press_profiles(indent="  "):
    """discrete strain 고정 상태에서: 다양한 속도 + 정지(hold)를 섞은 압력 프로파일 5종.
    각 프로파일은 Z 델타 합이 0이 되도록(= far로 복귀) 짜여 있어 이어붙이기 안전하다."""
    lines = []

    def block(name, body_lines):
        lines.append(f"{indent}# -- {name} --")
        lines.extend(f"{indent}{l}" for l in body_lines)

    block("slow_full: 느린 속도로 최대 깊이까지 눌러 2초 유지 (steady-state 포착용)", [
        f"MOVE Z={Z_MAX_PRESS_DELTA}@2",
        "WAIT 2000",
        f"MOVE Z={-Z_MAX_PRESS_DELTA}@2",
        "WAIT 300",
    ])
    block("med_hold: 중간 속도, 짧은 유지", [
        f"MOVE Z={Z_MAX_PRESS_DELTA}@6",
        "WAIT 800",
        f"MOVE Z={-Z_MAX_PRESS_DELTA}@6",
        "WAIT 300",
    ])
    block("fast_full: 빠른 속도, 유지 없음 (모델 반응 지연 확인용)", [
        f"MOVE Z={Z_MAX_PRESS_DELTA}@18",
        f"MOVE Z={-Z_MAX_PRESS_DELTA}@18",
        "WAIT 300",
    ])
    block("light_touch: 접촉만(깊이 없음), 낮은 힘 영역 보강", [
        f"MOVE Z={Z_CONTACT_DELTA}@6",
        "WAIT 1000",
        f"MOVE Z={-Z_CONTACT_DELTA}@6",
        "WAIT 300",
    ])
    step1_delta = Z_CONTACT_DELTA - 0.6   # 접촉 지나 0.6mm 더
    step2_delta = Z_MAX_PRESS_DELTA - step1_delta  # 남은 구간(=-0.6)
    block("staircase: 중간 깊이에서 한 번 멈췄다 마저 누르기 (단계별 힘 확인)", [
        f"MOVE Z={step1_delta:.2f}@4",
        "WAIT 800",
        f"MOVE Z={step2_delta:.2f}@4",
        "WAIT 1500",
        f"MOVE Z={-Z_MAX_PRESS_DELTA}@8",
        "WAIT 300",
    ])
    return "\n".join(lines) + "\n"


def proximity_multi_speed_sweep(indent="  ", speeds=PRESS_SWEEP_SPEEDS):
    """이 strain 레벨 고정 상태에서 근접도(비접촉, far<->contact)만 여러 속도로
    연속 스윕한다 — '하나 discrete(strain) / 하나 continuous(Z)' 축을 여러 속도로."""
    lines = [f"{indent}# -- proximity continuous sweep, {len(speeds)}가지 속도 (압력 없음) --"]
    for spd in speeds:
        lines.append(f"{indent}MOVE Z={Z_CONTACT_DELTA}@{spd}")
        lines.append(f"{indent}WAIT 200")
        lines.append(f"{indent}MOVE Z={-Z_CONTACT_DELTA}@{spd}")
        lines.append(f"{indent}WAIT 200")
    return "\n".join(lines) + "\n"


def strain_multi_speed_sweep(indent="  ", speeds=STRAIN_SWEEP_SPEEDS):
    """이 Z 레벨(근접도) 고정 상태에서 strain을 0<->max로 여러 속도로 연속
    스윕한다 — '하나 discrete(Z) / 하나 continuous(strain)' 축을 여러 속도로.
    시작/끝 모두 strain=max로 맞춰져 있어야 한다(호출부에서 보장)."""
    lines = [f"{indent}# -- strain continuous sweep, {len(speeds)}가지 속도 --"]
    for spd in speeds:
        lines.append(f"{indent}MOVE YA=-{STRAIN_MAX_MM}@{spd} YB=-{STRAIN_MAX_MM}@{spd}")
        lines.append(f"{indent}WAIT 200")
        lines.append(f"{indent}MOVE YA={STRAIN_MAX_MM}@{spd} YB={STRAIN_MAX_MM}@{spd}")
        lines.append(f"{indent}WAIT 200")
    return "\n".join(lines) + "\n"


def gen_train_dense():
    out = []
    out.append(header(
        "train_dense_seq.txt — 재학습용 촘촘한 데이터 수집 시퀀스",
        "구성:\n"
        "  Block A — discrete strain(10단계)마다 압력 프로파일 5종(속도/정지 다양화)\n"
        "            + 근접도(비접촉) 연속 스윕 3속도  [discrete=strain, continuous=Z]\n"
        "  Block B — discrete Z(6단계, 근접~접촉)마다 strain 연속 스윕 3속도\n"
        "            [discrete=Z, continuous=strain] — Block A와 반대 축 조합\n"
        "  Block C — strain·Z 동시 이동(대각선 왕복) 3속도\n"
        f"  strain 단계: {', '.join(f'{strain_pct(v):.1f}%' for v in STRAIN_STEPS_MM)}"
        f" (YA=YB {STRAIN_STEPS_MM} mm)\n"
        f"  Z 단계(far 기준 누적): {[0, -5, -10, -15, -20, -25]} mm"
    ))
    out.append("")
    out.append("ENABLE")
    out.append("ZERO")
    out.append("TARE_FZ")
    out.append("WAIT 500")
    out.append("RECORD ON")
    out.append("")
    out.append("# ==================== Block A: discrete strain / continuous Z ====================")

    prev = 0.0
    for level_mm in STRAIN_STEPS_MM:
        delta = level_mm - prev
        prev = level_mm
        out.append("")
        out.append(f"# ---- strain = {strain_pct(level_mm):.1f}% (YA=YB={level_mm}mm) ----")
        if abs(delta) > 1e-9:
            out.append(f"MOVE YA={delta}@5 YB={delta}@5")
            out.append("WAIT 500")
        out.append(press_profiles().rstrip("\n"))
        out.append(proximity_multi_speed_sweep().rstrip("\n"))

    out.append("")
    out.append("# ==================== Block B: discrete Z / continuous strain ====================")
    out.append(f"# 시작 위치: strain=30%(YA=YB={STRAIN_MAX_MM}mm), Z=far(0)  <- Block A 마지막 상태")
    out.append("# 각 Z 레벨에서 strain을 0<->max로 스윕하며 그 레벨에 머문다 (스윕 후 항상 max로 복귀).")
    for i, z_delta in enumerate(Z_LEVEL_DELTAS):
        cum = sum(Z_LEVEL_DELTAS[:i + 1])
        out.append("")
        out.append(f"# ---- Z level {i}: far 기준 {cum:.0f}mm ----")
        if abs(z_delta) > 1e-9:
            out.append(f"MOVE Z={z_delta}@6")
            out.append("WAIT 500")
        out.append(strain_multi_speed_sweep().rstrip("\n"))

    out.append("")
    out.append("# ==================== Block C: strain-Z 동시 이동 (대각선 왕복) ====================")
    out.append("# 시작 위치: strain=30%(max), Z=contact(-25, far 기준)  <- Block B 마지막 상태")
    for spd_s, spd_z, label in [(*DIAG_SPEED_PAIRS[0], "slow"),
                                 (*DIAG_SPEED_PAIRS[1], "medium"),
                                 (*DIAG_SPEED_PAIRS[2], "fast")]:
        out.append(f"# -- {label} diagonal: (strain=max,contact) <-> (strain=0,far) --")
        out.append(f"MOVE YA=-{STRAIN_MAX_MM}@{spd_s} YB=-{STRAIN_MAX_MM}@{spd_s} Z={-Z_CONTACT_DELTA}@{spd_z}")
        out.append("WAIT 300")
        out.append(f"MOVE YA={STRAIN_MAX_MM}@{spd_s} YB={STRAIN_MAX_MM}@{spd_s} Z={Z_CONTACT_DELTA}@{spd_z}")
        out.append("WAIT 300")

    out.append("")
    out.append("# ==================== 종료: 안전 위치로 복귀 ====================")
    out.append("# Block C 마지막 상태: strain=max, Z=contact")
    out.append(f"MOVE YA=-{STRAIN_MAX_MM}@5 YB=-{STRAIN_MAX_MM}@5 Z={-Z_CONTACT_DELTA}@5")
    out.append("RECORD OFF")
    out.append("DISABLE")
    out.append("")
    return "\n".join(out)


# 실시간 검증 시퀀스 공통 속도 세트 — 두 파일(strain-fixed/Z-fixed/동시)에 전부
# 동일하게 적용. train_* 쪽 속도(0.5~20 등 제각각)와 달리 여기는 4단계로 고정.
TEST_SPEEDS = [0.5, 1, 3, 5]


def gen_realtime_test():
    """3부 구성 — 전부 같은 속도 세트(0.5/1/3/5 mm/s)를 쓴다.
    Part 1: strain 고정 / Z만 움직임 (압입 포함 — strain이 고정돼 있으니 안전)
    Part 2: Z 고정(far, contact — press 깊이는 안 감) / strain만 움직임
    Part 3: strain·Z 동시 이동, 매 왕복마다 두 축에 '같은' 속도값 사용
    압입(Z가 -25mm 넘어 -26.2mm까지 들어가는 것)은 Part 1에서만 일어나고,
    그 구간은 strain이 항상 고정돼 있다 — Part 2/3는 Z를 contact(-25)까지만
    쓰고 그 이상 누르지 않아서 strain이 움직이는 동안은 절대 press가 없다."""
    strain_levels = [0.0, STRAIN_MAX_MM]     # 0%, 30% — 코너 케이스 + 최대
    # far(0) -> -24mm: contact(-25)에서 1mm 여유를 두고 멈춘다. strain이 움직이는
    # 동안에는 접촉 경계에 딱 붙지 않도록(=혹시 모를 접촉/힘 발생 방지) train_prox_discrete.txt와
    # 동일한 -24mm 기준을 그대로 따른다.
    Z_NEAR_NO_TOUCH = -24.0
    z_levels_delta = [0.0, Z_NEAR_NO_TOUCH]

    out = []
    out.append(header(
        "realtime_test_seq.txt — 재학습 후 실시간 검증용 짧은 시퀀스",
        "구성 (전부 동일 속도 세트 0.5/1/3/5 mm/s 사용):\n"
        "  Part 1 — strain 고정(0%, 30%) / Z만 움직임, 압입(-26.2mm)까지 포함\n"
        "           (strain이 고정돼 있을 때만 눌러도 안전하다)\n"
        "  Part 2 — Z 고정(far, -24mm) / strain만 움직임 (0<->30%), press는 안 함\n"
        "  Part 3 — strain·Z 동시 이동, 매 구간 두 축 모두 같은 속도값 사용\n"
        "압입 중에는 strain을 절대 움직이지 않도록 Part 2/3의 Z는 -24mm(접촉 1mm\n"
        "전, train_prox_discrete.txt와 동일 기준)까지만 가고 그 이상(접촉/압입\n"
        "-25~-26.2mm)은 Part 1에서만 다룬다."
    ))
    out.append("")
    out.append("ENABLE")
    out.append("ZERO")
    out.append("TARE_FZ")
    out.append("WAIT 500")
    out.append("RECORD ON")
    out.append("")

    # ---- Part 1: strain 고정 / Z 연속(압입 포함) ----
    out.append("# ==================== Part 1: strain 고정 / Z 연속 (압입 포함) ====================")
    prev = 0.0
    for level_mm in strain_levels:
        delta = level_mm - prev
        prev = level_mm
        out.append("")
        out.append(f"# ---- strain = {strain_pct(level_mm):.0f}% (YA=YB={level_mm}mm), 고정 ----")
        if abs(delta) > 1e-9:
            out.append(f"MOVE YA={delta}@5 YB={delta}@5")
            out.append("WAIT 500")
        for spd in TEST_SPEEDS:
            out.append(f"  # -- Z 압입 프로파일 @ {spd}mm/s --")
            out.append(f"  MOVE Z={Z_MAX_PRESS_DELTA}@{spd}")
            out.append("  WAIT 500")
            out.append(f"  MOVE Z={-Z_MAX_PRESS_DELTA}@{spd}")
            out.append("  WAIT 300")

    # Part 1 종료 위치: strain=max, Z=far(0)
    out.append("")
    out.append("# ==================== Part 2: Z 고정(far/contact) / strain 연속 ====================")
    out.append(f"# 시작 위치: strain={strain_pct(STRAIN_MAX_MM):.0f}%(max), Z=far(0)  <- Part 1 마지막 상태")
    prev_z = 0.0
    for z_delta in z_levels_delta:
        step = z_delta - prev_z
        prev_z = z_delta
        out.append("")
        out.append(f"# ---- Z = far 기준 {z_delta:.0f}mm, 고정 (press 없음) ----")
        if abs(step) > 1e-9:
            out.append(f"MOVE Z={step}@5")
            out.append("WAIT 500")
        for spd in TEST_SPEEDS:
            out.append(f"  # -- strain 연속 스윕 @ {spd}mm/s --")
            out.append(f"  MOVE YA=-{STRAIN_MAX_MM}@{spd} YB=-{STRAIN_MAX_MM}@{spd}")
            out.append("  WAIT 300")
            out.append(f"  MOVE YA={STRAIN_MAX_MM}@{spd} YB={STRAIN_MAX_MM}@{spd}")
            out.append("  WAIT 300")

    # Part 2 종료 위치: strain=max, Z=Z_NEAR_NO_TOUCH(-24, 접촉 1mm 전)
    out.append("")
    out.append("# ==================== Part 3: strain-Z 동시 이동 (두 축 동일 속도) ====================")
    out.append(f"# 시작 위치: strain={strain_pct(STRAIN_MAX_MM):.0f}%(max), Z={Z_NEAR_NO_TOUCH:.0f}(접촉 1mm 전)"
               "  <- Part 2 마지막 상태")
    for spd in TEST_SPEEDS:
        out.append(f"# -- 동시 이동 @ {spd}mm/s (두 축 동일 속도) --")
        out.append(f"MOVE YA=-{STRAIN_MAX_MM}@{spd} YB=-{STRAIN_MAX_MM}@{spd} Z={-Z_NEAR_NO_TOUCH}@{spd}")
        out.append("WAIT 300")
        out.append(f"MOVE YA={STRAIN_MAX_MM}@{spd} YB={STRAIN_MAX_MM}@{spd} Z={Z_NEAR_NO_TOUCH}@{spd}")
        out.append("WAIT 300")

    out.append("")
    out.append("# ==================== 종료: 안전 위치로 복귀 ====================")
    out.append("# Part 3 마지막 상태: strain=max, Z=Z_NEAR_NO_TOUCH(-24)")
    out.append(f"MOVE YA=-{STRAIN_MAX_MM}@5 YB=-{STRAIN_MAX_MM}@5 Z={-Z_NEAR_NO_TOUCH}@5")
    out.append("RECORD OFF")
    out.append("DISABLE")
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    train_path = HERE / "train_dense_seq.txt"
    test_path = HERE / "realtime_test_seq.txt"
    train_path.write_text(gen_train_dense(), encoding="utf-8")
    test_path.write_text(gen_realtime_test(), encoding="utf-8")
    print(f"wrote {train_path}")
    print(f"wrote {test_path}")
