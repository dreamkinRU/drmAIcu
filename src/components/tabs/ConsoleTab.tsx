import { useState, useRef, useEffect } from 'react';
import { Agent, AgentPipeline, CodeIssue, ProjectFile } from '../../types';
import { StreamMetrics } from '../../services/api';

interface ConsoleTabProps {
  consolePrompt: string;
  setConsolePrompt: (value: string) => void;
  consoleLoading: boolean;
  agents?: Agent[];
  pipelines?: AgentPipeline[];
  projectFiles?: ProjectFile[];
  codeIssues?: CodeIssue[];
  contextFiles?: string[];
  setContextFiles?: (files: string[]) => void;
  includeLogs?: boolean;
  setIncludeLogs?: (v: boolean) => void;
  includeCodeIssues?: boolean;
  setIncludeCodeIssues?: (v: boolean) => void;
  exportingPatch?: boolean;
  hasPatchCandidate?: boolean;
  exportPatchToPatches?: () => void;
  activeAgentId?: number | null;
  setActiveAgentId?: (id: number | null) => void;
  activePipelineId?: string | null;
  setActivePipelineId?: (id: string | null) => void;
  providerMode: 'ollama' | 'groq' | 'bionic' | 'lmstudio' | 'strata' | 'all';
  setProviderMode: (mode: 'ollama' | 'groq' | 'bionic' | 'lmstudio' | 'strata' | 'all') => void;
  selectedModel: string;
  setSelectedModel: (value: string) => void;
  installedModels: any[];
  bionicModels?: any[];
  lmstudioModels?: any[];
  strataModels?: any[];
  lastPrompt: string;
  consoleMetrics: StreamMetrics | null;
  runAiTask: () => void;
  stopAiTask: () => void;
  retryLastTask: () => void;
}

