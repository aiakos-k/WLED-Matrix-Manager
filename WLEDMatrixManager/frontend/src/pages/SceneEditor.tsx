import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Button, Card, Col, Collapse, Divider, Form, Input, InputNumber,
  message, Modal, Radio, Row, Select, Slider, Space, Tooltip, Upload,
} from 'antd';
import {
  SaveOutlined, PlayCircleOutlined, DeleteOutlined, PlusOutlined,
  UploadOutlined, StopOutlined, ArrowLeftOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import {
  createScene, getScene, updateScene, getDevices, playScene, stopScene,
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

type Pixel = { index: number; color: number[] };

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
  const [selectedPixels, setSelectedPixels] = useState<Set<number>>(new Set());
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);

  // Devices
  const [devices, setDevices] = useState<DeviceData[]>([]);
  const [selectedDevices, setSelectedDevices] = useState<number[]>([]);
  const [loopMode, setLoopMode] = useState<string>('once');

  // WLED JSON import
  const [wledJson, setWledJson] = useState('');

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

    // Grid
    ctx.strokeStyle = 'rgba(255,255,255,0.1)';
    ctx.lineWidth = 0.5;
    for (let x = 0; x <= width; x++) {
      ctx.beginPath();
      ctx.moveTo(x * cellSize, 0);
      ctx.lineTo(x * cellSize, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y <= height; y++) {
      ctx.beginPath();
      ctx.moveTo(0, y * cellSize);
      ctx.lineTo(canvas.width, y * cellSize);
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
      if (color) setSelectedColor(rgbToHex(color[0], color[1], color[2]));
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

        // Collect selected pixels with their colors
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

        // Remove old positions, set new ones
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

        // Update selection
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

  // ─── Image Upload ───────────────────────────────────────

  const handleImageUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const resp = await fetch(`/api/image/convert?width=${width}&height=${height}&colors=256`, {
        method: 'POST',
        body: formData,
      });
      if (!resp.ok) throw new Error('Upload failed');
      const data = await resp.json();
      setFrames((prev) => {
        const next = [...prev];
        next[currentFrame] = {
          ...next[currentFrame],
          pixel_data: { pixels: data.pixels, width, height },
        };
        return next;
      });
      message.success(`Imported ${data.pixels.length} pixels from image`);
    } catch {
      message.error('Image conversion failed');
    }
    return false;
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
    // Create temporary scene and play
    const tempScene: SceneCreate = {
      name: '__temp_test__',
      matrix_width: width,
      matrix_height: height,
      default_frame_duration: 5,
      loop_mode: 'once',
      device_ids: selectedDevices,
      frames: [frames[currentFrame]],
    };
    try {
      const created = await createScene(tempScene);
      await playScene(created.id, selectedDevices);
      message.success('Test frame sent to device');
    } catch {
      message.error('Failed to test frame');
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
    // Update all frames' pixel_data dimensions
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

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/scenes')}>Back</Button>
          <h2 style={{ margin: 0 }}>{isEdit ? 'Edit Scene' : 'Create Scene'}</h2>
        </Space>
        <Space>
          <Button icon={<PlayCircleOutlined />} onClick={testFrame}>Test Frame</Button>
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
                onChange={(e) => setSelectedColor(e.target.value)}
                style={{ width: '100%', height: 32, cursor: 'pointer', border: 'none' }}
              />
            </div>
            <div style={{ marginBottom: 8 }}>
              <label>Common Colors:</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {COMMON_COLORS.map((c) => (
                  <div key={c}
                    onClick={() => setSelectedColor(c)}
                    style={{
                      width: 24, height: 24, background: c, cursor: 'pointer',
                      border: selectedColor === c ? '2px solid #1890ff' : '1px solid #ccc',
                      borderRadius: 2,
                    }}
                  />
                ))}
              </div>
            </div>
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
            label: 'Import WLED JSON',
            children: (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Input.TextArea value={wledJson} onChange={(e) => setWledJson(e.target.value)}
                  rows={3} placeholder='{"seg":{"i":[...]}}' />
                <Button block onClick={importWledJson}>Import</Button>
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

          <Card title="Frames" size="small">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ maxHeight: 300, overflow: 'auto' }}>
                {frames.map((f, i) => (
                  <div key={i} onClick={() => setCurrentFrame(i)}
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
        </Col>
      </Row>
    </div>
  );
};

export default SceneEditor;
