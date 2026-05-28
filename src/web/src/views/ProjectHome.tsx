import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Empty, Form, Input, List, Modal, Space, Tag, Tree, message } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { FolderOpenOutlined, PlusOutlined, RightOutlined } from '@ant-design/icons';
import { createProject, listOpenRootChildren, listOpenRoots, listProjects, updateProject } from '../api';
import type { OpenRoot, Project } from '../types';
import { getErrorMessage } from '../utils/error';

type DirectoryTarget = 'create' | 'open-local';
type DirectoryNode = DataNode & {
  rootId: string;
  relativePath: string;
  absolutePath: string;
};

function basename(path: string): string {
  const normalized = path.replace(/\\/g, '/').replace(/\/+$/, '');
  const parts = normalized.split('/').filter(Boolean);
  return parts[parts.length - 1] || normalized || 'project';
}

function createRootNode(root: OpenRoot): DirectoryNode {
  return {
    title: root.label,
    key: `root:${root.root_id}`,
    rootId: root.root_id,
    relativePath: '',
    absolutePath: root.path,
    isLeaf: false,
    children: [],
  };
}

function ProjectHome() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [openLocalModalOpen, setOpenLocalModalOpen] = useState(false);
  const [existingProjectsOpen, setExistingProjectsOpen] = useState(false);
  const [directoryModalOpen, setDirectoryModalOpen] = useState(false);
  const [directoryLoading, setDirectoryLoading] = useState(false);
  const [openRoots, setOpenRoots] = useState<OpenRoot[]>([]);
  const [directoryTree, setDirectoryTree] = useState<DirectoryNode[]>([]);
  const [directoryTarget, setDirectoryTarget] = useState<DirectoryTarget>('create');
  const [bindingProject, setBindingProject] = useState<Project | null>(null);
  const [createForm] = Form.useForm();
  const [openLocalForm] = Form.useForm();
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    listProjects()
      .then((data) => {
        if (active) {
          setProjects(data);
        }
      })
      .catch((error: unknown) => {
        message.error(getErrorMessage(error, '项目列表加载失败'));
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const openProject = (projectId: string) => {
    setExistingProjectsOpen(false);
    setOpenLocalModalOpen(false);
    setBindingProject(null);
    navigate(`/projects/${projectId}`);
  };

  const startBindingProject = (project: Project) => {
    setBindingProject(project);
    openLocalForm.setFieldsValue({
      name: project.name,
      root_path: project.root_path || '',
    });
    setExistingProjectsOpen(false);
    setOpenLocalModalOpen(true);
  };

  const handleCreate = async (values: { name: string; root_path?: string }) => {
    try {
      const project = await createProject(values.name, values.root_path || '');
      message.success('项目已创建');
      setCreateModalOpen(false);
      createForm.resetFields();
      navigate(`/projects/${project.project_id}`);
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '项目创建失败'));
    }
  };

  const handleOpenLocal = async (values: { name?: string; root_path: string }) => {
    const rootPath = values.root_path.trim();

    if (bindingProject) {
      try {
        await updateProject(bindingProject.project_id, rootPath);
        message.success('项目目录已绑定');
        const projectId = bindingProject.project_id;
        setBindingProject(null);
        setOpenLocalModalOpen(false);
        openLocalForm.resetFields();
        navigate(`/projects/${projectId}`);
      } catch (error: unknown) {
        message.error(getErrorMessage(error, '绑定项目目录失败'));
      }
      return;
    }

    const existing = projects.find((project) => project.root_path === rootPath);
    if (existing) {
      message.success('已打开现有项目');
      openProject(existing.project_id);
      return;
    }

    try {
      const project = await createProject(values.name?.trim() || basename(rootPath), rootPath);
      message.success('本地项目已打开');
      setOpenLocalModalOpen(false);
      openLocalForm.resetFields();
      navigate(`/projects/${project.project_id}`);
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '打开本地项目失败'));
    }
  };

  const openDirectoryBrowser = async (target: DirectoryTarget) => {
    setDirectoryTarget(target);
    setDirectoryModalOpen(true);
    setDirectoryLoading(true);
    try {
      const roots = await listOpenRoots();
      setOpenRoots(roots);
      setDirectoryTree(roots.map(createRootNode));
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '可访问目录根加载失败'));
    } finally {
      setDirectoryLoading(false);
    }
  };

  const updateTreeNodes = (nodes: DirectoryNode[], key: string, children: DirectoryNode[]): DirectoryNode[] =>
    nodes.map((node) => {
      if (node.key === key) {
        return { ...node, children };
      }
      if (node.children) {
        return {
          ...node,
          children: updateTreeNodes(node.children as DirectoryNode[], key, children),
        };
      }
      return node;
    });

  const loadTreeData = async (node: DataNode): Promise<void> => {
    const directoryNode = node as DirectoryNode;
    if (directoryNode.children && directoryNode.children.length > 0) {
      return;
    }
    try {
      const children = await listOpenRootChildren(directoryNode.rootId, directoryNode.relativePath);
      const mapped: DirectoryNode[] = children.map((child) => ({
        title: child.name,
        key: `dir:${directoryNode.rootId}:${child.relative_path}`,
        rootId: directoryNode.rootId,
        relativePath: child.relative_path,
        absolutePath: child.path,
        isLeaf: false,
        children: [],
      }));
      setDirectoryTree((current) => updateTreeNodes(current, String(directoryNode.key), mapped));
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '目录加载失败'));
    }
  };

  const applySelectedDirectory = (node: DirectoryNode) => {
    const form = directoryTarget === 'create' ? createForm : openLocalForm;
    form.setFieldValue('root_path', node.absolutePath);
    if (directoryTarget === 'open-local' && !bindingProject && !form.getFieldValue('name')) {
      form.setFieldValue('name', basename(node.absolutePath));
    }
    setDirectoryModalOpen(false);
  };

  return (
    <div className="project-home">
      <div className="project-actions">
        <div className="page-surface project-action-card">
          <h3>创建项目</h3>
          <p>创建一个新的调度项目，把后续需求、开发和测试都归到这个项目下。</p>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
            创建项目
          </Button>
        </div>
        <div className="page-surface project-action-card">
          <h3>打开本地项目</h3>
          <p>从 Docker 已挂载的目录根中选择一个文件夹，把它绑定为项目工作区。</p>
          <Space>
            <Button
              type="primary"
              icon={<FolderOpenOutlined />}
              onClick={() => {
                setBindingProject(null);
                openLocalForm.resetFields();
                setOpenLocalModalOpen(true);
              }}
            >
              打开文件夹
            </Button>
            <Button onClick={() => setExistingProjectsOpen(true)}>已有项目</Button>
          </Space>
        </div>
      </div>

      <div className="page-surface project-entry">
        <div className="section-heading">
          <div>
            <h3>已有项目</h3>
            <p>已绑定目录的项目可以直接进入；未绑定目录的项目先补绑目录再继续使用。</p>
          </div>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
            新建项目
          </Button>
        </div>

        {projects.length === 0 && !loading ? (
          <Empty description="还没有项目">
            <Button
              type="primary"
              icon={<FolderOpenOutlined />}
              onClick={() => {
                setBindingProject(null);
                openLocalForm.resetFields();
                setOpenLocalModalOpen(true);
              }}
            >
              打开第一个本地项目
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
                  project.root_path ? (
                    <Button
                      key="open"
                      type="link"
                      icon={<RightOutlined />}
                      onClick={() => openProject(project.project_id)}
                    >
                      打开
                    </Button>
                  ) : (
                    <Button key="bind" type="link" onClick={() => startBindingProject(project)}>
                      绑定目录
                    </Button>
                  ),
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
        title="创建项目"
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => createForm.submit()}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
            <Input placeholder="例如：Scheduler 自动化平台" />
          </Form.Item>
          <Form.Item name="root_path" label="本地目录（可选）">
            <Space.Compact style={{ width: '100%' }}>
              <Input readOnly placeholder="可选：从已挂载目录中选择" />
              <Button onClick={() => openDirectoryBrowser('create')}>选择目录</Button>
            </Space.Compact>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={bindingProject ? `绑定项目目录：${bindingProject.name}` : '打开本地项目'}
        open={openLocalModalOpen}
        onCancel={() => {
          setBindingProject(null);
          setOpenLocalModalOpen(false);
        }}
        onOk={() => openLocalForm.submit()}
      >
        <Form form={openLocalForm} layout="vertical" onFinish={handleOpenLocal}>
          <Form.Item name="name" label="项目名称（可选）">
            <Input placeholder="默认使用目录名" disabled={Boolean(bindingProject)} />
          </Form.Item>
          <Form.Item name="root_path" label="项目目录" rules={[{ required: true, message: '请先选择项目目录' }]}>
            <Input readOnly placeholder="请选择目录" />
          </Form.Item>
          <Space>
            <Button type="primary" onClick={() => openDirectoryBrowser('open-local')}>
              选择文件夹
            </Button>
          </Space>
          <div style={{ color: '#667085', fontSize: 12, marginTop: 12 }}>
            目录来源于 Docker 预挂载的宿主目录根。绑定后，任务工作区、开发和测试都会在该路径下执行。
          </div>
        </Form>
      </Modal>

      <Modal title="已有项目" open={existingProjectsOpen} onCancel={() => setExistingProjectsOpen(false)} footer={null}>
        {projects.length === 0 && !loading ? (
          <Empty description="还没有可打开的项目" />
        ) : (
          <List
            loading={loading}
            dataSource={projects}
            renderItem={(project) => (
              <List.Item
                actions={[
                  project.root_path ? (
                    <Button key="open" type="primary" onClick={() => openProject(project.project_id)}>
                      打开
                    </Button>
                  ) : (
                    <Button key="bind" type="primary" onClick={() => startBindingProject(project)}>
                      绑定目录
                    </Button>
                  ),
                ]}
              >
                <List.Item.Meta
                  avatar={<FolderOpenOutlined />}
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
      </Modal>

      <Modal title="选择项目目录" open={directoryModalOpen} onCancel={() => setDirectoryModalOpen(false)} footer={null}>
        {directoryLoading ? (
          <Empty description="正在加载目录根" />
        ) : openRoots.length === 0 ? (
          <Empty description="当前没有可访问的挂载目录，请先配置 Docker 挂载。" />
        ) : (
          <Tree
            showIcon
            loadData={loadTreeData}
            treeData={directoryTree}
            onSelect={(_keys, info) => applySelectedDirectory(info.node as DirectoryNode)}
          />
        )}
      </Modal>
    </div>
  );
}

export default ProjectHome;
