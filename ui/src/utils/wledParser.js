/**
 * Parser for WLED JSON format used in Home Assistant automation
 *
 * WLED format example:
 * "i":[0,256,[0,0,0], 5,9,[152,0,0], 9,[204,0,0], ...]
 *
 * Format: [startIndex, endIndex, [R,G,B], startIndex, [R,G,B], ...]
 * - If only [R,G,B] without start/end, it applies to single pixel
 * - Numbers can be ranges (start, end) or single indices (start only)
 */

/**
 * Parse WLED pixel format array into a pixel map
 * @param {array} wledArray - The "i" array from WLED segment
 * @param {number} totalPixels - Total number of pixels (width * height)
 * @returns {object} - Map of pixelIndex -> [r, g, b]
 */
export function parseWledArray(wledArray, totalPixels = 256) {
  const pixelMap = {};

  if (!Array.isArray(wledArray) || wledArray.length === 0) {
    return pixelMap;
  }

  let i = 0;
  while (i < wledArray.length) {
    const element = wledArray[i];

    if (Array.isArray(element)) {
      // This is a color [R, G, B]
      // Should have been processed with previous index
      i++;
      continue;
    }

    // Check if this might be a start index
    if (typeof element === 'number') {
      const startIdx = element;
      let endIdx = startIdx;
      let color = null;

      // Look ahead to determine the range and color
      if (i + 1 < wledArray.length) {
        const nextElement = wledArray[i + 1];

        if (typeof nextElement === 'number') {
          // Could be: [startIdx, endIdx, [color]] or [startIdx, [color]]
          endIdx = nextElement;
          i += 2;

          // Check for color
          if (i < wledArray.length && Array.isArray(wledArray[i])) {
            color = wledArray[i];
            i++;
          }
        } else if (Array.isArray(nextElement)) {
          // [startIdx, [color]]
          color = nextElement;
          i += 2;
        } else {
          i++;
          continue;
        }
      } else {
        i++;
        continue;
      }

      // Apply color to range [startIdx, endIdx)
      if (color && Array.isArray(color) && color.length >= 3) {
        const [r, g, b] = color;
        for (let pixelIdx = startIdx; pixelIdx < endIdx && pixelIdx < totalPixels; pixelIdx++) {
          pixelMap[pixelIdx] = [r, g, b];
        }
      }
    } else {
      i++;
    }
  }

  return pixelMap;
}

/**
 * Parse raw WLED JSON string (from curl commands or direct input)
 * @param {string} jsonString - Raw JSON string with WLED data
 * @returns {object|null} - Parsed WLED data object
 */
