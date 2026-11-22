import { useState } from 'react';

interface ConsoleTabProps {
  consolePrompt: string;
  setConsolePrompt: (value: string) => void;
  consoleLoading: boolean;
  providerMode: 'ollama' | 'groq' | 'all';
  setProviderMode: (mode: 'ollama' | 'groq' | 'all') => void;
  selectedModel: string;
  setSelectedModel: (value: string) => void;
  installedModels: any[];
  ollamaUrl: string;
  setOllamaUrl: (url: string) => void;
  runAiTask: () => void;
}

export default function ConsoleTab(props: ConsoleTabProps) {
  const {
    consolePrompt, setConsolePrompt, consoleLoading,
    providerMode, setProviderMode, selectedModel, setSelectedModel, installedModels,
    ollamaUrl, setOllamaUrl, runAiTask,
  } = props;

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-6">
        <label className="text-sm font-bold text-gray-300 uppercase tracking-wider mb-3 block">Провайдеры</label>
        <div className="flex gap-3 mb-4">
          <button onClick={() => setProviderMode('ollama')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'ollama' ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'bg-gray-800/50 border-gray-700 text-gray-400'}`}>🏠 Ollama</button>
          <button onClick={() => setProviderMode('groq')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'groq' ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400' : 'bg-gray-800/50 border-gray-700 text-gray-400'}`}>☁️ Groq</button>
          <button onClick={() => setProviderMode('all')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'all' ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-gray-800/50 border-gray-700 text-gray-400'}`}>⚡ Все</button>
        </div>
        {(providerMode === 'ollama' || providerMode === 'all') && (
          <div className="space-y-3">
            <input
              type="text"
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              className="w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono focus:border-emerald-500 focus:outline-none"
              placeholder="http://localhost:11434"
            />
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none appearance-none cursor-pointer"
            >
              <option value="">🤖 Выбрать модель...</option>
              {installedModels.map((m: any) => (
                <option key={m.name || m} value={m.name || m}>
                  {m.name || m}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-6">
        <textarea
          value={consolePrompt}
          onChange={(e) => setConsolePrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              runAiTask();
            }
          }}
          placeholder="Опиши задачу... (Ctrl+Enter)"
          rows={8}
          className="w-full px-4 py-3 rounded-lg bg-gray-800/80 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none resize-none font-mono"
        />
        <div className="flex justify-end mt-4 gap-3">
          <button onClick={() => setConsolePrompt('')} className="px-4 py-3 rounded-lg font-bold text-sm bg-gray-700 hover:bg-gray-600 text-gray-300">🗑 Очистить</button>
          <button
            onClick={runAiTask}
            disabled={consoleLoading || !consolePrompt.trim()}
            className={`px-8 py-3 rounded-lg font-bold text-base transition-all ${consoleLoading ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white shadow-lg shadow-emerald-500/20'}`}
          >
            {consoleLoading ? '⏳ Отправка...' : '▶ Отправить (Ctrl+Enter)'}
          </button>
        </div>
      </div>
    </div>
  );
}
