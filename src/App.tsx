import { useState, useEffect } from 'react';

// ===== ТИПЫ =====
interface Agent {
  id: number;
  name: string;
  status: 'active' | 'frozen' | 'offline';
  task: string;
  stack: string[];
  progress: number;
  lastActivity: string;
  enabled: boolean;
  description: string;
}

interface Provider {
  name: string;
  status: 'online' | 'offline' | 'error';
  latency: number;
  models: number;
  description: string;
  url: string;
  enabled: boolean;
  apiKey?: string;
}

interface LogEntry {
  time: string;
  level: 'info' | 'warn' | 'error' | 'success';
  message: string;
  source: string;
  details?: string;
}

interface CodeIssue {
  id: number;
  severity: 'critical' | 'warning' | 'info';
  line: string;
  title: string;
  description: string;
  fix: string;
  before: string;
  after: string;
  file: string;
  fixed: boolean;
}

interface Task {
  id: number;
  text: string;
  done: boolean;
  priority: 'high' | 'medium' | 'low';
}

// ===== ДАННЫЕ =====
const initialAgents: Agent[] = [
  { id: 1, name: 'Агент №1 — Развитие системы', status: 'active', task: 'Исправление ошибок компиляции и импорта модулей', stack: ['Java', 'Python', 'VBA/Excel'], progress: 45, lastActivity: '2 мин назад', enabled: true, description: 'Основной агент для развития инфраструктуры drmAIcu. Специализируется на Java/Python разработке, VBA/Excel автоматизации. Отвечает за исправление ошибок, оптимизацию кода и внедрение новых функций.' },
  { id: 2, name: 'Агент №2 — Аналитика данных', status: 'frozen', task: 'На паузе', stack: ['Python', 'Pandas', 'SQL'], progress: 0, lastActivity: '—', enabled: false, description: 'Агент для анализа данных и построения отчётов. Работает с большими объёмами данных, создаёт визуализации, выполняет статистический анализ. Использует Pandas, NumPy, SQL для обработки данных.' },
  { id: 3, name: 'Агент №3 — Автоматизация отчётов', status: 'frozen', task: 'На паузе', stack: ['Python', 'Excel VBA', 'TTS'], progress: 0, lastActivity: '—', enabled: false, description: 'Агент для автоматизации создания отчётов и голосовых уведомлений. Генерирует Excel-отчёты, создаёт презентации, озвучивает результаты через TTS. Интегрируется с Excel VBA и системами голосового синтеза.' },
];

const agentStore = [
  { id: 'agent-ml', name: 'Агент ML — Машинное обучение', description: 'Специализируется на машинном обучении, нейронных сетях, обработке изображений и NLP.', stack: ['Python', 'TensorFlow', 'PyTorch', 'Scikit-learn'], category: 'AI/ML', price: 'Бесплатно' },
  { id: 'agent-web', name: 'Агент Web — Веб-разработка', description: 'Full-stack веб-разработчик. React, Node.js, базы данных, API.', stack: ['JavaScript', 'React', 'Node.js', 'PostgreSQL'], category: 'Web', price: 'Бесплатно' },
  { id: 'agent-devops', name: 'Агент DevOps — Инфраструктура', description: 'Автоматизация развёртывания, CI/CD, контейнеризация, мониторинг.', stack: ['Docker', 'Kubernetes', 'Jenkins', 'Terraform'], category: 'DevOps', price: 'Бесплатно' },
  { id: 'agent-security', name: 'Агент Security — Безопасность', description: 'Аудит безопасности, пентестинг, анализ уязвимостей, шифрование.', stack: ['Python', 'OWASP', 'Metasploit', 'Cryptography'], category: 'Security', price: 'Премиум' },
  { id: 'agent-mobile', name: 'Агент Mobile — Мобильная разработка', description: 'Разработка мобильных приложений для iOS и Android.', stack: ['React Native', 'Flutter', 'Swift', 'Kotlin'], category: 'Mobile', price: 'Бесплатно' },
];

