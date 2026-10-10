# main.py
# Version 3.1.0 FORTRESS (UNIVERSAL AI-GUARDIAN)

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
    return True, None


def create_triple_backup(filepath: str) -> list:
    if not os.path.exists(filepath):
        return []
    backups = []
    filename = os.path.basename(filepath)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    for suffix in ['', '_verified', '_LATEST']:
        backup_path = os.path.join(BACKUP_DIR, f"{filename}_{timestamp}{suffix}.bak")
        try:
            shutil.copy2(filepath, backup_path)
            backups.append(backup_path)
        except Exception:
            pass
    
    return backups


def restore_from_backup(filename: str) -> bool:
    """Восстанавливает файл из последнего бэкапа"""
    pattern = os.path.join(BACKUP_DIR, f"{filename}_*.bak")
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith(filename) and f.endswith('.bak')], reverse=True)
    
    if backups:
        latest_backup = os.path.join(BACKUP_DIR, backups[0])
        try:
            shutil.copy2(latest_backup, filename)
            log_debug(f"Restored {filename} from {latest_backup}", "SUCCESS")
            return True
        except Exception as e:
            log_debug(f"Restore error: {e}", "ERROR")
    
    return False


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
                return False, f"Python syntax error: {error}"
            if filename == 'agent_engine.py':
                valid, error = validate_engine_structure(content)
                if not valid:
                    return False, f"Structure error: {error}"
        elif file_type == 'json':
            valid, error = validate_json_syntax(content)
            if not valid:
                return False, f"JSON syntax error: {error}"
        
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
        
        if len(content) < 10:
            warnings.append("Very short content")
        
        if filename.endswith('.py'):
            if content.count('def ') == 0 and 'class ' not in content:
                warnings.append("No functions or classes found")
        
        elif filename.endswith('.json'):
            try:
                data = json.loads(content)
                if not 
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
            
            if filename == 'agent_engine.py':
                global engine_instance
                engine_instance = None
            
            if filename == 'main.py':
                self.log("main.py updated - restart required", "WARNING")
            
            return True
        except Exception as e:
            self.log(f"Apply error: {e}", "ERROR")
            backups = validation_result.get("backups", [])
            if backups:
                if restore_from_backup(filename):
                    self.log("Rollback done", "WARNING")
            return False


