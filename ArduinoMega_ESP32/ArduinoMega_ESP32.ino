#include <Keypad.h>

// LED 腳位定義
const int successLED = 2;
const int failureLED = 3;

const byte ROWS = 4;
const byte COLS = 4;

// 定義鍵盤按鍵排列
char keys[ROWS][COLS] = {
  {'D','C','B','A'},
  {'#','9','6','3'},
  {'0','8','5','2'},
  {'*','7','4','1'}
};

byte rowPins[ROWS] = {4, 5, 6, 7};
byte colPins[COLS] = {8, 9, 10, 11};

// 初始化鍵盤物件
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

String enteredOTP = "";
String correctOTP = "";
const int maxInputLength = 6;

void setup() {
  Serial.begin(115200);      // PC 監控
  Serial1.begin(115200);     // 與 ESP32 通信
  pinMode(successLED, OUTPUT);
  pinMode(failureLED, OUTPUT);
  Serial.println("系統已啟動，等待按鍵輸入...");
}

void loop() {
  // 檢查是否有新的 OTP 從 ESP32 傳入
  if (Serial1.available()) {
    correctOTP = Serial1.readStringUntil('\n');
    correctOTP.trim();
    Serial.print("收到來自 ESP32 的 OTP：");
    Serial.println(correctOTP);  // 在 Serial 監控視窗顯示
  }

  char key = keypad.getKey();
  if (key) {
    feedbackBlink();
    Serial.print("按鍵：");
    Serial.println(key);

    if (key == '#') {
      Serial.print("已輸入 OTP：");
      Serial.println(enteredOTP);
      if (enteredOTP.equals(correctOTP)) {
        Serial.println("OTP 正確！");
        activateSuccess();
        enteredOTP.trim();  // 去除空白及換行符號
      } else {
        Serial.println("OTP 錯誤！");
        activateFailure();
      }
      enteredOTP = "";  // 重置輸入
    } else if (key == '*') {
      enteredOTP = "";
      Serial.println("輸入已重置");
      feedbackBlink();
    } else {
      if (enteredOTP.length() < maxInputLength) {
        enteredOTP += key;
        Serial.print("當前輸入：");
        Serial.println(enteredOTP);
      } else {
        Serial.println("輸入長度已達上限");
        feedbackBlink();
      }
    }
  }
}

// 成功提示：LED 輪流亮滅
void activateSuccess() {
  for (int i = 0; i < 5; i++) {
    digitalWrite(successLED, HIGH);
    digitalWrite(failureLED, LOW);
    delay(300);
    digitalWrite(successLED, LOW);
    digitalWrite(failureLED, HIGH);
    delay(300);
  }
  digitalWrite(successLED, LOW);
  digitalWrite(failureLED, LOW);
}

// 失敗提示：紅燈慢閃
void activateFailure() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(failureLED, HIGH);
    delay(400);
    digitalWrite(failureLED, LOW);
    delay(400);
  }
}

// 按鍵回饋：短暫亮燈
void feedbackBlink() {
  digitalWrite(successLED, HIGH);
  delay(100);
  digitalWrite(successLED, LOW);
}
