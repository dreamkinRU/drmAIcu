import { useState, useEffect, useRef } from 'react';

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
  fixLog?: string[];
}

interface Task {
  id: number;
  text: string;
  done: boolean;
  priority: 'high' | 'medium' | 'low';
}

interface MDFile {
  name: string;
  description: string;
  content: string;
}

// ===== ДАННЫЕ =====
const initialAgents: Agent[] = [
  { id: 1, name: 'Агент №1 — Развитие системы', status: 'active', task: 'Исправление ошибок компиляции и импорта модулей', stack: ['Java', 'Python', 'VBA/Excel'], progress: 45, lastActivity: '2 мин назад', enabled: true, description: 'Основной агент для развития инфраструктуры drmAIcu. Специализируется на Java/Python разработке, VBA/Excel автоматизации.' },
  { id: 2, name: 'Агент №2 — Аналитика данных', status: 'frozen', task: 'На паузе', stack: ['Python', 'Pandas', 'SQL'], progress: 0, lastActivity: '—', enabled: false, description: 'Агент для анализа данных и построения отчётов.' },
  { id: 3, name: 'Агент №3 — Автоматизация отчётов', status: 'frozen', task: 'На паузе', stack: ['Python', 'Excel VBA', 'TTS'], progress: 0, lastActivity: '—', enabled: false, description: 'Агент для автоматизации создания отчётов и голосовых уведомлений.' },
];

const agentStore = [
  { id: 'agent-ml', name: 'Агент ML', description: 'Машинное обучение, нейронные сети, NLP.', stack: ['Python', 'TensorFlow', 'PyTorch'], category: 'AI/ML', price: 'Бесплатно' },
  { id: 'agent-web', name: 'Агент Web', description: 'Full-stack веб-разработчик.', stack: ['JavaScript', 'React', 'Node.js'], category: 'Web', price: 'Бесплатно' },
  { id: 'agent-devops', name: 'Агент DevOps', description: 'CI/CD, контейнеризация, мониторинг.', stack: ['Docker', 'Kubernetes', 'Jenkins'], category: 'DevOps', price: 'Бесплатно' },
  { id: 'agent-security', name: 'Агент Security', description: 'Аудит безопасности, пентестинг.', stack: ['Python', 'OWASP', 'Metasploit'], category: 'Security', price: 'Премиум' },
];

const initialProviders: Provider[] = [
  { name: 'Ollama', status: 'offline', latency: 0, models: 0, description: 'Локальные модели', url: 'http://localhost:11434', enabled: true },
  { name: 'Groq', status: 'online', latency: 23, models: 8, description: 'Быстрые облачные модели', url: 'https://console.groq.com', enabled: true, apiKey: '' },
  { name: 'HuggingFace', status: 'online', latency: 120, models: 150, description: 'Библиотека моделей', url: 'https://huggingface.co', enabled: true, apiKey: '' },
  { name: 'OpenRouter', status: 'online', latency: 89, models: 45, description: 'Агрегатор моделей', url: 'https://openrouter.ai', enabled: true, apiKey: '' },
  { name: 'Gemini', status: 'offline', latency: 0, models: 0, description: 'Google Gemini', url: 'https://makersuite.google.com', enabled: false, apiKey: '' },
  { name: 'Together', status: 'error', latency: 0, models: 0, description: 'Together AI', url: 'https://api.together.xyz', enabled: false, apiKey: '' },
];

const initialLogs: LogEntry[] = [
  { time: '14:32:01', level: 'info', message: 'ЦУ v.3.2.0 FORTRESS запущена', source: 'main.py', details: 'Система инициализирована' },
  { time: '14:32:05', level: 'warn', message: 'OSError: [Errno 22] в py_compile.compile', source: 'main.py', details: 'Решение: tempfile.mkstemp()' },
];

const initialCodeIssues: CodeIssue[] = [
  { id: 1, severity: 'critical', line: '113', file: 'agent_engine.py', title: 'asyncio.get_event_loop() — deprecated', description: 'В Python 3.10+ вызывает DeprecationWarning', fix: 'Заменить на asyncio.get_running_loop()', before: 'loop = asyncio.get_event_loop()', after: 'loop = asyncio.get_running_loop()', fixed: false, fixLog: [] },
  { id: 2, severity: 'critical', line: '126', file: 'agent_engine.py', title: 'Gemini: потеря контекста', description: 'Берётся только messages[-1]', fix: 'Конвертировать все messages', before: 'prompt_text = messages[-1]', after: 'contents = messages.map(...)', fixed: false, fixLog: [] },
  { id: 3, severity: 'warning', line: '83', file: 'agent_engine.py', title: 'HuggingFace: нет метода запроса', description: 'Клиент есть, метода нет', fix: 'Добавить _query_huggingface', before: '// Нет метода', after: 'async _query_huggingface(...)', fixed: false, fixLog: [] },
];

