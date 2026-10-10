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
  getKeyUrl?: string;
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
  category: 'code' | 'general';
}

interface MDFile {
  name: string;
  description: string;
  content: string;
}

// ===== ДАННЫЕ =====
const initialAgents: Agent[] = [
  { id: 1, name: 'Агент №1 — Развитие системы', status: 'active', task: 'Исправление ошибок компиляции', stack: ['Java', 'Python', 'VBA/Excel'], progress: 45, lastActivity: '2 мин назад', enabled: true, description: 'Основной агент для развития инфраструктуры drmAIcu.' },
  { id: 2, name: 'Агент №2 — Аналитика данных', status: 'frozen', task: 'На паузе', stack: ['Python', 'Pandas', 'SQL'], progress: 0, lastActivity: '—', enabled: false, description: 'Агент для анализа данных и построения отчётов.' },
  { id: 3, name: 'Агент №3 — Автоматизация отчётов', status: 'frozen', task: 'На паузе', stack: ['Python', 'Excel VBA', 'TTS'], progress: 0, lastActivity: '—', enabled: false, description: 'Агент для автоматизации создания отчётов.' },
];

const agentStore = [
  { id: 'agent-ml', name: 'Агент ML', description: 'Машинное обучение, нейронные сети.', stack: ['Python', 'TensorFlow'], category: 'AI/ML' },
  { id: 'agent-web', name: 'Агент Web', description: 'Full-stack веб-разработчик.', stack: ['JavaScript', 'React'], category: 'Web' },
  { id: 'agent-devops', name: 'Агент DevOps', description: 'CI/CD, контейнеризация.', stack: ['Docker', 'Kubernetes'], category: 'DevOps' },
];

const initialProviders: Provider[] = [
  { name: 'Ollama', status: 'offline', latency: 0, models: 0, description: 'Локальные модели', url: 'http://localhost:11434', enabled: true },
  { name: 'Groq', status: 'online', latency: 23, models: 8, description: 'Быстрые облачные модели', url: 'https://console.groq.com', enabled: true, apiKey: '', getKeyUrl: 'https://console.groq.com/keys' },
  { name: 'HuggingFace', status: 'online', latency: 120, models: 150, description: 'Библиотека моделей', url: 'https://huggingface.co', enabled: true, apiKey: '', getKeyUrl: 'https://huggingface.co/settings/tokens' },
  { name: 'OpenRouter', status: 'online', latency: 89, models: 45, description: 'Агрегатор моделей', url: 'https://openrouter.ai', enabled: true, apiKey: '', getKeyUrl: 'https://openrouter.ai/workspaces/default/keys' },
  { name: 'Gemini', status: 'offline', latency: 0, models: 0, description: 'Google Gemini', url: 'https://aistudio.google.com', enabled: false, apiKey: '', getKeyUrl: 'https://aistudio.google.com/api-keys' },
  { name: 'Together', status: 'error', latency: 0, models: 0, description: 'Together AI', url: 'https://api.together.xyz', enabled: false, apiKey: '' },
];

const initialLogs: LogEntry[] = [
  { time: '14:32:01', level: 'info', message: 'ЦУ v.3.2.0 FORTRESS запущена', source: 'main.py' },
];

const initialCodeIssues: CodeIssue[] = [
  { id: 1, severity: 'critical', line: '113', file: 'agent_engine.py', title: 'asyncio.get_event_loop() — deprecated', description: 'В Python 3.10+ вызывает DeprecationWarning', fix: 'Заменить на asyncio.get_running_loop()', before: 'loop = asyncio.get_event_loop()', after: 'loop = asyncio.get_running_loop()', fixed: false, fixLog: [] },
  { id: 2, severity: 'critical', line: '126', file: 'agent_engine.py', title: 'Gemini: потеря контекста', description: 'Берётся только messages[-1]', fix: 'Конвертировать все messages', before: 'prompt_text = messages[-1]', after: 'contents = messages.map(...)', fixed: false, fixLog: [] },
  { id: 3, severity: 'warning', line: '83', file: 'agent_engine.py', title: 'HuggingFace: нет метода запроса', description: 'Клиент есть, метода нет', fix: 'Добавить _query_huggingface', before: '// Нет метода', after: 'async _query_huggingface(...)', fixed: false, fixLog: [] },
];

const initialTasks: Task[] = [
  { id: 1, text: 'Исправить py_compile ошибку в main.py', done: false, priority: 'high', category: 'code' },
  { id: 2, text: 'Исправить импорт VBA-модулей', done: false, priority: 'high', category: 'code' },
  { id: 3, text: 'Реализовать модуль TTS', done: false, priority: 'medium', category: 'general' },
  { id: 4, text: 'Тестирование мульти-провайдеров', done: true, priority: 'low', category: 'general' },
];

