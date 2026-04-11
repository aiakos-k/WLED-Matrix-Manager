"""
Image to LED pixel data converter.
Resizes images to matrix dimensions with optional color quantization.
"""

from typing import Dict

import numpy as np
from PIL import Image


class ImageToPixelConverter:
    @staticmethod
    def convert(image_path: str, width: int, height: int, colors: int = 256) -> Dict:
        """Convert an image file to LED pixel data."""
        img = Image.open(image_path).convert("RGB")
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        arr = np.array(img)

        if colors < 256:
            arr = ImageToPixelConverter._quantize(arr, colors)

        pixels = []
        idx = 0
        for y in range(height):
            for x in range(width):
                r, g, b = arr[y, x]
                pixels.append({"index": idx, "color": [int(r), int(g), int(b)]})
                idx += 1

        return {"pixels": pixels, "width": width, "height": height}

    @staticmethod
    def convert_bytes(
        image_bytes: bytes, width: int, height: int, colors: int = 256
    ) -> Dict:
        """Convert image bytes to LED pixel data."""
        from io import BytesIO

        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        arr = np.array(img)

        if colors < 256:
            arr = ImageToPixelConverter._quantize(arr, colors)

        pixels = []
        idx = 0
        for y in range(height):
            for x in range(width):
                r, g, b = arr[y, x]
                pixels.append({"index": idx, "color": [int(r), int(g), int(b)]})
                idx += 1

        return {"pixels": pixels, "width": width, "height": height}

    @staticmethod
    def _quantize(arr: np.ndarray, num_colors: int) -> np.ndarray:
        """K-means color quantization."""
        try:
            from sklearn.cluster import KMeans

            pixels = arr.reshape(-1, 3)
            kmeans = KMeans(n_clusters=num_colors, n_init=10, random_state=42)
            labels = kmeans.fit_predict(pixels)
            return kmeans.cluster_centers_.astype(np.uint8)[labels].reshape(arr.shape)
        except ImportError:
            # sklearn not available, use PIL quantize
            img = Image.fromarray(arr)
            img = img.quantize(colors=num_colors).convert("RGB")
            return np.array(img)
