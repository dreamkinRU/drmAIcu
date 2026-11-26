# patch_engine.py
# Patch engine HARDENED: journaled crash-recoverable multi-file transactions (версия — version.py)
from version import VERSION as _ENGINE_VERSION
import json, os, re, ast, shutil, hashlib, threading, subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
PATCH_DIR = os.path.join(BASE, 'patch')
ARCHIVE_DIR = os.path.join(PATCH_DIR, 'archive')
BACKUP_DIR = os.path.join(BASE, 'backups')
DOWNLOADS_DIR = os.path.join(os.path.expanduser('~'), 'Downloads')
MANIFEST = os.path.join(BASE, 'patch_manifest.json')
JOURNAL = os.path.join(BASE, 'patch_journal.json')
MANIFEST_LOCK = ''
JOURNAL_LOCK = ''
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
    # B28 FIX: пустая строка и None — не путь
    if rel is None or not str(rel):
        return None
    rel = str(rel)
    if chr(0) in rel:
        return None
    # B28 FIX: backslash-сепараторы и drive-буквы Windows запрещены ( в manifest используется '/')
    if '\\' in rel or re.match(r'^[A-Za-z]:', rel):
        return None
    p = os.path.normpath(os.path.join(BASE, rel))
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
    """None означает PASS; строка описывает FAIL или UNAVAILABLE."""
    root = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(root, 'tools', 'tscheck.cjs')
    if not os.path.isfile(script):
        return 'UNAVAILABLE: tools/tscheck.cjs отсутствует'
    node = shutil.which('node')
    if not node:
        return 'UNAVAILABLE: Node.js не найден в PATH'
    try:
        result = subprocess.run(
            [node, script, name], input=code.encode('utf-8'),
            capture_output=True, timeout=30, cwd=root,
        )
    except subprocess.TimeoutExpired:
        return 'UNAVAILABLE: проверка Node.js превысила timeout 30s'
    except OSError as exc:
        return 'UNAVAILABLE: не удалось запустить Node.js: %s' % exc
    except Exception as exc:
        return 'UNAVAILABLE: ошибка запуска валидатора: %s' % exc
    if result.returncode == 0:
        return None
    output = (result.stdout or result.stderr).decode('utf-8', 'replace').strip()
    return output[:500] or 'FAIL: TypeScript validator exited with code %s' % result.returncode


def load_manifest():
    global MANIFEST_LOCK
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST, 'r', encoding='utf-8') as f:
                m = json.load(f)
            if not isinstance(m, dict) or not isinstance(m.get('applied'), list) or not isinstance(m.get('history'), list) or not isinstance(m.get('rollbacks'), list):
                raise ValueError('wrong manifest shape')
            MANIFEST_LOCK = ''
            return m
        except Exception as e:
            # B52 FIX (P1-05): повреждённый манифест НЕ превращается в пустой — движок блокируется
            cp = MANIFEST + '.corrupt'
            try:
                shutil.copy2(MANIFEST, cp)
            except Exception:
                pass
            if not MANIFEST_LOCK:
                MANIFEST_LOCK = 'манифест повреждён (' + str(e)[:80] + '), копия сохранена: ' + cp
                log('MANIFEST CORRUPT: ' + str(e) + '. Изменения заблокированы, повреждённый файл сохранён: ' + cp, 'ERROR')
            return {'applied': [], 'history': [], 'rollbacks': []}
    MANIFEST_LOCK = ''
    return {'applied': [], 'history': [], 'rollbacks': []}


def save_manifest(m):
    # B26 FIX: atomic write — tmp + os.replace, сбой записи не режет живой манифест
    tmp = MANIFEST + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(m, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, MANIFEST)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise


def _write_journal(j):
    # B51 FIX: crash-журнал — tmp + fsync + атомарная замена
    tmp = JOURNAL + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(j, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, JOURNAL)


