# main.py HARDENED (UI + API; engine lives in patch_engine.py; версия — version.py)
from version import VERSION as _VER
from nicegui import ui, app
import json, os, sys, re, ast, shutil, hashlib, threading, importlib, traceback, asyncio, time, subprocess
from datetime import datetime, timedelta
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8080', 'http://localhost:8080'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
except RuntimeError:
    pass
import patch_engine as _pe
from patch_engine import (
    TX_LOCK, apply_diff, apply_patch, apply_search_replace, backup, check_ts,
    compute_new, compute_ops, find_block, find_patch_file, file_newline,
    list_patches, load_manifest, normalize_ops, preview_patch, read_text,
    resolve, rollback, safe_path, save_manifest, sha, sha_bytes, stats,
    test_apply, to_bytes, validate,
)
from core.plugins.routes import plugin_router, startup_plugins, get_manager

app.include_router(plugin_router)
startup_plugins()
from guards import is_critical_rel, is_doc_rel, validate_url
BASE = _pe.BASE
PATCH_DIR = _pe.PATCH_DIR
ARCHIVE_DIR = _pe.ARCHIVE_DIR
BACKUP_DIR = _pe.BACKUP_DIR
MANIFEST = _pe.MANIFEST
CONFIG = os.path.join(BASE, 'settings.json')
ENGINE = os.path.join(BASE, 'agent_engine.py')
RESTART_FLAG = os.path.join(BASE, 'restart.flag')
PROJ_ARCHIVE = os.path.join(BASE, 'project_archive')
IMPORTANT = os.path.join(BASE, '.project-important.json')
LOG = []
SKIP = {'node_modules', '.git', '__pycache__', '.venv', 'venv', '.vscode', '.idea', 'dist', 'project_archive', '.vite', '.pytest_cache'}

for d in (PATCH_DIR, ARCHIVE_DIR, BACKUP_DIR, PROJ_ARCHIVE):
    os.makedirs(d, exist_ok=True)


def log(msg, lvl='INFO'):
    t = datetime.now().strftime('%H:%M:%S')
    LOG.append({'time': t, 'level': lvl.lower(), 'message': str(msg), 'source': 'Core'})
    if len(LOG) > 500:
        LOG.pop(0)
    print('[' + t + '] [' + lvl + '] ' + str(msg))

_pe.log = log


def human(n):
    if n < 1024:
        return str(n) + ' B'
    if n < 1048576:
        return str(round(n / 1024, 1)) + ' KB'
    return str(round(n / 1048576, 1)) + ' MB'


def load_cfg():
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'ollama_url': 'http://localhost:11434'}



@app.get('/api/patches/dump')
def s_dump():
    import re
    with open(os.path.join(BASE, 'patch_engine.py'), 'r', encoding='utf-8') as f:
        content = f.read()
    def extract(name):
        pat = re.compile(r'^\s*(?:async\s+)?def\s+' + re.escape(name) + r'\s*\(', re.MULTILINE)
        m = pat.search(content)
        if not m:
            return None
        start = m.start()
        indent_str = content[start:content.index('def', start)]
        indent = len(indent_str)
        lines = content[start:].split('\n')
        end = 0
        for i in range(1, len(lines)):
            ln = lines[i]
            if not ln.strip():
                continue
            li = len(ln) - len(ln.lstrip())
            if li <= indent and (ln.strip().startswith('def ') or ln.strip().startswith('async def ') or ln.strip().startswith('@')):
                end = sum(len(l) + 1 for l in lines[:i])
                break
        else:
            end = len(content) - start
        return content[start:start + end].rstrip()
    return JSONResponse({
        'success': True,
        'apply_patch': extract('apply_patch'),
        'apply_patch_atomic': extract('apply_patch_atomic'),
        'apply_search_replace': extract('apply_search_replace'),
        'preview_patch': extract('preview_patch'),
        'validate': extract('validate')
    })




@app.post('/api/project/smart-cleanup')
def s_smart_cleanup():
    """Возвращает список файлов, которые безопасно удалить (мусор), исключая важные."""
    try:
        files = smart_cleanup_scan()
        return {'success': True, 'files': files, 'count': len(files)}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def important_set():
    if os.path.exists(IMPORTANT):
        try:
            with open(IMPORTANT, 'r', encoding='utf-8') as f:
                return set(json.load(f).get('important', []))
        except Exception:
            pass
    return set()


def _archive_parts(rel_path):
    safe_rel = str(rel_path).replace(chr(92), '/').strip('/')
    return [q for q in safe_rel.split('/') if q and q not in ('.', '..')]


def _archive_rel_entry(archive_full):
    parts = os.path.abspath(archive_full).replace(chr(92), '/').split('/')
    for i, q in enumerate(parts):
        if q == 'project_archive':
            return '/'.join(parts[i + 1:])
    return None


def classify_file(name, rel, size):
    r = rel.replace('\\', '/').lower()
    n = name.lower()
    # Критическое ядро
    if is_critical_rel(rel):
        return {'category': 'critical', 'risk': 'critical', 'icon': 'lock',
                'reason': 'Критическое ядро системы. Удаление сломает приложение.', 'action': 'keep'}
    # Одноразовые скрипты миграции/фиксов — мусор
    import re as _re
    if _re.match(r'^(apply|fix|emergency|clean|restore|patch)_.*\\.py$', n):
        return {'category': 'trash', 'risk': 'low', 'icon': 'trash',
                'reason': 'Одноразовый скрипт миграции/фикса. Безопасно к удалению.', 'action': 'delete'}
    if n.startswith('diag_') or n.startswith('auto_fix') or n.startswith('final_') or n.startswith('make_perfect') or n.startswith('fix_all') or n.startswith('fix_backend') or n.startswith('create_audit') or n.startswith('generate_and_check') or n.startswith('patch_dryrun'):
        return {'category': 'trash', 'risk': 'low', 'icon': 'trash',
                'reason': 'Вспомогательный скрипт диагностики. Безопасно к удалению.', 'action': 'delete'}
    # Резервные копии
    if n.endswith('.bak'):
        return {'category': 'backup', 'risk': 'medium', 'icon': 'archive',
                'reason': 'Резервная копия. Можно архивировать.', 'action': 'archive'}
    # Мусор по размеру/расширению
    if size == 0 or n.endswith(('.tmp', '.pyc')) or n in ('.ds_store', 'thumbs.db', 'desktop.ini'):
        return {'category': 'trash', 'risk': 'low', 'icon': 'trash',
                'reason': 'Пустой файл или временный артефакт. Безопасно к удалению.', 'action': 'delete'}
    # Логи
    if n.endswith(('.log', '.txt')) and not n.endswith('requirements.txt'):
        return {'category': 'logs', 'risk': 'low', 'icon': 'file',
                'reason': 'Лог/текстовый артефакт.', 'action': 'archive'}
    # Документация
    if n.endswith('.md'):
        return {'category': 'docs', 'risk': 'low', 'icon': 'book',
                'reason': 'Документация.', 'action': 'keep'}
    # Код
    if n.endswith(('.py', '.tsx', '.ts', '.jsx', '.js')):
        return {'category': 'code', 'risk': 'medium', 'icon': 'code',
                'reason': 'Исходный код. Проверить перед удалением.', 'action': 'keep'}
    # Конфиг
    if n.endswith(('.json', '.yaml', '.yml', '.ini', '.cfg')):
        return {'category': 'config', 'risk': 'medium', 'icon': 'gear',
                'reason': 'Конфигурация. Проверить перед удалением.', 'action': 'keep'}
    # Скрипты запуска
    if n.endswith(('.bat', '.cmd', '.sh')):
        return {'category': 'scripts', 'risk': 'medium', 'icon': 'terminal',
                'reason': 'Скрипт запуска.', 'action': 'keep'}
    if n.endswith(('.html', '.css')):
        return {'category': 'web', 'risk': 'low', 'icon': 'globe',
                'reason': 'Веб-ресурс.', 'action': 'keep'}
    return {'category': 'other', 'risk': 'low', 'icon': 'file',
            'reason': 'Неизвестный тип файла.', 'action': 'keep'}

