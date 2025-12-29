#include <Arduino.h>

// === Motor 1 Pin Definitions ===
const int stepPin1 = D3;
const int dirPin1  = D2;
const int ms1_1    = D8;
const int ms2_1    = D7;
const int ms3_1    = D6;

// === Motor 2 Pin Definitions ===
const int stepPin2 = D1;
const int dirPin2  = D0;
const int ms1_2    = D8;
const int ms2_2    = D7;
const int ms3_2    = D6;

// === Shared Control Pin ===
const int sleepPin = D5; // Tied to RESET and SLEEP

// === Motor Settings ===
const int stepsPerRev = 200;
const int microsteps = 16;

void setup() {
  Serial.begin(9600);

  // Setup pins
  pinMode(stepPin1, OUTPUT);
  pinMode(dirPin1, OUTPUT);
  pinMode(ms1_1, OUTPUT);
  pinMode(ms2_1, OUTPUT);
  pinMode(ms3_1, OUTPUT);

  pinMode(stepPin2, OUTPUT);
  pinMode(dirPin2, OUTPUT);
  pinMode(ms1_2, OUTPUT);
  pinMode(ms2_2, OUTPUT);
  pinMode(ms3_2, OUTPUT);

  pinMode(sleepPin, OUTPUT);
  digitalWrite(sleepPin, LOW); // Start with motors disabled

  // Set microstepping to 1/16
  digitalWrite(ms1_1, HIGH);
  digitalWrite(ms2_1, HIGH);
  digitalWrite(ms3_1, HIGH);
  
  digitalWrite(ms1_2, HIGH);
  digitalWrite(ms2_2, HIGH);
  digitalWrite(ms3_2, HIGH);

  Serial.println("Stepper test ready...");
}

void loop() {
  // Wake up drivers
  digitalWrite(sleepPin, HIGH);
  delay(10); // Allow drivers to wake up

  // Motor sequence
  Serial.println("Motor 1: Forward 1 rev");
  stepMotor(stepPin1, dirPin1, stepsPerRev * microsteps, HIGH);
  delay(1000);

  Serial.println("Motor 2: Backward 0.5 rev");
  stepMotor(stepPin2, dirPin2, stepsPerRev * microsteps / 2, LOW);
  delay(1000);

  Serial.println("Motor 1: Backward 1 rev");
  stepMotor(stepPin1, dirPin1, stepsPerRev * microsteps, LOW);
  delay(1000);

  Serial.println("Motor 2: Forward 0.5 rev");
  stepMotor(stepPin2, dirPin2, stepsPerRev * microsteps / 2, HIGH);
  delay(1000);

  // Sleep the motors
  digitalWrite(sleepPin, LOW);
  Serial.println("Motors disabled\n");
  delay(2000);
}

// === Manual Stepping Function ===
void stepMotor(int stepPin, int dirPin, long steps, bool direction) {
  digitalWrite(dirPin, direction);
  delayMicroseconds(50); // Direction setup time

  for (long i = 0; i < steps; i++) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(1000); // Adjust speed here
    digitalWrite(stepPin, LOW);
    delayMicroseconds(1000);
    yield(); // Keep the ESP8266 watchdog happy
  }
}