export function parseWledJsonString(jsonString) {
  if (!jsonString || typeof jsonString !== 'string') {
    return null;
  }

  const trimmed = jsonString.trim();

  try {
    return JSON.parse(trimmed);
  } catch {
    // Try to extract JSON if it's embedded in curl command
    const jsonStart = trimmed.indexOf('{');
    const jsonEnd = trimmed.lastIndexOf('}');

    if (jsonStart === -1 || jsonEnd === -1 || jsonStart >= jsonEnd) {
      console.error('Could not find JSON in input');
      return null;
    }

    let jsonStr = trimmed.substring(jsonStart, jsonEnd + 1);

    // Fix common JSON encoding issues
    // Remove shell escapes like \[ and \]
    jsonStr = jsonStr.replace(/\\\[/g, '[').replace(/\\\]/g, ']');
    // Fix double-escaped quotes
    jsonStr = jsonStr.replace(/\\\\"/g, '"');

    try {
      return JSON.parse(jsonStr);
    } catch (parseError) {
      console.error('Failed to parse WLED JSON:', parseError);
      console.error('Attempted JSON string:', jsonStr.substring(0, 500) + '...');
      return null;
    }
  }
}

/**
 * Import WLED JSON data directly (from curl payload or raw JSON)
 * Creates a scene from the WLED data
 * @param {string|object} wledData - WLED JSON string or parsed object
 * @param {string} sceneName - Optional custom scene name
 * @returns {object|null} - Scene data in internal format
 */
export function importWledScene(wledData, sceneName = null) {
  let parsed = wledData;

  // Parse if it's a string
  if (typeof wledData === 'string') {
    parsed = parseWledJsonString(wledData);
  }

  if (!parsed || !parsed.seg || !parsed.seg.i) {
    console.error('Invalid WLED data - missing seg.i');
    return null;
  }

  const brightness = parsed.bri || 128;
  const isOn = parsed.on !== false;

  // Generate scene name from provided name or create default
  const name = sceneName || `WLED Scene ${Date.now()}`;
  const unique_id = name.toLowerCase().replace(/\s+/g, '_');

  return wledSceneToInternalFormat(
    {
      name,
      unique_id,
      wledData: parsed,
      brightness,
      on: isOn,
    },
    16, // width
    16 // height
  );
}

/**
 * Parse Home Assistant YAML automation to extract WLED scenes
 * Handles YAML multi-line strings properly
 * @param {string} yamlContent - YAML content with switches
 * @returns {array} - Array of parsed scenes
 */
export function parseHomeAssistantYaml(yamlContent) {
  const scenes = [];

  // Split by "- switch:" to find individual switch definitions
  const switchBlocks = yamlContent.split(/^-\s+switch:/m);

  for (let blockIdx = 0; blockIdx < switchBlocks.length; blockIdx++) {
    const block = switchBlocks[blockIdx];
    if (!block.trim()) continue;

    const scene = {};

    // Extract name
    const nameMatch = block.match(/^\s*name:\s*(.+?)(\n|$)/);
    if (nameMatch) {
      scene.name = nameMatch[1].trim();
    }

    // Extract unique_id
    const idMatch = block.match(/unique_id:\s*['"]*(.+?)['"]*\s*(\n|$)/);
    if (idMatch) {
      scene.unique_id = idMatch[1].trim();
    }

    // Extract command_on - handles ">" for multi-line YAML strings
    const commandMatch = block.match(
      /command_on:\s*>\s*([\s\S]*?)(?=\ncommand_off:|command_off:|$)/
    );
    if (commandMatch) {
      let curlCommand = commandMatch[1].trim();

      // Remove YAML line continuations
      curlCommand = curlCommand.replace(/\n\s+/g, '');

      // Extract JSON from curl command
      const jsonStart = curlCommand.indexOf('{');
      const jsonEnd = curlCommand.lastIndexOf('}');

      if (jsonStart !== -1 && jsonEnd !== -1 && jsonStart < jsonEnd) {
        const jsonStr = curlCommand.substring(jsonStart, jsonEnd + 1);
        const wledData = parseWledJsonString(jsonStr);

        if (wledData && wledData.seg && wledData.seg.i) {
          scene.wledData = wledData;
          scene.brightness = wledData.bri || 128;
        }
      }
    }

    if (scene.name && scene.wledData) {
      scenes.push(scene);
    }
  }

  return scenes;
}

/**
 * Convert parsed WLED scene data to internal scene format
 * @param {object} wledScene - Scene data with wledData and metadata
 * @param {number} width - Matrix width
 * @param {number} height - Matrix height
 * @returns {object} - Scene data in internal format
 */
export function wledSceneToInternalFormat(wledScene, width = 16, height = 16) {
  const totalPixels = width * height;
  const pixelMap = parseWledArray(wledScene.wledData.seg.i, totalPixels);

  // Convert pixel map to frame pixel data
  const framePixelData = {};
  Object.entries(pixelMap).forEach(([index, color]) => {
    framePixelData[index] = color;
  });

  return {
    name: wledScene.name,
    unique_id: wledScene.unique_id,
    description: `Imported from Home Assistant`,
    matrix_width: width,
    matrix_height: height,
    default_frame_duration: 5.0,
    loop_mode: 'once',
    frames: [
      {
        frame_index: 0,
        pixel_data: {
          pixels: Object.entries(framePixelData).map(([index, color]) => ({
            index: parseInt(index),
            color: color,
          })),
        },
        duration: 1.0,
        brightness: wledScene.brightness || 128,
      },
    ],
  };
}

/**
 * Export scene to JSON format
 * @param {object} scene - Scene object with frames
 * @returns {string} - JSON string
 */
export function exportSceneToJson(scene) {
  const exportData = {
    name: scene.name,
    unique_id: scene.unique_id,
    description: scene.description,
    matrix_width: scene.matrix_width,
    matrix_height: scene.matrix_height,
    default_frame_duration: scene.default_frame_duration,
    loop_mode: scene.loop_mode,
    brightness: scene.brightness,
    frames: scene.frames || [],
    exported_at: new Date().toISOString(),
  };

  return JSON.stringify(exportData, null, 2);
}
