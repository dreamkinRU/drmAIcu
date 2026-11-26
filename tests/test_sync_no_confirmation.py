# -*- coding: utf-8 -*-
"""Sync без подтверждения WRITE (решение заказчика 26.11.2026).

repos.sync выполняется одной кнопкой (замена sync.bat). Исключение оформлено
явным allowlist AUTO_CONFIRMED_CAPABILITIES в core/plugins/api.py: только
('repos', 'repos.sync'), остальные WRITE-капабилити по-прежнему требуют
подтверждение; разрешение repos.sync должно быть выдано.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def test_sync_capability_is_auto_not_confirm():
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

    module = load_entry('repos', os.path.join(BASE, 'plugins', 'repos'), 'plugin.py')
    ctx = PluginAPI(M(), 'repos')
    assert module.initialize(ctx) is True
    caps = {c['name']: c for c in ctx.capabilities()}
    assert caps['repos.sync']['policy'] == 'auto'
    # остальные WRITE — по-прежнему confirm
    for name in ('repos.add', 'repos.commit', 'repos.push', 'repos.pull',
                 'repos.fetch', 'repos.checkout'):
        assert caps[name]['policy'] == 'confirm', name


def test_allowlist_does_not_weaken_other_write_capabilities():
    from core.plugins.api import PluginAPI

    api = PluginAPI(None, 'repos')
    import pytest
    with pytest.raises(ValueError, match='weaker than required'):
        api.register_capability('repos.add', 'repos.write', lambda p: None, 'auto')
    # чужой плагин не может объявить свой sync авто-подтверждаемым
    rec = type('Rec', (), {'permissions': ['demo.sync'], 'status': 'running'})
    api2 = PluginAPI(type('M', (), {'registry': type('R', (), {'get': lambda self, pid: rec})()})(), 'demo')
    with pytest.raises(ValueError, match='weaker than required'):
        api2.register_capability('demo.sync', 'demo.sync', lambda p: None, 'auto')
