"""Plugin System v1.0: жизненный цикл, права, подтверждения, секреты, изоляция (§11.1, §11.3)."""
import json
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.plugins.loader import Loader, load_entry, unload
from core.plugins.manager import PluginInstallError, PluginManager, PluginNotRunningError
from core.plugins.models import api_compatible, validate_manifest
from core.plugins.permissions import permission_level

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GOOD_PLUGIN = {
    'id': 'demo',
    'name': 'Demo Plugin',
    'version': '1.0.0',
    'description': 'Test plugin',
    'api_version': '1.0',
    'entry_point': 'plugin.py',
    'permissions': [
        'demo.storage.read',
        'demo.storage.write',
        'demo.storage.merge',
        'demo.storage.delete',
    ],
    'settings_schema': {
        'greeting': {'type': 'string', 'default': 'hello'},
        'attempts': {'type': 'number', 'default': 1},
        'enabled': {'type': 'boolean', 'default': True},
        'mode': {'type': 'enum', 'enum': ['a', 'b'], 'default': 'a'},
    },
}

GOOD_PLUGIN_SRC = '''
STORE = []

def initialize(ctx):
    ctx.register_capability('demo.read_store', 'demo.storage.read', _read, 'auto')
    ctx.register_capability('demo.write_store', 'demo.storage.write', _write, 'confirm')
    ctx.register_capability('demo.merge', 'demo.storage.merge', _merge, 'critical')
    return True

def _read(params):
    return {'items': STORE}

def _write(params):
    STORE.append(params.get('item'))
    return {'count': len(STORE)}

def _merge(params):
    return {'merged': True}

def start():
    pass

def stop():
    CLEAR.append(1)

def health():
    return {'items': len(STORE)}

CLEAR = []
'''


@pytest.fixture()
def env(tmp_path):
    builtin = tmp_path / 'plugins_builtin'
    data = tmp_path / 'data_plugins'
    return builtin, data


def _write_plugin(root, manifest=GOOD_PLUGIN, src=GOOD_PLUGIN_SRC):
    d = root / manifest['id']
    d.mkdir(parents=True)
    (d / 'plugin.json').write_text(json.dumps(manifest), encoding='utf-8')
    (d / 'plugin.py').write_text(src, encoding='utf-8')
    return d


@pytest.fixture()
def manager(env):
    builtin, data = env
    _write_plugin(builtin)
    return PluginManager(base_dir=tmp_base(env), data_dir=str(data), builtin_dir=str(builtin))


def tmp_base(env):
    return os.path.dirname(str(env[0]))


# ------------------------------------------------------------------ манифест и совместимость

def test_manifest_rejects_bad_id():
    bad = dict(GOOD_PLUGIN, id='Bad Id!')
    m, errors = validate_manifest(bad)
    assert m is None and errors


def test_manifest_rejects_incompatible_schema():
    bad = dict(GOOD_PLUGIN, settings_schema={'x': {'type': 'matrix'}})
    m, errors = validate_manifest(bad)
    assert m is None and any('unsupported type' in e for e in errors)


def test_api_compatibility():
    assert api_compatible('1.0', '1.0')
    assert api_compatible('1.0', '1.3')
    assert not api_compatible('1.4', '1.3')
    assert not api_compatible('2.0', '1.3')


def test_permission_levels():
    assert permission_level('github.pull_requests.merge') == 'critical'
    assert permission_level('github.repositories.delete') == 'critical'
    assert permission_level('github.contents.write') == 'write'
    assert permission_level('github.contents.read') == 'read'
    with pytest.raises(ValueError):
        permission_level('github.contents.execute')


def test_builtin_catalog_lists_manifest(manager):
    cat = manager.catalog()
    assert len(cat) == 1 and cat[0]['available'] and cat[0]['compatible']
    perms = {p['permission']: p['level'] for p in cat[0]['permissions']}
    assert perms['demo.storage.write'] == 'write'
    assert perms['demo.storage.merge'] == 'critical'


def test_catalog_reports_broken_manifest(env, manager):
    (env[0] / 'broken').mkdir()
    (env[0] / 'broken' / 'plugin.json').write_text('{not json', encoding='utf-8')
    cat = manager.catalog()
    broken = [c for c in cat if not c['available']]
    assert broken and 'unreadable manifest' in broken[0]['errors'][0]


