# -*- coding: utf-8 -*-
"""Устойчивость к блокировкам файлов состояния (WinError 5, кейс пользователя).

Проект пользователя лежал в папке облачной синхронизации (G:\\Mega\\): клиент Mega
удерживал data/plugins/registry.json дольше окна retry — плагин падал в error и
вкладка «Репозитории» становилась недоступной. Теперь: (1) окно retry увеличено,
(2) сбой записи реестра НЕ роняет плагин — состояние живёт в памяти, деградация
видна в health/data_warnings и в баннере вкладки «Плагины».
"""
import json
import os
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.plugins.atomicio import atomic_write, RETRY_ATTEMPTS  # noqa: E402


def test_retry_window_is_wide_enough_for_cloud_sync():
    """Окно retry: 20 попыток, задержка до 1 с (Mega держит файлы дольше 3.5 с)."""
    assert RETRY_ATTEMPTS >= 20
    import core.plugins.atomicio as a
    assert a.RETRY_MAX_DELAY >= 1.0


def test_retry_survives_transient_lock(tmp_path, monkeypatch):
    """Блокировка отпустила на 5-й попытке — запись успешна, tmp заменён."""
    import core.plugins.atomicio as a
    target = str(tmp_path / 'x.json')
    with open(target, 'w', encoding='utf-8') as f:
        f.write('old')
    real_replace = os.replace
    calls = {'n': 0}

    def flaky(src, dst):
        calls['n'] += 1
        if calls['n'] <= 5:
            raise PermissionError(5, 'Отказано в доступе')
        return real_replace(src, dst)

    monkeypatch.setattr(a.os, 'replace', flaky)
    monkeypatch.setattr(a.time, 'sleep', lambda *_: None)
    atomic_write(target, 'new content')
    with open(target, encoding='utf-8') as f:
        assert f.read() == 'new content'
    assert calls['n'] == 6


def test_retry_exhaustion_honest_error_with_fix_path(tmp_path, monkeypatch):
    """Файл не отпустили — честная ошибка WinError 5 с путём исправления."""
    import core.plugins.atomicio as a
    target = str(tmp_path / 'y.json')
    real_replace = os.replace

    def locked(src, dst):
        raise PermissionError(5, 'Отказано в доступе')

    monkeypatch.setattr(a.os, 'replace', locked)
    monkeypatch.setattr(a.time, 'sleep', lambda *_: None)
    with pytest.raises(PermissionError) as ei:
        atomic_write(target, 'x')
    msg = str(ei.value)
    assert 'WinError 5' in msg and str(RETRY_ATTEMPTS) in msg
    assert 'Путь исправления' in msg and 'Mega' in msg


def test_registry_update_survives_locked_file(tmp_path, monkeypatch):
    """Сбой записи registry.json НЕ роняет update(): состояние в памяти + persist_error."""
    from core.plugins.registry import PluginRegistry
    from core.plugins.models import PluginRecord, PluginStatus

    reg = PluginRegistry(str(tmp_path / 'registry.json'))
    rec = PluginRecord(id='p1', name='P1', version='1.0.0', api_version='1.0')
    reg.upsert(rec)
    assert reg.get('p1') is not None

    import core.plugins.registry as rmod

    def locked(path, obj, chmod=None):
        raise PermissionError(
            '[WinError 5] Отказано в доступе: файл %r удерживается другой программой' % path)

    monkeypatch.setattr(rmod, 'atomic_write_json', locked)
    got = reg.update('p1', status=PluginStatus.RUNNING.value, enabled=True)
    assert got is not None and got.status == PluginStatus.RUNNING.value  # память живёт
    assert 'WinError 5' in reg.persist_error
    # на диске осталась прежняя версия (запись не удалась — но ничего не сломалось)
    with open(str(tmp_path / 'registry.json'), encoding='utf-8') as f:
        disk = json.load(f)
    assert disk['plugins'][0]['status'] != PluginStatus.RUNNING.value

    monkeypatch.undo()
    reg.update('p1', enabled=False)
    assert reg.persist_error == ''  # успешная запись сбрасывает деградацию


def test_manager_reports_data_warnings_and_health(tmp_path):
    """health()/data_warnings() честно показывают деградацию записи реестра."""
    from core.plugins.manager import PluginManager

    builtin = str(tmp_path / 'builtin')
    os.makedirs(os.path.join(builtin, 'repos'), exist_ok=True)
    src = os.path.join(BASE, 'plugins', 'repos')
    for fn in ('plugin.json', 'plugin.py', 'git_service.py', 'repos_service.py'):
        with open(os.path.join(src, fn), encoding='utf-8') as f, \
                open(os.path.join(builtin, 'repos', fn), 'w', encoding='utf-8') as w:
            w.write(f.read())
    mgr = PluginManager(base_dir=str(tmp_path / 'base'), data_dir=str(tmp_path / 'data'), builtin_dir=builtin)
    assert mgr.install('builtin:repos') is not None
    assert mgr.data_warnings() == {}  # без деградации — пусто

    mgr.registry.persist_error = '[WinError 5] Отказано в доступе: registry.json'
    w = mgr.data_warnings()
    assert 'WinError 5' in w.get('registry_persist_error', '')
    h = mgr.health('repos')
    assert 'WinError 5' in h.get('registry_persist_error', '')

    mgr.registry.persist_error = ''
    assert mgr.data_warnings() == {}
    assert 'registry_persist_error' not in mgr.health('repos')


def test_plugins_list_api_includes_data_warnings():
    """REST /api/plugins отдаёт data_warnings (контракт деградации для UI)."""
    src = open(os.path.join(BASE, 'core', 'plugins', 'routes.py'), encoding='utf-8').read()
    assert 'data_warnings=get_manager().data_warnings()' in src
    mgr_src = open(os.path.join(BASE, 'core', 'plugins', 'manager.py'), encoding='utf-8').read()
    assert 'def data_warnings' in mgr_src
    tab = open(os.path.join(BASE, 'src', 'components', 'tabs', 'PluginsTab.tsx'), encoding='utf-8').read()
    assert 'registry_persist_error' in tab, 'баннер деградации должен быть во вкладке Плагины'
    assert 'Деградация данных плагинов' in tab
