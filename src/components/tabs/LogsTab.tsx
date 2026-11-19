import { LogEntry } from '../../types';

interface LogsTabProps {
  logs: LogEntry[];
}

export default function LogsTab({ logs }: LogsTabProps) {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Логи</h2>
        <span className="text-xs text-gray-500">Обновление каждые 3 сек</span>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 max-h-[70vh] overflow-y-auto">
        {logs.slice().reverse().map((entry, i) => (
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
        ))}
      </div>
    </div>
  );
}
