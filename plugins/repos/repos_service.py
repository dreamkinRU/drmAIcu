"""Операции с локальными и сетевыми git-репозиториями (замена sync.bat + GitHub Desktop).

Полная последовательность Sync повторяет repo `sync.bat`:
  git add -A -> (есть staged? -> commit -m <msg>) -> git pull --rebase origin <ветка>
  -> push origin <ветка>.
Отличия документированы и честные: ветка не хардкодится как `main`, а берётся
текущая (или её upstream), проверка merged PR выполняется через локальный
`git log --grep="Merge pull request #"`. Любая ошибка возвращается структурой,
никогда не превращается в fake-успех.
"""
import os
import stat
import hashlib
import ntpath
import difflib
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from . import git_service

READ_FILE_MAX_BYTES = 512_000
SYNC_PREVIEW_MAX_CHARS = 1_000_000
LOG_LIMIT_MAX = 200


def _r(args, path=None, timeout=git_service.DEFAULT_TIMEOUT):
    return git_service.run_git(args, cwd=path, timeout=timeout)


def repo_sync_snapshot(path):
    with git_service.repo_operation_lock(path):
        return _repo_sync_snapshot_locked(path)


def _repo_sync_snapshot_locked(path):
    """Хэширует текущее содержимое изменённых/новых файлов для подтверждения Sync."""
    validate(path)
    commands = (
        ['diff', '--name-only', '-z', '--no-renames'],
        ['diff', '--cached', '--name-only', '-z', '--no-renames'],
        ['ls-files', '--others', '--exclude-standard', '-z'],
    )
    names = set()
    for args in commands:
        result = _r(args, path)
        if not result['ok']:
            return {'ok': False, 'error': result['stderr'].strip() or 'cannot build sync snapshot'}
        names.update(os.fsdecode(item) for item in result['stdout'].split('\0') if item)
    branch = _r(['rev-parse', '--abbrev-ref', 'HEAD'], path)
    head = _r(['rev-parse', 'HEAD'], path)
    upstream = _r(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], path)
    remotes = _r(['remote', '-v'], path)
    digest = hashlib.sha256()
    digest.update((branch.get('stdout', '').strip() + '\0').encode('utf-8'))
    digest.update((head.get('stdout', '').strip() + '\0').encode('ascii', errors='ignore'))
    digest.update((upstream.get('stdout', '').strip() + '\0').encode('utf-8'))
    # Сырые URL участвуют только в хэше: в snapshot/ответ API они не возвращаются.
    digest.update(remotes.get('stdout', '').encode('utf-8', errors='replace'))
    files = sorted(names)
    root = os.path.realpath(path)
    for rel in files:
        if not isinstance(rel, str) or rel.startswith('/') or '\\' in rel or ntpath.splitdrive(rel)[0]:
            return {'ok': False, 'error': 'unsafe path returned by Git status'}
        parts = rel.split('/')
        if any(part in ('', '.', '..') for part in parts):
            return {'ok': False, 'error': 'unsafe path returned by Git status'}
        digest.update(rel.encode('utf-8', errors='surrogatepass'))
        digest.update(b'\0')
        full = root
        try:
            for index, part in enumerate(parts):
                full = os.path.join(full, part)
                info = os.lstat(full)
                reparse = bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
                if stat.S_ISLNK(info.st_mode) or reparse:
                    if index != len(parts) - 1:
                        return {'ok': False, 'error': 'symlink/reparse parent in changed path'}
                    digest.update(b'LINK\0')
                    digest.update(os.readlink(full).encode('utf-8', errors='surrogatepass'))
                    break
            else:
                if stat.S_ISREG(info.st_mode):
                    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
                    fd = os.open(full, flags)
                    try:
                        opened = os.fstat(fd)
                        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                            return {'ok': False, 'error': 'changed file was replaced while building snapshot'}
                        digest.update(('MODE:%s:' % stat.S_IMODE(opened.st_mode)).encode('ascii'))
                        digest.update(b'FILE\0')
                        while True:
                            chunk = os.read(fd, 1024 * 1024)
                            if not chunk:
                                break
                            digest.update(chunk)
                    finally:
                        os.close(fd)
                elif stat.S_ISDIR(info.st_mode):
                    digest.update(b'DIR\0')
                    if os.path.exists(os.path.join(full, '.git')):
                        sub_head = _r(['rev-parse', 'HEAD'], full)
                        sub_status = _r(['status', '--porcelain=v1', '-z'], full)
                        digest.update(sub_head.get('stdout', '').strip().encode('ascii', errors='ignore'))
                        digest.update(sub_status.get('stdout', '').encode('utf-8', errors='replace'))
                else:
                    digest.update(('MODE:%s\0' % info.st_mode).encode('ascii'))
        except FileNotFoundError:
            digest.update(b'DELETED\0')
    return {'ok': True, 'snapshot': digest.hexdigest(), 'files': files}


