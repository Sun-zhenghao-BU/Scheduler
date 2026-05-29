export interface Task {
  task_id: string;
  title: string;
  current_stage: string;
  created_at: string;
  updated_at: string;
  project_id: string;
  requirement_status: 'drafting' | 'confirmed';
  requirement_confirmed_at: string;
}

export interface Project {
  project_id: string;
  name: string;
  root_path: string;
  created_at: string;
  updated_at: string;
}

export interface OpenRoot {
  root_id: string;
  label: string;
  path: string;
}

export interface OpenRootChild {
  name: string;
  path: string;
  relative_path: string;
  type: 'directory';
}

export interface WorkflowIssue {
  title: string;
  severity: string;
  blocking: boolean;
  source: string;
}

export interface WorkflowState {
  status: string;
  current_round: number;
  max_rounds: number;
  current_stage: string;
  release_ready: boolean;
  requires_human_review: boolean;
  last_error: string;
  last_test_exit_code: number;
  last_test_command: string;
  last_test_output: string;
  tester_summary: string;
  recommended_action: string;
  updated_at: string;
  issues: WorkflowIssue[];
}

export interface TaskDetail extends Task {
  files: Record<string, string>;
  journal: string;
  workflow_state: WorkflowState;
}

export interface LLMConfig {
  base_url: string;
  model: string;
  has_api_key: boolean;
}

export interface WorkspaceInfo {
  configured: boolean;
  root: string;
}

export interface WorkspaceItem {
  path: string;
  name: string;
  type: 'directory' | 'file';
}

export interface WorkspaceFile {
  path: string;
  content: string;
  size: number;
}

export interface FileChange {
  path: string;
  old_content: string;
  new_content: string;
  diff: string;
}

export interface DevelopmentProposal {
  session_id: string;
  summary: string;
  changes: FileChange[];
}

export interface TestCommandResult {
  command: string;
  exit_code: number;
  output: string;
}

export interface TaskExecutionResult {
  summary: string;
  selected_paths: string[];
  written: string[];
  test_command: string;
  test_exit_code: number;
  test_output: string;
  stage: string;
}

export interface TaskOrchestrationResult {
  product_status: string;
  product_content: string;
  product_error: string;
  developer_status: string;
  developer_content: string;
  developer_error: string;
  implementation_summary: string;
  written: string[];
  test_command: string;
  test_exit_code: number;
  test_output: string;
  tester_status: string;
  tester_content: string;
  tester_error: string;
  final_stage: string;
  release_ready: boolean;
  fix_rounds: number;
  spec_rounds: number;
  workflow_state: WorkflowState;
}

export type AgentRole = 'product_manager' | 'developer' | 'tester';
export type AgentStatus = 'completed' | 'failed';

export interface AgentResult {
  role: AgentRole;
  status: AgentStatus;
  content: string;
  error: string;
}

export interface RequirementMessage {
  role: 'user' | 'product_manager';
  content: string;
  created_at: string;
}

export interface RequirementSession {
  status: 'drafting' | 'confirmed';
  summary: string;
  next_action: 'ask' | 'confirm' | string;
  suggested_summary: string;
  messages: RequirementMessage[];
}

export const AGENT_LABELS: Record<AgentRole, string> = {
  product_manager: '产品经理',
  developer: '开发代理',
  tester: '测试代理',
};

export const STAGES = ['intake', 'spec', 'implement', 'review', 'fix', 'release'] as const;
export type Stage = (typeof STAGES)[number];

export const STAGE_LABELS: Record<Stage, string> = {
  intake: '需求录入',
  spec: '方案规划',
  implement: '实施开发',
  review: '测试评审',
  fix: '问题修复',
  release: '发布上线',
};

export const STAGE_COLORS: Record<Stage, string> = {
  intake: 'default',
  spec: 'processing',
  implement: 'blue',
  review: 'orange',
  fix: 'volcano',
  release: 'green',
};
