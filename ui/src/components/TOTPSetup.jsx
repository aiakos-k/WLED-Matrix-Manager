import { useState, useEffect } from 'react';
import { Modal, Steps, Input, Button, message, Alert, Space, Typography } from 'antd';
import {
  QrcodeOutlined,
  LockOutlined,
  CheckCircleOutlined,
  SafetyOutlined,
} from '@ant-design/icons';
import api from '../services/api';

const { Title, Paragraph, Text } = Typography;
const { Step } = Steps;

export default function TOTPSetupModal({ open, onClose, onSuccess }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [secret, setSecret] = useState('');
  const [qrCodeUrl, setQrCodeUrl] = useState('');
  const [verifyCode, setVerifyCode] = useState('');
  const [setupLoading, setSetupLoading] = useState(true);

  useEffect(() => {
    if (open) {
      fetchTOTPSetup();
    } else {
      // Reset state when modal closes
      setCurrentStep(0);
      setSecret('');
      setQrCodeUrl('');
      setVerifyCode('');
    }
  }, [open]);

  const fetchTOTPSetup = async () => {
    try {
      setSetupLoading(true);
      const response = await api.get('/auth/totp/setup');

      setSecret(response.secret);
      setQrCodeUrl(response.qr_code);
    } catch (error) {
      console.error('Failed to setup TOTP:', error);
      message.error('Failed to generate TOTP setup. Please try again.');
      onClose();
    } finally {
      setSetupLoading(false);
    }
  };

  const handleVerifyAndEnable = async () => {
    if (!verifyCode || verifyCode.length !== 6) {
      message.error('Please enter a valid 6-digit code');
      return;
    }

    try {
      setLoading(true);

      await api.post('/auth/totp/enable', {
        secret: secret,
        token: verifyCode,
      });

      message.success('2FA enabled successfully!');
      setCurrentStep(2);
      onSuccess?.();

      // Auto-close after 2 seconds
      setTimeout(() => {
        onClose();
      }, 2000);
    } catch (error) {
      console.error('Failed to enable TOTP:', error);
      message.error(error.response?.data?.message || 'Invalid code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const steps = [
    {
      title: 'Scan QR Code',
      icon: <QrcodeOutlined />,
      content: (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Alert
            message="Install an Authenticator App"
            description="You need an authenticator app like Google Authenticator, Microsoft Authenticator, or Authy on your smartphone."
            type="info"
            showIcon
          />

          {setupLoading ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>Loading...</div>
          ) : (
            <>
              <div style={{ textAlign: 'center' }}>
                <Title level={4}>Scan this QR code with your authenticator app</Title>
                {qrCodeUrl && (
                  <img
                    src={`data:image/png;base64,${qrCodeUrl.replace('data:image/png;base64,', '')}`}
                    alt="TOTP QR Code"
                    style={{
                      maxWidth: '300px',
                      border: '1px solid #d9d9d9',
                      borderRadius: '8px',
                      padding: '16px',
                      backgroundColor: 'white',
                    }}
                  />
                )}
              </div>

              <Alert
                message="Manual Entry"
                description={
                  <div>
                    If you can&apos;t scan the QR code, enter this secret key manually:
                    <br />
                    <Text code copyable style={{ fontSize: '16px', marginTop: '8px' }}>
                      {secret}
                    </Text>
                  </div>
                }
                type="warning"
              />
            </>
          )}
        </Space>
      ),
    },
    {
      title: 'Verify Code',
      icon: <LockOutlined />,
      content: (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Alert
            message="Enter Verification Code"
            description="Open your authenticator app and enter the 6-digit code it displays for LED Matrix Manager."
            type="info"
            showIcon
          />

          <div>
            <Title level={4}>Enter 6-digit code from your app:</Title>
            <Input
              size="large"
              placeholder="000000"
              value={verifyCode}
              onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              style={{ fontSize: '24px', textAlign: 'center', letterSpacing: '8px' }}
              autoFocus
              onPressEnter={handleVerifyAndEnable}
            />
          </div>

          <Button
            type="primary"
            size="large"
            block
            onClick={handleVerifyAndEnable}
            loading={loading}
            disabled={verifyCode.length !== 6}
            icon={<SafetyOutlined />}
          >
            Verify and Enable 2FA
          </Button>
        </Space>
      ),
    },
    {
      title: 'Complete',
      icon: <CheckCircleOutlined />,
      content: (
        <Space direction="vertical" size="large" style={{ width: '100%', textAlign: 'center' }}>
          <CheckCircleOutlined style={{ fontSize: '64px', color: '#52c41a' }} />
          <Title level={3}>2FA Enabled Successfully!</Title>
          <Paragraph>
            Your account is now protected with Two-Factor Authentication. You&apos;ll need your
            authenticator app to log in from now on.
          </Paragraph>
        </Space>
      ),
    },
  ];

  return (
    <Modal
      title="Enable Two-Factor Authentication (2FA)"
      open={open}
      onCancel={onClose}
      width={600}
      footer={
        currentStep < 2
          ? [
              <Button key="cancel" onClick={onClose}>
                Cancel
              </Button>,
              currentStep === 0 && (
                <Button
                  key="next"
                  type="primary"
                  onClick={() => setCurrentStep(1)}
                  disabled={setupLoading}
                >
                  Next: Verify Code
                </Button>
              ),
            ]
          : null
      }
    >
      <Steps current={currentStep} style={{ marginBottom: '32px' }}>
        {steps.map((step) => (
          <Step key={step.title} title={step.title} icon={step.icon} />
        ))}
      </Steps>

      <div style={{ minHeight: '300px' }}>{steps[currentStep].content}</div>
    </Modal>
  );
}