def repo_status(path):
    with git_service.repo_operation_lock(path):
        return _repo_status_locked(path)


def _repo_status_locked(path):
    """status --porcelain=v1 -b + ahead/behind/branch/upstream."""
    validate(path)
    r = _r(['status', '--porcelain=v1', '-b'], path)
    if not r['ok']:
        return {'ok': False, 'error': r['stderr'].strip() or 'git status failed'}
    lines = r['stdout'].splitlines()
    branch = ''
    upstream = ''
    ahead = 0
    behind = 0
    if lines and lines[0].startswith('##'):
        head = lines[0][2:].strip()
        # примеры: 'main...origin/main [ahead 1, behind 2]', 'main', '## No commits yet on main'
        if '...' in head:
            branch, rest = head.split('...', 1)
            ups = rest.split(' ', 1)
            upstream = ups[0]
            if len(ups) > 1:
                for tok in ups[1].replace('[', ' ').replace(']', ' ').split(','):
                    tok = tok.strip()
                    if tok.startswith('ahead'):
                        ahead = int(tok.split()[1])
                    elif tok.startswith('behind'):
                        behind = int(tok.split()[1])
        else:
            branch = head.replace('No commits yet on ', '')
    entries = []
    for line in lines[1:]:
        code = line[:2]
        file = line[3:]
        entries.append({'code': code, 'file': file,
                        'staged': code[0] not in (' ', '?'),
                        'unstaged': code[1] != ' ' if code[0] != '?' else True})
    snapshot = repo_sync_snapshot(path)
    if not snapshot.get('ok'):
        return {'ok': False, 'error': snapshot.get('error', 'cannot build repository snapshot')}
    return {'ok': True, 'path': path, 'branch': branch, 'upstream': upstream,
            'ahead': ahead, 'behind': behind,
            'changed': bool(entries), 'entries': entries,
            'snapshot': snapshot['snapshot'], 'snapshot_files': snapshot['files']}


def repo_log(path, limit=30):
    validate(path)
    limit = max(1, min(int(limit or 30), LOG_LIMIT_MAX))
    # %x1e (RS) разделяет записи коммитов, %x1f (US) — поля внутри записи. Так формат
    # выдерживает многострочный %b (тело коммита): строки тела не ломают разбиение,
    # потому что границы записей ищутся только по %x1e, а не по началу строки.
    r = _r(['log', '-n', str(limit), '--pretty=format:%x1e%H%x1f%an%x1f%aI%x1f%s%x1f%b'], path)
    if not r['ok']:
        return {'ok': False, 'error': r['stderr'].strip() or 'git log failed'}
    commits = []
    for rec in r['stdout'].split('\x1e'):
        parts = rec.split('\x1f', 4)
        if len(parts) == 5:
            commits.append({
                'sha': parts[0][:10], 'author': parts[1], 'date': parts[2],
                'subject': parts[3], 'body': parts[4].strip(),
            })
    return {'ok': True, 'commits': commits}


def repo_branches(path):
    validate(path)
    r = _r(['branch', '--all', '--format=%(refname:short)%09%(objectname:short)%09%(HEAD)'], path)
    if not r['ok']:
        return {'ok': False, 'error': r['stderr'].strip() or 'git branch failed'}
    current = ''
    branches = []
    for line in r['stdout'].splitlines():
        name, _, rest = line.partition('\t')
        if not name:
            continue
        parts = rest.split('\t')
        sha = parts[0] if parts else ''
        is_head = bool(parts[1] if len(parts) > 1 else '') or '*' in name
        clean = name.replace('* ', '').replace('remotes/', '', 1) if name.startswith('remotes/') else name
        clean = clean.replace('* ', '').strip()
        if is_head and not current:
            current = clean
        branches.append({'name': clean, 'sha': sha, 'head': is_head,
                         'remote': name.startswith('remotes/')})
    return {'ok': True, 'current': current, 'branches': branches}


