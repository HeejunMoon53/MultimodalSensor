# 연구 로드맵 & 할 일 목록

> 마지막 업데이트: 2026-04-30
> 현재 단계: **Step 1 — 물리량·모달리티·어플리케이션 결정** 논의 중

---

## 현재 상태 요약

| 항목 | 내용 |
|---|---|
| 센서 | EGaIn DIW 평면 직사각형 스파이럴 코일 (120mm) |
| 측정 신호 | L (LDC1614 공진주파수), R_DC (ADC), V_TENG (ADC) |
| 데이터 | 37종 (변형 0~30%, 각 시험당 근접도 0~50mm 스윔) |
| 플랫폼 | STM32G473CBT6 + 커스텀 PCB (추후 재설계 예정) |
| 진행 | Part 1 완료 / Part 2 진행 중 |

---

## Step 1 — 물리량 · 모달리티 · 어플리케이션 결정

> **결정되지 않으면 Step 2~5 전부 확정 불가. 최우선 과제.**

### 🔴 지금 당장 결정해야 할 것

- [ ] **최종 어플리케이션 확정** (아래 후보 중 선택)

| 후보 | 필요 모달리티 | 현재 신호로 가능? |
|---|---|---|
| A. 로봇 안전/근접 센서 | Proximity + Tactile | ✅ 가능 |
| B. 웨어러블 변형 센서 | 1D/2D Strain | ✅ 가능 |
| C. 크롤링 로봇 자가 인지 | Proximity + Strain + Tactile | ✅ 가능 |
| D. 물체 인식 포함 | Proximity + Object ID + Tactile | ❌ 회로 추가 필요 |

- [ ] **측정 신호 방식 결정**
  - 현재: LDC1614 공진주파수 단일값 → L
  - 검토 중: 다중 주파수 임피던스 Z(ω) 실수부·허수부 → 물체 인식 가능, but PCB 재설계 필요

- [ ] **2D-Strain 포함 여부 결정**
  - 포함 시: x/y 개별 인장 데이터 수집 필요, 테스트 플랫폼 수정 필요

### 📚 공부할 내용

- [ ] 임피던스 스펙트로스코피 기초 — Z(ω) 주파수 의존성, Nyquist plot 해석
- [ ] 물체 인식 관련 논문 서베이 — eddy current 기반 재질 분류 사례
- [ ] 2D-Strain 분해 이론 — 직사각형 코일 eigen-direction 수식 유도

---

## Step 2 — 회로 재설계 (PCB v2)

> Step 1 결정 후 착수. 현재 PCB는 L/R_DC/TENG 3종 전용이라 모달리티 추가 시 재설계 필수.

### 🔧 실무 작업

- [ ] Step 1 결과를 반영한 신호 경로 확정
- [ ] 다중 주파수 임피던스 측정이 포함될 경우 IC 선정 (AD5933 / MAX11210 등 비교)
- [ ] EasyEDA Pro로 회로도 작성 → PCB 레이아웃
- [ ] 노이즈 대책 검토 (EMI 차폐, 그라운드 플레인, TVS 다이오드)
- [ ] 제조 발주 (JLCPCB 등) 및 부품 구매
- [ ] PCB 납땜 및 기초 동작 검증

### 📚 공부할 내용

- [ ] AD5933 임피던스 분석기 IC 데이터시트 및 활용법
- [ ] 다층 PCB EMI 설계 기법 (그라운드 분리, 디커플링 커패시터 배치)
- [ ] STM32G473 고속 I2C / SPI DMA 활용법 (새 IC 인터페이스 대비)

---

## Step 3 — 데이터 수집 계획

> Step 2 완료 후 착수. 학습 모델 성능은 데이터 품질에 직결.

### 🔧 실무 작업

- [ ] 수집할 변수 범위 확정

| 변수 | 현재 범위 | 목표 범위 |
|---|---|---|
| 변형률 ε | 0~30% (1% 간격) | 미정 |
| 근접거리 d | 0~50mm | 미정 |
| 접촉 하중 F | 미수집 | 포함 여부 결정 필요 |
| 물체 재질 | 미수집 (단일 금속) | 포함 여부 결정 필요 |
| x/y 개별 변형 | 미수집 | 2D-Strain 포함 시 필요 |

- [ ] 동시 자극 시나리오 설계 (ε 변하는 동안 d도 동시에 변하는 궤적)
- [ ] 테스트 플랫폼 수정 (2D-Strain 측정 시 x/y 독립 인장 축 추가)
- [ ] 데이터 전처리 파이프라인 구축 (가감속 보정, 동기화, 정규화)
- [ ] 데이터 수집 자동화 스크립트 작성

