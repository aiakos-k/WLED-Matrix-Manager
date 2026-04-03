"""Tests for image to pixel converter service"""

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from flask_module.services.image_to_pixel_converter import ImageToPixelConverter


class TestImageToPixelConverter:
    """Test image to pixel conversion"""

    @pytest.fixture
    def test_image_path(self):
        """Create a temporary test image"""
        # Create a 4x4 image with specific colors
        img_array = np.array(
            [
                [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0]],  # Red, Green, Blue, Yellow
                [
                    [255, 0, 255],
                    [0, 255, 255],
                    [128, 128, 128],
                    [0, 0, 0],
                ],  # Magenta, Cyan, Gray, Black
                [
                    [255, 255, 255],
                    [128, 0, 0],
                    [0, 128, 0],
                    [0, 0, 128],
                ],  # White, Dark red, Dark green, Dark blue
                [
                    [255, 128, 0],
                    [128, 255, 0],
                    [0, 128, 255],
                    [192, 192, 192],
                ],  # Orange, Yellow-green, Sky blue, Silver
            ],
            dtype=np.uint8,
        )

        # Create PIL image and save to temp file
        img = Image.fromarray(img_array, mode="RGB")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            img.save(temp_path, "PNG")

        yield temp_path

        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    def test_convert_image_basic(self, test_image_path):
        """Test basic image conversion without quantization"""
        result = ImageToPixelConverter.convert_image_to_pixels(
            test_image_path, width=4, height=4, colors=256
        )

        assert "pixels" in result
        assert "width" in result
        assert "height" in result
        assert result["width"] == 4
        assert result["height"] == 4
        assert len(result["pixels"]) == 16  # 4x4

        # Check first pixel structure
        first_pixel = result["pixels"][0]
        assert "index" in first_pixel
        assert "color" in first_pixel
        assert "x" in first_pixel
        assert "y" in first_pixel
        assert len(first_pixel["color"]) == 3  # RGB

        # Check pixel values are in valid range
        for pixel in result["pixels"]:
            assert 0 <= pixel["color"][0] <= 255
            assert 0 <= pixel["color"][1] <= 255
            assert 0 <= pixel["color"][2] <= 255

    def test_convert_image_resize_down(self, test_image_path):
        """Test image conversion with downscaling"""
        result = ImageToPixelConverter.convert_image_to_pixels(test_image_path, width=2, height=2)

        assert result["width"] == 2
        assert result["height"] == 2
        assert len(result["pixels"]) == 4  # 2x2

    def test_convert_image_resize_up(self, test_image_path):
        """Test image conversion with upscaling"""
        result = ImageToPixelConverter.convert_image_to_pixels(test_image_path, width=8, height=8)

        assert result["width"] == 8
        assert result["height"] == 8
        assert len(result["pixels"]) == 64  # 8x8

    def test_convert_image_with_quantization(self, test_image_path):
        """Test image conversion with color quantization"""
        result = ImageToPixelConverter.convert_image_to_pixels(
            test_image_path, width=4, height=4, colors=4
        )

        assert "pixels" in result
        assert len(result["pixels"]) == 16

        # With only 4 colors, we should see repeated color values
        unique_colors = set()
        for pixel in result["pixels"]:
            color_tuple = tuple(pixel["color"])
            unique_colors.add(color_tuple)

        # Should have approximately 4 unique colors (K-means might produce slightly different results)
        assert len(unique_colors) <= 6  # Allow some tolerance

    def test_convert_image_pixel_ordering(self, test_image_path):
        """Test that pixels are ordered correctly (row by row, left to right)"""
        result = ImageToPixelConverter.convert_image_to_pixels(test_image_path, width=4, height=4)

        # Check indices are sequential
        for i, pixel in enumerate(result["pixels"]):
            assert pixel["index"] == i

        # Check x, y coordinates
        expected_coords = [(x, y) for y in range(4) for x in range(4)]  # Row-major order

        for i, (expected_x, expected_y) in enumerate(expected_coords):
            assert result["pixels"][i]["x"] == expected_x
            assert result["pixels"][i]["y"] == expected_y

    def test_convert_image_nonexistent_file(self):
        """Test error handling for non-existent image file"""
        with pytest.raises(ValueError, match="Failed to convert image"):
            ImageToPixelConverter.convert_image_to_pixels(
                "/nonexistent/path.png", width=16, height=16
            )

    def test_create_solid_color_frame(self):
        """Test creation of solid color frame"""
        color = (255, 128, 64)
        result = ImageToPixelConverter.create_solid_color_frame(width=8, height=8, color=color)

        assert result["width"] == 8
        assert result["height"] == 8
        assert len(result["pixels"]) == 64

        # All pixels should have the same color
        for pixel in result["pixels"]:
            assert pixel["color"] == list(color)

        # Check indices and coordinates
        for i, pixel in enumerate(result["pixels"]):
            assert pixel["index"] == i
            expected_x = i % 8
            expected_y = i // 8
            assert pixel["x"] == expected_x
            assert pixel["y"] == expected_y

    def test_create_solid_color_frame_small(self):
        """Test solid color frame with small dimensions"""
        color = (0, 255, 0)
        result = ImageToPixelConverter.create_solid_color_frame(width=2, height=2, color=color)

        assert len(result["pixels"]) == 4
        for pixel in result["pixels"]:
            assert pixel["color"] == list(color)

    def test_generate_wled_command_basic(self):
        """Test WLED command generation"""
        pixel_data = {
            "pixels": [
                {"index": 0, "color": [255, 0, 0], "x": 0, "y": 0},
                {"index": 1, "color": [0, 255, 0], "x": 1, "y": 0},
                {"index": 2, "color": [0, 0, 255], "x": 0, "y": 1},
            ],
            "width": 2,
            "height": 2,
        }

        result = ImageToPixelConverter.generate_wled_command(pixel_data, brightness=128, on=True)

        assert "on" in result
        assert "bri" in result
        assert "seg" in result
        assert result["on"] is True
        assert result["bri"] == 128
        assert "id" in result["seg"]
        assert "i" in result["seg"]
        assert result["seg"]["id"] == 0

        # Check WLED index format: [True, brightness, index, [R, G, B], ...]
        wled_index = result["seg"]["i"]
        assert wled_index[0] is True  # on flag
        assert wled_index[1] == 128  # brightness

        # Check pixel data
        assert wled_index[2] == 0  # First pixel index
        assert wled_index[3] == [255, 0, 0]  # First pixel color
        assert wled_index[4] == 1  # Second pixel index
        assert wled_index[5] == [0, 255, 0]  # Second pixel color

    def test_generate_wled_command_off(self):
        """Test WLED command generation with LEDs off"""
        pixel_data = {
            "pixels": [{"index": 0, "color": [255, 0, 0], "x": 0, "y": 0}],
            "width": 1,
            "height": 1,
        }

        result = ImageToPixelConverter.generate_wled_command(pixel_data, brightness=0, on=False)

        assert result["on"] is False
        assert result["bri"] == 0
        assert result["seg"]["i"][0] is False  # off flag

    def test_generate_wled_command_different_brightness(self):
        """Test WLED command with different brightness levels"""
        pixel_data = {
            "pixels": [{"index": 0, "color": [255, 255, 255], "x": 0, "y": 0}],
            "width": 1,
            "height": 1,
        }

        for brightness in [0, 64, 128, 192, 255]:
            result = ImageToPixelConverter.generate_wled_command(
                pixel_data, brightness=brightness, on=True
            )

            assert result["bri"] == brightness
            assert result["seg"]["i"][1] == brightness