def repo_remote(path):
    validate(path)
    r = _r(['remote', '-v'], path)
    if not r['ok']:
        return {'ok': False, 'error': r['stderr'].strip() or 'git remote failed'}
    remotes = []
    seen = set()
    for line in r['stdout'].splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] not in seen:
            seen.add(parts[0])
            remotes.append({'name': parts[0], 'url': _sanitize_remote_url(parts[1])})
    return {'ok': True, 'remotes': remotes}


def repo_patch_status(path):
    """Мост к PATCHMASTER (только чтение, Этап 5): последние применённые патчи,
    незавершённая транзакция (crash-журнал) и файлы патчей, ещё не попавшие в
    коммит/Sync. PATCHMASTER остаётся единственным писателем исходников —
    Repos Plugin файлы не пишет и apply_patch не вызывает."""
    with git_service.repo_operation_lock(path):
        return _repo_patch_status_locked(path)


def _repo_patch_status_locked(path):
    validate(path)
    try:
        import patch_engine as pe
    except Exception as e:
        return {'ok': False,
                'error': 'PATCHMASTER недоступен: %s. Путь исправления: проверьте наличие patch_engine.py в корне проекта и перезапустите панель.' % e}
    man = pe.load_manifest()
    journal = pe.load_journal()

    applied = []
    for rec in (man.get('applied') or [])[-10:]:
        if not isinstance(rec, dict):
            continue
        applied.append({
            'patch_id': str(rec.get('patch_id', '')),
            'target_file': str(rec.get('target_file', '')),
            'files': [str(op.get('target_file', '')) for op in (rec.get('operations') or [])
                      if isinstance(op, dict) and op.get('target_file')],
            'applied_at': str(rec.get('applied_at', '')),
        })

    in_progress = None
    if isinstance(journal, dict) and journal.get('op') == 'apply':
        in_progress = {'patch_id': str(journal.get('patch_id', '')),
                       'files': [str(st.get('tgt', '')) for st in (journal.get('steps') or [])
                                 if isinstance(st, dict) and st.get('tgt')]}

    journal_lock_reason = str(getattr(pe, 'JOURNAL_LOCK', '') or '')
    if journal is not None and not journal_lock_reason:
        journal_lock_reason = 'незавершённая транзакция требует recover_journal()'
    engine_blocked = bool(getattr(pe, 'MANIFEST_LOCK', '') or journal_lock_reason or journal is not None)

    # Файлы патчей, ещё не закоммиченные в ЭТОМ репозитории (только если
    # path — корень drmAIcu: патчи применяются к самому проекту).
    unsynced = []
    changed = None
    if os.path.realpath(path) == os.path.realpath(pe.BASE):
        st = _repo_status_locked(path)
        if st.get('ok'):
            changed = bool(st.get('changed'))
            patch_files = set()
            for rec in applied:
                patch_files.update(rec['files'])
            if patch_files:
                status_files = set(st.get('snapshot_files') or [])
                unsynced = sorted(patch_files & status_files)

    return {'ok': True, 'path': path,
            'engine_blocked': engine_blocked,
            'journal_lock_reason': journal_lock_reason,
            'applied': applied,
            'in_progress': in_progress,
            'unsynced_files': unsynced,
            'changed': changed}


def repo_sync_preview(path):
    """Возвращает полный review diff и snapshot, не изменяя Git index/worktree."""
    with git_service.repo_operation_lock(path):
        return _repo_sync_preview_locked(path)


