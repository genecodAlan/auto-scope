<<<<<<< HEAD
# auto-scope
ESP8266 and stepper motor controlled microscope baseplate. Python based software with tkinter GUI for features such as image stitching, hematology classification and live organism tracking with PID. 
=======
# Microscope Image Stitcher with Arduino Control

A Python application for automated microscope image stitching with Arduino-controlled stage movement.

## Features

- Real-time camera feed from USB microscope
- Manual stage control via arrow keys or GUI buttons
- Automated lawnmower pattern scanning
- Live image stitching with smooth blending
- Arduino-based XY stage control

## Hardware Requirements

- USB microscope camera (Camera index 1)
- Arduino connected to COM3 (115200 baud)
- XY motorized stage controlled by Arduino

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure Arduino is programmed and connected to COM3

## Usage

Run the main application:
```bash
python micro_camera_scope/Arrows_Key.py
```

### Controls

1. **Connect Arduino**: Click "Connect Arduino (COM3)" button
2. **Set Home**: Click "Set XY home" to establish origin point
3. **Start Camera**: Initialize the camera feed
4. **Manual Control**: 
   - Use arrow keys to move stage one microstep at a time
   - Or click directional buttons in GUI
5. **Manual Stitching**: Click "Start Manual Stitching" and move stage manually
6. **Auto Scan**: Configure scan parameters and click "Start Auto Scan" for automated scanning

### Auto Scan Configuration

- **Steps per row**: Number of horizontal movements (2-20)
- **Number of rows**: Vertical scan rows (2-10)
- **Step delay**: Time between movements in seconds (0.5-5.0)

## Project Structure

```
.
├── micro_camera_scope/
│   └── Arrows_Key.py          # Main application (run this)
├── captured_images/            # Saved frame captures
├── images/                     # Stitched output images
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Output

- Captured frames: `captured_images/frame_XXXX.png`
- Stitched images: `stitched_microscope_[timestamp].png`

## Troubleshooting

- **Camera not found**: Check camera index (currently set to 1)
- **Arduino connection failed**: Verify COM port and baud rate (115200)
- **Movement limits**: Set home position before scanning to enable boundary checking
>>>>>>> a89cc45 (Add: All files from micro_camera_scope and colony_counter)
