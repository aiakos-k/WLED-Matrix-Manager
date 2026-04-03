"""
Scene Playback Manager - handles looping and frame sequencing for LED scenes
"""

import logging
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Global registry of active playbacks
active_playbacks: Dict[int, "ScenePlayback"] = {}
playback_lock = threading.Lock()


def upscale_pixel_data(
    pixel_data: dict, target_width: int, target_height: int, mode: str = "auto"
) -> dict:
    """
    Flexible upscaling/mapping of pixel data from scene to device resolution.

    Supports multiple modes:
    - 'integer': Integer upscaling (2x, 4x) - each pixel becomes NxN block
    - 'stretch': Non-uniform stretch - maps pixels proportionally (for bindings, aspect ratio changes)
    - 'center': Centers smaller scene in larger device, black borders
    - 'auto': Automatically chooses best mode (integer if possible, else stretch)

    Examples:
    - 16×16 → 64×64: 4x integer upscaling (each pixel → 4×4 block)
    - 16×16 → 32×128: stretch mode (non-uniform mapping)
    - 32×32 → 64×64: 2x integer upscaling
    - 8×8 → 64×64: center mode or 8x upscaling

    Args:
        pixel_data: Source pixel data with 'pixels', 'width', 'height'
        target_width: Target device width
        target_height: Target device height
        mode: Scaling mode ('auto', 'integer', 'stretch', 'center')

    Returns:
        Scaled pixel data with target dimensions
    """
    source_width = pixel_data.get("width", 16)
    source_height = pixel_data.get("height", 16)
    source_pixels = pixel_data.get("pixels", [])

    # No scaling needed if dimensions match
    if source_width == target_width and source_height == target_height:
        return pixel_data

    # Calculate scale factors
    scale_x = target_width / source_width
    scale_y = target_height / source_height

    # Auto mode: choose best scaling strategy
    if mode == "auto":
        if scale_x == scale_y and scale_x % 1 == 0:
            mode = "integer"  # Perfect integer scale
        elif source_width <= target_width and source_height <= target_height:
            mode = "stretch"  # Upscaling with stretch
        else:
            logger.warning(
                f"Downscaling not supported: {source_width}x{source_height} → {target_width}x{target_height}"
            )
            return pixel_data

    # Create source pixel lookup (index → color)
    source_pixel_map = {}
    for pixel in source_pixels:
        source_pixel_map[pixel.get("index")] = pixel.get("color", [0, 0, 0])

    upscaled_pixels = []

    if mode == "integer":
        # Integer upscaling: each source pixel → scale×scale block
        if scale_x != scale_y or scale_x % 1 != 0:
            logger.warning(f"Integer mode requires uniform integer scale, got {scale_x}x{scale_y}")
            return pixel_data

        scale = int(scale_x)
        logger.info(
            f"Integer upscaling: {source_width}x{source_height} → {target_width}x{target_height} ({scale}x)"
        )

        for source_y in range(source_height):
            for source_x in range(source_width):
                source_index = source_y * source_width + source_x
                color = source_pixel_map.get(source_index, [0, 0, 0])

                # Create scale×scale block
                for dy in range(scale):
                    for dx in range(scale):
                        target_x = source_x * scale + dx
                        target_y = source_y * scale + dy
                        target_index = target_y * target_width + target_x
                        upscaled_pixels.append({"index": target_index, "color": color})

    elif mode == "stretch":
        # Stretch mode: proportional mapping (for bindings, non-uniform scales)
        logger.info(
            f"Stretch upscaling: {source_width}x{source_height} → {target_width}x{target_height} ({scale_x:.2f}x{scale_y:.2f})"
        )

        for target_y in range(target_height):
            for target_x in range(target_width):
                # Map target position back to source (nearest neighbor)
                source_x = int(target_x / scale_x)
                source_y = int(target_y / scale_y)

                # Clamp to source bounds
                source_x = min(source_x, source_width - 1)
                source_y = min(source_y, source_height - 1)

                source_index = source_y * source_width + source_x
                color = source_pixel_map.get(source_index, [0, 0, 0])

                # Skip black pixels to reduce packet size
                if color != [0, 0, 0]:
                    target_index = target_y * target_width + target_x
                    upscaled_pixels.append({"index": target_index, "color": color})

    elif mode == "center":
        # Center mode: place source in center of target, black borders
        offset_x = (target_width - source_width) // 2
        offset_y = (target_height - source_height) // 2
        logger.info(
            f"Center mode: {source_width}x{source_height} centered in {target_width}x{target_height}, offset=({offset_x},{offset_y})"
        )

        for source_y in range(source_height):
            for source_x in range(source_width):
                source_index = source_y * source_width + source_x
                color = source_pixel_map.get(source_index, [0, 0, 0])

                target_x = source_x + offset_x
                target_y = source_y + offset_y

                # Skip if out of bounds
                if 0 <= target_x < target_width and 0 <= target_y < target_height:
                    target_index = target_y * target_width + target_x
                    upscaled_pixels.append({"index": target_index, "color": color})

    return {"pixels": upscaled_pixels, "width": target_width, "height": target_height}


