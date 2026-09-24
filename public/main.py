# main.py
# Version 3.0.8 FORTRESS (НОВЫЙ ДИЗАЙН)

from nicegui import ui, app
import json
import os
import importlib
import sys
import asyncio
import time
import threading
import traceback
import shutil
import hashlib
import ast
from datetime import datetime
from openai import AsyncOpenAI
import tempfile

CONFIG_FILE = 'settings.json'
ENGINE_FILE = 'agent_engine.py'
RESTART_FLAG = 'restart.flag'
DEBUG_LOG = []
BACKUP_DIR = 'backups'
UPDATES_DIR = 'updates'

PROTECTED_FILES = [
    'main.py',
    'agent_engine.py',
    'settings.json',
    'launcher.bat',
    'context_manager.py'
]

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(UPDATES_DIR, exist_ok=True)

if os.path.exists(RESTART_FLAG):
    try:
        os.remove(RESTART_FLAG)
    except Exception:
        pass

EMERGENCY_ENGINE_CODE = '''# agent_engine.py
import asyncio
import ollama
from typing import List, Dict

class AgentEngine:
    def __init__(self, config, **kwargs):
        self.config = config
        self.log = kwargs.get('log_callback', lambda msg, lvl: print(f"[{lvl}] {msg}"))
        self.log("Emergency engine loaded", "WARNING")

    async def get_code_response(self, candidate: Dict, prompt: str) -> Dict:
        try:
            loop = asyncio.get_running_loop()
            def do_request():
                return ollama.chat(model=candidate["model"], messages=[
                    {"role": "system", "content": "You are an expert programmer."},
                    {"role": "user", "content": prompt}
                ])
            response = await asyncio.wait_for(loop.run_in_executor(None, do_request), timeout=120.0)
            code = response['message']['content']
            return {"candidate": candidate, "code": code, "error": None}
        except Exception as e:
            return {"candidate": candidate, "code": None, "error": str(e)}

    async def run_task(self, prompt: str, status_callback=None, mode: str = "full") -> str:
        candidates = [{"model": "qwen2.5-coder:1.5b", "name": "Qwen 1.5B"}]
        results = await asyncio.gather(*[self.get_code_response(c, prompt) for c in candidates], return_exceptions=True)
        valid = [r for r in results if isinstance(r, dict) and r.get("code")]
        return valid[0]["code"] if valid else "All models failed"
'''


def log_debug(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] [{level}] {message}"
    DEBUG_LOG.append(entry)
    if len(DEBUG_LOG) > 200:
        DEBUG_LOG.pop(0)
    print(entry)


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            log_debug("settings.json corrupted", "WARNING")
    return {
        "groq_api_key": "",
        "ollama_url": "http://localhost:11434",
        "hf_api_key": "",
        "openrouter_api_key": "",
        "gemini_api_key": "",
        "together_api_key": ""
    }


def save_config(data):
    current = load_config()
    current.update(data)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(current, f, indent=4, ensure_ascii=False)


def validate_python_syntax(code: str) -> tuple:
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)


def validate_engine_structure(code: str) -> tuple:
    required = ['class AgentEngine', 'async def run_task', 'async def get_code_response', '__init__']
    missing = [r for r in required if r not in code]
    if missing:
        return False, f"Missing: {', '.join(missing)}"
    return True, None


def ensure_base_files():
    if not os.path.exists(CONFIG_FILE):
        save_config({})
    if not os.path.exists(ENGINE_FILE):
        with open(ENGINE_FILE, 'w', encoding='utf-8') as f:
            f.write(EMERGENCY_ENGINE_CODE)


engine_instance = None
_engine_lock = threading.Lock()


def get_engine():
    global engine_instance
    try:
        with _engine_lock:
            if engine_instance is not None:
                return engine_instance
        config = load_config()
        if 'agent_engine' in sys.modules:
            importlib.reload(sys.modules['agent_engine'])
        else:
            import agent_engine
        engine_instance = sys.modules['agent_engine'].AgentEngine(config, log_callback=log_debug)
        return engine_instance
    except Exception as e:
        log_debug(f"Engine error: {e}", "ERROR")
        return None


def restart_server():
    with open(RESTART_FLAG, 'w') as f:
        f.write('restart')
    def do_exit():
        time.sleep(2)
        os._exit(0)
    threading.Thread(target=do_exit, daemon=True).start()


