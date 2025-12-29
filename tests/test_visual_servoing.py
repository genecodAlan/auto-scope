#!/usr/bin/env python3
"""
Test script for visual servoing integration.

This script demonstrates the integrated organism tracking with motor control
for automatic centering of tracked organisms.

Usage:
1. Connect Arduino to COM3
2. Run this script
3. Start camera and confirm crop region
4. Click "Start Organism Tracking"
5. Click on an organism in the tracking window
6. Click "Enable Auto-Centering" to start visual servoing
7. The stage should automatically move to keep the organism centered

Controls:
- T: Toggle auto-centering on/off
- R: Reset tracking (select new organism)
- Arrow keys: Manual motor control
- Q: Quit
"""

import sys
import os

# Add the micro_camera_scope directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'micro_camera_scope'))

from Arrows_Key import MicroscopeStitcher

def main():
    print("="*70)
    print("VISUAL SERVOING TEST")
    print("="*70)
    print("\nThis test demonstrates organism tracking with automatic motor control.")
    print("\nSetup Instructions:")
    print("1. Connect Arduino to COM3")
    print("2. Connect camera to USB port 1")
    print("3. Place sample under microscope")
    print("4. Ensure organisms are visible and moving")
    print("\nOperation:")
    print("1. Click 'Connect Arduino'")
    print("2. Click 'Start Camera' and adjust crop region")
    print("3. Click 'Confirm Crop Region'")
    print("4. Click 'Start Organism Tracking'")
    print("5. Click on an organism in the tracking window")
    print("6. Click 'Enable Auto-Centering' for visual servoing")
    print("\nThe stage will automatically move to keep the tracked organism centered!")
    print("="*70)
    
    # Create and run the application
    app = MicroscopeStitcher()
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        app.cleanup()
        print("Test complete.")

if __name__ == "__main__":
    main()