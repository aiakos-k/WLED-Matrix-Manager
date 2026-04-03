import { Layout, Space } from 'antd';
import { Link } from 'react-router-dom';
import { HeartFilled } from '@ant-design/icons';

const { Footer } = Layout;

export default function FooterBar() {
  return (
    <Footer style={{ textAlign: 'center', padding: '24px 50px' }}>
      <Space direction="vertical" size="small">
        <Link to="/" style={{ color: 'inherit', textDecoration: 'none' }}>
          LED Matrix Manager
        </Link>
        <Space split="|" size="middle" style={{ fontSize: '12px' }}>
          <span>
            © {new Date().getFullYear()} with <HeartFilled style={{ color: '#ff4d4f' }} />
          </span>
          <Link to="/legal">Legal</Link>
        </Space>
      </Space>
    </Footer>
  );
}
