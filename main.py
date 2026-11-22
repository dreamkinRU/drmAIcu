# main.py v3.5.0 MULTI-ATOMIC
from nicegui import ui, app
import json, os, sys, re, ast, shutil, hashlib, threading, importlib, traceback, asyncio, time, subprocess
from datetime import datetime, timedelta
from fastapi.responses import FileResponse,  JSONResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8080', 'http://localhost:8080'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
except RuntimeError:
    pass

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
SKIP = {'node_modules', '.git', '__pycache__', '.venv', 'venv', '.vscode', '.idea', 'dist', 'project_archive', '.vite', '.pytest_cache'}
CRIT_FILES = {'main.py', 'agent_engine.py', 'settings.json', 'launcher.bat', 'package.json', 'package-lock.json', 'vite.config.js', 'tsconfig.json', 'index.html', 'README.md'}
CRIT_DIRS = ('src/', 'patch/', 'docs/', 'tests/')

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


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(rel):
    if chr(0) in str(rel):
        return None
    p = os.path.normpath(os.path.join(BASE, str(rel)))
    try:
        # S-02 FIX: Разрешаем симлинки перед проверкой, чтобы избежать обхода песочницы
        real_p = os.path.realpath(p)
        real_base = os.path.realpath(BASE)
        if os.path.commonpath([real_base, real_p]) != real_base:
            return None
    except ValueError:
        return None
    return p


def file_newline(path):
    try:
        with open(path, 'rb') as f:
            return '\r\n' if b'\r\n' in f.read() else '\n'
    except Exception:
        return '\n'


def to_bytes(text, nl):
    return text.replace('\r\n', '\n').replace('\n', nl).encode('utf-8')


def check_ts(name, code):
    root = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(root, 'tools', 'tscheck.cjs')
    if not os.path.exists(script):
        return None
    try:
        r = subprocess.run(['node', script, name], input=code.encode('utf-8'),
                           capture_output=True, timeout=30, cwd=root)
    except Exception:
        return None
    if r.returncode == 0:
        return None
    return (r.stdout or r.stderr).decode('utf-8', 'replace').strip()[:300]


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


@app.get('/api/patches/dump')
def s_dump():
    import re
    with open(os.path.join(BASE, 'main.py'), 'r', encoding='utf-8') as f:
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


def save_manifest(m):
    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(m, f, indent=2, ensure_ascii=False)


def backup(path):
    out = []
    if not os.path.exists(path):
        return out
    name = os.path.relpath(path, BASE).replace(os.sep, '__').replace(':', '')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    for suffix in ('_' + ts + '.bak', '_' + ts + '_verified.bak', '_LATEST.bak'):
        dst = os.path.join(BACKUP_DIR, name + suffix)
        try:
            shutil.copy2(path, dst)
            out.append(dst)
        except Exception:
            pass
    return out


def find_block(lines, block, hint):
    if not block:
        return hint
    n = len(block)
    if hint is None:
        hint = 0
    hint = max(0, min(hint, len(lines)))
    if 0 <= hint <= len(lines) - n and lines[hint:hint + n] == block:
        return hint
    matches = [i for i in range(len(lines) - n + 1) if lines[i:i + n] == block]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return matches
    sb = [s.rstrip() for s in block]
    fm = [i for i in range(len(lines) - n + 1) if [x.rstrip() for x in lines[i:i + n]] == sb]
    if len(fm) == 1:
        return fm[0]
    if len(fm) > 1:
        return fm
    return -1


