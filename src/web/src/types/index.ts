export interface Task {
  task_id: string;
  title: string;
  current_stage: string;
  created_at: string;
  updated_at: string;
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

export type AgentRole = 'product_manager' | 'developer' | 'tester';
export type AgentStatus = 'completed' | 'failed';

export interface AgentResult {
  role: AgentRole;
  status: AgentStatus;
  content: string;
  error: string;
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
