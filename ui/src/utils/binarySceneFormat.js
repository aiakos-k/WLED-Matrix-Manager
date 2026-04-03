/**
 * Binary Scene Format Utility
 *
 * Format Structure:
 * HEADER (32 bytes):
 *   - Magic: "LEDM" (4 bytes)
 *   - Version: 1 (1 byte)
 *   - Reserved (3 bytes)
 *   - Scene Name Length: uint16 (2 bytes)
 *   - Description Length: uint16 (2 bytes)
 *   - Matrix Width: uint16 (2 bytes)
 *   - Matrix Height: uint16 (2 bytes)
 *   - Frame Count: uint16 (2 bytes)
 *   - Loop Mode: 1 byte (0=once, 1=loop)
 *   - Reserved (10 bytes)
 *
 * SCENE METADATA:
 *   - Scene Name (variable length, null-terminated)
 *   - Description (variable length, null-terminated)
 *
 * PER FRAME:
 *   - Frame Index: uint16 (2 bytes)
 *   - Duration: float32 (4 bytes)
 *   - Brightness: uint8 (1 byte)
 *   - Color_R: uint8 (1 byte)
 *   - Color_G: uint8 (1 byte)
 *   - Color_B: uint8 (1 byte)
 *   - Pixel Count: uint32 (4 bytes)
 *   - Pixels: (pixel_count * 7 bytes each)
 *     - Index: uint32 (4 bytes)
 *     - R: uint8 (1 byte)
 *     - G: uint8 (1 byte)
 *     - B: uint8 (1 byte)
 */

/**
 * Convert scene object to binary format
 * @param {Object} scene - Scene object with frames, name, description, etc.
 * @returns {ArrayBuffer} Binary data
 */
export function sceneToBinary(scene) {
  const sceneName = scene.name || '';
  const description = scene.description || '';
  const loopMode = scene.loop_mode === 'loop' ? 1 : 0;
  const frames = scene.frames || [];

  // Calculate total size needed
  let totalSize = 32; // Header
  totalSize += sceneName.length + 1; // Name + null terminator
  totalSize += description.length + 1; // Description + null terminator

  // Frame data
  for (const frame of frames) {
    totalSize += 14; // Frame header (index, duration, brightness, colors, pixel count)
    const pixelCount = frame.pixel_data?.pixels?.length || 0;
    totalSize += pixelCount * 7; // Each pixel: 4 bytes index + 3 bytes RGB
  }

  // Create buffer
  const buffer = new ArrayBuffer(totalSize);
  const view = new DataView(buffer);
  let offset = 0;

  // Write header
  // Magic: "LEDM"
  view.setUint8(offset, 'L'.charCodeAt(0));
  offset++;
  view.setUint8(offset, 'E'.charCodeAt(0));
  offset++;
  view.setUint8(offset, 'D'.charCodeAt(0));
  offset++;
  view.setUint8(offset, 'M'.charCodeAt(0));
  offset++;

  // Version
  view.setUint8(offset, 1);
  offset++;

  // Reserved (3 bytes)
  offset += 3;

  // Scene Name Length
  view.setUint16(offset, sceneName.length, true);
  offset += 2;

  // Description Length
  view.setUint16(offset, description.length, true);
  offset += 2;

  // Matrix Width
  view.setUint16(offset, scene.matrix_width || 16, true);
  offset += 2;

  // Matrix Height
  view.setUint16(offset, scene.matrix_height || 16, true);
  offset += 2;

  // Frame Count
  view.setUint16(offset, frames.length, true);
  offset += 2;

  // Loop Mode
  view.setUint8(offset, loopMode);
  offset++;

  // Reserved (10 bytes)
  offset += 10;

  // Write scene metadata
  // Scene Name
  for (let i = 0; i < sceneName.length; i++) {
    view.setUint8(offset, sceneName.charCodeAt(i));
    offset++;
  }
  view.setUint8(offset, 0); // Null terminator
  offset++;

  // Description
  for (let i = 0; i < description.length; i++) {
    view.setUint8(offset, description.charCodeAt(i));
    offset++;
  }
  view.setUint8(offset, 0); // Null terminator
  offset++;

  // Write frames
  for (const frame of frames) {
    // Frame Index
    view.setUint16(offset, frame.frame_index || 0, true);
    offset += 2;

    // Duration (seconds as float32)
    view.setFloat32(offset, frame.duration || 5.0, true);
    offset += 4;

    // Brightness
    view.setUint8(offset, frame.brightness || 255);
    offset++;

    // Color channels (0-100 mapped to 0-255)
    view.setUint8(offset, Math.round((frame.color_r || 100) * 2.55));
    offset++;
    view.setUint8(offset, Math.round((frame.color_g || 100) * 2.55));
    offset++;
    view.setUint8(offset, Math.round((frame.color_b || 100) * 2.55));
    offset++;

    // Pixel data
    const pixels = frame.pixel_data?.pixels || [];
    view.setUint32(offset, pixels.length, true);
    offset += 4;

    // Write each pixel
    for (const pixel of pixels) {
      // Pixel Index
      view.setUint32(offset, pixel.index, true);
      offset += 4;

      // RGB values
      const [r, g, b] = pixel.color || [0, 0, 0];
      view.setUint8(offset, r);
      offset++;
      view.setUint8(offset, g);
      offset++;
      view.setUint8(offset, b);
      offset++;
    }
  }

  return buffer;
}

