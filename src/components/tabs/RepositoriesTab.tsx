import { useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import type { LogEntry, PluginInfo,
  RepoBranches,
  RepoDiff,
  RepoFileContent,
  RepoRemote,
  RepoLog,
  RepoStatus,
  RepoSyncResult,
  SimpleGitResult,
} from '../../types';
import { nowStr, withFixHint } from '../../utils/logHelpers';
import {
  execCapability,
  putRepoSettings,
  reposAdd,
  reposBranches,
  reposCheckout,
  reposCommit,
  reposDiff,
  reposFetch,
  reposLog,
  reposPull,
  reposPush,
  reposReadFile,
  reposRemote,
  reposStatus,
  reposSync,
  REPOS_PLUGIN_ID,
} from '../../services/repos';

type Section = 'overview' | 'history' | 'branches' | 'changes';
type Notice = { kind: 'ok' | 'err' | 'warn'; text: string } | null;

interface RepositoriesTabProps {
  plugins: PluginInfo[];
  refresh: () => Promise<void>;
  setActiveTab: (t: 'plugins') => void;
  addLog: (entry: LogEntry) => void;
}

const PATH_STORAGE_KEY = 'drmAIcu.repos.defaultPath';

// STICKY ERRORS: ошибка сохраняется в sessionStorage — страница её дёргает
// перерисовками/перезагрузками, но текст ошибки остаётся видимым, пока
// пользователь не закроет его сам или пока новое действие не покажет результат.
const NOTICE_KEY = 'drmAIcu.repos.notice';

function loadStickyNotice(): Notice {
  try {
    const raw = sessionStorage.getItem(NOTICE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && (parsed.kind === 'ok' || parsed.kind === 'err' || parsed.kind === 'warn') && typeof parsed.text === 'string') {
        return parsed;
      }
    }
  } catch { /* повреждённые данные игнорируем */ }
  return null;
}

function storeNotice(n: Notice) {
  try {
    if (n) sessionStorage.setItem(NOTICE_KEY, JSON.stringify(n));
    else sessionStorage.removeItem(NOTICE_KEY);
  } catch { /* домашний режим без sessionStorage — просто не сохраняем */ }
}