class ScenePlayback:
    """Manages playback of a scene on devices"""

    def __init__(self, scene_id: int, devices_info: list, frames: list, loop_mode: str = "once"):
        """
        Initialize scene playback.

        Args:
            scene_id: ID of the scene being played
            devices_info: List of device dicts with ip_address, communication_protocol, width, height
            frames: List of frame dictionaries with pixel_data and duration
            loop_mode: "once" (play once then stop) or "loop" (continuous)
        """
        self.scene_id = scene_id
        self.devices_info = devices_info  # List of device dicts
        self.frames = frames
        self.loop_mode = loop_mode
        self.is_running = False
        self.thread: Optional[threading.Thread] = None

    def start(self):
        """Start playback of the scene"""
        if self.is_running:
            logger.warning(f"Scene {self.scene_id} playback already running")
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.thread.start()
        logger.info(
            f"Started playback of scene {self.scene_id} on {len(self.devices_info)} devices"
        )

    def stop(self):
        """Stop playback of the scene"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info(f"Stopped playback of scene {self.scene_id}")

    def _playback_loop(self):
        """Main playback loop - runs in separate thread"""
        from flask_module.services.device_controller import DeviceController

        loop_count = 0
        max_loops = 1 if self.loop_mode == "once" else float("inf")

        try:
            while self.is_running and loop_count < max_loops:
                for frame in self.frames:
                    if not self.is_running:
                        break

                    # Extract frame data
                    pixel_data = frame.get("pixel_data", {})
                    duration = frame.get("duration", 1.0)
                    brightness = frame.get(
                        "brightness", 255
                    )  # Per-frame brightness (default: 255 = 100%)
                    color_r = frame.get(
                        "color_r", 100
                    )  # Per-frame red intensity (0-100, default: 100 = full)
                    color_g = frame.get(
                        "color_g", 100
                    )  # Per-frame green intensity (0-100, default: 100 = full)
                    color_b = frame.get(
                        "color_b", 100
                    )  # Per-frame blue intensity (0-100, default: 100 = full)

                    pixels_count = len(pixel_data.get("pixels", []))
                    logger.info(
                        f"Scene {self.scene_id}: Frame {frame.get('frame_index', '?')} - "
                        f"{pixels_count} pixels, duration={duration}s, brightness={brightness}, "
                        f"color_r={color_r}, color_g={color_g}, color_b={color_b}"
                    )

                    # Send to all devices using their preferred protocol
                    for device_info in self.devices_info:
                        ip_address = device_info.get("ip_address")
                        protocol = device_info.get("communication_protocol", "json_api")
                        device_width = device_info.get("matrix_width", 16)
                        device_height = device_info.get("matrix_height", 16)

                        # Upscale pixel data if device resolution differs from scene
                        upscaled_pixel_data = upscale_pixel_data(
                            pixel_data, device_width, device_height
                        )

                        logger.info(
                            f"Scene {self.scene_id}: Sending frame to {ip_address} using protocol={protocol}, "
                            f"duration={duration}s, brightness={brightness}, device={device_width}x{device_height}"
                        )

                        try:
                            # Choose protocol based on device configuration
                            if protocol == "udp_dnrgb" or protocol == "udp_warls":
                                # UDP DNRGB (indexed dense RGB, max 458 LEDs per packet for WireGuard)
                                # udp_warls is legacy name, same protocol as udp_dnrgb
                                # Add chain_count and segment_id to pixel_data for multi-chain/multi-segment support
                                pixel_data_with_chains = (
                                    upscaled_pixel_data.copy()
                                    if isinstance(upscaled_pixel_data, dict)
                                    else {}
                                )
                                pixel_data_with_chains["chain_count"] = device_info.get(
                                    "chain_count", 1
                                )
                                pixel_data_with_chains["segment_id"] = device_info.get(
                                    "segment_id", 0
                                )
                                logger.debug(
                                    f"UDP DNRGB: Sending {len(upscaled_pixel_data.get('pixels', []))} pixels "
                                    f"with brightness={brightness}, color_r={color_r}, color_g={color_g}, color_b={color_b}, "
                                    f"will display for {duration}s"
                                )
                                # Pass frame_duration to UDP so it can set the timeout byte appropriately
                                DeviceController.send_udp_dnrgb(
                                    ip_address,
                                    pixel_data_with_chains,
                                    brightness=brightness,
                                    frame_duration=duration,
                                    color_r=color_r,
                                    color_g=color_g,
                                    color_b=color_b,
                                )
                            else:
                                # JSON API (default) - HTTP API for small devices
                                pixel_count = len(upscaled_pixel_data.get("pixels", []))
                                logger.info(
                                    f"JSON API: Sending frame to {ip_address}, "
                                    f"{pixel_count} pixels, "
                                    f"brightness={brightness}, color_r={color_r}, color_g={color_g}, color_b={color_b}, "
                                    f"will display for {duration}s"
                                )
                                # Debug: show first few pixels
                                first_pixels = upscaled_pixel_data.get("pixels", [])[:5]
                                logger.debug(f"JSON API first pixels: {first_pixels}")

                                wled_command = DeviceController.generate_wled_command(
                                    upscaled_pixel_data,
                                    brightness=brightness,
                                    on=True,
                                    color_r=color_r,
                                    color_g=color_g,
                                    color_b=color_b,
                                )
                                logger.debug(f"JSON API command: {wled_command}")
                                DeviceController.send_command_to_device(ip_address, wled_command)

                        except Exception as e:
                            logger.error(f"Error sending frame to {ip_address}: {e}", exc_info=True)

                    logger.debug(
                        f"Sent frame {frame.get('frame_index', '?')} of scene {self.scene_id}"
                    )

                    # Wait for frame duration
                    time.sleep(duration)

                    # For JSON API devices: Clear pixels before next frame to prevent ghosting
                    # (when a frame has fewer pixels than the previous one)
                    # For UDP DNRGB: Don't clear - the timeout_byte handles auto-off
                    for device_info in self.devices_info:
                        protocol = device_info.get("communication_protocol", "json_api")
                        ip_address = device_info.get("ip_address")

                        # Only clear for JSON API devices, not UDP DNRGB
                        if protocol != "udp_dnrgb" and protocol != "udp_warls":
                            try:
                                DeviceController.turn_off(ip_address)
                                logger.debug(f"Cleared pixels on {ip_address} before next frame")
                            except Exception as e:
                                logger.warning(f"Failed to clear pixels on {ip_address}: {e}")

                loop_count += 1

        except Exception as e:
            logger.error(f"Error during playback of scene {self.scene_id}: {e}")
        finally:
            self.is_running = False

            # Turn off devices when finished
            try:
                for device_info in self.devices_info:
                    ip = device_info.get("ip_address")
                    DeviceController.turn_off(ip)
                logger.info(f"Turned off devices after scene {self.scene_id} playback finished")
            except Exception as e:
                logger.error(f"Error turning off devices: {e}")

            # Remove from active playbacks registry now that playback is complete
            with playback_lock:
                if self.scene_id in active_playbacks:
                    del active_playbacks[self.scene_id]
                    logger.info(f"Scene {self.scene_id} removed from active playbacks")


def start_scene_playback(scene_id: int, devices_info: list, frames: list, loop_mode: str = "once"):
    """
    Start playback of a scene.

    Args:
        scene_id: ID of the scene
        devices_info: List of device dicts with ip_address, communication_protocol, width, height
        frames: List of frame dictionaries
        loop_mode: "once" or "loop"
    """
    with playback_lock:
        # Stop any existing playback for this scene
        if scene_id in active_playbacks:
            active_playbacks[scene_id].stop()

        # Create and start new playback
        playback = ScenePlayback(scene_id, devices_info, frames, loop_mode)
        playback.start()
        active_playbacks[scene_id] = playback


def stop_scene_playback(scene_id: int):
    """Stop playback of a scene"""
    with playback_lock:
        if scene_id in active_playbacks:
            active_playbacks[scene_id].stop()
            del active_playbacks[scene_id]


def get_all_playback_status() -> dict:
    """
    Get status of all active playbacks.

    Returns:
        Dictionary mapping scene_id to status dict with 'is_playing' and 'loop_mode'
    """
    with playback_lock:
        return {
            scene_id: {"is_playing": playback.is_running, "loop_mode": playback.loop_mode}
            for scene_id, playback in active_playbacks.items()
        }
