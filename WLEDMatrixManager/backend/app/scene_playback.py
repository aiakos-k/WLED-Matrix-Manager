"""
Scene Playback Manager - handles looping and frame sequencing for LED scenes.
Runs playback in background threads with async-friendly control.
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

active_playbacks: Dict[int, "ScenePlayback"] = {}
playback_lock = threading.Lock()


def upscale_pixel_data(
    pixel_data: dict, target_width: int, target_height: int, mode: str = "auto"
) -> dict:
    """
    Upscale pixel data from scene resolution to device resolution.
    Modes: 'auto', 'integer', 'stretch', 'center'
    """
    source_width = pixel_data.get("width", 16)
    source_height = pixel_data.get("height", 16)
    source_pixels = pixel_data.get("pixels", [])

    if source_width == target_width and source_height == target_height:
        return pixel_data

    scale_x = target_width / source_width
    scale_y = target_height / source_height

    if mode == "auto":
        if scale_x == scale_y and scale_x % 1 == 0:
            mode = "integer"
        elif source_width <= target_width and source_height <= target_height:
            mode = "stretch"
        else:
            return pixel_data

    source_pixel_map = {}
    for pixel in source_pixels:
        source_pixel_map[pixel.get("index")] = pixel.get("color", [0, 0, 0])

    upscaled_pixels = []

    if mode == "integer":
        scale = int(scale_x)
        for sy in range(source_height):
            for sx in range(source_width):
                si = sy * source_width + sx
                color = source_pixel_map.get(si, [0, 0, 0])
                for dy in range(scale):
                    for dx in range(scale):
                        tx = sx * scale + dx
                        ty = sy * scale + dy
                        ti = ty * target_width + tx
                        upscaled_pixels.append({"index": ti, "color": color})
    elif mode == "stretch":
        for ty in range(target_height):
            for tx in range(target_width):
                sx = min(int(tx / scale_x), source_width - 1)
                sy = min(int(ty / scale_y), source_height - 1)
                si = sy * source_width + sx
                color = source_pixel_map.get(si, [0, 0, 0])
                if color != [0, 0, 0]:
                    ti = ty * target_width + tx
                    upscaled_pixels.append({"index": ti, "color": color})
    elif mode == "center":
        ox = (target_width - source_width) // 2
        oy = (target_height - source_height) // 2
        for sy in range(source_height):
            for sx in range(source_width):
                si = sy * source_width + sx
                color = source_pixel_map.get(si, [0, 0, 0])
                tx = sx + ox
                ty = sy + oy
                if 0 <= tx < target_width and 0 <= ty < target_height:
                    ti = ty * target_width + tx
                    upscaled_pixels.append({"index": ti, "color": color})

    return {"pixels": upscaled_pixels, "width": target_width, "height": target_height}


class ScenePlayback:
    """Manages threaded playback of a scene on devices"""

    def __init__(
        self, scene_id: int, devices_info: list, frames: list, loop_mode: str = "once"
    ):
        self.scene_id = scene_id
        self.devices_info = devices_info
        self.frames = frames
        self.loop_mode = loop_mode
        self.is_running = False
        self.thread: Optional[threading.Thread] = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.thread.start()
        logger.info(
            f"Started playback: scene {self.scene_id} on {len(self.devices_info)} devices"
        )

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info(f"Stopped playback: scene {self.scene_id}")

    def _playback_loop(self):
        from app.device_controller import DeviceController

        loop_count = 0
        max_loops = 1 if self.loop_mode == "once" else float("inf")

        try:
            while self.is_running and loop_count < max_loops:
                for frame in self.frames:
                    if not self.is_running:
                        break

                    pixel_data = frame.get("pixel_data", {})
                    duration = frame.get("duration", 1.0)
                    brightness = frame.get("brightness", 255)
                    color_r = frame.get("color_r", 100)
                    color_g = frame.get("color_g", 100)
                    color_b = frame.get("color_b", 100)

                    for device in self.devices_info:
                        ip = device.get("ip_address")
                        protocol = device.get("communication_protocol", "udp_dnrgb")
                        dw = device.get("matrix_width", 16)
                        dh = device.get("matrix_height", 16)

                        upscaled = upscale_pixel_data(pixel_data, dw, dh)

                        try:
                            if protocol == "udp_dnrgb":
                                pd = upscaled.copy()
                                pd["chain_count"] = device.get("chain_count", 1)
                                pd["segment_id"] = device.get("segment_id", 0)
                                DeviceController.send_udp_dnrgb(
                                    ip,
                                    pd,
                                    brightness=brightness,
                                    frame_duration=duration,
                                    color_r=color_r,
                                    color_g=color_g,
                                    color_b=color_b,
                                )
                            else:
                                cmd = DeviceController.generate_wled_command(
                                    upscaled,
                                    brightness=brightness,
                                    color_r=color_r,
                                    color_g=color_g,
                                    color_b=color_b,
                                )
                                # Run async in a new event loop for the thread
                                loop = asyncio.new_event_loop()
                                loop.run_until_complete(
                                    DeviceController.send_json_command(ip, cmd)
                                )
                                loop.close()
                        except Exception as e:
                            logger.error(f"Error sending to {ip}: {e}")

                    time.sleep(duration)
                loop_count += 1
        except Exception as e:
            logger.error(f"Playback error scene {self.scene_id}: {e}")
        finally:
            self.is_running = False
            # Turn off devices
            for device in self.devices_info:
                try:
                    ip = device.get("ip_address")
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(DeviceController.turn_off(ip))
                    loop.close()
                except Exception:
                    pass
            with playback_lock:
                active_playbacks.pop(self.scene_id, None)


def start_scene_playback(
    scene_id: int, devices_info: list, frames: list, loop_mode: str = "once"
):
    with playback_lock:
        if scene_id in active_playbacks:
            active_playbacks[scene_id].stop()
        playback = ScenePlayback(scene_id, devices_info, frames, loop_mode)
        playback.start()
        active_playbacks[scene_id] = playback


def stop_scene_playback(scene_id: int):
    with playback_lock:
        if scene_id in active_playbacks:
            active_playbacks[scene_id].stop()
            del active_playbacks[scene_id]


def get_all_playback_status() -> dict:
    with playback_lock:
        return {
            scene_id: {"is_playing": pb.is_running, "loop_mode": pb.loop_mode}
            for scene_id, pb in active_playbacks.items()
        }
