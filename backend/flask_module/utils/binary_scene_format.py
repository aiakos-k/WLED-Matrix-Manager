"""
Binary Scene Format Parser for Python

Format Structure:
HEADER (32 bytes):
  - Magic: "LEDM" (4 bytes)
  - Version: 1 (1 byte)
  - Reserved (3 bytes)
  - Scene Name Length: uint16 (2 bytes, little-endian)
  - Description Length: uint16 (2 bytes, little-endian)
  - Matrix Width: uint16 (2 bytes, little-endian)
  - Matrix Height: uint16 (2 bytes, little-endian)
  - Frame Count: uint16 (2 bytes, little-endian)
  - Loop Mode: 1 byte (0=once, 1=loop)
  - Reserved (10 bytes)

SCENE METADATA:
  - Scene Name (variable length, null-terminated)
  - Description (variable length, null-terminated)

PER FRAME:
  - Frame Index: uint16 (2 bytes, little-endian)
  - Duration: float32 (4 bytes, little-endian)
  - Brightness: uint8 (1 byte)
  - Color_R: uint8 (1 byte) [0-255, where 100 = 0.4 * 255]
  - Color_G: uint8 (1 byte)
  - Color_B: uint8 (1 byte)
  - Pixel Count: uint32 (4 bytes, little-endian)
  - Pixels: (pixel_count * 7 bytes each)
    - Index: uint32 (4 bytes, little-endian)
    - R: uint8 (1 byte)
    - G: uint8 (1 byte)
    - B: uint8 (1 byte)
"""

import struct


def binary_to_scene(binary_data: bytes) -> dict:
    """
    Parse binary scene format and return scene dictionary

    Args:
        binary_data: Raw binary data from .ledm file

    Returns:
        dict: Scene object with frames and metadata

    Raises:
        ValueError: If format is invalid
    """
    if len(binary_data) < 32:
        raise ValueError("Binary data too short")

    offset = 0

    # Read header
    # Magic
    magic = binary_data[offset : offset + 4].decode("ascii")
    offset += 4

    if magic != "LEDM":
        raise ValueError(f"Invalid magic number: {magic}")

    # Version
    version = struct.unpack_from("B", binary_data, offset)[0]
    offset += 1

    if version != 1:
        raise ValueError(f"Unsupported version: {version}")

    # Reserved
    offset += 3

    # Scene Name Length
    name_length = struct.unpack_from("<H", binary_data, offset)[0]
    offset += 2

    # Description Length
    desc_length = struct.unpack_from("<H", binary_data, offset)[0]
    offset += 2

    # Matrix Width
    matrix_width = struct.unpack_from("<H", binary_data, offset)[0]
    offset += 2

    # Matrix Height
    matrix_height = struct.unpack_from("<H", binary_data, offset)[0]
    offset += 2

    # Frame Count
    frame_count = struct.unpack_from("<H", binary_data, offset)[0]
    offset += 2

    # Loop Mode
    loop_mode_byte = struct.unpack_from("B", binary_data, offset)[0]
    offset += 1

    # Reserved
    offset += 10

    # Read scene metadata
    # Scene Name
    scene_name = binary_data[offset : offset + name_length].decode("utf-8")
    offset += name_length + 1  # +1 for null terminator

    # Description
    description = binary_data[offset : offset + desc_length].decode("utf-8")
    offset += desc_length + 1  # +1 for null terminator

    # Read frames
    frames = []
    for _ in range(frame_count):
        # Frame Index
        frame_index = struct.unpack_from("<H", binary_data, offset)[0]
        offset += 2

        # Duration
        duration = struct.unpack_from("<f", binary_data, offset)[0]
        offset += 4

        # Brightness
        brightness = struct.unpack_from("B", binary_data, offset)[0]
        offset += 1

        # Color channels (0-255 mapped back to 0-100)
        color_r_byte = struct.unpack_from("B", binary_data, offset)[0]
        offset += 1
        color_g_byte = struct.unpack_from("B", binary_data, offset)[0]
        offset += 1
        color_b_byte = struct.unpack_from("B", binary_data, offset)[0]
        offset += 1

        # Convert back from 0-255 to 0-100
        color_r = round(color_r_byte / 2.55)
        color_g = round(color_g_byte / 2.55)
        color_b = round(color_b_byte / 2.55)

        # Pixel Count
        pixel_count = struct.unpack_from("<I", binary_data, offset)[0]
        offset += 4

        # Read pixels
        pixels = []
        for _ in range(pixel_count):
            pixel_index = struct.unpack_from("<I", binary_data, offset)[0]
            offset += 4

            r = struct.unpack_from("B", binary_data, offset)[0]
            offset += 1
            g = struct.unpack_from("B", binary_data, offset)[0]
            offset += 1
            b = struct.unpack_from("B", binary_data, offset)[0]
            offset += 1

            pixels.append(
                {
                    "index": pixel_index,
                    "color": [r, g, b],
                }
            )

        frames.append(
            {
                "frame_index": frame_index,
                "duration": float(duration),
                "brightness": brightness,
                "color_r": color_r,
                "color_g": color_g,
                "color_b": color_b,
                "pixel_data": {
                    "pixels": pixels,
                    "width": matrix_width,
                    "height": matrix_height,
                },
            }
        )

    return {
        "name": scene_name,
        "description": description,
        "matrix_width": matrix_width,
        "matrix_height": matrix_height,
        "loop_mode": "loop" if loop_mode_byte == 1 else "once",
        "frames": frames,
    }


