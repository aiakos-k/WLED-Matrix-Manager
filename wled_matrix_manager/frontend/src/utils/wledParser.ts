/**
 * WLED JSON format parser.
 * Parses WLED segment format: [startIdx, endIdx, [R,G,B], ...]
 * into a pixel map for the scene editor.
 *
 * Also handles:
 * - curl commands embedding WLED JSON
 * - Shell-escaped brackets (\[ \])
 * - HA YAML multi-line strings
 */

export interface ParsedPixel {
  index: number;
  color: number[];
}

/**
 * Extract and parse JSON from raw input that may be:
 * - Plain JSON
 * - JSON embedded in a curl command
 * - Shell-escaped JSON
 */
function extractJson(input: string): unknown | null {
  const trimmed = input.trim();

  // Try direct parse first
  try {
    return JSON.parse(trimmed);
  } catch {
    // Fall through to extraction
  }

  // Try to extract JSON from curl command or other wrapping text
  const jsonStart = trimmed.indexOf("{");
  const jsonEnd = trimmed.lastIndexOf("}");
  if (jsonStart === -1 || jsonEnd === -1 || jsonStart >= jsonEnd) return null;

  let jsonStr = trimmed.substring(jsonStart, jsonEnd + 1);

  // Fix shell escapes: \[ → [, \] → ]
  jsonStr = jsonStr.replace(/\\\[/g, "[").replace(/\\\]/g, "]");
  // Fix double-escaped quotes
  jsonStr = jsonStr.replace(/\\\\"/g, '"');

  try {
    return JSON.parse(jsonStr);
  } catch {
    return null;
  }
}

function parseWledArray(data: unknown[]): ParsedPixel[] {
  const pixels: ParsedPixel[] = [];
  let i = 0;

  while (i < data.length) {
    const val = data[i];

    if (typeof val === "number") {
      const next = data[i + 1];

      if (typeof next === "number") {
        // Range: [start, end, [R,G,B]]
        const color = data[i + 2];
        if (Array.isArray(color) && color.length >= 3) {
          for (let idx = val; idx < next; idx++) {
            pixels.push({ index: idx, color: [color[0], color[1], color[2]] });
          }
          i += 3;
        } else {
          i += 1;
        }
      } else if (Array.isArray(next) && next.length >= 3) {
        // Single: [idx, [R,G,B]]
        pixels.push({ index: val, color: [next[0], next[1], next[2]] });
        i += 2;
      } else {
        i += 1;
      }
    } else {
      i += 1;
    }
  }

  return pixels;
}

export function parseWledJson(input: string): ParsedPixel[] {
  const parsed = extractJson(input);
  if (!parsed || typeof parsed !== "object") return [];

  const obj = parsed as Record<string, unknown>;

  // Handle full WLED state: { seg: { i: [...] } } or { seg: [{ i: [...] }] }
  let segI: unknown[] | undefined;
  if (obj.seg) {
    const seg = Array.isArray(obj.seg) ? obj.seg[0] : obj.seg;
    if (seg && typeof seg === "object") {
      segI = (seg as Record<string, unknown>).i as unknown[];
    }
  }

  // Handle raw array passed as top-level
  if (!segI && Array.isArray(parsed)) {
    segI = parsed as unknown[];
  }

  if (!segI || !Array.isArray(segI)) return [];

  return parseWledArray(segI);
}
