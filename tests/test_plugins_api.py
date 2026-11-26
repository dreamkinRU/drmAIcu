"""REST-контракт Plugin System (§10.2): структура ответов, ошибки, exec/confirmations."""
import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.plugins.manager import PluginManager
from core.plugins import routes

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PLUGIN = {
    'id': 'demo', 'name': 'Demo Plugin', 'version': '1.0.0', 'description': 't',
    'api_version': '1.0', 'entry_point': 'plugin.py',
    'permissions': ['demo.storage.read', 'demo.storage.write', 'demo.storage.merge'],
}
PLUGIN_SRC = '''
def initialize(ctx):
    ctx.register_capability('demo.read_store', 'demo.storage.read', lambda p: {'items': []}, 'auto')
    ctx.register_capability('demo.write_store', 'demo.storage.write', lambda p: {'count': 1}, 'confirm')
    return True
'''


@pytest.fixture()
def client(tmp_path):
    builtin = tmp_path / 'plugins_builtin' / 'demo'
    builtin.mkdir(parents=True)
    (builtin / 'plugin.json').write_text(json.dumps(PLUGIN), encoding='utf-8')
    (builtin / 'plugin.py').write_text(PLUGIN_SRC, encoding='utf-8')
    mgr = PluginManager(base_dir=str(tmp_path), builtin_dir=str(tmp_path / 'plugins_builtin'))
    routes.set_manager(mgr)
    app = FastAPI()
    app.include_router(routes.plugin_router)
    return TestClient(app)


def test_list_and_catalog(client):
    r = client.get('/api/plugins')
    assert r.status_code == 200 and r.json()['success'] is True
    assert r.json()['api_version'] == '1.0'
    r = client.get('/api/plugins/catalog')
    cat = r.json()['catalog']
    assert len(cat) == 1 and cat[0]['available'] and cat[0]['installed'] is False


def test_install_enable_exec_flow(client):
    r = client.post('/api/plugins/install', json={'source': 'builtin:demo'})
    assert r.json()['success'] is True
    assert r.json()['plugin']['status'] == 'installed'

    r = client.post('/api/plugins/install', json={'source': 'builtin:demo'})
    assert r.json()['success'] is False and r.json()['code'] == 'install_rejected'

    r = client.post('/api/plugins/install', json={})
    assert r.json()['success'] is False and r.json()['code'] == 'invalid_source'

    r = client.post('/api/plugins/demo/enable')
    assert r.json()['plugin']['status'] == 'running'

    r = client.post('/api/plugins/demo/exec', json={'capability': 'demo.read_store'})
    assert r.json()['success'] is True and r.json()['result'] == {'items': []}

    client.put('/api/plugins/demo/permissions',
               json={'grants': [{'permission': 'demo.storage.write', 'granted': True}]})
    r = client.post('/api/plugins/demo/exec', json={'capability': 'demo.write_store'})
    body = r.json()
    assert body['status'] == 'confirmation_required'
    cid = body['confirmation']['id']

    r = client.get('/api/plugins/confirmations')
    assert cid in [c['id'] for c in r.json()['confirmations']]

    r = client.post('/api/plugins/confirmations/%s/approve' % cid)
    assert r.json()['success'] is True and r.json()['result'] == {'count': 1}

    r = client.post('/api/plugins/confirmations/%s/approve' % cid)
    assert r.json()['success'] is False and r.json()['code'] == 'confirmation_invalid'


def test_exec_requires_running_plugin(client):
    client.post('/api/plugins/install', json={'source': 'builtin:demo'})
    r = client.post('/api/plugins/demo/exec', json={'capability': 'demo.read_store'})
    assert r.json()['success'] is False and r.json()['code'] == 'plugin_not_running'


def test_permissions_endpoints_and_undeclared_guard(client):
    client.post('/api/plugins/install', json={'source': 'builtin:demo'})
    client.post('/api/plugins/demo/enable')
    r = client.get('/api/plugins/demo/permissions')
    perms = {p['permission']: p['granted'] for p in r.json()['permissions']}
    assert perms['demo.storage.read'] is True and perms['demo.storage.merge'] is False
    r = client.put('/api/plugins/demo/permissions',
                   json={'grants': [{'permission': 'demo.storage.merge', 'granted': True}]})
    assert r.json()['success'] is True
    r = client.put('/api/plugins/demo/permissions',
                   json={'grants': [{'permission': 'hax.root', 'granted': True}]})
    assert r.json()['success'] is False and r.json()['code'] == 'invalid_grants'
    client.put('/api/plugins/demo/permissions',
               json={'grants': [{'permission': 'demo.storage.write', 'granted': True}]})
    r = client.post('/api/plugins/demo/exec', json={'capability': 'demo.write_store'})
    assert r.json()['status'] == 'confirmation_required'