def load_journal():
    """Повреждение/неоднозначность журнала блокируют новые операции записи."""
    global JOURNAL_LOCK
    if not os.path.exists(JOURNAL):
        if os.path.exists(JOURNAL + '.tmp'):
            JOURNAL_LOCK = 'обнаружен незавершённый временный crash-журнал: ' + JOURNAL + '.tmp'
            return None
        JOURNAL_LOCK = ''
        return None
    try:
        with open(JOURNAL, 'r', encoding='utf-8') as f:
            journal = json.load(f)
        if not isinstance(journal, dict):
            raise ValueError('journal root must be an object')
        if journal.get('op') not in ('apply', 'rollback'):
            raise ValueError('unknown journal operation')
        if not isinstance(journal.get('steps'), list) or not journal['steps']:
            raise ValueError('journal steps must be a non-empty list')
        for index, step in enumerate(journal['steps']):
            if not isinstance(step, dict) or not isinstance(step.get('tgt'), str):
                raise ValueError('invalid journal step %s' % index)
            if not isinstance(step.get('done', False), bool):
                raise ValueError('invalid journal done flag at step %s' % index)
        JOURNAL_LOCK = ''
        return journal
    except Exception as exc:
        corrupt_copy = JOURNAL + '.corrupt'
        try:
            if not os.path.exists(corrupt_copy):
                shutil.copy2(JOURNAL, corrupt_copy)
        except OSError:
            pass
        JOURNAL_LOCK = 'crash-журнал повреждён или недоступен (%s); файл сохранён для ручного восстановления' % str(exc)[:160]
        log('JOURNAL CORRUPT: ' + JOURNAL_LOCK, 'ERROR')
        return None


def _clear_journal():
    global JOURNAL_LOCK
    try:
        os.remove(JOURNAL)
    except FileNotFoundError:
        pass
    except OSError as exc:
        JOURNAL_LOCK = 'не удалось удалить crash-журнал: %s' % exc
        return
    try:
        if os.path.exists(JOURNAL + '.tmp'):
            os.remove(JOURNAL + '.tmp')
    except OSError as exc:
        JOURNAL_LOCK = 'не удалось удалить временный crash-журнал: %s' % exc
        return
    JOURNAL_LOCK = ''


def _pick_backup(backs):
    # B32 FIX: timestamp-бэкап операции, _LATEST.bak — только фоллбэк
    for cand in backs or []:
        if not os.path.basename(str(cand)).endswith('_LATEST.bak'):
            return cand
    return (backs or [None])[-1]


def _rotate_backups(name, keep=10):
    # B61 FIX (P2-14): ротация — не более keep timestamp-бэкапов на файл (_LATEST.bak не считается)
    prefix = name + '_'
    try:
        stamps = sorted(
            f for f in os.listdir(BACKUP_DIR)
            if f.startswith(prefix) and f.endswith('.bak') and not f.endswith('_LATEST.bak')
        )
        for old in stamps[:max(0, len(stamps) - keep)]:
            try:
                os.remove(os.path.join(BACKUP_DIR, old))
            except OSError:
                pass
    except OSError:
        pass


def backup(path):
    out = []
    if not os.path.exists(path):
        return out
    name = os.path.relpath(path, BASE).replace(os.sep, '__').replace(':', '')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    timestamp_dst = None
    # B61 FIX: timestamp может совпасть на Windows/при параллельном вызове.
    # O_EXCL резервирует уникальное имя атомарно, затем copy2 записывает содержимое.
    try:
        attempt = 0
        while True:
            collision_suffix = '' if attempt == 0 else '_%02d' % attempt
            candidate = os.path.join(BACKUP_DIR, name + '_' + ts + collision_suffix + '.bak')
            try:
                fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_BINARY', 0), 0o600)
                os.close(fd)
                timestamp_dst = candidate
                break
            except FileExistsError:
                attempt += 1
        shutil.copy2(path, timestamp_dst)
        out.append(timestamp_dst)

        latest_dst = os.path.join(BACKUP_DIR, name + '_LATEST.bak')
        shutil.copy2(path, latest_dst)
        out.append(latest_dst)
    except Exception:
        # B27 FIX: all-or-nothing — частичный набор бэкапов равносилен отсутствию бэкапа
        for x in out + ([timestamp_dst] if timestamp_dst and timestamp_dst not in out else []):
            try:
                os.remove(x)
            except OSError:
                pass
        return []
    _rotate_backups(name, keep=10)
    return out


