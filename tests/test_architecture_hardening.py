import json
import os
import subprocess
import sys
import time

import pytest

import patch_engine
from core.plugins.resource_governor import PluginResourceGovernor, PluginResourceLimitError
from core.plugins.worker_process import PluginWorker
from plugins.repos import git_service


def _configure_engine(tmp_path, monkeypatch):
    (tmp_path / 'patch').mkdir()
    (tmp_path / 'backups').mkdir()
    monkeypatch.setattr(patch_engine, 'BASE', str(tmp_path))
    monkeypatch.setattr(patch_engine, 'PATCH_DIR', str(tmp_path / 'patch'))
    monkeypatch.setattr(patch_engine, 'ARCHIVE_DIR', str(tmp_path / 'patch' / 'archive'))
    monkeypatch.setattr(patch_engine, 'BACKUP_DIR', str(tmp_path / 'backups'))
    monkeypatch.setattr(patch_engine, 'MANIFEST', str(tmp_path / 'patch_manifest.json'))
    monkeypatch.setattr(patch_engine, 'JOURNAL', str(tmp_path / 'patch_journal.json'))
    monkeypatch.setattr(patch_engine, 'MANIFEST_LOCK', '')
    monkeypatch.setattr(patch_engine, 'JOURNAL_LOCK', '')


def test_corrupt_crash_journal_blocks_patch_and_preserves_file(tmp_path, monkeypatch):
    _configure_engine(tmp_path, monkeypatch)
    target = tmp_path / 'module.py'
    target.write_text('value = 1\n', encoding='utf-8')
    (tmp_path / 'patch_journal.json').write_text('{broken', encoding='utf-8')

    result = patch_engine.apply_patch({
        'patch_id': 'journal-corrupt-regression',
        'operations': [{
            'type': 'full_replace',
            'target_file': 'module.py',
            'full_file_content': 'value = 2\n',
        }],
    })

    assert result['success'] is False
    assert 'заблокирован' in result['error']
    assert target.read_text(encoding='utf-8') == 'value = 1\n'
    assert (tmp_path / 'patch_journal.json.corrupt').exists()
    assert patch_engine.JOURNAL_LOCK


def test_orphan_journal_temp_blocks_new_patch(tmp_path, monkeypatch):
    _configure_engine(tmp_path, monkeypatch)
    target = tmp_path / 'module.py'
    target.write_text('value = 1\n', encoding='utf-8')
    (tmp_path / 'patch_journal.json.tmp').write_text('partial', encoding='utf-8')

    result = patch_engine.apply_patch({
        'patch_id': 'journal-temp-regression',
        'operations': [{
            'type': 'full_replace',
            'target_file': 'module.py',
            'full_file_content': 'value = 2\n',
        }],
    })

    assert result['success'] is False
    assert 'временный crash-журнал' in result['error']
    assert target.read_text(encoding='utf-8') == 'value = 1\n'


def test_typescript_validator_reports_unavailable_instead_of_pass(monkeypatch):
    monkeypatch.setattr(patch_engine.shutil, 'which', lambda _name: None)
    error = patch_engine.check_ts('src/Example.tsx', 'const value: number = 1;')
    assert error is not None
    assert error.startswith('UNAVAILABLE:')


def test_plugin_resource_governor_bounds_workers_and_rpc():
    governor = PluginResourceGovernor(max_workers=1, max_concurrent_calls=1)
    governor.acquire_worker()
    assert governor.worker_count == 1
    with pytest.raises(PluginResourceLimitError):
        governor.acquire_worker()
    governor.release_worker()
    assert governor.worker_count == 0

    assert governor.acquire_call(0)
    assert governor.acquire_call(0) is False
    governor.release_call()
    assert governor.acquire_call(0)
    governor.release_call()


def test_git_diagnostics_redact_credentials():
    source = (
        'fatal: https://user:secret@example.com/repo.git failed; '
        'remote token=ghp_verysecret Authorization: Bearer abc123'
    )
    redacted = git_service._redact_git_output(source)
    assert 'secret@example.com' not in redacted
    assert 'ghp_verysecret' not in redacted
    assert 'abc123' not in redacted
    assert '***' in redacted


def test_typescript_validation_fails_closed_when_node_is_missing(monkeypatch):
    monkeypatch.setattr(patch_engine.shutil, 'which', lambda _name: None)
    ok, error = patch_engine.validate('src/Example.tsx', 'const value: number = 1;')
    assert ok is False
    assert 'UNAVAILABLE' in error


def test_typescript_validator_launch_error_is_unavailable(monkeypatch):
    monkeypatch.setattr(patch_engine.shutil, 'which', lambda _name: '/usr/bin/node')

    def fail_to_launch(*_args, **_kwargs):
        raise OSError('node launch failed')

    monkeypatch.setattr(patch_engine.subprocess, 'run', fail_to_launch)
    error = patch_engine.check_ts('src/Example.tsx', 'const value: number = 1;')
    assert error.startswith('UNAVAILABLE:')
    assert 'node launch failed' in error