def _repo_sync_preview_locked(path):
    # Обновляем remote-tracking refs, чтобы ahead/behind и список входящих
    # коммитов были актуальными. Fetch меняет только .git refs, не рабочее
    # дерево; при отсутствии сети/доступа preview продолжается с устаревшими
    # данными (fetch_ok=False — честная пометка в UI).
    fetch_r = _r(['fetch', '--all', '--prune'], path, timeout=git_service.PUSH_TIMEOUT)
    fetch_ok = bool(fetch_r.get('ok'))
    fetch_error = '' if fetch_ok else (fetch_r.get('stderr', '').strip() or 'git fetch failed')[-500:]

    status = _repo_status_locked(path)
    if not status.get('ok'):
        return status

    # ahead/behind точно по upstream (status -b может быть неточен без fetch)
    ahead = status.get('ahead', 0)
    behind = status.get('behind', 0)
    incoming = []
    upstream = status.get('upstream') or ''
    if upstream:
        count = _r(['rev-list', '--left-right', '--count', 'HEAD...%s' % upstream], path)
        if count.get('ok'):
            parts = count.get('stdout', '').split()
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                ahead, behind = int(parts[0]), int(parts[1])
        incoming_r = _r(['log', '--pretty=format:%h%x09%s', '-n', '20', 'HEAD..%s' % upstream], path)
        if incoming_r.get('ok'):
            for line in incoming_r.get('stdout', '').splitlines():
                if line.strip():
                    sha, _, subj = line.partition('\t')
                    incoming.append({'sha': sha.strip(), 'subject': subj.strip()})

    tracked = _r([
        'diff', '--no-ext-diff', '--no-textconv', '--no-color',
        '--binary', '--full-index', 'HEAD', '--',
    ], path)
    if not tracked.get('ok'):
        return {'ok': False, 'error': tracked.get('stderr', '').strip() or 'cannot build tracked diff'}

    untracked_result = _r(['ls-files', '--others', '--exclude-standard', '-z'], path)
    if not untracked_result.get('ok'):
        return {'ok': False, 'error': untracked_result.get('stderr', '').strip() or 'cannot list untracked files'}

    diff_text = tracked.get('stdout', '')
    truncated = len(diff_text) > SYNC_PREVIEW_MAX_CHARS
    if truncated:
        diff_text = diff_text[:SYNC_PREVIEW_MAX_CHARS]
    omitted = []
    root = os.path.realpath(path)

    def append_chunk(chunk):
        nonlocal diff_text, truncated
        remaining = SYNC_PREVIEW_MAX_CHARS - len(diff_text)
        if remaining <= 0:
            truncated = True
            return False
        if len(chunk) > remaining:
            diff_text += chunk[:remaining]
            truncated = True
            return False
        diff_text += chunk
        return True

    for rel in sorted(item for item in untracked_result['stdout'].split('\0') if item):
        if truncated:
            break
        if (rel.startswith('/') or '\\' in rel or ntpath.splitdrive(rel)[0]
                or any(part in ('', '.', '..') for part in rel.split('/'))):
            return {'ok': False, 'error': 'unsafe untracked path returned by Git'}
        full = os.path.join(root, *rel.split('/'))
        try:
            info = os.lstat(full)
            reparse = bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
            if stat.S_ISLNK(info.st_mode) or reparse:
                target = os.readlink(full)
                if not append_chunk(
                    'diff --git a/%s b/%s\nnew file mode 120000\n--- /dev/null\n+++ b/%s\n+%s\n'
                    % (rel, rel, rel, target)
                ):
                    break
                continue
            if not stat.S_ISREG(info.st_mode):
                omitted.append({'path': rel, 'reason': 'тип файла не поддерживается для текстового preview'})
                continue
        except FileNotFoundError:
            omitted.append({'path': rel, 'reason': 'файл исчез во время построения preview'})
            continue
        except OSError as e:
            omitted.append({'path': rel, 'reason': 'не удалось проверить файл: %s' % e})
            continue

        content = read_file(path, rel)
        if not content.get('ok'):
            omitted.append({'path': rel, 'reason': content.get('error', 'файл не прочитан')})
            continue
        text = content.get('content', '')
        if '\0' in text:
            if not append_chunk(
                'diff --git a/%s b/%s\nnew file mode 100644\nBinary file omitted from text preview\n'
                % (rel, rel)
            ):
                break
            omitted.append({'path': rel, 'reason': 'binary file'})
            continue
        lines = text.splitlines(keepends=True)
        patch = ''.join(difflib.unified_diff(
            [], lines, fromfile='/dev/null', tofile='b/' + rel,
        ))
        if not append_chunk('diff --git a/%s b/%s\nnew file mode 100644\n%s' % (rel, rel, patch)):
            break

    stat_result = _r(['diff', '--stat', 'HEAD', '--'], path)
    final_snapshot = repo_sync_snapshot(path)
    if not final_snapshot.get('ok') or final_snapshot.get('snapshot') != status.get('snapshot'):
        return {
            'ok': False,
            'error': 'репозиторий изменился во время построения diff preview. Обновите preview и повторите.',
            'snapshot_changed': True,
        }
    return {
        'ok': True,
        'path': path,
        'branch': status.get('branch', ''),
        'upstream': status.get('upstream', ''),
        'snapshot': status['snapshot'],
        'snapshot_files': status['snapshot_files'],
        'changed': status.get('changed', False),
        'fetch_ok': fetch_ok,
        'fetch_error': fetch_error,
        'ahead': ahead,
        'behind': behind,
        'incoming': incoming,
        'stat': stat_result.get('stdout', '').strip() if stat_result.get('ok') else '',
        'diff': diff_text,
        'truncated': truncated,
        'omitted_files': omitted,
        'complete': not truncated and not omitted,
    }


