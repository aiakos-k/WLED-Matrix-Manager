import { Layout, Menu, Button, Space, Dropdown } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  UserOutlined,
  LogoutOutlined,
  LoginOutlined,
  LockOutlined,
  SafetyOutlined,
} from '@ant-design/icons';
import { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import ChangePasswordModal from './ChangePasswordModal';
import TOTPSetup from './TOTPSetup';
import TOTPDisable from './TOTPDisable';

const { Header } = Layout;

export default function HeaderBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isLoggedIn, currentUser, isAdmin, logout, refreshUser } = useAuth();
  const [isChangePasswordModalOpen, setIsChangePasswordModalOpen] = useState(false);
  const [isTOTPSetupOpen, setIsTOTPSetupOpen] = useState(false);
  const [isTOTPDisableOpen, setIsTOTPDisableOpen] = useState(false);

  const items = [
    {
      key: '/',
      label: 'Home',
    },
    {
      key: '/scenes',
      label: 'Scenes',
    },
    ...(isAdmin
      ? [
          {
            key: '/devices',
            label: 'Devices',
          },
          {
            key: '/users',
            label: 'Users',
          },
        ]
      : []),
    {
      key: '/legal',
      label: 'Impressum & Datenschutz',
    },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const userMenuItems = [
    {
      key: 'profile',
      label: `${currentUser?.username} (${currentUser?.role})`,
      disabled: true,
    },
    {
      type: 'divider',
    },
    {
      key: 'change-password',
      icon: <LockOutlined />,
      label: 'Change Password',
      onClick: () => setIsChangePasswordModalOpen(true),
    },
    {
      key: '2fa-settings',
      icon: <SafetyOutlined />,
      label: currentUser?.totp_enabled ? '2FA: Enabled ✓' : '2FA: Disabled',
      onClick: () => {
        if (currentUser?.totp_enabled) {
          setIsTOTPDisableOpen(true);
        } else {
          setIsTOTPSetupOpen(true);
        }
      },
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      onClick: handleLogout,
    },
  ];

  return (
    <Header
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0 24px',
      }}
    >
      <div style={{ flex: 1 }}>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={items}
          onClick={({ key }) => navigate(key)}
        />
      </div>

      <Space>
        {isLoggedIn ? (
          <Dropdown menu={{ items: userMenuItems }}>
            <Button type="text" icon={<UserOutlined />} style={{ color: 'white' }}>
              {currentUser?.username}
            </Button>
          </Dropdown>
        ) : (
          <Button type="primary" icon={<LoginOutlined />} onClick={() => navigate('/login')}>
            Login
          </Button>
        )}
      </Space>

      <ChangePasswordModal
        open={isChangePasswordModalOpen}
        onClose={() => setIsChangePasswordModalOpen(false)}
      />

      <TOTPSetup
        open={isTOTPSetupOpen}
        onClose={() => setIsTOTPSetupOpen(false)}
        onSuccess={() => {
          setIsTOTPSetupOpen(false);
          refreshUser();
        }}
      />

      <TOTPDisable
        open={isTOTPDisableOpen}
        onClose={() => setIsTOTPDisableOpen(false)}
        onSuccess={() => {
          setIsTOTPDisableOpen(false);
          refreshUser();
        }}
      />
    </Header>
  );
}
