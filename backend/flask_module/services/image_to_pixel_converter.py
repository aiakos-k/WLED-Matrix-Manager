"""
Image to LED Pixel conversion service

Handles converting images to LED matrix pixel data with color quantization.
"""

from typing import Dict, Tuple

import numpy as np
from PIL import Image


class ImageToPixelConverter:
    """Convert images to LED matrix pixel data"""

    @staticmethod
    def convert_image_to_pixels(
        image_path: str,
        width: int,
        height: int,
        colors: int = 256,
    ) -> Dict:
        """
        Convert an image to LED pixel data.

        Args:
            image_path: Path to the image file
            width: Target matrix width (e.g., 16)
            height: Target matrix height (e.g., 16)
            colors: Number of colors to quantize to (default 256)

        Returns:
            Dictionary with pixel data in WLED format:
            {
                "pixels": [
                    {"index": 0, "color": [R, G, B]},
                    ...
                ]
            }
        """
        try:
            # Open and convert image to RGB
            img = Image.open(image_path).convert("RGB")

            # Resize image to match matrix dimensions
            img = img.resize((width, height), Image.Resampling.LANCZOS)

            # Convert to numpy array
            img_array = np.array(img)

            # Quantize colors if needed
            if colors < 256:
                img_array = ImageToPixelConverter._quantize_colors(img_array, colors)

            # Generate pixel data
            pixels = []
            pixel_index = 0

            for y in range(height):
                for x in range(width):
                    r, g, b = img_array[y, x]
                    pixels.append(
                        {
                            "index": pixel_index,
                            "color": [int(r), int(g), int(b)],
                            "x": x,
                            "y": y,
                        }
                    )
                    pixel_index += 1

            return {"pixels": pixels, "width": width, "height": height}

        except Exception as e:
            raise ValueError(f"Failed to convert image: {str(e)}")

    @staticmethod
    def _quantize_colors(img_array: np.ndarray, num_colors: int) -> np.ndarray:
        """
        Quantize image colors to a specific number of colors.

        Args:
            img_array: NumPy array of the image
            num_colors: Target number of colors

        Returns:
            Quantized image array
        """
        from sklearn.cluster import KMeans

        # Reshape to (pixels, 3)
        pixels = img_array.reshape(-1, 3)

        # Perform K-means clustering
        kmeans = KMeans(n_clusters=num_colors, n_init=10, random_state=42)
        labels = kmeans.fit_predict(pixels)

        # Get cluster centers (the new colors)
        quantized_pixels = kmeans.cluster_centers_.astype(np.uint8)[labels]

        # Reshape back to original image dimensions
        return quantized_pixels.reshape(img_array.shape)

    @staticmethod
    def create_solid_color_frame(width: int, height: int, color: Tuple[int, int, int]) -> Dict:
        """
        Create a solid color frame for all pixels.

        Args:
            width: Matrix width
            height: Matrix height
            color: RGB color tuple (R, G, B)

        Returns:
            Pixel data dictionary
        """
        pixels = []
        pixel_index = 0

        for y in range(height):
            for x in range(width):
                pixels.append({"index": pixel_index, "color": list(color), "x": x, "y": y})
                pixel_index += 1

        return {"pixels": pixels, "width": width, "height": height}

    @staticmethod
    def generate_wled_command(pixel_data: Dict, brightness: int = 128, on: bool = True) -> Dict:
        """
        Generate a WLED API command from pixel data.

        Args:
            pixel_data: Pixel data dictionary
            brightness: LED brightness (0-255)
            on: Whether LEDs should be on

        Returns:
            WLED JSON command dictionary
        """
        # Build the index array for WLED
        # WLED format: [index, [R, G, B], index, [R, G, B], ...]
        wled_index = [True] if on else [False]

        if brightness is not None:
            wled_index.append(brightness)

        # Add pixel data in WLED format
        for pixel in pixel_data["pixels"]:
            wled_index.append(pixel["index"])
            wled_index.append(pixel["color"])

        return {
            "on": on,
            "bri": brightness,
            "seg": {
                "id": 0,
                "i": wled_index,
            },
        }