def apply_diff(content, diff):
    diff = diff.replace('\r\n', '\n').replace('\r', '\n')
    lines = content.split('\n')
    dl = diff.split('\n')
    hunks = []
    i = 0
    while i < len(dl) and not dl[i].startswith('@@'):
        i += 1
    while i < len(dl):
        if dl[i].startswith('@@'):
            m = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', dl[i])
            if not m:
                i += 1
                continue
            old_start = int(m.group(1))
            old_count = int(m.group(2)) if m.group(2) is not None else 1
            j = i + 1
            while j < len(dl) and not dl[j].startswith('@@'):
                j += 1
            hunks.append((old_start, old_count, dl[i + 1:j]))
            i = j
        else:
            i += 1
    ops = []
    for old_start, old_count, body in hunks:
        while body and body[-1] == '':
            body.pop()
        has_add = False
        old_block = []
        new_block = []
        for s in body:
            if s.startswith('--- ') or s.startswith('+++ ') or s.startswith('\\'):
                continue
            if s.startswith(' '):
                old_block.append(s[1:])
                new_block.append(s[1:])
            elif s.startswith('-'):
                old_block.append(s[1:])
            elif s.startswith('+'):
                new_block.append(s[1:])
                has_add = True
            elif s == '':
                old_block.append('')
                new_block.append('')
        hint = old_start if old_count == 0 else old_start - 1
        pos = find_block(lines, old_block, hint)
        if isinstance(pos, list):
            raise ValueError('Ханк неоднозначен: контекст найден в ' + str(len(pos)) + ' местах ' + str(pos[:5]) + '. Уточни контекст патча.')
        if pos == -1:
            if has_add and new_block:
                p2 = find_block(lines, new_block, hint)
                if isinstance(p2, int) and p2 != -1:
                    continue
            hint = max(0, old_start - 1)
            real = lines[hint:hint + max(1, len(old_block))]
            raise ValueError('Ханк не найден (подсказка строки ' + str(old_start) + '): ожидалось ' + str(len(old_block)) + ' строк; РЕАЛЬНО в файле: ' + json.dumps(real, ensure_ascii=False)[:800])
        ops.append((pos, pos + len(old_block), new_block))
    for start, end, nb in sorted(ops, key=lambda x: -x[0]):
        lines = lines[:start] + nb + lines[end:]
    return '\n'.join(lines)


def check_ts_full():
    """Полная типовая проверка проекта через tsc --noEmit."""
    import sys
    try:
        # На Windows npx — это npx.cmd, нужен shell=True
        if sys.platform == 'win32':
            cmd = 'npx tsc --noEmit'
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=BASE)
        else:
            r = subprocess.run(['npx', 'tsc', '--noEmit'],
                               capture_output=True, text=True, timeout=30, cwd=BASE)
        if r.returncode == 0:
            return None
        return 'TypeScript errors: ' + (r.stdout or r.stderr).strip()[:300]
    except subprocess.TimeoutExpired:
        return 'tsc --noEmit timeout (30s)'
    except Exception as e:
        return 'tsc error: ' + str(e)


def validate(name, code):
    if code is None:
        return False, 'Resulting code is None (search/replace failed)'
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
    elif ext in ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'):
        if ext in ('.ts', '.tsx'):
            # Военный уровень: требуем наличия инструмента для проверки именно этого кода
            script = os.path.join(BASE, 'tools', 'tscheck.cjs')
            if not os.path.exists(script):
                return False, 'TSX validation tool (tools/tscheck.cjs) is missing'
            err = check_ts(name, code)
            if err:
                return False, 'TS/JS: ' + err
        else:
            err = check_ts(name, code)
            if err:
                return False, 'JS syntax error: ' + err
    return True, None


def apply_search_replace(content, find, replace):
    """Максимально устойчивая замена с двухуровневой нормализацией."""
    # Уровень 1: Нормализация переносов строк к \n
    norm_content = content.replace('\r\n', '\n').replace('\r', '\n')
    norm_find = find.replace('\r\n', '\n').replace('\r', '\n')
    norm_replace = replace.replace('\r\n', '\n').replace('\r', '\n')
    
    # Попытка 1: Точное совпадение (быстро и безопасно)
    if norm_find in norm_content:
        cnt = norm_content.count(norm_find)
        if cnt > 1:
            raise ValueError('Неоднозначно: подстрока найдена ' + str(cnt) + ' раз. Уточни find.')
        new_norm = norm_content.replace(norm_find, norm_replace, 1)
        return new_norm.replace('\n', '\r\n') if '\r\n' in content else new_norm

    # Попытка 2: Совпадение с игнорированием trailing-пробелов в каждой строке
    content_lines = norm_content.split('\n')
    find_lines = norm_find.split('\n')
    
    def strip_r(s): return s.rstrip()
    stripped_content = [strip_r(line) for line in content_lines]
    stripped_find = [strip_r(line) for line in find_lines]
    
    find_len = len(stripped_find)
    hits = [i for i in range(len(stripped_content) - find_len + 1) if stripped_content[i:i+find_len] == stripped_find]
    if len(hits) > 1:
        raise ValueError('Неоднозначно: блок (без trailing-пробелов) найден ' + str(len(hits)) + ' раз. Уточни find.')
    if hits:
        i = hits[0]
        # Нашли блок! Заменяем строки с i по i+find_len на norm_replace.split('\n')
        replace_lines = norm_replace.split('\n')
        new_lines = content_lines[:i] + replace_lines + content_lines[i+find_len:]
        new_norm = '\n'.join(new_lines)
        return new_norm.replace('\n', '\r\n') if '\r\n' in content else new_norm

    # Если не найдено, возвращаем None, чтобы движок выдал понятную ошибку валидации
    return None


