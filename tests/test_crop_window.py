"""Test crop adjustment window in isolation"""
import cv2
import time

print("Opening camera...")
cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("ERROR: Cannot open camera")
    exit(1)

cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

print("Waiting for camera to initialize...")
time.sleep(0.5)

# Test read
ret, frame = cap.read()
if not ret:
    print("ERROR: Cannot read from camera")
    cap.release()
    exit(1)

print(f"SUCCESS: Read frame of size {frame.shape}")

# Crop settings
crop_top, crop_bottom = 240, 465
crop_left, crop_right = 180, 380

print("\nShowing crop adjustment window...")
print("This should show your camera feed with a green rectangle")
print("Try clicking on the window - does Python freeze?")
print("Press ESC to exit\n")

cv2.namedWindow("Test Crop Window")

frame_count = 0
while True:
    ret, frame = cap.read()
    if not ret:
        print(f"Failed to read frame {frame_count}")
        break
    
    frame_count += 1
    if frame_count % 30 == 0:
        print(f"Frames processed: {frame_count}")
    
    # Draw rectangle
    overlay = frame.copy()
    cv2.rectangle(overlay, (crop_left, crop_top), 
                 (crop_right, crop_bottom), (0, 255, 0), 3)
    
    cv2.putText(overlay, f"Frame: {frame_count}", (10, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(overlay, "Press ESC to exit", (10, 460), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    cv2.imshow("Test Crop Window", overlay)
    
    key = cv2.waitKey(1) & 0xFF
    if key == 27:  # ESC
        print("ESC pressed - exiting")
        break

cap.release()
cv2.destroyAllWindows()
print(f"\nTest complete! Processed {frame_count} frames")
