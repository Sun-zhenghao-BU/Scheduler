import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Empty, Form, Input, List, Modal, Space, Tag, message } from 'antd';
import { FolderOpenOutlined, PlusOutlined, RightOutlined } from '@ant-design/icons';
import { createProject, listProjects } from '../api';
import type { Project } from '../types';

function ProjectHome() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
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

  return (
    <div className="project-home">
      <div className="page-surface project-entry">
        <div className="section-heading">
          <div>
            <h3>选择项目</h3>
            <p>先进入一个项目，再围绕这个项目创建需求、开发和测试任务。</p>
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
            <Input placeholder="例如：C:\\Users\\Zhenghao\\Project\\Scheduler" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default ProjectHome;
