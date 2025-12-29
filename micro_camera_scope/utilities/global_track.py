import cv2
import numpy as np
from collections import deque

class OrganismMotionDetector:
    """
    Detects independently moving microorganisms while compensating for stage movement.
    Uses optical flow to track global motion vs local motion.
    """
    
    def __init__(self):
        # Video capture
        self.cap = cv2.VideoCapture(1)
        
        # Background subtraction
        self.backsub = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=16,
            detectShadows=False
        )
        
        # Optical flow parameters for stage motion detection
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # Feature detection for optical flow
        self.feature_params = dict(
            maxCorners=100,
            qualityLevel=0.3,
            minDistance=7,
            blockSize=7
        )
        
        # State variables
        self.prev_gray = None
        self.prev_points = None
        self.stage_motion_history = deque(maxlen=10)
        
        # Motion accumulator for organism tracking
        self.motion_accumulator = None
        self.organism_tracks = {}  # Track organisms over time
        self.next_track_id = 0
        
        # Parameters
        self.ACCUM_DECAY = 0.85
        self.ACCUM_GAIN = 1.5
        self.MIN_ORGANISM_AREA = 30
        self.MAX_ORGANISM_AREA = 5000
        self.STAGE_MOTION_THRESHOLD = 5.0  # pixels average displacement
        self.ORGANISM_MOTION_THRESHOLD = 2.0  # pixels relative to stage
        self.TRACK_MAX_DISTANCE = 50  # max pixels to associate tracks
        self.TRACK_MIN_FRAMES = 3  # minimum frames to confirm organism
        
    def estimate_stage_motion(self, gray):
        """
        Estimate global stage motion using sparse optical flow.
        Returns: (dx, dy, is_stage_moving)
        """
        if self.prev_gray is None:
            self.prev_gray = gray.copy()
            return 0, 0, False
        
        # Detect features to track
        if self.prev_points is None or len(self.prev_points) < 20:
            self.prev_points = cv2.goodFeaturesToTrack(
                self.prev_gray, 
                mask=None, 
                **self.feature_params
            )
            
            if self.prev_points is None:
                return 0, 0, False
        
        # Calculate optical flow
        next_points, status, error = cv2.calcOpticalFlowPyrLK(
            self.prev_gray, 
            gray, 
            self.prev_points, 
            None, 
            **self.lk_params
        )
        
        # Select good points
        if next_points is None:
            self.prev_points = None
            return 0, 0, False
        
        good_old = self.prev_points[status == 1]
        good_new = next_points[status == 1]
        
        if len(good_old) < 10:
            self.prev_points = None
            return 0, 0, False
        
        # Calculate displacement vectors
        displacements = good_new - good_old
        
        # Use RANSAC-like approach: find median displacement (robust to outliers)
        dx_median = np.median(displacements[:, 0])
        dy_median = np.median(displacements[:, 1])
        
        # Calculate how much variation there is (detect if motion is uniform)
        dx_std = np.std(displacements[:, 0])
        dy_std = np.std(displacements[:, 1])
        
        displacement_magnitude = np.sqrt(dx_median**2 + dy_median**2)
        
        # Stage is moving if:
        # 1. Median displacement is significant
        # 2. Motion is relatively uniform (low std deviation)
        is_stage_moving = (
            displacement_magnitude > self.STAGE_MOTION_THRESHOLD and
            dx_std < 10 and dy_std < 10
        )
        
        # Update for next frame
        self.prev_points = good_new.reshape(-1, 1, 2)
        self.prev_gray = gray.copy()
        
        # Track stage motion over time
        self.stage_motion_history.append(is_stage_moving)
        
        return dx_median, dy_median, is_stage_moving
    
    def compensate_motion(self, mask, dx, dy):
        """
        Shift mask to compensate for stage motion.
        """
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            return mask
        
        # Create transformation matrix
        M = np.float32([[1, 0, -dx], [0, 1, -dy]])
        
        # Warp the mask
        compensated = cv2.warpAffine(
            mask, 
            M, 
            (mask.shape[1], mask.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0
        )
        
        return compensated
    
    def detect_organisms(self, frame):
        """
        Main detection pipeline with stage motion compensation.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Estimate stage motion
        dx, dy, is_stage_moving = self.estimate_stage_motion(gray)
        
        # Apply background subtraction
        fg_mask = self.backsub.apply(frame, learningRate=0.001 if is_stage_moving else -1)
        
        # Aggressive thresholding
        _, fg_mask = cv2.threshold(fg_mask, 240, 255, cv2.THRESH_BINARY)
        
        # Initialize accumulator
        if self.motion_accumulator is None:
            self.motion_accumulator = np.zeros_like(fg_mask, dtype=np.float32)
        
        # Motion compensation strategy
        if is_stage_moving:
            # During stage movement: heavily decay accumulator
            self.motion_accumulator *= 0.5
            
            # Compensate foreground mask for stage motion
            fg_mask = self.compensate_motion(fg_mask, dx, dy)
            
            # Only accumulate strong, persistent motion during stage movement
            strong_motion = fg_mask.astype(np.float32) * 0.3
            self.motion_accumulator = np.maximum(
                self.motion_accumulator * 0.7,
                strong_motion
            )
        else:
            # Stage stable: normal accumulation
            self.motion_accumulator = (
                self.motion_accumulator * self.ACCUM_DECAY +
                fg_mask.astype(np.float32) * self.ACCUM_GAIN
            )
        
        # Threshold accumulated motion
        accum_mask = np.uint8(self.motion_accumulator > 80) * 255
        
        # Morphological operations - tuned for small organisms
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        
        accum_mask = cv2.morphologyEx(accum_mask, cv2.MORPH_OPEN, kernel_open)
        accum_mask = cv2.morphologyEx(accum_mask, cv2.MORPH_CLOSE, kernel_close)
        
        # Find contours
        contours, _ = cv2.findContours(
            accum_mask, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Detect organisms
        organisms = []
        
        for c in contours:
            area = cv2.contourArea(c)
            
            # Size filtering
            if area < self.MIN_ORGANISM_AREA or area > self.MAX_ORGANISM_AREA:
                continue
            
            # Shape filtering - reject linear artifacts
            perimeter = cv2.arcLength(c, True)
            if perimeter == 0:
                continue
            
            circularity = 4 * np.pi * area / (perimeter ** 2)
            
            # Skip very elongated objects (likely artifacts)
            if circularity < 0.1:
                continue
            
            # Calculate centroid
            M = cv2.moments(c)
            if M["m00"] == 0:
                continue
            
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Calculate bounding box
            x, y, w, h = cv2.boundingRect(c)
            
            organisms.append({
                'centroid': (cx, cy),
                'contour': c,
                'area': area,
                'bbox': (x, y, w, h),
                'circularity': circularity
            })
        
        return organisms, is_stage_moving, (dx, dy), fg_mask, accum_mask
    
    def draw_results(self, frame, organisms, is_stage_moving, stage_motion):
        """
        Visualize detection results.
        """
        dx, dy = stage_motion
        
        # Draw stage motion indicator
        status_color = (0, 0, 255) if is_stage_moving else (0, 255, 0)
        status_text = "STAGE MOVING" if is_stage_moving else "STABLE"
        
        cv2.putText(
            frame, 
            f"{status_text} | Motion: ({dx:.1f}, {dy:.1f})",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.6, 
            status_color, 
            2
        )
        
        # Draw detected organisms
        for i, org in enumerate(organisms):
            cx, cy = org['centroid']
            contour = org['contour']
            area = org['area']
            x, y, w, h = org['bbox']
            
            # Draw contour
            cv2.drawContours(frame, [contour], -1, (0, 255, 0), 2)
            
            # Draw bounding box
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 0), 1)
            
            # Draw centroid
            cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)
            
            # Label
            label = f"Org {i+1}: ({cx},{cy})"
            cv2.putText(
                frame, 
                label,
                (cx + 10, cy - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.4, 
                (255, 255, 255), 
                1
            )
            
            # Area info
            cv2.putText(
                frame,
                f"Area: {area:.0f}",
                (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.3,
                (255, 255, 0),
                1
            )
        
        # Organism count
        cv2.putText(
            frame,
            f"Organisms: {len(organisms)}",
            (10, frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2
        )
        
        return frame
    
    def run(self):
        """
        Main loop.
        """
        print("Starting organism motion detector...")
        print("Controls:")
        print("  'q' - Quit")
        print("  'r' - Reset background model")
        print("  's' - Save current frame")
        
        frame_count = 0
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Detect organisms
            organisms, is_stage_moving, stage_motion, fg_mask, accum_mask = \
                self.detect_organisms(frame)
            
            # Draw results
            display_frame = self.draw_results(
                frame.copy(), 
                organisms, 
                is_stage_moving, 
                stage_motion
            )
            
            # Create debug view
            fg_display = cv2.cvtColor(fg_mask, cv2.COLOR_GRAY2BGR)
            accum_display = cv2.cvtColor(accum_mask, cv2.COLOR_GRAY2BGR)
            
            # Combine views
            top_row = np.hstack([display_frame, fg_display])
            bottom_row = np.hstack([accum_display, np.zeros_like(accum_display)])
            combined = np.vstack([top_row, bottom_row])
            
            # Resize for display
            scale = 0.7
            combined_resized = cv2.resize(
                combined, 
                None, 
                fx=scale, 
                fy=scale
            )
            
            cv2.imshow("Organism Motion Detection", combined_resized)
            
            # Keyboard controls
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('r'):
                print("Resetting background model...")
                self.backsub = cv2.createBackgroundSubtractorMOG2(
                    history=500,
                    varThreshold=16,
                    detectShadows=False
                )
                self.motion_accumulator = None
            elif key == ord('s'):
                filename = f"organism_detection_{frame_count}.png"
                cv2.imwrite(filename, display_frame)
                print(f"Saved: {filename}")
            
            # Print organism coordinates every 30 frames
            if frame_count % 30 == 0 and organisms:
                print(f"\nFrame {frame_count} - Detected {len(organisms)} organisms:")
                for i, org in enumerate(organisms):
                    cx, cy = org['centroid']
                    area = org['area']
                    print(f"  Organism {i+1}: Position ({cx}, {cy}), Area: {area:.0f}")
        
        self.cap.release()
        cv2.destroyAllWindows()


# ============================================================
# SIMPLIFIED VERSION (If optical flow is too slow)
# ============================================================

class SimpleOrganismDetector:
    """
    Simpler approach using frame differencing with temporal filtering.
    Faster but less robust to stage movement.
    """
    
    def __init__(self):
        self.cap = cv2.VideoCapture(1)
        self.prev_frames = deque(maxlen=3)
        self.MIN_AREA = 30
        self.MAX_AREA = 5000
        
    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        
        self.prev_frames.append(gray)
        
        if len(self.prev_frames) < 3:
            return [], frame
        
        # Multi-frame difference (reduces stage motion artifacts)
        diff1 = cv2.absdiff(self.prev_frames[0], self.prev_frames[1])
        diff2 = cv2.absdiff(self.prev_frames[1], self.prev_frames[2])
        
        # Intersection of motion
        motion = cv2.bitwise_and(diff1, diff2)
        
        _, thresh = cv2.threshold(motion, 25, 255, cv2.THRESH_BINARY)
        
        # Morphology
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        organisms = []
        for c in contours:
            area = cv2.contourArea(c)
            if self.MIN_AREA < area < self.MAX_AREA:
                M = cv2.moments(c)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    organisms.append({'centroid': (cx, cy), 'contour': c, 'area': area})
                    
                    cv2.drawContours(frame, [c], -1, (0, 255, 0), 2)
                    cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)
                    cv2.putText(frame, f"({cx},{cy})", (cx+10, cy-10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        return organisms, frame
    
    def run(self):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            organisms, display = self.detect(frame)
            
            cv2.putText(display, f"Organisms: {len(organisms)}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            cv2.imshow("Simple Organism Detection", display)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        cv2.destroyAllWindows()


# ============================================================
# USAGE
# ============================================================

if __name__ == "__main__":
    print("Select detector:")
    print("1 - Advanced (with stage motion compensation)")
    print("2 - Simple (faster, less robust)")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "2":
        detector = SimpleOrganismDetector()
    else:
        detector = OrganismMotionDetector()
    
    detector.run()