export default function RepositoriesTab({ plugins, refresh, setActiveTab, addLog }: RepositoriesTabProps) {
  const [section, setSection] = useState<Section>('overview');
  const [notice, setNoticeState] = useState<Notice>(() => loadStickyNotice());
  // Липкое уведомление: каждая установка <state> и снятие синхронно пишутся в
  // sessionStorage — ошибка не пропадает ни при перерисовке, ни при перезагрузке.
  const setNotice = useCallback((n: Notice) => {
    setNoticeState(n);
    storeNotice(n);
  }, []);
  // Ошибки не должны «мигать и исчезать»: любая ошибка вкладки (включая ошибки
  // синхронизации) остаётся в липкой плашке, дополучает путь исправления
  // (withFixHint) и пишется во вкладку «Логи» (addLog → POST /api/logs).
  const setNoticeLogged = useCallback((n: Notice) => {
    if (n && n.kind === 'err') {
      const msg = withFixHint(n.text);
      setNotice({ kind: 'err', text: msg });
      addLog({ time: nowStr(), level: 'error', message: msg, source: 'Репозитории' });
      return;
    }
    setNotice(n);
  }, [addLog, setNotice]);
  const [pathInput, setPathInput] = useState<string>(() => localStorage.getItem(PATH_STORAGE_KEY) || '');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const repoPath = pathInput.trim().replace(/\/+$/, '');

  const rp = plugins.find(p => p.id === REPOS_PLUGIN_ID);
  const running = rp?.status === 'running';

  const [status, setStatus] = useState<RepoStatus | null>(null);

  const openRepo = useCallback(async (p: string, opts?: { silent?: boolean }) => {
    // silent: обновить только статус, НЕ трогая плашку — иначе перезагрузка статуса
    // после синхронизации мгновенно затирала только что показанную ошибку.
    const silent = opts?.silent === true;
    const clean = p.trim().replace(/\/+$/, '');
    if (!clean) { if (!silent) setNoticeLogged({ kind: 'err', text: 'укажите путь к репозиторию' }); return; }
    const r = await reposStatus(clean);
    if (r.status === 'done' && r.result.ok) {
      localStorage.setItem(PATH_STORAGE_KEY, clean);
      setStatus(r.result);
      if (!silent) setNoticeLogged({ kind: 'ok', text: `репозиторий открыт: ${clean} (ветка ${r.result.branch || '—'})` });
    } else {
      setStatus(null);
      // Честная ошибка: если git вернул сбой (result.ok=false), показываем его stderr,
      // а не заготовленный текст про неожиданный ответ gateway.
      let err: string;
      if (r.status === 'error') {
        err = r.error;
      } else if (r.status === 'confirmation_required') {
        err = 'статус запросил подтверждение WRITE — проверьте разрешения плагина repos (READ должен быть auto)';
      } else if (r.status === 'done' && !r.result.ok && (r.result as { error?: string }).error) {
        err = `git status завершился с ошибкой: ${(r.result as { error?: string }).error}`;
      } else {
        err = 'не удалось открыть репозиторий — путь должен существовать и содержать каталог .git';
      }
      if (!silent) setNoticeLogged({ kind: 'err', text: err });
    }
  }, [setNoticeLogged]);

  useEffect(() => {
    if (running && repoPath) openRepo(repoPath);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  // Тихая перезагрузка статуса после операций: плашку с результатом не затираем.
  const reload = useCallback(() => { void openRepo(repoPath, { silent: true }); }, [openRepo, repoPath]);

  if (!running) return <PluginGate rp={rp} setActiveTab={setActiveTab} />;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-2xl font-bold">📁 Репозитории</h2>
        <div className="flex items-center gap-2 flex-wrap">
          <SectionButton active={section === 'overview'} onClick={() => setSection('overview')}>Обзор</SectionButton>
          <SectionButton active={section === 'history'} onClick={() => setSection('history')}>История</SectionButton>
          <SectionButton active={section === 'branches'} onClick={() => setSection('branches')}>Ветки</SectionButton>
          <SectionButton
            active={section === 'changes'}
            alert={(status?.entries.length ?? 0) > 0}
            onClick={() => setSection('changes')}
          >
            Изменения{status && status.entries.length > 0 ? ` (${status.entries.length})` : ''}
          </SectionButton>
          <SectionButton active={false} onClick={() => setSettingsOpen(true)}>⚙ Настройки</SectionButton>
        </div>
      </div>

      {notice && (
        <div
          className={`px-4 py-2.5 rounded-lg border text-sm cursor-pointer ${
            notice.kind === 'ok'
              ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
              : notice.kind === 'warn'
              ? 'bg-amber-500/10 border-amber-500/40 text-amber-300'
              : 'bg-red-500/10 border-red-500/40 text-red-300'
          }`}
          onClick={() => { setNoticeState(null); storeNotice(null); }}
        >
          {notice.text}
        </div>
      )}

      <RepoPathBar repoPath={repoPath} hasStatus={!!status} onOpenSettings={() => setSettingsOpen(true)} />

      {!status ? (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-sm text-gray-400">
          Откройте локальный репозиторий: укажите полный путь к папке с <span className="font-mono text-gray-300">.git</span> и нажмите «Открыть».
        </div>
      ) : section === 'overview' ? (
        <OverviewSection status={status} repoPath={repoPath} setNotice={setNoticeLogged} reload={reload} />
      ) : section === 'history' ? (
        <HistorySection repoPath={repoPath} />
      ) : section === 'branches' ? (
        <BranchesSection repoPath={repoPath} status={status} setNotice={setNoticeLogged} reload={reload} />
      ) : (
        <ChangesSection repoPath={repoPath} status={status} setNotice={setNoticeLogged} reload={reload} />
      )}

      {settingsOpen && (
        <SettingsModal
          pathInput={pathInput}
          setPathInput={setPathInput}
          onOpen={openRepo}
          onClose={() => setSettingsOpen(false)}
        />
      )}
    </div>
  );
}

// Тонкая строка пути: только сам путь (клик открывает модальное окно настроек).
// Ветка/↑↓/счётчики перенесены: ветка и ahead/behind — в карточке «Текущий проект»
// (RepoInfoCard), счётчик изменений — на кнопке «Изменения». Дубли в правой части
// path bar убраны по запросу пользователя.
function RepoPathBar({ repoPath, hasStatus, onOpenSettings }: { repoPath: string; hasStatus: boolean; onOpenSettings: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpenSettings}
      className="w-full rounded-xl border border-gray-800 bg-gray-900/50 p-3 flex items-center gap-3 text-left hover:border-gray-600"
      title="Открыть настройки репозитория"
    >
      <span className="text-base leading-none">⚙</span>
      <span className="flex-1 font-mono text-sm text-gray-300 truncate">{repoPath || <span className="text-gray-500">путь не задан — откройте ⚙ Настройки</span>}</span>
      <span className="text-xs text-gray-500 shrink-0">{hasStatus ? 'открыт' : 'задать путь'}</span>
    </button>
  );
}