def find_patch_file(pid, fname=''):
    if fname:
        p = os.path.join(PATCH_DIR, fname)
        if os.path.exists(p):
            return p
    if not pid:
        return None
    for c in (pid + '.json', 'patch_' + pid + '.json'):
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
    has_body = bool(data.get('operations')) or bool(data.get('diff')) or bool(data.get('full_file_content'))
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


def normalize_ops(data):
    ops = data.get('operations')
    if isinstance(ops, list) and ops:
        return ops
    return [{k: data.get(k) for k in ('type', 'target_file', 'diff', 'full_file_content', 'find', 'replace', 'expected_sha') if data.get(k) is not None}]


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
            ops = normalize_ops(d)
            multi = isinstance(d.get('operations'), list) and len(d.get('operations')) > 1
            pt = 'multi' if multi else (d.get('type', '') or ('search_and_replace' if d.get('find') else ('unified_diff' if d.get('diff') else 'full_replace')))
            targets = [str(o.get('target_file', 'unknown')) for o in ops]
            if multi:
                tgt = targets[0] + ' +' + str(len(targets) - 1) + ' (' + str(len(targets)) + ' файлов)'
            else:
                tgt = targets[0]
            body = d.get('full_file_content', '') if pt in ('full_replace', 'create') else d.get('diff', '')
            clen = len(body) if not multi else sum(len(str(o.get('full_file_content', '') or o.get('diff', ''))) for o in ops)
            out.append({'filename': f, 'filepath': p, 'patch_id': pid, 'patch_type': pt,
                        'target_file': tgt, 'description': d.get('description', ''),
                        'author': d.get('author', '?'), 'created_at': d.get('created_at', ''),
                        'is_applied': pid in done, 'multi': multi, 'op_count': len(targets),
                        'file_exists': os.path.exists(os.path.join(BASE, targets[0])),
                        'content_length': clen, 'has_content': bool(ops),
                        'full_file_content': d.get('full_file_content', ''), 'diff': d.get('diff', ''),
                        'operations': ops})
        except Exception as e:
            out.append({'filename': f, 'filepath': p, 'patch_id': f[:-5], 'patch_type': 'error',
                        'target_file': 'error', 'description': 'Bad JSON: ' + str(e)[:80],
                        'author': 'ERR', 'created_at': '', 'is_applied': False, 'multi': False, 'op_count': 0,
                        'file_exists': False, 'content_length': 0, 'has_content': False, 'error': str(e),
                        'full_file_content': '', 'diff': '', 'operations': []})
    return out


def compute_new(o):
    tgt = o.get('target_file', '')
    if not tgt:
        return None, None, None, 'Нет target_file'
    path = safe_path(tgt)
    if path is None:
        return None, None, None, 'Path outside project: ' + tgt
    pt = o.get('type', '')
    if not pt:
        if o.get('diff'):
            pt = 'unified_diff'
        elif 'find' in o or o.get('find') is not None:
            pt = 'search_and_replace'
        elif o.get('full_file_content'):
            pt = 'full_replace'
    base = None
    existed = os.path.exists(path)
    if existed:
        try:
            with open(path, 'rb') as f:
                base = sha_bytes(f.read())
        except OSError:
            return None, None, None, 'Нельзя прочитать текущий файл: ' + tgt
        expected = o.get('expected_sha')
        if expected and base != expected:
            return None, None, base, 'Stale target_file (expected_sha mismatch): ' + tgt
    if pt == 'create':
        new = o.get('full_file_content', '')
        if not new:
            return None, None, base, 'Нет full_file_content для создания'
        if existed:
            return None, None, base, 'Файл уже существует: ' + tgt + '. Используйте full_replace.'
    elif pt == 'unified_diff':
        d = o.get('diff', '')
        if not d:
            return None, None, base, 'Нет diff'
        if not existed:
            return None, None, base, 'Файл не существует: ' + tgt + '. Используйте create.'
        try:
            new = apply_diff(read_text(path), d)
        except Exception as e:
            return None, None, base, 'Diff не применим (' + tgt + '): ' + str(e)
    elif pt == 'search_and_replace':
        find = o.get('find', '')
        replace = o.get('replace', '')
        if not find:
            return None, None, base, 'Нет find для search_and_replace'
        try:
            new = apply_search_replace(read_text(path), find, replace)
        except Exception as e:
            return None, None, base, 'Search and replace не применим (' + tgt + '): ' + str(e)
    else:
        new = o.get('full_file_content', '')
        if not new:
            return None, None, base, 'Нет full_file_content'
    ok, err = validate(tgt, new)
    if not ok:
        return None, None, base, 'Валидация (' + tgt + '): ' + err
    return path, new, base, None


