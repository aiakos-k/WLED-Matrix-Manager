import React, { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Button, Space, Spin } from 'antd';
import {
  AppstoreOutlined,
  ApiOutlined,
  PlayCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getStats } from '@/api/client';

const Home: React.FC = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<{
    total_scenes: number;
    total_devices: number;
    active_playbacks: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  const loadStats = async () => {
    try {
      const data = await getStats();
      setStats(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 80 }} />;

  return (
    <div>
      <h2>Dashboard</h2>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate('/scenes')}>
            <Statistic
              title="Scenes"
              value={stats?.total_scenes ?? 0}
              prefix={<AppstoreOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate('/devices')}>
            <Statistic
              title="Devices"
              value={stats?.total_devices ?? 0}
              prefix={<ApiOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Active Playbacks"
              value={stats?.active_playbacks ?? 0}
              prefix={<PlayCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <div style={{ marginTop: 32 }}>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} size="large" onClick={() => navigate('/scenes/new')}>
            Create New Scene
          </Button>
          <Button icon={<AppstoreOutlined />} size="large" onClick={() => navigate('/scenes')}>
            Manage Scenes
          </Button>
          <Button icon={<ApiOutlined />} size="large" onClick={() => navigate('/devices')}>
            Manage Devices
          </Button>
        </Space>
      </div>
    </div>
  );
};

export default Home;
