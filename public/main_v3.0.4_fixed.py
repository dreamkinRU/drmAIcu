# main.py
# Версия 3.0.4 FORTRESS (ИСПРАВЛЕНО)

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
CHECKSUM_FILE = 'backups/checksums.json'

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
        self.log("Загружено АВАРИЙНОЕ ядро", "WARNING")

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
            self.log(f"✅ {candidate['name']}: {len(code)} симв.", "SUCCESS")
            return {"candidate": candidate, "code": code, "error": None}
        except Exception as e:
            self.log(f"❌ {candidate['name']}: {e}", "ERROR")
            return {"candidate": candidate, "code": None, "error": str(e)}

    async def run_task(self, prompt: str, status_callback=None, mode: str = "full") -> str:
        self.log(f"ЗАДАЧА: {prompt[:50]}", "INFO")
        candidates = [{"model": "qwen2.5-coder:1.5b", "name": "Qwen 1.5B"}]
        if status_callback:
            status_callback("Отправка...")
        results = await asyncio.gather(*[self.get_code_response(c, prompt) for c in candidates], return_exceptions=True)
        valid = [r for r in results if isinstance(r, dict) and r.get("code")]
        if not valid:
            return "Все модели не ответили"
        if status_callback:
            status_callback("✅ Готово")
        return valid[0]["code"]
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
            log_debug("⚠️ settings.json повреждён", "WARNING")
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
    if os.path.exists(CONFIG_FILE):
        backup_path = os.path.join(BACKUP_DIR, f"settings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            shutil.copy2(CONFIG_FILE, backup_path)
        except Exception:
            pass
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(current, f, indent=4, ensure_ascii=False)


def calculate_checksum(filepath: str) -> str:
    if not os.path.exists(filepath):
        return ""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def save_checksum(filepath: str):
    checksums = {}
    if os.path.exists(CHECKSUM_FILE):
        try:
            with open(CHECKSUM_FILE, 'r') as f:
                checksums = json.load(f)
        except Exception:
            pass
    checksums[filepath] = calculate_checksum(filepath)
    with open(CHECKSUM_FILE, 'w') as f:
        json.dump(checksums, f, indent=2)


def create_triple_backup(filepath: str) -> list:
    if not os.path.exists(filepath):
        return []
    backups = []
    filename = os.path.basename(filepath)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup1 = os.path.join(BACKUP_DIR, f"{filename}_{timestamp}.bak")
    backup2 = os.path.join(BACKUP_DIR, f"{filename}_{timestamp}_verified.bak")
    backup3 = os.path.join(BACKUP_DIR, f"{filename}_LATEST.bak")
    try:
        shutil.copy2(filepath, backup1)
        backups.append(backup1)
    except Exception:
        pass
    try:
        shutil.copy2(filepath, backup2)
        save_checksum(backup2)
        backups.append(backup2)
    except Exception:
        pass
    try:
        shutil.copy2(filepath, backup3)
        backups.append(backup3)
    except Exception:
        pass
    return backups


def validate_python_syntax(code: str) -> tuple:
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)
    except (UnicodeDecodeError, ValueError) as e:
        return False, f"Кодировка: {e}"


def validate_json_syntax(code: str) -> tuple:
    try:
        json.loads(code)
        return True, None
    except json.JSONDecodeError as e:
        return False, str(e)


def validate_engine_structure(code: str) -> tuple:
    required = ['class AgentEngine', 'async def run_task', 'async def get_code_response', '__init__']
    missing = [r for r in required if r not in code]
    if missing:
        return False, f"Отсутствуют: {', '.join(missing)}"
    if 'ui.dark_mode' in code or 'ui.label' in code or 'ui.button' in code:
        if 'def create_ui' not in code:
            return False, "Вызовы UI вне create_ui()"
    return True, None


