import os
import json
import numpy as np
import cv2
import tensorflow as tf
from tensorflow.keras.models import load_model



def load_wbc_model(model_path):
    """Load trained WBC classification model and class mapping.

    Returns tuple (model, classes) or raises Exception on failure.
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    model = load_model(model_path)

    model_dir = os.path.dirname(model_path)
    class_mapping_path = os.path.join(model_dir, 'class_mapping.json')
    if os.path.exists(class_mapping_path):
        with open(class_mapping_path, 'r') as f:
            class_info = json.load(f)
            classes = class_info.get('classes')
    else:
        classes = None

    return model, classes


def predict_image(model, classes, image_path, top_k=3):

    
    """Run classification on a single image and return top_k predictions.

    Returns a list of (class_or_index, probability) tuples ordered by probability desc.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    # Read image (BGR)
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Unable to read image: {image_path}")

    # Convert to RGB
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Determine expected input shape from model
    # Typical shape: (None, H, W, C)
    input_shape = None
    try:
        input_shape = model.input_shape
    except Exception:
        # Fallback: try attribute
        input_shape = getattr(model, 'inputs', [None])[0].shape

    if input_shape is None:
        raise RuntimeError("Unable to determine model input shape")

    # Extract height, width, channels
    _, h, w, c = input_shape
    h = int(h) if h is not None else img.shape[0]
    w = int(w) if w is not None else img.shape[1]
    c = int(c) if c is not None else img.shape[2]

    # Resize
    resized = cv2.resize(img, (w, h))

    if c == 1:
        resized = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
        resized = resized[..., np.newaxis]

    # Scale to [0,1]
    array = resized.astype(np.float32) / 255.0
    batch = np.expand_dims(array, axis=0)

    preds = model.predict(batch)
    preds = np.asarray(preds).squeeze()

    # If preds are not probabilities, apply softmax
    if preds.ndim == 0:
        preds = np.array([preds])

    probs = preds
    if probs.sum() <= 0 or not np.isclose(probs.sum(), 1.0):
        # numerically stable softmax
        ex = np.exp(probs - np.max(probs))
        probs = ex / ex.sum()

    # Get top_k indices
    idxs = np.argsort(probs)[::-1][:top_k]
    results = []
    for i in idxs:
        label = classes[i] if classes and i < len(classes) else i
        results.append((label, float(probs[i])))

    return results




