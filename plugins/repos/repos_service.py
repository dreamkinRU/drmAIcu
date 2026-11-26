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
            remotes.append({'name': parts[0], 'url': parts[1]})
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
    if not (full == os.path.normpath(path) or full.startswith(os.path.normpath(path) + os.sep)):
        return {'ok': False, 'error': 'путь вне репозитория'}
    if not os.path.isfile(full):
        return {'ok': False, 'error': 'файл не найден: %s' % rel}
    size = os.path.getsize(full)
    if size > max_bytes:
        return {'ok': False, 'error': 'файл слишком большой (%d байт, лимит %d)' % (size, max_bytes)}
    with open(full, 'rb') as f:
        data = f.read()
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
        return {'ok': False, 'error': 'требуется сообщение коммита — пустой коммит отклонён (как в sync.bat)'}
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
                    'error': 'push отклонён — на сервере есть новые коммиты. Сначала выполните pull.',
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
    args = ['checkout'] + (['-b'] if create else []) + [clean]
    r = _r(args, path)
    if not r['ok']:
        return {'ok': False, 'error': (r['stderr'].strip() or 'git checkout failed')[-1500:]}
    return {'ok': True, 'branch': clean, 'created': bool(create)}


def repo_sync(path, message):
    """Полная замена sync.bat: add -> commit -> pull --rebase -> push (+ merged PR check)."""
    validate(path)
    steps = []
    st = repo_status(path)
    if not st.get('ok'):
        return {'ok': False, 'error': st.get('error', 'git status failed'), 'steps': []}

    changes = st.get('changed', False)
    steps.append({'step': 'status', 'ok': True, 'changed': changes, 'branch': st.get('branch')})

    if changes:
        msg = (message or '').strip() if message else ''
        if not msg:
            return {'ok': False,
                    'error': 'есть незакоммиченные изменения — требуется сообщение коммита (как в sync.bat: пустое сообщение отклоняется)',
                    'steps': steps}
        ra = repo_add(path)
        steps.append({'step': 'add', **ra})
        if not ra.get('ok'):
            return {'ok': False, 'error': ra.get('error', 'git add failed'), 'steps': steps}
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