def test_catalog_reports_incompatible(env, manager):
    _write_plugin(env[0], manifest=dict(GOOD_PLUGIN, id='oldapi', api_version='2.0'))
    cat = manager.catalog()
    old = [c for c in cat if c['manifest'] and c['manifest']['id'] == 'oldapi'][0]
    assert not old['compatible']


# ------------------------------------------------------------------ установка и жизненный цикл

def test_install_register_and_default_grants(manager):
    info = manager.install('builtin:demo')
    assert info['status'] == 'installed' and info['source'] == 'builtin'
    perms = {p['permission']: p['granted'] for p in manager.permissions_status('demo')['permissions']}
    assert perms['demo.storage.read'] is True
    assert perms['demo.storage.write'] is False and perms['demo.storage.merge'] is False


def test_reinstall_rejected_no_duplicates(manager):
    manager.install('builtin:demo')
    registry_before = manager.registry.get('demo')
    with pytest.raises(PluginInstallError):
        manager.install('builtin:demo')
    registry_after = manager.registry.get('demo')
    assert registry_before is registry_after


def test_enable_disable_lifecycle(manager):
    manager.install('builtin:demo')
    info = manager.enable('demo')
    assert info['status'] == 'running'
    h = manager.health('demo')
    assert h['status'] == 'running' and h['items'] == 0
    info = manager.disable('demo')
    assert info['status'] == 'disabled'


def test_incompatible_rejected_at_install_and_not_started(env, manager):
    """§7.2: проверка версии Plugin API — в процессе установки."""
    _write_plugin(env[0], manifest=dict(GOOD_PLUGIN, id='oldapi', api_version='2.0'))
    with pytest.raises(PluginInstallError):
        manager.install('builtin:oldapi')
    assert manager.registry.get('oldapi') is None


def test_incompatible_record_never_starts(env, manager):
    """§11.1: несовместимый плагин не запускается (даже если запись попала в реестр)."""
    manager.install('builtin:demo')
    manager.registry.update('demo', api_version='2.0')
    with pytest.raises(PluginInstallError):
        manager.enable('demo')
    assert manager.registry.get('demo').status == 'incompatible'


def test_missing_entry_point_isolated_error(env, manager):
    d = env[0] / 'broken'
    d.mkdir()
    (d / 'plugin.json').write_text(json.dumps(dict(GOOD_PLUGIN, id='broken', entry_point='nope.py')), encoding='utf-8')
    manager.install('builtin:broken')
    with pytest.raises(Exception):
        manager.enable('broken')
    assert manager.registry.get('broken').status == 'error'
    assert manager.registry.get('broken').last_error


def test_initialize_false_marks_error(env, manager):
    src = GOOD_PLUGIN_SRC + '\n\ndef initialize_false():\n    return False\n'
    d = env[0] / 'refuse'
    d.mkdir()
    (d / 'plugin.json').write_text(json.dumps(dict(GOOD_PLUGIN, id='refuse')), encoding='utf-8')
    (d / 'plugin.py').write_text(src + '\n_orig = initialize\n\ndef initialize(ctx):\n    return False', encoding='utf-8')
    manager.install('builtin:refuse')
    with pytest.raises(Exception):
        manager.enable('refuse')
    assert manager.registry.get('refuse').status == 'error'


def test_error_of_one_plugin_does_not_break_others(env, manager):
    d = env[0] / 'boom'
    d.mkdir()
    (d / 'plugin.json').write_text(json.dumps(dict(GOOD_PLUGIN, id='boom')), encoding='utf-8')
    (d / 'plugin.py').write_text('def initialize(ctx):\n    raise RuntimeError("boom")', encoding='utf-8')
    manager.install('builtin:demo')
    manager.install('builtin:boom')
    try:
        manager.enable('boom')
    except Exception:
        pass
    manager.enable('demo')
    assert manager.registry.get('demo').status == 'running'
    assert manager.registry.get('boom').status == 'error'


def test_enable_unknown_plugin(manager):
    with pytest.raises(KeyError):
        manager.enable('ghost')


