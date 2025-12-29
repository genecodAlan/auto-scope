import cv2
import numpy as np
import serial
import time
import tkinter as tk
from tkinter import ttk

class MicroscopeStitcher:
    def __init__(self):
        # Arduino control
        self.arduino = None
        self.arduino_connected = False
        
        # GUI components
        self.root = tk.Tk()
        self.root.title("Microscope Stitcher")
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        
        # Create status label
        status_label = ttk.Label(self.root, textvariable=self.status_var)
        status_label.pack(pady=5)
        
        # Bind arrow keys
        self.root.bind('<Up>', self.on_key_press)
        self.root.bind('<Down>', self.on_key_press)
        self.root.bind('<Left>', self.on_key_press)
        self.root.bind('<Right>', self.on_key_press)
        
        # Initialize video capture
        self.cap = cv2.VideoCapture(1)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # Initialize stitching variables
        self.setup_stitching()
        
    def setup_stitching(self):
        # Your existing stitching initialization code
        self.orb = cv2.ORB_create(nfeatures=1000)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        
        self.crop_top, self.crop_bottom = 195, 489
        self.crop_left, self.crop_right = 55, 349
        
        self.canvas_height, self.canvas_width = 1500, 1500
        self.canvas = np.zeros((self.canvas_height, self.canvas_width, 3), dtype=np.uint8)
        
        self.pos_x = (self.canvas_width - (self.crop_right - self.crop_left)) // 2
        self.pos_y = ((self.crop_bottom)) // 2
        self.first_frame_init = False
        
    def connect_arduino(self, port="COM3", baud_rate=115200):
        try:
            self.arduino = serial.Serial(port, baud_rate, timeout=1)
            self.arduino_connected = True
            self.status_var.set("Arduino connected")
        except Exception as e:
            self.status_var.set(f"Arduino connection failed: {str(e)}")
    
    # Your existing methods
    
    def send_step(self, y_cmd, x_cmd):
        """
        Send a single step command matching your Arduino protocol.
        Format: 2-character command like "US", "DS", "LS", "RS"
        
        OOP Concept: Method that encapsulates Arduino communication protocol
        """
        if self.arduino_connected and self.arduino:
            try:
                cmd = f"{y_cmd}{x_cmd}"
                self.arduino.write(cmd.encode())
                print(f"Sent: {cmd}")  # Debug output
                return True
            except Exception as e:
                self.status_var.set(f"COMMUNICATION ERROR - Check cable connection: {str(e)}")
                return False
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
        """
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
        

    def blend_regions(canvas_region, new_region):
        """
        Alpha blend overlapping areas between canvas and new_region to avoid seams.
        canvas_region and new_region are numpy arrays of same shape.
        This removes the black lining between canvases 
        """
        alpha = 0.5
        # Create mask of where both regions have non-black pixels (assuming black means zero)
        overlap_mask = (np.sum(canvas_region, axis=2) > 0) & (np.sum(new_region, axis=2) > 0)

        blended = canvas_region.copy()
        # Blend overlapping pixels with equal alpha
        blended[overlap_mask] = (alpha * canvas_region[overlap_mask] + (1 - alpha) * new_region[overlap_mask]).astype(np.uint8)
        # For pixels only in new_region where canvas is black, copy them over
        only_new_mask = (np.sum(canvas_region, axis=2) == 0) & (np.sum(new_region, axis=2) > 0)
        blended[only_new_mask] = new_region[only_new_mask]

        return blended

    
    def run(self):
        while True:
            # Process GUI events
            self.root.update()
            
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to grab frame.")
                break

            # Your existing stitching code
            frame_cropped = frame[self.crop_top:self.crop_bottom, 
                                self.crop_left:self.crop_right]
            # ...rest of your stitching code...

            cv2.imshow("Stitched Canvas", self.canvas)
            
            if cv2.waitKey(1) == 27:  # ESC key
                break
        
        self.cap.release()
        cv2.destroyAllWindows()
        self.root.destroy()

def main():
    stitcher = MicroscopeStitcher()
    stitcher.connect_arduino()  # Connect to Arduino
    stitcher.run()

if __name__ == "__main__":
    main()

