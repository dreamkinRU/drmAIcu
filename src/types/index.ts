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
  | 'project'
  | 'plugins'
  | 'github';

export type PluginStatus = 'installed' | 'disabled' | 'loading' | 'running' | 'error' | 'update_available' | 'incompatible';

export interface PluginPermission {
  permission: string;
  level: 'read' | 'write' | 'critical';
  granted: boolean;
}

export interface PluginCapabilities {
  name: string;
  permission: string;
  policy: 'auto' | 'confirm' | 'critical';
  description: string;
}

export interface PluginInfo {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  api_version: string;
  status: PluginStatus;
  source: 'builtin' | 'installed';
  enabled: boolean;
  last_error: string;
  permissions?: string[];
  settings_schema?: Record<string, { type: string; title?: string; default?: unknown; enum?: unknown[] }>;
  capabilities?: PluginCapabilities[];
  installed_at?: string;
}

export interface PluginPermissionRow {
  plugin: string;
  permissions: PluginPermission[];
  granted: string[];
}

export interface PluginConfirmation {
  id: string;
  plugin: string;
  capability: string;
  params: unknown;
  permission: string;
  policy: 'confirm' | 'critical';
  created: number;
  expires_in: number;
}

export interface PluginActivityEntry {
  ts: string;
  level: 'info' | 'warn' | 'error' | 'action';
  plugin: string | null;
  event: string;
  details?: Record<string, unknown>;
}

export interface PluginCatalogEntry {
  available: boolean;
  errors: string[];
  manifest?: PluginInfo;
  installed?: boolean;
  compatible?: boolean;
  permissions?: PluginPermission[];
}

// === GitHub Plugin (Этап 4) ===

export interface GitHubRepository {
  full_name: string;
  private: boolean;
  default_branch: string;
  html_url: string | null;
  description: string | null;
  updated_at: string | null;
  permissions?: Record<string, boolean>;
}

export interface GitHubRepoList {
  page: number;
  total_count: number;
  repositories: GitHubRepository[];
}

export interface GitHubBranch {
  name: string;
  sha: string | null;
  protected: boolean;
}

export interface GitHubBranchList {
  page: number;
  branches: GitHubBranch[];
}

export interface GitHubTreeEntry {
  path: string;
  type: 'blob' | 'tree' | string;
  size?: number;
}

export interface GitHubTree {
  sha: string;
  truncated: boolean;
  tree: GitHubTreeEntry[];
}

export interface GitHubDirListing {
  type: 'dir';
  entries: { name: string; path: string; type: string; size?: number }[];
}

export interface GitHubFileContent {
  type: 'file';
  path: string;
  size: number;
  encoding: string;
  content: string;
  sha: string;
}

export interface GitHubConnection {
  ok: boolean;
  configured: boolean;
  app_id_set?: boolean;
  installation_id_set?: boolean;
  repositories_total?: number;
  error?: string;
}

export interface PluginSecretKeys {
  plugin: string;
  secrets: string[];
}

export type ExecOutcome<T> =
  | { status: 'done'; result: T }
  | { status: 'confirmation_required'; confirmation: PluginConfirmation }
  | { status: 'error'; error: string; code: string };