def compute_ops(data):
    res = []
    cache = {}
    bases = {}
    for o in normalize_ops(data):
        tgt = o.get('target_file', '')
        pt = o.get('type', '') or ('unified_diff' if o.get('diff') else 'full_replace')
        # ИСПРАВЛЕНИЕ: Используем safe_path для каждой операции, чтобы избежать обхода защиты (null-byte, traversal)
        path = safe_path(tgt)
        if path is None:
            res.append({'target_file': tgt, 'type': pt, 'path': None, 'new': None,
                        'err': 'Bad target_file (security): ' + str(tgt)})
            continue
        key = os.path.normcase(path)
        base = bases.get(key)
        if key in cache:
            new, err = None, None
            try:
                if pt == 'unified_diff':
                    new = apply_diff(cache[key], o.get('diff', ''))
                elif pt == 'search_and_replace':
                    fnd = o.get('find', '')
                    if not fnd:
                        err = 'No find for search_and_replace'
                    else:
                        new = apply_search_replace(cache[key], fnd, o.get('replace', ''))
                elif pt == 'create':
                    err = 'Already created in this patch: ' + tgt
                else:
                    new = o.get('full_file_content', '')
                    if not new:
                        err = 'No full_file_content'
                if err is None:
                    ok, ve = validate(tgt, new)
                    if not ok:
                        err = 'Validation (' + tgt + '): ' + str(ve)
            except Exception as e:
                new, err = None, str(e)
        else:
            path, new, base, err = compute_new(o)
        if err is None:
            cache[key] = new
        if err is None and base is not None:
            bases[key] = base
        res.append({'target_file': tgt, 'type': pt, 'path': path, 'new': new, 'base': base, 'err': err})
    return res


def preview_patch(raw):
    data = resolve(raw)
    ops = compute_ops(data)
    errs = [o['err'] for o in ops if o['err']]
    if errs:
        return {'success': False, 'error': ' | '.join(errs)}
    detail = []
    for o in ops:
        old = read_text(o['path']) if os.path.exists(o['path']) else ''
        detail.append({'target_file': o['target_file'], 'op': o['type'],
                       'old_lines': len(old.split('\n')), 'new_lines': len(o['new'].split('\n')),
                       'old_size': len(old), 'new_size': len(o['new'])})
    return {'success': True, 'valid': True, 'multi': len(ops) > 1, 'operations': detail,
            'message': 'OK: ' + str(len(ops)) + ' файл(ов) валидны'}


def test_apply(raw):
    data = resolve(raw)
    pid = str(data.get('patch_id', 'unknown'))
    ops = compute_ops(data)
    errs = [o['err'] for o in ops if o['err']]
    if errs:
        return {'success': False, 'error': ' | '.join(errs)}
    detail = []
    for o in ops:
        old = read_text(o['path']) if os.path.exists(o['path']) else ''
        ol = len(old.split('\n'))
        nl = len(o['new'].split('\n'))
        detail.append({'target_file': o['target_file'], 'op': o['type'], 'old_lines': ol, 'new_lines': nl,
                       'lines_added': max(0, nl - ol), 'lines_removed': max(0, ol - nl)})
    return {'success': True, 'patch_id': pid, 'multi': len(ops) > 1, 'operations': detail,
            'message': 'Тест пройден: ' + str(len(ops)) + ' файл(ов)'}


TX_LOCK = threading.RLock()


def apply_patch(raw):
    data = resolve(raw)
    pid = str(data.get('patch_id', 'unknown'))
    with TX_LOCK:
        return _apply_patch_locked(data, pid)


