"""Simple camera test to verify camera index and functionality"""
import cv2
import time

print("Testing camera access...")

# Try camera index 1 (your phone camera)
cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("ERROR: Could not open camera at index 1")
    print("Trying index 0...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open camera at index 0 either")
        exit(1)
    else:
        print("SUCCESS: Camera opened at index 0")
else:
    print("SUCCESS: Camera opened at index 1")

# Set properties
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

print("Waiting for camera to initialize...")
time.sleep(1)

# Try to read a few frames
for i in range(5):
    ret, frame = cap.read()
    if ret:
        print(f"Frame {i+1}: Successfully read {frame.shape}")
    else:
        print(f"Frame {i+1}: FAILED to read")
    time.sleep(0.1)

# Show one frame
print("\nShowing test frame - press any key to close...")
ret, frame = cap.read()
if ret:
    cv2.imshow("Camera Test", frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
else:
    print("ERROR: Could not read frame for display")

cap.release()
print("\nCamera test complete!")
