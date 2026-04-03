"""
Device control service for communicating with LED matrix devices
"""

import logging
import socket
import time
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)


class DeviceController:
    """Control LED matrix devices via HTTP API and UDP Realtime protocols"""

    # WLED API endpoint
    DEFAULT_API_ENDPOINT = "/json/state"
    DEFAULT_TIMEOUT = 5  # seconds
    UDP_PORT = 21324  # Default WLED UDP notifier port
    UDP_TIMEOUT = 2  # UDP timeout in seconds

    # Protocol types
    PROTOCOL_JSON = "json_api"
    PROTOCOL_UDP_DNRGB = "udp_dnrgb"

    @staticmethod
    def send_command_to_device(
        device_ip: str,
        command: Dict,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> bool:
        """
        Send a command to a device.

        Args:
            device_ip: IP address of the device
            command: WLED command dictionary
            timeout: Request timeout in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"http://{device_ip}{DeviceController.DEFAULT_API_ENDPOINT}"
            response = requests.post(
                url,
                json=command,
                timeout=timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            logger.info(f"Command sent successfully to {device_ip}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send command to {device_ip}: {str(e)}")
            return False

    @staticmethod
    def send_command_to_devices(
        device_ips: List[str],
        command: Dict,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Dict[str, bool]:
        """
        Send a command to multiple devices.

        Args:
            device_ips: List of device IP addresses
            command: WLED command dictionary
            timeout: Request timeout in seconds

        Returns:
            Dictionary mapping device IPs to success status
        """
        results = {}
        for ip in device_ips:
            results[ip] = DeviceController.send_command_to_device(ip, command, timeout)
        return results

    @staticmethod
    def turn_on(device_ip: str, brightness: int = 255) -> bool:
        """Turn on a device."""
        command = {"on": True, "bri": brightness}
        return DeviceController.send_command_to_device(device_ip, command)

    @staticmethod
    def turn_off(device_ip: str) -> bool:
        """Turn off a device."""
        command = {"on": False}
        return DeviceController.send_command_to_device(device_ip, command)

    @staticmethod
    def set_color(device_ip: str, r: int, g: int, b: int) -> bool:
        """Set a solid color on a device."""
        command = {
            "on": True,
            "bri": 255,
            "seg": {
                "id": 0,
                "col": [[r, g, b]],
            },
        }
        return DeviceController.send_command_to_device(device_ip, command)

    @staticmethod
    def check_device_health(device_ip: str, timeout: int = 3) -> bool:
        """
        Check if a device is reachable and responding.

        Args:
            device_ip: IP address of the device
            timeout: Request timeout in seconds

        Returns:
            True if device is healthy, False otherwise
        """
        try:
            url = f"http://{device_ip}/json/info"
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            logger.info(f"Device {device_ip} is healthy")
            return True
        except requests.exceptions.RequestException as e:
            logger.warning(f"Device {device_ip} is not responding: {str(e)}")
            return False

    @staticmethod
    def generate_wled_command(
        pixel_data: Dict,
        brightness: int = 128,
        on: bool = True,
        color_r: int = 10,
        color_g: int = 10,
        color_b: int = 10,
    ) -> Dict:
        """
        Generate a WLED command from pixel data.

        Uses WLED JSON API indexed pixel format with range compression.
        Format: [idx, [R, G, B], ...] for single pixels or [start_idx, end_idx, [R, G, B]] for ranges

        **IMPORTANT: JSON API (WLED HTTP) handles brightness via the 'bri' parameter at device level**
        Pixel colors are sent UNCHANGED by default. The device dimming is handled by WLED firmware.
        However, per-channel color multipliers (color_r, color_g, color_b) can be applied to individual pixels.

        Args:
            pixel_data: Dictionary with 'pixels' list, 'width', 'height'
            brightness: Brightness level (0-255) - sent to device via 'bri' parameter, NOT applied to pixels
            on: Whether to turn on the device
            color_r: Red channel intensity (0-100, where 100 = full intensity)
            color_g: Green channel intensity (0-100, where 100 = full intensity)
            color_b: Blue channel intensity (0-100, where 100 = full intensity)

        Returns:
            WLED command dictionary
        """
        pixels = pixel_data.get("pixels", [])
        width = pixel_data.get("width", 16)
        height = pixel_data.get("height", 16)
        total_leds = width * height

        logger.debug(
            f"generate_wled_command: input has {len(pixels)} pixels, total_leds={total_leds}, "
            f"brightness={brightness} (sent to device via bri parameter)"
        )

        # Build indexed pixel array
        led_data = []

        if pixels:
            # Sort pixels by index
            sorted_pixels = sorted(pixels, key=lambda p: p.get("index", 0))

            i = 0
            while i < len(sorted_pixels):
                current_pixel = sorted_pixels[i]
                current_idx = current_pixel.get("index", 0)
                current_color = current_pixel.get("color", [0, 0, 0])

                # Send colors - apply per-channel color intensity multipliers
                # color_r, color_g, color_b are 0-100, where 100 = full intensity
                color_multipliers = [
                    color_r / 100.0,
                    color_g / 100.0,
                    color_b / 100.0,
                ]
                adjusted_color = [int(current_color[i] * color_multipliers[i]) for i in range(3)]

                # Look ahead for consecutive pixels with same color
                end_idx = i
                while (
                    end_idx + 1 < len(sorted_pixels)
                    and sorted_pixels[end_idx + 1].get("index", 0)
                    == sorted_pixels[end_idx].get("index", 0) + 1
                ):
                    next_color = sorted_pixels[end_idx + 1].get("color", [0, 0, 0])
                    next_adjusted = [int(next_color[i] * color_multipliers[i]) for i in range(3)]

                    if next_adjusted == adjusted_color:
                        end_idx += 1
                    else:
                        break

                # Add to led_data: single pixel or range
                if end_idx == i:
                    # Single pixel: [idx, [R, G, B]]
                    led_data.append(current_idx)
                    led_data.append(adjusted_color)
                else:
                    # Range: [start_idx, end_idx+1, [R, G, B]] (end_idx+1 is exclusive)
                    led_data.append(current_idx)
                    led_data.append(sorted_pixels[end_idx].get("index", 0) + 1)
                    led_data.append(adjusted_color)

                i = end_idx + 1
        else:
            # No pixels - send black
            led_data = [0, [0, 0, 0]]

        # Build WLED command
        # NOTE: brightness is sent via 'bri' parameter (device-level brightness)
        # Pixel colors are NOT modified
        command = {
            "on": on,
            "bri": brightness,  # Device-level brightness parameter - WLED handles the dimming
            "seg": {
                "id": 0,
                "i": led_data,
            },
        }

        logger.info(
            f"Generated WLED command: on={on}, bri={brightness} (device-level), "
            f"led_data_length={len(led_data)}, format=indexed_with_ranges, num_pixels={len(pixels)}"
        )

        return command

    # ==================== UDP REALTIME METHODS ====================

    @staticmethod
    def send_udp_dnrgb(
        device_ip: str,
        pixel_data: Dict,
        brightness: int = 128,
        timeout: int = UDP_TIMEOUT,
        frame_duration: float = None,
        color_r: int = 10,
        color_g: int = 10,
        color_b: int = 10,
    ) -> bool:
        """
        Send pixels to device using UDP DNRGB protocol (indexed dense RGB mode).

        DNRGB = DRGB with start index. Allows multiple packets for >489 LEDs.
        Each packet has a start index and then sequential RGB data.
        Max 489 LEDs per packet, can send multiple packets to cover all LEDs.

        Args:
            device_ip: IP address of the device
            pixel_data: Pixel data dictionary
            brightness: Overall brightness (0-255)
            timeout: UDP timeout
            frame_duration: Duration this frame should display (in seconds)
            color_r: Red channel intensity (0-100, where 100 = full intensity)
            color_g: Green channel intensity (0-100, where 100 = full intensity)
            color_b: Blue channel intensity (0-100, where 100 = full intensity)

        Supports multi-chain devices: If chain_count > 1, data is distributed across chains.
        Example: 4 chains of 1024 LEDs each:
        - Chain 0: LEDs 0-1023
        - Chain 1: LEDs 1024-2047
        - Chain 2: LEDs 2048-3071
        - Chain 3: LEDs 3072-4095

        Format: [protocol=3, timeout, idx_high, idx_low, R, G, B, R, G, B, ...]
        - Byte 0: Protocol (3 = DNRGB)
        - Byte 1: Timeout (1-2 seconds recommended, 255 for no timeout)
        - Byte 2: Start index HIGH byte
        - Byte 3: Start index LOW byte
        - Byte 4+: RGB data (3 bytes per LED, sequential from start index)

        Max 489 LEDs per packet = (1500 - 4) / 3 = 498 bytes for RGB, but WLED limits to ~489
        This allows sending 4096 LEDs in ~9 packets.

        Args:
            device_ip: IP address of the device
            pixel_data: Dictionary with 'pixels' list, 'width', 'height', 'chain_count' (optional)
            brightness: Brightness level (0-255) - applied to RGB values since UDP has no 'bri' parameter
            timeout: UDP timeout in seconds

        Returns:
            True if successful, False otherwise

        **IMPORTANT: UDP DNRGB does NOT have device-level brightness control**
        Must apply brightness as a multiplier to pixel RGB values, BUT proportionally:
        - Very dark pixels (< 50): Darker colors in background, apply full brightness factor
        - Bright pixels (>= 50): Colored pixels, apply softer brightness curve to preserve vibrance
        """
        try:
            pixels = pixel_data.get("pixels", [])
            width = pixel_data.get("width", 16)
            height = pixel_data.get("height", 16)
            chain_count = pixel_data.get("chain_count", 1)  # Default to single chain
            total_leds = width * height

            # UDP DNRGB brightness handling: proportional adjustment
            # Use a curve that preserves bright colors better than dark ones
            brightness_factor = brightness / 255.0

            logger.debug(
                f"UDP DNRGB brightness={brightness} (factor={brightness_factor:.2f}) - "
                f"proportional adjustment with curve to preserve color vibrance"
            )

            # Build pixel map by index
            pixel_by_idx = {}
            for pixel in pixels:
                idx = pixel.get("index", 0)
                color = pixel.get("color", [0, 0, 0])

                if 0 <= idx < total_leds:
                    # Calculate perceived brightness of the pixel (0-255)
                    # Using luminance formula: 0.299*R + 0.587*G + 0.114*B
                    perceived_brightness = int(
                        0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
                    )

                    # Apply adaptive brightness curve:
                    # - Dark pixels (0-50): Apply full brightness_factor (nearly linear)
                    # - Mid pixels (50-150): Softer curve (less aggressive dimming)
                    # - Bright pixels (150-255): Very soft curve (preserve vibrance)
                    # Formula: blended approach between linear and sqrt-based curves
                    if perceived_brightness < 50:
                        # Dark pixels: apply brightness factor nearly linearly
                        adaptive_factor = brightness_factor
                    elif perceived_brightness < 150:
                        # Mid pixels: blend between linear and sqrt curve
                        # This reduces the dimming effect for mid-tone colors
                        linear = brightness_factor
                        sqrt_based = (
                            brightness_factor * 0.5 + 0.5
                        )  # Softer: between sqrt and linear
                        # Interpolate based on brightness
                        t = (perceived_brightness - 50) / 100.0  # 0 to 1
                        adaptive_factor = linear * (1 - t) + sqrt_based * t
                    else:
                        # Bright pixels (colors): use softer curve
                        # min(1.0, sqrt(brightness_factor)) - preserves bright colors much better
                        adaptive_factor = min(1.0, brightness_factor**0.5)

                    # Apply adaptive brightness to each channel
                    adjusted_color = [
                        int(color[0] * adaptive_factor),
                        int(color[1] * adaptive_factor),
                        int(color[2] * adaptive_factor),
                    ]

                    # Apply per-channel color intensity multipliers (0-100 scale)
                    # color_r, color_g, color_b are 0-100, where 100 = full intensity
                    color_multipliers = [
                        color_r / 100.0,
                        color_g / 100.0,
                        color_b / 100.0,
                    ]
                    adjusted_color = [
                        int(adjusted_color[i] * color_multipliers[i]) for i in range(3)
                    ]

                    # Boost color saturation: increase vibrance by pushing weak channels down
                    # This makes colors more saturated without making them whiter
                    # Formula: push lowest channel towards 0 (increases saturation)
                    # Only apply if pixel is colored (perceived_brightness > 10)
                    if perceived_brightness > 10:
                        # Find min and max channels
                        min_val = min(adjusted_color)
                        max_val = max(adjusted_color)

                        # Saturation = (max - min) / max
                        # To increase saturation, reduce the minimum channel
                        if max_val > 0:
                            # Push weak channels down by 75% (0.25 factor = strong saturation boost)
                            saturation_factor = 0.25  # Reduces weak channels to 25% of original
                            boosted_color = [
                                (
                                    max(0, int(adjusted_color[i] * saturation_factor))
                                    if adjusted_color[i] == min_val and min_val < max_val
                                    else adjusted_color[i]
                                )
                                for i in range(3)
                            ]
                        else:
                            boosted_color = adjusted_color
                    else:
                        boosted_color = adjusted_color

                    pixel_by_idx[idx] = boosted_color

            # Max LEDs per packet: Optimized for WireGuard VPN
            # Standard MTU: 1500 bytes
            # WireGuard overhead: ~80 bytes (60 WireGuard + 20 IP header)
            # Effective MTU over WireGuard: ~1420 bytes
            # Safe packet size: 1380 bytes (leaves 40 bytes safety margin)
            # DNRGB header: 4 bytes (protocol, timeout, start_index_high, start_index_low)
            # Available for RGB data: 1380 - 4 = 1376 bytes
            # LEDs per packet: 1376 / 3 = 458 LEDs (rounded down for safety)
            # For 4096 LEDs (64x64): 4096 / 458 = 9 packets
            MAX_LEDS_PER_PACKET = 458  # Optimized for WireGuard MTU

            logger.info(
                f"UDP DNRGB preparing to send to {device_ip}: "
                f"Device size {width}x{height} = {total_leds} total LEDs, "
                f"Chains: {chain_count}, Input: {len(pixels)} pixels"
            )

            # For multi-chain devices: WLED expects INTERLEAVED indexing
            # Example with 4 chains of 1024 LEDs:
            # Chain 0: LEDs at indices 0, 4, 8, 12, 16, ... (every 4th LED)
            # Chain 1: LEDs at indices 1, 5, 9, 13, 17, ... (every 4th LED)
            # Chain 2: LEDs at indices 2, 6, 10, 14, 18, ... (every 4th LED)
            # Chain 3: LEDs at indices 3, 7, 11, 15, 19, ... (every 4th LED)
            #
            # However, when sending via UDP DNRGB, we send ALL LEDs sequentially in one go,
            # and WLED will automatically distribute them across chains based on chain_count config.
            # So we send LEDs 0-4095 sequentially, and WLED handles the interleaving.

            # Send in chunks of MAX_LEDS_PER_PACKET
            sent_packets = 0
            delay_ms = 10  # milliseconds delay between packets (optimized for WireGuard MTU)

            # Open a single UDP socket for all packets (more efficient)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)

            # Increase socket send buffer to 64KB (helps with burst UDP traffic)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)

            # Initial delay after socket creation to ensure connection is ready
            # Critical for WireGuard/Docker where socket needs time to establish route
            time.sleep(0.010)  # 10ms initial delay
            logger.info(
                f"UDP socket opened to {device_ip} with 64KB send buffer, waiting {delay_ms}ms before first packet"
            )

            try:
                # For single chain or if WLED handles distribution, send sequentially
                for start_idx in range(0, total_leds, MAX_LEDS_PER_PACKET):
                    end_idx = min(start_idx + MAX_LEDS_PER_PACKET, total_leds)

                    logger.debug(
                        f"UDP DNRGB: sending LEDs {start_idx}-{end_idx - 1} (chain_count={chain_count})"
                    )

                    # Build DNRGB packet for this chunk
                    packet = bytearray()
                    protocol_id = 4  # Protocol: DNRGB (supports 485 LEDs per packet)
                    packet.append(protocol_id)  # Protocol: 4 = DNRGB (indexed dense RGB)

                    # Timeout byte: controls how long LEDs stay on after last packet
                    # If frame_duration provided (scene playback), use it, else default to 5 seconds
                    # Max value is 255 seconds
                    if frame_duration is not None:
                        timeout_byte = min(
                            int(frame_duration) + 2, 255
                        )  # +2s buffer for packet processing
                    else:
                        timeout_byte = 5  # Default 5 seconds for single frame sends
                    packet.append(timeout_byte)

                    packet.append((start_idx >> 8) & 0xFF)  # Start index HIGH byte
                    packet.append(start_idx & 0xFF)  # Start index LOW byte

                    # Add RGB data for LEDs in this chunk (sequential)
                    leds_in_chunk = end_idx - start_idx
                    for idx in range(start_idx, end_idx):
                        if idx in pixel_by_idx:
                            rgb = pixel_by_idx[idx]
                            packet.extend([int(rgb[0]), int(rgb[1]), int(rgb[2])])
                        else:
                            packet.extend([0, 0, 0])  # Black for missing LEDs

                    # Log detailed packet info
                    logger.info(
                        f"UDP DNRGB packet {sent_packets + 1} to {device_ip}: "
                        f"start_idx={start_idx} (0x{start_idx:x}), LEDs {start_idx}-{end_idx-1} ({leds_in_chunk} LEDs), "
                        f"packet_size={len(packet)} bytes, chain_count={chain_count}, protocol={protocol_id}, "
                        f"first_pixels=LED{start_idx}=RGB({packet[4]},{packet[5]},{packet[6]}), "
                        f"LED{start_idx+1}=RGB({packet[7]},{packet[8]},{packet[9]}), "
                        f"LED{start_idx+2}=RGB({packet[10]},{packet[11]},{packet[12]})"
                    )

                    # Send packet (reusing same socket)
                    if len(packet) > 4:  # More than just header
                        sock.sendto(bytes(packet), (device_ip, DeviceController.UDP_PORT))
                        sent_packets += 1

                        # Delay between packets for device processing
                        # Docker/network overhead requires longer delay than local
                        # This ensures UDP socket buffer is ready and device can process each packet
                        time.sleep(delay_ms / 1000.0)
                        logger.debug(
                            f"Packet {sent_packets} sent, waiting {delay_ms}ms before next"
                        )

                logger.info(
                    f"UDP DNRGB completed to {device_ip}: {sent_packets} packets sent with chain_count={chain_count}, delay={delay_ms}ms between packets"
                )
            finally:
                # Always close socket, even if error occurs
                sock.close()
            return True

        except Exception as e:
            logger.error(f"Failed to send UDP DNRGB to {device_ip}: {str(e)}")
            return False
