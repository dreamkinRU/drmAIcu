import { Agent, AgentPipeline, LogEntry, OllamaModel, PatchInfo, ProjectFile, ProjectStats } from '../types';

// ============================================================================
// Агенты
// ============================================================================

export async function loadAgentsApi(): Promise<Agent[] | null> {
  try {
    const res = await fetch('/api/agents');
    if (!res.ok) return null;
    const data = await res.json();
    return data.success && Array.isArray(data.agents) ? data.agents : null;
  } catch {
    return null;
  }
}

export async function loadAppVersionApi(): Promise<string | null> {
  try {
    const res = await fetch('/api/version');
    if (!res.ok) return null;
    const data = await res.json();
    return typeof data.version === 'string' && data.version ? data.version : null;
  } catch {
    return null;
  }
}

export async function saveAgentsApi(agents: Agent[]): Promise<boolean> {
  try {
    const res = await fetch('/api/agents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agents }),
    });
    const data = await res.json();
    return Boolean(data.success);
  } catch {
    return false;
  }
}

export interface CouncilAgentResult {
  name: string;
  provider: string;
  model: string;
  elapsed_sec: number;
  content: string | null;
  error: string | null;
}

export async function runCouncilTaskStream(
  prompt: string,
  agents: Agent[],
  judge: Agent | null,
  handlers: {
    onStatus?: (msg: string) => void;
    onAgentDone?: (res: CouncilAgentResult) => void;
    onSingleWinner?: (name: string, content: string) => void;
    onJudgeChunk?: (judgeName: string, chunk: string) => void;
    onMeta?: (meta: StreamMetrics) => void;
    signal?: AbortSignal;
  }
): Promise<{ success: boolean; error?: string; aborted?: boolean }> {
  try {
    const res = await fetch('/api/task/council', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, agents, judge }),
      signal: handlers.signal,
    });
    if (!res.ok || !res.body) {
      return { success: false, error: `HTTP ${res.status}` };
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const rawEvent of events) {
        const line = rawEvent.trim();
        if (!line.startsWith('data:')) continue;
        const jsonStr = line.slice(5).trim();
        if (!jsonStr) continue;
        try {
          const ev = JSON.parse(jsonStr);
          if (ev.type === 'status' && handlers.onStatus) {
            handlers.onStatus(ev.content || '');
          } else if (ev.type === 'agent_done' && handlers.onAgentDone) {
            handlers.onAgentDone(ev as CouncilAgentResult);
          } else if (ev.type === 'single_winner' && handlers.onSingleWinner) {
            handlers.onSingleWinner(ev.name || 'Agent', ev.content || '');
          } else if (ev.type === 'judge_chunk' && handlers.onJudgeChunk) {
            handlers.onJudgeChunk(ev.judge_name || 'Judge', ev.content || '');
          } else if (ev.type === 'meta' && handlers.onMeta) {
            handlers.onMeta(ev as StreamMetrics);
          } else if (ev.type === 'error') {
            return { success: false, error: ev.error || 'Ошибка консилиума' };
          }
        } catch {}
      }
    }
    return { success: true };
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      return { success: false, aborted: true };
    }
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function loadPipelinesApi(): Promise<AgentPipeline[] | null> {
  try {
    const res = await fetch('/api/pipelines');
    if (!res.ok) return null;
    const data = await res.json();
    return data.success && Array.isArray(data.pipelines) ? data.pipelines : null;
  } catch {
    return null;
  }
}

export async function savePipelinesApi(pipelines: AgentPipeline[]): Promise<boolean> {
  try {
    const res = await fetch('/api/pipelines', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pipelines }),
    });
    const data = await res.json();
    return Boolean(data.success);
  } catch {
    return false;
  }
}

export interface PipelineStepPayload {
  name: string;
  provider: string;
  model: string;
  systemPrompt: string;
  instruction?: string;
}