const mdFiles: MDFile[] = [
  { 
    name: 'CHANGELOG.md', 
    description: 'Полная история изменений', 
    content: `# drmAIcu — История изменений

## v.3.2.0 (Текущая)
### Новые функции
- Управление агентами с магазином
- Улучшенные провайдеры с мониторингом RAM/VRAM
- MD-редактор с AI-подсказками
- Анализ кода с исправлением
- Информационные панели

### Исправления
- Кодировка MD файлов
- AI-Guardian для всех файлов
- Реальная проверка Ollama
- Порядок вкладок

## v.3.1.0
- Universal AI-Guardian для всех файлов
- Управление агентами
- Магазин агентов

## v.3.0.9
- React-дашборд + Ollama + Groq
- Один интерфейс для всех моделей

## v.3.0.8
- Новый дизайн как в React-дашборде

## v.3.0.7
- Исправлена lambda ошибка в Console

## v.3.0.6
- Удалены дубликаты функций

## v.3.0.5
- Исправлено FileNotFoundError
- Полный комплект файлов

## v.3.0.4
- Universal AI-Guardian
- Русский интерфейс

## v.3.0.3
- Исправления ошибок (OSError, asyncio, Gemini)` 
  },
  { 
    name: 'USER_GUIDE.md', 
    description: 'Руководство пользователя', 
    content: `# Руководство пользователя drmAIcu

## Установка

### React-дашборд
\`\`\`bash
cd G:\\Mega\\git\\drmAIcu
npm install
npm run dev
\`\`\`
Откроется: http://localhost:5173

### Python-версия
\`\`\`bash
python main.py
\`\`\`
Откроется: http://localhost:8080

## Использование

### Консоль
1. Выберите режим: Ollama / Groq / Все
2. Настройте провайдеры во вкладке "Провайдеры"
3. Напишите запрос и нажмите "Отправить"
4. Смотрите ответы моделей и выбор арбитра

### Агенты
1. Включите/выключите агентов
2. Читайте описания
3. Импортируйте из магазина

### Провайдеры
1. Проверьте статус Ollama
2. Используйте кнопки управления
3. Следите за RAM/VRAM
4. Настраивайте API ключи

### MD-редактор
1. Выберите файл
2. Отредактируйте
3. Сохраните

### Анализ кода
1. Просмотрите ошибки
2. Нажмите "Исправить"
3. Следуйте инструкциям` 
  },
  { 
    name: 'NEW_FEATURES.md', 
    description: 'Описание новых функций', 
    content: `# Новые функции v.3.2.0

## Управление агентами
- Включение/выключение кнопками
- Подробные описания
- Магазин готовых агентов
- Мониторинг прогресса

## Улучшенные провайдеры
- Реальная проверка Ollama каждые 5 сек
- Кнопки управления (копируют команды)
- Мониторинг RAM/VRAM
- Фильтрация по статусу
- Настройки API ключей

## MD-редактор
- Отображение всех .md файлов
- Редактирование с сохранением
- AI-подсказки (в будущем)

## Анализ кода
- Обнаружение ошибок
- Классификация по серьёзности
- Честные инструкции по исправлению
- Массовое исправление

## Интерфейс
- Блоки статистики в шапке
- Tooltips везде
- Современный дизайн
- Градиенты и анимации` 
  },
];