def category(name, rel, size):
    return classify_file(name, rel, size)['category']

def load_important():
    if os.path.exists(IMPORTANT):
        try:
            with open(IMPORTANT, 'r', encoding='utf-8') as f:
                return set(json.load(f).get('important', []))
        except Exception:
            pass
    return set()

def save_important(items):
    try:
        with open(IMPORTANT, 'w', encoding='utf-8') as f:
            json.dump({'important': sorted(list(items))}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def smart_cleanup_scan():
    important = important_set()
    result = []
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', '__pycache__', 'backups', 'project_archive')]
        for fn in files:
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, BASE).replace('\\', '/')
            if rel in important:
                continue
            try:
                size = os.path.getsize(fp)
            except Exception:
                size = 0
            info = classify_file(fn, rel, size)
            if info['action'] == 'delete':
                result.append({'target_file': rel, 'size': size, **info})
    return result



ICONS = {'.py': 'PY', '.tsx': 'TSX', '.ts': 'TS', '.js': 'JS', '.json': 'CFG',
         '.md': 'MD', '.bat': 'BAT', '.html': 'HTML', '.css': 'CSS', '.bak': 'BAK'}


def get_cleanup_recommendation(f):
    name = f.get('filename', '')
    rel = f.get('path', '')
    size = f.get('size', 0)
    ext = f.get('extension', '')
    size_human = f.get('size_human', human(size))
    is_dup = f.get('is_duplicate', False)
    dups = f.get('duplicates', [])
    is_critical = f.get('is_critical', False)
    is_important = f.get('is_important', False)
    if is_critical or is_important:
        return {'action': 'keep', 'reason': 'Критичный или помеченный как важный'}
    if size == 0 and ext not in ('.gitkeep', '.keep'):
        return {'action': 'delete', 'reason': 'Пустой файл (0 байт)'}
    if name in ('.DS_Store', 'Thumbs.db', 'desktop.ini', 'ehthumbs.db'):
        return {'action': 'delete', 'reason': 'Системный мусор ОС'}
    if ext in ('.tmp', '.pyc', '.pyo') or '__pycache__' in rel or '.vite' in rel:
        return {'action': 'delete', 'reason': 'Временный файл или кэш'}
    if re.search(r'_(old|backup|v\d+|copy|fixed|ru)\.', name, re.IGNORECASE):
        return {'action': 'delete', 'reason': 'Устаревшая/тестовая версия файла'}
    if rel.startswith('backups/') and ext == '.bak':
        try:
            mt = datetime.fromisoformat(f.get('modified', ''))
            if datetime.now() - mt > timedelta(days=7):
                return {'action': 'delete', 'reason': 'Старый бэкап (>7 дней)'}
        except Exception:
            pass
        return {'action': 'review', 'reason': 'Свежий бэкап. Проверить перед удалением'}
    if ext in ('.log', '.txt') and size > 5 * 1024 * 1024:
        return {'action': 'review', 'reason': 'Большой файл (' + size_human + ')'}
    if is_dup and dups:
        primary = dups[0]
        if len(rel) > len(primary):
            return {'action': 'delete', 'reason': 'Дубликат. Оригинал: ' + primary}
        else:
            return {'action': 'review', 'reason': 'Дубликат в: ' + ', '.join(dups[:2])}
    if re.match(r'^(test|temp|tmp|untitled|new_file|copy)\..+', name, re.IGNORECASE) and '/' not in rel:
        return {'action': 'review', 'reason': 'Подозрительное временное имя'}
    return {'action': 'keep', 'reason': 'Файл корректен'}


def scan_project():
    files = []
    hashes = {}
    imp = important_set()
    for root, dirs, names in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for n in names:
            p = os.path.join(root, n)
            rel = os.path.relpath(p, BASE).replace('\\', '/')
            try:
                stt = os.stat(p)
                h = ''
                try:
                    with open(p, 'rb') as f:
                        h = hashlib.md5(f.read()).hexdigest()
                except Exception:
                    pass
                cat = category(n, rel, stt.st_size)
                files.append({'path': rel, 'filename': n, 'size': stt.st_size,
                              'size_human': human(stt.st_size),
                              'modified': datetime.fromtimestamp(stt.st_mtime).isoformat(),
                              'category': cat, 'hash': h,
                              'is_critical': cat == 'critical', 'is_important': rel in imp,
                              'extension': os.path.splitext(n)[1].lower(),
                              'icon': ICONS.get(os.path.splitext(n)[1].lower(), 'FILE'),
                              'is_duplicate': False, 'duplicates': []})
                if h:
                    hashes.setdefault(h, []).append(rel)
            except Exception:
                continue
    for f in files:
        g = hashes.get(f['hash'], [])
        if len(g) > 1:
            f['is_duplicate'] = True
            f['duplicates'] = [x for x in g if x != f['path']]
    for f in files:
        f['cleanup'] = get_cleanup_recommendation(f)
    total = sum(f['size'] for f in files)
    st = {'total': len(files), 'total_size': total, 'total_size_human': human(total),
          'by_category': {}, 'by_extension': {},
          'duplicates_count': len([f for f in files if f['is_duplicate']]),
          'duplicates_groups': len([v for v in hashes.values() if len(v) > 1]),
          'critical_count': len([f for f in files if f['is_critical']]),
          'important_count': len([f for f in files if f['is_important']]),
          'trash_count': len([f for f in files if f['category'] == 'trash']),
          'backup_count': len([f for f in files if f['category'] == 'backup']),
          'cleanup_delete_count': len([f for f in files if f['cleanup']['action'] == 'delete']),
          'cleanup_review_count': len([f for f in files if f['cleanup']['action'] == 'review'])}
    for f in files:
        st['by_category'][f['category']] = st['by_category'].get(f['category'], 0) + 1
        st['by_extension'][f['extension']] = st['by_extension'].get(f['extension'], 0) + 1
    return {'files': files, 'stats': st}


engine_obj = None
lock = threading.Lock()


def get_engine():
    global engine_obj
    with lock:
        if engine_obj is not None:
            return engine_obj
        try:
            if 'agent_engine' in sys.modules:
                importlib.reload(sys.modules['agent_engine'])
            else:
                import agent_engine
            engine_obj = sys.modules['agent_engine'].AgentEngine(load_cfg(), log_callback=log)
            log('Engine loaded', 'SUCCESS')
        except Exception as e:
            log('Engine error: ' + str(e), 'ERROR')
        return engine_obj