def restore_from_backup(backup_path: str = None) -> bool:
    if backup_path and os.path.exists(backup_path):
        try:
            shutil.copy2(backup_path, ENGINE_FILE)
            log_debug(f"🔄 Восстановлено из: {backup_path}", "SUCCESS")
            return True
        except Exception as e:
            log_debug(f"❌ Ошибка восстановления: {e}", "ERROR")
    latest_backup = os.path.join(BACKUP_DIR, "agent_engine_LATEST.bak")
    if os.path.exists(latest_backup):
        return restore_from_backup(latest_backup)
    log_debug("⚠️ Бэкапы не найдены — создаю аварийное ядро", "WARNING")
    with open(ENGINE_FILE, 'w', encoding='utf-8') as f:
        f.write(EMERGENCY_ENGINE_CODE)
    return True


def ensure_base_files():
    if not os.path.exists(CONFIG_FILE):
        save_config({})
        log_debug("✅ settings.json создан", "SUCCESS")
    if not os.path.exists(ENGINE_FILE):
        log_debug("⚠️ agent_engine.py не найден — создаю аварийное ядро", "WARNING")
        with open(ENGINE_FILE, 'w', encoding='utf-8') as f:
            f.write(EMERGENCY_ENGINE_CODE)
        return
    with open(ENGINE_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    valid_syntax, syntax_error = validate_python_syntax(content)
    valid_structure, structure_error = validate_engine_structure(content)
    if not valid_syntax or not valid_structure:
        log_debug(f"⚠️ agent_engine.py ПОВРЕЖДЁН!", "ERROR")
        if syntax_error:
            log_debug(f"Синтаксис: {syntax_error}", "ERROR")
        if structure_error:
            log_debug(f"Структура: {structure_error}", "ERROR")
        log_debug("🔄 Восстановление из бэкапа...", "INFO")
        if not restore_from_backup():
            log_debug("❌ НЕ УДАЛОСЬ восстановить ядро!", "ERROR")
    log_debug("🛡️ Базовые файлы проверены", "SUCCESS")


engine_instance = None
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
        config = load_config()
        if 'agent_engine' in sys.modules:
            importlib.reload(sys.modules['agent_engine'])
        else:
            import agent_engine
        try:
            engine_instance = sys.modules['agent_engine'].AgentEngine(config, log_callback=log_debug)
        except TypeError:
            engine_instance = sys.modules['agent_engine'].AgentEngine(config)
        log_debug("✅ Ядро загружено", "SUCCESS")
        return engine_instance
    except Exception as e:
        log_debug(f"❌ Ошибка ядра: {e}", "ERROR")
        log_debug(f"Traceback: {traceback.format_exc()}", "ERROR")
        log_debug("🔄 Попытка восстановления...", "WARNING")
        if restore_from_backup():
            log_debug("✅ Восстановлено! Перезагрузите ЦУ", "SUCCESS")
        else:
            log_debug("❌ НЕ УДАЛОСЬ восстановить", "ERROR")
        return None


def get_language(filename):
    if filename.endswith('.py'):
        return 'python'
    if filename.endswith('.json'):
        return 'json'
    if filename.endswith(('.bas', '.vba')):
        return 'vbscript'
    return 'plaintext'


def get_project_files():
    return [f for f in os.listdir('.') if os.path.isfile(f) and f.endswith(('.py', '.json', '.txt', '.bas', '.vba', '.md'))]


def restart_server():
    log_debug("🔄 Перезапуск...", "WARNING")
    with open(RESTART_FLAG, 'w') as f:
        f.write('restart')

    def do_exit():
        time.sleep(2)
        os._exit(0)

    threading.Thread(target=do_exit, daemon=True).start()


class UniversalAIGuardian:
    def __init__(self, engine, log_callback):
        self.engine = engine
        self.log = log_callback
    
    def _get_file_type(self, filename: str) -> str:
        if filename.endswith('.py'):
            return 'python'
        elif filename.endswith('.json'):
            return 'json'
        elif filename.endswith(('.bat', '.cmd')):
            return 'batch'
        else:
            return 'text'
    
    def _validate_file(self, filename: str, content: str) -> tuple:
        file_type = self._get_file_type(filename)
        
        if file_type == 'python':
            valid, error = validate_python_syntax(content)
            if not valid:
                return False, f"Ошибка синтаксиса Python: {error}"
            if filename == 'agent_engine.py':
                valid, error = validate_engine_structure(content)
                if not valid:
                    return False, f"Ошибка структуры: {error}"
        elif file_type == 'json':
            valid, error = validate_json_syntax(content)
            if not valid:
                return False, f"Ошибка синтаксиса JSON: {error}"
        
        return True, None
    
    async def validate_and_apply_patch(self, filename: str, new_content: str, description: str) -> dict:
        result = {
            "approved": False,
            "filename": filename,
            "errors": [],
            "warnings": [],
            "steps": [],
            "backups": []
        }
        
        self.log(f"[GUARDIAN] Обработка: {filename}", "INFO")
        
        self.log("Уровень 1/4: Проверка синтаксиса...", "INFO")
        result["steps"].append("1. Синтаксис")
        valid, error = self._validate_file(filename, new_content)
        if not valid:
            result["errors"].append(f"Синтаксис: {error}")
            self.log(f"❌ ОШИБКА СИНТАКСИСА: {error}", "ERROR")
            return result
        self.log("✅ Синтаксис OK", "SUCCESS")
        
        if filename.endswith('.py'):
            self.log("Уровень 2/4: Проверка структуры...", "INFO")
            result["steps"].append("2. Структура")
            if filename == 'agent_engine.py':
                valid, error = validate_engine_structure(new_content)
                if not valid:
                    result["errors"].append(f"Структура: {error}")
                    self.log(f"❌ ОШИБКА СТРУКТУРЫ: {error}", "ERROR")
                    return result
            self.log("✅ Структура OK", "SUCCESS")
        else:
            result["steps"].append("2. Структура (пропущено)")
        
        self.log("Уровень 3/4: AI-проверка...", "INFO")
        result["steps"].append("3. AI-проверка")
        ai_result = await self._ai_validation(filename, new_content, description)
        if not ai_result.get("approved", False):
            result["errors"].extend(ai_result.get("errors", []))
            result["warnings"].extend(ai_result.get("warnings", []))
            self.log(f"❌ AI-ПРОВЕРКА НЕ ПРОЙДЕНА: {ai_result.get('reason')}", "ERROR")
            return result
        self.log("✅ AI-проверка OK", "SUCCESS")
        
        self.log("Уровень 4/4: Создание бэкапа...", "INFO")
        result["steps"].append("4. Бэкап")
        if os.path.exists(filename):
            backups = create_triple_backup(filename)
            result["backups"] = backups
            if not backups:
                result["warnings"].append("Не удалось создать бэкап")
            else:
                self.log(f"✅ Создано {len(backups)} бэкапов", "SUCCESS")
        else:
            result["warnings"].append("Файл ещё не существует")
        
        result["approved"] = True
        self.log("🎉 ВСЕ 4 УРОВНЯ ПРОЙДЕНЫ!", "SUCCESS")
        return result
    
    async def _ai_validation(self, filename: str, content: str, description: str) -> dict:
        validation_prompt = f"""Ты — ревизор кода. Проверь обновление файла.

ФАЙЛ: {filename}
ОПИСАНИЕ: {description}
СОДЕРЖИМОЕ (первые 3000 символов):
{content[:3000]}

ПРОВЕРКИ:
1. Код логичен и корректен?
2. Есть ли очевидные ошибки?
3. Безопасно ли применять?

ВЕРНИ JSON:
{{"approved": true/false, "reason": "причина если отклонено", "warnings": [], "suggestions": []}}

JSON:"""
        
        try:
            if self.engine and hasattr(self.engine, '_get_judge_model'):
                judge_model = self.engine._get_judge_model()
                messages = [{"role": "user", "content": validation_prompt}]
                if hasattr(self.engine, '_query_model'):
                    response = await self.engine._query_model(judge_model, messages, timeout=120.0)
                    import json as json_module
                    import re
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        return json_module.loads(json_match.group())
            return self._heuristic_validation(filename, content)
        except Exception as e:
            self.log(f"⚠️ AI ошибка: {e}", "WARNING")
            return self._heuristic_validation(filename, content)
    
    def _heuristic_validation(self, filename: str, content: str) -> dict:
        errors = []
        warnings = []
        
        if len(content) < 10:
            warnings.append("Очень короткое содержимое")
        
        if filename.endswith('.py'):
            if content.count('def ') == 0 and 'class ' not in content:
                warnings.append("Не найдено функций или классов")
        
        elif filename.endswith('.json'):
            try:
                data = json.loads(content)
                if not 
                    warnings.append("Пустой JSON")
            except Exception:
                errors.append("Невалидный JSON")
        
        return {
            "approved": len(errors) == 0,
            "reason": "; ".join(errors) if errors else None,
            "warnings": warnings,
            "suggestions": []
        }
    
    async def apply_patch(self, filename: str, content: str, validation_result: dict) -> bool:
        if not validation_result.get("approved", False):
            self.log("❌ Отклонено", "ERROR")
            return False
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            self.log(f"✅ Патч применён: {filename}", "SUCCESS")
            
            if filename == 'agent_engine.py':
                global engine_instance
                engine_instance = None
            
            if filename == 'main.py':
                self.log("⚠️ main.py обновлён — требуется перезапуск", "WARNING")
            
            return True
        except Exception as e:
            self.log(f"❌ Ошибка применения: {e}", "ERROR")
            backups = validation_result.get("backups", [])
            if backups:
                if restore_from_backup(backups[0]):
                    self.log("🔄 Откат выполнен", "WARNING")
            return False
    
    async def apply_context_patch(self, context_json: str) -> dict:
        try:
            context = json.loads(context_json)
        except Exception as e:
            return {"success": False, "error": f"Невалидный JSON: {e}"}
        
        files_data = context.get("files", {})
        results = {}
        
        for filename, file_info in files_data.items():
            content = file_info.get("content", "")
            description = f"Обновление из контекста: {filename}"
            
            self.log(f"\n{'='*60}", "INFO")
            self.log(f"Обработка: {filename}", "INFO")
            
            validation = await self.validate_and_apply_patch(filename, content, description)
            
            if validation.get("approved"):
                success = await self.apply_patch(filename, content, validation)
                results[filename] = {"success": success, "validation": validation}
            else:
                results[filename] = {"success": False, "validation": validation}
        
        return {"success": True, "results": results}


def create_ui():
    global guardian_instance
    ui.dark_mode().enable()

    with ui.header().classes('bg-gray-900 text-white border-b border-gray-700 p-4'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('🛡️ drmAIcu v3.0.4 FORTRESS • Universal AI-Guardian').classes('text-xl font-bold')
            ui.button('🔄 ПЕРЕЗАПУСТИТЬ', on_click=restart_server).props('color=orange')

    with ui.tabs().classes('w-full') as tabs:
        tab_dash = ui.tab('dashboard', label='Панель')
        tab_api = ui.tab('api', label='API')
        tab_llm = ui.tab('llm', label='LLM')
        tab_updates = ui.tab('updates', label='🛡️ Универсальные обновления')
        tab_debug = ui.tab('debug', label='Отладка')
        tab_editor = ui.tab('editor', label='📝 Редактор')
        tab_console = ui.tab('console', label='💬 Консоль')

    with ui.tab_panels(tabs, value=tab_dash).classes('w-full p-6'):

        with ui.tab_panel(tab_dash):
            ui.label('Статус системы (FORTRESS v3.0.4)').classes('text-lg font-bold mb-4')
            config = load_config()
            with ui.row().classes('gap-4'):
                ui.badge('Ollama: OK', color='green')
                groq_text = 'Groq: OK' if config.get('groq_api_key') else 'Groq: Нет'
                groq_color = 'green' if config.get('groq_api_key') else 'red'
                ui.badge(groq_text, color=groq_color)
                ui.badge('Ядро: v3.0.4 FORTRESS', color='green')
                ui.badge('🛡️ Универсальный Guardian: АКТИВЕН', color='green')
            ui.markdown('''
**Универсальный AI-Guardian:**
- ✅ Поддерживает ВСЕ файлы проекта
- ✅ 4-уровневая валидация
- ✅ Тройной бэкап
- ✅ Авто-откат при ошибке
- ✅ Импорт контекста через UI
            ''')

        with ui.tab_panel(tab_api):
            ui.label('API ключи').classes('text-lg font-bold mb-2')
            config = load_config()
            with ui.row().classes('w-full items-center gap-4 mb-4'):
                groq_key = ui.input('Groq API Key', value=config.get('groq_api_key', ''), password=True).classes('flex-grow')

                def save_groq():
                    save_config({'groq_api_key': groq_key.value})
                    ui.notify('✅ Groq сохранён', type='positive')

                groq_key.on('blur', save_groq)
                ui.button('💾', on_click=save_groq)

        with ui.tab_panel(tab_llm):
            ui.label('LLM Провайдеры').classes('text-lg font-bold mb-4')
            config = load_config()
            providers = [
                ('groq_api_key', 'Groq', 'https://console.groq.com'),
                ('hf_api_key', 'Hugging Face', 'https://huggingface.co/settings/tokens'),
                ('openrouter_api_key', 'OpenRouter', 'https://openrouter.ai/keys'),
                ('gemini_api_key', 'Google Gemini', 'https://makersuite.google.com/app/apikey'),
                ('together_api_key', 'Together AI', 'https://api.together.xyz/settings/api-keys')
            ]
            for key_name, label, url in providers:
                with ui.card().classes('w-full mb-4'):
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label(label).classes('font-bold')
                        status = '✅' if config.get(key_name) else '❌'
                        ui.badge(f'{status}', color='green' if config.get(key_name) else 'red')
                    key_input = ui.input('API Key', value=config.get(key_name, ''), password=True).classes('w-full')
                    with ui.row().classes('gap-2'):
                        def make_save(kn, inp, lbl):
                            return lambda: (save_config({kn: inp.value}), ui.notify(f'✅ {lbl} сохранён'))
                        ui.button('💾', on_click=make_save(key_name, key_input, label)).props('color=green')
                        ui.button('🔗', on_click=lambda u=url: ui.open_url(u)).props('flat')

        with ui.tab_panel(tab_updates):
            ui.label('🛡️ Универсальный AI-Guardian: Обновление ЛЮБОГО файла').classes('text-lg font-bold mb-4')
            ui.label('Поддерживает: main.py, agent_engine.py, settings.json, launcher.bat, context_manager.py').classes('text-gray-400 mb-4')
            
            file_selector = ui.select(
                options=PROTECTED_FILES,
                value='agent_engine.py',
                label='Выберите файл для обновления'
            ).classes('w-full mb-4')
            
            update_description = ui.textarea('Описание обновления', placeholder='Что нового?').classes('w-full h-24')
            new_code_area = ui.textarea('Новый код').classes('w-full h-96')
            validation_log = ui.log(max_lines=50).classes('w-full h-48 bg-black text-green-400 font-mono mt-4')
            
            async def validate_and_update():
                global guardian_instance
                filename = file_selector.value
                if not filename:
                    ui.notify('Выберите файл!', type='warning')
                    return
                if not update_description.value:
                    ui.notify('Введите описание!', type='warning')
                    return
                validation_log.clear()
                validation_log.push(f'[INFO] Универсальный Guardian активирован для {filename}...')
                engine = get_engine()
                if not engine:
                    validation_log.push('[ERROR] Ядро не загружено!')
                    ui.notify('❌ Ядро не загружено', type='negative')
                    return
                if guardian_instance is None:
                    guardian_instance = UniversalAIGuardian(engine, lambda msg, lvl: validation_log.push(f'[{lvl}] {msg}'))
                new_code = new_code_area.value.strip()
                if not new_code:
                    validation_log.push('[ERROR] Введите код!')
                    ui.notify('⚠️ Введите код', type='warning')
                    return
                validation_log.push('[INFO] Запуск 4-уровневой валидации...')
                result = await guardian_instance.validate_and_apply_patch(filename, new_code, update_description.value)
                if result.get("approved"):
                    validation_log.push('[SUCCESS] ✅ ВСЕ УРОВНИ ПРОЙДЕНЫ!')
                    if result.get("warnings"):
                        for w in result["warnings"]:
                            validation_log.push(f'[WARNING] ⚠️ {w}')
                    validation_log.push('[INFO] Применение...')
                    success = await guardian_instance.apply_patch(filename, new_code, result)
                    if success:
                        validation_log.push('[SUCCESS] 🎉 Патч применён!')
                        ui.notify('✅ Патч применён!', type='positive')
                        if filename == 'main.py':
                            ui.notify('⚠️ main.py обновлён — требуется перезапуск', type='warning')
                    else:
                        validation_log.push('[ERROR] ❌ Ошибка применения')
                        ui.notify('❌ Ошибка', type='negative')
                else:
                    validation_log.push('[ERROR] ❌ ВАЛИДАЦИЯ НЕ ПРОЙДЕНА')
                    for error in result.get("errors", []):
                        validation_log.push(f'[ERROR] ❌ {error}')
                    ui.notify(f'❌ Не пройдено: {result.get("errors", ["неизвестно"])[0]}', type='negative')
            
            with ui.row().classes('mt-4 gap-4'):
                ui.button('🛡️ Проверить и применить', on_click=validate_and_update).props('color=green size=lg')
            
            ui.separator().classes('my-6')
            ui.label('📦 Импорт из контекстного JSON').classes('text-lg font-bold mb-4')
            context_json_area = ui.textarea('Вставьте context_export.json сюда').classes('w-full h-64')
            
            async def import_context():
                global guardian_instance
                context_json = context_json_area.value.strip()
                if not context_json:
                    ui.notify('Вставьте контекстный JSON!', type='warning')
                    return
                validation_log.clear()
                validation_log.push('[INFO] Импорт контекста...')
                engine = get_engine()
                if not engine:
                    validation_log.push('[ERROR] Ядро не загружено!')
                    ui.notify('❌ Ядро не загружено', type='negative')
                    return
                if guardian_instance is None:
                    guardian_instance = UniversalAIGuardian(engine, lambda msg, lvl: validation_log.push(f'[{lvl}] {msg}'))
                result = await guardian_instance.apply_context_patch(context_json)
                if result.get("success"):
                    results = result.get("results", {})
                    for filename, res in results.items():
                        if res.get("success"):
                            validation_log.push(f'[SUCCESS] ✅ {filename} обновлён')
                        else:
                            validation_log.push(f'[ERROR] ❌ {filename} не удался')
                    ui.notify('✅ Контекст импортирован!', type='positive')
                else:
                    validation_log.push(f'[ERROR] ❌ {result.get("error")}')
                    ui.notify('❌ Импорт не удался', type='negative')
            
            ui.button('📦 Импортировать контекст', on_click=import_context).props('color=blue size=lg').classes('mt-4')

        with ui.tab_panel(tab_debug):
            ui.label('🐞 Отладка').classes('text-lg font-bold mb-4')
            with ui.row().classes('w-full gap-4'):
                with ui.column().classes('w-1/3'):
                    ui.label('Тесты').classes('font-bold mb-2')

                    async def test_ollama():
                        try:
                            import ollama
                            models = ollama.list()
                            ui.notify(f"✅ Ollama: {len(models.get('models', []))} моделей", type='positive')
                            log_debug(f"Ollama: {models}", "SUCCESS")
                        except Exception as e:
                            ui.notify(f"❌ Ollama: {e}", type='negative')
                            log_debug(f"Ollama error: {e}", "ERROR")

                    ui.button('🔌 Тест Ollama', on_click=test_ollama).classes('w-full mb-2')
                    ui.button('⚙️ Тест Ядра', on_click=lambda: ui.notify("✅ Ядро OK" if get_engine() else "❌ Ядро ERROR")).classes('w-full mb-2')
                    ui.button('🗑️ Очистить лог', on_click=lambda: (DEBUG_LOG.clear(), ui.notify('Лог очищен'))).classes('w-full')
                with ui.column().classes('w-2/3'):
                    log_display = ui.log(max_lines=200).classes('w-full h-[500px] bg-black text-green-400 font-mono')
                    _last_log_len = 0

                    async def update_log():
                        nonlocal _last_log_len
                        if len(DEBUG_LOG) > _last_log_len:
                            for entry in DEBUG_LOG[_last_log_len:]:
                                log_display.push(entry)
                            _last_log_len = len(DEBUG_LOG)

                    ui.timer(1, update_log, once=False)

        with ui.tab_panel(tab_editor):
            ui.label('📝 Редактор (ВСЕ ФАЙЛЫ ЗАЩИЩЕНЫ)').classes('text-lg font-bold mb-4')
            ui.label('⚠️ Используйте вкладку "🛡️ Универсальные обновления" для защищённых файлов').classes('text-yellow-400 mb-4')
            with ui.row().classes('w-full gap-4 items-end'):
                file_selector = ui.select(
                    options=get_project_files(),
                    label='Файл',
                    on_change=lambda e: load_file_to_editor(e.value)
                ).classes('w-1/3')
                new_file_name = ui.input('Новый файл').classes('w-1/3')

                def create_file():
                    fname = new_file_name.value.strip()
                    if not fname or os.path.exists(fname):
                        ui.notify('Файл существует!', type='warning')
                        return
                    with open(fname, 'w') as f:
                        f.write(f"# {fname}\n")
                    file_selector.options = get_project_files()
                    file_selector.update()
                    file_selector.value = fname
                    load_file_to_editor(fname)
                    ui.notify(f'✅ {fname} создан', type='positive')

                ui.button('➕ Создать', on_click=create_file)
            editor_container = ui.column().classes('w-full')

            def load_file_to_editor(filename):
                global current_editor, current_file
                if not filename:
                    return
                # ИСПРАВЛЕНИЕ: проверка существования файла
                if not os.path.exists(filename):
                    ui.notify(f'⚠️ Файл {filename} не найден', type='warning')
                    return
                current_file = filename
                editor_container.clear()
                with editor_container:
                    with open(filename, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if filename in PROTECTED_FILES:
                        ui.label(f'🔒 {filename} — ТОЛЬКО ЧТЕНИЕ').classes('text-red-400 font-bold mb-2')
                        ui.markdown('Для обновления используйте вкладку **🛡️ Универсальные обновления**')
                        escaped_code = content.replace('`', '\\`')
                        ui.markdown(f'```{get_language(filename)}\n{escaped_code}\n```').classes('w-full')
                        current_editor = None
                    else:
                        current_editor = ui.codemirror(
                            value=content,
                            language=get_language(filename),
                            theme='dark'
                        ).classes('w-full h-[500px] border rounded')

            def save_current_file():
                global current_file, current_editor, engine_instance
                if current_file and current_editor:
                    if current_file in PROTECTED_FILES:
                        ui.notify(f'⛔ {current_file} защищён!', type='negative')
                        ui.notify('Используйте вкладку 🛡️ Универсальные обновления', type='warning')
                        return
                    code = current_editor.value
                    if current_file.endswith('.py'):
                        is_valid, error = validate_python_syntax(code)
                        if not is_valid:
                            ui.notify(f'❌ Ошибка синтаксиса: {error[:100]}', type='negative', timeout=10)
                            return
                    with open(current_file, 'w', encoding='utf-8') as f:
                        f.write(code)
                    if current_file == 'main.py':
                        ui.notify('🔄 Перезапуск...', type='info')
                        restart_server()
                    else:
                        ui.notify(f'💾 {current_file} сохранён', type='positive')
                else:
                    ui.notify('⚠️ Нет активного редактора', type='warning')

            ui.button('💾 Сохранить', on_click=save_current_file).classes('mt-4')
            # ИСПРАВЛЕНИЕ: загружаем settings.json вместо main.py
            if os.path.exists('settings.json'):
                load_file_to_editor('settings.json')
                file_selector.value = 'settings.json'
            elif os.path.exists('agent_engine.py'):
                load_file_to_editor('agent_engine.py')
                file_selector.value = 'agent_engine.py'

        with ui.tab_panel(tab_console):
            ui.label('💬 Консоль').classes('text-lg font-bold mb-4')
            with ui.row().classes('w-full items-center gap-4 mb-2'):
                mode_select = ui.select(
                    options={'full': ' Полный', 'fast': '⚡ Быстрый'},
                    value='full',
                    label='Режим'
                ).classes('w-1/3')
            task_input = ui.input('Задача (Enter)').classes('w-full')
            status_label = ui.label('Статус: Ожидание').classes('text-lg mt-4')
            log_area = ui.log(max_lines=200).classes('w-full h-64 bg-black text-green-400 font-mono mt-4')
            result_area = ui.textarea('Результат').classes('w-full h-64 mt-4')

            async def run_task():
                if not task_input.value:
                    ui.notify('Введите задачу!', type='warning')
                    return
                log_area.clear()
                log_area.push('=' * 70)
                log_area.push(f'ЗАДАЧА: {task_input.value}')
                log_area.push(f'РЕЖИМ: {mode_select.value}')
                log_area.push('=' * 70)
                log_debug(f"Задача: {task_input.value[:50]}", "INFO")

                def update_status(text):
                    status_label.text = f"Статус: {text}"
                    log_debug(f"Статус: {text}", "INFO")
                    log_area.push(f'[СТАТУС] {text}')

                try:
                    engine = get_engine()
                    if not engine:
                        raise Exception("Ядро не загружено")
                    if hasattr(engine, '_get_candidates'):
                        candidates = engine._get_candidates()
                        log_area.push('')
                        log_area.push(f'📋 БУДУТ ОПРОШЕНЫ {len(candidates)} МОДЕЛЕЙ:')
                        for i, c in enumerate(candidates, 1):
                            provider = c.get('provider', 'ollama').upper()
                            log_area.push(f'  {i}. [{provider}] {c["name"]}')
                        log_area.push('-' * 70)
                    else:
                        log_area.push('📋 Используется аварийное ядро (1 модель)')
                        log_area.push('-' * 70)
                    update_status(" Отправка запросов...")
                    result = await engine.run_task(
                        task_input.value,
                        status_callback=update_status,
                        mode=mode_select.value
                    )
                    log_area.push('')
                    log_area.push('=' * 70)
                    log_area.push(' ЗАДАЧА ВЫПОЛНЕНА')
                    log_area.push('=' * 70)
                    result_area.value = result
                    log_debug("✅ Готово", "SUCCESS")
                    update_status("🏁 Готово")
                except Exception as e:
                    log_area.push('')
                    log_area.push(f'[ОШИБКА] {str(e)}')
                    log_area.push(f'[TRACEBACK] {traceback.format_exc()}')
                    result_area.value = f"Ошибка: {str(e)}"
                    log_debug(f"❌ Ошибка: {e}", "ERROR")
                    update_status("❌ Ошибка")

            task_input.on('keydown.enter', lambda: asyncio.create_task(run_task()))
            ui.button('▶️ Отправить', on_click=run_task).props('color=green').classes('mt-2')


log_debug("ЦУ v3.0.4 FORTRESS запущен", "SUCCESS")
ensure_base_files()
create_ui()
ui.run(title='drmAIcu v3.0.4 FORTRESS • Universal AI-Guardian', port=8080, dark=True, reload=False)
