import { Agent, Provider, LogEntry, CodeIssue, Task, MDFile } from '../types';

export const initialAgents: Agent[] = [
  {
    id: 1,
    name: 'Агент №1 — Развитие системы',
    status: 'active',
    task: 'Разработка и рефакторинг кода',
    stack: ['Python', 'TypeScript', 'React'],
    progress: 45,
    lastActivity: '2 мин назад',
    enabled: true,
    description: 'Основной инженерный агент для развития инфраструктуры drmAIcu.',
    provider: 'ollama',
    model: 'qwen2.5-coder:14b',
    systemPrompt: 'Ты старший инженер-разработчик (Python, FastAPI, React, TypeScript). Пиши чистый, надёжный код без лишней воды. Отвечай на русском языке.',
  },
  {
    id: 2,
    name: 'Агент №2 — Аналитика данных',
    status: 'frozen',
    task: 'Анализ логов и метрик',
    stack: ['Python', 'Pandas', 'SQL'],
    progress: 0,
    lastActivity: '—',
    enabled: false,
    description: 'Агент для анализа данных, метрик производительности и отчётов.',
    provider: 'ollama',
    model: '',
    systemPrompt: 'Ты аналитик данных и системный инженер. Анализируй метрики, логи и структуры данных чётко, структурированно и с конкретными выводами на русском языке.',
  },
  {
    id: 3,
    name: 'Агент №3 — Ревьюер кода',
    status: 'frozen',
    task: 'Поиск багов и проверка типов',
    stack: ['TypeScript', 'Python', 'Security'],
    progress: 0,
    lastActivity: '—',
    enabled: false,
    description: 'Строгий ревьюер для поиска уязвимостей, утечек и ошибок логики.',
    provider: 'ollama',
    model: '',
    systemPrompt: 'Ты строгий code reviewer. Находи логические ошибки, проблемы безопасности, несоответствия типов и предлагай точные исправления. Отвечай кратко и по делу на русском языке.',
  },
];

export const agentStore = [
  {
    id: 'agent-ml',
    name: 'Агент ML',
    description: 'Машинное обучение, оптимизация локальных LLM и инференса.',
    stack: ['Python', 'PyTorch', 'GGUF'],
    category: 'AI/ML',
    provider: 'ollama' as const,
    model: '',
    systemPrompt: 'Ты эксперт по локальным LLM, квантованию GGUF, VRAM-оптимизации и ML-пайплайнам. Давай практичные рекомендации с точными параметрами на русском языке.',
  },
  {
    id: 'agent-web',
    name: 'Агент Web',
    description: 'Full-stack веб-разработчик (React, TypeScript, Tailwind CSS).',
    stack: ['TypeScript', 'React', 'Tailwind'],
    category: 'Web',
    provider: 'ollama' as const,
    model: '',
    systemPrompt: 'Ты senior frontend-разработчик на React, TypeScript и Tailwind CSS. Создавай лаконичные, типобезопасные компоненты без лишних зависимостей.',
  },
  {
    id: 'agent-devops',
    name: 'Агент DevOps',
    description: 'Автоматизация Windows/Linux, скрипты, CI/CD и диагностика.',
    stack: ['PowerShell', 'Batch', 'Git'],
    category: 'DevOps',
    provider: 'ollama' as const,
    model: '',
    systemPrompt: 'Ты DevOps-инженер. Специализируешься на Windows PowerShell, .bat-скриптах, Git-автоматизации и диагностике сервисов.',
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
  { time: '14:32:01', level: 'info', message: 'ЦУ запущена', source: 'main.py' },
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

// Вся документация собрана в docs/ (в корне — только README.md).
export const mdFiles: MDFile[] = [
  { name: 'README.md', description: 'Обзор проекта' },
  { name: 'docs/ARCHITECTURE.md', description: 'Архитектура системы' },
  { name: 'docs/USER_GUIDE.md', description: 'Руководство пользователя' },
  { name: 'docs/NEW_FEATURES.md', description: 'Описание новых функций' },
  { name: 'docs/CHANGELOG.md', description: 'Полная история изменений' },
  { name: 'docs/PLUGIN_SYSTEM.md', description: 'Описание системы плагинов' },
  { name: 'docs/PLUGIN_API_CONTRACT.md', description: 'Контракт Plugin API для разработчиков' },
];

// ANTI-JITTER: увеличены интервалы опроса — частые обновления перерисовывали
// страницу и «дёргали» элементы/счётчики каждые 3–10 секунд.
export const POLL_INTERVALS = {
  PLUGINS: 15000,
  OLLAMA: 15000,
  LOGS: 10000,
  MODELS: 30000,
  PATCHES: 15000,
  RESOURCES: 10000,
} as const;
