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

interface CodeIssue {
  id: number;
  severity: 'critical' | 'warning' | 'info';
  line: string;
  title: string;
  description: string;
  fix: string;
  before: string;
  after: string;
}

interface Task {
  id: number;
  text: string;
  done: boolean;
  priority: 'high' | 'medium' | 'low';
}

// ===== ДАННЫЕ =====
const agents: Agent[] = [
  { id: 1, name: 'Агент №1 — Развитие системы', status: 'active', task: 'Исправление ошибок компиляции и импорта модулей', stack: ['Java', 'Python', 'VBA/Excel'], progress: 45, lastActivity: '2 мин назад' },
  { id: 2, name: 'Агент №2 — Аналитика данных', status: 'frozen', task: 'На паузе', stack: ['Python', 'Pandas', 'SQL'], progress: 0, lastActivity: '—' },
  { id: 3, name: 'Агент №3 — Автоматизация отчётов', status: 'frozen', task: 'На паузе', stack: ['Python', 'Excel VBA', 'TTS'], progress: 0, lastActivity: '—' },
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

const initialTasks: Task[] = [
  { id: 1, text: 'Исправить py_compile ошибку в main.py (строка ~160)', done: false, priority: 'high' },
  { id: 2, text: 'Исправить импорт VBA-модулей в mod_Core', done: false, priority: 'high' },
  { id: 3, text: 'Реализовать модуль TTS для голосовых отчётов', done: false, priority: 'medium' },
  { id: 4, text: 'Тестирование мульти-провайдеров', done: true, priority: 'low' },
  { id: 5, text: 'Документация API агентов', done: false, priority: 'low' },
];

// Анализ launcher.bat и settings.json
const launcherIssues: CodeIssue[] = [
  {
    id: 201,
    severity: 'critical',
    line: '11-12',
    title: 'settings.json: ollama_url содержит /v1 — дублирование',
    description: 'В agent_engine.py используется библиотека ollama (Python), которая сама добавляет /v1 к URL. В settings.json указан http://localhost:11434/v1 — будет http://localhost:11434/v1/v1. Ollama не ответит.',
    fix: 'Убрать /v1 из settings.json',
    before: `{
    "groq_api_key": "",
    "ollama_url": "http://localhost:11434/v1"
}`,
    after: `{
    "groq_api_key": "",
    "ollama_url": "http://localhost:11434"
}`,
  },
  {
    id: 202,
    severity: 'critical',
    line: '1-15',
    title: 'launcher.bat: нет проверки существования Python',
    description: 'Если Python не установлен или не в PATH, скрипт уйдёт в бесконечный цикл с ошибкой "python не является внутренней командой". Нет graceful exit.',
    fix: 'Добавить проверку Python в начале скрипта',
    before: `@echo off
title ЦУ Агент - Launcher
color 0A
echo ========================================
echo   ЦУ Агент - Автозапуск
echo ========================================
echo.

:loop`,
    after: `@echo off
title ЦУ Агент - Launcher
color 0A

:: Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ОШИБКА] Python не найден! Установите Python 3.10+
    echo и добавьте в PATH.
    pause
    exit /b 1
)

echo ========================================
echo   ЦУ Агент - Автозапуск
echo ========================================
echo.

:loop`,
  },
  {
    id: 203,
    severity: 'warning',
    line: '11-15',
    title: 'launcher.bat: нет обработки Ctrl+C для выхода',
    description: 'Бесконечный цикл :loop не имеет выхода. Ctrl+C вызывает "Завершить пакетный файл?" — неудобно. Нужна возможность graceful shutdown.',
    fix: 'Добавить проверку restart.flag и обработку Ctrl+C',
    before: `:loop
echo [%time%] Запуск ЦУ...
python main.py

echo.
echo [%time%] ЦУ остановился. Перезапуск через 3 секунды...
timeout /t 3 /nobreak >nul
echo.
goto loop`,
    after: `:loop
echo [%time%] Запуск ЦУ...
python main.py
set EXITCODE=%errorlevel%

:: Проверка флага перезапуска
if exist restart.flag (
    del restart.flag >nul 2>&1
    echo [%time%] Флаг перезапуска найден. Перезапуск...
    timeout /t 2 /nobreak >nul
    goto loop
)

:: Exit code 0 = нормальный выход
if %EXITCODE%==0 (
    echo [%time%] ЦУ остановлен нормально.
    pause
    exit /b 0
)

echo.
echo [%time%] ЦУ упал (код %EXITCODE%). Перезапуск через 3 секунды...
echo Нажмите любую клавишу для отмены...
timeout /t 3 /nobreak >nul
if errorlevel 1 goto loop
echo.
goto loop`,
  },
  {
    id: 204,
    severity: 'warning',
    line: '1-15',
    title: 'launcher.bat: нет логирования в файл',
    description: 'Весь вывод только в консоль. При краше — теряется. Нужен лог-файл для диагностики.',
    fix: 'Добавить tee-подобное логирование в файл',
    before: `:loop
echo [%time%] Запуск ЦУ...
python main.py

echo.
echo [%time%] ЦУ остановился. Перезапуск через 3 секунды...`,
    after: `:: Создание папки логов
if not exist logs mkdir logs

:loop
echo [%time%] Запуск ЦУ...
python main.py 2>&1 | tee logs/cu_%date:~-4%%date:~3,2%%date:~0,2%.log

echo.
echo [%time%] ЦУ остановился. Перезапуск через 3 секунды...`,
  },
  {
    id: 205,
    severity: 'info',
    line: '1-5',
    title: 'launcher.bat: нет проверки наличия main.py',
    description: 'Если main.py отсутствует, скрипт уйдёт в цикл с ошибкой. Нужна проверка перед запуском.',
    fix: 'Добавить проверку существования main.py',
    before: `echo ========================================
echo   ЦУ Агент - Автозапуск
echo ========================================
echo.

:loop`,
    after: `:: Проверка main.py
if not exist main.py (
    color 0C
    echo [ОШИБКА] main.py не найден!
    echo Поместите launcher.bat в папку с main.py
    pause
    exit /b 1
)

echo ========================================
echo   ЦУ Агент - Автозапуск
echo ========================================
echo.

:loop`,
  },
];

// Анализ main.py
const mainPyIssues: CodeIssue[] = [
  {
    id: 101,
    severity: 'critical',
    line: '33-52',
    title: 'EMERGENCY_ENGINE_CODE: asyncio.get_event_loop() — deprecated',
    description: 'Аварийное ядро содержит ту же ошибку что и agent_engine.py. При восстановлении из бэкапа — RuntimeError в Python 3.12+.',
    fix: 'Заменить на asyncio.get_running_loop()',
    before: `    async def get_code_response(self, candidate: Dict, prompt: str) -> Dict:
        try:
            loop = asyncio.get_event_loop()
            def do_request():
                return ollama.chat(model=candidate["model"], messages=[`,
    after: `    async def get_code_response(self, candidate: Dict, prompt: str) -> Dict:
        try:
            loop = asyncio.get_running_loop()
            def do_request():
                return ollama.chat(model=candidate["model"], messages=[`,
  },
  {
    id: 102,
    severity: 'critical',
    line: '225-245',
    title: '_sandbox_test: OSError [Errno 22] на Windows',
    description: 'tempfile.NamedTemporaryFile(delete=False) + exec_module на Windows блокирует файл. Это и есть причина OSError: [Errno 22] Invalid argument при py_compile.compile.',
    fix: 'Использовать delete=False + явный unlink в finally + закрыть spec перед удалением',
    before: `    async def _sandbox_test(self, code: str) -> dict:
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                temp_path = f.name
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_engine", temp_path)`,
    after: `    async def _sandbox_test(self, code: str) -> dict:
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix='.py', prefix='sandbox_')
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(code)
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_engine", temp_path)`,
  },
  {
    id: 103,
    severity: 'warning',
    line: '155-160',
    title: 'validate_python_syntax: нет обработки UnicodeDecodeError',
    description: 'Если код содержит невалидные UTF-8 байты, ast.parse бросит UnicodeDecodeError вместо SyntaxError.',
    fix: 'Обернуть в try/except с обработкой UnicodeDecodeError',
    before: `def validate_python_syntax(code: str) -> tuple:
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)`,
    after: `def validate_python_syntax(code: str) -> tuple:
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)
    except (UnicodeDecodeError, ValueError) as e:
        return False, f"Кодировка: {e}"`,
  },
  {
    id: 104,
    severity: 'warning',
    line: '172-185',
    title: 'get_engine(): race condition без блокировки',
    description: 'Глобальная engine_instance может быть инициализирована дважды при параллельных запросах. Нет threading.Lock.',
    fix: 'Добавить threading.Lock для инициализации',
    before: `engine_instance = None
current_editor = None
current_file = None
guardian_instance = None

def get_engine():
    global engine_instance
    try:
        if engine_instance is None:`,
    after: `engine_instance = None
current_editor = None
current_file = None
guardian_instance = None
_engine_lock = threading.Lock()

def get_engine():
    global engine_instance
    try:
        with _engine_lock:
          if engine_instance is not None:
              return engine_instance
        # далее — инициализация вне lock (долгая операция)`,
  },
  {
    id: 105,
    severity: 'warning',
    line: '245-250',
    title: '_sandbox_test: нет cleanup в finally',
    description: 'Если exec_module бросит исключение, временный файл останется на диске. Нужен finally с os.unlink.',
    fix: 'Добавить finally блок с удалением temp_path',
    before: `                os.unlink(temp_path)
                return {"success": True}
            else:
                os.unlink(temp_path)
                return {"success": False, "error": "Не удалось загрузить"}
        except Exception as e:
            return {"success": False, "error": str(e)}`,
    after: `                return {"success": True}
            else:
                return {"success": False, "error": "Не удалось загрузить"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if temp_path and os.path.exists(temp_path):
                try: os.unlink(temp_path)
                except: pass`,
  },
  {
    id: 106,
    severity: 'info',
    line: '340-345',
    title: 'Debug: ui.timer каждую секунду очищает и перерисовывает весь лог',
    description: 'log_display.clear() + push всех записей каждую секунду — неэффективно. 200 строк × 1 сек = мерцание.',
    fix: 'Использовать инкрементальное обновление — push только новых записей',
    before: `                    async def update_log():
                        while True:
                            log_display.clear()
                            for entry in DEBUG_LOG:
                                log_display.push(entry)
                            await asyncio.sleep(1)`,
    after: `                    _last_log_len = 0
                    async def update_log():
                        nonlocal _last_log_len
                        if len(DEBUG_LOG) > _last_log_len:
                            for entry in DEBUG_LOG[_last_log_len:]:
                                log_display.push(entry)
                            _last_log_len = len(DEBUG_LOG)`,
  },
];

// Анализ agent_engine.py
const codeIssues: CodeIssue[] = [
  {
    id: 1,
    severity: 'critical',
    line: '113',
    title: 'asyncio.get_event_loop() — deprecated',
    description: 'В Python 3.10+ get_event_loop() вызывает DeprecationWarning, а в 3.12+ может выбросить RuntimeError если нет running loop.',
    fix: 'Заменить на asyncio.get_running_loop()',
    before: `    async def _query_ollama(self, model: str, messages: List[Dict], timeout: float = 120.0) -> str:
        loop = asyncio.get_event_loop()
        def do_request():`,
    after: `    async def _query_ollama(self, model: str, messages: List[Dict], timeout: float = 120.0) -> str:
        loop = asyncio.get_running_loop()
        def do_request():`,
  },
  {
    id: 2,
    severity: 'critical',
    line: '126-145',
    title: 'Gemini: потеря контекста диалога',
    description: 'Берётся только messages[-1] — весь системный промпт и история игнорируются. Судья и многораундовые запросы ломаются.',
    fix: 'Конвертировать все messages в формат Gemini contents[]',
    before: `        # Конвертируем сообщения в формат Gemini
        prompt_text = messages[-1]['content']  # Берем последний user message
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }],`,
    after: `        # Конвертируем ВСЕ сообщения в формат Gemini
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        
        payload = {
            "contents": contents,`,
  },
  {
    id: 3,
    severity: 'warning',
    line: '83-93',
    title: 'HuggingFace: клиент есть, метода запроса нет',
    description: 'HF инициализирован как dict с api_key, но в _query_model нет ветки для huggingface. Модели HF не добавлены в _get_candidates.',
    fix: 'Добавить _query_huggingface и модели в _get_candidates',
    before: `    async def _query_model(self, candidate: Dict, messages: List[Dict], timeout: float = 120.0) -> str:
        """Универсальный диспетчер запросов"""
        provider = candidate['provider']
        model = candidate['model']
        
        if provider == 'ollama':`,
    after: `    async def _query_huggingface(self, model: str, messages: List[Dict], timeout: float = 60.0) -> str:
        """Запрос к HuggingFace Inference API"""
        import aiohttp
        api_key = self.config.get('hf_api_key', '')
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {api_key}"}
        prompt = messages[-1]['content']
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={"inputs": prompt}, timeout=timeout) as resp:
                result = await resp.json()
                return result[0]['generated_text']

    async def _query_model(self, candidate: Dict, messages: List[Dict], timeout: float = 120.0) -> str:
        """Универсальный диспетчер запросов"""
        provider = candidate['provider']
        model = candidate['model']
        
        if provider == 'ollama':`,
  },
  {
    id: 4,
    severity: 'warning',
    line: '139',
    title: 'Gemini: нет обработки ошибок aiohttp',
    description: 'Если API вернёт 4xx/5xx, response.json() может вернуть неожиданный формат. Нет проверки status_code.',
    fix: 'Добавить проверку response.status',
    before: `        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=timeout) as response:
                result = await response.json()
                return result['candidates'][0]['content']['parts'][0]['text']`,
    after: `        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Gemini API error {response.status}: {error_text[:100]}")
                result = await response.json()
                return result['candidates'][0]['content']['parts'][0]['text']`,
  },
  {
    id: 5,
    severity: 'warning',
    line: '170',
    title: 'Нет retry-логики при сбоях',
    description: 'Один таймаут = модель исключена. Для нестабильных API (Together, HF) нужен retry.',
    fix: 'Обернуть запрос в retry-цикл (2-3 попытки)',
    before: `        try:
            code = await self._query_model(candidate, messages, timeout=120.0)
            self.log(f"✅ [{provider}] {model_name}: {len(code)} симв.", "SUCCESS")
            return {"candidate": candidate, "code": code, "error": None}
        except asyncio.TimeoutError:`,
    after: `        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                code = await self._query_model(candidate, messages, timeout=120.0)
                self.log(f"✅ [{provider}] {model_name}: {len(code)} симв.", "SUCCESS")
                return {"candidate": candidate, "code": code, "error": None}
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    self.log(f"⏳ [{provider}] Попытка {attempt+2}/{max_retries+1}...", "WARN")
                    await asyncio.sleep(2)
                    continue`,
  },
  {
    id: 6,
    severity: 'info',
    line: '47-65',
    title: 'Дублирование импорта AsyncOpenAI',
    description: 'from openai import AsyncOpenAI повторяется 3 раза. Можно вынести в начало _init_clients.',
    fix: 'Импортировать один раз в начале метода',
    before: `    def _init_clients(self):
        """Ленивая инициализация клиентов"""
        if self.providers['groq']:
            from openai import AsyncOpenAI
            self._clients['groq'] = AsyncOpenAI(`,
    after: `    def _init_clients(self):
        """Ленивая инициализация клиентов"""
        from openai import AsyncOpenAI
        
        if self.providers['groq']:
            self._clients['groq'] = AsyncOpenAI(`,
  },
  {
    id: 7,
    severity: 'info',
    line: '155',
    title: 'Статус WARNING не обрабатывается в логе',
    description: 'В get_code_response используется уровень "WARNING", но в log-колбэке обрабатываются только INFO/SUCCESS/ERROR.',
    fix: 'Унифицировать уровни логирования',
    before: `            elif isinstance(res, dict):
                self.log(f"⚠️ {res['candidate']['name']}: {res.get('error')}", "WARNING")`,
    after: `            elif isinstance(res, dict):
                self.log(f"⚠️ {res['candidate']['name']}: {res.get('error')}", "WARN")`,
  },
];

// ===== КОМПОНЕНТЫ =====
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
    active: 'АКТИВЕН', frozen: 'ЗАМОРОЖЕН', offline: 'ОФФЛАЙН',
    online: 'ОНЛАЙН', error: 'ОШИБКА', loaded: 'ЗАГРУЖЕН', pending: 'ОЖИДАНИЕ',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${colors[status] || colors.offline}`}>
      {labels[status] || status.toUpperCase()}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const config: Record<string, { bg: string; label: string }> = {
    critical: { bg: 'bg-red-500/20 text-red-400 border-red-500/30', label: 'КРИТИЧНО' },
    warning: { bg: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30', label: 'ВНИМАНИЕ' },
    info: { bg: 'bg-blue-500/20 text-blue-400 border-blue-500/30', label: 'ИНФО' },
  };
  const c = config[severity] || config.info;
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${c.bg}`}>{c.label}</span>
  );
}

