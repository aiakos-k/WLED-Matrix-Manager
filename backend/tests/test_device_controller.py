"""Tests for device controller service"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from flask_module.services.device_controller import DeviceController


class TestDeviceController:
    """Test DeviceController service"""

    def test_generate_wled_command_basic(self):
        """Test basic WLED command generation"""
        pixel_data = {
            "pixels": [
                {"index": 0, "color": [255, 0, 0]},
                {"index": 1, "color": [0, 255, 0]},
                {"index": 2, "color": [0, 0, 255]},
            ],
            "width": 16,
            "height": 16,
        }

        command = DeviceController.generate_wled_command(
            pixel_data, brightness=128, on=True, color_r=10, color_g=10, color_b=10
        )

        assert command["on"] is True
        assert command["bri"] == 128
        assert "seg" in command
        assert "i" in command["seg"]
        # Check that pixels are included
        assert len(command["seg"]["i"]) > 0

    def test_generate_wled_command_with_color_multipliers(self):
        """Test WLED command with color multipliers"""
        pixel_data = {
            "pixels": [{"index": 0, "color": [100, 100, 100]}],
            "width": 16,
            "height": 16,
        }

        command = DeviceController.generate_wled_command(
            pixel_data, brightness=255, color_r=50, color_g=50, color_b=50
        )

        # Color should be reduced by 50%
        pixel_color = command["seg"]["i"][1]  # [idx, [R, G, B]]
        assert pixel_color[0] == 50  # R
        assert pixel_color[1] == 50  # G
        assert pixel_color[2] == 50  # B

    def test_generate_wled_command_empty_pixels(self):
        """Test WLED command with no pixels"""
        pixel_data = {"pixels": [], "width": 16, "height": 16}

        command = DeviceController.generate_wled_command(pixel_data, brightness=255)

        assert command["on"] is True
        assert command["bri"] == 255
        # Empty pixels still get a black pixel entry
        assert len(command["seg"]["i"]) == 2  # [0, [0,0,0]]

    def test_generate_wled_command_range_compression(self):
        """Test range compression for consecutive pixels"""
        pixel_data = {
            "pixels": [
                {"index": 0, "color": [255, 0, 0]},
                {"index": 1, "color": [255, 0, 0]},
                {"index": 2, "color": [255, 0, 0]},
            ],
            "width": 16,
            "height": 16,
        }

        command = DeviceController.generate_wled_command(pixel_data, brightness=255)

        # Should use range format: [start_idx, end_idx, [R, G, B]]
        pixel_data_result = command["seg"]["i"]
        # First element should be start index, second should be end index (exclusive)
        assert pixel_data_result[0] == 0
        assert pixel_data_result[1] == 3  # End is exclusive, so 2+1=3

    @patch("flask_module.services.device_controller.socket.socket")
    def test_send_udp_dnrgb_basic(self, mock_socket):
        """Test basic UDP DNRGB sending"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock

        pixel_data = {
            "pixels": [{"index": 0, "color": [255, 0, 0]}],
            "width": 16,
            "height": 16,
        }

        result = DeviceController.send_udp_dnrgb(
            "192.168.1.100",
            pixel_data,
            brightness=128,
            color_r=10,
            color_g=10,
            color_b=10,
        )

        assert result is True
        # Verify socket was created and data sent
        mock_socket.assert_called_once()
        assert mock_sock.sendto.called

    @patch("flask_module.services.device_controller.socket.socket")
    def test_send_udp_dnrgb_multi_packet(self, mock_socket):
        """Test UDP DNRGB with multiple packets (>458 LEDs)"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock

        # Create 500 pixels (needs 2 packets)
        pixels = [{"index": i, "color": [255, 0, 0]} for i in range(500)]
        pixel_data = {"pixels": pixels, "width": 32, "height": 32}

        result = DeviceController.send_udp_dnrgb("192.168.1.100", pixel_data)

        assert result is True
        # Should send 2 packets (458 + 42 LEDs)
        assert mock_sock.sendto.call_count >= 2

    @patch("flask_module.services.device_controller.requests.post")
    def test_send_command_to_device_success(self, mock_post):
        """Test successful HTTP command to device"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_post.return_value = mock_response

        command = {"on": True, "bri": 128}
        result = DeviceController.send_command_to_device("192.168.1.100", command)

        assert result is True
        mock_post.assert_called_once()

    @patch("flask_module.services.device_controller.requests.post")
    def test_send_command_to_device_failure(self, mock_post):
        """Test failed HTTP command to device"""
        import requests

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("HTTP Error")
        mock_post.return_value = mock_response

        command = {"on": True, "bri": 128}
        result = DeviceController.send_command_to_device("192.168.1.100", command)

        assert result is False

    @patch("flask_module.services.device_controller.requests.post")
    def test_turn_off_device(self, mock_post):
        """Test turning off device"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = DeviceController.turn_off("192.168.1.100")

        assert result is True
        # Verify the command sent
        call_args = mock_post.call_args
        assert call_args[1]["json"]["on"] is False

    @patch("flask_module.services.device_controller.requests.get")
    def test_check_device_health_success(self, mock_get):
        """Test device health check success"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"state": {"on": True}}
        mock_get.return_value = mock_response

        result = DeviceController.check_device_health("192.168.1.100")

        assert result is True

    @patch("flask_module.services.device_controller.requests.get")
    def test_check_device_health_failure(self, mock_get):
        """Test device health check failure"""
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("Connection error")

        result = DeviceController.check_device_health("192.168.1.100")

        assert result is False
