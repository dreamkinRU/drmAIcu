"""Git CLI через контролируемый сервис (§5.2): allowlist, sys.argv-аргументы, таймауты.

AI не получает возможность выполнить произвольную команду ОС: команда выбирается
только из GIT_COMMANDS, аргументы передаются списком (shell=False), пути
ограничиваются рабочим каталогом проекта/репозитория.
"""
import os
import shutil
import subprocess

GIT_COMMANDS = {
    'status', 'branch', 'remote', 'log', 'diff', 'fetch', 'pull', 'push',
    'checkout', 'rev-parse', 'show-ref', 'ls-files', 'merge-base', 'config',
}
GIT_GLOBAL_FLAGS = {'--version', '--help'}

DEFAULT_TIMEOUT = 30
PUSH_TIMEOUT = 120


class GitUnavailable(Exception):
    pass


class GitCommandRejected(Exception):
    pass


def is_git_available():
    return shutil.which('git') is not None


def git_version():
    r = run_git(['--version'])
    return r.get('stdout', '').strip() if r.get('ok') else None


def validate_repo_path(path):
    if not path or not os.path.isdir(path):
        raise GitCommandRejected('repo path does not exist: %s' % path)
    if not os.path.isdir(os.path.join(path, '.git')):
        raise GitCommandRejected('not a git repository: %s' % path)


def run_git(args, cwd=None, timeout=DEFAULT_TIMEOUT):
    """-> {'ok': bool, 'code': int, 'stdout': str, 'stderr': str}"""
    if not is_git_available():
        raise GitUnavailable('Git CLI не установлен. Установите git — REST-функции GitHub продолжают работать без него.')
    if not args:
        raise GitCommandRejected('empty git command')
    head = str(args[0])
    if head not in GIT_COMMANDS and head not in GIT_GLOBAL_FLAGS:
        raise GitCommandRejected('git command not allowed: %r' % head)
    if cwd is not None:
        validate_repo_path(cwd)
    argv = ['git'] + [str(a) for a in args]
    try:
        proc = subprocess.run(argv, cwd=cwd, timeout=PUSH_TIMEOUT if head == 'push' else timeout,
                              capture_output=True, text=True, shell=False,
                              encoding='utf-8', errors='replace')
    except subprocess.TimeoutExpired:
        return {'ok': False, 'code': -1, 'stdout': '', 'stderr': 'git command timeout: %s' % head}
    return {
        'ok': proc.returncode == 0,
        'code': proc.returncode,
        'stdout': proc.stdout or '',
        'stderr': proc.stderr or '',
    }
