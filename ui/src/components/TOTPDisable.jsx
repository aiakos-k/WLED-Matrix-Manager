import { useState } from 'react';
import { Modal, Input, Button, message, Alert, Space, Typography } from 'antd';
import { LockOutlined, WarningOutlined } from '@ant-design/icons';
import api from '../services/api';

const { Title, Paragraph } = Typography;

export default function TOTPDisableModal({ open, onClose, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [verifyCode, setVerifyCode] = useState('');

  const handleDisable = async () => {
    if (!verifyCode || verifyCode.length !== 6) {
      message.error('Please enter a valid 6-digit code');
      return;
    }

    try {
      setLoading(true);

      await api.post('/auth/totp/disable', {
        token: verifyCode,
      });

      message.success('2FA disabled successfully');
      onSuccess?.();
      onClose();
      setVerifyCode('');
    } catch (error) {
      console.error('Failed to disable TOTP:', error);
      message.error(error.response?.data?.message || 'Invalid code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title="Disable Two-Factor Authentication"
      open={open}
      onCancel={() => {
        onClose();
        setVerifyCode('');
      }}
      width={500}
      footer={[
        <Button
          key="cancel"
          onClick={() => {
            onClose();
            setVerifyCode('');
          }}
        >
          Cancel
        </Button>,
        <Button
          key="disable"
          type="primary"
          danger
          onClick={handleDisable}
          loading={loading}
          disabled={verifyCode.length !== 6}
          icon={<WarningOutlined />}
        >
          Disable 2FA
        </Button>,
      ]}
    >
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Alert
          message="Warning"
          description="Disabling 2FA will make your account less secure. You'll only need your password to log in."
          type="warning"
          showIcon
          icon={<WarningOutlined />}
        />

        <div>
          <Title level={4}>Enter your current 6-digit 2FA code to confirm:</Title>
          <Input
            size="large"
            placeholder="000000"
            value={verifyCode}
            onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            maxLength={6}
            style={{ fontSize: '24px', textAlign: 'center', letterSpacing: '8px' }}
            autoFocus
            onPressEnter={handleDisable}
            prefix={<LockOutlined />}
          />
        </div>

        <Paragraph type="secondary">
          Open your authenticator app and enter the current 6-digit code to disable Two-Factor
          Authentication.
        </Paragraph>
      </Space>
    </Modal>
  );
}
