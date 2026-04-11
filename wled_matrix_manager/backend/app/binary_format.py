"""
Binary Scene Format (.ledm) - encoder and decoder.
32-byte header + metadata + frame data with compact pixel encoding.
"""

import struct


def binary_to_scene(binary_data: bytes) -> dict:
    """Parse .ledm binary data into a scene dictionary."""
    if len(binary_data) < 32:
        raise ValueError("Binary data too short")

    offset = 0
    magic = binary_data[offset : offset + 4].decode("ascii")
    offset += 4
    if magic != "LEDM":
        raise ValueError(f"Invalid magic: {magic}")

    version = struct.unpack_from("B", binary_data, offset)[0]
    offset += 1
    if version != 1:
        raise ValueError(f"Unsupported version: {version}")

    offset += 3  # reserved
    name_length = struct.unpack_from("<H", binary_data, offset)[0]
    offset += 2
    desc_length = struct.unpack_from("<H", binary_data, offset)[0]
    offset += 2
    matrix_width = struct.unpack_from("<H", binary_data, offset)[0]
    offset += 2
    matrix_height = struct.unpack_from("<H", binary_data, offset)[0]
    offset += 2
    frame_count = struct.unpack_from("<H", binary_data, offset)[0]
    offset += 2
    loop_mode_byte = struct.unpack_from("B", binary_data, offset)[0]
    offset += 1
    offset += 10  # reserved

    scene_name = binary_data[offset : offset + name_length].decode("utf-8")
    offset += name_length + 1
    description = binary_data[offset : offset + desc_length].decode("utf-8")
    offset += desc_length + 1

    frames = []
    for _ in range(frame_count):
        frame_index = struct.unpack_from("<H", binary_data, offset)[0]
        offset += 2
        duration = struct.unpack_from("<f", binary_data, offset)[0]
        offset += 4
        brightness = struct.unpack_from("B", binary_data, offset)[0]
        offset += 1
        cr = round(struct.unpack_from("B", binary_data, offset)[0] / 2.55)
        offset += 1
        cg = round(struct.unpack_from("B", binary_data, offset)[0] / 2.55)
        offset += 1
        cb = round(struct.unpack_from("B", binary_data, offset)[0] / 2.55)
        offset += 1
        pixel_count = struct.unpack_from("<I", binary_data, offset)[0]
        offset += 4

        pixels = []
        for _ in range(pixel_count):
            pi = struct.unpack_from("<I", binary_data, offset)[0]
            offset += 4
            r = struct.unpack_from("B", binary_data, offset)[0]
            offset += 1
            g = struct.unpack_from("B", binary_data, offset)[0]
            offset += 1
            b = struct.unpack_from("B", binary_data, offset)[0]
            offset += 1
            pixels.append({"index": pi, "color": [r, g, b]})

        frames.append(
            {
                "frame_index": frame_index,
                "duration": float(duration),
                "brightness": brightness,
                "color_r": cr,
                "color_g": cg,
                "color_b": cb,
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
    """Convert a scene dictionary to .ledm binary format."""
    name = (scene_dict.get("name") or "").encode("utf-8")
    desc = (scene_dict.get("description") or "").encode("utf-8")
    loop_mode = scene_dict.get("loop_mode", "once")
    mw = scene_dict.get("matrix_width", 16)
    mh = scene_dict.get("matrix_height", 16)
    frames = scene_dict.get("frames") or []

    total = 32 + len(name) + 1 + len(desc) + 1
    for f in frames:
        total += 14 + len(f.get("pixel_data", {}).get("pixels", [])) * 7

    buf = bytearray(total)
    o = 0

    buf[o : o + 4] = b"LEDM"
    o += 4
    struct.pack_into("B", buf, o, 1)
    o += 1
    o += 3
    struct.pack_into("<H", buf, o, len(name))
    o += 2
    struct.pack_into("<H", buf, o, len(desc))
    o += 2
    struct.pack_into("<H", buf, o, mw)
    o += 2
    struct.pack_into("<H", buf, o, mh)
    o += 2
    struct.pack_into("<H", buf, o, len(frames))
    o += 2
    struct.pack_into("B", buf, o, 1 if loop_mode == "loop" else 0)
    o += 1
    o += 10

    buf[o : o + len(name)] = name
    o += len(name)
    buf[o] = 0
    o += 1
    buf[o : o + len(desc)] = desc
    o += len(desc)
    buf[o] = 0
    o += 1

    for f in frames:
        struct.pack_into("<H", buf, o, f.get("frame_index", 0))
        o += 2
        struct.pack_into("<f", buf, o, f.get("duration", 1.0))
        o += 4
        struct.pack_into("B", buf, o, f.get("brightness", 255))
        o += 1
        struct.pack_into(
            "B", buf, o, min(255, max(0, round((f.get("color_r", 100) or 100) * 2.55)))
        )
        o += 1
        struct.pack_into(
            "B", buf, o, min(255, max(0, round((f.get("color_g", 100) or 100) * 2.55)))
        )
        o += 1
        struct.pack_into(
            "B", buf, o, min(255, max(0, round((f.get("color_b", 100) or 100) * 2.55)))
        )
        o += 1
        pixels = f.get("pixel_data", {}).get("pixels", [])
        struct.pack_into("<I", buf, o, len(pixels))
        o += 4
        for px in pixels:
            struct.pack_into("<I", buf, o, px.get("index", 0))
            o += 4
            c = px.get("color", [0, 0, 0])
            buf[o] = c[0]
            o += 1
            buf[o] = c[1]
            o += 1
            buf[o] = c[2]
            o += 1

    return bytes(buf)
