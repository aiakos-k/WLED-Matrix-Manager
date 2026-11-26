import { ConfigProvider, Layout, theme } from "antd";
import type React from "react";
import { Route, Routes } from "react-router-dom";
import HeaderBar from "@/components/HeaderBar";
import Devices from "@/pages/Devices";
import Home from "@/pages/Home";
import SceneEditor from "@/pages/SceneEditor";
import Scenes from "@/pages/Scenes";

const { Content, Footer } = Layout;

const App: React.FC = () => (
  <ConfigProvider theme={{ algorithm: theme.defaultAlgorithm }}>
    <Layout style={{ minHeight: "100vh" }}>
      <HeaderBar />
      <Content style={{ padding: "24px", background: "#f5f5f5" }}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/scenes" element={<Scenes />} />
          <Route path="/scenes/new" element={<SceneEditor />} />
          <Route path="/scenes/:id/edit" element={<SceneEditor />} />
          <Route path="/devices" element={<Devices />} />
        </Routes>
      </Content>
      <Footer style={{ textAlign: "center" }}>
        WLED Matrix Manager &copy; {new Date().getFullYear()}
      </Footer>
    </Layout>
  </ConfigProvider>
);

export default App;
