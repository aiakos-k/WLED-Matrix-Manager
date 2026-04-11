/**
 * Binary Scene Format (.ledm) — TypeScript encoder/decoder.
 * Matches the Python implementation exactly.
 */

import type { FrameData } from "@/api/client";

interface BinaryScene {
  name: string;
  description: string;
  matrix_width: number;
  matrix_height: number;
  loop_mode: string;
  frames: FrameData[];
}

export function binaryToScene(buffer: ArrayBuffer): BinaryScene {
  const view = new DataView(buffer);
  const bytes = new Uint8Array(buffer);
  let o = 0;

  const magic = String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3]);
  o += 4;
  if (magic !== "LEDM") throw new Error(`Invalid magic: ${magic}`);

  const version = view.getUint8(o);
  o += 1;
  if (version !== 1) throw new Error(`Unsupported version: ${version}`);
  o += 3; // reserved

  const nameLen = view.getUint16(o, true);
  o += 2;
  const descLen = view.getUint16(o, true);
  o += 2;
  const mw = view.getUint16(o, true);
  o += 2;
  const mh = view.getUint16(o, true);
  o += 2;
  const frameCount = view.getUint16(o, true);
  o += 2;
  const loopByte = view.getUint8(o);
  o += 1;
  o += 10; // reserved

  const dec = new TextDecoder();
  const name = dec.decode(bytes.slice(o, o + nameLen));
  o += nameLen + 1;
  const description = dec.decode(bytes.slice(o, o + descLen));
  o += descLen + 1;

  const frames: FrameData[] = [];
  for (let f = 0; f < frameCount; f++) {
    const fi = view.getUint16(o, true);
    o += 2;
    const dur = view.getFloat32(o, true);
    o += 4;
    const bri = view.getUint8(o);
    o += 1;
    const cr = Math.round(view.getUint8(o) / 2.55);
    o += 1;
    const cg = Math.round(view.getUint8(o) / 2.55);
    o += 1;
    const cb = Math.round(view.getUint8(o) / 2.55);
    o += 1;
    const pixelCount = view.getUint32(o, true);
    o += 4;

    const pixels: Array<{ index: number; color: number[] }> = [];
    for (let p = 0; p < pixelCount; p++) {
      const idx = view.getUint32(o, true);
      o += 4;
      const r = view.getUint8(o);
      o += 1;
      const g = view.getUint8(o);
      o += 1;
      const b = view.getUint8(o);
      o += 1;
      pixels.push({ index: idx, color: [r, g, b] });
    }

    frames.push({
      frame_index: fi,
      duration: dur,
      brightness: bri,
      color_r: cr,
      color_g: cg,
      color_b: cb,
      pixel_data: { pixels, width: mw, height: mh },
    });
  }

  return {
    name,
    description,
    matrix_width: mw,
    matrix_height: mh,
    loop_mode: loopByte === 1 ? "loop" : "once",
    frames,
  };
}

export function sceneToBinary(scene: BinaryScene): ArrayBuffer {
  const enc = new TextEncoder();
  const nameBytes = enc.encode(scene.name || "");
  const descBytes = enc.encode(scene.description || "");
  const frames = scene.frames || [];

  let size = 32 + nameBytes.length + 1 + descBytes.length + 1;
  for (const f of frames) {
    size += 14 + (f.pixel_data?.pixels?.length || 0) * 7;
  }

  const buf = new ArrayBuffer(size);
  const view = new DataView(buf);
  const arr = new Uint8Array(buf);
  let o = 0;

  arr.set([0x4c, 0x45, 0x44, 0x4d], o);
  o += 4;
  view.setUint8(o, 1);
  o += 1;
  o += 3;
  view.setUint16(o, nameBytes.length, true);
  o += 2;
  view.setUint16(o, descBytes.length, true);
  o += 2;
  view.setUint16(o, scene.matrix_width, true);
  o += 2;
  view.setUint16(o, scene.matrix_height, true);
  o += 2;
  view.setUint16(o, frames.length, true);
  o += 2;
  view.setUint8(o, scene.loop_mode === "loop" ? 1 : 0);
  o += 1;
  o += 10;

  arr.set(nameBytes, o);
  o += nameBytes.length;
  arr[o] = 0;
  o += 1;
  arr.set(descBytes, o);
  o += descBytes.length;
  arr[o] = 0;
  o += 1;

  for (const f of frames) {
    view.setUint16(o, f.frame_index, true);
    o += 2;
    view.setFloat32(o, f.duration || 1.0, true);
    o += 4;
    view.setUint8(o, f.brightness);
    o += 1;
    view.setUint8(
      o,
      Math.min(255, Math.max(0, Math.round((f.color_r ?? 100) * 2.55))),
    );
    o += 1;
    view.setUint8(
      o,
      Math.min(255, Math.max(0, Math.round((f.color_g ?? 100) * 2.55))),
    );
    o += 1;
    view.setUint8(
      o,
      Math.min(255, Math.max(0, Math.round((f.color_b ?? 100) * 2.55))),
    );
    o += 1;
    const pixels = f.pixel_data?.pixels || [];
    view.setUint32(o, pixels.length, true);
    o += 4;
    for (const px of pixels) {
      view.setUint32(o, px.index, true);
      o += 4;
      arr[o] = px.color[0];
      o += 1;
      arr[o] = px.color[1];
      o += 1;
      arr[o] = px.color[2];
      o += 1;
    }
  }

  return buf;
}
