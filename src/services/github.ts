import {
  ExecOutcome,
  GitHubBranchList,
  GitHubConnection,
  GitHubDirListing,
  GitHubFileContent,
  GitHubRepoList,
  GitHubTree,
  PluginConfirmation,
  PluginSecretKeys,
} from '../types';

/** Ключ здоровья плагина GitHub. */
export const GITHUB_PLUGIN_ID = 'github';

/**
 * Вызов capability через Capability Gateway.
 * READ (auto) выполняется сразу; WRITE/CRITICAL возвращают confirmation_required —
 * повторный вызов с confirmation_token исполняет подтверждённую операцию.
 */
export async function execCapability<T>(
  capability: string,
  params?: Record<string, unknown>,
  confirmationToken?: string,
): Promise<ExecOutcome<T>> {
  const empty: ExecOutcome<T> = { status: 'error', error: 'backend недоступен', code: 'network' };
  try {
    const res = await fetch(`/api/plugins/${GITHUB_PLUGIN_ID}/exec`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ capability, params: params ?? {}, confirmation_token: confirmationToken }),
    });
    const data = await res.json().catch(() => null);
    if (!data) return empty;
    if (data.status === 'confirmation_required' && data.confirmation) {
      return { status: 'confirmation_required', confirmation: data.confirmation as PluginConfirmation };
    }
    if (data.success && data.status === 'done') {
      return { status: 'done', result: data.result as T };
    }
    return { status: 'error', error: String(data.error || 'ошибка выполнения'), code: String(data.code || 'exec_failed') };
  } catch {
    return empty;
  }
}

export interface PluginSettingsPayload {
  plugin: string;
  settings: Record<string, string | number | boolean>;
  schema: Record<string, { type: string; description?: string; default?: unknown; enum?: unknown[] }>;
}

export async function fetchPluginSettings(pid: string): Promise<PluginSettingsPayload | null> {
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(pid)}/settings`);
    const data = await res.json().catch(() => null);
    return data?.success ? (data as PluginSettingsPayload) : null;
  } catch {
    return null;
  }
}

export async function putPluginSettings(
  pid: string,
  settings: Record<string, string | number | boolean>,
): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(pid)}/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings }),
    });
    const data = await res.json().catch(() => null);
    return data?.success ? { ok: true } : { ok: false, error: String(data?.error || 'ошибка сохранения настроек') };
  } catch {
    return { ok: false, error: 'backend недоступен' };
  }
}

/** Запись секретов (write-only). Значения никогда не читаются обратно. */
export async function putPluginSecrets(
  pid: string,
  secrets: Record<string, string>,
): Promise<{ ok: boolean; keys?: string[]; error?: string }> {
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(pid)}/secrets`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ secrets }),
    });
    const data = await res.json().catch(() => null);
    const keys = (data as PluginSecretKeys | null)?.secrets;
    return data?.success ? { ok: true, keys } : { ok: false, error: String(data?.error || 'ошибка записи секрета') };
  } catch {
    return { ok: false, error: 'backend недоступен' };
  }
}

/** Health-диагностика плагина (settings_configured / private_key_stored / auth_configured). */
export async function fetchPluginHealthCompat(pid: string): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(pid)}/health`);
    const data = await res.json().catch(() => null);
    return data?.success && data.health ? (data.health as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

/** Имена сохранённых секретов (значения недоступны по REST в принципе). */
export async function fetchPluginSecretKeys(pid: string): Promise<string[] | null> {
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(pid)}/secrets`);
    const data = await res.json().catch(() => null);
    const keys = (data as PluginSecretKeys | null)?.secrets;
    return data?.success && Array.isArray(keys) ? keys : null;
  } catch {
    return null;
  }
}

export async function deletePluginSecret(pid: string, key: string): Promise<boolean> {
  try {
    const res = await fetch(
      `/api/plugins/${encodeURIComponent(pid)}/secrets/${encodeURIComponent(key)}`,
      { method: 'DELETE' },
    );
    const data = await res.json().catch(() => null);
    return Boolean(data?.success);
  } catch {
    return false;
  }
}

// ==== типизированные обёртки capabilities GitHub Plugin ====

export const githubListRepositories = (page = 1) =>
  execCapability<GitHubRepoList>('github.list_repositories', { page });

export const githubListBranches = (repository: string) =>
  execCapability<GitHubBranchList>('github.list_branches', { repository });

export const githubGetTree = (repository: string, ref: string, recursive = true) =>
  execCapability<GitHubTree>('github.get_tree', { repository, ref, recursive });

export const githubGetFile = (repository: string, path: string, ref?: string) =>
  execCapability<GitHubDirListing | GitHubFileContent>('github.get_file', { repository, path, ref });

export const githubTestConnection = () =>
  execCapability<GitHubConnection>('github.test_connection');
