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

// === Shared Control Pins ===
const int sleepPin = D5; // Controls both SLEEP and RESET (tied together)

// === Motor Settings ===
const int microsteps = 16;
const int stepsPerRev = 200;

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
  digitalWrite(sleepPin, LOW); // Disable motors initially

  // Set microstepping to 1/16
  digitalWrite(ms1_1, HIGH);
  digitalWrite(ms2_1, HIGH);
  digitalWrite(ms3_1, HIGH);
  
  digitalWrite(ms1_2, HIGH);
  digitalWrite(ms2_2, HIGH);
  digitalWrite(ms3_2, HIGH);

  Serial.println("Stepper control ready. Awaiting step inputs...");
}

void loop() {
  // === Serial Input: Format = "Y X" steps ===
  if (Serial.available() > 0) {
    int ySteps = Serial.parseInt();
    int xSteps = Serial.parseInt();

    Serial.flush();

    if (ySteps != 0 || xSteps != 0) {
      digitalWrite(sleepPin, HIGH);  // Wake up drivers
      synchronizedMove(ySteps, xSteps);
      digitalWrite(sleepPin, LOW);   // Sleep after move
    }
  }
}

// === Manual Stepping Function for Individual Motors ===
void stepMotor(int stepPin, int dirPin, long steps, bool direction) {
  digitalWrite(dirPin, direction);
  delayMicroseconds(50); // Direction setup time

  for (long i = 0; i < steps; i++) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(500); // Adjust speed here
    digitalWrite(stepPin, LOW);
    delayMicroseconds(1000);
    yield(); // Prevent ESP8266 watchdog reset
  }
}

// === Blocked Move Function ===
// Moves Y axis first, then X axis (or swap order if you prefer)
void synchronizedMove(int ySteps, int xSteps) {
  // Move Y axis in one block
  if (ySteps != 0) {
    stepMotor(stepPin1, dirPin1, abs(ySteps), (ySteps > 0) ? HIGH : LOW);
    delay(10); // Optional small delay between axes
  }

  // Move X axis in one block
  if (xSteps != 0) {
    stepMotor(stepPin2, dirPin2, abs(xSteps), (xSteps > 0) ? HIGH : LOW);
    delay(10); // Optional small delay after movement
  }
}