def _rel_backup(p):
    # B69 FIX (P2-22): в манифесте храним путь относительно BASE с '/' вместо Windows-абсолютных путей
    return os.path.relpath(p, BASE).replace(os.sep, '/')


def _backup_path(p):
    # B69 FIX (P2-22): резолвер backup-путей — относительный (новый манифест) относительно BASE,
    # абсолютный (легаси-манифесты со старых машин) — как есть
    if not p:
        return p
    p = str(p)
    if os.path.isabs(p):
        return p
    return os.path.join(BASE, p.replace('/', os.sep))


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
    # B44 FIX: diff без единого валидного ханка — ошибка, а не молчаливый no-op
    if not hunks:
        raise ValueError('Не удалось распарсить unified diff: нет ни одного валидного ханка (кривые @@-заголовки или diff пуст)')
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
        # B44 FIX: пустой ханк (ни -/+ действий) — ошибка, а не молчаливый no-op
        if not old_block and not new_block:
            raise ValueError('Пустой ханк в diff (нет строк -/+ у ханка, смещение ' + str(old_start) + ')')
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


def _tsc_cmd():
    # B62 FIX (P2-15): только локальный tsc — без npx (npx тянет сеть)
    local = os.path.join(BASE, 'node_modules', 'typescript', 'bin', 'tsc')
    if os.path.exists(local):
        return ['node', local]
    found = shutil.which('tsc')
    if found:
        return [found]
    return None


def check_ts_full():
    """Полная типовая проверка проекта через tsc --noEmit.
    B62 FIX (P2-15): возвращает None, если tsc недоступен (пропуск проверки),
    строку с ошибкой типов — если проверка провалилась."""
    import sys
    cmd = _tsc_cmd()
    if cmd is None:
        return None
    iargs = ['--noEmit']
    try:
        if sys.platform == 'win32' and cmd[0] != 'node':
            r = subprocess.run(subprocess.list2cmdline(cmd + iargs),
                               shell=True, capture_output=True, text=True, timeout=60, cwd=BASE)
        else:
            r = subprocess.run(cmd + iargs,
                               capture_output=True, text=True, timeout=60, cwd=BASE)
        if r.returncode == 0:
            return None
        return 'TypeScript errors: ' + (r.stdout or r.stderr).strip()[:300]
    except subprocess.TimeoutExpired:
        return 'tsc --noEmit timeout (60s)'
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


def _patch_source_dirs():
    dirs = [PATCH_DIR]
    if DOWNLOADS_DIR and os.path.isdir(DOWNLOADS_DIR) and os.path.normcase(os.path.realpath(DOWNLOADS_DIR)) != os.path.normcase(os.path.realpath(PATCH_DIR)):
        dirs.append(DOWNLOADS_DIR)
    return dirs


def find_patch_file(pid, fname=''):
    # B25 FIX: fname из payload не может совершить traversal — только basename + '.json' внутри разрешённых папок
    dirs = _patch_source_dirs()
    if fname:
        f = os.path.basename(str(fname))
        if f and f.endswith('.json'):
            for d_dir in dirs:
                p = os.path.join(d_dir, f)
                if os.path.isfile(p):
                    return p
    if not pid:
        return None
    for d_dir in dirs:
        for c in (pid + '.json', 'patch_' + pid + '.json'):
            p = os.path.join(d_dir, c)
            if os.path.isfile(p):
                return p
    for d_dir in dirs:
        try:
            for f in os.listdir(d_dir):
                if not f.endswith('.json'):
                    continue
                p = os.path.join(d_dir, f)
                if not os.path.isfile(p):
                    continue
                try:
                    d = json.loads(read_text(p))
                    if isinstance(d, dict) and str(d.get('patch_id', '')) == str(pid):
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


def _is_valid_patch_dict(d):
    if not isinstance(d, dict):
        return False
    if isinstance(d.get('operations'), list) and len(d.get('operations')) > 0:
        return True
    if d.get('patch_id') and d.get('target_file'):
        return True
    return False


