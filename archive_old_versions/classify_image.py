"""Simple CLI to classify a single image with a WBC model.

Usage:
    python scripts/classify_image.py --model path/to/model.keras --image path/to/image.png
"""
import argparse
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from micro_camera_scope.model_utils import load_wbc_model, predict_image


def main():
    p = argparse.ArgumentParser(description="Classify an image using WBC model")
    p.add_argument('--model', '-m', required=True, help='Path to .keras model file')
    p.add_argument('--image_folder', '-i', required=True, help='Path to images to classify')
    p.add_argument('--top', '-k', type=int, default=3, help='Top-k results to show')
    args = p.parse_args()

    try:
        model, classes = load_wbc_model(args.model)
    except Exception as e:
        print(f"Error loading model: {e}")
        sys.exit(2)
    for img_name in os.listdir(args.image_folder):
        img_path = os.path.join(args.image_folder, img_name)
        try:
            results = predict_image(model, classes, img_path, top_k=args.top)
        except Exception as e:
            print(f"Error during prediction: {e}")
            sys.exit(3)
        
        class_dict = {0: 'Eosinophil', 1: 'lymphocyte', 2: 'Monocyte', 3: 'Neutrophil', 4: 'Basophil'}
        print(f"Predictions for {img_path}:")
        for label, prob in results:
            print(f"  {class_dict[int(label)]}: {prob:.4f}")


if __name__ == '__main__':
    main()
