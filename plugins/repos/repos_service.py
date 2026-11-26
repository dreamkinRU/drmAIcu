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
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from . import git_service

READ_FILE_MAX_BYTES = 512_000
LOG_LIMIT_MAX = 200


def _r(args, path=None, timeout=git_service.DEFAULT_TIMEOUT):
    return git_service.run_git(args, cwd=path, timeout=timeout)


def repo_sync_snapshot(path):
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
    for rel in files:
        full = os.path.join(path, rel)
        digest.update(rel.encode('utf-8', errors='surrogatepass'))
        digest.update(b'\0')
        try:
            info = os.lstat(full)
        except FileNotFoundError:
            digest.update(b'DELETED\0')
            continue
        if stat.S_ISLNK(info.st_mode):
            digest.update(b'LINK\0')
            digest.update(os.readlink(full).encode('utf-8', errors='surrogatepass'))
        elif stat.S_ISREG(info.st_mode):
            digest.update(('MODE:%s:' % stat.S_IMODE(info.st_mode)).encode('ascii'))
            digest.update(b'FILE\0')
            with open(full, 'rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
        elif stat.S_ISDIR(info.st_mode):
            digest.update(b'DIR\0')
            if os.path.exists(os.path.join(full, '.git')):
                sub_head = _r(['rev-parse', 'HEAD'], full)
                sub_status = _r(['status', '--porcelain=v1', '-z'], full)
                digest.update(sub_head.get('stdout', '').strip().encode('ascii', errors='ignore'))
                digest.update(sub_status.get('stdout', '').encode('utf-8', errors='replace'))
        else:
            digest.update(('MODE:%s\0' % info.st_mode).encode('ascii'))
    return {'ok': True, 'snapshot': digest.hexdigest(), 'files': files}


def repo_status(path):
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
    r = _r(['log', '-n', str(limit), '--pretty=format:%H%x1f%an%x1f%aI%x1f%s'], path)
    if not r['ok']:
        return {'ok': False, 'error': r['stderr'].strip() or 'git log failed'}
    commits = []
    for line in r['stdout'].splitlines():
        parts = line.split('\x1f')
        if len(parts) == 4:
            commits.append({'sha': parts[0][:10], 'author': parts[1], 'date': parts[2], 'subject': parts[3]})
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


def repo_diff(path, staged=False):
    validate(path)
    args = ['diff', '--stat'] if not staged else ['diff', '--cached', '--stat']
    r = _r(args, path)
    if not r['ok']:
        return {'ok': False, 'error': r['stderr'].strip() or 'git diff failed'}
    return {'ok': True, 'staged': bool(staged), 'stat': r['stdout'][-git_service.DIFF_MAX_CHARS:]}


def read_file(path, rel, max_bytes=READ_FILE_MAX_BYTES):
    """Чтение файла репозитория с защитой от выхода за пределы каталога."""
    validate(path)
    if not rel or rel.startswith('/') or '..' in os.path.normpath(rel).split(os.sep) or '\\' in str(rel):
        return {'ok': False, 'error': 'недопустимый путь файла'}
    full = os.path.normpath(os.path.join(path, rel))
    root_real = os.path.realpath(path)
    full_real = os.path.realpath(full)
    try:
        inside = os.path.commonpath([root_real, full_real]) == root_real
    except ValueError:
        inside = False
    if not inside:
        return {'ok': False, 'error': 'путь вне репозитория (включая symbolic link)'}
    if not os.path.isfile(full_real):
        return {'ok': False, 'error': 'файл не найден: %s' % rel}
    try:
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(full_real, flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                return {'ok': False, 'error': 'допускается чтение только обычных файлов'}
            if info.st_size > max_bytes:
                return {'ok': False, 'error': 'файл слишком большой (%d байт, лимит %d)' % (info.st_size, max_bytes)}
            with os.fdopen(fd, 'rb') as f:
                fd = None
                data = f.read(max_bytes + 1)
        finally:
            if fd is not None:
                os.close(fd)
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
        rc = repo_commit(path, msg)
        steps.append({'step': 'commit', **{k: v for k, v in rc.items() if k in ('ok', 'sha', 'error')}})
        if not rc.get('ok'):
            return {'ok': False, 'error': rc.get('error', 'git commit failed'), 'steps': steps}
    else:
        steps.append({'step': 'add', 'ok': True, 'skipped': True, 'note': 'изменений нет'})

    rp = repo_pull(path, rebase=True)
    steps.append({'step': 'pull --rebase', **{k: v for k, v in rp.items() if k in ('ok', 'error')}})
    if not rp.get('ok'):
        return {'ok': False, 'error': rp.get('error', 'pull failed'),
                'rebase_conflict': rp.get('rebase_conflict', False), 'steps': steps}

    merged = last_merged_pr(path)
    steps.append({'step': 'merged_pr_check', 'ok': True, 'last_merged': merged})

    rpush = repo_push(path)
    steps.append({'step': 'push', **{k: v for k, v in rpush.items() if k in ('ok', 'branch', 'remote', 'error')}})
    if not rpush.get('ok'):
        return {'ok': False, 'error': rpush.get('error', 'push failed'),
                'push_rejected': rpush.get('rejected', False), 'steps': steps}

    r = _r(['log', '-1', '--oneline'], path)
    return {'ok': True, 'steps': steps, 'head': r.get('stdout', '').strip(),
            'committed': changes, 'commit_sha': steps[-4]['sha'] if (changes and len(steps) >= 4) else None}


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
        sensitive = ('token', 'access_token', 'password', 'passwd', 'auth', 'key', 'secret')
        query = [
            (key, '***' if any(word in key.lower() for word in sensitive) else val)
            for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        ]
        return urlunsplit((parsed.scheme, netloc, parsed.path, urlencode(query), parsed.fragment))
    except (ValueError, TypeError):
        return '[remote URL скрыт]'


def validate(path):
    git_service.validate_repo_path(path)


def diagnostics():
    return {'git': git_service.is_git_available(), 'version': git_service.git_version()}
