export type AgentProviderId = 'ollama' | 'strata' | 'lmstudio' | 'bionic' | 'groq' | 'openrouter' | 'together' | 'huggingface' | 'gemini' | 'all';

export interface Agent {
  id: number;
  name: string;
  status: 'active' | 'frozen' | 'offline';
  task: string;
  stack: string[];
  progress: number;
  lastActivity: string;
  enabled: boolean;
  description: string;
  provider?: AgentProviderId;
  model?: string;
  systemPrompt?: string;
  isJudge?: boolean;
  tasksCompleted?: number;
  avgTps?: number;
  patchesCreated?: number;
  contextFiles?: string[];
}

export interface AgentPipelineStep {
  agentId: number;
  instruction?: string;
}

export interface AgentPipeline {
  id: string;
  name: string;
  description: string;
  steps: AgentPipelineStep[];
}

export interface Provider {
  name: string;
  status: 'online' | 'offline' | 'error';
  latency: number;
  models: number;
  description: string;
  url: string;
  enabled: boolean;
  apiKey?: string;
  getKeyUrl?: string;
}

export interface LogEntry {
  time: string;
  level: 'info' | 'warn' | 'error' | 'success';
  message: string;
  source: string;
  details?: string;
}

export interface CodeIssue {
  id: number;
  severity: 'critical' | 'warning' | 'info';
  line: string;
  title: string;
  description: string;
  fix: string;
  before: string;
  after: string;
  file: string;
  fixed: boolean;
  fixLog?: string[];
}

export interface Task {
  id: number;
  text: string;
  done: boolean;
  priority: 'high' | 'medium' | 'low';
  category: 'code' | 'general';
}

export interface MDFile {
  name: string;
  description: string;
}

export interface OllamaModel {
  name: string;
  size_gb: number;
}

export interface PatchInfo {
  filename: string;
  filepath: string;
  patch_id: string;
  target_file: string;
  description: string;
  author: string;
  created_at: string;
  is_applied: boolean;
  file_exists: boolean;
  checksum_ok: boolean | null;
  content_length: number;
  has_content: boolean;
  error?: string;
  full_file_content?: string;
  patch_type?: string;
  diff?: string;
}

export interface CleanupRecommendation {
  action: 'keep' | 'delete' | 'review';
  reason: string;
}

export interface ProjectFile {
  path: string;
  filename: string;
  size: number;
  size_human: string;
  modified: string;
  category: string;
  hash: string;
  preview: string;
  is_critical: boolean;
  is_important: boolean;
  extension: string;
  icon: string;
  is_duplicate: boolean;
  duplicates: string[];
  error?: string;
  cleanup?: CleanupRecommendation;
}

export interface ProjectStats {
  total: number;
  total_size: number;
  total_size_human: string;
  by_category: Record<string, number>;
  by_extension: Record<string, number>;
  duplicates_count: number;
  duplicates_groups: number;
  critical_count: number;
  important_count: number;
  trash_count: number;
  backup_count: number;
  cleanup_delete_count?: number;
  cleanup_review_count?: number;
}

export type TabId =
  | 'console'
  | 'panel'
  | 'agents'
  | 'providers'
  | 'models'
  | 'md'
  | 'code'
  | 'logs'
  | 'tasks'
  | 'patches'
  | 'project';
