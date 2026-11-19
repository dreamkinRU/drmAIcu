import { Agent, Provider, LogEntry, CodeIssue, Task, MDFile } from '../types';

export const initialAgents: Agent[] = [
  {
    id: 1,
    name: 'Агент №1 — Развитие системы',
    status: 'active',
    task: 'Исправление ошибок компиляции',
    stack: ['Java', 'Python', 'VBA/Excel'],
    progress: 45,
    lastActivity: '2 мин назад',
    enabled: true,
    description: 'Основной агент для развития инфраструктуры drmAIcu.',
  },
  {
    id: 2,
    name: 'Агент №2 — Аналитика данных',
    status: 'frozen',
    task: 'На паузе',
    stack: ['Python', 'Pandas', 'SQL'],
    progress: 0,
    lastActivity: '—',
    enabled: false,
    description: 'Агент для анализа данных и построения отчётов.',
  },
  {
    id: 3,
    name: 'Агент №3 — Автоматизация отчётов',
    status: 'frozen',
    task: 'На паузе',
    stack: ['Python', 'Excel VBA', 'TTS'],
    progress: 0,
    lastActivity: '—',
    enabled: false,
    description: 'Агент для автоматизации создания отчётов.',
  },
];

export const agentStore = [
  {
    id: 'agent-ml',
    name: 'Агент ML',
    description: 'Машинное обучение, нейронные сети.',
    stack: ['Python', 'TensorFlow'],
    category: 'AI/ML',
  },
  {
    id: 'agent-web',
    name: 'Агент Web',
    description: 'Full-stack веб-разработчик.',
    stack: ['JavaScript', 'React'],
    category: 'Web',
  },
  {
    id: 'agent-devops',
    name: 'Агент DevOps',
    description: 'CI/CD, контейнеризация.',
    stack: ['Docker', 'Kubernetes'],
    category: 'DevOps',
  },
];

export const initialProviders: Provider[] = [
  { name: 'Ollama', status: 'offline', latency: 0, models: 0, description: 'Локальные модели', url: 'http://localhost:11434', enabled: true },
  { name: 'Groq', status: 'online', latency: 23, models: 8, description: 'Быстрые облачные модели', url: 'https://console.groq.com', enabled: true, apiKey: '', getKeyUrl: 'https://console.groq.com/keys' },
  { name: 'HuggingFace', status: 'online', latency: 120, models: 150, description: 'Библиотека моделей', url: 'https://huggingface.co', enabled: true, apiKey: '', getKeyUrl: 'https://huggingface.co/settings/tokens' },
  { name: 'OpenRouter', status: 'online', latency: 89, models: 45, description: 'Агрегатор моделей', url: 'https://openrouter.ai', enabled: true, apiKey: '', getKeyUrl: 'https://openrouter.ai/workspaces/default/keys' },
  { name: 'Gemini', status: 'offline', latency: 0, models: 0, description: 'Google Gemini', url: 'https://aistudio.google.com', enabled: false, apiKey: '', getKeyUrl: 'https://aistudio.google.com/api-keys' },
  { name: 'Together', status: 'error', latency: 0, models: 0, description: 'Together AI', url: 'https://api.together.xyz', enabled: false, apiKey: '' },
];

export const initialLogs: LogEntry[] = [
  { time: '14:32:01', level: 'info', message: 'ЦУ v.3.4.3 TOGGLES запущена', source: 'main.py' },
];

export const initialCodeIssues: CodeIssue[] = [
  {
    id: 1,
    severity: 'critical',
    line: '113',
    file: 'agent_engine.py',
    title: 'asyncio.get_event_loop() — deprecated',
    description: 'В Python 3.10+ вызывает DeprecationWarning',
    fix: 'Заменить на asyncio.get_running_loop()',
    before: 'loop = asyncio.get_event_loop()',
    after: 'loop = asyncio.get_running_loop()',
    fixed: false,
    fixLog: [],
  },
  {
    id: 2,
    severity: 'critical',
    line: '126',
    file: 'agent_engine.py',
    title: 'Gemini: потеря контекста',
    description: 'Берётся только messages[-1]',
    fix: 'Конвертировать все messages',
    before: 'prompt_text = messages[-1]',
    after: 'contents = messages.map(...)',
    fixed: false,
    fixLog: [],
  },
  {
    id: 3,
    severity: 'warning',
    line: '83',
    file: 'agent_engine.py',
    title: 'HuggingFace: нет метода запроса',
    description: 'Клиент есть, метода нет',
    fix: 'Добавить _query_huggingface',
    before: '// Нет метода',
    after: 'async _query_huggingface(...)',
    fixed: false,
    fixLog: [],
  },
];

export const initialTasks: Task[] = [
  { id: 1, text: 'Исправить py_compile ошибку в main.py', done: false, priority: 'high', category: 'code' },
  { id: 2, text: 'Исправить импорт VBA-модулей', done: false, priority: 'high', category: 'code' },
  { id: 3, text: 'Реализовать модуль TTS', done: false, priority: 'medium', category: 'general' },
  { id: 4, text: 'Тестирование мульти-провайдеров', done: true, priority: 'low', category: 'general' },
];

export const mdFiles: MDFile[] = [
  { name: 'CHANGELOG.md', description: 'Полная история изменений' },
  { name: 'USER_GUIDE.md', description: 'Руководство пользователя' },
  { name: 'NEW_FEATURES.md', description: 'Описание новых функций' },
  { name: 'ARCHITECTURE.md', description: 'Архитектура системы' },
];

// Интервалы опроса в миллисекундах.
export const POLL_INTERVALS = {
  OLLAMA: 5000,
  LOGS: 3000,
  MODELS: 10000,
  PATCHES: 5000,
} as const;
