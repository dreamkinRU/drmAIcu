"""Операции с локальными и сетевыми git-репозиториями (замена sync.bat + GitHub Desktop).

Полная последовательность Sync повторяет repo `sync.bat`:
  git add -A -> (есть staged? -> commit -m <msg>) -> git pull --rebase origin <ветка>
  -> push origin <ветка>.
Отличия документированы и честные: ветка не хардкодится как `main`, а берётся
текущая (или её upstream), проверка merged PR выполняется через локальный
`git log --grep="Merge pull request #"`. Любая ошибка возвращается структурой,
никогда не превращается в fake-успех.
"""
import hashlib
import os
import re
import stat
import urllib.parse

from . import git_service

READ_FILE_MAX_BYTES = 512_000
LOG_LIMIT_MAX = 200


def _r(args, path=None, timeout=git_service.DEFAULT_TIMEOUT):
    return git_service.run_git(args, cwd=path, timeout=timeout)


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
    return {'ok': True, 'path': path, 'branch': branch, 'upstream': upstream,
            'ahead': ahead, 'behind': behind,
            'changed': bool(entries), 'entries': entries}


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


def _sanitize_remote_url(value):
    """Удалить userinfo и чувствительные query-параметры из URL remote."""
    raw = str(value or '')
    try:
        parsed = urllib.parse.urlsplit(raw)
        if not parsed.scheme or not parsed.netloc:
            return raw
        host = parsed.hostname or ''
        if ':' in host and not host.startswith('['):
            host = '[%s]' % host
        if parsed.port:
            host += ':%d' % parsed.port
        safe_query = [
            (key, '***' if re.search(r'token|key|secret|password|auth', key, re.I) else val)
            for key, val in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        ]
        return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path,
                                        urllib.parse.urlencode(safe_query), parsed.fragment))
    except (ValueError, TypeError):
        return '[remote URL скрыт: некорректный формат]'


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
    root = os.path.realpath(os.path.abspath(path))
    full = os.path.abspath(os.path.join(root, rel))
    fd = -1
    try:
        resolved = os.path.realpath(full, strict=True)
        if os.path.commonpath((root, resolved)) != root:
            return {'ok': False, 'error': 'путь вне репозитория (symlink traversal запрещён)'}
        if os.path.islink(full) or not os.path.isfile(resolved):
            return {'ok': False, 'error': 'файл не найден или является symlink: %s' % rel}
        before = os.stat(resolved, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            return {'ok': False, 'error': 'разрешено читать только обычные файлы'}
        if before.st_size > max_bytes:
            return {'ok': False, 'error': 'файл слишком большой (%d байт, лимит %d)' % (before.st_size, max_bytes)}
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(resolved, flags)
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            return {'ok': False, 'error': 'файл изменился во время проверки; повторите чтение'}
        with os.fdopen(fd, 'rb') as f:
            fd = -1
            data = f.read(max_bytes + 1)
        if len(data) > max_bytes:
            return {'ok': False, 'error': 'файл превысил лимит размера во время чтения'}
        size = len(data)
    except (OSError, ValueError) as e:
        return {'ok': False, 'error': 'не удалось безопасно прочитать файл: %s' % e}
    finally:
        if fd >= 0:
            os.close(fd)
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


def repo_add(path, files=None):
    validate(path)
    args = ['add', '-A']
    if files is not None:
        if not isinstance(files, list) or not files:
            return {'ok': False, 'error': 'список подтверждённых файлов пуст или имеет неверный формат'}
        safe_paths = []
        for rel in files:
            rel = str(rel)
            if not rel or os.path.isabs(rel) or '..' in rel.replace('\\\\', '/').split('/'):
                return {'ok': False, 'error': 'недопустимый путь в списке подтверждённых файлов'}
            safe_paths.append(':(literal)' + rel.replace('\\\\', '/'))
        args += ['--'] + safe_paths
    r = _r(args, path)
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
    clean = str(branch).strip().replace('remotes/origin/', '')
    if clean.startswith('-') or clean.startswith('remotes/'):
        return {'ok': False, 'error': 'недопустимое имя ветки'}
    check = _r(['check-ref-format', '--branch', clean], path)
    if not check['ok']:
        return {'ok': False, 'error': 'недопустимое имя ветки: %s' % clean}
    args = ['checkout'] + (['-b'] if create else []) + ['--', clean]
    r = _r(args, path)
    if not r['ok']:
        return {'ok': False, 'error': (r['stderr'].strip() or 'git checkout failed')[-1500:]}
    return {'ok': True, 'branch': clean, 'created': bool(create)}


def repo_sync_preview(path, expected_files=None):
    """Снимок изменённых файлов для подтверждения Sync."""
    validate(path)
    status = _r(['status', '--porcelain=v1', '-z', '--untracked-files=all'], path)
    if not status['ok']:
        return {'ok': False, 'error': status['stderr'].strip() or 'git status failed'}
    branch = current_branch(path) or ''
    head_result = _r(['rev-parse', 'HEAD'], path)
    head = head_result.get('stdout', '').strip() if head_result.get('ok') else ''
    raw_parts = status['stdout'].split('\0')
    paths = []
    index = 0
    while index < len(raw_parts):
        record = raw_parts[index]
        index += 1
        if len(record) < 4:
            continue
        code, rel = record[:2], record[3:]
        if rel:
            paths.append(rel)
        if 'R' in code or 'C' in code:
            if index < len(raw_parts) and raw_parts[index]:
                paths.append(raw_parts[index])
                index += 1
    current_paths = sorted(set(paths))
    if expected_files is not None:
        expected_paths = sorted(set(str(item) for item in expected_files))
        unexpected = sorted(set(current_paths) - set(expected_paths))
        if unexpected:
            return {'ok': False, 'snapshot_mismatch': True,
                    'error': 'после подтверждения появились новые файлы: %s' % ', '.join(unexpected[:10])}
        unique_paths = expected_paths
    else:
        unique_paths = current_paths
    digest = hashlib.sha256()
    digest.update(b'BRANCH\\x00')
    digest.update(branch.encode('utf-8', errors='replace'))
    digest.update(b'HEAD\\x00')
    digest.update(head.encode('ascii', errors='ignore'))
    upstream = _r(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], path)
    digest.update((upstream.get('stdout', '') if upstream.get('ok') else '').encode('utf-8', errors='replace'))
    remote_config = _r(['remote', '-v'], path)
    digest.update((remote_config.get('stdout', '') if remote_config.get('ok') else '').encode('utf-8', errors='replace'))
    root = os.path.realpath(os.path.abspath(path))
    for rel in unique_paths:
        if os.path.isabs(rel) or '..' in rel.replace('\\\\', '/').split('/'):
            return {'ok': False, 'error': 'Git вернул небезопасный путь в status; Sync остановлен'}
        full = os.path.abspath(os.path.join(root, rel))
        try:
            if os.path.commonpath((root, full)) != root:
                return {'ok': False, 'error': 'изменённый файл находится вне репозитория'}
            info = os.lstat(full)
            digest.update(b'\\x00PATH\\x00')
            digest.update(rel.encode('utf-8', errors='replace'))
            digest.update(str(stat.S_IMODE(info.st_mode)).encode('ascii'))
            if stat.S_ISLNK(info.st_mode):
                digest.update(b'LINK:')
                digest.update(os.readlink(full).encode('utf-8', errors='replace'))
            elif stat.S_ISREG(info.st_mode):
                digest.update(b'FILE:')
                with open(full, 'rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
            elif stat.S_ISDIR(info.st_mode):
                # Submodule: include its own working-tree snapshot, not just the gitlink SHA.
                try:
                    nested = repo_sync_preview(full)
                except Exception as e:
                    return {'ok': False, 'error': 'не удалось проверить submodule %s: %s' % (rel, e)}
                if not nested.get('ok'):
                    return {'ok': False, 'error': 'не удалось проверить submodule %s: %s' % (rel, nested.get('error', 'unknown error'))}
                digest.update(b'SUBMODULE:')
                digest.update(nested['snapshot'].encode('ascii'))
            else:
                digest.update(b'OTHER:')
        except FileNotFoundError:
            digest.update(rel.encode('utf-8', errors='replace'))
            digest.update(b'DELETED')
        except (OSError, ValueError) as e:
            return {'ok': False, 'error': 'не удалось зафиксировать снимок %s: %s' % (rel, e)}
    diff = _r(['diff', '--stat', 'HEAD'], path)
    if not diff['ok']:
        diff = _r(['diff', '--stat'], path)
    return {'ok': True, 'snapshot': digest.hexdigest(), 'files': unique_paths,
            'branch': branch, 'head': head or None,
            'diff_stat': (diff.get('stdout') or '')[-git_service.DIFF_MAX_CHARS:]}


def repo_sync(path, message, expected_snapshot=None, expected_files=None):
    """Полная замена sync.bat: add -> commit -> pull --rebase -> push (+ merged PR check)."""
    validate(path)
    steps = []
    st = repo_status(path)
    if not st.get('ok'):
        return {'ok': False, 'error': st.get('error', 'git status failed'), 'steps': []}

    changes = st.get('changed', False)
    steps.append({'step': 'status', 'ok': True, 'changed': changes, 'branch': st.get('branch')})
    if expected_snapshot is not None:
        if (not isinstance(expected_files, list)
                or any(not isinstance(item, str) or not item for item in expected_files)
                or not re.fullmatch(r'[0-9a-f]{64}', str(expected_snapshot))):
            return {'ok': False, 'error': 'некорректный snapshot или список подтверждённых файлов',
                    'snapshot_mismatch': True, 'steps': steps}
        current = repo_sync_preview(path)
        if (not current.get('ok') or current.get('snapshot') != expected_snapshot
                or sorted(current.get('files', [])) != sorted(expected_files or [])):
            return {'ok': False,
                    'error': 'рабочее дерево изменилось после предпросмотра; обновите список изменений и подтвердите Sync заново',
                    'snapshot_mismatch': True, 'steps': steps}

    if changes:
        msg = (message or '').strip() if message else ''
        if not msg:
            return {'ok': False,
                    'error': 'есть незакоммиченные изменения — требуется сообщение коммита (как в sync.bat: пустое сообщение отклоняется). Путь исправления: введите сообщение коммита в поле над кнопкой «Синхронизировать» и повторите — sync сам выполнит add -A → commit → pull --rebase → push',
                    'steps': steps}
        ra = repo_add(path, expected_files if expected_snapshot is not None else None)
        steps.append({'step': 'add', **ra})
        if not ra.get('ok'):
            return {'ok': False, 'error': ra.get('error', 'git add failed'), 'steps': steps}
        if expected_snapshot is not None:
            staged_snapshot = repo_sync_preview(path, expected_files=expected_files)
            if not staged_snapshot.get('ok') or staged_snapshot.get('snapshot') != expected_snapshot:
                return {'ok': False,
                        'error': 'состав или содержимое файлов изменилось во время git add; коммит и push остановлены. Проверьте staged changes и повторите Sync',
                        'snapshot_mismatch': True, 'steps': steps}
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


def validate(path):
    git_service.validate_repo_path(path)


def diagnostics():
    return {'git': git_service.is_git_available(), 'version': git_service.git_version()}


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
    validate(path)
    state = repo_rebase_state(path)
    if not state.get('active'):
        return {'ok': False, 'error': 'активный rebase не найден'}
    if state.get('conflicts'):
        return {'ok': False, 'error': 'остались неразрешённые конфликты', 'conflicts': state['conflicts']}
    result = _r(['-c', 'core.editor=:', 'rebase', '--continue'], path,
                timeout=git_service.PUSH_TIMEOUT)
    if not result['ok']:
        return {'ok': False, 'error': (result['stderr'] or result['stdout'] or 'rebase --continue failed')[-1500:]}
    return {'ok': True, 'output': (result['stdout'] or result['stderr'])[-1500:]}


def repo_rebase_abort(path):
    validate(path)
    state = repo_rebase_state(path)
    if not state.get('active'):
        return {'ok': False, 'error': 'активный rebase не найден'}
    result = _r(['rebase', '--abort'], path, timeout=git_service.PUSH_TIMEOUT)
    if not result['ok']:
        return {'ok': False, 'error': (result['stderr'] or result['stdout'] or 'rebase --abort failed')[-1500:]}
    return {'ok': True, 'output': (result['stdout'] or result['stderr'])[-1500:]}