def scene_to_binary(scene_dict: dict) -> bytes:
    """
    Convert scene dictionary to binary format

    Args:
        scene_dict: Scene object with frames and metadata

    Returns:
        bytes: Binary data in .ledm format
    """
    scene_name = scene_dict.get("name", "") or ""
    description = scene_dict.get("description", "") or ""
    loop_mode = scene_dict.get("loop_mode", "once")
    matrix_width = scene_dict.get("matrix_width", 16)
    matrix_height = scene_dict.get("matrix_height", 16)
    frames = scene_dict.get("frames", []) or []

    # Calculate total size
    total_size = 32  # Header
    total_size += len(scene_name) + 1  # Name + null terminator
    total_size += len(description) + 1  # Description + null terminator

    # Frame data
    for frame in frames:
        total_size += 14  # Frame header
        pixels = frame.get("pixel_data", {}).get("pixels", [])
        total_size += len(pixels) * 7  # Each pixel: 4 bytes index + 3 bytes RGB

    # Create buffer
    binary_data = bytearray(total_size)
    offset = 0

    # Write header
    # Magic
    binary_data[offset : offset + 4] = b"LEDM"
    offset += 4

    # Version
    struct.pack_into("B", binary_data, offset, 1)
    offset += 1

    # Reserved (3 bytes)
    offset += 3

    # Scene Name Length
    struct.pack_into("<H", binary_data, offset, len(scene_name))
    offset += 2

    # Description Length
    struct.pack_into("<H", binary_data, offset, len(description))
    offset += 2

    # Matrix Width
    struct.pack_into("<H", binary_data, offset, matrix_width)
    offset += 2

    # Matrix Height
    struct.pack_into("<H", binary_data, offset, matrix_height)
    offset += 2

    # Frame Count
    struct.pack_into("<H", binary_data, offset, len(frames))
    offset += 2

    # Loop Mode
    loop_mode_byte = 1 if loop_mode == "loop" else 0
    struct.pack_into("B", binary_data, offset, loop_mode_byte)
    offset += 1

    # Reserved (10 bytes)
    offset += 10

    # Write scene metadata
    # Scene Name
    binary_data[offset : offset + len(scene_name)] = scene_name.encode("utf-8")
    offset += len(scene_name)
    binary_data[offset] = 0  # Null terminator
    offset += 1

    # Description
    binary_data[offset : offset + len(description)] = description.encode("utf-8")
    offset += len(description)
    binary_data[offset] = 0  # Null terminator
    offset += 1

    # Write frames
    for frame in frames:
        # Frame Index
        struct.pack_into("<H", binary_data, offset, frame.get("frame_index", 0))
        offset += 2

        # Duration
        struct.pack_into("<f", binary_data, offset, frame.get("duration", 5.0))
        offset += 4

        # Brightness
        struct.pack_into("B", binary_data, offset, frame.get("brightness", 255))
        offset += 1

        # Color channels (0-100 mapped to 0-255)
        color_r = round((frame.get("color_r", 100) or 100) * 2.55)
        color_g = round((frame.get("color_g", 100) or 100) * 2.55)
        color_b = round((frame.get("color_b", 100) or 100) * 2.55)

        struct.pack_into("B", binary_data, offset, min(255, max(0, color_r)))
        offset += 1
        struct.pack_into("B", binary_data, offset, min(255, max(0, color_g)))
        offset += 1
        struct.pack_into("B", binary_data, offset, min(255, max(0, color_b)))
        offset += 1

        # Pixel data
        pixels = frame.get("pixel_data", {}).get("pixels", [])
        struct.pack_into("<I", binary_data, offset, len(pixels))
        offset += 4

        # Write each pixel
        for pixel in pixels:
            struct.pack_into("<I", binary_data, offset, pixel.get("index", 0))
            offset += 4

            color = pixel.get("color", [0, 0, 0])
            struct.pack_into("B", binary_data, offset, color[0])
            offset += 1
            struct.pack_into("B", binary_data, offset, color[1])
            offset += 1
            struct.pack_into("B", binary_data, offset, color[2])
            offset += 1

    return bytes(binary_data)
