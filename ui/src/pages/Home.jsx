import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Button, Typography, Space, Alert } from 'antd';
import {
  RocketOutlined,
  BulbOutlined,
  VideoCameraOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../hooks/useAuth';

const { Title, Paragraph, Text } = Typography;

const Home = () => {
  const { isLoggedIn, isAdmin } = useAuth();
  const [stats, setStats] = useState({
    scenes: 0,
    devices: 0,
    activeScenes: 0,
    onlineDevices: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();

    // Refresh stats every 5 seconds to update active scenes and online devices
    const interval = setInterval(() => {
      fetchStats();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      // Use public stats endpoint - no authentication required
      const stats = await api.get('/stats/');

      setStats({
        scenes: stats.total_scenes || 0,
        devices: stats.total_devices || 0,
        activeScenes: stats.active_scenes || 0,
        onlineDevices: stats.active_devices || 0,
      });
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      // Set to 0 on error
      setStats({
        scenes: 0,
        devices: 0,
        activeScenes: 0,
        onlineDevices: 0,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px' }}>
      {/* Hero Section */}
      <Card
        style={{
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          marginBottom: '24px',
          color: 'white',
        }}
        bordered={false}
      >
        <Row align="middle" gutter={[24, 24]}>
          <Col xs={24} md={16}>
            <Space direction="vertical" size="large">
              <Title level={1} style={{ color: 'white', margin: 0 }}>
                🎨 LED Matrix Manager
              </Title>
              <Paragraph style={{ color: 'white', fontSize: '16px', margin: 0 }}>
                Erstelle, verwalte und steuere LED-Matrix-Animationen mit einer intuitiven
                Web-Oberfläche. Pixel für Pixel oder per Bild-Upload - deine Kreativität kennt keine
                Grenzen!
              </Paragraph>
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                {isLoggedIn ? (
                  <Row gutter={[8, 8]} style={{ width: '100%', maxWidth: '500px' }}>
                    <Col xs={24} sm={12}>
                      <Link to="/create-scene" style={{ width: '100%', display: 'block' }}>
                        <Button type="primary" size="large" icon={<ThunderboltOutlined />} block>
                          Neue Scene erstellen
                        </Button>
                      </Link>
                    </Col>
                    <Col xs={24} sm={12}>
                      <Link to="/scenes" style={{ width: '100%', display: 'block' }}>
                        <Button size="large" style={{ background: 'white' }} block>
                          Scenes verwalten
                        </Button>
                      </Link>
                    </Col>
                  </Row>
                ) : (
                  <Link to="/scenes">
                    <Button type="primary" size="large" icon={<ThunderboltOutlined />}>
                      Scenes ansehen
                    </Button>
                  </Link>
                )}
              </Space>
            </Space>
          </Col>
          <Col xs={24} md={8} style={{ textAlign: 'center' }}>
            <RocketOutlined style={{ fontSize: '120px', color: 'white', opacity: 0.3 }} />
          </Col>
        </Row>
      </Card>

      {/* Statistics */}
      <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
        <Col xs={12} sm={6}>
          <Card loading={loading}>
            <Statistic
              title="Scenes"
              value={stats.scenes}
              prefix={<VideoCameraOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card loading={loading}>
            <Statistic
              title="Aktive Scenes"
              value={stats.activeScenes}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card loading={loading}>
            <Statistic
              title="Geräte"
              value={stats.devices}
              prefix={<BulbOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card loading={loading}>
            <Statistic
              title="Aktive"
              value={stats.onlineDevices}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Quick Start Guide */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <RocketOutlined />
                <span>Quick Start</span>
              </Space>
            }
            bordered={false}
          >
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              {isLoggedIn ? (
                <>
                  {isAdmin && (
                    <div>
                      <Title level={5}>1. Gerät hinzufügen</Title>
                      <Paragraph>
                        Gehe zu <Link to="/devices">Geräte</Link> und füge deine LED-Matrix per
                        IP-Adresse hinzu. Unterstützt werden WLED-kompatible Geräte (HTTP) und UDP
                        DNRGB Protocol 4.
                      </Paragraph>
                    </div>
                  )}

                  <div>
                    <Title level={5}>{isAdmin ? '2' : '1'}. Scene erstellen</Title>
                    <Paragraph>
                      Erstelle eine neue <Link to="/create-scene">Scene</Link> - male Pixel manuell
                      oder lade ein Bild hoch. Füge mehrere Frames hinzu für Animationen.
                    </Paragraph>
                  </div>

                  <div>
                    <Title level={5}>{isAdmin ? '3' : '2'}. Abspielen</Title>
                    <Paragraph>
                      Gehe zu <Link to="/scenes">Scene Manager</Link> und starte deine Animation mit
                      einem Klick auf Play!
                    </Paragraph>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <Title level={5}>1. Scenes ansehen</Title>
                    <Paragraph>
                      Gehe zu <Link to="/scenes">Scene Manager</Link> und schaue dir alle
                      verfügbaren Animationen an.
                    </Paragraph>
                  </div>

                  <div>
                    <Title level={5}>2. Preview & Abspielen</Title>
                    <Paragraph>
                      Klicke auf &quot;Start Preview&quot; um eine Animation im Browser zu sehen,
                      oder auf &quot;Play&quot; um sie auf den LED-Matrizen abzuspielen.
                    </Paragraph>
                  </div>

                  <div>
                    <Title level={5}>3. Account erstellen</Title>
                    <Paragraph>
                      <Link to="/login">Melde dich an</Link> oder registriere dich, um eigene Scenes
                      zu erstellen und zu verwalten.
                    </Paragraph>
                  </div>
                </>
              )}
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <BulbOutlined />
                <span>Features</span>
              </Space>
            }
            bordered={false}
          >
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Card size="small" style={{ background: '#f0f5ff', border: '1px solid #adc6ff' }}>
                <Row gutter={16} align="middle">
                  <Col xs={24} sm={14} style={{ textAlign: 'center', padding: '12px' }}>
                    <img
                      src="/demo/pixel-editor.gif"
                      alt="Pixel Editor Demo"
                      style={{
                        width: '100%',
                        maxWidth: '400px',
                        height: 'auto',
                        borderRadius: '8px',
                        border: '2px solid #adc6ff',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                      }}
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.nextSibling.style.display = 'block';
                      }}
                    />
                    <div
                      style={{
                        display: 'none',
                        fontSize: '80px',
                        background: 'linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        fontWeight: 'bold',
                      }}
                    >
                      🎨
                    </div>
                  </Col>
                  <Col xs={24} sm={10}>
                    <Title level={5} style={{ marginTop: '8px', marginBottom: '4px' }}>
                      Pixel Editor
                    </Title>
                    <Text type="secondary">
                      Male Pixel für Pixel mit Farbwähler und Helligkeitsregler
                    </Text>
                  </Col>
                </Row>
              </Card>

              <Card size="small" style={{ background: '#f6ffed', border: '1px solid #b7eb8f' }}>
                <Row gutter={16} align="middle">
                  <Col xs={24} sm={14} style={{ textAlign: 'center', padding: '12px' }}>
                    <img
                      src="/demo/image-upload.gif"
                      alt="Bild Upload Demo"
                      style={{
                        width: '100%',
                        maxWidth: '400px',
                        height: 'auto',
                        borderRadius: '8px',
                        border: '2px solid #b7eb8f',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                      }}
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.nextSibling.style.display = 'block';
                      }}
                    />
                    <div
                      style={{
                        display: 'none',
                        fontSize: '80px',
                        background: 'linear-gradient(45deg, #52c41a, #73d13d)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        fontWeight: 'bold',
                      }}
                    >
                      📤
                    </div>
                  </Col>
                  <Col xs={24} sm={10}>
                    <Title level={5} style={{ marginTop: '8px', marginBottom: '4px' }}>
                      Bild Upload
                    </Title>
                    <Text type="secondary">
                      Lade PNG/JPG hoch - automatische Skalierung und Color Quantization
                    </Text>
                  </Col>
                </Row>
              </Card>

              <Card size="small" style={{ background: '#fff7e6', border: '1px solid #ffd591' }}>
                <Row gutter={16} align="middle">
                  <Col xs={24} sm={14} style={{ textAlign: 'center', padding: '12px' }}>
                    <img
                      src="/demo/animation.gif"
                      alt="Animation Demo"
                      style={{
                        width: '100%',
                        maxWidth: '400px',
                        height: 'auto',
                        borderRadius: '8px',
                        border: '2px solid #ffd591',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                      }}
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.nextSibling.style.display = 'block';
                      }}
                    />
                    <div
                      style={{
                        display: 'none',
                        fontSize: '80px',
                        animation: 'spin 2s linear infinite',
                      }}
                    >
                      🔄
                    </div>
                  </Col>
                  <Col xs={24} sm={10}>
                    <Title level={5} style={{ marginTop: '8px', marginBottom: '4px' }}>
                      Multi-Frame Animationen
                    </Title>
                    <Text type="secondary">
                      Erstelle Animationen mit mehreren Frames und konfigurierbarer Geschwindigkeit
                    </Text>
                  </Col>
                </Row>
              </Card>

              <Card size="small" style={{ background: '#f0f5ff', border: '1px solid #adc6ff' }}>
                <Row gutter={16} align="middle">
                  <Col xs={24} sm={14} style={{ textAlign: 'center', padding: '12px' }}>
                    <div
                      style={{
                        fontSize: '80px',
                        background: 'linear-gradient(45deg, #1890ff, #722ed1)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        fontWeight: 'bold',
                      }}
                    >
                      🖥️
                    </div>
                  </Col>
                  <Col xs={24} sm={10}>
                    <Title level={5} style={{ marginTop: '8px', marginBottom: '4px' }}>
                      Multi-Device Support
                    </Title>
                    <Text type="secondary">
                      Steuere mehrere LED-Matrizen gleichzeitig - UDP & HTTP
                    </Text>
                  </Col>
                </Row>
              </Card>

              <Card size="small" style={{ background: '#f6ffed', border: '1px solid #b7eb8f' }}>
                <Row gutter={16} align="middle">
                  <Col xs={24} sm={14} style={{ textAlign: 'center', padding: '12px' }}>
                    <div
                      style={{
                        fontSize: '80px',
                        background: 'linear-gradient(45deg, #13c2c2, #52c41a)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        fontWeight: 'bold',
                      }}
                    >
                      📏
                    </div>
                  </Col>
                  <Col xs={24} sm={10}>
                    <Title level={5} style={{ marginTop: '8px', marginBottom: '4px' }}>
                      Flexible Größen
                    </Title>
                    <Text type="secondary">
                      Unterstützt 16×16, 32×16, 32×128 und mehr mit automatischem Upscaling
                    </Text>
                  </Col>
                </Row>
              </Card>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* System Info */}
      <Row gutter={[16, 16]} style={{ marginTop: '24px' }}>
        <Col xs={24}>
          <Card
            title={
              <Space>
                <SettingOutlined />
                <span>System</span>
              </Space>
            }
            bordered={false}
            size="small"
          >
            <Space split="|">
              <Text type="secondary">LED Matrix Manager v1.0</Text>
              <Text type="secondary">React 18 + Flask 3</Text>
              <Text type="secondary">
                <Link to="/legal">Impressum & Datenschutz</Link>
              </Text>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Home;
