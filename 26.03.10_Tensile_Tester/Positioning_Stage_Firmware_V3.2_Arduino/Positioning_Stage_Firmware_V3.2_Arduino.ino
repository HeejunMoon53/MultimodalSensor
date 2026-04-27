/* [Positioning_Stage_Firmware_V3.2_Arduino - JOG Speed Added] */
#include <AccelStepper.h>

#define PIN_XA_STEP 8
#define PIN_XA_DIR  9
#define PIN_XB_STEP 4 
#define PIN_XB_DIR  5 
#define PIN_YA_STEP 2
#define PIN_YA_DIR  3
#define PIN_YB_STEP 6
#define PIN_YB_DIR  7
#define PIN_Z_STEP  10
#define PIN_Z_DIR   11
#define PIN_ENABLE  12 

#define PIN_LIM_A0 A0
#define PIN_LIM_A1 A1
#define PIN_LIM_A2 A2
#define PIN_LIM_A3 A3
#define PIN_LIM_A4 A4
#define PIN_LIM_A5 A5

AccelStepper mXA(AccelStepper::DRIVER, PIN_XA_STEP, PIN_XA_DIR);
AccelStepper mXB(AccelStepper::DRIVER, PIN_XB_STEP, PIN_XB_DIR);
AccelStepper mYA(AccelStepper::DRIVER, PIN_YA_STEP, PIN_YA_DIR);
AccelStepper mYB(AccelStepper::DRIVER, PIN_YB_STEP, PIN_YB_DIR);
AccelStepper mZ(AccelStepper::DRIVER, PIN_Z_STEP, PIN_Z_DIR);

bool isMoving = false;
bool emgTripped = false;  //Emergency Stop
bool emgOverride = false; //EMG RESET

void setup() {
  Serial.begin(115200);
  pinMode(PIN_ENABLE, OUTPUT);
  digitalWrite(PIN_ENABLE, LOW); // Locked
  pinMode(PIN_LIM_A0, INPUT_PULLUP);
  pinMode(PIN_LIM_A1, INPUT_PULLUP);
  pinMode(PIN_LIM_A2, INPUT_PULLUP);
  pinMode(PIN_LIM_A3, INPUT_PULLUP);
  pinMode(PIN_LIM_A4, INPUT_PULLUP);
  pinMode(PIN_LIM_A5, INPUT_PULLUP);

  initMotor(mXA); initMotor(mXB);
  initMotor(mYA); initMotor(mYB);
  initMotor(mZ);

  // 1. 매뉴얼 모터 방향 설정
  mXA.setPinsInverted(true, false, false); 
  mYA.setPinsInverted(true, false, false); 
  mXB.setPinsInverted(true, false, false); 
  mYB.setPinsInverted(true, false, false);
  mZ.setPinsInverted(true, false, false);
}

void loop() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    parseCommand(input);
  }

  // 하드웨어 리미트 스위치 상시 감시
  bool hitA0 = (digitalRead(PIN_LIM_A0) == LOW);
  bool hitA1 = (digitalRead(PIN_LIM_A1) == LOW);
  bool hitA2 = (digitalRead(PIN_LIM_A2) == LOW);
  bool hitA3 = (digitalRead(PIN_LIM_A3) == LOW);
  bool hitA4 = (digitalRead(PIN_LIM_A4) == LOW);
  bool hitA5 = (digitalRead(PIN_LIM_A5) == LOW);
  
  bool anyHit = hitA0 || hitA1 || hitA2 || hitA3 || hitA4 || hitA5;

  // 상태 1: 스위치에 닿았고, 아직 처리되지 않은 응급 상황일 때
  if (anyHit && !emgTripped && !emgOverride) {
      emgTripped = true;
      digitalWrite(PIN_ENABLE, HIGH);
      mXA.setCurrentPosition(mXA.currentPosition());
      mXB.setCurrentPosition(mXB.currentPosition());
      mYA.setCurrentPosition(mYA.currentPosition());
      mYB.setCurrentPosition(mYB.currentPosition());
      mZ.setCurrentPosition(mZ.currentPosition());
      isMoving = false;
      Serial.println("ALARM:LIMIT"); // 파이썬 UI로 알람 전송
  }
  
  // 상태 2: 리셋 후 스위치에서 벗어났을 때 (완전한 정상 복구)
  if (!anyHit && (emgTripped || emgOverride)) {
      emgTripped = false;
      emgOverride = false;
      digitalWrite(PIN_ENABLE, LOW);
      Serial.println("ALARM:CLEARED"); 
  }

  if (!emgTripped) {
    mXA.run(); mXB.run(); 
    mYA.run(); mYB.run(); 
    mZ.run();
  }

  if (isMoving && 
      mXA.distanceToGo() == 0 && mXB.distanceToGo() == 0 &&
      mYA.distanceToGo() == 0 && mYB.distanceToGo() == 0 &&
      mZ.distanceToGo() == 0) {
    isMoving = false;
    Serial.println("DONE"); 
  }
}

