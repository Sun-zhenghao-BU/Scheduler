import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Input,
  Popconfirm,
  Row,
  Space,
  Tabs,
  Tag,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  SaveOutlined,
  SendOutlined,
  StepForwardOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import {
  addRequirementMessage,
  advanceTask,
  confirmRequirements,
  getAgentResults,
  getRequirements,
  getTask,
  orchestrateTask,
  runAgentWorkflow,
  updateTaskFile,
} from '../api';
import type {
  AgentResult,
  AgentRole,
  RequirementSession,
  Stage,
  TaskDetail as TaskDetailModel,
  TaskOrchestrationResult,
} from '../types';
import { AGENT_LABELS, STAGES, STAGE_COLORS, STAGE_LABELS } from '../types';
import { getErrorMessage } from '../utils/error';

const { TextArea } = Input;

const AGENT_STATUS_LABELS: Record<string, string> = {
  completed: '已完成',
  failed: '失败',
  pending: '未运行',
};

const FILE_LABELS: Record<string, string> = {
  'request.md': '需求',
  'spec.md': '产品规划',
  'implementation.md': '实施方案',
  'review.md': '测试评审',
  'fixes.md': '修复记录',
  'release.md': '发布记录',
};

function TaskDetail() {
  const { projectId, taskId } = useParams<{ projectId: string; taskId: string }>();
  const navigate = useNavigate();

  const [detail, setDetail] = useState<TaskDetailModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [agents, setAgents] = useState<AgentResult[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [requirements, setRequirements] = useState<RequirementSession | null>(null);
  const [requirementsLoading, setRequirementsLoading] = useState(false);
  const [requirementMessage, setRequirementMessage] = useState('');
  const [requirementSummary, setRequirementSummary] = useState('');
  const [editingFile, setEditingFile] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const [workflowResult, setWorkflowResult] = useState<TaskOrchestrationResult | null>(null);

  const fetchTask = useCallback(async () => {
    if (!taskId) {
      return;
    }
    const data = await getTask(taskId);
    setDetail(data);
    return data;
  }, [taskId]);

  const fetchRequirements = useCallback(async () => {
    if (!taskId) {
      return;
    }
    const data = await getRequirements(taskId);
    setRequirements(data);
    setRequirementSummary(data.summary);
    return data;
  }, [taskId]);

  const fetchAgents = useCallback(async () => {
    if (!taskId) {
      return;
    }
    try {
      const data = await getAgentResults(taskId);
      setAgents(data);
    } catch {
      setAgents([]);
    }
  }, [taskId]);

  useEffect(() => {
    if (!taskId) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.allSettled([fetchTask(), fetchRequirements(), fetchAgents()]).then((results) => {
      if (cancelled) {
        return;
      }
      if (results[0].status === 'rejected') {
        message.error('任务加载失败');
      }
      if (results[1].status === 'rejected') {
        setRequirements(null);
      }
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [taskId, fetchTask, fetchRequirements, fetchAgents]);

  const currentStage = detail?.current_stage as Stage | undefined;
  const currentIdx = currentStage ? STAGES.indexOf(currentStage) : -1;
  const nextStage = currentIdx >= 0 && currentIdx < STAGES.length - 1 ? STAGES[currentIdx + 1] : null;
  const requirementsConfirmed = detail?.requirement_status === 'confirmed';

  async function handleSaveFile() {
    if (!taskId || !editingFile) {
      return;
    }
    try {
      await updateTaskFile(taskId, editingFile, editContent);
      message.success('文件已保存');
      setEditingFile(null);
      await fetchTask();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '文件保存失败'));
    }
  }

  const fileTabs = useMemo(
    () =>
      Object.entries(detail?.files ?? {}).map(([name, content]) => ({
        key: name,
        label: FILE_LABELS[name] || name,
        children: editingFile === name ? (
          <div>
            <TextArea
              value={editContent}
              onChange={(event) => setEditContent(event.target.value)}
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
        ),
      })),
    [detail?.files, editContent, editingFile],
  );

  async function handleAdvance() {
    if (!detail || !taskId || !nextStage) {
      return;
    }
    if (nextStage === 'implement' && !requirementsConfirmed) {
      message.warning('请先确认需求，再进入实施阶段');
      return;
    }
    try {
      await advanceTask(taskId, nextStage);
      message.success(`已推进到${STAGE_LABELS[nextStage as Stage]}`);
      await fetchTask();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '阶段推进失败'));
    }
  }

  async function handleAddRequirementMessage() {
    if (!taskId || !requirementMessage.trim()) {
      return;
    }
    setRequirementsLoading(true);
    try {
      const updated = await addRequirementMessage(taskId, 'user', requirementMessage.trim());
      setRequirements(updated);
      setRequirementMessage('');
      message.success('需求补充已记录');
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '需求补充保存失败'));
    } finally {
      setRequirementsLoading(false);
    }
  }

  async function handleConfirmRequirements() {
    if (!taskId || !requirementSummary.trim()) {
      message.warning('请填写确认后的需求摘要');
      return;
    }
    setRequirementsLoading(true);
    try {
      await confirmRequirements(taskId, requirementSummary.trim());
      message.success('需求已确认');
      await Promise.all([fetchTask(), fetchRequirements()]);
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '需求确认失败'));
    } finally {
      setRequirementsLoading(false);
    }
  }

  async function handleRunAgents() {
    if (!taskId) {
      return;
    }
    setAgentsLoading(true);
    try {
      const results = await runAgentWorkflow(taskId);
      setAgents(results);
      message.success('辅助代理分析已完成');
      await fetchTask();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '辅助代理分析失败'));
    } finally {
      setAgentsLoading(false);
    }
  }

  async function handleStartWorkflow() {
    if (!taskId) {
      return;
    }
    setWorkflowLoading(true);
    try {
      const result = await orchestrateTask(taskId);
      setWorkflowResult(result);
      message.success(
        result.release_ready
          ? '流程执行完成，已达到发布条件'
          : `流程执行完成，已进入修复阶段，自动修复轮次：${result.fix_rounds}`,
      );
      await Promise.all([fetchTask(), fetchAgents()]);
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '自动流程执行失败'));
    } finally {
      setWorkflowLoading(false);
    }
  }

  if (!detail) {
    return loading ? <p>加载中...</p> : <p>任务不存在</p>;
  }

  const agentByRole = new Map(agents.map((agent) => [agent.role, agent]));
  const roles: AgentRole[] = ['product_manager', 'developer', 'tester'];

  return (
    <div className="task-detail">
      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate(projectId ? `/projects/${projectId}` : '/')}
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
            nextStage ? (
              <Popconfirm title={`确认推进到${STAGE_LABELS[nextStage as Stage]}？`} onConfirm={handleAdvance}>
                <Button
                  type="default"
                  icon={<StepForwardOutlined />}
                  disabled={nextStage === 'implement' && !requirementsConfirmed}
                >
                  推进到{STAGE_LABELS[nextStage as Stage]}
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
          <Descriptions.Item label="所属项目">{projectId || detail.project_id || '未绑定'}</Descriptions.Item>
          <Descriptions.Item label="当前阶段">
            <Tag color={STAGE_COLORS[detail.current_stage as Stage]}>
              {STAGE_LABELS[detail.current_stage as Stage]}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="需求状态">
            <Tag color={requirementsConfirmed ? 'green' : 'orange'}>
              {requirementsConfirmed ? '已确认' : '待确认'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">{new Date(detail.created_at).toLocaleString('zh-CN')}</Descriptions.Item>
          <Descriptions.Item label="更新时间">{new Date(detail.updated_at).toLocaleString('zh-CN')}</Descriptions.Item>
        </Descriptions>
      </div>

      <div className="page-surface requirements-panel">
        <div className="section-heading">
          <div>
            <h3>需求确认</h3>
            <p>先把需求摘要锁定，后续产品规划、实施方案、测试评审和修复回环都会以这份确认内容为准。</p>
          </div>
          <Tag color={requirementsConfirmed ? 'green' : 'orange'}>{requirementsConfirmed ? '已锁定' : '开放中'}</Tag>
        </div>
        {!requirementsConfirmed && (
          <Alert type="warning" showIcon message="当前任务还不能进入自动流程，请先确认需求。" style={{ marginBottom: 12 }} />
        )}
        <div className="requirement-thread">
          {requirements?.messages.length ? (
            requirements.messages.map((item, index) => (
              <div className={`requirement-message ${item.role}`} key={`${item.created_at}-${index}`}>
                <Tag color={item.role === 'product_manager' ? 'blue' : 'default'}>
                  {item.role === 'product_manager' ? '产品经理' : '用户'}
                </Tag>
                <span>{item.content}</span>
              </div>
            ))
          ) : (
            <p className="empty-copy">暂时没有需求对话记录。</p>
          )}
        </div>
        {!requirementsConfirmed && (
          <div className="requirement-inputs">
            <TextArea
              value={requirementMessage}
              onChange={(event) => setRequirementMessage(event.target.value)}
              rows={3}
              placeholder="补充边界条件、验收标准或额外上下文。"
            />
            <Space style={{ marginTop: 8 }}>
              <Button icon={<SendOutlined />} loading={requirementsLoading} onClick={handleAddRequirementMessage}>
                记录补充
              </Button>
            </Space>
          </div>
        )}
        <div className="requirement-inputs">
          <TextArea
            value={requirementSummary}
            onChange={(event) => setRequirementSummary(event.target.value)}
            rows={5}
            disabled={requirementsConfirmed}
            placeholder="填写最终确认的需求摘要。"
          />
          {!requirementsConfirmed && (
            <Space style={{ marginTop: 8 }}>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                loading={requirementsLoading}
                onClick={handleConfirmRequirements}
              >
                确认需求
              </Button>
            </Space>
          )}
        </div>
      </div>

      <div className="page-surface agents-panel">
        <div className="section-heading">
          <div>
            <h3>自动流程</h3>
            <p>点击后会按顺序执行：生成产品规划、生成实施方案、实际改代码、测试评审；如果失败，会自动进入修复并重新开发、回测。</p>
          </div>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={workflowLoading}
            disabled={!requirementsConfirmed}
            onClick={handleStartWorkflow}
          >
            开始自动流程
          </Button>
        </div>
        {!requirementsConfirmed && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="请先确认需求摘要，确认后才能执行完整的产品、开发、测试串行流程。"
          />
        )}
        {workflowResult && (
          <Card size="small" title="最近一次流程结果">
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <div>
                <strong>产品规划输出（spec.md）</strong>
                <pre>{workflowResult.product_error || workflowResult.product_content || '无'}</pre>
              </div>
              <div>
                <strong>实施方案输出（implementation.md）</strong>
                <pre>{workflowResult.developer_error || workflowResult.developer_content || '无'}</pre>
              </div>
              <div>
                <strong>实际实施结果摘要</strong>
                <pre>{workflowResult.implementation_summary}</pre>
              </div>
              <div>
                <strong>写回文件</strong>
                <pre>{workflowResult.written.join('\n') || '无'}</pre>
              </div>
              <div>
                <strong>测试命令</strong>
                <pre>{workflowResult.test_command || '无'}</pre>
              </div>
              <div>
                <strong>测试退出码</strong>
                <pre>{String(workflowResult.test_exit_code)}</pre>
              </div>
              <div>
                <strong>测试输出</strong>
                <pre>{workflowResult.test_output || '无输出'}</pre>
              </div>
              <div>
                <strong>测试评审输出（review.md）</strong>
                <pre>{workflowResult.tester_error || workflowResult.tester_content || '无'}</pre>
              </div>
              <div>
                <strong>自动修复轮次</strong>
                <pre>{String(workflowResult.fix_rounds)}</pre>
              </div>
              <div>
                <strong>最终阶段</strong>
                <pre>{STAGE_LABELS[workflowResult.final_stage as Stage] || workflowResult.final_stage}</pre>
              </div>
              <div>
                <strong>发布判定</strong>
                <pre>{workflowResult.release_ready ? '达到发布条件' : '未达到发布条件，仍需修复'}</pre>
              </div>
            </Space>
          </Card>
        )}
      </div>

      <div className="page-surface agents-panel">
        <div className="section-heading">
          <div>
            <h3>辅助代理分析</h3>
            <p>这部分保留给手动参考使用，不参与自动串行流程。</p>
          </div>
          <Button type="default" icon={<TeamOutlined />} loading={agentsLoading} onClick={handleRunAgents}>
            运行辅助代理
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
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: '#666' }}>{detail.journal}</pre>
        </Card>
      )}
    </div>
  );
}

export default TaskDetail;
