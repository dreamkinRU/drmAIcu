# main.py
# Version 3.0.4 FORTRESS (UNIVERSAL AI-GUARDIAN)

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

# Универсальный список защищённых файлов
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
            self.log(f"[OK] {candidate['name']}: {len(code)} chars", "SUCCESS")
            return {"candidate": candidate, "code": code, "error": None}
        except Exception as e:
            self.log(f"[ERR] {candidate['name']}: {e}", "ERROR")
            return {"candidate": candidate, "code": None, "error": str(e)}

    async def run_task(self, prompt: str, status_callback=None, mode: str = "full") -> str:
        self.log(f"TASK: {prompt[:50]}", "INFO")
        candidates = [{"model": "qwen2.5-coder:1.5b", "name": "Qwen 1.5B"}]
        if status_callback:
            status_callback("Sending...")
        results = await asyncio.gather(*[self.get_code_response(c, prompt) for c in candidates], return_exceptions=True)
        valid = [r for r in results if isinstance(r, dict) and r.get("code")]
        if not valid:
            return "All models failed"
        if status_callback:
            status_callback("Done")
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
        return False, f"Encoding: {e}"


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
        return False, f"Missing: {', '.join(missing)}"
    if 'ui.dark_mode' in code or 'ui.label' in code or 'ui.button' in code:
        if 'def create_ui' not in code:
            return False, "UI calls outside create_ui()"
    return True, None


def restore_from_backup(backup_path: str = None) -> bool:
    if backup_path and os.path.exists(backup_path):
        try:
            shutil.copy2(backup_path, ENGINE_FILE)
            log_debug(f"Restored from: {backup_path}", "SUCCESS")
            return True
        except Exception as e:
            log_debug(f"Restore error: {e}", "ERROR")
    latest_backup = os.path.join(BACKUP_DIR, "agent_engine_LATEST.bak")
    if os.path.exists(latest_backup):
        return restore_from_backup(latest_backup)
    log_debug("No backups found - creating emergency engine", "WARNING")
    with open(ENGINE_FILE, 'w', encoding='utf-8') as f:
        f.write(EMERGENCY_ENGINE_CODE)
    return True


