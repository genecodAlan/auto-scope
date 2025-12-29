#include <Arduino.h>
#include "A4988.h"

// === Motor 1 Pin Definitions ===
const int stepPin1 = D1;
const int dirPin1  = D0;
const int ms1_1    = D8;
const int ms2_1    = D7;
const int ms3_1    = D6;

// === Shared Control Pin ===
const int sleepPin = D5; // Tied to RESET and SLEEP

// === Motor Settings ===
const int stepsPerRev = 200;
const int microsteps = 16;
const int RPM = 20;

A4988 stepper1(stepsPerRev, dirPin1, stepPin1, ms1_1, ms2_1, ms3_1);

void setup() {
  Serial.begin(9600);

  pinMode(sleepPin, OUTPUT);
  digitalWrite(sleepPin, HIGH); // Wake up driver

  stepper1.begin(RPM, microsteps);

  Serial.println("Starting microstepping test with Laurb9 library...");
}

void loop() {
  Serial.println("Motor: Forward 1 rev (microstepping)");
  stepWithYield(stepsPerRev * microsteps); // Forward
  delay(2000);

  Serial.println("Motor: Backward 1 rev (microstepping)");
  stepWithYield(-(stepsPerRev * microsteps)); // Backward
  delay(2000);
}

// === Custom stepping function with yield ===
void stepWithYield(long steps) {
  long stepsRemaining = abs(steps);
  int stepDirection = (steps > 0) ? 1 : -1;

  for (long i = 0; i < stepsRemaining; i++) {
    stepper1.move(5*stepDirection);
    yield(); // Prevent ESP8266 watchdog reset
  }
}