def test_typescript_validator_timeout_is_unavailable(monkeypatch):
    monkeypatch.setattr(patch_engine.shutil, 'which', lambda _name: '/usr/bin/node')

    def time_out(*_args, **_kwargs):
        raise patch_engine.subprocess.TimeoutExpired(cmd='node', timeout=30)

    monkeypatch.setattr(patch_engine.subprocess, 'run', time_out)
    error = patch_engine.check_ts('src/Example.tsx', 'const value: number = 1;')
    assert error.startswith('UNAVAILABLE:')
    assert 'timeout' in error


def test_corrupt_journal_recovery_reports_blocked(tmp_path, monkeypatch):
    _configure_engine(tmp_path, monkeypatch)
    journal = tmp_path / 'patch_journal.json'
    journal.write_text('not-json', encoding='utf-8')

    result = patch_engine.recover_journal()

    assert result['action'] == 'blocked'
    assert patch_engine.JOURNAL_LOCK
    assert journal.exists()
    assert (tmp_path / 'patch_journal.json.corrupt').exists()


@pytest.mark.skipif(sys.platform != 'linux', reason='POSIX process-group integration test')
def test_worker_cleanup_kills_descendant_after_group_leader_exits(tmp_path):
    parent_code = (
        "import subprocess,sys; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        "print(child.pid, flush=True)"
    )
    parent = subprocess.Popen(
        [sys.executable, '-c', parent_code],
        cwd=str(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, start_new_session=True,
    )
    child_pid = int(parent.stdout.readline().strip())
    parent.wait(timeout=5)
    parent.stdout.close()

    worker = PluginWorker(object(), 'test', str(tmp_path), 'plugin.py', object())
    worker._terminate_process_tree(parent)

    def child_is_alive():
        stat_path = '/proc/%s/stat' % child_pid
        try:
            with open(stat_path, 'r', encoding='utf-8') as handle:
                return handle.read().split()[2] != 'Z'
        except FileNotFoundError:
            return False

    for _ in range(40):
        if not child_is_alive():
            break
        time.sleep(0.05)
    assert not child_is_alive()


def test_apply_recovery_does_not_clear_journal_when_backup_is_missing(tmp_path, monkeypatch):
    _configure_engine(tmp_path, monkeypatch)
    target = tmp_path / 'module.py'
    target.write_text('new value\n', encoding='utf-8')
    (tmp_path / 'patch_journal.json').write_text(json.dumps({
        'op': 'apply',
        'patch_id': 'missing-backup',
        'steps': [{
            'path': str(target), 'tgt': 'module.py', 'existed': True,
            'backs': [], 'backup_sha': None, 'done': True,
        }],
    }), encoding='utf-8')

    result = patch_engine.recover_journal()

    assert result['action'] == 'apply-revert-incomplete'
    assert 'backup missing' in result['failed'][0]
    assert target.read_text(encoding='utf-8') == 'new value\n'
    assert (tmp_path / 'patch_journal.json').exists()


def test_apply_recovery_rejects_tampered_backup(tmp_path, monkeypatch):
    _configure_engine(tmp_path, monkeypatch)
    target = tmp_path / 'module.py'
    target.write_text('new value\n', encoding='utf-8')
    backup = tmp_path / 'backups' / 'module.bak'
    backup.write_text('tampered value\n', encoding='utf-8')
    expected_sha = patch_engine.sha_bytes(b'original value\n')
    (tmp_path / 'patch_journal.json').write_text(json.dumps({
        'op': 'apply',
        'patch_id': 'tampered-backup',
        'steps': [{
            'path': str(target), 'tgt': 'module.py', 'existed': True,
            'backs': ['backups/module.bak'], 'backup_sha': expected_sha, 'done': True,
        }],
    }), encoding='utf-8')

    result = patch_engine.recover_journal()

    assert result['action'] == 'apply-revert-incomplete'
    assert 'backup checksum mismatch' in result['failed'][0]
    assert target.read_text(encoding='utf-8') == 'new value\n'
    assert (tmp_path / 'patch_journal.json').exists()


def test_stats_reports_valid_unrecovered_journal_as_locked(tmp_path, monkeypatch):
    _configure_engine(tmp_path, monkeypatch)
    (tmp_path / 'patch_journal.json').write_text(json.dumps({
        'op': 'apply',
        'patch_id': 'pending-apply',
        'steps': [{
            'path': str(tmp_path / 'module.py'), 'tgt': 'module.py',
            'existed': False, 'backs': [], 'backup_sha': None, 'done': False,
        }],
    }), encoding='utf-8')

    result = patch_engine.stats()

    assert result['locked'] is True
    assert result['journal_locked'] is True
    assert result['journal_pending'] is True
    assert 'recover_journal' in result['journal_lock_reason']
