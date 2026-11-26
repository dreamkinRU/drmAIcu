# -*- coding: utf-8 -*-
"""Repos: честные подсказки после Sync (refresh_hints/pulled_files).

sync.bat умел сам ставить npm-зависимости при изменении package-lock.json
(шаг 2.7). Плагин команды не запускает (замороженная политика: WRITE только
через гейтвей), но repos.sync возвращает pulled_files и refresh_hints, а
панель «✅ Актуально» честно подсказывает требуемые шаги.
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


def competitor_push(remote, files):
    """Клон remote, коммиты с файлами (name -> content), push — имитация мержа чужих PR."""
    import tempfile
    other = os.path.join(tempfile.mkdtemp(), 'other')
    subprocess.run(['git', 'clone', remote, other], check=True, capture_output=True)
    for name, content in files:
        full = os.path.join(other, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w') as f:
            f.write(content)
    subprocess.run(['git', '-C', other, 'config', 'commit.gpgsign', 'false'], check=True, capture_output=True)
    subprocess.run(['git', '-C', other, 'config', 'user.email', 'o@e.c'], check=True, capture_output=True)
    subprocess.run(['git', '-C', other, 'config', 'user.name', 'o'], check=True, capture_output=True)
    subprocess.run(['git', '-C', other, 'add', '-A'], check=True, capture_output=True)
    subprocess.run(['git', '-C', other, 'commit', '-m', 'remote updates'], check=True, capture_output=True)
    subprocess.run(['git', '-C', other, 'push', 'origin', 'main'], check=True, capture_output=True)


def test_sync_refresh_hints_cover_npm_src_and_py(tmp_path):
    """Sync с pulled-коммитами: refresh_hints покрывают npm/src/.py, pulled_files честный."""
    remote = str(tmp_path / 'remote.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote], check=True, capture_output=True)
    repo = make_repo(tmp_path)
    subprocess.run(['git', 'remote', 'add', 'origin', remote], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=repo, check=True, capture_output=True)
    competitor_push(remote, [
        ('package-lock.json', '{"lockfileVersion": 3}\n'),
        ('src/App.tsx', 'export default function App() { return null }\n'),
        ('core/engine.py', 'NEW = True\n'),
    ])

    from plugins.repos import repos_service
    r = repos_service.repo_sync(repo, '')
    assert r['ok'] is True, r
    assert r['pulled_count'] == 1 and r['pulled'], r
    assert sorted(r['pulled_files']) == ['core/engine.py', 'package-lock.json', 'src/App.tsx'], r['pulled_files']
    hints = ' | '.join(r['refresh_hints'])
    assert 'npm install' in hints, r['refresh_hints']
    assert 'npm run build' in hints, r['refresh_hints']
    assert 'Перезапуск' in hints or 'перезапустите панель' in hints, r['refresh_hints']


def test_sync_without_pulled_commits_has_no_hints(tmp_path):
    """Ничего не пришло с remote — refresh_hints пуст, никаких выдуманных подсказок."""
    remote = str(tmp_path / 'remote.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote], check=True, capture_output=True)
    repo = make_repo(tmp_path)
    subprocess.run(['git', 'remote', 'add', 'origin', remote], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=repo, check=True, capture_output=True)

    from plugins.repos import repos_service
    r = repos_service.repo_sync(repo, '')
    assert r['ok'] is True and r['pulled_count'] == 0, r
    assert r['refresh_hints'] == [] and r['pulled_files'] == [], r


def test_sync_result_persists_with_hints_in_last_sync(tmp_path):
    """Подсказки переживают обновление страницы: repos.last_sync возвращает
    refresh_hints вместе с результатом (state плагина)."""
    remote = str(tmp_path / 'remote.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote], check=True, capture_output=True)
    repo = make_repo(tmp_path)
    subprocess.run(['git', 'remote', 'add', 'origin', remote], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=repo, check=True, capture_output=True)
    competitor_push(remote, [('package-lock.json', '{}\n')])

    from core.plugins.manager import PluginManager
    builtin = str(tmp_path / 'builtin')
    os.makedirs(os.path.join(builtin, 'repos'), exist_ok=True)
    for fn in ('plugin.json', 'plugin.py', 'git_service.py', 'repos_service.py'):
        with open(os.path.join(PLUGIN_DIR, fn), encoding='utf-8') as f:
            with open(os.path.join(builtin, 'repos', fn), 'w', encoding='utf-8') as w:
                w.write(f.read())
    mgr = PluginManager(base_dir=str(tmp_path / 'base'), data_dir=str(tmp_path / 'data'), builtin_dir=builtin)
    mgr.install('builtin:repos')
    mgr.enable('repos')
    rows = [{'permission': row['permission'], 'granted': True} for row in mgr.permissions_status('repos')['permissions']]
    mgr.permissions_put('repos', rows)

    out = mgr.exec('repos', 'repos.sync', {'path': repo, 'message': ''})
    out2 = mgr.confirm(out['confirmation']['id'], True)
    assert out2['status'] == 'done' and out2['result']['ok'], out2
    got = mgr.exec('repos', 'repos.last_sync', {'path': repo})
    res = got['result']['result']
    assert res['ok'] is True and res['pulled_count'] == 1, res
    assert res['refresh_hints'] and 'npm install' in res['refresh_hints'][0], res


def test_ui_contract_refresh_hints_rendered():
    """UI-контракт: панель «Актуально» рендерит подсказки (кириллическая строка в .tsx)."""
    tab = os.path.join(BASE, 'src', 'components', 'tabs', 'RepositoriesTab.tsx')
    with open(tab, encoding='utf-8') as f:
        src = f.read()
    assert 'syncResult.refresh_hints' in src
    assert 'Требуется после обновления' in src
