import { useState, useEffect } from 'react';

// Типы
interface Agent {
  id: number;
  name: string;
  status: 'active' | 'frozen' | 'offline';
  task: string;
  stack: string[];
  progress: number;
  lastActivity: string;
}

interface Provider {
  name: string;
  status: 'online' | 'offline' | 'error';
  latency: number;
  models: number;
}

interface LogEntry {
  time: string;
  level: 'info' | 'warn' | 'error' | 'success';
  message: string;
  source: string;
}

interface VBAModule {
  name: string;
  status: 'loaded' | 'error' | 'pending';
  description: string;
}

// Данные
const agents: Agent[] = [
  {
    id: 1,
    name: 'Агент №1 — Развитие системы',
    status: 'active',
    task: 'Исправление ошибок компиляции и импорта модулей',
    stack: ['Java', 'Python', 'VBA/Excel'],
    progress: 45,
    lastActivity: '2 мин назад',
  },
  {
    id: 2,
    name: 'Агент №2 — Аналитика данных',
    status: 'frozen',
    task: 'На паузе',
    stack: ['Python', 'Pandas', 'SQL'],
    progress: 0,
    lastActivity: '—',
  },
  {
    id: 3,
    name: 'Агент №3 — Автоматизация отчётов',
    status: 'frozen',
    task: 'На паузе',
    stack: ['Python', 'Excel VBA', 'TTS'],
    progress: 0,
    lastActivity: '—',
  },
];

const providers: Provider[] = [
  { name: 'Ollama', status: 'online', latency: 45, models: 12 },
  { name: 'Groq', status: 'online', latency: 23, models: 8 },
  { name: 'HuggingFace', status: 'online', latency: 120, models: 150 },
  { name: 'OpenRouter', status: 'online', latency: 89, models: 45 },
  { name: 'Gemini', status: 'offline', latency: 0, models: 0 },
  { name: 'Together', status: 'error', latency: 0, models: 0 },
];

const initialLogs: LogEntry[] = [
  { time: '14:32:01', level: 'info', message: 'ЦУ v3.0 FORTRESS запущена', source: 'main.py' },
  { time: '14:32:03', level: 'success', message: 'Агент №1 инициализирован', source: 'agent_engine.py' },
  { time: '14:32:05', level: 'warn', message: 'OSError: [Errno 22] в py_compile.compile (строка ~160)', source: 'main.py' },
  { time: '14:32:07', level: 'error', message: 'drm.cls could not be loaded — Bad file name or number', source: 'mod_Core' },
  { time: '14:32:10', level: 'info', message: 'Провайдер Ollama подключен (12 моделей)', source: 'agent_engine.py' },
  { time: '14:32:12', level: 'info', message: 'Провайдер Groq подключен (8 моделей)', source: 'agent_engine.py' },
  { time: '14:32:15', level: 'warn', message: 'Together API: timeout при подключении', source: 'agent_engine.py' },
  { time: '14:32:18', level: 'info', message: 'VBA модули: mod_Core, drm_Logger, drm_Validator загружены', source: 'mod_Core' },
  { time: '14:32:20', level: 'error', message: 'drm_State: ошибка импорта из временной папки', source: 'mod_Core' },
  { time: '14:32:22', level: 'info', message: 'Ожидание команд оператора...', source: 'main.py' },
];

const vbaModules: VBAModule[] = [
  { name: 'mod_Core', status: 'loaded', description: 'Ядро загрузки/сохранения' },
  { name: 'drm_Logger', status: 'loaded', description: 'Система логирования' },
  { name: 'drm_Validator', status: 'loaded', description: 'Валидация данных' },
  { name: 'drm_State', status: 'error', description: 'Управление состоянием' },
  { name: 'drm_Context', status: 'pending', description: 'Управление контекстом' },
  { name: 'drm_Distribution_DP', status: 'loaded', description: 'Распределение задач' },
  { name: 'drm_Distribution_DP_EdgeControl', status: 'pending', description: 'Контроль граничных условий' },
];

