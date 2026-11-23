import { useState, useRef, useEffect } from 'react';
import { StreamMetrics } from '../../services/api';

interface ConsoleTabProps {
  consolePrompt: string;
  setConsolePrompt: (value: string) => void;
  consoleLoading: boolean;
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
    providerMode, setProviderMode, selectedModel, setSelectedModel, installedModels, bionicModels = [], lmstudioModels = [], strataModels = [],
    lastPrompt, consoleMetrics,
    runAiTask, stopAiTask, retryLastTask,
  } = props;

  const [showSelector, setShowSelector] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.scrollTop = textareaRef.current.scrollHeight;
    }
  }, [consolePrompt]);

  return (
    <div className="relative flex flex-col h-[calc(100vh-175px)] min-h-[360px] rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-4">
      <div className="flex items-center justify-between text-xs text-gray-400 mb-3 px-1">
        <div className="flex items-center gap-3">
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

      <div className="flex justify-end mt-3 gap-3 shrink-0">
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
