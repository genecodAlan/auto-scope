int button_state = 0;
int last_button_state = 0;
int button  = D4;
bool motor_state = false;

void setup() {
  Serial.begin(9600);
  pinMode(2, OUTPUT);
  pinMode(button, INPUT_PULLDOWN_16);
}

void loop() {
 if (Serial.available() > 0) {
      int data = Serial.parseInt();
      Serial.print(data + 1);
      digitalWrite(2, HIGH);
      delay(1500);
      digitalWrite(2, LOW);
      delay(100);
      }
  button_state = digitalRead(button);
  Serial.print(button_state);
  delay(100);
    if (button_state != last_button_state){
      if (button_state == HIGH){
          motor_state = !motor_state;
            if (motor_state){
              Serial.print("U are diddy");
            }
      }
    }
  
}

