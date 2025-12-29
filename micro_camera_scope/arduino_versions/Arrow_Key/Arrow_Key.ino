#include <Arduino.h>

// === Pin Definitions ===
const int stepPin1 = D3;
const int dirPin1  = D2;
const int stepPin2 = D1;
const int dirPin2  = D0;

const int ms1 = D8;
const int ms2 = D7;
const int ms3 = D6;

const int sleepPin = D5; // Shared SLEEP/RESET

// === Speed & Step Control (Configurable via serial) ===
int pulseWidth = 1500;      // Microseconds (pulse duration)
int stepDelay = 4000;       // Microseconds between steps (bigger = slower)
int stepsPerCommand = 100;  // Steps to execute per movement command

// Position tracking
int pos_x = 0;
int pos_y = 0;

// Command buffer
String commandBuffer = "";

void setup() {
  pos_x = 0;
  pos_y = 0;
  Serial.begin(115200);
  Serial.setTimeout(50); // Faster serial timeout

  pinMode(stepPin1, OUTPUT);
  pinMode(dirPin1, OUTPUT);
  pinMode(stepPin2, OUTPUT);
  pinMode(dirPin2, OUTPUT);

  pinMode(ms1, OUTPUT);
  pinMode(ms2, OUTPUT);
  pinMode(ms3, OUTPUT);
  
  pinMode(sleepPin, OUTPUT);
  digitalWrite(sleepPin, HIGH); // Keep drivers awake

  // Set microstepping to 1/16
  digitalWrite(ms1, HIGH);
  digitalWrite(ms2, HIGH);
  digitalWrite(ms3, HIGH);

  Serial.println("READY"); // Signal to Python that Arduino is ready
  Serial.flush();
}

void loop() {
  // Check for incoming serial data
  while (Serial.available() > 0) {
    char inChar = (char)Serial.read();
    
    // Check for command terminator
    if (inChar == '\n' || inChar == '\r') {
      if (commandBuffer.length() > 0) {
        processCommand(commandBuffer);
        commandBuffer = "";
      }
    } else {
      commandBuffer += inChar;
    }
  }
}

// === Command Processing ===
void processCommand(String cmd) {
  cmd.trim(); // Remove whitespace
  
  if (cmd.length() < 2) return; // Invalid command
  
  // === CONFIGURATION COMMANDS (new feature) ===
  if (cmd.startsWith("SPEED:")) {
    // Format: SPEED:4000
    int newDelay = cmd.substring(6).toInt();
    if (newDelay >= 500 && newDelay <= 50000) { // Safety limits
      stepDelay = newDelay;
      Serial.print("SPEED_SET:");
      Serial.println(stepDelay);
    } else {
      Serial.println("ERROR:SPEED_OUT_OF_RANGE");
    }
    return;
  }
  
  if (cmd.startsWith("STEPS:")) {
    // Format: STEPS:100
    int newSteps = cmd.substring(6).toInt();
    if (newSteps >= 1 && newSteps <= 1000) { // Safety limits
      stepsPerCommand = newSteps;
      Serial.print("STEPS_SET:");
      Serial.println(stepsPerCommand);
    } else {
      Serial.println("ERROR:STEPS_OUT_OF_RANGE");
    }
    return;
  }
  
  if (cmd.startsWith("PULSE:")) {
    // Format: PULSE:1500
    int newPulse = cmd.substring(6).toInt();
    if (newPulse >= 500 && newPulse <= 5000) { // Safety limits
      pulseWidth = newPulse;
      Serial.print("PULSE_SET:");
      Serial.println(pulseWidth);
    } else {
      Serial.println("ERROR:PULSE_OUT_OF_RANGE");
    }
    return;
  }
  
  if (cmd == "STATUS") {
    // Return current settings
    Serial.print("STATUS:");
    Serial.print(stepDelay);
    Serial.print(",");
    Serial.print(stepsPerCommand);
    Serial.print(",");
    Serial.println(pulseWidth);
    return;
  }
  
  // === MOVEMENT COMMANDS (original 2-char format) ===
  if (cmd.length() == 2) {
    char y_cmd = cmd.charAt(0);
    char x_cmd = cmd.charAt(1);
    
    // Y-axis (Up/Down)
    if (y_cmd == 'U') {
      stepMotor(stepPin1, dirPin1, stepsPerCommand, HIGH);
      pos_y += stepsPerCommand;
    } else if (y_cmd == 'D') {
      stepMotor(stepPin1, dirPin1, stepsPerCommand, LOW);
      pos_y -= stepsPerCommand;
    }

    // X-axis (Left/Right)
    if (x_cmd == 'L') {
      stepMotor(stepPin2, dirPin2, stepsPerCommand, LOW);
      pos_x -= stepsPerCommand;
    } else if (x_cmd == 'R') {
      stepMotor(stepPin2, dirPin2, stepsPerCommand, HIGH);
      pos_x += stepsPerCommand;
    }
    
    // Acknowledge movement complete
    Serial.print("MOVE_OK:");
    Serial.print(pos_x);
    Serial.print(",");
    Serial.println(pos_y);
    return;
  }
  
  Serial.println("ERROR:UNKNOWN_COMMAND");
}

// === Manual Stepping Function (Improved) ===
void stepMotor(int stepPin, int dirPin, long steps, bool direction) {
  digitalWrite(dirPin, direction);
  delayMicroseconds(50); // Direction setup time

  for (long i = 0; i < steps; i++) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(pulseWidth);
    digitalWrite(stepPin, LOW);
    delayMicroseconds(stepDelay);
    
    // ESP8266 watchdog yield every 10 steps
    if (i % 10 == 0) yield();
  }
}