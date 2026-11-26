"""Git CLI через контролируемый сервис (§5.2): allowlist, sys.argv-аргументы, таймауты.

AI не получает возможность выполнить произвольную команду ОС: команда выбирается
только из GIT_COMMANDS, аргументы передаются списком (shell=False), пути
ограничиваются каталогом репозитория. Для pull/push требуется подтверждение
WRITE через Capability Gateway — сам сервис политику не решает.
"""
import os
import stat
import shutil
import subprocess
import threading
import time
from contextlib import contextmanager

GIT_COMMANDS = {
    'status', 'branch', 'remote', 'log', 'diff', 'fetch', 'pull', 'push',
    'checkout', 'rev-parse', 'show-ref', 'ls-files', 'merge-base',
    'add', 'commit', 'switch', 'check-ref-format', 'rebase',
}
GIT_GLOBAL_FLAGS = {'--version', '--help'}

DEFAULT_TIMEOUT = 30
PUSH_TIMEOUT = 120
REPO_LOCK_TIMEOUT = 30
MUTATING_GIT_COMMANDS = {'add', 'branch', 'checkout', 'commit', 'fetch', 'pull', 'push', 'remote', 'rebase', 'switch'}
_REPO_LOCKS = {}
_REPO_LOCKS_GUARD = threading.Lock()
_REPO_LOCK_LOCAL = threading.local()

DIFF_MAX_CHARS = 200_000


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
    marker = os.path.join(path, '.git')
    # В обычном репозитории .git — каталог; в worktree/submodule — файл.
    # Проверка остаётся дешёвой: фактическую валидность Git подтвердит сама команда.
    if not (os.path.isdir(marker) or os.path.isfile(marker)):
        raise GitCommandRejected('not a git working tree: %s' % path)



def _git_common_dir(path):
    try:
        proc = subprocess.run(
            ['git', '-C', os.path.abspath(path), 'rev-parse', '--git-common-dir'],
            cwd=path, capture_output=True, text=True, timeout=DEFAULT_TIMEOUT,
            shell=False, encoding='utf-8', errors='replace',
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise GitCommandRejected('cannot resolve git common directory: %s' % e)
    if proc.returncode != 0:
        raise GitCommandRejected('cannot resolve git common directory: %s' % proc.stderr.strip())
    value = proc.stdout.strip()
    common = value if os.path.isabs(value) else os.path.join(path, value)
    common = os.path.realpath(common)
    if not os.path.isdir(common):
        raise GitCommandRejected('git common directory does not exist')
    return common


@contextmanager
def repo_operation_lock(path, timeout=REPO_LOCK_TIMEOUT):
    """Кроссплатформенная блокировка операций одного Git common-dir."""
    if not is_git_available():
        raise GitUnavailable('Git CLI не установлен')
    validate_repo_path(path)
    common = _git_common_dir(path)
    key = os.path.normcase(os.path.realpath(common))
    with _REPO_LOCKS_GUARD:
        local_lock = _REPO_LOCKS.setdefault(key, threading.RLock())
    if not local_lock.acquire(timeout=timeout):
        raise GitCommandRejected('repository is busy: operation lock timeout')

    depths = getattr(_REPO_LOCK_LOCAL, 'depths', None)
    if depths is None:
        depths = {}
        _REPO_LOCK_LOCAL.depths = depths
    if depths.get(key, 0):
        depths[key] += 1
        try:
            yield
        finally:
            depths[key] -= 1
            local_lock.release()
        return

    lock_path = os.path.join(common, 'drmAIcu-operation.lock')
    fd = None
    os_locked = False
    try:
        flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        try:
            before = os.lstat(lock_path)
            if stat.S_ISLNK(before.st_mode) or (getattr(before, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
                raise GitCommandRejected('unsafe repository lock file')
        except FileNotFoundError:
            pass
        fd = os.open(lock_path, flags, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise GitCommandRejected('repository lock is not a regular file')
        try:
            after = os.stat(lock_path)
            if (getattr(info, 'st_dev', None), getattr(info, 'st_ino', None)) != (getattr(after, 'st_dev', None), getattr(after, 'st_ino', None)):
                raise GitCommandRejected('repository lock file changed while opening')
        except OSError as e:
            raise GitCommandRejected('cannot verify repository lock file: %s' % e)

        deadline = time.monotonic() + timeout
        if os.name == 'nt':
            import msvcrt
            if info.st_size == 0:
                os.write(fd, b'\0')
            while True:
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    os_locked = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise GitCommandRejected('repository is busy: operation lock timeout')
                    time.sleep(0.05)
        else:
            import fcntl
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    os_locked = True
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise GitCommandRejected('repository is busy: operation lock timeout')
                    time.sleep(0.05)

        depths[key] = 1
        yield
    finally:
        depths.pop(key, None)
        if fd is not None:
            if os_locked:
                try:
                    if os.name == 'nt':
                        import msvcrt
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(fd)
        local_lock.release()



def _effective_head(args):
    """Команда с учётом единственного разрешённого префикса `-c core.editor=:` (rebase --continue)."""
    if not args:
        return ''
    head = str(args[0])
    if head == '-c':
        # Единственный разрешённый префикс: `git -c core.editor=: rebase --continue` —
        # неинтерактивное продолжение rebase без запуска редактора.
        if len(args) < 3 or str(args[1]) != 'core.editor=:' or str(args[2]) != 'rebase':
            raise GitCommandRejected('git global option is not allowed')
        return 'rebase'
    return head


def run_git(args, cwd=None, timeout=DEFAULT_TIMEOUT):
    if cwd is not None and _effective_head(args) in MUTATING_GIT_COMMANDS:
        with repo_operation_lock(cwd):
            return _run_git_unlocked(args, cwd=cwd, timeout=timeout)
    return _run_git_unlocked(args, cwd=cwd, timeout=timeout)


def _run_git_unlocked(args, cwd=None, timeout=DEFAULT_TIMEOUT):
    """-> {'ok': bool, 'code': int, 'stdout': str, 'stderr': str}"""
    if not is_git_available():
        raise GitUnavailable('Git CLI не установлен. Установите git — локальные операции с репозиториями недоступны.')
    if not args:
        raise GitCommandRejected('empty git command')
    head = _effective_head(args)
    if head not in GIT_COMMANDS and head not in GIT_GLOBAL_FLAGS:
        raise GitCommandRejected('git command not allowed: %r' % head)
    if cwd is not None:
        validate_repo_path(cwd)
    argv = ['git'] + [str(a) for a in args]
    attempt_timeout = PUSH_TIMEOUT if head == 'push' else timeout
    try:
        proc = subprocess.run(argv, cwd=cwd, timeout=attempt_timeout,
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