export async function runPipelineTaskStream(
  prompt: string,
  steps: PipelineStepPayload[],
  handlers: {
    onStepStart?: (info: { step: number; total: number; name: string; provider: string; model: string }) => void;
    onStepChunk?: (step: number, chunk: string) => void;
    onStepDone?: (info: { step: number; total: number; name: string; elapsed_sec: number }) => void;
    onMeta?: (meta: StreamMetrics) => void;
    signal?: AbortSignal;
  }
): Promise<{ success: boolean; error?: string; aborted?: boolean }> {
  try {
    const res = await fetch('/api/task/pipeline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, steps }),
      signal: handlers.signal,
    });
    if (!res.ok || !res.body) {
      return { success: false, error: `HTTP ${res.status}` };
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const rawEvent of events) {
        const line = rawEvent.trim();
        if (!line.startsWith('data:')) continue;
        const jsonStr = line.slice(5).trim();
        if (!jsonStr) continue;
        try {
          const ev = JSON.parse(jsonStr);
          if (ev.type === 'step_start' && handlers.onStepStart) {
            handlers.onStepStart(ev);
          } else if (ev.type === 'step_chunk' && handlers.onStepChunk) {
            handlers.onStepChunk(ev.step || 1, ev.content || '');
          } else if (ev.type === 'step_done' && handlers.onStepDone) {
            handlers.onStepDone(ev);
          } else if (ev.type === 'meta' && handlers.onMeta) {
            handlers.onMeta(ev as StreamMetrics);
          } else if (ev.type === 'error') {
            return { success: false, error: ev.error || 'Ошибка цепочки' };
          }
        } catch {}
      }
    }
    return { success: true };
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      return { success: false, aborted: true };
    }
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function buildAgentContextApi(payload: {
  files: string[];
  include_logs?: boolean;
  code_issues?: any[];
}): Promise<{ success: boolean; context_text: string; attached_files: string[]; error?: string }> {
  try {
    const res = await fetch('/api/context/build', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) return { success: false, context_text: '', attached_files: [], error: `HTTP ${res.status}` };
    return await res.json();
  } catch {
    return { success: false, context_text: '', attached_files: [], error: 'Ошибка сети' };
  }
}

export async function savePatchFromConsoleApi(rawText: string): Promise<{
  success: boolean;
  filename?: string;
  patch_id?: string;
  preview?: any;
  error?: string;
}> {
  try {
    const res = await fetch('/api/patches/save-from-console', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw_text: rawText }),
    });
    if (!res.ok) return { success: false, error: `HTTP ${res.status}` };
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

// ============================================================================
// Ollama
// ============================================================================

export interface OllamaStatus {
  online: boolean;
  models: string[];
  processes: Array<{ name: string; size: number; vram: number }>;
}

export async function checkOllama(ollamaUrl: string): Promise<OllamaStatus> {
  const offline: OllamaStatus = { online: false, models: [], processes: [] };
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    const res = await fetch(`${ollamaUrl}/api/tags`, { signal: controller.signal });
    clearTimeout(timeout);
    if (!res.ok) return offline;

    const data = await res.json();
    const models: string[] = data.models?.map((m: any) => m.name) || [];

    let processes: Array<{ name: string; size: number; vram: number }> = [];
    try {
      const psRes = await fetch(`${ollamaUrl}/api/ps`);
      if (psRes.ok) {
        const psData = await psRes.json();
        processes = (psData.models || []).map((m: any) => ({
          name: m.name || m.model || 'unknown',
          size: Math.round((m.size || 0) / 1024 / 1024),
          vram: Math.round((m.size_vram || 0) / 1024 / 1024),
        }));
      }
    } catch {
      // /api/ps может быть недоступен на старых версиях Ollama
    }

    return { online: true, models, processes };
  } catch {
    return offline;
  }
}

export async function loadBionicModels(bionicUrl?: string): Promise<OllamaModel[]> {
  try {
    const q = bionicUrl ? `?url=${encodeURIComponent(bionicUrl)}` : '';
    const res = await fetch(`/api/bionic/models${q}`);
    const data = await res.json();
    return data.success ? data.models : [];
  } catch {
    return [];
  }
}

export async function loadLmStudioModels(lmstudioUrl?: string): Promise<OllamaModel[]> {
  try {
    const q = lmstudioUrl ? `?url=${encodeURIComponent(lmstudioUrl)}` : '';
    const res = await fetch(`/api/lmstudio/models${q}`);
    const data = await res.json();
    return data.success ? data.models : [];
  } catch {
    return [];
  }
}

export async function loadStrataModels(strataUrl?: string): Promise<OllamaModel[]> {
  try {
    const q = strataUrl ? `?url=${encodeURIComponent(strataUrl)}` : '';
    const res = await fetch(`/api/strata/models${q}`);
    const data = await res.json();
    return data.success ? data.models : [];
  } catch {
    return [];
  }
}

export async function loadInstalledModels(): Promise<OllamaModel[]> {
  try {
    const res = await fetch('/api/ollama/models');
    const data = await res.json();
    return data.success ? data.models : [];
  } catch {
    return [];
  }
}

