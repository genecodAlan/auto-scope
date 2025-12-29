#Alan Notes
import cv2 #All computer vision
import numpy as np #All arrays and alignment
import threading #Collection of frames to stitch
import time
from queue import Queue
import tkinter as tk #for UI
from tkinter import ttk
from tkinter import messagebox
from PIL import Image, ImageTk
import serial
import os
import serial.tools.list_ports
import json
from visual_servo_tracker import VisualServoTracker

class MicroscopeStitcher:
    """
    Main class for microscope image stitching with Arduino control.
    """
    
    def __init__(self, create_gui=True):
        """
        Constructor method - called when creating a new instance of the class.
        Initializes all the instance variables (object's state).
        """
        # Camera and capture control
        self.camera = None
        self.is_capturing = False
        self.is_stitching = False
        self.stitching_active = False
        
        # Image cropping parameters (defaults)
        self.crop_top, self.crop_bottom = 240, 465 
        self.crop_left, self.crop_right = 180, 380
        
        # Crop adjustment mode
        self.adjusting_crop = False
        self.crop_confirmed = False
        self.crop_width = self.crop_right - self.crop_left  # Fixed width
        self.crop_height = self.crop_bottom - self.crop_top  # Fixed height
        self.dragging_rect = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Stitching components - your smooth stitching algorithm
        self.orb = cv2.ORB_create(nfeatures=1000)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        
        # Canvas for stitching (larger canvas for your algorithm)
        self.canvas_height, self.canvas_width = 1500, 1500
        self.canvas = np.zeros((self.canvas_height, self.canvas_width, 3), dtype=np.uint8)
        self.pos_x = (self.canvas_width - (self.crop_right - self.crop_left)) // 2
        self.pos_y = ((self.canvas_height) // 2) - (self.crop_bottom)
        self.first_frame_init = False
        self.abs_x = 0
        self.abs_y = 0
        
        # Tracking variables for smooth stitching
        self.kp_last = None
        self.des_last = None
        self.pos_last = None
        
        # Threading components
        self.frame_queue = Queue(maxsize=10)  # For cropped frames (small tile view)
        self.raw_frame_queue = Queue(maxsize=10)  # For raw frames (full window view)
        self.stitch_queue = Queue(maxsize=5)
        
        # Visual servoing tracker integration
        self.visual_servo_tracker = VisualServoTracker(motor_controller=self)
        self.tracking_mode_active = False
        self.backsub = cv2.createBackgroundSubtractorMOG2(
            history=500, 
            varThreshold=50, 
            detectShadows=True
        )
        
        # Arduino communication
        self.arduino = None
        self.arduino_connected = False
        self.set = False
        self.step_delay = 4000      # Microseconds between steps (speed)
        self.steps_per_move = 100   # Steps per button press
        self.pulse_width = 1500 
        # Lawnmower pattern automation
        self.auto_scan_active = False
        self.lawnmower_thread = None
        self.scan_pattern = []
        self.current_step = 0
        self.steps_per_row = 5  # Number of steps in each row (configurable)
        self.rows_to_scan = 4   # Number of rows to scan (configurable)
        self.step_delay = 2.0   # Delay between movements in seconds (configurable)
        
        # GUI components
        self.root = None
        self.preview_window = None
        # Allow tests or headless environments to skip creating a Tk root
        if create_gui:
            self.setup_gui()
        else:
            # Provide lightweight substitutes used by logic to avoid tkinter dependency
            class _SimpleVar:
                def __init__(self):
                    self._v = ""
                def set(self, v):
                    self._v = v
                def get(self):
                    return self._v

            class _DummyLabel:
                def __init__(self):
                    self.text = ""
                def config(self, **kwargs):
                    if 'text' in kwargs:
                        self.text = kwargs['text']

            self.status_var = _SimpleVar()
            self.pos_label = _DummyLabel()
        self.save_directory = "captured_images"
        self.image_counter = 0
        self.preview_label = None
        
        # Create save directory if it doesn't exist
        if not os.path.exists(self.save_directory):
            os.makedirs(self.save_directory)

    #Now we have setup the entire constructor of the class when it is made it holds all of these variables
    
    def save_current_frame(self, frame):
        """Save the current frame with an index"""
        filename = f"{self.save_directory}/frame_{self.image_counter:04d}.png"
        cv2.imwrite(filename, frame)
        self.image_counter += 1
        print(f"Saved frame to {filename}")

    def blend_regions(self, canvas_region, new_region):
        """
        Your smooth blending function integrated as a class method.
        
        OOP Concept: Method - a function that belongs to the class and can
        access the object's data through 'self'
        """
        alpha = 0.5
        overlap_mask = (np.sum(canvas_region, axis=2) > 0) & (np.sum(new_region, axis=2) > 0)
        blended = canvas_region.copy()
        blended[overlap_mask] = (alpha * canvas_region[overlap_mask] + (1 - alpha) * new_region[overlap_mask]).astype(np.uint8)
        only_new_mask = (np.sum(canvas_region, axis=2) == 0) & (np.sum(new_region, axis=2) > 0)
        blended[only_new_mask] = new_region[only_new_mask]
        return blended
    
        #Remember that the alpha is meant to clean the black lining between them by finding merge points in the image. 
        
    def setup_gui(self):
        """
        Initialize the main GUI.
        
        OOP Concept: Encapsulation - GUI setup is contained within the class,
        keeping related functionality together.
        """
        self.root = tk.Tk()
        self.root.title("Microscope Image Stitcher with Arduino Control")
        self.root.geometry("1200x900")
        
        # Arduino connection panel
        arduino_frame = ttk.LabelFrame(self.root, text="Arduino Control", padding=10)
        arduino_frame.pack(pady=5, padx=10, fill=tk.X)
        
        self.connect_arduino_btn = ttk.Button(arduino_frame, text="Connect Arduino (COM3)", 
                                            command=self.connect_arduino)
        self.connect_arduino_btn.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_arduino_btn = ttk.Button(arduino_frame, text="Disconnect Arduino", 
                                               command=self.disconnect_arduino, state='disabled')
        self.disconnect_arduino_btn.pack(side=tk.LEFT, padx=5)
        
        self.arduino_status = ttk.Label(arduino_frame, text="Not Connected", foreground="red")
        self.arduino_status.pack(side=tk.LEFT, padx=10)
        
        # Control panel
        control_frame = ttk.LabelFrame(self.root, text="Camera Controls", padding=10)
        control_frame.pack(pady=5, padx=10, fill=tk.X)

        self.set_home_btn = ttk.Button(control_frame, text= "Set XY home", command=self.set_home)

        self.set_home_btn.pack(side= tk.LEFT, padx=5)
        
        self.start_camera_btn = ttk.Button(control_frame, text="Start Camera", 
                                         command=self.start_camera)
        self.start_camera_btn.pack(side=tk.LEFT, padx=5)
        
        self.confirm_crop_btn = ttk.Button(control_frame, text="Confirm Crop Region", 
                                         command=self.confirm_crop, state='disabled')
        self.confirm_crop_btn.pack(side=tk.LEFT, padx=5)
        
        self.start_stitch_btn = ttk.Button(control_frame, text="Start Manual Stitching", 
                                         command=self.start_stitching, state='disabled')
        self.start_stitch_btn.pack(side=tk.LEFT, padx=5)
        
        self.auto_scan_btn = ttk.Button(control_frame, text="Start Auto Scan", 
                                      command=self.start_auto_scan, state='disabled')
        self.auto_scan_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_stitch_btn = ttk.Button(control_frame, text="Stop Stitching", 
                                        command=self.stop_stitching, state='disabled')
        self.stop_stitch_btn.pack(side=tk.LEFT, padx=5)
        
        self.reset_canvas_btn = ttk.Button(control_frame, text="Reset Canvas", 
                                         command=self.reset_canvas)
        self.reset_canvas_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_btn = ttk.Button(control_frame, text="Save Result", 
                                 command=self.save_result, state='disabled')
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        # Visual servoing controls
        self.start_tracking_btn = ttk.Button(control_frame, text="Start Organism Tracking", 
                                           command=self.toggle_organism_tracking, state='disabled')
        self.start_tracking_btn.pack(side=tk.LEFT, padx=5)
        
        self.toggle_auto_track_btn = ttk.Button(control_frame, text="Enable Auto-Centering", 
                                              command=self.toggle_auto_tracking, state='disabled')
        self.toggle_auto_track_btn.pack(side=tk.LEFT, padx=5)
        
        # Auto scan configuration panel
        config_frame = ttk.LabelFrame(self.root, text="Auto Scan Configuration", padding=10)
        config_frame.pack(pady=5, padx=10, fill=tk.X)
        
        # Steps per row configuration
        steps_frame = ttk.Frame(config_frame)
        steps_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(steps_frame, text="Steps per row:").pack()
        self.steps_var = tk.StringVar(value=str(self.steps_per_row))
        steps_spinbox = ttk.Spinbox(steps_frame, from_=2, to=20, width=5, textvariable=self.steps_var)
        steps_spinbox.pack()
        
        motor_control_frame = ttk.LabelFrame(self.root, text="Motor Speed & Step Size Control", padding=10)
        motor_control_frame.pack(pady=5, padx=10, fill=tk.X)
        
        # Speed control (step delay)
        speed_frame = ttk.Frame(motor_control_frame)
        speed_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(speed_frame, text="Speed (delay μs):").pack()
        ttk.Label(speed_frame, text="Higher = Slower", font=('Arial', 8, 'italic')).pack()
        
        speed_inner = ttk.Frame(speed_frame)
        speed_inner.pack()
        
        self.speed_var = tk.IntVar(value=self.step_delay)
        self.speed_scale = ttk.Scale(speed_inner, from_=500, to=20000, 
                                    variable=self.speed_var, orient=tk.HORIZONTAL, 
                                    length=200, command=self.on_speed_change)
        self.speed_scale.pack(side=tk.LEFT)
        
        self.speed_label = ttk.Label(speed_inner, text=f"{self.step_delay} μs", width=10)
        self.speed_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(speed_frame, text="Apply Speed", 
                command=self.apply_speed_setting).pack(pady=5)
        
        # Step size control
        step_size_frame = ttk.Frame(motor_control_frame)
        step_size_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(step_size_frame, text="Steps per move:").pack()
        ttk.Label(step_size_frame, text="Higher = Larger movement", font=('Arial', 8, 'italic')).pack()
        
        step_inner = ttk.Frame(step_size_frame)
        step_inner.pack()
        
        self.step_size_var = tk.IntVar(value=self.steps_per_move)
        self.step_size_scale = ttk.Scale(step_inner, from_=1, to=500, 
                                        variable=self.step_size_var, orient=tk.HORIZONTAL,
                                        length=200, command=self.on_step_size_change)
        self.step_size_scale.pack(side=tk.LEFT)
        
        self.step_size_label = ttk.Label(step_inner, text=f"{self.steps_per_move} steps", width=10)
        self.step_size_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(step_size_frame, text="Apply Step Size", 
                command=self.apply_step_size_setting).pack(pady=5)
        
        # Preset buttons
        preset_frame = ttk.Frame(motor_control_frame)
        preset_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(preset_frame, text="Quick Presets:").pack()
        
        ttk.Button(preset_frame, text="Fine (Slow, Small)", 
                command=lambda: self.apply_preset(8000, 50)).pack(pady=2, fill=tk.X)
        ttk.Button(preset_frame, text="Normal (Default)", 
                command=lambda: self.apply_preset(4000, 100)).pack(pady=2, fill=tk.X)
        ttk.Button(preset_frame, text="Fast (Quick, Large)", 
                command=lambda: self.apply_preset(2000, 200)).pack(pady=2, fill=tk.X)
        
        # Status indicator
        self.motor_status_label = ttk.Label(motor_control_frame, 
                                        text="Motor settings: Default", 
                                        foreground="blue")
        self.motor_status_label.pack(pady=5)
        # Rows configuration
        rows_frame = ttk.Frame(config_frame)
        rows_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(rows_frame, text="Number of rows:").pack()
        self.rows_var = tk.StringVar(value=str(self.rows_to_scan))
        rows_spinbox = ttk.Spinbox(rows_frame, from_=2, to=10, width=5, textvariable=self.rows_var)
        rows_spinbox.pack()
        
        # Delay configuration
        delay_frame = ttk.Frame(config_frame)
        delay_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(delay_frame, text="Step delay (sec):").pack()
        self.delay_var = tk.StringVar(value=str(self.step_delay))
        delay_spinbox = ttk.Spinbox(delay_frame, from_=0.5, to=5.0, increment=0.5, width=5, textvariable=self.delay_var)
        delay_spinbox.pack()
        
        # Update button
        ttk.Button(config_frame, text="Update Settings", 
                  command=self.update_scan_settings).pack(side=tk.LEFT, padx=10)
        arrow_frame = ttk.LabelFrame(self.root, text="Manual Movement Controls", padding=10)
        arrow_frame.pack(pady=5, padx=10, fill=tk.X)
        
        instructions = ttk.Label(arrow_frame, 
                               text="Use arrow keys to move one microstep per press:\n" +
                                    "↑ = Up (U), ↓ = Down (D), ← = Left (L), → = Right (R)\n" +
                                    "Commands sent as 2-character format (e.g., 'US', 'DS', 'LS', 'RS')")
        instructions.pack()
        
        # Manual control buttons for clicking (alternative to arrow keys)
        button_frame = ttk.Frame(arrow_frame)
        button_frame.pack(pady=5)
        
        ttk.Button(button_frame, text="↑", width=3, 
                  command=lambda: self.send_step('U', 'S')).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(button_frame, text="←", width=3, 
                  command=lambda: self.send_step('S', 'L')).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(button_frame, text="STOP", width=5, 
                  command=lambda: self.send_step('S', 'S')).grid(row=1, column=1, padx=2, pady=2)
        ttk.Button(button_frame, text="→", width=3, 
                  command=lambda: self.send_step('S', 'R')).grid(row=1, column=2, padx=2, pady=2)
        ttk.Button(button_frame, text="↓", width=3, 
                  command=lambda: self.send_step('D', 'S')).grid(row=2, column=1, padx=2, pady=2)
        
        # Bind arrow keys for Arduino control
        self.root.bind('<Key>', self.on_key_press)
        self.root.focus_set()  # Ensure window can receive key events
        
        # Visual servoing configuration panel
        servo_frame = ttk.LabelFrame(self.root, text="Visual Servoing Configuration", padding=10)
        servo_frame.pack(pady=5, padx=10, fill=tk.X)
        
        # Calibration constants
        cal_frame = ttk.Frame(servo_frame)
        cal_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(cal_frame, text="Pixels per step:").pack()
        
        px_frame = ttk.Frame(cal_frame)
        px_frame.pack()
        
        ttk.Label(px_frame, text="X:").pack(side=tk.LEFT)
        self.pixels_per_step_x_var = tk.DoubleVar(value=2.0)
        px_x_spinbox = ttk.Spinbox(px_frame, from_=0.1, to=10.0, increment=0.1, 
                                   width=6, textvariable=self.pixels_per_step_x_var)
        px_x_spinbox.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(px_frame, text="Y:").pack(side=tk.LEFT, padx=(10,0))
        self.pixels_per_step_y_var = tk.DoubleVar(value=2.0)
        px_y_spinbox = ttk.Spinbox(px_frame, from_=0.1, to=10.0, increment=0.1, 
                                   width=6, textvariable=self.pixels_per_step_y_var)
        px_y_spinbox.pack(side=tk.LEFT, padx=2)
        
        # Control parameters
        ctrl_frame = ttk.Frame(servo_frame)
        ctrl_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(ctrl_frame, text="Deadzone (px):").pack()
        self.deadzone_var = tk.IntVar(value=10)
        deadzone_spinbox = ttk.Spinbox(ctrl_frame, from_=1, to=50, width=6, 
                                       textvariable=self.deadzone_var)
        deadzone_spinbox.pack()
        
        ttk.Label(ctrl_frame, text="Max steps/cmd:").pack()
        self.max_steps_var = tk.IntVar(value=5)
        max_steps_spinbox = ttk.Spinbox(ctrl_frame, from_=1, to=20, width=6, 
                                        textvariable=self.max_steps_var)
        max_steps_spinbox.pack()
        
        # Update button
        ttk.Button(servo_frame, text="Update Servo Settings", 
                  command=self.update_servo_settings).pack(side=tk.LEFT, padx=10)
        
        # Camera display controls
        camera_display_frame = ttk.LabelFrame(self.root, text="Camera Display", padding=10)
        camera_display_frame.pack(pady=5, padx=10, fill=tk.X)
        
        self.toggle_view_btn = ttk.Button(camera_display_frame, text="Open Full Window View", 
                                        command=self.toggle_camera_view, state='disabled')
        self.toggle_view_btn.pack(side=tk.LEFT, padx=5)
        
        # Live camera feed display (small tile view)
        self.camera_label = ttk.Label(self.root, text="Camera feed will appear here")
        self.camera_label.pack(pady=20)
        self.pos_label = ttk.Label(self.root, text= f"{self.abs_x}" + ", " + f"{self.abs_y}")
        self.pos_label.pack(pady=20)
        
        # Full window view variables
        self.full_view_window = None
        self.full_view_label = None
        self.is_full_view = False
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def on_speed_change(self, value):
        """Update speed label when slider moves"""
        speed = int(float(value))
        self.speed_label.config(text=f"{speed} μs")

    def on_step_size_change(self, value):
        """Update step size label when slider moves"""
        steps = int(float(value))
        self.step_size_label.config(text=f"{steps} steps")

    def apply_speed_setting(self):
        """Send speed setting to Arduino"""
        if not self.arduino_connected:
            self.status_var.set("Arduino not connected - cannot change speed")
            return
        
        new_speed = self.speed_var.get()
        
        try:
            command = f"SPEED:{new_speed}\n"
            self.arduino.write(command.encode())
            time.sleep(0.1)  # Wait for Arduino to process
            
            # Read response
            if self.arduino.in_waiting:
                response = self.arduino.readline().decode().strip()
                if response.startswith("SPEED_SET:"):
                    actual_speed = int(response.split(':')[1])
                    self.step_delay = actual_speed
                    self.motor_status_label.config(
                        text=f"Speed: {actual_speed}μs, Steps: {self.steps_per_move}",
                        foreground="green"
                    )
                    self.status_var.set(f"Speed updated to {actual_speed} μs")
                elif "ERROR" in response:
                    self.status_var.set(f"Arduino error: {response}")
            else:
                self.status_var.set("Speed command sent (no confirmation)")
                
        except Exception as e:
            self.status_var.set(f"Failed to set speed: {str(e)}")

    def apply_step_size_setting(self):
        """Send step size setting to Arduino"""
        if not self.arduino_connected:
            self.status_var.set("Arduino not connected - cannot change step size")
            return
        
        new_steps = self.step_size_var.get()
        
        try:
            command = f"STEPS:{new_steps}\n"
            self.arduino.write(command.encode())
            time.sleep(0.1)
            
            # Read response
            if self.arduino.in_waiting:
                response = self.arduino.readline().decode().strip()
                if response.startswith("STEPS_SET:"):
                    actual_steps = int(response.split(':')[1])
                    self.steps_per_move = actual_steps
                    self.motor_status_label.config(
                        text=f"Speed: {self.step_delay}μs, Steps: {actual_steps}",
                        foreground="green"
                    )
                    self.status_var.set(f"Step size updated to {actual_steps} steps")
                elif "ERROR" in response:
                    self.status_var.set(f"Arduino error: {response}")
            else:
                self.status_var.set("Step size command sent (no confirmation)")
                
        except Exception as e:
            self.status_var.set(f"Failed to set step size: {str(e)}")

    def apply_preset(self, speed, steps):
        """Apply a preset combination of speed and step size"""
        if not self.arduino_connected:
            self.status_var.set("Arduino not connected")
            return
        
        # Update sliders
        self.speed_var.set(speed)
        self.step_size_var.set(steps)
        
        # Send both settings
        try:
            # Send speed
            self.arduino.write(f"SPEED:{speed}\n".encode())
            time.sleep(0.1)
            
            # Send step size
            self.arduino.write(f"STEPS:{steps}\n".encode())
            time.sleep(0.1)
            
            # Update internal state
            self.step_delay = speed
            self.steps_per_move = steps
            
            self.motor_status_label.config(
                text=f"Speed: {speed}μs, Steps: {steps}",
                foreground="green"
            )
            
            preset_name = "Fine" if speed > 6000 else "Fast" if speed < 3000 else "Normal"
            self.status_var.set(f"Applied preset: {preset_name}")
            
        except Exception as e:
            self.status_var.set(f"Failed to apply preset: {str(e)}")

    def get_motor_status(self):
        """Query Arduino for current motor settings"""
        if not self.arduino_connected:
            return
        
        try:
            self.arduino.write(b"STATUS\n")
            time.sleep(0.1)
            
            if self.arduino.in_waiting:
                response = self.arduino.readline().decode().strip()
                if response.startswith("STATUS:"):
                    parts = response.split(':')[1].split(',')
                    if len(parts) == 3:
                        speed = int(parts[0])
                        steps = int(parts[1])
                        pulse = int(parts[2])
                        
                        # Update GUI
                        self.speed_var.set(speed)
                        self.step_size_var.set(steps)
                        
                        self.step_delay = speed
                        self.steps_per_move = steps
                        self.pulse_width = pulse
                        
                        self.motor_status_label.config(
                            text=f"Speed: {speed}μs, Steps: {steps}",
                            foreground="blue"
                        )
                        
        except Exception as e:
            print(f"Failed to get motor status: {e}")

        
    def connect_arduino(self):
        """
        Connect to Arduino on COM3 port with correct baud rate.
        
        OOP Concept: Method that modifies object state (self.arduino, self.arduino_connected)
        """
        try:
            self.arduino = serial.Serial('COM3', 115200, timeout=0.1)
            time.sleep(2)  # Wait for Arduino to reset and initialize
            
            # Flush any startup messages
            while self.arduino.in_waiting:
                self.arduino.readline()
            
            self.arduino_connected = True
            
            self.connect_arduino_btn.config(state='disabled')
            self.disconnect_arduino_btn.config(state='normal')
            self.arduino_status.config(text="Connected", foreground="green")
            self.status_var.set("Arduino connected on COM3 at 115200 baud")
            
            # Query current settings from Arduino
            self.root.after(500, self.get_motor_status)
            
        except Exception as e:
            self.status_var.set(f"Arduino connection error: {str(e)}")
            self.arduino_connected = False
            
    def disconnect_arduino(self):
        """Disconnect from Arduino"""
        if self.arduino and self.arduino_connected:
            self.arduino.close()
            self.arduino = None
            self.arduino_connected = False
            
            self.connect_arduino_btn.config(state='normal')
            self.disconnect_arduino_btn.config(state='disabled')
            self.arduino_status.config(text="Not Connected", foreground="red")
            self.status_var.set("Arduino disconnected")
            
    def send_step(self, y_cmd, x_cmd):
        """
        Send a single step command and update absolute position coordinates
        """
        # Determine proposed new absolute coordinates without modifying state yet
        # Descriptive variable names: new_abs_x, new_abs_y
        # Movement deltas: U=+1 in Y, D=-1 in Y, L=+1 in X, R=-1 in X (consistent with prior code)

        if not self.arduino_connected or not self.arduino:
            self.status_var.set("Arduino not connected")
            return False
        
        # Calculate what the NEW position would be
        new_abs_x = self.abs_x
        new_abs_y = self.abs_y
        
        if y_cmd == 'U':
            new_abs_y += 1
        elif y_cmd == 'D':
            new_abs_y -= 1
        
        if x_cmd == 'L':
            new_abs_x += 1
        elif x_cmd == 'R':
            new_abs_x -= 1
        
        # BOUNDARY CHECK: Prevent going below zero if home is set
        if self.set:
            if new_abs_x < 0:
                self.status_var.set("Cannot move right - at boundary (x=0)")
                return False
            if new_abs_y < 0:
                self.status_var.set("Cannot move down - at boundary (y=0)")
                return False
        
        # TRY to send command to Arduino BEFORE updating position
        try:
            cmd = f"{y_cmd}{x_cmd}\n"  # ← CRITICAL FIX: Added \n
            self.arduino.write(cmd.encode())
            
            # Wait for response from Arduino
            time.sleep(0.05)
            response = ""
            if self.arduino.in_waiting:
                response = self.arduino.readline().decode().strip()
                print(f"Arduino response: {response}")  # Debug output
            
            # Only update position if command was sent successfully
            self.abs_x = new_abs_x
            self.abs_y = new_abs_y
            
            # Update GUI
            self.pos_label.config(text=f"Position: ({self.abs_x}, {self.abs_y})")
            print(f"Sent: {cmd.strip()}, Position: ({self.abs_x}, {self.abs_y})")
            return True
            
        except Exception as e:
            self.status_var.set(f"COMMUNICATION ERROR: {str(e)}")
            print(f"Error sending command: {e}")
            # Position NOT updated because command failed
            return False
    def send_arduino_command(self, command):
        """
        Legacy method for compatibility - converts single commands to step format.
        """
        # Convert single direction commands to your Arduino's 2-char format
        command_map = {
            'UP': ('U', 'S'),
            'DOWN': ('D', 'S'), 
            'LEFT': ('S', 'L'),
            'RIGHT': ('S', 'R'),
            'STOP': ('S', 'S')
        }
        
        if command in command_map:
            y_cmd, x_cmd = command_map[command]
            return self.send_step(y_cmd, x_cmd)
        return False
        
    def on_key_press(self, event):
        """
        Handle arrow key presses for Arduino control matching your protocol.
        Sends 2-character commands with small delay to avoid accidental repeats.
        Also handles visual servoing hotkeys.
        """
        # Visual servoing hotkeys
        if event.keysym == 't' or event.keysym == 'T':
            if self.tracking_mode_active:
                self.toggle_auto_tracking()
            return
        elif event.keysym == 'r' or event.keysym == 'R':
            if self.tracking_mode_active:
                self.visual_servo_tracker.reset_tracking()
            return
        
        if not self.arduino_connected:
            self.status_var.set("Arduino not connected - connect first to use arrow keys")
            return
            
        # Default to 'S' (stop) for both axes
        y_cmd = 'S'
        x_cmd = 'S'
        
        if event.keysym == 'Up':
            y_cmd = 'U'
        elif event.keysym == 'Down':
            y_cmd = 'D'
        elif event.keysym == 'Right':
            x_cmd = 'R'
        elif event.keysym == 'Left':
            x_cmd = 'L'
        else:
            return  # Ignore other keys
            
        if self.send_step(y_cmd, x_cmd):
            self.status_var.set(f"Sent step command: {y_cmd}{x_cmd}")
            # Small delay to avoid accidental repeats (matching your original code)
            self.root.after(80, lambda: None)  # 80ms delay
        

    def set_home(self):

        if self.arduino_connected and self.arduino:
            try:
                self.abs_x = 0
                self.abs_y = 0
                self.pos_label.config(text=f"Position: ({self.abs_x}, {self.abs_y})")
                self.set = True

            except:
                pass
            finally:
                print("Home Set")
    
    def open_crop_adjustment_window(self):
        """Open Tkinter window for adjusting crop region interactively"""
        # Get actual camera frame size
        ret, test_frame = self.camera.read()
        if ret:
            cam_height, cam_width = test_frame.shape[:2]
            # Store camera dimensions for crop bounds checks
            self.cam_width = cam_width
            self.cam_height = cam_height
        else:
            # Fallback to default
            cam_width, cam_height = 1280, 720
            self.cam_width = cam_width
            self.cam_height = cam_height
        
        # Create a new Tkinter window for crop adjustment
        self.crop_window = tk.Toplevel(self.root)
        self.crop_window.title("Adjust Crop Region - Full Camera View")
        
        # Set window size to fit camera feed plus some padding
        window_width = cam_width + 40
        window_height = cam_height + 120
        self.crop_window.geometry(f"{window_width}x{window_height}")
        
        # Instructions
        instructions = ttk.Label(self.crop_window, 
                                text=f"Full camera view ({cam_width}x{cam_height}). Click and drag the green rectangle to position your crop region.\n" +
                                     "Click 'Confirm Crop Region' button in main window when ready.",
                                font=('Arial', 10))
        instructions.pack(pady=10)
        
        # Canvas for displaying full video feed with crop overlay
        self.crop_canvas = tk.Canvas(self.crop_window, width=cam_width, height=cam_height, bg='gray')
        self.crop_canvas.pack(pady=10)
        
        # Store camera dimensions for later use
        self.cam_width = cam_width
        self.cam_height = cam_height
        
        # Bind mouse events to canvas
        self.crop_canvas.bind('<ButtonPress-1>', self.on_crop_canvas_click)
        self.crop_canvas.bind('<B1-Motion>', self.on_crop_canvas_drag)
        self.crop_canvas.bind('<ButtonRelease-1>', self.on_crop_canvas_release)
        
        # Start thread to update the canvas with camera feed
        self.crop_adjust_thread = threading.Thread(target=self.update_crop_canvas)
        self.crop_adjust_thread.daemon = True
        self.crop_adjust_thread.start()
    
    def on_crop_canvas_click(self, event):
        """Handle mouse click on crop canvas"""
        if not self.adjusting_crop:
            return
        
        x, y = event.x, event.y
        # Check if click is inside the rectangle
        if (self.crop_left <= x <= self.crop_right and 
            self.crop_top <= y <= self.crop_bottom):
            self.dragging_rect = True
            self.drag_offset_x = x - self.crop_left
            self.drag_offset_y = y - self.crop_top
    
    def on_crop_canvas_drag(self, event):
        """Handle mouse drag on crop canvas"""
        if not self.adjusting_crop or not self.dragging_rect:
            return
        
        x, y = event.x, event.y
        # Move the rectangle (keeping same size)
        new_left = x - self.drag_offset_x
        new_top = y - self.drag_offset_y
        
        # Keep within frame bounds (use actual camera dimensions)
        max_width = getattr(self, 'cam_width', 1280)
        max_height = getattr(self, 'cam_height', 720)
        new_left = max(0, min(new_left, max_width - self.crop_width))
        new_top = max(0, min(new_top, max_height - self.crop_height))
        
        self.crop_left = new_left
        self.crop_top = new_top
        self.crop_right = new_left + self.crop_width
        self.crop_bottom = new_top + self.crop_height
    
    def on_crop_canvas_release(self, event):
        """Handle mouse release on crop canvas"""
        self.dragging_rect = False
    
    def update_crop_canvas(self):
        """Update the Tkinter canvas with camera feed and crop overlay"""
        print("Starting crop adjustment display...")
        frame_count = 0
        
        while self.adjusting_crop:
            try:
                ret, frame = self.camera.read()
                if not ret:
                    time.sleep(0.033)
                    continue
                
                frame_count += 1
                
                # Draw the crop rectangle
                overlay = frame.copy()
                
                # Draw semi-transparent overlay outside crop region
                mask = np.ones(frame.shape[:2], dtype=np.uint8) * 255
                cv2.rectangle(mask, (self.crop_left, self.crop_top), 
                             (self.crop_right, self.crop_bottom), 0, -1)
                overlay[mask > 0] = overlay[mask > 0] // 2
                
                # Draw crop rectangle border (thicker green)
                cv2.rectangle(overlay, (self.crop_left, self.crop_top), 
                             (self.crop_right, self.crop_bottom), (0, 255, 0), 3)
                
                # Convert to RGB for Tkinter
                overlay_rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
                
                # Convert to PhotoImage
                image = Image.fromarray(overlay_rgb)
                photo = ImageTk.PhotoImage(image)
                
                # Schedule a main-thread-safe GUI update using root.after
                if hasattr(self, 'crop_canvas') and self.root:
                    # Use a helper to avoid closure issues with 'photo'
                    self.root.after(0, lambda p=photo: self._update_crop_canvas_image(p))
                    
            except Exception as e:
                print(f"Error in crop adjustment: {e}")
                break
            
            time.sleep(0.033)  # ~30 FPS
        
        print("Crop adjustment display ended")

    def _update_crop_canvas_image(self, photo):
        """Helper executed on main thread to safely update crop canvas image."""
        try:
            if hasattr(self, 'crop_canvas'):
                self.crop_canvas.delete("all")
                self.crop_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
                self.crop_canvas.image = photo  # Keep reference
        except Exception as e:
            print(f"Error updating crop canvas on main thread: {e}")
    
    def confirm_crop(self):
        """Confirm the crop region and start normal camera operation"""
        self.adjusting_crop = False
        self.crop_confirmed = True
        
        # Close crop adjustment window
        if hasattr(self, 'crop_window'):
            self.crop_window.destroy()
        
        # Start normal capture and display
        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self.capture_frames)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
        self.display_thread = threading.Thread(target=self.update_display)
        self.display_thread.daemon = True
        self.display_thread.start()
        
        # Enable stitching buttons and camera view toggle
        self.confirm_crop_btn.config(state='disabled')
        self.start_stitch_btn.config(state='normal')
        self.auto_scan_btn.config(state='normal')
        self.toggle_view_btn.config(state='normal')  # Enable camera view toggle
        self.start_tracking_btn.config(state='normal')  # Enable organism tracking
        
        self.status_var.set(f"Crop confirmed: {self.crop_width}x{self.crop_height} - Camera active")
        print(f"Crop settings: Top={self.crop_top}, Bottom={self.crop_bottom}, Left={self.crop_left}, Right={self.crop_right}")
        print(f"Crop settings: Top={self.crop_top}, Bottom={self.crop_bottom}, Left={self.crop_left}, Right={self.crop_right}")

    def start_camera(self):
        """
        Initialize camera and start crop adjustment mode.
        
        OOP Concept: Method that coordinates multiple object components
        """
        try:
            self.camera = cv2.VideoCapture(1)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

            if not self.camera.isOpened():
                raise Exception("Could not open camera")
            
            # Give camera time to initialize
            time.sleep(0.5)
            
            # Test read a frame
            ret, test_frame = self.camera.read()
            if not ret:
                raise Exception("Camera opened but cannot read frames")
            
            # Start in crop adjustment mode
            self.adjusting_crop = True
            self.crop_confirmed = False
            
            # Open crop adjustment window
            self.open_crop_adjustment_window()
            
            self.start_camera_btn.config(state='disabled')
            self.confirm_crop_btn.config(state='normal')
            self.status_var.set("Adjust crop region - drag the green box, then click 'Confirm Crop Region'")
            
        except Exception as e:
            self.status_var.set(f"Camera error: {str(e)}")
            if self.camera:
                self.camera.release()
    
    def capture_frames(self):
        """
        Continuous frame capture thread.
        
        OOP Concept: Method that runs in a separate thread, accessing object state
        """
        while self.is_capturing:
            ret, frame = self.camera.read()
            if ret:
                # Add raw frame to raw queue for full window view
                if not self.raw_frame_queue.full():
                    self.raw_frame_queue.put(frame.copy())
                
                # Crop frame for small tile view and stitching
                frame_cropped = frame[self.crop_top:self.crop_bottom, self.crop_left:self.crop_right]

                # Add cropped frame to queue for small tile display
                if not self.frame_queue.full():
                    self.frame_queue.put(frame_cropped.copy())
                
                # If stitching is active, add cropped frame to stitch queue
                if self.stitching_active and not self.stitch_queue.full():
                    self.stitch_queue.put(frame_cropped.copy())
            
            time.sleep(1/30)  # 30 FPS
    
    def update_display(self):
        """Update camera display in GUI - handles both small tile and full window views"""
        while self.is_capturing:
            # Update small tile view with cropped frames
            if not self.frame_queue.empty():
                frame_cropped = self.frame_queue.get()
                
                # Convert to RGB
                frame_rgb = cv2.cvtColor(frame_cropped, cv2.COLOR_BGR2RGB)
                
                # Update small tile view (cropped frame, small size)
                frame_small = cv2.resize(frame_rgb, (200, 150))  # Small size for tile
                image_small = Image.fromarray(frame_small)
                photo_small = ImageTk.PhotoImage(image_small)
                
                self.camera_label.config(image=photo_small, text="")
                self.camera_label.image = photo_small  # Keep reference
                
            # Update full window view with raw frames
            if self.is_full_view and self.full_view_label and not self.raw_frame_queue.empty():
                try:
                    frame_raw = self.raw_frame_queue.get()
                    
                    # Convert raw frame to RGB
                    frame_raw_rgb = cv2.cvtColor(frame_raw, cv2.COLOR_BGR2RGB)
                    
                    # Scale raw frame to fit full window while maintaining aspect ratio
                    h, w = frame_raw_rgb.shape[:2]
                    max_size = 700  # Maximum size for full view
                    
                    if max(h, w) > max_size:
                        scale = max_size / max(h, w)
                        new_w = int(w * scale)
                        new_h = int(h * scale)
                        frame_full = cv2.resize(frame_raw_rgb, (new_w, new_h))
                    else:
                        frame_full = frame_raw_rgb
                    
                    # Draw crop region overlay on raw frame for reference
                    if hasattr(self, 'crop_top'):
                        # Scale crop coordinates to match the displayed frame size
                        scale_x = frame_full.shape[1] / w
                        scale_y = frame_full.shape[0] / h
                        
                        crop_left_scaled = int(self.crop_left * scale_x)
                        crop_right_scaled = int(self.crop_right * scale_x)
                        crop_top_scaled = int(self.crop_top * scale_y)
                        crop_bottom_scaled = int(self.crop_bottom * scale_y)
                        
                        # Draw crop region rectangle (green outline)
                        frame_full_with_overlay = frame_full.copy()
                        # Convert to BGR for OpenCV drawing, then back to RGB
                        frame_bgr = cv2.cvtColor(frame_full_with_overlay, cv2.COLOR_RGB2BGR)
                        cv2.rectangle(frame_bgr, 
                                    (crop_left_scaled, crop_top_scaled), 
                                    (crop_right_scaled, crop_bottom_scaled), 
                                    (0, 255, 0), 2)
                        frame_full = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    
                    image_full = Image.fromarray(frame_full)
                    photo_full = ImageTk.PhotoImage(image_full)
                    
                    self.full_view_label.config(image=photo_full, text="")
                    self.full_view_label.image = photo_full  # Keep reference
                    
                    # Update position in full view
                    if hasattr(self, 'full_pos_label'):
                        self.full_pos_label.config(text=f"Position: ({self.abs_x}, {self.abs_y})")
                        
                except Exception as e:
                    print(f"Error updating full view: {e}")
            
            time.sleep(1/30)
    
    def toggle_camera_view(self):
        """Toggle between small tile view and full window view for camera feed"""
        if not self.is_full_view:
            # Open full window view
            self.open_full_camera_window()
            self.is_full_view = True
            self.toggle_view_btn.config(text="Close Full Tracking View")
            self.status_var.set("Full window camera view opened")
        else:
            # Close full window view
            self.close_full_camera_window()
            self.is_full_view = False
            self.toggle_view_btn.config(text="Open Full Tracking View")
            self.status_var.set("Returned to small tile view")
    
    def open_full_camera_window(self):
        """Open a full window for camera feed display"""
        if self.full_view_window:
            self.full_view_window.destroy()
            
        self.full_view_window = tk.Toplevel(self.root)
        self.full_view_window.title("Full Camera View - Raw Feed (Uncropped)")
        self.full_view_window.geometry("900x700")
        
        # Add controls frame at the top
        controls_frame = ttk.Frame(self.full_view_window)
        controls_frame.pack(pady=5, padx=10, fill=tk.X)
        
        # Info label
        info_label = ttk.Label(controls_frame, 
                              text="Raw camera feed - Green rectangle shows crop region used for stitching",
                              font=('Arial', 9, 'italic'))
        info_label.pack(side=tk.LEFT, padx=10)
        
        # Position display in full view
        self.full_pos_label = ttk.Label(controls_frame, text=f"Position: ({self.abs_x}, {self.abs_y})")
        self.full_pos_label.pack(side=tk.LEFT, padx=10)
        
        # Close button
        close_btn = ttk.Button(controls_frame, text="Close Full View", 
                              command=self.toggle_camera_view)
        close_btn.pack(side=tk.RIGHT, padx=10)
        
        # Camera display label for full view
        self.full_view_label = ttk.Label(self.full_view_window, text="Full camera view loading...")
        self.full_view_label.pack(expand=True, fill='both', padx=10, pady=10)
        
        # Handle window close event
        self.full_view_window.protocol("WM_DELETE_WINDOW", self.toggle_camera_view)
    
    def close_full_camera_window(self):
        """Close the full camera window"""
        if self.full_view_window:
            self.full_view_window.destroy()
            self.full_view_window = None
            self.full_view_label = None
    
    def update_scan_settings(self):
        """Update scan pattern settings from GUI inputs"""
        # Guard against headless/test mode where GUI widgets may not exist
        try:
            if hasattr(self, 'steps_var'):
                self.steps_per_row = int(self.steps_var.get())
            if hasattr(self, 'rows_var'):
                self.rows_to_scan = int(self.rows_var.get())
            if hasattr(self, 'delay_var'):
                self.step_delay = float(self.delay_var.get())

            if hasattr(self, 'status_var'):
                self.status_var.set(f"Settings updated: {self.steps_per_row} steps × {self.rows_to_scan} rows, {self.step_delay}s delay")
        except ValueError:
            if hasattr(self, 'status_var'):
                self.status_var.set("Invalid settings - please enter valid numbers")
    
    def start_stitching(self):
        """
        Begin the stitching process using your smooth algorithm.
        
        OOP Concept: Method that initializes stitching state and starts processing
        """
        self.reset_canvas()  # Start with fresh canvas
        
        self.stitching_active = True
        self.is_stitching = True
        
        # Start stitching thread
        self.stitch_thread = threading.Thread(target=self.stitch_frames)
        self.stitch_thread.daemon = True
        self.stitch_thread.start()
        
        # Open preview window
        self.open_preview_window()
        
        self.start_stitch_btn.config(state='disabled')
        self.stop_stitch_btn.config(state='normal')
        self.save_btn.config(state='normal')
        self.status_var.set("Stitching active - move microscope slowly")
    
    def generate_lawnmower_pattern(self):
        """
        Generate lawnmower scan pattern commands.
        
        Pattern: Right → Down → Left → Down → Right → Down → Left → etc.
        Returns list of (y_cmd, x_cmd) tuples
        """
        pattern = []
        going_right = True
        
        for row in range(self.rows_to_scan):
            # Move horizontally across the row
            for step in range(self.steps_per_row - 1):  # -1 because we don't move after last step in row
                if going_right:
                    pattern.append(('S', 'R'))  # Move right
                else:
                    pattern.append(('S', 'L'))  # Move left
            
            # Move down to next row (except for last row)
            if row < self.rows_to_scan - 1:
                pattern.append(('D', 'S'))  # Move down
                going_right = not going_right  # Alternate direction for next row
        
        return pattern
    
    def lawnmower_scan(self):
        """
        Execute the lawnmower pattern in a separate thread.
        
        OOP Concept: Method that runs automated hardware control while stitching
        """
        self.scan_pattern = self.generate_lawnmower_pattern()
        self.current_step = 0
        
        total_steps = len(self.scan_pattern)
        self.status_var.set(f"Starting auto scan: {total_steps} moves planned")
        
        ret, frame = self.camera.read()
        if ret:
            cropped_frame = frame[self.crop_top:self.crop_bottom, 
                                self.crop_left:self.crop_right]
            self.save_current_frame(cropped_frame)

        for i, (y_cmd, x_cmd) in enumerate(self.scan_pattern):
            if not self.auto_scan_active:
                break
            
            
                
            # Send movement command
            if self.send_step(y_cmd, x_cmd):
                self.current_step = i + 1
                remaining = total_steps - self.current_step
                self.status_var.set(f"Auto scan: Step {self.current_step}/{total_steps} - {remaining} moves remaining")
            else:
                self.status_var.set("Auto scan failed - Arduino communication error")
                break
            
            # Wait before next movement
            time.sleep(self.step_delay)
            ret, frame = self.camera.read()
            if ret:
                cropped_frame = frame[self.crop_top:self.crop_bottom, 
                                    self.crop_left:self.crop_right]
                self.save_current_frame(cropped_frame)

                
            
        # Scan complete
        if self.auto_scan_active:
            self.status_var.set("Auto scan complete - stopping stitching")
            self.root.after(1000, self.stop_stitching)  # Stop stitching after 1 second delay
        
        self.auto_scan_active = False
    
    def start_auto_scan(self):
        """
        Start automated lawnmower scanning with stitching.
        
        OOP Concept: Method that coordinates multiple subsystems (stitching + movement)
        """
        if not self.arduino_connected:
            self.status_var.set("Arduino not connected - connect Arduino first")
            return
            
        # Update settings from GUI
        self.update_scan_settings()
        # Validate that the user is at home/origin before starting the lawnmower pattern
        # Auto-scan assumes starting at (0,0). If home has been set and current
        # position is not origin, warn the user and allow cancel.
        if self.set and (self.abs_x != 0 or self.abs_y != 0):
            proceed = messagebox.askyesno(title="Auto Scan Position",
                                          message=(f"Auto-scan typically starts at home (0,0).\n"
                                                   f"Current position is ({self.abs_x}, {self.abs_y}).\n"
                                                   "Continue anyway?"))
            if not proceed:
                self.status_var.set("Auto-scan cancelled - return to home first")
                return
        
        # Start stitching first
        self.reset_canvas()
        self.stitching_active = True
        self.is_stitching = True
        
        # Start stitching thread
        self.stitch_thread = threading.Thread(target=self.stitch_frames)
        self.stitch_thread.daemon = True
        self.stitch_thread.start()
        
        # Open preview window
        self.open_preview_window()
        
        # Start automated movement
        self.auto_scan_active = True
        self.lawnmower_thread = threading.Thread(target=self.lawnmower_scan)
        self.lawnmower_thread.daemon = True
        self.lawnmower_thread.start()
        
        # Update button states
        self.start_stitch_btn.config(state='disabled')
        self.auto_scan_btn.config(state='disabled')
        self.stop_stitch_btn.config(state='normal')
        self.save_btn.config(state='normal')
        """
        Begin the stitching process using your smooth algorithm.
        
        OOP Concept: Method that initializes stitching state and starts processing
        """
        self.reset_canvas()  # Start with fresh canvas
        
        self.stitching_active = True
        self.is_stitching = True
        
        # Start stitching thread
        self.stitch_thread = threading.Thread(target=self.stitch_frames)
        self.stitch_thread.daemon = True
        self.stitch_thread.start()
        
        # Open preview window
        self.open_preview_window()
        
        self.start_stitch_btn.config(state='disabled')
        self.stop_stitch_btn.config(state='normal')
        self.save_btn.config(state='normal')
        self.status_var.set("Stitching active - move microscope slowly")
    
    def stitch_frames(self):
        """
        Main stitching processing thread using your smooth stitching algorithm.
        
        OOP Concept: Method that implements your core algorithm as part of the class
        """
        while self.is_stitching:
            if not self.stitch_queue.empty():
                frame_cropped = self.stitch_queue.get()
                
                try:
                    height, width = frame_cropped.shape[:2]
                    gray = cv2.cvtColor(frame_cropped, cv2.COLOR_BGR2GRAY)
                    kp_curr, des_curr = self.orb.detectAndCompute(gray, None)
                    
                    if not self.first_frame_init:
                        # For the first frame, put it on canvas center
                        self.canvas[self.pos_y:self.pos_y+height, self.pos_x:self.pos_x+width] = frame_cropped
                        self.kp_last = kp_curr
                        self.des_last = des_curr
                        self.pos_last = (self.pos_x, self.pos_y)
                        self.first_frame_init = True
                    else:
                        if self.des_last is not None and des_curr is not None:
                            matches = self.bf.match(des_curr, self.des_last)
                            matches = sorted(matches, key=lambda x: x.distance)
                            
                            if len(matches) >= 10:
                                offsets = []
                                for m in matches:
                                    pt_curr = kp_curr[m.queryIdx].pt
                                    pt_last = self.kp_last[m.trainIdx].pt
                                    offsets.append((pt_last[0] - pt_curr[0], pt_last[1] - pt_curr[1]))
                                
                                dx = int(round(np.median([o[0] for o in offsets])))
                                dy = int(round(np.median([o[1] for o in offsets])))
                                
                                pos_x_new = self.pos_last[0] + dx
                                pos_y_new = self.pos_last[1] + dy
                                
                                # Boundary checks
                                pos_x_new = max(0, min(pos_x_new, self.canvas_width - width))
                                pos_y_new = max(0, min(pos_y_new, self.canvas_height - height))
                                
                                # Extract canvas region and blend
                                canvas_region = self.canvas[pos_y_new:pos_y_new+height, pos_x_new:pos_x_new+width]
                                blended_region = self.blend_regions(canvas_region, frame_cropped)
                                self.canvas[pos_y_new:pos_y_new+height, pos_x_new:pos_x_new+width] = blended_region
                                
                                # Update tracking variables
                                self.kp_last = kp_curr
                                self.des_last = des_curr
                                self.pos_last = (pos_x_new, pos_y_new)
                    
                    # Update preview
                    self.update_preview()
                
                except Exception as e:
                    print(f"Stitching error: {e}")
            
            time.sleep(0.1)  # Process at 10 Hz
    
    def reset_canvas(self):
        """
        Reset the stitching canvas.
        
        OOP Concept: Method that resets object state
        """
        self.canvas = np.zeros((self.canvas_height, self.canvas_width, 3), dtype=np.uint8)
        self.first_frame_init = False
        self.pos_x = (self.canvas_width - (self.crop_right - self.crop_left)) // 2
        self.pos_y = ((self.canvas_height) // 2) - (self.crop_bottom)
        self.kp_last = None
        self.des_last = None
        self.pos_last = None
        self.status_var.set("Canvas reset")
    
    def open_preview_window(self):
        """Open separate window for stitching preview"""
        if self.preview_window:
            self.preview_window.destroy()
            
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("Stitching Preview")
        self.preview_window.geometry("800x600")
        
        self.preview_label = ttk.Label(self.preview_window, text="Stitched image preview")
        self.preview_label.pack(expand=True, fill='both')
    
    def update_preview(self):
        """Update the preview window with current stitched result"""
        if self.preview_window and self.canvas is not None:
            try:
                # Find non-zero region to crop empty space
                gray_canvas = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2GRAY)
                coords = cv2.findNonZero(gray_canvas)
                
                if coords is not None:
                    x, y, w, h = cv2.boundingRect(coords)
                    preview_img = self.canvas[y:y+h, x:x+w]
                else:
                    preview_img = self.canvas.copy()
                
                h, w = preview_img.shape[:2]
                
                # Scale to fit preview window
                max_size = 700
                if max(h, w) > max_size:
                    scale = max_size / max(h, w)
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    preview_img = cv2.resize(preview_img, (new_w, new_h))
                
                # Convert and display
                preview_rgb = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(preview_rgb)
                photo = ImageTk.PhotoImage(image)
                
                self.preview_label.config(image=photo, text="")
                self.preview_label.image = photo
                
            except Exception as e:
                print(f"Preview update error: {e}")
    
    def stop_stitching(self):
        """Stop stitching process"""
        # Stop any stitching and automated scans
        self.stitching_active = False
        self.is_stitching = False

        # Stop lawnmower/auto-scan if active and signal Arduino to stop movement
        self.auto_scan_active = False
        try:
            # Send stop command to Arduino ('S','S') - do not modify internal pos
            if self.arduino_connected and self.arduino:
                self.send_step('S', 'S')
        except Exception:
            pass

        # If lawnmower thread is running, wait briefly for it to finish
        if getattr(self, 'lawnmower_thread', None):
            try:
                self.lawnmower_thread.join(timeout=3.0)
            except Exception:
                pass

        if hasattr(self, 'start_stitch_btn'):
            self.start_stitch_btn.config(state='normal')
        if hasattr(self, 'stop_stitch_btn'):
            self.stop_stitch_btn.config(state='disabled')
        if hasattr(self, 'status_var'):
            self.status_var.set("Stitching stopped - result ready")
    
    def save_result(self):
        """Save the final stitched image"""
        if self.canvas is not None:
            # Crop to content area
            gray_canvas = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2GRAY)
            coords = cv2.findNonZero(gray_canvas)
            
            if coords is not None:
                x, y, w, h = cv2.boundingRect(coords)
                result_img = self.canvas[y:y+h, x:x+w]
            else:
                result_img = self.canvas.copy()
            
            timestamp = int(time.time())
            filename = f"stitched_microscope_{timestamp}.png"
            cv2.imwrite(filename, result_img)
            self.status_var.set(f"Saved: {filename}")
    
    # ============================================================
    # VISUAL SERVOING METHODS
    # ============================================================
    
    def toggle_organism_tracking(self):
        """Toggle organism tracking on/off with proper cleanup."""
        if not self.tracking_mode_active:
            # Start tracking
            self.start_organism_tracking()
        else:
            # Stop tracking
            self.stop_organism_tracking()
    
    def start_organism_tracking(self):
        """Start simple organism tracking with OpenCV windows like click_proxy."""
        if not self.is_capturing:
            self.status_var.set("Start camera first before tracking")
            return
        
        self.tracking_mode_active = True
        
        # Simple tracking variables (like click_proxy)
        self.tracking_active = False
        self.target_position = None
        self.target_history = []
        self.selected_contour = None
        self.click_position = None
        self.awaiting_selection = False
        
        # Tracking parameters
        self.MAX_JUMP_DISTANCE = 100
        self.MIN_CONTOUR_AREA = 50
        self.MAX_CONTOUR_AREA = 3000
        self.SEARCH_RADIUS = 150
        
        # Motor control parameters (updated for much calmer movement)
        self.auto_centering_enabled = False
        self.PIXELS_PER_STEP_X = 2.0  # Calibration constant
        self.PIXELS_PER_STEP_Y = 2.0  # Calibration constant
        self.DEADZONE = 50  # Pixels - much larger deadzone to reduce erratic movement
        self.AXIS_THRESHOLD = 30  # Minimum error to move individual axis
        self.MAX_STEPS = 5  # Maximum steps per command for safety
        self.frame_center_x = None  # Will be computed from frame size
        self.frame_center_y = None
        self.last_motor_command_time = 0  # Rate limiting
        self.MOTOR_COMMAND_INTERVAL = 3.0  # 3 seconds between commands (much slower)
        self.motor_stop_sent = False  # Track if stop command was already sent
        
        # Start the simple tracking loop
        self.simple_tracking_thread = threading.Thread(target=self.simple_tracking_loop)
        self.simple_tracking_thread.daemon = True
        self.simple_tracking_thread.start()
        
        # Update button states
        self.start_tracking_btn.config(text="Stop Organism Tracking", state='normal')
        self.toggle_auto_track_btn.config(state='normal')
        
        self.status_var.set("Organism tracking started - OpenCV windows will open")
    
    def simple_tracking_loop(self):
        """Simple tracking loop exactly like click_proxy - no complex integration."""
        print("\n" + "="*70)
        print("SIMPLE ORGANISM TRACKER")
        print("="*70)
        print("Click on organism to track, press 'q' to quit")
        print("="*70 + "\n")
        
        # Create OpenCV windows
        window_name = 'Organism Tracker'
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, self.simple_mouse_callback)
        
        while self.tracking_mode_active and self.is_capturing:
            try:
                # Get frame from queue
                if not self.raw_frame_queue.empty():
                    frame_raw = self.raw_frame_queue.get()
                    
                    # Use FULL camera frame for tracking (not cropped like stitching)
                    frame = frame_raw.copy()  # Use full frame, not cropped region
                    
                    # Compute frame center once (required for motor control)
                    if self.frame_center_x is None:
                        self.frame_center_x = frame.shape[1] // 2
                        self.frame_center_y = frame.shape[0] // 2
                        print(f"Frame center: ({self.frame_center_x}, {self.frame_center_y})")
                    
                    # Background subtraction
                    fg_mask = self.backsub.apply(frame)
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                    mask_cleaned = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
                    
                    # Find contours
                    contours, _ = cv2.findContours(mask_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    valid_contours = [c for c in contours if self.MIN_CONTOUR_AREA < cv2.contourArea(c) < self.MAX_CONTOUR_AREA]
                    
                    # Handle click selection
                    if self.awaiting_selection and self.click_position:
                        nearest_cnt, distance, centroid = self.find_nearest_contour(valid_contours, self.click_position)
                        if nearest_cnt is not None and distance < 100:
                            self.tracking_active = True
                            self.target_position = centroid
                            self.selected_contour = nearest_cnt
                            self.target_history = [centroid]
                            # Reset motor control state on new click
                            self.last_motor_command_time = 0
                            self.motor_stop_sent = False
                            print(f"Locked onto organism at {centroid} - Motor control reset")
                        self.awaiting_selection = False
                        self.click_position = None
                    
                    # Update tracking
                    if self.tracking_active and self.target_position:
                        nearest_cnt, distance, centroid = self.find_nearest_contour(valid_contours, self.target_position)
                        if nearest_cnt is not None and distance < self.MAX_JUMP_DISTANCE:
                            self.target_position = centroid
                            self.target_history.append(centroid)
                            self.selected_contour = nearest_cnt
                            
                            # Reset stop flag since we have valid tracking
                            self.motor_stop_sent = False
                            
                            # MOTOR CONTROL INTEGRATION POINT (3 second intervals)
                            if self.auto_centering_enabled and self.arduino_connected:
                                cx, cy = centroid
                                y_cmd, x_cmd = self.compute_motor_direction(cx, cy)
                                self.send_motor_command_simple(y_cmd, x_cmd, cx, cy)
                            
                            # Keep history manageable
                            if len(self.target_history) > 50:
                                self.target_history.pop(0)
                        else:
                            print("Tracking lost")
                            self.tracking_active = False
                            # Send stop command once when tracking is lost
                            if self.auto_centering_enabled and self.arduino_connected and not self.motor_stop_sent:
                                self.send_motor_command_simple('S', 'S')
                                self.motor_stop_sent = True
                                print("Motors stopped - tracking lost")
                    
                    # Draw everything (like click_proxy)
                    display_frame = frame.copy()
                    
                    # Draw crop region overlay to show stitching area vs tracking area
                    cv2.rectangle(display_frame, 
                                (self.crop_left, self.crop_top), 
                                (self.crop_right, self.crop_bottom), 
                                (0, 255, 255), 2)  # Yellow rectangle for crop region
                    cv2.putText(display_frame, "Stitching Region", 
                               (self.crop_left + 5, self.crop_top - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    
                    # Draw frame center crosshair for motor control reference
                    if self.frame_center_x is not None:
                        cv2.line(display_frame, 
                                (self.frame_center_x - 20, self.frame_center_y), 
                                (self.frame_center_x + 20, self.frame_center_y), 
                                (255, 0, 0), 2)  # Blue crosshair
                        cv2.line(display_frame, 
                                (self.frame_center_x, self.frame_center_y - 20), 
                                (self.frame_center_x, self.frame_center_y + 20), 
                                (255, 0, 0), 2)
                        
                    
                    # Draw all contours faintly
                    for cnt in valid_contours:
                        M = cv2.moments(cnt)
                        if M["m00"] != 0:
                            cx = int(M["m10"] / M["m00"])
                            cy = int(M["m01"] / M["m00"])
                            cv2.drawContours(display_frame, [cnt], -1, (255, 200, 100), 1)
                            cv2.circle(display_frame, (cx, cy), 3, (255, 200, 100), -1)
                    
                    # Draw tracking info
                    if self.tracking_active and self.target_position:
                        cx, cy = self.target_position
                        
                        # Draw tracked contour
                        if self.selected_contour is not None:
                            cv2.drawContours(display_frame, [self.selected_contour], -1, (0, 0, 255), 1)
                        
                        # Centroid marker
                        cv2.circle(display_frame, (cx, cy), 1, (0, 0, 255), -1)
                        cv2.circle(display_frame, (cx, cy), 20, (255, 255, 255), 1)
                        
                        # Coordinates with error display for motor control
                        error_x = cx - self.frame_center_x if self.frame_center_x else 0
                        error_y = cy - self.frame_center_y if self.frame_center_y else 0
                        cv2.putText(display_frame, f"TRACKING: ({cx}, {cy})", 
                                   (cx + 15, cy - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                        cv2.putText(display_frame, f"Error: ({error_x:+d}, {error_y:+d})", 
                                   (cx + 15, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        
                        # Trail
                        if len(self.target_history) > 1:
                            points = np.array(self.target_history, dtype=np.int32)
                            cv2.polylines(display_frame, [points], False, (0, 255, 255), 2)
                    
                    # Status overlay
                    status_bg = display_frame.copy()
                    cv2.rectangle(status_bg, (0, 0), (display_frame.shape[1], 80), (0, 0, 0), -1)
                    cv2.addWeighted(status_bg, 0.4, display_frame, 0.6, 0, display_frame)
                    
                    # Status text
                    if self.tracking_active:
                        status = "TRACKING ACTIVE"
                        if self.auto_centering_enabled:
                            status += " - AUTO-CENTERING ON"
                        color = (0, 255, 0)
                    else:
                        status = "CLICK TO SELECT ORGANISM"
                        color = (0, 165, 255)
                    
                    cv2.putText(display_frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    cv2.putText(display_frame, "Controls: CLICK=Select | T=Auto-Center | R=Reset | Q=Quit", 
                               (10, display_frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                    
                    # Show windows
                    cv2.imshow(window_name, display_frame)
                    cv2.imshow('Motion Mask', mask_cleaned)
                    
                    # Handle keys
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord('r'):
                        self.tracking_active = False
                        self.target_position = None
                        self.target_history = []
                        # Reset motor control state and send stop command
                        if self.auto_centering_enabled and self.arduino_connected:
                            self.send_motor_command_simple('S', 'S')
                            self.last_motor_command_time = 0  # Reset timing
                            self.motor_stop_sent = True
                        print("Tracking reset - Motors stopped")
                    elif key == ord('t'):
                        self.toggle_auto_tracking()
                
                time.sleep(1/30)
                
            except Exception as e:
                print(f"Tracking error: {e}")
                time.sleep(0.1)
        
        # Cleanup (thread-safe)
        cv2.destroyAllWindows()
        print("Tracking loop ended - OpenCV windows closed")
    
    def simple_mouse_callback(self, event, x, y, flags, param):
        """Simple mouse callback like click_proxy."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.click_position = (x, y)
            self.awaiting_selection = True
            print(f"Click at ({x}, {y})")
    
    def find_nearest_contour(self, contours, target_point):
        """Find contour closest to target point."""
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
    
    def compute_motor_direction(self, cx, cy):
        """
        Determine single-step direction with independent axis thresholds.
        Only moves axes that are significantly off-center to reduce erratic movement.
        """
        if self.frame_center_x is None or self.frame_center_y is None:
            return 'S', 'S'  # Stop if no center defined
        
        # Compute pixel error (organism position - frame center)
        error_x = cx - self.frame_center_x
        error_y = cy - self.frame_center_y
        
        # Global deadzone - if both errors are small, don't move at all
        if abs(error_x) < self.DEADZONE and abs(error_y) < self.DEADZONE:
            return 'S', 'S'  # Stop - organism is centered enough
        
        # Independent axis movement with higher thresholds
        y_cmd = 'S'  # Default to stop
        x_cmd = 'S'  # Default to stop
        
        # Only move Y if error is significant (prevents small jitter movements)
        if abs(error_y) > self.AXIS_THRESHOLD:
            if error_y > 0:
                y_cmd = 'D'  # Organism too high, move stage down
            else:
                y_cmd = 'U'  # Organism too low, move stage up
        
        # Only move X if error is significant (prevents small jitter movements)
        if abs(error_x) > self.AXIS_THRESHOLD:
            if error_x > 0:
                x_cmd = 'R'  # Organism too right, move stage left
            else:
                x_cmd = 'L'  # Organism too left, move stage right
        
        return y_cmd, x_cmd
    
    def send_motor_command_simple(self, y_cmd, x_cmd, cx=None, cy=None):
        """
        Send single motor command for tracking (3 second intervals, thread-safe).
        """
        # Don't send if no movement needed
        if y_cmd == 'S' and x_cmd == 'S':
            # Always allow stop commands to go through immediately
            if not self.arduino_connected or not self.arduino:
                return False
            try:
                cmd = f"{y_cmd}{x_cmd}\n"
                self.arduino.write(cmd.encode())
                time.sleep(0.02)
                if self.arduino.in_waiting:
                    self.arduino.readline()  # Consume response
                print("Motors stopped")
                return True
            except Exception as e:
                print(f"Stop command failed: {e}")
                return False
        
        # Rate limiting - 3 seconds between movement commands
        current_time = time.time()
        time_since_last = current_time - self.last_motor_command_time
        if time_since_last < self.MOTOR_COMMAND_INTERVAL:
            # Only show countdown occasionally to reduce spam
            remaining = self.MOTOR_COMMAND_INTERVAL - time_since_last
            if int(remaining) % 2 == 0 and remaining > 1.0:  # Print every 2 seconds, only if >1s remaining
                print(f"Motor ready in {remaining:.0f}s...")
            return True
        
        # Send command directly to Arduino without GUI updates
        if not self.arduino_connected or not self.arduino:
            print("Arduino not connected for motor command")
            return False
        
        try:
            cmd = f"{y_cmd}{x_cmd}\n"
            self.arduino.write(cmd.encode())
            
            # Brief wait for Arduino processing
            time.sleep(0.02)
            
            # Read response if available (optional)
            if self.arduino.in_waiting:
                response = self.arduino.readline().decode().strip()
                # Don't print response to avoid spam, just consume it
            
            self.last_motor_command_time = current_time
            # Show actual command with error context if position provided
            if cx is not None and cy is not None and self.frame_center_x is not None:
                error_x = cx - self.frame_center_x
                error_y = cy - self.frame_center_y
                print(f"MOTOR COMMAND: {y_cmd}{x_cmd} | Error: ({error_x:+d}, {error_y:+d}) | Next in 3.0s")
            else:
                print(f"MOTOR COMMAND: {y_cmd}{x_cmd} | Next in 3.0s")
            return True
            
        except Exception as e:
            print(f"Motor command failed: {e}")
            return False
    
    def stop_organism_tracking(self):
        """Stop organism tracking and reset button states (GUI thread safe)."""
        print("Stopping organism tracking...")
        
        # Signal tracking thread to stop
        self.tracking_mode_active = False
        
        # Wait a moment for thread to finish
        if hasattr(self, 'simple_tracking_thread') and self.simple_tracking_thread.is_alive():
            self.simple_tracking_thread.join(timeout=2.0)
        
        # Send final stop command to motors (thread-safe)
        if hasattr(self, 'auto_centering_enabled') and self.auto_centering_enabled and self.arduino_connected:
            try:
                if self.arduino:
                    self.arduino.write(b"SS\n")
                    time.sleep(0.1)
                    print("Sent final stop command to motors")
            except Exception as e:
                print(f"Error sending final stop command: {e}")
        
        # Reset tracking state
        self.tracking_active = False
        self.target_position = None
        self.target_history = []
        self.auto_centering_enabled = False
        
        # Update button states (safe from GUI thread)
        self.start_tracking_btn.config(text="Start Organism Tracking", state='normal')
        self.toggle_auto_track_btn.config(state='disabled', text="Enable Auto-Centering")
        
        self.status_var.set("Organism tracking stopped - ready to restart")
        print("Organism tracking stopped successfully")
    
    def toggle_auto_tracking(self):
        """Toggle automatic motor control for visual servoing."""
        if not self.tracking_mode_active:
            return
        
        if not self.arduino_connected:
            print("Arduino not connected - cannot enable auto-centering")
            self.status_var.set("Connect Arduino first for auto-centering")
            return
        
        # Toggle auto-centering state
        self.auto_centering_enabled = not self.auto_centering_enabled
        
        if self.auto_centering_enabled:
            self.toggle_auto_track_btn.config(text="Disable Auto-Centering")
            self.status_var.set("Auto-centering ENABLED - stage will move to keep organism centered")
            print("Auto-centering ENABLED")
        else:
            self.toggle_auto_track_btn.config(text="Enable Auto-Centering")
            self.status_var.set("Auto-centering DISABLED - tracking only, no motor movement")
            # Safety stop when disabling (thread-safe)
            try:
                if self.arduino:
                    self.arduino.write(b"SS\n")
                    time.sleep(0.1)
                    print("Motors stopped - auto-centering disabled")
            except Exception as e:
                print(f"Error stopping motors: {e}")
            print("Auto-centering DISABLED")
    
    def update_servo_settings(self):
        """Update visual servoing calibration parameters."""
        print("Servo settings update - feature coming soon")
        self.status_var.set("Servo settings noted")
    
    
    def run(self):
        """
        Start the application.
        
        OOP Concept: Public method that starts the main event loop
        """
        self.root.mainloop()
    
    def cleanup(self):
        """
        Clean up resources, ensuring Arduino is stopped.
        
        OOP Concept: Method that properly releases resources when object is destroyed
        """
        print("Starting cleanup...")
        
        # Stop all activities
        self.is_capturing = False
        self.is_stitching = False
        self.auto_scan_active = False  # Stop any automated scanning
        self.tracking_mode_active = False  # Stop organism tracking
        
        # Wait a moment for threads to notice the stop flags
        time.sleep(0.5)
        
        # Safety stop - motors must stop when system shuts down (thread-safe)
        if hasattr(self, 'auto_centering_enabled') and self.auto_centering_enabled and self.arduino_connected:
            try:
                # Direct Arduino communication without GUI updates
                if self.arduino:
                    self.arduino.write(b"SS\n")
                    time.sleep(0.1)
                    print("Sent direct stop command to Arduino")
            except Exception as e:
                print(f"Error sending stop command: {e}")
        
        # Close OpenCV windows
        try:
            cv2.destroyAllWindows()
        except:
            pass
        
        # Close full view window if open
        if hasattr(self, 'full_view_window') and self.full_view_window:
            try:
                self.full_view_window.destroy()
            except:
                pass
        
        # Close Arduino connection
        if self.arduino_connected and self.arduino:
            try:
                self.arduino.close()
                print("Arduino connection closed")
            except Exception as e:
                print(f"Error closing Arduino: {e}")
        
        # Release camera
        if hasattr(self, 'camera') and self.camera:
            try:
                self.camera.release()
                print("Camera released")
            except Exception as e:
                print(f"Error releasing camera: {e}")
        
        print("System shutdown complete")

# Usage - Creating and using the class
if __name__ == "__main__":
    # OOP Concept: Instantiation - creating an object of the class
    app = MicroscopeStitcher()
    try:
        # OOP Concept: Method call - calling a method on the object
        app.run()
    finally:
        # OOP Concept: Cleanup - ensuring resources are properly released
        app.cleanup()