/**
 * Convert binary data back to scene object
 * @param {ArrayBuffer} buffer - Binary data
 * @returns {Object} Scene object
 */
export function binaryToScene(buffer) {
  const view = new DataView(buffer);
  let offset = 0;

  // Read and verify magic
  const magic = String.fromCharCode(
    view.getUint8(offset),
    view.getUint8(offset + 1),
    view.getUint8(offset + 2),
    view.getUint8(offset + 3)
  );
  offset += 4;

  if (magic !== 'LEDM') {
    throw new Error('Invalid binary format: magic number mismatch');
  }

  // Version
  const version = view.getUint8(offset);
  offset++;

  if (version !== 1) {
    throw new Error(`Unsupported binary format version: ${version}`);
  }

  // Reserved
  offset += 3;

  // Scene Name Length
  const nameLength = view.getUint16(offset, true);
  offset += 2;

  // Description Length
  const descLength = view.getUint16(offset, true);
  offset += 2;

  // Matrix Width
  const matrixWidth = view.getUint16(offset, true);
  offset += 2;

  // Matrix Height
  const matrixHeight = view.getUint16(offset, true);
  offset += 2;

  // Frame Count
  const frameCount = view.getUint16(offset, true);
  offset += 2;

  // Loop Mode
  const loopModeByte = view.getUint8(offset);
  offset++;

  // Reserved
  offset += 10;

  // Read scene metadata
  let sceneName = '';
  for (let i = 0; i < nameLength; i++) {
    sceneName += String.fromCharCode(view.getUint8(offset));
    offset++;
  }
  offset++; // Skip null terminator

  let description = '';
  for (let i = 0; i < descLength; i++) {
    description += String.fromCharCode(view.getUint8(offset));
    offset++;
  }
  offset++; // Skip null terminator

  // Read frames
  const frames = [];
  for (let f = 0; f < frameCount; f++) {
    // Frame Index
    const frameIndex = view.getUint16(offset, true);
    offset += 2;

    // Duration
    const duration = view.getFloat32(offset, true);
    offset += 4;

    // Brightness
    const brightness = view.getUint8(offset);
    offset++;

    // Color channels (0-255 mapped back to 0-100)
    const colorR = Math.round(view.getUint8(offset) / 2.55);
    offset++;
    const colorG = Math.round(view.getUint8(offset) / 2.55);
    offset++;
    const colorB = Math.round(view.getUint8(offset) / 2.55);
    offset++;

    // Pixel count
    const pixelCount = view.getUint32(offset, true);
    offset += 4;

    // Read pixels
    const pixels = [];
    for (let p = 0; p < pixelCount; p++) {
      const pixelIndex = view.getUint32(offset, true);
      offset += 4;

      const r = view.getUint8(offset);
      offset++;
      const g = view.getUint8(offset);
      offset++;
      const b = view.getUint8(offset);
      offset++;

      pixels.push({
        index: pixelIndex,
        color: [r, g, b],
      });
    }

    frames.push({
      frame_index: frameIndex,
      duration: duration,
      brightness: brightness,
      color_r: colorR,
      color_g: colorG,
      color_b: colorB,
      pixel_data: {
        pixels: pixels,
        width: matrixWidth,
        height: matrixHeight,
      },
    });
  }

  return {
    name: sceneName,
    description: description,
    matrix_width: matrixWidth,
    matrix_height: matrixHeight,
    loop_mode: loopModeByte === 1 ? 'loop' : 'once',
    frames: frames,
  };
}