export async function pullModel(name: string): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch('/api/ollama/pull', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

// ============================================================================
// Задачи ИИ и логи
// ============================================================================

export interface StreamMetrics {
  provider: string;
  model: string;
  elapsed_sec: number;
  ttft_sec: number;
  tokens: number;
  tps: number;
}

export async function runAiTask(prompt: string, mode: string, model?: string): Promise<{ success: boolean; result?: string; error?: string }> {
  try {
    const res = await fetch('/api/task', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, mode, model: model || '' }),
    });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function runAiTaskStream(
  prompt: string,
  provider: string,
  model: string,
  handlers: {
    onChunk: (chunk: string) => void;
    onMeta?: (meta: StreamMetrics) => void;
    signal?: AbortSignal;
    systemPrompt?: string;
  }
): Promise<{ success: boolean; error?: string; aborted?: boolean }> {
  try {
    const res = await fetch('/api/task/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        mode: 'fast',
        provider,
        model: model || '',
        system_prompt: handlers.systemPrompt || '',
      }),
      signal: handlers.signal,
    });
    if (!res.ok || !res.body) {
      return { success: false, error: `HTTP ${res.status}` };
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const rawEvent of events) {
        const line = rawEvent.trim();
        if (!line.startsWith('data:')) continue;
        const jsonStr = line.slice(5).trim();
        if (!jsonStr) continue;
        try {
          const ev = JSON.parse(jsonStr);
          if (ev.type === 'chunk' && ev.content) {
            handlers.onChunk(ev.content);
          } else if (ev.type === 'meta' && handlers.onMeta) {
            handlers.onMeta(ev as StreamMetrics);
          } else if (ev.type === 'error') {
            return { success: false, error: ev.error || 'Ошибка генерации' };
          }
        } catch {
          // игнорируем неполный JSON-фрагмент
        }
      }
    }
    return { success: true };
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      return { success: false, aborted: true };
    }
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function fetchBackendLogs(): Promise<LogEntry[]> {
  try {
    const res = await fetch('/api/logs');
    if (!res.ok) return [];
    const data = await res.json();
    if (!data.logs) return [];
    return data.logs.map((bl: any) => ({
      time: bl.time,
      level: (bl.level === 'success' ? 'success' : bl.level === 'error' ? 'error' : bl.level === 'warn' ? 'warn' : 'info') as LogEntry['level'],
      message: bl.message,
      source: bl.source || 'Core',
    }));
  } catch {
    return [];
  }
}

/**
 * Очистить ошибки и предупреждения из журнала (кнопка «Очистить ошибки» во вкладке «Логи»):
 * DELETE /api/issues/log сходит в LOG ядра и журналы плагинов data/plugins/activity/*.jsonl,
 * предупреждающий фильтр убирает только error/warn записи — info/действия остаются честно.
 */
