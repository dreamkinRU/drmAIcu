"""
Тесты итерации «Репозитории #2»: честная причина ошибки доступа при синхронизации
с изменениями (WinError 5 при os.replace confirmations.json.tmp → confirmations.json,
когда файл мгновенно захватывает антивирус/облачная синхронизация) и её retry-решение,
кнопка «Очистить ошибки» (DELETE /api/logs/issues), время HH:MM UTC+3 в Истории,
модальное окно «⚙ Настройки» со счётчиком изменений на кнопке «Изменения»,
селектор размера шрифта в MD.

Запуск: python -m pytest tests/test_repos_ui2_fixes.py -q
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
REPOS_TAB = os.path.join(ROOT, 'src', 'components', 'tabs', 'RepositoriesTab.tsx')
LOGS_TAB = os.path.join(ROOT, 'src', 'components', 'tabs', 'LogsTab.tsx')
MD_TAB = os.path.join(ROOT, 'src', 'components', 'tabs', 'MDTab.tsx')
USE_LOGS = os.path.join(ROOT, 'src', 'hooks', 'useLogs.ts')
API_SERVICE = os.path.join(ROOT, 'src', 'services', 'api.ts')


def _read(path):
    with io.open(path, encoding='utf-8', newline='') as f:
        return f.read()


# ==== 1. atomicio: retry при временной блокировке (корень «проблемы с доступами») ====

def test_atomicio_retry_survives_transient_lock(monkeypatch):
    """os.replace падает PermissionError дважды, третья попытка успешна — запись должна пройти."""
    tmpdir = os.path.join(ROOT, '.pytest_atomicio_tmp')
    os.makedirs(tmpdir, exist_ok=True)
    target = os.path.join(tmpdir, 'x.json')
    real_replace = os.replace
    state = {'n': 0}

    def flaky(a, b):
        state['n'] += 1
        if state['n'] < 3:
            raise PermissionError(5, 'Отказано в доступе')
        return real_replace(a, b)

    from core.plugins import atomicio
    monkeypatch.setattr(os, 'replace', flaky)
    monkeypatch.setattr(atomicio.time, 'sleep', lambda s: None)
    try:
        atomicio.atomic_write_json(target, {'pending': [{'id': 'c1'}]})
    finally:
        monkeypatch.undo()
    with io.open(target, encoding='utf-8') as f:
        assert json.load(f) == {'pending': [{'id': 'c1'}]}
    assert state['n'] == 3  # честно: было ровно 2 отказа перед успехом


def test_atomicio_permanent_lock_error_has_fix_path(monkeypatch):
    """Блокировка не уходит — отдаём PermissionError с «Путь исправления» и пометкой WinError 5."""
    tmpdir = os.path.join(ROOT, '.pytest_atomicio_tmp')
    os.makedirs(tmpdir, exist_ok=True)
    target = os.path.join(tmpdir, 'y.json')
    with io.open(target, 'w', encoding='utf-8') as f:
        f.write('old')

    from core.plugins import atomicio
    monkeypatch.setattr(os, 'replace', lambda a, b: (_ for _ in ()).throw(PermissionError(5, 'Отказано в доступе')))
    monkeypatch.setattr(atomicio.time, 'sleep', lambda s: None)
    try:
        try:
            atomicio.atomic_write_json(target, {'x': 1})
            raise AssertionError('ожидали PermissionError при постоянной блокировке')
        except PermissionError as e:
            assert 'WinError 5' in str(e) or 'Отказано в доступе' in str(e)
            assert 'Путь исправления' in str(e), str(e)
            assert 'антивирус' in str(e) and 'Mega' in str(e)  # честный путь исправления
    finally:
        monkeypatch.undo()


def test_all_state_managers_use_atomicio_retry():
    """Все 5 менеджеров состояния пишут через atomicio (bare os.replace на tmp убран)."""
    managers = [
        'core/plugins/confirmations.py',
        'core/plugins/permissions.py',
        'core/plugins/registry.py',
        'core/plugins/secrets.py',
        'core/plugins/settings.py',
    ]
    for rel in managers:
        src = _read(os.path.join(ROOT, rel))
        assert 'from .atomicio import atomic_write_json' in src, rel
        assert 'os.replace(tmp, ' not in src, '%s: осталась небезопасная запись os.replace' % rel


# ==== 2. кнопка «Очистить ошибки» ====

def test_journal_clear_issues_removes_only_warn_and_error(tmp_path):
    from core.plugins.events import ActivityJournal
    j = ActivityJournal(str(tmp_path))
    j.add('repos', 'error', 'boom')
    j.add('repos', 'warn', 'hmm')
    j.add('repos', 'info', 'ok')
    j.add('repos', 'action', 'did')
    removed = j.clear_issues()
    assert removed == 2
    left = j.read('repos')
    assert sorted(e['level'] for e in left) == ['action', 'info']


def test_clear_issues_endpoint_filters_core_log():
    """DELETE /api/issues логика: LOG чистится от error/warn, info остаётся (реальный вызов функции)."""
    from api import shared
    saved = list(shared.LOG)
    try:
        shared.LOG[:] = [
            {'time': '10:00:00', 'level': 'error', 'message': 'старая ошибка', 'source': 'Т'},
            {'time': '10:00:01', 'level': 'warn', 'message': 'старое предупреждение', 'source': 'Т'},
            {'time': '10:00:02', 'level': 'info', 'message': 'обычное событие', 'source': 'Т'},
        ]
        from api.routes_system import s_logs_clear_issues
        resp = s_logs_clear_issues()
        data = json.loads(resp.body)
        assert data['success'] is True and data['removed'] == 2
        assert [e['level'] for e in shared.LOG] == ['info']
    finally:
        shared.LOG[:] = saved


def test_logs_tab_has_clear_errors_button():
    src = _read(LOGS_TAB)
    assert 'onClearIssues' in src, 'LogsTab должен принимать onClearIssues'
    assert 'Очистить ошибки' in src, 'нет кнопки очистки ошибок; путь исправления: добавить кнопку в LogsTab рядом с фильтрами'
    uses = _read(USE_LOGS)
    assert 'clearIssues' in uses and "prev.filter(l => l.level !== 'error' && l.level !== 'warn')" in uses
    api = _read(API_SERVICE)
    assert "fetch('/api/logs/issues', { method: 'DELETE' })" in api, 'нет DELETE-запроса очистки на бэкенд'


# ==== 9. История: время HH:MM UTC+3 (без метки «UTC+3» в строке — сама конвертация осталась) ====

def test_history_shows_time_utc3():
    src = _read(REPOS_TAB)
    assert 'timeUtc3' in src, 'нет функции времени UTC+3; путь исправления: добавить конвертацию ISO-даты в HistorySection'
    assert "timeZone: 'Europe/Moscow'" in src, 'зона должна быть фиксированной (Europe/Moscow = UTC+3)'
    # с PR #40 метка «UTC+3» из строки истории убрана (пользовательская просьба) —
    # но конвертация в Europe/Moscow обязана остаться.
    assert "{c.author}" not in src, 'автор коммита больше не показывается в строке истории'
    assert 'hour: \'2-digit\', minute: \'2-digit\', hour12: false' in src, 'формат HH:MM 24-часовой'


# ==== 4. морфология настроек: модальное окно, счётчик на кнопке ====

def test_settings_opened_from_button_after_changes():
    src = _read(REPOS_TAB)
    assert 'SettingsModal' in src, 'нет модального окна настроек'
    assert '⚙ Настройки' in src, 'нет кнопки ⚙ Настройки'
    i_btn = src.index("⚙ Настройки</SectionButton>")
    i_chg = src.index("active={section === 'changes'}")
    assert i_chg < i_btn, 'кнопка «⚙ Настройки» должна стоять ПОСЛЕ кнопки «Изменения»'


def test_changes_button_carries_counter():
    src = _read(REPOS_TAB)
    assert 'Изменения{status && status.entries.length > 0 ? ` (${status.entries.length})`' in src, \
        'счётчик изменений должен отображаться прямо на кнопке «Изменения»'


def test_path_bar_right_side_counters_removed():
    src = _read(REPOS_TAB)
    assert 'изменённых</span>' not in src, 'правая часть path bar (счётчики) должна быть убрана'


# ==== 5. MDTab: компактные кнопки + селектор размера шрифта ====

def test_md_tab_font_selector_before_view_buttons():
    src = _read(MD_TAB)
    assert 'drmAIcu.md.fontPx' in src, 'нет сохранения размера шрифта; путь исправления: localStorage drmAIcu.md.fontPx'
    assert 'MD_FONT_OPTIONS' in src, 'нет набора вариантов размера шрифта'
    assert 'DEFAULT_FONT_PX = 15' in src, 'шрифт содержимого должен быть на пункт меньше (15 вместо 16)'
    i_sel = src.index('<select')
    i_view = src.index("👁 Просмотр")
    assert i_sel < i_view, 'селектор размера шрифта должен стоять ПЕРЕД кнопками Просмотр/Редактор'
    assert 'style={{ fontSize: fontPx }}' in src, 'размер шрифта должен применяться к окну содержимого'


def test_md_tab_buttons_compact():
    src = _read(MD_TAB)
    assert 'px-3 py-1 text-xs font-semibold' in src, 'кнопки Просмотр/Редактор должны быть ниже (py-1)'
    assert 'px-4 py-2 rounded-lg bg-emerald-500' not in src, 'кнопка «Сохранить» должна стать ниже'
