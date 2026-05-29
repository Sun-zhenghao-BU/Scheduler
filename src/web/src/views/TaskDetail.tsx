import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Input,
  Popconfirm,
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
  UndoOutlined,
} from '@ant-design/icons';
import {
  addRequirementMessage,
  advanceTask,
  autoRefineRequirements,
  confirmRequirementsAndStart,
  getRequirements,
  getTask,
  orchestrateTask,
  reopenRequirements,
  updateTaskFile,
} from '../api';
import type { RequirementSession, Stage, TaskDetail as TaskDetailModel } from '../types';
import { STAGE_COLORS, STAGE_LABELS, STAGES } from '../types';
import { getErrorMessage } from '../utils/error';

const { TextArea } = Input;

const FILE_LABELS: Record<string, string> = {
  'request.md': '需求原文',
  'spec.md': '产品规划',
  'implementation.md': '实施方案',
  'review.md': '测试评审',
  'fixes.md': '修复记录',
  'release.md': '发布记录',
  'workflow_state.json': '工作流状态',
};

function TaskDetail() {
  const { projectId, taskId } = useParams<{ projectId: string; taskId: string }>();
  const navigate = useNavigate();

  const [detail, setDetail] = useState<TaskDetailModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [requirements, setRequirements] = useState<RequirementSession | null>(null);
  const [requirementsLoading, setRequirementsLoading] = useState(false);
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const [requirementMessage, setRequirementMessage] = useState('');
  const [requirementSummary, setRequirementSummary] = useState('');
  const [editingFile, setEditingFile] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');

  const fetchTask = useCallback(async () => {
    if (!taskId) return null;
    const data = await getTask(taskId);
    setDetail(data);
    return data;
  }, [taskId]);

  const fetchRequirements = useCallback(async () => {
    if (!taskId) return null;
    const data = await getRequirements(taskId);
    setRequirements(data);
    setRequirementSummary(data.summary || data.suggested_summary || '');
    return data;
  }, [taskId]);

  useEffect(() => {
    if (!taskId) return;
    let cancelled = false;
    setLoading(true);
    Promise.allSettled([fetchTask(), fetchRequirements()]).then((results) => {
      if (cancelled) return;
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
  }, [fetchRequirements, fetchTask, taskId]);

  useEffect(() => {
    if (!detail) return;
    const status = detail.workflow_state.status;
    if (status !== 'queued' && status !== 'running') return;
    const timer = window.setInterval(() => {
      fetchTask().catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [detail, fetchTask]);

  const currentStage = detail?.current_stage as Stage | undefined;
  const currentIdx = currentStage ? STAGES.indexOf(currentStage) : -1;
  const nextStage = currentIdx >= 0 && currentIdx < STAGES.length - 1 ? STAGES[currentIdx + 1] : null;
  const requirementsConfirmed = detail?.requirement_status === 'confirmed';

  const fileTabs = useMemo(
    () =>
      Object.entries(detail?.files ?? {}).map(([name, content]) => ({
        key: name,
        label: FILE_LABELS[name] || name,
        children:
          editingFile === name ? (
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

  async function handleSaveFile() {
    if (!taskId || !editingFile) return;
    try {
      await updateTaskFile(taskId, editingFile, editContent);
      message.success('文件已保存');
      setEditingFile(null);
      await fetchTask();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '文件保存失败'));
    }
  }

  async function handleAdvance() {
    if (!taskId || !nextStage) return;
    if (nextStage === 'implement' && !requirementsConfirmed) {
      message.warning('请先确认需求，再进入实施阶段');
      return;
    }
    try {
      await advanceTask(taskId, nextStage);
      message.success(`已推进到 ${STAGE_LABELS[nextStage as Stage]}`);
      await fetchTask();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '阶段推进失败'));
    }
  }

  async function handleAddRequirementMessage() {
    if (!taskId || !requirementMessage.trim()) return;
    setRequirementsLoading(true);
    try {
      const updated = await addRequirementMessage(taskId, 'user', requirementMessage.trim());
      setRequirements(updated);
      setRequirementMessage('');
      if (updated.summary) {
        setRequirementSummary(updated.summary);
      }
      message.success('需求补充已记录');
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '需求补充保存失败'));
    } finally {
      setRequirementsLoading(false);
    }
  }

  async function handleAutoRefineRequirements() {
    if (!taskId) return;
    setRequirementsLoading(true);
    try {
      const updated = await autoRefineRequirements(taskId);
      setRequirements(updated);
      if (!updated.summary && updated.suggested_summary) {
        setRequirementSummary(updated.suggested_summary);
      }
      message.success(
        updated.next_action === 'confirm'
          ? '需求已自动收敛到可确认状态'
          : '已完成一轮自动收敛，请继续补充需求',
      );
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '自动收敛需求失败'));
    } finally {
      setRequirementsLoading(false);
    }
  }

  async function handleConfirmRequirements() {
    if (!taskId || !requirementSummary.trim()) {
      message.warning('请填写最终确认的需求摘要');
      return;
    }
    setRequirementsLoading(true);
    setWorkflowLoading(true);
    try {
      const result = await confirmRequirementsAndStart(taskId, { summary: requirementSummary.trim() });
      message.success(result.message);
      await Promise.all([fetchTask(), fetchRequirements()]);
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '确认需求并启动流程失败'));
    } finally {
      setRequirementsLoading(false);
      setWorkflowLoading(false);
    }
  }

  async function handleReopenRequirements() {
    if (!taskId) return;
    setRequirementsLoading(true);
    try {
      await reopenRequirements(taskId);
      message.success('任务已退回需求确认阶段');
      await Promise.all([fetchTask(), fetchRequirements()]);
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '退回需求确认失败'));
    } finally {
      setRequirementsLoading(false);
    }
  }

  async function handleStartWorkflow() {
    if (!taskId) return;
    setWorkflowLoading(true);
    try {
      const result = await orchestrateTask(taskId);
      message.success(result.message);
      await fetchTask();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '自动流程启动失败'));
    } finally {
      setWorkflowLoading(false);
    }
  }

  function adoptSuggestedSummary() {
    if (!requirements?.suggested_summary) return;
    setRequirementSummary(requirements.suggested_summary);
    message.success('已填入建议摘要');
  }

  if (!detail) {
    return loading ? <p>加载中...</p> : <p>任务不存在</p>;
  }

  const workflowState = detail.workflow_state;
  const shouldReopenRequirements =
    workflowState.requires_human_review && workflowState.recommended_action === 'spec';

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
              <Popconfirm title={`确认推进到 ${STAGE_LABELS[nextStage as Stage]}？`} onConfirm={handleAdvance}>
                <Button
                  type="default"
                  icon={<StepForwardOutlined />}
                  disabled={nextStage === 'implement' && !requirementsConfirmed}
                >
                  推进到 {STAGE_LABELS[nextStage as Stage]}
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
            <Tag color={STAGE_COLORS[detail.current_stage as Stage]}>{STAGE_LABELS[detail.current_stage as Stage]}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="需求状态">
            <Tag color={requirementsConfirmed ? 'green' : 'orange'}>{requirementsConfirmed ? '已确认' : '待确认'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="工作流状态">
            <Tag color={workflowState.release_ready ? 'green' : workflowState.requires_human_review ? 'red' : 'blue'}>
              {workflowState.status || 'idle'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="当前步骤">{workflowState.active_step || '无'}</Descriptions.Item>
          <Descriptions.Item label="建议动作">{workflowState.recommended_action || '无'}</Descriptions.Item>
          <Descriptions.Item label="当前轮次">{workflowState.current_round}</Descriptions.Item>
          <Descriptions.Item label="最大轮次">{workflowState.max_rounds}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{new Date(detail.created_at).toLocaleString('zh-CN')}</Descriptions.Item>
          <Descriptions.Item label="更新时间">{new Date(detail.updated_at).toLocaleString('zh-CN')}</Descriptions.Item>
        </Descriptions>
      </div>

      <div className="page-surface requirements-panel">
        <div className="section-heading">
          <div>
            <h3>需求确认</h3>
            <p>先收敛需求，再锁定摘要。摘要确认后，系统会在后台启动开发测试流程。</p>
          </div>
          <Tag color={requirementsConfirmed ? 'green' : 'orange'}>{requirementsConfirmed ? '已锁定' : '开放中'}</Tag>
        </div>
        {!requirementsConfirmed && (
          <Alert
            type="warning"
            showIcon
            message="当前任务还不能进入自动流程，请先完成需求确认。"
            style={{ marginBottom: 12 }}
          />
        )}
        {!requirementsConfirmed && requirements?.next_action === 'confirm' && requirements.suggested_summary && (
          <Alert
            type="success"
            showIcon
            style={{ marginBottom: 12 }}
            message="当前信息已足够，可以确认需求摘要。"
            description={requirements.suggested_summary}
            action={
              <Button size="small" icon={<CheckCircleOutlined />} onClick={adoptSuggestedSummary}>
                采用建议摘要
              </Button>
            }
          />
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
          <>
            <div className="requirement-inputs">
              <Space wrap>
                <Button loading={requirementsLoading} onClick={handleAutoRefineRequirements}>
                  自动收敛需求
                </Button>
                <Tag color={requirements?.next_action === 'confirm' ? 'green' : 'blue'}>
                  {requirements?.next_action === 'confirm' ? '可确认摘要' : '继续补充'}
                </Tag>
              </Space>
            </div>
            <div className="requirement-inputs">
              <TextArea
                value={requirementMessage}
                onChange={(event) => setRequirementMessage(event.target.value)}
                rows={3}
                placeholder="补充边界条件、业务规则、验收标准、异常情况或依赖约束。"
              />
              <Space style={{ marginTop: 8 }}>
                <Button icon={<SendOutlined />} loading={requirementsLoading} onClick={handleAddRequirementMessage}>
                  记录补充
                </Button>
              </Space>
            </div>
          </>
        )}
        <div className="requirement-inputs">
          <TextArea
            value={requirementSummary}
            onChange={(event) => setRequirementSummary(event.target.value)}
            rows={5}
            disabled={requirementsConfirmed}
            placeholder="在这里填写最终确认的需求摘要。"
          />
          {!requirementsConfirmed && (
            <Space style={{ marginTop: 8 }}>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                loading={requirementsLoading || workflowLoading}
                onClick={handleConfirmRequirements}
              >
                确认需求并启动流程
              </Button>
            </Space>
          )}
        </div>
      </div>

      <div className="page-surface workflow-panel">
        <div className="section-heading">
          <div>
            <h3>自动流程</h3>
            <p>流程在后台执行。页面会自动轮询状态，日志和任务文件会按阶段更新。</p>
          </div>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={workflowLoading}
            disabled={!requirementsConfirmed || workflowState.status === 'queued' || workflowState.status === 'running'}
            onClick={handleStartWorkflow}
          >
            开始自动流程
          </Button>
        </div>
        {(workflowState.status === 'queued' || workflowState.status === 'running') && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="自动流程正在后台执行。"
            description={workflowState.step_message || '页面会每 2 秒刷新一次状态。'}
          />
        )}
        {workflowState.step_message && workflowState.status !== 'queued' && workflowState.status !== 'running' && (
          <Alert type="success" showIcon style={{ marginBottom: 12 }} message={workflowState.step_message} />
        )}
        {workflowState.requires_human_review && (
          <Alert
            type="error"
            showIcon
            style={{ marginBottom: 12 }}
            message="当前流程已触发人工介入条件。"
            description={workflowState.last_error || workflowState.tester_summary || '请检查修复记录和测试评审。'}
            action={
              shouldReopenRequirements ? (
                <Button size="small" icon={<UndoOutlined />} loading={requirementsLoading} onClick={handleReopenRequirements}>
                  退回需求确认
                </Button>
              ) : undefined
            }
          />
        )}

        <Card size="small" title="发布门禁" style={{ marginBottom: 12 }}>
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <div>
              <strong>门禁状态：</strong>
              <Tag color={workflowState.release_gate_status === 'passed' ? 'green' : 'red'}>
                {workflowState.release_gate_status || 'unknown'}
              </Tag>
            </div>
            <div>
              <strong>门禁结论：</strong>
              <span>{workflowState.release_gate_reason || '暂无'}</span>
            </div>
            {(workflowState.release_gate_checks || []).map((check) => (
              <div key={check.name}>
                <Tag color={check.passed ? 'green' : 'red'}>{check.passed ? '通过' : '拦截'}</Tag>
                <strong>{check.name}</strong>
                <span style={{ marginLeft: 8 }}>{check.detail}</span>
              </div>
            ))}
          </Space>
        </Card>

        {(workflowState.issues || []).length > 0 && (
          <Card size="small" title="阻塞问题" style={{ marginBottom: 12 }}>
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              {workflowState.issues.map((issue, index) => (
                <div key={`${issue.title}-${index}`}>
                  <Space wrap>
                    <Tag color={issue.blocking ? 'red' : 'orange'}>{issue.blocking ? '阻塞' : '非阻塞'}</Tag>
                    <Tag>{issue.severity}</Tag>
                    {issue.category ? <Tag>{issue.category}</Tag> : null}
                    <strong>{issue.title}</strong>
                  </Space>
                  {issue.evidence ? <div style={{ marginTop: 4, color: '#666' }}>{issue.evidence}</div> : null}
                </div>
              ))}
            </Space>
          </Card>
        )}
      </div>

      <div className="page-surface">
        <Tabs
          items={[
            {
              key: 'files',
              label: '任务文件',
              children: fileTabs.length ? <Tabs items={fileTabs} /> : <p>暂无任务文件。</p>,
            },
            {
              key: 'journal',
              label: '执行日志',
              children: (
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
                  {detail.journal || '暂无日志。'}
                </pre>
              ),
            },
          ]}
        />
      </div>
    </div>
  );
}

export default TaskDetail;
