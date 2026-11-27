"""Repos Plugin: манифест, capability-политики, реальные git-операции (локально, без сети)."""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.join(BASE, 'plugins', 'repos')


def make_repo(tmp_path):
    """Коммитающий репозиторий с настроенным user.name/email."""
    repo = str(tmp_path / 'repo')
    os.makedirs(repo)
    def g(*args):
        subprocess.run(['git'] + list(args), cwd=repo, check=True, capture_output=True)
    g('init', '-b', 'main')
    g('config', 'user.name', 'tester')
    g('config', 'user.email', 'tester@example.com')
    with open(os.path.join(repo, 'README.md'), 'w') as f:
        f.write('hi\n')
    g('add', '-A')
    g('commit', '-m', 'init')
    return repo


def make_ctx(manager_cls=None):
    from core.plugins.loader import load_entry
    from core.plugins.api import PluginAPI
    import tempfile
    from core.plugins.events import ActivityJournal, EventBus
    from core.plugins.secrets import SecretManager

    class FakeManager:
        def __init__(self):
            tmp = tempfile.mkdtemp()
            self.secrets = SecretManager(os.path.join(tmp, 'secrets'))
            self.activity = ActivityJournal(os.path.join(tmp, 'activity'))
            self.events = EventBus()
            self.registry = type('R', (), {'get': lambda self, pid: None})()
            from core.plugins.settings import SettingsManager
            self.settings = SettingsManager(os.path.join(tmp, 'state'))

    module = load_entry('repos', PLUGIN_DIR, 'plugin.py')
    ctx = PluginAPI(FakeManager(), 'repos')
    assert module.initialize(ctx) is True
    return module, ctx


def test_initialize_fails_fast_on_mixed_versions(monkeypatch):
    """Частичная синхронизация (новый plugin.py + старый repos_service) — понятная ошибка старта,
    а не capability_failed на каждый вызов (класс отказа: облако удерживало файл при git pull)."""
    import types
    module, ctx = make_ctx()
    funcs = {n: (lambda *a, **k: None)
             for n in module._REQUIRED_SERVICE_FUNCS if n != 'repo_rebase_state'}
    monkeypatch.setattr(module, 'repos_service', types.SimpleNamespace(**funcs))
    with pytest.raises(RuntimeError) as ei:
        module.initialize(ctx)
    msg = str(ei.value)
    assert 'разноверсионные' in msg
    assert 'repo_rebase_state' in msg
    assert 'Путь исправления' in msg


def test_manifest_valid():
    from core.plugins.models import validate_manifest
    with open(os.path.join(PLUGIN_DIR, 'plugin.json'), encoding='utf-8') as f:
        data = json.load(f)
    manifest, errors = validate_manifest(data)
    assert manifest is not None, errors
    assert data['id'] == 'repos' and data['api_version'] == '1.0'
    # GitHub App полностью удалён: никаких секретов и App-полей в манифесте
    assert data.get('settings_schema', {}).get('private_key') is None
    assert 'app_id' not in data.get('settings_schema', {})


def test_entry_registers_capabilities_with_policies():
    module, ctx = make_ctx()
    caps = {c['name']: c for c in ctx.capabilities()}
    # READ — auto
    for name in ('repos.status', 'repos.log', 'repos.branches', 'repos.remote',
                 'repos.diff', 'repos.read_file', 'repos.diagnostics'):
        assert caps[name]['policy'] == 'auto', name
        assert caps[name]['permission'] == 'repos.read'
    # WRITE — confirm
    for name in ('repos.add', 'repos.commit', 'repos.push', 'repos.pull',
                 'repos.fetch', 'repos.checkout'):
        assert caps[name]['policy'] == 'confirm', name
        assert caps[name]['permission'] == 'repos.write'
    # Sync — отдельное разрешение, один пакет; без подтверждения (решение заказчика 26.11.2026)
    assert caps['repos.sync']['permission'] == 'repos.sync'
    assert caps['repos.sync']['policy'] == 'auto'