const initialProviders: Provider[] = [
  { name: 'Ollama', status: 'offline', latency: 0, models: 0, description: 'Локальные модели. Работает без интернета. Требует установки Ollama.', url: 'http://localhost:11434', enabled: true },
  { name: 'Groq', status: 'online', latency: 23, models: 8, description: 'Быстрые облачные модели. Бесплатный тариф доступен.', url: 'https://console.groq.com', enabled: true, apiKey: '' },
  { name: 'HuggingFace', status: 'online', latency: 120, models: 150, description: 'Огромная библиотека моделей. Бесплатные и платные варианты.', url: 'https://huggingface.co', enabled: true, apiKey: '' },
  { name: 'OpenRouter', status: 'online', latency: 89, models: 45, description: 'Агрегатор моделей. Доступ к GPT-4, Claude и другим.', url: 'https://openrouter.ai', enabled: true, apiKey: '' },
  { name: 'Gemini', status: 'offline', latency: 0, models: 0, description: 'Google Gemini. Требуется API ключ от Google AI Studio.', url: 'https://makersuite.google.com', enabled: false, apiKey: '' },
  { name: 'Together', status: 'error', latency: 0, models: 0, description: 'Together AI. Ошибка подключения. Проверьте API ключ.', url: 'https://api.together.xyz', enabled: false, apiKey: '' },
];

const initialLogs: LogEntry[] = [
  { time: '14:32:01', level: 'info', message: 'ЦУ v3.2.0 FORTRESS запущена', source: 'main.py', details: 'Система инициализирована успешно' },
  { time: '14:32:03', level: 'success', message: 'Агент №1 инициализирован', source: 'agent_engine.py', details: 'Все модули загружены' },
  { time: '14:32:05', level: 'warn', message: 'OSError: [Errno 22] в py_compile.compile', source: 'main.py', details: 'Строка ~160. Решение: использовать tempfile.mkstemp() вместо NamedTemporaryFile' },
  { time: '14:32:07', level: 'error', message: 'drm.cls could not be loaded', source: 'mod_Core', details: 'Bad file name or number. Проверьте путь к временным файлам' },
  { time: '14:32:10', level: 'info', message: 'Провайдер Ollama подключен', source: 'agent_engine.py', details: '12 моделей доступно' },
];

const initialCodeIssues: CodeIssue[] = [
  { id: 1, severity: 'critical', line: '113', file: 'agent_engine.py', title: 'asyncio.get_event_loop() — deprecated', description: 'В Python 3.10+ get_event_loop() вызывает DeprecationWarning', fix: 'Заменить на asyncio.get_running_loop()', before: 'loop = asyncio.get_event_loop()', after: 'loop = asyncio.get_running_loop()', fixed: false },
  { id: 2, severity: 'critical', line: '126-145', file: 'agent_engine.py', title: 'Gemini: потеря контекста диалога', description: 'Берётся только messages[-1] — весь системный промпт игнорируется', fix: 'Конвертировать все messages в формат Gemini', before: 'prompt_text = messages[-1][\'content\']', after: 'contents = messages.map(m => ({role: m.role, parts: [{text: m.content}]}))', fixed: false },
  { id: 3, severity: 'warning', line: '83-93', file: 'agent_engine.py', title: 'HuggingFace: клиент есть, метода запроса нет', description: 'HF инициализирован как dict, но в _query_model нет ветки для huggingface', fix: 'Добавить _query_huggingface и модели в _get_candidates', before: '// Нет метода', after: 'async _query_huggingface(model, messages, timeout)', fixed: false },
];

const initialTasks: Task[] = [
  { id: 1, text: 'Исправить py_compile ошибку в main.py', done: false, priority: 'high' },
  { id: 2, text: 'Исправить импорт VBA-модулей в mod_Core', done: false, priority: 'high' },
  { id: 3, text: 'Реализовать модуль TTS для голосовых отчётов', done: false, priority: 'medium' },
  { id: 4, text: 'Тестирование мульти-провайдеров', done: true, priority: 'low' },
];

