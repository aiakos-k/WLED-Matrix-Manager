import React from 'react';
import { Layout, Menu } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  HomeOutlined,
  AppstoreOutlined,
  ApiOutlined,
} from '@ant-design/icons';

const { Header } = Layout;

const menuItems = [
  { key: '/', icon: <HomeOutlined />, label: 'Home' },
  { key: '/scenes', icon: <AppstoreOutlined />, label: 'Scenes' },
  { key: '/devices', icon: <ApiOutlined />, label: 'Devices' },
];

const HeaderBar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const selectedKey = menuItems.find(
    (item) => item.key !== '/' && location.pathname.startsWith(item.key),
  )?.key ?? '/';

  return (
    <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px' }}>
      <div style={{ color: '#fff', fontWeight: 'bold', fontSize: 18, marginRight: 32, whiteSpace: 'nowrap' }}>
        WLED Matrix Manager
      </div>
      <Menu
        theme="dark"
        mode="horizontal"
        selectedKeys={[selectedKey]}
        items={menuItems}
        onClick={({ key }) => navigate(key)}
        style={{ flex: 1, minWidth: 0 }}
      />
    </Header>
  );
};

export default HeaderBar;
