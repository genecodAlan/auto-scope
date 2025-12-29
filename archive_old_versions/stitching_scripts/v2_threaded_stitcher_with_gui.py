import cv2
import numpy as np
import threading
import time
from queue import Queue
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import serial
import serial.tools.list_ports

class MicroscopeStitcher:
    """
    Main class for microscope image stitching with Arduino control.
    
    OOP Concepts demonstrated:
    - Encapsulation: All data and methods are contained within the class
    - Constructor (__init__): Initializes object state
    - Instance variables (self.variable): Store object-specific data
    - Methods: Functions that operate on the object's data
    """
    
    def __init__(self):
        """
        Constructor method - called when creating a new instance of the class.
        Initializes all the instance variables (object's state).
        """
        # Camera and capture control
        self.camera = None
        self.is_capturing = False
        self.is_stitching = False
        self.stitching_active = False
        
        # Image cropping parameters
        self.crop_top, self.crop_bottom = 240, 465 
        self.crop_left, self.crop_right = 180, 380
        
        # Stitching components - your smooth stitching algorithm
        self.orb = cv2.ORB_create(nfeatures=1000)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        
        # Canvas for stitching (larger canvas for your algorithm)
        self.canvas_height, self.canvas_width = 1500, 1500
        self.canvas = np.zeros((self.canvas_height, self.canvas_width, 3), dtype=np.uint8)
        self.pos_x = (self.canvas_width - (self.crop_right - self.crop_left)) // 2
        self.pos_y = ((self.canvas_height) // 2) - (self.crop_bottom)
        self.first_frame_init = False
        
        # Tracking variables for smooth stitching
        self.kp_last = None
        self.des_last = None
        self.pos_last = None
        
        # Threading components
        self.frame_queue = Queue(maxsize=10)
        self.stitch_queue = Queue(maxsize=5)
        
        # Arduino communication
        self.arduino = None
        self.arduino_connected = False
        
        # GUI components
        self.root = None
        self.preview_window = None
        self.setup_gui()
        
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
        
        self.start_camera_btn = ttk.Button(control_frame, text="Start Camera", 
                                         command=self.start_camera)
        self.start_camera_btn.pack(side=tk.LEFT, padx=5)
        
        self.start_stitch_btn = ttk.Button(control_frame, text="Start Stitching", 
                                         command=self.start_stitching, state='disabled')
        self.start_stitch_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_stitch_btn = ttk.Button(control_frame, text="Stop Stitching", 
                                        command=self.stop_stitching, state='disabled')
        self.stop_stitch_btn.pack(side=tk.LEFT, padx=5)
        
        self.reset_canvas_btn = ttk.Button(control_frame, text="Reset Canvas", 
                                         command=self.reset_canvas)
        self.reset_canvas_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_btn = ttk.Button(control_frame, text="Save Result", 
                                 command=self.save_result, state='disabled')
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        # Arrow key control panel
        arrow_frame = ttk.LabelFrame(self.root, text="Manual Movement", padding=10)
        arrow_frame.pack(pady=5, padx=10, fill=tk.X)
        
        ttk.Label(arrow_frame, text="Use arrow keys to control microscope stage:").pack()
        
        # Bind arrow keys for Arduino control
        self.root.bind('<Key>', self.on_key_press)
        self.root.focus_set()  # Ensure window can receive key events
        
        # Live camera feed display
        self.camera_label = ttk.Label(self.root, text="Camera feed will appear here")
        self.camera_label.pack(pady=20)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def connect_arduino(self):
        """
        Connect to Arduino on COM3 port.
        
        OOP Concept: Method that modifies object state (self.arduino, self.arduino_connected)
        """
        try:
            self.arduino = serial.Serial('COM3', 9600, timeout=1)
            time.sleep(2)  # Wait for Arduino to initialize
            self.arduino_connected = True
            
            self.connect_arduino_btn.config(state='disabled')
            self.disconnect_arduino_btn.config(state='normal')
            self.arduino_status.config(text="Connected", foreground="green")
            self.status_var.set("Arduino connected on COM3")
            
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
            
    def send_arduino_command(self, command):
        """
        Send command to Arduino.
        
        OOP Concept: Method that uses instance variables (self.arduino, self.arduino_connected)
        """
        if self.arduino_connected and self.arduino:
            try:
                self.arduino.write(f"{command}\n".encode())
                return True
            except Exception as e:
                self.status_var.set(f"Arduino communication error: {str(e)}")
                return False
        return False
        
    def on_key_press(self, event):
        """Handle arrow key presses for Arduino control"""
        if not self.arduino_connected:
            return
            
        key_commands = {
            'Up': 'UP',
            'Down': 'DOWN', 
            'Left': 'LEFT',
            'Right': 'RIGHT'
        }
        
        if event.keysym in key_commands:
            command = key_commands[event.keysym]
            if self.send_arduino_command(command):
                self.status_var.set(f"Sent command: {command}")
        
    def start_camera(self):
        """
        Initialize camera and start capture thread.
        
        OOP Concept: Method that coordinates multiple object components
        """
        try:
            self.camera = cv2.VideoCapture(1)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

            if not self.camera.isOpened():
                raise Exception("Could not open camera")
            
            self.is_capturing = True
            self.capture_thread = threading.Thread(target=self.capture_frames)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            self.display_thread = threading.Thread(target=self.update_display)
            self.display_thread.daemon = True
            self.display_thread.start()
            
            self.start_camera_btn.config(state='disabled')
            self.start_stitch_btn.config(state='normal')
            self.status_var.set("Camera active")
            
        except Exception as e:
            self.status_var.set(f"Camera error: {str(e)}")
    
    def capture_frames(self):
        """
        Continuous frame capture thread.
        
        OOP Concept: Method that runs in a separate thread, accessing object state
        """
        while self.is_capturing:
            ret, frame = self.camera.read()
            if ret:
                frame_cropped = frame[self.crop_top:self.crop_bottom, self.crop_left:self.crop_right]

                # Add frame to queue for display
                if not self.frame_queue.full():
                    self.frame_queue.put(frame_cropped.copy())
                
                # If stitching is active, add to stitch queue
                if self.stitching_active and not self.stitch_queue.full():
                    self.stitch_queue.put(frame_cropped.copy())
            
            time.sleep(1/30)  # 30 FPS
    
    def update_display(self):
        """Update camera display in GUI"""
        while self.is_capturing:
            if not self.frame_queue.empty():
                frame = self.frame_queue.get()
                
                # Convert to RGB and resize for display
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_resized = cv2.resize(frame_rgb, (480, 360))
                
                # Convert to PhotoImage for tkinter
                image = Image.fromarray(frame_resized)
                photo = ImageTk.PhotoImage(image)
                
                self.camera_label.config(image=photo, text="")
                self.camera_label.image = photo  # Keep reference
            
            time.sleep(1/30)
    
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
        self.stitching_active = False
        self.is_stitching = False
        
        self.start_stitch_btn.config(state='normal')
        self.stop_stitch_btn.config(state='disabled')
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
    
    def run(self):
        """
        Start the application.
        
        OOP Concept: Public method that starts the main event loop
        """
        self.root.mainloop()
    
    def cleanup(self):
        """
        Clean up resources.
        
        OOP Concept: Method that properly releases resources when object is destroyed
        """
        self.is_capturing = False
        self.is_stitching = False
        
        if self.camera:
            self.camera.release()
            
        if self.arduino_connected and self.arduino:
            self.arduino.close()

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