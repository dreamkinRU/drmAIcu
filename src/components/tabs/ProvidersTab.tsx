import { useState, useEffect, useCallback } from 'react';
import { Provider, TabId } from '../../types';

interface ProvidersTabProps {
  providers: Provider[];
  providerFilter: 'all' | 'online' | 'offline';
  setProviderFilter: (filter: 'all' | 'online' | 'offline') => void;
  providerMode: 'ollama' | 'groq' | 'bionic' | 'lmstudio' | 'strata' | 'all';
  setProviderMode: (mode: 'ollama' | 'groq' | 'bionic' | 'lmstudio' | 'strata' | 'all') => void;
  selectedModel: string;
  setSelectedModel: (value: string) => void;
  installedModels: any[];
  bionicUrl?: string;
  setBionicUrl?: (url: string) => void;
  bionicModels?: any[];
  lmstudioUrl?: string;
  setLmstudioUrl?: (url: string) => void;
  lmstudioModels?: any[];
  strataUrl?: string;
  setStrataUrl?: (url: string) => void;
  strataModels?: any[];
  ollamaStatus: 'checking' | 'online' | 'offline';
  ollamaUrl: string;
  setOllamaUrl: (url: string) => void;
  ollamaProcesses: Array<{ name: string; size: number; vram: number }>;
  toggleProvider: (name: string) => void;
  setActiveTab: (tab: TabId) => void;
  installedModelsCount: number;
  newModelName?: string;
  setNewModelName?: (val: string) => void;
  isPulling?: boolean;
  pullModel?: () => void;
}

type ProviderKey = 'ollama' | 'strata' | 'lmstudio' | 'bionic' | 'groq' | 'openrouter' | 'together' | 'huggingface' | 'gemini';

interface ProviderFormState {
  host: string;
  port: string;
  apiKey: string;
  enabled: boolean;
}

interface LiveStatus {
  online: boolean;
  latency: number;
  models: string[];
  error?: string;
}

const PROVIDER_DEFS: Array<{
  id: ProviderKey;
  label: string;
  legacyName: string;
  consoleMode?: 'ollama' | 'strata' | 'lmstudio' | 'bionic' | 'groq';
  defaultHost: string;
  defaultPort: string;
  suffix: string;
  isLocal: boolean;
  needsKey: boolean;
  getKeyUrl?: string;
  fallbackModels?: string[];
}> = [
  { id: 'ollama', label: 'OLLAMA', legacyName: 'Ollama', consoleMode: 'ollama', defaultHost: 'http://localhost', defaultPort: '11434', suffix: '', isLocal: true, needsKey: false },
  { id: 'strata', label: 'STRATA', legacyName: 'Strata', consoleMode: 'strata', defaultHost: 'http://127.0.0.1', defaultPort: '47831', suffix: '/v1', isLocal: true, needsKey: false },
  { id: 'lmstudio', label: 'LM Studio', legacyName: 'LM Studio', consoleMode: 'lmstudio', defaultHost: 'http://localhost', defaultPort: '1234', suffix: '/v1', isLocal: true, needsKey: false },
  { id: 'bionic', label: 'Bionic AI', legacyName: 'Bionic', consoleMode: 'bionic', defaultHost: 'http://localhost', defaultPort: '1235', suffix: '/v1', isLocal: true, needsKey: false },
  { id: 'groq', label: 'Groq', legacyName: 'Groq', consoleMode: 'groq', defaultHost: 'https://api.groq.com/openai/v1', defaultPort: '', suffix: '', isLocal: false, needsKey: true, getKeyUrl: 'https://console.groq.com/keys', fallbackModels: ['llama-3.1-8b-versatile', 'llama-3.1-70b-versatile', 'llama-3.3-70b-versatile'] },
  { id: 'openrouter', label: 'OpenRouter', legacyName: 'OpenRouter', defaultHost: 'https://openrouter.ai/api/v1', defaultPort: '', suffix: '', isLocal: false, needsKey: true, getKeyUrl: 'https://openrouter.ai/keys', fallbackModels: ['meta-llama/llama-3.1-8b-instruct:free', 'qwen/qwen-2.5-coder-32b-instruct:free'] },
  { id: 'together', label: 'Together AI', legacyName: 'Together', defaultHost: 'https://api.together.xyz/v1', defaultPort: '', suffix: '', isLocal: false, needsKey: true, getKeyUrl: 'https://api.together.xyz/settings/api-keys', fallbackModels: ['meta-llama/Llama-3.1-8B-Instruct-Turbo', 'Qwen/Qwen2.5-Coder-32B-Instruct'] },
  { id: 'huggingface', label: 'Hugging Face', legacyName: 'HuggingFace', defaultHost: 'https://api-inference.huggingface.co', defaultPort: '', suffix: '', isLocal: false, needsKey: true, getKeyUrl: 'https://huggingface.co/settings/tokens', fallbackModels: ['meta-llama/Llama-3.1-8B-Instruct', 'Qwen/Qwen2.5-Coder-32B-Instruct'] },
  { id: 'gemini', label: 'Gemini', legacyName: 'Gemini', defaultHost: 'https://generativelanguage.googleapis.com/v1beta', defaultPort: '', suffix: '', isLocal: false, needsKey: true, getKeyUrl: 'https://aistudio.google.com/app/apikey', fallbackModels: ['gemini-1.5-flash', 'gemini-2.0-flash'] },
];

