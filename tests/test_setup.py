"""
Quick setup verification script
Run this to check if all dependencies are installed correctly
"""

import sys

def check_imports():
    """Check if all required packages can be imported"""
    print("Checking dependencies...\n")
    
    packages = {
        'cv2': 'opencv-python',
        'numpy': 'numpy',
        'serial': 'pyserial',
        'PIL': 'Pillow',
        'tkinter': 'tkinter (built-in)'
    }
    
    all_good = True
    
    for module, package in packages.items():
        try:
            __import__(module)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} - NOT INSTALLED")
            all_good = False
    
    print("\n" + "="*50)
    
    if all_good:
        print("✓ All dependencies installed correctly!")
        print("\nYou can now run: python micro_camera_scope/Arrows_Key.py")
    else:
        print("✗ Some dependencies are missing")
        print("\nPlease run: pip install -r requirements.txt")
    
    return all_good

def check_camera():
    """Check if camera is accessible"""
    print("\n" + "="*50)
    print("Checking camera access...\n")
    
    try:
        import cv2
        cap = cv2.VideoCapture(1)
        if cap.isOpened():
            print("✓ Camera found at index 1")
            cap.release()
            return True
        else:
            print("✗ Camera not found at index 1")
            print("  Try checking camera index or connection")
            return False
    except Exception as e:
        print(f"✗ Camera check failed: {e}")
        return False

def check_serial_ports():
    """List available serial ports"""
    print("\n" + "="*50)
    print("Checking serial ports...\n")
    
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        
        if ports:
            print("Available COM ports:")
            for port in ports:
                print(f"  - {port.device}: {port.description}")
                if "COM3" in port.device:
                    print("    ✓ COM3 found (configured port)")
        else:
            print("✗ No COM ports found")
            print("  Check Arduino connection")
        
        return len(ports) > 0
    except Exception as e:
        print(f"✗ Serial port check failed: {e}")
        return False

if __name__ == "__main__":
    print("="*50)
    print("Microscope Stitcher - Setup Verification")
    print("="*50 + "\n")
    
    deps_ok = check_imports()
    
    if deps_ok:
        cam_ok = check_camera()
        serial_ok = check_serial_ports()
        
        print("\n" + "="*50)
        print("Setup Summary:")
        print(f"  Dependencies: {'✓' if deps_ok else '✗'}")
        print(f"  Camera:       {'✓' if cam_ok else '✗'}")
        print(f"  Serial Ports: {'✓' if serial_ok else '✗'}")
        print("="*50)
        
        if deps_ok and cam_ok and serial_ok:
            print("\n✓ System ready! Run: python micro_camera_scope/Arrows_Key.py")
        else:
            print("\n⚠ Some components need attention (see above)")
    
    input("\nPress Enter to exit...")
