import cv2
import numpy as np
import re
from pathlib import Path

class ManualGridAssembler:
    def __init__(self, tile_width=220, tile_height=250):
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.images = []

    def load_images_from_folder(self, folder_path, pattern="*.png"):
        """
        Load numerically labeled images from folder
        
        Args:
            folder_path (str): Path to folder containing images
            pattern (str): File pattern (e.g., "*.jpg", "*.png", "img_*.jpg")
        
        Returns:
            list: Loaded images in numerical order
        """
        folder_path = Path(folder_path)
        if not folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        image_files = list(folder_path.glob(pattern))
        if not image_files:
            raise FileNotFoundError(f"No images found with pattern: {pattern}")
        
        def numerical_sort_key(filename):
            numbers = re.findall(r'\d+', filename.stem)
            return [int(num) for num in numbers] if numbers else [0]
        
        image_files.sort(key=numerical_sort_key)

        print(f"Found {len(image_files)} images:")
        for i, file in enumerate(image_files[:5]):
            print(f"  {i+1}: {file.name}")
        if len(image_files) > 5:
            print(f"  ... and {len(image_files) - 5} more")
        
        self.images = []
        for img_file in image_files:
            img = cv2.imread(str(img_file))
            if img is not None:
                img = cv2.resize(img, (self.tile_width, self.tile_height))
                self.images.append(img)
                print(f"Loaded: {img_file.name} - Size: {img.shape[:2]}")
            else:
                print(f"Failed to load: {img_file.name}")
        
        print(f"Successfully loaded {len(self.images)} images")
        return self.images
    
    def alpha_blend_overlap(self, img1, img2, axis, overlap):
        """
        Alpha blends the overlapping region between img1 and img2 along the given axis.
        
        Args:
            img1, img2: Images to blend
            axis: 0 for vertical (row-wise), 1 for horizontal (column-wise)
            overlap: Number of pixels to blend
        
        Returns:
            np.ndarray: The alpha-blended image combining img1 and img2
        """
        if axis == 1:  # Horizontal stitch
            non_overlap_1 = img1[:, :-overlap]
            overlap_1 = img1[:, -overlap:]
            overlap_2 = img2[:, :overlap]
            non_overlap_2 = img2[:, overlap:]
        elif axis == 0:  # Vertical stitch
            non_overlap_1 = img1[:-overlap, :]
            overlap_1 = img1[-overlap:, :]
            overlap_2 = img2[:overlap, :]
            non_overlap_2 = img2[overlap:, :]
        else:
            raise ValueError("Axis must be 0 (vertical) or 1 (horizontal)")

        # Blend overlap
        blended_overlap = np.zeros_like(overlap_1)
        for i in range(overlap):
            alpha = i / overlap
            if axis == 1:
                blended_overlap[:, i] = (
                    (1 - alpha) * overlap_1[:, i] + alpha * overlap_2[:, i]
                ).astype(np.uint8)
            else:
                blended_overlap[i, :] = (
                    (1 - alpha) * overlap_1[i, :] + alpha * overlap_2[i, :]
                ).astype(np.uint8)

        if axis == 1:
            return np.hstack([non_overlap_1, blended_overlap, non_overlap_2])
        else:
            return np.vstack([non_overlap_1, blended_overlap, non_overlap_2])

    def assemble_manual_grid_with_alpha_blend(self, layout_indices, overlap_x=50, overlap_y=50):
        """
        Assembles and stitches images using alpha blending in a custom grid layout.

        Args:
            layout_indices (list of list of int): Grid layout of image indices (0-based)
            overlap_x (int): Horizontal overlap in pixels
            overlap_y (int): Vertical overlap in pixels

        Returns:
            np.ndarray: Final alpha-blended stitched image
        """
        if not self.images:
            raise RuntimeError("No images loaded.")

        tile_w, tile_h = self.tile_width, self.tile_height
        grid_rows = len(layout_indices)
        
        stitched_rows = []

        for row_num, row_indices in enumerate(layout_indices):
            # --- Horizontal stitch for each row ---
            stitched_row = None
            for col_idx, img_idx in enumerate(row_indices):
                img = self.images[img_idx]
                img = cv2.resize(img, (tile_w, tile_h))  # Ensure size consistency

                if stitched_row is None:
                    stitched_row = img
                else:
                    stitched_row = self.alpha_blend_overlap(stitched_row, img, axis=1, overlap=overlap_x)
            
            stitched_rows.append(stitched_row)

        # --- Vertical stitch for all rows ---
        final_image = stitched_rows[0]
        for row_img in stitched_rows[1:]:
            final_image = self.alpha_blend_overlap(final_image, row_img, axis=0, overlap=overlap_y)

        return final_image

    
    



    
if __name__ == "__main__":
    assembler = ManualGridAssembler(tile_width=220, tile_height=250)

    folder = "captured_images"  # Update this!
    assembler.load_images_from_folder(folder, pattern="*.png")


    size = input("Enter Dimensions in WxH format eg. 4x3: ")
    width, height = int(size[:1]), int(size[2:]) 
    layout = []
    rows = height
    col = width

    total = [x for x in range(rows * col)]

    for i in range(rows):
        layout.append([])
        lane = total[(i*col):(i*col + col)] 
        if i % 2 == 1:
            lane.reverse()
        for j in lane:
            layout[i].append(j)

    result = assembler.assemble_manual_grid_with_alpha_blend(layout, overlap_x=100, overlap_y=50)
    cv2.imshow("Manual Grid Assembled", result)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    cv2.imwrite("assembled_grid_output_2.jpg", result)

