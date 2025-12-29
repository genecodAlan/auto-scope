# Colony Analysis

This folder contains files related to bacterial colony counting and analysis.

## Main Script

### colony_counter.py
- **Original**: Microbio_colony.py
- **Description**: Interactive bacterial colony counter with manual correction
- **Features**:
  - Automatic colony detection using contour analysis
  - Manual circle drawing for missed colonies
  - Rectangle tool to exclude non-colony regions
  - Mode switching (circle/rectangle) with 'm' key
  - Real-time colony count display
  - Morphological operations for noise reduction

### Usage
```python
python colony_counter.py
```

**Controls:**
- Left click + drag: Draw circle (circle mode) or rectangle (rectangle mode)
- 'm' key: Switch between circle and rectangle modes
- 'q' or ESC: Quit

**Detection Parameters:**
- Area threshold: 1 < area < 1600 pixels
- Shape validation: Checks if contour is roughly circular
- Adjustable thresholds for different colony sizes

## Sample Images

- `after_wash.jpg` - Colony plate after washing
- `arjcol2.jpg` - Sample colony image
- `BF_Handwash.jpg` - Bacterial colonies from handwash
- `Col.png` - Colony sample
- `Col2.jpg` - Colony sample (used in script)
- `assembled_grid_output_2.jpg` - Stitched microscope grid

## Image Processing Pipeline

1. **Preprocessing**: Convert to grayscale
2. **Thresholding**: Binary threshold at 127
3. **Morphological Opening**: Remove noise with 2x2 kernel
4. **Contour Detection**: Find external contours
5. **Filtering**: Apply area and shape constraints
6. **Manual Correction**: User can add/remove detections

## Notes

This is a separate project from the main microscope stitcher. It focuses on colony counting rather than image stitching.