def test_diagnostics_and_status(tmp_path):
    from plugins.repos import repos_service
    d = repos_service.diagnostics()
    assert d['git'] is True and 'git' in (d['version'] or '')
    repo = make_repo(tmp_path)
    st = repos_service.repo_status(repo)
    assert st['ok'] and st['branch'] == 'main' and st['changed'] is False
    # несуществующий / не-git путь — честная ошибка
    with pytest.raises(Exception):
        repos_service.repo_status(str(tmp_path / 'nope'))


def test_log_and_branches(tmp_path):
    from plugins.repos import repos_service
    repo = make_repo(tmp_path)
    lg = repos_service.repo_log(repo, limit=5)
    assert lg['ok'] and lg['commits'][0]['subject'] == 'init'
    br = repos_service.repo_branches(repo)
    assert br['ok'] and br['current'] == 'main'
    assert any(b['name'] == 'main' for b in br['branches'])


def test_read_file_and_traversal_protection(tmp_path):
    from plugins.repos import repos_service
    repo = make_repo(tmp_path)
    r = repos_service.read_file(repo, 'README.md')
    assert r['ok'] and 'hi' in r['content']
    bad = repos_service.read_file(repo, '../outside.txt')
    assert bad['ok'] is False
    bad2 = repos_service.read_file(repo, '/etc/hostname')
    assert bad2['ok'] is False


def test_add_commit_ready_requires_confirmation(tmp_path):
    """WRITE-операции не выполняются без подтверждения пользователя."""
    from core.plugins.manager import PluginManager
    base = str(tmp_path / 'base')
    os.makedirs(base, exist_ok=True)
    data = tmp_path / 'data'
    builtin = tmp_path / 'builtin'
    (builtin / 'repos').mkdir(parents=True)
    for fn in ('plugin.json', 'plugin.py', 'git_service.py', 'repos_service.py'):
        with open(os.path.join(PLUGIN_DIR, fn), encoding='utf-8') as f:
            (builtin / 'repos' / fn).write_text(f.read(), encoding='utf-8')
    mgr = PluginManager(base_dir=base, data_dir=str(data), builtin_dir=str(builtin))
    mgr.install('builtin:repos')
    mgr.enable('repos')
    rows = [{'permission': row['permission'], 'granted': True}
            for row in mgr.permissions_status('repos')['permissions']]
    mgr.permissions_put('repos', rows)
    repo = make_repo(tmp_path)
    with open(os.path.join(repo, 'new.txt'), 'w') as f:
        f.write('x\n')
    out = mgr.exec('repos', 'repos.add', {'path': repo})
    assert out['status'] == 'confirmation_required'
    assert out['confirmation']['policy'] == 'confirm'
    # READ при этом выполняется сразу (auto)
    out2 = mgr.exec('repos', 'repos.status', {'path': repo})
    assert out2['status'] == 'done' and out2['result']['ok']


def test_commit_rejects_empty_message(tmp_path):
    from plugins.repos import repos_service
    repo = make_repo(tmp_path)
    r = repos_service.repo_commit(repo, '   ')
    assert r['ok'] is False and 'сообщение' in r['error']