def repo_diff(path, staged=False):
    validate(path)
    args = ['diff', '--stat'] if not staged else ['diff', '--cached', '--stat']
    r = _r(args, path)
    if not r['ok']:
        return {'ok': False, 'error': r['stderr'].strip() or 'git diff failed'}
    return {'ok': True, 'staged': bool(staged), 'stat': r['stdout'][-git_service.DIFF_MAX_CHARS:]}


def read_file(path, rel, max_bytes=READ_FILE_MAX_BYTES):
    """Чтение обычного файла без перехода через symlink/reparse components."""
    validate(path)
    if (not isinstance(rel, str) or not rel or rel.startswith('/') or '\\' in rel
            or ntpath.splitdrive(rel)[0] or '\x00' in rel
            or (os.name == 'nt' and ':' in rel)
            or any(p in ('', '.', '..') for p in rel.split('/'))):
        return {'ok': False, 'error': 'недопустимый путь файла'}
    if not isinstance(max_bytes, int) or max_bytes < 1:
        return {'ok': False, 'error': 'недопустимый лимит размера файла'}
    root_real = os.path.realpath(path)
    full = root_real
    try:
        parts = rel.split('/')
        for index, part in enumerate(parts):
            full = os.path.join(full, part)
            info = os.lstat(full)
            reparse = bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
            if stat.S_ISLNK(info.st_mode) or reparse:
                return {'ok': False, 'error': 'чтение через symbolic link/reparse point запрещено'}
            if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
                return {'ok': False, 'error': 'родительский компонент пути не является каталогом'}
        if not stat.S_ISREG(info.st_mode):
            return {'ok': False, 'error': 'допускается чтение только обычных файлов'}
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(full, flags)
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                return {'ok': False, 'error': 'файл был заменён во время безопасного открытия'}
            if opened.st_size > max_bytes:
                return {'ok': False, 'error': 'файл слишком большой (%d байт, лимит %d)' % (opened.st_size, max_bytes)}
            data = os.read(fd, max_bytes + 1)
        finally:
            os.close(fd)
    except FileNotFoundError:
        return {'ok': False, 'error': 'файл не найден: %s' % rel}
    except OSError as e:
        return {'ok': False, 'error': 'не удалось безопасно открыть файл: %s' % e}
    if len(data) > max_bytes:
        return {'ok': False, 'error': 'файл слишком большой (лимит %d байт)' % max_bytes}
    size = len(data)
    try:
        text = data.decode('utf-8')
        encoding = 'utf-8'
    except UnicodeDecodeError:
        text = data.decode('cp1251', errors='replace')
        encoding = 'cp1251'
    return {'ok': True, 'path': rel, 'size': size, 'encoding': encoding, 'content': text}


def current_branch(path):
    r = _r(['rev-parse', '--abbrev-ref', 'HEAD'], path)
    if not r['ok']:
        return None
    return r['stdout'].strip() or None


def upstream_of(path, branch):
    r = _r(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], path)
    if r['ok'] and r['stdout'].strip():
        up = r['stdout'].strip()  # напр. 'origin/main'
        if '.' in up or up.count('/') >= 1:
            return up.rsplit('/', 1)
    return ('origin', branch)


def repo_add(path):
    validate(path)
    r = _r(['add', '-A'], path)
    if not r['ok']:
        return {'ok': False, 'error': r['stderr'].strip() or 'git add failed'}
    return {'ok': True, 'staged': True}


