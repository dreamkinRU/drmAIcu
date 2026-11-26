# -*- coding: utf-8 -*-
"""Тесты итерации «Репозитории #3» (после PR #39):

1. repo_log отдаёт body коммита (многострочный) через RS/US-разделители.
2. История: без автора, без метки «UTC+3», tooltip с полным текстом коммита,
   мерж-коммиты не рисуются строками, а входят в tooltip ближайшего нижнего коммита.
3. Путь репозитория — под заголовком «📁 Репозитории», плашка RepoPathBar удалена.
4. Диалог подтверждения перед синхронизацией при наличии локальных изменений.
5. Красный блок с ошибкой и путём исправления при неудачной синхронизации.
6. confirmation_required в журнале плагинов — уровень info (штатная механика, не ошибка).
"""

import os
import subprocess
import tempfile

import pytest

from plugins.repos.repos_service import repo_log

REPOS_TAB = os.path.join('src', 'components', 'tabs', 'RepositoriesTab.tsx')
TYPES = os.path.join('src', 'types', 'index.ts')
PLUGIN_API = os.path.join('core', 'plugins', 'api.py')


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


# ==== 1. repo_log: тело коммита ====

def _git(*args, cwd):
    subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture()
def git_repo():
    d = tempfile.mkdtemp(prefix='pytest_repo_log_')
    _git('init', '-q', '-b', 'main', cwd=d)
    _git('config', 'user.name', 'tester', cwd=d)
    _git('config', 'user.email', 'tester@example.com', cwd=d)
    _git('-c', 'commit.gpgsign=false', 'commit', '-q', '--allow-empty',
         '-m', 'тема коммита\n\nпервая строка тела\nвторая строка тела', cwd=d)
    _git('-c', 'commit.gpgsign=false', 'commit', '-q', '--allow-empty',
         '-m', 'Merge pull request #99 from someone/branch', cwd=d)
    return d


def test_repo_log_returns_multiline_body(git_repo):
    r = repo_log(git_repo, 10)
    assert r['ok'] is True, r.get('error')
    by_subject = {c['subject']: c for c in r['commits']}
    c = by_subject['тема коммита']
    assert c['body'] == 'первая строка тела\nвторая строка тела'
    assert c['sha'] and c['date'] and c['author'] == 'tester'


def test_repo_log_merge_commit_present_for_lineage(git_repo):
    """Мерж-коммит ДОЛЖЕН приходить с бэкенда (по нему строится lineage во фронте)."""
    r = repo_log(git_repo, 10)
    subjects = [c['subject'] for c in r['commits']]
    assert any(s.startswith('Merge pull request') for s in subjects)


def test_repo_log_body_empty_when_no_body(git_repo):
    d = tempfile.mkdtemp(prefix='pytest_repo_log2_')
    _git('init', '-q', '-b', 'main', cwd=d)
    _git('config', 'user.name', 'tester', cwd=d)
    _git('config', 'user.email', 'tester@example.com', cwd=d)
    _git('-c', 'commit.gpgsign=false', 'commit', '-q', '--allow-empty', '-m', 'only subject', cwd=d)
    r = repo_log(d, 5)
    assert r['ok'] and r['commits'][0]['body'] == ''


# ==== 2. История: фронт-контракты ====

def test_history_row_no_author_and_no_utc3_label():
    src = _read(REPOS_TAB)
    assert '{c.author}' not in src, 'автор не должен показываться в строке истории; путь исправления: убрать {c.author} из HistorySection'
    assert '{timeUtc3(c.date)} UTC+3' not in src, 'метка «UTC+3» убрана из строки (конвертация Europe/Moscow остаётся)'


def test_history_merge_rows_filtered_and_lineage_tooltip():
    src = _read(REPOS_TAB)
    assert "c.subject.startsWith('Merge ')" in src, 'мерж-коммиты не должны рисоваться отдельными строками'
    assert 'rows.map(({ c, merge })' in src, 'lineage: обычному коммиту подставляется ближайший мерж'
    assert 'title={fullTip}' in src, 'нет tooltip на строке коммита'
    assert 'вошёл через мерж' in src, 'в tooltip должна попасть информация о мерже'
    assert 'c.body' in src, 'в tooltip должен входить полный текст коммита (body)'


def test_repo_commit_type_has_body():
    src = _read(TYPES)
    assert 'body?: string;' in src, 'RepoCommit.body не объявлен в типах'


# ==== 3. Путь под заголовком, плашка сверху удалена ====

def test_path_shown_after_heading_no_pathbar():
    src = _read(REPOS_TAB)
    assert 'RepoPathBar' not in src, 'плашка RepoPathBar должна быть удалена'
    i_head = src.index('📁 Репозитории</h2>')
    i_path = src.index('Текущий проект:')
    assert i_head < i_path, 'путь должен идти ПОСЛЕ заголовка «📁 Репозитории»'
    assert '{repoPath}' in src, 'путь не отображается под заголовком'


# ==== 4. Диалог подтверждения перед sync при локальных изменениях ====

def test_sync_confirm_dialog_contract():
    src = _read(REPOS_TAB)
    assert 'syncConfirm' in src, 'нет состояния диалога подтверждения синхронизации'
    assert "status.entries.length > 0 ? setSyncConfirm(true) : runSync()" in src, \
        'кнопка «Синхронизировать» должна открывать диалог только при наличии изменений'
    assert 'Продолжить' in src and 'Отмена' in src, 'в диалоге должны быть кнопки Продолжить/Отмена'
    assert 'git add -A' in src, 'в диалоге должен быть показан план операций'
    assert '!commitMsg.trim()' in src, 'Продолжить должно быть заблокировано при пустом сообщении'


# ==== 5. Блок ошибки синхронизации с путём исправления ====

def test_sync_failure_block_shows_error_and_fix_path():
    src = _read(REPOS_TAB)
    assert '!syncResult.ok &&' in src, 'нет блока ошибки при неудачной синхронизации'
    assert 'whitespace-pre-wrap' in src, 'текст ошибки (с «Путь исправления: …») должен переноситься построчно'
    svc = _read(os.path.join('plugins', 'repos', 'repos_service.py'))
    # честность: ошибка каждого упавшего шага попадает в верхний level error ответа
    assert "'Путь исправления:" in svc or 'Путь исправления' in svc, 'ошибки sync должны содержать путь исправления'


# ==== 6. confirmation_required — это info, не warn ====

def test_confirmation_required_logged_as_info():
    src = _read(PLUGIN_API)
    assert "self.log('info', 'confirmation_required'" in src, \
        'confirmation_required — штатная механика WRITE-подтверждения, уровень должен быть info; ' \
        'путь исправления: core/plugins/api.py — self.log(\'warn\', ...) заменить на self.log(\'info\', ...)'
    assert "self.log('warn', 'confirmation_required'" not in src, 'старый уровень warn остался'
