import {
  PluginActivityEntry,
  PluginCatalogEntry,
  PluginInfo,
  PluginPermissionRow,
} from '../types';

async function j<T>(res: Response): Promise<T | null> {
  try {
    const data = await res.json();
    return data as T;
  } catch {
    return null;
  }
}

export async function fetchPlugins(): Promise<PluginInfo[] | null> {
  try {
    const res = await fetch('/api/plugins');
    const data = await j<{ success: boolean; plugins: PluginInfo[] }>(res);
    return data?.success && Array.isArray(data.plugins) ? data.plugins : null;
  } catch {
    return null;
  }
}

export async function fetchPluginsWarnings(): Promise<{ registry_persist_error?: string } | null> {
  try {
    const res = await fetch('/api/plugins');
    const data = await j<{ success: boolean; data_warnings?: { registry_persist_error?: string } }>(res);
    return data?.success ? (data.data_warnings ?? null) : null;
  } catch {
    return null;
  }
}

export async function fetchPluginsCatalog(): Promise<PluginCatalogEntry[] | null> {
  try {
    const res = await fetch('/api/plugins/catalog');
    const data = await j<{ success: boolean; catalog: PluginCatalogEntry[] }>(res);
    return data?.success && Array.isArray(data.catalog) ? data.catalog : null;
  } catch {
    return null;
  }
}

export async function fetchPluginPermissions(id: string): Promise<PluginPermissionRow | null> {
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(id)}/permissions`);
    const data = await j<PluginPermissionRow & { success: boolean }>(res);
    return data?.success ? data : null;
  } catch {
    return null;
  }
}

export async function putPluginPermissions(
  id: string,
  grants: { permission: string; granted: boolean }[],
): Promise<boolean> {
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(id)}/permissions`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ grants }),
    });
    const data = await j<{ success: boolean }>(res);
    return Boolean(data?.success);
  } catch {
    return false;
  }
}

export async function installPlugin(source: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch('/api/plugins/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source }),
    });
    const data = await j<{ success: boolean; error?: string }>(res);
    return data?.success ? { ok: true } : { ok: false, error: data?.error || 'установка отклонена' };
  } catch {
    return { ok: false, error: 'backend недоступен' };
  }
}

export async function pluginAction(id: string, action: 'enable' | 'disable'): Promise<boolean> {
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(id)}/${action}`, { method: 'POST' });
    const data = await j<{ success: boolean }>(res);
    return Boolean(data?.success);
  } catch {
    return false;
  }
}

export async function uninstallPlugin(id: string): Promise<boolean> {
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(id)}`, { method: 'DELETE' });
    const data = await j<{ success: boolean }>(res);
    return Boolean(data?.success);
  } catch {
    return false;
  }
}

export async function fetchPluginHealth(
  id: string,
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`/api/plugins/${encodeURIComponent(id)}/health`);
    const data = await j<{ success: boolean; health: Record<string, unknown> }>(res);
    return data?.success ? data.health : null;
  } catch {
    return null;
  }
}

export async function fetchPluginActivity(id?: string): Promise<PluginActivityEntry[] | null> {
  try {
    const q = id ? `?plugin=${encodeURIComponent(id)}` : '';
    const res = await fetch(`/api/plugins/activity${q}`);
    const data = await j<{ success: boolean; activity: PluginActivityEntry[] }>(res);
    return data?.success && Array.isArray(data.activity) ? data.activity : null;
  } catch {
    return null;
  }
}

export async function fetchConfirmations() {
  try {
    const res = await fetch('/api/plugins/confirmations');
    const data = await j<{ success: boolean; confirmations: import('../types').PluginConfirmation[] }>(res);
    return data?.success && Array.isArray(data.confirmations) ? data.confirmations : null;
  } catch {
    return null;
  }
}

export async function decideConfirmation(cid: string, approve: boolean): Promise<boolean> {
  try {
    const res = await fetch(`/api/plugins/confirmations/${encodeURIComponent(cid)}/${approve ? 'approve' : 'reject'}`, {
      method: 'POST',
    });
    const data = await j<{ success: boolean }>(res);
    return Boolean(data?.success);
  } catch {
    return false;
  }
}
