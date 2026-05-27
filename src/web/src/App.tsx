import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ConfigProvider, Layout, Menu } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import {
  DashboardOutlined,
  FolderOpenOutlined,
  HomeOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useState } from 'react';
import Dashboard from './views/Dashboard';
import ProjectHome from './views/ProjectHome';
import TaskDetail from './views/TaskDetail';
import Settings from './views/Settings';
import Workspace from './views/Workspace';
import './App.css';

const { Header, Content, Sider } = Layout;

function AppShell() {
  const [currentTask, setCurrentTask] = useState<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const projectMatch = location.pathname.match(/^\/projects\/([^/]+)/);
  const projectId = projectMatch?.[1] || '';
  const menuItems = [
    { key: 'projects', icon: <HomeOutlined />, label: '项目', path: '/' },
    ...(projectId
      ? [
          { key: 'dashboard', icon: <DashboardOutlined />, label: '任务面板', path: `/projects/${projectId}` },
          { key: 'workspace', icon: <FolderOpenOutlined />, label: '项目工作区', path: `/projects/${projectId}/workspace` },
        ]
      : []),
    { key: 'settings', icon: <SettingOutlined />, label: '系统设置', path: '/settings' },
  ];
  const selectedKey = location.pathname.startsWith('/settings')
    ? 'settings'
    : location.pathname.includes('/workspace')
      ? 'workspace'
      : location.pathname.startsWith('/projects/')
        ? 'dashboard'
        : location.pathname === '/'
          ? 'projects'
      : 'dashboard';

  return (
      <Layout className="app-shell">
        <Sider className="app-sidebar" theme="light" breakpoint="lg" collapsedWidth={80}>
          <div className="brand">
            <div className="brand-mark">S</div>
            <div className="brand-copy">
              <strong>调度器</strong>
              <span>多代理工作流</span>
            </div>
          </div>
          <Menu
            className="sidebar-menu"
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            onClick={({ key }) => {
              const item = menuItems.find(i => i.key === key);
              if (item) navigate(item.path);
            }}
          />
        </Sider>
        <Layout>
          <Header className="app-header">
            <h3>
              {currentTask ? `任务：${currentTask}` : '调度自动化'}
            </h3>
          </Header>
          <Content className="app-content">
            <Routes>
              <Route path="/" element={<ProjectHome />} />
              <Route path="/projects/:projectId" element={<Dashboard onTaskSelect={setCurrentTask} />} />
              <Route path="/projects/:projectId/task/:taskId" element={<TaskDetail />} />
              <Route path="/projects/:projectId/workspace" element={<Workspace />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
  );
}

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
