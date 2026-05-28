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
  executeTask,
  getAgentResults,
  getRequirements,
  getTask,
  runAgentWorkflow,
  updateTaskFile,
} from '../api';
import type {
  AgentResult,
  AgentRole,
  RequirementSession,
  Stage,
  TaskDetail as TaskDetailModel,
  TaskExecutionResult,
} from '../types';
import { AGENT_LABELS, STAGES, STAGE_COLORS, STAGE_LABELS } from '../types';

const { TextArea } = Input;

const AGENT_STATUS_LABELS: Record<string, string> = {
  completed: 'Completed',
  failed: 'Failed',
  pending: 'Not run',
};

const FILE_LABELS: Record<string, string> = {
  'request.md': 'Request',
  'spec.md': 'Spec',
  'implementation.md': 'Implementation',
  'review.md': 'Review',
  'fixes.md': 'Fixes',
  'release.md': 'Release',
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
  const [executionLoading, setExecutionLoading] = useState(false);
  const [executionResult, setExecutionResult] = useState<TaskExecutionResult | null>(null);

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
      const taskResult = results[0];
      if (taskResult.status === 'rejected') {
        message.error('Failed to load task.');
      }
      const requirementResult = results[1];
      if (requirementResult.status === 'rejected') {
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
                Save
              </Button>
              <Button onClick={() => setEditingFile(null)}>Cancel</Button>
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
              Edit
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
      message.warning('Confirm requirements before entering implementation.');
      return;
    }
    try {
      await advanceTask(taskId, nextStage);
      message.success(`Moved to ${STAGE_LABELS[nextStage as Stage]}.`);
      await fetchTask();
    } catch {
      message.error('Failed to advance task stage.');
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
      message.success('Requirement note recorded.');
    } catch {
      message.error('Failed to save requirement note.');
    } finally {
      setRequirementsLoading(false);
    }
  }

  async function handleConfirmRequirements() {
    if (!taskId || !requirementSummary.trim()) {
      message.warning('Requirement summary is required.');
      return;
    }
    setRequirementsLoading(true);
    try {
      await confirmRequirements(taskId, requirementSummary.trim());
      message.success('Requirements confirmed.');
      await Promise.all([fetchTask(), fetchRequirements()]);
    } catch {
      message.error('Failed to confirm requirements.');
    } finally {
      setRequirementsLoading(false);
    }
  }

  async function handleSaveFile() {
    if (!taskId || !editingFile) {
      return;
    }
    try {
      await updateTaskFile(taskId, editingFile, editContent);
      message.success('File saved.');
      setEditingFile(null);
      await fetchTask();
    } catch {
      message.error('Failed to save file.');
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
      message.success('Analysis agents finished.');
      await fetchTask();
    } catch (error: unknown) {
      const err = error as Error;
      message.error(`Agent workflow failed: ${err.message}`);
    } finally {
      setAgentsLoading(false);
    }
  }

  async function handleExecuteTask() {
    if (!taskId) {
      return;
    }
    setExecutionLoading(true);
    try {
      const result = await executeTask(taskId);
      setExecutionResult(result);
      message.success('Implementation workflow finished.');
      await Promise.all([fetchTask(), fetchAgents()]);
    } catch (error: unknown) {
      const err = error as Error;
      message.error(`Execution failed: ${err.message}`);
    } finally {
      setExecutionLoading(false);
    }
  }

  if (!detail) {
    return loading ? <p>Loading...</p> : <p>Task not found.</p>;
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
        Back to tasks
      </Button>

      <div className="page-surface task-summary">
        <Descriptions
          title={detail.title}
          bordered
          column={2}
          size="small"
          extra={
            nextStage ? (
              <Popconfirm title={`Move to ${STAGE_LABELS[nextStage as Stage]}?`} onConfirm={handleAdvance}>
                <Button
                  type="default"
                  icon={<StepForwardOutlined />}
                  disabled={nextStage === 'implement' && !requirementsConfirmed}
                >
                  Move to {STAGE_LABELS[nextStage as Stage]}
                </Button>
              </Popconfirm>
            ) : (
              <Tag color="green">Completed</Tag>
            )
          }
        >
          <Descriptions.Item label="Task ID">
            <code style={{ fontSize: 12 }}>{detail.task_id}</code>
          </Descriptions.Item>
          <Descriptions.Item label="Project">
            {projectId || detail.project_id || '(unbound)'}
          </Descriptions.Item>
          <Descriptions.Item label="Stage">
            <Tag color={STAGE_COLORS[detail.current_stage as Stage]}>
              {STAGE_LABELS[detail.current_stage as Stage]}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Requirements">
            <Tag color={requirementsConfirmed ? 'green' : 'orange'}>
              {requirementsConfirmed ? 'Confirmed' : 'Drafting'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Created">
            {new Date(detail.created_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="Updated">
            {new Date(detail.updated_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
        </Descriptions>
      </div>

      <div className="page-surface requirements-panel">
        <div className="section-heading">
          <div>
            <h3>Requirements</h3>
            <p>Lock the approved requirement first. Implementation should start from this summary.</p>
          </div>
          <Tag color={requirementsConfirmed ? 'green' : 'orange'}>{requirementsConfirmed ? 'Locked' : 'Open'}</Tag>
        </div>
        {nextStage === 'implement' && !requirementsConfirmed && (
          <Alert
            type="warning"
            showIcon
            message="This task cannot enter implementation until the requirement is confirmed."
            style={{ marginBottom: 12 }}
          />
        )}
        <div className="requirement-thread">
          {requirements?.messages.length ? (
            requirements.messages.map((item, index) => (
              <div className={`requirement-message ${item.role}`} key={`${item.created_at}-${index}`}>
                <Tag color={item.role === 'product_manager' ? 'blue' : 'default'}>
                  {item.role === 'product_manager' ? 'PM' : 'User'}
                </Tag>
                <span>{item.content}</span>
              </div>
            ))
          ) : (
            <p className="empty-copy">No requirement discussion yet.</p>
          )}
        </div>
        {!requirementsConfirmed && (
          <div className="requirement-inputs">
            <TextArea
              value={requirementMessage}
              onChange={(event) => setRequirementMessage(event.target.value)}
              rows={3}
              placeholder="Add constraints, acceptance criteria, or extra context."
            />
            <Space style={{ marginTop: 8 }}>
              <Button icon={<SendOutlined />} loading={requirementsLoading} onClick={handleAddRequirementMessage}>
                Record note
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
            placeholder="Write the final confirmed requirement summary."
          />
          {!requirementsConfirmed && (
            <Space style={{ marginTop: 8 }}>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                loading={requirementsLoading}
                onClick={handleConfirmRequirements}
              >
                Confirm requirements
              </Button>
            </Space>
          )}
        </div>
      </div>

      <div className="page-surface agents-panel">
        <div className="section-heading">
          <div>
            <h3>Execution</h3>
            <p>
              This is the main workflow. It selects project files, generates code changes, applies them, and runs tests.
            </p>
          </div>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={executionLoading}
            disabled={!requirementsConfirmed}
            onClick={handleExecuteTask}
          >
            Start implementation
          </Button>
        </div>
        {!requirementsConfirmed && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="Confirm the requirement summary first. Then the implementation workflow can run end to end."
          />
        )}
        {executionResult && (
          <Card size="small" title="Latest execution result">
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <div>
                <strong>Summary</strong>
                <pre>{executionResult.summary}</pre>
              </div>
              <div>
                <strong>Selected files</strong>
                <pre>{executionResult.selected_paths.join('\n') || '(none)'}</pre>
              </div>
              <div>
                <strong>Written files</strong>
                <pre>{executionResult.written.join('\n') || '(none)'}</pre>
              </div>
              <div>
                <strong>Test command</strong>
                <pre>{executionResult.test_command || '(none)'}</pre>
              </div>
              <div>
                <strong>Test exit code</strong>
                <pre>{String(executionResult.test_exit_code)}</pre>
              </div>
              <div>
                <strong>Test output</strong>
                <pre>{executionResult.test_output || '(no output)'}</pre>
              </div>
            </Space>
          </Card>
        )}
      </div>

      <div className="page-surface agents-panel">
        <div className="section-heading">
          <div>
            <h3>Analysis agents</h3>
            <p>
              These agents only produce supporting documents. They do not apply code changes to the project workspace.
            </p>
          </div>
          <Button type="default" icon={<TeamOutlined />} loading={agentsLoading} onClick={handleRunAgents}>
            Run analysis
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
                  <pre>{result?.error || result?.content || 'No result yet.'}</pre>
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
        <Card title="Journal" size="small" style={{ marginTop: 16 }}>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: '#666' }}>{detail.journal}</pre>
        </Card>
      )}
    </div>
  );
}

export default TaskDetail;
