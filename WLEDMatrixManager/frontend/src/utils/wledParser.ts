/**
 * WLED JSON format parser.
 * Parses WLED segment format: [startIdx, endIdx, [R,G,B], ...]
 * into a pixel map for the scene editor.
 */

export interface ParsedPixel {
  index: number;
  color: number[];
}

export function parseWledJson(input: string): ParsedPixel[] {
  const pixels: ParsedPixel[] = [];

  try {
    let data = JSON.parse(input);

    // Handle full WLED state object
    if (data.seg) {
      const seg = Array.isArray(data.seg) ? data.seg[0] : data.seg;
      data = seg?.i || [];
    }

    if (!Array.isArray(data)) return pixels;

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
              pixels.push({
                index: idx,
                color: [color[0], color[1], color[2]],
              });
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
  } catch {
    // Not valid JSON
  }

  return pixels;
}