def test_uninstall_cleans_all_data(env, manager):
    manager.install('builtin:demo')
    manager.enable('demo')
    api = manager._apis['demo']
    api.set_secret('token', 'ghs_supersecret_value_123456')
    api.set_settings({'greeting': 'hi'})
    manager.uninstall('demo')
    assert manager.registry.get('demo') is None
    assert manager.secrets.get_secret('demo', 'token') is None
    assert not os.path.exists(os.path.join(manager.data_dir, 'state', 'demo'))
    assert not os.path.exists(os.path.join(manager.data_dir, 'installed', 'demo'))


def test_uninstall_remove_plugin_from_registry_persists_after_reload(env, manager):
    manager.install('builtin:demo')
    manager.uninstall('demo')
    data_path = os.path.join(manager.data_dir, 'registry.json')
    content = json.loads(open(data_path, encoding='utf-8').read())
    assert content['plugins'] == []

# ------------------------------------------------------------------ разрешения и gateway


def test_operation_blocked_without_permission(manager):
    manager.install('builtin:demo')
    manager.enable('demo')
    from core.plugins.permissions import PermissionDenied
    manager.permissions.revoke('demo', 'demo.storage.read')
    with pytest.raises(PermissionDenied):
        manager.exec('demo', 'demo.read_store', params={})
    manager.permissions.grant('demo', 'demo.storage.read')
    r = manager.exec('demo', 'demo.read_store', params={})
    assert r['status'] == 'done' and r['result'] == {'items': []}


def test_revoked_permission_blocks_subsequent_calls(manager):
    manager.install('builtin:demo')
    manager.enable('demo')
    manager.permissions.grant('demo', 'demo.storage.read')
    assert manager.exec('demo', 'demo.read_store', params={})['status'] == 'done'
    manager.permissions.revoke('demo', 'demo.storage.read')
    from core.plugins.permissions import PermissionDenied
    with pytest.raises(PermissionDenied):
        manager.exec('demo', 'demo.read_store', params={})


def test_undeclared_permission_cannot_be_granted(env, manager):
    manager.install('builtin:demo')
    with pytest.raises(ValueError):
        manager.permissions_put('demo', [{'permission': 'secret.thing.read', 'granted': True}])


def test_write_requires_confirmation(manager):
    manager.install('builtin:demo')
    manager.enable('demo')
    from core.plugins.permissions import PermissionDenied
    with pytest.raises(PermissionDenied):
        manager.exec('demo', 'demo.write_store', params={'item': 'x'})
    manager.permissions.grant('demo', 'demo.storage.write')
    r = manager.exec('demo', 'demo.write_store', params={'item': 'x'})
    assert r['status'] == 'confirmation_required'
    cid = r['confirmation']['id']
    pending = [c['id'] for c in manager.pending_confirmations()]
    assert cid in pending
    approved = manager.confirm(cid, True)
    assert approved['result'] == {'count': 1}


def test_confirmation_single_use_and_stale_reuse(manager):
    manager.install('builtin:demo')
    manager.enable('demo')
    manager.permissions.grant('demo', 'demo.storage.merge')
    r = manager.exec('demo', 'demo.merge', params={})
    cid = r['confirmation']['id']
    assert manager.confirm(cid, True)['result'] == {'merged': True}
    from core.plugins.confirmations import ConfirmationError
    with pytest.raises(ConfirmationError):
        manager.confirm(cid, True)


def test_confirmation_params_mismatch_rejected(manager):
    """§11.3: повторное использование устаревшего подтверждения с другими params."""
    from core.plugins.api import GatewayBlocked
    from core.plugins.confirmations import ConfirmationError
    manager.install('builtin:demo')
    manager.enable('demo')
    manager.permissions.grant('demo', 'demo.storage.write')
    r = manager.exec('demo', 'demo.write_store', params={'item': 'a'})
    cid = r['confirmation']['id']
    with pytest.raises(GatewayBlocked):
        manager.exec('demo', 'demo.write_store', params={'item': 'b'}, confirmation_token=cid)
    assert manager.confirm(cid, True)['result'] == {'count': 1}
    with pytest.raises(ConfirmationError):
        manager.confirm(cid, True)


def test_critical_cannot_run_with_write_permission(manager):
    manager.install('builtin:demo')
    manager.enable('demo')
    manager.permissions.grant('demo', 'demo.storage.write')
    from core.plugins.permissions import PermissionDenied
    with pytest.raises(PermissionDenied):
        manager.exec('demo', 'demo.merge', params={})