def repo_commit(path, message):
    validate(path)
    if not message or not str(message).strip():
        return {'ok': False, 'error': 'требуется сообщение коммита — пустой коммит отклонён (как в sync.bat). Путь исправления: введите осмысленное сообщение в поле «Сообщение коммита» над кнопками git add -A / commit / push и повторите commit.'}
    r = _r(['commit', '-m', str(message).strip()], path)
    if not r['ok']:
        err = r['stderr'].strip() or r['stdout'].strip() or 'git commit failed'
        if 'nothing to commit' in err:
            return {'ok': False, 'error': 'нечего коммитить (изменения отсутствуют)', 'nothing_to_commit': True}
        return {'ok': False, 'error': err}
    sha_r = _r(['rev-parse', '--short', 'HEAD'], path)
    return {'ok': True, 'sha': sha_r.get('stdout', '').strip() or None, 'message': str(message).strip()}


def repo_pull(path, rebase=True):
    validate(path)
    branch = current_branch(path)
    remote, rb = upstream_of(path, branch or 'main')
    args = ['pull'] + (['--rebase'] if rebase else []) + [remote, rb]
    r = _r(args, path, timeout=git_service.PUSH_TIMEOUT)
    if not r['ok']:
        err = (r['stderr'].strip() or r['stdout'].strip() or 'git pull failed')[-1500:]
        if 'conflict' in err.lower() or 'Could not apply' in err or 'unmerged' in err.lower():
            return {'ok': False, 'rebase_conflict': True,
                    'error': 'конфликт при pull --rebase. Решите конфликты, затем: git add -A && git rebase --continue (как в sync.bat)',
                    'details': err}
        return {'ok': False, 'error': err}
    return {'ok': True, 'output': (r['stdout'] or r['stderr'] or '')[-1500:], 'rebase': bool(rebase)}


def repo_push(path):
    validate(path)
    branch = current_branch(path)
    remote, rb = upstream_of(path, branch or 'main')
    r = _r(['push', remote, rb], path)
    if not r['ok']:
        err = (r['stderr'].strip() or r['stdout'].strip() or 'git push failed')[-1500:]
        if 'rejected' in err.lower():
            return {'ok': False, 'rejected': True,
                    'error': 'push отклонён — на сервере есть новые коммиты. Путь исправления: вкладка «Репозитории» → «Обзор» → кнопка «pull --rebase» или «Синхронизировать», затем повторите push',
                    'details': err}
        return {'ok': False, 'error': err}
    return {'ok': True, 'branch': rb, 'remote': remote, 'output': (r['stderr'] or r['stdout'] or '')[-1500:]}


def repo_fetch(path):
    validate(path)
    r = _r(['fetch', '--all', '--prune'], path, timeout=git_service.PUSH_TIMEOUT)
    if not r['ok']:
        return {'ok': False, 'error': (r['stderr'].strip() or 'git fetch failed')[-1500:]}
    return {'ok': True, 'output': (r['stderr'] or r['stdout'] or '')[-1500:]}


def repo_checkout(path, branch, create=False):
    validate(path)
    if not branch or not str(branch).strip():
        return {'ok': False, 'error': 'требуется имя ветки'}
    clean = str(branch).strip()
    if clean.startswith('remotes/origin/'):
        clean = clean[len('remotes/origin/'):]
    if clean.startswith('-'):
        return {'ok': False, 'error': 'имя ветки не может начинаться с дефиса'}
    check = _r(['check-ref-format', '--branch', clean], path)
    if not check['ok']:
        return {'ok': False, 'error': 'недопустимое имя ветки: %s' % clean}
    args = ['checkout'] + (['-b'] if create else []) + [clean]
    r = _r(args, path)
    if not r['ok']:
        return {'ok': False, 'error': (r['stderr'].strip() or 'git checkout failed')[-1500:]}
    return {'ok': True, 'branch': clean, 'created': bool(create)}


def repo_sync(path, message, expected_snapshot=None):
    """Одна sync-сессия под общей блокировкой drmAIcu; внешние Git CLI не обязаны её соблюдать."""
    validate(path)
    with git_service.repo_operation_lock(path):
        return _repo_sync_locked(path, message, expected_snapshot)


