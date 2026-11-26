# -*- coding: utf-8 -*-
"""Этап 5: мост PATCHMASTER ↔ Sync (только чтение).

capability repos.patch_status (READ/auto) читает patch_manifest.json и
patch_journal.json движка: последние применённые патчи, незавершённая
транзакция (crash-журнал) и файлы патчей, ещё не закоммиченные в drmAIcu.
PATCHMASTER остаётся единственным писателем исходников — Repos Plugin файлы
не пишет и apply_patch не вызывает (проверяется contract-тестом).
"""
import json
import os
import subprocess
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

PLUGIN_DIR = os.path.join(BASE, 'plugins', 'repos')


def make_repo(tmp_path):
    repo = str(tmp_path / 'repo')
    os.makedirs(repo)
    def g(*args):
        subprocess.run(['git'] + list(args), cwd=repo, check=True, capture_output=True)
    g('init', '-b', 'main')
    g('config', 'user.name', 'tester')
    g('config', 'user.email', 'tester@example.com')
    g('config', 'commit.gpgsign', 'false')
    with open(os.path.join(repo, 'README.md'), 'w') as f:
        f.write('hi\n')
    g('add', '-A')
    g('commit', '-m', 'init')
    return repo


class _FakeManager:
    def __init__(self, tmp):
        from core.plugins.events import ActivityJournal, EventBus
        from core.plugins.secrets import SecretManager
        from core.plugins.settings import SettingsManager
        self.secrets = SecretManager(os.path.join(tmp, 'secrets'))
        self.activity = ActivityJournal(os.path.join(tmp, 'activity'))
        self.events = EventBus()
        self.registry = type('R', (), {'get': lambda self, pid: None})()
        self.settings = SettingsManager(os.path.join(tmp, 'state'))


def _load_plugin(tmp_path):
    from core.plugins.api import PluginAPI
    from core.plugins.loader import load_entry
    module = load_entry('repos', PLUGIN_DIR, 'plugin.py')
    ctx = PluginAPI(_FakeManager(str(tmp_path)), 'repos')
    assert module.initialize(ctx) is True
    return module, ctx


def _write_manifest(tmp_path, applied):
    pe = sys.modules.get('patch_engine')
    man_path = os.path.join(str(tmp_path), 'patch_manifest.json')
    with open(man_path, 'w', encoding='utf-8') as f:
        json.dump({'applied': applied, 'history': [], 'rollbacks': []}, f)
    jr_path = os.path.join(str(tmp_path), 'patch_journal.json')
    return man_path, jr_path


def test_patch_status_capability_registered_read_auto(tmp_path):
    module, ctx = _load_plugin(tmp_path)
    caps = {c['name']: c for c in ctx.capabilities()}
    assert 'repos.patch_status' in caps
    assert caps['repos.patch_status']['permission'] == 'repos.read'
    assert caps['repos.patch_status']['policy'] == 'auto'


def test_patch_status_reports_unsynced_patch_files(tmp_path, monkeypatch):
    """Патч применён движком (запись в manifest), файл изменён, но не закоммичен —
    мост должен показать его в unsynced_files, чтобы UI предложил Sync."""
    import patch_engine as pe
    repo = make_repo(tmp_path)
    with open(os.path.join(repo, 'app.py'), 'w') as f:
        f.write('print(1)\n')  # незакоммиченное изменение
    man_path, jr_path = _write_manifest(tmp_path, [
        {'patch_id': 'p1', 'target_file': 'app.py', 'applied_at': '2026-11-26T10:00:00',
         'operations': [{'target_file': 'app.py', 'checksum': 'x', 'backups': [], 'backup_sha': None}],
         'checksum': 'y', 'backups': []},
    ])
    monkeypatch.setattr(pe, 'BASE', repo)
    monkeypatch.setattr(pe, 'MANIFEST', man_path)
    monkeypatch.setattr(pe, 'JOURNAL', jr_path)
    monkeypatch.setattr(pe, 'MANIFEST_LOCK', '')

    from plugins.repos import repos_service
    out = repos_service.repo_patch_status(repo)
    assert out['ok'] is True, out
    assert out['engine_blocked'] is False
    assert out['unsynced_files'] == ['app.py'], out
    assert out['changed'] is True
    assert out['applied'][0]['patch_id'] == 'p1'
    assert out['applied'][0]['files'] == ['app.py']


