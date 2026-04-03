import { Card, Form, Input, Button, Space, Alert, Tabs, Divider } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { HomeOutlined, LockOutlined } from '@ant-design/icons';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';

export default function Login({ onLoginSuccess }) {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('login'); // 'login' or 'register'
  const [loginForm] = Form.useForm();
  const [registerForm] = Form.useForm();

  // TOTP 2FA state
  const [totpRequired, setTotpRequired] = useState(false);
  const [totpUsername, setTotpUsername] = useState('');
  const [totpCode, setTotpCode] = useState('');

  const handleLogin = async (values) => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.post('/auth/login', {
        username: values.username,
        password: values.password,
      });

      const data = response.data || response;

      // Check if TOTP is required
      if (data.totp_required) {
        setTotpRequired(true);
        setTotpUsername(data.username);
        setLoading(false);
        return;
      }

      // Normal login (no TOTP)
      const { token, user } = data;

      // Update auth context
      login(user, token);

      // Call parent callback if provided
      if (onLoginSuccess) {
        onLoginSuccess(user, token);
      }

      // Redirect to scenes
      navigate('/scenes');
    } catch (err) {
      console.error('Login error:', err);
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleTOTPVerify = async () => {
    if (!totpCode || totpCode.length !== 6) {
      setError('Please enter a valid 6-digit code');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await api.post('/auth/totp/verify', {
        username: totpUsername,
        token: totpCode,
      });

      const { token, user } = response.data || response;

      // Update auth context
      login(user, token);

      // Call parent callback if provided
      if (onLoginSuccess) {
        onLoginSuccess(user, token);
      }

      // Redirect to scenes
      navigate('/scenes');
    } catch (err) {
      console.error('TOTP verification error:', err);
      setError(err.response?.data?.message || 'Invalid 2FA code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleBackToLogin = () => {
    setTotpRequired(false);
    setTotpUsername('');
    setTotpCode('');
    setError(null);
    loginForm.resetFields();
  };

  const handleRegister = async (values) => {
    setLoading(true);
    setError(null);

    try {
      if (values.password !== values.confirmPassword) {
        setError('Passwords do not match');
        setLoading(false);
        return;
      }

      const response = await api.post('/auth/register', {
        username: values.username,
        email: values.email,
        password: values.password,
      });

      const { token, user } = response.data || response;

      // Update auth context
      login(user, token);

      // Call parent callback if provided
      if (onLoginSuccess) {
        onLoginSuccess(user, token);
      }

      // Redirect to scenes
      navigate('/scenes');
    } catch (err) {
      console.error('Register error:', err);
      setError(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  // TOTP verification screen
  if (totpRequired) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          background: '#f0f2f5',
        }}
      >
        <Card
          title={
            <Space>
              <LockOutlined />
              Two-Factor Authentication
            </Space>
          }
          style={{ width: 400, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
        >
          {error && <Alert message={error} type="error" showIcon style={{ marginBottom: 16 }} />}

          <Alert
            message={`Logged in as: ${totpUsername}`}
            description="Enter the 6-digit code from your authenticator app"
            type="info"
            showIcon
            style={{ marginBottom: 24 }}
          />

          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <div>
              <Input
                size="large"
                placeholder="000000"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                maxLength={6}
                style={{ fontSize: '24px', textAlign: 'center', letterSpacing: '8px' }}
                autoFocus
                onPressEnter={handleTOTPVerify}
                prefix={<LockOutlined />}
              />
            </div>

            <Button
              type="primary"
              size="large"
              block
              onClick={handleTOTPVerify}
              loading={loading}
              disabled={totpCode.length !== 6}
            >
              Verify & Login
            </Button>

            <Button block onClick={handleBackToLogin}>
              Back to Login
            </Button>
          </Space>
        </Card>
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: '#f0f2f5',
      }}
    >
      <Card
        title="LED Matrix Manager"
        style={{ width: 400, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
      >
        {error && <Alert message={error} type="error" showIcon style={{ marginBottom: 16 }} />}

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'login',
              label: 'Login',
              children: (
                <Form form={loginForm} layout="vertical" onFinish={handleLogin} autoComplete="off">
                  <Form.Item
                    label="Username"
                    name="username"
                    rules={[{ required: true, message: 'Please enter username' }]}
                  >
                    <Input placeholder="Enter your username" />
                  </Form.Item>

                  <Form.Item
                    label="Password"
                    name="password"
                    rules={[{ required: true, message: 'Please enter password' }]}
                  >
                    <Input.Password placeholder="Enter your password" />
                  </Form.Item>

                  <Button type="primary" htmlType="submit" block loading={loading}>
                    Login
                  </Button>
                </Form>
              ),
            },
            {
              key: 'register',
              label: 'Register',
              children: (
                <Form
                  form={registerForm}
                  layout="vertical"
                  onFinish={handleRegister}
                  autoComplete="off"
                >
                  <Form.Item
                    label="Username"
                    name="username"
                    rules={[{ required: true, message: 'Please enter username' }]}
                  >
                    <Input placeholder="Choose a username" />
                  </Form.Item>

                  <Form.Item
                    label="Email"
                    name="email"
                    rules={[
                      { required: true, message: 'Please enter email' },
                      { type: 'email', message: 'Invalid email' },
                    ]}
                  >
                    <Input placeholder="Enter your email" />
                  </Form.Item>

                  <Form.Item
                    label="Password"
                    name="password"
                    rules={[{ required: true, message: 'Please enter password' }]}
                  >
                    <Input.Password placeholder="Create a password" />
                  </Form.Item>

                  <Form.Item
                    label="Confirm Password"
                    name="confirmPassword"
                    rules={[{ required: true, message: 'Please confirm password' }]}
                  >
                    <Input.Password placeholder="Confirm your password" />
                  </Form.Item>

                  <Button type="primary" htmlType="submit" block loading={loading}>
                    Register
                  </Button>
                </Form>
              ),
            },
          ]}
        />

        <Divider style={{ margin: '16px 0' }} />

        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Button block icon={<HomeOutlined />} onClick={() => navigate('/scenes')}>
            Continue to Scenes (without login)
          </Button>
          <div style={{ textAlign: 'center', fontSize: 12, color: '#999' }}>
            Browse available scenes and preview them without registration
          </div>
        </Space>
      </Card>
    </div>
  );
}