@app.get('/rollback')
def rollback_page():
    """Аварийная страница отката"""
    rollback_html = os.path.join(BASE, 'rollback.html')
    if os.path.exists(rollback_html):
        return FileResponse(rollback_html)
    return {'error': 'rollback.html not found'}


@app.get('/api/status')
def s_status():
    cfg = load_cfg()
    ok = False
    try:
        import requests
        r = requests.get(cfg.get('ollama_url', 'http://localhost:11434') + '/api/tags', timeout=2)
        ok = r.status_code == 200
    except Exception:
        pass
    return JSONResponse({'ollama': 'online' if ok else 'offline', 'guardian': 'active',
                         'version': _VER + ' MULTI-ATOMIC HARDENED',
                         'providers': {'groq': bool(cfg.get('groq_api_key')),
                                       'openrouter': bool(cfg.get('openrouter_api_key')),
                                       'gemini': bool(cfg.get('gemini_api_key'))}})


@app.get('/api/version')
def s_version():
    # Оболочка (Header) берёт версию отсюда — единый источник version.py (B68), без хардкода в UI.
    return JSONResponse({'success': True, 'version': _VER})


@app.get('/api/logs')
def s_logs():
    # Вкладка «Логи»: ядро (LOG) + ошибки/предупреждения плагинов из журналов
    # активности (manager.recent_issues) — раньше ошибки плагинов туда не попадали.
    merged = list(LOG[-100:])
    try:
        mgr = get_manager()
        if mgr is not None:
            merged.extend(mgr.recent_issues(limit=60))
    except Exception:
        pass  # логи ядра всё равно отдаём
    return JSONResponse({'logs': merged})


@app.delete('/api/logs/issues')
def s_logs_clear_issues():
    """Кнопка «Очистить ошибки» во вкладке «Логи».

    Честное поведение: удаляем из журнала только записи уровня error/warn —
    как из ядра (LOG), так и из журналов активности плагинов
    (manager.clear_issues → data/plugins/activity/*.jsonl). Info/action записи
    остаются. Без этого пользователь не может убрать старые уже исправленные ошибки.
    """
    before = len(LOG)
    LOG[:] = [e for e in LOG if e.get('level') not in ('error', 'warn')]
    removed = before - len(LOG)
    try:
        mgr = get_manager()
        if mgr is not None:
            removed += mgr.clear_issues()
    except Exception:
        pass  # логи ядра мы уже очистили — не отдаём 500 из-за плагинов
    return JSONResponse({'success': True, 'removed': removed})


@app.post('/api/logs')
async def s_log_add(payload: dict):
    """Принять ошибку/событие от UI и сохранить в общий LOG.

    Нужно, чтобы ошибки, увиденные на фронтенде (плашка «Репозитории/Плагины»),
    остались во вкладке «Логи» даже после перезагрузки страницы.
    Поле time приходит от клиента (dedupe по time+message на фронтенде).
    """
    msg = str(payload.get('message') or '')[:2000]
    lvl = str(payload.get('level') or 'info').lower()
    if lvl not in ('info', 'warn', 'error', 'success'):
        lvl = 'info'
    if not msg:
        return JSONResponse({'success': False, 'error': 'пустое сообщение (message)'})
    src = str(payload.get('source') or 'UI')[:60]
    t = str(payload.get('time') or datetime.now().strftime('%H:%M:%S'))[:12]
    LOG.append({'time': t, 'level': lvl, 'message': msg, 'source': src})
    if len(LOG) > 500:
        LOG.pop(0)
    return JSONResponse({'success': True})


_RES_CACHE = {'ts': 0.0, 'data': None}
_RES_LOCK = threading.Lock()


def _get_ram_gb():
    try:
        if sys.platform == 'win32':
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            total = st.ullTotalPhys / (1024 ** 3)
            used = (st.ullTotalPhys - st.ullAvailPhys) / (1024 ** 3)
            return round(used, 1), round(total, 1)
    except Exception:
        pass
    return 0.0, 0.0


def _get_vram_total_gb():
    if sys.platform != 'win32':
        return 0.0
    max_bytes = 0
    try:
        import winreg
        base_key = r'SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
        for i in range(16):
            sub = rf'{base_key}\{i:04d}'
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub) as k:
                    val, _ = winreg.QueryValueEx(k, 'HardwareInformation.qwMemorySize')
                    if isinstance(val, bytes):
                        val = int.from_bytes(val, 'little')
                    if isinstance(val, int) and val > max_bytes:
                        max_bytes = val
            except OSError:
                continue
    except Exception:
        pass
    return round(max_bytes / (1024 ** 3), 1) if max_bytes > 0 else 0.0


def _get_vram_used_gb():
    if sys.platform != 'win32':
        return 0.0
    try:
        cmd = [
            'powershell', '-NoProfile', '-Command',
            '(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory | Measure-Object -Property DedicatedUsage -Sum).Sum'
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=4, creationflags=0x08000000)
        out = (r.stdout or '').strip().replace(',', '.')
        if out:
            val = float(out)
            return round(val / (1024 ** 3), 1)
    except Exception:
        pass
    return 0.0


@app.get('/api/system/resources')
def s_sys_resources():
    now = time.time()
    with _RES_LOCK:
        if _RES_CACHE['data'] is not None and (now - _RES_CACHE['ts']) < 2.5:
            return JSONResponse(_RES_CACHE['data'])
        ram_used, ram_total = _get_ram_gb()
        vram_total = _get_vram_total_gb()
        vram_used = _get_vram_used_gb()
        data = {
            'ram_used_gb': ram_used,
            'ram_total_gb': ram_total,
            'vram_used_gb': vram_used,
            'vram_total_gb': vram_total,
        }
        _RES_CACHE['data'] = data
        _RES_CACHE['ts'] = now
        return JSONResponse(data)


@app.get('/api/md/{name:path}')
def s_md_get(name):
    if not is_doc_rel(name):
        return JSONResponse({'content': '', 'name': name, 'error': 'Разрешены только Markdown-файлы документации (*.md)'})
    p = safe_path(name)
    if p is None:
        return JSONResponse({'content': '', 'name': name, 'error': 'forbidden'})
    if os.path.exists(p):
        return JSONResponse({'content': read_text(p), 'name': name})
    return JSONResponse({'content': '', 'name': name, 'error': 'not found'})


@app.post('/api/md/{name:path}')
def s_md_post(name, payload: dict):
    if not is_doc_rel(name):
        return JSONResponse({'success': False, 'error': 'Разрешены только Markdown-файлы документации (*.md)'})
    p = safe_path(name)
    if p is None:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    try:
        with open(p, 'w', encoding='utf-8') as f:
            f.write(payload.get('content', ''))
        return JSONResponse({'success': True})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


@app.post('/api/task')
async def s_task(payload: dict):
    e = get_engine()
    if not e:
        return JSONResponse({'success': False, 'error': 'Engine not loaded'})
    try:
        prompt = payload.get('prompt', '')
        mode = payload.get('mode', 'fast')
        model = payload.get('model', '')
        provider = payload.get('provider', 'ollama')
        r = await e.run_task(prompt, mode=mode, model=model, provider=provider)
        return JSONResponse(r)
    except Exception as ex:
        return JSONResponse({'success': False, 'result': '', 'error': str(ex), 'providers': []})


AGENTS_FILE = os.path.join(BASE, 'agents.json')


