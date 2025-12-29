import cv2
import numpy as np

# Initialize video capture (0 is usually the default webcam)
cap = cv2.VideoCapture(1)

# Background Subtractor
backsub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=True)

# Create window and set mouse callback
window_name = 'Contour Tracker'
cv2.namedWindow(window_name)

print("Contour Tracker Started")
print("Press 'q' to quit")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to read frame")
        break

    # ============================================================
    # STEP 1: Background Subtraction & Preprocessing
    # ============================================================
    fg_mask = backsub.apply(frame)
    
    # Clean up noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_cleaned = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
    
    # ============================================================
    # STEP 2: Find Contours
    # ============================================================
    contours, _ = cv2.findContours(
        mask_cleaned, 
        cv2.RETR_EXTERNAL, 
        cv2.CHAIN_APPROX_SIMPLE
    )
    
    # Filter by area
    MIN_CONTOUR_AREA = 50
    MAX_CONTOUR_AREA = 3000
    valid_contours = [
        cnt for cnt in contours 
        if MIN_CONTOUR_AREA < cv2.contourArea(cnt) < MAX_CONTOUR_AREA
    ]
    
    # ============================================================
    # STEP 3: Visualization
    # ============================================================
    display_frame = frame.copy()
    
    # Draw all valid contours
    for cnt in valid_contours:
        # Calculate centroid
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Draw contour (green outline)
            cv2.drawContours(display_frame, [cnt], -1, (0, 255, 0), 3)
            
            # Centroid marker
            cv2.circle(display_frame, (cx, cy), 8, (0, 0, 255), -1)
            cv2.circle(display_frame, (cx, cy), 12, (255, 255, 255), 2)
            
            # Coordinates
            cv2.putText(display_frame, f"({cx}, {cy})", 
                       (cx + 15, cy - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(display_frame, f"({cx}, {cy})", 
                       (cx + 15, cy - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
    
    # Status overlay
    status_bg = display_frame.copy()
    cv2.rectangle(status_bg, (0, 0), (display_frame.shape[1], 80), (0, 0, 0), -1)
    cv2.addWeighted(status_bg, 0.4, display_frame, 0.6, 0, display_frame)
    
    # Status text
    status = f"TRACKING {len(valid_contours)} OBJECTS"
    cv2.putText(display_frame, status, (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # Controls
    cv2.putText(display_frame, "Press 'q' to quit",
               (10, display_frame.shape[0] - 10),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    # Show frames
    cv2.imshow(window_name, display_frame)
    cv2.imshow('Motion Mask', mask_cleaned)
    
    # ============================================================
    # STEP 4: Keyboard Controls
    # ============================================================
    key = cv2.waitKey(1) & 0xFF
    
    if key == ord('q'):
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()