def ensure_base_files():
    if not os.path.exists(CONFIG_FILE):
        save_config({})
        log_debug("settings.json created", "SUCCESS")
    if not os.path.exists(ENGINE_FILE):
        log_debug("agent_engine.py not found - creating emergency engine", "WARNING")
        with open(ENGINE_FILE, 'w', encoding='utf-8') as f:
            f.write(EMERGENCY_ENGINE_CODE)
        return
    with open(ENGINE_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    valid_syntax, syntax_error = validate_python_syntax(content)
    valid_structure, structure_error = validate_engine_structure(content)
    if not valid_syntax or not valid_structure:
        log_debug("agent_engine.py CORRUPTED!", "ERROR")
        if syntax_error:
            log_debug(f"Syntax: {syntax_error}", "ERROR")
        if structure_error:
            log_debug(f"Structure: {structure_error}", "ERROR")
        log_debug("Restoring from backup...", "INFO")
        if not restore_from_backup():
            log_debug("FAILED to restore engine!", "ERROR")
    log_debug("Base files checked", "SUCCESS")


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
        log_debug("Engine loaded", "SUCCESS")
        return engine_instance
    except Exception as e:
        log_debug(f"Engine error: {e}", "ERROR")
        log_debug(f"Traceback: {traceback.format_exc()}", "ERROR")
        log_debug("Trying to restore...", "WARNING")
        if restore_from_backup():
            log_debug("Restored! Restart CU", "SUCCESS")
        else:
            log_debug("FAILED to restore", "ERROR")
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
    log_debug("Restarting...", "WARNING")
    with open(RESTART_FLAG, 'w') as f:
        f.write('restart')

    def do_exit():
        time.sleep(2)
        os._exit(0)

    threading.Thread(target=do_exit, daemon=True).start()


class UniversalAIGuardian:
    """Универсальный AI-Guardian для всех файлов проекта"""
    
    def __init__(self, engine, log_callback):
        self.engine = engine
        self.log = log_callback
    
    def _get_file_type(self, filename: str) -> str:
        """Определяет тип файла"""
        if filename.endswith('.py'):
            return 'python'
        elif filename.endswith('.json'):
            return 'json'
        elif filename.endswith(('.bat', '.cmd')):
            return 'batch'
        else:
            return 'text'
    
    def _validate_file(self, filename: str, content: str) -> tuple:
        """Валидация файла по типу"""
        file_type = self._get_file_type(filename)
        
        if file_type == 'python':
            valid, error = validate_python_syntax(content)
            if not valid:
                return False, f"Python syntax error: {error}"
            
            # Специальная проверка для agent_engine.py
            if filename == 'agent_engine.py':
                valid, error = validate_engine_structure(content)
                if not valid:
                    return False, f"Structure error: {error}"
        
        elif file_type == 'json':
            valid, error = validate_json_syntax(content)
            if not valid:
                return False, f"JSON syntax error: {error}"
        
        # Для batch и text файлов — базовая проверка
        return True, None
    
    async def validate_and_apply_patch(self, filename: str, new_content: str, description: str) -> dict:
        """Универсальная валидация и применение патча для любого файла"""
        result = {
            "approved": False,
            "filename": filename,
            "errors": [],
            "warnings": [],
            "steps": [],
            "backups": []
        }
        
        self.log(f"[GUARDIAN] Processing: {filename}", "INFO")
        
        # Уровень 1: Синтаксис
        self.log("Level 1/4: Syntax validation...", "INFO")
        result["steps"].append("1. Syntax")
        valid, error = self._validate_file(filename, new_content)
        if not valid:
            result["errors"].append(f"Syntax: {error}")
            self.log(f"SYNTAX ERROR: {error}", "ERROR")
            return result
        self.log("Syntax OK", "SUCCESS")
        
        # Уровень 2: Структура (для Python файлов)
        if filename.endswith('.py'):
            self.log("Level 2/4: Structure validation...", "INFO")
            result["steps"].append("2. Structure")
            
            if filename == 'agent_engine.py':
                valid, error = validate_engine_structure(new_content)
                if not valid:
                    result["errors"].append(f"Structure: {error}")
                    self.log(f"STRUCTURE ERROR: {error}", "ERROR")
                    return result
            self.log("Structure OK", "SUCCESS")
        else:
            result["steps"].append("2. Structure (skipped)")
        
        # Уровень 3: AI-проверка
        self.log("Level 3/4: AI validation...", "INFO")
        result["steps"].append("3. AI-Check")
        ai_result = await self._ai_validation(filename, new_content, description)
        if not ai_result.get("approved", False):
            result["errors"].extend(ai_result.get("errors", []))
            result["warnings"].extend(ai_result.get("warnings", []))
            self.log(f"AI CHECK FAILED: {ai_result.get('reason')}", "ERROR")
            return result
        self.log("AI check OK", "SUCCESS")
        
        # Уровень 4: Бэкап
        self.log("Level 4/4: Creating backup...", "INFO")
        result["steps"].append("4. Backup")
        if os.path.exists(filename):
            backups = create_triple_backup(filename)
            result["backups"] = backups
            if not backups:
                result["warnings"].append("Failed to create backup")
            else:
                self.log(f"Created {len(backups)} backups", "SUCCESS")
        else:
            result["warnings"].append("File does not exist yet")
        
        result["approved"] = True
        self.log("ALL LEVELS PASSED!", "SUCCESS")
        return result
    
    async def _ai_validation(self, filename: str, content: str, description: str) -> dict:
        """AI-проверка содержимого файла"""
        validation_prompt = f"""You are a code reviewer. Check this file update.

FILE: {filename}
DESCRIPTION: {description}
CONTENT (first 3000 chars):
{content[:3000]}

CHECK:
1. Is the code logical and correct?
2. Are there obvious bugs?
3. Is it safe to apply?

RETURN JSON:
{{"approved": true/false, "reason": "reason if rejected", "warnings": [], "suggestions": []}}

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
            self.log(f"AI error: {e}", "WARNING")
            return self._heuristic_validation(filename, content)
    
    def _heuristic_validation(self, filename: str, content: str) -> dict:
        """Эвристическая проверка без AI"""
        errors = []
        warnings = []
        
        # Базовые проверки
        if len(content) < 10:
            warnings.append("Very short content")
        
        if filename.endswith('.py'):
            if content.count('def ') == 0 and 'class ' not in content:
                warnings.append("No functions or classes found")
        
        elif filename.endswith('.json'):
            try:
                data = json.loads(content)
                if not data:
                    warnings.append("Empty JSON")
            except Exception:
                errors.append("Invalid JSON")
        
        return {
            "approved": len(errors) == 0,
            "reason": "; ".join(errors) if errors else None,
            "warnings": warnings,
            "suggestions": []
        }
    
    async def apply_patch(self, filename: str, content: str, validation_result: dict) -> bool:
        """Применяет патч к файлу"""
        if not validation_result.get("approved", False):
            self.log("Rejected", "ERROR")
            return False
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            self.log(f"Patch applied: {filename}", "SUCCESS")
            
            # Если это agent_engine.py — сбрасываем engine_instance
            if filename == 'agent_engine.py':
                global engine_instance
                engine_instance = None
            
            # Если это main.py — нужен перезапуск
            if filename == 'main.py':
                self.log("main.py updated - restart required", "WARNING")
            
            return True
        except Exception as e:
            self.log(f"Apply error: {e}", "ERROR")
            backups = validation_result.get("backups", [])
            if backups:
                if restore_from_backup(backups[0]):
                    self.log("Rollback done", "WARNING")
            return False
    
    async def apply_context_patch(self, context_json: str) -> dict:
        """Применяет патч из JSON контекста"""
        try:
            context = json.loads(context_json)
        except Exception as e:
            return {"success": False, "error": f"Invalid JSON: {e}"}
        
        files_data = context.get("files", {})
        results = {}
        
        for filename, file_info in files_data.items():
            content = file_info.get("content", "")
            description = f"Update from context: {filename}"
            
            self.log(f"\n{'='*60}", "INFO")
            self.log(f"Processing: {filename}", "INFO")
            
            validation = await self.validate_and_apply_patch(filename, content, description)
            
            if validation.get("approved"):
                success = await self.apply_patch(filename, content, validation)
                results[filename] = {"success": success, "validation": validation}
            else:
                results[filename] = {"success": False, "validation": validation}
        
        return {"success": True, "results": results}


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
    log_debug("Restarting...", "WARNING")
    with open(RESTART_FLAG, 'w') as f:
        f.write('restart')

    def do_exit():
        time.sleep(2)
        os._exit(0)

    threading.Thread(target=do_exit, daemon=True).start()


def create_ui():
    global guardian_instance
    ui.dark_mode().enable()

    with ui.header().classes('bg-gray-900 text-white border-b border-gray-700 p-4'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('CU v3.0.4 FORTRESS').classes('text-xl font-bold')
            ui.button('RESTART', on_click=restart_server).props('color=orange')

    with ui.tabs().classes('w-full') as tabs:
        tab_dash = ui.tab('dashboard', label='Dashboard')
        tab_api = ui.tab('api', label='API')
        tab_llm = ui.tab('llm', label='LLM')
        tab_updates = ui.tab('updates', label='Universal Updates')
        tab_debug = ui.tab('debug', label='Debug')
        tab_editor = ui.tab('editor', label='Editor')
        tab_console = ui.tab('console', label='Console')

    with ui.tab_panels(tabs, value=tab_dash).classes('w-full p-6'):

        with ui.tab_panel(tab_dash):
            ui.label('System Status (FORTRESS v3.0.4)').classes('text-lg font-bold mb-4')
            config = load_config()
            with ui.row().classes('gap-4'):
                ui.badge('Ollama: OK', color='green')
                groq_text = 'Groq: OK' if config.get('groq_api_key') else 'Groq: No'
                groq_color = 'green' if config.get('groq_api_key') else 'red'
                ui.badge(groq_text, color=groq_color)
                ui.badge('Core: v3.0.4 FORTRESS', color='green')
                ui.badge('Universal Guardian: ACTIVE', color='green')
            ui.markdown('''
**Universal AI-Guardian:**
- Supports ALL project files (main.py, agent_engine.py, settings.json, launcher.bat)
- 4-level validation (syntax, structure, AI-check, backup)
- Triple backup for each file
- Auto-rollback on error
- Context-based patching
            ''')

        with ui.tab_panel(tab_api):
            ui.label('API Keys').classes('text-lg font-bold mb-2')
            config = load_config()
            with ui.row().classes('w-full items-center gap-4 mb-4'):
                groq_key = ui.input('Groq API Key', value=config.get('groq_api_key', ''), password=True).classes('flex-grow')

                def save_groq():
                    save_config({'groq_api_key': groq_key.value})
                    ui.notify('Groq saved', type='positive')

                groq_key.on('blur', save_groq)
                ui.button('Save', on_click=save_groq)

        with ui.tab_panel(tab_llm):
            ui.label('LLM Providers').classes('text-lg font-bold mb-4')
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
                        status = 'OK' if config.get(key_name) else 'No'
                        ui.badge(f'{status}', color='green' if config.get(key_name) else 'red')
                    key_input = ui.input('API Key', value=config.get(key_name, ''), password=True).classes('w-full')
                    with ui.row().classes('gap-2'):
                        def make_save(kn, inp, lbl):
                            return lambda: (save_config({kn: inp.value}), ui.notify(f'{lbl} saved'))
                        ui.button('Save', on_click=make_save(key_name, key_input, label)).props('color=green')
                        ui.button('Link', on_click=lambda u=url: ui.open_url(u)).props('flat')

        with ui.tab_panel(tab_updates):
            ui.label('Universal AI-Guardian: Update ANY File').classes('text-lg font-bold mb-4')
            ui.label('Supports: main.py, agent_engine.py, settings.json, launcher.bat, context_manager.py').classes('text-gray-400 mb-4')
            
            file_selector = ui.select(
                options=PROTECTED_FILES,
                value='agent_engine.py',
                label='Select file to update'
            ).classes('w-full mb-4')
            
            update_description = ui.textarea('Update description', placeholder='What is new?').classes('w-full h-24')
            new_code_area = ui.textarea('New code').classes('w-full h-96')
            validation_log = ui.log(max_lines=50).classes('w-full h-48 bg-black text-green-400 font-mono mt-4')
            
            async def validate_and_update():
                global guardian_instance
                filename = file_selector.value
                if not filename:
                    ui.notify('Select file!', type='warning')
                    return
                if not update_description.value:
                    ui.notify('Enter description!', type='warning')
                    return
                validation_log.clear()
                validation_log.push(f'[INFO] Universal Guardian activated for {filename}...')
                engine = get_engine()
                if not engine:
                    validation_log.push('[ERROR] Engine not loaded!')
                    ui.notify('Engine not loaded', type='negative')
                    return
                if guardian_instance is None:
                    guardian_instance = UniversalAIGuardian(engine, lambda msg, lvl: validation_log.push(f'[{lvl}] {msg}'))
                new_code = new_code_area.value.strip()
                if not new_code:
                    validation_log.push('[ERROR] Enter code!')
                    ui.notify('Enter code', type='warning')
                    return
                validation_log.push('[INFO] Running 4-level validation...')
                result = await guardian_instance.validate_and_apply_patch(filename, new_code, update_description.value)
                if result.get("approved"):
                    validation_log.push('[SUCCESS] ALL LEVELS PASSED!')
                    if result.get("warnings"):
                        for w in result["warnings"]:
                            validation_log.push(f'[WARNING] {w}')
                    validation_log.push('[INFO] Applying...')
                    success = await guardian_instance.apply_patch(filename, new_code, result)
                    if success:
                        validation_log.push('[SUCCESS] Patch applied!')
                        ui.notify('Patch applied! Restart may be required.', type='positive')
                        if filename == 'main.py':
                            ui.notify('main.py updated - restart required', type='warning')
                    else:
                        validation_log.push('[ERROR] Apply error')
                        ui.notify('Error', type='negative')
                else:
                    validation_log.push('[ERROR] VALIDATION FAILED')
                    for error in result.get("errors", []):
                        validation_log.push(f'[ERROR] {error}')
                    ui.notify(f'Failed: {result.get("errors", ["unknown"])[0]}', type='negative')
            
            with ui.row().classes('mt-4 gap-4'):
                ui.button('Check and Apply', on_click=validate_and_update).props('color=green size=lg')
            
            # Context import section
            ui.separator().classes('my-6')
            ui.label('Import from Context JSON').classes('text-lg font-bold mb-4')
            context_json_area = ui.textarea('Paste context_export.json here').classes('w-full h-64')
            
            async def import_context():
                global guardian_instance
                context_json = context_json_area.value.strip()
                if not context_json:
                    ui.notify('Paste context JSON!', type='warning')
                    return
                validation_log.clear()
                validation_log.push('[INFO] Importing context...')
                engine = get_engine()
                if not engine:
                    validation_log.push('[ERROR] Engine not loaded!')
                    ui.notify('Engine not loaded', type='negative')
                    return
                if guardian_instance is None:
                    guardian_instance = UniversalAIGuardian(engine, lambda msg, lvl: validation_log.push(f'[{lvl}] {msg}'))
                result = await guardian_instance.apply_context_patch(context_json)
                if result.get("success"):
                    results = result.get("results", {})
                    for filename, res in results.items():
                        if res.get("success"):
                            validation_log.push(f'[SUCCESS] {filename} updated')
                        else:
                            validation_log.push(f'[ERROR] {filename} failed')
                    ui.notify('Context imported!', type='positive')
                else:
                    validation_log.push(f'[ERROR] {result.get("error")}')
                    ui.notify('Import failed', type='negative')
            
            ui.button('Import Context', on_click=import_context).props('color=blue size=lg').classes('mt-4')

        with ui.tab_panel(tab_debug):
            ui.label('Debug').classes('text-lg font-bold mb-4')
            with ui.row().classes('w-full gap-4'):
                with ui.column().classes('w-1/3'):
                    ui.label('Tests').classes('font-bold mb-2')

                    async def test_ollama():
                        try:
                            import ollama
                            models = ollama.list()
                            ui.notify(f"Ollama: {len(models.get('models', []))} models", type='positive')
                            log_debug(f"Ollama: {models}", "SUCCESS")
                        except Exception as e:
                            ui.notify(f"Ollama: {e}", type='negative')
                            log_debug(f"Ollama error: {e}", "ERROR")

                    ui.button('Test Ollama', on_click=test_ollama).classes('w-full mb-2')
                    ui.button('Test Engine', on_click=lambda: ui.notify("Engine OK" if get_engine() else "Engine ERROR")).classes('w-full mb-2')
                    ui.button('Clear log', on_click=lambda: (DEBUG_LOG.clear(), ui.notify('Log cleared'))).classes('w-full')
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
            ui.label('Editor (ALL FILES PROTECTED)').classes('text-lg font-bold mb-4')
            ui.label('Use Universal Updates tab for protected files').classes('text-yellow-400 mb-4')
            with ui.row().classes('w-full gap-4 items-end'):
                file_selector = ui.select(
                    options=get_project_files(),
                    label='File',
                    on_change=lambda e: load_file_to_editor(e.value)
                ).classes('w-1/3')
                new_file_name = ui.input('New file').classes('w-1/3')

                def create_file():
                    fname = new_file_name.value.strip()
                    if not fname or os.path.exists(fname):
                        ui.notify('File exists!', type='warning')
                        return
                    with open(fname, 'w') as f:
                        f.write(f"# {fname}\n")
                    file_selector.options = get_project_files()
                    file_selector.update()
                    file_selector.value = fname
                    load_file_to_editor(fname)
                    ui.notify(f'{fname} created', type='positive')

                ui.button('Create', on_click=create_file)
            editor_container = ui.column().classes('w-full')

            def load_file_to_editor(filename):
                global current_editor, current_file
                if not filename:
                    return
                current_file = filename
                editor_container.clear()
                with editor_container:
                    with open(filename, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if filename in PROTECTED_FILES:
                        ui.label(f'{filename} - READ ONLY').classes('text-red-400 font-bold mb-2')
                        ui.markdown('Use **Universal Updates** tab to modify')
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
                        ui.notify(f'{current_file} is protected!', type='negative')
                        ui.notify('Use Universal Updates tab', type='warning')
                        return
                    code = current_editor.value
                    if current_file.endswith('.py'):
                        is_valid, error = validate_python_syntax(code)
                        if not is_valid:
                            ui.notify(f'Syntax error: {error[:100]}', type='negative', timeout=10)
                            return
                    with open(current_file, 'w', encoding='utf-8') as f:
                        f.write(code)
                    if current_file == 'main.py':
                        ui.notify('Restarting...', type='info')
                        restart_server()
                    else:
                        ui.notify(f'{current_file} saved', type='positive')
                else:
                    ui.notify('No active editor', type='warning')

            ui.button('Save', on_click=save_current_file).classes('mt-4')
            load_file_to_editor('main.py')
            file_selector.value = 'main.py'

        with ui.tab_panel(tab_console):
            ui.label('Console').classes('text-lg font-bold mb-4')
            with ui.row().classes('w-full items-center gap-4 mb-2'):
                mode_select = ui.select(
                    options={'full': 'Full', 'fast': 'Fast'},
                    value='full',
                    label='Mode'
                ).classes('w-1/3')
            task_input = ui.input('Task (Enter)').classes('w-full')
            status_label = ui.label('Status: Waiting').classes('text-lg mt-4')
            log_area = ui.log(max_lines=200).classes('w-full h-64 bg-black text-green-400 font-mono mt-4')
            result_area = ui.textarea('Result').classes('w-full h-64 mt-4')

            async def run_task():
                if not task_input.value:
                    ui.notify('Enter task!', type='warning')
                    return
                log_area.clear()
                log_area.push('=' * 70)
                log_area.push(f'TASK: {task_input.value}')
                log_area.push(f'MODE: {mode_select.value}')
                log_area.push('=' * 70)
                log_debug(f"Task: {task_input.value[:50]}", "INFO")

                def update_status(text):
                    status_label.text = f"Status: {text}"
                    log_debug(f"Status: {text}", "INFO")
                    log_area.push(f'[STATUS] {text}')

                try:
                    engine = get_engine()
                    if not engine:
                        raise Exception("Engine not loaded")
                    if hasattr(engine, '_get_candidates'):
                        candidates = engine._get_candidates()
                        log_area.push('')
                        log_area.push(f'MODELS TO QUERY: {len(candidates)}')
                        for i, c in enumerate(candidates, 1):
                            provider = c.get('provider', 'ollama').upper()
                            log_area.push(f'  {i}. [{provider}] {c["name"]}')
                        log_area.push('-' * 70)
                    else:
                        log_area.push('Using emergency engine (1 model)')
                        log_area.push('-' * 70)
                    update_status("Sending requests...")
                    if hasattr(engine, 'run_task_detailed'):
                        result = await engine.run_task_detailed(
                            task_input.value,
                            status_callback=update_status,
                            log_callback=lambda msg: log_area.push(msg),
                            mode=mode_select.value
                        )
                    else:
                        result = await engine.run_task(
                            task_input.value,
                            status_callback=update_status,
                            mode=mode_select.value
                        )
                    log_area.push('')
                    log_area.push('=' * 70)
                    log_area.push('TASK COMPLETED')
                    log_area.push('=' * 70)
                    result_area.value = result
                    log_debug("Done", "SUCCESS")
                    update_status("Done")
                except Exception as e:
                    log_area.push('')
                    log_area.push(f'[ERROR] {str(e)}')
                    log_area.push(f'[TRACEBACK] {traceback.format_exc()}')
                    result_area.value = f"Error: {str(e)}"
                    log_debug(f"Error: {e}", "ERROR")
                    update_status("Error")

            task_input.on('keydown.enter', lambda: asyncio.create_task(run_task()))
            ui.button('Send', on_click=run_task).props('color=green').classes('mt-2')


log_debug("CU v3.0.4 FORTRESS started", "SUCCESS")
ensure_base_files()
create_ui()
ui.run(title='CU v3.0.4 FORTRESS', port=8080, dark=True, reload=False)
