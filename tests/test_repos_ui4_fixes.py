# -*- coding: utf-8 -*-
"""Тесты итерации «Репозитории #4» (консолидация PR #41 + UX-правки):

1. Результат Sync показывается ВСЕГДА после попытки — и при успехе, и при ошибке
   (постоянная панель с итогом и шагами, а не только исчезающая плашка).
2. Нативный title-tooltip в Истории заменён модальным окном CommitModal.
3. Кнопка «Перейти к подтверждению WRITE» не показывается, когда изменений нет
   (вместо неё — нейтральное продолжение pull --rebase → push).
4. Rebase recovery (портировано из PR #41): баннер незавершённого rebase с
   явными WRITE-действиями rebase --continue / rebase --abort.
"""

import os

REPOS_TAB = os.path.join('src', 'components', 'tabs', 'RepositoriesTab.tsx')
REPOS_SVC = os.path.join('plugins', 'repos', 'repos_service.py')
REPOS_PLUGIN = os.path.join('plugins', 'repos', 'plugin.py')
GIT_SERVICE = os.path.join('plugins', 'repos', 'git_service.py')
REPOS_TS = os.path.join('src', 'services', 'repos.ts')


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


# ==== 1. Результат Sync виден всегда (и при успехе) ====

def test_sync_result_panel_has_always_visible_header():
    src = _read(REPOS_TAB)
    assert 'Синхронизация выполнена' in src, \
        'при успешном Sync панель результата должна явно называть итог (что произошло)'
    assert 'Синхронизация не завершена' in src, \
        'при неуспешном Sync панель результата должна явно называть итог'
    assert 'syncResult.ok' in src, 'итог должен выбираться по syncResult.ok'
    assert 'syncResult.steps.map' in src, 'панель результата должна показывать шаги (что именно произошло)'
    assert 'syncResult.head' in src, 'панель результата должна показывать HEAD'


def test_backend_reports_committed_and_head():
    src = _read(REPOS_SVC)
    assert "'committed': changes" in src, 'ответ sync должен честно сообщать, был ли создан commit'
    assert "'head':" in src, 'ответ sync должен сообщать итоговый HEAD'


# ==== 2. Модальное окно деталей коммита вместо title-tooltip ====

def test_history_uses_commit_modal_instead_of_native_tooltip():
    src = _read(REPOS_TAB)
    assert 'title={fullTip}' not in src, 'нативный title-tooltip удалён'
    assert 'CommitModal' in src, 'есть модальное окно деталей коммита'
    assert "onClick={() => setSelected({ c, merge })}" in src, 'строка коммита кликабельна и открывает модалку'
    assert "e.key === 'Escape'" in src, 'модалка закрывается по Escape'
    assert '(UTC+3)' in src, 'модалка показывает время в UTC+3'
    assert 'commit.body' in src, 'модалка показывает полное тело коммита'


# ==== 3. Без изменений — без кнопки «Перейти к подтверждению WRITE» ====

def test_write_confirmation_button_hidden_when_no_changes():
    src = _read(REPOS_TAB)
    assert 'syncPreview.snapshot_files.length === 0' in src, \
        'при пустом списке файлов нельзя показывать WRITE-кнопку подтверждения'
    assert 'Продолжить без коммита' in src, \
        'вместо WRITE-кнопки — нейтральное продолжение (pull --rebase → push)'
    # нейтральная ветка идёт раньше amber-кнопки и является условием
    assert src.index('Продолжить без коммита') < src.index('Перейти к подтверждению WRITE')


# ==== 4. Rebase recovery (PR #41) ====

def test_rebase_recovery_has_explicit_confirmed_actions():
    src = _read(REPOS_TAB)
    assert 'reposRebaseState' in src
    assert 'reposRebaseContinue' in src and 'reposRebaseAbort' in src
    assert 'rebase --continue' in src and 'rebase --abort' in src
    assert 'rebaseState.conflicts.map' in src
    assert 'disabled={rebaseState.conflicts.length > 0}' in src


def test_rebase_capabilities_registered_and_allowlisted():
    plugin = _read(REPOS_PLUGIN)
    assert "reg('repos.rebase_state', 'repos.read'" in plugin, 'rebase_state — READ, auto'
    assert "reg('repos.rebase_continue', 'repos.write'" in plugin, 'rebase_continue — WRITE, с подтверждением'
    assert "reg('repos.rebase_abort', 'repos.write'" in plugin, 'rebase_abort — WRITE, с подтверждением'
    svc = _read(REPOS_SVC)
    assert 'def repo_rebase_state' in svc and 'def repo_rebase_continue' in svc and 'def repo_rebase_abort' in svc
    gs = _read(GIT_SERVICE)
    assert "'rebase'" in gs, 'rebase должен быть в allowlist git_service'
    assert 'core.editor=:' in gs, 'разрешён только неинтерактивный префикс -c core.editor=: для rebase'
    ts = _read(REPOS_TS)
    assert 'reposRebaseState' in ts and 'reposRebaseContinue' in ts and 'reposRebaseAbort' in ts



# ==== 5. Персистентный последний результат Sync (state плагина, §9.1) ====

def test_last_sync_persisted_in_plugin_state_and_restored_by_ui():
    """Результат Sync переживает обновление страницы: repos.sync пишет его в
    state плагина (ctx.save_state), repos.last_sync (READ/auto) возвращает,
    UI восстанавливает панель при монтировании и показывает время попытки."""
    plugin = _read(REPOS_PLUGIN)
    assert "reg('repos.last_sync', 'repos.read'" in plugin, \
        'repos.last_sync — READ, auto (доступен без подтверждения)'
    assert '_remember_sync' in plugin and 'last_sync_by_path' in plugin, \
        'результат Sync сохраняется в state плагина'
    assert 'ctx.save_state' in plugin and 'ctx.load_state' in plugin

    tab = _read(REPOS_TAB)
    assert 'refreshLastSync' in tab, 'панель результата восстанавливается при монтировании'
    assert 'reposLastSync(' in tab, 'UI запрашивает последний результат Sync с бэкенда'
    assert 'последняя попытка' in tab, 'показывается время последней попытки Sync'

    # capability есть в service-слое frontend
    svc = _read(REPOS_TS)
    assert 'repos.last_sync' in svc
