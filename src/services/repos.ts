import {
  ExecOutcome,
  PluginConfirmation,
  ReposDiagnostics,
  RepoBranches,
  RepoDiff,
  RepoFileContent,
  RepoLog,
  RepoRemote,
  RepoStatus,
  RepoSyncResult,
  SimpleGitResult,
} from '../types';

/** id плагина «Репозитории». */
export const REPOS_PLUGIN_ID = 'repos';

/**
 * Вызов capability через Capability Gateway (плагин-агностично).
 * READ (auto) выполняется сразу; WRITE (confirm) возвращает confirmation_required —
 * повторный вызов с confirmation_token исполняет подтверждённую операцию.
 */
export async function execCapability<T>(
  capability: string,
  params?: Record<string, unknown>,
  confirmationToken?: string,
): Promise<ExecOutcome<T>> {
  const empty: ExecOutcome<T> = { status: 'error', error: 'backend недоступен', code: 'network' };
  try {
    const res = await fetch(`/api/plugins/${REPOS_PLUGIN_ID}/exec`, {
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

// ==== типизированные обёртки capabilities плагина repos (READ — авто) ====

export const reposDiagnostics = () =>
  execCapability<ReposDiagnostics>('repos.diagnostics');

export const reposStatus = (path: string) =>
  execCapability<RepoStatus>('repos.status', { path });

export const reposLog = (path: string, limit = 30) =>
  execCapability<RepoLog>('repos.log', { path, limit });

export const reposBranches = (path: string) =>
  execCapability<RepoBranches>('repos.branches', { path });

export const reposRemote = (path: string) =>
  execCapability<RepoRemote>('repos.remote', { path });

export const reposDiff = (path: string, staged: boolean) =>
  execCapability<RepoDiff>('repos.diff', { path, staged });

export const reposReadFile = (path: string, rel: string) =>
  execCapability<RepoFileContent>('repos.read_file', { path, rel });

// ==== WRITE — вызывать через execWrite с подтверждением ====

export const reposAdd = (path: string, token?: string) =>
  execCapability<SimpleGitResult>('repos.add', { path }, token);

export const reposCommit = (path: string, message: string, token?: string) =>
  execCapability<SimpleGitResult>('repos.commit', { path, message }, token);

export const reposPush = (path: string, token?: string) =>
  execCapability<SimpleGitResult>('repos.push', { path }, token);

export const reposPull = (path: string, rebase: boolean, token?: string) =>
  execCapability<SimpleGitResult>('repos.pull', { path, rebase }, token);

export const reposFetch = (path: string, token?: string) =>
  execCapability<SimpleGitResult>('repos.fetch', { path }, token);

export const reposCheckout = (path: string, branch: string, create: boolean, token?: string) =>
  execCapability<SimpleGitResult>('repos.checkout', { path, branch, create }, token);

export const reposSync = (path: string, message: string, token?: string) =>
  execCapability<RepoSyncResult>('repos.sync', { path, message }, token);

/** PUT настроек плагина (путь репозитория по умолчанию). */
export async function putRepoSettings(
  settings: Record<string, string | number | boolean>,
): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch(`/api/plugins/${REPOS_PLUGIN_ID}/settings`, {
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
