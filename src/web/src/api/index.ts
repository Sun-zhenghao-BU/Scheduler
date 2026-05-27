import axios from 'axios';
import type { AgentResult, Task, TaskDetail, LLMConfig, WorkspaceFile, WorkspaceInfo, WorkspaceItem } from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Tasks
export async function listTasks(): Promise<Task[]> {
  const { data } = await api.get<Task[]>('/tasks/');
  return data;
}

export async function createTask(title: string, request = ''): Promise<Task> {
  const { data } = await api.post<Task>('/tasks/', { title, request });
  return data;
}

export async function getTask(taskId: string): Promise<TaskDetail> {
  const { data } = await api.get<TaskDetail>(`/tasks/${taskId}`);
  return data;
}

export async function advanceTask(taskId: string, stage: string): Promise<Task> {
  const { data } = await api.post<Task>(`/tasks/${taskId}/advance`, { stage });
  return data;
}

export async function logTask(taskId: string, stage: string, message: string): Promise<Task> {
  const { data } = await api.post<Task>(`/tasks/${taskId}/log`, { stage, message });
  return data;
}

export async function updateTaskFile(taskId: string, fileName: string, content: string): Promise<void> {
  await api.put(`/tasks/${taskId}/files/${fileName}`, { content });
}

export async function getAgentResults(taskId: string): Promise<AgentResult[]> {
  const { data } = await api.get<AgentResult[]>(`/tasks/${taskId}/agents`);
  return data;
}

export async function runAgentWorkflow(taskId: string): Promise<AgentResult[]> {
  const { data } = await api.post<AgentResult[]>(`/tasks/${taskId}/agents/run`);
  return data;
}

export async function getLLMConfig(): Promise<LLMConfig> {
  const { data } = await api.get<LLMConfig>('/llm/config');
  return data;
}

export async function updateLLMConfig(apiKey: string, baseUrl: string, model: string): Promise<void> {
  await api.post('/llm/config', { api_key: apiKey, base_url: baseUrl, model });
}

export async function validateLLMConfig(): Promise<{ valid: boolean; message: string }> {
  const { data } = await api.post('/llm/validate');
  return data;
}

export async function getWorkspaceInfo(): Promise<WorkspaceInfo> {
  const { data } = await api.get<WorkspaceInfo>('/workspace/');
  return data;
}

export async function getWorkspaceTree(): Promise<WorkspaceItem[]> {
  const { data } = await api.get<WorkspaceItem[]>('/workspace/tree');
  return data;
}

export async function getWorkspaceFile(path: string): Promise<WorkspaceFile> {
  const { data } = await api.get<WorkspaceFile>('/workspace/file', { params: { path } });
  return data;
}
