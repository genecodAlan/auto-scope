import cv2
import numpy as np
import time
import matplotlib as plt
import pyautogui as pg

def y_move_to_center(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"Clicked at: ({x}, {y})")



cap = cv2.VideoCapture(1)
cv2.namedWindow('Frame')
cv2.setMouseCallback('Frame', y_move_to_center)

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("could not get frame")
            break 
        

        cv2.imshow("Frame", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
except KeyboardInterrupt:
    print("Exiting...")
finally:
    cap.release()
    cv2.destroyAllWindows()
    print("Camera released.")