// Модальное окно настроек: ввод пути + «Открыть» + «Запомнить по умолчанию».
// Открывается кнопкой «⚙ Настройки» в ряду секций (после «Изменения»).
function SettingsModal({
  pathInput, setPathInput, onOpen, onClose,
}: {
  pathInput: string;
  setPathInput: (v: string) => void;
  onOpen: (p: string) => Promise<void>;
  onClose: () => void;
}) {
  const saveDefault = async () => {
    const r = await putRepoSettings({ default_path: pathInput.trim() });
    if (r.ok) localStorage.setItem(PATH_STORAGE_KEY, pathInput.trim());
  };
  const openAndClose = async () => { await onOpen(pathInput.trim().replace(/\/+$/, '')); onClose(); };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div
        className="w-full max-w-xl rounded-xl border border-gray-700 bg-gray-900 shadow-2xl p-5 space-y-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-bold text-white">⚙ Настройки репозитория</h3>
          <button onClick={onClose} className="px-2 py-1 rounded-lg text-sm border border-gray-700 text-gray-400 hover:border-gray-500">✕</button>
        </div>
        <div className="space-y-2">
          <label className="block text-xs text-gray-400">
            Путь к локальному репозиторию — полный путь к папке, содержащей <span className="font-mono text-gray-300">.git</span>
          </label>
          <input
            autoFocus
            value={pathInput}
            onChange={e => setPathInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') void openAndClose(); }}
            placeholder="C:\\projects\\drmAIcu"
            className="w-full bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono text-gray-200 outline-none focus:border-cyan-500/60"
          />
          <p className="text-xs text-gray-500">
            Если git отвечает «не является репозиторием» или «dubious ownership» — проверьте наличие папки .git
            и права: <span className="font-mono text-gray-400">git config --global --add safe.directory &lt;путь&gt;</span>
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => void openAndClose()}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-cyan-500/15 border border-cyan-400/70 text-cyan-300 hover:bg-cyan-500/25"
          >
            Открыть
          </button>
          <button
            onClick={saveDefault}
            className="px-3 py-2 rounded-lg text-xs border border-gray-700 text-gray-300 hover:border-gray-500"
          >
            Запомнить по умолчанию
          </button>
          <button
            onClick={onClose}
            className="px-3 py-2 rounded-lg text-xs border border-gray-700 text-gray-400 hover:border-gray-500"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}

// ==== Обзор: Sync (замена sync.bat) + удалённые репозитории + просмотр файла ====

