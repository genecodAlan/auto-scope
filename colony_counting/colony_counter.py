import cv2
import numpy as np
import math
import threading
# --- Load image ---


colony_count = 0
global image
drawing = False
ix, iy = -1, -1

def mouse_callback(event, x, y, flags, param):
    global drawing, ix, iy, colony_count, image
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            temp_img = image.copy()
            cv2.circle(temp_img, (ix, iy), int(math.hypot(x - ix, y - iy)), (255, 0, 0), 2)
            cv2.imshow("Colonies", temp_img)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        radius = int(math.hypot(x - ix, y - iy))
        cv2.circle(image, (ix, iy), radius, (255, 0, 0), 2)
        colony_count += 1
        print("Updated count = ", colony_count)

        mode = "circle"  # "circle" or "rectangle"
        rect_start = (-1, -1)
        rect_end = (-1, -1)
        rectangles = []

        def switch_mode():
            global mode
            mode = "rectangle" if mode == "circle" else "circle"
            print(f"Switched to {mode} mode.")

        def mouse_callback(event, x, y, flags, param):
            global drawing, ix, iy, colony_count, image, rect_start, rect_end, rectangles, clean
            if event == cv2.EVENT_LBUTTONDOWN:
                drawing = True
                if mode == "circle":
                    ix, iy = x, y
                else:
                    rect_start = (x, y)
                    rect_end = (x, y)
            elif event == cv2.EVENT_MOUSEMOVE:
                if drawing:
                    temp_img = image.copy()
                    if mode == "circle":
                        cv2.circle(temp_img, (ix, iy), int(math.hypot(x - ix, y - iy)), (255, 0, 0), 2)
                    else:
                        rect_end = (x, y)
                        cv2.rectangle(temp_img, rect_start, rect_end, (0, 0, 255), 2)
                    cv2.imshow("Colonies", temp_img)
            elif event == cv2.EVENT_LBUTTONUP:
                drawing = False
                if mode == "circle":
                    radius = int(math.hypot(x - ix, y - iy))
                    cv2.circle(image, (ix, iy), radius, (255, 0, 0), 2)
                    colony_count += 1
                    print("Updated count = ", colony_count)
                else:
                    rect_end = (x, y)
                    cv2.rectangle(image, rect_start, rect_end, (0, 0, 255), 2)
                    rectangles.append((rect_start, rect_end))
                    # Erase region in clean mask
                    x1, y1 = rect_start
                    x2, y2 = rect_end
                    x_min, x_max = min(x1, x2), max(x1, x2)
                    y_min, y_max = min(y1, y2), max(y1, y2)
                    clean[y_min:y_max, x_min:x_max] = 0
                    print(f"Erased region: ({x_min},{y_min}) to ({x_max},{y_max})")

        def handle_keys():
            while True:
                key = cv2.waitKey(1) & 0xFF
                if key == ord('m'):
                    switch_mode()
                elif key == 27 or key == ord('q'):

                    break

        threading.Thread(target=handle_keys, daemon=True).start()


image = cv2.imread("Colonies/Col2.jpg")
if image is None:
    raise FileNotFoundError("Could not load image. Make sure '*file*.jpg' exists in the same directory.")


image = cv2.resize(image, (550, 750))
# --- Preprocessing ---
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

ret, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
# --- Thresholding (try adaptive if lighting is uneven) ----
kernel = np.ones((2,2), np.uint8)
clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)

# --- Detect colonies with contours ---
contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

for cnt in contours:
    area = cv2.contourArea(cnt)
    (x,y), radius = cv2.minEnclosingCircle(cnt)
    size = (math.pi)*((radius)**2)
    if 1 < area < 1600 and (size - area < 900): # adjust thresholds depending on your colonies
        (x, y), radius = cv2.minEnclosingCircle(cnt)
        center = (int(x), int(y))
        radius = int(radius)
        cv2.circle(image, center, radius, (0, 255, 0), 2)
        colony_count += 1




print(f"Detected colonies: {colony_count}")

# --- Show results ---
cv2.imshow("Colonies", image)
cv2.imshow("Clean", clean)
cv2.imshow("Mask", thresh)


cv2.setMouseCallback("Colonies", mouse_callback)


cv2.waitKey(0)
cv2.destroyAllWindows()
