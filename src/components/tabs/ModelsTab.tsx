import { OllamaModel, TabId } from '../../types';

interface ModelsTabProps {
  ollamaStatus: 'checking' | 'online' | 'offline';
  newModelName: string;
  setNewModelName: (name: string) => void;
  isPulling: boolean;
  pullModel: () => void;
  installedModels: OllamaModel[];
  setConsolePrompt: (updater: (prev: string) => string) => void;
  setActiveTab: (tab: TabId) => void;
}

export default function ModelsTab({
  ollamaStatus, newModelName, setNewModelName, isPulling, pullModel,
  installedModels, setConsolePrompt, setActiveTab,
}: ModelsTabProps) {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">🧠 Управление моделями Ollama</h2>

      <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
        <h3 className="text-lg font-bold mb-4">📥 Скачать новую модель</h3>
        <div className="flex gap-3">
          <input
            type="text"
            value={newModelName}
            onChange={(e) => setNewModelName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                pullModel();
              }
            }}
            placeholder="Например: qwen2.5-coder:1.5b"
            className="flex-1 px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none font-mono"
            disabled={isPulling}
          />
          <button
            onClick={pullModel}
            disabled={isPulling || !newModelName.trim()}
            className={`px-6 py-3 rounded-lg font-bold text-sm transition-all whitespace-nowrap ${
              isPulling
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : 'bg-emerald-500 hover:bg-emerald-600 text-white'
            }`}
          >
            {isPulling ? '⏳ Загрузка...' : '📥 Скачать'}
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          💡 Популярные: qwen2.5-coder:1.5b, qwen2.5-coder:14b, llama3.2, mistral, phi3
        </p>
      </div>

      <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
        <h3 className="text-lg font-bold mb-4">📦 Установленные модели ({installedModels.length})</h3>
        {installedModels.length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            {ollamaStatus === 'online' ? 'Нет моделей' : 'Ollama не запущена'}
          </p>
        ) : (
          <div className="grid md:grid-cols-2 gap-3">
            {installedModels.map((m, idx) => (
              <div
                key={idx}
                className="flex justify-between items-center p-4 rounded-lg bg-gray-800/50 border border-gray-700"
              >
                <div>
                  <span className="font-mono text-sm text-emerald-400 font-bold">{m.name}</span>
                  <p className="text-xs text-gray-500 mt-1">Размер: {m.size_gb} GB</p>
                </div>
                <button
                  onClick={() => {
                    setConsolePrompt(prev => prev + (prev ? '\n' : '') + `// Использую модель: ${m.name}`);
                    setActiveTab('console');
                  }}
                  className="px-3 py-1.5 rounded bg-gray-700 hover:bg-emerald-500/20 text-gray-300 hover:text-emerald-400 text-xs font-bold"
                >
                  ▶ Использовать
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