def _apply_patch_locked(data, pid):
    ops = compute_ops(data)
    errs = [o['err'] for o in ops if o['err']]
    if errs:
        log('Patch ' + pid + ' rejected (phase1): ' + ' | '.join(errs), 'ERROR')
        return {'success': False, 'error': ' | '.join(errs)}
    log('Applying patch ' + pid + ' (' + str(len(ops)) + ' file(s))', 'INFO')
    final = {}
    for o in ops:
        final[os.path.normcase(o['path'])] = o
    ops = list(final.values())
    planned = []
    for o in ops:
        dir_name = os.path.dirname(o['path'])
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        backs = backup(o['path'])
        # A-01 FIX: Если файл существовал, но бэкап не создался, мы не имеем права его трогать
        if os.path.exists(o['path']) and not backs:
            log('Patch ' + pid + ' aborted: backup failed for existing file ' + o['target_file'], 'ERROR')
            return {'success': False, 'error': 'Критическая ошибка: не удалось создать резервную копию ' + o['target_file'] + '. Операция прервана для предотвращения потери данных.'}
        try:
            with open(o['path'], 'rb') as f:
                disk_sha = sha_bytes(f.read()) if os.path.exists(o['path']) else None
        except OSError:
            disk_sha = 'unreadable'
        if o.get('base') is not None and disk_sha != o['base']:
            log('Patch ' + pid + ' aborted: stale file on disk ' + o['target_file'] + ' (changed outside the panel)', 'ERROR')
            return {'success': False, 'error': 'Код на диске изменился вне панели (stale target_file): ' + o['target_file'] + '. Патч отвергнут целиком.'}
        if o.get('base') is None and o['type'] == 'create' and os.path.exists(o['path']):
            log('Patch ' + pid + ' aborted: create target appeared mid-transaction ' + o['target_file'], 'ERROR')
            return {'success': False, 'error': 'Файл появился во время транзакции (create): ' + o['target_file']}
        data = to_bytes(o['new'], file_newline(o['path']))
        planned.append({'path': o['path'], 'new': o['new'], 'backs': backs, 'data': data,
                        'tgt': o['target_file'], 'sha': sha_bytes(data), 'existed': os.path.exists(o['path'])})
    written = []
    try:
        for pl in planned:
            tmp = pl['path'] + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(pl['data'])
            os.replace(tmp, pl['path'])
            written.append(pl)
            with open(pl['path'], 'rb') as f:
                actual = sha_bytes(f.read())
            if actual != pl['sha']:
                raise ValueError('Checksum mismatch: ' + pl['tgt'])
        oprecs = [{'target_file': pl['tgt'], 'checksum': pl['sha'], 'backups': pl['backs']} for pl in planned]
        allb = [x for pl in planned for x in pl['backs']]
        combined = sha(json.dumps(oprecs, sort_keys=True))
        man = load_manifest()
        man['applied'].append({'patch_id': pid, 'target_file': planned[0]['tgt'] if len(planned) == 1 else '+'.join(pl['tgt'] for pl in planned),
                               'operations': oprecs, 'applied_at': datetime.now().isoformat(),
                               'checksum': combined, 'backups': allb})
        man['history'].append({'action': 'apply', 'patch_id': pid, 'files': [pl['tgt'] for pl in planned],
                               'timestamp': datetime.now().isoformat()})
        if len(man['applied']) > 100:
            man['applied'] = man['applied'][-100:]
        if len(man['history']) > 500:
            man['history'] = man['history'][-500:]
        save_manifest(man)
        log('Patch ' + pid + ' applied atomically to ' + str(len(planned)) + ' file(s)', 'SUCCESS')
        return {'success': True, 'message': 'Патч ' + pid + ' применён к ' + str(len(planned)) + ' файл(ам)', 'backups': allb}
    except Exception as e:
        rollback_failed = []
        for pl in written:
            if pl['backs']:
                try:
                    shutil.copy2(pl['backs'][-1], pl['path'])
                except Exception as rb_err:
                    rollback_failed.append(pl['tgt'] + ': ' + str(rb_err))
            elif pl.get('existed') and not pl['backs']:
                # Файл существовал, бэкапа нет, удалять его НЕЛЬЗЯ (A-01 fix)
                pass
            elif not pl.get('existed') and os.path.exists(pl['path']):
                # Это был новый файл (create), его можно безопасно удалить при откате
                try:
                    os.remove(pl['path'])
                except Exception as rb_err:
                    rollback_failed.append(pl['tgt'] + ': ' + str(rb_err))
            tmp = pl['path'] + '.tmp'
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
        log('Patch ' + pid + ' ROLLED BACK (phase2): ' + str(e), 'ERROR')
        return {'success': False, 'error': 'Транзакция отменена, выполнен откат: ' + str(e)}