function OverviewSection({
  status, repoPath, setNotice, reload,
}: {
  status: RepoStatus;
  repoPath: string;
  setNotice: (n: Notice) => void;
  reload: () => void;
}) {
  const [commitMsg, setCommitMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<{ label: string; cid: string; run: (token: string) => void } | null>(null);
  const [syncResult, setSyncResult] = useState<RepoSyncResult | null>(null);
  const [fileRel, setFileRel] = useState('');
  const [fileView, setFileView] = useState<RepoFileContent | null>(null);

  const runSync = async (token?: string) => {
    setBusy(true);
    const r = await reposSync(repoPath, commitMsg, status.snapshot, token);
    setBusy(false);
    if (r.status === 'confirmation_required' && r.confirmation) {
      const cid = r.confirmation.id;
      setPending({
        label: `Синхронизировать ${repoPath}: ${status.snapshot_files.length} файл(ов) — ${status.snapshot_files.slice(0, 8).join(', ')}${status.snapshot_files.length > 8 ? ` и ещё ${status.snapshot_files.length - 8}` : ''}. add -A → commit → pull --rebase → push`,
        cid,
        run: t => runSync(t),
      });
      return;
    }
    if (r.status === 'done') {
      setSyncResult(r.result);
      if (r.result.ok) {
        setNotice({ kind: 'ok', text: r.result.committed
          ? `синхронизировано: commit ${r.result.commit_sha || ''} доведён до ${r.result.head}`
          : `синхронизировано без нового коммита, HEAD: ${r.result.head}` });
      } else {
        setNotice({ kind: 'err', text: r.result.error || 'синхронизация не завершена' });
      }
      reload();
    } else if (r.status === 'error') {
      setNotice({ kind: 'err', text: r.error });
    }
  };

  const runWrite = async (label: string, call: (token?: string) => ReturnType<typeof reposFetch>, token?: string) => {
    setBusy(true);
    const r = await call(token);
    setBusy(false);
    if (r.status === 'confirmation_required' && r.confirmation) {
      setPending({
        label: `${label} ${repoPath} (WRITE — подтвердите)`,
        cid: r.confirmation.id,
        run: t => { void runWrite(label, call, t); },
      });
      return;
    }
    if (r.status === 'done') {
      const res = r.result as SimpleGitResult;
      if (res.ok) setNotice({ kind: 'ok', text: `${label}: OK${res.output ? ' — ' + res.output.split('\\n')[0] : ''}` });
      else setNotice({ kind: 'err', text: res.error || `${label}: ошибка` });
      reload();
    } else if (r.status === 'error') {
      setNotice({ kind: 'err', text: r.error });
    } else {
      setNotice({ kind: 'err', text: `${label}: сервер вернул неожиданный статус` });
    }
  };

  const viewFile = async () => {
    setBusy(true);
    const r = await reposReadFile(repoPath, fileRel);
    setBusy(false);
    if (r.status === 'done') {
      setFileView(r.result.ok ? r.result : null);
      if (!r.result.ok) setNotice({ kind: 'err', text: r.result.error || 'файл не прочитан' });
    } else if (r.status === 'error') setNotice({ kind: 'err', text: r.error });
  };

  return (
    <div className="space-y-4">
      {pending && <ConfirmationBar pending={pending} busy={busy} clear={() => setPending(null)} />}

      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-3">
        <h3 className="font-bold text-white">🔄 Синхронизация (замена sync.bat)</h3>
        <div className="flex items-center gap-2">
          <input
            value={commitMsg}
            onChange={e => setCommitMsg(e.target.value)}
            placeholder="Сообщение коммита (если есть изменения — обязательно, как в sync.bat)"
            className="flex-1 bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 outline-none focus:border-cyan-500/60"
          />
          <button
            disabled={busy}
            onClick={() => runSync()}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-emerald-500/15 border border-emerald-400/70 text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-40"
          >
            Синхронизировать
          </button>
        </div>
        <p className="text-xs text-gray-500">
          add -A → commit (если есть изменения) → pull --rebase → push → проверка merged PR. Одно подтверждение WRITE на весь пакет.
        </p>
        {syncResult && (
          <div className="rounded-lg bg-gray-800/60 border border-gray-700 p-3 text-xs font-mono space-y-1">
            {syncResult.steps.map((s, i) => (
              <div key={i}>
                <span className={s.ok === false ? 'text-red-400' : 'text-emerald-400'}>{s.ok === false ? '✗' : '✓'}</span>{' '}
                <span className="text-gray-300">{s.step}</span>
                {s.branch ? <> · <span className="text-cyan-300">{s.branch}</span></> : null}
                {s.sha ? <> · <span className="text-cyan-300">{s.sha}</span></> : null}
                {s.note ? <> · <span className="text-gray-500">{s.note}</span></> : null}
                {s.last_merged !== undefined && s.last_merged !== null ? <> · <span className="text-gray-400">{s.last_merged}</span></> : null}
                {s.error ? <> · <span className="text-red-400">{s.error}</span></> : null}
              </div>
            ))}
            {syncResult.head && <div className="text-gray-400">HEAD: {syncResult.head}</div>}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-3">
        <h3 className="font-bold text-white">🛠 Отдельные операции (каждая с подтверждением WRITE)</h3>
        <div className="flex items-center gap-2 flex-wrap">
          <OpBtn busy={busy} label="fetch" onClick={() => runWrite('fetch', t => reposFetch(repoPath, t))} />
          <OpBtn busy={busy} label="pull --rebase" onClick={() => runWrite('pull --rebase', t => reposPull(repoPath, true, t))} />
          <OpBtn busy={busy} label="push" onClick={() => runWrite('push', t => reposPush(repoPath, t))} disabled={!status.changed && !status.ahead} />
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-3">
        <h3 className="font-bold text-white">📄 Просмотр файла</h3>
        <div className="flex items-center gap-2">
          <input
            value={fileRel}
            onChange={e => setFileRel(e.target.value)}
            placeholder="src/App.tsx — путь внутри репозитория"
            className="flex-1 bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono text-gray-200 outline-none focus:border-cyan-500/60"
          />
          <button onClick={viewFile} className="px-4 py-2 rounded-lg text-sm font-semibold bg-gray-800 border border-gray-700 text-gray-300 hover:border-gray-500">
            Прочитать
          </button>
        </div>
        {fileView && (
          <pre className="max-h-96 overflow-auto rounded-lg bg-gray-950 border border-gray-800 p-3 text-xs text-gray-300 whitespace-pre-wrap">{fileView.content}</pre>
        )}
      </div>
    </div>
  );
}

// Время коммита в HH:MM UTC+3: git отдаёт ISO-дату со смещением (%aI), честно
// конвертируем её в фиксированную зону Europe/Moscow (= UTC+3, без перевода часов).
function timeUtc3(dateIso: string): string {
  const d = new Date(dateIso);
  if (isNaN(d.getTime())) return '--:--';
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Europe/Moscow', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(d);
}

function HistorySection({ repoPath }: { repoPath: string }) {
  const [log, setLog] = useState<RepoLog | null>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    let alive = true;
    (async () => {
      const r = await reposLog(repoPath, 50);
      if (!alive) return;
      if (r.status === 'done' && r.result.ok) setLog(r.result);
      else setErr(r.status === 'error' ? r.error : 'git log failed');
    })();
    return () => { alive = false; };
  }, [repoPath]);

  if (err) return <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">{err}</div>;
  if (!log) return <div className="text-sm text-gray-500">загрузка истории…</div>;
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-1.5">
      {log.commits.map(c => (
        <div key={c.sha} className="flex items-center gap-3 text-sm">
          <span className="font-mono text-cyan-300 text-xs">{c.sha}</span>
          <span className="text-gray-300 flex-1 truncate">{c.subject}</span>
          <span className="text-gray-500 text-xs">{c.author} · {c.date.slice(0, 10)} · {timeUtc3(c.date)} UTC+3</span>
        </div>
      ))}
      {log.commits.length === 0 && <p className="text-sm text-gray-500">коммитов нет (репозиторий пуст)</p>}
    </div>
  );
}