void initMotor(AccelStepper &m) {
  m.setMaxSpeed(1000);
  m.setAcceleration(500); 
}

void parseCommand(String cmd) {
  if (cmd.startsWith("POS?")) {
    String posStr = "POS:";
    posStr += mXA.currentPosition(); posStr += ":";
    posStr += mXB.currentPosition(); posStr += ":";
    posStr += mYA.currentPosition(); posStr += ":";
    posStr += mYB.currentPosition(); posStr += ":";
    posStr += mZ.currentPosition(); posStr += ":";
    
    posStr += digitalRead(PIN_LIM_A0); posStr += ":";
    posStr += digitalRead(PIN_LIM_A1); posStr += ":";
    posStr += digitalRead(PIN_LIM_A2); posStr += ":";
    posStr += digitalRead(PIN_LIM_A3); posStr += ":";
    posStr += digitalRead(PIN_LIM_A4); posStr += ":";
    posStr += digitalRead(PIN_LIM_A5);
    
    Serial.println(posStr);
    return;
  }

  // 파이썬 UI에서 'EMERGENCY RESET' 버튼 눌렀을 때
  if (cmd.startsWith("RESET_EMG")) {
    if (emgTripped) {
      emgOverride = true;   // 오버라이드 켜기
      emgTripped = false;   // 정지 강제 풀기
      digitalWrite(PIN_ENABLE, LOW); // 모터 살려줌 -> 매뉴얼로 반대 방향 이동 가능하도록
    }
    return;
  }

  // 시퀀스 이동 명령 (ABS)
  if (cmd.startsWith("ABS")) {
    int idx = cmd.indexOf(':');
    while (idx != -1) {
      int nextIdx = cmd.indexOf(':', idx + 1); if (nextIdx == -1) break;
      String axis = cmd.substring(idx + 1, nextIdx);
      int valIdx = cmd.indexOf(':', nextIdx + 1); if (valIdx == -1) break;
      long targetPos = cmd.substring(nextIdx + 1, valIdx).toInt();
      int spdIdx = cmd.indexOf(':', valIdx + 1);
      String spdStr = (spdIdx == -1) ? cmd.substring(valIdx + 1) : cmd.substring(valIdx + 1, spdIdx);
      float speed = spdStr.toFloat();

      if (axis=="XA") { mXA.setMaxSpeed(speed); mXA.moveTo(targetPos); }
      else if (axis=="XB") { mXB.setMaxSpeed(speed); mXB.moveTo(targetPos); }
      else if (axis=="YA") { mYA.setMaxSpeed(speed); mYA.moveTo(targetPos); }
      else if (axis=="YB") { mYB.setMaxSpeed(speed); mYB.moveTo(targetPos); }
      else if (axis=="Z") { mZ.setMaxSpeed(speed); mZ.moveTo(targetPos); }
      if (spdIdx == -1) break; idx = spdIdx;
    }
    isMoving = true;
  }
  
  // --- [수정됨] 조그(JOG) 이동 명령 (속도 파라미터 파싱 추가) ---
  else if (cmd.startsWith("JOG")) {
      int idx1 = cmd.indexOf(':'); 
      int idx2 = cmd.indexOf(':', idx1 + 1);
      int idx3 = cmd.indexOf(':', idx2 + 1);
      
      if (idx1 != -1 && idx2 != -1) {
          String axis = cmd.substring(idx1 + 1, idx2);
          long val = 0;
          float speed = 0.0;
          
          if (idx3 != -1) {
              // 신규 포맷: JOG:축:거리:속도
              val = cmd.substring(idx2 + 1, idx3).toInt();
              speed = cmd.substring(idx3 + 1).toFloat();
          } else {
              // 기존 포맷: JOG:축:거리 (하위 호환)
              val = cmd.substring(idx2 + 1).toInt();
          }

          if (axis == "XA") { if(speed > 0) mXA.setMaxSpeed(speed); mXA.move(val); }
          else if (axis == "XB") { if(speed > 0) mXB.setMaxSpeed(speed); mXB.move(val); }
          else if (axis == "YA") { if(speed > 0) mYA.setMaxSpeed(speed); mYA.move(val); }
          else if (axis == "YB") { if(speed > 0) mYB.setMaxSpeed(speed); mYB.move(val); }
          else if (axis == "Z")  { if(speed > 0) mZ.setMaxSpeed(speed);  mZ.move(val); }
      }
  }
  // -----------------------------------------------------------------
  
  else if (cmd.startsWith("EN")) {
    int val = cmd.substring(3).toInt();
    digitalWrite(PIN_ENABLE, (val == 1) ? LOW : HIGH);
  }
  else if (cmd.startsWith("ZERO")) {
    mXA.setCurrentPosition(0); mXB.setCurrentPosition(0);
    mYA.setCurrentPosition(0); mYB.setCurrentPosition(0);
    mZ.setCurrentPosition(0);
  }
}