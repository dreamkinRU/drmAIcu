# main.py v3.3.0 DISK-READER
from nicegui import ui, app
import json, os, sys, re, ast, shutil, hashlib, threading, importlib, traceback, asyncio, time
from datetime import datetime
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

BASE = os.path.dirname(os.path.abspath(__file__))
PATCH_DIR = os.path.join(BASE, 'patch')
ARCHIVE_DIR = os.path.join(PATCH_DIR, 'archive')
BACKUP_DIR = os.path.join(BASE, 'backups')
MANIFEST = os.path.join(BASE, 'patch_manifest.json')
CONFIG = os.path.join(BASE, 'settings.json')
ENGINE = os.path.join(BASE, 'agent_engine.py')
RESTART_FLAG = os.path.join(BASE, 'restart.flag')
PROJ_ARCHIVE = os.path.join(BASE, 'project_archive')
IMPORTANT = os.path.join(BASE, '.project-important.json')
LOG = []
SKIP = {'node_modules', '.git', '__pycache__', '.venv', 'venv', '.vscode', '.idea'}
CRIT_FILES = {'main.py', 'agent_engine.py', 'settings.json', 'launcher.bat', 'package.json', 'package-lock.json', 'vite.config.js', 'tsconfig.json', 'index.html', 'README.md'}
CRIT_DIRS = ('src/', 'patch/', 'backups/', 'docs/')

for d in (PATCH_DIR, ARCHIVE_DIR, BACKUP_DIR, PROJ_ARCHIVE):
    os.makedirs(d, exist_ok=True)


def log(msg, lvl='INFO'):
    t = datetime.now().strftime('%H:%M:%S')
    LOG.append({'time': t, 'level': lvl.lower(), 'message': str(msg), 'source': 'Core'})
    if len(LOG) > 500:
        LOG.pop(0)
    print('[' + t + '] [' + lvl + '] ' + str(msg))


def read_text(path):
    for enc in ('utf-8', 'utf-8-sig', 'cp1251', 'latin-1'):
        try:
            with open(path, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception:
            return ''
    return ''


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


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


def load_manifest():
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'applied': [], 'history': [], 'rollbacks': []}


def save_manifest(m):
    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(m, f, indent=2, ensure_ascii=False)


def backup(path):
    out = []
    if not os.path.exists(path):
        return out
    name = os.path.basename(path)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    for suffix in ('_' + ts + '.bak', '_' + ts + '_verified.bak', '_LATEST.bak'):
        dst = os.path.join(BACKUP_DIR, name + suffix)
        try:
            shutil.copy2(path, dst)
            out.append(dst)
        except Exception:
            pass
    return out


def apply_diff(content, diff):
    lines = content.split('\n')
    dl = diff.split('\n')
    i = 0
    while i < len(dl):
        if dl[i].startswith('@@'):
            m = re.match(r'@@ -(\d+)', dl[i])
            if not m:
                i += 1
                continue
            start = int(m.group(1)) - 1
            j = i + 1
            while j < len(dl) and not dl[j].startswith('@@'):
                j += 1
            block = []
            pos = start
            for k in range(i + 1, j):
                s = dl[k]
                if s.startswith('--- ') or s.startswith('+++ '):
                    continue
                if s.startswith(' '):
                    if pos < len(lines):
                        block.append(lines[pos])
                    pos += 1
                elif s.startswith('-'):
                    pos += 1
                elif s.startswith('+'):
                    block.append(s[1:])
                elif s == '':
                    if pos < len(lines):
                        block.append(lines[pos])
                    pos += 1
            lines = lines[:start] + block + lines[pos:]
            i = j
        else:
            i += 1
    return '\n'.join(lines)


def validate(name, code):
    ext = os.path.splitext(name)[1].lower()
    if ext == '.py':
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, 'Python line ' + str(e.lineno) + ': ' + str(e.msg)
    elif ext == '.json':
        try:
            json.loads(code)
        except Exception as e:
            return False, 'JSON: ' + str(e)
    return True, None