def list_patches():
    out = []
    seen_files = set()
    man = load_manifest()
    done = set()
    for a in man.get('applied', []):
        done.add(str(a.get('patch_id')))
    for src_dir in _patch_source_dirs():
        is_downloads = (src_dir == DOWNLOADS_DIR)
        if not os.path.isdir(src_dir):
            continue
        try:
            names = sorted(os.listdir(src_dir))
        except OSError:
            continue
        for f in names:
            if not f.endswith('.json') or f.startswith('.'):
                continue
            if f in seen_files:
                continue
            p = os.path.join(src_dir, f)
            if not os.path.isfile(p):
                continue
            try:
                d = json.loads(read_text(p))
                if is_downloads and not _is_valid_patch_dict(d):
                    continue
                seen_files.add(f)
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
                desc = d.get('description', '')
                if is_downloads:
                    desc = '[Загрузки] ' + desc
                out.append({'filename': f, 'filepath': p, 'patch_id': pid, 'patch_type': pt,
                            'target_file': tgt, 'description': desc,
                            'author': d.get('author', '?'), 'created_at': d.get('created_at', ''),
                            'is_applied': pid in done, 'multi': multi, 'op_count': len(targets),
                            'file_exists': os.path.exists(os.path.join(BASE, targets[0])),
                            'content_length': clen, 'has_content': bool(ops),
                            'full_file_content': d.get('full_file_content', ''), 'diff': d.get('diff', ''),
                            'operations': ops})
            except Exception as e:
                if is_downloads:
                    continue
                seen_files.add(f)
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
    patch_fname = data.get('filename', '') if isinstance(data, dict) else ''
    # B52 FIX: повреждённый манифест → любые изменения движка запрещены
    journal0 = load_journal()
    if JOURNAL_LOCK:
        return {'success': False, 'error': 'Движок заблокирован: ' + JOURNAL_LOCK}
    if journal0 is not None:
        return {'success': False, 'error': 'Движок ожидает восстановления незавершённой транзакции. Сначала выполните recover_journal().'}
    man0 = load_manifest()
    if MANIFEST_LOCK:
        log('Patch ' + pid + ' rejected: манифест заблокирован (повреждён)', 'ERROR')
        return {'success': False, 'error': 'Движок заблокирован: ' + MANIFEST_LOCK}
    # B43 FIX: повторное применение уже применённого патча запрещено (_LATEST после rollback — можно)
    if str(pid) in {str(a.get('patch_id')) for a in man0.get('applied', [])}:
        log('Patch ' + pid + ' rejected: already applied', 'ERROR')
        return {'success': False, 'error': 'Патч ' + str(pid) + ' уже применён (повторное применение запрещено)'}
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
    # B62 FIX (P2-15): полная типовая проверка tsc --noEmit перед изменением ЛЮБОГО .ts/.tsx;
    # ошибка типов останавливает транзакцию до записи файлов и бэкапов
    if any(str(o['target_file']).lower().endswith(('.ts', '.tsx')) for o in ops) and _tsc_cmd() is not None:
        ts_err = check_ts_full()
        if ts_err:
            log('Patch ' + pid + ' rejected (tsc --noEmit): ' + ts_err[:300], 'ERROR')
            return {'success': False, 'error': 'Патч отклонён tsc --noEmit (проверка типов до записи): ' + ts_err[:300]}
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
        old_sha = None
        try:
            if os.path.exists(o['path']):
                with open(o['path'], 'rb') as f:
                    old_sha = sha_bytes(f.read())
            disk_sha = old_sha
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
                        'tgt': o['target_file'], 'sha': sha_bytes(data), 'existed': os.path.exists(o['path']),
                        'old_sha': old_sha})
    written = []
    # B51 FIX (P1-04): crash-журнал транзакции пишется до первой записи на диск,
    # done-флаг — после каждого os.replace; по нему recover_journal(): после перезапуска
    # восстанавливает старое состояние всех файлов (в том числе записанных до сбоя)
    jrec = {'op': 'apply', 'patch_id': pid,
            'steps': [{'path': pl['path'], 'tgt': pl['tgt'], 'existed': pl['existed'],
                       'backs': pl['backs'], 'backup_sha': pl['old_sha'], 'done': False}
                      for pl in planned]}
    try:
        _write_journal(jrec)
        for pl in planned:
            tmp = pl['path'] + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(pl['data'])
            os.replace(tmp, pl['path'])
            written.append(pl)
            for st in jrec['steps']:
                if st['path'] == pl['path']:
                    st['done'] = True
            _write_journal(jrec)
            with open(pl['path'], 'rb') as f:
                actual = sha_bytes(f.read())
            if actual != pl['sha']:
                raise ValueError('Checksum mismatch: ' + pl['tgt'])
        # B40 FIX: в манифест попадает sha контента ДО apply — верификация бэкапа при откате
        oprecs = [{'target_file': pl['tgt'], 'checksum': pl['sha'],
                   'backups': [_rel_backup(x) for x in pl['backs']],
                   'backup_sha': pl['old_sha']} for pl in planned]
        allb = [_rel_backup(x) for pl in planned for x in pl['backs']]
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
        # B51 FIX: транзакция зафиксирована в манифесте — журнал больше не нужен
        _clear_journal()
        src_patch = find_patch_file(pid, patch_fname)
        if src_patch and os.path.isfile(src_patch):
            try:
                dst_patch = os.path.join(ARCHIVE_DIR, os.path.basename(src_patch))
                if os.path.exists(dst_patch):
                    os.remove(dst_patch)
                shutil.move(src_patch, dst_patch)
                log('Patch ' + pid + ' auto-archived to ' + os.path.basename(dst_patch), 'INFO')
            except Exception as arch_err:
                log('Auto-archive failed for ' + pid + ': ' + str(arch_err), 'WARN')
        log('Patch ' + pid + ' applied with journaled recovery to ' + str(len(planned)) + ' file(s)', 'SUCCESS')
        return {'success': True, 'message': 'Патч ' + pid + ' применён к ' + str(len(planned)) + ' файл(ам) и перемещён в архив', 'backups': allb}
    except Exception as e:
        rollback_failed = []
        for pl in planned:
            # B38 FIX: tmp-мусор чистим для ЛЮБОЙ запланированной цели, а не только записанных
            tmp = pl['path'] + '.tmp'
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
        for pl in written:
            if pl['backs']:
                try:
                    shutil.copy2(_pick_backup(pl['backs']), pl['path'])
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
        log('Patch ' + pid + ' ROLLED BACK (phase2): ' + str(e), 'ERROR')
        # B50 FIX (P1-03): частичный откат НЕ выдаётся за удачный — явно перечисляем файлы
        if rollback_failed:
            log('Patch ' + pid + ' PARTIAL ROLLBACK, не восстановлены: ' + '; '.join(rollback_failed), 'ERROR')
            return {'success': False,
                    'error': 'Транзакция отменена, НО откат неполный! Не восстановлены: ' + '; '.join(rollback_failed) + ' | ' + str(e) + '. Журнал patch_journal.json сохранён для последующего восстановления.',
                    'rollback_failed': rollback_failed, 'rollback_incomplete': True}
        _clear_journal()
        return {'success': False, 'error': 'Транзакция отменена, выполнен откат: ' + str(e), 'rollback_failed': []}


