"""Security regression tests for Repos Plugin and Capability Gateway."""
import os
import subprocess

import pytest


def make_repo(path):
    os.makedirs(path)
    def git(*args):
        subprocess.run(['git', *args], cwd=path, check=True, capture_output=True)
    git('init', '-b', 'main')
    git('config', 'user.name', 'test')
    git('config', 'user.email', 'test@example.com')
    with open(os.path.join(path, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('inside\n')
    git('add', '-A')
    git('commit', '-m', 'initial')
    return path


def test_gateway_rejects_write_auto_and_critical_confirm():
    from core.plugins.api import PluginAPI

    api = PluginAPI(None, 'demo')
    with pytest.raises(ValueError, match='weaker than required'):
        api.register_capability('demo.write', 'demo.write', lambda p: None, 'auto')
    with pytest.raises(ValueError, match='weaker than required'):
        api.register_capability('demo.merge', 'demo.merge', lambda p: None, 'confirm')
    api.register_capability('demo.read', 'demo.read', lambda p: None, 'auto')
    api.register_capability('demo.write_safe', 'demo.write', lambda p: None, 'confirm')
    api.register_capability('demo.critical', 'demo.merge', lambda p: None, 'critical')


def test_confirmation_is_bound_to_full_operation_context(tmp_path):
    from core.plugins.confirmations import ConfirmationError, ConfirmationManager

    manager = ConfirmationManager(str(tmp_path / 'confirmations.json'))
    params = {'path': '/repo', 'branch': 'main'}
    item = manager.create('repos', 'repos.checkout', params, 'repos.write', 'confirm')

    with pytest.raises(ConfirmationError, match='capability'):
        manager.consume(item['id'], 'repos', 'repos.push', 'repos.write', 'confirm', params)
    # Ошибка контекста не должна сжигать корректный одноразовый токен.
    consumed = manager.consume(item['id'], 'repos', 'repos.checkout', 'repos.write', 'confirm', params)
    assert consumed['capability'] == 'repos.checkout'

    with pytest.raises(ConfirmationError, match='already used'):
        manager.consume(item['id'], 'repos', 'repos.checkout', 'repos.write', 'confirm', params)


def test_read_file_rejects_symlink_escape(tmp_path):
    from plugins.repos import repos_service

    repo = make_repo(str(tmp_path / 'repo'))
    outside = tmp_path / 'outside.txt'
    outside.write_text('secret\n', encoding='utf-8')
    link = os.path.join(repo, 'outside-link.txt')
    try:
        os.symlink(str(outside), link)
    except (OSError, NotImplementedError):
        pytest.skip('symlink creation is unavailable on this platform')

    result = repos_service.read_file(repo, 'outside-link.txt')
    assert result['ok'] is False
    assert 'symbolic link/reparse point' in result['error']


def test_checkout_rejects_invalid_or_option_like_branch_names(tmp_path):
    from plugins.repos import repos_service

    repo = make_repo(str(tmp_path / 'repo'))
    assert repos_service.repo_checkout(repo, '--help')['ok'] is False
    assert repos_service.repo_checkout(repo, 'feature..broken', create=True)['ok'] is False
    result = repos_service.repo_checkout(repo, 'feature/safe', create=True)
    assert result['ok'] is True
    branch = subprocess.run(['git', 'branch', '--show-current'], cwd=repo,
                            capture_output=True, text=True, check=True)
    assert branch.stdout.strip() == 'feature/safe'


def test_remote_urls_are_redacted_before_returning_to_ui(tmp_path):
    from plugins.repos.repos_service import _sanitize_remote_url

    assert _sanitize_remote_url('https://user:ghp_secret@github.com/org/repo.git') == (
        'https://***@github.com/org/repo.git'
    )
    safe = _sanitize_remote_url('https://github.com/org/repo.git')
    assert safe == 'https://github.com/org/repo.git'
    private_query = _sanitize_remote_url('https://example.com/repo?access_token=abc&branch=main')
    assert 'abc' not in private_query and 'branch=main' in private_query
    signed = _sanitize_remote_url('https://example.com/repo?X-Amz-Signature=secret#token=fragment-secret')
    assert 'secret' not in signed and 'fragment-secret' not in signed


def test_worktree_is_accepted_as_repository(tmp_path):
    from plugins.repos import repos_service

    repo = make_repo(str(tmp_path / 'repo'))
    worktree = str(tmp_path / 'worktree')
    subprocess.run(['git', 'worktree', 'add', '-b', 'feature-worktree', worktree],
                   cwd=repo, check=True, capture_output=True)
    result = repos_service.repo_status(worktree)
    assert result['ok'] is True
    assert result['branch'] == 'feature-worktree'

def test_sync_refuses_worktree_changed_after_preview(tmp_path):
    from plugins.repos import repos_service

    repo = make_repo(str(tmp_path / 'repo'))
    file_path = os.path.join(repo, 'new.txt')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('approved content\n')
    preview = repos_service.repo_status(repo)
    assert preview['ok'] and preview['snapshot_files'] == ['new.txt']

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('unapproved content\n')
    result = repos_service.repo_sync(repo, 'must not commit', preview['snapshot'])
    assert result['ok'] is False and result['snapshot_changed'] is True
    log = subprocess.run(['git', 'log', '-1', '--format=%s'], cwd=repo,
                         capture_output=True, text=True, check=True)
    assert log.stdout.strip() == 'initial'
    status = subprocess.run(['git', 'status', '--porcelain'], cwd=repo,
                            capture_output=True, text=True, check=True)
    assert status.stdout.strip()


def test_sync_snapshot_binds_remote_and_upstream(tmp_path):
    from plugins.repos import repos_service

    repo = make_repo(str(tmp_path / 'repo'))
    remote_a = str(tmp_path / 'remote-a.git')
    remote_b = str(tmp_path / 'remote-b.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote_a],
                   check=True, capture_output=True)
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote_b],
                   check=True, capture_output=True)
    subprocess.run(['git', 'remote', 'add', 'origin', remote_a],
                   cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', 'push', '-u', 'origin', 'main'],
                   cwd=repo, check=True, capture_output=True)

    preview = repos_service.repo_status(repo)
    subprocess.run(['git', 'remote', 'set-url', 'origin', remote_b],
                   cwd=repo, check=True, capture_output=True)
    result = repos_service.repo_sync(repo, 'must not push elsewhere', preview['snapshot'])
    assert result['ok'] is False and result['snapshot_changed'] is True


