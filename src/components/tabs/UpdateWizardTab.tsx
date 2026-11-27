import { useCallback, useEffect, useState, useRef } from 'react';
import { cleanCommandOutput, updateStateLabel, hasNpmWarnings } from './updatePresentation';

type ApiResult = { success: boolean; error?: string; code?: string; plan?: any; journal?: any };

async function callUpdate(path: string, operationId?: string, manualConfirmation = false): Promise<ApiResult> {
  const response = await fetch(path, {
    method: path.endsWith('/state') ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    ...(operationId ? { body: JSON.stringify({ operation_id: operationId, manual_confirmation: manualConfirmation }) } : {}),
  });
  const data = await response.json().catch(() => ({ success: false, error: 'Сервер вернул некорректный ответ' }));
  if (!response.ok || !data.success) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

export default function UpdateWizardTab({ visible, incomingRequest, onBusyChange, onOpenRepositories }: { visible: boolean; incomingRequest: number; onBusyChange: (busy: boolean) => void; onOpenRepositories: () => void }) {
  const [journal, setJournal] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const [progress, setProgress] = useState<any>(null);
  const [activity, setActivity] = useState("");
  const [error, setError] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [copyStatus, setCopyStatus] = useState('');
  const running = useRef(false);
  const requestStarted = useRef(0);
  const consumedRequest = useRef(0);
  const restartId = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await callUpdate('/api/updates/state');
      setJournal(result.journal || null);
      setLoaded(true);
    } catch (e: any) {
      setError(e?.message || 'Не удалось получить состояние Update Manager');
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const r = await fetch('/api/updates/history');
      const data = await r.json();
      if (r.ok && Array.isArray(data.history)) setHistory(data.history);
    } catch { /* old server or restart; keep existing records */ }
  }, []);
  useEffect(() => { if (visible && !running.current && !restarting && incomingRequest === consumedRequest.current) { void refresh(); void refreshHistory(); } }, [visible, refresh, refreshHistory]);
  useEffect(() => { onBusyChange(busy || restarting); }, [busy, restarting, onBusyChange]);
  useEffect(() => {
    if (!busy && !restarting && !['APPLYING','RESTORING','PREPARING'].includes(journal?.state)) return;
    let active = true;
    const poll = async () => {
      try {
        const r = await fetch('/api/updates/progress');
        const data = await r.json();
        if (active && r.ok && data.progress?.id) {
          const snapshot = data.progress;
          const fresh = Date.parse(snapshot.updated_at || '') >= requestStarted.current - 1000;
          if (!busy || fresh) setProgress(snapshot);
          if (!busy && !restarting && snapshot.state && !['APPLYING','RESTORING','PREPARING'].includes(snapshot.state)) void refresh();
        }
      } catch { /* restart or old server */ }
    };
    void poll();
    const timer = window.setInterval(poll, 1200);
    return () => { active = false; window.clearInterval(timer); };
  }, [busy, restarting, journal?.state, refresh]);

  const run = async (path: string, operationId?: string, manualConfirmation = false) => {
    if (running.current || restarting) return;
    running.current = true;
    requestStarted.current = Date.now();
    setBusy(true);
    setProgress(null);
    setActivity(({incoming: 'Получение актуального плана GitHub (fetch)', check: 'Проверка Git', apply: 'Резервирование и обновление', prepare: 'Подготовка окружения', recover: 'Восстановление Git'} as Record<string,string>)[path.split('/').pop() || ''] || 'Выполнение операции');
    setError('');
    try {
      const result = await callUpdate(path, operationId, manualConfirmation);
      setJournal(result.plan || result.journal || null);
      setConfirmed(false);
      if (path.endsWith('/incoming') && result.journal?.state === 'RESTART_REQUIRED') {
        restartId.current = result.journal.id;
        await callUpdate('/api/updates/restart', result.journal.id);
        setRestarting(true);
      }
    } catch (e: any) {
      await refresh();
      setError(e?.message || 'Операция обновления завершилась ошибкой');
    } finally {
      running.current = false;
      setBusy(false);
      void refreshHistory();
    }
  };

  useEffect(() => {
    if (incomingRequest <= consumedRequest.current) return;
    consumedRequest.current = incomingRequest;
    if (!running.current && !restarting) void run('/api/updates/incoming');
  }, [incomingRequest]);

  const live = busy ? (progress?.id ? progress : null) : restarting ? (progress?.id ? progress : journal) : journal;
  const state = live?.state || 'IDLE';
  const canCheck = loaded && ['IDLE','CHECKED','COMPLETED','FAILED'].includes(state);
  const restart = async () => {
    if (running.current || restarting) return;
    restartId.current = journal?.id || null;
    setRestarting(true);
    setError('');
    try {
      await callUpdate('/api/updates/restart', journal?.id);
    } catch (e: any) {
      setError(e?.message || 'Не удалось запросить перезапуск');
      setRestarting(false);
    }
  };
  useEffect(() => {
    if (!restarting) return;
    let cancelled = false;
    const started = Date.now();
    let timer: number;
    const poll = async () => {
      try {
        const response = await fetch('/api/updates/state', {cache:'no-store', signal:AbortSignal.timeout(4000)});
        const data = await response.json();
        if (cancelled) return;
        if (response.ok && restartId.current && data.journal?.id === restartId.current && data.journal?.state === 'COMPLETED') {
          window.location.reload();
          return;
        }
      } catch { /* server restarting */ }
      if (cancelled) return;
      if (Date.now() - started > 90000) {
        setRestarting(false);
        setError('Перезапуск не подтверждён. Проверьте окно watchdog и обновите страницу.');
        return;
      }
      timer = window.setTimeout(poll, 1500);
    };
    timer = window.setTimeout(poll, 1500);
    return () => {cancelled = true; window.clearTimeout(timer);};
  }, [restarting]);
  const latestReport = journal?.state === 'COMPLETED' ? journal : history.find(item => item.state === 'COMPLETED');
  const upToDate = state === 'CHECKED' && journal?.ahead === 0 && journal?.behind === 0 && !(journal?.blockers || []).filter((x: string) => x !== 'Нет входящих коммитов для обновления.').length;
  const localOnly = state === 'CHECKED' && journal?.behind === 0 && (journal?.ahead > 0 || journal?.local_files?.length > 0);
  const canApply = state === 'CHECKED' && journal?.behind > 0 && !(journal?.blockers || []).length;
  const environmentRepair = state === 'UPDATE_NEEDS_REPAIR' && journal?.local_changes_restored === true;
  const canPrepare = state === 'CODE_UPDATED' || environmentRepair;
  const canRecover = !environmentRepair && ['APPLYING', 'RECOVERY_REQUIRED', 'UPDATE_NEEDS_REPAIR', 'RESTORING', 'PREPARING'].includes(state);
  const steps = [
    { number: 1, title: 'Проверка и план', done: ['CHECKED', 'APPLYING', 'CODE_UPDATED', 'RESTORING', 'PREPARING', 'RESTART_REQUIRED', 'COMPLETED', 'RECOVERY_REQUIRED', 'UPDATE_NEEDS_REPAIR'].includes(state) },
    { number: 2, title: 'Резервирование и обновление', done: ['CODE_UPDATED', 'RESTORING', 'PREPARING', 'RESTART_REQUIRED', 'COMPLETED', 'UPDATE_NEEDS_REPAIR'].includes(state) },
    { number: 3, title: 'Восстановление и окружение', done: ['RESTART_REQUIRED','COMPLETED'].includes(state) },
  ];

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-cyan-500/30 bg-gradient-to-br from-gray-900 to-gray-950 p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-white">🔄 Мастер обновления drmAIcu</h2>
            <p className="text-sm text-gray-400 mt-1">Ручной мастер или входящая синхронизация одним нажатием на зелёную иконку в шапке. При ошибке процесс останавливается.</p>
          </div>
          <span className={`text-xs px-3 py-1.5 rounded-full border ${state === 'COMPLETED' ? 'border-emerald-500/50 text-emerald-300 bg-emerald-500/10' : canRecover ? 'border-red-500/50 text-red-300 bg-red-500/10' : 'border-gray-700 text-gray-300 bg-gray-800'}`}>
            {localOnly ? 'Локальные изменения' : upToDate ? 'Актуальная версия' : updateStateLabel(state)}
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          <Metric label="Запущенная версия" value={journal?.running_version || journal?.restart_health?.version || '—'} />
          <Metric label="Установленная версия (Git)" value={journal?.installed_version || (journal?.new_head ? journal?.target_version : journal?.current_version) || '—'} />
          <Metric label="GitHub (последняя проверка)" value={journal?.target_version || '—'} />
        </div>
        <p className="text-xs text-gray-400">Последняя проверка GitHub: {formatDate(journal?.created_at)}. Нажмите входящую синхронизацию для нового fetch.</p>
        {(busy || ['APPLYING','RESTORING','PREPARING'].includes(state)) && <div role="status" className="space-y-2 text-sm text-cyan-200">
          <div>{(({backup:'Резервирование',merge:'Fast-forward Git',restore:'Восстановление файлов',python:'Python зависимости',npm:'npm ci',frontend_build:'Сборка frontend'} as Record<string,string>)[progress?.active_step] || activity)}</div>
          <div className="h-2 overflow-hidden rounded bg-gray-800"><div className="h-full w-1/3 animate-pulse rounded bg-cyan-500" /></div>
          <div className="text-xs text-gray-400">Операция выполняется. Процент и время окончания неизвестны.</div>
        </div>}
        {upToDate && !localOnly && <div className="rounded-lg border border-emerald-500/30 p-3 text-sm text-emerald-200">По последней проверке новых входящих коммитов нет.</div>}
        {localOnly && <div className="rounded-lg border border-amber-500/40 p-3 text-sm text-amber-200">Нет входящих коммитов. Для публикации локальных изменений используйте <button onClick={onOpenRepositories} className="underline">Репозитории</button>.</div>}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {steps.map(step => (
            <div key={step.number} className={`rounded-xl border p-3 ${step.done ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-gray-700 bg-gray-900/70'}`}>
              <div className="text-xs text-gray-500">ШАГ {step.number}</div>
              <div className="font-semibold text-sm text-gray-100 mt-1">{step.title}</div>
              <div className={`text-xs mt-2 ${step.done ? 'text-emerald-300' : 'text-gray-500'}`}>{step.done ? 'Завершён' : 'Ожидает выполнения'}</div>
            </div>
          ))}
        </div>
      </div>

      <section className="rounded-xl border border-cyan-500/40 bg-gray-950 p-4 space-y-2" aria-label="Журнал событий обновления">
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-bold text-cyan-200">Журнал событий обновления</h3>
          <span className="text-xs text-gray-400">{busy || restarting ? 'Обновляется автоматически' : 'Последняя операция'}</span>
        </div>
        {(busy || restarting) && <p className="text-sm text-cyan-300">{restarting ? 'Ожидание подтверждения перезапуска API' : activity}</p>}
        <div className="max-h-72 overflow-auto space-y-1 font-mono text-xs" role="log" aria-live="polite">
          {(live?.events || []).map((event: any, i: number) => <div key={i} className="border-b border-gray-800 py-1 text-gray-200">
            <span className="text-gray-500">{formatDate(event.at)} · </span>{updateStateLabel(event.state)} {event.step ? '· ' + event.step : ''} {event.code ? '· ' + event.code : ''}
          </div>)}
          {(live?.environment_steps || []).map((step: any) => <div key={step.step} className={step.ok ? 'text-emerald-300' : 'text-red-300'}>{step.step} · {step.ok ? 'PASS' : 'FAIL'} · exit {step.code ?? '—'} {step.diagnostic || ''}</div>)}
          {!live?.events?.length && <p className="text-gray-400">{busy ? 'Ожидание первого события сервера…' : 'Нет записанных событий.'}</p>}
        </div>
        <p className="text-xs text-gray-500">События сервера, не имитация вывода команд. Полный вывод доступен после завершения команды.</p>
      </section>
      {latestReport && <section className="rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-4 space-y-2">
        <h3 className="text-lg font-bold text-emerald-300">{state === 'COMPLETED' ? 'Обновление успешно завершено' : 'Последнее успешное обновление'}</h3>
        <UpdateReport item={latestReport} />
      </section>}
      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200 whitespace-pre-wrap">
          <b>Операция не завершена:</b> {error}<div className="mt-2">Путь исправления: устраните указанную причину. При повреждённом журнале сохраните journal.json и journal.json.tmp для диагностики; не удаляйте резервные ссылки.</div>
        </div>
      )}

      {journal?.error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-200 whitespace-pre-wrap">
          <b>Последняя ошибка из журнала:</b> {cleanCommandOutput(journal.error)}
        </div>
      )}

      <section className="rounded-xl border border-gray-800 bg-gray-900/60 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-cyan-300 font-bold">01</span>
          <h3 className="font-bold text-white">Проверить обновления и построить план</h3>
        </div>
        <p className="text-sm text-gray-400">Выполняется fetch официального репозитория, анализ ветки, входящих коммитов и локальных изменений. Рабочие файлы не изменяются.</p>
        <button disabled={!canCheck || busy || restarting} onClick={() => run('/api/updates/check')} className="px-4 py-2 rounded-lg text-sm font-semibold bg-cyan-500/15 border border-cyan-400/50 text-cyan-200 hover:bg-cyan-500/25 disabled:opacity-40">
          {busy ? 'Проверка…' : 'Проверить обновления'}
        </button>
        {journal && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
            <Metric label="Ветка" value={journal.branch || '—'} />
            <Metric label="Локальные коммиты" value={String(journal.ahead ?? '—')} />
            <Metric label="Входящие коммиты" value={String(journal.behind ?? '—')} />
            <Metric label="Локальные файлы" value={String(journal.local_files?.length ?? 0)} />
          </div>
        )}
        {journal?.local_files?.length > 0 && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
            <div className="text-sm font-semibold text-amber-200">Локальные изменения будут сохранены до обновления</div>
            <ul className="mt-2 space-y-1 text-xs font-mono text-gray-300 max-h-40 overflow-auto">
              {journal.local_files.map((file: string) => <li key={file}>{file}</li>)}
            </ul>
            <p className="text-xs text-gray-400 mt-2">Будет создан отдельный Git backup ref. Staged-состояние восстанавливается отдельно. Игнорируемые файлы не затрагиваются.</p>
          </div>
        )}
        {journal?.incoming_commits?.length > 0 && (
          <div className="space-y-1">
            <div className="text-xs uppercase tracking-wide text-gray-500">Входящие коммиты</div>
            {journal.incoming_commits.map((commit: any) => (
              <div key={commit.sha} className="text-xs text-gray-300"><code className="text-cyan-300">{commit.sha.slice(0, 8)}</code> · {commit.subject}</div>
            ))}
          </div>
        )}

        {journal?.change_summary?.files?.length > 0 && (
          <div className="rounded-lg border border-gray-800 bg-gray-950/60 p-3">
            <div className="text-xs uppercase tracking-wide text-gray-500">Файлы, которые придут с обновлением ({journal.change_summary.files.length})</div>
            <ul className="mt-2 space-y-1 text-xs font-mono text-gray-300 max-h-40 overflow-auto">
              {journal.change_summary.files.map((file: string) => <li key={file}>{file}</li>)}
            </ul>
          </div>
        )}
        {journal?.migration_files?.length > 0 && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-200">
            Обнаружены миграции, которые мастер не запускает автоматически:
            <ul className="list-disc ml-5 mt-1">{journal.migration_files.map((file: string) => <li key={file}>{file}</li>)}</ul>
          </div>
        )}
        {!upToDate && journal?.blockers?.length > 0 && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-200">
            <b>Обновление заблокировано:</b>
            <ul className="list-disc ml-5 mt-1">{journal.blockers.map((item: string) => <li key={item}>{item}</li>)}</ul>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-gray-800 bg-gray-900/60 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-cyan-300 font-bold">02</span>
          <h3 className="font-bold text-white">Создать backup и обновить исходники</h3>
        </div>
        <p className="text-sm text-gray-400">Локальные изменения сохраняются в отдельной ссылке Git, проверяются, затем выполняется только fast-forward. Commit, push, rebase и reset не используются.</p>
        <label className="flex items-start gap-2 text-sm text-gray-300">
          <input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} disabled={!canApply || busy} className="mt-1" />
          Я проверил план и подтверждаю резервирование локальных изменений и обновление исходников.
        </label>
        <button disabled={!canApply || !confirmed || busy || restarting} onClick={() => run('/api/updates/apply', journal?.id)} className="px-4 py-2 rounded-lg text-sm font-semibold bg-amber-500/15 border border-amber-400/50 text-amber-200 hover:bg-amber-500/25 disabled:opacity-40">
          Выполнить шаг 2
        </button>
        {journal?.backup_ref && <p className="text-xs text-emerald-300">Backup: <code>{journal.backup_ref}</code> {journal.backup_verified ? '· проверен' : '· проверка не завершена'}</p>}
        {journal?.backup_bundle && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-xs text-emerald-200">
            Внешняя копия проверена: <code>{journal.backup_bundle.path}</code>
            <div className="text-gray-400 mt-1">Размер: {Math.round(journal.backup_bundle.size_bytes / 1024)} KB · SHA-256: <code>{journal.backup_bundle.sha256}</code></div>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-gray-800 bg-gray-900/60 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-cyan-300 font-bold">03</span>
          <h3 className="font-bold text-white">Восстановить изменения и подготовить окружение</h3>
        </div>
        <p className="text-sm text-gray-400">Восстановление выполняется с индексом Git. Затем при необходимости обновляются Python/npm-зависимости и собирается frontend. При конфликте резервная копия остаётся нетронутой.</p>
        {!upToDate && state !== 'COMPLETED' && state !== 'RESTART_REQUIRED' && <button disabled={!canPrepare || busy || restarting} onClick={() => run('/api/updates/prepare', journal?.id)} className="px-4 py-2 rounded-lg text-sm font-semibold bg-emerald-500/15 border border-emerald-400/50 text-emerald-200 hover:bg-emerald-500/25 disabled:opacity-40">
          {environmentRepair ? 'Повторить подготовку окружения' : 'Выполнить шаг 3'}
        </button>}
        {upToDate && <p className="text-sm text-emerald-300">Новых обновлений нет. Подготовка окружения не требуется.</p>}
        {state === 'COMPLETED' && <p className="text-sm text-emerald-300">Все обязательные этапы завершены. Отчёт сохранён в истории.</p>}
        {environmentRepair && <p className="text-sm text-amber-200">Git восстановлен. Повторяются только незавершённые шаги окружения. При EPERM остановите старый Vite/watchdog и приостановите MEGA.</p>}
        {canRecover && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 space-y-2">
            <p className="text-sm text-red-200">Требуется восстановление. Не удаляйте backup ref и не запускайте новую операцию обновления.</p>
            <button disabled={busy} onClick={() => run('/api/updates/recover', journal?.id)} className="px-4 py-2 rounded-lg text-sm border border-red-400/50 text-red-200 hover:bg-red-500/10 disabled:opacity-40">Повторить восстановление локальных изменений</button>
            <button disabled={busy} onClick={() => {
              if (window.confirm('Подтверждаете, что вручную разрешили конфликты и проверили восстановленные локальные файлы? Резервная копия останется сохранённой.')) {
                void run('/api/updates/recover', journal?.id, true);
              }
            }} className="px-4 py-2 rounded-lg text-sm border border-amber-400/50 text-amber-200 hover:bg-amber-500/10 disabled:opacity-40">Я вручную восстановил и проверил локальные изменения</button>
          </div>
        )}
        {journal?.restart_required && state === 'RESTART_REQUIRED' && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-200">
            Для загрузки обновлённого ядра или статического интерфейса требуется перезапустить drmAIcu. Если проверка не прошла, исправьте причину и повторно откройте мастер. <div className="mt-3"><button disabled={busy || restarting} onClick={() => void restart()} className="rounded-lg border border-amber-400 px-4 py-2 disabled:opacity-40">{restarting ? 'Ожидаем перезапуск…' : 'Перезапустить drmAIcu'}</button></div>
          </div>
        )}
        {journal?.restart_verified_at && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm text-emerald-200">
            Перезапуск подтверждён: версия {journal.restart_health?.version || '—'}, HEAD {journal.restart_health?.head?.slice(0, 12) || '—'}, API отвечает. {journal.restart_verified_at}
          </div>
        )}
        {journal?.environment_steps?.map((item: any) => (
          <div key={item.step} className="rounded-lg border border-gray-800 bg-gray-950/70 p-3">
            <div className="flex justify-between text-sm"><b className="text-gray-200">{item.step}</b><span className={item.ok ? (hasNpmWarnings(item) ? 'text-amber-300' : 'text-emerald-300') : 'text-red-300'}>{item.ok ? (hasNpmWarnings(item) ? 'Выполнен с предупреждениями' : 'Выполнен') : 'Ошибка'}</span></div>
            {(item.stderr || item.stdout) && <details className="mt-2 text-xs text-gray-400"><summary>Вывод команды</summary><pre className="whitespace-pre-wrap max-h-48 overflow-auto">{[item.stdout, item.stderr].map(cleanCommandOutput).filter(Boolean).join("\n")}</pre></details>}
          </div>
        ))}
      </section>

      <section className="rounded-xl border border-gray-800 bg-gray-900/60 p-4 space-y-2">
        <h3 className="font-bold text-white">История обновлений</h3>
        {!history.length && <p className="text-sm text-gray-400">Архив пока пуст. Завершённые операции сохраняются перед следующей проверкой.</p>}
        {history.map(item => <details key={item.id} className="rounded-lg border border-gray-800 p-3 text-sm">
          <summary className="cursor-pointer text-gray-200">{item.current_version || '—'} → {item.target_version || item.remote_head?.slice(0,8) || '—'} · {updateStateLabel(item.state)} · {formatDate(item.finished_at || item.updated_at)}</summary>
          <div className="mt-3"><UpdateReport item={item} /></div>
          <button className="mt-3 rounded border border-gray-600 px-3 py-1" onClick={async () => {
            try { await navigator.clipboard.writeText(JSON.stringify(item, null, 2)); setCopyStatus('Диагностический отчёт скопирован'); }
            catch { setCopyStatus('Не удалось скопировать отчёт'); }
          }}>Копировать отчёт</button>
        </details>)}
        {copyStatus && <p role="status" className="text-sm text-gray-300">{copyStatus}</p>}
      </section>
      <p className="text-xs text-gray-600">Безопасность: обновление разрешено только из официального HTTPS-репозитория drmAIcu. Журнал хранится локально в data/updater. Резервные refs намеренно не удаляются автоматически.</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-950/60 p-3">
      <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="font-mono text-sm text-gray-200 mt-1 break-all">{value}</div>
    </div>
  );
}


