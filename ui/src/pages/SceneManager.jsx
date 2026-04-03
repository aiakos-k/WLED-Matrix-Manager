import { useState, useEffect, useRef } from 'react';
import {
  Button,
  List,
  Space,
  Card,
  Spin,
  Empty,
  Modal,
  message,
  Row,
  Col,
  Tag,
  Upload,
} from 'antd';
import {
  PlayCircleOutlined,
  StopOutlined,
  DeleteOutlined,
  PlusOutlined,
  EditOutlined,
  UploadOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import api from '../services/api';
import { sceneToBinary, binaryToScene } from '../utils/binarySceneFormat';
import { useAuth } from '../hooks/useAuth';

// Animated Preview Canvas Component
const PreviewCanvas = ({ scene, isPlaying, isPreviewMode, onPreviewClick }) => {
  const canvasRef = useRef(null);
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0);

  // Auto-play during actual playback (use frame duration)
  useEffect(() => {
    if (!isPlaying || !scene?.frames || scene.frames.length === 0) {
      console.log(
        `PreviewCanvas: NOT playing. isPlaying=${isPlaying}, frames=${scene?.frames?.length || 0}`
      );
      return;
    }

    const currentFrame = scene.frames[currentFrameIndex];
    const duration = currentFrame?.duration || 5.0;
    const durationMs = Math.max(50, duration * 1000); // Min 50ms

    console.log(
      `PreviewCanvas: Playing frame ${currentFrameIndex}/${scene.frames.length}, duration=${duration}s (${durationMs}ms)`
    );

    const timeout = setTimeout(() => {
      console.log(`PreviewCanvas: Frame timeout, advancing to next`);
      setCurrentFrameIndex((prev) => (prev + 1) % scene.frames.length);
    }, durationMs);

    return () => clearTimeout(timeout);
  }, [isPlaying, currentFrameIndex, scene]);

  // Auto-play during preview mode (faster for browsing)
  useEffect(() => {
    if (!isPreviewMode || !scene?.frames || scene.frames.length === 0) {
      return;
    }

    const currentFrame = scene.frames[currentFrameIndex];
    const duration = currentFrame?.duration || 5.0;
    const previewDurationMs = Math.max(200, duration * 1000 * 0.5); // Half speed for preview

    const timeout = setTimeout(() => {
      setCurrentFrameIndex((prev) => (prev + 1) % scene.frames.length);
    }, previewDurationMs);

    return () => clearTimeout(timeout);
  }, [isPreviewMode, currentFrameIndex, scene]);

  // Draw frame on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !scene?.frames || scene.frames.length === 0) return;

    const ctx = canvas.getContext('2d');
    const pixelSize = 8;

    // Clear canvas
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw current frame
    const frame = scene.frames[currentFrameIndex];
    if (frame?.pixel_data?.pixels) {
      frame.pixel_data.pixels.forEach((pixel) => {
        const [r, g, b] = pixel.color;
        ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
        const x = (pixel.index % scene.matrix_width) * pixelSize;
        const y = Math.floor(pixel.index / scene.matrix_width) * pixelSize;
        ctx.fillRect(x, y, pixelSize, pixelSize);
      });
    }
  }, [currentFrameIndex, scene]);

  const handleCanvasClick = () => {
    if (!isPreviewMode || !scene?.frames) return;
    onPreviewClick?.((prev) => (prev + 1) % scene.frames.length);
    setCurrentFrameIndex((prev) => (prev + 1) % scene.frames.length);
  };

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: '200px',
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#1a1a1a',
        borderRadius: '4px',
      }}
    >
      <canvas
        ref={canvasRef}
        width={scene?.matrix_width * 8}
        height={scene?.matrix_height * 8}
        onClick={handleCanvasClick}
        style={{
          border: '1px solid #ddd',
          borderRadius: '4px',
          maxWidth: '100%',
          maxHeight: '100%',
          objectFit: 'contain',
          cursor: isPreviewMode ? 'pointer' : 'default',
        }}
      />
      {(isPlaying || isPreviewMode) && scene?.frames && scene.frames.length > 0 && (
        <div
          style={{
            position: 'absolute',
            bottom: '8px',
            right: '8px',
            background: 'rgba(0, 0, 0, 0.7)',
            color: 'white',
            padding: '4px 8px',
            borderRadius: '4px',
            fontSize: '12px',
          }}
        >
          {currentFrameIndex + 1} / {scene.frames.length}
        </div>
      )}
    </div>
  );
};

