import { useCallback, useEffect, useState } from 'react';
import {
  PluginActivityEntry,
  PluginCatalogEntry,
  PluginConfirmation,
  PluginInfo,
} from '../types';
import {
  decideConfirmation,
  fetchConfirmations,
  fetchPluginActivity,
  fetchPlugins,
  fetchPluginsCatalog,
  fetchPluginsWarnings,
  installPlugin,
  pluginAction,
  uninstallPlugin,
  putPluginPermissions,
} from '../services/plugins';
import { POLL_INTERVALS } from '../utils/constants';

// ANTI-JITTER: обновляем состояние только если данные реально изменились —
// иначе каждый опрос рендерит новый массив и перерисовывает всех потребителей.
function sameJson(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function usePlugins() {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [catalog, setCatalog] = useState<PluginCatalogEntry[]>([]);
  const [confirmations, setConfirmations] = useState<PluginConfirmation[]>([]);
  const [activity, setActivity] = useState<PluginActivityEntry[]>([]);
  const [dataWarnings, setDataWarnings] = useState<{ registry_persist_error?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  const refresh = useCallback(async () => {
    const [pl, cat, warnings, conf, act] = await Promise.all([
      fetchPlugins(),
      fetchPluginsCatalog(),
      fetchPluginsWarnings(),
      fetchConfirmations(),
      fetchPluginActivity(),
    ]);
    let changed = false;
    setPlugins(prev => {
      if (pl && !sameJson(pl, prev)) { changed = true; return pl; }
      return prev;
    });
    setDataWarnings(prev => (warnings && !sameJson(warnings, prev) ? warnings : prev));
    setCatalog(prev => {
      if (cat && !sameJson(cat, prev)) { changed = true; return cat; }
      return prev;
    });
    setConfirmations(prev => {
      if (conf && !sameJson(conf, prev)) { changed = true; return conf; }
      return prev;
    });
    setActivity(prev => {
      if (act && !sameJson(act, prev)) { changed = true; return act; }
      return prev;
    });
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_INTERVALS.PLUGINS);
    return () => clearInterval(t);
  }, [refresh]);

  const install = useCallback(async (source: string) => {
    const r = await installPlugin(source);
    setNotice(r.ok ? { kind: 'ok', text: 'Плагин установлен' } : { kind: 'err', text: r.error || 'Ошибка установки' });
    await refresh();
    return r.ok;
  }, [refresh]);

  const enable = useCallback(async (id: string) => {
    const okA = await pluginAction(id, 'enable');
    setNotice(okA ? { kind: 'ok', text: `${id}: запущен` } : { kind: 'err', text: `${id}: не удалось включить` });
    await refresh();
    return okA;
  }, [refresh]);

  const disable = useCallback(async (id: string) => {
    const okA = await pluginAction(id, 'disable');
    setNotice(okA ? { kind: 'ok', text: `${id}: остановлен` } : { kind: 'err', text: `${id}: не удалось отключить` });
    await refresh();
    return okA;
  }, [refresh]);

  const uninstall = useCallback(async (id: string) => {
    const okA = await uninstallPlugin(id);
    setNotice(okA ? { kind: 'ok', text: `${id}: удалён` } : { kind: 'err', text: `${id}: не удалось удалить` });
    await refresh();
    return okA;
  }, [refresh]);

  const grantAll = useCallback(async (id: string, rows: { permission: string; granted: boolean }[]) => {
    const okA = await putPluginPermissions(id, rows);
    setNotice(okA ? { kind: 'ok', text: `${id}: разрешения сохранены` } : { kind: 'err', text: `${id}: ошибка сохранения разрешений` });
    await refresh();
    return okA;
  }, [refresh]);

  const decide = useCallback(async (cid: string, approve: boolean) => {
    const okA = await decideConfirmation(cid, approve);
    setNotice(okA
      ? { kind: 'ok', text: approve ? 'Подтверждено' : 'Отклонено' }
      : { kind: 'err', text: 'Не удалось обработать подтверждение' });
    await refresh();
    return okA;
  }, [refresh]);

  return {
    plugins, catalog, confirmations, activity, dataWarnings, loading, notice,
    refresh, install, enable, disable, uninstall, grantAll, decide, setNotice,
  };
}
