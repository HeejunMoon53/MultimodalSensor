import os
import subprocess
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("Malgun", r"C:\Windows\Fonts\malgun.ttf"))
pdfmetrics.registerFont(TTFont("MalgunBold", r"C:\Windows\Fonts\malgunbd.ttf"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PDF = os.path.join(BASE_DIR, "MultimodalSensor_Report.pdf")

NAVY  = colors.HexColor("#16213e")
BLUE  = colors.HexColor("#0f3460")
LIGHT = colors.HexColor("#f8f9fa")
GRAY  = colors.HexColor("#cccccc")
WHITE = colors.white

def S(name, **kw):
    base = dict(fontName="Malgun", fontSize=9, leading=15, spaceAfter=3)
    base.update(kw)
    return ParagraphStyle(name, **base)

COVER_TITLE  = S("ct", fontName="MalgunBold", fontSize=20, spaceAfter=6,  textColor=NAVY)
COVER_SUB    = S("cs", fontName="MalgunBold", fontSize=13, spaceAfter=4,  textColor=BLUE)
H2           = S("h2", fontName="MalgunBold", fontSize=12, spaceBefore=12, spaceAfter=5, textColor=NAVY)
H3           = S("h3", fontName="MalgunBold", fontSize=10, spaceBefore=8,  spaceAfter=3, textColor=BLUE)
BODY         = S("bd")
BODY_INDENT  = S("bi", leftIndent=8)
SMALL        = S("sm", fontSize=8, textColor=colors.HexColor("#555555"))
BOLD_BODY    = S("bb", fontName="MalgunBold", fontSize=9)


def hr():
    return HRFlowable(width="100%", thickness=0.8, color=NAVY, spaceAfter=8, spaceBefore=4)

def thin_hr():
    return HRFlowable(width="100%", thickness=0.4, color=GRAY, spaceAfter=5, spaceBefore=5)

def section(title):
    return [hr(), Paragraph(title, H2)]

def bullet(text):
    return Paragraph(f"• {text}", BODY_INDENT)

def tbl(data, col_widths, header=True):
    t = Table(data, colWidths=col_widths)
    style = [
        ("FONTNAME",  (0, 0), (-1, -1), "Malgun"),
        ("FONTSIZE",  (0, 0), (-1, -1), 8),
        ("GRID",      (0, 0), (-1, -1), 0.4, GRAY),
        ("VALIGN",    (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING",   (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [WHITE, LIGHT]),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
            ("FONTNAME",   (0, 0), (-1, 0), "MalgunBold"),
        ]
    t.setStyle(TableStyle(style))
    return t

def git_log(n=20):
    try:
        r = subprocess.run(
            ["git", "log", f"--max-count={n}",
             "--pretty=format:%h|%ad|%s", "--date=format:%Y-%m-%d"],
            cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8"
        )
        return [l.split("|", 2) for l in r.stdout.strip().splitlines() if l.strip()]
    except Exception:
        return []

def build():
    doc = SimpleDocTemplate(
        OUTPUT_PDF, pagesize=A4,
        leftMargin=22*mm, rightMargin=22*mm,
        topMargin=22*mm, bottomMargin=22*mm
    )
    s = []

    # ── 표지 ──────────────────────────────────────────────────────────
    s += [
        Spacer(1, 10*mm),
        Paragraph("연구 프로젝트 리포트", SMALL),
        Spacer(1, 3*mm),
        Paragraph("Embedded AI-Driven Soft Multimodal<br/>Single-Electrode Sensor", COVER_TITLE),
        Paragraph("for Proximity, Tactile, and 2D-Strain Sensing", COVER_SUB),
        Spacer(1, 4*mm),
        thin_hr(),
        tbl(
            [["연구자", "HeeJun Moon (문희준)"],
             ["소속",   "BioRobotics & Control Lab (BiRC), 고려대학교 기계공학과"],
             ["생성일", datetime.now().strftime("%Y년 %m월 %d일 %H:%M")]],
            [35*mm, 120*mm], header=False
        ),
        Spacer(1, 6*mm),
    ]

    # ── 1. 연구 개요 ──────────────────────────────────────────────────
    s += section("1. 연구 개요")
    s += [
        Paragraph(
            "본 연구는 <b>단일 전극 구조의 소프트 인덕티브 센서</b>를 이용하여 근접, 촉각, 2D 인장 변형을 "
            "동시에 측정하고, Edge AI를 통해 실시간으로 신호를 분리(디커플링)하는 시스템을 개발한다. "
            "소형 MCU(STM32) 위에서 독립적으로 동작하며, 별도의 PC 없이 초경량 PINN 모델로 추론한다.", BODY),
        Spacer(1, 2*mm),
    ]

    # ── 2. 연구 배경 및 동기 ──────────────────────────────────────────
    s += section("2. 연구 배경 및 동기")
    s += [
        Paragraph("2.1 소프트 멀티모달 센서의 필요성", H3),
        bullet("로봇공학 및 인간-기계 상호작용의 발전으로 인간과 유사한 촉각 인식 능력이 요구됨"),
        bullet("유연 센서는 굴곡 접촉, 대형 변형, 웨어러블 응용에 적합함"),
        bullet("단일 모달 센서는 하나의 물리량만 측정 가능 → 실제 환경 적용에 한계"),
        Spacer(1, 3*mm),
        Paragraph("2.2 기존 디커플링 기술의 한계", H3),
        tbl(
            [["방법", "한계"],
             ["재료 설계 디커플링", "복잡한 합성·최적화, 독립적 신호만 분리 가능, 고가 장비 필요"],
             ["구조 설계 디커플링", "복잡한 구조 제조, 두께 증가 및 박리 위험, 센서 간 크로스톡"],
             ["AI 기반 디커플링",   "대규모 라벨 데이터 필요, 높은 계산 비용, 실시간 엣지 배포 어려움"]],
            [45*mm, 115*mm]
        ),
        Spacer(1, 2*mm),
        Paragraph("2.3 기존 인덕티브 센서 연구의 한계", H3),
        bullet("최대 2가지 모달리티(L/R 조합)만 측정 가능"),
        bullet("LCR 미터 등 대형 계측 장비 필요 → 독립적 임베디드 구현 불가"),
    ]

    # ── 3. 핵심 아이디어 및 주요 특징 ────────────────────────────────
    s += section("3. 핵심 아이디어 및 주요 특징")
    s += [
        Paragraph("3.1 Time Division Measurement (TDM)", H3),
        Paragraph(
            "단일 전극 센서에서 <b>인덕턴스(L), DC 저항(R_DC), TENG 전압(V)</b> 3가지 신호를 "
            "~1ms 주기로 시분할 측정한다. 각 모달리티는 아래 물리 정보를 포함한다.", BODY),
        tbl(
            [["측정 신호", "측정 방법", "포함 정보"],
             ["인덕턴스 (L)",    "LDC1614 I2C DMA (28-bit)", "인장 변형 + 근접 거리"],
             ["DC 저항 (R_DC)", "STM32 내장 ADC + OPAMP",   "인장 변형 (도미넌트)"],
             ["TENG 전압 (V)",  "STM32 내장 ADC + OPAMP",   "접촉 감지"]],
            [38*mm, 60*mm, 57*mm]
        ),
        Spacer(1, 3*mm),
        Paragraph("3.2 핵심 혁신 포인트", H3),
        bullet("연속적 사전-사후 접촉 공간 인식 (Continuous pre-to-post contact spatial perception)"),
        bullet("평면형·신축성 진정한 단일 전극 센서 구조"),
        bullet("3가지 이상 모달리티로의 독립적 신호 추출 확장 가능"),
        bullet("소형·저비용 임베디드 구현 (PC 독립)"),
        bullet("발산 없는 디커플링 — PINN 기반 경량 AI 모델"),
        bullet("물리 제약 PINN으로 데이터 효율 극대화 및 개별 센서 교정 비용 최소화"),
    ]

    # ── 4. 연구 방법 ──────────────────────────────────────────────────
    s += section("4. 연구 방법")
    s += [Paragraph("전체 연구는 3단계로 구성된다.", BODY)]
    s.append(tbl(
        [["단계", "세부 항목"],
         ["Part 1\n준비 및 설계",
          "① 센서 제작  ② PCB 회로 설계  ③ 소프트웨어 개발  ④ 커스텀 테스트 플랫폼 구축"],
         ["Part 2\n데이터 취득 및 학습",
          "① 복합 신호 취득  ② 신호 디커플링 분석  ③ 데이터셋 및 전처리 설계  ④ 모델 학습·평가"],
         ["Part 3\n실시간 응용",
          "① Edge-AI 모델 임베딩  ② 실시간 추론 시스템  ③ 응용 시나리오 설계  ④ 최종 시스템 통합"]],
        [28*mm, 130*mm]
    ))
    s += [
        Spacer(1, 3*mm),
        Paragraph("4.1 센서 제작 (EGaIn DIW)", H3),
        tbl(
            [["단계", "내용"],
             ["Step 1", "EGaIn DIW (Direct Ink Writing) — 액체 금속 코일 패턴 인쇄"],
             ["Step 2", "브리징 (Bridging) — 교차 배선 연결"],
             ["Step 3", "커버링 (Covering) — 보호층 도포"],
             ["Step 4", "와이어 삽입 및 커팅 — 전극 연결"]],
            [20*mm, 138*mm]
        ),
        Spacer(1, 3*mm),
        Paragraph("4.2 PCB 회로 설계", H3),
        bullet("STM32G473CBT6 — 메인 MCU (ARM Cortex-M4, 170MHz)"),
        bullet("LDC1614 — 28-bit 인덕턴스-디지털 변환기 (1kHz~10MHz, I2C)"),
        bullet("ADG734 — Quad SPDT RF 스위치 (R_on: 2.5Ω, t_on: 29ns, 200MHz 대역폭)"),
        bullet("내장 12-bit ADC + OPAMP — TENG 전압 및 DC 저항 측정"),
        Spacer(1, 3*mm),
        Paragraph("4.3 소프트웨어 개발", H3),
        bullet("타이머 기반 병렬 논블로킹 DMA 처리 (TIM7/TIM6 + I2C DMA + ADC DMA)"),
        bullet("1kHz 고정 샘플링 레이트, CPU 유휴율 93.908%"),
        bullet("USART2 (115200 baud) CSV 출력: ldc_ch, r_dc_adc, teng_adc"),
        Spacer(1, 3*mm),
        Paragraph("4.4 커스텀 테스트 플랫폼", H3),
        bullet("5축 스테핑 모터 포지셔닝 스테이지 (700×700×300mm)"),
        bullet("Arduino Uno + Python GUI 제어 프로그램"),
        bullet("기존 CNC 장비의 중심점 이동 문제 해결 및 2D 인장 측정 지원"),
    ]

    # ── 5. 현재 진행 상황 및 결과 ────────────────────────────────────
    s += section("5. 현재 진행 상황 및 결과")
    s += [
        Paragraph("Part 1(준비 및 설계) 완료 — 현재 Part 2(신호 디커플링 분석) 진행 중", BOLD_BODY),
        Spacer(1, 3*mm),
        Paragraph("5.1 복합 신호 취득 실험", H3),
        bullet("초기 길이 120mm 센서를 0~36mm (30% 인장)로 1mm 간격 인장, 총 37회 시행"),
        bullet("동시에 50mm~0mm 근접 거리 연속 데이터 취득"),
        bullet("스테퍼 모터 가감속 보정 및 시공간 데이터 축 동기화 완료"),
        Spacer(1, 3*mm),
        Paragraph("5.2 신호 디커플링 분석 결과", H3),
        tbl(
            [["신호", "인장(ε)에 대한 반응", "근접거리(d)에 대한 반응"],
             ["DC 저항 (R)", "지배적 반응 (단조 증가)", "반응 미미"],
             ["인덕턴스 (L)", "민감 반응", "민감 반응 (이중 민감도)"]],
            [25*mm, 70*mm, 62*mm]
        ),
        Spacer(1, 2*mm),
        bullet("∇L(d,ε) 와 ∇R(d,ε) 그래디언트가 선형 독립 → 신호 디커플링 수학적으로 가능"),
        Spacer(1, 3*mm),
        Paragraph("5.3 해석적 역산의 한계 → PINN 필요성", H3),
        tbl(
            [["문제", "내용"],
             ["① 극단 조건의 절단 오류",
              "극근접(M² 지배) 또는 대변형(sinh⁻¹, ln 지배) 조건에서 선형 근사 오류 급증"],
             ["② 야코비안 특이점",
              "그래디언트 방향이 유사해지면 J→0 → J⁻¹→∞ → 노이즈 증폭 및 수학적 발산"],
             ["③ 과도한 계산 비용",
              "반복 솔버 및 역행렬 계산이 MCU의 제한된 자원을 심각하게 초과"]],
            [40*mm, 118*mm]
        ),
        Spacer(1, 3*mm),
        Paragraph("5.4 PINN (Physics Informed Neural Network) 솔루션", H3),
        Paragraph(
            "Loss_Total = Loss_Data + λ·Loss_Physics 구조로, 물리 방정식을 제약으로 삼아 "
            "비물리적 예측을 방지하고 최소 데이터로 일반화를 극대화한다.", BODY),
        tbl(
            [["특성", "내용"],
             ["발산 없는 추론",   "순방향 패스만으로 야코비안 특이점 위험 완전 제거"],
             ["전역 비선형 매핑", "구간별 오류 없이 복잡한 표면 근사"],
             ["O(1) 지연 시간",  "경량 MAC 연산으로 MCU 위 마이크로초 지연 보장"],
             ["물리 기반 정규화", "물리 다양체를 따라 OOD·노이즈에 강건, 과적합 방지"]],
            [38*mm, 120*mm]
        ),
    ]

    # ── 6. 향후 계획 ──────────────────────────────────────────────────
    s += section("6. 향후 계획")
    s += [
        tbl(
            [["단계", "내용"],
             ["Part 2 완료",  "데이터셋 설계, PINN 모델 학습 및 평가"],
             ["Part 3 착수",  "STM32에 Edge-AI 모델 임베딩, 실시간 추론 시스템 구축"],
             ["응용 시나리오", "크롤링 로봇 — 단일 센서로 모든 모달리티 자가 인지 + 자가 충전\n"
                              "터치리스 인터페이스 / 로봇 안전 센서"],
             ["최종 통합",    "전체 시스템 통합 및 성능 검증"]],
            [30*mm, 128*mm]
        ),
    ]

    # ── 7. git 커밋 히스토리 ──────────────────────────────────────────
    s += section("7. Git 커밋 히스토리")
    logs = git_log(20)
    if logs:
        data = [["SHA", "날짜", "커밋 메시지"]] + logs
        s.append(tbl(data, [18*mm, 22*mm, 118*mm]))
    else:
        s.append(Paragraph("커밋 기록 없음", BODY))

    # ── 푸터 ──────────────────────────────────────────────────────────
    s += [
        Spacer(1, 6*mm),
        thin_hr(),
        Paragraph(
            f"BioRobotics & Control Lab (BiRC) | 고려대학교 기계공학과 | "
            f"생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            SMALL
        ),
    ]

    doc.build(s)
    print(f"PDF 생성 완료: {OUTPUT_PDF}")


if __name__ == "__main__":
    build()