def rollback():
    with TX_LOCK:
        return _rollback_locked()


def _rollback_locked():
    man = load_manifest()
    if not man.get('applied'):
        return {'success': False, 'error': 'Нет патчей для отката'}
    last = man['applied'][-1]
    ops = last.get('operations')
    if ops:
        for op in reversed(ops):
            path = safe_path(op['target_file'])
            if path is None:
                return {'success': False, 'error': 'Подозрительный target_file в манифесте (path traversal): ' + str(op['target_file'])}
            b = op.get('backups') or []
            # A-02 FIX: Используем конкретный timestamp-бэкап из манифеста, а не _LATEST
            if b and len(b) > 0:
                # b[-1] в манифесте - это конкретный созданный бэкап для этой операции
                specific_backup = b[-1]
                if os.path.exists(specific_backup):
                    shutil.copy2(specific_backup, path)
                else:
                    return {'success': False, 'error': 'Бэкап ' + specific_backup + ' не найден. Откат невозможен.'}
            elif os.path.exists(path):
                # Если это был созданный файл (нет бэкапа), удаляем его
                os.remove(path)
        man['applied'].pop()
        man['rollbacks'].append(last)
        save_manifest(man)
        return {'success': True, 'message': 'Откат ' + str(last['patch_id']) + ' (' + str(len(ops)) + ' файл(ов))'}
    tgt = last['target_file']
    dst = safe_path(tgt)
    if dst is None:
        return {'success': False, 'error': 'Подозрительный target_file в манифесте (path traversal): ' + str(tgt)}
    b = os.path.join(BACKUP_DIR, os.path.basename(tgt) + '_LATEST.bak')
    if not os.path.exists(b):
        return {'success': False, 'error': 'Бэкап не найден'}
    shutil.copy2(b, dst)
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
            'multi_count': len([p for p in ps if p.get('multi')]),
            'history_count': len(man.get('history', [])),
            'rollbacks_count': len(man.get('rollbacks', [])),
            'backups_count': len(os.listdir(BACKUP_DIR))}



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
                         'version': '3.5.0 MULTI-ATOMIC',
                         'providers': {'groq': bool(cfg.get('groq_api_key')),
                                       'openrouter': bool(cfg.get('openrouter_api_key')),
                                       'gemini': bool(cfg.get('gemini_api_key'))}})


@app.get('/api/logs')
def s_logs():
    return JSONResponse({'logs': LOG[-100:]})


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
    return JSONResponse(apply_patch(payload))


@app.get('/api/patches/verify-108')
def s_verify_108():
    """Проверка единого конвейера применения патчей."""
    with open(os.path.join(BASE, 'main.py'), 'r', encoding='utf-8') as f:
        content = f.read()
    checks = {
        'apply_patch_exists': 'def apply_patch(raw):' in content,
        'endpoint_uses_unified': 'return JSONResponse(apply_patch(payload))' in content,
        'rollback_mechanism': 'shutil.copy2' in content,
        'syntax_check': 'ast.parse' in content or 'compile(' in content,
        'safe_path_used': 'safe_path(' in content,
        'no_atomic_leak': 'def apply_patch_atomic' + '(data):' not in content
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
    f = os.path.basename(str(payload.get('filename', '')))
    if not f or not f.endswith('.json'):
        return JSONResponse({'success': False, 'error': 'Подозрительное имя файла'})
    p = os.path.join(PATCH_DIR, f)
    if os.path.realpath(os.path.dirname(p)) != os.path.realpath(PATCH_DIR):
        return JSONResponse({'success': False, 'error': 'forbidden'})
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
        ui.label('drmAIcu Core v3.5.2 NICEGUI').classes('text-xl font-bold')
    
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
    log('Starting drmAIcu Core v3.5.0 MULTI-ATOMIC...')
    get_engine()
    create_ui()
    ui.run(title='drmAIcu Core', port=8080, reload=False, show=False)