function formatDate(value?: string) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

function UpdateReport({ item }: { item: any }) {
  const summary = item.change_summary || {};
  const env = (step: string, required: boolean | undefined) => {
    const result = item.environment_steps?.find((x: any) => x.step === step);
    if (result) return result.ok ? 'Выполнен' : 'Ошибка';
    if (required === false) return 'Не требуется';
    return 'Нет данных';
  };
  const rows = [
    ['Обновление исходников', item.new_head && item.new_head === item.remote_head ? 'Выполнен' : 'Нет данных'],
    ['Резервирование', item.backup_verified ? 'Выполнен' : item.local_changes === false ? 'Не требуется' : 'Нет данных'],
    ['Восстановление Git', item.local_changes === false ? 'Не требуется' : item.local_changes_restored ? 'Выполнен' : 'Нет данных'],
    ['Python', env('python', summary.requirements_changed)],
    ['npm', env('npm', summary.npm_lock_changed)],
    ['Сборка frontend', env('frontend_build', summary.frontend_changed)],
    ['Перезапуск', item.restart_verified_at ? 'Выполнен' : item.restart_required === false ? 'Не требуется' : 'Нет данных'],
  ];
  return <div className="space-y-2 text-sm text-gray-300">
    <div className="font-mono">{item.current_version || '—'} → {item.target_version || '—'} · {updateStateLabel(item.state)}</div>
    <div>Начало: {formatDate(item.started_at)} · Окончание: {formatDate(item.finished_at || item.updated_at)}</div>
    <div>Продолжительность: {typeof item.duration_seconds === 'number' ? item.duration_seconds + ' сек.' : 'Нет данных'}</div>
    {rows.map(([label,status]) => <div key={label} className="flex justify-between gap-2 border-t border-gray-800 pt-1"><span>{label}</span><span className={status === 'Выполнен' ? 'text-emerald-300' : status === 'Ошибка' ? 'text-red-300' : 'text-gray-400'}>{status}</span></div>)}
    <details><summary className="cursor-pointer text-cyan-300">Журнал этапов и коды завершения</summary>
      <div className="mt-2 max-h-64 overflow-auto space-y-1 font-mono text-xs">
        {(item.events || []).map((e: any,i: number) => <div key={i}>{formatDate(e.at)} · {updateStateLabel(e.state)} {e.step || ''} {e.code || ''}</div>)}
        {(item.environment_steps || []).map((e: any) => <div key={e.step}>{e.step}: {e.ok ? 'PASS' : 'FAIL'} · exit {e.code ?? '—'} {e.diagnostic || ''}</div>)}
        {!item.events?.length && <div>Подробные события старой операции не сохранены.</div>}
      </div>
    </details>
    <div className="text-xs text-gray-500">Архив содержит структурированную диагностику, без необработанного вывода команд.</div>
  </div>;
}