// ==== карточка текущего проекта: с каким репозиторием сейчас работаем ====

function RepoInfoCard({ repoPath, status }: { repoPath: string; status: RepoStatus | null }) {
  const [remote, setRemote] = useState<RepoRemote | null>(null);
  useEffect(() => {
    let alive = true;
    (async () => {
      const r = await reposRemote(repoPath);
      if (alive && r.status === 'done' && r.result.ok) setRemote(r.result);
    })();
    return () => { alive = false; };
  }, [repoPath]);

  return (
    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4 space-y-1.5 text-sm">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Текущий проект</span>
        <span className="font-mono text-gray-200 break-all">{repoPath || '—'}</span>
        {status && <span className="px-2 py-0.5 rounded bg-gray-800 border border-gray-700 text-cyan-300 text-xs font-mono">{status.branch || '—'}</span>}
        {status && status.upstream && <span className="text-xs text-gray-400 font-mono">→ {status.upstream}</span>}
        {status && status.ahead > 0 && <span className="text-emerald-400 text-xs">↑{status.ahead} не запушено</span>}
        {status && status.behind > 0 && <span className="text-amber-400 text-xs">↓{status.behind} не получено</span>}
      </div>
      {remote && remote.remotes.length > 0 ? (
        <div className="text-xs text-gray-400 space-y-0.5">
          {remote.remotes.map(rm => (
            <div key={rm.name} className="break-all"><span className="font-mono text-gray-300">{rm.name}:</span> <span className="font-mono">{rm.url}</span></div>
          ))}
        </div>
      ) : (
        <div className="text-xs text-amber-400">
          Удалённые репозитории не настроены («git remote -v» пуст) — push будет невозможен. Путь исправления: в консоли репозитория выполните <span className="font-mono">git remote add origin &lt;URL&gt;</span> и нажмите «Обновить».
        </div>
      )}
      <div className="text-xs text-gray-500">Все разделы — История, Ветки, Изменения — показывают файлы и коммиты именно этого репозитория.</div>
    </div>
  );
}