def test_patch_status_committed_patch_not_reported(tmp_path, monkeypatch):
    """Если файл патча уже закоммичен (нет незакоммиченных изменений) —
    unsynced_files пуст, баннер Sync не показывается."""
    import patch_engine as pe
    repo = make_repo(tmp_path)
    man_path, jr_path = _write_manifest(tmp_path, [
        {'patch_id': 'p1', 'target_file': 'README.md', 'applied_at': '2026-11-26T10:00:00',
         'operations': [{'target_file': 'README.md', 'checksum': 'x', 'backups': [], 'backup_sha': None}],
         'checksum': 'y', 'backups': []},
    ])
    monkeypatch.setattr(pe, 'BASE', repo)
    monkeypatch.setattr(pe, 'MANIFEST', man_path)
    monkeypatch.setattr(pe, 'JOURNAL', jr_path)
    monkeypatch.setattr(pe, 'MANIFEST_LOCK', '')

    from plugins.repos import repos_service
    out = repos_service.repo_patch_status(repo)
    assert out['ok'] is True
    assert out['unsynced_files'] == []
    assert out['changed'] is False


def test_patch_status_reports_in_progress_journal(tmp_path, monkeypatch):
    """crash-журнал транзакции (op=apply) → in_progress с patch_id и файлами:
    пользователь видит, что восстановление обязательно при перезапуске."""
    import patch_engine as pe
    repo = make_repo(tmp_path)
    man_path, _ = _write_manifest(tmp_path, [])
    jr_path = os.path.join(str(tmp_path), 'patch_journal.json')
    with open(jr_path, 'w', encoding='utf-8') as f:
        json.dump({'op': 'apply', 'patch_id': 'pX',
                   'steps': [{'path': '/tmp/x.py', 'tgt': 'a.py', 'existed': True,
                              'backs': ['b'], 'done': True}]}, f)
    monkeypatch.setattr(pe, 'BASE', repo)
    monkeypatch.setattr(pe, 'MANIFEST', man_path)
    monkeypatch.setattr(pe, 'JOURNAL', jr_path)

    from plugins.repos import repos_service
    out = repos_service.repo_patch_status(repo)
    assert out['ok'] is True
    assert out['in_progress'] == {'patch_id': 'pX', 'files': ['a.py']}, out


def test_patch_status_engine_blocked(tmp_path, monkeypatch):
    """Повреждённый manifest (MANIFEST_LOCK) → engine_blocked=True: UI обязан
    показать красный баннер с путём исправления."""
    import patch_engine as pe
    repo = make_repo(tmp_path)
    man_path, jr_path = _write_manifest(tmp_path, [])
    monkeypatch.setattr(pe, 'BASE', repo)
    monkeypatch.setattr(pe, 'JOURNAL', jr_path)
    # честный сценарий: manifest реально повреждён — load_manifest() сам
    # выставляет MANIFEST_LOCK (B52 FIX) и сохраняет .corrupt-копию
    monkeypatch.setattr(pe, 'MANIFEST', man_path)
    with open(man_path, 'w', encoding='utf-8') as f:
        f.write('{broken json')

    from plugins.repos import repos_service
    out = repos_service.repo_patch_status(repo)
    assert out['ok'] is True and out['engine_blocked'] is True
    # уборка: MANIFEST_LOCK — глобальное состояние движка, не тащим его в другие тесты
    pe.MANIFEST_LOCK = ''


def test_patch_bridge_is_read_only_contract():
    """PATCHMASTER остаётся обязательным шлюзом: Repos Plugin НИКОГДА не пишет
    исходники — в plugin.py нет apply_patch и записи файлов."""
    with open(os.path.join(PLUGIN_DIR, 'plugin.py'), encoding='utf-8') as f:
        plugin = f.read()
    assert 'apply_patch(' not in plugin, 'плагин не имеет права применять патчи'
    assert 'repos.patch_status' in plugin
    svc = os.path.join(PLUGIN_DIR, 'repos_service.py')
    with open(svc, encoding='utf-8') as f:
        src = f.read()
    assert 'pe.apply_patch' not in src, 'плагин не вызывает apply_patch даже через модуль движка'
    assert 'def repo_patch_status' in src
    # единственные WRITE-операции плагина — git allowlist (git_service), не запись файлов
    gs = os.path.join(PLUGIN_DIR, 'git_service.py')
    with open(gs, encoding='utf-8') as f:
        git_src = f.read()
    assert "os.replace" not in git_src, 'git_service не пишет файлы напрямую'


def test_patch_bridge_ui_contract():
    """UI обязан показывать баннеры PATCHMASTER-моста с путём исправления."""
    tab_path = os.path.join(BASE, 'src', 'components', 'tabs', 'RepositoriesTab.tsx')
    with open(tab_path, encoding='utf-8') as f:
        tab = f.read()
    assert 'repos.patch_status' in open(os.path.join(BASE, 'src', 'services', 'repos.ts'), encoding='utf-8').read()
    assert 'PATCHMASTER: патчи применены, но ещё не закоммичены' in tab
    assert 'unsynced_files' in tab
    assert 'Путь исправления: Предпросмотр Sync' in tab
    assert 'PATCHMASTER: незавершённая транзакция патча' in tab
    assert 'recover_journal' in tab
    assert 'PATCHMASTER заблокирован' in tab
