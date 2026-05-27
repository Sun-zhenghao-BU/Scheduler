import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Empty, Form, Input, List, Modal, Space, Tag, Tree, message } from 'antd';
import { FolderOpenOutlined, PlusOutlined, RightOutlined } from '@ant-design/icons';
import { createProject, getWorkspaceTree, listProjects } from '../api';
import type { Project, WorkspaceItem } from '../types';

function ProjectHome() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [directoryModalOpen, setDirectoryModalOpen] = useState(false);
  const [workspaceItems, setWorkspaceItems] = useState<WorkspaceItem[]>([]);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    listProjects()
      .then((data) => {
        if (active) setProjects(data);
      })
      .catch(() => {
        message.error('项目列表加载失败');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleCreate = async (values: { name: string; root_path?: string }) => {
    try {
      const project = await createProject(values.name, values.root_path || '');
      message.success('项目已创建');
      setModalOpen(false);
      form.resetFields();
      navigate(`/projects/${project.project_id}`);
    } catch {
      message.error('项目创建失败');
    }
  };

  const openDirectoryPicker = async () => {
    setDirectoryModalOpen(true);
    setWorkspaceLoading(true);
    try {
      setWorkspaceItems(await getWorkspaceTree());
    } catch {
      message.error('目录树加载失败');
    } finally {
      setWorkspaceLoading(false);
    }
  };

  const directoryTree = workspaceItems
    .filter(item => item.type === 'directory')
    .map(item => ({
      title: item.path || '/',
      key: item.path || '.',
      isLeaf: true,
    }));

  return (
    <div className="project-home">
      <div className="project-actions">
        <div className="page-surface project-action-card">
          <h3>创建项目</h3>
          <p>从一个新项目开始，把后续需求、开发和测试都收敛到这个项目里。</p>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            创建项目
          </Button>
        </div>
        <div className="page-surface project-action-card">
          <h3>打开项目</h3>
          <p>继续已有项目中的任务流，回到需求确认、开发或测试阶段。</p>
          <Button icon={<FolderOpenOutlined />} onClick={() => document.getElementById('project-list')?.scrollIntoView({ behavior: 'smooth' })}>
            查看已有项目
          </Button>
        </div>
      </div>

      <div id="project-list" className="page-surface project-entry">
        <div className="section-heading">
          <div>
            <h3>已有项目</h3>
            <p>打开一个项目后，任务面板和项目工作区会在侧边栏中出现。</p>
          </div>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新建项目
          </Button>
        </div>

        {projects.length === 0 && !loading ? (
          <Empty description="还没有项目">
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
              新建第一个项目
            </Button>
          </Empty>
        ) : (
          <List
            loading={loading}
            dataSource={projects}
            renderItem={(project) => (
              <List.Item
                className="project-item"
                actions={[
                  <Button
                    key="open"
                    type="link"
                    icon={<RightOutlined />}
                    onClick={() => navigate(`/projects/${project.project_id}`)}
                  >
                    打开
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  avatar={<FolderOpenOutlined className="project-icon" />}
                  title={project.name}
                  description={
                    <Space direction="vertical" size={2}>
                      <code>{project.project_id}</code>
                      {project.root_path ? <span>{project.root_path}</span> : <Tag>未绑定目录</Tag>}
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </div>

      <Modal
        title="新建项目"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
            <Input placeholder="例如：Scheduler 自动化平台" />
          </Form.Item>
          <Form.Item name="root_path" label="本地目录（可选）">
            <Space.Compact style={{ width: '100%' }}>
              <Input placeholder="选择已挂载目录，或手动输入路径" />
              <Button onClick={openDirectoryPicker}>选择目录</Button>
            </Space.Compact>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="选择已挂载目录"
        open={directoryModalOpen}
        onCancel={() => setDirectoryModalOpen(false)}
        footer={null}
      >
        {workspaceLoading ? (
          <Empty description="正在加载目录" />
        ) : directoryTree.length === 0 ? (
          <Empty description="当前挂载工作区没有可选目录" />
        ) : (
          <Tree
            showIcon
            treeData={directoryTree}
            onSelect={(keys) => {
              const selected = String(keys[0] || '');
              if (!selected) return;
              form.setFieldValue('root_path', selected === '.' ? '/workspace/project' : `/workspace/project/${selected}`);
              setDirectoryModalOpen(false);
            }}
          />
        )}
      </Modal>
    </div>
  );
}

export default ProjectHome;