def _repo_sync_locked(path, message, expected_snapshot=None):
    """Sync выполняется только если рабочие файлы совпадают с подтверждённым snapshot."""
    validate(path)
    steps = []
    st = repo_status(path)
    if not st.get('ok'):
        return {'ok': False, 'error': st.get('error', 'git status failed'), 'steps': []}
    if expected_snapshot is None:
        expected_snapshot = st.get('snapshot')
    if not expected_snapshot or st.get('snapshot') != expected_snapshot:
        return {'ok': False,
                'error': 'рабочие файлы изменились после предварительного просмотра. Обновите статус и подтвердите Sync заново.',
                'snapshot_changed': True, 'steps': [],
                'expected_snapshot': expected_snapshot, 'actual_snapshot': st.get('snapshot')}

    changes = st.get('changed', False)
    steps.append({'step': 'status', 'ok': True, 'changed': changes, 'branch': st.get('branch')})

    if changes:
        msg = (message or '').strip() if message else ''
        if not msg:
            return {'ok': False,
                    'error': 'есть незакоммиченные изменения — требуется сообщение коммита (как в sync.bat: пустое сообщение отклоняется). Путь исправления: введите сообщение коммита в поле над кнопкой «Синхронизировать» и повторите — sync сам выполнит add -A → commit → pull --rebase → push',
                    'steps': steps}
        ra = repo_add(path)
        steps.append({'step': 'add', **ra})
        if not ra.get('ok'):
            return {'ok': False, 'error': ra.get('error', 'git add failed'), 'steps': steps}
        after_add = repo_sync_snapshot(path)
        if not after_add.get('ok') or after_add.get('snapshot') != expected_snapshot:
            return {'ok': False,
                    'error': 'содержимое изменилось во время git add. Коммит и push отменены; проверьте staged changes и повторите Sync.',
                    'snapshot_changed': True, 'steps': steps}
        staged_tree = _r(['write-tree'], path)
        if not staged_tree.get('ok'):
            return {'ok': False, 'error': staged_tree.get('stderr', '').strip() or 'cannot snapshot staged Git tree', 'steps': steps}
        expected_tree = staged_tree.get('stdout', '').strip()
        precommit_tree = _r(['write-tree'], path)
        if not precommit_tree.get('ok') or precommit_tree.get('stdout', '').strip() != expected_tree:
            return {'ok': False,
                    'error': 'Git index изменился перед commit. Коммит и push отменены; повторите Sync после обновления preview.',
                    'snapshot_changed': True, 'steps': steps}
        rc = repo_commit(path, msg)
        steps.append({'step': 'commit', **{k: v for k, v in rc.items() if k in ('ok', 'sha', 'error')}})
        if not rc.get('ok'):
            return {'ok': False, 'error': rc.get('error', 'git commit failed'), 'steps': steps}
        committed_tree = _r(['rev-parse', 'HEAD^{tree}'], path)
        if not committed_tree.get('ok') or committed_tree.get('stdout', '').strip() != expected_tree:
            return {'ok': False,
                    'error': 'Commit создан, но его tree не совпадает с подтверждённым staged tree. Push заблокирован; проверьте локальный commit и повторите preview.',
                    'commit_tree_mismatch': True, 'steps': steps}
    else:
        steps.append({'step': 'add', 'ok': True, 'skipped': True, 'note': 'изменений нет'})

    hb = _r(['rev-parse', 'HEAD'], path)
    head_before = hb.get('stdout', '').strip() if hb.get('ok') else ''

    rp = repo_pull(path, rebase=True)
    steps.append({'step': 'pull --rebase', **{k: v for k, v in rp.items() if k in ('ok', 'error')}})
    if not rp.get('ok'):
        return {'ok': False, 'error': rp.get('error', 'pull failed'),
                'rebase_conflict': rp.get('rebase_conflict', False), 'steps': steps}

    # Что пришло с remote (для честного уведомления «Актуально»): HEAD сдвинулся —
    # перечисляем коммиты между old..new (получено pull --rebase).
    ha = _r(['rev-parse', 'HEAD'], path)
    head_after = ha.get('stdout', '').strip() if ha.get('ok') else ''
    pulled = []
    if head_before and head_after and head_before != head_after:
        gl = _r(['log', '--pretty=format:%h%x09%s', '-n', '20', head_before + '..' + head_after], path)
        if gl.get('ok') and (gl.get('stdout') or '').strip():
            for line in gl['stdout'].strip().splitlines():
                parts = line.split('\t', 1)
                pulled.append({'sha': parts[0], 'subject': parts[1] if len(parts) > 1 else ''})

    merged = last_merged_pr(path)
    steps.append({'step': 'merged_pr_check', 'ok': True, 'last_merged': merged})

    rpush = repo_push(path)
    steps.append({'step': 'push', **{k: v for k, v in rpush.items() if k in ('ok', 'branch', 'remote', 'error')}})
    if not rpush.get('ok'):
        return {'ok': False, 'error': rpush.get('error', 'push failed'),
                'push_rejected': rpush.get('rejected', False), 'steps': steps}

    r = _r(['log', '-1', '--oneline'], path)
    return {'ok': True, 'steps': steps, 'head': r.get('stdout', '').strip(),
            'committed': changes, 'commit_sha': steps[-4]['sha'] if (changes and len(steps) >= 4) else None,
            'pulled': pulled, 'pulled_count': len(pulled)}