export default function ConsoleTab(props: ConsoleTabProps) {
  const {
    consolePrompt, setConsolePrompt, consoleLoading,
    agents = [], pipelines = [], projectFiles = [], codeIssues = [],
    contextFiles = [], setContextFiles, includeLogs = false, setIncludeLogs,
    includeCodeIssues = false, setIncludeCodeIssues,
    exportingPatch = false, hasPatchCandidate = false, exportPatchToPatches,
    activeAgentId = null, setActiveAgentId, activePipelineId = null, setActivePipelineId,
    providerMode, setProviderMode, selectedModel, setSelectedModel, installedModels, bionicModels = [], lmstudioModels = [], strataModels = [],
    lastPrompt, consoleMetrics,
    runAiTask, stopAiTask, retryLastTask,
  } = props;

  const [showSelector, setShowSelector] = useState(false);
  const [showContextModal, setShowContextModal] = useState(false);
  const [fileSearch, setFileSearch] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.scrollTop = textareaRef.current.scrollHeight;
    }
  }, [consolePrompt]);

  const enabledAgentsCount = agents.filter((a) => a.enabled).length;
  const judgeAgent = agents.find((a) => a.isJudge);
  const activePipeline = activePipelineId ? pipelines.find((p) => p.id === activePipelineId) : null;
  const selectValue = activePipelineId ? `pipe:${activePipelineId}` : activeAgentId !== null ? String(activeAgentId) : '';
  const openIssuesCount = codeIssues.filter((i) => !i.fixed).length;
  const contextCount = contextFiles.length + (includeLogs ? 1 : 0) + (includeCodeIssues ? 1 : 0);

  const toggleContextFile = (relPath: string) => {
    if (!setContextFiles) return;
    if (contextFiles.includes(relPath)) {
      setContextFiles(contextFiles.filter((f) => f !== relPath));
    } else if (contextFiles.length < 10) {
      setContextFiles([...contextFiles, relPath]);
    }
  };

  const selectableFiles = projectFiles
    .filter((f) => !f.is_duplicate && f.category !== 'backup' && f.category !== 'trash')
    .filter((f) => !fileSearch.trim() || f.path.toLowerCase().includes(fileSearch.trim().toLowerCase()))
    .slice(0, 40);

  return (
    <div className="relative flex flex-col h-[calc(100vh-175px)] min-h-[360px] rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-4">
      <div className="flex items-center justify-between text-xs text-gray-400 mb-3 px-1">
        <div className="flex flex-wrap items-center gap-3">
          {setActiveAgentId && (
            <div className="flex items-center gap-1.5">
              <span>Агент:</span>
              <select
                value={selectValue}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val.startsWith('pipe:') && setActivePipelineId) {
                    setActivePipelineId(val.slice(5));
                  } else {
                    if (setActivePipelineId) setActivePipelineId(null);
                    setActiveAgentId(val ? Number(val) : null);
                  }
                }}
                className="bg-gray-800/90 border border-gray-700 hover:border-purple-500/60 rounded px-2 py-0.5 text-xs font-bold text-purple-300 focus:outline-none cursor-pointer"
                title="Выбор агента, консилиума или цепочки"
              >
                <option value="">Без агента</option>
                <option value="-1">👥 Консилиум (активные: {enabledAgentsCount})</option>
                {pipelines.length > 0 && (
                  <optgroup label="⛓️ Цепочки (Pipeline)">
                    {pipelines.map((p) => (
                      <option key={p.id} value={`pipe:${p.id}`}>
                        ⛓️ {p.name} ({p.steps.length} ш.)
                      </option>
                    ))}
                  </optgroup>
                )}
                <optgroup label="🤖 Агенты">
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.enabled ? '● ' : '○ '}{a.name}{a.isJudge ? ' ⚖️' : ''}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>
          )}

          {activePipeline ? (
            <span className="px-2 py-0.5 rounded bg-indigo-500/15 border border-indigo-500/40 text-indigo-300 font-mono">
              {activePipeline.steps.map((s) => agents.find((a) => a.id === s.agentId)?.name.split('—')[0].trim() || `#${s.agentId}`).join(' → ')}
            </span>
          ) : activeAgentId === -1 ? (
            <span className="px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/40 text-amber-300 font-semibold">
              ⚖️ Судья: {judgeAgent ? judgeAgent.name : 'автовыбор'}
            </span>
          ) : (
            <>
              <span>
                Провайдер:{' '}
                <button
                  type="button"
                  onClick={() => setShowSelector(true)}
                  className="text-emerald-400 font-bold uppercase hover:underline cursor-pointer"
                  title="Выбрать провайдера и модель"
                >
                  {providerMode}
                </button>
              </span>
              <span>
                Модель:{' '}
                <button
                  type="button"
                  onClick={() => setShowSelector(true)}
                  className="text-cyan-400 font-bold hover:underline cursor-pointer"
                  title="Выбрать провайдера и модель"
                >
                  {selectedModel || 'по умолчанию'}
                </button>
              </span>
            </>
          )}

          {setContextFiles && (
            <button
              type="button"
              onClick={() => setShowContextModal(true)}
              className={`px-2 py-0.5 rounded border text-xs font-semibold transition-all ${
                contextCount > 0
                  ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                  : 'bg-gray-800/80 border-gray-700 text-gray-300 hover:border-gray-500'
              }`}
              title="Прикрепить файлы проекта, логи ядра или замечания из вкладки Код"
            >
              📎 Контекст{contextCount > 0 ? ` (${contextCount})` : ''}
            </button>
          )}
        </div>

        {consoleMetrics && (
          <div className="flex items-center gap-3 font-mono text-gray-400">
            <span>⚡ {consoleMetrics.tps} tok/s</span>
            <span>⏱ {consoleMetrics.elapsed_sec}s (TTFT {consoleMetrics.ttft_sec}s)</span>
            <span>~{consoleMetrics.tokens} tok</span>
          </div>
        )}
      </div>

      <textarea
        ref={textareaRef}
        value={consolePrompt}
        onChange={(e) => setConsolePrompt(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            runAiTask();
          }
        }}
        placeholder="Опиши задачу... (Enter — отправить, Shift+Enter — новая строка)"
        className="flex-1 w-full px-4 py-3 rounded-lg bg-gray-800/80 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none resize-none font-mono leading-relaxed"
      />

      <div className="flex justify-between items-center mt-3 gap-3 shrink-0">
        <div className="flex items-center gap-2">
          {hasPatchCandidate && exportPatchToPatches && !consoleLoading && (
            <button
              type="button"
              onClick={exportPatchToPatches}
              disabled={exportingPatch}
              className="px-4 py-2.5 rounded-lg font-bold text-sm bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/50 text-amber-300 disabled:opacity-50"
              title="Сохранить JSON-патч из ответа в patch/ и запустить preflight-проверку"
            >
              {exportingPatch ? '⏳ Проверка...' : '📦 В Патчи'}
            </button>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setConsolePrompt('')}
            disabled={consoleLoading}
            className="px-4 py-2.5 rounded-lg font-bold text-sm bg-gray-700 hover:bg-gray-600 text-gray-300 disabled:opacity-50"
          >
            🗑 Очистить
          </button>
          {lastPrompt && !consoleLoading && (
            <button
              onClick={retryLastTask}
              className="px-4 py-2.5 rounded-lg font-bold text-sm bg-cyan-600/30 hover:bg-cyan-600/50 border border-cyan-500/50 text-cyan-300"
            >
              ↻ Повторить
            </button>
          )}
          {consoleLoading ? (
            <button
              onClick={stopAiTask}
              className="px-8 py-2.5 rounded-lg font-bold text-base bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-500/20"
            >
              ⏹ Стоп
            </button>
          ) : (
            <button
              onClick={runAiTask}
              disabled={!consolePrompt.trim()}
              className="px-8 py-2.5 rounded-lg font-bold text-base transition-all bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white shadow-lg shadow-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              ▶ Отправить (Enter)
            </button>
          )}
        </div>
      </div>

      {showContextModal && setContextFiles && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setShowContextModal(false)}
        >
          <div
            className="w-full max-w-xl rounded-xl border border-gray-700 bg-gray-900 p-5 shadow-2xl space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-gray-200 uppercase tracking-wider">📎 Контекст репозитория для агента</h3>
              <button
                type="button"
                onClick={() => setShowContextModal(false)}
                className="text-gray-400 hover:text-white text-sm px-2 py-1 rounded hover:bg-gray-800"
              >
                ✕
              </button>
            </div>

            <div className="flex flex-wrap gap-3">
              {setIncludeLogs && (
                <label className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-xs text-gray-200 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includeLogs}
                    onChange={(e) => setIncludeLogs(e.target.checked)}
                  />
                  <span>▤ Последние логи ядра (25 строк)</span>
                </label>
              )}
              {setIncludeCodeIssues && (
                <label className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-xs text-gray-200 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includeCodeIssues}
                    onChange={(e) => setIncludeCodeIssues(e.target.checked)}
                  />
                  <span>⟨⟩ Ошибки из вкладки Код ({openIssuesCount})</span>
                </label>
              )}
            </div>

            {contextFiles.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {contextFiles.map((f) => (
                  <span
                    key={f}
                    onClick={() => toggleContextFile(f)}
                    className="px-2.5 py-1 rounded-md bg-emerald-500/20 border border-emerald-500/50 text-emerald-300 text-xs font-mono cursor-pointer hover:bg-red-500/20 hover:border-red-500/50 hover:text-red-300"
                    title="Нажмите, чтобы убрать файл"
                  >
                    {f} ✕
                  </span>
                ))}
              </div>
            )}

            <div className="space-y-2">
              <input
                type="text"
                value={fileSearch}
                onChange={(e) => setFileSearch(e.target.value)}
                placeholder="Поиск файла проекта (например: main.py, agent_engine.py, App.tsx)..."
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-xs font-mono focus:border-emerald-500 focus:outline-none"
              />
              <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
                {selectableFiles.map((f) => {
                  const checked = contextFiles.includes(f.path);
                  return (
                    <div
                      key={f.path}
                      onClick={() => toggleContextFile(f.path)}
                      className={`flex items-center justify-between px-3 py-1.5 rounded text-xs font-mono cursor-pointer ${
                        checked
                          ? 'bg-emerald-500/15 border border-emerald-500/40 text-emerald-300'
                          : 'bg-gray-800/60 hover:bg-gray-800 text-gray-300'
                      }`}
                    >
                      <span className="truncate">{f.path}</span>
                      <span className="text-[11px] text-gray-500 shrink-0 ml-2">{f.size_human}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="flex justify-between items-center pt-1">
              <button
                type="button"
                onClick={() => {
                  setContextFiles([]);
                  if (setIncludeLogs) setIncludeLogs(false);
                  if (setIncludeCodeIssues) setIncludeCodeIssues(false);
                }}
                className="px-3 py-1.5 rounded-lg text-xs font-bold bg-gray-800 hover:bg-gray-700 text-gray-400"
              >
                Сбросить всё
              </button>
              <button
                type="button"
                onClick={() => setShowContextModal(false)}
                className="px-4 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white"
              >
                Готово
              </button>
            </div>
          </div>
        </div>
      )}

      {showSelector && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setShowSelector(false)}
        >
          <div
            className="w-full max-w-md rounded-xl border border-gray-700 bg-gray-900 p-5 shadow-2xl space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-gray-200 uppercase tracking-wider">Выбор провайдера и модели</h3>
              <button
                type="button"
                onClick={() => setShowSelector(false)}
                className="text-gray-400 hover:text-white text-sm px-2 py-1 rounded hover:bg-gray-800"
              >
                ✕
              </button>
            </div>

            <div>
              <label className="block text-xs text-gray-400 mb-2">Провайдер</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setProviderMode('ollama')}
                  className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium border transition-all ${providerMode === 'ollama' ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white'}`}
                >
                  🏠 Ollama
                </button>
                <button
                  type="button"
                  onClick={() => setProviderMode('groq')}
                  className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium border transition-all ${providerMode === 'groq' ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400' : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white'}`}
                >
                  ☁️ Groq
                </button>
                <button
                  type="button"
                  onClick={() => setProviderMode('bionic')}
                  className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium border transition-all ${providerMode === 'bionic' ? 'bg-amber-500/20 border-amber-500/50 text-amber-400' : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white'}`}
                >
                  🧬 Bionic
                </button>
                <button
                  type="button"
                  onClick={() => setProviderMode('lmstudio')}
                  className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium border transition-all ${providerMode === 'lmstudio' ? 'bg-blue-500/20 border-blue-500/50 text-blue-400' : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white'}`}
                >
                  💻 LM Studio
                </button>
                <button
                  type="button"
                  onClick={() => setProviderMode('strata')}
                  className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium border transition-all ${providerMode === 'strata' ? 'bg-rose-500/20 border-rose-500/50 text-rose-400' : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white'}`}
                >
                  🪨 Strata
                </button>
                <button
                  type="button"
                  onClick={() => setProviderMode('all')}
                  className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium border transition-all ${providerMode === 'all' ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white'}`}
                >
                  ⚡ Все
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-400 mb-2">Модель</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none cursor-pointer"
              >
                <option value="">🤖 По умолчанию</option>
                {(providerMode === 'bionic' ? bionicModels : providerMode === 'lmstudio' ? lmstudioModels : providerMode === 'strata' ? strataModels : installedModels).map((m: any) => (
                  <option key={m.name || m} value={m.name || m}>
                    {m.name || m}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={() => setShowSelector(false)}
                className="px-4 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white"
              >
                Готово
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