def test_checkout_ui_requires_explicit_confirmation():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, 'src', 'components', 'tabs', 'RepositoriesTab.tsx')
    with open(path, encoding='utf-8') as f:
        source = f.read()
    assert 'await reposCheckout(repoPath, branch, create, r.confirmation.id)' not in source
    start = source.index('function BranchesSection(')
    end = source.index('function ChangesSection(', start)
    branches = source[start:end]
    assert 'setPending({' in branches
    assert 'ConfirmationBar pending={pending}' in branches
    assert 'doCheckout(branch, create, t)' in branches


def test_sync_add_normalizes_index_to_approved_worktree_content(tmp_path):
    from plugins.repos import repos_service

    repo = make_repo(str(tmp_path / 'repo'))
    target = os.path.join(repo, 'README.md')
    with open(target, 'w', encoding='utf-8') as f:
        f.write('approved working tree content\n')
    preview = repos_service.repo_status(repo)
    assert preview['ok'] is True

    blob = subprocess.run(
        ['git', 'hash-object', '-w', '--stdin'], cwd=repo, input=b'unapproved staged blob\n',
        check=True, capture_output=True,
    ).stdout.decode().strip()
    subprocess.run(
        ['git', 'update-index', '--cacheinfo', '100644', blob, 'README.md'],
        cwd=repo, check=True, capture_output=True,
    )
    after_index_change = repos_service.repo_status(repo)
    assert after_index_change['ok'] is True
    assert after_index_change['snapshot'] == preview['snapshot']

    staged = repos_service.repo_add(repo)
    assert staged['ok'] is True
    subprocess.run(['git', 'commit', '-m', 'approved snapshot'], cwd=repo,
                   check=True, capture_output=True)
    committed = subprocess.run(['git', 'show', 'HEAD:README.md'], cwd=repo,
                               check=True, capture_output=True).stdout.decode()
    assert committed == 'approved working tree content\n'


def test_repo_operation_lock_serializes_threads_and_processes(tmp_path):
    import sys
    import threading

    from plugins.repos.git_service import repo_operation_lock, GitCommandRejected

    repo = make_repo(str(tmp_path / 'repo'))
    first_inside = threading.Event()
    release_first = threading.Event()
    second_inside = threading.Event()

    def first_worker():
        with repo_operation_lock(repo):
            first_inside.set()
            assert release_first.wait(5)

    def second_worker():
        assert first_inside.wait(5)
        with repo_operation_lock(repo):
            second_inside.set()

    first = threading.Thread(target=first_worker)
    second = threading.Thread(target=second_worker)
    first.start()
    assert first_inside.wait(5)
    second.start()
    assert not second_inside.wait(0.2)
    release_first.set()
    first.join(5)
    second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert second_inside.is_set()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = (
        "import sys\n"
        "from plugins.repos.git_service import repo_operation_lock, GitCommandRejected\n"
        "try:\n"
        "    with repo_operation_lock(sys.argv[1], timeout=0.25):\n"
        "        print('ACQUIRED')\n"
        "except GitCommandRejected:\n"
        "    print('BLOCKED')\n"
    )
    env = os.environ.copy()
    env['PYTHONPATH'] = root + os.pathsep + env.get('PYTHONPATH', '')
    with repo_operation_lock(repo):
        child = subprocess.run(
            [sys.executable, '-c', code, repo], cwd=root, env=env,
            capture_output=True, text=True, timeout=10,
        )
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == 'BLOCKED'


def test_read_file_rejects_symlink_parent_escape(tmp_path):
    from plugins.repos import repos_service

    repo = make_repo(str(tmp_path / 'repo'))
    outside = tmp_path / 'outside-dir'
    outside.mkdir()
    (outside / 'secret.txt').write_text('outside secret', encoding='utf-8')
    link = os.path.join(repo, 'linked-dir')
    if os.name == 'nt':
        junction = subprocess.run(
            ['cmd', '/c', 'mklink', '/J', link, str(outside)],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
        )
        if junction.returncode != 0:
            pytest.skip('directory junction creation is unavailable on this runner')
    else:
        try:
            os.symlink(str(outside), link, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip('directory symlink creation is unavailable on this platform')

    result = repos_service.read_file(repo, 'linked-dir/secret.txt')
    assert result['ok'] is False