const SceneManager = () => {
  const { isLoggedIn } = useAuth();
  const [scenes, setScenes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [playing, setPlaying] = useState([]); // Array of playing scene IDs
  const [previewMode, setPreviewMode] = useState(null); // sceneId when in preview mode
  const [selectedScene, setSelectedScene] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  // Import/Export states
  const [showImportModal, setShowImportModal] = useState(false);
  const [importedScenes, setImportedScenes] = useState([]);
  const [selectedImportScene, setSelectedImportScene] = useState(null);
  const [importLoading, setImportLoading] = useState(false);

  // Use refs to prevent multiple intervals from being created
  const statusCheckIntervalRef = useRef(null);
  const sceneRefreshIntervalRef = useRef(null);

  useEffect(() => {
    fetchScenesAndStatus();

    // Set up scene refresh interval once on mount (not dependent on playing state)
    sceneRefreshIntervalRef.current = setInterval(() => {
      // Check if any scene is playing, if not refresh
      setPlaying((currentPlaying) => {
        if (currentPlaying.length === 0) {
          console.log('Refreshing scenes (no playback active)');
          fetchScenesAndStatus();
        } else {
          console.log(`Skipping scene refresh (scenes ${currentPlaying.join(', ')} are playing)`);
        }
        return currentPlaying;
      });
    }, 30000); // 30 seconds between refreshes

    return () => {
      if (sceneRefreshIntervalRef.current) {
        clearInterval(sceneRefreshIntervalRef.current);
      }
    };
  }, []); // Empty dependency - only run once on mount

  // Check playback status periodically for all active scenes
  useEffect(() => {
    if (playing.length === 0) {
      // Clear status check interval if no scenes are playing
      if (statusCheckIntervalRef.current) {
        clearInterval(statusCheckIntervalRef.current);
        statusCheckIntervalRef.current = null;
      }
      return;
    }

    // Only create interval if not already running
    if (statusCheckIntervalRef.current) {
      return; // Interval already running
    }

    const checkStatus = async () => {
      // Check each playing scene
      for (const sceneId of playing) {
        try {
          const response = await api.get(`/scenes/${sceneId}/playback-status`);
          const status = response.data || response;

          // If "once" mode and no longer playing, remove from playing list
          if (status.loop_mode === 'once' && !status.is_playing) {
            setPlaying((prev) => prev.filter((id) => id !== sceneId));
          }
        } catch (error) {
          console.error(`Failed to check playback status for scene ${sceneId}:`, error);
        }
      }
    };

    // Check every 2 seconds while playing (reduced from 1 second)
    statusCheckIntervalRef.current = setInterval(checkStatus, 2000);
    return () => {
      // Keep interval running while scenes are playing
      // It will be cleared above when playing.length becomes 0
    };
  }, [playing]);

  const fetchScenes = async () => {
    try {
      const response = await api.get('/scenes/');
      // API returns array directly or wrapped in data
      const scenesArray = Array.isArray(response) ? response : response.data || [];
      setScenes(scenesArray);
    } catch (error) {
      console.error('Failed to fetch scenes:', error);
      message.error('Failed to load scenes');
      setScenes([]); // Set empty array on error
    } finally {
      setLoading(false);
    }
  };

  const fetchScenesAndStatus = async () => {
    try {
      // Fetch all scenes
      const response = await api.get('/scenes/');
      const scenesArray = Array.isArray(response) ? response : response.data || [];
      setScenes(scenesArray);

      // Fetch active playbacks from backend
      try {
        const statusResponse = await api.get('/scenes/playback-status');
        const activeScenesData = Array.isArray(statusResponse)
          ? statusResponse
          : statusResponse.data || [];

        // Extract scene IDs from active playbacks
        const activeSceneIds = activeScenesData
          .filter((status) => status.is_playing)
          .map((status) => status.scene_id);

        console.log('Active scenes from backend:', activeSceneIds);
        setPlaying(activeSceneIds);
      } catch (statusError) {
        console.error('Failed to fetch playback status:', statusError);
        // Don't fail entirely if status endpoint doesn't exist
      }
    } catch (error) {
      console.error('Failed to fetch scenes:', error);
      message.error('Failed to load scenes');
      setScenes([]);
    } finally {
      setLoading(false);
    }
  };

  const handlePlayScene = async (sceneId, sceneDevices) => {
    console.log(`=== handlePlayScene called for scene ${sceneId}`);
    // Check if scene has devices
    if (!sceneDevices || sceneDevices.length === 0) {
      console.log('WARNING: No devices for this scene');
      message.warning(
        'Scene has no assigned devices. Please edit the scene to add devices before playing.'
      );
      return;
    }

    try {
      console.log(`Sending POST to /api/scenes/${sceneId}/play`);
      await api.post(`/scenes/${sceneId}/play`, {
        loop_mode: 'once',
      });
      console.log(`API call successful, adding scene ${sceneId} to playing list`);
      setPlaying((prev) => [...prev, sceneId]);
      message.success('Scene started');
    } catch (error) {
      console.error('=== PLAY SCENE ERROR ===', error);
      message.error('Failed to start scene');
    }
  };

  const handleStopScene = async (sceneId) => {
    try {
      await api.post(`/scenes/${sceneId}/stop`, {});
      setPlaying((prev) => prev.filter((id) => id !== sceneId));
      message.success('Scene stopped');
    } catch (error) {
      console.error('Failed to stop scene:', error);
      message.error('Failed to stop scene');
    }
  };

  const handleDeleteScene = (sceneId) => {
    Modal.confirm({
      title: 'Delete Scene',
      content: 'Are you sure you want to delete this scene?',
      okText: 'Delete',
      cancelText: 'Cancel',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await api.delete(`/scenes/${sceneId}`);
          setScenes(scenes.filter((s) => s.id !== sceneId));
          message.success('Scene deleted');
        } catch (error) {
          console.error('Failed to delete scene:', error);
          message.error('Failed to delete scene');
        }
      },
    });
  };

  const handleImportFile = async (file) => {
    try {
      setImportLoading(true);
      console.log('Loading import file:', file.name);

      // Check file extension to determine format
      const fileName = file.name.toLowerCase();
      let sceneData;

      if (fileName.endsWith('.ledm')) {
        // Binary format
        console.log('Detected binary format (.ledm)');
        const arrayBuffer = await file.arrayBuffer();
        sceneData = binaryToScene(arrayBuffer);
        message.success('Binary Scene file (.ledm) loaded successfully');
      } else if (fileName.endsWith('.json')) {
        // JSON format (backward compatibility)
        console.log('Detected JSON format');
        const text = await file.text();
        sceneData = JSON.parse(text);
        message.success('JSON Scene file loaded successfully');
      } else {
        throw new Error('Unsupported file format. Please use .ledm (binary) or .json files.');
      }

      setImportedScenes([sceneData]);
      setSelectedImportScene(sceneData);
    } catch (error) {
      console.error('Failed to parse import file:', error);
      message.error('Failed to parse file: ' + error.message);
    } finally {
      setImportLoading(false);
    }
    return false;
  };

  const handleConfirmImport = async () => {
    if (!selectedImportScene) {
      message.error('Please select a scene to import');
      return;
    }

    try {
      setImportLoading(true);

      // Prepare scene data - only include fields that the backend expects
      // Generate unique_id if not provided (from binary export)
      const generateUniqueId = (name) => {
        return (name || 'scene')
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '_')
          .substring(0, 50);
      };

      const sceneData = {
        name: selectedImportScene.name,
        unique_id: selectedImportScene.unique_id || generateUniqueId(selectedImportScene.name),
        description: selectedImportScene.description,
        matrix_width: selectedImportScene.matrix_width || 16,
        matrix_height: selectedImportScene.matrix_height || 16,
        default_frame_duration: selectedImportScene.default_frame_duration || 1.0,
        loop_mode: selectedImportScene.loop_mode || 'once',
        device_ids: selectedImportScene.device_ids || [], // Use exported device_ids if available, otherwise empty
      };

      console.log('Creating scene with data:', sceneData);

      // Create the scene
      const sceneResponse = await api.post('/scenes/', sceneData);
      const newScene = sceneResponse.data || sceneResponse;
      const sceneId = newScene.id;

      console.log('Scene created:', newScene);

      // Import frames if they exist in the exported data
      if (selectedImportScene.frames && selectedImportScene.frames.length > 0) {
        console.log('Importing frames:', selectedImportScene.frames.length);

        for (const frame of selectedImportScene.frames) {
          try {
            const frameData = {
              frame_index: frame.frame_index,
              pixel_data: frame.pixel_data,
              duration: frame.duration,
              brightness: frame.brightness,
              color_r: frame.color_r || 100,
              color_g: frame.color_g || 100,
              color_b: frame.color_b || 100,
            };
            console.log('Importing frame:', frameData.frame_index);

            // Try to update existing frame if it's index 0 (created by default)
            if (frame.frame_index === 0) {
              await api.patch(`/scenes/${sceneId}/frames`, frameData);
            } else {
              await api.post(`/scenes/${sceneId}/frames`, frameData);
            }
          } catch (frameError) {
            console.error('Error importing frame:', frameError);
            // Continue with next frame if one fails
          }
        }
      }

      message.success('Scene imported successfully with all frames');
      setShowImportModal(false);
      setImportedScenes([]);
      setSelectedImportScene(null);
      await fetchScenes();
    } catch (error) {
      console.error('Failed to import scene:', error);
      message.error('Failed to import scene: ' + (error.message || 'Unknown error'));
    } finally {
      setImportLoading(false);
    }
  };

  const handleExportScene = (scene) => {
    try {
      console.log('Exporting scene to binary format:', scene.name);
      const binaryData = sceneToBinary(scene);
      const blob = new Blob([binaryData], { type: 'application/octet-stream' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${scene.unique_id || scene.name}_${new Date().getTime()}.ledm`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success(
        `Scene exported successfully (Binary format, ${(blob.size / 1024).toFixed(1)}KB)`
      );
    } catch (error) {
      console.error('Failed to export scene:', error);
      message.error('Failed to export scene');
    }
  };

  const handleSelectScene = (scene) => {
    setSelectedScene(scene);
    setShowDetailModal(true);
  };

  if (loading) {
    return <Spin />;
  }

  return (
    <div style={{ padding: '20px' }}>
      <Row gutter={[16, 16]} style={{ marginBottom: '20px' }}>
        <Col span={24}>
          <Space>
            <h2>Scenes</h2>
            {isLoggedIn && (
              <>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => (window.location.href = '/create-scene')}
                >
                  Create New Scene
                </Button>
                <Button icon={<UploadOutlined />} onClick={() => setShowImportModal(true)}>
                  Import Scene
                </Button>
              </>
            )}
          </Space>
        </Col>
      </Row>

      {scenes.length === 0 ? (
        <Empty description="No scenes available. Create one to get started!" />
      ) : (
        <List
          grid={{ gutter: 16, xs: 1, sm: 1, md: 2, lg: 3 }}
          dataSource={scenes}
          renderItem={(scene) => (
            <List.Item>
              <Card
                hoverable
                onClick={() => handleSelectScene(scene)}
                style={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  borderColor: playing.includes(scene.id)
                    ? '#1890ff'
                    : previewMode === scene.id
                      ? '#faad14'
                      : undefined,
                  borderWidth: playing.includes(scene.id) || previewMode === scene.id ? 3 : 1,
                }}
                bodyStyle={{ display: 'flex', flexDirection: 'column', flex: 1 }}
              >
                {/* Animated Preview Canvas */}
                <PreviewCanvas
                  scene={scene}
                  isPlaying={playing.includes(scene.id)}
                  isPreviewMode={previewMode === scene.id}
                />

                <div style={{ marginBottom: '12px', marginTop: '12px' }}>
                  <h3>{scene.name}</h3>
                  <p style={{ color: '#666', margin: 0 }}>
                    {scene.matrix_width} × {scene.matrix_height}
                  </p>
                  <p
                    style={{
                      color: scene.devices && scene.devices.length > 0 ? '#52c41a' : '#d9d9d9',
                      margin: '4px 0 0 0',
                      fontSize: '13px',
                    }}
                  >
                    📱{' '}
                    {scene.devices && scene.devices.length > 0
                      ? scene.devices.map((d) => d.name).join(', ')
                      : 'No devices assigned'}
                  </p>
                  <Space style={{ marginTop: '8px' }}>
                    <Tag color="blue">{scene.frame_count} frames</Tag>
                    <Tag color={scene.loop_mode === 'loop' ? 'orange' : 'green'}>
                      {scene.loop_mode === 'loop' ? '🔄 Loop' : '▶️ Once'}
                    </Tag>
                    {playing.includes(scene.id) && <Tag color="red">▶️ PLAYING</Tag>}
                  </Space>
                </div>

                {scene.description && (
                  <p style={{ color: '#999', fontSize: '12px', margin: '8px 0' }}>
                    {scene.description}
                  </p>
                )}

                <Space style={{ marginTop: 'auto', paddingTop: '12px' }} wrap>
                  {playing.includes(scene.id) ? (
                    <Button
                      danger
                      icon={<StopOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleStopScene(scene.id);
                      }}
                    >
                      Stop
                    </Button>
                  ) : (
                    <Button
                      type={scene.devices && scene.devices.length > 0 ? 'primary' : 'default'}
                      danger={!(scene.devices && scene.devices.length > 0)}
                      icon={<PlayCircleOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        handlePlayScene(scene.id, scene.devices);
                      }}
                      disabled={!scene.devices || scene.devices.length === 0}
                      style={!scene.devices || scene.devices.length === 0 ? { opacity: 0.6 } : {}}
                    >
                      Play
                    </Button>
                  )}
                  {previewMode === scene.id ? (
                    <Button
                      type="dashed"
                      danger
                      onClick={(e) => {
                        e.stopPropagation();
                        setPreviewMode(null);
                      }}
                    >
                      Stop Preview
                    </Button>
                  ) : (
                    <Button
                      onClick={(e) => {
                        e.stopPropagation();
                        setPreviewMode(scene.id);
                      }}
                      disabled={playing.includes(scene.id)}
                      style={playing.includes(scene.id) ? { opacity: 0.6 } : {}}
                    >
                      Start Preview
                    </Button>
                  )}{' '}
                  {isLoggedIn && (
                    <>
                      <Button
                        icon={<EditOutlined />}
                        onClick={(e) => {
                          e.stopPropagation();
                          window.location.href = `/create-scene?edit=${scene.id}`;
                        }}
                      >
                        Edit
                      </Button>
                      <Button
                        icon={<DownloadOutlined />}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleExportScene(scene);
                        }}
                      >
                        Export
                      </Button>
                      <Button
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteScene(scene.id);
                        }}
                      />
                    </>
                  )}
                </Space>
              </Card>
            </List.Item>
          )}
        />
      )}

      {selectedScene && (
        <Modal
          title={selectedScene.name}
          open={showDetailModal}
          onCancel={() => setShowDetailModal(false)}
          footer={null}
          width={800}
        >
          <div style={{ marginBottom: '16px' }}>
            <p>
              <strong>Size:</strong> {selectedScene.matrix_width} × {selectedScene.matrix_height}
            </p>
            <p>
              <strong>Frames:</strong> {selectedScene.frame_count}
            </p>
            <p>
              <strong>Default Duration:</strong> {selectedScene.default_frame_duration}s per frame
            </p>
            {selectedScene.description && (
              <p>
                <strong>Description:</strong> {selectedScene.description}
              </p>
            )}
          </div>
        </Modal>
      )}

      {/* Import Modal */}
      <Modal
        title="Import Scene"
        open={showImportModal}
        onCancel={() => {
          setShowImportModal(false);
          setImportedScenes([]);
          setSelectedImportScene(null);
        }}
        onOk={handleConfirmImport}
        confirmLoading={importLoading}
        width={700}
      >
        <div style={{ marginBottom: '20px' }}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
              Upload exported scene file to restore (.ledm or .json):
            </label>
            <Upload
              accept=".ledm,.json"
              beforeUpload={handleImportFile}
              maxCount={1}
              onRemove={() => {
                setImportedScenes([]);
                setSelectedImportScene(null);
              }}
            >
              <Button icon={<UploadOutlined />}>Click to upload scene file</Button>
            </Upload>
          </div>

          {importedScenes.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
                Select Scene to Import:
              </label>
              <div
                style={{
                  maxHeight: '300px',
                  overflowY: 'auto',
                  border: '1px solid #d9d9d9',
                  borderRadius: '4px',
                }}
              >
                {importedScenes.map((scene, idx) => (
                  <div
                    key={idx}
                    onClick={() => setSelectedImportScene(scene)}
                    style={{
                      padding: '12px',
                      borderBottom: idx < importedScenes.length - 1 ? '1px solid #f0f0f0' : 'none',
                      cursor: 'pointer',
                      backgroundColor: selectedImportScene === scene ? '#e6f7ff' : '#fafafa',
                    }}
                  >
                    <div style={{ fontWeight: 'bold' }}>{scene.name}</div>
                    {scene.unique_id && (
                      <div style={{ fontSize: '12px', color: '#666' }}>ID: {scene.unique_id}</div>
                    )}
                    {scene.description && (
                      <div style={{ fontSize: '12px', color: '#999' }}>{scene.description}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};

export default SceneManager;
