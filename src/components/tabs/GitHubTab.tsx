import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  GitHubBranchList,
  GitHubConnection,
  GitHubDirListing,
  GitHubFileContent,
  GitHubRepoList,
  GitHubTree,
  PluginInfo,
} from '../../types';
import {
  GITHUB_PLUGIN_ID,
  deletePluginSecret,
  execCapability,
  fetchPluginHealthCompat,
  fetchPluginSecretKeys,
  fetchPluginSettings,
  githubGetFile,
  githubGetTree,
  githubListBranches,
  githubListRepositories,
  githubTestConnection,
  putPluginSecrets,
  putPluginSettings,
} from '../../services/github';
import { decideConfirmation } from '../../services/plugins';

type Section = 'connect' | 'repositories';

interface GitHubTabProps {
  plugins: PluginInfo[];
  refresh: () => Promise<void>;
  setActiveTab: (t: 'plugins') => void;
}

type Notice = { kind: 'ok' | 'err'; text: string } | null;

const HEALTH_LABELS: Record<string, string> = {
  settings_configured: 'app_id/installation_id',
  private_key_stored: 'Private Key',
  auth_configured: 'авторизация',
};

export default function GitHubTab({ plugins, refresh, setActiveTab }: GitHubTabProps) {
  const [section, setSection] = useState<Section>('connect');
  const [notice, setNotice] = useState<Notice>(null);

  const gh = plugins.find(p => p.id === GITHUB_PLUGIN_ID);
  const running = gh?.status === 'running';

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-2xl font-bold">🐙 GitHub</h2>
        <div className="flex items-center gap-2 flex-wrap">
          {running && (
            <>
              <SectionButton active={section === 'connect'} onClick={() => setSection('connect')}>
                Подключение
              </SectionButton>
              <SectionButton active={section === 'repositories'} onClick={() => setSection('repositories')}>
                Репозитории
              </SectionButton>
            </>
          )}
        </div>
      </div>

      {notice && (
        <div
          className={`px-4 py-2.5 rounded-lg border text-sm cursor-pointer ${
            notice.kind === 'ok'
              ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
              : 'bg-red-500/10 border-red-500/40 text-red-300'
          }`}
          onClick={() => setNotice(null)}
        >
          {notice.text}
        </div>
      )}

      {!running ? (
        <PluginGate gh={gh} setActiveTab={setActiveTab} />
      ) : section === 'connect' ? (
        <ConnectSection setNotice={setNotice} refresh={refresh} />
      ) : (
        <RepositoriesSection setNotice={setNotice} />
      )}
    </div>
  );
}

function SectionButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
        active
          ? 'bg-cyan-500/15 border-cyan-400/70 text-cyan-300'
          : 'bg-gray-800/50 border-gray-700/60 text-gray-300 hover:border-gray-600'
      }`}
    >
      {children}
    </button>
  );
}

function PluginGate({
  gh,
  setActiveTab,
}: {
  gh: PluginInfo | undefined;
  setActiveTab: (t: 'plugins') => void;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 space-y-3">
      <h3 className="font-bold text-white">Плагин GitHub не активен</h3>
      {gh ? (
        <p className="text-sm text-gray-400">
          Статус плагина: <span className="font-mono">{gh.status}</span>
          {gh.last_error ? <> · ошибка: <span className="text-red-400 font-mono">{gh.last_error}</span></> : null}
        </p>
      ) : (
        <p className="text-sm text-gray-400">
          Плагин <span className="font-mono">github</span> не установлен. Он доступен во встроенном каталоге.
        </p>
      )}
      <button
        type="button"
        onClick={() => setActiveTab('plugins')}
        className="px-4 py-2 rounded-lg text-sm font-bold bg-cyan-500/15 border border-cyan-400/70 text-cyan-300 hover:bg-cyan-500/25"
      >
        🔌 Открыть «Плагины»
      </button>
    </div>
  );
}

// ============================ Подключение (GitHub App) ============================

function ConnectSection({
  setNotice,
  refresh,
}: {
  setNotice: (n: Notice) => void;
  refresh: () => Promise<void>;
}) {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [schema, setSchema] = useState<Record<string, { type: string; description?: string; default?: unknown }>>({});
  const [secretKeys, setSecretKeys] = useState<string[]>([]);
  const [pem, setPem] = useState('');
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [connection, setConnection] = useState<GitHubConnection | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    const [s, h, k] = await Promise.all([
      fetchPluginSettings(GITHUB_PLUGIN_ID),
      fetchPluginHealthCompat(GITHUB_PLUGIN_ID),
      fetchPluginSecretKeys(GITHUB_PLUGIN_ID),
    ]);
    if (s) {
      setSettings(Object.fromEntries(Object.entries(s.settings).map(([key, v]) => [key, String(v)])));
      setSchema(s.schema || {});
    }
    if (h) setHealth(h);
    if (k) setSecretKeys(k);
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const editable = Object.keys(schema);

  const save = async () => {
    setBusy(true);
    const updates: Record<string, string> = {};
    for (const k of editable) updates[k] = settings[k] ?? '';
    const r1 = await putPluginSettings(GITHUB_PLUGIN_ID, updates);
    if (!r1.ok) {
      setNotice({ kind: 'err', text: r1.error || 'ошибка сохранения' });
      setBusy(false);
      return;
    }
    if (pem.trim()) {
      const r2 = await putPluginSecrets(GITHUB_PLUGIN_ID, { private_key: pem });
      if (!r2.ok) {
        setNotice({ kind: 'err', text: r2.error || 'ошибка записи Private Key' });
        setBusy(false);
        return;
      }
      setPem('');
      setNotice({ kind: 'ok', text: 'Настройки GitHub App сохранены, Private Key записан (только backend)' });
    } else {
      setNotice({ kind: 'ok', text: 'Настройки GitHub App сохранены' });
    }
    await reload();
    await refresh();
    setBusy(false);
  };

  const removeKey = async () => {
    setBusy(true);
    const okDel = await deletePluginSecret(GITHUB_PLUGIN_ID, 'private_key');
    setNotice(okDel
      ? { kind: 'ok', text: 'Private Key удалён' }
      : { kind: 'err', text: 'не удалось удалить Private Key' });
    await reload();
    setBusy(false);
  };

  const test = async () => {
    setBusy(true);
    setConnection(null);
    const r = await githubTestConnection();
    if (r.status === 'done') setConnection(r.result);
    else if (r.status === 'error') setConnection({ ok: false, configured: true, error: r.error });
    setBusy(false);
  };

  const healthBadges = useMemo(() => {
    if (!health) return null;
    const items: { label: string; ok: boolean }[] = [];
    for (const key of Object.keys(HEALTH_LABELS)) {
      if (key in health) items.push({ label: HEALTH_LABELS[key], ok: Boolean(health[key]) });
    }
    return items;
  }, [health]);

  const hasKey = secretKeys.includes('private_key');

  return (
    <div className="space-y-4">
      {healthBadges && (
        <div className="flex gap-2 flex-wrap">
          {healthBadges.map(b => (
            <span
              key={b.label}
              className={`text-[11px] px-2 py-1 rounded-md border font-mono ${
                b.ok
                  ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                  : 'bg-gray-800 border-gray-700 text-gray-500'
              }`}
            >
              {b.ok ? '✓' : '○'} {b.label}
            </span>
          ))}
        </div>
      )}

      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-3">
        <h3 className="text-sm font-bold text-gray-300 uppercase tracking-wider">GitHub App</h3>
        {editable.length === 0 && <p className="text-xs text-gray-500">Схема настроек пуста.</p>}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {editable.map(k => (
            <label key={k} className="block">
              <span className="block text-xs text-gray-400 mb-1">
                <span className="font-mono text-gray-300">{k}</span>
                {schema[k]?.description ? <> — {schema[k].description}</> : null}
              </span>
              <input
                value={settings[k] ?? ''}
                onChange={e => setSettings(s => ({ ...s, [k]: e.target.value }))}
                className="w-full bg-gray-800/70 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 font-mono focus:border-cyan-500/70 focus:outline-none"
              />
            </label>
          ))}
        </div>

        <label className="block">
          <span className="block text-xs text-gray-400 mb-1">
            <span className="font-mono text-gray-300">Private Key</span> (.pem) — хранится только на backend
            {hasKey
              ? <span className="ml-2 text-emerald-400">✓ сохранён</span>
              : <span className="ml-2 text-gray-500">не задан</span>}
          </span>
          <textarea
            value={pem}
            onChange={e => setPem(e.target.value)}
            rows={5}
            spellCheck={false}
            placeholder={'-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----'}
            className="w-full bg-gray-800/70 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-200 font-mono focus:border-cyan-500/70 focus:outline-none"
          />
        </label>

        <div className="flex gap-2 flex-wrap">
          <button
            type="button"
            onClick={save}
            disabled={busy}
            className="px-4 py-2 rounded-lg text-sm font-bold bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-40"
          >
            Сохранить
          </button>
          <button
            type="button"
            onClick={test}
            disabled={busy}
            className="px-4 py-2 rounded-lg text-sm font-bold bg-cyan-500/15 border border-cyan-400/70 text-cyan-300 hover:bg-cyan-500/25 disabled:opacity-40"
          >
            Проверить подключение
          </button>
          {hasKey && (
            <button
              type="button"
              onClick={removeKey}
              disabled={busy}
              className="px-4 py-2 rounded-lg text-sm font-bold bg-red-500/10 border border-red-500/40 text-red-300 hover:bg-red-500/20 disabled:opacity-40"
            >
              Удалить Private Key
            </button>
          )}
        </div>

        {connection && (
          <div
            className={`rounded-lg border px-3 py-2 text-sm font-mono whitespace-pre-wrap ${
              connection.ok
                ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                : 'bg-red-500/10 border-red-500/40 text-red-300'
            }`}
          >
            {connection.ok
              ? `✓ Подключено · репозиториев в установке: ${connection.repositories_total}`
              : `✗ ${connection.error || 'подключение не удалось'}`}
          </div>
        )}
      </div>

      {secretKeys.length > 0 && (
        <p className="text-[11px] text-gray-500 font-mono">
          хранимые секреты (имена): {secretKeys.join(', ')}
        </p>
      )}
    </div>
  );
}

// ============================ Репозитории ============================

function RepositoriesSection({ setNotice }: { setNotice: (n: Notice) => void }) {
  const [repos, setRepos] = useState<GitHubRepoList | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async (page = 1) => {
    setLoading(true);
    const r = await githubListRepositories(page);
    setLoading(false);
    if (r.status === 'done') setRepos(r.result);
    else if (r.status === 'error') setNotice({ kind: 'err', text: r.error });
    else setNotice({ kind: 'err', text: 'требуется подтверждение (непредвиденно для READ)' });
  }, [setNotice]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    if (!repos) return [];
    const q = search.trim().toLowerCase();
    return q ? repos.repositories.filter(r => r.full_name.toLowerCase().includes(q)) : repos.repositories;
  }, [repos, search]);

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center flex-wrap">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Поиск по имени…"
          className="flex-1 min-w-[200px] bg-gray-800/70 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:border-cyan-500/70 focus:outline-none"
        />
        <button
          type="button"
          onClick={() => load()}
          disabled={loading}
          className="px-4 py-2 rounded-lg text-sm font-bold bg-gray-800 border border-gray-700 text-gray-300 hover:border-gray-600 disabled:opacity-40"
        >
          ⟳ Обновить
        </button>
        {repos && (
          <span className="text-xs text-gray-500">всего: {repos.total_count} (стр. {repos.page})</span>
        )}
      </div>

      {loading && <div className="text-sm text-gray-500 py-4 text-center">Загрузка…</div>}

      {!loading && !repos && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-sm text-gray-500">
          Список недоступен — проверьте подключение на вкладке «Подключение».
        </div>
      )}

      {!loading && repos && filtered.length === 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-sm text-gray-500">
          Репозиториев не найдено.
        </div>
      )}

      {filtered.length > 0 && (
        <div className="space-y-2">
          {filtered.map(r => (
            <div
              key={r.full_name}
              className={`rounded-xl border p-4 cursor-pointer transition-all ${
                selected === r.full_name
                  ? 'border-cyan-400/60 bg-cyan-500/5'
                  : 'border-gray-800 bg-gray-900/50 hover:border-gray-700'
              }`}
              onClick={() => setSelected(selected === r.full_name ? null : r.full_name)}
            >
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-bold text-white font-mono">{r.full_name}</span>
                {r.private && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/15 border border-yellow-500/30 text-yellow-300">
                    private
                  </span>
                )}
                {r.default_branch && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-400 font-mono">
                    ⎇ {r.default_branch}
                  </span>
                )}
              </div>
              {r.description && <p className="text-xs text-gray-500 mt-1">{r.description}</p>}
            </div>
          ))}
        </div>
      )}

      {selected && <RepoBrowser repository={selected} setNotice={setNotice} />}
    </div>
  );
}

// ============================ Браузер репозитория ============================

const fmtSize = (n?: number) => (typeof n === 'number' && n < 1024 ? `${n} B` : `${Math.round((n || 0) / 1024)} KB`);

function RepoBrowser({ repository, setNotice }: { repository: string; setNotice: (n: Notice) => void }) {
  const [branches, setBranches] = useState<GitHubBranchList | null>(null);
  const [ref, setRef] = useState<string>('');
  const [dir, setDir] = useState<string>('');
  const [tree, setTree] = useState<GitHubTree | null>(null);
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState<{ path: string; text: string; size: number } | null>(null);
  const [fileLoading, setFileLoading] = useState(false);

  const loadBranches = useCallback(async () => {
    const r = await githubListBranches(repository);
    if (r.status === 'done') {
      setBranches(r.result);
      if (r.result.branches.length > 0) setRef(prev => prev || r.result.branches[0].name);
    } else if (r.status === 'error') {
      setNotice({ kind: 'err', text: `ветки: ${r.error}` });
    }
  }, [repository, setNotice]);

  useEffect(() => {
    setBranches(null);
    setRef('');
    setDir('');
    setTree(null);
    setFile(null);
    loadBranches();
  }, [repository, loadBranches]);

  const loadTree = useCallback(async (branchRef: string) => {
    setLoading(true);
    const r = await githubGetTree(repository, branchRef, true);
    setLoading(false);
    if (r.status === 'done') setTree(r.result);
    else if (r.status === 'error') setNotice({ kind: 'err', text: `дерево: ${r.error}` });
  }, [repository, setNotice]);

  useEffect(() => {
    if (ref) loadTree(ref);
  }, [ref, loadTree]);

  const entries = useMemo(() => {
    if (!tree) return [];
    const prefix = dir ? dir + '/' : '';
    const seen = new Set<string>();
    const out: { name: string; path: string; type: string; size?: number }[] = [];
    if (dir) out.push({ name: '..', path: dir.includes('/') ? dir.slice(0, dir.lastIndexOf('/')) : '', type: 'dir' });
    for (const e of tree.tree) {
      if (!e.path.startsWith(prefix)) continue;
      const rest = e.path.slice(prefix.length);
      if (!rest || rest.startsWith('/')) continue;
      const slash = rest.indexOf('/');
      if (slash >= 0) {
        const sub = rest.slice(0, slash);
        if (!seen.has(sub)) {
          seen.add(sub);
          out.push({ name: sub, path: prefix + sub, type: 'tree' });
        }
      } else {
        out.push({ name: rest, path: e.path, type: e.type, size: e.size });
      }
    }
    return out.sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === 'tree' ? -1 : 1));
  }, [tree, dir]);

  const openFile = async (path: string) => {
    setFileLoading(true);
    setFile(null);
    const r = await githubGetFile(repository, path, ref || undefined);
    setFileLoading(false);
    if (r.status !== 'done') {
      setNotice({ kind: 'err', text: r.status === 'error' ? `файл: ${r.error}` : 'файл: требуется подтверждение (непредвиденно)' });
      return;
    }
    const d = r.result;
    if (d.type !== 'file') {
      setNotice({ kind: 'err', text: 'это каталог — выберите файл' });
      return;
    }
    const fc = d as GitHubFileContent;
    let text: string;
    try {
      if (fc.encoding === 'base64') {
        const bin = atob(fc.content.replace(/\s/g, ''));
        const bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
        text = new TextDecoder('utf-8').decode(bytes);
      } else {
        text = fc.content;
      }
    } catch {
      text = '(не удалось декодировать содержимое)';
    }
    setFile({ path: fc.path, text, size: fc.size });
  };

  return (
    <div className="rounded-xl border border-cyan-500/30 bg-gray-900/50 p-4 space-y-3">
      <RepoHeader repository={repository} branches={branches} refState={[ref, setRef]} />
      {loading && <div className="text-sm text-gray-500 py-4 text-center">Загрузка дерева…</div>}
      {!loading && tree?.truncated && (
        <div className="text-xs text-yellow-300 bg-yellow-500/10 border border-yellow-500/40 rounded-lg px-3 py-2">
          дерево усечено GitHub (truncated) — крупные репозитории показаны не полностью
        </div>
      )}
      {!loading && tree && (
        <>
          <Breadcrumbs dir={dir} onNavigate={setDir} repository={repository} />
          <div className="divide-y divide-gray-800/70 rounded-lg border border-gray-800 overflow-hidden">
            {entries.map(e => (
              <div
                key={e.path + e.type}
                className="flex items-center justify-between px-3 py-2 hover:bg-gray-800/50 cursor-pointer"
                onClick={() => (e.name === '..' || e.type === 'tree' ? setDir(e.path) : openFile(e.path))}
              >
                <span className="font-mono text-sm text-gray-300 truncate">
                  {e.name === '..' ? '↩ ..' : e.type === 'tree' ? `📁 ${e.name}` : `📄 ${e.name}`}
                </span>
                {e.type !== 'tree' && e.name !== '..' && (
                  <span className="text-[11px] text-gray-600 font-mono shrink-0">{fmtSize(e.size)}</span>
                )}
              </div>
            ))}
            {entries.length === 0 && (
              <div className="px-3 py-4 text-sm text-gray-600 text-center">пустой каталог</div>
            )}
          </div>
          <CreateBranchBar repository={repository} branches={branches} onDone={loadBranches} setNotice={setNotice} />
          {fileLoading && <div className="text-xs text-gray-500">Чтение файла…</div>}
          {file && (
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-300 font-mono break-all">{file.path}</span>
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  className="text-xs text-gray-500 hover:text-gray-300"
                >
                  ✕ закрыть
                </button>
              </div>
              <pre className="max-h-96 overflow-auto text-[11px] leading-4 bg-gray-950/80 border border-gray-800 rounded-lg p-3 text-gray-300">
                {file.text}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function RepoHeader({
  repository,
  branches,
  refState,
}: {
  repository: string;
  branches: GitHubBranchList | null;
  refState: [string, (v: string) => void];
}) {
  const current = branches?.branches.find(b => b.name === refState[0]);
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="font-bold text-cyan-300 font-mono">{repository}</span>
      {branches && branches.branches.length > 0 && (
        <select
          value={refState[0]}
          onChange={e => refState[1](e.target.value)}
          className="bg-gray-800/70 border border-gray-700 rounded-lg px-2 py-1 text-xs text-gray-200 font-mono focus:outline-none"
        >
          {branches.branches.map(b => (
            <option key={b.name} value={b.name}>⎇ {b.name}</option>
          ))}
        </select>
      )}
      {current?.protected && (
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 border border-red-500/30 text-red-300">
          protected
        </span>
      )}
    </div>
  );
}

function Breadcrumbs({
  repository,
  dir,
  onNavigate,
}: {
  repository: string;
  dir: string;
  onNavigate: (dir: string) => void;
}) {
  const parts = dir ? dir.split('/') : [];
  return (
    <div className="flex items-center gap-1 flex-wrap text-xs font-mono">
      <button type="button" className="text-cyan-400 hover:underline" onClick={() => onNavigate('')}>
        {repository}
      </button>
      {parts.map((p, i) => (
        <span key={p + i} className="flex items-center gap-1">
          <span className="text-gray-600">/</span>
          <button
            type="button"
            className="text-cyan-400 hover:underline"
            onClick={() => onNavigate(parts.slice(0, i + 1).join('/'))}
          >
            {p}
          </button>
        </span>
      ))}
    </div>
  );
}

// ============================ Создание ветки (WRITE + подтверждение) ============================

function CreateBranchBar({
  repository,
  branches,
  onDone,
  setNotice,
}: {
  repository: string;
  branches: GitHubBranchList | null;
  onDone: () => void;
  setNotice: (n: Notice) => void;
}) {
  const [name, setName] = useState('');
  const [source, setSource] = useState('');
  const [busy, setBusy] = useState(false);
  const [pendingCid, setPendingCid] = useState<string | null>(null);

  useEffect(() => {
    if (!source && branches && branches.branches.length > 0) setSource(branches.branches[0].name);
  }, [branches, source]);

  const shaOf = (branch: string) => branches?.branches.find(b => b.name === branch)?.sha || '';

  const params = () => ({ repository, branch: name.trim(), sha: shaOf(source) });

  const request = async () => {
    if (!name.trim()) {
      setNotice({ kind: 'err', text: 'укажите имя ветки' });
      return;
    }
    if (!shaOf(source)) {
      setNotice({ kind: 'err', text: 'не найден SHA исходной ветки' });
      return;
    }
    setBusy(true);
    const r = await execCapability<{ branch: string; sha: string }>('github.create_branch', params());
    setBusy(false);
    if (r.status === 'confirmation_required') {
      setPendingCid(r.confirmation.id);
    } else if (r.status === 'done') {
      setNotice({ kind: 'ok', text: `ветка ${r.result.branch} создана` });
      setName('');
      onDone();
    } else if (r.status === 'error') {
      setNotice({ kind: 'err', text: r.error });
    }
  };

  const approve = async () => {
    if (!pendingCid) return;
    setBusy(true);
    const r = await execCapability<{ branch: string; sha: string }>(
      'github.create_branch',
      params(),
      pendingCid,
    );
    setBusy(false);
    setPendingCid(null);
    if (r.status === 'done') {
      setNotice({ kind: 'ok', text: `ветка ${r.result.branch} создана (подтверждено)` });
      setName('');
      onDone();
    } else if (r.status === 'error') {
      setNotice({ kind: 'err', text: r.error });
    }
  };

  const reject = async () => {
    if (!pendingCid) return;
    setBusy(true);
    const okRej = await decideConfirmation(pendingCid, false);
    setBusy(false);
    setPendingCid(null);
    setNotice(okRej
      ? { kind: 'ok', text: 'создание ветки отклонено' }
      : { kind: 'err', text: 'не удалось отклонить подтверждение' });
  };

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-800/30 p-3 space-y-2">
      <div className="flex gap-2 items-center flex-wrap">
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="feature/новая-ветка"
          className="flex-1 min-w-[180px] bg-gray-800/70 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-gray-200 font-mono focus:border-cyan-500/70 focus:outline-none"
        />
        {branches && branches.branches.length > 0 && (
          <select
            value={source}
            onChange={e => setSource(e.target.value)}
            className="bg-gray-800/70 border border-gray-700 rounded-lg px-2 py-1.5 text-xs text-gray-200 font-mono focus:outline-none"
          >
            {branches.branches.map(b => (
              <option key={b.name} value={b.name}>от {b.name}</option>
            ))}
          </select>
        )}
        <button
          type="button"
          onClick={request}
          disabled={busy}
          className="px-3 py-1.5 rounded-lg text-xs font-bold bg-yellow-500/15 border border-yellow-500/40 text-yellow-300 hover:bg-yellow-500/25 disabled:opacity-40"
        >
          Создать ветку (WRITE)
        </button>
      </div>
      {pendingCid && (
        <div className="rounded-lg border border-yellow-500/50 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-200 flex items-center justify-between gap-2 flex-wrap">
          <span>
            ⚠ WRITE-операция требует подтверждения: <span className="font-mono">{name.trim()}</span> от {source}
          </span>
          <span className="flex gap-2 shrink-0">
            <button
              type="button"
              onClick={approve}
              disabled={busy}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-yellow-500/20 border border-yellow-500/50 text-yellow-200 hover:bg-yellow-500/30 disabled:opacity-40"
            >
              Подтвердить
            </button>
            <button
              type="button"
              onClick={reject}
              disabled={busy}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-gray-700/60 border border-gray-600 text-gray-300 hover:bg-gray-700 disabled:opacity-40"
            >
              Отклонить
            </button>
          </span>
        </div>
      )}
    </div>
  );
}