def rollback():
    with TX_LOCK:
        return _rollback_locked()


def _verify_current_for_rollback(op, path):
    # B48 FIX (P1-01): текущий файл обязан соответствовать checksum применённого патча,
    # иначе rollback молча стёр бы пользовательские правки — операция запрещается
    expected_new = op.get('checksum')
    if expected_new is None:
        return None
    if not os.path.exists(path):
        return 'Файл исчез после применения патча: ' + str(op['target_file']) + '. Откат запрещён.'
    try:
        with open(path, 'rb') as f:
            cur = sha_bytes(f.read())
    except OSError:
        return 'Целевой файл нечитаем: ' + str(op['target_file']) + '. Откат запрещён.'
    if cur != expected_new:
        return 'Файл изменён после применения патча: ' + str(op['target_file']) + '. Откат запрещён, чтобы не потерять правки. Верните файл в ожидаемое состояние.'
    return None


def _rollback_locked(resume_journal=False):
    journal = load_journal()
    if JOURNAL_LOCK:
        return {'success': False, 'error': 'Движок заблокирован: ' + JOURNAL_LOCK}
    man = load_manifest()
    if MANIFEST_LOCK:
        return {'success': False, 'error': 'Движок заблокирован: ' + MANIFEST_LOCK}
    if journal is not None and not resume_journal:
        if journal.get('op') != 'rollback':
            return {'success': False, 'error': 'Незавершённый apply требует recover_journal() перед откатом.'}
        applied = man.get('applied') or []
        last_applied = applied[-1] if applied else None
        if not last_applied or str(last_applied.get('patch_id')) != str(journal.get('patch_id')):
            return {'success': False, 'error': 'Rollback-журнал не соответствует последнему применённому патчу; требуется ручная диагностика.'}
        # Повторный вызов rollback безопасно возобновляет ранее прерванный rollback.
    if not man.get('applied'):
        return {'success': False, 'error': 'Нет патчей для отката'}
    last = man['applied'][-1]
    ops = last.get('operations')
    if ops:
        # B40 FIX: verify-first — ВСЯ целостность проверяется до первой записи на диск
        # B51 FIX: resume — если журнал принадлежит этому rollback, шаги с done=True уже восстановлены
        done_paths = set()
        j = load_journal()
        if j and j.get('op') == 'rollback' and str(j.get('patch_id')) == str(last.get('patch_id')):
            done_paths = {str(st['path']) for st in j.get('steps', []) if st.get('done')}
            log('CRASH-RECOVERY: возобновляю прерванный rollback патча ' + str(last.get('patch_id')) + ' (восстановлено ранее: ' + str(len(done_paths)) + ')', 'WARNING')
        restores = []
        for op in reversed(ops):
            path = safe_path(op['target_file'])
            if path is None:
                return {'success': False, 'error': 'Подозрительный target_file в манифесте (path traversal): ' + str(op['target_file'])}
            if str(path) in done_paths:
                continue
            b = op.get('backups') or []
            # A-02/B32 FIX: timestamp-бэкап этой операции, _LATEST — только фоллбэк
            if b:
                specific_backup = _backup_path(_pick_backup(b))
                if not os.path.exists(specific_backup):
                    return {'success': False, 'error': 'Бэкап ' + str(specific_backup) + ' не найден. Откат невозможен.'}
                expected = op.get('backup_sha')
                if expected is not None:
                    try:
                        with open(specific_backup, 'rb') as f:
                            actual = sha_bytes(f.read())
                    except OSError:
                        return {'success': False, 'error': 'Бэкап ' + str(specific_backup) + ' нечитаем. Откат невозможен.'}
                    if actual != expected:
                        log('Rollback aborted: backup content does not match manifest checksum ' + str(specific_backup), 'ERROR')
                        return {'success': False, 'error': 'Бэкап не совпадает с контрольной суммой манифеста (подменён или повреждён): ' + str(specific_backup)}
                err = _verify_current_for_rollback(op, path)
                if err:
                    return {'success': False, 'error': err}
                restores.append({'path': path, 'tgt': op['target_file'],
                                 'backup': specific_backup, 'backup_sha': expected})
            elif os.path.exists(path):
                # созданный патчем файл (нет бэкапа) — перед удалением та же B48-проверка
                err = _verify_current_for_rollback(op, path)
                if err:
                    return {'success': False, 'error': err}
                restores.append({'path': path, 'tgt': op['target_file'],
                                 'backup': None, 'backup_sha': None})
        if not restores:
            man['applied'].pop()
            man['rollbacks'].append(last)
            save_manifest(man)
            _clear_journal()
            return {'success': True, 'message': 'Откат ' + str(last['patch_id']) + ' завершён (все файлы уже были восстановлены)'}
        # B49 FIX (P1-02): two-phase rollback — сначала staging ВСЕХ файлов во временные
        # копии с проверкой контрольных сумм, только потом контролируемая замена;
        # сбой оставляет crash-журнал для resume
        jrec = {'op': 'rollback', 'patch_id': last.get('patch_id'),
                'steps': [{'path': st['path'], 'tgt': st['tgt'], 'backup': st['backup'],
                           'backup_sha': st['backup_sha'], 'done': st['path'] in done_paths} for st in restores],
                'entry': last}
        staged = []
        try:
            _write_journal(jrec)
            for st in restores:
                if st['backup']:
                    tmp = st['path'] + '.rbk.tmp'
                    shutil.copy2(st['backup'], tmp)
                    if st['backup_sha'] is not None:
                        with open(tmp, 'rb') as f:
                            actual = sha_bytes(f.read())
                        if actual != st['backup_sha']:
                            raise ValueError('Staging: контрольная сумма не совпала: ' + st['tgt'])
                    staged.append((st, tmp))
                else:
                    staged.append((st, None))
            for st, tmp in staged:
                if tmp:
                    os.replace(tmp, st['path'])
                elif os.path.exists(st['path']):
                    os.remove(st['path'])
                for step in jrec['steps']:
                    if step['path'] == st['path']:
                        step['done'] = True
                _write_journal(jrec)
            man['applied'].pop()
            man['rollbacks'].append(last)
            save_manifest(man)
            _clear_journal()
            return {'success': True, 'message': 'Откат ' + str(last['patch_id']) + ' (' + str(len(ops)) + ' файл(ов))'}
        except Exception as e:
            for st, tmp in staged:
                if tmp and os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
            for st in restores:
                t = st['path'] + '.rbk.tmp'
                if os.path.exists(t):
                    try:
                        os.remove(t)
                    except OSError:
                        pass
            log('Rollback interrupted: ' + str(e) + '. Журнал сохранён для resume', 'ERROR')
            return {'success': False, 'error': 'Откат прерван (' + str(e) + '). Журнал patch_journal.json сохранён — повторный откат завершит восстановление.', 'interrupted': True}

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


