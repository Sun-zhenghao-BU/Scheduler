import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Descriptions,
  Tag,
  Button,
  Space,
  Tabs,
  message,
  Input,
  Popconfirm,
  Card,
  Row,
  Col,
} from 'antd';
import { ArrowLeftOutlined, SaveOutlined, StepForwardOutlined, TeamOutlined } from '@ant-design/icons';
import { getTask, advanceTask, updateTaskFile, getAgentResults, runAgentWorkflow } from '../api';
import type { AgentResult, AgentRole, TaskDetail, Stage } from '../types';
import { AGENT_LABELS, STAGES, STAGE_LABELS, STAGE_COLORS } from '../types';

const { TextArea } = Input;

const AGENT_STATUS_LABELS: Record<string, string> = {
  completed: '完成',
  failed: '失败',
  pending: '未运行',
};

const FILE_LABELS: Record<string, string> = {
  'request.md': '需求',
  'spec.md': '产品规划',
  'implementation.md': '实施方案',
  'review.md': '测试方案',
  'fixes.md': '修复记录',
  'release.md': '发布记录',
};

function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [agents, setAgents] = useState<AgentResult[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [editingFile, setEditingFile] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');

  const fetchTask = useCallback(async () => {
    if (!taskId) return;
    setLoading(true);
    try {
      const data = await getTask(taskId);
      setDetail(data);
    } catch {
      message.error('任务加载失败');
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  const fetchAgents = useCallback(async () => {
    if (!taskId) return;
    try {
      setAgents(await getAgentResults(taskId));
    } catch {
      setAgents([]);
    }
  }, [taskId]);

  useEffect(() => {
    fetchTask();
    fetchAgents();
  }, [fetchTask, fetchAgents]);

  const handleAdvance = async () => {
    if (!detail || !taskId) return;
    const currentIdx = STAGES.indexOf(detail.current_stage as Stage);
    if (currentIdx >= STAGES.length - 1) {
      message.info('已经是最终阶段');
      return;
    }
    const nextStage = STAGES[currentIdx + 1];
    try {
      await advanceTask(taskId, nextStage);
      message.success(`已推进到${STAGE_LABELS[nextStage as Stage]}`);
      fetchTask();
    } catch {
      message.error('阶段推进失败');
    }
  };

  const handleSaveFile = async () => {
    if (!taskId || !editingFile) return;
    try {
      await updateTaskFile(taskId, editingFile, editContent);
      message.success('文件已保存');
      setEditingFile(null);
      fetchTask();
    } catch {
      message.error('文件保存失败');
    }
  };

  const handleRunAgents = async () => {
    if (!taskId) return;
    setAgentsLoading(true);
    try {
      const results = await runAgentWorkflow(taskId);
      setAgents(results);
      message.success('代理工作流已完成');
      await fetchTask();
    } catch (err: unknown) {
      const error = err as Error;
      message.error(`代理工作流运行失败：${error.message}`);
    } finally {
      setAgentsLoading(false);
    }
  };

  if (!detail) {
    return loading ? <p>加载中...</p> : <p>任务不存在</p>;
  }

  const currentIdx = STAGES.indexOf(detail.current_stage as Stage);
  const fileTabs = Object.entries(detail.files).map(([name, content]) => ({
    key: name,
    label: FILE_LABELS[name] || name.replace('.md', ''),
    children: (
      <div>
        {editingFile === name ? (
          <div>
            <TextArea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              rows={20}
              style={{ fontFamily: 'monospace', marginBottom: 8 }}
            />
            <Space>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveFile}>
                保存
              </Button>
              <Button onClick={() => setEditingFile(null)}>取消</Button>
            </Space>
          </div>
        ) : (
          <div>
            <Button
              size="small"
              style={{ marginBottom: 8 }}
              onClick={() => {
                setEditingFile(name);
                setEditContent(content);
              }}
            >
              编辑
            </Button>
            <pre
              style={{
                whiteSpace: 'pre-wrap',
                background: '#f5f5f5',
                padding: 16,
                borderRadius: 4,
                maxHeight: '60vh',
                overflow: 'auto',
              }}
            >
              {content}
            </pre>
          </div>
        )}
      </div>
    ),
  }));

  const agentByRole = new Map(agents.map(agent => [agent.role, agent]));
  const roles: AgentRole[] = ['product_manager', 'developer', 'tester'];

  return (
    <div className="task-detail">
      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/')}
        style={{ marginBottom: 16, paddingLeft: 0 }}
      >
        返回任务列表
      </Button>

      <div className="page-surface task-summary">
        <Descriptions
          title={detail.title}
          bordered
          column={2}
          size="small"
          extra={
            currentIdx < STAGES.length - 1 ? (
              <Popconfirm
                title={`确认推进到${STAGE_LABELS[STAGES[currentIdx + 1] as Stage]}？`}
                onConfirm={handleAdvance}
              >
                <Button type="primary" icon={<StepForwardOutlined />}>
                  推进到{STAGE_LABELS[STAGES[currentIdx + 1] as Stage]}
                </Button>
              </Popconfirm>
            ) : (
              <Tag color="green">已完成</Tag>
            )
          }
        >
          <Descriptions.Item label="任务 ID">
            <code style={{ fontSize: 12 }}>{detail.task_id}</code>
          </Descriptions.Item>
          <Descriptions.Item label="阶段">
            <Tag color={STAGE_COLORS[detail.current_stage as Stage]}>
              {STAGE_LABELS[detail.current_stage as Stage]}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {new Date(detail.created_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {new Date(detail.updated_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
        </Descriptions>
      </div>

      <div className="page-surface agents-panel">
        <div className="section-heading">
          <div>
            <h3>代理工作流</h3>
            <p>并行运行产品经理、开发代理和测试代理。结果会覆盖核心任务文件。</p>
          </div>
          <Button type="primary" icon={<TeamOutlined />} loading={agentsLoading} onClick={handleRunAgents}>
            运行代理
          </Button>
        </div>
        <Row gutter={[12, 12]}>
          {roles.map((role) => {
            const result = agentByRole.get(role);
            return (
              <Col xs={24} lg={8} key={role}>
                <Card
                  className="agent-card"
                  title={AGENT_LABELS[role]}
                  size="small"
                  extra={
                    result ? (
                      <Tag color={result.status === 'completed' ? 'green' : 'red'}>
                        {AGENT_STATUS_LABELS[result.status] || result.status}
                      </Tag>
                    ) : (
                      <Tag>{AGENT_STATUS_LABELS.pending}</Tag>
                    )
                  }
                >
                  <pre>{result?.error || result?.content || '暂无结果'}</pre>
                </Card>
              </Col>
            );
          })}
        </Row>
      </div>

      <div className="page-surface file-panel">
        <Tabs items={fileTabs} defaultActiveKey={fileTabs[0]?.key} />
      </div>

      {detail.journal && (
        <Card title="日志" size="small" style={{ marginTop: 16 }}>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: '#666' }}>
            {detail.journal}
          </pre>
        </Card>
      )}
    </div>
  );
}

export default TaskDetail;