function AgentCard({ agent }: { agent: Agent }) {
  return (
    <div className={`rounded-xl border p-4 transition-all hover:scale-[1.01] ${
      agent.status === 'active' ? 'border-emerald-500/30 bg-emerald-500/5' :
      agent.status === 'frozen' ? 'border-blue-500/20 bg-blue-500/5 opacity-70' :
      'border-gray-700 bg-gray-800/50 opacity-50'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-white">{agent.name}</h3>
        <StatusBadge status={agent.status} />
      </div>
      <p className="text-xs text-gray-400 mb-3">{agent.task}</p>
      <div className="flex flex-wrap gap-1 mb-3">
        {agent.stack.map((s) => (
          <span key={s} className="px-1.5 py-0.5 bg-gray-700/50 rounded text-[10px] text-gray-300">{s}</span>
        ))}
      </div>
      <div className="flex items-center justify-between text-[10px] text-gray-500">
        <span>Прогресс: {agent.progress}%</span>
        <span>Активность: {agent.lastActivity}</span>
      </div>
      <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${agent.status === 'active' ? 'bg-emerald-500' : 'bg-blue-500/50'}`} style={{ width: `${agent.progress}%` }} />
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
  const colors: Record<string, string> = { info: 'text-blue-400', warn: 'text-yellow-400', error: 'text-red-400', success: 'text-emerald-400' };
  const icons: Record<string, string> = { info: 'ℹ', warn: '⚠', error: '✕', success: '✓' };
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

function TaskItem({ task, onToggle }: { task: Task; onToggle: () => void }) {
  const priorityColors: Record<string, string> = { high: 'bg-red-500/20 text-red-400', medium: 'bg-yellow-500/20 text-yellow-400', low: 'bg-gray-500/20 text-gray-400' };
  const priorityLabels: Record<string, string> = { high: 'ВЫСОКИЙ', medium: 'СРЕДНИЙ', low: 'НИЗКИЙ' };
  return (
    <div className="flex items-center gap-3 py-2 border-b border-gray-800/50 last:border-0">
      <button onClick={onToggle} className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${task.done ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-gray-600 hover:border-gray-400'}`}>
        {task.done && <span className="text-xs">✓</span>}
      </button>
      <span className={`text-sm flex-1 ${task.done ? 'text-gray-500 line-through' : 'text-gray-200'}`}>{task.text}</span>
      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${priorityColors[task.priority]}`}>{priorityLabels[task.priority]}</span>
    </div>
  );
}

function CodeBlock({ code, highlight }: { code: string; highlight?: boolean }) {
  return (
    <pre className={`text-xs font-mono p-3 rounded-lg overflow-x-auto leading-relaxed ${
      highlight === false ? 'bg-red-500/5 border border-red-500/20 text-red-300' :
      highlight === true ? 'bg-emerald-500/5 border border-emerald-500/20 text-emerald-300' :
      'bg-gray-800/50 border border-gray-700/50 text-gray-300'
    }`}>
      {code}
    </pre>
  );
}

function IssueCard({ issue, isExpanded, onToggle }: { issue: CodeIssue; isExpanded: boolean; onToggle: () => void }) {
  const severityBorder: Record<string, string> = {
    critical: 'border-red-500/30',
    warning: 'border-yellow-500/30',
    info: 'border-blue-500/30',
  };
  return (
    <div className={`rounded-xl border ${severityBorder[issue.severity]} bg-gray-900/50 overflow-hidden`}>
      <button onClick={onToggle} className="w-full p-4 text-left flex items-start gap-3 hover:bg-gray-800/30 transition-all">
        <span className={`text-lg mt-0.5 ${issue.severity === 'critical' ? 'text-red-400' : issue.severity === 'warning' ? 'text-yellow-400' : 'text-blue-400'}`}>
          {issue.severity === 'critical' ? '🔴' : issue.severity === 'warning' ? '🟡' : '🔵'}
        </span>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <SeverityBadge severity={issue.severity} />
            <span className="text-[10px] text-gray-500 font-mono">строка {issue.line}</span>
          </div>
          <h4 className="text-sm font-bold text-gray-200">{issue.title}</h4>
          <p className="text-xs text-gray-400 mt-1">{issue.description}</p>
        </div>
        <span className={`text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}>▾</span>
      </button>
      {isExpanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-800/50 pt-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-emerald-400">💡</span>
            <span className="text-gray-300">{issue.fix}</span>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            <div>
              <p className="text-[10px] text-red-400 font-bold uppercase tracking-wider mb-1">❌ Было</p>
              <CodeBlock code={issue.before} highlight={false} />
            </div>
            <div>
              <p className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider mb-1">✅ Стало</p>
              <CodeBlock code={issue.after} highlight={true} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ===== ГЛАВНЫЙ КОМПОНЕНТ =====
export default function App() {
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs);
  const [taskList, setTaskList] = useState<Task[]>(initialTasks);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [activeTab, setActiveTab] = useState<'dashboard' | 'code' | 'logs' | 'vba' | 'tasks'>('dashboard');
  const [expandedIssues, setExpandedIssues] = useState<Set<number>>(new Set([1]));
  const [analyzedFile, setAnalyzedFile] = useState<'engine' | 'main' | 'launcher'>('engine');
  const currentIssues = analyzedFile === 'engine' ? codeIssues : analyzedFile === 'main' ? mainPyIssues : launcherIssues;

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const toggleTask = (id: number) => {
    setTaskList(prev => prev.map(t => t.id === id ? { ...t, done: !t.done } : t));
  };

  const toggleIssue = (id: number) => {
    setExpandedIssues(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const completedTasks = taskList.filter(t => t.done).length;

  const tabs = [
    { id: 'dashboard' as const, label: 'Панель', icon: '◈' },
    { id: 'code' as const, label: 'Анализ кода', icon: '⟨⟩', badge: codeIssues.length + mainPyIssues.length + launcherIssues.length },
    { id: 'logs' as const, label: 'Логи', icon: '▤' },
    { id: 'vba' as const, label: 'VBA', icon: '⧉' },
    { id: 'tasks' as const, label: 'Задачи', icon: '☑' },
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center font-bold text-sm shadow-lg shadow-emerald-500/20">AI</div>
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
            <div className="font-mono text-sm text-gray-300">{currentTime.toLocaleTimeString('ru-RU')}</div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-gray-800 bg-gray-900/50 sticky top-[61px] z-40">
        <div className="max-w-7xl mx-auto px-4 flex gap-1 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-all whitespace-nowrap flex items-center gap-1.5 ${
                activeTab === tab.id ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-gray-500 hover:text-gray-300'
              }`}
            >
              <span>{tab.icon}</span>
              {tab.label}
              {tab.badge && (
                <span className="px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 text-[10px] font-bold">{tab.badge}</span>
              )}
            </button>
          ))}
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">

        {/* ===== DASHBOARD ===== */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
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
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Баги в коде</p>
                <p className="text-2xl font-bold text-red-400">{codeIssues.length + mainPyIssues.length + launcherIssues.length}</p>
              </div>
            </div>

            <section>
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />Агенты
              </h2>
              <div className="grid md:grid-cols-3 gap-3">
                {agents.map((a) => <AgentCard key={a.id} agent={a} />)}
              </div>
            </section>

            <section>
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />Провайдеры LLM
              </h2>
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                {providers.map((p) => <ProviderRow key={p.name} provider={p} />)}
              </div>
            </section>

            {/* Code Issues Summary */}
            <section>
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400" />Найдено проблем в коде
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <button onClick={() => { setActiveTab('code'); setAnalyzedFile('engine'); }} className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-left hover:bg-emerald-500/10 transition-all">
                  <p className="text-lg font-bold text-emerald-400">agent_engine.py</p>
                  <p className="text-xs text-gray-400 mt-1">{codeIssues.length} проблем</p>
                </button>
                <button onClick={() => { setActiveTab('code'); setAnalyzedFile('main'); }} className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4 text-left hover:bg-cyan-500/10 transition-all">
                  <p className="text-lg font-bold text-cyan-400">main.py</p>
                  <p className="text-xs text-gray-400 mt-1">{mainPyIssues.length} проблем</p>
                </button>
                <button onClick={() => { setActiveTab('code'); setAnalyzedFile('launcher'); }} className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-4 text-left hover:bg-yellow-500/10 transition-all">
                  <p className="text-lg font-bold text-yellow-400">launcher + config</p>
                  <p className="text-xs text-gray-400 mt-1">{launcherIssues.length} проблем</p>
                </button>
                <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
                  <p className="text-2xl font-bold text-red-400">{[...codeIssues, ...mainPyIssues, ...launcherIssues].filter(i => i.severity === 'critical').length}</p>
                  <p className="text-xs text-gray-400 mt-1">Критических</p>
                </div>
              </div>
            </section>

            <section>
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />Голосовой отчёт (TTS)
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

        {/* ===== CODE ANALYSIS ===== */}
        {activeTab === 'code' && (
          <div className="space-y-4">
            {/* File switcher */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => { setAnalyzedFile('engine'); setExpandedIssues(new Set([1])); }}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    analyzedFile === 'engine'
                      ? 'bg-emerald-500/20 border border-emerald-500/30 text-emerald-400'
                      : 'bg-gray-800 border border-gray-700 text-gray-400 hover:text-gray-200'
                  }`}
                >
                  agent_engine.py
                </button>
                <button
                  onClick={() => { setAnalyzedFile('main'); setExpandedIssues(new Set([101])); }}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    analyzedFile === 'main'
                      ? 'bg-emerald-500/20 border border-emerald-500/30 text-emerald-400'
                      : 'bg-gray-800 border border-gray-700 text-gray-400 hover:text-gray-200'
                  }`}
                >
                  main.py
                </button>
                <button
                  onClick={() => { setAnalyzedFile('launcher'); setExpandedIssues(new Set([201])); }}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    analyzedFile === 'launcher'
                      ? 'bg-emerald-500/20 border border-emerald-500/30 text-emerald-400'
                      : 'bg-gray-800 border border-gray-700 text-gray-400 hover:text-gray-200'
                  }`}
                >
                  launcher.bat / settings.json
                </button>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setExpandedIssues(new Set(currentIssues.map(i => i.id)))}
                  className="px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-gray-300 text-xs hover:bg-gray-700 transition-all"
                >
                  Раскрыть все
                </button>
                <button
                  onClick={() => setExpandedIssues(new Set())}
                  className="px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-gray-300 text-xs hover:bg-gray-700 transition-all"
                >
                  Свернуть все
                </button>
              </div>
            </div>

            {/* File info */}
            <div>
              <h2 className="text-lg font-bold text-white">
                {analyzedFile === 'engine' ? 'Анализ agent_engine.py v2.2' : analyzedFile === 'main' ? 'Анализ main.py v3.0.2 FORTRESS' : 'Анализ launcher.bat + settings.json'}
              </h2>
              <p className="text-xs text-gray-500 mt-1">
                {analyzedFile === 'engine'
                  ? 'Мульти-провайдеры • Детальный лог • Async/await'
                  : analyzedFile === 'main'
                  ? 'NiceGUI • AI-Guardian • 5 уровней защиты • Sandbox'
                  : 'Автозапуск • Конфигурация • Логирование'}
              </p>
            </div>

            {/* Summary bar */}
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              <div className="flex flex-wrap items-center gap-4 text-xs">
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500" />
                  <span className="text-gray-300">{currentIssues.filter(i => i.severity === 'critical').length} критических</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-yellow-500" />
                  <span className="text-gray-300">{currentIssues.filter(i => i.severity === 'warning').length} предупреждений</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-blue-500" />
                  <span className="text-gray-300">{currentIssues.filter(i => i.severity === 'info').length} рекомендаций</span>
                </div>
                <div className="ml-auto text-gray-500">
                  {analyzedFile === 'engine' ? '~230 строк • Python' : analyzedFile === 'main' ? '~400 строк • Python' : '15 строк • BAT + JSON'}
                </div>
              </div>
            </div>

            {/* Issues */}
            <div className="space-y-3">
              {currentIssues.map((issue) => (
                <IssueCard
                  key={issue.id}
                  issue={issue}
                  isExpanded={expandedIssues.has(issue.id)}
                  onToggle={() => toggleIssue(issue.id)}
                />
              ))}
            </div>

            {/* Architecture diagram */}
            {analyzedFile === 'engine' && (
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Архитектура запросов</h3>
              <div className="flex flex-col items-center gap-2">
                <div className="px-4 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold">
                  run_task(prompt)
                </div>
                <div className="text-gray-600">↓</div>
                <div className="px-4 py-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-bold">
                  _get_candidates() → {providers.filter(p => p.status === 'online').length} провайдеров
                </div>
                <div className="text-gray-600">↓</div>
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 w-full">
                  {['Ollama', 'Groq', 'HF', 'OpenRouter', 'Gemini', 'Together'].map((p) => (
                    <div key={p} className="px-2 py-1.5 rounded bg-gray-800/50 border border-gray-700/50 text-center text-[10px] text-gray-400">
                      {p}
                    </div>
                  ))}
                </div>
                <div className="text-gray-600">↓ asyncio.gather</div>
                <div className="px-4 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs font-bold">
                  judge_responses() → лучший код
                </div>
              </div>
            </div>
            )}

            {analyzedFile === 'launcher' && (
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Схема запуска</h3>
                <div className="flex flex-col items-center gap-2">
                  <div className="px-4 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold">
                    launcher.bat
                  </div>
                  <div className="text-gray-600">↓ проверка Python + main.py</div>
                  <div className="px-4 py-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-bold">
                    settings.json
                  </div>
                  <div className="text-gray-600">↓ загрузка конфига</div>
                  <div className="px-4 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs font-bold">
                    python main.py
                  </div>
                  <div className="text-gray-600">↓ exit code</div>
                  <div className="grid grid-cols-3 gap-2 w-full">
                    <div className="px-2 py-1.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-center text-[10px] text-emerald-400">
                      code=0 → выход
                    </div>
                    <div className="px-2 py-1.5 rounded bg-yellow-500/10 border border-yellow-500/30 text-center text-[10px] text-yellow-400">
                      restart.flag → перезапуск
                    </div>
                    <div className="px-2 py-1.5 rounded bg-red-500/10 border border-red-500/30 text-center text-[10px] text-red-400">
                      code≠0 → retry
                    </div>
                  </div>
                </div>
              </div>
            )}

            {analyzedFile === 'main' && (
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Архитектура FORTRESS</h3>
                <div className="flex flex-col items-center gap-2">
                  <div className="px-4 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold">
                    main.py → create_ui()
                  </div>
                  <div className="text-gray-600">↓</div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 w-full">
                    {['Дашборд', 'API', 'LLM', 'Обновления'].map((t) => (
                      <div key={t} className="px-2 py-1.5 rounded bg-gray-800/50 border border-gray-700/50 text-center text-[10px] text-gray-400">{t}</div>
                    ))}
                  </div>
                  <div className="text-gray-600">↓</div>
                  <div className="px-4 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs font-bold">
                    AI-Guardian (5 уровней)
                  </div>
                  <div className="grid grid-cols-5 gap-1 w-full text-[9px] text-center">
                    {['Синтаксис', 'Структура', 'AI-Судья', 'Sandbox', 'Бэкап'].map((s, i) => (
                      <div key={s} className="px-1 py-1.5 rounded bg-gray-800/30 border border-gray-700/30 text-gray-500">
                        <span className="text-emerald-400">{i + 1}.</span> {s}
                      </div>
                    ))}
                  </div>
                  <div className="text-gray-600">↓</div>
                  <div className="px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-bold">
                    agent_engine.py (ЗАЩИЩЁН)
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ===== LOGS ===== */}
        {activeTab === 'logs' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Системный лог</h2>
              <button
                onClick={() => setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'info', message: 'Ручная проверка системы оператором', source: 'operator' }])}
                className="px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-gray-300 text-xs hover:bg-gray-700 transition-all"
              >
                + Добавить запись
              </button>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 max-h-[70vh] overflow-y-auto">
              {logs.map((entry, i) => <LogLine key={i} entry={entry} />)}
            </div>
          </div>
        )}

        {/* ===== VBA ===== */}
        {activeTab === 'vba' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider">VBA Модули</h2>
              <div className="text-xs text-gray-500">Загружено: {vbaModules.filter(m => m.status === 'loaded').length}/{vbaModules.length}</div>
            </div>
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
              <div className="flex items-start gap-3">
                <span className="text-red-400 text-lg">⚠</span>
                <div>
                  <p className="text-sm font-medium text-red-400">Известные проблемы импорта</p>
                  <p className="text-xs text-gray-400 mt-1">
                    Ошибки: <code className="text-red-300 bg-red-500/10 px-1 rounded">drm.cls could not be loaded</code>,
                    <code className="text-red-300 bg-red-500/10 px-1 rounded ml-1">Bad file name or number</code>
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Скрипт находит маркеры, создаёт временные файлы, но не может загрузить их обратно в проект.</p>
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              {vbaModules.map((m) => <VBAModuleRow key={m.name} module={m} />)}
            </div>
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

        {/* ===== TASKS ===== */}
        {activeTab === 'tasks' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Задачи Агента №1</h2>
              <div className="text-xs text-gray-500">Выполнено: {completedTasks}/{taskList.length}</div>
            </div>
            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-full transition-all" style={{ width: `${(completedTasks / taskList.length) * 100}%` }} />
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              {taskList.map((t) => <TaskItem key={t.id} task={t} onToggle={() => toggleTask(t.id)} />)}
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Правила работы</h3>
              <ul className="space-y-2 text-xs text-gray-400">
                <li className="flex items-start gap-2"><span className="text-emerald-400">▸</span>Правило "3 строк": 3 строки ДО и 3 ПОСЛЕ места вставки</li>
                <li className="flex items-start gap-2"><span className="text-emerald-400">▸</span>Код модулей — ЦЕЛИКОМ и без ошибок</li>
                <li className="flex items-start gap-2"><span className="text-emerald-400">▸</span>Краткость: никаких "вод"</li>
                <li className="flex items-start gap-2"><span className="text-emerald-400">▸</span>Голосовой формат: короткие фразы для TTS</li>
                <li className="flex items-start gap-2"><span className="text-emerald-400">▸</span>Агенты №2 и №3: на паузе</li>
              </ul>
            </div>
          </div>
        )}
      </main>

      {/* Download Section */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="rounded-xl border border-emerald-500/30 bg-gradient-to-r from-emerald-500/10 to-cyan-500/10 p-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                📦 Исправленный код готов
              </h3>
              <p className="text-sm text-gray-400 mt-1">
                4 файла с исправлениями • 18 проблем решено • Копируй и заменяй
              </p>
            </div>
            <a
              href="/fixed-code.html"
              target="_blank"
              className="px-6 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-sm transition-all shadow-lg shadow-emerald-500/20 hover:scale-105"
            >
              📋 Открыть код →
            </a>
          </div>
        </div>
      </div>

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