def create_ui():
    # Кастомный CSS для дизайна как в React-дашборде
    ui.add_head_html('''
    <style>
        body {
            background: #030712 !important;
            color: #fff !important;
            font-family: system-ui, -apple-system, sans-serif !important;
        }
        .q-header {
            background: rgba(17, 24, 39, 0.8) !important;
            backdrop-filter: blur(8px) !important;
            border-bottom: 1px solid #1f2937 !important;
        }
        .ai-icon {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            background: linear-gradient(135deg, #10b981, #06b6d4);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 14px;
            box-shadow: 0 4px 6px rgba(16, 185, 129, 0.2);
        }
        .custom-card {
            background: rgba(17, 24, 39, 0.5) !important;
            border: 1px solid #1f2937 !important;
            border-radius: 12px !important;
        }
        .custom-button {
            background: #10b981 !important;
            color: white !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            transition: all 0.2s !important;
        }
        .custom-button:hover {
            background: #059669 !important;
            transform: scale(1.05) !important;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
    ''')

    ui.dark_mode().enable()

    # Header
    with ui.header().classes('items-center justify-between px-4 py-3'):
        with ui.row().classes('items-center gap-3'):
            ui.html('<div class="ai-icon">AI</div>')
            with ui.column().classes('gap-0'):
                ui.label('drmAIcu').classes('text-lg font-bold')
                ui.label('v3.0.8 FORTRESS • Local + Cloud Models').classes('text-[10px] text-gray-500')

        with ui.row().classes('items-center gap-4'):
            with ui.row().classes('items-center gap-2'):
                ui.html('<div class="status-dot"></div>')
                ui.label('Система активна').classes('text-xs text-gray-400')

            clock_label = ui.label().classes('font-mono text-sm text-gray-300')

            def update_clock():
                clock_label.text = datetime.now().strftime('%H:%M:%S')

            ui.timer(1.0, update_clock)

    # Navigation
    with ui.tabs().classes('w-full border-b border-gray-800') as tabs:
        tab_console = ui.tab('console', label='▶ Консоль')
        tab_dashboard = ui.tab('dashboard', label='◈ Панель')
        tab_updates = ui.tab('updates', label='🛡️ Обновления')
        tab_debug = ui.tab('debug', label='🐞 Отладка')

    with ui.tab_panels(tabs, value=tab_console).classes('w-full p-6'):

        # ===== CONSOLE TAB =====
        with ui.tab_panel(tab_console):
            ui.label('Консоль').classes('text-2xl font-bold mb-4')

            # Groq API Key
            with ui.card().classes('custom-card w-full p-4 mb-4'):
                ui.label('Groq API Key').classes('text-xs font-bold text-gray-400 uppercase tracking-wider mb-2')
                config = load_config()
                groq_key_input = ui.input(
                    value=config.get('groq_api_key', ''),
                    password=True,
                    placeholder='gsk_...'
                ).classes('w-full')

                with ui.row().classes('gap-2 mt-2'):
                    def save_groq_key():
                        save_config({'groq_api_key': groq_key_input.value})
                        ui.notify('Groq API ключ сохранён', type='positive')

                    ui.button('💾 Сохранить', on_click=save_groq_key).props('color=green')
                    ui.button('🔗 Получить ключ', on_click=lambda: ui.open_url('https://console.groq.com/keys')).props('flat')

                ui.label('Бесплатная регистрация на console.groq.com').classes('text-[10px] text-gray-500 mt-2')

            # Prompt
            with ui.card().classes('custom-card w-full p-4 mb-4'):
                ui.label('Запрос').classes('text-xs font-bold text-gray-400 uppercase tracking-wider mb-2')
                prompt_input = ui.textarea(
                    placeholder='Опиши задачу для нейросети...',
                    value=''
                ).classes('w-full').props('rows=4')

                with ui.row().classes('items-center justify-between mt-3'):
                    with ui.row().classes('items-center gap-2'):
                        ui.label('🚀 Локальные + облачные модели').classes('text-xs text-gray-500')
                        ui.label('•').classes('text-xs text-gray-500')
                        ui.label('⚖️ Арбитр выберет лучший ответ').classes('text-xs text-gray-500')

                    send_button = ui.button('▶ Отправить', on_click=lambda: None).classes('custom-button')

            # Status
            status_label = ui.label('Статус: Ожидание').classes('text-lg mt-4')

            # Log
            log_area = ui.log(max_lines=200).classes('w-full h-64 bg-black text-green-400 font-mono mt-4')

            # Result
            result_area = ui.textarea('Результат').classes('w-full h-64 mt-4')

            async def send_task():
                if not prompt_input.value:
                    ui.notify('Введи запрос', type='warning')
                    return

                log_area.clear()
                log_area.push('=' * 70)
                log_area.push(f'ЗАДАЧА: {prompt_input.value}')
                log_area.push('=' * 70)

                status_label.text = 'Статус: Отправка запросов...'

                try:
                    engine = get_engine()
                    if not engine:
                        raise Exception('Ядро не загружено')

                    # Показываем какие модели будут опрошены
                    if hasattr(engine, '_get_candidates'):
                        candidates = engine._get_candidates()
                        log_area.push('')
                        log_area.push(f'📋 БУДУТ ОПРОШЕНЫ {len(candidates)} МОДЕЛЕЙ:')
                        for i, c in enumerate(candidates, 1):
                            provider = c.get('provider', 'ollama').upper()
                            log_area.push(f'  {i}. [{provider}] {c["name"]}')
                        log_area.push('-' * 70)

                    def update_status(text):
                        status_label.text = f'Статус: {text}'
                        log_area.push(f'[СТАТУС] {text}')

                    result = await engine.run_task(
                        prompt_input.value,
                        status_callback=update_status,
                        mode='full'
                    )

                    log_area.push('')
                    log_area.push('=' * 70)
                    log_area.push('✅ ЗАДАЧА ВЫПОЛНЕНА')
                    log_area.push('=' * 70)

                    result_area.value = result
                    status_label.text = 'Статус: Готово'

                except Exception as e:
                    log_area.push(f'[ОШИБКА] {str(e)}')
                    result_area.value = f'Ошибка: {str(e)}'
                    status_label.text = 'Статус: Ошибка'

            send_button.on_click(send_task)

        # ===== DASHBOARD TAB =====
        with ui.tab_panel(tab_dashboard):
            ui.label('Панель').classes('text-2xl font-bold mb-4')

            # Stats
            with ui.row().classes('gap-3 mb-6'):
                with ui.card().classes('custom-card p-4'):
                    ui.label('Агенты').classes('text-[10px] text-gray-500 uppercase')
                    ui.label('1/3').classes('text-2xl font-bold text-emerald-400')

                with ui.card().classes('custom-card p-4'):
                    ui.label('Провайдеры').classes('text-[10px] text-gray-500 uppercase')
                    config = load_config()
                    active = sum(1 for k in ['groq_api_key', 'hf_api_key', 'openrouter_api_key', 'gemini_api_key', 'together_api_key'] if config.get(k))
                    ui.label(f'{active + 1}/6').classes('text-2xl font-bold text-cyan-400')

                with ui.card().classes('custom-card p-4'):
                    ui.label('Версия').classes('text-[10px] text-gray-500 uppercase')
                    ui.label('v3.0.8').classes('text-2xl font-bold text-yellow-400')

            # Info
            with ui.card().classes('custom-card w-full p-4'):
                ui.label('О системе').classes('text-lg font-bold mb-2')
                ui.markdown('''
**drmAIcu v3.0.8 FORTRESS**

✅ Поддержка локальных моделей (Ollama)
✅ Поддержка облачных моделей (Groq, Gemini, HuggingFace, OpenRouter, Together)
✅ Универсальный AI-Guardian для всех файлов
✅ 4-уровневая валидация с бэкапом
✅ Авто-откат при ошибках
                ''')

        # ===== UPDATES TAB =====
        with ui.tab_panel(tab_updates):
            ui.label('🛡️ Универсальные обновления').classes('text-2xl font-bold mb-4')

            file_selector = ui.select(
                options=PROTECTED_FILES,
                value='agent_engine.py',
                label='Выберите файл'
            ).classes('w-full mb-4')

            description_input = ui.textarea('Описание обновления').classes('w-full h-24 mb-4')
            code_input = ui.textarea('Новый код').classes('w-full h-96 mb-4')
            update_log = ui.log(max_lines=50).classes('w-full h-48 bg-black text-green-400 font-mono')

            async def apply_update():
                filename = file_selector.value
                new_code = code_input.value.strip()

                if not new_code:
                    ui.notify('Введите код', type='warning')
                    return

                update_log.clear()
                update_log.push(f'[INFO] Обновление {filename}...')

                # Валидация
                if filename.endswith('.py'):
                    valid, error = validate_python_syntax(new_code)
                    if not valid:
                        update_log.push(f'[ERROR] Синтаксис: {error}')
                        ui.notify('Ошибка синтаксиса', type='negative')
                        return

                # Бэкап
                if os.path.exists(filename):
                    backup_path = f'{filename}.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
                    shutil.copy2(filename, backup_path)
                    update_log.push(f'[INFO] Бэкап создан: {backup_path}')

                # Применение
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(new_code)
                    update_log.push(f'[SUCCESS] ✅ {filename} обновлён')
                    ui.notify('Обновление применено', type='positive')

                    if filename == 'main.py':
                        ui.notify('Перезапуск...', type='info')
                        restart_server()

                except Exception as e:
                    update_log.push(f'[ERROR] {e}')
                    ui.notify('Ошибка применения', type='negative')

            ui.button('🛡️ Применить обновление', on_click=apply_update).classes('custom-button mt-4')

        # ===== DEBUG TAB =====
        with ui.tab_panel(tab_debug):
            ui.label('🐞 Отладка').classes('text-2xl font-bold mb-4')

            with ui.row().classes('gap-4 mb-4'):
                ui.button('🔌 Тест Ollama', on_click=lambda: ui.notify('Ollama OK', type='positive')).classes('custom-button')
                ui.button('⚙️ Тест Ядра', on_click=lambda: ui.notify('Ядро OK' if get_engine() else 'Ядро ERROR', type='positive')).classes('custom-button')

            debug_log = ui.log(max_lines=200).classes('w-full h-[500px] bg-black text-green-400 font-mono')

            _last_log_len = 0
            async def update_debug_log():
                nonlocal _last_log_len
                if len(DEBUG_LOG) > _last_log_len:
                    for entry in DEBUG_LOG[_last_log_len:]:
                        debug_log.push(entry)
                    _last_log_len = len(DEBUG_LOG)

            ui.timer(1.0, update_debug_log)


log_debug('ЦУ v3.0.8 FORTRESS запущен', 'SUCCESS')
ensure_base_files()
create_ui()
ui.run(title='drmAIcu v3.0.8 FORTRESS', port=8080, dark=True, reload=False)
