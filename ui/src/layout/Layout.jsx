import { Layout } from 'antd';
import { Outlet } from 'react-router-dom';
import HeaderBar from '../components/HeaderBar';
import FooterBar from '../components/FooterBar';

const { Content } = Layout;

export default function LayoutWrapper() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <HeaderBar />
      <Content style={{ padding: '24px' }}>
        <Outlet />
      </Content>
      <FooterBar />
    </Layout>
  );
}