def _recover_apply(j):
    # Восстановление старого состояния всех целей; отсутствие/подмена backup не считается успехом.
    steps = j.get('steps') or []
    recovered = []
    failed = []
    backup_root = os.path.realpath(BACKUP_DIR)
    for st in steps:
        tgt = st.get('tgt', '')
        sp = safe_path(tgt)
        if sp is None:
            failed.append(str(tgt) + ': bad path')
            continue
        for suffix in ('.tmp', '.rbk.tmp'):
            temp_path = sp + suffix
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
        try:
            if st.get('existed'):
                backup_ref = _pick_backup(st.get('backs') or [])
                src = _backup_path(backup_ref)
                if not src or not os.path.isfile(src):
                    raise FileNotFoundError('backup missing for previously existing target')
                resolved_src = os.path.realpath(src)
                try:
                    if os.path.normcase(os.path.commonpath([backup_root, resolved_src])) != os.path.normcase(backup_root):
                        raise ValueError('backup path escapes BACKUP_DIR')
                except ValueError:
                    raise ValueError('backup path escapes BACKUP_DIR')
                expected_backup_sha = st.get('backup_sha')
                if expected_backup_sha is not None:
                    with open(resolved_src, 'rb') as backup_file:
                        actual_backup_sha = sha_bytes(backup_file.read())
                    if actual_backup_sha != expected_backup_sha:
                        raise ValueError('backup checksum mismatch')
                shutil.copy2(resolved_src, sp)
                if expected_backup_sha is not None:
                    with open(sp, 'rb') as restored_file:
                        actual_restored_sha = sha_bytes(restored_file.read())
                    if actual_restored_sha != expected_backup_sha:
                        raise ValueError('restored file checksum mismatch')
                recovered.append(str(tgt))
            elif os.path.exists(sp):
                os.remove(sp)
                recovered.append(str(tgt))
        except Exception as exc:
            failed.append(str(tgt) + ': ' + str(exc))
    if failed:
        log('CRASH RECOVERY (apply): неполное восстановление — ' + '; '.join(failed), 'ERROR')
        return {'action': 'apply-revert-incomplete', 'patch_id': j.get('patch_id'),
                'recovered': recovered, 'failed': failed}
    _clear_journal()
    if JOURNAL_LOCK:
        return {'action': 'blocked', 'patch_id': j.get('patch_id'),
                'error': JOURNAL_LOCK, 'recovered': recovered}
    log('CRASH RECOVERY (apply): состояние до патча ' + str(j.get('patch_id')) + ' восстановлено (' + str(len(recovered)) + ' файл(ов))', 'WARNING')
    return {'action': 'apply-reverted', 'patch_id': j.get('patch_id'), 'files': recovered}


