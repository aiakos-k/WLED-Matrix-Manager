import React, { useEffect, useState, useCallback } from 'react';
import {
  Button, Card, Col, Form, Input, InputNumber, message, Modal,
  Row, Select, Space, Table, Tag, Popconfirm, Spin, Alert,
} from 'antd';
import {
  PlusOutlined, SearchOutlined, DeleteOutlined, EditOutlined,
  CheckCircleOutlined, CloseCircleOutlined, SyncOutlined,
} from '@ant-design/icons';
import {
  getDevices, createDevice, updateDevice, deleteDevice,
  checkDeviceHealth, discoverHADevices,
  type DeviceData, type HADevice,
} from '@/api/client';

const PROTOCOLS = [
  { value: 'udp_dnrgb', label: 'UDP DNRGB (Recommended)' },
  { value: 'json_api', label: 'JSON API (HTTP)' },
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

  // ─── HA Discovery ─────────────────────────────────────

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      const result = await discoverHADevices();
      setHaDevices(result.devices);
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
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input placeholder="Living Room Matrix" />
          </Form.Item>
          <Form.Item name="ip_address" label="IP Address" rules={[{ required: true }]}>
            <Input placeholder="192.168.1.100" />
          </Form.Item>
          <Form.Item name="ha_entity_id" label="HA Entity ID">
            <Input placeholder="light.wled_matrix" />
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
