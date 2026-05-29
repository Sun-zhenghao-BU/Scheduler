import axios from 'axios';
import type {
  AgentResult,
  DevelopmentProposal,
  LLMConfig,
  OpenRoot,
  OpenRootChild,
  Project,
  RequirementSession,
  Task,
  TaskDetail,
  TaskExecutionResult,
  TaskOrchestrationResult,
  TestCommandResult,
  WorkspaceFile,
  WorkspaceInfo,
  WorkspaceItem,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Tasks
export async function listProjects(): Promise<Project[]> {
  const { data } = await api.get<Project[]>('/projects/');
  return data;
}

export async function createProject(name: string, rootPath = ''): Promise<Project> {
  const { data } = await api.post<Project>('/projects/', { name, root_path: rootPath });
  return data;
}

export async function updateProject(projectId: string, rootPath: string): Promise<Project> {
  const { data } = await api.put<Project>(`/projects/${projectId}`, { root_path: rootPath });
  return data;
}

export async function pickProjectFolder(): Promise<{ selected: boolean; path: string }> {
  const { data } = await api.post<{ selected: boolean; path: string }>('/projects/pick-folder');
  return data;
}

export async function listOpenRoots(): Promise<OpenRoot[]> {
  const { data } = await api.get<OpenRoot[]>('/projects/open-roots');
  return data;
}

export async function listOpenRootChildren(rootId: string, relativePath = ''): Promise<OpenRootChild[]> {
  const { data } = await api.get<OpenRootChild[]>(`/projects/open-roots/${rootId}/children`, {
    params: relativePath ? { relative_path: relativePath } : undefined,
  });
  return data;
}

export async function getProject(projectId: string): Promise<Project> {
  const { data } = await api.get<Project>(`/projects/${projectId}`);
  return data;
}

export async function listProjectTasks(projectId: string): Promise<Task[]> {
  const { data } = await api.get<Task[]>(`/projects/${projectId}/tasks`);
  return data;
}

export async function listTasks(): Promise<Task[]> {
  const { data } = await api.get<Task[]>('/tasks/');
  return data;
}

export async function createTask(title: string, request = '', projectId = ''): Promise<Task> {
  const { data } = await api.post<Task>('/tasks/', { title, request, project_id: projectId });
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

export async function getRequirements(taskId: string): Promise<RequirementSession> {
  const { data } = await api.get<RequirementSession>(`/tasks/${taskId}/requirements`);
  return data;
}

export async function addRequirementMessage(
  taskId: string,
  role: 'user' | 'product_manager',
  content: string,
): Promise<RequirementSession> {
  const { data } = await api.post<RequirementSession>(`/tasks/${taskId}/requirements/messages`, { role, content });
  return data;
}

export async function confirmRequirements(taskId: string, summary: string): Promise<Task> {
  const { data } = await api.post<Task>(`/tasks/${taskId}/requirements/confirm`, { summary });
  return data;
}

export async function reopenRequirements(taskId: string): Promise<Task> {
  const { data } = await api.post<Task>(`/tasks/${taskId}/requirements/reopen`);
  return data;
}

export async function executeTask(
  taskId: string,
  payload: { instruction?: string; paths?: string[]; test_command?: string; apply_changes?: boolean } = {},
): Promise<TaskExecutionResult> {
  const { data } = await api.post<TaskExecutionResult>(`/tasks/${taskId}/execute`, payload);
  return data;
}

export async function orchestrateTask(
  taskId: string,
  payload: { instruction?: string; paths?: string[]; test_command?: string; apply_changes?: boolean } = {},
): Promise<TaskOrchestrationResult> {
  const { data } = await api.post<TaskOrchestrationResult>(`/tasks/${taskId}/orchestrate`, payload);
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

export async function getWorkspaceInfo(projectId = ''): Promise<WorkspaceInfo> {
  const { data } = await api.get<WorkspaceInfo>('/workspace/', {
    params: projectId ? { project_id: projectId } : undefined,
  });
  return data;
}

export async function getWorkspaceTree(projectId = ''): Promise<WorkspaceItem[]> {
  const { data } = await api.get<WorkspaceItem[]>('/workspace/tree', {
    params: projectId ? { project_id: projectId } : undefined,
  });
  return data;
}

export async function getWorkspaceFile(path: string, projectId = ''): Promise<WorkspaceFile> {
  const params = projectId ? { path, project_id: projectId } : { path };
  const { data } = await api.get<WorkspaceFile>('/workspace/file', { params });
  return data;
}

export async function proposeDevelopment(
  instruction: string,
  paths: string[],
  projectId = '',
): Promise<DevelopmentProposal> {
  const { data } = await api.post<DevelopmentProposal>('/development/propose', {
    instruction,
    paths,
    project_id: projectId,
  });
  return data;
}

export async function applyDevelopment(sessionId: string): Promise<{ written: string[] }> {
  const { data } = await api.post<{ written: string[] }>('/development/apply', { session_id: sessionId });
  return data;
}

export async function runDevelopmentTest(command: string, projectId = ''): Promise<TestCommandResult> {
  const { data } = await api.post<TestCommandResult>('/development/test', {
    command,
    project_id: projectId,
  });
  return data;
}