export async function clearBackendLogIssues(): Promise<boolean> {
  try {
    const res = await fetch('/api/logs/issues', { method: 'DELETE' });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Отправить событие/ошибку UI на бэкенд (POST /api/logs), чтобы она осталась
 * во вкладке «Логи» даже после перезагрузки страницы. Fire-and-forget:
 * при недоступном бэкенде запись остаётся только в памяти страницы.
 */
export async function postBackendLog(entry: LogEntry): Promise<void> {
  try {
    await fetch('/api/logs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ time: entry.time, level: entry.level, message: entry.message, source: entry.source }),
    });
  } catch { /* бэкенд недоступен — лог останется локальным */ }
}

// ============================================================================
// Документация (MD-файлы)
// ============================================================================

export async function loadMDFile(name: string): Promise<{ content: string; error?: string }> {
  try {
    // Докам может быть вложенный путь (docs/X.md) — кодируем посегментно, иначе '/' станет %2F
    const enc = name.split('/').map(encodeURIComponent).join('/');
    const res = await fetch(`/api/md/${enc}`);
    const data = await res.json();
    if (data.error) return { content: '', error: data.error };
    return { content: data.content || '' };
  } catch {
    return { content: '', error: 'Ошибка сети' };
  }
}

export async function saveMDFile(name: string, content: string): Promise<{ success: boolean; error?: string }> {
  try {
    const enc = name.split('/').map(encodeURIComponent).join('/');
    const res = await fetch(`/api/md/${enc}` , {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

// ============================================================================
// Патчи
// ============================================================================

export interface PatchProgress {
  state: string;
  patch_id?: string;
  stage?: string;
  done?: number;
  total?: number | null;
  updated_at?: string;
}
export interface PatchReport {
  patch_id: string;
  applied_at?: string;
  files: string[];
  archive_status: string;
  archive_name?: string | null;
  backup_count: number;
}

export interface PatchStats {
  reports?: PatchReport[];
  total: number;
  applied: number;
  pending: number;
  errors: number;
  backups_count: number;
}

export async function loadPatchList(): Promise<PatchInfo[]> {
  try {
    const res = await fetch('/api/patches/list');
    const data = await res.json();
    return data.success ? data.patches : [];
  } catch {
    return [];
  }
}

export async function loadPatchStats(): Promise<PatchStats> {
  try {
    const res = await fetch('/api/patches/stats');
    const data = await res.json();
    return data.success ? data.stats : { total: 0, applied: 0, pending: 0, errors: 0, backups_count: 0 };
  } catch {
    return { total: 0, applied: 0, pending: 0, errors: 0, backups_count: 0 };
  }
}

function patchPayload(patch: PatchInfo) {
  return {
    patch_id: patch.patch_id,
    type: patch.patch_type,
    target_file: patch.target_file,
    full_file_content: patch.full_file_content || '',
    diff: patch.diff || '',
    filename: patch.filename,
  };
}

export async function previewPatch(patch: PatchInfo): Promise<any> {
  try {
    const res = await fetch('/api/patches/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patchPayload(patch)),
    });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function applyPatchApi(patch: PatchInfo): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const rawOps = (patch as any).operations;
    const isMulti = patch.patch_type === 'multi' || (Array.isArray(rawOps) && rawOps.length > 0);
    const payload = isMulti
      ? {
          patch_id: patch.patch_id,
          filename: patch.filename,
          type: 'multi',
          ...(Array.isArray(rawOps) && rawOps.length > 0 ? { operations: rawOps } : {}),
        }
      : {
          patch_id: patch.patch_id,
          filename: patch.filename,
          operations: [{
            type: patch.patch_type || (patch.diff ? 'unified_diff' : 'full_replace'),
            target_file: patch.target_file,
            full_file_content: patch.full_file_content || '',
            diff: patch.diff || '',
            find: (patch as any).find || '',
            replace: (patch as any).replace || ''
          }]
        };
    const res = await fetch('/api/patches/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function rollbackLastPatch(): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch('/api/patches/rollback', { method: 'POST' });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function archivePatchApi(filename: string): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch('/api/patches/archive', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
    });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function deletePatchApi(filename: string): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch('/api/patches/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
    });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function applyAllPendingApi(): Promise<{ success: boolean; results: Array<{ patch_id: string; success: boolean; error?: string }> }> {
  try {
    const res = await fetch('/api/patches/apply-all', { method: 'POST' });
    return await res.json();
  } catch {
    return { success: false, results: [] };
  }
}

// ============================================================================
// Система
// ============================================================================

export interface SystemResources {
  ram_used_gb: number;
  ram_total_gb: number;
  vram_used_gb: number;
  vram_total_gb: number;
}

export async function fetchSystemResources(): Promise<SystemResources | null> {
  try {
    const res = await fetch('/api/system/resources');
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function restartSystem(): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch('/api/system/restart', { method: 'POST' });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети. Система, возможно, перезапускается...' };
  }
}

// ============================================================================
// Проект
// ============================================================================

export async function scanProject(): Promise<{ files: ProjectFile[]; stats: ProjectStats | null }> {
  try {
    const res = await fetch('/api/project/scan');
    const data = await res.json();
    if (data.files) {
      return { files: data.files, stats: data.stats };
    }
    return { files: [], stats: null };
  } catch {
    return { files: [], stats: null };
  }
}

export async function loadProjectFile(path: string): Promise<{ success: boolean; content: string; error?: string }> {
  try {
    const res = await fetch(`/api/project/file?path=${encodeURIComponent(path)}`);
    const data = await res.json();
    if (data.success) {
      return { success: true, content: data.content };
    }
    return { success: false, content: '', error: data.error };
  } catch {
    return { success: false, content: '', error: 'Ошибка сети' };
  }
}

export async function archiveProjectFile(path: string): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch('/api/project/archive', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function deleteProjectFile(path: string): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch('/api/project/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function toggleImportant(path: string): Promise<{ success: boolean; important?: string[] }> {
  try {
    const res = await fetch('/api/project/important', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, action: 'toggle' }),
    });
    return await res.json();
  } catch {
    return { success: false };
  }
}

export async function bulkProjectAction(action: 'archive' | 'important' | 'delete', paths: string[]): Promise<{ success: boolean; processed: number }> {
  try {
    const res = await fetch('/api/project/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, paths }),
    });
    return await res.json();
  } catch {
    return { success: false, processed: 0 };
  }
}

export async function restoreProjectFile(archivePath: string): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch('/api/project/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ archive_path: archivePath }),
    });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

export async function rollbackProjectAction(): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch('/api/project/rollback', { method: 'POST' });
    return await res.json();
  } catch {
    return { success: false, error: 'Ошибка сети' };
  }
}

export interface ProjectHistoryEntry {
  action: string;
  paths: string[];
  backups: string[];
  timestamp: string;
}

export async function loadProjectHistory(): Promise<ProjectHistoryEntry[]> {
  try {
    const res = await fetch('/api/project/history');
    const data = await res.json();
    return data.history || [];
  } catch {
    return [];
  }
}

export interface ArchiveFile {
  path: string;
  filename: string;
  size: number;
  modified: string;
}

export async function loadArchiveList(): Promise<ArchiveFile[]> {
  try {
    const res = await fetch('/api/project/archive-list');
    const data = await res.json();
    return data.files || [];
  } catch {
    return [];
  }
}