function parseUrlToHostPort(rawUrl: string, defHost: string, defPort: string): { host: string; port: string } {
  if (!rawUrl) return { host: defHost, port: defPort };
  try {
    const u = new URL(rawUrl);
    const host = `${u.protocol}//${u.hostname}`;
    const port = u.port || defPort;
    return { host, port };
  } catch {
    return { host: rawUrl, port: defPort };
  }
}

function buildUrlFromParts(host: string, port: string, suffix: string): string {
  const cleanHost = host.trim().replace(/\/+$/, '');
  if (!cleanHost) return '';
  const cleanPort = port.trim();
  if (!cleanPort) return cleanHost;
  try {
    const u = new URL(cleanHost.includes('://') ? cleanHost : `http://${cleanHost}`);
    return `${u.protocol}//${u.hostname}:${cleanPort}${suffix}`;
  } catch {
    return `${cleanHost}:${cleanPort}${suffix}`;
  }
}

const STORAGE_SETTINGS_KEY = 'drmaicu_provider_settings_v2';

export default function ProvidersTab(props: ProvidersTabProps) {
  const {
    providers, providerMode, setProviderMode, selectedModel, setSelectedModel,
    installedModels, bionicUrl = 'http://localhost:1235/v1', setBionicUrl, bionicModels = [],
    lmstudioUrl = 'http://localhost:1234/v1', setLmstudioUrl, lmstudioModels = [],
    strataUrl = 'http://127.0.0.1:47831/v1', setStrataUrl, strataModels = [],
    ollamaStatus, ollamaUrl, setOllamaUrl, ollamaProcesses,
    toggleProvider, newModelName = '', setNewModelName, isPulling = false, pullModel,
  } = props;

  const [selectedId, setSelectedId] = useState<ProviderKey>('ollama');
  const [showKey, setShowKey] = useState(false);
  const [checkingNow, setCheckingNow] = useState(false);
  const [savedNotice, setSavedNotice] = useState(false);
  const [liveStatuses, setLiveStatuses] = useState<Record<string, LiveStatus>>({});

  const [forms, setForms] = useState<Record<ProviderKey, ProviderFormState>>(() => {
    let saved: Partial<Record<ProviderKey, ProviderFormState>> = {};
    try {
      const raw = localStorage.getItem(STORAGE_SETTINGS_KEY);
      if (raw) saved = JSON.parse(raw);
    } catch {}

    const init = {} as Record<ProviderKey, ProviderFormState>;
    for (const def of PROVIDER_DEFS) {
      if (saved[def.id]) {
        init[def.id] = saved[def.id]!;
        continue;
      }
      let initialUrl = '';
      if (def.id === 'ollama') initialUrl = ollamaUrl;
      else if (def.id === 'strata') initialUrl = strataUrl;
      else if (def.id === 'lmstudio') initialUrl = lmstudioUrl;
      else if (def.id === 'bionic') initialUrl = bionicUrl;

      const parsed = initialUrl
        ? parseUrlToHostPort(initialUrl, def.defaultHost, def.defaultPort)
        : { host: def.defaultHost, port: def.defaultPort };

      const legacy = providers.find(p => p.name.toLowerCase() === def.legacyName.toLowerCase());
      init[def.id] = {
        host: parsed.host,
        port: parsed.port,
        apiKey: legacy?.apiKey || '',
        enabled: legacy ? Boolean(legacy.enabled) : def.isLocal,
      };
    }
    return init;
  });

  const pollStatuses = useCallback(async () => {
    const payload = PROVIDER_DEFS.filter(d => forms[d.id]?.enabled).map(d => {
      const f = forms[d.id];
      return {
        id: d.id,
        url: buildUrlFromParts(f.host, f.port, d.suffix),
        api_key: f.apiKey,
      };
    });
    if (payload.length === 0) return;
    try {
      const res = await fetch('/api/providers/ping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ providers: payload }),
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data?.success && data.statuses) {
        setLiveStatuses(prev => ({ ...prev, ...data.statuses }));
      }
    } catch {}
  }, [forms]);

  useEffect(() => {
    pollStatuses();
    const id = setInterval(pollStatuses, 5000);
    return () => clearInterval(id);
  }, [pollStatuses]);

  const activeDef = PROVIDER_DEFS.find(d => d.id === selectedId) || PROVIDER_DEFS[0];
  const activeForm = forms[selectedId];
  const activeLive = liveStatuses[selectedId];

  const updateFormField = (id: ProviderKey, patch: Partial<ProviderFormState>) => {
    setForms(prev => {
      const next = { ...prev, [id]: { ...prev[id], ...patch } };
      try {
        localStorage.setItem(STORAGE_SETTINGS_KEY, JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  const handleToggleEnabled = (def: typeof PROVIDER_DEFS[number]) => {
    const nextEnabled = !forms[def.id].enabled;
    updateFormField(def.id, { enabled: nextEnabled });
    const legacy = providers.find(p => p.name.toLowerCase() === def.legacyName.toLowerCase());
    if (legacy && Boolean(legacy.enabled) !== nextEnabled) {
      toggleProvider(legacy.name);
    }
  };

  const handleCheckNow = async () => {
    setCheckingNow(true);
    await pollStatuses();
    setCheckingNow(false);
  };

  const handleSaveSettings = async () => {
    try {
      localStorage.setItem(STORAGE_SETTINGS_KEY, JSON.stringify(forms));
    } catch {}

    const fullUrl = buildUrlFromParts(activeForm.host, activeForm.port, activeDef.suffix);
    if (selectedId === 'ollama' && fullUrl) setOllamaUrl(fullUrl);
    if (selectedId === 'strata' && fullUrl && setStrataUrl) setStrataUrl(fullUrl);
    if (selectedId === 'lmstudio' && fullUrl && setLmstudioUrl) setLmstudioUrl(fullUrl);
    if (selectedId === 'bionic' && fullUrl && setBionicUrl) setBionicUrl(fullUrl);

    const cfgUpdates: Record<string, string> = {};
    for (const d of PROVIDER_DEFS) {
      const f = forms[d.id];
      const u = buildUrlFromParts(f.host, f.port, d.suffix);
      if (d.id === 'ollama') cfgUpdates.ollama_url = u;
      if (d.id === 'strata') { cfgUpdates.strata_url = u; if (f.apiKey) cfgUpdates.strata_api_key = f.apiKey; }
      if (d.id === 'lmstudio') { cfgUpdates.lmstudio_url = u; if (f.apiKey) cfgUpdates.lmstudio_api_key = f.apiKey; }
      if (d.id === 'bionic') { cfgUpdates.bionic_url = u; if (f.apiKey) cfgUpdates.bionic_api_key = f.apiKey; }
      if (d.id === 'groq') cfgUpdates.groq_api_key = f.apiKey;
      if (d.id === 'openrouter') cfgUpdates.openrouter_api_key = f.apiKey;
      if (d.id === 'together') cfgUpdates.together_api_key = f.apiKey;
      if (d.id === 'huggingface') cfgUpdates.hf_api_key = f.apiKey;
      if (d.id === 'gemini') cfgUpdates.gemini_api_key = f.apiKey;
    }

    try {
      await fetch('/api/providers/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: cfgUpdates }),
      });
    } catch {}

    setSavedNotice(true);
    setTimeout(() => setSavedNotice(false), 2000);
    await pollStatuses();
  };

  const getProviderStatusBadge = (def: typeof PROVIDER_DEFS[number]) => {
    const f = forms[def.id];
    if (!f?.enabled) {
      return { text: 'Выкл', dot: 'bg-gray-500', badge: 'bg-gray-800 border-gray-700 text-gray-400', online: false };
    }
    const live = liveStatuses[def.id];
    const isOnline = live ? live.online : def.id === 'ollama' ? ollamaStatus === 'online' : false;
    if (isOnline) {
      return {
        text: 'Онлайн',
        dot: 'bg-emerald-400 animate-pulse',
        badge: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300',
        online: true,
      };
    }
    return {
      text: 'Оффлайн',
      dot: 'bg-red-400',
      badge: 'bg-red-500/15 border-red-500/40 text-red-300',
      online: false,
    };
  };

  const getModelsForSelected = (): Array<{ name: string; sizeLabel?: string }> => {
    if (selectedId === 'ollama') {
      if (installedModels && installedModels.length > 0) {
        return installedModels.map((m: any) => ({
          name: m.name || String(m),
          sizeLabel: m.size_gb ? `${m.size_gb} GB RAM` : undefined,
        }));
      }
      return (activeLive?.models || []).map(name => ({ name }));
    }
    if (selectedId === 'strata') {
      const list = (activeLive?.models?.length ? activeLive.models : strataModels.map((m: any) => m.name || m));
      return list.map(name => ({ name }));
    }
    if (selectedId === 'lmstudio') {
      const list = (activeLive?.models?.length ? activeLive.models : lmstudioModels.map((m: any) => m.name || m));
      return list.map(name => ({ name }));
    }
    if (selectedId === 'bionic') {
      const list = (activeLive?.models?.length ? activeLive.models : bionicModels.map((m: any) => m.name || m));
      return list.map(name => ({ name }));
    }
    const remote = activeLive?.models?.length ? activeLive.models : (activeDef.fallbackModels || []);
    return remote.map(name => ({ name }));
  };

  const modelsList = getModelsForSelected();

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      {/* Левая колонка: список провайдеров */}
      <div className="lg:col-span-5 space-y-3">
        <div className="flex items-center justify-between px-1 mb-2">
          <div className="flex items-center gap-2">
            <span className="text-lg">🌐</span>
            <h2 className="text-lg font-bold text-white">Провайдеры</h2>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-gray-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Автообновление: 5с</span>
          </div>
        </div>

        <div className="space-y-2.5">
          {PROVIDER_DEFS.map(def => {
            const isSelected = def.id === selectedId;
            const f = forms[def.id];
            const st = getProviderStatusBadge(def);
            return (
              <div
                key={def.id}
                onClick={() => setSelectedId(def.id)}
                className={`flex items-center justify-between px-4 py-3.5 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? 'border-cyan-400/80 bg-cyan-950/20 shadow-[0_0_16px_rgba(34,211,238,0.18)]'
                    : 'border-gray-800 bg-gray-900/60 hover:border-gray-700'
                } ${!f.enabled ? 'opacity-65' : ''}`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${st.dot}`} />
                  <span className="font-bold text-white text-sm truncate">{def.label}</span>
                </div>

                <div className="flex items-center gap-3 shrink-0" onClick={(e) => e.stopPropagation()}>
                  <span className={`px-2.5 py-0.5 rounded-md text-xs font-semibold border ${st.badge}`}>
                    {st.text}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleToggleEnabled(def)}
                    className={`w-11 h-6 rounded-full transition-all relative ${f.enabled ? 'bg-cyan-500' : 'bg-gray-700'}`}
                    title={f.enabled ? 'Выключить провайдера' : 'Включить провайдера'}
                  >
                    <span
                      className="w-4 h-4 rounded-full bg-white absolute top-1 transition-all shadow"
                      style={{ left: f.enabled ? '24px' : '4px' }}
                    />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Правая колонка: настройки подключения + модели выбранного провайдера */}
      <div className="lg:col-span-7 space-y-5">
        {/* Карточка подключения */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/70 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-base">🔌</span>
              <h3 className="text-base font-bold text-white">Подключение и статус — {activeDef.label}</h3>
            </div>
            {activeLive?.online && activeLive.latency > 0 && (
              <span className="text-xs font-mono text-emerald-400">{activeLive.latency} ms</span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
            <div className={activeDef.isLocal ? 'sm:col-span-8' : 'sm:col-span-12'}>
              <label className="block text-xs text-gray-400 mb-1.5">Хост / URL API</label>
              <input
                type="text"
                value={activeForm.host}
                onChange={(e) => updateFormField(selectedId, { host: e.target.value })}
                placeholder={activeDef.defaultHost}
                className="w-full px-3.5 py-2.5 rounded-lg bg-gray-950/80 border border-gray-700 text-white text-sm font-mono focus:border-cyan-500 focus:outline-none"
              />
            </div>

            {activeDef.isLocal && (
              <div className="sm:col-span-4">
                <label className="block text-xs text-gray-400 mb-1.5">Порт</label>
                <input
                  type="text"
                  value={activeForm.port}
                  onChange={(e) => updateFormField(selectedId, { port: e.target.value })}
                  placeholder={activeDef.defaultPort}
                  className="w-full px-3.5 py-2.5 rounded-lg bg-gray-950/80 border border-gray-700 text-white text-sm font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs text-gray-400">API-ключ {activeDef.needsKey ? '(обязателен)' : '(опционально)'}</label>
              {activeDef.getKeyUrl && (
                <a href={activeDef.getKeyUrl} target="_blank" rel="noreferrer" className="text-xs text-cyan-400 hover:underline">
                  Получить ключ →
                </a>
              )}
            </div>
            <div className="relative">
              <input
                type={showKey ? 'text' : 'password'}
                value={activeForm.apiKey}
                onChange={(e) => updateFormField(selectedId, { apiKey: e.target.value })}
                placeholder={activeDef.needsKey ? 'sk-...' : 'Не требуется для локального сервера'}
                className="w-full px-3.5 py-2.5 pr-10 rounded-lg bg-gray-950/80 border border-gray-700 text-white text-sm font-mono focus:border-cyan-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowKey(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400 hover:text-white"
                title="Показать / скрыть ключ"
              >
                {showKey ? '🙈' : '👁'}
              </button>
            </div>
          </div>

          {activeLive?.error && activeForm.enabled && !activeLive.online && (
            <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 font-mono">
              Ошибка подключения: {activeLive.error}
            </div>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-gray-800">
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-300 font-semibold">Включен</span>
              <button
                type="button"
                onClick={() => handleToggleEnabled(activeDef)}
                className={`w-11 h-6 rounded-full transition-all relative ${activeForm.enabled ? 'bg-cyan-500' : 'bg-gray-700'}`}
              >
                <span
                  className="w-4 h-4 rounded-full bg-white absolute top-1 transition-all shadow"
                  style={{ left: activeForm.enabled ? '24px' : '4px' }}
                />
              </button>
              {savedNotice && <span className="text-xs text-emerald-400 font-semibold">✓ Сохранено</span>}
            </div>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={handleCheckNow}
                disabled={checkingNow}
                className="px-3.5 py-2 rounded-lg text-xs font-bold bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 disabled:opacity-50"
              >
                {checkingNow ? '⏳ Проверка...' : '🔍 Проверить'}
              </button>
              <button
                type="button"
                onClick={handleSaveSettings}
                className="px-4 py-2 rounded-lg text-xs font-bold bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-500/20"
              >
                💾 Сохранить
              </button>
            </div>
          </div>
        </div>

        {/* Карточка доступных моделей */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/70 p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-base">🤖</span>
              <h3 className="text-base font-bold text-white">
                {activeDef.isLocal ? 'Доступные локальные модели' : 'Доступные модели'}
              </h3>
            </div>
            <span className="text-xs text-gray-400 font-mono">{modelsList.length} шт.</span>
          </div>

          {selectedId === 'ollama' && ollamaProcesses.length > 0 && (
            <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-3 py-2">
              В памяти GPU/RAM: {ollamaProcesses.map(m => `${m.name} (${m.vram}MB VRAM)`).join(' • ')}
            </div>
          )}

          <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
            {modelsList.length === 0 ? (
              <div className="text-center py-6 text-xs text-gray-500 border border-dashed border-gray-800 rounded-lg">
                Модели не обнаружены. Убедитесь, что сервер запущен и включён.
              </div>
            ) : (
              modelsList.map(m => {
                const isCurrentActive =
                  Boolean(activeDef.consoleMode) &&
                  providerMode === activeDef.consoleMode &&
                  selectedModel === m.name;
                return (
                  <div
                    key={m.name}
                    className={`flex items-center justify-between px-3.5 py-2.5 rounded-lg border transition-all ${
                      isCurrentActive
                        ? 'border-emerald-500/50 bg-emerald-500/10'
                        : 'border-gray-800 bg-gray-950/60 hover:border-gray-700'
                    }`}
                  >
                    <span className="font-mono text-sm text-white truncate pr-3">{m.name}</span>
                    <div className="flex items-center gap-3 shrink-0">
                      {isCurrentActive ? (
                        <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/20 border border-emerald-500/50 text-emerald-300">
                          Активна
                        </span>
                      ) : activeDef.consoleMode ? (
                        <button
                          type="button"
                          onClick={() => {
                            setProviderMode(activeDef.consoleMode!);
                            setSelectedModel(m.name);
                          }}
                          className="px-3 py-1 rounded-md text-xs font-semibold bg-gray-800 hover:bg-cyan-500/20 border border-gray-700 hover:border-cyan-500/50 text-gray-200"
                        >
                          Выбрать
                        </button>
                      ) : null}
                      {m.sizeLabel && (
                        <span className="text-xs font-mono text-gray-400 w-20 text-right">{m.sizeLabel}</span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {selectedId === 'ollama' && setNewModelName && pullModel && (
            <div className="pt-3 border-t border-gray-800 flex gap-2">
              <input
                type="text"
                value={newModelName}
                onChange={(e) => setNewModelName(e.target.value)}
                placeholder="Скачать модель Ollama (например: qwen2.5-coder:7b)"
                className="flex-1 px-3 py-2 rounded-lg bg-gray-950/80 border border-gray-700 text-white text-xs font-mono focus:border-emerald-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={pullModel}
                disabled={isPulling || !newModelName.trim()}
                className="px-3.5 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50"
              >
                {isPulling ? '⏳ Загрузка...' : '⬇ Скачать'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