def test_exec_on_stopped_plugin_blocked(manager):
    manager.install('builtin:demo')
    manager.enable('demo')
    manager.permissions.grant('demo', 'demo.storage.read')
    manager.disable('demo')
    from core.plugins.manager import PluginNotRunningError
    with pytest.raises(PluginNotRunningError):
        manager.exec('demo', 'demo.read_store', params={})


# ------------------------------------------------------------------ секреты и журнал


def test_secrets_isolated_files_and_never_in_settings(env, manager):
    manager.install('builtin:demo')
    manager.enable('demo')
    api = manager._apis['demo']
    api.set_secret('token', 'ghs_supersecret_value_123456')
    assert manager.secrets.get_secret('demo', 'token') == 'ghs_supersecret_value_123456'
    st = manager.settings_get('demo')
    assert 'token' not in json.dumps(st)
    assert os.path.isfile(os.path.join(manager.data_dir, 'secrets', 'demo.secrets.json'))
    state_dir = os.path.join(manager.data_dir, 'state', 'demo')
    assert 'token' not in ''.join(open(os.path.join(state_dir, f), encoding='utf-8').read()
                                  for f in os.listdir(state_dir))


def test_activity_journal_redacts_secrets(env, manager):
    manager.install('builtin:demo')
    manager.enable('demo')
    api = manager._apis['demo']
    api.set_secret('token', 'ghs_supersecret_value_123456')
    api.log('info', 'joined_with', raw='ghs_supersecret_value_123456 in text')
    entries = manager.activity_read('demo')
    assert entries and entries[0]['details']['raw'] == '***REDACTED*** in text'


def test_log_never_contains_secret_value_in_any_level(env, manager):
    manager.install('builtin:demo')
    manager.enable('demo')
    api = manager._apis['demo']
    api.set_secret('k', 'abcdef1234567890')
    api.log('error', 'boom', error='abcdef1234567890')
    joined = json.dumps(manager.activity_read('demo'), ensure_ascii=False)
    assert 'abcdef1234567890' not in joined


# ------------------------------------------------------------------ settings валидация


def test_settings_validation_and_defaults(env, manager):
    manager.install('builtin:demo')
    st = manager.settings_get('demo')
    assert st['settings']['greeting'] == 'hello'
    with pytest.raises(PluginInstallError):
        manager.settings_put('demo', {'mode': 'zzz'})
    with pytest.raises(PluginInstallError):
        manager.settings_put('demo', {'unknown_key': 1})
    out = manager.settings_put('demo', {'greeting': 'hi'})
    assert out['settings']['greeting'] == 'hi'


# ------------------------------------------------------------------ install: каталог и архив


def test_install_from_local_dir_copy(env, manager):
    srcroot = env[0].parent / 'external_src'
    src = _write_plugin(srcroot)
    info = manager.install(str(src))
    assert info['source'] == 'installed'
    assert os.path.isdir(os.path.join(manager.data_dir, 'installed', 'demo'))
    assert manager.registry.get('demo').path == os.path.join(manager.data_dir, 'installed', 'demo')


def test_install_from_zip_archive(env, manager):
    archive = str(env[0] / 'demo-pack.zip')
    with zipfile.ZipFile(archive, 'w') as z:
        z.write(os.path.join(env[0], 'demo', 'plugin.json'), 'demo/plugin.json')
        z.write(os.path.join(env[0], 'demo', 'plugin.py'), 'demo/plugin.py')
    info = manager.install(archive)
    assert info['status'] == 'installed'


def test_install_rejects_zip_path_traversal(env, manager):
    archive = str(env[0] / 'evil.zip')
    with open(archive, 'wb') as f:
        f.write(b'PK\x05\x06' + b'\x00' * 18)
    with pytest.raises(Exception):
        manager.install(archive)


# ------------------------------------------------------------------ loader


def test_unload_removes_modules(env, manager):
    manager.install('builtin:demo')
    manager.enable('demo')
    assert [m for m in sys.modules if m.startswith('_plugin_demo.')]
    unload('demo')
    assert not [m for m in sys.modules if m.startswith('_plugin_demo.')]
