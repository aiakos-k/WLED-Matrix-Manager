import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Card, Row, Col, Button, Space, Tag, message, Upload, Popconfirm, Spin } from 'antd';
import {
  PlusOutlined,
  PlayCircleOutlined,
  StopOutlined,
  EditOutlined,
  ExportOutlined,
  DeleteOutlined,
  ImportOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import {
  getScenes,
  playScene,
  stopScene,
  deleteScene,
  exportScene,
  importScene,
  getPlaybackStatus,
  type SceneData,
} from '@/api/client';

/** Draw first frame of scene onto a canvas */
function drawPreview(canvas: HTMLCanvasElement, scene: SceneData) {
  const ctx = canvas.getContext('2d');
  if (!ctx || !scene.frames.length) return;

  const frame = scene.frames[0];
  const w = scene.matrix_width;
  const h = scene.matrix_height;
  canvas.width = w;
  canvas.height = h;

  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, w, h);

  for (const px of frame.pixel_data?.pixels || []) {
    const x = px.index % w;
    const y = Math.floor(px.index / w);
    ctx.fillStyle = `rgb(${px.color[0]},${px.color[1]},${px.color[2]})`;
    ctx.fillRect(x, y, 1, 1);
  }
}

const SceneCard: React.FC<{
  scene: SceneData;
  isPlaying: boolean;
  onPlay: () => void;
  onStop: () => void;
  onEdit: () => void;
  onExport: () => void;
  onDelete: () => void;
}> = ({ scene, isPlaying, onPlay, onStop, onEdit, onExport, onDelete }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (canvasRef.current) drawPreview(canvasRef.current, scene);
  }, [scene]);

  return (
    <Card
      hoverable
      cover={
        <div style={{ background: '#000', display: 'flex', justifyContent: 'center', padding: 8, minHeight: 120 }}>
          <canvas
            ref={canvasRef}
            style={{ imageRendering: 'pixelated', width: '100%', maxWidth: 200, height: 'auto', aspectRatio: '1' }}
          />
        </div>
      }
    >
      <Card.Meta
        title={scene.name}
        description={`${scene.matrix_width} × ${scene.matrix_height}`}
      />
      <div style={{ marginTop: 8 }}>
        <Space size={4} wrap>
          <Tag color="blue">{scene.frame_count} frames</Tag>
          <Tag color={scene.loop_mode === 'loop' ? 'green' : 'orange'}>
            {scene.loop_mode === 'loop' ? 'Loop' : 'Once'}
          </Tag>
        </Space>
      </div>
      <div style={{ marginTop: 12 }}>
        <Space size={4} wrap>
          {isPlaying ? (
            <Button icon={<StopOutlined />} danger onClick={onStop} size="small">
              Stop
            </Button>
          ) : (
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={onPlay} size="small">
              Play
            </Button>
          )}
          <Button icon={<EditOutlined />} onClick={onEdit} size="small">Edit</Button>
          <Button icon={<ExportOutlined />} onClick={onExport} size="small">Export</Button>
          <Popconfirm title="Delete this scene?" onConfirm={onDelete} okText="Yes" cancelText="No">
            <Button icon={<DeleteOutlined />} danger size="small" />
          </Popconfirm>
        </Space>
      </div>
    </Card>
  );
};

const Scenes: React.FC = () => {
  const navigate = useNavigate();
  const [scenes, setScenes] = useState<SceneData[]>([]);
  const [playbacks, setPlaybacks] = useState<Record<string, { is_playing: boolean }>>({});
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [sc, pb] = await Promise.all([getScenes(), getPlaybackStatus()]);
      setScenes(sc);
      setPlaybacks(pb);
    } catch {
      message.error('Failed to load scenes');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [load]);

  const handlePlay = async (id: number) => {
    try {
      await playScene(id);
      message.success('Playback started');
      load();
    } catch {
      message.error('Failed to start playback');
    }
  };

  const handleStop = async (id: number) => {
    try {
      await stopScene(id);
      message.success('Playback stopped');
      load();
    } catch {
      message.error('Failed to stop playback');
    }
  };

  const handleExport = async (id: number, name: string) => {
    try {
      const blob = await exportScene(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${name.replace(/[^a-z0-9_-]/gi, '_')}.ledm`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      message.error('Export failed');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteScene(id);
      message.success('Scene deleted');
      load();
    } catch {
      message.error('Delete failed');
    }
  };

  const handleImport = async (file: File) => {
    try {
      const result = await importScene(file);
      message.success(`Imported: ${result.name}`);
      load();
    } catch {
      message.error('Import failed');
    }
    return false; // Prevent default Upload behavior
  };

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 80 }} />;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Scenes</h2>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/scenes/new')}>
            Create New Scene
          </Button>
          <Upload
            accept=".ledm"
            showUploadList={false}
            beforeUpload={(file) => { handleImport(file); return false; }}
          >
            <Button icon={<ImportOutlined />}>Import Scene</Button>
          </Upload>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        {scenes.map((scene) => (
          <Col key={scene.id} xs={24} sm={12} md={8} lg={6}>
            <SceneCard
              scene={scene}
              isPlaying={!!playbacks[String(scene.id)]?.is_playing}
              onPlay={() => handlePlay(scene.id)}
              onStop={() => handleStop(scene.id)}
              onEdit={() => navigate(`/scenes/${scene.id}/edit`)}
              onExport={() => handleExport(scene.id, scene.name)}
              onDelete={() => handleDelete(scene.id)}
            />
          </Col>
        ))}
        {scenes.length === 0 && (
          <Col span={24}>
            <Card style={{ textAlign: 'center', padding: 48 }}>
              <p>No scenes yet. Create your first pixel art!</p>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/scenes/new')}>
                Create Scene
              </Button>
            </Card>
          </Col>
        )}
      </Row>
    </div>
  );
};

export default Scenes;