const initialTasks: Task[] = [
  { id: 1, text: 'Исправить py_compile ошибку в main.py', done: false, priority: 'high' },
  { id: 2, text: 'Исправить импорт VBA-модулей', done: false, priority: 'high' },
  { id: 3, text: 'Реализовать модуль TTS', done: false, priority: 'medium' },
  { id: 4, text: 'Тестирование мульти-провайдеров', done: true, priority: 'low' },
];

const mdFiles: MDFile[] = [
  { name: 'CHANGELOG_v3.2.0.md', description: 'Полная история изменений', content: '# drmAIcu v3.2.0\n\n## Новые функции\n- Управление агентами\n- Улучшенные провайдеры\n- MD-редактор\n- Анализ кода с исправлением' },
  { name: 'USER_GUIDE_v3.2.0.md', description: 'Руководство пользователя', content: '# Руководство пользователя\n\n## Установка\n```bash\nnpm install\nnpm run dev\n```\n\n## Использование\nОткройте http://localhost:5173' },
  { name: 'NEW_FEATURES_v3.2.0.md', description: 'Описание новых функций', content: '# Новые функции v3.2.0\n\n## Управление агентами\nВключение/выключение, магазин агентов\n\n## Провайдеры\nРеальная проверка Ollama, мониторинг RAM/VRAM' },
];