def find_patch_file(pid, fname=''):
    if fname:
        p = os.path.join(PATCH_DIR, fname)
        if os.path.exists(p):
            return p
    if not pid:
        return None
    cands = [pid + '.json', 'patch_' + pid + '.json']
    for c in cands:
        p = os.path.join(PATCH_DIR, c)
        if os.path.exists(p):
            return p
    try:
        for f in os.listdir(PATCH_DIR):
            if not f.endswith('.json'):
                continue
            p = os.path.join(PATCH_DIR, f)
            try:
                d = json.loads(read_text(p))
                if str(d.get('patch_id', '')) == str(pid):
                    return p
            except Exception:
                continue
    except Exception:
        pass
    return None


def resolve(data):
    pid = str(data.get('patch_id', ''))
    fname = data.get('filename', '')
    has_body = bool(data.get('diff')) or bool(data.get('full_file_content'))
    if not has_body:
        p = find_patch_file(pid, fname)
        if p:
            try:
                full = json.loads(read_text(p))
                log('Loaded patch body from disk: ' + os.path.basename(p))
                return full
            except Exception as e:
                log('Read patch failed: ' + str(e), 'ERROR')
    return data


def list_patches():
    out = []
    man = load_manifest()
    done = set()
    for a in man.get('applied', []):
        done.add(str(a.get('patch_id')))
    if not os.path.exists(PATCH_DIR):
        return out
    for f in sorted(os.listdir(PATCH_DIR)):
        if not f.endswith('.json') or f.startswith('.'):
            continue
        p = os.path.join(PATCH_DIR, f)
        if not os.path.isfile(p):
            continue
        try:
            d = json.loads(read_text(p))
            pid = str(d.get('patch_id', f[:-5]))
            pt = d.get('type', '')
            if not pt:
                pt = 'unified_diff' if d.get('diff') else 'full_replace'
            body = d.get('full_file_content', '') if pt == 'full_replace' else d.get('diff', '')
            tgt = d.get('target_file', 'unknown')
            out.append({'filename': f, 'filepath': p, 'patch_id': pid, 'patch_type': pt,
                        'target_file': tgt, 'description': d.get('description', ''),
                        'author': d.get('author', '?'), 'created_at': d.get('created_at', ''),
                        'is_applied': pid in done,
                        'file_exists': os.path.exists(os.path.join(BASE, tgt)),
                        'content_length': len(body), 'has_content': bool(body),
                        'full_file_content': d.get('full_file_content', ''), 'diff': d.get('diff', '')})
        except Exception as e:
            out.append({'filename': f, 'filepath': p, 'patch_id': f[:-5], 'patch_type': 'error',
                        'target_file': 'error', 'description': 'Bad JSON: ' + str(e)[:80],
                        'author': 'ERR', 'created_at': '', 'is_applied': False, 'file_exists': False,
                        'content_length': 0, 'has_content': False, 'error': str(e),
                        'full_file_content': '', 'diff': ''})
    return out


def compute_new(data):
    tgt = data.get('target_file', '')
    if not tgt:
        return None, None, 'Нет target_file'
    path = os.path.join(BASE, tgt)
    pt = data.get('type', '')
    if not pt:
        pt = 'unified_diff' if data.get('diff') else 'full_replace'
    if pt == 'unified_diff':
        d = data.get('diff', '')
        if not d:
            return None, None, 'Нет diff'
        if not os.path.exists(path):
            return None, None, 'Файл не существует: ' + tgt
        new = apply_diff(read_text(path), d)
    else:
        new = data.get('full_file_content', '')
        if not new:
            return None, None, 'Нет full_file_content'
    ok, err = validate(tgt, new)
    if not ok:
        return None, None, 'Валидация: ' + err
    return path, new, None


