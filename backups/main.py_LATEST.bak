# main.py
# Version 3.2.0 UI-COMPLETE

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
import re
from datetime import datetime
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === АБСОЛЮТНЫЕ ПУТИ ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'settings.json')
ENGINE_FILE = os.path.join(BASE_DIR, 'agent_engine.py')
RESTART_FLAG = os.path.join(BASE_DIR, 'restart.flag')
DEBUG_LOG = []
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
CHECKSUM_FILE = os.path.join(BASE_DIR, 'backups', 'checksums.json')
PATCH_DIR = os.path.join(BASE_DIR, 'patch')
ARCHIVE_DIR = os.path.join(PATCH_DIR, 'archive')
MANIFEST_FILE = os.path.join(BASE_DIR, 'patch_manifest.json')
PROJECT_ARCHIVE = os.path.join(BASE_DIR, 'project_archive')
IMPORTANT_FILE = os.path.join(BASE_DIR, '.project-important.json')

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(PATCH_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(PROJECT_ARCHIVE, exist_ok=True)

if os.path.exists(RESTART_FLAG):
    try:
        os.remove(RESTART_FLAG)
    except Exception:
        pass

EMERGENCY_ENGINE_CODE = '''# agent_engine.py (EMERGENCY)\nimport asyncio\nimport ollama\nfrom typing import List, Dict\n\nclass AgentEngine:\n    def __init__(self, config, **kwargs):\n        self.config = config\n        self.log = kwargs.get('log_callback', lambda msg, lvl: print(f"[{lvl}] {msg}"))\n        self.log("Emergency engine loaded", "WARNING")\n\n    async def get_code_response(self, candidate: Dict, prompt: str) -> Dict:\n        try:\n            loop = asyncio.get_running_loop()\n            def do_req():\n                return ollama.chat(model=candidate["model"], messages=[{"role": "user", "content": prompt}])\n            response = await asyncio.wait_for(loop.run_in_executor(None, do_req), timeout=60.0)\n            return {"candidate": candidate, "code": response['message']['content'], "error": None}\n        except Exception as e:\n            return {"candidate": candidate, "code": None, "error": str(e)}\n\n    async def run_task(self, prompt: str, status_callback=None, mode: str = "full") -> str:\n        self.log(f"TASK: {prompt[:50]}", "INFO")\n        candidates = [{"model": "qwen2.5-coder:1.5b", "name": "Qwen 1.5B", "provider": "ollama"}]\n        results = await asyncio.gather(*[self.get_code_response(c, prompt) for c in candidates], return_exceptions=True)\n        valid = [r for r in results if isinstance(r, dict) and r.get("code")]\n        return valid[0]["code"] if valid else "All models failed"\n'''

# === КРИТИЧНЫЕ ФАЙЛЫ ===
CRITICAL_FILES = {
    'main.py', 'agent_engine.py', 'settings.json', 'launcher.bat',
    'package.json', 'package-lock.json', 'vite.config.js', 'tsconfig.json',
    'index.html', 'README.md', 'App.tsx', 'main.tsx', 'index.css'
}
CRITICAL_PATHS = {'src/', 'patch/', 'backups/', 'docs/'}
SKIP_FOLDERS = {'node_modules', '.git', '__pycache__', '.venv', 'venv', '.vscode', '.idea'}

# === ЛОГИРОВАНИЕ ===
def log_debug(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {"time": timestamp, "level": level.lower(), "message": message, "source": "Core"}
    DEBUG_LOG.append(entry)
    if len(DEBUG_LOG) > 500:
        DEBUG_LOG.pop(0)
    print(f"[{timestamp}] [{level}] {message}")

# === УТИЛИТЫ ЧТЕНИЯ/ЗАПИСИ ===
def read_file_safe(filepath: str) -> str:
    encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'windows-1251', 'latin-1', 'iso-8859-1']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            if filepath.endswith('.json'):
                json.loads(content)
            return content
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        except Exception:
            return ""
    raise ValueError(f"Не удалось прочитать файл: {filepath}")

def write_file_safe(filepath: str, content: str):
    with open(filepath, 'w', encoding='utf-8-sig') as f:
        f.write(content)

def compute_checksum(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def compute_file_hash(filepath: str) -> str:
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return ""

def human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

# === ВАЛИДАЦИЯ ФАЙЛОВ ===
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

def validate_json_syntax(code: str) -> tuple:
    try:
        json.loads(code)
        return True, None
    except json.JSONDecodeError as e:
        return False, str(e)

def validate_file(filename: str, content: str) -> tuple:
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.py':
        ok, err = validate_python_syntax(content)
        if not ok:
            return False, f"Python syntax: {err}"
        if filename == 'agent_engine.py':
            ok2, err2 = validate_engine_structure(content)
            if not ok2:
                return False, f"Structure: {err2}"
        return True, None
    elif ext == '.json':
        return validate_json_syntax(content)
    else:
        return True, None

# === БЕКАПЫ ===
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
        shutil.copy2(filepath, backup1); backups.append(backup1)
        shutil.copy2(filepath, backup2); backups.append(backup2)
        shutil.copy2(filepath, backup3); backups.append(backup3)
    except Exception:
        pass
    return backups

def restore_from_backup(filepath: str) -> bool:
    filename = os.path.basename(filepath)
    latest = os.path.join(BACKUP_DIR, f"{filename}_LATEST.bak")
    if os.path.exists(latest):
        try:
            shutil.copy2(latest, filepath)
            log_debug(f"Restored {filepath} from backup", "SUCCESS")
            return True
        except Exception as e:
            log_debug(f"Restore error: {e}", "ERROR")
    return False

def ensure_base_files():
    if not os.path.exists(CONFIG_FILE):
        save_config({})
    if not os.path.exists(ENGINE_FILE):
        log_debug("agent_engine.py not found, creating emergency engine", "WARNING")
        with open(ENGINE_FILE, 'w', encoding='utf-8') as f:
            f.write(EMERGENCY_ENGINE_CODE)
        return
    with open(ENGINE_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    v1, e1 = validate_python_syntax(content)
    v2, e2 = validate_engine_structure(content)
    if not v1 or not v2:
        log_debug("agent_engine.py CORRUPTED! Restoring...", "ERROR")
        restore_from_backup(ENGINE_FILE)

# === ДВИЖОК ===
engine_instance = None
_engine_lock = threading.Lock()

def get_engine():
    global engine_instance
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
        log_debug("Engine loaded successfully", "SUCCESS")
        return engine_instance
    except Exception as e:
        log_debug(f"Engine error: {e}", "ERROR")
        log_debug(f"Traceback: {traceback.format_exc()}", "ERROR")
        restore_from_backup(ENGINE_FILE)
        return None

# === КОНФИГУРАЦИЯ ===
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "groq_api_key": "",
        "ollama_url": "http://localhost:11434",
        "openrouter_api_key": "",
        "gemini_api_key": ""
    }

def save_config(data):
    current = load_config()
    current.update(data)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(current, f, indent=4, ensure_ascii=False)

# === УТИЛИТЫ ДЛЯ ПАТЧЕЙ ===
def load_manifest() -> dict:
    if os.path.exists(MANIFEST_FILE):
        try:
            with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"applied": [], "history": [], "rollbacks": []}

def save_manifest(manifest: dict):
    with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

def list_patches() -> list:
    patches = []
    manifest = load_manifest()
    applied_ids = {p['patch_id'] for p in manifest.get('applied', [])}
    if not os.path.exists(PATCH_DIR):
        return patches
    for filename in sorted(os.listdir(PATCH_DIR)):
        if not filename.endswith('.json') or filename.startswith('.') or filename.startswith('_'):
            continue
        filepath = os.path.join(PATCH_DIR, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            content = read_file_safe(filepath)
            data = json.loads(content)
            patch_id = str(data.get('patch_id', filename.replace('.json', '').replace('patch', '')))
            patch_type = data.get('type', 'full_replace')
            target_file = data.get('target_file', 'unknown')
            description = data.get('description', 'Без описания')
            author = data.get('author', 'Unknown')
            created_at = data.get('created_at', '')
            full_content = data.get('full_file_content', '')
            diff_content = data.get('diff', '')
            is_applied = patch_id in applied_ids
            file_exists = os.path.exists(os.path.join(BASE_DIR, target_file)) if target_file != 'unknown' else False
            patches.append({
                'filename': filename,
                'filepath': filepath,
                'patch_id': patch_id,
                'patch_type': patch_type,
                'target_file': target_file,
                'description': description,
                'author': author,
                'created_at': created_at,
                'is_applied': is_applied,
                'file_exists': file_exists,
                'content_length': len(full_content) if patch_type == 'full_replace' else len(diff_content),
                'has_content': bool(full_content) if patch_type == 'full_replace' else bool(diff_content),
                'full_file_content': full_content if patch_type == 'full_replace' else '',
                'diff': diff_content if patch_type == 'unified_diff' else ''
            })
        except Exception as e:
            patches.append({
                'filename': filename,
                'filepath': filepath,
                'patch_id': filename.replace('.json', '').replace('patch', ''),
                'patch_type': 'error',
                'target_file': 'error',
                'description': f'Ошибка чтения: {str(e)[:100]}',
                'author': 'ERROR',
                'created_at': '',
                'is_applied': False,
                'file_exists': False,
                'content_length': 0,
                'has_content': False,
                'error': str(e),
                'full_file_content': '',
                'diff': ''
            })
    patches.sort(key=lambda p: p['patch_id'])
    return patches

def apply_patch(patch_data: dict) -> dict:
    patch_type = patch_data.get('type', 'full_replace')
    target_file = patch_data.get('target_file', '')
    patch_id = patch_data.get('patch_id', 'unknown')
    content = patch_data.get('full_file_content', '')
    if not target_file or not content:
        return {'success': False, 'error': 'Нет target_file или full_file_content'}
    valid, error = validate_file(target_file, content)
    if not valid:
        return {'success': False, 'error': f'Валидация не пройдена: {error}'}
    backups = create_triple_backup(os.path.join(BASE_DIR, target_file))
    temp_file = os.path.join(BASE_DIR, target_file) + '.tmp'
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(temp_file, os.path.join(BASE_DIR, target_file))
        manifest = load_manifest()
        manifest['applied'].append({
            'patch_id': patch_id,
            'target_file': target_file,
            'patch_type': 'full_replace',
            'applied_at': datetime.now().isoformat(),
            'checksum': compute_checksum(content),
            'backups': backups
        })
        manifest['history'].append({
            'action': 'apply',
            'patch_id': patch_id,
            'target_file': target_file,
            'timestamp': datetime.now().isoformat()
        })
        save_manifest(manifest)
        log_debug(f"Patch {patch_id} applied to {target_file}", "SUCCESS")
        return {
            'success': True,
            'patch_type': 'full_replace',
            'message': f'Патч {patch_id} успешно применен к {target_file}',
            'backups': backups
        }
    except Exception as e:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        log_debug(f"Patch apply error: {e}", "ERROR")
        return {'success': False, 'error': f'Ошибка применения: {e}'}

def rollback_last_patch() -> dict:
    manifest = load_manifest()
    if not manifest.get('applied'):
        return {'success': False, 'error': 'Нет примененных патчей для отката'}
    last = manifest['applied'][-1]
    target_file = last['target_file']
    patch_id = last['patch_id']
    filename = os.path.basename(target_file)
    latest_backup = os.path.join(BACKUP_DIR, f"{filename}_LATEST.bak")
    if not os.path.exists(latest_backup):
        return {'success': False, 'error': f'Бэкап не найден: {latest_backup}'}
    try:
        temp_file = os.path.join(BASE_DIR, target_file) + '.tmp'
        shutil.copy2(latest_backup, temp_file)
        os.replace(temp_file, os.path.join(BASE_DIR, target_file))
        manifest['applied'].pop()
        manifest['rollbacks'].append({
            'patch_id': patch_id,
            'target_file': target_file,
            'rolled_back_at': datetime.now().isoformat()
        })
        manifest['history'].append({
            'action': 'rollback',
            'patch_id': patch_id,
            'target_file': target_file,
            'timestamp': datetime.now().isoformat()
        })
        save_manifest(manifest)
        log_debug(f"Rolled back patch {patch_id} for {target_file}", "SUCCESS")
        return {
            'success': True,
            'message': f'Патч {patch_id} откатен. Файл {target_file} восстановлен из бэкапа.'
        }
    except Exception as e:
        log_debug(f"Rollback error: {e}", "ERROR")
        return {'success': False, 'error': f'Ошибка отката: {e}'}

def get_stats() -> dict:
    patches = list_patches()
    manifest = load_manifest()
    total = len(patches)
    applied = len([p for p in patches if p['is_applied']])
    pending = total - applied
    errors = len([p for p in patches if 'error' in p])
    return {
        'total': total,
        'applied': applied,
        'pending': pending,
        'errors': errors,
        'history_count': len(manifest.get('history', [])),
        'rollbacks_count': len(manifest.get('rollbacks', [])),
        'backups_count': len(os.listdir(BACKUP_DIR)) if os.path.exists(BACKUP_DIR) else 0
    }

# ==========================================
# FASTAPI ENDPOINTS
# ==========================================

@app.get("/api/status")
def api_status():
    config = load_config()
    ollama_ok = False
    try:
        import requests
        r = requests.get(f"{config.get('ollama_url', 'http://localhost:11434')}/api/tags", timeout=2)
        ollama_ok = r.status_code == 200
    except Exception:
        pass
    return JSONResponse({
        "ollama": "online" if ollama_ok else "offline",
        "guardian": "active",
        "version": "3.2.0 UI-COMPLETE",
        "providers": {
            "groq": bool(config.get('groq_api_key')),
            "openrouter": bool(config.get('openrouter_api_key')),
            "gemini": bool(config.get('gemini_api_key'))
        }
    })

@app.get("/api/logs")
def api_logs():
    return JSONResponse({"logs": DEBUG_LOG[-100:]})

@app.post("/api/task")
async def api_run_task(payload: dict):
    prompt = payload.get("prompt", "")
    log_debug(f"API Task received: {prompt[:50]}...", "INFO")
    engine = get_engine()
    if not engine:
        return JSONResponse({"error": "Engine not loaded", "result": "Ошибка загрузки движка"})
    try:
        result = await engine.run_task(prompt, mode="full")
        return JSONResponse({"success": True, "result": result})
    except Exception as e:
        log_debug(f"Task error: {e}", "ERROR")
        return JSONResponse({"success": False, "error": str(e), "result": "Ошибка выполнения"})

@app.get("/api/patches/list")
def api_patches_list():
    try:
        patches = list_patches()
        return JSONResponse({"success": True, "patches": patches})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/patches/stats")
def api_patches_stats():
    try:
        stats = get_stats()
        return JSONResponse({"success": True, "stats": stats})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/patches/apply")
def api_patches_apply(payload: dict):
    try:
        result = apply_patch(payload)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/patches/rollback")
def api_patches_rollback():
    try:
        result = rollback_last_patch()
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/patches/apply-all")
def api_patches_apply_all(payload: dict):
    try:
        patches = list_patches()
        pending = [p for p in patches if not p['is_applied'] and p.get('has_content')]
        results = []
        for patch_info in pending:
            try:
                content = read_file_safe(patch_info['filepath'])
                patch_data = json.loads(content)
                result = apply_patch(patch_data)
                results.append({'patch_id': patch_info['patch_id'], **result})
                if not result.get('success'):
                    break
            except Exception as e:
                results.append({'patch_id': patch_info['patch_id'], 'success': False, 'error': str(e)})
                break
        return JSONResponse({"success": True, "results": results})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

# ==========================================
# UI
# ==========================================

def create_ui():
    ui.dark_mode().enable()
    
    with ui.header().classes('bg-gray-900 text-white p-4'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('🛡️ drmAIcu Core v3.2.0').classes('text-xl font-bold')
            ui.button('🔄 RESTART', on_click=lambda: os._exit(0)).props('color=orange')
    
    with ui.tabs().classes('w-full') as tabs:
        tab_console = ui.tab('console', label='💬 Console')
        tab_updates = ui.tab('updates', label='🛡️ Updates')
        tab_debug = ui.tab('debug', label='🐞 Debug')
    
    with ui.tab_panels(tabs, value=tab_console).classes('w-full p-6'):
        
        # === CONSOLE TAB ===
        with ui.tab_panel(tab_console):
            ui.label('💬 Console').classes('text-lg font-bold mb-4')
            
            with ui.row().classes('w-full items-center gap-4 mb-2'):
                mode_select = ui.select(
                    options={'full': '🔍 Полный', 'fast': '⚡ Быстрый'},
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
                log_debug(f"Task: {task_input.value[:50]}", "INFO")
                
                def update_status(text):
                    status_label.text = f"Статус: {text}"
                    log_debug(f"Status: {text}", "INFO")
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
                    
                    update_status("Отправка запросов...")
                    result = await engine.run_task(
                        task_input.value,
                        status_callback=update_status,
                        mode=mode_select.value
                    )
                    log_area.push('')
                    log_area.push('=' * 70)
                    log_area.push('✅ ЗАДАЧА ВЫПОЛНЕНА')
                    log_area.push('=' * 70)
                    result_area.value = result
                    log_debug("Done", "SUCCESS")
                    update_status("🏁 Готово")
                except Exception as e:
                    log_area.push('')
                    log_area.push(f'[ОШИБКА] {str(e)}')
                    log_area.push(f'[TRACEBACK] {traceback.format_exc()}')
                    result_area.value = f"Ошибка: {str(e)}"
                    log_debug(f"Error: {e}", "ERROR")
                    update_status("❌ Ошибка")
            
            task_input.on('keydown.enter', lambda: asyncio.create_task(run_task()))
            ui.button('▶️ Отправить', on_click=run_task).props('color=green').classes('mt-2')
        
        # === UPDATES TAB ===
        with ui.tab_panel(tab_updates):
            ui.label('🛡️ Управление патчами').classes('text-lg font-bold mb-4')
            
            stats_container = ui.row().classes('w-full gap-4 mb-4')
            patches_container = ui.column().classes('w-full')
            
            async def refresh_patches():
                stats_container.clear()
                patches_container.clear()
                
                stats = get_stats()
                with stats_container:
                    ui.badge(f"📊 Всего: {stats['total']}", color='blue')
                    ui.badge(f"✅ Применено: {stats['applied']}", color='green')
                    ui.badge(f"⏳ Ожидает: {stats['pending']}", color='orange')
                    ui.badge(f"❌ Ошибок: {stats['errors']}", color='red')
                
                patches = list_patches()
                with patches_container:
                    for patch in patches:
                        with ui.card().classes('w-full mb-2'):
                            with ui.row().classes('w-full items-center justify-between'):
                                with ui.column().classes('flex-grow'):
                                    ui.label(f"📦 {patch['patch_id']}").classes('font-bold')
                                    ui.label(f"📄 {patch['target_file']} | {patch['patch_type']}").classes('text-sm text-gray-400')
                                    ui.label(patch['description']).classes('text-sm')
                                
                                status = '✅ Применён' if patch['is_applied'] else '⏳ Ожидает'
                                color = 'green' if patch['is_applied'] else 'orange'
                                ui.badge(status, color=color)
                                
                                if not patch['is_applied'] and patch['has_content']:
                                    async def apply_single(p=patch):
                                        try:
                                            content = read_file_safe(p['filepath'])
                                            patch_data = json.loads(content)
                                            result = apply_patch(patch_data)
                                            if result.get('success'):
                                                ui.notify(f"✅ {p['patch_id']} применён!", type='positive')
                                                await refresh_patches()
                                            else:
                                                ui.notify(f"❌ Ошибка: {result.get('error')}", type='negative')
                                        except Exception as e:
                                            ui.notify(f"❌ {str(e)}", type='negative')
                                    
                                    ui.button('▶️ Применить', on_click=apply_single).props('color=green size=sm')
            
            with ui.row().classes('gap-2 mb-4'):
                ui.button('🔄 Обновить', on_click=refresh_patches).props('color=blue')
                
                async def apply_all():
                    patches = list_patches()
                    pending = [p for p in patches if not p['is_applied'] and p.get('has_content')]
                    if not pending:
                        ui.notify('Нет ожидающих патчей', type='info')
                        return
                    for p in pending:
                        try:
                            content = read_file_safe(p['filepath'])
                            patch_data = json.loads(content)
                            result = apply_patch(patch_data)
                            if not result.get('success'):
                                ui.notify(f"❌ Ошибка на {p['patch_id']}: {result.get('error')}", type='negative')
                                break
                        except Exception as e:
                            ui.notify(f"❌ {str(e)}", type='negative')
                            break
                    ui.notify('✅ Все патчи применены!', type='positive')
                    await refresh_patches()
                
                ui.button('▶️ Применить все', on_click=apply_all).props('color=green')
                
                async def rollback():
                    result = rollback_last_patch()
                    if result.get('success'):
                        ui.notify(result['message'], type='positive')
                        await refresh_patches()
                    else:
                        ui.notify(f"❌ {result.get('error')}", type='negative')
                
                ui.button('↩️ Откатить', on_click=rollback).props('color=orange')
            
            ui.run_javascript(refresh_patches)
        
        # === DEBUG TAB ===
        with ui.tab_panel(tab_debug):
            ui.label('🐞 Отладка').classes('text-lg font-bold mb-4')
            
            with ui.row().classes('w-full gap-4'):
                with ui.column().classes('w-1/3'):
                    ui.label('Тесты').classes('font-bold mb-2')
                    
                    async def test_ollama():
                        try:
                            import requests
                            config = load_config()
                            r = requests.get(f"{config.get('ollama_url', 'http://localhost:11434')}/api/tags", timeout=5)
                            if r.status_code == 200:
                                models = r.json().get('models', [])
                                ui.notify(f"✅ Ollama: {len(models)} моделей", type='positive')
                            else:
                                ui.notify("❌ Ollama не отвечает", type='negative')
                        except Exception as e:
                            ui.notify(f"❌ Ollama: {e}", type='negative')
                    
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
                                log_display.push(f"[{entry['time']}] [{entry['level'].upper()}] {entry['message']}")
                            _last_log_len = len(DEBUG_LOG)
                    
                    ui.timer(1, update_log, once=False)

if __name__ in {"__main__", "__mp_main__"}:
    ensure_base_files()
    log_debug("Starting drmAIcu Core v3.2.0 UI-COMPLETE...", "INFO")
    get_engine()
    create_ui()
    
    ui.run(
        title="drmAIcu Core v3.2.0",
        port=8080,
        reload=False,
        show=False,
        favicon="🤖"
    )