### 📚 공부할 내용

- [ ] 실험 설계(DOE, Design of Experiments) — 최소 실험으로 최대 정보 획득
- [ ] 데이터 증강 기법 — 물리 기반 데이터 생성으로 실험 횟수 절감
- [ ] 시계열 동기화 기법 — 스테퍼 모터 포지션과 센서 신호 정합 방법

---

## Step 4 — 모델 설계 및 학습

> Step 3 완료 후 착수. Embedded 제약(STM32 메모리·연산량)을 처음부터 고려해야 함.

### 🔧 실무 작업

- [ ] PINN 구조 설계 확정
  - Stage 1: ΔR → ε̂
  - Stage 2: (ΔL, ε̂) → d̂
  - 물체 인식 포함 시 Stage 3 추가 여부 결정
- [ ] PyTorch로 프로토타입 학습 코드 작성
- [ ] 물리 Loss 함수 구현 — `Loss_Physics = (ΔR - R_theory(ε̂))² + (ΔL - L_theory(ε̂,d̂))²`
- [ ] 모델 경량화 — 파라미터 수 최소화, INT8 양자화 테스트
- [ ] X-CUBE-AI로 STM32 변환 가능 여부 사전 검증 (메모리 프로파일링)
- [ ] 교차검증 및 OOD(분포 외) 성능 평가

### 📚 공부할 내용

- [ ] PINN (Physics-Informed Neural Networks) 이론 및 구현
  - Raissi et al. (2019) 원논문
  - Loss 가중치 튜닝 전략 (λ 스케줄링)
- [ ] STM32 Edge-AI 배포 파이프라인
  - X-CUBE-AI 사용법 (Keras/ONNX → C코드 변환)
  - INT8 양자화 정확도 손실 분석
- [ ] 경량 모델 설계 기법
  - Knowledge Distillation
  - Structured Pruning
- [ ] 모노토닉 네트워크 (Stage 1: R-ε 단조성 보장 기법)

---

## Step 5 — 테스트 및 실시간 임베디드 구현

> Step 4 완료 후 착수.

### 🔧 실무 작업

- [ ] X-CUBE-AI로 학습된 모델 → STM32 C코드 변환
- [ ] STM32 펌웨어에 추론 루프 통합 (TDM 1ms 사이클 내 처리 가능 여부 검증)
- [ ] UART 실시간 출력 포맷 설계 (ε̂, d̂, 접촉 여부)
- [ ] 실시간 성능 지표 측정 — 지연, 정확도, CPU 점유율
- [ ] 어플리케이션 시나리오 시연 (크롤링 로봇 / 터치리스 인터페이스 등)
- [ ] 논문 작성

### 📚 공부할 내용

- [ ] STM32 CubeAI 추론 최적화 — SRAM 배치, DMA 활용
- [ ] CMSIS-NN — ARM Cortex-M용 NN 커널 라이브러리
- [ ] 실시간 시스템 레이턴시 분석 (WCET 측정)

---

## 논문 / 참고자료

| 분류 | 제목 | 상태 |
|---|---|---|
| 핵심 참고 | Wang et al. "Programming stretchable planar coils..." Materials Today Physics (2025) | ✅ 읽음 |
| 핵심 참고 | Li et al. "Fingertip-inspired spatially anisotropic inductive liquid metal sensors..." Advanced Materials (2025) | ✅ 읽음 |
| 읽어야 함 | Raissi et al. "Physics-informed neural networks" J. Comput. Phys. (2019) | ⏳ |
| 읽어야 함 | 다중 주파수 임피던스 기반 물체 인식 관련 논문 (서베이 필요) | ⏳ |
| 읽어야 함 | "Recent Progress on Flexible Multimodal Sensors: Decoupling Strategies..." Advanced Materials (2026) | ⏳ |

---

## 우선순위 요약 (지금 당장 해야 할 것)

```
1순위 ── Step 1 결정: 어플리케이션 + 신호 방식 확정 (논의 중)
           └─ 이게 결정되어야 나머지 모든 것이 정해짐

2순위 ── Step 1 결정 후 즉시: PINN 논문 읽기 + 임피던스 IC 서베이
           └─ 회로 재설계와 모델 설계 양쪽에 필요

3순위 ── Step 2: PCB 설계 시작 (발주~납품 리드타임 고려, 최대한 빨리)
```