def recover_journal():
    global JOURNAL_LOCK
    # Crash recovery выполняется до любых новых операций записи.
    j = load_journal()
    if JOURNAL_LOCK:
        return {'action': 'blocked', 'error': JOURNAL_LOCK}
    if j is None:
        return None
    with TX_LOCK:
        j = load_journal()
        if JOURNAL_LOCK:
            return {'action': 'blocked', 'error': JOURNAL_LOCK}
        if j is None:
            return None
        op = j.get('op')
        pid = str(j.get('patch_id'))
        man = load_manifest()
        if MANIFEST_LOCK:
            return {'action': 'blocked', 'patch_id': pid, 'error': MANIFEST_LOCK}
        if op == 'apply':
            if pid in {str(a.get('patch_id')) for a in man.get('applied', [])}:
                _clear_journal()
                return {'action': 'apply-committed', 'patch_id': pid}
            log('CRASH RECOVERY: незавершённый apply патча ' + pid + ' — возвращаю файлы к состоянию до патча', 'WARNING')
            return _recover_apply(j)
        if op == 'rollback':
            last = man['applied'][-1] if man.get('applied') else None
            if last is None or str(last.get('patch_id')) != pid:
                _clear_journal()
                return {'action': 'rollback-stale', 'patch_id': pid}
            log('CRASH RECOVERY: незавершённый rollback патча ' + pid + ' — завершаю восстановление', 'WARNING')
            return _rollback_locked(resume_journal=True)
        JOURNAL_LOCK = 'неизвестная операция crash-журнала: ' + str(op)
        log('CRASH RECOVERY: неизвестный тип журнала (' + str(op) + ') — новые записи заблокированы', 'ERROR')
        return {'action': 'blocked', 'patch_id': pid, 'error': JOURNAL_LOCK}