def last_merged_pr(path):
    r = _r(['log', '-1', '--grep=Merge pull request #', '--format=%s'], path)
    return (r.get('stdout', '').strip() if r.get('ok') else None) or None


def _sanitize_remote_url(value):
    """Удаляет userinfo и секреты из query string перед выдачей в UI/API."""
    try:
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.netloc:
            return value
        host = parsed.hostname or ''
        if parsed.port:
            host = '%s:%s' % (host, parsed.port)
        netloc = ('***@' if parsed.username is not None or parsed.password is not None else '') + host
        sensitive = ('token', 'access_token', 'password', 'passwd', 'auth', 'key', 'secret', 'signature', 'credential', 'jwt', 'bearer')
        query = [
            (key, '***' if any(word in key.lower() for word in sensitive) else val)
            for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        ]
        return urlunsplit((parsed.scheme, netloc, parsed.path, urlencode(query), ''))
    except (ValueError, TypeError):
        return '[remote URL скрыт]'


def repo_rebase_state(path):
    """Диагностика активного rebase и конфликтующих файлов."""
    validate(path)
    merge = _r(['rev-parse', '--git-path', 'rebase-merge'], path)
    apply = _r(['rev-parse', '--git-path', 'rebase-apply'], path)
    candidates = []
    for result in (merge, apply):
        if result.get('ok') and result.get('stdout', '').strip():
            candidate = result['stdout'].strip()
            if not os.path.isabs(candidate):
                candidate = os.path.join(path, candidate)
            candidates.append(candidate)
    active = any(os.path.isdir(p) for p in candidates)
    if not active:
        return {'ok': True, 'active': False, 'conflicts': []}
    unmerged = _r(['diff', '--name-only', '--diff-filter=U'], path)
    return {'ok': True, 'active': True,
            'conflicts': unmerged.get('stdout', '').splitlines() if unmerged.get('ok') else []}


def repo_rebase_continue(path):
    """Продолжить rebase после ручного разрешения конфликтов (WRITE, с подтверждением)."""
    validate(path)
    state = repo_rebase_state(path)
    if not state.get('active'):
        return {'ok': False, 'error': 'активный rebase не найден. Путь исправления: проверьте репозиторий — операция нужна только после конфликта при pull --rebase.'}
    if state.get('conflicts'):
        return {'ok': False, 'error': 'остались неразрешённые конфликты. Путь исправления: исправьте конфликты в перечисленных файлах, затем выполните git add -A (кнопка add -A) и повторите «rebase --continue».', 'conflicts': state['conflicts']}
    result = _r(['-c', 'core.editor=:', 'rebase', '--continue'], path,
                timeout=git_service.PUSH_TIMEOUT)
    if not result['ok']:
        return {'ok': False, 'error': (result['stderr'] or result['stdout'] or 'rebase --continue failed')[-1500:]}
    return {'ok': True, 'output': (result['stdout'] or result['stderr'])[-1500:]}


def repo_rebase_abort(path):
    """Отменить незавершённый rebase и вернуть репозиторий в состояние до pull (WRITE, с подтверждением)."""
    validate(path)
    state = repo_rebase_state(path)
    if not state.get('active'):
        return {'ok': False, 'error': 'активный rebase не найден. Путь исправления: отмена не требуется — репозиторий не в состоянии rebase.'}
    result = _r(['rebase', '--abort'], path, timeout=git_service.PUSH_TIMEOUT)
    if not result['ok']:
        return {'ok': False, 'error': (result['stderr'] or result['stdout'] or 'rebase --abort failed')[-1500:]}
    return {'ok': True, 'output': (result['stdout'] or result['stderr'])[-1500:]}


def validate(path):
    git_service.validate_repo_path(path)


def diagnostics():
    return {'git': git_service.is_git_available(), 'version': git_service.git_version()}