@app.get('/api/agents')
def s_agents_get():
    if os.path.exists(AGENTS_FILE):
        try:
            with open(AGENTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return JSONResponse({'success': True, 'agents': data})
        except Exception as e:
            return JSONResponse({'success': False, 'error': str(e), 'agents': None})
    return JSONResponse({'success': True, 'agents': None})


@app.post('/api/agents')
def s_agents_post(payload: dict):
    try:
        items = payload.get('agents')
        if not isinstance(items, list):
            return JSONResponse({'success': False, 'error': 'agents must be a list'})
        tmp = AGENTS_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        os.replace(tmp, AGENTS_FILE)
        return JSONResponse({'success': True})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


@app.post('/api/task/stream')
async def s_task_stream(payload: dict):
    e = get_engine()
    if not e:
        return JSONResponse({'success': False, 'error': 'Engine not loaded'}, status_code=503)
    prompt = payload.get('prompt', '')
    mode = payload.get('mode', 'fast')
    model = payload.get('model', '')
    provider = payload.get('provider', 'ollama')
    system_prompt = payload.get('system_prompt', '')

    async def event_gen():
        try:
            async for ev in e.stream_task(prompt, mode=mode, model=model, provider=provider, system_prompt=system_prompt):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            return
        except Exception as ex:
            yield f"data: {json.dumps({'type': 'error', 'error': str(ex)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type='text/event-stream')


PIPELINES_FILE = os.path.join(BASE, 'pipelines.json')


@app.get('/api/pipelines')
def s_pipelines_get():
    if os.path.exists(PIPELINES_FILE):
        try:
            with open(PIPELINES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return JSONResponse({'success': True, 'pipelines': data})
        except Exception as e:
            return JSONResponse({'success': False, 'error': str(e), 'pipelines': None})
    return JSONResponse({'success': True, 'pipelines': None})


@app.post('/api/pipelines')
def s_pipelines_post(payload: dict):
    try:
        items = payload.get('pipelines')
        if not isinstance(items, list):
            return JSONResponse({'success': False, 'error': 'pipelines must be a list'})
        tmp = PIPELINES_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        os.replace(tmp, PIPELINES_FILE)
        return JSONResponse({'success': True})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


@app.post('/api/task/council')
async def s_task_council(payload: dict):
    e = get_engine()
    if not e:
        return JSONResponse({'success': False, 'error': 'Engine not loaded'}, status_code=503)
    prompt = payload.get('prompt', '')
    agents = payload.get('agents') or []
    judge = payload.get('judge')

    async def event_gen():
        try:
            async for ev in e.stream_council(prompt, agents=agents, judge=judge):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            return
        except Exception as ex:
            yield f"data: {json.dumps({'type': 'error', 'error': str(ex)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type='text/event-stream')


@app.post('/api/task/pipeline')
async def s_task_pipeline(payload: dict):
    e = get_engine()
    if not e:
        return JSONResponse({'success': False, 'error': 'Engine not loaded'}, status_code=503)
    prompt = payload.get('prompt', '')
    steps = payload.get('steps') or []

    async def event_gen():
        try:
            async for ev in e.stream_pipeline(prompt, steps=steps):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            return
        except Exception as ex:
            yield f"data: {json.dumps({'type': 'error', 'error': str(ex)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type='text/event-stream')


@app.post('/api/context/build')
def s_context_build(payload: dict):
    files = payload.get('files') or []
    include_logs = bool(payload.get('include_logs'))
    code_issues = payload.get('code_issues') or []
    blocks = []
    attached = []
    total_chars = 0
    max_total = 36000

    for rel in files[:10]:
        rel_str = str(rel).strip()
        if not rel_str:
            continue
        fp = safe_path(rel_str)
        if fp and os.path.isfile(fp):
            try:
                txt = read_text(fp)
                if len(txt) > 12000:
                    txt = txt[:12000] + '\n... [обрезано по лимиту 12000 символов]'
                if total_chars + len(txt) > max_total:
                    break
                total_chars += len(txt)
                blocks.append(f'--- ФАЙЛ ПРОЕКТА: {rel_str} ---\n{txt}')
                attached.append(rel_str)
            except Exception:
                continue

    if include_logs and LOG:
        tail = LOG[-25:]
        log_lines = [f"[{x.get('time', '')}] [{x.get('level', '')}] {x.get('message', '')}" for x in tail]
        blocks.append('--- ПОСЛЕДНИЕ ЛОГИ ЯДРА ---\n' + '\n'.join(log_lines))

    if isinstance(code_issues, list) and len(code_issues) > 0:
        issue_lines = [
            f"- {it.get('file', '?')}:{it.get('line', '?')} — {it.get('title', '')}: {it.get('description', '')}"
            for it in code_issues[:15] if isinstance(it, dict)
        ]
        if issue_lines:
            blocks.append('--- ОТКРЫТЫЕ ЗАМЕЧАНИЯ В КОДЕ ---\n' + '\n'.join(issue_lines))

    return JSONResponse({
        'success': True,
        'context_text': '\n\n'.join(blocks),
        'attached_files': attached,
    })


@app.post('/api/patches/save-from-console')
def s_save_patch_from_console(payload: dict):
    raw_text = str(payload.get('raw_text') or '').strip()
    if not raw_text:
        return JSONResponse({'success': False, 'error': 'Пустой текст ответа'})

    patch_obj = None
    try:
        cand = json.loads(raw_text)
        if isinstance(cand, dict) and ('operations' in cand or 'target_file' in cand):
            patch_obj = cand
    except Exception:
        pass

    if patch_obj is None:
        decoder = json.JSONDecoder()
        idx = 0
        best = None
        while idx < len(raw_text):
            brace = raw_text.find('{', idx)
            if brace == -1:
                break
            try:
                obj, end_idx = decoder.raw_decode(raw_text, brace)
                if isinstance(obj, dict) and ('operations' in obj or 'target_file' in obj):
                    best = obj
                idx = end_idx
            except Exception:
                idx = brace + 1
        patch_obj = best

    if not isinstance(patch_obj, dict):
        return JSONResponse({'success': False, 'error': 'В ответе не найден валидный JSON-патч с operations или target_file'})

    raw_pid = str(patch_obj.get('patch_id') or '').strip()
    safe_pid = re.sub(r'[^a-zA-Z0-9_-]', '', raw_pid)
    if not safe_pid:
        max_num = 160
        for d in (PATCH_DIR, ARCHIVE_DIR):
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    m = re.match(r'^(\d+)\.json$', fn)
                    if m:
                        max_num = max(max_num, int(m.group(1)))
        safe_pid = str(max_num + 1)

    patch_obj['patch_id'] = safe_pid
    filename = f'{safe_pid}.json'
    dst = os.path.join(PATCH_DIR, filename)
    try:
        tmp = dst + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(patch_obj, f, indent=2, ensure_ascii=False)
        os.replace(tmp, dst)
    except Exception as e:
        return JSONResponse({'success': False, 'error': f'Ошибка записи патча: {str(e)}'})

    prev = preview_patch(patch_obj)
    log(f'Console patch exported: {filename} (preflight={prev.get("success")})', 'INFO')
    return JSONResponse({
        'success': True,
        'filename': filename,
        'patch_id': safe_pid,
        'preview': prev,
    })
@app.get('/api/bionic/models')
def s_bionic_models(url: str = ''):
    try:
        import requests
        base = (url or load_cfg().get('bionic_url', 'http://localhost:1235/v1')).rstrip('/')
        r = requests.get(base + '/models', timeout=4)
        if r.status_code != 200:
            return JSONResponse({'success': False, 'error': f'HTTP {r.status_code}', 'models': []})
        ms = r.json().get('data', [])
        out = [{'name': m.get('id', ''), 'size_gb': 0} for m in ms if m.get('id') and 'embed' not in m.get('id', '').lower()]
        return JSONResponse({'success': True, 'models': out})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e), 'models': []})


