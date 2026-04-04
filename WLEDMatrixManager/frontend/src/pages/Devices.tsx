import React, { useEffect, useState, useCallback } from 'react';
import {
  Button, Card, Col, Divider, Form, Input, InputNumber, message, Modal,
  Row, Select, Slider, Space, Table, Tag, Popconfirm, Spin, Alert, Typography,
} from 'antd';
import {
  PlusOutlined, SearchOutlined, DeleteOutlined, EditOutlined,
  CheckCircleOutlined, CloseCircleOutlined, SyncOutlined,
  HomeOutlined,
} from '@ant-design/icons';
import {
  getDevices, createDevice, updateDevice, deleteDevice,
  checkDeviceHealth, discoverHADevices,
  type DeviceData, type HADevice,
} from '@/api/client';

const { Text } = Typography;

const PROTOCOLS = [
  { value: 'udp_dnrgb', label: 'UDP DNRGB (Recommended)' },
  { value: 'json_api', label: 'JSON API (HTTP)' },
];

const SCALE_MODES = [
  { value: 'stretch', label: 'Stretch (resize to fit)' },
  { value: 'tile', label: 'Tile (repeat pattern)' },
  { value: 'center', label: 'Center (pad with black)' },
  { value: 'none', label: 'None (1:1, crop if larger)' },
];

