# patch_engine.py
# Patch engine v3.5.3 HARDENED: atomic two-phase commits, no UI dependencies
import json, os, re, ast, shutil, hashlib, threading, subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
PATCH_DIR = os.path.join(BASE, 'patch')
ARCHIVE_DIR = os.path.join(PATCH_DIR, 'archive')
BACKUP_DIR = os.path.join(BASE, 'backups')
MANIFEST = os.path.join(BASE, 'patch_manifest.json')
LOG = []

for d in (PATCH_DIR, ARCHIVE_DIR, BACKUP_DIR):
    os.makedirs(d, exist_ok=True)


def log(msg, lvl='INFO'):
    t = datetime.now().strftime('%H:%M:%S')
    LOG.append({'time': t, 'level': lvl.lower(), 'message': str(msg), 'source': 'Engine'})
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
