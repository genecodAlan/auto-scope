"""Unit tests for model utilities."""
import json
import os
import tempfile
import numpy as np
import cv2

from micro_camera_scope.model_utils import load_wbc_model, predict_image


class FakeModel:
    def __init__(self, n_classes=2, input_shape=(None, 16, 16, 3)):
        self._input_shape = input_shape
        self._n = n_classes

    @property
    def input_shape(self):
        return self._input_shape

    def predict(self, batch):
        # Return uniform probabilities biased to class 1
        out = np.zeros((1, self._n), dtype=np.float32)
        out[0, 1 % self._n] = 1.0
        return out


def test_load_wbc_model_not_found_raises():
    try:
        load_wbc_model('nonexistent_model.keras')
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_predict_image_with_fake_model(tmp_path):
    # Create fake image
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    cv2.putText(img, 'A', (2, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
    img_path = str(tmp_path / 't.png')
    cv2.imwrite(img_path, img)

    # Create fake model and classes
    model = FakeModel(n_classes=3, input_shape=(None, 16, 16, 3))
    classes = ['class0', 'class1', 'class2']

    results = predict_image(model, classes, img_path, top_k=2)
    assert len(results) == 2
    assert results[0][0] in classes