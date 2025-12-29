import cv2
import numpy as np
import time
import matplotlib as plt
import pyautogui as pg
import keyboard
import serial


drawing = False
mode = True 
ix, iy = -1, -1
moving = False

"""
def draw_circle(event, x, y, flags, param):
    global ix, iy, drawing, mode
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing == True:
            if mode == True:
                r = int(np.sqrt((x-ix)**2 + (y-iy)**2))
                cv2.circle(img, (ix,iy), r, (0,255,0), -1)
                #cv2.circle(img, (x,y), 5, (0,255,0), -1)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        #if mode == True:
            #cv2.circle(img, (x,y), 5, (0,255,0), -1)

"""
"""
def y_move_to_center(event, x, y, flags, param):
    #center of the frame
    cx, cy = 480, 360
    if event == cv2.EVENT_LBUTTONDOWN:
        moving = True
        if y < cy:
"""      


"""
img = np.zeros((512,512,3), np.uint8)
cv2.namedWindow('image')
cv2.setMouseCallback('image', draw_circle)

while(True):
    cv2.imshow('image', img)
    k = cv2.waitKey(1) & 0xFF
    if k  == ord('q'):
        break
"""


arduino_port =  "COM3"  
baud_rate = 9600 
ser = serial.Serial(arduino_port, baud_rate, timeout=1)
img = np.zeros((480, 640, 3), dtype=np.uint8)

try:
    while True:

        data_to_send = input("Enter data to send to Arduino (or 'q' to quit): ")
        print("You typed;", data_to_send)
        if data_to_send.lower().strip() == 'q':
            break
        ser.write((data_to_send.strip() + '\n').encode())  # Ensure newline
        ser.flush()
        time.sleep(0.1)
        
        
except KeyboardInterrupt:
    print("Exiting...")
finally:
    ser.close()
    cv2.destroyAllWindows()
    print("Serial port closed.")