def force_unlock_manifest():
    # B52 FIX (P1-05): управляемая процедура восстановления после повреждения манифеста
    global MANIFEST_LOCK
    with TX_LOCK:
        fresh = {'applied': [], 'history': [], 'rollbacks': []}
        try:
            save_manifest(fresh)
        except Exception as e:
            log('MANIFEST RESET failed: ' + str(e), 'ERROR')
            return {'success': False, 'error': 'Не удалось сбросить манифест: ' + str(e)}
        MANIFEST_LOCK = ''
        log('MANIFEST RESET: история патчей начата заново, повреждённая копия сохранена рядом', 'WARNING')
        return {'success': True, 'message': 'Манифест сброшен до пустого; повреждённая копия сохранена рядом (patch_manifest.json.corrupt). История патчей начата заново.'}


def stats():
    ps = list_patches()
    man = load_manifest()
    ap = len([p for p in ps if p['is_applied']])
    load_journal()
    return {'total': len(ps), 'applied': ap, 'pending': len(ps) - ap, 'version': _ENGINE_VERSION,
            'errors': len([p for p in ps if p.get('error')]),
            'multi_count': len([p for p in ps if p.get('multi')]),
            'history_count': len(man.get('history', [])),
            'rollbacks_count': len(man.get('rollbacks', [])),
            'backups_count': len(os.listdir(BACKUP_DIR)),
            'locked': bool(MANIFEST_LOCK or JOURNAL_LOCK),
            'journal_locked': bool(JOURNAL_LOCK),
            'journal_lock_reason': JOURNAL_LOCK}
