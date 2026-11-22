import { LogEntry, OllamaModel, PatchInfo, ProjectFile, ProjectStats } from '../types';

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

// ============================================================================
// Документация (MD-файлы)
// ============================================================================

export async function loadMDFile(name: string): Promise<{ content: string; error?: string }> {
  try {
    const res = await fetch(`/api/md/${encodeURIComponent(name)}`);
    const data = await res.json();
    if (data.error) return { content: '', error: data.error };
    return { content: data.content || '' };
  } catch {
    return { content: '', error: 'Ошибка сети' };
  }
}

export async function saveMDFile(name: string, content: string): Promise<{ success: boolean; error?: string }> {
  try {
    const res = await fetch(`/api/md/${encodeURIComponent(name)}` , {
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

export interface PatchStats {
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
    const res = await fetch('/api/patches/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patchPayload(patch)),
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