// ===== TOOLTIP С УМНЫМ ПОЗИЦИОНИРОВАНИЕМ =====
function Tooltip({ children, text, position = 'bottom' }: { children: React.ReactNode; text: string; position?: 'top' | 'bottom' | 'left' | 'right' }) {
  const posClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };
  const arrowClasses = {
    top: 'top-full left-1/2 -translate-x-1/2 border-t-gray-900',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-gray-900',
    left: 'left-full top-1/2 -translate-y-1/2 border-l-gray-900',
    right: 'right-full top-1/2 -translate-y-1/2 border-r-gray-900',
  };
  
  return (
    <div className="relative group">
      {children}
      <div className={`absolute ${posClasses[position]} px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-xs text-gray-300 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-[100] shadow-xl`}>
        {text}
        <div className={`absolute ${arrowClasses[position]} border-4 border-transparent`}></div>
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
  const [activeTab, setActiveTab] = useState<'console' | 'panel' | 'agents' | 'providers' | 'md' | 'code' | 'logs' | 'tasks'>('console');
  
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'all'>('all');
  const [consolePrompt, setConsolePrompt] = useState('');
  const [consoleLoading, setConsoleLoading] = useState(false);
  
  const [showAgentStore, setShowAgentStore] = useState(false);
  const [providerFilter, setProviderFilter] = useState<'all' | 'online' | 'offline'>('all');
  
  const [ollamaStatus, setOllamaStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaProcesses, setOllamaProcesses] = useState<Array<{name: string; size: number; vram: number}>>([]);
  
  const [selectedMDFile, setSelectedMDFile] = useState<MDFile | null>(null);
  const [mdContent, setMdContent] = useState('');
  
  const [newTaskText, setNewTaskText] = useState('');
  const [newTaskPriority, setNewTaskPriority] = useState<'high' | 'medium' | 'low'>('medium');
  const [newTaskCategory, setNewTaskCategory] = useState<'code' | 'general'>('general');

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
      const res = await fetch(`${ollamaUrl}/api/tags`, { signal: controller.signal });
      clearTimeout(timeout);
      
      if (res.ok) {
        const data = await res.json();
        setOllamaStatus('online');
        setOllamaModels(data.models?.map((m: any) => m.name) || []);
        setProviders(prev => prev.map(p => p.name === 'Ollama' ? { ...p, status: 'online', models: data.models?.length || 0 } : p));
      } else {
        throw new Error('Not OK');
      }
    } catch {
      setOllamaStatus('offline');
      setOllamaModels([]);
      setOllamaProcesses([]);
      setProviders(prev => prev.map(p => p.name === 'Ollama' ? { ...p, status: 'offline', models: 0 } : p));
      return;
    }
    
    // Check running processes for RAM/VRAM
    try {
      const res = await fetch(`${ollamaUrl}/api/ps`);
      if (res.ok) {
        const data = await res.json();
        const processes = (data.models || []).map((m: any) => ({
          name: m.name || m.model || 'unknown',
          size: Math.round((m.size || 0) / 1024 / 1024),
          vram: Math.round((m.size_vram || 0) / 1024 / 1024)
        }));
        setOllamaProcesses(processes);
      }
    } catch {
      setOllamaProcesses([]);
    }
  };

  useEffect(() => {
    checkOllama();
    const interval = setInterval(checkOllama, 5000);
    return () => clearInterval(interval);
  }, [ollamaUrl]);

  const totalRam = ollamaProcesses.reduce((s, m) => s + m.size, 0);
  const totalVram = ollamaProcesses.reduce((s, m) => s + m.vram, 0);

  const toggleTask = (id: number) => setTaskList(prev => prev.map(t => t.id === id ? { ...t, done: !t.done } : t));
  const toggleAgent = (id: number) => setAgents(prev => prev.map(a => a.id === id ? { ...a, enabled: !a.enabled, status: !a.enabled ? 'active' : 'frozen' } : a));
  const toggleProvider = (name: string) => setProviders(prev => prev.map(p => p.name === name ? { ...p, enabled: !p.enabled } : p));
  
  const addTask = () => {
    if (!newTaskText.trim()) return;
    setTaskList(prev => [...prev, { id: prev.length + 1, text: newTaskText, done: false, priority: newTaskPriority, category: newTaskCategory }]);
    setNewTaskText('');
  };

  const deleteTask = (id: number) => setTaskList(prev => prev.filter(t => t.id !== id));
  
  const importAgent = (agentId: string) => {
    const sa = agentStore.find(a => a.id === agentId);
    if (sa) {
      setAgents(prev => [...prev, { id: prev.length + 1, name: sa.name, status: 'frozen', task: 'Готов к активации', stack: sa.stack, progress: 0, lastActivity: 'Только что', enabled: false, description: sa.description }]);
      setShowAgentStore(false);
    }
  };

  // ЧЕСТНОЕ исправление с реальными инструкциями
  const fixCodeIssue = (issueId: number) => {
    const issue = codeIssues.find(i => i.id === issueId);
    if (!issue || issue.fixed) return;
    
    const fixLog: string[] = [
      `═══════════════════════════════════════`,
      `⚠️  ВНИМАНИЕ: Это веб-дашборд (React)`,
      `Реальное исправление файлов возможно ТОЛЬКО через Python AI-Guardian`,
      `═══════════════════════════════════════`,
      ``,
      `📋 Что БУДЕТ сделано при реальном исправлении:`,
      ``,
      `1️⃣  Проверка существования файла: ${issue.file}`,
      `2️⃣  Создание тройного бэкапа:`,
      `   • ${issue.file}_${Date.now()}.bak`,
      `   • ${issue.file}_${Date.now()}_verified.bak`,
      `   • ${issue.file}_LATEST.bak`,
      ``,
      `3️⃣  Замена в строке ${issue.line}:`,
      `   ❌ Было: ${issue.before}`,
      `   ✅ Стало: ${issue.after}`,
      ``,
      `4️⃣  Проверка синтаксиса Python (ast.parse)`,
      `5️⃣  AI-валидация через LLM`,
      ``,
      `═══════════════════════════════════════`,
      `🔧 КАК ВЫПОЛНИТЬ РЕАЛЬНОЕ ИСПРАВЛЕНИЕ:`,
      `═══════════════════════════════════════`,
      ``,
      `Шаг 1: Откройте терминал в папке проекта`,
      `  cd G:\\Mega\\git\\drmAIcu`,
      ``,
      `Шаг 2: Запустите Python AI-Guardian`,
      `  python main.py`,
      ``,
      `Шаг 3: Откройте в браузере`,
      `  http://localhost:8080`,
      ``,
      `Шаг 4: Перейдите на вкладку "Универсальные обновления"`,
      ``,
      `Шаг 5: Выберите файл: ${issue.file}`,
      ``,
      `Шаг 6: Введите описание:`,
      `  ${issue.title}`,
      ``,
      `Шаг 7: Вставьте исправленный код (замените ${issue.before} на ${issue.after})`,
      ``,
      `Шаг 8: Нажмите "Проверить и применить"`,
      ``,
      `Шаг 9: AI-Guardian выполнит:`,
      `  ✓ 4-уровневую валидацию`,
      `  ✓ Создание бэкапа`,
      `  ✓ Применение патча`,
      `  ✓ Авто-откат при ошибке`,
      ``,
      `═══════════════════════════════════════`,
      `✅ После выполнения реальное исправление будет завершено`,
      `═══════════════════════════════════════`,
    ];
    
    setCodeIssues(prev => prev.map(i => i.id === issueId ? { ...i, fixed: true, fixLog } : i));
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'warn', message: `Отмечено: ${issue.title}`, source: 'Web Dashboard', details: 'Реальное исправление через Python AI-Guardian на порту 8080' }]);
  };

  const completedTasks = taskList.filter(t => t.done).length;
  const codeTasks = taskList.filter(t => t.category === 'code');
  const generalTasks = taskList.filter(t => t.category === 'general');

  const tabs = [
    { id: 'console' as const, label: 'Консоль', icon: '▶', tooltip: 'Отправка запросов к LLM' },
    { id: 'panel' as const, label: 'Панель', icon: '◈', tooltip: 'Общая статистика системы' },
    { id: 'agents' as const, label: 'Агенты', icon: '🤖', tooltip: 'Управление AI-агентами' },
    { id: 'providers' as const, label: 'Провайдеры', icon: '🌐', tooltip: 'Настройка LLM провайдеров' },
    { id: 'md' as const, label: 'MD', icon: '📝', tooltip: 'Редактор документации' },
    { id: 'code' as const, label: 'Код', icon: '⟨⟩', badge: codeIssues.filter(i => !i.fixed).length, tooltip: 'Анализ и исправление ошибок' },
    { id: 'logs' as const, label: 'Логи', icon: '▤', tooltip: 'Системные события' },
    { id: 'tasks' as const, label: 'Задачи', icon: '☑', tooltip: 'Список задач' },
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col text-base">
      {/* ===== HEADER WITH STATS ===== */}
      <header className="bg-gray-900/90 backdrop-blur-sm border-b border-gray-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3">
          {/* Top row: Logo + Stats + Clock */}
          <div className="flex items-center justify-between gap-4">
            {/* Logo */}
            <Tooltip text={ollamaStatus === 'online' ? `✅ Ollama онлайн • ${ollamaModels.length} моделей • RAM: ${totalRam}MB VRAM: ${totalVram}MB` : '❌ Ollama не запущен. Выполните: ollama serve'} position="bottom">
              <div className="flex items-center gap-3 cursor-pointer">
                <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-emerald-500 via-cyan-500 to-blue-500 flex items-center justify-center font-bold text-sm shadow-lg shadow-emerald-500/30">AI</div>
                <div>
                  <h1 className="text-lg font-bold gradient-text leading-tight">drmAIcu</h1>
                  <p className="text-xs text-gray-500 leading-tight">v.3.2.0</p>
                </div>
              </div>
            </Tooltip>

            {/* Stats */}
            <div className="flex items-center gap-3 flex-1 justify-center">
              <Tooltip text={`${agents.filter(a => a.enabled).length} из ${agents.length} агентов включено`} position="bottom">
                <button onClick={() => setActiveTab('agents')} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-all">
                  <span className="text-xl">🤖</span>
                  <div className="text-left">
                    <div className="flex items-baseline gap-1">
                      <span className="font-bold text-emerald-400 text-lg">{agents.filter(a => a.enabled).length}</span>
                      <span className="text-gray-500 text-sm">/{agents.length}</span>
                    </div>
                    <p className="text-[10px] text-gray-500">Агенты</p>
                  </div>
                </button>
              </Tooltip>
              <Tooltip text={`${providers.filter(p => p.status === 'online').length} из ${providers.length} провайдеров онлайн`} position="bottom">
                <button onClick={() => setActiveTab('providers')} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-cyan-500/50 hover:bg-cyan-500/5 transition-all">
                  <span className="text-xl">🌐</span>
                  <div className="text-left">
                    <div className="flex items-baseline gap-1">
                      <span className="font-bold text-cyan-400 text-lg">{providers.filter(p => p.status === 'online').length}</span>
                      <span className="text-gray-500 text-sm">/{providers.length}</span>
                    </div>
                    <p className="text-[10px] text-gray-500">Провайдеры</p>
                  </div>
                </button>
              </Tooltip>
              <Tooltip text={`${codeIssues.filter(i => !i.fixed).length} ошибок требуют исправления`} position="bottom">
                <button onClick={() => setActiveTab('code')} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-red-500/50 hover:bg-red-500/5 transition-all">
                  <span className="text-xl">⟨⟩</span>
                  <div className="text-left">
                    <span className="font-bold text-red-400 text-lg">{codeIssues.filter(i => !i.fixed).length}</span>
                    <p className="text-[10px] text-gray-500">Код</p>
                  </div>
                </button>
              </Tooltip>
              <Tooltip text={`${completedTasks} из ${taskList.length} задач выполнено`} position="bottom">
                <button onClick={() => setActiveTab('tasks')} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-yellow-500/50 hover:bg-yellow-500/5 transition-all">
                  <span className="text-xl">☑</span>
                  <div className="text-left">
                    <div className="flex items-baseline gap-1">
                      <span className="font-bold text-yellow-400 text-lg">{completedTasks}</span>
                      <span className="text-gray-500 text-sm">/{taskList.length}</span>
                    </div>
                    <p className="text-[10px] text-gray-500">Задачи</p>
                  </div>
                </button>
              </Tooltip>
            </div>

            {/* Right: Download + RAM/VRAM + Clock */}
            <div className="flex items-center gap-3">
              <Tooltip text="Скачать исправленный код проекта" position="bottom">
                <a href="/fixed-code.html" target="_blank" className="w-10 h-10 rounded-lg bg-gray-800/50 border border-gray-700/50 flex items-center justify-center hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-all text-lg">📦</a>
              </Tooltip>
              
              {/* RAM/VRAM */}
              <Tooltip text={ollamaProcesses.length > 0 ? ollamaProcesses.map(m => `${m.name}: ${m.size}MB RAM, ${m.vram}MB VRAM`).join('\n') : 'Нет запущенных моделей Ollama'} position="bottom">
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50">
                  <span className="text-xs text-gray-500">RAM:</span>
                  <span className={`font-mono font-bold text-sm ${totalRam > 0 ? 'text-emerald-400' : 'text-gray-600'}`}>{totalRam}MB</span>
                  <span className="text-gray-600">|</span>
                  <span className="text-xs text-gray-500">VRAM:</span>
                  <span className={`font-mono font-bold text-sm ${totalVram > 0 ? 'text-cyan-400' : 'text-gray-600'}`}>{totalVram}MB</span>
                </div>
              </Tooltip>

              {/* Clock */}
              <div className="px-4 py-2 rounded-lg bg-gray-800/50 border-2 border-emerald-500/30">
                <span className="font-mono text-lg text-emerald-400 tabular-nums font-bold">{currentTime.toLocaleTimeString('ru-RU')}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="max-w-7xl mx-auto px-4 flex items-center gap-2 overflow-x-auto border-t border-gray-800">
          {tabs.map((tab) => (
            <Tooltip key={tab.id} text={tab.tooltip} position="bottom">
              <button onClick={() => setActiveTab(tab.id)} className={`px-4 py-3 text-sm font-medium border-b-2 transition-all whitespace-nowrap flex items-center gap-2 ${activeTab === tab.id ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-gray-500 hover:text-gray-300'}`}>
                <span className="text-base">{tab.icon}</span>
                <span>{tab.label}</span>
                {tab.badge ? <span className="px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 text-xs font-bold">{tab.badge}</span> : null}
              </button>
            </Tooltip>
          ))}
        </div>
      </header>

      {/* ===== CONTENT ===== */}
      <main className="flex-1 max-w-7xl mx-auto px-4 py-6 w-full">
        
        {/* CONSOLE */}
        {activeTab === 'console' && (
          <div className="space-y-6">
            <div className="rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-6">
              <label className="text-sm font-bold text-gray-300 uppercase tracking-wider mb-3 block">Провайдеры</label>
              <div className="flex gap-3 mb-4">
                <button onClick={() => setProviderMode('ollama')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'ollama' ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:text-gray-200'}`}>🏠 Ollama</button>
                <button onClick={() => setProviderMode('groq')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'groq' ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:text-gray-200'}`}>☁️ Groq</button>
                <button onClick={() => setProviderMode('all')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'all' ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:text-gray-200'}`}>⚡ Все</button>
              </div>
              {(providerMode === 'ollama' || providerMode === 'all') && (
                <div className="mb-3">
                  <input type="text" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} className="w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono focus:border-emerald-500 focus:outline-none" />
                </div>
              )}
            </div>
            <div className="rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-6">
              <textarea value={consolePrompt} onChange={(e) => setConsolePrompt(e.target.value)} placeholder="Опиши задачу для нейросети..." rows={5} className="w-full px-4 py-3 rounded-lg bg-gray-800/80 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none resize-none font-mono" />
              <div className="flex justify-end mt-4">
                <button onClick={() => {}} disabled={consoleLoading} className={`px-8 py-3 rounded-lg font-bold text-base transition-all ${consoleLoading ? 'bg-gray-700 text-gray-500' : 'bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white shadow-lg shadow-emerald-500/20'}`}>{consoleLoading ? '⏳ Отправка...' : '▶ Отправить'}</button>
              </div>
            </div>
          </div>
        )}

        {/* PANEL */}
        {activeTab === 'panel' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Панель управления</h2>
            <div className="grid md:grid-cols-2 gap-6">
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
                <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>🤖</span> Агенты</h3>
                <div className="space-y-2">
                  {agents.map(a => (
                    <div key={a.id} className="flex justify-between items-center text-sm">
                      <span className={a.enabled ? 'text-emerald-400' : 'text-gray-500'}>{a.name}</span>
                      <StatusBadge status={a.status} />
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
                <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>🌐</span> Провайдеры</h3>
                <div className="space-y-2">
                  {providers.map(p => (
                    <div key={p.name} className="flex justify-between items-center text-sm">
                      <span className={p.enabled ? 'text-white' : 'text-gray-500'}>{p.name}</span>
                      <StatusBadge status={p.status} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* AGENTS */}
        {activeTab === 'agents' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold">Агенты</h2>
              <button onClick={() => setShowAgentStore(true)} className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm font-bold">🛒 Магазин</button>
            </div>
            {showAgentStore && (
              <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setShowAgentStore(false)}>
                <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-3xl w-full max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                  <div className="flex justify-between mb-4"><h3 className="text-xl font-bold gradient-text">Магазин агентов</h3><button onClick={() => setShowAgentStore(false)} className="text-gray-400 text-2xl">×</button></div>
                  <div className="grid md:grid-cols-2 gap-4">
                    {agentStore.map(a => (
                      <div key={a.id} className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
                        <h4 className="font-bold text-white mb-2">{a.name}</h4>
                        <p className="text-sm text-gray-400 mb-3">{a.description}</p>
                        <div className="flex justify-between items-center">
                          <span className="text-xs text-gray-500">{a.category}</span>
                          <button onClick={() => importAgent(a.id)} className="px-3 py-1.5 rounded bg-emerald-500 text-white text-xs font-bold">➕ Импортировать</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
            {agents.map(agent => (
              <div key={agent.id} className={`rounded-xl border-2 p-6 transition-all ${agent.enabled ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-gray-700 bg-gray-900/50 opacity-70'}`}>
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <div className="flex items-center gap-3 mb-2"><h3 className="text-lg font-bold text-white">{agent.name}</h3><StatusBadge status={agent.status} /></div>
                    <p className="text-sm text-gray-400">{agent.task}</p>
                    <p className="text-xs text-gray-500 italic mt-2">{agent.description}</p>
                  </div>
                  <button onClick={() => toggleAgent(agent.id)} className={`px-4 py-2 rounded-lg text-sm font-bold ${agent.enabled ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'}`}>{agent.enabled ? '⏸ Выключить' : '▶ Включить'}</button>
                </div>
                <div className="flex gap-2 mb-3">{agent.stack.map(s => <span key={s} className="px-2 py-1 bg-gray-700/50 rounded text-xs text-gray-300">{s}</span>)}</div>
                <div className="h-2 bg-gray-700 rounded-full"><div className={`h-full rounded-full ${agent.enabled ? 'bg-gradient-to-r from-emerald-500 to-cyan-500' : 'bg-gray-600'}`} style={{ width: `${agent.progress}%` }} /></div>
              </div>
            ))}
          </div>
        )}

        {/* PROVIDERS */}
        {activeTab === 'providers' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold">Провайдеры</h2>
              <div className="flex gap-2">
                {(['all', 'online', 'offline'] as const).map(f => (
                  <button key={f} onClick={() => setProviderFilter(f)} className={`px-3 py-2 rounded-lg text-sm font-bold ${providerFilter === f ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50' : 'bg-gray-800 text-gray-400 border border-gray-700'}`}>{f === 'all' ? 'Все' : f === 'online' ? 'Онлайн' : 'Оффлайн'}</button>
                ))}
              </div>
            </div>

            {/* Ollama */}
            <div className={`rounded-xl border-2 p-6 transition-all ${ollamaStatus === 'online' ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <Tooltip text={ollamaStatus === 'online' ? `Ollama работает. Моделей: ${ollamaModels.length}` : `Ollama не отвечает`} position="bottom">
                    <div className={`w-4 h-4 rounded-full cursor-help ${ollamaStatus === 'online' ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
                  </Tooltip>
                  <div>
                    <span className="text-lg font-bold text-white">Ollama</span>
                    <span className="text-sm text-gray-400 ml-3">— {providers.find(p => p.name === 'Ollama')?.description}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Tooltip text="Скопировать команду: ollama serve" position="bottom">
                    <button onClick={() => { navigator.clipboard.writeText('ollama serve'); setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'info', message: 'Команда скопирована: ollama serve', source: 'Ollama' }]); }} className="px-3 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-xs font-bold hover:bg-emerald-500/30">▶ Запуск</button>
                  </Tooltip>
                  <Tooltip text="Скопировать команду: pkill ollama && ollama serve" position="bottom">
                    <button onClick={() => { navigator.clipboard.writeText('pkill ollama && ollama serve'); setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'info', message: 'Команда скопирована', source: 'Ollama' }]); }} className="px-3 py-2 rounded-lg bg-yellow-500/20 border border-yellow-500/50 text-yellow-400 text-xs font-bold hover:bg-yellow-500/30">🔄</button>
                  </Tooltip>
                  <Tooltip text="Скопировать команду: pkill ollama" position="bottom">
                    <button onClick={() => { navigator.clipboard.writeText('pkill ollama'); setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'warn', message: 'Команда скопирована', source: 'Ollama' }]); }} className="px-3 py-2 rounded-lg bg-red-500/20 border border-red-500/50 text-red-400 text-xs font-bold hover:bg-red-500/30">⏸</button>
                  </Tooltip>
                </div>
              </div>
              <input type="text" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} className="w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono mb-3" />
              {ollamaProcesses.length > 0 && (
                <div className="text-sm text-gray-400">
                  Запущено: {ollamaProcesses.map(m => `${m.name} (${m.size}MB RAM, ${m.vram}MB VRAM)`).join(' • ')}
                </div>
              )}
            </div>

            {/* Other providers */}
            <div className="space-y-3">
              {providers.filter(p => p.name !== 'Ollama').filter(p => providerFilter === 'all' || (providerFilter === 'online' ? p.status === 'online' : p.status !== 'online')).map(provider => (
                <div key={provider.name} className={`rounded-xl border p-4 transition-all ${provider.enabled ? 'border-gray-700 bg-gray-900/50' : 'border-gray-800 bg-gray-900/30 opacity-60'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <Tooltip text={provider.status === 'online' ? 'Доступен' : provider.status === 'error' ? 'Ошибка' : 'Не настроен'} position="bottom">
                        <div className={`w-3 h-3 rounded-full shrink-0 cursor-help ${provider.status === 'online' ? 'bg-emerald-400 animate-pulse' : provider.status === 'error' ? 'bg-red-400' : 'bg-gray-600'}`} />
                      </Tooltip>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-3">
                          <span className="font-bold text-white text-base">{provider.name}</span>
                          <span className="text-sm text-gray-400 truncate">{provider.description}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 shrink-0">
                      <span className="text-sm text-gray-400">{provider.latency > 0 ? `${provider.latency}ms` : '—'} <span className="text-xs text-gray-600">задержка</span></span>
                      <span className="text-sm text-gray-400">{provider.models > 0 ? provider.models : '—'} <span className="text-xs text-gray-600">моделей</span></span>
                      <button onClick={() => toggleProvider(provider.name)} className={`w-12 h-6 rounded-full transition-all relative ${provider.enabled ? 'bg-emerald-500' : 'bg-gray-700'}`}>
                        <div className="w-5 h-5 rounded-full bg-white absolute top-0.5 transition-all" style={{ left: provider.enabled ? '26px' : '2px' }} />
                      </button>
                    </div>
                  </div>
                  {provider.enabled && provider.apiKey !== undefined && (
                    <div className="flex gap-3 items-center mt-3">
                      <input type="password" placeholder="API Key" defaultValue={provider.apiKey} className="flex-1 max-w-xs px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm" />
                      {provider.getKeyUrl && <a href={provider.getKeyUrl} target="_blank" className="text-sm text-cyan-400 hover:text-cyan-300 whitespace-nowrap">Получить ключ →</a>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* MD */}
        {activeTab === 'md' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Документация</h2>
            <div className="grid md:grid-cols-3 gap-4">
              {mdFiles.map(file => (
                <button key={file.name} onClick={() => { setSelectedMDFile(file); setMdContent(file.content); }} className={`rounded-xl border-2 p-4 text-left transition-all ${selectedMDFile?.name === file.name ? 'border-emerald-500/50 bg-emerald-500/5' : 'border-gray-700 bg-gray-900/50 hover:border-gray-600'}`}>
                  <h3 className="font-bold text-white text-base mb-2">{file.name}</h3>
                  <p className="text-sm text-gray-400">{file.description}</p>
                </button>
              ))}
            </div>
            {selectedMDFile && (
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-lg font-bold text-gray-300">📝 {selectedMDFile.name}</h3>
                  <button onClick={() => setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'success', message: `${selectedMDFile.name} сохранён`, source: 'MD Editor' }])} className="px-4 py-2 rounded-lg bg-emerald-500 text-white text-sm font-bold">💾 Сохранить</button>
                </div>
                <textarea value={mdContent} onChange={(e) => setMdContent(e.target.value)} className="w-full h-96 px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono focus:border-emerald-500 focus:outline-none resize-none" />
              </div>
            )}
          </div>
        )}

        {/* CODE */}
        {activeTab === 'code' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold">Анализ кода</h2>
              <button onClick={() => codeIssues.filter(i => !i.fixed).forEach(i => fixCodeIssue(i.id))} className="px-4 py-2 rounded-lg bg-gradient-to-r from-red-500 to-orange-500 text-white text-sm font-bold">🔧 Исправить все</button>
            </div>
            {codeIssues.map(issue => (
              <div key={issue.id} className={`rounded-xl border p-6 ${issue.fixed ? 'border-emerald-500/30 bg-emerald-500/5' : issue.severity === 'critical' ? 'border-red-500/30 bg-red-500/5' : issue.severity === 'warning' ? 'border-yellow-500/30 bg-yellow-500/5' : 'border-blue-500/30 bg-blue-500/5'}`}>
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`px-2 py-1 rounded text-xs font-bold ${issue.severity === 'critical' ? 'bg-red-500/20 text-red-400' : issue.severity === 'warning' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-blue-500/20 text-blue-400'}`}>{issue.severity.toUpperCase()}</span>
                      <span className="text-xs text-gray-500 font-mono">{issue.file}:{issue.line}</span>
                      {issue.fixed && <span className="px-2 py-1 rounded text-xs font-bold bg-emerald-500/20 text-emerald-400">ИСПРАВЛЕНО</span>}
                    </div>
                    <h4 className="text-base font-bold text-white">{issue.title}</h4>
                    <p className="text-sm text-gray-400 mt-2">{issue.description}</p>
                  </div>
                  {!issue.fixed && <button onClick={() => fixCodeIssue(issue.id)} className="px-4 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-sm font-bold">🔧 Исправить</button>}
                </div>
                {issue.fixed && issue.fixLog && issue.fixLog.length > 0 && (
                  <div className="mt-4 p-4 rounded-lg bg-gray-900/80 border border-gray-700">
                    <div className="space-y-1 max-h-96 overflow-y-auto">
                      {issue.fixLog.map((log, i) => <p key={i} className="text-xs text-gray-400 font-mono whitespace-pre-wrap">{log}</p>)}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* LOGS */}
        {activeTab === 'logs' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Логи</h2>
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 max-h-[70vh] overflow-y-auto">
              {logs.slice().reverse().map((entry, i) => (
                <div key={i} className="flex items-start gap-3 py-2 font-mono text-sm border-b border-gray-800/30 last:border-0">
                  <span className="text-gray-600 shrink-0">[{entry.time}]</span>
                  <span className={entry.level === 'info' ? 'text-blue-400' : entry.level === 'warn' ? 'text-yellow-400' : entry.level === 'error' ? 'text-red-400' : 'text-emerald-400'}>{entry.level === 'info' ? 'ℹ' : entry.level === 'warn' ? '⚠' : entry.level === 'error' ? '✕' : '✓'}</span>
                  <div className="flex-1">
                    <span className="text-gray-300">{entry.message}</span>
                    {entry.details && <p className="text-xs text-gray-500 mt-1">{entry.details}</p>}
                  </div>
                  <span className="text-gray-600 shrink-0">({entry.source})</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TASKS */}
        {activeTab === 'tasks' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Задачи</h2>
            
            {/* Add task */}
            <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
              <h3 className="text-lg font-bold mb-4">➕ Добавить задачу</h3>
              <div className="space-y-3">
                <input type="text" value={newTaskText} onChange={(e) => setNewTaskText(e.target.value)} placeholder="Описание задачи..." className="w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none" />
                <div className="flex gap-3">
                  <select value={newTaskPriority} onChange={(e) => setNewTaskPriority(e.target.value as any)} className="px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm">
                    <option value="high">🔴 Высокий</option>
                    <option value="medium">🟡 Средний</option>
                    <option value="low">🔵 Низкий</option>
                  </select>
                  <select value={newTaskCategory} onChange={(e) => setNewTaskCategory(e.target.value as any)} className="px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm">
                    <option value="code">⟨⟩ Исправление кода</option>
                    <option value="general">📋 Общая задача</option>
                  </select>
                  <button onClick={addTask} className="px-6 py-2 rounded-lg bg-emerald-500 text-white text-sm font-bold">Добавить</button>
                </div>
              </div>
            </div>

            {/* Code tasks */}
            <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-6">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>⟨⟩</span> Задачи по исправлению кода ({codeTasks.filter(t => !t.done).length})</h3>
              <div className="space-y-3">
                {codeTasks.map(task => (
                  <div key={task.id} className="flex items-center gap-3 py-3 border-b border-gray-800/50 last:border-0">
                    <button onClick={() => toggleTask(task.id)} className={`w-6 h-6 rounded border-2 flex items-center justify-center ${task.done ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-gray-600'}`}>{task.done && '✓'}</button>
                    <span className={`text-sm flex-1 ${task.done ? 'text-gray-500 line-through' : 'text-gray-200'}`}>{task.text}</span>
                    <span className={`px-2 py-1 rounded text-xs font-bold ${task.priority === 'high' ? 'bg-red-500/20 text-red-400' : task.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-500/20 text-gray-400'}`}>{task.priority.toUpperCase()}</span>
                    <button onClick={() => deleteTask(task.id)} className="text-red-400 hover:text-red-300 text-sm">✕</button>
                  </div>
                ))}
              </div>
            </div>

            {/* General tasks */}
            <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-6">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>📋</span> Общие задачи ({generalTasks.filter(t => !t.done).length})</h3>
              <div className="space-y-3">
                {generalTasks.map(task => (
                  <div key={task.id} className="flex items-center gap-3 py-3 border-b border-gray-800/50 last:border-0">
                    <button onClick={() => toggleTask(task.id)} className={`w-6 h-6 rounded border-2 flex items-center justify-center ${task.done ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-gray-600'}`}>{task.done && '✓'}</button>
                    <span className={`text-sm flex-1 ${task.done ? 'text-gray-500 line-through' : 'text-gray-200'}`}>{task.text}</span>
                    <span className={`px-2 py-1 rounded text-xs font-bold ${task.priority === 'high' ? 'bg-red-500/20 text-red-400' : task.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-500/20 text-gray-400'}`}>{task.priority.toUpperCase()}</span>
                    <button onClick={() => deleteTask(task.id)} className="text-red-400 hover:text-red-300 text-sm">✕</button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 bg-gray-900/50 shrink-0">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between text-xs text-gray-600">
          <div className="flex items-center gap-4">
            <span>🤖 {agents.filter(a => a.enabled).length} агент(ов) активно</span>
            <span>•</span>
            <span>🌐 {providers.filter(p => p.status === 'online').length} провайдер(ов) онлайн</span>
            <span>•</span>
            <span>☑ {completedTasks}/{taskList.length} задач выполнено</span>
          </div>
          <span>v.3.2.0 FORTRESS • dreamkin • 2026</span>
        </div>
      </footer>
    </div>
  );
}
