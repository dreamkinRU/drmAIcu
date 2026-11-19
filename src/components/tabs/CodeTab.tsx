import { CodeIssue } from '../../types';

interface CodeTabProps {
  codeIssues: CodeIssue[];
  fixCodeIssue: (id: number) => void;
  fixAll: () => void;
}

export default function CodeTab({ codeIssues, fixCodeIssue, fixAll }: CodeTabProps) {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Анализ кода</h2>
        <button
          onClick={fixAll}
          className="px-4 py-2 rounded-lg bg-gradient-to-r from-red-500 to-orange-500 text-white text-sm font-bold"
        >
          🔧 Исправить все
        </button>
      </div>

      {codeIssues.map(issue => (
        <div
          key={issue.id}
          className={`rounded-xl border p-6 ${
            issue.fixed
              ? 'border-emerald-500/30 bg-emerald-500/5'
              : issue.severity === 'critical'
              ? 'border-red-500/30 bg-red-500/5'
              : issue.severity === 'warning'
              ? 'border-yellow-500/30 bg-yellow-500/5'
              : 'border-blue-500/30 bg-blue-500/5'
          }`}
        >
          <div className="flex justify-between items-start mb-3">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <span
                  className={`px-2 py-1 rounded text-xs font-bold ${
                    issue.severity === 'critical'
                      ? 'bg-red-500/20 text-red-400'
                      : issue.severity === 'warning'
                      ? 'bg-yellow-500/20 text-yellow-400'
                      : 'bg-blue-500/20 text-blue-400'
                  }`}
                >
                  {issue.severity.toUpperCase()}
                </span>
                <span className="text-xs text-gray-500 font-mono">
                  {issue.file}:{issue.line}
                </span>
                {issue.fixed && (
                  <span className="px-2 py-1 rounded text-xs font-bold bg-emerald-500/20 text-emerald-400">
                    ИСПРАВЛЕНО
                  </span>
                )}
              </div>
              <h4 className="text-base font-bold text-white">{issue.title}</h4>
              <p className="text-sm text-gray-400 mt-2">{issue.description}</p>
            </div>
            {!issue.fixed && (
              <button
                onClick={() => fixCodeIssue(issue.id)}
                className="px-4 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-sm font-bold"
              >
                🔧 Исправить
              </button>
            )}
          </div>
          {issue.fixed && issue.fixLog && issue.fixLog.length > 0 && (
            <div className="mt-4 p-4 rounded-lg bg-gray-900/80 border border-gray-700">
              <div className="space-y-1 max-h-96 overflow-y-auto">
                {issue.fixLog.map((log, i) => (
                  <p key={i} className="text-xs text-gray-400 font-mono whitespace-pre-wrap">
                    {log}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
