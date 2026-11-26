import { useEffect, useState } from 'react';
import {
  PluginActivityEntry,
  PluginCatalogEntry,
  PluginConfirmation,
  PluginInfo,
  PluginPermissionRow,
} from '../../types';
import { fetchPluginPermissions } from '../../services/plugins';

type Section = 'installed' | 'catalog' | 'permissions' | 'activity';

interface PluginsTabProps {
  plugins: PluginInfo[];
  catalog: PluginCatalogEntry[];
  confirmations: PluginConfirmation[];
  activity: PluginActivityEntry[];
  loading: boolean;
  notice: { kind: 'ok' | 'err'; text: string } | null;
  setNotice: (n: { kind: 'ok' | 'err'; text: string } | null) => void;
  refresh: () => Promise<void>;
  install: (source: string) => Promise<boolean>;
  enable: (id: string) => Promise<boolean>;
  disable: (id: string) => Promise<boolean>;
  uninstall: (id: string) => Promise<boolean>;
  grantAll: (id: string, rows: { permission: string; granted: boolean }[]) => Promise<boolean>;
  decide: (cid: string, approve: boolean) => Promise<boolean>;
}

const STATUS_COLORS: Record<string, string> = {
  running: 'text-emerald-400',
  installed: 'text-blue-400',
  disabled: 'text-gray-400',
  loading: 'text-cyan-400',
  error: 'text-red-400',
  incompatible: 'text-orange-400',
  update_available: 'text-yellow-400',
};

const LEVEL_COLORS: Record<string, string> = {
  read: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  write: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
  critical: 'bg-red-500/20 text-red-300 border-red-500/40',
};

const LEVEL_LABELS: Record<string, string> = {
  read: 'READ',
  write: 'WRITE',
  critical: 'CRITICAL',
};

const SECTIONS: { id: Section; label: string }[] = [
  { id: 'installed', label: 'Установленные' },
  { id: 'catalog', label: 'Каталог' },
  { id: 'permissions', label: 'Разрешения' },
  { id: 'activity', label: 'Активность' },
];