def test_settings_endpoints(client):
    client.post('/api/plugins/install', json={'source': 'builtin:demo'})
    r = client.get('/api/plugins/demo/settings')
    assert r.json()['success'] is True
    r = client.put('/api/plugins/demo/settings', json={'settings': {'enabled': 'not-bool'}})
    assert r.json()['success'] is False and r.json()['code'] == 'invalid_settings'


def test_disable_uninstall_and_404(client):
    client.post('/api/plugins/install', json={'source': 'builtin:demo'})
    client.post('/api/plugins/demo/enable')
    r = client.post('/api/plugins/demo/disable')
    assert r.json()['plugin']['status'] == 'disabled'
    r = client.delete('/api/plugins/demo')
    assert r.json()['deleted'] == 'demo'
    r = client.get('/api/plugins/demo')
    assert r.status_code == 404
    r = client.get('/api/plugins/ghost/health')
    assert r.status_code == 404


# ---------- secrets API (Этап 4): write-only ----------

def _install_running(client):
    client.post('/api/plugins/install', json={'source': 'builtin:demo'})
    client.post('/api/plugins/demo/enable')


def test_secrets_put_get_names_and_file(tmp_path, client):
    _install_running(client)
    r = client.put('/api/plugins/demo/secrets', json={'secrets': {'api_key': 'vk-123', 'private_key': 'PEM'}})
    body = r.json()
    assert r.status_code == 200 and body['success'] is True
    assert body['secrets'] == ['api_key', 'private_key']  # только имена

    # значения никогда не возвращаются
    r = client.get('/api/plugins/demo/secrets')
    assert r.json()['success'] is True and r.json()['secrets'] == ['api_key', 'private_key']

    # файл со значением на месте
    secrets_file = None
    for root, _dirs, files in os.walk(tmp_path / 'data' / 'plugins' / 'secrets'):
        for f in files:
            if f == 'demo.secrets.json':
                secrets_file = os.path.join(root, f)
    assert secrets_file, 'secrets file must exist'
    with open(secrets_file, 'r', encoding='utf-8') as fh:
        stored = json.load(fh)
    assert stored['api_key'] == 'vk-123' and stored['private_key'] == 'PEM'

    # через настройки/реестр секреты не утекают
    r = client.get('/api/plugins/demo/settings')
    assert 'vk-123' not in r.text and 'PEM' not in r.text
    r = client.get('/api/plugins')
    assert 'vk-123' not in r.text


def test_secrets_validation_errors(client):
    _install_running(client)
    r = client.put('/api/plugins/demo/secrets', json={'secrets': {}})
    assert r.json()['success'] is False and r.json()['code'] == 'invalid_secrets'
    r = client.put('/api/plugins/demo/secrets', json={'key': 'ok_key', 'value': '   '})
    assert r.json()['code'] == 'invalid_secrets' and r.status_code == 422
    r = client.put('/api/plugins/demo/secrets', json={'key': 'bad key!.', 'value': 'x'})
    assert r.json()['code'] == 'invalid_secrets' and r.status_code == 422
    r = client.put('/api/plugins/demo/secrets', json={})
    assert r.json()['code'] == 'invalid_secrets'
    r = client.put('/api/plugins/nope/secrets', json={'secrets': {'k': 'v'}})
    assert r.json()['code'] == 'not_found' and r.status_code == 404


def test_secret_delete_and_journals(client):
    _install_running(client)
    client.put('/api/plugins/demo/secrets', json={'key': 'api_key', 'value': 'vk-123'})

    # в журнале только имя ключа, не значение
    r = client.get('/api/plugins/activity?plugin=demo')
    text = r.text
    assert 'vk-123' not in text and 'secret_set' in text

    r = client.delete('/api/plugins/demo/secrets/api_key')
    assert r.json()['success'] is True and r.json()['secrets'] == []
    r = client.delete('/api/plugins/demo/secrets/bad%20key!')
    assert r.status_code == 422 and r.json()['code'] == 'invalid_secrets'
    r = client.delete('/api/plugins/nope/secrets/api_key')
    assert r.json()['code'] == 'not_found'
