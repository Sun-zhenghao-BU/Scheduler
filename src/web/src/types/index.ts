export interface Task {
  task_id: string;
  title: string;
  current_stage: string;
  created_at: string;
  updated_at: string;
  requirement_status: 'drafting' | 'confirmed';
  requirement_confirmed_at: string;
}

export interface TaskDetail extends Task {
  files: Record<string, string>;
  journal: string;
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
  implement: '实施方案',
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
