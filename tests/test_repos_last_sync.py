# -*- coding: utf-8 -*-
"""Repos: персистентный последний результат Sync (state плагина, §9.1).

UI показывает результат Sync после обновления страницы: capability
repos.last_sync (READ/AUTO) возвращает последний результат из
data/plugins/state/repos/state.json, запись делает repos.sync при каждом
запуске (и при успехе, и при ошибке).
"""
import os
import subprocess
import sys

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


def build_manager(tmp_path, label):
    from core.plugins.manager import PluginManager
    builtin = str(tmp_path / ('builtin_' + label))
    os.makedirs(os.path.join(builtin, 'repos'), exist_ok=True)
    for fn in ('plugin.json', 'plugin.py', 'git_service.py', 'repos_service.py'):
        with open(os.path.join(PLUGIN_DIR, fn), encoding='utf-8') as f:
            with open(os.path.join(builtin, 'repos', fn), 'w', encoding='utf-8') as w:
                w.write(f.read())
    data = str(tmp_path / ('data_' + label))
    return PluginManager(base_dir=str(tmp_path / ('base_' + label)), data_dir=data, builtin_dir=builtin)


def grant_all(mgr):
    rows = [{'permission': row['permission'], 'granted': True} for row in mgr.permissions_status('repos')['permissions']]
    mgr.permissions_put('repos', rows)


def test_ctx_state_roundtrip(tmp_path):
    """ctx.save_state/load_state — персистентное произвольное состояние плагина (§9.1)."""
    from core.plugins.api import PluginAPI
    from core.plugins.settings import SettingsManager
    from core.plugins.events import ActivityJournal, EventBus
    from core.plugins.secrets import SecretManager

    class M:
        def __init__(self):
            self.secrets = SecretManager(str(tmp_path / 'secrets'))
            self.activity = ActivityJournal(str(tmp_path / 'activity'))
            self.events = EventBus()
            self.settings = SettingsManager(str(tmp_path / 'state'))

    ctx = PluginAPI(M(), 'demo')
    assert ctx.load_state() == {}
    ctx.save_state({'answer': 42, 'nested': {'ok': True}})
    assert ctx.load_state() == {'answer': 42, 'nested': {'ok': True}}
    # файл реально на диске (переживает процесс)
    import json
    with open(os.path.join(str(tmp_path / 'state'), 'demo', 'state.json'), encoding='utf-8') as f:
        assert json.load(f)['answer'] == 42


def test_last_sync_capability_registered_read_auto():
    from core.plugins.loader import load_entry
    from core.plugins.api import PluginAPI
    from core.plugins.settings import SettingsManager
    from core.plugins.events import ActivityJournal, EventBus
    from core.plugins.secrets import SecretManager
    import tempfile

    class M:
        def __init__(self):
            tmp = tempfile.mkdtemp()
            self.secrets = SecretManager(os.path.join(tmp, 'secrets'))
            self.activity = ActivityJournal(os.path.join(tmp, 'activity'))
            self.events = EventBus()
            self.registry = type('R', (), {'get': lambda self, pid: None})()
            self.settings = SettingsManager(os.path.join(tmp, 'state'))

    module = load_entry('repos', PLUGIN_DIR, 'plugin.py')
    ctx = PluginAPI(M(), 'repos')
    assert module.initialize(ctx) is True
    caps = {c['name']: c for c in ctx.capabilities()}
    assert 'repos.last_sync' in caps, 'capability repos.last_sync должна быть зарегистрирована'
    assert caps['repos.last_sync']['permission'] == 'repos.read'
    assert caps['repos.last_sync']['policy'] == 'auto'