def preview_patch(raw):
    data = resolve(raw)
    path, new, err = compute_new(data)
    if err:
        return {'success': False, 'error': err}
    old = read_text(path) if os.path.exists(path) else ''
    return {'success': True, 'valid': True, 'target_file': data.get('target_file'),
            'old_size': len(old), 'new_size': len(new),
            'old_lines': len(old.split('\n')), 'new_lines': len(new.split('\n')),
            'message': 'OK: ' + str(len(old.split('\n'))) + ' -> ' + str(len(new.split('\n'))) + ' строк'}


def apply_patch(raw):
    data = resolve(raw)
    pid = str(data.get('patch_id', 'unknown'))
    tgt = data.get('target_file', '')
    path, new, err = compute_new(data)
    if err:
        log('Patch ' + pid + ' rejected: ' + err, 'ERROR')
        return {'success': False, 'error': err}
    backs = backup(path)
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(new)
        os.replace(tmp, path)
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        return {'success': False, 'error': 'Запись: ' + str(e)}
    man = load_manifest()
    man['applied'].append({'patch_id': pid, 'target_file': tgt,
                           'applied_at': datetime.now().isoformat(),
                           'checksum': sha(new), 'backups': backs})
    man['history'].append({'action': 'apply', 'patch_id': pid, 'target_file': tgt,
                           'timestamp': datetime.now().isoformat()})
    save_manifest(man)
    log('Patch ' + pid + ' applied to ' + tgt, 'SUCCESS')
    return {'success': True, 'message': 'Патч ' + pid + ' применён к ' + tgt, 'backups': backs}


def rollback():
    man = load_manifest()
    if not man.get('applied'):
        return {'success': False, 'error': 'Нет патчей для отката'}
    last = man['applied'][-1]
    tgt = last['target_file']
    b = os.path.join(BACKUP_DIR, os.path.basename(tgt) + '_LATEST.bak')
    if not os.path.exists(b):
        return {'success': False, 'error': 'Бэкап не найден'}
    shutil.copy2(b, os.path.join(BASE, tgt))
    man['applied'].pop()
    man['rollbacks'].append(last)
    save_manifest(man)
    return {'success': True, 'message': 'Откат ' + str(last['patch_id'])}


def stats():
    ps = list_patches()
    man = load_manifest()
    ap = len([p for p in ps if p['is_applied']])
    return {'total': len(ps), 'applied': ap, 'pending': len(ps) - ap,
            'errors': len([p for p in ps if p.get('error')]),
            'history_count': len(man.get('history', [])),
            'rollbacks_count': len(man.get('rollbacks', [])),
            'backups_count': len(os.listdir(BACKUP_DIR))}


def important_set():
    if os.path.exists(IMPORTANT):
        try:
            with open(IMPORTANT, 'r', encoding='utf-8') as f:
                return set(json.load(f).get('important', []))
        except Exception:
            pass
    return set()


def category(name, rel, size):
    if name in CRIT_FILES or rel.replace('\\', '/').startswith(CRIT_DIRS):
        return 'critical'
    if name.endswith('.bak'):
        return 'backup'
    if size == 0 or name.endswith(('.tmp', '.pyc')):
        return 'trash'
    if name in ('.DS_Store', 'Thumbs.db', 'desktop.ini'):
        return 'trash'
    if name.endswith('.md'):
        return 'docs'
    if name.endswith(('.py', '.tsx', '.ts', '.jsx', '.js')):
        return 'code'
    if name.endswith(('.json', '.yaml', '.yml', '.ini', '.cfg')):
        return 'config'
    if name.endswith(('.bat', '.cmd', '.sh')):
        return 'scripts'
    if name.endswith(('.html', '.css')):
        return 'web'
    if name.endswith(('.log', '.txt')):
        return 'logs'
    return 'other'