const Devices: React.FC = () => {
  const [devices, setDevices] = useState<DeviceData[]>([]);
  const [loading, setLoading] = useState(true);
  const [healthMap, setHealthMap] = useState<Record<number, boolean>>({});
  const [modalOpen, setModalOpen] = useState(false);
  const [editDevice, setEditDevice] = useState<DeviceData | null>(null);
  const [form] = Form.useForm();

  // HA Discovery
  const [discovering, setDiscovering] = useState(false);
  const [haDevices, setHaDevices] = useState<HADevice[]>([]);
  const [discoveryOpen, setDiscoveryOpen] = useState(false);
  const [haLoading, setHaLoading] = useState(false);
  const [haOptions, setHaOptions] = useState<HADevice[]>([]);

  const load = useCallback(async () => {
    try {
      const d = await getDevices();
      setDevices(d);
    } catch {
      message.error('Failed to load devices');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Health checks
  useEffect(() => {
    const checkAll = async () => {
      const results: Record<number, boolean> = {};
      await Promise.all(
        devices.map(async (d) => {
          try {
            const r = await checkDeviceHealth(d.id);
            results[d.id] = r.healthy;
          } catch {
            results[d.id] = false;
          }
        }),
      );
      setHealthMap(results);
    };
    if (devices.length > 0) {
      checkAll();
      const interval = setInterval(checkAll, 15000);
      return () => clearInterval(interval);
    }
  }, [devices]);

  // ─── Load HA devices for the Select dropdown ──────────

  const loadHAOptions = useCallback(async () => {
    if (haOptions.length > 0) return; // already loaded
    setHaLoading(true);
    try {
      const result = await discoverHADevices();
      setHaOptions(result.devices);
    } catch {
      // Not running inside HA — silently ignore
    } finally {
      setHaLoading(false);
    }
  }, [haOptions.length]);

  const onHAEntitySelect = (entityId: string) => {
    const device = haOptions.find((d) => d.entity_id === entityId);
    if (device) {
      const updates: Record<string, unknown> = { ha_entity_id: entityId };
      if (device.name) updates.name = device.name;
      if (device.ip_address) updates.ip_address = device.ip_address;
      form.setFieldsValue(updates);
    }
  };

  const onHAEntityClear = () => {
    form.setFieldsValue({ ha_entity_id: undefined });
  };

  // ─── CRUD ─────────────────────────────────────────────

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editDevice) {
        await updateDevice(editDevice.id, values);
        message.success('Device updated');
      } else {
        await createDevice(values);
        message.success('Device added');
      }
      setModalOpen(false);
      form.resetFields();
      setEditDevice(null);
      load();
    } catch {
      message.error('Please fill required fields');
    }
  };

  const handleEdit = (device: DeviceData) => {
    setEditDevice(device);
    form.setFieldsValue(device);
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteDevice(id);
      message.success('Device removed');
      load();
    } catch {
      message.error('Delete failed');
    }
  };

  // ─── HA Discovery Modal ───────────────────────────────

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      const result = await discoverHADevices();
      setHaDevices(result.devices);
      setHaOptions(result.devices); // also update the inline Select cache
      setDiscoveryOpen(true);
      if (result.devices.length === 0) {
        message.info('No WLED devices found in Home Assistant');
      }
    } catch {
      message.warning('Device discovery not available (not running in Home Assistant?)');
    } finally {
      setDiscovering(false);
    }
  };

  const addFromHA = (haDevice: HADevice) => {
    form.resetFields();
    form.setFieldsValue({
      name: haDevice.name,
      ip_address: haDevice.ip_address,
      ha_entity_id: haDevice.entity_id,
      matrix_width: 16,
      matrix_height: 16,
      communication_protocol: 'udp_dnrgb',
      chain_count: 1,
      segment_id: 0,
      base_brightness: haDevice.attributes?.brightness != null
        ? Math.round(Number(haDevice.attributes.brightness) * 255 / 100)
        : 255,
      scale_mode: 'stretch',
    });
    setDiscoveryOpen(false);
    setEditDevice(null);
    setModalOpen(true);
  };

  const columns = [
    {
      title: 'Status',
      dataIndex: 'id',
      key: 'status',
      width: 70,
      render: (id: number) =>
        healthMap[id] === true ? (
          <Tag icon={<CheckCircleOutlined />} color="success">Online</Tag>
        ) : healthMap[id] === false ? (
          <Tag icon={<CloseCircleOutlined />} color="error">Offline</Tag>
        ) : (
          <Tag icon={<SyncOutlined spin />} color="processing">...</Tag>
        ),
    },
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'IP Address', dataIndex: 'ip_address', key: 'ip' },
    {
      title: 'Matrix',
      key: 'matrix',
      render: (_: unknown, d: DeviceData) => `${d.matrix_width}×${d.matrix_height}`,
    },
    {
      title: 'Protocol',
      dataIndex: 'communication_protocol',
      key: 'protocol',
      render: (p: string) => (
        <Tag color={p === 'udp_dnrgb' ? 'blue' : 'green'}>
          {p === 'udp_dnrgb' ? 'UDP DNRGB' : 'JSON API'}
        </Tag>
      ),
    },
    {
      title: 'Chains',
      dataIndex: 'chain_count',
      key: 'chains',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, d: DeviceData) => (
        <Space size={4}>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(d)} />
          <Popconfirm title="Delete this device?" onConfirm={() => handleDelete(d.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 80 }} />;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Devices</h2>
        <Space>
          <Button icon={<SearchOutlined />} onClick={handleDiscover} loading={discovering}>
            Discover from HA
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => {
            setEditDevice(null);
            form.resetFields();
            form.setFieldsValue({
              matrix_width: 16, matrix_height: 16,
              communication_protocol: 'udp_dnrgb', chain_count: 1, segment_id: 0,
              base_brightness: 255, scale_mode: 'stretch',
            });
            setModalOpen(true);
          }}>
            Add Device
          </Button>
        </Space>
      </div>

      <Table dataSource={devices} columns={columns} rowKey="id" pagination={false} />

      {/* Add/Edit Modal */}
      <Modal
        open={modalOpen}
        title={editDevice ? 'Edit Device' : 'Add Device'}
        onOk={handleSave}
        onCancel={() => { setModalOpen(false); setEditDevice(null); form.resetFields(); }}
        okText="Save"
        width={520}
      >
        <Form form={form} layout="vertical">
          {/* HA Entity search — auto-fills name + IP */}
          <Form.Item
            name="ha_entity_id"
            label={
              <Space>
                <HomeOutlined />
                <span>Home Assistant Device</span>
              </Space>
            }
            extra="Select a WLED device from HA to auto-fill name and IP"
          >
            <Select
              showSearch
              allowClear
              placeholder="Search WLED devices in Home Assistant..."
              loading={haLoading}
              onDropdownVisibleChange={(open) => { if (open) loadHAOptions(); }}
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={haOptions.map((d) => ({
                value: d.entity_id,
                label: `${d.name}${d.ip_address ? ` (${d.ip_address})` : ''} — ${d.entity_id}`,
              }))}
              onChange={(val) => val ? onHAEntitySelect(val) : onHAEntityClear()}
              notFoundContent={haLoading ? <Spin size="small" /> : 'No WLED devices found'}
            />
          </Form.Item>

          <Divider style={{ margin: '8px 0 16px' }} />

          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input placeholder="Living Room Matrix" />
          </Form.Item>
          <Form.Item
            name="ip_address"
            label="IP Address"
            rules={[{ required: true, message: 'IP address is required for device communication' }]}
            extra={<Text type="secondary">Required — used for UDP/HTTP communication with WLED</Text>}
          >
            <Input placeholder="192.168.1.100" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="matrix_width" label="Width">
                <InputNumber min={1} max={256} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="matrix_height" label="Height">
                <InputNumber min={1} max={256} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="communication_protocol" label="Protocol">
            <Select options={PROTOCOLS} />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="chain_count" label="Chain Count">
                <InputNumber min={1} max={16} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="segment_id" label="Segment ID">
                <InputNumber min={0} max={15} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="scale_mode" label="Scale Mode"
            extra="How to map scene pixels when scene and device sizes differ">
            <Select options={SCALE_MODES} />
          </Form.Item>
          <Form.Item name="base_brightness" label={
            <span>Base Brightness ({form.getFieldValue('base_brightness') ?? 255})</span>
          } extra="Device-level brightness applied to all scenes">
            <Slider min={0} max={255} />
          </Form.Item>
        </Form>
      </Modal>

      {/* HA Discovery Modal */}
      <Modal
        open={discoveryOpen}
        title="WLED Devices in Home Assistant"
        onCancel={() => setDiscoveryOpen(false)}
        footer={null}
        width={600}
      >
        {haDevices.length === 0 ? (
          <Alert message="No WLED devices found" type="info" />
        ) : (
          <div>
            {haDevices.map((d) => {
              const alreadyAdded = devices.some((dev) => dev.ha_entity_id === d.entity_id || dev.ip_address === d.ip_address);
              return (
                <Card key={d.entity_id} size="small" style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong>{d.name}</strong>
                      <br />
                      <span style={{ color: '#888' }}>{d.entity_id}</span>
                      {d.ip_address && <span style={{ marginLeft: 8 }}>({d.ip_address})</span>}
                      <Tag color={d.state === 'on' ? 'green' : 'default'} style={{ marginLeft: 8 }}>
                        {d.state}
                      </Tag>
                    </div>
                    <Button
                      type="primary"
                      size="small"
                      disabled={alreadyAdded}
                      onClick={() => addFromHA(d)}
                    >
                      {alreadyAdded ? 'Already Added' : 'Add'}
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Devices;
