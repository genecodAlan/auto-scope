import cv2
import numpy as np
import time
import matplotlib as plt
import pyautogui as pg
import keyboard
import serial


def y_move_to_center(event, x, y, flags, param):
    global moving
    cx, cy = 480, 360  # Center of the frame

    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"Clicked at: ({x}, {y})")
        moving = True

        # Compute step differences from center
        dy = y - cy
        dx = x - cx

        y_steps = round(dy / 1.875)
        x_steps = round(dx / 1.875)

        # Debug output
        if y_steps < 0:
            print("Moving up", abs(y_steps))
        elif y_steps > 0:
            print("Moving down", y_steps)
        else:
            print("No Y movement required.")

        if x_steps < 0:
            print("Moving left", abs(x_steps))
        elif x_steps > 0:
            print("Moving right", x_steps)
        else:
            print("No X movement required.")

        # Send steps to Arduino in "Y X" format
        if y_steps != 0 or x_steps != 0:
            command = f"{y_steps} {x_steps}\n"
            ser.write(command.encode())
            time.sleep(0.1)
        else:
            print("No movement required.")
            
#initialize the camera                  
cap = cv2.VideoCapture(1)
if not cap.isOpened():
    print("Error: Camera not found.")
    exit()
cap.set(cv2.CAP_PROP_FRAME_WIDTH, (640*1.5))
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, (480*1.5))
cap.set(cv2.CAP_PROP_FPS, 30)
cv2.namedWindow('Micro Camera')
cv2.setMouseCallback('Micro Camera', y_move_to_center)

# Initialize call back variables
moving = False
steps = 0
# Initialize the serial port for Arduino
arduino_port =  "COM3"  
baud_rate = 9600 
ser = serial.Serial(arduino_port, baud_rate, timeout=1)

try: 
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture image.")
            break

        # Display the frame
        cv2.imshow('Micro Camera', frame)

        # Wait for a key press
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
except KeyboardInterrupt:
    print("Exiting...")
finally:
    cap.release()
    cv2.destroyAllWindows()
    print("Camera released.")