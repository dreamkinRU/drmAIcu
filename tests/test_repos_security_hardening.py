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
    assert 'путь вне репозитория' in result['error']


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


def test_worktree_is_accepted_as_repository(tmp_path):
    from plugins.repos import repos_service

    repo = make_repo(str(tmp_path / 'repo'))
    worktree = str(tmp_path / 'worktree')
    subprocess.run(['git', 'worktree', 'add', '-b', 'feature-worktree', worktree],
                   cwd=repo, check=True, capture_output=True)
    result = repos_service.repo_status(worktree)
    assert result['ok'] is True
    assert result['branch'] == 'feature-worktree'

\n\ndef test_sync_refuses_worktree_changed_after_preview(tmp_path):
    from plugins.repos import repos_service

    repo = make_repo(str(tmp_path / 'repo'))
    file_path = os.path.join(repo, 'new.txt')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('approved content\\n')
    preview = repos_service.repo_status(repo)
    assert preview['ok'] and preview['snapshot_files'] == ['new.txt']

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('unapproved content\\n')
    result = repos_service.repo_sync(repo, 'must not commit', preview['snapshot'])
    assert result['ok'] is False and result['snapshot_changed'] is True
    log = subprocess.run(['git', 'log', '-1', '--format=%s'], cwd=repo,
                         capture_output=True, text=True, check=True)
    assert log.stdout.strip() == 'initial'
    status = subprocess.run(['git', 'status', '--porcelain'], cwd=repo,
                            capture_output=True, text=True, check=True)
    assert status.stdout.strip()
