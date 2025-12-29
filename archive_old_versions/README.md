# Archive - Old Versions

This folder contains previous versions and development files from the microscope stitcher project.

## Version History

### v0_raw_stitching_algorithm.py
- **Original**: cv2_Stitch_Raw.py
- **Description**: Initial proof-of-concept for live stitching algorithm
- **Features**: 
  - Basic ORB feature matching
  - Alpha blending for smooth transitions
  - Manual camera control
- **Status**: Foundation for later versions

### v1_basic_stitcher_with_arduino.py
- **Original**: Basic_Live_Stitch.py
- **Description**: First integration with Arduino control
- **Features**:
  - Arduino serial communication (115200 baud)
  - Basic GUI with tkinter
  - Arrow key controls
  - 2-character command protocol (US, DS, LS, RS)
- **Status**: Early Arduino integration

### v2_threaded_stitcher_with_gui.py
- **Original**: Live_Stitching.py
- **Description**: Advanced version with threading and improved GUI
- **Features**:
  - Multi-threaded capture and stitching
  - Separate preview window
  - Queue-based frame processing
  - Better GUI layout
- **Status**: Pre-release version before final Arrows_Key.py

## Old Module Files

### old_camera_module.py
- **Original**: micro_camera_scope/camera.py
- **Description**: Standalone camera control with serial communication
- **Features**: Basic Arduino serial testing (9600 baud)

### old_main_click_to_center.py
- **Original**: micro_camera_scope/main.py
- **Description**: Click-to-center movement system
- **Features**: 
  - Mouse click to move stage to center
  - Pixel-to-step conversion (1.875 pixels per step)
  - Y X command format

### old_processing_module.py
- **Original**: micro_camera_scope/processing.py
- **Description**: Image processing utilities (if existed)

### old_utils_module.py
- **Original**: micro_camera_scope/utils.py
- **Description**: Utility functions (if existed)

## Development Tools

### dev_mouse_coordinate_tester.py
- **Original**: Mouse_Cords.py
- **Description**: Simple tool to test mouse click coordinates
- **Purpose**: Development/debugging tool for click-based controls

## Current Version

The current production version is:
**micro_camera_scope/Arrows_Key.py**

This version includes:
- Automated lawnmower scanning
- Position tracking with home setting
- Frame capture during auto-scan
- Improved Arduino protocol
- Configurable scan parameters
- Boundary checking