// ===== КОМПОНЕНТЫ =====
function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    frozen: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    offline: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    online: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  const labels: Record<string, string> = {
    active: 'АКТИВЕН', frozen: 'ЗАМОРОЖЕН', offline: 'ОФФЛАЙН', online: 'ОНЛАЙН', error: 'ОШИБКА',
  };
  return <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${colors[status] || colors.offline}`}>{labels[status] || status.toUpperCase()}</span>;
}

function InfoPanel({ icon, title, items }: { icon: string; title: string; items: string[] }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-4">
      <h3 className="text-sm font-bold text-gray-300 mb-2 flex items-center gap-2">
        <span className="text-lg">{icon}</span> {title}
      </h3>
      <ul className="space-y-1 text-xs text-gray-400">
        {items.map((item, i) => <li key={i}>• {item}</li>)}
      </ul>
    </div>
  );
}

export default function App() {
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [providers, setProviders] = useState<Provider[]>(initialProviders);
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs);
  const [codeIssues, setCodeIssues] = useState<CodeIssue[]>(initialCodeIssues);
  const [taskList, setTaskList] = useState<Task[]>(initialTasks);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [activeTab, setActiveTab] = useState<'console' | 'dashboard' | 'agents' | 'providers' | 'md' | 'code' | 'logs' | 'tasks'>('console');
  const [expandedIssues, setExpandedIssues] = useState<Set<number>>(new Set([1]));
  const [analyzedFile, setAnalyzedFile] = useState<'engine' | 'main' | 'launcher'>('engine');
  
  // Console state
  const [groqKey, setGroqKey] = useState('');
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'all'>('all');
  const [consolePrompt, setConsolePrompt] = useState('');
  const [consoleResponses, setConsoleResponses] = useState<Array<{model: string, response: string, time: number}>>([]);
  const [judgeResult, setJudgeResult] = useState<{winner: string, reason: string, code: string} | null>(null);
  const [consoleLoading, setConsoleLoading] = useState(false);
  const [consoleError, setConsoleError] = useState('');
  
  // Agent state
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [showAgentStore, setShowAgentStore] = useState(false);
  
  // Provider state
  const [providerFilter, setProviderFilter] = useState<'all' | 'online' | 'offline'>('all');
  const [ollamaStatus, setOllamaStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [systemStats, setSystemStats] = useState({ ram: 0, vram: 0 });
  
  // MD Editor state
  const [mdContent, setMdContent] = useState('# drmAIcu v3.2.0\n\nОписание проекта...');
  const [mdFileName, setMdFileName] = useState('README.md');
  const [aiSuggestions, setAiSuggestions] = useState<string[]>([]);
  
  // Ollama control
  const [ollamaRunning, setOllamaRunning] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Проверка Ollama
  useEffect(() => {
    const checkOllama = async () => {
      try {
        const res = await fetch(`${ollamaUrl}/api/tags`, { method: 'GET' });
        if (res.ok) {
          setOllamaStatus('online');
          setOllamaRunning(true);
          const data = await res.json();
          setProviders(prev => prev.map(p => p.name === 'Ollama' ? { ...p, status: 'online', models: data.models?.length || 0 } : p));
        } else {
          setOllamaStatus('offline');
          setOllamaRunning(false);
          setProviders(prev => prev.map(p => p.name === 'Ollama' ? { ...p, status: 'offline', models: 0 } : p));
        }
      } catch {
        setOllamaStatus('offline');
        setOllamaRunning(false);
        setProviders(prev => prev.map(p => p.name === 'Ollama' ? { ...p, status: 'offline', models: 0 } : p));
      }
    };
    checkOllama();
    const interval = setInterval(checkOllama, 5000);
    return () => clearInterval(interval);
  }, [ollamaUrl]);

  // Мониторинг системы
  useEffect(() => {
    const checkStats = async () => {
      try {
        const res = await fetch(`${ollamaUrl}/api/ps`);
        if (res.ok) {
          const data = await res.json();
          const ram = data.models?.reduce((sum: number, m: any) => sum + (m.size_vram || 0), 0) || 0;
          setSystemStats({ ram: Math.round(ram / 1024 / 1024), vram: Math.round(ram / 1024 / 1024) });
        }
      } catch {}
    };
    checkStats();
    const interval = setInterval(checkStats, 5000);
    return () => clearInterval(interval);
  }, [ollamaUrl]);

  const toggleTask = (id: number) => setTaskList(prev => prev.map(t => t.id === id ? { ...t, done: !t.done } : t));
  const toggleIssue = (id: number) => setExpandedIssues(prev => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const toggleAgent = (id: number) => setAgents(prev => prev.map(a => a.id === id ? { ...a, enabled: !a.enabled, status: !a.enabled ? 'active' : 'frozen' } : a));
  
  const importAgent = (agentId: string) => {
    const storeAgent = agentStore.find(a => a.id === agentId);
    if (storeAgent) {
      const newAgent: Agent = { id: agents.length + 1, name: storeAgent.name, status: 'frozen', task: 'Готов к активации', stack: storeAgent.stack, progress: 0, lastActivity: 'Только что', enabled: false, description: storeAgent.description };
      setAgents(prev => [...prev, newAgent]);
      setShowAgentStore(false);
    }
  };

  const toggleProvider = (name: string) => setProviders(prev => prev.map(p => p.name === name ? { ...p, enabled: !p.enabled } : p));
  
  const fixCodeIssue = async (issueId: number) => {
    const issue = codeIssues.find(i => i.id === issueId);
    if (!issue) return;
    
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'info', message: `Исправление: ${issue.title}`, source: 'AI-Guardian', details: `Файл: ${issue.file}, строка: ${issue.line}` }]);
    
    // Симуляция исправления через AI-Guardian
    setTimeout(() => {
      setCodeIssues(prev => prev.map(i => i.id === issueId ? { ...i, fixed: true } : i));
      setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'success', message: `Исправлено: ${issue.title}`, source: 'AI-Guardian', details: 'Патч применён успешно' }]);
    }, 1000);
  };

  const fixAllIssues = async () => {
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'info', message: 'Массовое исправление ошибок', source: 'AI-Guardian', details: `Всего проблем: ${codeIssues.filter(i => !i.fixed).length}` }]);
    
    for (const issue of codeIssues.filter(i => !i.fixed)) {
      await fixCodeIssue(issue.id);
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  };

  const completedTasks = taskList.filter(t => t.done).length;

  const tabs = [
    { id: 'console' as const, label: 'Консоль', icon: '▶' },
    { id: 'dashboard' as const, label: 'Панель', icon: '◈' },
    { id: 'agents' as const, label: 'Агенты', icon: '🤖' },
    { id: 'providers' as const, label: 'Провайдеры', icon: '🌐' },
    { id: 'md' as const, label: 'MD', icon: '📝' },
    { id: 'code' as const, label: 'Анализ кода', icon: '⟨⟩', badge: codeIssues.filter(i => !i.fixed).length },
    { id: 'logs' as const, label: 'Логи', icon: '▤' },
    { id: 'tasks' as const, label: 'Задачи', icon: '☑' },
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 via-cyan-500 to-blue-500 flex items-center justify-center font-bold text-sm shadow-lg shadow-emerald-500/30 animate-glow">AI</div>
            <div>
              <h1 className="text-lg font-bold tracking-tight gradient-text">drmAIcu</h1>
              <p className="text-[10px] text-gray-500">v3.2.0 FORTRESS • Ollama + Groq • 2026</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <a href="/fixed-code.html" target="_blank" className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-bold transition-all shadow-lg shadow-emerald-500/20 whitespace-nowrap inline-flex items-center gap-1.5">📦 Скачать код</a>
            <div className="hidden sm:flex items-center gap-2 text-xs text-gray-400">
              <div className={`w-2 h-2 rounded-full ${ollamaStatus === 'online' ? 'bg-emerald-400 animate-pulse' : 'bg-gray-600'}`} />
              <span>Система активна</span>
            </div>
            <div className="font-mono text-sm text-gray-300">{currentTime.toLocaleTimeString('ru-RU')}</div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-gray-800 bg-gray-900/50 sticky top-[61px] z-40">
        <div className="max-w-7xl mx-auto px-4 flex items-center gap-1 overflow-x-auto">
          {tabs.map((tab) => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-all whitespace-nowrap flex items-center gap-1.5 ${activeTab === tab.id ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-gray-500 hover:text-gray-300'}`}>
              <span>{tab.icon}</span>{tab.label}
              {tab.badge && <span className="px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 text-[10px] font-bold">{tab.badge}</span>}
            </button>
          ))}
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* ===== CONSOLE ===== */}
        {activeTab === 'console' && (
          <div className="space-y-6">
            <InfoPanel icon="💬" title="Консоль" items={['Отправка запросов к LLM моделям', 'Параллельный опрос нескольких моделей', 'Арбитр выбирает лучший ответ', 'Поддержка Ollama + Groq']} />
            {/* Provider Selection */}
            <div className="rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-5 shadow-xl card-hover">
              <label className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-3 block">🎯 Провайдеры моделей</label>
              <div className="flex gap-2 mb-4">
                <button onClick={() => setProviderMode('ollama')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'ollama' ? 'bg-gradient-to-br from-emerald-500/30 to-emerald-600/20 border-emerald-500 text-emerald-300 shadow-lg shadow-emerald-500/20' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-600'}`}>🏠 Только Ollama</button>
                <button onClick={() => setProviderMode('groq')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'groq' ? 'bg-gradient-to-br from-cyan-500/30 to-cyan-600/20 border-cyan-500 text-cyan-300 shadow-lg shadow-cyan-500/20' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-600'}`}>☁️ Только Groq</button>
                <button onClick={() => setProviderMode('all')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'all' ? 'bg-gradient-to-br from-purple-500/30 to-pink-600/20 border-purple-500 text-purple-300 shadow-lg shadow-purple-500/20' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-600'}`}>⚡ Все (Ollama + Groq)</button>
              </div>
              {(providerMode === 'ollama' || providerMode === 'all') && (
                <div className="mb-3">
                  <label className="text-xs text-gray-500 mb-1 block">Ollama URL</label>
                  <div className="flex gap-2">
                    <input type="text" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} placeholder="http://localhost:11434" className="flex-1 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none font-mono" />
                    <span className={`px-3 py-2 rounded-lg border text-xs flex items-center ${ollamaStatus === 'online' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-red-500/10 border-red-500/30 text-red-400'}`}>{ollamaStatus === 'online' ? '🏠 Онлайн' : '❌ Оффлайн'}</span>
                  </div>
                </div>
              )}
              {(providerMode === 'groq' || providerMode === 'all') && (
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Groq API Key</label>
                  <div className="flex gap-2">
                    <input type="password" value={groqKey} onChange={(e) => setGroqKey(e.target.value)} placeholder="gsk_..." className="flex-1 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-cyan-500 focus:outline-none" />
                    <a href="https://console.groq.com/keys" target="_blank" className="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 text-xs hover:text-white transition-all">Получить ключ →</a>
                  </div>
                </div>
              )}
            </div>
            {/* Prompt */}
            <div className="rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-5 shadow-xl card-hover">
              <label className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2 block">💬 Запрос</label>
              <textarea value={consolePrompt} onChange={(e) => setConsolePrompt(e.target.value)} placeholder="Опиши задачу для нейросети..." rows={4} className="w-full px-4 py-3 rounded-lg bg-gray-800/80 border-2 border-gray-700 text-white text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 focus:outline-none resize-none font-mono transition-all" />
              <div className="flex items-center justify-between mt-4">
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <span className="px-2 py-1 rounded bg-emerald-500/10 text-emerald-400">🚀 {providerMode === 'ollama' ? '2 локальные' : providerMode === 'groq' ? '3 облачные' : '5 моделей'}</span>
                  <span className="px-2 py-1 rounded bg-cyan-500/10 text-cyan-400">⚖️ Арбитр выберет лучший</span>
                </div>
                <button onClick={() => {}} disabled={consoleLoading} className={`px-8 py-3 rounded-lg font-bold text-sm transition-all ${consoleLoading ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white shadow-xl shadow-emerald-500/30 hover:scale-105'}`}>{consoleLoading ? '⏳ Отправка...' : '▶ Отправить'}</button>
              </div>
            </div>
          </div>
        )}

        {/* ===== DASHBOARD ===== */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            <InfoPanel icon="◈" title="Панель управления" items={['Общая статистика системы', 'Активные агенты и провайдеры', 'Выполненные задачи', 'Обнаруженные проблемы']} />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 card-hover">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Агенты</p>
                <p className="text-2xl font-bold text-emerald-400">{agents.filter(a => a.enabled).length}<span className="text-sm text-gray-500">/{agents.length}</span></p>
                <p className="text-[10px] text-gray-500 mt-1">включено</p>
              </div>
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 card-hover">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Провайдеры</p>
                <p className="text-2xl font-bold text-cyan-400">{providers.filter(p => p.enabled && p.status === 'online').length}<span className="text-sm text-gray-500">/{providers.length}</span></p>
                <p className="text-[10px] text-gray-500 mt-1">онлайн</p>
              </div>
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 card-hover">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Задачи</p>
                <p className="text-2xl font-bold text-yellow-400">{completedTasks}<span className="text-sm text-gray-500">/{taskList.length}</span></p>
                <p className="text-[10px] text-gray-500 mt-1">выполнено</p>
              </div>
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 card-hover">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Баги</p>
                <p className="text-2xl font-bold text-red-400">{codeIssues.filter(i => !i.fixed).length}</p>
                <p className="text-[10px] text-gray-500 mt-1">требуют исправления</p>
              </div>
            </div>
          </div>
        )}

        {/* ===== AGENTS ===== */}
        {activeTab === 'agents' && (
          <div className="space-y-6">
            <InfoPanel icon="🤖" title="Управление агентами" items={['Включение/выключение агентов', 'Подробные описания и задачи', 'Магазин готовых агентов', 'Мониторинг прогресса']} />
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">Агенты</h2>
              <button onClick={() => setShowAgentStore(true)} className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm font-bold hover:scale-105 transition-all shadow-lg">🛒 Магазин агентов</button>
            </div>
            {showAgentStore && (
              <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setShowAgentStore(false)}>
                <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-4xl w-full max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xl font-bold gradient-text">Магазин агентов</h3>
                    <button onClick={() => setShowAgentStore(false)} className="text-gray-400 hover:text-white text-2xl">×</button>
                  </div>
                  <div className="grid md:grid-cols-2 gap-4">
                    {agentStore.map(agent => (
                      <div key={agent.id} className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 card-hover">
                        <h4 className="font-bold text-white mb-2">{agent.name}</h4>
                        <p className="text-sm text-gray-400 mb-3">{agent.description}</p>
                        <div className="flex flex-wrap gap-1 mb-3">{agent.stack.map(s => <span key={s} className="px-2 py-0.5 bg-gray-700 rounded text-[10px] text-gray-300">{s}</span>)}</div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-gray-500">{agent.category} • {agent.price}</span>
                          <button onClick={() => importAgent(agent.id)} className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold transition-all">➕ Импортировать</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
            <div className="grid gap-4">
              {agents.map(agent => (
                <div key={agent.id} className={`rounded-xl border-2 p-5 transition-all card-hover ${agent.enabled ? 'border-emerald-500/50 bg-gradient-to-br from-emerald-500/10 to-cyan-500/5' : 'border-gray-700 bg-gray-900/50 opacity-70'}`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-lg font-bold text-white">{agent.name}</h3>
                        <StatusBadge status={agent.status} />
                      </div>
                      <p className="text-sm text-gray-400 mb-2">{agent.task}</p>
                      <p className="text-xs text-gray-500 italic">{agent.description}</p>
                    </div>
                    <button onClick={() => toggleAgent(agent.id)} className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${agent.enabled ? 'bg-red-500/20 border border-red-500/50 text-red-400 hover:bg-red-500/30' : 'bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 hover:bg-emerald-500/30'}`}>{agent.enabled ? '⏸ Выключить' : '▶ Включить'}</button>
                  </div>
                  <div className="flex flex-wrap gap-1 mb-3">{agent.stack.map(s => <span key={s} className="px-2 py-0.5 bg-gray-700/50 rounded text-[10px] text-gray-300">{s}</span>)}</div>
                  <div className="flex items-center justify-between text-[10px] text-gray-500">
                    <span>Прогресс: {agent.progress}%</span>
                    <span>Активность: {agent.lastActivity}</span>
                  </div>
                  <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all ${agent.enabled ? 'bg-gradient-to-r from-emerald-500 to-cyan-500' : 'bg-gray-600'}`} style={{ width: `${agent.progress}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===== PROVIDERS ===== */}
        {activeTab === 'providers' && (
          <div className="space-y-6">
            <InfoPanel icon="🌐" title="Провайдеры LLM" items={['Управление локальными и облачными моделями', 'Мониторинг статуса и производительности', 'Настройка API ключей', 'Фильтрация по статусу']} />
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">Провайдеры</h2>
              <div className="flex gap-2">
                <button onClick={() => setProviderFilter('all')} className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${providerFilter === 'all' ? 'bg-emerald-500/20 border border-emerald-500/50 text-emerald-400' : 'bg-gray-800 border border-gray-700 text-gray-400'}`}>Все</button>
                <button onClick={() => setProviderFilter('online')} className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${providerFilter === 'online' ? 'bg-emerald-500/20 border border-emerald-500/50 text-emerald-400' : 'bg-gray-800 border border-gray-700 text-gray-400'}`}>Онлайн</button>
                <button onClick={() => setProviderFilter('offline')} className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${providerFilter === 'offline' ? 'bg-red-500/20 border border-red-500/50 text-red-400' : 'bg-gray-800 border border-gray-700 text-gray-400'}`}>Оффлайн</button>
              </div>
            </div>
            {/* Ollama Control */}
            {providers.find(p => p.name === 'Ollama') && (
              <div className="rounded-xl border-2 border-emerald-500/30 bg-gradient-to-br from-emerald-500/10 to-cyan-500/5 p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-bold text-white flex items-center gap-2">🏠 Ollama (Локально)</h3>
                    <p className="text-xs text-gray-400 mt-1">Статус: {ollamaStatus === 'online' ? '✅ Онлайн' : '❌ Оффлайн'} • RAM: {systemStats.ram}MB • VRAM: {systemStats.vram}MB</p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => {}} className="px-3 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-xs font-bold hover:bg-emerald-500/30 transition-all">▶ Запуск</button>
                    <button onClick={() => {}} className="px-3 py-1.5 rounded-lg bg-yellow-500/20 border border-yellow-500/50 text-yellow-400 text-xs font-bold hover:bg-yellow-500/30 transition-all">🔄 Перезапуск</button>
                    <button onClick={() => {}} className="px-3 py-1.5 rounded-lg bg-red-500/20 border border-red-500/50 text-red-400 text-xs font-bold hover:bg-red-500/30 transition-all">⏸ Остановка</button>
                  </div>
                </div>
                <div className="flex gap-2">
                  <input type="text" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} className="flex-1 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono" />
                  <span className={`px-3 py-2 rounded-lg border text-xs ${ollamaStatus === 'online' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-red-500/10 border-red-500/30 text-red-400'}`}>{ollamaStatus === 'online' ? '✅ Подключено' : '❌ Недоступно'}</span>
                </div>
              </div>
            )}
            {/* Other Providers */}
            <div className="rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-5">
              {providers.filter(p => p.name !== 'Ollama').filter(p => providerFilter === 'all' || (providerFilter === 'online' ? p.status === 'online' : p.status !== 'online')).map(provider => (
                <div key={provider.name} className="py-4 border-b border-gray-800 last:border-0">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className={`w-3 h-3 rounded-full ${provider.status === 'online' ? 'bg-emerald-400 animate-pulse' : provider.status === 'error' ? 'bg-red-400' : 'bg-gray-600'}`} />
                      <div>
                        <span className="text-sm font-bold text-white">{provider.name}</span>
                        <StatusBadge status={provider.status} />
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className="text-xs text-gray-400">{provider.latency > 0 ? `${provider.latency}ms` : '—'}</p>
                        <p className="text-[10px] text-gray-500">Задержка</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-gray-400">{provider.models > 0 ? provider.models : '—'}</p>
                        <p className="text-[10px] text-gray-500">Моделей</p>
                      </div>
                      <button onClick={() => toggleProvider(provider.name)} className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${provider.enabled ? 'bg-emerald-500/20 border border-emerald-500/50 text-emerald-400' : 'bg-gray-800 border border-gray-700 text-gray-400'}`}>{provider.enabled ? '✅ Вкл' : '❌ Выкл'}</button>
                    </div>
                  </div>
                  <p className="text-xs text-gray-400 mb-2 ml-6">{provider.description}</p>
                  {provider.enabled && provider.apiKey !== undefined && (
                    <div className="ml-6 mt-2">
                      <input type="password" placeholder="API Key" defaultValue={provider.apiKey} className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-xs" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===== MD EDITOR ===== */}
        {activeTab === 'md' && (
          <div className="space-y-6">
            <InfoPanel icon="📝" title="MD Редактор" items={['Редактирование Markdown файлов', 'AI-подсказки для улучшения', 'Чтение и запись файлов', 'Предварительный просмотр']} />
            <div className="grid lg:grid-cols-2 gap-4">
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-gray-300">📝 Markdown редактор</h3>
                  <div className="flex gap-2">
                    <input type="text" value={mdFileName} onChange={(e) => setMdFileName(e.target.value)} className="px-2 py-1 rounded bg-gray-800 border border-gray-700 text-white text-xs" />
                    <button onClick={() => {}} className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold transition-all">💾 Сохранить</button>
                  </div>
                </div>
                <textarea value={mdContent} onChange={(e) => setMdContent(e.target.value)} className="w-full h-96 px-4 py-3 rounded-lg bg-gray-800/80 border-2 border-gray-700 text-white text-sm font-mono focus:border-emerald-500 focus:outline-none resize-none" />
              </div>
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-gray-300">🤖 AI-подсказки</h3>
                  <button onClick={() => setAiSuggestions(['Добавьте больше примеров кода', 'Улучшите структуру заголовков', 'Добавьте раздел с установкой'])} className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 text-white text-xs font-bold hover:scale-105 transition-all">✨ Получить подсказки</button>
                </div>
                <div className="h-96 overflow-y-auto space-y-2">
                  {aiSuggestions.length === 0 ? <p className="text-sm text-gray-500 italic">Нажмите "Получить подсказки" для анализа документа</p> : aiSuggestions.map((s, i) => <div key={i} className="p-3 rounded-lg bg-gray-800/50 border border-gray-700 text-sm text-gray-300">{s}</div>)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ===== CODE ANALYSIS ===== */}
        {activeTab === 'code' && (
          <div className="space-y-6">
            <InfoPanel icon="⟨⟩" title="Анализ кода" items={['Автоматическое обнаружение ошибок', 'Классификация по серьёзности', 'Исправление через AI-Guardian', 'Массовое исправление проблем']} />
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">Найденные проблемы</h2>
              <button onClick={fixAllIssues} className="px-4 py-2 rounded-lg bg-gradient-to-r from-red-500 to-orange-500 text-white text-sm font-bold hover:scale-105 transition-all shadow-lg">🔧 Исправить все</button>
            </div>
            <div className="space-y-3">
              {codeIssues.map(issue => (
                <div key={issue.id} className={`rounded-xl border p-4 transition-all ${issue.fixed ? 'border-emerald-500/30 bg-emerald-500/5 opacity-60' : issue.severity === 'critical' ? 'border-red-500/30 bg-red-500/5' : issue.severity === 'warning' ? 'border-yellow-500/30 bg-yellow-500/5' : 'border-blue-500/30 bg-blue-500/5'}`}>
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${issue.severity === 'critical' ? 'bg-red-500/20 text-red-400' : issue.severity === 'warning' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-blue-500/20 text-blue-400'}`}>{issue.severity.toUpperCase()}</span>
                        <span className="text-[10px] text-gray-500 font-mono">{issue.file}:{issue.line}</span>
                        {issue.fixed && <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400">ИСПРАВЛЕНО</span>}
                      </div>
                      <h4 className="text-sm font-bold text-white">{issue.title}</h4>
                      <p className="text-xs text-gray-400 mt-1">{issue.description}</p>
                    </div>
                    {!issue.fixed && (
                      <button onClick={() => fixCodeIssue(issue.id)} className="px-3 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-xs font-bold hover:bg-emerald-500/30 transition-all">🔧 Исправить</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===== LOGS ===== */}
        {activeTab === 'logs' && (
          <div className="space-y-6">
            <InfoPanel icon="▤" title="Системные логи" items={['Детальная информация о событиях', 'Уровни: info, warn, error, success', 'Подробности для устранения ошибок', 'Автоматическая прокрутка']} />
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 max-h-[70vh] overflow-y-auto">
              {logs.map((entry, i) => (
                <div key={i} className="flex items-start gap-2 py-1 font-mono text-xs border-b border-gray-800/30 last:border-0">
                  <span className="text-gray-600 shrink-0">[{entry.time}]</span>
                  <span className={`shrink-0 ${entry.level === 'info' ? 'text-blue-400' : entry.level === 'warn' ? 'text-yellow-400' : entry.level === 'error' ? 'text-red-400' : 'text-emerald-400'}`}>{entry.level === 'info' ? 'ℹ' : entry.level === 'warn' ? '⚠' : entry.level === 'error' ? '✕' : '✓'}</span>
                  <div className="flex-1">
                    <span className="text-gray-300">{entry.message}</span>
                    {entry.details && <p className="text-[10px] text-gray-500 mt-0.5">{entry.details}</p>}
                  </div>
                  <span className="text-gray-600 shrink-0">({entry.source})</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===== TASKS ===== */}
        {activeTab === 'tasks' && (
          <div className="space-y-6">
            <InfoPanel icon="☑" title="Задачи" items={['Список задач для выполнения', 'Приоритеты: высокий, средний, низкий', 'Отслеживание прогресса', 'Автоматическое обновление статуса']} />
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">Задачи Агента №1</h3>
              <div className="space-y-2">
                {taskList.map(task => (
                  <div key={task.id} className="flex items-center gap-3 py-2 border-b border-gray-800/50 last:border-0">
                    <button onClick={() => toggleTask(task.id)} className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${task.done ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-gray-600 hover:border-gray-400'}`}>{task.done && <span className="text-xs">✓</span>}</button>
                    <span className={`text-sm flex-1 ${task.done ? 'text-gray-500 line-through' : 'text-gray-200'}`}>{task.text}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${task.priority === 'high' ? 'bg-red-500/20 text-red-400' : task.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-500/20 text-gray-400'}`}>{task.priority.toUpperCase()}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 bg-gray-900/50 mt-8">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between text-[10px] text-gray-600">
          <span>Агент №1 активен • Агенты №2, №3 заморожены</span>
          <span>v3.2.0 FORTRESS • dreamkin • 2026</span>
        </div>
      </footer>
    </div>
  );
}