ICONS = {'.py': 'PY', '.tsx': 'TSX', '.ts': 'TS', '.js': 'JS', '.json': 'CFG',
         '.md': 'MD', '.bat': 'BAT', '.html': 'HTML', '.css': 'CSS', '.bak': 'BAK'}


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
                st = os.stat(p)
                h = ''
                try:
                    with open(p, 'rb') as f:
                        h = hashlib.md5(f.read()).hexdigest()
                except Exception:
                    pass
                cat = category(n, rel, st.st_size)
                files.append({'path': rel, 'filename': n, 'size': st.st_size,
                              'size_human': human(st.st_size),
                              'modified': datetime.fromtimestamp(st.st_mtime).isoformat(),
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
    total = sum(f['size'] for f in files)
    st = {'total': len(files), 'total_size': total, 'total_size_human': human(total),
          'by_category': {}, 'by_extension': {},
          'duplicates_count': len([f for f in files if f['is_duplicate']]),
          'duplicates_groups': len([v for v in hashes.values() if len(v) > 1]),
          'critical_count': len([f for f in files if f['is_critical']]),
          'important_count': len([f for f in files if f['is_important']]),
          'trash_count': len([f for f in files if f['category'] == 'trash']),
          'backup_count': len([f for f in files if f['category'] == 'backup'])}
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
                         'version': '3.3.0 DISK-READER',
                         'providers': {'groq': bool(cfg.get('groq_api_key')),
                                       'openrouter': bool(cfg.get('openrouter_api_key')),
                                       'gemini': bool(cfg.get('gemini_api_key'))}})


@app.get('/api/logs')
def s_logs():
    return JSONResponse({'logs': LOG[-100:]})


@app.get('/api/md/{name:path}')
def s_md_get(name):
    p = os.path.join(BASE, name.replace('..', ''))
    if os.path.exists(p):
        return JSONResponse({'content': read_text(p), 'name': name})
    return JSONResponse({'content': '', 'name': name, 'error': 'not found'})


@app.post('/api/md/{name:path}')
def s_md_post(name, payload: dict):
    p = os.path.join(BASE, name.replace('..', ''))
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
        r = await e.run_task(payload.get('prompt', ''), mode=payload.get('mode', 'full'))
        return JSONResponse({'success': True, 'result': r})
    except Exception as ex:
        return JSONResponse({'success': False, 'error': str(ex)})


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


@app.get('/api/patches/stats')
def s_pstats():
    return JSONResponse({'success': True, 'stats': stats()})


@app.post('/api/patches/preview')
def s_pprev(payload: dict):
    return JSONResponse(preview_patch(payload))


@app.post('/api/patches/apply')
def s_papply(payload: dict):
    return JSONResponse(apply_patch(payload))


@app.post('/api/patches/rollback')
def s_pback():
    return JSONResponse(rollback())


@app.post('/api/patches/archive')
def s_parch(payload: dict):
    f = payload.get('filename', '')
    src = os.path.join(PATCH_DIR, f)
    dst = os.path.join(ARCHIVE_DIR, f)
    if not os.path.exists(src):
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
    p = os.path.join(PATCH_DIR, payload.get('filename', ''))
    if os.path.exists(p):
        os.remove(p)
        return JSONResponse({'success': True, 'message': 'deleted'})
    return JSONResponse({'success': False, 'error': 'not found'})


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
    return JSONResponse(scan_project())


@app.get('/api/project/file')
def s_pfile(path: str):
    p = os.path.join(BASE, path)
    if not os.path.exists(p):
        return JSONResponse({'success': False, 'error': 'not found'})
    c = read_text(p)
    return JSONResponse({'success': True, 'content': c, 'size': len(c)})


@app.post('/api/project/archive')
def s_proj_arch(payload: dict):
    rel = payload.get('path', '')
    p = os.path.join(BASE, rel)
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
    p = os.path.join(BASE, rel)
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
    with ui.header().classes('bg-gray-900 text-white p-4'):
        ui.label('drmAIcu Core v3.3.0 DISK-READER').classes('text-xl font-bold')


if __name__ in {'__main__', '__mp_main__'}:
    log('Starting drmAIcu Core v3.3.0 DISK-READER...')
    get_engine()
    create_ui()
    ui.run(title='drmAIcu Core', port=8080, reload=False, show=False)