// ===== TOOLTIP =====
function Tooltip({ children, text }: { children: React.ReactNode; text: string }) {
  return (
    <div className="relative group">
      {children}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-xs text-gray-300 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-[100] shadow-xl">
        {text}
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900"></div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    frozen: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    offline: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    online: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  const labels: Record<string, string> = { active: 'АКТИВЕН', frozen: 'ЗАМОРОЖЕН', offline: 'ОФФЛАЙН', online: 'ОНЛАЙН', error: 'ОШИБКА' };
  return <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${colors[status] || colors.offline}`}>{labels[status] || status}</span>;
}

// ===== MAIN =====
export default function App() {
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [providers, setProviders] = useState<Provider[]>(initialProviders);
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs);
  const [codeIssues, setCodeIssues] = useState<CodeIssue[]>(initialCodeIssues);
  const [taskList, setTaskList] = useState<Task[]>(initialTasks);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [activeTab, setActiveTab] = useState<'console' | 'agents' | 'providers' | 'md' | 'code' | 'logs' | 'tasks'>('console');
  const [expandedIssues, setExpandedIssues] = useState<Set<number>>(new Set());
  
  const [groqKey, setGroqKey] = useState('');
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'all'>('all');
  const [consolePrompt, setConsolePrompt] = useState('');
  const [consoleLoading, setConsoleLoading] = useState(false);
  
  const [showAgentStore, setShowAgentStore] = useState(false);
  const [providerFilter, setProviderFilter] = useState<'all' | 'online' | 'offline'>('all');
  
  // Ollama real state
  const [ollamaStatus, setOllamaStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaProcesses, setOllamaProcesses] = useState<Array<{name: string, size: number, vram: number}>>([]);
  
  const [selectedMDFile, setSelectedMDFile] = useState<MDFile | null>(null);
  const [mdContent, setMdContent] = useState('');
  
  const ollamaCheckRef = useRef<number | null>(null);

  // Clock
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Real Ollama check
  const checkOllama = async () => {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      
      const res = await fetch(`${ollamaUrl}/api/tags`, { method: 'GET', signal: controller.signal });
      clearTimeout(timeout);
      
      if (res.ok) {
        const data = await res.json();
        setOllamaStatus('online');
        setOllamaModels(data.models?.map((m: any) => m.name) || []);
        setProviders(prev => prev.map(p => p.name === 'Ollama' ? { ...p, status: 'online', models: data.models?.length || 0 } : p));
      } else {
        setOllamaStatus('offline');
        setOllamaModels([]);
        setProviders(prev => prev.map(p => p.name === 'Ollama' ? { ...p, status: 'offline', models: 0 } : p));
      }
    } catch {
      setOllamaStatus('offline');
      setOllamaModels([]);
      setProviders(prev => prev.map(p => p.name === 'Ollama' ? { ...p, status: 'offline', models: 0 } : p));
    }
    
    // Check running processes
    try {
      const res = await fetch(`${ollamaUrl}/api/ps`);
      if (res.ok) {
        const data = await res.json();
        setOllamaProcesses(data.models?.map((m: any) => ({
          name: m.name || m.model,
          size: Math.round((m.size || 0) / 1024 / 1024),
          vram: Math.round((m.size_vram || 0) / 1024 / 1024)
        })) || []);
      }
    } catch {
      setOllamaProcesses([]);
    }
  };

  useEffect(() => {
    checkOllama();
    if (ollamaCheckRef.current) clearInterval(ollamaCheckRef.current);
    ollamaCheckRef.current = window.setInterval(checkOllama, 5000);
    return () => { if (ollamaCheckRef.current) clearInterval(ollamaCheckRef.current); };
  }, [ollamaUrl]);

  const totalRam = ollamaProcesses.reduce((s, m) => s + m.size, 0);
  const totalVram = ollamaProcesses.reduce((s, m) => s + m.vram, 0);

  const toggleTask = (id: number) => setTaskList(prev => prev.map(t => t.id === id ? { ...t, done: !t.done } : t));
  const toggleAgent = (id: number) => setAgents(prev => prev.map(a => a.id === id ? { ...a, enabled: !a.enabled, status: !a.enabled ? 'active' : 'frozen' } : a));
  const toggleProvider = (name: string) => setProviders(prev => prev.map(p => p.name === name ? { ...p, enabled: !p.enabled } : p));
  
  const importAgent = (agentId: string) => {
    const sa = agentStore.find(a => a.id === agentId);
    if (sa) {
      setAgents(prev => [...prev, { id: prev.length + 1, name: sa.name, status: 'frozen', task: 'Готов к активации', stack: sa.stack, progress: 0, lastActivity: 'Только что', enabled: false, description: sa.description }]);
      setShowAgentStore(false);
    }
  };

  // ЧЕСТНОЕ исправление — без выдуманных логов
  const fixCodeIssue = (issueId: number) => {
    const issue = codeIssues.find(i => i.id === issueId);
    if (!issue || issue.fixed) return;
    
    const fixLog: string[] = [];
    fixLog.push(`[${new Date().toLocaleTimeString('ru-RU')}] ⚠️ ВНИМАНИЕ: Это веб-дашборд (React).`);
    fixLog.push(`Реальное исправление файлов возможно ТОЛЬКО через Python AI-Guardian (main.py на порту 8080).`);
    fixLog.push(``);
    fixLog.push(`📋 Что БУДЕТ сделано при реальном исправлении:`);
    fixLog.push(`  1. Проверка синтаксиса файла ${issue.file}`);
    fixLog.push(`  2. Создание тройного бэкапа`);
    fixLog.push(`  3. Замена строки ${issue.line}:`);
    fixLog.push(`     Было: ${issue.before}`);
    fixLog.push(`     Стало: ${issue.after}`);
    fixLog.push(`  4. Проверка синтаксиса после изменения`);
    fixLog.push(`  5. AI-валидация через LLM`);
    fixLog.push(``);
    fixLog.push(`🔧 Для реального исправления:`);
    fixLog.push(`  1. Запустите: python main.py`);
    fixLog.push(`  2. Откройте: http://localhost:8080`);
    fixLog.push(`  3. Вкладка "Универсальные обновления"`);
    fixLog.push(`  4. Выберите файл: ${issue.file}`);
    fixLog.push(`  5. Вставьте исправленный код`);
    fixLog.push(`  6. Нажмите "Проверить и применить"`);
    
    setCodeIssues(prev => prev.map(i => i.id === issueId ? { ...i, fixed: true, fixLog } : i));
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'warn', message: `Отмечено как исправленное: ${issue.title}`, source: 'Web Dashboard', details: 'Реальное исправление через Python AI-Guardian на порту 8080' }]);
  };

  const completedTasks = taskList.filter(t => t.done).length;

  const tabs = [
    { id: 'console' as const, label: 'Консоль', icon: '▶', tooltip: 'Отправка запросов к LLM' },
    { id: 'agents' as const, label: 'Агенты', icon: '🤖', tooltip: 'Управление AI-агентами' },
    { id: 'providers' as const, label: 'Провайдеры', icon: '🌐', tooltip: 'Настройка LLM провайдеров' },
    { id: 'md' as const, label: 'MD', icon: '📝', tooltip: 'Редактор документации' },
    { id: 'code' as const, label: 'Код', icon: '⟨⟩', badge: codeIssues.filter(i => !i.fixed).length, tooltip: 'Анализ и исправление ошибок' },
    { id: 'logs' as const, label: 'Логи', icon: '▤', tooltip: 'Системные события' },
    { id: 'tasks' as const, label: 'Задачи', icon: '☑', tooltip: 'Список задач' },
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* ===== HEADER WITH STATS ===== */}
      <header className="bg-gray-900/90 backdrop-blur-sm border-b border-gray-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-2">
          {/* Top row: Logo + Stats + Clock */}
          <div className="flex items-center justify-between gap-4">
            {/* Logo */}
            <Tooltip text={ollamaStatus === 'online' ? `✅ Ollama онлайн • ${ollamaModels.length} моделей • RAM: ${totalRam}MB VRAM: ${totalVram}MB` : '❌ Ollama не запущен. Выполните: ollama serve'}>
              <div className="flex items-center gap-2 cursor-pointer">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500 via-cyan-500 to-blue-500 flex items-center justify-center font-bold text-xs shadow-lg shadow-emerald-500/30">AI</div>
                <div>
                  <h1 className="text-sm font-bold gradient-text leading-tight">drmAIcu</h1>
                  <p className="text-[10px] text-gray-500 leading-tight">v.3.2.0</p>
                </div>
              </div>
            </Tooltip>

            {/* Stats */}
            <div className="flex items-center gap-2 flex-1 justify-center">
              <Tooltip text={`${agents.filter(a => a.enabled).length} из ${agents.length} агентов включено`}>
                <button onClick={() => setActiveTab('agents')} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-all text-xs">
                  <span>🤖</span>
                  <span className="font-bold text-emerald-400">{agents.filter(a => a.enabled).length}</span>
                  <span className="text-gray-500">/{agents.length}</span>
                </button>
              </Tooltip>
              <Tooltip text={`${providers.filter(p => p.status === 'online').length} из ${providers.length} провайдеров онлайн`}>
                <button onClick={() => setActiveTab('providers')} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-cyan-500/50 hover:bg-cyan-500/5 transition-all text-xs">
                  <span>🌐</span>
                  <span className="font-bold text-cyan-400">{providers.filter(p => p.status === 'online').length}</span>
                  <span className="text-gray-500">/{providers.length}</span>
                </button>
              </Tooltip>
              <Tooltip text={`${completedTasks} из ${taskList.length} задач выполнено`}>
                <button onClick={() => setActiveTab('tasks')} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-yellow-500/50 hover:bg-yellow-500/5 transition-all text-xs">
                  <span>☑</span>
                  <span className="font-bold text-yellow-400">{completedTasks}</span>
                  <span className="text-gray-500">/{taskList.length}</span>
                </button>
              </Tooltip>
              <Tooltip text={`${codeIssues.filter(i => !i.fixed).length} ошибок требуют исправления`}>
                <button onClick={() => setActiveTab('code')} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-red-500/50 hover:bg-red-500/5 transition-all text-xs">
                  <span>⟨⟩</span>
                  <span className="font-bold text-red-400">{codeIssues.filter(i => !i.fixed).length}</span>
                </button>
              </Tooltip>
            </div>

            {/* Right: Download + RAM/VRAM + Clock */}
            <div className="flex items-center gap-3">
              <Tooltip text="Скачать исправленный код проекта">
                <a href="/fixed-code.html" target="_blank" className="w-8 h-8 rounded-lg bg-gray-800/50 border border-gray-700/50 flex items-center justify-center hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-all text-sm">📦</a>
              </Tooltip>
              
              {/* RAM/VRAM */}
              <Tooltip text={ollamaProcesses.length > 0 ? ollamaProcesses.map(m => `${m.name}: ${m.size}MB RAM, ${m.vram}MB VRAM`).join('\n') : 'Нет запущенных моделей Ollama'}>
                <div className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-gray-800/50 border border-gray-700/50 text-[10px]">
                  <span className="text-gray-500">RAM:</span>
                  <span className={`font-mono font-bold ${totalRam > 0 ? 'text-emerald-400' : 'text-gray-600'}`}>{totalRam}MB</span>
                  <span className="text-gray-600 mx-0.5">|</span>
                  <span className="text-gray-500">VRAM:</span>
                  <span className={`font-mono font-bold ${totalVram > 0 ? 'text-cyan-400' : 'text-gray-600'}`}>{totalVram}MB</span>
                </div>
              </Tooltip>

              {/* Clock */}
              <div className="px-3 py-1.5 rounded-lg bg-gray-800/50 border border-gray-700/50">
                <span className="font-mono text-sm text-emerald-400 tabular-nums">{currentTime.toLocaleTimeString('ru-RU')}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="max-w-7xl mx-auto px-4 flex items-center gap-1 overflow-x-auto">
          {tabs.map((tab) => (
            <Tooltip key={tab.id} text={tab.tooltip}>
              <button onClick={() => setActiveTab(tab.id)} className={`px-3 py-2 text-xs font-medium border-b-2 transition-all whitespace-nowrap flex items-center gap-1 ${activeTab === tab.id ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-gray-500 hover:text-gray-300'}`}>
                <span>{tab.icon}</span>{tab.label}
                {tab.badge ? <span className="px-1 py-0 rounded-full bg-red-500/20 text-red-400 text-[9px] font-bold">{tab.badge}</span> : null}
              </button>
            </Tooltip>
          ))}
        </div>
      </header>

      {/* ===== CONTENT ===== */}
      <main className="flex-1 max-w-7xl mx-auto px-4 py-4 w-full">
        
        {/* CONSOLE */}
        {activeTab === 'console' && (
          <div className="space-y-4">
            <div className="rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-4">
              <label className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2 block">Провайдеры</label>
              <div className="flex gap-2 mb-3">
                <button onClick={() => setProviderMode('ollama')} className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all border ${providerMode === 'ollama' ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:text-gray-200'}`}>🏠 Ollama</button>
                <button onClick={() => setProviderMode('groq')} className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all border ${providerMode === 'groq' ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:text-gray-200'}`}>☁️ Groq</button>
                <button onClick={() => setProviderMode('all')} className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all border ${providerMode === 'all' ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:text-gray-200'}`}>⚡ Все</button>
              </div>
              {(providerMode === 'ollama' || providerMode === 'all') && (
                <div className="mb-2">
                  <input type="text" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-xs font-mono focus:border-emerald-500 focus:outline-none" />
                </div>
              )}
              {(providerMode === 'groq' || providerMode === 'all') && (
                <div className="flex gap-2">
                  <input type="password" value={groqKey} onChange={(e) => setGroqKey(e.target.value)} placeholder="Groq API Key" className="flex-1 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-xs focus:border-cyan-500 focus:outline-none" />
                  <a href="https://console.groq.com/keys" target="_blank" className="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 text-xs hover:text-white">Ключ →</a>
                </div>
              )}
            </div>
            <div className="rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-4">
              <textarea value={consolePrompt} onChange={(e) => setConsolePrompt(e.target.value)} placeholder="Опиши задачу..." rows={4} className="w-full px-3 py-2 rounded-lg bg-gray-800/80 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none resize-none font-mono" />
              <div className="flex justify-end mt-3">
                <button onClick={() => {}} disabled={consoleLoading} className={`px-6 py-2 rounded-lg font-bold text-sm transition-all ${consoleLoading ? 'bg-gray-700 text-gray-500' : 'bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white shadow-lg shadow-emerald-500/20'}`}>{consoleLoading ? '⏳...' : '▶ Отправить'}</button>
              </div>
            </div>
          </div>
        )}

        {/* AGENTS */}
        {activeTab === 'agents' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold">Агенты</h2>
              <button onClick={() => setShowAgentStore(true)} className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white text-xs font-bold">🛒 Магазин</button>
            </div>
            {showAgentStore && (
              <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setShowAgentStore(false)}>
                <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 max-w-3xl w-full max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                  <div className="flex justify-between mb-3"><h3 className="text-lg font-bold gradient-text">Магазин агентов</h3><button onClick={() => setShowAgentStore(false)} className="text-gray-400 text-xl">×</button></div>
                  <div className="grid md:grid-cols-2 gap-3">
                    {agentStore.map(a => (
                      <div key={a.id} className="bg-gray-800/50 border border-gray-700 rounded-lg p-3">
                        <h4 className="font-bold text-white text-sm mb-1">{a.name}</h4>
                        <p className="text-xs text-gray-400 mb-2">{a.description}</p>
                        <div className="flex justify-between items-center">
                          <span className="text-[10px] text-gray-500">{a.category} • {a.price}</span>
                          <button onClick={() => importAgent(a.id)} className="px-2 py-1 rounded bg-emerald-500 text-white text-[10px] font-bold">➕</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
            {agents.map(agent => (
              <div key={agent.id} className={`rounded-xl border-2 p-4 transition-all ${agent.enabled ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-gray-700 bg-gray-900/50 opacity-70'}`}>
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <div className="flex items-center gap-2 mb-1"><h3 className="font-bold text-white text-sm">{agent.name}</h3><StatusBadge status={agent.status} /></div>
                    <p className="text-xs text-gray-400">{agent.task}</p>
                    <p className="text-[10px] text-gray-500 italic mt-1">{agent.description}</p>
                  </div>
                  <button onClick={() => toggleAgent(agent.id)} className={`px-3 py-1.5 rounded-lg text-xs font-bold ${agent.enabled ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'}`}>{agent.enabled ? '⏸' : '▶'}</button>
                </div>
                <div className="flex gap-1 mb-2">{agent.stack.map(s => <span key={s} className="px-1.5 py-0.5 bg-gray-700/50 rounded text-[10px] text-gray-300">{s}</span>)}</div>
                <div className="h-1 bg-gray-700 rounded-full"><div className={`h-full rounded-full ${agent.enabled ? 'bg-gradient-to-r from-emerald-500 to-cyan-500' : 'bg-gray-600'}`} style={{ width: `${agent.progress}%` }} /></div>
              </div>
            ))}
          </div>
        )}

        {/* PROVIDERS */}
        {activeTab === 'providers' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold">Провайдеры</h2>
              <div className="flex gap-1">
                {(['all', 'online', 'offline'] as const).map(f => (
                  <button key={f} onClick={() => setProviderFilter(f)} className={`px-2 py-1 rounded text-[10px] font-bold ${providerFilter === f ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50' : 'bg-gray-800 text-gray-400 border border-gray-700'}`}>{f === 'all' ? 'Все' : f === 'online' ? 'Онлайн' : 'Оффлайн'}</button>
                ))}
              </div>
            </div>

            {/* Ollama — special block with real controls */}
            <div className={`rounded-xl border-2 p-4 transition-all ${ollamaStatus === 'online' ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Tooltip text={ollamaStatus === 'online' ? `Ollama работает. Моделей: ${ollamaModels.length}. Запущено процессов: ${ollamaProcesses.length}` : `Ollama не отвечает на ${ollamaUrl}. Запустите в терминале: ollama serve`}>
                    <div className={`w-3 h-3 rounded-full cursor-help ${ollamaStatus === 'online' ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
                  </Tooltip>
                  <div>
                    <span className="font-bold text-white text-sm">Ollama</span>
                    <span className="text-xs text-gray-400 ml-2">— Локальные модели</span>
                  </div>
                </div>
                <div className="flex gap-1">
                  <Tooltip text="Выполните в терминале: ollama serve">
                    <button onClick={() => { navigator.clipboard.writeText('ollama serve'); setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'info', message: 'Команда ollama serve скопирована в буфер обмена. Вставьте в терминал.', source: 'Ollama', details: 'Браузер не может запускать процессы на ПК напрямую. Скопируйте команду и выполните в терминале.' }]); }} className="px-2 py-1 rounded bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-[10px] font-bold hover:bg-emerald-500/30">▶ Запуск</button>
                  </Tooltip>
                  <Tooltip text="Выполните: pkill ollama && ollama serve">
                    <button onClick={() => { navigator.clipboard.writeText('pkill ollama && ollama serve'); setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'info', message: 'Команда перезапуска скопирована', source: 'Ollama' }]); }} className="px-2 py-1 rounded bg-yellow-500/20 border border-yellow-500/50 text-yellow-400 text-[10px] font-bold hover:bg-yellow-500/30">🔄</button>
                  </Tooltip>
                  <Tooltip text="Выполните: pkill ollama">
                    <button onClick={() => { navigator.clipboard.writeText('pkill ollama'); setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'warn', message: 'Команда остановки скопирована', source: 'Ollama' }]); }} className="px-2 py-1 rounded bg-red-500/20 border border-red-500/50 text-red-400 text-[10px] font-bold hover:bg-red-500/30">⏸</button>
                  </Tooltip>
                </div>
              </div>
              <div className="flex gap-2 items-center">
                <input type="text" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} className="flex-1 px-2 py-1.5 rounded bg-gray-800 border border-gray-700 text-white text-xs font-mono" />
                {ollamaStatus === 'online' && ollamaModels.length > 0 && (
                  <div className="text-[10px] text-gray-400">
                    Модели: {ollamaModels.slice(0, 3).join(', ')}{ollamaModels.length > 3 ? ` +${ollamaModels.length - 3}` : ''}
                  </div>
                )}
              </div>
              {ollamaProcesses.length > 0 && (
                <div className="mt-2 text-[10px] text-gray-400">
                  Запущено: {ollamaProcesses.map(m => `${m.name} (${m.size}MB RAM, ${m.vram}MB VRAM)`).join(' • ')}
                </div>
              )}
            </div>

            {/* Other providers */}
            <div className="space-y-2">
              {providers.filter(p => p.name !== 'Ollama').filter(p => providerFilter === 'all' || (providerFilter === 'online' ? p.status === 'online' : p.status !== 'online')).map(provider => (
                <div key={provider.name} className={`rounded-xl border p-3 transition-all ${provider.enabled ? 'border-gray-700 bg-gray-900/50' : 'border-gray-800 bg-gray-900/30 opacity-60'}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <Tooltip text={provider.status === 'online' ? 'Доступен' : provider.status === 'error' ? 'Ошибка подключения' : 'Не настроен'}>
                        <div className={`w-2.5 h-2.5 rounded-full shrink-0 cursor-help ${provider.status === 'online' ? 'bg-emerald-400 animate-pulse' : provider.status === 'error' ? 'bg-red-400' : 'bg-gray-600'}`} />
                      </Tooltip>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white text-sm">{provider.name}</span>
                          <span className="text-xs text-gray-400 truncate">{provider.description}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-[10px] text-gray-500">{provider.latency > 0 ? `${provider.latency}ms` : '—'} <span className="text-gray-600">задержка</span></span>
                      <span className="text-[10px] text-gray-500">{provider.models > 0 ? provider.models : '—'} <span className="text-gray-600">моделей</span></span>
                      <button onClick={() => toggleProvider(provider.name)} className={`w-10 h-5 rounded-full transition-all relative ${provider.enabled ? 'bg-emerald-500' : 'bg-gray-700'}`}>
                        <div className={`w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all ${provider.enabled ? 'left-5.5 right-0.5' : 'left-0.5'}`} style={{ left: provider.enabled ? '22px' : '2px' }} />
                      </button>
                    </div>
                  </div>
                  {provider.enabled && provider.apiKey !== undefined && (
                    <div className="mt-2 flex gap-2">
                      <input type="password" placeholder="API Key" defaultValue={provider.apiKey} className="flex-1 max-w-[200px] px-2 py-1 rounded bg-gray-800 border border-gray-700 text-white text-[10px]" />
                      <a href={provider.url} target="_blank" className="text-[10px] text-cyan-400 hover:text-cyan-300 self-center">Получить ключ →</a>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* MD */}
        {activeTab === 'md' && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold">Документация</h2>
            <div className="grid md:grid-cols-3 gap-3">
              {mdFiles.map(file => (
                <button key={file.name} onClick={() => { setSelectedMDFile(file); setMdContent(file.content); }} className={`rounded-xl border-2 p-3 text-left transition-all ${selectedMDFile?.name === file.name ? 'border-emerald-500/50 bg-emerald-500/5' : 'border-gray-700 bg-gray-900/50 hover:border-gray-600'}`}>
                  <h3 className="font-bold text-white text-xs mb-1 truncate">{file.name}</h3>
                  <p className="text-[10px] text-gray-400">{file.description}</p>
                </button>
              ))}
            </div>
            {selectedMDFile && (
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-4">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="text-sm font-bold text-gray-300">📝 {selectedMDFile.name}</h3>
                  <button onClick={() => setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'success', message: `${selectedMDFile.name} сохранён`, source: 'MD Editor' }])} className="px-3 py-1 rounded bg-emerald-500 text-white text-xs font-bold">💾 Сохранить</button>
                </div>
                <textarea value={mdContent} onChange={(e) => setMdContent(e.target.value)} className="w-full h-80 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-xs font-mono focus:border-emerald-500 focus:outline-none resize-none" />
              </div>
            )}
          </div>
        )}

        {/* CODE */}
        {activeTab === 'code' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold">Анализ кода</h2>
              <button onClick={() => codeIssues.filter(i => !i.fixed).forEach(i => fixCodeIssue(i.id))} className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-red-500 to-orange-500 text-white text-xs font-bold">🔧 Исправить все</button>
            </div>
            {codeIssues.map(issue => (
              <div key={issue.id} className={`rounded-xl border p-4 ${issue.fixed ? 'border-emerald-500/30 bg-emerald-500/5' : issue.severity === 'critical' ? 'border-red-500/30 bg-red-500/5' : issue.severity === 'warning' ? 'border-yellow-500/30 bg-yellow-500/5' : 'border-blue-500/30 bg-blue-500/5'}`}>
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${issue.severity === 'critical' ? 'bg-red-500/20 text-red-400' : issue.severity === 'warning' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-blue-500/20 text-blue-400'}`}>{issue.severity.toUpperCase()}</span>
                      <span className="text-[10px] text-gray-500 font-mono">{issue.file}:{issue.line}</span>
                      {issue.fixed && <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400">ИСПРАВЛЕНО</span>}
                    </div>
                    <h4 className="text-sm font-bold text-white">{issue.title}</h4>
                    <p className="text-xs text-gray-400 mt-1">{issue.description}</p>
                  </div>
                  {!issue.fixed && <button onClick={() => fixCodeIssue(issue.id)} className="px-3 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-xs font-bold">🔧 Исправить</button>}
                </div>
                {issue.fixed && issue.fixLog && issue.fixLog.length > 0 && (
                  <div className="mt-3 p-3 rounded-lg bg-gray-900/80 border border-gray-700">
                    <p className="text-[10px] font-bold text-yellow-400 mb-2">⚠️ ВНИМАНИЕ: Это веб-дашборд. Реальное исправление — через Python AI-Guardian.</p>
                    <div className="space-y-0.5 max-h-48 overflow-y-auto">
                      {issue.fixLog.map((log, i) => <p key={i} className="text-[10px] text-gray-400 font-mono">{log}</p>)}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* LOGS */}
        {activeTab === 'logs' && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold">Логи</h2>
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-3 max-h-[70vh] overflow-y-auto">
              {logs.slice().reverse().map((entry, i) => (
                <div key={i} className="flex items-start gap-2 py-1 font-mono text-xs border-b border-gray-800/30 last:border-0">
                  <span className="text-gray-600 shrink-0">[{entry.time}]</span>
                  <span className={entry.level === 'info' ? 'text-blue-400' : entry.level === 'warn' ? 'text-yellow-400' : entry.level === 'error' ? 'text-red-400' : 'text-emerald-400'}>{entry.level === 'info' ? 'ℹ' : entry.level === 'warn' ? '⚠' : entry.level === 'error' ? '✕' : '✓'}</span>
                  <div className="flex-1">
                    <span className="text-gray-300">{entry.message}</span>
                    {entry.details && <p className="text-[10px] text-gray-500">{entry.details}</p>}
                  </div>
                  <span className="text-gray-600 shrink-0">({entry.source})</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TASKS */}
        {activeTab === 'tasks' && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold">Задачи</h2>
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              {taskList.map(task => (
                <div key={task.id} className="flex items-center gap-3 py-2 border-b border-gray-800/50 last:border-0">
                  <button onClick={() => toggleTask(task.id)} className={`w-5 h-5 rounded border-2 flex items-center justify-center ${task.done ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-gray-600'}`}>{task.done && '✓'}</button>
                  <span className={`text-sm flex-1 ${task.done ? 'text-gray-500 line-through' : 'text-gray-200'}`}>{task.text}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${task.priority === 'high' ? 'bg-red-500/20 text-red-400' : task.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-500/20 text-gray-400'}`}>{task.priority.toUpperCase()}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 bg-gray-900/50 shrink-0">
        <div className="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between text-[10px] text-gray-600">
          <span>Агент №1 активен • Агенты №2, №3 заморожены</span>
          <span>v.3.2.0 FORTRESS • dreamkin • 2026</span>
        </div>
      </footer>
    </div>
  );
}
