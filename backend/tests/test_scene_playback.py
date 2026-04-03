"""Tests for scene playback service"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from flask_module.services.scene_playback import (
    ScenePlayback,
    start_scene_playback,
    stop_scene_playback,
    upscale_pixel_data,
)


class TestUpscalePixelData:
    """Test upscale_pixel_data function"""

    def test_no_scaling_needed(self):
        """Test when source and target dimensions match"""
        pixel_data = {
            "pixels": [{"index": 0, "color": [255, 0, 0]}],
            "width": 16,
            "height": 16,
        }

        result = upscale_pixel_data(pixel_data, 16, 16)

        assert result == pixel_data

    def test_integer_upscaling_2x(self):
        """Test 2x integer upscaling (16x16 -> 32x32)"""
        pixel_data = {
            "pixels": [{"index": 0, "color": [255, 0, 0]}],  # Top-left pixel
            "width": 16,
            "height": 16,
        }

        result = upscale_pixel_data(pixel_data, 32, 32, mode="integer")

        assert result["width"] == 32
        assert result["height"] == 32
        # Creates full 32x32 matrix (all pixels, including black)
        assert len(result["pixels"]) == 1024  # 32*32
        # First 4 pixels should be the 2x2 block of our single red pixel
        red_pixels = [p for p in result["pixels"] if p["color"] == [255, 0, 0]]
        assert len(red_pixels) == 4  # 2x2 block

    def test_integer_upscaling_4x(self):
        """Test 4x integer upscaling (16x16 -> 64x64)"""
        pixel_data = {
            "pixels": [{"index": 0, "color": [0, 255, 0]}],
            "width": 16,
            "height": 16,
        }

        result = upscale_pixel_data(pixel_data, 64, 64, mode="integer")

        assert result["width"] == 64
        assert result["height"] == 64
        # Creates full 64x64 matrix (all pixels, including black)
        assert len(result["pixels"]) == 4096  # 64*64
        # First pixel block should be green
        green_pixels = [p for p in result["pixels"] if p["color"] == [0, 255, 0]]
        assert len(green_pixels) == 16  # 4x4 block

    def test_stretch_upscaling(self):
        """Test stretch mode for non-uniform scaling"""
        pixel_data = {
            "pixels": [
                {"index": 0, "color": [255, 0, 0]},
                {"index": 1, "color": [0, 255, 0]},
            ],
            "width": 2,
            "height": 1,
        }

        result = upscale_pixel_data(pixel_data, 4, 2, mode="stretch")

        assert result["width"] == 4
        assert result["height"] == 2
        # Should map proportionally
        assert len(result["pixels"]) > 0

    def test_auto_mode_chooses_integer(self):
        """Test auto mode chooses integer for perfect scale"""
        pixel_data = {
            "pixels": [{"index": 0, "color": [255, 0, 0]}],
            "width": 16,
            "height": 16,
        }

        result = upscale_pixel_data(pixel_data, 32, 32, mode="auto")

        # Should behave like integer mode
        assert result["width"] == 32
        assert result["height"] == 32
        assert len(result["pixels"]) == 1024  # Full 32x32 matrix

    def test_auto_mode_chooses_stretch(self):
        """Test auto mode chooses stretch for non-integer scale"""
        pixel_data = {
            "pixels": [{"index": 0, "color": [255, 0, 0]}],
            "width": 16,
            "height": 16,
        }

        result = upscale_pixel_data(pixel_data, 32, 128, mode="auto")

        # Should use stretch mode
        assert result["width"] == 32
        assert result["height"] == 128
        assert len(result["pixels"]) > 0

    def test_center_mode(self):
        """Test center mode places source in center of target"""
        pixel_data = {
            "pixels": [{"index": 0, "color": [255, 0, 0]}],
            "width": 8,
            "height": 8,
        }

        result = upscale_pixel_data(pixel_data, 16, 16, mode="center")

        assert result["width"] == 16
        assert result["height"] == 16
        # Creates full 8x8 pixels centered in 16x16
        assert len(result["pixels"]) == 64  # 8x8 source pixels
        # Find the red pixel
        red_pixels = [p for p in result["pixels"] if p["color"] == [255, 0, 0]]
        assert len(red_pixels) == 1


class TestScenePlayback:
    """Test ScenePlayback class"""

    def test_scene_playback_initialization(self):
        """Test ScenePlayback initialization"""
        devices_info = [
            {
                "ip_address": "192.168.1.100",
                "communication_protocol": "json_api",
                "matrix_width": 16,
                "matrix_height": 16,
            }
        ]
        frames_data = [
            {
                "frame_index": 0,
                "pixel_data": {"pixels": [], "width": 16, "height": 16},
                "duration": 5.0,
                "brightness": 128,
            }
        ]

        playback = ScenePlayback(1, devices_info, frames_data, "once")

        assert playback.scene_id == 1
        assert playback.devices_info == devices_info
        assert playback.frames == frames_data
        assert playback.loop_mode == "once"
        assert playback.is_running is False

    def test_start_scene_playback(self):
        """Test starting scene playback"""
        devices_info = [{"ip_address": "192.168.1.100", "communication_protocol": "json_api"}]
        frames_data = [
            {
                "frame_index": 0,
                "pixel_data": {"pixels": [], "width": 16, "height": 16},
                "duration": 0.1,  # Short duration for test
                "brightness": 128,
            }
        ]

        start_scene_playback(999, devices_info, frames_data, "once")

        # Should create playback instance
        from flask_module.services.scene_playback import active_playbacks

        assert 999 in active_playbacks

        # Stop it
        stop_scene_playback(999)
        assert 999 not in active_playbacks

    def test_stop_nonexistent_scene(self):
        """Test stopping scene that doesn't exist"""
        # Should not raise error
        stop_scene_playback(99999)

    @patch("flask_module.services.device_controller.DeviceController")
    def test_playback_with_multiple_frames(self, mock_controller):
        """Test playback with multiple frames"""
        mock_controller.send_udp_dnrgb.return_value = True
        mock_controller.generate_wled_command.return_value = {}
        mock_controller.send_command_to_device.return_value = True

        devices_info = [
            {
                "ip_address": "192.168.1.100",
                "communication_protocol": "json_api",
                "matrix_width": 16,
                "matrix_height": 16,
            }
        ]
        frames_data = [
            {
                "frame_index": 0,
                "pixel_data": {"pixels": [], "width": 16, "height": 16},
                "duration": 0.01,
                "brightness": 128,
                "color_r": 10,
                "color_g": 10,
                "color_b": 10,
            },
            {
                "frame_index": 1,
                "pixel_data": {"pixels": [], "width": 16, "height": 16},
                "duration": 0.01,
                "brightness": 255,
                "color_r": 100,
                "color_g": 100,
                "color_b": 100,
            },
        ]

        playback = ScenePlayback(100, devices_info, frames_data, "once")
        playback.start()

        # Wait a bit for thread to process
        import time

        time.sleep(0.1)

        playback.stop()

        # Verify controller was called
        assert mock_controller.generate_wled_command.called or mock_controller.send_udp_dnrgb.called
