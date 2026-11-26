import { useCallback, useEffect, useState } from 'react';

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

export default function UpdateWizardTab() {
  const [journal, setJournal] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirmed, setConfirmed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const result = await callUpdate('/api/updates/state');
      setJournal(result.journal || null);
    } catch (e: any) {
      setError(e?.message || 'Не удалось получить состояние Update Manager');
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const run = async (path: string, operationId?: string, manualConfirmation = false) => {
    setBusy(true);
    setError('');
    try {
      const result = await callUpdate(path, operationId, manualConfirmation);
      setJournal(result.plan || result.journal || null);
      setConfirmed(false);
    } catch (e: any) {
      setError(e?.message || 'Операция обновления завершилась ошибкой');
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const state = journal?.state || 'IDLE';
  const canApply = state === 'CHECKED' && !(journal?.blockers || []).length;
  const canPrepare = state === 'CODE_UPDATED';
  const canRecover = ['APPLYING', 'RECOVERY_REQUIRED', 'UPDATE_NEEDS_REPAIR', 'RESTORING', 'PREPARING'].includes(state);
  const steps = [
    { number: 1, title: 'Проверка и план', done: ['CHECKED', 'APPLYING', 'CODE_UPDATED', 'RESTORING', 'COMPLETED', 'RECOVERY_REQUIRED', 'UPDATE_NEEDS_REPAIR'].includes(state) },
    { number: 2, title: 'Резервирование и обновление', done: ['CODE_UPDATED', 'RESTORING', 'COMPLETED', 'UPDATE_NEEDS_REPAIR'].includes(state) },
    { number: 3, title: 'Восстановление и окружение', done: state === 'COMPLETED' },
  ];

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-cyan-500/30 bg-gradient-to-br from-gray-900 to-gray-950 p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-white">🔄 Мастер обновления drmAIcu</h2>
            <p className="text-sm text-gray-400 mt-1">Три шага. Каждый этап запускается отдельно и только после подтверждения.</p>
          </div>
          <span className={`text-xs px-3 py-1.5 rounded-full border ${state === 'COMPLETED' ? 'border-emerald-500/50 text-emerald-300 bg-emerald-500/10' : canRecover ? 'border-red-500/50 text-red-300 bg-red-500/10' : 'border-gray-700 text-gray-300 bg-gray-800'}`}>
            {state}
          </span>
        </div>
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

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200 whitespace-pre-wrap">
          <b>Операция не завершена:</b> {error}
        </div>
      )}

      {journal?.error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-200 whitespace-pre-wrap">
          <b>Последняя ошибка из журнала:</b> {journal.error}
        </div>
      )}

      <section className="rounded-xl border border-gray-800 bg-gray-900/60 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-cyan-300 font-bold">01</span>
          <h3 className="font-bold text-white">Проверить обновления и построить план</h3>
        </div>
        <p className="text-sm text-gray-400">Выполняется fetch официального репозитория, анализ ветки, входящих коммитов и локальных изменений. Рабочие файлы не изменяются.</p>
        <button disabled={busy} onClick={() => run('/api/updates/check')} className="px-4 py-2 rounded-lg text-sm font-semibold bg-cyan-500/15 border border-cyan-400/50 text-cyan-200 hover:bg-cyan-500/25 disabled:opacity-40">
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
        {journal?.blockers?.length > 0 && (
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
        <button disabled={!canApply || !confirmed || busy} onClick={() => run('/api/updates/apply', journal?.id)} className="px-4 py-2 rounded-lg text-sm font-semibold bg-amber-500/15 border border-amber-400/50 text-amber-200 hover:bg-amber-500/25 disabled:opacity-40">
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
        <button disabled={!canPrepare || busy} onClick={() => run('/api/updates/prepare', journal?.id)} className="px-4 py-2 rounded-lg text-sm font-semibold bg-emerald-500/15 border border-emerald-400/50 text-emerald-200 hover:bg-emerald-500/25 disabled:opacity-40">
          Выполнить шаг 3
        </button>
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
        {journal?.restart_required && state === 'COMPLETED' && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-200">
            Изменён Python-код. Для загрузки новой версии требуется перезапустить drmAIcu. Перезапуск не выполняется автоматически, чтобы не прервать показ результата мастера.
          </div>
        )}
        {journal?.environment_steps?.map((item: any) => (
          <div key={item.step} className="rounded-lg border border-gray-800 bg-gray-950/70 p-3">
            <div className="flex justify-between text-sm"><b className="text-gray-200">{item.step}</b><span className={item.ok ? 'text-emerald-300' : 'text-red-300'}>{item.ok ? 'PASS' : 'FAIL'}</span></div>
            {(item.stderr || item.stdout) && <pre className="mt-2 text-xs text-gray-500 whitespace-pre-wrap max-h-36 overflow-auto">{item.stderr || item.stdout}</pre>}
          </div>
        ))}
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