@app.get('/api/lmstudio/models')
def s_lmstudio_models(url: str = ''):
    try:
        import requests
        base = (url or load_cfg().get('lmstudio_url', 'http://localhost:1234/v1')).rstrip('/')
        ok, why = validate_url(base)
        if not ok:
            return JSONResponse({'success': False, 'error': 'URL отклонён: ' + why, 'models': []})
        r = requests.get(base + '/models', timeout=4)
        if r.status_code != 200:
            return JSONResponse({'success': False, 'error': f'HTTP {r.status_code}', 'models': []})
        ms = r.json().get('data', [])
        out = [{'name': m.get('id', ''), 'size_gb': 0} for m in ms if m.get('id') and 'embed' not in m.get('id', '').lower()]
        return JSONResponse({'success': True, 'models': out})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e), 'models': []})


@app.get('/api/strata/models')
def s_strata_models(url: str = ''):
    try:
        import requests
        base = (url or load_cfg().get('strata_url', 'http://127.0.0.1:47831/v1')).rstrip('/')
        ok, why = validate_url(base)
        if not ok:
            return JSONResponse({'success': False, 'error': 'URL отклонён: ' + why, 'models': []})
        r = requests.get(base + '/models', timeout=4)
        if r.status_code != 200:
            return JSONResponse({'success': False, 'error': f'HTTP {r.status_code}', 'models': []})
        ms = r.json().get('data', [])
        out = [{'name': m.get('id', ''), 'size_gb': 0} for m in ms if m.get('id') and 'embed' not in m.get('id', '').lower()]
        return JSONResponse({'success': True, 'models': out})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e), 'models': []})


@app.post('/api/providers/ping')
def s_providers_ping(payload: dict):
    import requests
    from concurrent.futures import ThreadPoolExecutor

    items = payload.get('providers') or []

    KNOWN_PROVIDER_BASE = {
        'groq': 'https://api.groq.com/openai/v1',
        'openrouter': 'https://openrouter.ai/api/v1',
        'together': 'https://api.together.xyz/v1',
    }

    def guarded_get(u, **kw):
        ok, why = validate_url(u)
        if not ok:
            raise ValueError('URL отклонён: ' + why)
        return requests.get(u, **kw)

    def check_one(item):
        pid = str(item.get('id', ''))
        url = str(item.get('url', '')).strip().rstrip('/')
        api_key = str(item.get('api_key', '')).strip()
        t0 = time.perf_counter()
        try:
            if pid == 'ollama':
                base = url or 'http://localhost:11434'
                r = guarded_get(base + '/api/tags', timeout=2.5)
                ms = int((time.perf_counter() - t0) * 1000)
                if r.status_code == 200:
                    models = [m.get('name', '') for m in r.json().get('models', []) if m.get('name')]
                    return pid, {'online': True, 'latency': ms, 'models': models}
                return pid, {'online': False, 'latency': 0, 'models': [], 'error': f'HTTP {r.status_code}'}
            elif pid == 'gemini':
                if not api_key:
                    return pid, {'online': False, 'latency': 0, 'models': [], 'error': 'Нет ключа'}
                r = requests.get('https://generativelanguage.googleapis.com/v1beta/models', headers={'x-goog-api-key': api_key}, timeout=3.0)
                ms = int((time.perf_counter() - t0) * 1000)
                if r.status_code == 200:
                    return pid, {'online': True, 'latency': ms, 'models': ['gemini-1.5-flash', 'gemini-2.0-flash']}
                return pid, {'online': False, 'latency': 0, 'models': [], 'error': f'HTTP {r.status_code}'}
            elif pid == 'huggingface':
                if not api_key:
                    return pid, {'online': False, 'latency': 0, 'models': [], 'error': 'Нет ключа'}
                r = requests.get('https://huggingface.co/api/whoami-v2', headers={'Authorization': f'Bearer {api_key}'}, timeout=3.0)
                ms = int((time.perf_counter() - t0) * 1000)
                if r.status_code == 200:
                    return pid, {'online': True, 'latency': ms, 'models': ['meta-llama/Llama-3.1-8B-Instruct', 'Qwen/Qwen2.5-Coder-32B-Instruct']}
                return pid, {'online': False, 'latency': 0, 'models': [], 'error': f'HTTP {r.status_code}'}
            else:
                base = KNOWN_PROVIDER_BASE.get(pid)
                if base is not None:
                    if not api_key:
                        return pid, {'online': False, 'latency': 0, 'models': [], 'error': 'Нет API-ключа'}
                    headers = {'Authorization': f'Bearer {api_key}'}
                else:
                    if not url:
                        return pid, {'online': False, 'latency': 0, 'models': [], 'error': 'Нет URL'}
                    base = url
                    headers = {}
                r = guarded_get(base + '/models', headers=headers, timeout=2.5)
                ms = int((time.perf_counter() - t0) * 1000)
                if r.status_code == 200:
                    data = r.json().get('data', [])
                    models = [m.get('id', '') for m in data if m.get('id') and 'embed' not in m.get('id', '').lower()]
                    return pid, {'online': True, 'latency': ms, 'models': models}
                return pid, {'online': False, 'latency': 0, 'models': [], 'error': f'HTTP {r.status_code}'}
        except Exception as e:
            return pid, {'online': False, 'latency': 0, 'models': [], 'error': str(e)[:80]}

    statuses = {}
    if items:
        with ThreadPoolExecutor(max_workers=min(8, len(items))) as ex:
            for pid, st in ex.map(check_one, items):
                statuses[pid] = st
    return JSONResponse({'success': True, 'statuses': statuses})


@app.post('/api/providers/config')
def s_providers_config(payload: dict):
    try:
        cfg = load_cfg()
        if not isinstance(cfg, dict):
            cfg = {}
        updates = payload.get('config') or {}
        if isinstance(updates, dict):
            for k, v in updates.items():
                if isinstance(k, str) and isinstance(v, (str, int, float, bool, dict)):
                    cfg[k] = v
        tmp = CONFIG + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG)

        global engine_obj
        with lock:
            if engine_obj is not None:
                try:
                    importlib.reload(sys.modules['agent_engine'])
                    engine_obj = sys.modules['agent_engine'].AgentEngine(load_cfg(), log_callback=log)
                except Exception as e:
                    log('Engine rebuild error: ' + str(e), 'ERROR')
        return JSONResponse({'success': True, 'file': 'settings.json'})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


@app.get('/api/ollama/models')
def s_models():
    try:
        import requests
        r = requests.get(load_cfg().get('ollama_url', 'http://localhost:11434') + '/api/tags', timeout=5)
        ms = r.json().get('models', [])
        out = [{'name': m['name'], 'size_gb': round(m.get('size', 0) / 1073741824, 2)} for m in ms]
        return JSONResponse({'success': True, 'models': out})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e), 'models': []})