export default function PluginsTab(props: PluginsTabProps) {
  const { plugins, catalog, confirmations, activity, loading, notice, setNotice } = props;
  const [section, setSection] = useState<Section>('installed');
  const [permissionRow, setPermissionRow] = useState<PluginPermissionRow | null>(null);
  const [selectedPlugin, setSelectedPlugin] = useState<string | null>(null);

  useEffect(() => {
    if (section === 'permissions' && selectedPlugin) {
      fetchPluginPermissions(selectedPlugin).then(r => setPermissionRow(r));
    } else if (section !== 'permissions') {
      setPermissionRow(null);
    }
  }, [section, selectedPlugin]);
  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-2xl font-bold">🔌 Плагины</h2>
        <div className="flex items-center gap-2 flex-wrap">
          {SECTIONS.map(s => (
            <button
              key={s.id}
              type="button"
              onClick={() => setSection(s.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                section === s.id
                  ? 'bg-cyan-500/15 border-cyan-400/70 text-cyan-300'
                  : 'bg-gray-800/50 border-gray-700/60 text-gray-300 hover:border-gray-600'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {notice && (
        <div
          className={`px-4 py-2.5 rounded-lg border text-sm ${
            notice.kind === 'ok'
              ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
              : 'bg-red-500/10 border-red-500/40 text-red-300'
          }`}
          onClick={() => setNotice(null)}        >
          {notice.text}
        </div>
      )}

      <ConfirmationsPanel confirmations={confirmations} decide={props.decide} />

      {loading ? (
        <div className="text-sm text-gray-500 py-8 text-center">Загрузка…</div>
      ) : section === 'installed' ? (
        <InstalledSection
          plugins={plugins}
          onEnable={props.enable}
          onDisable={props.disable}
          onUninstall={props.uninstall}
        />
      ) : section === 'catalog' ? (
        <CatalogSection catalog={catalog} onInstall={props.install} />
      ) : section === 'permissions' ? (
        <PermissionsSection
          plugins={plugins}
          selected={selectedPlugin}
          setSelected={setSelectedPlugin}
          row={permissionRow}
          onSave={props.grantAll}
        />
      ) : (
        <ActivitySection activity={activity} />
      )}
    </div>
  );
}

function ConfirmationsPanel({
  confirmations,
  decide,
}: {
  confirmations: PluginConfirmation[];
  decide: (cid: string, approve: boolean) => Promise<boolean>;
}) {
  if (confirmations.length === 0) return null;
  return (
    <div className="rounded-xl border border-yellow-500/40 bg-yellow-500/5 p-4 space-y-3">
      <h3 className="text-sm font-bold text-yellow-300 uppercase tracking-wider">
        ⚠ Требуют подтверждения
      </h3>
      {confirmations.map(c => (
        <div key={c.id} className="flex items-center justify-between gap-3 flex-wrap bg-gray-900/60 border border-gray-800 rounded-lg px-3 py-2">
          <div className="min-w-0">
            <div className="text-sm text-white font-mono truncate">
              {c.plugin} · {c.capability}
            </div>
            <div className="text-xs text-gray-500">
              {c.policy === 'critical' ? 'CRITICAL' : 'WRITE'} · параметры:{' '}
              <span className="font-mono">{JSON.stringify(c.params).slice(0, 120)}</span>
            </div>
          </div>
          <div className="flex gap-2 shrink-0">
            <button
              type="button"
              onClick={() => decide(c.id, true)}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-yellow-500/20 border border-yellow-500/50 text-yellow-200 hover:bg-yellow-500/30"
            >
              Подтвердить
            </button>
            <button
              type="button"
              onClick={() => decide(c.id, false)}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-gray-700/60 border border-gray-600 text-gray-300 hover:bg-gray-700"
            >
              Отклонить
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function InstalledSection({
  plugins,
  onEnable,
  onDisable,
  onUninstall,
}: {
  plugins: PluginInfo[];
  onEnable: (id: string) => Promise<boolean>;
  onDisable: (id: string) => Promise<boolean>;
  onUninstall: (id: string) => Promise<boolean>;
}) {
  if (plugins.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-sm text-gray-500">
        Установленных плагинов нет. Раздел «Каталог» — доступные интеграции.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {plugins.map(p => (
        <div key={p.id} className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-bold text-white">{p.name}</span>
                <span className="text-xs text-gray-500 font-mono">v{p.version}</span>
                <span className={`text-xs font-bold uppercase ${STATUS_COLORS[p.status] || 'text-gray-400'}`}>
                  {p.status}
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-400">
                  {p.source === 'builtin' ? 'встроенный' : 'установлен'}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">{p.description}</p>
              {p.last_error && <p className="text-xs text-red-400 mt-1">⚠ {p.last_error}</p>}
              {p.capabilities && p.capabilities.length > 0 && (
                <p className="text-[11px] text-gray-600 mt-1">
                  операций: {p.capabilities.length} · API {p.api_version}
                </p>
              )}
            </div>
            <div className="flex gap-2 shrink-0">
              {p.status === 'running' ? (
                <button
                  type="button"
                  onClick={() => onDisable(p.id)}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-yellow-500/15 border border-yellow-500/40 text-yellow-300 hover:bg-yellow-500/25"
                >
                  Отключить
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => onEnable(p.id)}
                  disabled={p.status === 'incompatible'}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-40"
                >
                  Запустить
                </button>
              )}
              <button
                type="button"
                onClick={() => onUninstall(p.id)}
                className="px-3 py-1.5 rounded-lg text-xs font-bold bg-red-500/10 border border-red-500/40 text-red-300 hover:bg-red-500/20"
              >
                Удалить
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function CatalogSection({
  catalog,
  onInstall,
}: {
  catalog: PluginCatalogEntry[];
  onInstall: (source: string) => Promise<boolean>;
}) {
  if (catalog.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-sm text-gray-500">
        Встроенный каталог пуст.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {catalog.map(entry => {
        const m = entry.manifest;
        if (!m || !entry.available) {
          return (
            <div key={entry.errors.join('|')} className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-xs text-red-300">
              Некорректный плагин в каталоге: {entry.errors.join('; ')}
            </div>
          );
        }
        const installed = Boolean(entry.installed);
        return (
          <div key={m.id} className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-bold text-white">{m.name}</span>
                  <span className="text-xs text-gray-500 font-mono">v{m.version}</span>
                  {!entry.compatible && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/15 border border-orange-500/40 text-orange-300 font-bold">
                      несовместим с Plugin API {m.api_version}
                    </span>
                  )}
                  {installed && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/15 border border-blue-500/40 text-blue-300 font-bold">
                      установлен
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-1">{m.description}</p>
                <div className="flex gap-1.5 mt-2 flex-wrap">
                  {(entry.permissions || []).map(pp => (
                    <span
                      key={pp.permission}
                      className={`px-1.5 py-0.5 rounded border text-[10px] font-mono ${LEVEL_COLORS[pp.level] || ''}`}
                      title={`Уровень: ${LEVEL_LABELS[pp.level] || pp.level}`}
                    >
                      {pp.permission}
                    </span>
                  ))}
                </div>
              </div>
              <button
                type="button"
                disabled={installed || !entry.compatible}
                onClick={() => onInstall(`builtin:${m.id}`)}
                className="px-3 py-1.5 rounded-lg text-xs font-bold bg-cyan-500/15 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/25 disabled:opacity-40 shrink-0"
              >
                {installed ? 'Установлен' : 'Установить'}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PermissionsSection({
  plugins,
  selected,
  setSelected,
  row,
  onSave,
}: {
  plugins: PluginInfo[];
  selected: string | null;
  setSelected: (id: string) => void;
  row: PluginPermissionRow | null;
  onSave: (id: string, rows: { permission: string; granted: boolean }[]) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState<Record<string, boolean>>({});
  useEffect(() => {
    if (row) {
      const d: Record<string, boolean> = {};
      row.permissions.forEach(p => (d[p.permission] = p.granted));
      setDraft(d);
    }
  }, [row]);

  if (plugins.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-sm text-gray-500">
        Нет установленных плагинов.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap">
        {plugins.map(p => (
          <button
            key={p.id}
            type="button"
            onClick={() => setSelected(p.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${
              selected === p.id
                ? 'bg-cyan-500/15 border-cyan-400/70 text-cyan-300'
                : 'bg-gray-800/50 border-gray-700/60 text-gray-300'
            }`}
          >
            {p.name}
          </button>
        ))}
      </div>
      {row && selected === row.plugin && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-2">
          {row.permissions.map(p => (
            <div key={p.permission} className="flex items-center justify-between gap-3 py-1.5 border-b border-gray-800/40 last:border-0">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold ${LEVEL_COLORS[p.level]}`}>
                  {LEVEL_LABELS[p.level] || p.level.toUpperCase()}
                </span>
                <span className="text-sm text-gray-300 font-mono truncate">{p.permission}</span>
              </div>
              <button
                type="button"
                onClick={() => setDraft(prev => ({ ...prev, [p.permission]: !prev[p.permission] }))}
                className={`px-3 py-1 rounded-lg text-xs font-bold border ${
                  draft[p.permission]
                    ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                    : 'bg-gray-800 border-gray-700 text-gray-400'
                }`}
              >
                {draft[p.permission] ? 'выдано' : 'нет'}
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() =>
              onSave(
                row.plugin,
                row.permissions.map(p => ({ permission: p.permission, granted: Boolean(draft[p.permission]) })),
              )
            }
            className="px-4 py-2 rounded-lg text-xs font-bold bg-cyan-500/15 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/25"
          >
            Сохранить разрешения
          </button>
        </div>
      )}
    </div>
  );
}

function ActivitySection({ activity }: { activity: PluginActivityEntry[] }) {
  if (activity.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-sm text-gray-500">
        Журнал активности пуст.
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 max-h-[70vh] overflow-y-auto">
      {activity.map((e, i) => (
        <div key={`${e.ts}-${i}`} className="flex items-start gap-3 py-2 font-mono text-sm border-b border-gray-800/30 last:border-0">
          <span className="text-gray-600 shrink-0">[{e.ts}]</span>
          <span
            className={
              e.level === 'error'
                ? 'text-red-400'
                : e.level === 'warn'
                ? 'text-yellow-400'
                : e.level === 'action'
                ? 'text-cyan-400'
                : 'text-blue-400'
            }
          >
            {e.level === 'error' ? '✕' : e.level === 'warn' ? '⚠' : e.level === 'action' ? '▶' : 'ℹ'}
          </span>
          <div className="min-w-0">
            <span className="text-gray-300">
              {e.plugin ? `[${e.plugin}] ` : ''}
              {e.event}
            </span>
            {e.details && (
              <p className="text-xs text-gray-600 mt-0.5 break-all">{JSON.stringify(e.details)}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