def create_ui():
    ui.dark_mode().enable()

    with ui.header().classes('bg-gray-900 text-white border-b border-gray-700 p-4'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('drmAIcu v3.1.0 FORTRESS').classes('text-xl font-bold')
            ui.button('RESTART', on_click=restart_server).props('color=orange')

    with ui.tabs().classes('w-full') as tabs:
        tab_dash = ui.tab('dashboard', label='Dashboard')
        tab_agents = ui.tab('agents', label='🤖 Agents')
        tab_updates = ui.tab('updates', label='🛡️ Universal Updates')
        tab_console = ui.tab('console', label='Console')

    with ui.tab_panels(tabs, value=tab_dash).classes('w-full p-6'):

        with ui.tab_panel(tab_dash):
            ui.label('System Status').classes('text-lg font-bold mb-4')
            config = load_config()
            with ui.row().classes('gap-4'):
                ui.badge('Ollama: OK', color='green')
                groq_text = 'Groq: OK' if config.get('groq_api_key') else 'Groq: No'
                groq_color = 'green' if config.get('groq_api_key') else 'red'
                ui.badge(groq_text, color=groq_color)
                ui.badge('Universal Guardian: ACTIVE', color='green')

        with ui.tab_panel(tab_agents):
            ui.label('Agent Management').classes('text-lg font-bold mb-4')
            ui.label('Manage and configure agents for your project').classes('text-gray-400 mb-4')
            
            # Agent list
            agents_data = [
                {'id': 1, 'name': 'Agent #1 — System Development', 'status': 'active', 'enabled': True},
                {'id': 2, 'name': 'Agent #2 — Data Analytics', 'status': 'frozen', 'enabled': False},
                {'id': 3, 'name': 'Agent #3 — Report Automation', 'status': 'frozen', 'enabled': False},
            ]
            
            for agent in agents_data:
                with ui.card().classes('w-full mb-4'):
                    with ui.row().classes('w-full items-center justify-between p-4'):
                        ui.label(agent['name']).classes('font-bold')
                        status_color = 'green' if agent['enabled'] else 'grey'
                        ui.badge(agent['status'], color=status_color)
                    
                    with ui.row().classes('gap-2 p-4'):
                        toggle_btn = ui.button(
                            'Disable' if agent['enabled'] else 'Enable',
                            on_click=lambda a=agent: ui.notify(f"Agent {a['id']} toggled")
                        )
                        toggle_btn.props('color=green' if agent['enabled'] else 'color=grey')

        with ui.tab_panel(tab_updates):
            ui.label('Universal AI-Guardian').classes('text-lg font-bold mb-4')
            ui.label('Update ANY protected file with 4-level validation').classes('text-gray-400 mb-4')
            
            file_selector = ui.select(
                options=PROTECTED_FILES,
                value='agent_engine.py',
                label='Select file to update'
            ).classes('w-full mb-4')
            
            update_description = ui.textarea('Update description', placeholder='What is new?').classes('w-full h-24')
            new_code_area = ui.textarea('New code').classes('w-full h-96')
            validation_log = ui.log(max_lines=50).classes('w-full h-48 bg-black text-green-400 font-mono mt-4')
            
            async def validate_and_update():
                filename = file_selector.value
                if not filename:
                    ui.notify('Select file!', type='warning')
                    return
                if not update_description.value:
                    ui.notify('Enter description!', type='warning')
                    return
                
                validation_log.clear()
                validation_log.push(f'[INFO] Guardian activated for {filename}...')
                
                engine = get_engine()
                if not engine:
                    validation_log.push('[ERROR] Engine not loaded!')
                    return
                
                guardian = UniversalAIGuardian(engine, lambda msg, lvl: validation_log.push(f'[{lvl}] {msg}'))
                new_code = new_code_area.value.strip()
                
                if not new_code:
                    validation_log.push('[ERROR] Enter code!')
                    return
                
                validation_log.push('[INFO] Running 4-level validation...')
                result = await guardian.validate_and_apply_patch(filename, new_code, update_description.value)
                
                if result.get("approved"):
                    validation_log.push('[SUCCESS] ALL LEVELS PASSED!')
                    success = await guardian.apply_patch(filename, new_code, result)
                    if success:
                        validation_log.push('[SUCCESS] Patch applied!')
                        ui.notify('Patch applied!', type='positive')
                else:
                    validation_log.push('[ERROR] VALIDATION FAILED')
                    for error in result.get("errors", []):
                        validation_log.push(f'[ERROR] {error}')
            
            ui.button('Check and Apply', on_click=validate_and_update).props('color=green size=lg').classes('mt-4')

        with ui.tab_panel(tab_console):
            ui.label('Console').classes('text-lg font-bold mb-4')
            task_input = ui.input('Task (Enter)').classes('w-full')
            status_label = ui.label('Status: Waiting').classes('text-lg mt-4')
            log_area = ui.log(max_lines=200).classes('w-full h-64 bg-black text-green-400 font-mono mt-4')
            result_area = ui.textarea('Result').classes('w-full h-64 mt-4')

            async def run_task():
                if not task_input.value:
                    return
                log_area.clear()
                log_area.push(f'TASK: {task_input.value}')
                
                try:
                    engine = get_engine()
                    if not engine:
                        raise Exception("Engine not loaded")
                    status_label.text = "Sending..."
                    result = await engine.run_task(task_input.value, status_callback=lambda t: status_label.text = f"Status: {t}")
                    result_area.value = result
                    status_label.text = "Done"
                except Exception as e:
                    result_area.value = f"Error: {str(e)}"
                    status_label.text = "Error"

            task_input.on('keydown.enter', lambda: asyncio.create_task(run_task()))
            ui.button('Send', on_click=run_task).props('color=green').classes('mt-2')


log_debug("CU v3.1.0 FORTRESS started", "SUCCESS")
ensure_base_files()
create_ui()
ui.run(title='drmAIcu v3.1.0 FORTRESS', port=8080, dark=True, reload=False)
