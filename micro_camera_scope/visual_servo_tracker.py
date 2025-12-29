"""
Visual Servoing Tracker - Integrates organism tracking with motor control
for closed-loop visual servoing to keep tracked organisms centered.

This module combines the InteractiveOrganismTracker with Arduino motor control
to implement automatic stage movement that keeps tracked organisms centered
in the camera frame.
"""

import cv2
import numpy as np
from collections import deque
import time
import threading
from queue import Queue, Empty

class VisualServoTracker:
    """
    Visual servoing tracker that combines organism tracking with motor control.
    
    Key Features:
    - Click-to-select organism tracking (from InteractiveOrganismTracker)
    - Automatic motor control to keep organism centered
    - Configurable deadzone, rate limiting, and safety checks
    - Toggle-able auto-tracking mode
    """
    
    def __init__(self, motor_controller=None):
        """
        Initialize the visual servo tracker.
        
        Args:
            motor_controller: Object with send_step(y_cmd, x_cmd) method for motor control
        """
        # Motor control interface
        self.motor_controller = motor_controller
        self.auto_tracking_enabled = False
        
        # ============================================================
        # VISUAL SERVOING CALIBRATION CONSTANTS
        # ============================================================
        # These values need to be calibrated for your specific setup
        # Pixels per motor step - adjust based on your microscope/camera setup
        self.PIXELS_PER_STEP_X = 2.0  # Horizontal pixels per motor step
        self.PIXELS_PER_STEP_Y = 2.0  # Vertical pixels per motor step
        
        # Control parameters
        self.DEADZONE_PIXELS = 10     # Don't move if error is smaller than this
        self.MAX_STEPS_PER_COMMAND = 5  # Maximum steps to send in one command
        self.MIN_COMMAND_INTERVAL = 0.2  # Minimum seconds between motor commands
        
        # Frame center (will be set when camera starts)
        self.CENTER_X = None
        self.CENTER_Y = None
        self.frame_width = None
        self.frame_height = None
        
        # ============================================================
        # TRACKING STATE (from InteractiveOrganismTracker)
        # ============================================================
        self.tracking_active = False
        self.target_position = None  # (x, y) of tracked organism
        self.target_history = deque(maxlen=50)  # Trail of positions
        self.selected_contour = None
        
        # Mouse interaction
        self.click_position = None
        self.awaiting_selection = False
        
        # Tracking parameters
        self.MAX_JUMP_DISTANCE = 100
        self.MIN_CONTOUR_AREA = 50
        self.MAX_CONTOUR_AREA = 3000
        self.SEARCH_RADIUS = 150
        
        # Visualization
        self.show_all_contours = False
        self.show_search_radius = True
        self.show_center_crosshair = True
        self.trail_color = (255, 0, 255)  # Magenta trail
        
        # ============================================================
        # MOTOR CONTROL STATE
        # ============================================================
        self.last_command_time = 0
        self.motor_command_queue = Queue(maxsize=10)
        self.motor_thread = None
        self.motor_thread_active = False
        
        # Statistics
        self.frame_count = 0
        self.commands_sent = 0
        self.tracking_errors = []  # Store recent tracking errors for analysis
        
        print("Visual Servo Tracker Initialized")
        print("Features: Click-to-track + Auto-centering motor control")
    
    def set_frame_dimensions(self, width, height):
        """
        Set frame dimensions and compute center coordinates.
        Call this when camera is initialized.
        """
        self.frame_width = width
        self.frame_height = height
        self.CENTER_X = width // 2
        self.CENTER_Y = height // 2
        print(f"Frame center set to ({self.CENTER_X}, {self.CENTER_Y})")
    
    def set_motor_controller(self, motor_controller):
        """Set the motor controller interface."""
        self.motor_controller = motor_controller
        print("Motor controller connected to visual servo tracker")
    
    def toggle_auto_tracking(self):
        """Toggle automatic motor control on/off."""
        self.auto_tracking_enabled = not self.auto_tracking_enabled
        
        if self.auto_tracking_enabled:
            self.start_motor_thread()
            print("AUTO-TRACKING ENABLED - Stage will move to keep organism centered")
        else:
            self.stop_motor_thread()
            print("AUTO-TRACKING DISABLED - Manual control only")
        
        return self.auto_tracking_enabled
    
    def start_motor_thread(self):
        """Start the motor control thread."""
        if not self.motor_thread_active:
            self.motor_thread_active = True
            self.motor_thread = threading.Thread(target=self._motor_control_loop)
            self.motor_thread.daemon = True
            self.motor_thread.start()
    
    def stop_motor_thread(self):
        """Stop the motor control thread."""
        self.motor_thread_active = False
        if self.motor_thread:
            self.motor_thread.join(timeout=1.0)
    
    def compute_motor_steps(self, cx, cy):
        """
        Convert pixel error to motor steps with safety checks.
        
        Args:
            cx, cy: Current organism position in pixels
            
        Returns:
            (steps_x, steps_y): Motor steps needed to center organism
                               Returns (0, 0) if within deadzone or invalid
        """
        if self.CENTER_X is None or self.CENTER_Y is None:
            return 0, 0
        
        # Compute pixel error (organism position relative to frame center)
        error_x = cx - self.CENTER_X
        error_y = cy - self.CENTER_Y
        
        # Apply deadzone - don't move if error is small
        if abs(error_x) < self.DEADZONE_PIXELS:
            error_x = 0
        if abs(error_y) < self.DEADZONE_PIXELS:
            error_y = 0
        
        # Convert pixel error to motor steps
        steps_x = int(error_x / self.PIXELS_PER_STEP_X)
        steps_y = int(error_y / self.PIXELS_PER_STEP_Y)
        
        # Clamp to maximum steps per command (safety)
        steps_x = max(-self.MAX_STEPS_PER_COMMAND, min(steps_x, self.MAX_STEPS_PER_COMMAND))
        steps_y = max(-self.MAX_STEPS_PER_COMMAND, min(steps_y, self.MAX_STEPS_PER_COMMAND))
        
        # Store error for analysis
        if len(self.tracking_errors) > 100:
            self.tracking_errors.pop(0)
        self.tracking_errors.append((error_x, error_y))
        
        return steps_x, steps_y
    
    def send_motor_command(self, steps_x, steps_y):
        """
        Send relative motor command to Arduino.
        
        Args:
            steps_x: Steps in X direction (positive = right)
            steps_y: Steps in Y direction (positive = up)
        """
        if not self.motor_controller:
            return False
        
        # Rate limiting - don't send commands too frequently
        current_time = time.time()
        if current_time - self.last_command_time < self.MIN_COMMAND_INTERVAL:
            return False
        
        # Convert steps to Arduino command format
        # Note: You may need to adjust the sign conventions based on your setup
        y_cmd = 'S'  # Default to stop
        x_cmd = 'S'  # Default to stop
        
        # Y-axis movement (vertical)
        if steps_y > 0:
            y_cmd = 'U'  # Move up
        elif steps_y < 0:
            y_cmd = 'D'  # Move down
        
        # X-axis movement (horizontal)  
        if steps_x > 0:
            x_cmd = 'R'  # Move right
        elif steps_x < 0:
            x_cmd = 'L'  # Move left
        
        # Send command if there's movement needed
        if y_cmd != 'S' or x_cmd != 'S':
            success = self.motor_controller.send_step(y_cmd, x_cmd)
            if success:
                self.last_command_time = current_time
                self.commands_sent += 1
                print(f"Motor command: {y_cmd}{x_cmd} (steps: {steps_x}, {steps_y})")
            return success
        
        return True  # No movement needed is considered success
    
    def _motor_control_loop(self):
        """
        Motor control thread - processes motor commands from queue.
        This runs continuously when auto-tracking is enabled.
        """
        while self.motor_thread_active:
            try:
                # Check if we have a valid tracking target
                if (self.tracking_active and 
                    self.target_position is not None and 
                    self.auto_tracking_enabled):
                    
                    cx, cy = self.target_position
                    steps_x, steps_y = self.compute_motor_steps(cx, cy)
                    
                    # Send motor command if movement is needed
                    if steps_x != 0 or steps_y != 0:
                        self.send_motor_command(steps_x, steps_y)
                
                time.sleep(0.1)  # 10 Hz control loop
                
            except Exception as e:
                print(f"Motor control loop error: {e}")
                time.sleep(0.5)
    
    # ============================================================
    # TRACKING METHODS (from InteractiveOrganismTracker)
    # ============================================================
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse clicks to select organism."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.click_position = (x, y)
            self.awaiting_selection = True
            print(f"\n[CLICK] Position: ({x}, {y})")
            print("Searching for nearest contour...")
    
    def find_nearest_contour(self, contours, target_point):
        """Find contour whose centroid is closest to target point."""
        if not contours:
            return None, float('inf'), None
        
        min_distance = float('inf')
        nearest_contour = None
        nearest_centroid = None
        
        for cnt in contours:
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            distance = np.sqrt((cx - target_point[0])**2 + (cy - target_point[1])**2)
            
            if distance < min_distance:
                min_distance = distance
                nearest_contour = cnt
                nearest_centroid = (cx, cy)
        
        return nearest_contour, min_distance, nearest_centroid
    
    def filter_contours_near_target(self, contours, target_position):
        """Filter contours to only those within search radius of target."""
        if target_position is None:
            return contours
        
        filtered = []
        for cnt in contours:
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            distance = np.sqrt(
                (cx - target_position[0])**2 + 
                (cy - target_position[1])**2
            )
            
            if distance <= self.SEARCH_RADIUS:
                filtered.append(cnt)
        
        return filtered
    
    def update_tracking(self, contours):
        """
        Update tracking by finding nearest contour to last known position.
        This is the main tracking update method called each frame.
        """
        if not self.tracking_active or self.target_position is None:
            return None
        
        # Filter to contours near last known position
        nearby_contours = self.filter_contours_near_target(contours, self.target_position)
        
        if not nearby_contours:
            return None
        
        # Find nearest contour to last position
        nearest_cnt, distance, centroid = self.find_nearest_contour(
            nearby_contours, 
            self.target_position
        )
        
        if nearest_cnt is None:
            return None
        
        # Check if jump is reasonable
        if distance > self.MAX_JUMP_DISTANCE:
            print(f"[WARNING] Large jump detected: {distance:.1f}px - possible tracking loss")
        
        # Update tracking state
        self.target_position = centroid
        self.target_history.append(centroid)
        self.selected_contour = nearest_cnt
        
        return nearest_cnt
    
    def handle_click_selection(self, contours):
        """Handle mouse click selection of organism."""
        if self.awaiting_selection and self.click_position:
            nearest_cnt, distance, centroid = self.find_nearest_contour(
                contours, 
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
                
                if self.auto_tracking_enabled:
                    print("         Auto-tracking will keep organism centered")
            else:
                print(f"[FAILED] No contour found near click position")
                print(f"         Nearest contour: {distance:.1f}px away")
            
            self.awaiting_selection = False
            self.click_position = None
    
    def reset_tracking(self):
        """Reset tracking state."""
        print("\n[RESET] Tracking cleared - click to select new organism")
        self.tracking_active = False
        self.target_position = None
        self.target_history.clear()
        self.selected_contour = None
        self.tracking_errors.clear()
    
    # ============================================================
    # VISUALIZATION METHODS
    # ============================================================
    
    def draw_tracking_info(self, frame):
        """Draw all tracking and motor control visualizations."""
        # Draw frame center crosshair
        if self.show_center_crosshair and self.CENTER_X is not None:
            cv2.line(frame, (self.CENTER_X - 20, self.CENTER_Y), 
                    (self.CENTER_X + 20, self.CENTER_Y), (0, 255, 255), 2)
            cv2.line(frame, (self.CENTER_X, self.CENTER_Y - 20), 
                    (self.CENTER_X, self.CENTER_Y + 20), (0, 255, 255), 2)
            cv2.circle(frame, (self.CENTER_X, self.CENTER_Y), 5, (0, 255, 255), -1)
        
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
            
            # Coordinates and error info
            if self.CENTER_X is not None:
                error_x = cx - self.CENTER_X
                error_y = cy - self.CENTER_Y
                steps_x, steps_y = self.compute_motor_steps(cx, cy)
                
                cv2.putText(frame, f"TRACKING: ({cx}, {cy})", 
                           (cx + 15, cy - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(frame, f"TRACKING: ({cx}, {cy})", 
                           (cx + 15, cy - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
                
                cv2.putText(frame, f"Error: ({error_x:.0f}, {error_y:.0f})px", 
                           (cx + 15, cy + 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                cv2.putText(frame, f"Error: ({error_x:.0f}, {error_y:.0f})px", 
                           (cx + 15, cy + 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
                if self.auto_tracking_enabled:
                    cv2.putText(frame, f"Steps: ({steps_x}, {steps_y})", 
                               (cx + 15, cy + 25),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    cv2.putText(frame, f"Steps: ({steps_x}, {steps_y})", 
                               (cx + 15, cy + 25),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Trail of previous positions
            if len(self.target_history) > 1:
                points = np.array(self.target_history, dtype=np.int32)
                cv2.polylines(frame, [points], False, self.trail_color, 2)
                
                # Draw dots along trail
                for i, point in enumerate(self.target_history):
                    alpha = i / len(self.target_history)
                    radius = int(3 + 2 * alpha)
                    cv2.circle(frame, point, radius, self.trail_color, -1)
        
        # Status overlay
        self.draw_status_overlay(frame)
    
    def draw_status_overlay(self, frame):
        """Draw status information overlay."""
        # Status background
        status_bg = frame.copy()
        cv2.rectangle(status_bg, (0, 0), (frame.shape[1], 100), (0, 0, 0), -1)
        cv2.addWeighted(status_bg, 0.4, frame, 0.6, 0, frame)
        
        # Main status
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
        
        # Auto-tracking status
        if self.auto_tracking_enabled:
            auto_status = "AUTO-TRACKING: ON"
            auto_color = (0, 255, 0)
        else:
            auto_status = "AUTO-TRACKING: OFF"
            auto_color = (0, 0, 255)
        
        cv2.putText(frame, auto_status, (10, 75),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, auto_color, 2)
        
        # Commands sent counter
        cv2.putText(frame, f"Commands sent: {self.commands_sent}",
                   (frame.shape[1] - 200, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Controls
        cv2.putText(frame, "Controls: CLICK=Select | T=Toggle Auto | R=Reset | Q=Quit",
                   (10, frame.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    def draw_all_contours(self, frame, contours):
        """Draw all detected contours in debug mode."""
        if not self.show_all_contours:
            return
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if self.MIN_CONTOUR_AREA < area < self.MAX_CONTOUR_AREA:
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    cv2.drawContours(frame, [cnt], -1, (255, 200, 100), 1)
                    cv2.circle(frame, (cx, cy), 3, (255, 200, 100), -1)
    
    def cleanup(self):
        """Clean up resources."""
        self.stop_motor_thread()
        print("Visual servo tracker cleanup complete")