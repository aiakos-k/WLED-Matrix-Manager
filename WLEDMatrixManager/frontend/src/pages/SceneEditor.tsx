import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Button, Card, Checkbox, Col, Collapse, Divider, Form, Input, InputNumber,
  message, Modal, Radio, Row, Select, Slider, Space, Tooltip, Upload,
} from 'antd';
import {
  SaveOutlined, PlayCircleOutlined, DeleteOutlined, PlusOutlined,
  UploadOutlined, StopOutlined, ArrowLeftOutlined, ExportOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import {
  createScene, getScene, updateScene, getDevices, playScene, stopScene,
  testFrameOnDevice,
  type FrameData, type DeviceData, type SceneCreate,
} from '@/api/client';
import { parseWledJson } from '@/utils/wledParser';
import { useWebSocket } from '@/hooks/useWebSocket';

const COMMON_COLORS = [
  '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF',
  '#00FFFF', '#FFFFFF', '#FFA500', '#800080', '#FFC0CB',
];

function hexToRgb(hex: string): number[] {
  const n = parseInt(hex.replace('#', ''), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex(r: number, g: number, b: number): string {
  return '#' + [r, g, b].map((c) => c.toString(16).padStart(2, '0')).join('');
}

type CropBox = { x: number; y: number; width: number; height: number };

const SceneEditor: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const [form] = Form.useForm();

  // Matrix
  const [width, setWidth] = useState(16);
  const [height, setHeight] = useState(16);

  // Frames
  const [frames, setFrames] = useState<FrameData[]>([{
    frame_index: 0,
    pixel_data: { pixels: [], width: 16, height: 16 },
    duration: 1.0,
    brightness: 255,
    color_r: 100, color_g: 100, color_b: 100,
  }]);
  const [currentFrame, setCurrentFrame] = useState(0);

  // Drawing
  const [selectedColor, setSelectedColor] = useState('#FF0000');
  const [recentColors, setRecentColors] = useState<string[]>([]);
  const [selectedPixels, setSelectedPixels] = useState<Set<number>>(new Set());
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);

  // Devices
  const [devices, setDevices] = useState<DeviceData[]>([]);
  const [selectedDevices, setSelectedDevices] = useState<number[]>([]);
  const [loopMode, setLoopMode] = useState<string>('once');

  // WLED JSON import / export
  const [wledJson, setWledJson] = useState('');
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportedWledJson, setExportedWledJson] = useState('');

  // Image upload modal
  const [showImageModal, setShowImageModal] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<{ src: string; width: number; height: number } | null>(null);
  const [cropBox, setCropBox] = useState<CropBox>({ x: 0, y: 0, width: 100, height: 100 });
  const [previewPixels, setPreviewPixels] = useState<number[][] | null>(null);
  const [invertColors, setInvertColors] = useState(false);
  const [makeTransparent, setMakeTransparent] = useState(false);
  const [transparentColor, setTransparentColor] = useState('#FFFFFF');
  const [colorThreshold, setColorThreshold] = useState(30);
  const imageRef = useRef<HTMLImageElement>(null);
  const previewCanvasRef = useRef<HTMLCanvasElement>(null);

  // Playback animation from editor
  const [isPlaying, setIsPlaying] = useState(false);
  const playbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // WebSocket for live preview
  const { send: wsSend } = useWebSocket();

  // Load existing scene for editing
  useEffect(() => {
    if (isEdit) {
      getScene(Number(id)).then((s) => {
        form.setFieldsValue({ name: s.name, description: s.description });
        setWidth(s.matrix_width);
        setHeight(s.matrix_height);
        setLoopMode(s.loop_mode);
        setSelectedDevices(s.device_ids);
        if (s.frames.length > 0) {
          setFrames(s.frames);
        }
      }).catch(() => message.error('Failed to load scene'));
    }
    // Load devices
    getDevices().then(setDevices).catch(() => {});
  }, [id, isEdit, form]);

  // Cleanup playback timer on unmount
  useEffect(() => {
    return () => {
      if (playbackTimer.current) clearTimeout(playbackTimer.current);
    };
  }, []);

  const addRecentColor = useCallback((color: string) => {
    setRecentColors((prev) => {
      const filtered = prev.filter((c) => c.toLowerCase() !== color.toLowerCase());
      return [color, ...filtered].slice(0, 5);
    });
  }, []);

  // ─── Pixel helpers ──────────────────────────────────────

  const getPixelMap = useCallback((): Map<number, number[]> => {
    const m = new Map<number, number[]>();
    for (const px of frames[currentFrame]?.pixel_data?.pixels || []) {
      m.set(px.index, px.color);
    }
    return m;
  }, [frames, currentFrame]);

  const setPixel = useCallback((index: number, color: number[]) => {
    setFrames((prev) => {
      const next = [...prev];
      const frame = { ...next[currentFrame] };
      const pixels = [...(frame.pixel_data?.pixels || [])];
      const existing = pixels.findIndex((p) => p.index === index);
      if (existing >= 0) {
        pixels[existing] = { index, color };
      } else {
        pixels.push({ index, color });
      }
      frame.pixel_data = { pixels, width, height };
      next[currentFrame] = frame;
      return next;
    });
  }, [currentFrame, width, height]);

  const removePixel = useCallback((index: number) => {
    setFrames((prev) => {
      const next = [...prev];
      const frame = { ...next[currentFrame] };
      const pixels = (frame.pixel_data?.pixels || []).filter((p) => p.index !== index);
      frame.pixel_data = { pixels, width, height };
      next[currentFrame] = frame;
      return next;
    });
  }, [currentFrame, width, height]);

  // ─── Canvas drawing ─────────────────────────────────────

  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const cellSize = Math.min(Math.floor(600 / Math.max(width, height)), 40);
    canvas.width = width * cellSize;
    canvas.height = height * cellSize;

    // Background
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Pixels
    const pixelMap = getPixelMap();
    for (const [idx, color] of pixelMap) {
      const x = idx % width;
      const y = Math.floor(idx / width);
      ctx.fillStyle = `rgb(${color[0]},${color[1]},${color[2]})`;
      ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
    }

    // Grid – subtle lines between pixels for distinction
    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
    ctx.lineWidth = 1;
    for (let x = 0; x <= width; x++) {
      ctx.beginPath();
      ctx.moveTo(x * cellSize + 0.5, 0);
      ctx.lineTo(x * cellSize + 0.5, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y <= height; y++) {
      ctx.beginPath();
      ctx.moveTo(0, y * cellSize + 0.5);
      ctx.lineTo(canvas.width, y * cellSize + 0.5);
      ctx.stroke();
    }

    // Selected pixels highlight
    ctx.strokeStyle = 'rgba(0,150,255,0.8)';
    ctx.lineWidth = 2;
    for (const idx of selectedPixels) {
      const x = idx % width;
      const y = Math.floor(idx / width);
      ctx.strokeRect(x * cellSize + 1, y * cellSize + 1, cellSize - 2, cellSize - 2);
    }
  }, [width, height, getPixelMap, selectedPixels]);

  useEffect(() => { drawCanvas(); }, [drawCanvas, frames, currentFrame]);

  // ─── Mouse handlers ─────────────────────────────────────

  const getPixelIndex = (e: React.MouseEvent<HTMLCanvasElement>): number => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const cellSize = canvas.width / width;
    const x = Math.floor((e.clientX - rect.left) * (canvas.width / rect.width) / cellSize);
    const y = Math.floor((e.clientY - rect.top) * (canvas.height / rect.height) / cellSize);
    if (x < 0 || x >= width || y < 0 || y >= height) return -1;
    return y * width + x;
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const idx = getPixelIndex(e);
    if (idx < 0) return;

    if (e.button === 2) {
      // Right-click: pick color
      e.preventDefault();
      const pixelMap = getPixelMap();
      const color = pixelMap.get(idx);
      if (color) {
        const hex = rgbToHex(color[0], color[1], color[2]);
        setSelectedColor(hex);
        addRecentColor(hex);
      }
      return;
    }

    if (e.ctrlKey || e.metaKey) {
      // Ctrl+click: multi-select
      setSelectedPixels((prev) => {
        const next = new Set(prev);
        if (next.has(idx)) next.delete(idx);
        else next.add(idx);
        return next;
      });
      return;
    }

    setIsDrawing(true);
    setPixel(idx, hexToRgb(selectedColor));
    addRecentColor(selectedColor);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    const idx = getPixelIndex(e);
    if (idx >= 0) setPixel(idx, hexToRgb(selectedColor));
  };

  const handleMouseUp = () => setIsDrawing(false);

  // ─── Keyboard (arrow keys move selected) ────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (selectedPixels.size === 0) return;
      let dx = 0, dy = 0;
      if (e.key === 'ArrowUp') dy = -1;
      else if (e.key === 'ArrowDown') dy = 1;
      else if (e.key === 'ArrowLeft') dx = -1;
      else if (e.key === 'ArrowRight') dx = 1;
      else return;
      e.preventDefault();

      setFrames((prev) => {
        const next = [...prev];
        const frame = { ...next[currentFrame] };
        const pixels = [...(frame.pixel_data?.pixels || [])];
        const pixelMap = new Map(pixels.map((p) => [p.index, p.color]));

        const moved: { oldIdx: number; newIdx: number; color: number[] }[] = [];
        for (const idx of selectedPixels) {
          const x = idx % width;
          const y = Math.floor(idx / width);
          const nx = x + dx;
          const ny = y + dy;
          if (nx < 0 || nx >= width || ny < 0 || ny >= height) return prev;
          const newIdx = ny * width + nx;
          moved.push({ oldIdx: idx, newIdx, color: pixelMap.get(idx) || hexToRgb(selectedColor) });
        }

        const resultMap = new Map(pixelMap);
        for (const m of moved) {
          if (!selectedPixels.has(m.newIdx)) resultMap.delete(m.oldIdx);
        }
        for (const m of moved) resultMap.set(m.newIdx, m.color);

        frame.pixel_data = {
          pixels: Array.from(resultMap, ([index, color]) => ({ index, color })),
          width, height,
        };
        next[currentFrame] = frame;

        setSelectedPixels(new Set(moved.map((m) => m.newIdx)));
        return next;
      });
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selectedPixels, currentFrame, width, height, selectedColor]);

  // ─── Frame management ───────────────────────────────────

  const addFrame = () => {
    const newFrame: FrameData = {
      frame_index: frames.length,
      pixel_data: { pixels: [], width, height },
      duration: frames[currentFrame]?.duration || 1.0,
      brightness: frames[currentFrame]?.brightness ?? 255,
      color_r: frames[currentFrame]?.color_r ?? 100,
      color_g: frames[currentFrame]?.color_g ?? 100,
      color_b: frames[currentFrame]?.color_b ?? 100,
    };
    setFrames([...frames, newFrame]);
    setCurrentFrame(frames.length);
  };

  const duplicateFrame = () => {
    const src = frames[currentFrame];
    const dup: FrameData = {
      ...JSON.parse(JSON.stringify(src)),
      frame_index: frames.length,
    };
    setFrames([...frames, dup]);
    setCurrentFrame(frames.length);
  };

  const deleteFrame = (index: number) => {
    if (frames.length <= 1) return;
    const next = frames.filter((_, i) => i !== index).map((f, i) => ({ ...f, frame_index: i }));
    setFrames(next);
    setCurrentFrame(Math.min(currentFrame, next.length - 1));
  };

  const clearFrame = () => {
    setFrames((prev) => {
      const next = [...prev];
      next[currentFrame] = { ...next[currentFrame], pixel_data: { pixels: [], width, height } };
      return next;
    });
  };

  const updateFrameProp = (key: keyof FrameData, value: number | null) => {
    if (value == null) return;
    setFrames((prev) => {
      const next = [...prev];
      next[currentFrame] = { ...next[currentFrame], [key]: value };
      return next;
    });
  };

  // ─── WLED JSON Import ───────────────────────────────────

  const importWledJson = () => {
    if (!wledJson.trim()) return;
    const pixels = parseWledJson(wledJson);
    if (pixels.length === 0) {
      message.error('No pixels found in WLED JSON');
      return;
    }
    setFrames((prev) => {
      const next = [...prev];
      next[currentFrame] = {
        ...next[currentFrame],
        pixel_data: { pixels, width, height },
      };
      return next;
    });
    message.success(`Imported ${pixels.length} pixels`);
    setWledJson('');
  };

  // ─── WLED JSON Export ───────────────────────────────────

  const exportCurrentFrameAsWled = () => {
    const frame = frames[currentFrame];
    const pixels = [...(frame.pixel_data?.pixels || [])].sort((a, b) => a.index - b.index);

    // Build WLED array with range compression
    const wledArray: (number | number[])[] = [];
    let i = 0;
    while (i < pixels.length) {
      const curr = pixels[i];
      let endI = i;
      // Find consecutive pixels with same color
      while (
        endI + 1 < pixels.length &&
        pixels[endI + 1].index === pixels[endI].index + 1 &&
        pixels[endI + 1].color[0] === curr.color[0] &&
        pixels[endI + 1].color[1] === curr.color[1] &&
        pixels[endI + 1].color[2] === curr.color[2]
      ) {
        endI++;
      }

      if (endI === i) {
        // Single pixel
        wledArray.push(curr.index, curr.color);
      } else {
        // Range (exclusive end)
        wledArray.push(curr.index, pixels[endI].index + 1, curr.color);
      }
      i = endI + 1;
    }

    const wledObj = {
      on: true,
      bri: frame.brightness ?? 128,
      seg: { id: 0, i: wledArray },
    };

    setExportedWledJson(JSON.stringify(wledObj));
    setExportModalOpen(true);
  };

  // ─── Image Upload & Crop Modal ──────────────────────────

  const handleImageUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (ev) => {
      const img = new Image();
      img.onload = () => {
        setUploadedImage({ src: ev.target!.result as string, width: img.width, height: img.height });
        const size = Math.min(img.width, img.height);
        setCropBox({
          x: (img.width - size) / 2,
          y: (img.height - size) / 2,
          width: size,
          height: size,
        });
        setInvertColors(false);
        setMakeTransparent(false);
        setPreviewPixels(null);
        setShowImageModal(true);
      };
      img.src = ev.target!.result as string;
    };
    reader.readAsDataURL(file);
    return false;
  };

  // Update preview when crop/options change
  useEffect(() => {
    if (!uploadedImage || !previewCanvasRef.current) return;

    const canvas = previewCanvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      const scaleFactor = 15;
      canvas.width = width * scaleFactor;
      canvas.height = height * scaleFactor;

      ctx.drawImage(
        img,
        cropBox.x, cropBox.y, cropBox.width, cropBox.height,
        0, 0, canvas.width, canvas.height,
      );

      const scaledData = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      const pxArr: number[][] = [];
      for (let py = 0; py < height; py++) {
        for (let px = 0; px < width; px++) {
          const sx = Math.floor(px * scaleFactor + scaleFactor / 2);
          const sy = Math.floor(py * scaleFactor + scaleFactor / 2);
          const idx = (sy * canvas.width + sx) * 4;
          let r = scaledData[idx], g = scaledData[idx + 1], b = scaledData[idx + 2];
          if (invertColors) { r = 255 - r; g = 255 - g; b = 255 - b; }
          pxArr.push([r, g, b]);
        }
      }
      setPreviewPixels(pxArr);
    };
    img.src = uploadedImage.src;
  }, [uploadedImage, cropBox, width, height, invertColors, makeTransparent, transparentColor, colorThreshold]);

  const handlePreviewClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!makeTransparent || !previewPixels || !previewCanvasRef.current) return;
    const canvas = previewCanvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleFactor = 15;
    const px = Math.floor((e.clientX - rect.left) / (rect.width / width));
    const py = Math.floor((e.clientY - rect.top) / (rect.height / height));
    if (px >= 0 && px < width && py >= 0 && py < height) {
      const idx = py * width + px;
      if (previewPixels[idx]) {
        const [r, g, b] = previewPixels[idx];
        setTransparentColor(rgbToHex(r, g, b));
      }
    }
  };

  const applyImageToCanvas = () => {
    if (!previewPixels) return;
    const newPixels: Array<{ index: number; color: number[] }> = [];

    let tR = 255, tG = 255, tB = 255;
    if (makeTransparent) {
      [tR, tG, tB] = hexToRgb(transparentColor);
    }

    previewPixels.forEach((color, index) => {
      const [r, g, b] = color;
      // Skip transparent color if enabled
      if (
        makeTransparent &&
        Math.abs(r - tR) <= colorThreshold &&
        Math.abs(g - tG) <= colorThreshold &&
        Math.abs(b - tB) <= colorThreshold
      ) return;
      // Skip near-black pixels
      if (r <= 30 && g <= 30 && b <= 30) return;
      newPixels.push({ index, color: [r, g, b] });
    });

    // Merge with existing pixels (new ones overwrite)
    setFrames((prev) => {
      const next = [...prev];
      const frame = { ...next[currentFrame] };
      const existing = new Map<number, number[]>();
      for (const px of frame.pixel_data?.pixels || []) existing.set(px.index, px.color);
      for (const px of newPixels) existing.set(px.index, px.color);
      frame.pixel_data = {
        pixels: Array.from(existing, ([index, color]) => ({ index, color })),
        width, height,
      };
      next[currentFrame] = frame;
      return next;
    });

    setShowImageModal(false);
    message.success('Image imported to canvas');
  };

  const handleCropMouseDown = (e: React.MouseEvent, handle: string | null) => {
    if (!imageRef.current || !uploadedImage) return;
    e.stopPropagation();
    e.preventDefault();

    const imgRect = imageRef.current.getBoundingClientRect();
    const startX = e.clientX;
    const startY = e.clientY;
    const startCrop = { ...cropBox };
    const scaleX = imgRect.width / uploadedImage.width;
    const scaleY = imgRect.height / uploadedImage.height;
    const minSize = 10;

    const onMove = (mv: MouseEvent) => {
      const dx = (mv.clientX - startX) / scaleX;
      const dy = (mv.clientY - startY) / scaleY;
      const c = { ...startCrop };

      if (!handle) {
        // Move entire box
        c.x = Math.max(0, Math.min(uploadedImage.width - c.width, startCrop.x + dx));
        c.y = Math.max(0, Math.min(uploadedImage.height - c.height, startCrop.y + dy));
      } else {
        // Resize from handle
        if (handle.includes('w')) { c.x = Math.max(0, startCrop.x + dx); c.width = Math.max(minSize, startCrop.width - dx); }
        if (handle.includes('e')) { c.width = Math.max(minSize, startCrop.width + dx); }
        if (handle.includes('n')) { c.y = Math.max(0, startCrop.y + dy); c.height = Math.max(minSize, startCrop.height - dy); }
        if (handle.includes('s')) { c.height = Math.max(minSize, startCrop.height + dy); }
        // Clamp to image bounds
        c.x = Math.max(0, Math.min(c.x, uploadedImage.width - c.width));
        c.y = Math.max(0, Math.min(c.y, uploadedImage.height - c.height));
        c.width = Math.min(c.width, uploadedImage.width - c.x);
        c.height = Math.min(c.height, uploadedImage.height - c.y);
      }
      setCropBox(c);
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  // ─── Play/Stop animation from editor ────────────────────

  const startPlayback = () => {
    if (frames.length <= 1) { message.info('Need more than one frame to play'); return; }
    setIsPlaying(true);
    let idx = 0;

    const playNext = () => {
      if (idx >= frames.length) {
        if (loopMode === 'loop') { idx = 0; } else { setIsPlaying(false); return; }
      }
      setCurrentFrame(idx);
      const dur = (frames[idx]?.duration || 1.0) * 1000;
      idx++;
      playbackTimer.current = setTimeout(playNext, dur);
    };
    playNext();
  };

  const stopPlayback = () => {
    setIsPlaying(false);
    if (playbackTimer.current) { clearTimeout(playbackTimer.current); playbackTimer.current = null; }
  };

  // ─── Live preview via WebSocket ─────────────────────────

  const sendPreview = () => {
    const frame = frames[currentFrame];
    wsSend({
      action: 'preview_frame',
      data: {
        pixel_data: frame.pixel_data,
        brightness: frame.brightness,
        color_r: frame.color_r,
        color_g: frame.color_g,
        color_b: frame.color_b,
      },
    });
    message.info('Preview sent');
  };

  // ─── Test frame on device ───────────────────────────────

  const testFrame = async () => {
    if (selectedDevices.length === 0) {
      message.warning('Select a device first');
      return;
    }
    const frame = frames[currentFrame];
    try {
      await testFrameOnDevice({
        device_ids: selectedDevices,
        pixel_data: frame.pixel_data,
        brightness: frame.brightness,
        color_r: frame.color_r,
        color_g: frame.color_g,
        color_b: frame.color_b,
      });
      message.success('Frame sent to device');
    } catch {
      message.error('Failed to send frame to device');
    }
  };

  // ─── Save ───────────────────────────────────────────────

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const sceneData: SceneCreate = {
        name: values.name,
        description: values.description || '',
        matrix_width: width,
        matrix_height: height,
        default_frame_duration: frames[0]?.duration || 1.0,
        loop_mode: loopMode,
        device_ids: selectedDevices,
        frames: frames.map((f, i) => ({ ...f, frame_index: i })),
      };

      if (isEdit) {
        await updateScene(Number(id), sceneData);
        message.success('Scene updated');
      } else {
        await createScene(sceneData);
        message.success('Scene created');
      }
      navigate('/scenes');
    } catch {
      message.error('Please fill in the scene name');
    }
  };

  // ─── Resize handler ─────────────────────────────────────

  const handleResize = (newW: number, newH: number) => {
    setWidth(newW);
    setHeight(newH);
    setFrames((prev) =>
      prev.map((f) => ({
        ...f,
        pixel_data: {
          ...f.pixel_data,
          width: newW,
          height: newH,
          pixels: (f.pixel_data?.pixels || []).filter(
            (p) => (p.index % (f.pixel_data?.width || 16)) < newW && Math.floor(p.index / (f.pixel_data?.width || 16)) < newH,
          ).map((p) => {
            const oldW = f.pixel_data?.width || 16;
            const x = p.index % oldW;
            const y = Math.floor(p.index / oldW);
            return { ...p, index: y * newW + x };
          }),
        },
      })),
    );
  };

  const curFrame = frames[currentFrame];

  // ─── Crop overlay handles ───────────────────────────────

  const cropHandles = uploadedImage ? (() => {
    const lPct = (cropBox.x / uploadedImage.width) * 100;
    const tPct = (cropBox.y / uploadedImage.height) * 100;
    const wPct = (cropBox.width / uploadedImage.width) * 100;
    const hPct = (cropBox.height / uploadedImage.height) * 100;
    const hs = 10; // handle size
    const ho = -hs / 2; // handle offset
    const handles: { key: string; style: React.CSSProperties; cursor: string }[] = [
      { key: 'nw', cursor: 'nwse-resize', style: { left: ho, top: ho, width: hs, height: hs } },
      { key: 'ne', cursor: 'nesw-resize', style: { right: ho, top: ho, width: hs, height: hs } },
      { key: 'sw', cursor: 'nesw-resize', style: { left: ho, bottom: ho, width: hs, height: hs } },
      { key: 'se', cursor: 'nwse-resize', style: { right: ho, bottom: ho, width: hs, height: hs } },
      { key: 'n', cursor: 'ns-resize', style: { left: '50%', top: -3, transform: 'translateX(-50%)', width: 30, height: 6 } },
      { key: 's', cursor: 'ns-resize', style: { left: '50%', bottom: -3, transform: 'translateX(-50%)', width: 30, height: 6 } },
      { key: 'e', cursor: 'ew-resize', style: { right: -3, top: '50%', transform: 'translateY(-50%)', width: 6, height: 30 } },
      { key: 'w', cursor: 'ew-resize', style: { left: -3, top: '50%', transform: 'translateY(-50%)', width: 6, height: 30 } },
    ];
    return { lPct, tPct, wPct, hPct, handles };
  })() : null;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/scenes')}>Back</Button>
          <h2 style={{ margin: 0 }}>{isEdit ? 'Edit Scene' : 'Create Scene'}</h2>
        </Space>
        <Space>
          <Button icon={<PlayCircleOutlined />} onClick={testFrame}>Send to Device</Button>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>Save</Button>
        </Space>
      </div>

      <Row gutter={16}>
        {/* Left: Tools */}
        <Col xs={24} md={6}>
          <Card title="Scene" size="small" style={{ marginBottom: 16 }}>
            <Form form={form} layout="vertical" size="small">
              <Form.Item name="name" label="Name" rules={[{ required: true }]}>
                <Input placeholder="My Scene" />
              </Form.Item>
              <Form.Item name="description" label="Description">
                <Input.TextArea rows={2} />
              </Form.Item>
            </Form>
            <Space style={{ width: '100%' }} direction="vertical" size={4}>
              <div style={{ display: 'flex', gap: 8 }}>
                <div>
                  <label>Width</label>
                  <InputNumber min={1} max={256} value={width}
                    onChange={(v) => v && handleResize(v, height)} style={{ width: '100%' }} />
                </div>
                <div>
                  <label>Height</label>
                  <InputNumber min={1} max={256} value={height}
                    onChange={(v) => v && handleResize(width, v)} style={{ width: '100%' }} />
                </div>
              </div>
              <div>
                <label>Loop Mode</label>
                <Radio.Group value={loopMode} onChange={(e) => setLoopMode(e.target.value)}
                  style={{ width: '100%' }}>
                  <Radio.Button value="once" style={{ width: '50%', textAlign: 'center' }}>Once</Radio.Button>
                  <Radio.Button value="loop" style={{ width: '50%', textAlign: 'center' }}>Loop</Radio.Button>
                </Radio.Group>
              </div>
              <div>
                <label>Target Devices</label>
                <Select mode="multiple" style={{ width: '100%' }}
                  value={selectedDevices} onChange={setSelectedDevices}
                  placeholder="Select devices"
                  options={devices.map((d) => ({ value: d.id, label: `${d.name} (${d.matrix_width}×${d.matrix_height})` }))}
                />
              </div>
            </Space>
          </Card>

          <Card title="Tools" size="small" style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8 }}>
              <label>Color:</label>
              <input type="color" value={selectedColor}
                onChange={(e) => { setSelectedColor(e.target.value); addRecentColor(e.target.value); }}
                style={{ width: '100%', height: 32, cursor: 'pointer', border: 'none' }}
              />
            </div>
            <div style={{ marginBottom: 8 }}>
              <label>Common Colors:</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {COMMON_COLORS.map((c) => (
                  <Tooltip key={c} title={c}>
                    <div
                      onClick={() => { setSelectedColor(c); addRecentColor(c); }}
                      style={{
                        width: 24, height: 24, background: c, cursor: 'pointer',
                        border: selectedColor === c ? '2px solid #1890ff' : '1px solid #ccc',
                        borderRadius: 2,
                      }}
                    />
                  </Tooltip>
                ))}
              </div>
            </div>
            {recentColors.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <label>Recent:</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {recentColors.map((c) => (
                    <Tooltip key={c} title={c}>
                      <div
                        onClick={() => setSelectedColor(c)}
                        style={{
                          width: 24, height: 24, background: c, cursor: 'pointer',
                          border: selectedColor === c ? '2px solid #1890ff' : '1px solid #ccc',
                          borderRadius: 2,
                        }}
                      />
                    </Tooltip>
                  ))}
                </div>
              </div>
            )}
            <Divider style={{ margin: '8px 0' }} />
            <p style={{ fontSize: 12, color: '#666' }}>
              Click: draw &bull; Right-click: pick color<br />
              Ctrl+Click: multi-select &bull; Arrow keys: move
            </p>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button block onClick={clearFrame}>Clear Frame</Button>
              <Upload accept="image/*" showUploadList={false}
                beforeUpload={(file) => { handleImageUpload(file); return false; }}>
                <Button block icon={<UploadOutlined />}>Upload Image</Button>
              </Upload>
              <Button block onClick={sendPreview} icon={<PlayCircleOutlined />}>
                Live Preview
              </Button>
            </Space>
          </Card>

          <Collapse size="small" items={[{
            key: 'wled',
            label: 'WLED JSON Import / Export',
            children: (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Input.TextArea value={wledJson} onChange={(e) => setWledJson(e.target.value)}
                  rows={3} placeholder='{"seg":{"i":[...]}} or curl command' />
                <Button block onClick={importWledJson}>Import to Frame {currentFrame + 1}</Button>
                <Divider style={{ margin: '8px 0' }} />
                <Button block icon={<ExportOutlined />} onClick={exportCurrentFrameAsWled}>
                  Export Frame {currentFrame + 1} as WLED JSON
                </Button>
              </Space>
            ),
          }]} />
        </Col>

        {/* Center: Canvas */}
        <Col xs={24} md={12}>
          <Card title="Canvas" size="small">
            <div style={{ overflow: 'auto', maxHeight: '70vh', display: 'flex', justifyContent: 'center' }}>
              <canvas
                ref={canvasRef}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onContextMenu={(e) => e.preventDefault()}
                style={{ cursor: 'crosshair', imageRendering: 'pixelated' }}
              />
            </div>
          </Card>
        </Col>

        {/* Right: Frame settings */}
        <Col xs={24} md={6}>
          <Card title={`Frame ${currentFrame + 1} / ${frames.length}`} size="small" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }} size={8}>
              <div>
                <label>Duration (sec)</label>
                <InputNumber min={0.1} max={60} step={0.1} value={curFrame?.duration ?? 1.0}
                  onChange={(v) => updateFrameProp('duration', v)} style={{ width: '100%' }} />
              </div>
              <div>
                <label>Brightness ({curFrame?.brightness ?? 255})</label>
                <Slider min={0} max={255} value={curFrame?.brightness ?? 255}
                  onChange={(v) => updateFrameProp('brightness', v)} />
              </div>
              <div>
                <label style={{ color: 'red' }}>Red ({curFrame?.color_r ?? 100}%)</label>
                <Slider min={0} max={100} value={curFrame?.color_r ?? 100}
                  onChange={(v) => updateFrameProp('color_r', v)}
                  styles={{ track: { background: '#ff4d4f' } }} />
              </div>
              <div>
                <label style={{ color: 'green' }}>Green ({curFrame?.color_g ?? 100}%)</label>
                <Slider min={0} max={100} value={curFrame?.color_g ?? 100}
                  onChange={(v) => updateFrameProp('color_g', v)}
                  styles={{ track: { background: '#52c41a' } }} />
              </div>
              <div>
                <label style={{ color: 'blue' }}>Blue ({curFrame?.color_b ?? 100}%)</label>
                <Slider min={0} max={100} value={curFrame?.color_b ?? 100}
                  onChange={(v) => updateFrameProp('color_b', v)}
                  styles={{ track: { background: '#1890ff' } }} />
              </div>
            </Space>
          </Card>

          <Card title="Frames" size="small" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ maxHeight: 300, overflow: 'auto' }}>
                {frames.map((f, i) => (
                  <div key={i} onClick={() => { if (!isPlaying) setCurrentFrame(i); }}
                    style={{
                      padding: '4px 8px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between',
                      alignItems: 'center', borderRadius: 4,
                      background: i === currentFrame ? '#e6f7ff' : 'transparent',
                      border: i === currentFrame ? '1px solid #91d5ff' : '1px solid transparent',
                    }}>
                    <span>Frame {i + 1} ({(f.pixel_data?.pixels?.length || 0)} px)</span>
                    {frames.length > 1 && (
                      <Button size="small" type="text" danger icon={<DeleteOutlined />}
                        onClick={(e) => { e.stopPropagation(); deleteFrame(i); }} />
                    )}
                  </div>
                ))}
              </div>
              <Space>
                <Button size="small" icon={<PlusOutlined />} onClick={addFrame}>Add</Button>
                <Button size="small" onClick={duplicateFrame}>Duplicate</Button>
              </Space>
            </Space>
          </Card>

          <Card title="Playback" size="small">
            <Space style={{ width: '100%' }}>
              {isPlaying ? (
                <Button danger icon={<StopOutlined />} onClick={stopPlayback}>Stop</Button>
              ) : (
                <Button icon={<PlayCircleOutlined />} onClick={startPlayback}
                  disabled={frames.length <= 1}>
                  Play ({loopMode === 'loop' ? 'Loop' : 'Once'})
                </Button>
              )}
            </Space>
          </Card>
        </Col>
      </Row>

      {/* ─── Image Import Modal ──────────────────────────── */}
      <Modal
        title="Import Image"
        open={showImageModal}
        width={900}
        onCancel={() => setShowImageModal(false)}
        footer={[
          <Button key="cancel" onClick={() => setShowImageModal(false)}>Cancel</Button>,
          <Button key="import" type="primary" onClick={applyImageToCanvas}>Import to Canvas</Button>,
        ]}
      >
        {uploadedImage && (
          <div style={{ display: 'flex', gap: 20 }}>
            {/* Left: Image with crop overlay */}
            <div style={{ flex: 1 }}>
              <h4>Select Region</h4>
              <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%' }}>
                <img
                  ref={imageRef}
                  src={uploadedImage.src}
                  style={{ maxWidth: '100%', maxHeight: 400, display: 'block' }}
                />
                {cropHandles && (
                  <div
                    style={{
                      position: 'absolute',
                      left: `${cropHandles.lPct}%`, top: `${cropHandles.tPct}%`,
                      width: `${cropHandles.wPct}%`, height: `${cropHandles.hPct}%`,
                      border: '3px solid #1890ff',
                      boxShadow: 'inset 0 0 0 4000px rgba(0,0,0,0.5)',
                      cursor: 'move',
                    }}
                    onMouseDown={(e) => handleCropMouseDown(e, null)}
                  >
                    {cropHandles.handles.map((h) => (
                      <div key={h.key}
                        onMouseDown={(e) => handleCropMouseDown(e, h.key)}
                        style={{
                          position: 'absolute', ...h.style,
                          backgroundColor: '#1890ff', cursor: h.cursor,
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Crop numeric inputs */}
              <div style={{ marginTop: 12 }}>
                <label>Crop Position & Size:</label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginTop: 8 }}>
                  <InputNumber addonBefore="X" size="small" min={0} max={uploadedImage.width}
                    value={Math.round(cropBox.x)} onChange={(v) => setCropBox((p) => ({ ...p, x: v || 0 }))} />
                  <InputNumber addonBefore="Y" size="small" min={0} max={uploadedImage.height}
                    value={Math.round(cropBox.y)} onChange={(v) => setCropBox((p) => ({ ...p, y: v || 0 }))} />
                  <InputNumber addonBefore="W" size="small" min={10} max={uploadedImage.width}
                    value={Math.round(cropBox.width)} onChange={(v) => setCropBox((p) => ({ ...p, width: v || 10 }))} />
                  <InputNumber addonBefore="H" size="small" min={10} max={uploadedImage.height}
                    value={Math.round(cropBox.height)} onChange={(v) => setCropBox((p) => ({ ...p, height: v || 10 }))} />
                </div>
                <Space style={{ marginTop: 8, width: '100%' }} direction="vertical">
                  <Button block onClick={() => {
                    const s = Math.min(uploadedImage.width, uploadedImage.height);
                    setCropBox({ x: (uploadedImage.width - s) / 2, y: (uploadedImage.height - s) / 2, width: s, height: s });
                  }}>Square Crop</Button>
                  <Button block onClick={() => setCropBox({ x: 0, y: 0, width: uploadedImage.width, height: uploadedImage.height })}>
                    Full Image
                  </Button>
                </Space>
              </div>

              {/* Color processing options */}
              <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid #eee' }}>
                <label style={{ fontWeight: 'bold' }}>Color Processing:</label>
                <div style={{ marginTop: 8 }}>
                  <Checkbox checked={invertColors} onChange={(e) => setInvertColors(e.target.checked)}>
                    Invert Colors
                  </Checkbox>
                  <p style={{ fontSize: 12, color: '#666', margin: '4px 0 0 24px' }}>
                    Converts colors (white ↔ black, etc.)
                  </p>
                </div>
                <div style={{ marginTop: 12 }}>
                  <Checkbox checked={makeTransparent} onChange={(e) => setMakeTransparent(e.target.checked)}>
                    Make Color Transparent
                  </Checkbox>
                  <p style={{ fontSize: 12, color: '#666', margin: '4px 0 0 24px' }}>
                    Remove a specific color (e.g. white background)
                  </p>
                  {makeTransparent && (
                    <div style={{ marginLeft: 24, marginTop: 8 }}>
                      <div style={{ marginBottom: 8 }}>
                        <label style={{ fontSize: 12 }}>Color to Remove:</label>
                        <div
                          onClick={() => {
                            const inp = document.createElement('input');
                            inp.type = 'color';
                            inp.value = transparentColor;
                            inp.onchange = (ev) => setTransparentColor((ev.target as HTMLInputElement).value);
                            inp.click();
                          }}
                          style={{
                            backgroundColor: transparentColor,
                            width: 60, height: 28, borderRadius: 4,
                            cursor: 'pointer', border: '1px solid #ccc', marginTop: 4,
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: 12 }}>Threshold: {colorThreshold}</label>
                        <Slider min={0} max={100} value={colorThreshold} onChange={setColorThreshold} />
                        <p style={{ fontSize: 11, color: '#999', margin: '4px 0 0 0' }}>
                          How close colors need to match (0 = exact, 100 = very loose)
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Right: Preview */}
            <div style={{ flex: 1 }}>
              <h4>Preview ({width}×{height})</h4>
              <canvas
                ref={previewCanvasRef}
                onClick={handlePreviewClick}
                style={{
                  border: '2px solid #ccc', maxWidth: '100%', maxHeight: 400,
                  display: 'block', cursor: makeTransparent ? 'crosshair' : 'default',
                }}
              />
              <p style={{ fontSize: 12, color: '#666', marginTop: 8 }}>
                Near-black pixels will be skipped (transparent)
                {makeTransparent && <><br />Click on preview to pick a color to remove</>}
              </p>
            </div>
          </div>
        )}
      </Modal>

      {/* ─── WLED Export Modal ───────────────────────────── */}
      <Modal
        title={`Frame ${currentFrame + 1} as WLED JSON`}
        open={exportModalOpen}
        width={700}
        onCancel={() => setExportModalOpen(false)}
        footer={[
          <Button key="copy" icon={<CopyOutlined />} type="primary" onClick={() => {
            navigator.clipboard.writeText(exportedWledJson);
            message.success('Copied to clipboard');
          }}>Copy to Clipboard</Button>,
          <Button key="close" onClick={() => setExportModalOpen(false)}>Close</Button>,
        ]}
      >
        <p style={{ color: '#666', marginBottom: 10 }}>
          Copy this WLED JSON to use with WLED devices:
        </p>
        <Input.TextArea readOnly rows={8} value={exportedWledJson}
          style={{ fontFamily: 'monospace', fontSize: 12 }} />
      </Modal>
    </div>
  );
};

export default SceneEditor;
