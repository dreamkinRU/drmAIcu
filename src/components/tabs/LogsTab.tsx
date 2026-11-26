import { useState } from 'react';
import { LogEntry } from '../../types';

type LogFilter = 'all' | 'issues';

interface LogsTabProps {
  logs: LogEntry[];
  onClearIssues: () => Promise<void> | void;
}

// Вкладка «Логи» получает: лог ядра (/api/logs), ошибки/предупреждения плагинов
// (manager.recent_issues) и ошибки UI (addLog → POST /api/logs). Фильтр
// «Ошибки» помогает найти сбой синхронизации, который раньше мигал и исчезал.
export default function LogsTab({ logs, onClearIssues }: LogsTabProps) {
  const [filter, setFilter] = useState<LogFilter>('all');
  const [clearing, setClearing] = useState(false);
  const issues = logs.filter(l => l.level === 'error' || l.level === 'warn');
  const shown = filter === 'all' ? logs : issues;
  const issuesCount = issues.length;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <h2 className="text-2xl font-bold">Логи</h2>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setFilter('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${
              filter === 'all'
                ? 'bg-cyan-500/15 border-cyan-400/70 text-cyan-300'
                : 'border-gray-700 text-gray-400 hover:border-gray-500'
            }`}
          >
            Все ({logs.length})
          </button>
          <button
            onClick={() => setFilter('issues')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${
              filter === 'issues'
                ? 'bg-red-500/15 border-red-400/70 text-red-300'
                : 'border-gray-700 text-gray-400 hover:border-gray-500'
            }`}
          >
            Ошибки и предупреждения ({issuesCount})
          </button>
          {/* Кнопка очистки ошибок: ошибки не должны оставаться в журнале вечно —
              пользователь сам решает, что старые уже исправленные записи можно убрать */}
          <button
            disabled={clearing || issuesCount === 0}
            onClick={async () => {
              setClearing(true);
              await onClearIssues();
              setClearing(false);
            }}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all bg-red-500/10 border-red-500/40 text-red-300 hover:bg-red-500/20 disabled:opacity-40"
            title="Удалить из журнала все записи ошибок и предупреждений (info останется)"
          >
            ✕ Очистить ошибки{issuesCount > 0 ? ` (${issuesCount})` : ''}
          </button>
          <span className="text-xs text-gray-500">Обновление каждые 10 сек</span>
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 max-h-[70vh] overflow-y-auto">
        {shown.length === 0 ? (
          <div className="text-sm text-gray-500 py-6 text-center">
            {filter === 'issues' ? 'Ошибок и предупреждений нет — всё хорошо.' : 'Записей пока нет.'}
          </div>
        ) : (
          shown.slice().reverse().map((entry, i) => (
            <div
              key={i}
              className="flex items-start gap-3 py-2 font-mono text-sm border-b border-gray-800/30 last:border-0"
            >
              <span className="text-gray-600 shrink-0">[{entry.time}]</span>
              <span
                className={
                  entry.level === 'info'
                    ? 'text-blue-400'
                    : entry.level === 'warn'
                    ? 'text-yellow-400'
                    : entry.level === 'error'
                    ? 'text-red-400'
                    : 'text-emerald-400'
                }
              >
                {entry.level === 'info' ? 'ℹ' : entry.level === 'warn' ? '⚠' : entry.level === 'error' ? '✕' : '✓'}
              </span>
              <div className="flex-1">
                <span className="text-gray-300">{entry.message}</span>
                {entry.details && <p className="text-xs text-gray-500 mt-1">{entry.details}</p>}
              </div>
              <span className="text-gray-600 shrink-0">({entry.source})</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