function BranchesSection({
  repoPath, status, setNotice, reload,
}: { repoPath: string; status: RepoStatus | null; setNotice: (n: Notice) => void; reload: () => void }) {
  const [branches, setBranches] = useState<RepoBranches | null>(null);
  const [newBranch, setNewBranch] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const r = await reposBranches(repoPath);
    if (r.status === 'done' && r.result.ok) setBranches(r.result);
    else setNotice({ kind: 'err', text: r.status === 'error' ? r.error : 'git branch failed' });
    void reload;
  }, [repoPath, setNotice, reload]);

  useEffect(() => { load(); }, [load]);

  const [pending, setPending] = useState<{ label: string; cid: string; run: (token: string) => void } | null>(null);

  const doCheckout = async (branch: string, create: boolean, token?: string) => {
    setBusy(true);
    const r = await reposCheckout(repoPath, branch, create, token);
    setBusy(false);
    if (r.status === 'confirmation_required' && r.confirmation) {
      setPending({
        label: `${create ? 'Создать и переключиться на' : 'Переключиться на'} ветку ${branch} в ${repoPath}`,
        cid: r.confirmation.id,
        run: t => { void doCheckout(branch, create, t); },
      });
      return;
    }
    if (r.status === 'done' && r.result.ok) {
      setNotice({ kind: 'ok', text: `ветка ${create ? 'создана и активирована' : 'активирована'}: ${branch}` });
    } else if (r.status === 'done') {
      setNotice({ kind: 'err', text: r.result.error || 'checkout не выполнен' });
    } else if (r.status === 'error') {
      setNotice({ kind: 'err', text: r.error });
    } else {
      setNotice({ kind: 'err', text: 'checkout не выполнен: неожиданный статус ответа' });
    }
    load();
    reload();
  };

  return (
    <div className="space-y-4">
      {pending && <ConfirmationBar pending={pending} busy={busy} clear={() => setPending(null)} />}
      <RepoInfoCard repoPath={repoPath} status={status} />
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-3">
        <h3 className="font-bold text-white">🌿 Ветки</h3>
      <div className="flex items-center gap-2">
        <input
          value={newBranch}
          onChange={e => setNewBranch(e.target.value)}
          placeholder="имя новой ветки"
          className="flex-1 bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono text-gray-200 outline-none focus:border-cyan-500/60"
        />
        <button
          disabled={busy || !newBranch.trim()}
          onClick={() => doCheckout(newBranch.trim(), true)}
          className="px-4 py-2 rounded-lg text-sm font-semibold bg-cyan-500/15 border border-cyan-400/70 text-cyan-300 hover:bg-cyan-500/25 disabled:opacity-40"
        >
          Создать
        </button>
      </div>
      {branches ? (
        <div className="space-y-1">
          {branches.branches.map(b => (
            <div key={b.name} className="flex items-center gap-3 text-sm">
              <span className={`font-mono text-xs ${b.remote ? 'text-gray-500' : 'text-gray-300'}`}>{b.remote ? 'remotes/' : ''}{b.name}</span>
              {b.name === branches.current && <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-400/40">текущая</span>}
              {!b.remote && b.name !== branches.current && (
                <button onClick={() => doCheckout(b.name, false)} className="text-xs px-2 py-0.5 rounded border border-gray-700 text-gray-400 hover:border-gray-500">
                  Переключиться
                </button>
              )}
              {!b.remote && <span className="font-mono text-[10px] text-gray-600">{b.sha}</span>}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-500">загрузка…</p>
      )}
      </div>
    </div>
  );
}

function ChangesSection({
  repoPath, status, setNotice, reload,
}: { repoPath: string; status: RepoStatus | null; setNotice: (n: Notice) => void; reload: () => void }) {
  const [stagedDiff, setStagedDiff] = useState<RepoDiff | null>(null);
  const [unstagedDiff, setUnstagedDiff] = useState<RepoDiff | null>(null);
  const [commitMsg, setCommitMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<{ label: string; cid: string; run: (token: string) => void } | null>(null);

  const load = useCallback(async () => {
    const [st, un] = await Promise.all([reposDiff(repoPath, true), reposDiff(repoPath, false)]);
    if (st.status === 'done' && st.result.ok) setStagedDiff(st.result);
    if (un.status === 'done' && un.result.ok) setUnstagedDiff(un.result);
  }, [repoPath]);

  useEffect(() => { load(); }, [load]);

  // Обновить список файлов и диффы + общий статус (сомнений в том, откуда данные, не остётся).
  const refresh = useCallback(() => { load(); reload(); }, [load, reload]);

  const write = async (label: string, call: (token?: string) => ReturnType<typeof reposAdd>, token?: string) => {
    setBusy(true);
    const r = await call(token);
    setBusy(false);
    if (r.status === 'confirmation_required' && r.confirmation) {
      setPending({
        label: `${label} ${repoPath} (WRITE — подтвердите)`,
        cid: r.confirmation.id,
        run: t => { void write(label, call, t); },
      });
      return;
    }
    if (r.status === 'done') {
      const res = r.result as SimpleGitResult;
      if (res.ok) setNotice({ kind: 'ok', text: `${label}: OK${res.sha ? ' (' + res.sha + ')' : ''}` });
      else setNotice({ kind: 'err', text: res.error || `${label}: ошибка` });
    } else if (r.status === 'error') setNotice({ kind: 'err', text: r.error });
    else setNotice({ kind: 'err', text: `${label}: сервер вернул неожиданный статус` });
    load();
    reload();
  };

  return (
    <div className="space-y-4">
      {pending && <ConfirmationBar pending={pending} busy={busy} clear={() => setPending(null)} />}

      <RepoInfoCard repoPath={repoPath} status={status} />

      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-3">
        <h3 className="font-bold text-white">✏️ Коммит (по шагам)</h3>
        <div className="flex items-center gap-2">
          <input
            value={commitMsg}
            onChange={e => setCommitMsg(e.target.value)}
            placeholder="Сообщение коммита (пустое отклоняется)"
            className="flex-1 bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 outline-none focus:border-cyan-500/60"
          />
          <OpBtn busy={busy} label="git add -A" onClick={() => write('git add -A', t => reposAdd(repoPath, t))} />
          <OpBtn busy={busy} label="commit" onClick={() => write('commit', t => reposCommit(repoPath, commitMsg, t))} />
          <OpBtn busy={busy} label="push" onClick={() => write('push', t => reposPush(repoPath, t))} />
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-white text-sm">Файлы с изменениями в этом репозитории ({status?.entries.length ?? 0})</h3>
          <button
            onClick={refresh}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-gray-800 border border-gray-700 text-gray-200 hover:border-gray-500"
          >
            ↻ Обновить
          </button>
        </div>
        {status && status.entries.length > 0 ? (
          <div className="space-y-1">
            {status.entries.map(e => (
              <div key={e.file} className="flex items-center gap-2 text-sm">
                <span
                  className={`font-mono text-[10px] px-1.5 py-0.5 rounded border ${
                    e.code.includes('D')
                      ? 'bg-red-500/10 border-red-400/40 text-red-300'
                      : e.code === '??'
                      ? 'bg-emerald-500/10 border-emerald-400/40 text-emerald-300'
                      : 'bg-amber-500/10 border-amber-400/40 text-amber-300'
                  }`}
                  title={e.code === '??' ? 'новый файл' : e.code.includes('D') ? 'удалён' : 'изменён'}
                >{e.code.trim() || '—'}</span>
                <span className="font-mono text-gray-300 flex-1 truncate" title={e.file}>{e.file}</span>
                {e.staged && <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/10 border border-cyan-400/30 text-cyan-300">staged</span>}
                {e.unstaged && <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-400">unstaged</span>}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-500">изменений нет — рабочее дерево чистое (если изменения есть в другой папке — откройте её в поле пути выше и нажмите «Открыть»)</p>
        )}
      </div>

      <DiffCard title="staged (--cached)" diff={stagedDiff} />
      <DiffCard title="unstaged" diff={unstagedDiff} />
    </div>
  );
}

function DiffCard({ title, diff }: { title: string; diff: RepoDiff | null }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-2">
      <h3 className="font-bold text-white text-sm">{title}</h3>
      {diff && diff.stat ? (
        <pre className="max-h-72 overflow-auto rounded-lg bg-gray-950 border border-gray-800 p-3 text-xs text-gray-300 whitespace-pre-wrap">{diff.stat}</pre>
      ) : (
        <p className="text-xs text-gray-500">пусто</p>
      )}
    </div>
  );
}

// ==== общий появляющийся бар подтверждения WRITE ====

function ConfirmationBar({
  pending, busy, clear,
}: {
  pending: { label: string; cid: string; run: (token: string) => void };
  busy: boolean;
  clear: () => void;
}) {
  return (
    <div className="rounded-xl border border-amber-500/50 bg-amber-500/10 p-4 space-y-3">
      <p className="text-sm text-amber-200 font-semibold">⚠️ Требуется подтверждение WRITE</p>
      <p className="text-sm text-amber-100">{pending.label}</p>
      <div className="flex items-center gap-2">
        <button
          disabled={busy}
          onClick={() => { const { run, cid } = pending; clear(); run(cid); }}
          className="px-4 py-2 rounded-lg text-sm font-semibold bg-emerald-500/15 border border-emerald-400/70 text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-40"
        >
          Подтвердить
        </button>
        <button onClick={clear} className="px-4 py-2 rounded-lg text-sm border border-gray-700 text-gray-300 hover:border-gray-500">
          Отмена
        </button>
      </div>
    </div>
  );
}

function OpBtn({ busy, label, onClick, disabled }: { busy: boolean; label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      disabled={busy || disabled}
      onClick={onClick}
      className="px-3 py-2 rounded-lg text-sm font-semibold bg-gray-800 border border-gray-700 text-gray-200 hover:border-gray-500 disabled:opacity-40"
    >
      {label}
    </button>
  );
}

function SectionButton({ active, alert, onClick, children }: { active: boolean; alert?: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
        active
          ? 'bg-cyan-500/15 border-cyan-400/70 text-cyan-300'
          : alert
          ? 'bg-amber-500/15 border-amber-400/70 text-amber-300 hover:bg-amber-500/25'
          : 'bg-gray-800/50 border-gray-700/60 text-gray-300 hover:border-gray-600'
      }`}
    >
      {children}
    </button>
  );
}

function PluginGate({
  rp,
  setActiveTab,
}: {
  rp: PluginInfo | undefined;
  setActiveTab: (t: 'plugins') => void;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 space-y-3">
      <h3 className="font-bold text-white">Плагин «Репозитории» не активен</h3>
      {rp ? (
        <p className="text-sm text-gray-400">
          Статус плагина: <span className="font-mono">{rp.status}</span>
          {rp.last_error ? <> · ошибка: <span className="text-red-400 font-mono">{rp.last_error}</span></> : null}
        </p>
      ) : (
        <p className="text-sm text-gray-400">
          Плагин <span className="font-mono">repos</span> не установлен. Он доступен во встроенном каталоге плагинов.
        </p>
      )}
      <button
        type="button"
        onClick={() => setActiveTab('plugins')}
        className="px-4 py-2 rounded-lg text-sm font-semibold bg-cyan-500/15 border border-cyan-400/70 text-cyan-300 hover:bg-cyan-500/25"
      >
        🔌 Открыть «Плагины»
      </button>
    </div>
  );
}