def test_last_sync_persists_across_manager_restart(tmp_path):
    """Успешный Sync -> repos.last_sync возвращает результат; НОВЫЙ PluginManager
    на тех же data (имитация обновления страницы/перезапуска панели) — результат
    всё ещё доступен."""
    remote = str(tmp_path / 'remote.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote], check=True, capture_output=True)
    repo = make_repo(tmp_path)
    subprocess.run(['git', 'remote', 'add', 'origin', remote], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=repo, check=True, capture_output=True)

    mgr = build_manager(tmp_path, 'a')
    mgr.install('builtin:repos')
    mgr.enable('repos')
    grant_all(mgr)

    with open(os.path.join(repo, 'persist.txt'), 'w') as f:
        f.write('last sync panel\n')

    from plugins.repos import repos_service
    params = {'path': repo, 'message': 'persist sync', 'snapshot': repos_service.repo_status(repo)['snapshot']}
    out = mgr.exec('repos', 'repos.sync', params)
    assert out['status'] == 'confirmation_required', out
    out2 = mgr.confirm(out['confirmation']['id'], True)
    assert out2['status'] == 'done' and out2['result']['ok'], out2

    got = mgr.exec('repos', 'repos.last_sync', {'path': repo})
    assert got['status'] == 'done', got
    info = got['result']
    assert info['found'] is True and info['result']['ok'] is True
    assert info['result']['committed'] is True and info['finished_at']
    assert info['path'] == repo

    # «перезапуск панели»: свежий менеджер на тех же data — результат персистентен
    from core.plugins.manager import PluginManager
    mgr2 = PluginManager(base_dir=mgr.base, data_dir=mgr.data_dir, builtin_dir=mgr.builtin_dir)
    mgr2.load_all()
    got2 = mgr2.exec('repos', 'repos.last_sync', {'path': repo})
    assert got2['status'] == 'done' and got2['result']['found'] is True, got2
    assert got2['result']['result']['ok'] is True
    assert got2['result']['result']['head'] == info['result']['head']


def test_failed_sync_is_recorded_with_error(tmp_path):
    """Неудачный Sync (push отклонён: remote ушёл вперёд) тоже попадает в
    repos.last_sync — пользователь видит честный итог, а не пустоту."""
    remote = str(tmp_path / 'remote.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote], check=True, capture_output=True)
    repo = make_repo(tmp_path)
    subprocess.run(['git', 'remote', 'add', 'origin', remote], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=repo, check=True, capture_output=True)
    # конкурентный коммит в remote изменяет ТОТ ЖЕ файл README.md —
    # после локального коммита pull --rebase даст конфликт (детерминированный отказ Sync)
    other = str(tmp_path / 'other')
    subprocess.run(['git', 'clone', remote, other], check=True, capture_output=True)
    subprocess.run(['git', '-C', other, 'config', 'commit.gpgsign', 'false'], check=True, capture_output=True)
    subprocess.run(['git', '-C', other, 'config', 'user.email', 'o@e.c'], check=True, capture_output=True)
    subprocess.run(['git', '-C', other, 'config', 'user.name', 'o'], check=True, capture_output=True)
    with open(os.path.join(other, 'README.md'), 'w') as f:
        f.write('remote side\n')
    subprocess.run(['git', '-C', other, 'add', '-A'], check=True, capture_output=True)
    subprocess.run(['git', '-C', other, 'commit', '-m', 'competing'], check=True, capture_output=True)
    subprocess.run(['git', '-C', other, 'push', 'origin', 'main'], check=True, capture_output=True)

    # локальное изменение того же файла
    with open(os.path.join(repo, 'README.md'), 'w') as f:
        f.write('local side\n')

    mgr = build_manager(tmp_path, 'a')
    mgr.install('builtin:repos')
    mgr.enable('repos')
    grant_all(mgr)

    from plugins.repos import repos_service
    params = {'path': repo, 'message': 'will fail at rebase', 'snapshot': repos_service.repo_status(repo)['snapshot']}
    out = mgr.exec('repos', 'repos.sync', params)
    cid = out['confirmation']['id']
    out2 = mgr.confirm(cid, True)
    assert out2['status'] == 'done', out2
    result = out2['result']
    assert result['ok'] is False and result.get('rebase_conflict') is True, result

    got = mgr.exec('repos', 'repos.last_sync', {'path': repo})
    assert got['status'] == 'done', got
    info = got['result']
    assert info['found'] is True
    assert info['result']['ok'] is False and info['result']['error']
    assert any(s.get('step') == 'pull --rebase' and s.get('ok') is False for s in info['result']['steps'])


def test_last_sync_unknown_repo_reports_found_false():
    from core.plugins.loader import load_entry
    from core.plugins.api import PluginAPI
    from core.plugins.settings import SettingsManager
    from core.plugins.events import ActivityJournal, EventBus
    from core.plugins.secrets import SecretManager
    import tempfile

    class M:
        def __init__(self):
            tmp = tempfile.mkdtemp()
            self.secrets = SecretManager(os.path.join(tmp, 'secrets'))
            self.activity = ActivityJournal(os.path.join(tmp, 'activity'))
            self.events = EventBus()
            self.registry = type('R', (), {'get': lambda self, pid: None})()
            self.settings = SettingsManager(os.path.join(tmp, 'state'))

    module = load_entry('repos', PLUGIN_DIR, 'plugin.py')
    ctx = PluginAPI(M(), 'repos')
    assert module.initialize(ctx) is True
    tmp2 = tempfile.mkdtemp()
    repo = make_repo_path(tmp2)
    cap = ctx._get_cap('repos.last_sync')
    out = cap.handler({'path': repo})
    assert out == {'found': False}


def make_repo_path(tmp):
    """Валидный git-репозиторий без записей о Sync (для found=False)."""
    import subprocess as sp
    repo = os.path.join(tmp, 'clean_repo')
    os.makedirs(repo)
    def g(*args):
        sp.run(['git'] + list(args), cwd=repo, check=True, capture_output=True)
    g('init', '-b', 'main')
    g('config', 'user.name', 'tester')
    g('config', 'user.email', 'tester@example.com')
    with open(os.path.join(repo, 'README.md'), 'w') as f:
        f.write('hi\n')
    g('add', '-A')
    g('commit', '-m', 'init')
    return repo


def test_sync_preview_shows_incoming_commits_from_remote(tmp_path):
    """Preview Sync показывает, что ПРИДЁТ с remote (behind + список входящих
    коммитов), даже когда локальных изменений нет — именно это было невидимо
    раньше: sync.bat «синхронизировал» pull-ом, а preview говорил «0 файлов»."""
    remote = str(tmp_path / 'remote.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote], check=True, capture_output=True)
    repo = make_repo(tmp_path)
    subprocess.run(['git', 'remote', 'add', 'origin', remote], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=repo, check=True, capture_output=True)
    # competitor: 2 коммита прямо в remote (как мерж чужого PR)
    other = str(tmp_path / 'other')
    subprocess.run(['git', 'clone', remote, other], check=True, capture_output=True)
    for name, msg in (('a.txt', 'incoming one'), ('b.txt', 'incoming two')):
        subprocess.run(['git', '-C', other, 'config', 'commit.gpgsign', 'false'], check=True, capture_output=True)
        subprocess.run(['git', '-C', other, 'config', 'user.email', 'o@e.c'], check=True, capture_output=True)
        subprocess.run(['git', '-C', other, 'config', 'user.name', 'o'], check=True, capture_output=True)
        with open(os.path.join(other, name), 'w') as f:
            f.write('x\n')
        subprocess.run(['git', '-C', other, 'add', '-A'], check=True, capture_output=True)
        subprocess.run(['git', '-C', other, 'commit', '-m', msg], check=True, capture_output=True)
        subprocess.run(['git', '-C', other, 'push', 'origin', 'main'], check=True, capture_output=True)

    from plugins.repos import repos_service
    prev = repos_service.repo_sync_preview(repo)
    assert prev['ok'] is True, prev
    assert prev['changed'] is False
    assert prev['fetch_ok'] is True, prev
    assert prev['behind'] == 2, prev
    assert prev['ahead'] == 0
    subjects = [c['subject'] for c in prev['incoming']]
    assert 'incoming one' in subjects and 'incoming two' in subjects, prev['incoming']
    assert all(c['sha'] for c in prev['incoming'])

    # snapshot стабилен (fetch не менял рабочее дерево) — Sync пройдёт по этому preview
    st = repos_service.repo_status(repo)
    assert st['ok'] and st['snapshot'] == prev['snapshot']
