"""Тесты вкладки «Репозитории»: оранжевая метка «Изменений», карточка текущего
проекта, список файлов открытого репозитория и пути исправления в ошибках
(Sync/commit/push). Ошибки обязаны содержать «Путь исправления» (правило проекта).

Запуск: python -m pytest tests/test_repos_ui_changes.py -q
"""
import os
import subprocess

import pytest

REPOS_TAB = os.path.join(os.path.dirname(__file__), '..', 'src', 'components', 'tabs', 'RepositoriesTab.tsx')
REPOS_SERVICE = os.path.join(os.path.dirname(__file__), '..', 'plugins', 'repos', 'repos_service.py')


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def make_repo(tmp_path, name='repo'):
    """Реальный git-репозиторий с одним коммитом (как в test_repos_plugin)."""
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(['git', 'init', '-b', 'main', str(repo)], check=True, capture_output=True)
    (repo / 'readme.md').write_text('base\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(repo), 'add', '-A'], check=True, capture_output=True)
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    subprocess.run(['git', '-C', str(repo), 'commit', '-m', 'init'], check=True, capture_output=True, env=env)
    return str(repo)


# ==== пути исправления в ошибках (backend) ====

def test_sync_requires_message_error_has_fix_path(tmp_path):
    from plugins.repos import repos_service
    repo = make_repo(tmp_path)
    with open(os.path.join(repo, 'f.txt'), 'w', encoding='utf-8') as f:
        f.write('x')
    res = repos_service.repo_sync(repo, '')
    assert res['ok'] is False, res
    assert 'Путь исправления' in res['error'], res['error']
    assert 'Синхронизировать' in res['error'], res['error']


def test_commit_empty_message_error_has_fix_path(tmp_path):
    from plugins.repos import repos_service
    repo = make_repo(tmp_path)
    r = repos_service.repo_commit(repo, '   ')
    assert r['ok'] is False
    assert 'Путь исправления' in r['error'], r['error']


def test_push_rejected_error_has_fix_path(tmp_path):
    """push отклонён (сервер ушёл вперёд) — сообщение содержит путь исправления."""
    from plugins.repos import repos_service
    remote = str(tmp_path / 'remote.git')
    subprocess.run(['git', 'init', '--bare', '-b', 'main', remote], check=True, capture_output=True)
    repo_a = make_repo(tmp_path, 'repo_a')
    subprocess.run(['git', '-C', repo_a, 'remote', 'add', 'origin', remote], check=True, capture_output=True)
    subprocess.run(['git', '-C', repo_a, 'push', '-u', 'origin', 'main'], check=True, capture_output=True)
    # repo_b — клон удалённого: гарантированно та же история (детерминированный diverge)
    repo_b = str(tmp_path / 'repo_b')
    subprocess.run(['git', 'clone', remote, repo_b], check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t'))
    # оба клона diverge: A коммитит, B коммитит и пушит, затем A пушит -> rejected
    open(os.path.join(repo_a, 'a.txt'), 'w').write('a')
    subprocess.run(['git', '-C', repo_a, 'add', '-A'], check=True, capture_output=True)
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    subprocess.run(['git', '-C', repo_a, 'commit', '-m', 'a'], check=True, capture_output=True, env=env)
    open(os.path.join(repo_b, 'b.txt'), 'w').write('b')
    subprocess.run(['git', '-C', repo_b, 'add', '-A'], check=True, capture_output=True)
    subprocess.run(['git', '-C', repo_b, 'commit', '-m', 'b'], check=True, capture_output=True, env=env)
    subprocess.run(['git', '-C', repo_b, 'push', 'origin', 'main'], check=True, capture_output=True)
    res = repos_service.repo_push(repo_a)
    assert res['ok'] is False
    assert 'Путь исправления' in res['error'], res['error']


# ==== UI-контракт вкладки Репозитории (source contract, как test_docs_hygiene) ====

def test_actions_button_changes_orange_marker_source():
    """Кнопка «Изменения» помечается оранжевым (alert) при незакоммиченных изменениях."""
    src = _read(REPOS_TAB)
    # v.3.12.3: alert теперь считается по числу изменённых файлов (счётчик на кнопке)
    assert 'alert={(status?.entries.length ?? 0) > 0}' in src, (
        'Оранжевая метка кнопки «Изменения» отсутствует. Путь исправления: в RepositoriesTab.tsx '
        'передайте alert={(status?.entries.length ?? 0) > 0} в SectionButton для раздела changes.'
    )
    assert 'bg-amber-500/15' in src, (
        'Стиль оранжевой метки отсутствует. Путь исправления: в SectionButton (RepositoriesTab.tsx) '
        'добавьте ветку alert с классами amber-500.'
    )


def test_repo_info_card_shows_current_project():
    """Карточка «Текущий проект»: путь, ветка, upstream, remote URL — видно, с каким репозиторием работаем."""
    src = _read(REPOS_TAB)
    for needle in ('function RepoInfoCard', 'reposRemote', '\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u043f\u0440\u043e\u0435\u043a\u0442', 'status.branch', 'status.upstream', 'rm.url'):
        assert needle in src, (
            f'Карточка текущего проекта неполная: нет {needle!r}. Путь исправления: компонент RepoInfoCard '
            'в RepositoriesTab.tsx должен показывать путь, ветку, upstream и remote (reposRemote).'
        )
    assert '<RepoInfoCard repoPath={repoPath} status={status} />' in src, (
        'Карточка текущего проекта не встроена в разделы Ветки/Изменения. Путь исправления: '
        'добавьте <RepoInfoCard .../> в BranchesSection и ChangesSection (RepositoriesTab.tsx).'
    )


def test_changes_section_lists_repo_files():
    """«Изменения» показывают список файлов именно открытого репозитория + кнопку «Обновить»."""
    src = _read(REPOS_TAB)
    assert '\u0424\u0430\u0439\u043b\u044b \u0441 \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u044f\u043c\u0438 \u0432 \u044d\u0442\u043e\u043c \u0440\u0435\u043f\u043e\u0437\u0438\u0442\u043e\u0440\u0438\u0438' in src, (
        'Список файлов открытого репозитория отсутствует. Путь исправления: в ChangesSection '
        'отрендерить status.entries (RepositoriesTab.tsx).'
    )
    assert 'const refresh = useCallback(() => { load(); reload(); }' in src, (
        'Кнопка «Обновить» в разделе «Изменения» не подключена. Путь исправления: '
        'ChangesSection должен вызывать load() + reload() (RepositoriesTab.tsx).'
    )


def test_sync_overview_requires_preview_before_write_confirmation():
    src = _read(REPOS_TAB)
    assert 'reposSyncPreview(repoPath)' in src
    assert 'Полный diff (staged + unstaged + untracked)' in src
    assert 'Синхронизировать (add -A → commit → pull --rebase → push, без подтверждения)' in src
    assert 'syncPreview.complete' in src
    assert 'syncPreview.truncated' in src
    assert 'onClick={() => runSync()}' not in src