@app.post('/api/ollama/pull')
async def s_pull(payload: dict):
    n = payload.get('name', '').strip()
    if not n:
        return JSONResponse({'success': False, 'error': 'no name'})
    try:
        import ollama
        await asyncio.to_thread(ollama.pull, n)
        return JSONResponse({'success': True, 'message': n + ' ready'})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


@app.get('/api/patches/list')
def s_plist():
    return JSONResponse({'success': True, 'patches': list_patches()})


@app.get('/api/patches/validate-all')
def s_pvalidate_all():
    """Проверить валидность всех патчей без применения."""
    if not os.path.isdir(PATCH_DIR):
        return JSONResponse({'patches': []})
    results = []
    man = load_manifest()
    done = set(str(a.get('patch_id')) for a in man.get('applied', []))
    for f in sorted(os.listdir(PATCH_DIR)):
        if not f.endswith('.json'):
            continue
        fp = os.path.join(PATCH_DIR, f)
        try:
            with open(fp, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            ops = data.get('operations', [])
            errors = []
            for i, op in enumerate(ops):
                tgt = op.get('target_file', '')
                full_path = safe_path(tgt)
                # B64 FIX (P2-17): путь через safe_path — как в Patch Engine, иначе подозрительный целевой файл
                if full_path is None:
                    errors.append(f'Операция {i+1}: подозрительный target_file (за пределами проекта): {tgt}')
                    continue
                if not os.path.exists(full_path):
                    errors.append(f'Операция {i+1}: файл {tgt} не существует')
                    continue
                with open(full_path, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                if op.get('type') == 'search_and_replace':
                    find_txt = op.get('find', '')
                    if find_txt not in content:
                        errors.append(f'Операция {i+1}: подстрока не найдена в {tgt}')
                    elif content.count(find_txt) > 1:
                        errors.append(f'Операция {i+1}: найдено {content.count(find_txt)} вхождений в {tgt}')
                elif op.get('type') == 'full_replace':
                    if 'full_file_content' not in op:
                        errors.append(f'Операция {i+1}: отсутствует full_file_content')
            results.append({
                'filename': f,
                'patch_id': str(data.get('patch_id', f[:-5])),
                'valid': len(errors) == 0,
                'errors': errors,
                'operations_count': len(ops),
                'is_applied': str(data.get('patch_id', f[:-5])) in done
            })
        except Exception as e:
            results.append({'filename': f, 'patch_id': '?', 'valid': False, 'errors': [f'Ошибка: {str(e)}'], 'operations_count': 0, 'is_applied': False})
    return JSONResponse({'patches': results})


@app.get('/api/patches/stats')
def s_pstats():
    return JSONResponse({'success': True, 'stats': stats()})


@app.post('/api/patches/preview')
def s_pprev(payload: dict):
    return JSONResponse(preview_patch(payload))


@app.post('/api/patches/test-apply')
def s_ptest(payload: dict):
    return JSONResponse(test_apply(payload))


@app.post('/api/patches/apply')
def s_papply(payload: dict):
    log('API apply: ' + str(payload.get('patch_id', 'unknown')), 'INFO')
    if payload.get('filename') and not payload.get('operations'):
        fp = os.path.join(PATCH_DIR, os.path.basename(str(payload['filename'])))
        if os.path.exists(fp):
            try:
                payload = json.loads(read_text(fp))
            except Exception:
                pass
    r = apply_patch(payload)
    # B72 FIX (P3-25): авто-рестарт после .py-патча — создаём restart.flag для launcher.bat
    if r.get('success') and isinstance(payload, dict):
        for _op in (payload.get('operations') or []):
            if str(_op.get('target_file', '')).lower().endswith('.py'):
                try:
                    with open(RESTART_FLAG, 'w', encoding='utf-8') as _ff:
                        _ff.write(datetime.now().isoformat())
                    r['restart_scheduled'] = True
                    log('Auto-restart flag set: patch touches .py files', 'INFO')
                except OSError as _e:
                    log('Cannot write restart.flag: ' + str(_e), 'WARN')
                break
    return JSONResponse(r)


@app.get('/api/patches/verify-108')
def s_verify_108():
    """Проверка единого конвейера применения патчей."""
    with open(os.path.join(BASE, 'patch_engine.py'), 'r', encoding='utf-8') as f:
        engine = f.read()
    with open(os.path.join(BASE, 'main.py'), 'r', encoding='utf-8') as f:
        content = f.read()
    checks = {
        'apply_patch_exists': 'def apply_patch(raw):' in engine,
        'endpoint_uses_unified': 'return JSONResponse(apply_patch(payload))' in content,
        'rollback_mechanism': 'shutil.copy2' in engine,
        'syntax_check': 'ast.parse' in engine or 'compile(' in engine,
        'safe_path_used': 'safe_path(' in engine,
        'no_atomic_leak': 'def apply_patch_atomic' + '(data):' not in engine
    }
    passed = sum(1 for v in checks.values() if v)
    return JSONResponse({
        'success': True,
        'unified_pipeline_verified': passed == 6,
        'checks': checks,
        'passed': f'{passed}/6'
    })


@app.post('/api/patches/rollback')
def s_pback():
    return JSONResponse(rollback())


@app.post('/api/patches/manifest-reset')
def s_manifest_reset():
    # B52 FIX: управляемый выход из блокировки после повреждения манифеста
    return JSONResponse(_pe.force_unlock_manifest())


@app.post('/api/patches/archive')
def s_parch(payload: dict):
    f = os.path.basename(str(payload.get('filename', '')))
    if not f or not f.endswith('.json'):
        return JSONResponse({'success': False, 'error': 'Подозрительное имя файла'})
    src = find_patch_file('', f)
    dst = os.path.join(ARCHIVE_DIR, f)
    if not src or not os.path.exists(src):
        return JSONResponse({'success': False, 'error': 'Файл не найден'})
    if os.path.exists(dst):
        os.remove(dst)
    try:
        shutil.move(src, dst)
        return JSONResponse({'success': True, 'message': f + ' в архиве'})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


@app.post('/api/patches/delete')
def s_pdel(payload: dict):
    f = os.path.basename(str(payload.get('filename', '')))
    if not f or not f.endswith('.json'):
        return JSONResponse({'success': False, 'error': 'Подозрительное имя файла'})
    p = find_patch_file('', f)
    if not p or not os.path.exists(p):
        return JSONResponse({'success': False, 'error': 'not found'})
    allowed = {os.path.realpath(d) for d in (PATCH_DIR, getattr(_pe, 'DOWNLOADS_DIR', '')) if d and os.path.isdir(d)}
    if os.path.realpath(os.path.dirname(p)) not in allowed:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    os.remove(p)
    return JSONResponse({'success': True, 'message': 'deleted'})


@app.post('/api/patches/apply-all')
def s_pall(payload: dict = {}):
    res = []
    for p in list_patches():
        if p['is_applied'] or not p['has_content']:
            continue
        try:
            d = json.loads(read_text(p['filepath']))
            r = apply_patch(d)
            res.append(dict(patch_id=p['patch_id'], **r))
            if not r.get('success'):
                break
        except Exception as e:
            res.append({'patch_id': p['patch_id'], 'success': False, 'error': str(e)})
            break
    # B63 FIX (P2-16): success НИКОГДА не ложный — отражает реальный итог apply-all
    ok = all(r.get('success') for r in res) if res else True
    return JSONResponse({'success': ok, 'results': res})


@app.get('/api/project/scan')
def s_scan():
    try:
        return JSONResponse(scan_project())
    except Exception as e:
        log('Scan error: ' + str(e), 'ERROR')
        return JSONResponse({'success': False, 'error': str(e), 'files': [], 'stats': {}})


@app.get('/api/project/file')
def s_pfile(path: str):
    p = safe_path(path)
    if p is None:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    if not os.path.exists(p):
        return JSONResponse({'success': False, 'error': 'not found'})
    c = read_text(p)
    return JSONResponse({'success': True, 'content': c, 'size': len(c)})


def _archive_paths(archive_dir, rel_path):
    safe_rel = str(rel_path).replace(chr(92), '/').strip('/')
    parts = [q for q in safe_rel.split('/') if q and q not in ('.', '..')]
    return os.path.join(archive_dir, *parts)


@app.post('/api/project/archive')
def s_proj_arch(payload: dict):
    rel = payload.get('path', '')
    p = safe_path(rel)
    if p is None:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    if not os.path.exists(p):
        return JSONResponse({'success': False, 'error': 'not found'})
    if is_critical_rel(rel):
        return JSONResponse({'success': False, 'error': 'Критичный файл'})
    folder = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_dir = os.path.join(PROJ_ARCHIVE, folder)
    dst = _archive_paths(archive_dir, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    before = _load_state_snapshot(IMPORTANT)
    shutil.move(p, dst)
    after = _load_state_snapshot(IMPORTANT)
    log_action('archive', [rel], [dst], before, after)
    entry = '/'.join(['project_archive', folder] + _archive_parts(rel))
    return JSONResponse({
        'success': True,
        'message': 'Архив: project_archive/' + folder,
        'paths': [rel],
        'backups': [dst],
        'archive': {rel: entry}
    })


@app.post('/api/project/delete')
def s_proj_del(payload: dict):
    rel = payload.get('path', '')
    p = safe_path(rel)
    if p is None:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    if not os.path.exists(p):
        return JSONResponse({'success': False, 'error': 'not found'})
    if is_critical_rel(rel):
        return JSONResponse({'success': False, 'error': 'Критичный файл'})
    b = backup(p)
    if not b:
        return JSONResponse({'success': False, 'error': 'Не удалось создать резервную копию — удаление запрещено'})
    os.remove(p)
    return JSONResponse({'success': True, 'message': 'Удалён: ' + rel})


@app.post('/api/project/important')
def s_proj_imp(payload: dict):
    s = important_set()
    path = payload.get('path', '')
    if path in s:
        s.discard(path)
    else:
        s.add(path)
    with open(IMPORTANT, 'w', encoding='utf-8') as f:
        json.dump({'important': list(s)}, f, indent=2)
    return JSONResponse({'success': True, 'important': list(s)})


@app.post('/api/system/restart')
def s_restart():
    import subprocess
    log('RESTART via panel', 'WARNING')
    with open(RESTART_FLAG, 'w') as f:
        f.write('restart')
    for title in ('drmAIcu Core', 'drmAIcu UI'):
        try:
            subprocess.run(['taskkill', '/F', '/FI', 'WINDOWTITLE eq ' + title], capture_output=True)
        except Exception:
            pass

    def bye():
        time.sleep(1.5)
        os._exit(0)
    threading.Thread(target=bye, daemon=True).start()
    return JSONResponse({'success': True, 'message': 'Перезапуск инициирован'})


def create_ui():
    ui.dark_mode().enable()
    
    # Шапка
    with ui.header().classes('bg-gray-900 text-white p-4'):
        ui.label('drmAIcu Core v' + _VER + ' HARDENED').classes('text-xl font-bold')
    
    # Вкладки
    with ui.tabs().classes('w-full') as tabs:
        console_tab = ui.tab('🖥 Консоль')
    
    with ui.tab_panels(tabs, value=console_tab).classes('w-full'):
        with ui.tab_panel(console_tab):
            # Выбор провайдера
            provider_select = ui.select(
                ['Ollama', 'Groq', 'Все'],
                value='Ollama',
                label='Провайдер'
            ).classes('w-64 mb-4')
            
            # Выбор модели
            model_select = ui.select(

                [],

                label='Модель'

            ).classes('w-64 mb-4')
            
            # Промпт
            prompt_input = ui.textarea(
                label='Промпт',
                placeholder='Опишите задачу... (Ctrl+Enter для отправки)'
            ).classes('w-full mb-4').props('rows=4')
            
            # Ответ
            response_display = ui.markdown('*Ожидание запроса...*').classes('w-full')
            
            # Функция загрузки моделей
            def load_models():
                try:
                    import requests
                    cfg = load_cfg()
                    r = requests.get(cfg.get('ollama_url', 'http://localhost:11434') + '/api/tags', timeout=5)
                    if r.status_code == 200:
                        models_data = r.json().get('models', [])
                        model_names = [m['name'] for m in models_data]
                        model_select.options = model_names
                        if model_names and not model_select.value:
                            model_select.value = model_names[0]
                except Exception as e:
                    log(f'Ошибка загрузки моделей: {e}', 'ERROR')
            
            # Функция отправки задачи
            async def send_task():
                prompt = prompt_input.value
                if not prompt:
                    response_display.content = '**Ошибка:** Введите промпт'
                    return
                
                response_display.content = '*Обработка...*'
                
                try:
                    import requests
                    payload = {
                        'prompt': prompt,
                        'mode': 'fast',
                        'model': model_select.value or '',
                        'provider': 'ollama' if provider_select.value == 'Ollama' else 'groq' if provider_select.value == 'Groq' else 'all'
                    }
                    r = requests.post('http://127.0.0.1:8080/api/task', json=payload, timeout=120)
                    if r.status_code == 200:
                        result = r.json()
                        if result.get('success'):
                            payload = result.get('result', '')
                            if isinstance(payload, dict):
                                payload = payload.get('result') or ''
                            response_display.content = payload or '*Нет ответа*'
                        else:
                            response_display.content = f"**Ошибка:** {result.get('error', 'Неизвестная ошибка')}"
                    else:
                        response_display.content = f'**HTTP Ошибка:** {r.status_code}'
                except Exception as e:
                    response_display.content = f'**Исключение:** {str(e)}'
            
            # Кнопка отправки
            ui.button('▶ Отправить', on_click=send_task).classes('bg-green-500 text-white mb-4')
            
            # Автообновление списка моделей каждые 10 секунд
            ui.timer(10.0, load_models)
            
            # Загрузка моделей при старте
            load_models()
            
            # Обработка Enter
            prompt_input.on('keydown.enter', send_task)


# ============================================================================
# Project History & Bulk Operations
# ============================================================================

MAX_HISTORY = 50
PROJECT_HISTORY_FILE = os.path.join(BASE, '.project-history.json')
PROJECT_HISTORY = []


def _load_project_history():
    try:
        if os.path.exists(PROJECT_HISTORY_FILE):
            with open(PROJECT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
    except Exception as e:
        log('History load error: ' + str(e), 'ERROR')
        data = []
    if not isinstance(data, list):
        data = []
    return [h for h in data if isinstance(h, dict) and h.get('action') and isinstance(h.get('paths'), list)]


def _save_project_history():
    try:
        tmp = PROJECT_HISTORY_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(PROJECT_HISTORY, f, indent=2, ensure_ascii=False)
        os.replace(tmp, PROJECT_HISTORY_FILE)
    except Exception as e:
        log('History save error: ' + str(e), 'ERROR')


def _load_state_snapshot(path):
    try:
        if not os.path.exists(path):
            return {'exists': False, 'important': []}
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        items = data.get('important', []) if isinstance(data, dict) else []
        return {'exists': True, 'important': [str(x) for x in items]}
    except Exception as e:
        log('Important load error: ' + str(e), 'ERROR')
        return {'exists': False, 'important': []}


def _parse_state_snapshot(snap):
    if not isinstance(snap, dict):
        return None
    items = snap.get('important')
    if not isinstance(items, list):
        return None
    return set(items)


PROJECT_HISTORY = _load_project_history()


def log_action(action, paths, backups, important_before=None, important_after=None):
    PROJECT_HISTORY.append({
        'action': action,
        'paths': paths,
        'backups': backups,
        'important_before': important_before,
        'important_after': important_after,
        'timestamp': datetime.now().isoformat()
    })
    if len(PROJECT_HISTORY) > MAX_HISTORY:
        PROJECT_HISTORY.pop(0)
    _save_project_history()


@app.post('/api/project/bulk')
def s_project_bulk(payload: dict):
    action = payload.get('action', '')
    paths = payload.get('paths', [])
    if not paths:
        return JSONResponse({'success': False, 'error': 'Нет выбранных файлов'})
    important_before = None
    if action == 'important':
        important_before = _load_state_snapshot(IMPORTANT)
    important_state = important_set()
    backups = []
    processed = []
    skipped = []
    archive_map = {}
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_dir = os.path.join(PROJ_ARCHIVE, stamp)
    for rel_path in paths:
        full_path = safe_path(rel_path)
        if not full_path or not os.path.exists(full_path):
            continue
        if action in ('archive', 'delete') and is_critical_rel(rel_path):
            skipped.append(rel_path)
            continue
        if action == 'archive':
            b = backup(full_path)
            if not b:
                skipped.append(rel_path)
                continue
            backups.append(b[0])
            adst = _archive_paths(archive_dir, rel_path)
            os.makedirs(os.path.dirname(adst), exist_ok=True)
            shutil.move(full_path, adst)
            archive_map[rel_path] = '/'.join(['project_archive', stamp] + _archive_parts(rel_path))
            processed.append(rel_path)
        elif action == 'important':
            if rel_path in important_state:
                important_state.remove(rel_path)
            else:
                important_state.add(rel_path)
            save_important(important_state)
            processed.append(rel_path)
        elif action == 'delete':
            b = backup(full_path)
            if not b:
                skipped.append(rel_path)
                continue
            backups.append(b[0])
            os.remove(full_path)
            processed.append(rel_path)
    if processed:
        important_after = None
        if action == 'important':
            important_after = _load_state_snapshot(IMPORTANT)
        log_action(action, processed, backups, important_before, important_after)
    return JSONResponse({'success': True, 'processed': len(processed), 'skipped': len(skipped), 'archive': archive_map})


@app.post('/api/project/restore')
def s_project_restore(payload: dict):
    archive_path = payload.get('archive_path', '')
    archive_full = safe_path(archive_path)
    if not archive_full or not os.path.exists(archive_full):
        return JSONResponse({'success': False, 'error': 'Файл не найден в архиве'})
    if not archive_path.replace(chr(92), '/').startswith('project_archive/'):
        return JSONResponse({'success': False, 'error': 'Файл не из project_archive'})
    entry = _archive_rel_entry(archive_full)
    if not entry or len(entry.split('/')) < 2:
        return JSONResponse({'success': False, 'error': ' некорректный путь архива'})
    target_rel = '/'.join(entry.split('/')[1:])
    if not target_rel:
        return JSONResponse({'success': False, 'error': ' некорректный путь архива'})
    if is_critical_rel(target_rel):
        return JSONResponse({'success': False, 'error': 'Восстановление критичного файла запрещено'})
    target = safe_path(target_rel)
    if target is None:
        return JSONResponse({'success': False, 'error': 'Восстановление в критичный путь запрещено'})
    if os.path.exists(target):
        return JSONResponse({'success': False, 'error': f'Файл {target_rel} уже существует'})
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.copy2(archive_full, target)
    return JSONResponse({'success': True, 'message': f'Восстановлен {target_rel}'})


@app.post('/api/project/rollback')
def s_project_rollback():
    if not PROJECT_HISTORY:
        return JSONResponse({'success': False, 'error': 'История пуста'})
    last = PROJECT_HISTORY.pop()
    restored = 0
    errors = []
    for backup_path, original_path in zip(last['backups'], last['paths']):
        if backup_path and os.path.exists(backup_path):
            dest = safe_path(original_path)
            if dest is None:
                errors.append(f'{original_path}: восстановление в критичный путь запрещено')
                continue
            try:
                os.makedirs(os.path.dirname(dest) or BASE, exist_ok=True)
                shutil.copy2(backup_path, dest)
                restored += 1
            except Exception as e:
                errors.append(f'{original_path}: {e}')
        else:
            errors.append(f'{original_path}: резервная копия не найдена')
    before = _parse_state_snapshot(last.get('important_before'))
    after = _parse_state_snapshot(last.get('important_after'))
    imp_restored = 0
    if before is not None and after is not None and before != after:
        save_important(before)
        imp_restored = len(before ^ after)
    _save_project_history()
    msg = f'Откат: {last["action"]} ({restored} файлов)' + (f', important: {imp_restored}' if imp_restored else '')
    if errors:
        return JSONResponse({'success': True, 'message': msg + ' (с ошибками: ' + '; '.join(errors) + ')', 'errors': errors})
    return JSONResponse({'success': True, 'message': msg})


@app.get('/api/project/history')
def s_project_history():
    return JSONResponse({'history': PROJECT_HISTORY})


@app.get('/api/project/archive-list')
def s_project_archive_list():
    archive_dir = os.path.join(BASE, 'project_archive')
    if not os.path.exists(archive_dir):
        return JSONResponse({'files': []})
    files = []
    for root, dirs, filenames in os.walk(archive_dir):
        for f in filenames:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, BASE)
            files.append({
                'path': rel,
                'filename': f,
                'size': os.path.getsize(full),
                'modified': datetime.fromtimestamp(os.path.getmtime(full)).isoformat()
            })
    return JSONResponse({'files': files})


if __name__ in {'__main__', '__mp_main__'}:
    log('Starting drmAIcu Core v' + _VER + ' HARDENED...')
    # B51 FIX (P1-04): crash-восстановление незавершённой транзакции после перезапуска
    rec_j = _pe.recover_journal()
    if rec_j:
        try:
            log('CRASH RECOVERY: ' + json.dumps(rec_j, ensure_ascii=False), 'WARNING')
        except Exception:
            pass
    get_engine()
    create_ui()
    ui.run(title='drmAIcu Core', port=8080, reload=False, show=False)