def test_full_sync_package(tmp_path):
    """Полная замена sync.bat: add -> commit -> pull --rebase -> push в bare-remote."""
    from plugins.repos import repos_service
    remote = str(tmp_path / 'remote.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote], check=True, capture_output=True)
    repo = make_repo(tmp_path)
    subprocess.run(['git', 'remote', 'add', 'origin', remote], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=repo, check=True, capture_output=True)

    # изменение -> sync с сообщением
    with open(os.path.join(repo, 'new.txt'), 'w') as f:
        f.write('data\n')
    res = repos_service.repo_sync(repo, 'feat: новая фича')
    assert res['ok'], res
    step_names = [s['step'] for s in res['steps']]
    assert step_names == ['status', 'add', 'commit', 'pull --rebase', 'merged_pr_check', 'push'], step_names
    assert res['committed'] is True and res['commit_sha']
    # коммит реально на удалённом
    out = subprocess.run(['git', 'log', '--oneline', '-1'], cwd=remote, capture_output=True, text=True, encoding='utf-8', errors='replace')
    assert 'feat: новая фича' in out.stdout

    # sync без изменений — без нового коммита, но с pull/push
    res2 = repos_service.repo_sync(repo, 'ignored-msg')
    assert res2['ok'] and res2['committed'] is False


def test_sync_without_changes_and_empty_message_still_syncs(tmp_path):
    """Как в sync.bat: если изменений нет — пустое сообщение допустимо, pull/push идут."""
    from plugins.repos import repos_service
    remote = str(tmp_path / 'remote.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote], check=True, capture_output=True)
    repo = make_repo(tmp_path)
    subprocess.run(['git', 'remote', 'add', 'origin', remote], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=repo, check=True, capture_output=True)
    res = repos_service.repo_sync(repo, '')
    assert res['ok'], res
    add_step = [s for s in res['steps'] if s['step'] == 'add'][0]
    assert add_step.get('skipped') is True


def test_sync_requires_message_when_changes_exist(tmp_path):
    from plugins.repos import repos_service
    repo = make_repo(tmp_path)
    with open(os.path.join(repo, 'f.txt'), 'w') as f:
        f.write('x')
    res = repos_service.repo_sync(repo, '')
    assert res['ok'] is False
    assert 'сообщение коммита' in res['error']
    # и ничего не закоммичено
    out = subprocess.run(['git', 'status', '--porcelain'], cwd=repo, capture_output=True, text=True)
    assert out.stdout.strip() != ''


def test_git_allowlist_rejects_dangerous_commands(tmp_path):
    """allowlist блокирует произвольные подкоманды git (v1-контракт §5.2).
    Ограничения флагов (config --global) в v1 не входят: capability плагина
    вообще не выставляют `config`, поэтому путь к ним недоступен."""
    from plugins.repos.git_service import GitCommandRejected, run_git
    repo = make_repo(tmp_path)
    with pytest.raises(GitCommandRejected):
        run_git(['rm', '-rf', '/'], cwd=repo)
    with pytest.raises(GitCommandRejected):
        run_git(['format-patch', 'HEAD~1'], cwd=repo)
    assert run_git(['status', '--porcelain'], cwd=repo)['ok'] is True


def test_sync_exec_flow_through_manager(tmp_path):
    """Сквозной поток через реальный PluginManager: exec выполняет пакет сразу
    (repos.sync — auto, решение заказчика 26.11.2026; замена sync.bat)."""
    from core.plugins.manager import PluginManager

    remote = str(tmp_path / 'remote.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote], check=True, capture_output=True)
    repo = make_repo(tmp_path)
    subprocess.run(['git', 'remote', 'add', 'origin', remote], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=repo, check=True, capture_output=True)
    with open(os.path.join(repo, 'g.txt'), 'w') as f:
        f.write('gw\n')

    builtin = tmp_path / 'builtin'
    builtin.mkdir()
    (builtin / 'repos').mkdir()
    for fn in ('plugin.json', 'plugin.py', 'git_service.py', 'repos_service.py'):
        with open(os.path.join(PLUGIN_DIR, fn), encoding='utf-8') as f:
            (builtin / 'repos' / fn).write_text(f.read(), encoding='utf-8')

    base = str(tmp_path / 'base')
    os.makedirs(base, exist_ok=True)
    mgr = PluginManager(base_dir=base, data_dir=str(tmp_path / 'data'), builtin_dir=str(builtin))
    mgr.install('builtin:repos')
    mgr.enable('repos')
    # выдать WRITE-разрешения (READ выдаётся при установке автоматически)
    rows = []
    st = mgr.permissions_status('repos')
    for row in st['permissions']:
        rows.append({'permission': row['permission'], 'granted': True})
    mgr.permissions_put('repos', rows)

    from plugins.repos import repos_service
    params = {'path': repo, 'message': 'e2e sync через gateway', 'snapshot': repos_service.repo_status(repo)['snapshot']}
    out2 = mgr.exec('repos', 'repos.sync', params)
    assert out2['status'] == 'done', out2
    result = out2['result']
    assert result['ok'], result
    assert result['committed'] is True and result['commit_sha']
    step_names = [s['step'] for s in result['steps']]
    assert 'commit' in step_names and 'push' in step_names
    # коммит реально ушёл в bare-remote
    out_log = subprocess.run(['git', 'log', '--oneline', '-1'], cwd=remote, capture_output=True, text=True, encoding='utf-8', errors='replace')
    assert 'e2e sync через gateway' in out_log.stdout
    # auto-капабилити не принимает confirmation_token — честный отказ
    from core.plugins.api import GatewayBlocked
    with pytest.raises(GatewayBlocked):
        mgr.exec('repos', 'repos.sync', params, confirmation_token='stale-token')


def test_rebase_recovery_reports_conflicts_and_requires_explicit_actions(tmp_path):
    """Портировано из PR #41: конфликт при pull --rebase диагностируется, recovery — явные WRITE-действия."""
    from plugins.repos import repos_service
    remote = str(tmp_path / 'remote.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote], check=True, capture_output=True)
    local = make_repo(tmp_path)
    # подпись коммитов в тестовом окружении недоступна — отключаем явно
    subprocess.run(['git', '-C', local, 'config', 'commit.gpgsign', 'false'], check=True, capture_output=True)
    subprocess.run(['git', '-C', local, 'remote', 'add', 'origin', remote], check=True, capture_output=True)
    subprocess.run(['git', '-C', local, 'push', '-u', 'origin', 'main'], check=True, capture_output=True)
    other = str(tmp_path / 'other')
    subprocess.run(['git', 'clone', remote, other], check=True, capture_output=True)
    subprocess.run(['git', '-C', other, 'config', 'commit.gpgsign', 'false'], check=True, capture_output=True)
    env = dict(os.environ, GIT_AUTHOR_NAME='tester', GIT_AUTHOR_EMAIL='tester@example.com',
               GIT_COMMITTER_NAME='tester', GIT_COMMITTER_EMAIL='tester@example.com')
    with open(os.path.join(other, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('remote version\n')
    subprocess.run(['git', '-C', other, 'commit', '-am', 'remote change'], check=True, capture_output=True, env=env)
    subprocess.run(['git', '-C', other, 'push', 'origin', 'main'], check=True, capture_output=True)
    with open(os.path.join(local, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('local version\n')
    subprocess.run(['git', '-C', local, 'commit', '-am', 'local change'], check=True, capture_output=True, env=env)

    pulled = repos_service.repo_pull(local, rebase=True)
    assert pulled['ok'] is False and pulled.get('rebase_conflict') is True
    state = repos_service.repo_rebase_state(local)
    assert state['ok'] and state['active'] and 'README.md' in state['conflicts']
    # продолжить с неразрешёнными конфликтами нельзя — ошибка с путём исправления
    blocked = repos_service.repo_rebase_continue(local)
    assert blocked['ok'] is False and blocked.get('conflicts')
    with open(os.path.join(local, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('resolved version\n')
    subprocess.run(['git', '-C', local, 'add', 'README.md'], check=True, capture_output=True)
    continued = repos_service.repo_rebase_continue(local)
    assert continued['ok'], continued
    final = repos_service.repo_rebase_state(local)
    assert final['ok'] and final['active'] is False
    # rebase --abort вне rebase — честная ошибка, а не fake-успех
    aborted = repos_service.repo_rebase_abort(local)
    assert aborted['ok'] is False and 'rebase' in aborted['error']


def test_sync_aborts_when_staged_tree_changes_before_commit(tmp_path, monkeypatch):
    from plugins.repos import repos_service

    repo = make_repo(tmp_path)
    with open(os.path.join(repo, 'README.md'), 'w', encoding='utf-8') as handle:
        handle.write('approved content\n')
    snapshot = repos_service.repo_sync_snapshot(repo)['snapshot']
    original_run = repos_service._r
    write_tree_calls = {'count': 0}

    def concurrent_index_change(args, path=None, timeout=None):
        result = original_run(args, path, timeout or repos_service.git_service.DEFAULT_TIMEOUT)
        if args == ['write-tree']:
            write_tree_calls['count'] += 1
            if write_tree_calls['count'] == 2:
                result = dict(result)
                result['stdout'] = 'externally-changed-tree\n'
        return result

    monkeypatch.setattr(repos_service, '_r', concurrent_index_change)
    before = subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()

    result = repos_service.repo_sync(repo, 'test: approved tree', snapshot)

    after = subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    assert result['ok'] is False
    assert result['snapshot_changed'] is True
    assert 'index изменился' in result['error']
    assert before == after
