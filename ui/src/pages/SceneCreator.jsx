import React, { useState, useRef, useEffect } from 'react';
import {
  Form,
  Input,
  InputNumber,
  Button,
  Space,
  Card,
  Row,
  Col,
  Select,
  message,
  Upload,
  Slider,
  Divider,
  Modal,
  Radio,
  Tooltip,
  Collapse,
} from 'antd';
import {
  UploadOutlined,
  SaveOutlined,
  PlayCircleOutlined,
  DeleteOutlined,
  PlusOutlined,
  StopOutlined,
} from '@ant-design/icons';
import api from '../services/api';
import { useNavigate } from 'react-router-dom';
import { parseWledJsonString } from '../utils/wledParser';
import { useAuth } from '../hooks/useAuth';

// Common colors palette
const COMMON_COLORS = [
  '#FF0000', // Red
  '#00FF00', // Green
  '#0000FF', // Blue
  '#FFFF00', // Yellow
  '#FF00FF', // Magenta
  '#00FFFF', // Cyan
  '#FFFFFF', // White
  '#FFA500', // Orange
  '#800080', // Purple
  '#FFC0CB', // Pink
];

const SceneCreator = () => {
  const { isLoggedIn, isLoading } = useAuth();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [matrixSize, setMatrixSize] = useState({ width: 16, height: 16 });
  const [devices, setDevices] = useState([]);
  const [selectedDevices, setSelectedDevices] = useState([]);
  const [frames, setFrames] = useState([]);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [pixelData, setPixelData] = useState({});
  const [selectedColor, setSelectedColor] = useState('#FF0000');
  const [frameBrightness, setFrameBrightness] = useState({}); // Per-frame brightness
  const [frameColorR, setFrameColorR] = useState({}); // Per-frame red intensity (0-100)
  const [frameColorG, setFrameColorG] = useState({}); // Per-frame green intensity (0-100)
  const [frameColorB, setFrameColorB] = useState({}); // Per-frame blue intensity (0-100)
  const [frameDurations, setFrameDurations] = useState({}); // Per-frame duration
  const [recentColors, setRecentColors] = useState([]); // Track recently used colors
  const [selectedPixels, setSelectedPixels] = useState(new Set()); // For multi-select
  const canvasRef = useRef(null);
  const [editingSceneId, setEditingSceneId] = useState(null);
  const [isEditMode, setIsEditMode] = useState(false);
  const [loopMode, setLoopMode] = useState('once');
  // Image upload modal states
  const [showImageModal, setShowImageModal] = useState(false);
  const [uploadedImage, setUploadedImage] = useState(null);
  const [cropBox, setCropBox] = useState({ x: 0, y: 0, width: 100, height: 100 });
  const [previewPixels, setPreviewPixels] = useState(null);
  const [invertColors, setInvertColors] = useState(false);
  const [makeTransparent, setMakeTransparent] = useState(false);
  const [transparentColor, setTransparentColor] = useState('#FFFFFF'); // Default white
  const [colorThreshold, setColorThreshold] = useState(30); // Threshold for transparency
  const imageCanvasRef = useRef(null);
  const previewCanvasRef = useRef(null);
  const [wledJsonInput, setWledJsonInput] = useState('');

  // Check authentication
  useEffect(() => {
    // Wait until auth is loaded before checking
    if (isLoading) return;

    if (!isLoggedIn) {
      message.error('Please login to create scenes');
      navigate('/login');
    }
  }, [isLoggedIn, isLoading, navigate]);

  // Load devices on mount and check if editing

  React.useEffect(() => {
    fetchDevices();

    // Check if we're editing an existing scene
    const params = new URLSearchParams(window.location.search);
    const sceneIdParam = params.get('edit');
    if (sceneIdParam) {
      setEditingSceneId(Number(sceneIdParam));
      setIsEditMode(true);
      loadSceneForEditing(Number(sceneIdParam));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Draw canvas when frame changes
  React.useEffect(() => {
    drawCanvas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentFrame, pixelData, matrixSize, selectedPixels]);

  // Handle keyboard events for arrow keys (move selected pixels)

  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if (selectedPixels.size === 0) return;

      if (e.key === 'ArrowUp') {
        e.preventDefault();
        moveSelectedPixels(0, -1);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        moveSelectedPixels(0, 1);
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        moveSelectedPixels(-1, 0);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        moveSelectedPixels(1, 0);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPixels, currentFrame, pixelData, matrixSize]);

  const fetchDevices = async () => {
    try {
      const response = await api.get('/devices/');
      const devicesArray = Array.isArray(response) ? response : response.data || [];
      setDevices(devicesArray);
    } catch (error) {
      console.error('Failed to fetch devices:', error);
      message.error('Failed to load devices');
    }
  };

  const loadSceneForEditing = async (sceneId) => {
    try {
      const response = await api.get(`/scenes/${sceneId}`);
      const scene = response.data || response;

      console.log('DEBUG: Scene loaded:', scene);
      console.log('DEBUG: scene.devices:', scene.devices);
      console.log(
        'DEBUG: scene.devices length:',
        scene.devices ? scene.devices.length : 'undefined'
      );

      // Set form values
      form.setFieldsValue({
        name: scene.name,
        unique_id: scene.unique_id,
        description: scene.description,
        matrix_width: scene.matrix_width,
        matrix_height: scene.matrix_height,
        default_frame_duration: scene.default_frame_duration,
      });

      // Set loop mode from scene
      if (scene.loop_mode) {
        setLoopMode(scene.loop_mode);
      }

      // Set matrix size
      setMatrixSize({
        width: scene.matrix_width,
        height: scene.matrix_height,
      });

      // Set selected devices (ensure it's an array)
      const devicesToSet =
        scene.devices && scene.devices.length > 0 ? scene.devices.map((d) => d.id) : [];
      console.log('DEBUG: Setting selectedDevices to:', devicesToSet);
      setSelectedDevices(devicesToSet);

      // Load frames into pixelData
      const newPixelData = {};
      const newFrameBrightness = {};
      const newFrameColorR = {};
      const newFrameColorG = {};
      const newFrameColorB = {};
      const newFrameDurations = {};
      scene.frames.forEach((frame) => {
        if (frame.pixel_data && frame.pixel_data.pixels) {
          frame.pixel_data.pixels.forEach((pixel) => {
            const key = `${frame.frame_index}-${pixel.index}`;
            const [r, g, b] = pixel.color;
            const hex = `#${r.toString(16).padStart(2, '0')}${g
              .toString(16)
              .padStart(2, '0')}${b.toString(16).padStart(2, '0')}`.toUpperCase();
            newPixelData[key] = hex;
          });
        }
        // Load brightness for each frame
        if (frame.brightness) {
          newFrameBrightness[frame.frame_index] = frame.brightness;
        }
        // Load color intensities for each frame
        newFrameColorR[frame.frame_index] = frame.color_r || 10;
        newFrameColorG[frame.frame_index] = frame.color_g || 10;
        newFrameColorB[frame.frame_index] = frame.color_b || 10;
        // Load duration for each frame
        if (frame.duration) {
          newFrameDurations[frame.frame_index] = frame.duration;
        }
      });
      setPixelData(newPixelData);
      setFrameBrightness(newFrameBrightness);
      setFrameColorR(newFrameColorR);
      setFrameColorG(newFrameColorG);
      setFrameColorB(newFrameColorB);
      setFrameDurations(newFrameDurations);

      // Set frames count
      setFrames(Array.from({ length: scene.frames.length }, (_, i) => i));
      setCurrentFrame(0);

      message.success('Scene loaded for editing');
    } catch (error) {
      console.error('Failed to load scene:', error);
      message.error('Failed to load scene for editing');
    }
  };

  const drawCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const pixelSize = 30;
    const { width, height } = matrixSize;

    canvas.width = width * pixelSize;
    canvas.height = height * pixelSize;

    // Draw grid and pixels
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const index = y * width + x;
        const key = `${currentFrame}-${index}`;
        const color = pixelData[key] || '#000000';

        // Draw pixel
        ctx.fillStyle = color;
        ctx.fillRect(x * pixelSize, y * pixelSize, pixelSize, pixelSize);

        // Draw grid
        ctx.strokeStyle = '#ccc';
        ctx.lineWidth = 1;
        ctx.strokeRect(x * pixelSize, y * pixelSize, pixelSize, pixelSize);

        // Highlight selected pixels
        if (selectedPixels.has(index)) {
          ctx.strokeStyle = '#00FF00';
          ctx.lineWidth = 3;
          ctx.strokeRect(x * pixelSize, y * pixelSize, pixelSize, pixelSize);
        }
      }
    }
  };

  const handleCanvasClick = (e) => {
    // Ignore right-click here (handled by handleCanvasMouseDown)
    if (e.button === 2) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const { width, height } = matrixSize;

    // Calculate actual pixel size based on rendered canvas dimensions
    const actualPixelWidth = rect.width / width;
    const actualPixelHeight = rect.height / height;

    const x = Math.floor((e.clientX - rect.left) / actualPixelWidth);
    const y = Math.floor((e.clientY - rect.top) / actualPixelHeight);

    if (x >= 0 && x < width && y >= 0 && y < height) {
      const index = y * width + x;

      // Linksklick: normales Malen
      if (e.button === 0) {
        // Multi-select mit Strg
        if (e.ctrlKey) {
          setSelectedPixels((prev) => {
            const newSet = new Set(prev);
            if (newSet.has(index)) {
              newSet.delete(index);
            } else {
              newSet.add(index);
            }
            return newSet;
          });
        } else {
          const key = `${currentFrame}-${index}`;
          setPixelData((prev) => ({
            ...prev,
            [key]: selectedColor,
          }));
          // Deselect all when painting
          setSelectedPixels(new Set());
        }
      }
    }
  };

  const handleCanvasMouseDown = (e) => {
    // Handle right-click to pick color
    if (e.button === 2) {
      e.preventDefault();
      const canvas = canvasRef.current;
      const rect = canvas.getBoundingClientRect();
      const { width, height } = matrixSize;

      // Calculate actual pixel size based on rendered canvas dimensions
      const actualPixelWidth = rect.width / width;
      const actualPixelHeight = rect.height / height;

      const x = Math.floor((e.clientX - rect.left) / actualPixelWidth);
      const y = Math.floor((e.clientY - rect.top) / actualPixelHeight);

      if (x >= 0 && x < width && y >= 0 && y < height) {
        const index = y * width + x;
        const key = `${currentFrame}-${index}`;
        const pixelColor = pixelData[key] || '#000000';
        setSelectedColor(pixelColor);
        addRecentColor(pixelColor);
      }
    }
  };

  const addRecentColor = (color) => {
    setRecentColors((prev) => {
      const filtered = prev.filter((c) => c !== color);
      return [color, ...filtered].slice(0, 5);
    });
  };

  const moveSelectedPixels = (dx, dy) => {
    if (selectedPixels.size === 0) return;

    const { width, height } = matrixSize;
    const newPixelData = { ...pixelData };
    const newSelectedPixels = new Set();
    const movedPixels = new Map(); // Track old -> new positions

    // First pass: calculate all new positions and collect data
    selectedPixels.forEach((index) => {
      const x = index % width;
      const y = Math.floor(index / width);
      const newX = x + dx;
      const newY = y + dy;

      // Check bounds
      if (newX >= 0 && newX < width && newY >= 0 && newY < height) {
        const newIndex = newY * width + newX;
        const oldKey = `${currentFrame}-${index}`;
        movedPixels.set(oldKey, {
          newIndex,
          newKey: `${currentFrame}-${newIndex}`,
          data: newPixelData[oldKey],
        });
      }
    });

    // Second pass: remove all old positions first
    movedPixels.forEach(({ newKey: _newKey, data: _data }, oldKey) => {
      delete newPixelData[oldKey];
    });

    // Third pass: set all new positions
    movedPixels.forEach(({ newIndex, newKey, data }) => {
      newPixelData[newKey] = data;
      newSelectedPixels.add(newIndex);
    });

    setPixelData(newPixelData);
    setSelectedPixels(newSelectedPixels);
  };

  const handleImageUpload = (file) => {
    if (!file) return false;

    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        // Store image and show modal
        setUploadedImage({
          src: e.target.result,
          width: img.width,
          height: img.height,
        });
        // Initialize crop box to center with square aspect
        const size = Math.min(img.width, img.height);
        setCropBox({
          x: (img.width - size) / 2,
          y: (img.height - size) / 2,
          width: size,
          height: size,
        });
        setShowImageModal(true);
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
    return false;
  };

  // Crop box mouse event handlers
  const handleCropBoxMouseDown = (e, handle) => {
    if (!imageCanvasRef.current || !uploadedImage) return;

    e.stopPropagation();
    e.preventDefault();

    const rect = imageCanvasRef.current.getBoundingClientRect();
    const dragStartData = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      cropX: cropBox.x,
      cropY: cropBox.y,
      cropWidth: cropBox.width,
      cropHeight: cropBox.height,
      handle: handle,
      rect: rect,
    };

    const handleMouseMove = (moveEvent) => {
      const currentX = moveEvent.clientX - dragStartData.rect.left;
      const currentY = moveEvent.clientY - dragStartData.rect.top;
      const deltaX = currentX - dragStartData.x;
      const deltaY = currentY - dragStartData.y;

      const imageScaleX = dragStartData.rect.width / uploadedImage.width;
      const imageScaleY = dragStartData.rect.height / uploadedImage.height;

      let newCropBox = { ...cropBox };
      const minSize = 10;

      if (!dragStartData.handle) {
        // Move the entire box
        newCropBox.x = Math.max(
          0,
          Math.min(
            uploadedImage.width - dragStartData.cropWidth,
            dragStartData.cropX + deltaX / imageScaleX
          )
        );
        newCropBox.y = Math.max(
          0,
          Math.min(
            uploadedImage.height - dragStartData.cropHeight,
            dragStartData.cropY + deltaY / imageScaleY
          )
        );
      } else {
        // Resize from handle
        switch (dragStartData.handle) {
          case 'nw': // Northwest
            newCropBox.x = Math.max(0, dragStartData.cropX + deltaX / imageScaleX);
            newCropBox.y = Math.max(0, dragStartData.cropY + deltaY / imageScaleY);
            newCropBox.width = Math.max(minSize, dragStartData.cropWidth - deltaX / imageScaleX);
            newCropBox.height = Math.max(minSize, dragStartData.cropHeight - deltaY / imageScaleY);
            break;
          case 'ne': // Northeast
            newCropBox.y = Math.max(0, dragStartData.cropY + deltaY / imageScaleY);
            newCropBox.width = Math.max(minSize, dragStartData.cropWidth + deltaX / imageScaleX);
            newCropBox.height = Math.max(minSize, dragStartData.cropHeight - deltaY / imageScaleY);
            break;
          case 'sw': // Southwest
            newCropBox.x = Math.max(0, dragStartData.cropX + deltaX / imageScaleX);
            newCropBox.width = Math.max(minSize, dragStartData.cropWidth - deltaX / imageScaleX);
            newCropBox.height = Math.max(minSize, dragStartData.cropHeight + deltaY / imageScaleY);
            break;
          case 'se': // Southeast
            newCropBox.width = Math.max(minSize, dragStartData.cropWidth + deltaX / imageScaleX);
            newCropBox.height = Math.max(minSize, dragStartData.cropHeight + deltaY / imageScaleY);
            break;
          case 'n': // North
            newCropBox.y = Math.max(0, dragStartData.cropY + deltaY / imageScaleY);
            newCropBox.height = Math.max(minSize, dragStartData.cropHeight - deltaY / imageScaleY);
            break;
          case 's': // South
            newCropBox.height = Math.max(minSize, dragStartData.cropHeight + deltaY / imageScaleY);
            break;
          case 'e': // East
            newCropBox.width = Math.max(minSize, dragStartData.cropWidth + deltaX / imageScaleX);
            break;
          case 'w': // West
            newCropBox.x = Math.max(0, dragStartData.cropX + deltaX / imageScaleX);
            newCropBox.width = Math.max(minSize, dragStartData.cropWidth - deltaX / imageScaleX);
            break;
          default:
            break;
        }

        // Ensure crop box stays within bounds
        newCropBox.x = Math.max(0, Math.min(newCropBox.x, uploadedImage.width - newCropBox.width));
        newCropBox.y = Math.max(
          0,
          Math.min(newCropBox.y, uploadedImage.height - newCropBox.height)
        );
        newCropBox.width = Math.min(newCropBox.width, uploadedImage.width - newCropBox.x);
        newCropBox.height = Math.min(newCropBox.height, uploadedImage.height - newCropBox.y);
      }

      setCropBox(newCropBox);
    };

    const handleMouseUp = () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  // Update preview when crop box changes or processing options change
  React.useEffect(() => {
    if (!uploadedImage || !previewCanvasRef.current) return;

    const canvas = previewCanvasRef.current;
    const ctx = canvas.getContext('2d');
    const img = new Image();
    img.onload = () => {
      const { width, height } = matrixSize;
      const scaleFactor = 15;
      canvas.width = width * scaleFactor; // Scale up for preview
      canvas.height = height * scaleFactor;

      // Draw the cropped region scaled to matrix size
      ctx.drawImage(
        img,
        cropBox.x,
        cropBox.y,
        cropBox.width,
        cropBox.height,
        0,
        0,
        canvas.width,
        canvas.height
      );

      // Get pixel data from the SCALED canvas and downsample to matrix size
      const scaledImageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const scaledPixels = scaledImageData.data;

      // Downsample from scaled canvas back to matrix size
      const pixels = [];
      for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
          // Get center pixel from each cell
          const scaledX = Math.floor(x * scaleFactor + scaleFactor / 2);
          const scaledY = Math.floor(y * scaleFactor + scaleFactor / 2);
          const pixelIndex = (scaledY * canvas.width + scaledX) * 4;

          let r = scaledPixels[pixelIndex];
          let g = scaledPixels[pixelIndex + 1];
          let b = scaledPixels[pixelIndex + 2];

          // Apply color inversion if enabled
          if (invertColors) {
            r = 255 - r;
            g = 255 - g;
            b = 255 - b;
          }

          pixels.push([r, g, b]);
        }
      }
      setPreviewPixels(pixels);
    };
    img.src = uploadedImage.src;
  }, [uploadedImage, cropBox, matrixSize, invertColors, transparentColor, makeTransparent]);

  const handlePreviewCanvasClick = (e) => {
    if (!makeTransparent || !previewCanvasRef.current || !previewPixels) return;

    const canvas = previewCanvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const { width, height } = matrixSize;
    const scaleFactor = 15;

    // Get click position relative to canvas
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Convert to matrix pixel coordinates
    const pixelX = Math.floor(x / scaleFactor);
    const pixelY = Math.floor(y / scaleFactor);

    if (pixelX >= 0 && pixelX < width && pixelY >= 0 && pixelY < height) {
      const index = pixelY * width + pixelX;
      if (previewPixels[index]) {
        const [r, g, b] = previewPixels[index];
        const hex =
          `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`.toUpperCase();
        setTransparentColor(hex);
      }
    }
  };

  const applyImageToCanvas = () => {
    if (!previewPixels) return;

    const newPixelData = { ...pixelData };

    // Parse transparent color if enabled
    let transparentR = 255,
      transparentG = 255,
      transparentB = 255;
    if (makeTransparent) {
      const transparentHex = transparentColor.replace('#', '');
      transparentR = parseInt(transparentHex.substring(0, 2), 16);
      transparentG = parseInt(transparentHex.substring(2, 4), 16);
      transparentB = parseInt(transparentHex.substring(4, 6), 16);
    }

    previewPixels.forEach((color, index) => {
      const [r, g, b] = color;

      // Skip transparent color if enabled
      if (
        makeTransparent &&
        Math.abs(r - transparentR) <= colorThreshold &&
        Math.abs(g - transparentG) <= colorThreshold &&
        Math.abs(b - transparentB) <= colorThreshold
      ) {
        return; // Skip this pixel
      }

      // Skip very dark pixels (nearly black)
      if (r > 30 || g > 30 || b > 30) {
        const hex =
          `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`.toUpperCase();
        const key = `${currentFrame}-${index}`;
        newPixelData[key] = hex;
      }
    });

    setPixelData(newPixelData);
    setShowImageModal(false);
    message.success('Image imported to canvas');
  };

  const handleSaveScene = async (values) => {
    try {
      // Convert pixel data to frame format
      const frameData = [];
      const { width, height } = matrixSize;

      for (let i = 0; i < (frames.length || 1); i++) {
        const pixels = [];
        for (let j = 0; j < width * height; j++) {
          const key = `${i}-${j}`;
          if (pixelData[key] && pixelData[key] !== '#000000') {
            const hex = pixelData[key].replace('#', '');
            const r = parseInt(hex.substring(0, 2), 16);
            const g = parseInt(hex.substring(2, 4), 16);
            const b = parseInt(hex.substring(4, 6), 16);

            pixels.push({
              index: j,
              color: [r, g, b],
            });
          }
        }

        // Get frame-specific duration and brightness
        // Frame MUST have a brightness - never fall back to scene default
        const frameDuration = frameDurations[i] !== undefined ? frameDurations[i] : 5.0;
        const frameBright = frameBrightness[i] !== undefined ? frameBrightness[i] : 128;
        const frameR = frameColorR[i] !== undefined ? frameColorR[i] : 10;
        const frameG = frameColorG[i] !== undefined ? frameColorG[i] : 10;
        const frameB = frameColorB[i] !== undefined ? frameColorB[i] : 10;

        console.log(
          `Frame ${i}: duration=${frameDuration}, brightness=${frameBright}, frameDurations[${i}]=${frameDurations[i]}`
        );

        frameData.push({
          frame_index: i,
          pixel_data: {
            pixels,
            width,
            height,
          },
          duration: frameDuration,
          brightness: frameBright,
          color_r: frameR,
          color_g: frameG,
          color_b: frameB,
        });
      }

      let sceneId;

      if (isEditMode && editingSceneId) {
        // Update existing scene
        await api.patch(`/scenes/${editingSceneId}`, {
          name: values.name,
          description: values.description,
          default_frame_duration: values.default_frame_duration,
          loop_mode: loopMode,
          device_ids: selectedDevices,
        });
        sceneId = editingSceneId;

        // Load existing frames from backend
        const sceneResponse = await api.get(`/scenes/${editingSceneId}`);
        const existingScene = sceneResponse.data || sceneResponse;

        // Delete ALL frames except frame 0 (we'll recreate them with correct indices)
        const framesToDelete = existingScene.frames.filter((f) => f.frame_index !== 0);

        console.log(
          'Deleting all frames except 0:',
          framesToDelete.map((f) => f.frame_index)
        );

        for (const frame of framesToDelete) {
          try {
            await api.delete(`/scenes/frames/${frame.id}`);
            console.log(`Deleted frame ${frame.frame_index} (ID: ${frame.id})`);
          } catch (error) {
            console.error(`Failed to delete frame ${frame.id}:`, error);
          }
        }

        message.success('Scene updated successfully!');
      } else {
        // Create new scene
        const sceneResponse = await api.post('/scenes/', {
          name: values.name,
          unique_id: values.unique_id,
          description: values.description,
          matrix_width: matrixSize.width,
          matrix_height: matrixSize.height,
          default_frame_duration: values.default_frame_duration,
          loop_mode: loopMode,
          device_ids: selectedDevices,
        });
        sceneId = Array.isArray(sceneResponse)
          ? sceneResponse.id
          : sceneResponse.data?.id || sceneResponse.id;
        message.success('Scene created successfully!');
      }

      // Handle frames - update frame 0 or create new frames
      for (const frame of frameData) {
        if (frame.frame_index === 0) {
          // Update frame 0 since backend creates it automatically
          await api.patch(`/scenes/${sceneId}/frames`, frame);
        } else {
          // In edit mode, frames > 0 were already deleted, so always create new
          // In create mode, just create new frames
          await api.post(`/scenes/${sceneId}/frames`, frame);
        }
      }
      // Redirect to scenes page
      window.location.href = '/scenes';
    } catch (error) {
      console.error('Failed to save scene:', error);
      const errorMessage = error.message || 'Failed to save scene';
      message.error(`Error: ${errorMessage}`);
    }
  };

  const handleTestFrame = async () => {
    if (selectedDevices.length === 0) {
      message.warning('No devices selected');
      return;
    }

    try {
      const { width, height } = matrixSize;
      const pixels = [];

      for (let j = 0; j < width * height; j++) {
        const key = `${currentFrame}-${j}`;
        if (pixelData[key] && pixelData[key] !== '#000000') {
          const hex = pixelData[key].replace('#', '');
          const r = parseInt(hex.substring(0, 2), 16);
          const g = parseInt(hex.substring(2, 4), 16);
          const b = parseInt(hex.substring(4, 6), 16);

          pixels.push({
            index: j,
            color: [r, g, b],
          });
        }
      }

      // Fetch the first device to get chain_count and segment_id
      const deviceResponse = await api.get(`/devices/${selectedDevices[0]}`);
      const device = deviceResponse.data || deviceResponse;

      // DEBUG: Log frame durations
      console.log('DEBUG frameDurations:', frameDurations);
      console.log('DEBUG currentFrame:', currentFrame);
      console.log('DEBUG frameDurations[currentFrame]:', frameDurations[currentFrame]);

      // Get frame-specific brightness and duration (duration is stored in seconds)
      const frameBright = frameBrightness[currentFrame] || 128;
      const frameDurationSeconds =
        frameDurations[currentFrame] !== undefined ? frameDurations[currentFrame] : 5.0; // Fallback to 5 seconds

      console.log('DEBUG frameDurationSeconds:', frameDurationSeconds);

      // Send test frame with current pixel data to first device
      const pixelDataPayload = {
        pixels,
        width,
        height,
        chain_count: device.chain_count || 1,
        segment_id: device.segment_id || 0,
      };

      // Compute per-channel multipliers for this frame (0-100)
      const frameR = frameColorR[currentFrame] !== undefined ? frameColorR[currentFrame] : 10;
      const frameG = frameColorG[currentFrame] !== undefined ? frameColorG[currentFrame] : 10;
      const frameB = frameColorB[currentFrame] !== undefined ? frameColorB[currentFrame] : 10;

      // Use the timed endpoint - auto turns off after the frame duration + 2 seconds
      const autoOffDelay = frameDurationSeconds + 2; // In seconds
      await api.post(`/devices/${selectedDevices[0]}/send-frame-timed`, {
        pixel_data: pixelDataPayload,
        brightness: frameBright,
        auto_off_delay: autoOffDelay,
        color_r: frameR,
        color_g: frameG,
        color_b: frameB,
      });

      message.success(
        `Test frame sent (brightness: ${frameBright}, duration: ${frameDurationSeconds}s)`
      );
    } catch (error) {
      console.error('Failed to send test frame:', error);
      message.error('Failed to send test frame');
    }
  };

  const handleAddFrame = () => {
    setFrames([...frames, frames.length]);
  };

  const handleImportWledJson = () => {
    if (!wledJsonInput.trim()) {
      message.error('Please enter WLED JSON');
      return;
    }

    try {
      const wledData = parseWledJsonString(wledJsonInput);
      if (!wledData || !wledData.seg || !wledData.seg.i) {
        message.error('Invalid WLED JSON format - missing seg.i array');
        return;
      }

      // Convert WLED pixel data to our frame format
      const pixelArray = wledData.seg.i;
      const { width, height } = matrixSize;
      const totalPixels = width * height;
      const newPixelData = { ...pixelData };

      // Parse WLED array format: [startIdx, endIdx, [R,G,B], startIdx, [R,G,B], ...]
      // Format can be:
      // - [start, end, [R,G,B]]     = Range start-end with color
      // - [start, [R,G,B]]          = Single pixel start with color
      // - [start, end]              = Range without color (skip)

      let i = 0;
      while (i < pixelArray.length) {
        const element = pixelArray[i];

        // Skip color arrays that appear standalone
        if (Array.isArray(element)) {
          i++;
          continue;
        }

        // Must be a number (pixel index or range start)
        if (typeof element === 'number') {
          const startIdx = element;
          let endIdx = null;
          let color = null;

          // Look ahead
          if (i + 1 < pixelArray.length) {
            const nextElement = pixelArray[i + 1];

            if (typeof nextElement === 'number') {
              // Format: [start, end, ...]
              endIdx = nextElement;
              i += 2;

              // Check if next is color
              if (i < pixelArray.length && Array.isArray(pixelArray[i])) {
                color = pixelArray[i];
                i++;
              }
            } else if (Array.isArray(nextElement)) {
              // Format: [start, [R,G,B], ...]
              // This is a single pixel or end of range definition
              endIdx = startIdx + 1; // Single pixel
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
            const hexColor = `#${[r, g, b]
              .map((x) => x.toString(16).padStart(2, '0'))
              .join('')
              .toUpperCase()}`;

            // Handle both single pixels and ranges
            const effectiveEndIdx =
              endIdx !== null ? Math.min(endIdx, totalPixels) : Math.min(startIdx + 1, totalPixels);

            for (let pixelIdx = startIdx; pixelIdx < effectiveEndIdx; pixelIdx++) {
              if (pixelIdx >= 0 && pixelIdx < totalPixels) {
                const key = `${currentFrame}-${pixelIdx}`;
                newPixelData[key] = hexColor;
              }
            }
          }
        } else {
          i++;
        }
      }

      setPixelData(newPixelData);
      // Set brightness from WLED data
      if (wledData.bri) {
        const newBrightness = { ...frameBrightness };
        newBrightness[currentFrame] = wledData.bri;
        setFrameBrightness(newBrightness);
      }

      message.success('WLED JSON imported to current frame');
      setWledJsonInput('');
    } catch (error) {
      console.error('Failed to import WLED JSON:', error);
      message.error('Failed to import WLED JSON');
    }
  };

  const handleExportCurrentFrameAsWled = () => {
    const { width, height } = matrixSize;
    const totalPixels = width * height;

    // Collect all pixels from current frame
    const pixels = [];
    for (let i = 0; i < totalPixels; i++) {
      const key = `${currentFrame}-${i}`;
      if (pixelData[key] && pixelData[key] !== '#000000') {
        const hex = pixelData[key].replace('#', '');
        const r = parseInt(hex.substring(0, 2), 16);
        const g = parseInt(hex.substring(2, 4), 16);
        const b = parseInt(hex.substring(4, 6), 16);
        pixels.push({ index: i, color: [r, g, b] });
      }
    }

    // Build WLED array format with range compression: [idx, [R,G,B]] or [startIdx, endIdx, [R,G,B]]
    const pixelArray = [];

    let i = 0;
    while (i < pixels.length) {
      const currentPixel = pixels[i];
      let endIdx = i;

      // Find consecutive pixels with the same color
      while (
        endIdx + 1 < pixels.length &&
        pixels[endIdx + 1].index === pixels[endIdx].index + 1 &&
        JSON.stringify(pixels[endIdx + 1].color) === JSON.stringify(currentPixel.color)
      ) {
        endIdx++;
      }

      // Add to array: single pixel or range
      if (endIdx === i) {
        // Single pixel: [idx, [R,G,B]]
        pixelArray.push(currentPixel.index);
        pixelArray.push(currentPixel.color);
      } else {
        // Range: [startIdx, endIdx+1, [R,G,B]] (endIdx+1 because WLED uses exclusive end)
        pixelArray.push(currentPixel.index);
        pixelArray.push(pixels[endIdx].index + 1);
        pixelArray.push(currentPixel.color);
      }

      i = endIdx + 1;
    }

    // Create WLED JSON
    const wledJson = {
      on: true,
      bri: frameBrightness[currentFrame] || 128,
      seg: {
        id: 0,
        i: pixelArray,
      },
    };

    // Show in modal for copying
    Modal.info({
      title: `Frame ${currentFrame} as WLED JSON`,
      width: 800,
      content: (
        <div>
          <p style={{ marginBottom: '10px', color: '#666' }}>
            Copy this WLED JSON to use it with WLED devices:
          </p>
          <Input.TextArea
            readOnly
            rows={8}
            value={JSON.stringify(wledJson)}
            style={{ fontFamily: 'monospace', fontSize: '12px' }}
          />
        </div>
      ),
      okText: 'Close',
      onOk() {
        // Copy to clipboard
        navigator.clipboard.writeText(JSON.stringify(wledJson));
        message.success('WLED JSON copied to clipboard!');
      },
    });
  };

  const handleDeleteFrame = (index) => {
    if (frames.length <= 1) {
      message.warning('You must have at least one frame');
      return;
    }

    Modal.confirm({
      title: 'Delete Frame',
      content: `Are you sure you want to delete Frame ${index}? This action cannot be undone.`,
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk() {
        // Remove frame from frames array
        const newFrames = frames.filter((_, i) => i !== index);
        setFrames(newFrames);

        // Remove all pixel data for this frame
        const newPixelData = { ...pixelData };
        Object.keys(newPixelData).forEach((key) => {
          if (key.startsWith(`${index}-`)) {
            delete newPixelData[key];
          }
        });

        // Shift pixel data for frames after the deleted one
        Object.keys(newPixelData).forEach((key) => {
          const [frameIdx, pixelIdx] = key.split('-').map(Number);
          if (frameIdx > index) {
            const newKey = `${frameIdx - 1}-${pixelIdx}`;
            newPixelData[newKey] = newPixelData[key];
            delete newPixelData[key];
          }
        });

        setPixelData(newPixelData);

        // Update current frame if needed
        if (currentFrame >= newFrames.length) {
          setCurrentFrame(Math.max(0, newFrames.length - 1));
        }

        message.success(`Frame ${index} deleted`);
      },
    });
  };

  const handleClearFrame = () => {
    const { width, height } = matrixSize;
    const newPixelData = { ...pixelData };
    for (let i = 0; i < width * height; i++) {
      const key = `${currentFrame}-${i}`;
      delete newPixelData[key];
    }
    setPixelData(newPixelData);
  };

  const handlePlayScene = async () => {
    console.log('=== PLAY SCENE CALLED ===');
    console.log(
      'DEBUG: Play button clicked. selectedDevices:',
      selectedDevices,
      'length:',
      selectedDevices ? selectedDevices.length : 'undefined'
    );

    if (!editingSceneId) {
      console.log('WARNING: No editingSceneId set');
      message.warning('Please save the scene first before playing');
      return;
    }

    if (!selectedDevices || selectedDevices.length === 0) {
      console.log('WARNING: No selectedDevices');
      message.warning(
        'No devices selected. Please select at least one device and save the scene before playing.'
      );
      return;
    }

    try {
      console.log(`DEBUG: Sending play request to /api/scenes/${editingSceneId}/play`);
      // Start playing on devices
      await api.post(`/scenes/${editingSceneId}/play`);
      console.log('DEBUG: Play request successful');
      message.success(`Scene playing in ${loopMode} mode`);

      // Simulate frame preview - show frames in sequence based on their durations
      const numFrames = frames.length || 1;
      console.log(
        `Preview: Starting playback with ${numFrames} frames, loopMode=${loopMode}, frames=${JSON.stringify(frames)}`
      );

      // Use an external counter since setCurrentFrame is async
      let playbackIndex = 0;

      const playNextFramePreview = () => {
        if (playbackIndex < numFrames) {
          console.log(
            `Preview: Setting frame to index ${playbackIndex}, currentFrame state change triggered`
          );
          setCurrentFrame(playbackIndex); // This triggers drawCanvas via useEffect

          const frameDuration = (frameDurations[playbackIndex] || 5.0) * 1000; // ms
          console.log(`Preview: Frame ${playbackIndex} will show for ${frameDuration}ms`);

          playbackIndex++; // Increment BEFORE scheduling next, so closure has correct value

          setTimeout(() => {
            if (playbackIndex < numFrames || loopMode === 'loop') {
              if (playbackIndex >= numFrames && loopMode === 'loop') {
                console.log('Preview: Loop restarting from frame 0');
                playbackIndex = 0; // Reset for loop
              }
              playNextFramePreview(); // Tail recursion
            } else {
              console.log('Preview: Playback finished');
            }
          }, frameDuration);
        }
      };

      // Start the preview sequence immediately
      console.log('DEBUG: Starting preview sequence');
      playNextFramePreview();
    } catch (error) {
      console.error('=== PLAY SCENE ERROR ===', error);
      message.error(
        'Failed to play scene - make sure you have saved the scene with devices assigned'
      );
    }
  };

  const handleStopScene = async () => {
    if (!editingSceneId) return;

    try {
      await api.post(`/scenes/${editingSceneId}/stop`);
      message.success('Scene stopped');
    } catch (error) {
      console.error('Failed to stop scene:', error);
      message.error('Failed to stop scene');
    }
  };

  const handleFrameBrightnessChange = (value) => {
    const newBrightness = { ...frameBrightness };
    newBrightness[currentFrame] = value;
    setFrameBrightness(newBrightness);
  };

  const handleFrameColorRChange = (value) => {
    const newColorR = { ...frameColorR };
    newColorR[currentFrame] = value;
    setFrameColorR(newColorR);
  };

  const handleFrameColorGChange = (value) => {
    const newColorG = { ...frameColorG };
    newColorG[currentFrame] = value;
    setFrameColorG(newColorG);
  };

  const handleFrameColorBChange = (value) => {
    const newColorB = { ...frameColorB };
    newColorB[currentFrame] = value;
    setFrameColorB(newColorB);
  };

  const handleFrameDurationChange = (value) => {
    const newDurations = { ...frameDurations };
    newDurations[currentFrame] = value;
    setFrameDurations(newDurations);
  };

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <h2>{isEditMode ? 'Edit Scene' : 'Create Scene'}</h2>

      <Form layout="vertical" form={form} onFinish={handleSaveScene}>
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item
              label="Scene Name"
              name="name"
              rules={[{ required: true, message: 'Scene name is required' }]}
            >
              <Input placeholder="e.g., Christmas Lights" />
            </Form.Item>
          </Col>

          <Col xs={24} sm={12}>
            <Form.Item
              label="Unique ID"
              name="unique_id"
              rules={[{ required: !isEditMode, message: 'Unique ID is required' }]}
            >
              <Input placeholder="e.g., christmas_lights" disabled={isEditMode} />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item label="Description" name="description">
          <Input.TextArea rows={2} placeholder="Optional description" />
        </Form.Item>

        {/* Hidden field for default_frame_duration - needed for form values */}
        <Form.Item name="default_frame_duration" initialValue={5} style={{ display: 'none' }}>
          <Input type="hidden" />
        </Form.Item>

        <Row gutter={16}>
          <Col xs={12} sm={6}>
            <Form.Item label="Matrix Width" initialValue={16} name="matrix_width">
              <InputNumber
                min={1}
                max={64}
                onChange={(value) => setMatrixSize((prev) => ({ ...prev, width: value }))}
              />
            </Form.Item>
          </Col>

          <Col xs={12} sm={6}>
            <Form.Item label="Matrix Height" initialValue={16} name="matrix_height">
              <InputNumber
                min={1}
                max={64}
                onChange={(value) => setMatrixSize((prev) => ({ ...prev, height: value }))}
              />
            </Form.Item>
          </Col>

          <Col xs={12} sm={6}>
            <Form.Item label="Playback Mode">
              <Radio.Group value={loopMode} onChange={(e) => setLoopMode(e.target.value)}>
                <Radio value="once">▶️ Play Once</Radio>
                <Radio value="loop">🔄 Loop</Radio>
              </Radio.Group>
            </Form.Item>
          </Col>

          <Col xs={12} sm={6}>
            <Form.Item label="Select Devices">
              <Select
                mode="multiple"
                placeholder="Select target devices"
                value={selectedDevices}
                onChange={setSelectedDevices}
                options={devices.map((d) => ({
                  label: d.name,
                  value: d.id,
                }))}
              />
            </Form.Item>
          </Col>
        </Row>

        <Divider>Pixel Editor</Divider>

        <Row gutter={16} style={{ marginBottom: '16px' }}>
          <Col xs={24}>
            <Collapse
              items={[
                {
                  key: '1',
                  label: '📥 Import WLED JSON / 📤 Export Frame',
                  children: (
                    <Space direction="vertical" style={{ width: '100%' }} size="large">
                      <div>
                        <h4 style={{ marginTop: 0, marginBottom: '12px' }}>
                          Import WLED JSON to current frame:
                        </h4>
                        <p style={{ fontSize: '12px', color: '#666', margin: '0 0 12px 0' }}>
                          Paste a WLED JSON payload to fill the current frame with pixel data:
                        </p>
                        <Input.TextArea
                          rows={4}
                          placeholder='{"on":true,"bri":25,"seg":{"id":0,"i":[...]}}'
                          value={wledJsonInput}
                          onChange={(e) => setWledJsonInput(e.target.value)}
                          style={{
                            fontFamily: 'monospace',
                            fontSize: '12px',
                            marginBottom: '12px',
                          }}
                        />
                        <Button type="primary" onClick={handleImportWledJson} block>
                          📥 Import to Frame {currentFrame}
                        </Button>
                      </div>
                      <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: '16px' }}>
                        <h4 style={{ marginTop: 0, marginBottom: '12px' }}>
                          Export current frame as WLED JSON:
                        </h4>
                        <p style={{ fontSize: '12px', color: '#666', margin: '0 0 12px 0' }}>
                          Copy the WLED format of Frame {currentFrame} to share or use with other
                          WLED projects.
                        </p>
                        <Button type="default" onClick={handleExportCurrentFrameAsWled} block>
                          📤 Export Frame {currentFrame} as WLED JSON
                        </Button>
                      </div>
                    </Space>
                  ),
                },
              ]}
            />
          </Col>
        </Row>

        <Row gutter={16}>
          <Col xs={24} sm={6}>
            <Card size="small" title="Tools">
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <label>Color:</label>
                  <div
                    style={{
                      backgroundColor: selectedColor,
                      width: '100%',
                      height: '40px',
                      borderRadius: '4px',
                      marginTop: '8px',
                      cursor: 'pointer',
                      border: '2px solid #ccc',
                    }}
                    onClick={() => {
                      const input = document.createElement('input');
                      input.type = 'color';
                      input.value = selectedColor;
                      input.onchange = (e) => {
                        setSelectedColor(e.target.value);
                        addRecentColor(e.target.value);
                      };
                      input.click();
                    }}
                    title="Click to open color picker. Right-click on canvas to pick colors."
                  />
                </div>

                {/* Common Colors */}
                <div>
                  <label style={{ fontSize: '12px' }}>Common Colors:</label>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(5, 1fr)',
                      gap: '4px',
                      marginTop: '4px',
                    }}
                  >
                    {COMMON_COLORS.map((color) => (
                      <Tooltip key={color} title={color}>
                        <div
                          onClick={() => {
                            setSelectedColor(color);
                            addRecentColor(color);
                          }}
                          style={{
                            backgroundColor: color,
                            width: '100%',
                            aspectRatio: '1',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            border: selectedColor === color ? '3px solid #000' : '1px solid #ccc',
                          }}
                        />
                      </Tooltip>
                    ))}
                  </div>
                </div>

                {/* Recently Used Colors */}
                {recentColors.length > 0 && (
                  <div>
                    <label style={{ fontSize: '12px' }}>Recently Used:</label>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(5, 1fr)',
                        gap: '4px',
                        marginTop: '4px',
                      }}
                    >
                      {recentColors.map((color) => (
                        <Tooltip key={color} title={color}>
                          <div
                            onClick={() => setSelectedColor(color)}
                            style={{
                              backgroundColor: color,
                              width: '100%',
                              aspectRatio: '1',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              border: selectedColor === color ? '3px solid #000' : '1px solid #ccc',
                            }}
                          />
                        </Tooltip>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ fontSize: '12px', color: '#666' }}>
                  <strong>Tips:</strong>
                  <ul style={{ marginTop: '4px', paddingLeft: '16px' }}>
                    <li>Right-click pixel → pick color</li>
                    <li>Ctrl+Click → multi-select</li>
                    <li>Arrow keys → move selected</li>
                  </ul>
                </div>

                <Button type="primary" block onClick={handleClearFrame}>
                  Clear Frame
                </Button>

                <Upload maxCount={1} beforeUpload={handleImageUpload} accept="image/*">
                  <Button block icon={<UploadOutlined />}>
                    Upload Image
                  </Button>
                </Upload>

                <Button block onClick={handleTestFrame} icon={<PlayCircleOutlined />}>
                  Test Frame
                </Button>
              </Space>
            </Card>
          </Col>

          <Col xs={24} sm={18}>
            <Card size="small" title="Canvas">
              <canvas
                ref={canvasRef}
                onClick={handleCanvasClick}
                onMouseDown={handleCanvasMouseDown}
                onContextMenu={(e) => e.preventDefault()}
                style={{
                  border: '1px solid #ccc',
                  cursor: 'crosshair',
                  maxWidth: '100%',
                  height: 'auto',
                }}
              />
            </Card>

            <Card size="small" title="Frames" style={{ marginTop: '16px' }}>
              <Space wrap align="center">
                {frames.map((_, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Button
                      type={currentFrame === i ? 'primary' : 'default'}
                      onClick={() => setCurrentFrame(i)}
                    >
                      Frame {i}
                    </Button>
                    {frames.length > 1 && (
                      <Tooltip title={`Delete Frame ${i}`}>
                        <Button
                          type="text"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={() => handleDeleteFrame(i)}
                          style={{ padding: '4px 8px' }}
                        />
                      </Tooltip>
                    )}
                  </div>
                ))}
                <Button type="dashed" icon={<PlusOutlined />} onClick={handleAddFrame}>
                  Add Frame
                </Button>
              </Space>

              <Divider style={{ margin: '12px 0' }} />

              <div style={{ marginTop: '12px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                  Frame {currentFrame} Duration (seconds): {frameDurations[currentFrame] ?? 5}
                </label>
                <InputNumber
                  step={0.1}
                  min={0.1}
                  value={frameDurations[currentFrame] ?? 5}
                  onChange={handleFrameDurationChange}
                  style={{ width: '100%', marginBottom: '16px' }}
                />

                <label style={{ display: 'block', marginBottom: '8px' }}>
                  Frame {currentFrame} Brightness: {frameBrightness[currentFrame] || 128}
                </label>
                <Slider
                  min={0}
                  max={255}
                  step={1}
                  value={frameBrightness[currentFrame] || 128}
                  onChange={handleFrameBrightnessChange}
                  marks={{ 0: '0%', 128: '50%', 255: '100%' }}
                />

                {/* RGB Color Intensity Controls */}
                <div style={{ marginTop: '24px' }}>
                  <h4 style={{ marginBottom: '12px' }}>Color Intensity (per channel)</h4>

                  <label style={{ display: 'block', marginBottom: '8px' }}>
                    🔴 Red: {frameColorR[currentFrame] || 10}%
                  </label>
                  <Slider
                    min={0}
                    max={100}
                    step={1}
                    value={frameColorR[currentFrame] || 10}
                    onChange={handleFrameColorRChange}
                    marks={{ 0: '0%', 50: '50%', 100: '100%' }}
                  />

                  <label style={{ display: 'block', marginBottom: '8px', marginTop: '16px' }}>
                    🟢 Green: {frameColorG[currentFrame] || 10}%
                  </label>
                  <Slider
                    min={0}
                    max={100}
                    step={1}
                    value={frameColorG[currentFrame] || 10}
                    onChange={handleFrameColorGChange}
                    marks={{ 0: '0%', 50: '50%', 100: '100%' }}
                  />

                  <label style={{ display: 'block', marginBottom: '8px', marginTop: '16px' }}>
                    🔵 Blue: {frameColorB[currentFrame] || 10}%
                  </label>
                  <Slider
                    min={0}
                    max={100}
                    step={1}
                    value={frameColorB[currentFrame] || 10}
                    onChange={handleFrameColorBChange}
                    marks={{ 0: '0%', 50: '50%', 100: '100%' }}
                  />
                </div>
              </div>

              <Space style={{ marginTop: '12px', width: '100%' }}>
                {selectedDevices && selectedDevices.length > 0 ? (
                  <Tooltip title={`Play this scene in ${loopMode} mode on selected devices`}>
                    <Button type="primary" icon={<PlayCircleOutlined />} onClick={handlePlayScene}>
                      Play ({loopMode === 'once' ? '▶️ Once' : '🔄 Loop'})
                    </Button>
                  </Tooltip>
                ) : (
                  <Tooltip title="Select at least one device to play">
                    <span>
                      <Button
                        type="primary"
                        icon={<PlayCircleOutlined />}
                        disabled
                        style={{ cursor: 'not-allowed' }}
                      >
                        Play ({loopMode === 'once' ? '▶️ Once' : '🔄 Loop'})
                      </Button>
                    </span>
                  </Tooltip>
                )}
                {selectedDevices && selectedDevices.length > 0 ? (
                  <Button danger icon={<StopOutlined />} onClick={handleStopScene}>
                    Stop
                  </Button>
                ) : (
                  <Tooltip title="Select at least one device to use stop button">
                    <span>
                      <Button
                        danger
                        icon={<StopOutlined />}
                        disabled
                        style={{ cursor: 'not-allowed' }}
                      >
                        Stop
                      </Button>
                    </span>
                  </Tooltip>
                )}
              </Space>
            </Card>
          </Col>
        </Row>

        <Divider />

        <Space style={{ marginTop: '20px' }}>
          <Button type="primary" htmlType="submit" icon={<SaveOutlined />} size="large">
            Save Scene
          </Button>
          <Button onClick={() => (window.location.href = '/scenes')} size="large">
            Cancel
          </Button>
        </Space>
      </Form>

      {/* Image Upload Modal */}
      <Modal
        title="Import Image"
        open={showImageModal}
        width={900}
        onCancel={() => setShowImageModal(false)}
        footer={[
          <Button key="cancel" onClick={() => setShowImageModal(false)}>
            Cancel
          </Button>,
          <Button key="import" type="primary" onClick={applyImageToCanvas}>
            Import to Canvas
          </Button>,
        ]}
      >
        {uploadedImage && (
          <div style={{ display: 'flex', gap: '20px' }}>
            {/* Original Image with Crop Box */}
            <div style={{ flex: 1 }}>
              <h4>Select Region</h4>
              <div
                style={{
                  position: 'relative',
                  display: 'inline-block',
                  maxWidth: '100%',
                }}
              >
                <img
                  ref={imageCanvasRef}
                  src={uploadedImage.src}
                  style={{
                    maxWidth: '100%',
                    maxHeight: '400px',
                    display: 'block',
                  }}
                />
                {/* Crop Box Overlay with Draggable/Resizable Handles */}
                <div
                  style={{
                    position: 'absolute',
                    left: `${(cropBox.x / uploadedImage.width) * 100}%`,
                    top: `${(cropBox.y / uploadedImage.height) * 100}%`,
                    width: `${(cropBox.width / uploadedImage.width) * 100}%`,
                    height: `${(cropBox.height / uploadedImage.height) * 100}%`,
                    border: '3px solid #1890ff',
                    boxShadow: 'inset 0 0 0 4000px rgba(0,0,0,0.5)',
                    cursor: 'move',
                  }}
                  onMouseDown={(e) => handleCropBoxMouseDown(e, null)}
                >
                  {/* Corner/Edge Handles */}
                  {/* Northwest */}
                  <div
                    style={{
                      position: 'absolute',
                      left: '-6px',
                      top: '-6px',
                      width: '12px',
                      height: '12px',
                      backgroundColor: '#1890ff',
                      cursor: 'nwse-resize',
                    }}
                    onMouseDown={(e) => handleCropBoxMouseDown(e, 'nw')}
                  />
                  {/* Northeast */}
                  <div
                    style={{
                      position: 'absolute',
                      right: '-6px',
                      top: '-6px',
                      width: '12px',
                      height: '12px',
                      backgroundColor: '#1890ff',
                      cursor: 'nesw-resize',
                    }}
                    onMouseDown={(e) => handleCropBoxMouseDown(e, 'ne')}
                  />
                  {/* Southwest */}
                  <div
                    style={{
                      position: 'absolute',
                      left: '-6px',
                      bottom: '-6px',
                      width: '12px',
                      height: '12px',
                      backgroundColor: '#1890ff',
                      cursor: 'nesw-resize',
                    }}
                    onMouseDown={(e) => handleCropBoxMouseDown(e, 'sw')}
                  />
                  {/* Southeast */}
                  <div
                    style={{
                      position: 'absolute',
                      right: '-6px',
                      bottom: '-6px',
                      width: '12px',
                      height: '12px',
                      backgroundColor: '#1890ff',
                      cursor: 'nwse-resize',
                    }}
                    onMouseDown={(e) => handleCropBoxMouseDown(e, 'se')}
                  />
                  {/* Edge Handles */}
                  {/* North */}
                  <div
                    style={{
                      position: 'absolute',
                      left: '50%',
                      top: '-4px',
                      transform: 'translateX(-50%)',
                      width: '40px',
                      height: '8px',
                      backgroundColor: '#1890ff',
                      cursor: 'ns-resize',
                    }}
                    onMouseDown={(e) => handleCropBoxMouseDown(e, 'n')}
                  />
                  {/* South */}
                  <div
                    style={{
                      position: 'absolute',
                      left: '50%',
                      bottom: '-4px',
                      transform: 'translateX(-50%)',
                      width: '40px',
                      height: '8px',
                      backgroundColor: '#1890ff',
                      cursor: 'ns-resize',
                    }}
                    onMouseDown={(e) => handleCropBoxMouseDown(e, 's')}
                  />
                  {/* East */}
                  <div
                    style={{
                      position: 'absolute',
                      right: '-4px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      width: '8px',
                      height: '40px',
                      backgroundColor: '#1890ff',
                      cursor: 'ew-resize',
                    }}
                    onMouseDown={(e) => handleCropBoxMouseDown(e, 'e')}
                  />
                  {/* West */}
                  <div
                    style={{
                      position: 'absolute',
                      left: '-4px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      width: '8px',
                      height: '40px',
                      backgroundColor: '#1890ff',
                      cursor: 'ew-resize',
                    }}
                    onMouseDown={(e) => handleCropBoxMouseDown(e, 'w')}
                  />
                </div>
              </div>

              <div style={{ marginTop: '12px' }}>
                <label>Crop Position & Size:</label>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: '8px',
                    marginTop: '8px',
                  }}
                >
                  <InputNumber
                    label="X"
                    size="small"
                    min={0}
                    max={uploadedImage.width}
                    value={Math.round(cropBox.x)}
                    onChange={(val) => setCropBox((prev) => ({ ...prev, x: val || 0 }))}
                  />
                  <InputNumber
                    label="Y"
                    size="small"
                    min={0}
                    max={uploadedImage.height}
                    value={Math.round(cropBox.y)}
                    onChange={(val) => setCropBox((prev) => ({ ...prev, y: val || 0 }))}
                  />
                  <InputNumber
                    label="Width"
                    size="small"
                    min={10}
                    max={uploadedImage.width}
                    value={Math.round(cropBox.width)}
                    onChange={(val) => setCropBox((prev) => ({ ...prev, width: val || 10 }))}
                  />
                  <InputNumber
                    label="Height"
                    size="small"
                    min={10}
                    max={uploadedImage.height}
                    value={Math.round(cropBox.height)}
                    onChange={(val) => setCropBox((prev) => ({ ...prev, height: val || 10 }))}
                  />
                </div>

                <div style={{ marginTop: '12px' }}>
                  <Button
                    block
                    onClick={() => {
                      const size = Math.min(uploadedImage.width, uploadedImage.height);
                      setCropBox({
                        x: (uploadedImage.width - size) / 2,
                        y: (uploadedImage.height - size) / 2,
                        width: size,
                        height: size,
                      });
                    }}
                  >
                    Square Crop
                  </Button>
                  <Button
                    block
                    style={{ marginTop: '8px' }}
                    onClick={() => {
                      setCropBox({
                        x: 0,
                        y: 0,
                        width: uploadedImage.width,
                        height: uploadedImage.height,
                      });
                    }}
                  >
                    Full Image
                  </Button>
                </div>
              </div>

              {/* Color Processing Options */}
              <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid #eee' }}>
                <label style={{ fontWeight: 'bold' }}>Color Processing:</label>

                <div style={{ marginTop: '8px' }}>
                  <label>
                    <input
                      type="checkbox"
                      checked={invertColors}
                      onChange={(e) => setInvertColors(e.target.checked)}
                    />
                    {' Invert Colors'}
                  </label>
                  <p style={{ fontSize: '12px', color: '#666', margin: '4px 0 0 20px' }}>
                    Converts colors (white ↔ black, etc.)
                  </p>
                </div>

                <div style={{ marginTop: '12px' }}>
                  <label>
                    <input
                      type="checkbox"
                      checked={makeTransparent}
                      onChange={(e) => setMakeTransparent(e.target.checked)}
                    />
                    {' Make Color Transparent'}
                  </label>
                  <p style={{ fontSize: '12px', color: '#666', margin: '4px 0 0 20px' }}>
                    Remove a specific color (e.g., white background)
                  </p>

                  {makeTransparent && (
                    <div style={{ marginLeft: '20px', marginTop: '8px' }}>
                      <div style={{ marginBottom: '8px' }}>
                        <label style={{ fontSize: '12px' }}>Color to Remove:</label>
                        <div
                          onClick={() => {
                            const input = document.createElement('input');
                            input.type = 'color';
                            input.value = transparentColor;
                            input.onchange = (e) => setTransparentColor(e.target.value);
                            input.click();
                          }}
                          style={{
                            backgroundColor: transparentColor,
                            width: '60px',
                            height: '30px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            border: '1px solid #ccc',
                            marginTop: '4px',
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: '12px' }}>Threshold: {colorThreshold}</label>
                        <Slider
                          min={0}
                          max={100}
                          value={colorThreshold}
                          onChange={setColorThreshold}
                        />
                        <p style={{ fontSize: '11px', color: '#999', margin: '4px 0 0 0' }}>
                          How close colors need to match (0 = exact, 100 = very loose)
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Preview Canvas */}
            <div style={{ flex: 1 }}>
              <h4>
                Preview ({matrixSize.width}×{matrixSize.height})
              </h4>
              <canvas
                ref={previewCanvasRef}
                onClick={handlePreviewCanvasClick}
                style={{
                  border: '2px solid #ccc',
                  maxWidth: '100%',
                  maxHeight: '400px',
                  display: 'block',
                  cursor: makeTransparent ? 'crosshair' : 'default',
                }}
              />
              <p style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
                Black pixels will be skipped (transparent)
                {makeTransparent && (
                  <>
                    <br />
                    💡 Click on preview to pick a color!
                  </>
                )}
              </p>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default SceneCreator;
