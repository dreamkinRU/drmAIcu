import { Provider } from '../../types';
import { TabId } from '../../types';

interface ProvidersTabProps {
  providers: Provider[];
  providerFilter: 'all' | 'online' | 'offline';
  setProviderFilter: (filter: 'all' | 'online' | 'offline') => void;
  ollamaStatus: 'checking' | 'online' | 'offline';
  ollamaUrl: string;
  setOllamaUrl: (url: string) => void;
  ollamaProcesses: Array<{ name: string; size: number; vram: number }>;
  toggleProvider: (name: string) => void;
  setActiveTab: (tab: TabId) => void;
  installedModelsCount: number;
}

export default function ProvidersTab({
  providers, providerFilter, setProviderFilter,
  ollamaStatus, ollamaUrl, setOllamaUrl, ollamaProcesses,
  toggleProvider, setActiveTab, installedModelsCount,
}: ProvidersTabProps) {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Провайдеры</h2>
        <div className="flex gap-2">
          {(['all', 'online', 'offline'] as const).map(f => (
            <button
              key={f}
              onClick={() => setProviderFilter(f)}
              className={`px-3 py-2 rounded-lg text-sm font-bold ${
                providerFilter === f
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                  : 'bg-gray-800 text-gray-400 border border-gray-700'
              }`}
            >
              {f === 'all' ? 'Все' : f === 'online' ? 'Онлайн' : 'Оффлайн'}
            </button>
          ))}
        </div>
      </div>

      <div
        className={`rounded-xl border-2 p-6 transition-all ${
          ollamaStatus === 'online'
            ? 'border-emerald-500/30 bg-emerald-500/5'
            : 'border-red-500/20 bg-red-500/5'
        }`}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div
              className={`w-4 h-4 rounded-full ${
                ollamaStatus === 'online' ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
              }`}
            />
            <div>
              <span className="text-lg font-bold text-white">Ollama</span>
              <span className="text-sm text-gray-400 ml-3">
                — {providers.find(p => p.name === 'Ollama')?.description}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => navigator.clipboard.writeText('ollama serve')}
              className="px-3 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-xs font-bold"
            >
              ▶ Запуск
            </button>
            <button
              onClick={() => setActiveTab('models')}
              className="flex items-center gap-2 px-2 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-purple-500/50 transition-all"
            >
              <span className="text-xl">🧠</span>
              <div className="text-left">
                <p className="text-[10px] text-gray-500">Модели</p>
                <div className="flex items-baseline gap-1">
                  <span className="font-bold text-purple-400 text-lg">{installedModelsCount}</span>
                </div>
              </div>
            </button>
          </div>
        </div>
        <input
          type="text"
          value={ollamaUrl}
          onChange={(e) => setOllamaUrl(e.target.value)}
          className="w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono mb-3"
        />
        {ollamaProcesses.length > 0 && (
          <div className="text-sm text-gray-400">
            Запущено: {ollamaProcesses.map(m => `${m.name} (${m.size}MB RAM, ${m.vram}MB VRAM)`).join(' • ')}
          </div>
        )}
      </div>

      <div className="space-y-3">
        {providers
          .filter(p => p.name !== 'Ollama')
          .filter(p =>
            providerFilter === 'all' ||
            (providerFilter === 'online' ? p.status === 'online' : p.status !== 'online')
          )
          .map(provider => (
            <div
              key={provider.name}
              className={`rounded-xl border p-4 transition-all ${
                provider.enabled
                  ? 'border-gray-700 bg-gray-900/50'
                  : 'border-gray-800 bg-gray-900/30 opacity-60'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      provider.status === 'online'
                        ? 'bg-emerald-400 animate-pulse'
                        : provider.status === 'error'
                        ? 'bg-red-400'
                        : 'bg-gray-600'
                    }`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-white text-base">{provider.name}</span>
                      <span className="text-sm text-gray-400 truncate">{provider.description}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <span className="text-sm text-gray-400">
                    {provider.latency > 0 ? `${provider.latency}ms` : '—'}
                  </span>
                  <span className="text-sm text-gray-400">
                    {provider.models > 0 ? provider.models : '—'} моделей
                  </span>
                  <button
                    onClick={() => toggleProvider(provider.name)}
                    className={`w-12 h-6 rounded-full transition-all relative ${
                      provider.enabled ? 'bg-emerald-500' : 'bg-gray-700'
                    }`}
                  >
                    <div
                      className="w-5 h-5 rounded-full bg-white absolute top-0.5 transition-all"
                      style={{ left: provider.enabled ? '26px' : '2px' }}
                    />
                  </button>
                </div>
              </div>
              {provider.enabled && provider.apiKey !== undefined && (
                <div className="flex gap-3 items-center mt-3">
                  <input
                    type="password"
                    placeholder="API Key"
                    defaultValue={provider.apiKey}
                    className="flex-1 max-w-xs px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm"
                  />
                  {provider.getKeyUrl && (
                    <a
                      href={provider.getKeyUrl}
                      target="_blank"
                      className="text-sm text-cyan-400 hover:text-cyan-300 whitespace-nowrap"
                    >
                      Получить ключ →
                    </a>
                  )}
                </div>
              )}
            </div>
          ))}
      </div>
    </div>
  );
}