const tasks = [
  { id: 1, text: 'Исправить py_compile ошибку в main.py (строка ~160)', done: false, priority: 'high' },
  { id: 2, text: 'Исправить импорт VBA-модулей в mod_Core', done: false, priority: 'high' },
  { id: 3, text: 'Реализовать модуль TTS для голосовых отчётов', done: false, priority: 'medium' },
  { id: 4, text: 'Тестирование мульти-провайдеров', done: true, priority: 'low' },
  { id: 5, text: 'Документация API агентов', done: false, priority: 'low' },
];

// Компоненты
function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    frozen: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    offline: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    online: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
    loaded: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  };
  const labels: Record<string, string> = {
    active: 'АКТИВЕН',
    frozen: 'ЗАМОРОЖЕН',
    offline: 'ОФФЛАЙН',
    online: 'ОНЛАЙН',
    error: 'ОШИБКА',
    loaded: 'ЗАГРУЖЕН',
    pending: 'ОЖИДАНИЕ',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold border ${colors[status] || colors.offline}`}>
      {labels[status] || status.toUpperCase()}
    </span>
  );
}

function AgentCard({ agent }: { agent: Agent }) {
  return (
    <div className={`rounded-xl border p-4 transition-all hover:scale-[1.02] ${
      agent.status === 'active'
        ? 'border-emerald-500/30 bg-emerald-500/5 shadow-lg shadow-emerald-500/5'
        : agent.status === 'frozen'
        ? 'border-blue-500/20 bg-blue-500/5 opacity-70'
        : 'border-gray-700 bg-gray-800/50 opacity-50'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-white">{agent.name}</h3>
        <StatusBadge status={agent.status} />
      </div>
      <p className="text-xs text-gray-400 mb-3">{agent.task}</p>
      <div className="flex flex-wrap gap-1 mb-3">
        {agent.stack.map((s) => (
          <span key={s} className="px-1.5 py-0.5 bg-gray-700/50 rounded text-[10px] text-gray-300">
            {s}
          </span>
        ))}
      </div>
      <div className="flex items-center justify-between text-[10px] text-gray-500">
        <span>Прогресс: {agent.progress}%</span>
        <span>Активность: {agent.lastActivity}</span>
      </div>
      <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            agent.status === 'active' ? 'bg-emerald-500' : 'bg-blue-500/50'
          }`}
          style={{ width: `${agent.progress}%` }}
        />
      </div>
    </div>
  );
}

function ProviderRow({ provider }: { provider: Provider }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${
          provider.status === 'online' ? 'bg-emerald-400 animate-pulse' :
          provider.status === 'error' ? 'bg-red-400' : 'bg-gray-600'
        }`} />
        <span className="text-sm text-gray-200">{provider.name}</span>
      </div>
      <div className="flex items-center gap-4 text-xs text-gray-400">
        <span>{provider.latency > 0 ? `${provider.latency}ms` : '—'}</span>
        <span>{provider.models > 0 ? `${provider.models} моделей` : 'недоступно'}</span>
        <StatusBadge status={provider.status} />
      </div>
    </div>
  );
}

function LogLine({ entry }: { entry: LogEntry }) {
  const colors: Record<string, string> = {
    info: 'text-blue-400',
    warn: 'text-yellow-400',
    error: 'text-red-400',
    success: 'text-emerald-400',
  };
  const icons: Record<string, string> = {
    info: 'ℹ',
    warn: '⚠',
    error: '✕',
    success: '✓',
  };
  return (
    <div className="flex items-start gap-2 py-1 font-mono text-xs">
      <span className="text-gray-600 shrink-0">[{entry.time}]</span>
      <span className={`${colors[entry.level]} shrink-0`}>{icons[entry.level]}</span>
      <span className="text-gray-300">{entry.message}</span>
      <span className="text-gray-600 ml-auto shrink-0">({entry.source})</span>
    </div>
  );
}

function VBAModuleRow({ module }: { module: VBAModule }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-800/50 last:border-0">
      <div>
        <span className="text-sm text-gray-200 font-mono">{module.name}</span>
        <p className="text-[10px] text-gray-500 mt-0.5">{module.description}</p>
      </div>
      <StatusBadge status={module.status} />
    </div>
  );
}

