# main.py v3.6.0 MULTI-ATOMIC HARDENED (UI + API; engine lives in patch_engine.py)
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
CRIT_FILES = {'main.py', 'patch_engine.py', 'agent_engine.py', 'settings.json', 'launcher.bat', 'package.json', 'package-lock.json', 'vite.config.js', 'tsconfig.json', 'index.html', 'README.md'}
CRIT_DIRS = ('src/', 'patch/', 'docs/', 'tests/')

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


def classify_file(name, rel, size):
    r = rel.replace('\\', '/').lower()
    n = name.lower()
    # Критическое ядро
    if name in CRIT_FILES or r.startswith(CRIT_DIRS):
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
                         'version': '3.6.0 MULTI-ATOMIC HARDENED',
                         'providers': {'groq': bool(cfg.get('groq_api_key')),
                                       'openrouter': bool(cfg.get('openrouter_api_key')),
                                       'gemini': bool(cfg.get('gemini_api_key'))}})


@app.get('/api/logs')
def s_logs():
    return JSONResponse({'logs': LOG[-100:]})


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
            sub = f'{base_key}\{i:04d}'
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
    p = safe_path(name)
    if p is None:
        return JSONResponse({'content': '', 'name': name, 'error': 'forbidden'})
    if os.path.exists(p):
        return JSONResponse({'content': read_text(p), 'name': name})
    return JSONResponse({'content': '', 'name': name, 'error': 'not found'})


@app.post('/api/md/{name:path}')
def s_md_post(name, payload: dict):
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
        return JSONResponse({'success': True, 'result': r})
    except Exception as ex:
        return JSONResponse({'success': False, 'error': str(ex)})


@app.post('/api/task/stream')
async def s_task_stream(payload: dict):
    e = get_engine()
    if not e:
        return JSONResponse({'success': False, 'error': 'Engine not loaded'}, status_code=503)
    prompt = payload.get('prompt', '')
    mode = payload.get('mode', 'fast')
    model = payload.get('model', '')
    provider = payload.get('provider', 'ollama')

    async def event_gen():
        try:
            async for ev in e.stream_task(prompt, mode=mode, model=model, provider=provider):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            return
        except Exception as ex:
            yield f"data: {json.dumps({'type': 'error', 'error': str(ex)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type='text/event-stream')
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

    def check_one(item):
        pid = str(item.get('id', ''))
        url = str(item.get('url', '')).strip().rstrip('/')
        api_key = str(item.get('api_key', '')).strip()
        t0 = time.perf_counter()
        try:
            if pid == 'ollama':
                base = url or 'http://localhost:11434'
                r = requests.get(base + '/api/tags', timeout=2.5)
                ms = int((time.perf_counter() - t0) * 1000)
                if r.status_code == 200:
                    models = [m.get('name', '') for m in r.json().get('models', []) if m.get('name')]
                    return pid, {'online': True, 'latency': ms, 'models': models}
                return pid, {'online': False, 'latency': 0, 'models': [], 'error': f'HTTP {r.status_code}'}
            elif pid == 'gemini':
                if not api_key:
                    return pid, {'online': False, 'latency': 0, 'models': [], 'error': 'Нет ключа'}
                r = requests.get(f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}', timeout=3.0)
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
                if not url:
                    return pid, {'online': False, 'latency': 0, 'models': [], 'error': 'Нет URL'}
                if pid in ('groq', 'openrouter', 'together') and not api_key:
                    return pid, {'online': False, 'latency': 0, 'models': [], 'error': 'Нет API-ключа'}
                headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
                r = requests.get(url + '/models', headers=headers, timeout=2.5)
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
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        cfg = load_cfg() if 'load_cfg' in globals() else {}
        if not isinstance(cfg, dict):
            cfg = {}
        updates = payload.get('config') or {}
        if isinstance(updates, dict):
            for k, v in updates.items():
                if isinstance(k, str) and isinstance(v, (str, int, float, bool)):
                    cfg[k] = v
        tmp = cfg_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(tmp, cfg_path)
        return JSONResponse({'success': True})
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
                full_path = os.path.join(BASE, tgt)
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
    return JSONResponse(apply_patch(payload))


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
    return JSONResponse({'success': True, 'results': res})


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


