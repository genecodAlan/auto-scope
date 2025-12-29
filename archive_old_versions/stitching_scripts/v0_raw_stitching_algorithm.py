import cv2
import numpy as np 


def stitch_with_opencv(self, images):
    """Fast OpenCV stitching for grid images"""
    stitcher = cv2.Stitcher.create(cv2.Stitcher_PANORAMA)
    status, stitched = stitcher.stitch(images)
    return stitched if status == cv2.Stitcher_OK else None


def blend_regions(canvas_region, new_region):
    alpha = 0.5
    overlap_mask = (np.sum(canvas_region, axis=2) > 0) & (np.sum(new_region, axis=2) > 0)
    blended = canvas_region.copy()
    blended[overlap_mask] = (alpha * canvas_region[overlap_mask] + (1 - alpha) * new_region[overlap_mask]).astype(np.uint8)

    only_new_mask = (np.sum(canvas_region, axis=2) == 0) & (np.sum(new_region, axis=2) > 0)
    blended[only_new_mask] = new_region[only_new_mask]

    return blended

def main():
    cap = cv2.VideoCapture(1)
    cap.set(cv2.CAP_PROP_FPS,30)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

    orb = cv2.ORB.create(nfeatures=1000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    crop_top, crop_bottom = 300, 550  
    crop_left, crop_right = 180, 400  

    # Large canvas size to accommodate stitched images (adjust if needed)
    canvas_height, canvas_width = 1500, 1500
    canvas = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)

    pos_x = (canvas_width - (crop_right - crop_left)) // 2
    pos_y = ((canvas_height) // 2) - (crop_bottom)

    first_frame_init = False

    while True:
        ret, frame = cap.read()
        if not ret:
            print('Failed to grab frame')
            break
        frame_cropped = frame[crop_top:crop_bottom, crop_left:crop_right]
        height, width = frame_cropped.shape[:2]

        gray = cv2.cvtColor(frame_cropped, cv2.COLOR_BGR2GRAY)

        kp_curr, des_curr = orb.detectAndCompute(gray, None)

        if not first_frame_init:
            # For the first frame, just put it on canvas center and initialize tracking vars
            canvas[pos_y:pos_y+height, pos_x:pos_x+width] = frame_cropped
            kp_last = kp_curr
            des_last = des_curr
            pos_last = (pos_x, pos_y)
            first_frame_init = True
        else:


            matches = bf.match(des_curr, des_last)
            matches = sorted(matches, key= lambda x:x.distance)



            if len(matches) < 10:
                # Not enough matches - skip updating position, just show
                cv2.imshow("Stitched Canvas", canvas)
                if cv2.waitKey(1) == 27:
                    break
                continue


            offsets = []
            for m in matches:
                pt_curr = kp_curr[m.queryIdx].pt
                pt_last = kp_last[m.trainIdx].pt
                offsets.append((pt_last[0] - pt_curr[0], pt_last[1] - pt_curr[1]))
            dx = int(round(np.median([o[0] for o in offsets])))
            dy = int(round(np.median([o[1] for o in offsets])))

            pos_x_new = pos_last[0] + dx
            pos_y_new = pos_last[1] + dy

            pos_x_new = max(0, min(pos_x_new, canvas_width - width))
            pos_y_new = max(0, min(pos_y_new, canvas_height - height))

            # Extract canvas region where we'll place the new frame
            canvas_region = canvas[pos_y_new:pos_y_new+height, pos_x_new:pos_x_new+width]
            # Blend current frame into the canvas region
            blended_region = blend_regions(canvas_region, frame_cropped)
            canvas[pos_y_new:pos_y_new+height, pos_x_new:pos_x_new+width] = blended_region

            # Update tracking variables for next iteration
            kp_last = kp_curr
            des_last = des_curr
            pos_last = (pos_x_new, pos_y_new)

        # Display the stitched mosaic canvas
        cv2.imshow("Stitched Canvas", canvas)
        cv2.imshow("Non_cropped", frame)

        if cv2.waitKey(1) == 27:  # ESC key
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()