function TaskItem({ task, onToggle }: { task: typeof tasks[0]; onToggle: () => void }) {
  const priorityColors: Record<string, string> = {
    high: 'bg-red-500/20 text-red-400',
    medium: 'bg-yellow-500/20 text-yellow-400',
    low: 'bg-gray-500/20 text-gray-400',
  };
  const priorityLabels: Record<string, string> = {
    high: 'ВЫСОКИЙ',
    medium: 'СРЕДНИЙ',
    low: 'НИЗКИЙ',
  };
  return (
    <div className="flex items-center gap-3 py-2 border-b border-gray-800/50 last:border-0">
      <button
        onClick={onToggle}
        className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${
          task.done
            ? 'bg-emerald-500 border-emerald-500 text-white'
            : 'border-gray-600 hover:border-gray-400'
        }`}
      >
        {task.done && <span className="text-xs">✓</span>}
      </button>
      <span className={`text-sm flex-1 ${task.done ? 'text-gray-500 line-through' : 'text-gray-200'}`}>
        {task.text}
      </span>
      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${priorityColors[task.priority]}`}>
        {priorityLabels[task.priority]}
      </span>
    </div>
  );
}

export default function App() {
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs);
  const [taskList, setTaskList] = useState(tasks);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [activeTab, setActiveTab] = useState<'dashboard' | 'logs' | 'vba' | 'tasks'>('dashboard');

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const toggleTask = (id: number) => {
    setTaskList(prev => prev.map(t => t.id === id ? { ...t, done: !t.done } : t));
  };

  const completedTasks = taskList.filter(t => t.done).length;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center font-bold text-sm">
              AI
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">drmAIcu</h1>
              <p className="text-[10px] text-gray-500">ЦУ v3.0 FORTRESS • dreamkin</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 text-xs text-gray-400">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Система активна</span>
            </div>
            <div className="font-mono text-sm text-gray-300">
              {currentTime.toLocaleTimeString('ru-RU')}
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-gray-800 bg-gray-900/50">
        <div className="max-w-7xl mx-auto px-4 flex gap-1">
          {[
            { id: 'dashboard' as const, label: 'Панель', icon: '◈' },
            { id: 'logs' as const, label: 'Логи', icon: '▤' },
            { id: 'vba' as const, label: 'VBA Модули', icon: '⧉' },
            { id: 'tasks' as const, label: 'Задачи', icon: '☑' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-all ${
                activeTab === tab.id
                  ? 'border-emerald-500 text-emerald-400'
                  : 'border-transparent text-gray-500 hover:text-gray-300'
              }`}
            >
              <span className="mr-1.5">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            {/* Stats Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Агенты</p>
                <p className="text-2xl font-bold text-emerald-400">1<span className="text-sm text-gray-500">/3</span></p>
              </div>
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Провайдеры</p>
                <p className="text-2xl font-bold text-cyan-400">4<span className="text-sm text-gray-500">/6</span></p>
              </div>
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Задачи</p>
                <p className="text-2xl font-bold text-yellow-400">{completedTasks}<span className="text-sm text-gray-500">/{taskList.length}</span></p>
              </div>
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Ошибки</p>
                <p className="text-2xl font-bold text-red-400">2</p>
              </div>
            </div>

            {/* Agents Section */}
            <section>
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                Агенты
              </h2>
              <div className="grid md:grid-cols-3 gap-3">
                {agents.map((agent) => (
                  <AgentCard key={agent.id} agent={agent} />
                ))}
              </div>
            </section>

            {/* Providers Section */}
            <section>
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                Провайдеры LLM
              </h2>
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                {providers.map((provider) => (
                  <ProviderRow key={provider.name} provider={provider} />
                ))}
              </div>
            </section>

            {/* Recent Logs */}
            <section>
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
                Последние события
              </h2>
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 max-h-48 overflow-y-auto">
                {logs.slice(-5).map((entry, i) => (
                  <LogLine key={i} entry={entry} />
                ))}
              </div>
            </section>

            {/* Voice Report */}
            <section>
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                Голосовой отчёт (TTS)
              </h2>
              <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-4">
                <p className="text-sm text-gray-300 leading-relaxed italic">
                  "Отчёт по проекту drmAIcu. Агент номер один: первая часть задач выполнена. 
                  Система ЦУ v3.0 FORTRESS запущена. Текущая задача: исправить ошибки компиляции 
                  и импорта модулей. Агенты номер два и три: на паузе, не трогаем. 
                  Жду ваших указаний по коду."
                </p>
                <div className="mt-3 flex items-center gap-2">
                  <button className="px-3 py-1.5 rounded-lg bg-purple-500/20 border border-purple-500/30 text-purple-400 text-xs font-medium hover:bg-purple-500/30 transition-all">
                    ▶ Озвучить
                  </button>
                  <span className="text-[10px] text-gray-500">TTS модуль: в разработке</span>
                </div>
              </div>
            </section>
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Системный лог</h2>
              <button
                onClick={() => setLogs(prev => [...prev, {
                  time: new Date().toLocaleTimeString('ru-RU'),
                  level: 'info',
                  message: 'Ручная проверка системы оператором',
                  source: 'operator'
                }])}
                className="px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-gray-300 text-xs hover:bg-gray-700 transition-all"
              >
                + Добавить запись
              </button>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 max-h-[70vh] overflow-y-auto">
              {logs.map((entry, i) => (
                <LogLine key={i} entry={entry} />
              ))}
            </div>
          </div>
        )}

        {activeTab === 'vba' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider">VBA Модули</h2>
              <div className="text-xs text-gray-500">
                Загружено: {vbaModules.filter(m => m.status === 'loaded').length}/{vbaModules.length}
              </div>
            </div>
            
            {/* Error Alert */}
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
              <div className="flex items-start gap-3">
                <span className="text-red-400 text-lg">⚠</span>
                <div>
                  <p className="text-sm font-medium text-red-400">Известные проблемы импорта</p>
                  <p className="text-xs text-gray-400 mt-1">
                    Ошибки: <code className="text-red-300 bg-red-500/10 px-1 rounded">drm.cls could not be loaded</code>, 
                    <code className="text-red-300 bg-red-500/10 px-1 rounded ml-1">Bad file name or number</code>
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Скрипт находит маркеры, создаёт временные файлы, но не может загрузить их обратно в проект.
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              {vbaModules.map((module) => (
                <VBAModuleRow key={module.name} module={module} />
              ))}
            </div>

            {/* Architecture */}
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Архитектура</h3>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2 rounded bg-gray-800/50 border border-gray-700/50">
                  <p className="text-emerald-400 font-mono">Python-ядро</p>
                  <p className="text-gray-500 mt-1">main.py, agent_engine.py</p>
                </div>
                <div className="p-2 rounded bg-gray-800/50 border border-gray-700/50">
                  <p className="text-cyan-400 font-mono">VBA/Excel</p>
                  <p className="text-gray-500 mt-1">mod_Core, drm_* семейство</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'tasks' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider">
                Задачи Агента №1
              </h2>
              <div className="text-xs text-gray-500">
                Выполнено: {completedTasks}/{taskList.length}
              </div>
            </div>

            {/* Progress bar */}
            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-full transition-all"
                style={{ width: `${(completedTasks / taskList.length) * 100}%` }}
              />
            </div>

            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              {taskList.map((task) => (
                <TaskItem key={task.id} task={task} onToggle={() => toggleTask(task.id)} />
              ))}
            </div>

            {/* Rules */}
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Правила работы</h3>
              <ul className="space-y-2 text-xs text-gray-400">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">▸</span>
                  Правило "3 строк": ВСЕГДА показывать 3 строки кода ДО и 3 ПОСЛЕ места вставки
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">▸</span>
                  Целостность: код модулей выдавать ЦЕЛИКОМ и без ошибок
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">▸</span>
                  Краткость: никаких "вод". Только суть
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">▸</span>
                  Голосовой формат: короткие фразы для TTS
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400">▸</span>
                  Агенты №2 и №3: на паузе, не трогаем
                </li>
              </ul>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 bg-gray-900/50 mt-8">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between text-[10px] text-gray-600">
          <span>drmAIcu v2.0 • dreamkin • 2026</span>
          <span>Агент №1 активен • Агенты №2, №3 заморожены</span>
        </div>
      </footer>
    </div>
  );
}