@app.post('/api/project/archive')
def s_proj_arch(payload: dict):
    rel = payload.get('path', '')
    p = safe_path(rel)
    if p is None:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    if not os.path.exists(p):
        return JSONResponse({'success': False, 'error': 'not found'})
    if os.path.basename(rel) in CRIT_FILES or rel.replace('\\', '/').startswith(CRIT_DIRS):
        return JSONResponse({'success': False, 'error': 'Критичный файл'})
    folder = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(PROJ_ARCHIVE, folder, os.path.basename(rel))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(p, dst)
    return JSONResponse({'success': True, 'message': 'Архив: project_archive/' + folder})


@app.post('/api/project/delete')
def s_proj_del(payload: dict):
    rel = payload.get('path', '')
    p = safe_path(rel)
    if p is None:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    if not os.path.exists(p):
        return JSONResponse({'success': False, 'error': 'not found'})
    if os.path.basename(rel) in CRIT_FILES or rel.replace('\\', '/').startswith(CRIT_DIRS):
        return JSONResponse({'success': False, 'error': 'Критичный файл'})
    backup(p)
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
        ui.label('drmAIcu Core v3.6.0 MULTI-ATOMIC HARDENED').classes('text-xl font-bold')
    
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
                            response_display.content = result.get('result', '*Нет ответа*')
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

PROJECT_HISTORY = []
MAX_HISTORY = 50


def log_action(action, paths, backups):
    PROJECT_HISTORY.append({
        'action': action,
        'paths': paths,
        'backups': backups,
        'timestamp': datetime.now().isoformat()
    })
    if len(PROJECT_HISTORY) > MAX_HISTORY:
        PROJECT_HISTORY.pop(0)


@app.post('/api/project/bulk')
def s_project_bulk(payload: dict):
    action = payload.get('action', '')
    paths = payload.get('paths', [])
    if not paths:
        return JSONResponse({'success': False, 'error': 'Нет выбранных файлов'})
    backups = []
    processed = []
    for rel_path in paths:
        full_path = safe_path(rel_path)
        if not full_path or not os.path.exists(full_path):
            continue
        if action == 'archive':
            b = backup(full_path)
            if b:
                backups.append(b[0])
            else:
                backups.append('')
            archive_dir = os.path.join(BASE, 'project_archive', datetime.now().strftime('%Y%m%d_%H%M%S'))
            os.makedirs(archive_dir, exist_ok=True)
            shutil.move(full_path, os.path.join(archive_dir, os.path.basename(full_path)))
            processed.append(rel_path)
        elif action == 'important':
            important = load_important()
            if rel_path in important:
                important.remove(rel_path)
            else:
                important.add(rel_path)
            save_important(important)
            processed.append(rel_path)
        elif action == 'delete':
            b = backup(full_path)
            if b:
                backups.append(b[0])
            else:
                backups.append('')
            os.remove(full_path)
            processed.append(rel_path)
    if processed:
        log_action(action, processed, backups)
    return JSONResponse({'success': True, 'processed': len(processed)})


@app.post('/api/project/restore')
def s_project_restore(payload: dict):
    archive_path = payload.get('archive_path', '')
    archive_full = safe_path(archive_path)
    if not archive_full or not os.path.exists(archive_full):
        return JSONResponse({'success': False, 'error': 'Файл не найден в архиве'})
    filename = os.path.basename(archive_full)
    target = os.path.join(BASE, filename)
    if os.path.exists(target):
        return JSONResponse({'success': False, 'error': f'Файл {filename} уже существует'})
    shutil.copy2(archive_full, target)
    return JSONResponse({'success': True, 'message': f'Восстановлен {filename}'})


@app.post('/api/project/rollback')
def s_project_rollback():
    if not PROJECT_HISTORY:
        return JSONResponse({'success': False, 'error': 'История пуста'})
    last = PROJECT_HISTORY.pop()
    restored = 0
    for backup_path, original_path in zip(last['backups'], last['paths']):
        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, original_path)
            restored += 1
    return JSONResponse({'success': True, 'message': f'Откат: {last["action"]} ({restored} файлов)'})


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
    log('Starting drmAIcu Core v3.6.0 MULTI-ATOMIC HARDENED...')
    get_engine()
    create_ui()
    ui.run(title='drmAIcu Core', port=8080, reload=False, show=False)
