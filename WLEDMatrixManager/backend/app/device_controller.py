"""
Device control service for communicating with WLED LED matrix devices.
Supports HTTP JSON API and UDP DNRGB protocols.
"""

import logging
import socket
import time
from typing import Dict

import aiohttp

logger = logging.getLogger(__name__)


class DeviceController:
    """Control LED matrix devices via HTTP JSON API and UDP DNRGB"""

    DEFAULT_API_ENDPOINT = "/json/state"
    DEFAULT_TIMEOUT = 5
    UDP_PORT = 21324
    UDP_TIMEOUT = 2

    PROTOCOL_JSON = "json_api"
    PROTOCOL_UDP_DNRGB = "udp_dnrgb"

    @staticmethod
    async def send_json_command(
        device_ip: str, command: Dict, timeout: int = DEFAULT_TIMEOUT
    ) -> bool:
        """Send a command via WLED HTTP JSON API."""
        try:
            url = f"http://{device_ip}{DeviceController.DEFAULT_API_ENDPOINT}"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=command, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    resp.raise_for_status()
                    logger.info(f"JSON API command sent to {device_ip}")
                    return True
        except Exception as e:
            logger.error(f"Failed to send JSON API command to {device_ip}: {e}")
            return False

    @staticmethod
    async def check_health(device_ip: str, timeout: int = 3) -> bool:
        """Check if a WLED device is reachable."""
        try:
            url = f"http://{device_ip}/json/info"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    resp.raise_for_status()
                    return True
        except Exception:
            return False

    @staticmethod
    async def turn_off(device_ip: str) -> bool:
        """Turn off a device."""
        return await DeviceController.send_json_command(
            device_ip, {"on": False, "transition": 0}
        )

    @staticmethod
    def generate_wled_command(
        pixel_data: Dict,
        brightness: int = 128,
        on: bool = True,
        color_r: int = 100,
        color_g: int = 100,
        color_b: int = 100,
    ) -> Dict:
        """
        Generate a WLED JSON API command from pixel data.
        Uses indexed pixel format with range compression.

        Args:
            pixel_data: Dict with 'pixels', 'width', 'height'
            brightness: Brightness 0-255 (device-level via 'bri')
            color_r/g/b: Channel intensity 0-100
        """
        pixels = pixel_data.get("pixels", [])
        color_multipliers = [color_r / 100.0, color_g / 100.0, color_b / 100.0]

        led_data = []
        if pixels:
            sorted_pixels = sorted(pixels, key=lambda p: p.get("index", 0))
            i = 0
            while i < len(sorted_pixels):
                current = sorted_pixels[i]
                idx = current.get("index", 0)
                color = current.get("color", [0, 0, 0])
                adjusted = [int(color[c] * color_multipliers[c]) for c in range(3)]

                end_i = i
                while (
                    end_i + 1 < len(sorted_pixels)
                    and sorted_pixels[end_i + 1].get("index", 0)
                    == sorted_pixels[end_i].get("index", 0) + 1
                ):
                    next_color = sorted_pixels[end_i + 1].get("color", [0, 0, 0])
                    next_adjusted = [
                        int(next_color[c] * color_multipliers[c]) for c in range(3)
                    ]
                    if next_adjusted == adjusted:
                        end_i += 1
                    else:
                        break

                if end_i == i:
                    led_data.append(idx)
                    led_data.append(adjusted)
                else:
                    led_data.append(idx)
                    led_data.append(sorted_pixels[end_i].get("index", 0) + 1)
                    led_data.append(adjusted)
                i = end_i + 1
        else:
            led_data = [0, [0, 0, 0]]

        return {
            "on": on,
            "bri": brightness,
            "transition": 0,
            "seg": {"id": 0, "i": led_data},
        }

    @staticmethod
    def send_udp_dnrgb(
        device_ip: str,
        pixel_data: Dict,
        brightness: int = 128,
        timeout: int = UDP_TIMEOUT,
        frame_duration: float = None,
        color_r: int = 100,
        color_g: int = 100,
        color_b: int = 100,
    ) -> bool:
        """
        Send pixels via UDP DNRGB protocol.
        Supports large matrices (>256 LEDs) with chunked packets.
        """
        try:
            pixels = pixel_data.get("pixels", [])
            width = pixel_data.get("width", 16)
            height = pixel_data.get("height", 16)
            total_leds = width * height
            brightness_factor = brightness / 255.0
            color_multipliers = [color_r / 100.0, color_g / 100.0, color_b / 100.0]

            # Build pixel map
            pixel_by_idx = {}
            for pixel in pixels:
                idx = pixel.get("index", 0)
                color = pixel.get("color", [0, 0, 0])
                if 0 <= idx < total_leds:
                    perceived = int(
                        0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
                    )
                    if perceived < 50:
                        factor = brightness_factor
                    elif perceived < 150:
                        linear = brightness_factor
                        sqrt_based = brightness_factor * 0.5 + 0.5
                        t = (perceived - 50) / 100.0
                        factor = linear * (1 - t) + sqrt_based * t
                    else:
                        factor = min(1.0, brightness_factor**0.5)

                    adjusted = [
                        int(color[c] * factor * color_multipliers[c]) for c in range(3)
                    ]
                    pixel_by_idx[idx] = adjusted

            MAX_LEDS_PER_PACKET = 458
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            time.sleep(0.010)

            try:
                for start_idx in range(0, total_leds, MAX_LEDS_PER_PACKET):
                    end_idx = min(start_idx + MAX_LEDS_PER_PACKET, total_leds)
                    packet = bytearray()
                    packet.append(4)  # Protocol: DNRGB

                    if frame_duration is not None:
                        timeout_byte = min(int(frame_duration) + 2, 255)
                    else:
                        timeout_byte = 5
                    packet.append(timeout_byte)
                    packet.append((start_idx >> 8) & 0xFF)
                    packet.append(start_idx & 0xFF)

                    for idx in range(start_idx, end_idx):
                        if idx in pixel_by_idx:
                            rgb = pixel_by_idx[idx]
                            packet.extend([int(rgb[0]), int(rgb[1]), int(rgb[2])])
                        else:
                            packet.extend([0, 0, 0])

                    if len(packet) > 4:
                        sock.sendto(
                            bytes(packet), (device_ip, DeviceController.UDP_PORT)
                        )
                        time.sleep(0.010)
            finally:
                sock.close()

            logger.info(f"UDP DNRGB sent to {device_ip}: {total_leds} LEDs")
            return True
        except Exception as e:
            logger.error(f"Failed UDP DNRGB to {device_ip}: {e}")
            return False
