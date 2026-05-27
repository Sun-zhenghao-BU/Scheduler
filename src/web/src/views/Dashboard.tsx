import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Table, Button, Tag, Space, Modal, Form, Input, message } from 'antd';
import { PlusOutlined, EyeOutlined } from '@ant-design/icons';
import { createTask, getProject, listProjectTasks } from '../api';
import type { Project, Task } from '../types';
import { STAGES, STAGE_LABELS, STAGE_COLORS, type Stage } from '../types';

interface Props {
  onTaskSelect: (taskId: string | null) => void;
}

function Dashboard({ onTaskSelect }: Props) {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const fetchTasks = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const data = await listProjectTasks(projectId);
      setTasks(data);
    } catch {
      message.error('任务列表加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    let active = true;
    getProject(projectId)
      .then((data) => {
        if (active) setProject(data);
      })
      .catch(() => {
        message.error('项目加载失败');
      });
    listProjectTasks(projectId)
      .then((data) => {
        if (active) setTasks(data);
      })
      .catch(() => {
        message.error('任务列表加载失败');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [projectId]);

  const handleCreate = async (values: { title: string; request?: string }) => {
    if (!projectId) return;
    try {
      await createTask(values.title, values.request || '', projectId);
      message.success('任务已创建');
      setModalOpen(false);
      form.resetFields();
      fetchTasks();
    } catch {
      message.error('任务创建失败');
    }
  };

  const stageIndex = (stage: string) => STAGES.indexOf(stage as Stage);

  const columns = [
    {
      title: '任务 ID',
      dataIndex: 'task_id',
      key: 'task_id',
      render: (id: string) => <code style={{ fontSize: 12 }}>{id}</code>,
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '阶段',
      dataIndex: 'current_stage',
      key: 'current_stage',
      render: (stage: string) => (
        <Tag color={STAGE_COLORS[stage as Stage] || 'default'}>
          {STAGE_LABELS[stage as Stage] || stage}
        </Tag>
      ),
    },
    {
      title: '进度',
      key: 'progress',
      render: (_: unknown, record: Task) => {
        const idx = stageIndex(record.current_stage);
        const pct = Math.round(((idx + 1) / STAGES.length) * 100);
        return `${pct}%`;
      },
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (ts: string) => new Date(ts).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: Task) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              onTaskSelect(record.title);
              navigate(`/projects/${record.project_id}/task/${record.task_id}`);
            }}
          >
            查看
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div className="page-surface dashboard-page">
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0 }}>{project?.name || '项目任务'}</h2>
          <p style={{ margin: '4px 0 0', color: '#667085', fontSize: 12 }}>
            在当前项目内创建需求，然后按需求确认、开发、测试推进。
          </p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建任务
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={tasks}
        rowKey="task_id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />
      <Modal
        title="新建任务"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入任务标题' }]}>
            <Input placeholder="请输入任务标题" />
          </Form.Item>
          <Form.Item name="request" label="需求描述（可选）">
            <Input.TextArea rows={4} placeholder="请描述需求、目标或背景" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default Dashboard;
