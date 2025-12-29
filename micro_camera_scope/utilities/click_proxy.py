import cv2
import numpy as np
from collections import deque

class InteractiveOrganismTracker:
    """
    Click-to-track organism detector.
    
    Concept:
    1. User clicks on organism
    2. System finds nearest contour to click
    3. Tracks that specific contour across frames
    4. Ignores all other motion (debris, noise, other organisms)
    """
    
    def __init__(self):
        # Video capture
        self.cap = cv2.VideoCapture(1)
        
        # Background subtractor
        self.backsub = cv2.createBackgroundSubtractorMOG2(
            history=500, 
            varThreshold=50, 
            detectShadows=True
        )
        
        # ============================================================
        # TRACKING STATE
        # ============================================================
        self.tracking_active = False
        self.target_position = None  # (x, y) of tracked organism
        self.target_history = deque(maxlen=50)  # Trail of positions
        self.selected_contour = None
        
        # ============================================================
        # MOUSE INTERACTION
        # ============================================================
        self.click_position = None
        self.awaiting_selection = False
        
        # ============================================================
        # TRACKING PARAMETERS
        # ============================================================
        self.MAX_JUMP_DISTANCE = 100  # Max pixels organism can move per frame
        self.MIN_CONTOUR_AREA = 50
        self.MAX_CONTOUR_AREA = 3000
        self.SEARCH_RADIUS = 150  # Search radius around last known position
        
        # ============================================================
        # VISUALIZATION
        # ============================================================
        self.show_all_contours = False  # Toggle to see all detected contours
        self.show_search_radius = True
        self.trail_color = (255, 0, 255)  # Magenta trail
        
        # Performance
        self.frame_count = 0
        
        print("Interactive Organism Tracker Initialized")
        print("Click on an organism to start tracking!")
    
    def mouse_callback(self, event, x, y, flags, param):
        """
        Handle mouse clicks to select organism.
        """
        if event == cv2.EVENT_LBUTTONDOWN:
            self.click_position = (x, y)
            self.awaiting_selection = True
            print(f"\n[CLICK] Position: ({x}, {y})")
            print("Searching for nearest contour...")
    
    def find_nearest_contour(self, contours, target_point):
        """
        Find contour whose centroid is closest to target point.
        
        Args:
            contours: List of contours
            target_point: (x, y) tuple
            
        Returns:
            nearest_contour, distance, centroid
        """
        if not contours:
            return None, float('inf'), None
        
        min_distance = float('inf')
        nearest_contour = None
        nearest_centroid = None
        
        for cnt in contours:
            # Calculate centroid
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Distance to target
            distance = np.sqrt((cx - target_point[0])**2 + (cy - target_point[1])**2)
            
            if distance < min_distance:
                min_distance = distance
                nearest_contour = cnt
                nearest_centroid = (cx, cy)
        
        return nearest_contour, min_distance, nearest_centroid
    
    def filter_contours_near_target(self, contours, target_position):
        """
        Filter contours to only those within search radius of target.
        
        This is the KEY innovation: only look for contours near last known position.
        """
        if target_position is None:
            return contours
        
        filtered = []
        
        for cnt in contours:
            # Calculate centroid
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Distance to last known position
            distance = np.sqrt(
                (cx - target_position[0])**2 + 
                (cy - target_position[1])**2
            )
            
            # Only keep contours within search radius
            if distance <= self.SEARCH_RADIUS:
                filtered.append(cnt)
        
        return filtered
    
    def update_tracking(self, contours):
        """
        Update tracking by finding nearest contour to last known position.
        
        KEY LOGIC:
        1. Filter contours to search radius around last position
        2. Find nearest contour within that radius
        3. Update position
        4. If no contour found nearby → tracking lost
        """
        if not self.tracking_active or self.target_position is None:
            return None
        
        # Filter to contours near last known position
        nearby_contours = self.filter_contours_near_target(contours, self.target_position)
        
        if not nearby_contours:
            # No contours nearby → organism might have left frame or stopped moving
            return None
        
        # Find nearest contour to last position
        nearest_cnt, distance, centroid = self.find_nearest_contour(
            nearby_contours, 
            self.target_position
        )
        
        if nearest_cnt is None:
            return None
        
        # Check if jump is reasonable (organism can't teleport)
        if distance > self.MAX_JUMP_DISTANCE:
            print(f"[WARNING] Large jump detected: {distance:.1f}px - possible tracking loss")
            # Could choose to stop tracking here, or continue with caution
            # return None  # Uncomment to stop tracking on large jumps
        
        # Update tracking state
        self.target_position = centroid
        self.target_history.append(centroid)
        self.selected_contour = nearest_cnt
        
        return nearest_cnt
    
    def draw_tracking_info(self, frame):
        """
        Draw all tracking visualizations.
        """
        # Draw click position if awaiting selection
        if self.awaiting_selection and self.click_position:
            cv2.circle(frame, self.click_position, 10, (0, 0, 255), 2)
            cv2.circle(frame, self.click_position, 15, (0, 0, 255), 1)
            cv2.putText(frame, "Click", 
                       (self.click_position[0] + 20, self.click_position[1]),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        # Draw tracking info if active
        if self.tracking_active and self.target_position:
            cx, cy = self.target_position
            
            # Search radius circle
            if self.show_search_radius:
                cv2.circle(frame, (cx, cy), self.SEARCH_RADIUS, (255, 255, 0), 1)
            
            # Draw tracked contour (thick green outline)
            if self.selected_contour is not None:
                cv2.drawContours(frame, [self.selected_contour], -1, (0, 255, 0), 3)
            
            # Centroid marker
            cv2.circle(frame, (cx, cy), 8, (0, 0, 255), -1)
            cv2.circle(frame, (cx, cy), 12, (255, 255, 255), 2)
            
            # Coordinates
            cv2.putText(frame, f"TRACKING: ({cx}, {cy})", 
                       (cx + 15, cy - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"TRACKING: ({cx}, {cy})", 
                       (cx + 15, cy - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
            
            # Trail of previous positions
            if len(self.target_history) > 1:
                points = np.array(self.target_history, dtype=np.int32)
                cv2.polylines(frame, [points], False, self.trail_color, 2)
                
                # Draw dots along trail
                for i, point in enumerate(self.target_history):
                    alpha = i / len(self.target_history)  # Fade older points
                    radius = int(3 + 2 * alpha)
                    cv2.circle(frame, point, radius, self.trail_color, -1)
        
        # Status overlay
        status_bg = frame.copy()
        cv2.rectangle(status_bg, (0, 0), (frame.shape[1], 80), (0, 0, 0), -1)
        cv2.addWeighted(status_bg, 0.4, frame, 0.6, 0, frame)
        
        # Status text
        if self.tracking_active:
            status = "TRACKING ACTIVE"
            color = (0, 255, 0)
            trail_length = len(self.target_history)
            cv2.putText(frame, f"Trail Length: {trail_length} frames",
                       (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        else:
            status = "CLICK TO SELECT ORGANISM"
            color = (0, 165, 255)
        
        cv2.putText(frame, status, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # Controls
        cv2.putText(frame, "Controls: CLICK=Select | R=Reset | A=Show All | S=Save | Q=Quit",
                   (10, frame.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    def draw_all_contours(self, frame, contours):
        """
        Draw all detected contours in semi-transparent blue (debug mode).
        """
        if not self.show_all_contours:
            return
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if self.MIN_CONTOUR_AREA < area < self.MAX_CONTOUR_AREA:
                # Calculate centroid
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # Draw faint contour
                    cv2.drawContours(frame, [cnt], -1, (255, 200, 100), 1)
                    cv2.circle(frame, (cx, cy), 3, (255, 200, 100), -1)
    
    def run(self):
        """
        Main tracking loop.
        """
        print("\n" + "="*70)
        print("INTERACTIVE ORGANISM TRACKER")
        print("="*70)
        print("\nHow to use:")
        print("  1. Wait for video to start")
        print("  2. Click directly on a moving organism")
        print("  3. System will lock onto nearest contour and track it")
        print("  4. Press 'R' to reset and select a different organism")
        print("\nControls:")
        print("  LEFT CLICK - Select organism to track")
        print("  'r' - Reset tracking (select new organism)")
        print("  'a' - Toggle show all contours (debug)")
        print("  's' - Toggle search radius visualization")
        print("  'p' - Save screenshot")
        print("  'q' - Quit")
        print("\n" + "="*70 + "\n")
        
        # Create window and set mouse callback
        window_name = 'Interactive Organism Tracker'
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, self.mouse_callback)
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to read frame")
                break
            
            self.frame_count += 1
            
            # ============================================================
            # STEP 1: Background Subtraction & Preprocessing
            # ============================================================
            fg_mask = self.backsub.apply(frame)
            
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
            valid_contours = [
                cnt for cnt in contours 
                if self.MIN_CONTOUR_AREA < cv2.contourArea(cnt) < self.MAX_CONTOUR_AREA
            ]
            
            # ============================================================
            # STEP 3: Handle Mouse Click Selection
            # ============================================================
            if self.awaiting_selection and self.click_position:
                # Find nearest contour to click position
                nearest_cnt, distance, centroid = self.find_nearest_contour(
                    valid_contours, 
                    self.click_position
                )
                
                if nearest_cnt is not None and distance < 100:
                    # Start tracking this organism
                    self.tracking_active = True
                    self.target_position = centroid
                    self.selected_contour = nearest_cnt
                    self.target_history.clear()
                    self.target_history.append(centroid)
                    
                    print(f"[LOCKED] Organism at ({centroid[0]}, {centroid[1]})")
                    print(f"         Distance from click: {distance:.1f}px")
                    print(f"         Contour area: {cv2.contourArea(nearest_cnt):.0f}px²")
                else:
                    print(f"[FAILED] No contour found near click position")
                    print(f"         Nearest contour: {distance:.1f}px away")
                
                self.awaiting_selection = False
                self.click_position = None
            
            # ============================================================
            # STEP 4: Update Tracking
            # ============================================================
            if self.tracking_active:
                tracked_contour = self.update_tracking(valid_contours)
                
                if tracked_contour is None:
                    # Lost tracking
                    print(f"[LOST] Tracking lost at frame {self.frame_count}")
                    print("       Click on organism again to re-track")
                    self.tracking_active = False
            
            # ============================================================
            # STEP 5: Visualization
            # ============================================================
            display_frame = frame.copy()
            
            # Draw all contours if debug mode
            self.draw_all_contours(display_frame, valid_contours)
            
            # Draw tracking overlays
            self.draw_tracking_info(display_frame)
            
            # Show frames
            cv2.imshow(window_name, display_frame)
            cv2.imshow('Motion Mask', mask_cleaned)
            
            # ============================================================
            # STEP 6: Keyboard Controls
            # ============================================================
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('r'):
                # Reset tracking
                print("\n[RESET] Tracking cleared - click to select new organism")
                self.tracking_active = False
                self.target_position = None
                self.target_history.clear()
                self.selected_contour = None
            elif key == ord('a'):
                # Toggle show all contours
                self.show_all_contours = not self.show_all_contours
                print(f"[TOGGLE] Show all contours: {'ON' if self.show_all_contours else 'OFF'}")
            elif key == ord('s'):
                # Toggle search radius
                self.show_search_radius = not self.show_search_radius
                print(f"[TOGGLE] Search radius: {'ON' if self.show_search_radius else 'OFF'}")
            elif key == ord('p'):
                # Save screenshot
                filename = f"tracked_organism_{self.frame_count}.png"
                cv2.imwrite(filename, display_frame)
                print(f"[SAVED] {filename}")
            
            # Print position every 30 frames
            if self.tracking_active and self.frame_count % 30 == 0:
                cx, cy = self.target_position
                print(f"Frame {self.frame_count}: Organism at ({cx}, {cy})")
        
        # Cleanup
        self.cap.release()
        cv2.destroyAllWindows()
        
        # Print summary
        if self.target_history:
            print("\n" + "="*70)
            print("TRACKING SUMMARY")
            print("="*70)
            print(f"Total frames tracked: {len(self.target_history)}")
            print(f"Start position: {self.target_history[0]}")
            print(f"End position: {self.target_history[-1]}")
            
            # Calculate total distance traveled
            total_distance = 0
            for i in range(1, len(self.target_history)):
                p1 = self.target_history[i-1]
                p2 = self.target_history[i]
                total_distance += np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
            
            print(f"Total distance traveled: {total_distance:.1f} pixels")
            print("="*70)


# ============================================================
# SIMPLIFIED VERSION (Even More Minimal)
# ============================================================

class SimpleClickTracker:
    """
    Ultra-minimal click-to-track implementation.
    """
    
    def __init__(self):
        self.cap = cv2.VideoCapture(1)
        self.backsub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=True)
        self.target_pos = None
        self.tracking = False
        
    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.click_pos = (x, y)
    
    def find_nearest(self, contours, point):
        best = None
        best_dist = 999999
        for cnt in contours:
            M = cv2.moments(cnt)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                dist = np.sqrt((cx - point[0])**2 + (cy - point[1])**2)
                if dist < best_dist:
                    best_dist = dist
                    best = (cnt, cx, cy)
        return best
    
    def run(self):
        cv2.namedWindow('Tracker')
        cv2.setMouseCallback('Tracker', self.mouse_callback)
        self.click_pos = None
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            # Get contours
            fg_mask = self.backsub.apply(frame)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask_cleaned = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(mask_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            valid = [c for c in contours if 50 < cv2.contourArea(c) < 1000]
            
            # Handle click
            if self.click_pos:
                result = self.find_nearest(valid, self.click_pos)
                if result and result[1]:
                    self.target_pos = (result[1], result[2])
                    self.tracking = True
                    print(f"Locked: {self.target_pos}")
                self.click_pos = None
            
            # Update tracking
            if self.tracking and self.target_pos:
                result = self.find_nearest(valid, self.target_pos)
                if result and result[1]:
                    cnt, cx, cy = result
                    self.target_pos = (cx, cy)
                    
                    # Draw
                    cv2.drawContours(frame, [cnt], -1, (0, 255, 0), 2)
                    cv2.circle(frame, (cx, cy), 7, (0, 0, 255), -1)
                    cv2.putText(frame, f"({cx},{cy})", (cx+10, cy-10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            cv2.putText(frame, "Click to track" if not self.tracking else "Tracking...",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow('Tracker', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                self.tracking = False
                self.target_pos = None
        
        self.cap.release()
        cv2.destroyAllWindows()


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    print("Select tracker:")
    print("1 - Full-featured interactive tracker (recommended)")
    print("2 - Simple minimal tracker")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "2":
        tracker = SimpleClickTracker()
    else:
        tracker = InteractiveOrganismTracker()
    
    tracker.run()