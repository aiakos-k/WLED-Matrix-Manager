import { useState, useEffect } from 'react';
import {
  Button,
  Table,
  Space,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  message,
  Popconfirm,
  Tag,
  Row,
  Col,
  Upload,
  Alert,
} from 'antd';
import {
  DeleteOutlined,
  PlusOutlined,
  EditOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DownloadOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import api from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { useNavigate } from 'react-router-dom';

const DeviceManager = () => {
  const { isAdmin, isLoading } = useAuth();
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingDevice, setEditingDevice] = useState(null);
  const [form] = Form.useForm();
  const [deviceHealth, setDeviceHealth] = useState({});
  const [selectedProtocol, setSelectedProtocol] = useState('json_api');

  // Redirect non-admin users
  useEffect(() => {
    // Wait until auth is loaded before checking
    if (isLoading) return;

    if (!isAdmin) {
      message.error('Admin access required');
      navigate('/scenes');
    }
  }, [isAdmin, isLoading, navigate]);

  useEffect(() => {
    fetchDevices();
    checkDeviceHealth();
    const interval = setInterval(checkDeviceHealth, 10000); // Check every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchDevices = async () => {
    try {
      setLoading(true);
      const response = await api.get('/devices/');
      const devicesArray = Array.isArray(response) ? response : response.data || [];
      setDevices(devicesArray);
    } catch (error) {
      console.error('Failed to fetch devices:', error);
      message.error('Failed to load devices');
    } finally {
      setLoading(false);
    }
  };

  const checkDeviceHealth = async () => {
    try {
      const response = await api.get('/devices/');
      const devicesArray = Array.isArray(response) ? response : response.data || [];
      const health = {};
      for (const device of devicesArray) {
        try {
          const healthResponse = await api.get(`/devices/${device.id}/health`);
          // API returns {healthy: boolean} directly, not wrapped in data
          health[device.id] = healthResponse.healthy === true;
        } catch {
          health[device.id] = false;
        }
      }
      setDeviceHealth(health);
    } catch (error) {
      console.error('Failed to check device health:', error);
    }
  };

  const showAddModal = () => {
    setEditingDevice(null);
    form.resetFields();
    setSelectedProtocol('json_api');
    setIsModalVisible(true);
  };

  const showEditModal = (device) => {
    setEditingDevice(device);
    setSelectedProtocol(device.communication_protocol || 'json_api');
    form.setFieldsValue({
      name: device.name,
      ip_address: device.ip_address,
      matrix_width: device.matrix_width,
      matrix_height: device.matrix_height,
      communication_protocol: device.communication_protocol,
      chain_count: device.chain_count,
      segment_id: device.segment_id,
    });
    setIsModalVisible(true);
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();

      if (editingDevice) {
        // Update existing device
        await api.patch(`/devices/${editingDevice.id}`, values);
        message.success('Device updated successfully');
      } else {
        // Create new device
        await api.post('/devices/', values);
        message.success('Device created successfully');
      }

      setIsModalVisible(false);
      fetchDevices();
    } catch (error) {
      if (error.response?.data?.message) {
        message.error(error.response.data.message);
      } else {
        message.error('Failed to save device');
      }
    }
  };

  const handleDelete = async (deviceId) => {
    try {
      await api.delete(`/devices/${deviceId}`);
      message.success('Device deleted successfully');
      fetchDevices();
    } catch {
      message.error('Failed to delete device');
    }
  };

  const handleTest = async (deviceId) => {
    try {
      await api.post(`/devices/${deviceId}/test`, {});
      message.success('Test pattern sent to device');

      // Auto turn-off after 5 seconds
      setTimeout(async () => {
        try {
          await api.post(`/devices/${deviceId}/off`, {});
          console.log('Device turned off after test');
        } catch {
          console.error('Failed to turn off device');
        }
      }, 5000);
    } catch {
      message.error('Failed to send test command');
    }
  };

  const handleExport = async () => {
    try {
      const response = await api.get('/devices/export', {
        responseType: 'blob',
      });

      // Create blob and download
      const url = window.URL.createObjectURL(new Blob([response]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'devices_export.json');
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);

      message.success('Devices exported successfully');
    } catch (error) {
      console.error('Export error:', error);
      message.error('Failed to export devices');
    }
  };

  const handleImport = async (file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await api.post('/devices/import', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      message.success(`Imported ${response.imported} devices successfully`);
      if (response.errors && response.errors.length > 0) {
        message.warning(`Some devices had errors: ${response.errors.join(', ')}`);
      }

      fetchDevices();
      return false; // Prevent default upload behavior
    } catch (error) {
      console.error('Import error:', error);
      message.error('Failed to import devices');
      return false;
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Space>
          <span>{text}</span>
          {deviceHealth[record.id] !== undefined && (
            <Tag
              color={deviceHealth[record.id] ? 'green' : 'red'}
              icon={deviceHealth[record.id] ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
            >
              {deviceHealth[record.id] ? 'Online' : 'Offline'}
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'IP Address',
      dataIndex: 'ip_address',
      key: 'ip_address',
    },
    {
      title: 'Matrix Size',
      key: 'matrix_size',
      render: (_, record) => `${record.matrix_width}×${record.matrix_height}`,
    },
    {
      title: 'Protocol',
      dataIndex: 'communication_protocol',
      key: 'communication_protocol',
      render: (protocol) => {
        const protocolLabels = {
          json_api: { label: 'JSON API', color: 'blue' },
          udp_dnrgb: { label: 'UDP DNRGB', color: 'green' },
        };
        const config = protocolLabels[protocol] || { label: protocol, color: 'default' };
        return <Tag color={config.color}>{config.label}</Tag>;
      },
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (is_active) => (is_active ? 'Active' : 'Inactive'),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Button type="primary" size="small" onClick={() => handleTest(record.id)}>
            Test
          </Button>
          <Button
            type="primary"
            size="small"
            icon={<EditOutlined />}
            onClick={() => showEditModal(record)}
          />
          <Popconfirm
            title="Delete Device"
            description="Are you sure you want to delete this device?"
            onConfirm={() => handleDelete(record.id)}
            okText="Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Button danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '20px' }}>
      <Row gutter={[16, 16]} style={{ marginBottom: '20px' }}>
        <Col span={24}>
          <Space>
            <h2>Devices</h2>
            <Button type="primary" icon={<PlusOutlined />} onClick={showAddModal}>
              Add Device
            </Button>
            <Button icon={<DownloadOutlined />} onClick={handleExport}>
              Export
            </Button>
            <Upload
              name="devices_file"
              accept=".json"
              beforeUpload={handleImport}
              maxCount={1}
              showUploadList={false}
            >
              <Button icon={<UploadOutlined />}>Import</Button>
            </Upload>
          </Space>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={devices}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title={editingDevice ? 'Edit Device' : 'Add Device'}
        open={isModalVisible}
        onOk={handleOk}
        onCancel={() => setIsModalVisible(false)}
      >
        <Form layout="vertical" form={form}>
          <Form.Item
            label="Device Name"
            name="name"
            rules={[{ required: true, message: 'Device name is required' }]}
          >
            <Input placeholder="e.g., Living Room" />
          </Form.Item>

          <Form.Item
            label="IP Address"
            name="ip_address"
            rules={[
              { required: true, message: 'IP address is required' },
              {
                pattern: /^(\d{1,3}\.){3}\d{1,3}$/,
                message: 'Invalid IP address format',
              },
            ]}
          >
            <Input placeholder="e.g., 10.0.0.12" />
          </Form.Item>

          <Form.Item
            label="Matrix Width"
            name="matrix_width"
            initialValue={16}
            rules={[
              { required: true },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  const protocol = getFieldValue('communication_protocol');
                  if (protocol === 'json_api' && value > 16) {
                    return Promise.reject(new Error('JSON API supports max 16×16 (256 LEDs)'));
                  }
                  return Promise.resolve();
                },
              }),
            ]}
          >
            <InputNumber min={1} max={64} />
          </Form.Item>

          <Form.Item
            label="Matrix Height"
            name="matrix_height"
            initialValue={16}
            rules={[
              { required: true },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  const protocol = getFieldValue('communication_protocol');
                  if (protocol === 'json_api' && value > 16) {
                    return Promise.reject(new Error('JSON API supports max 16×16 (256 LEDs)'));
                  }
                  return Promise.resolve();
                },
              }),
            ]}
          >
            <InputNumber min={1} max={64} />
          </Form.Item>

          <Form.Item
            label="Communication Protocol"
            name="communication_protocol"
            initialValue="json_api"
            rules={[{ required: true }]}
          >
            <Select
              placeholder="Select communication protocol"
              onChange={(value) => {
                setSelectedProtocol(value);
                // Reset chain/segment fields when switching to JSON API
                if (value === 'json_api') {
                  form.setFieldsValue({ chain_count: 1, segment_id: 0 });
                }
              }}
              options={[
                {
                  label: 'JSON API (HTTP) - Up to 256 LEDs (16×16 max)',
                  value: 'json_api',
                },
                {
                  label: '⭐ UDP DNRGB - Unlimited LEDs (Recommended)',
                  value: 'udp_dnrgb',
                },
              ]}
            />
          </Form.Item>

          {selectedProtocol === 'udp_dnrgb' && (
            <>
              <Form.Item
                label="Number of Chains/Segments"
                name="chain_count"
                initialValue={1}
                tooltip="For WLED devices with multiple parallel chains (e.g., 4 chains × 1024 LEDs = 4096 total). Most devices use 1 chain."
                rules={[{ required: true }]}
              >
                <InputNumber
                  min={1}
                  max={8}
                  placeholder="1 (single chain)"
                  help="Number of parallel LED chains/segments in the device"
                />
              </Form.Item>

              <Form.Item
                label="Segment ID"
                name="segment_id"
                initialValue={0}
                tooltip="For WLED devices with multiple segments (0-15). Usually 0 for single-segment devices."
                rules={[{ required: true }]}
              >
                <InputNumber
                  min={0}
                  max={15}
                  placeholder="0 (first segment)"
                  help="WLED Segment ID (0 = first segment, 1 = second segment, etc.)"
                />
              </Form.Item>
            </>
          )}

          <Alert
            message="Protocol Selection"
            description={
              <div>
                <p>
                  <strong>JSON API:</strong> HTTP-based control, best for small devices (&lt;256
                  LEDs).
                </p>
                <p>
                  <strong>UDP DNRGB:</strong> Recommended for all devices. Supports unlimited LEDs
                  by chunking into multiple packets (max 489 LEDs per packet). For devices with
                  multiple segments, set the Segment ID (usually 0 for single-segment devices).
                </p>
              </div>
            }
            type="info"
            style={{ marginBottom: '16px' }}
          />
        </Form>
      </Modal>
    </div>
  );
};

export default DeviceManager;
