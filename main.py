# main.py v3.5.0 MULTI-ATOMIC
from nicegui import ui, app
import json, os, sys, re, ast, shutil, hashlib, threading, importlib, traceback, asyncio, time, subprocess
from datetime import datetime, timedelta
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
    p = os.path.normpath(os.path.join(BASE, str(rel)))
    try:
        if os.path.commonpath([BASE, p]) != BASE:
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
        err = check_ts(name, code)
        if err:
            return False, 'TS/JS: ' + err
        # Полная типовая проверка (только для TS/TSX, не JS)
        if ext in ('.ts', '.tsx'):
            err = check_ts_full()
            if err:
                return False, err
    elif ext in ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'):
        err = check_ts(name, code)
        if err:
            return False, 'TS/JS: ' + err
        # Полная типовая проверка (только для TS/TSX, не JS)
        if ext in ('.ts', '.tsx'):
            err = check_ts_full()
            if err:
                return False, err
    return True, None


def apply_search_replace(content, find, replace):
    """Точечная замена подстроки с авто-нормализацией переносов строк (Windows \r\n <-> Unix \n)."""
    # Определяем тип переносов в файле
    crlf = '\r\n' in content
    # Нормализуем все три строки к \n для поиска
    content_n = content.replace('\r\n', '\n')
    find_n = find.replace('\r\n', '\n')
    replace_n = replace.replace('\r\n', '\n')
    if find_n not in content_n:
        raise ValueError('Подстрока не найдена в файле (после нормализации переносов). Фрагмент: ' + find_n[:80] + '... Проверьте точное совпадение.')
    count = content_n.count(find_n)
    if count > 1:
        raise ValueError(f'Подстрока найдена {count} раз. Уточните контекст для уникальности.')
    new_content = content_n.replace(find_n, replace_n)
    # Возвращаем исходный тип переносов, если файл был Windows
    if crlf:
        new_content = new_content.replace('\n', '\r\n')
    return new_content


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
    return [{k: data.get(k) for k in ('type', 'target_file', 'diff', 'full_file_content', 'find', 'replace') if data.get(k) is not None}]


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
        return None, None, 'Нет target_file'
    path = safe_path(tgt)
    if path is None:
        return None, None, 'Path outside project: ' + tgt
    pt = o.get('type', '')
    if not pt:
        if o.get('diff'):
            pt = 'unified_diff'
        elif o.get('full_file_content'):
            pt = 'full_replace'
    if pt == 'create':
        new = o.get('full_file_content', '')
        if not new:
            return None, None, 'Нет full_file_content для создания'
        if os.path.exists(path):
            return None, None, 'Файл уже существует: ' + tgt + '. Используйте full_replace.'
    elif pt == 'unified_diff':
        d = o.get('diff', '')
        if not d:
            return None, None, 'Нет diff'
        if not os.path.exists(path):
            return None, None, 'Файл не существует: ' + tgt + '. Используйте create.'
        try:
            new = apply_diff(read_text(path), d)
        except Exception as e:
            return None, None, 'Diff не применим (' + tgt + '): ' + str(e)
    elif pt == 'search_and_replace':
        find = o.get('find', '')
        replace = o.get('replace', '')
        if not find:
            return None, None, 'Нет find для search_and_replace'
        try:
            new = apply_search_replace(read_text(path), find, replace)
        except Exception as e:
            return None, None, 'Search and replace не применим (' + tgt + '): ' + str(e)
    else:
        new = o.get('full_file_content', '')
        if not new:
            return None, None, 'Нет full_file_content'
    ok, err = validate(tgt, new)
    if not ok:
        return None, None, 'Валидация (' + tgt + '): ' + err
    return path, new, None


def compute_ops(data):
    res = []
    cache = {}
    for o in normalize_ops(data):
        tgt = o.get('target_file', '')
        pt = o.get('type', '') or ('unified_diff' if o.get('diff') else 'full_replace')
        path = os.path.normpath(os.path.join(BASE, tgt))
        try:
            inside = os.path.commonpath([BASE, path]) == BASE
        except ValueError:
            inside = False
        if not tgt or not inside:
            res.append({'target_file': tgt, 'type': pt, 'path': None, 'new': None,
                        'err': 'Bad target_file: ' + str(tgt)})
            continue
        key = os.path.normcase(path)
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
            path, new, err = compute_new(o)
        if err is None:
            cache[key] = new
        res.append({'target_file': tgt, 'type': pt, 'path': path, 'new': new, 'err': err})
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


def apply_patch(raw):
    data = resolve(raw)
    pid = str(data.get('patch_id', 'unknown'))
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
        data = to_bytes(o['new'], file_newline(o['path']))
        planned.append({'path': o['path'], 'new': o['new'], 'backs': backs, 'data': data,
                        'tgt': o['target_file'], 'sha': sha_bytes(data)})
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
        for pl in written:
            if pl['backs']:
                try:
                    shutil.copy2(pl['backs'][-1], pl['path'])
                except Exception:
                    pass
            elif os.path.exists(pl['path']):
                try:
                    os.remove(pl['path'])
                except Exception:
                    pass
            tmp = pl['path'] + '.tmp'
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
        log('Patch ' + pid + ' ROLLED BACK (phase2): ' + str(e), 'ERROR')
        return {'success': False, 'error': 'Транзакция отменена, всё восстановлено: ' + str(e)}


def rollback():
    man = load_manifest()
    if not man.get('applied'):
        return {'success': False, 'error': 'Нет патчей для отката'}
    last = man['applied'][-1]
    ops = last.get('operations')
    if ops:
        for op in reversed(ops):
            path = os.path.join(BASE, op['target_file'])
            b = op.get('backups') or []
            if b:
                shutil.copy2(b[-1], path)
            elif os.path.exists(path):
                os.remove(path)
        man['applied'].pop()
        man['rollbacks'].append(last)
        save_manifest(man)
        return {'success': True, 'message': 'Откат ' + str(last['patch_id']) + ' (' + str(len(ops)) + ' файл(ов))'}
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
            'multi_count': len([p for p in ps if p.get('multi')]),
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


@app.post('/api/patches/test-apply')
def s_ptest(payload: dict):
    return JSONResponse(test_apply(payload))


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
    with ui.header().classes('bg-gray-900 text-white p-4'):
        ui.label('drmAIcu Core v3.5.0 MULTI-ATOMIC').classes('text-xl font-bold')


if __name__ in {'__main__', '__mp_main__'}:
    log('Starting drmAIcu Core v3.5.0 MULTI-ATOMIC...')
    get_engine()
    create_ui()
    ui.run(title='drmAIcu Core', port=8080, reload=False, show=False)
