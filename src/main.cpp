#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

const int PULSO_MIN = 150;
const int PULSO_MAX = 600;

void setup() {
  Serial.begin(9600);
  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(50);
  delay(10);
  Serial.println("Inicio de prueba");
}

void loop() {
  for (int ch = 4; ch <= 8; ch++) {
    Serial.print("Probando canal ");
    Serial.println(ch);

    pwm.setPWM(ch, 0, PULSO_MIN);
    delay(1000);

    pwm.setPWM(ch, 0, PULSO_MAX);
    delay(1000);

    pwm.setPWM(ch, 0, 0);  // apaga este canal
    delay(500);
  }
  Serial.println("--- vuelta completa ---");
  delay(2000);
}