"""GitHub Plugin: манифест, JWT, git-allowlist, валидация параметров (без сети)."""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.join(BASE, 'plugins', 'github')


def test_manifest_valid_and_complete():
    from core.plugins.models import validate_manifest
    with open(os.path.join(PLUGIN_DIR, 'plugin.json'), encoding='utf-8') as f:
        data = json.load(f)
    from core.plugins.permissions import permission_level
    manifest, errors = validate_manifest(data)
    assert manifest is not None, errors
    wants = {c.name for c in permission_level.__wrapped__()} if hasattr(permission_level, '__wrapped__') else None
    assert data['id'] == 'github' and data['api_version'] == '1.0'


def test_entry_point_imports():
    from core.plugins.loader import load_entry
    module = load_entry('github', PLUGIN_DIR, 'plugin.py')
    assert hasattr(module, 'initialize') and hasattr(module, 'health')


def test_entry_module_registers_on_initialize():
    from core.plugins.loader import load_entry
    from core.plugins.api import PluginAPI

    class FakeManager:
        def __init__(self):
            from core.plugins.events import ActivityJournal, EventBus
            from core.plugins.secrets import SecretManager
            import tempfile
            tmp = tempfile.mkdtemp()
            self.secrets = SecretManager(os.path.join(tmp, 'secrets'))
            self.activity = ActivityJournal(os.path.join(tmp, 'activity'))
            self.events = EventBus()
            self.registry = type('R', (), {'get': lambda self, pid: None})()
            self.settings = type('S', (), {'merged': lambda self, pid, schema: {}})()

    module = load_entry('github', PLUGIN_DIR, 'plugin.py')
    mgr = FakeManager()
    ctx = PluginAPI(mgr, 'github')
    assert module.initialize(ctx) is True
    caps = {c['name']: c for c in ctx.capabilities()}
    assert caps['github.test_connection']['permission'] == 'github.repositories.read'
    assert caps['github.test_connection']['policy'] == 'auto'
    assert caps['github.create_branch']['policy'] == 'confirm'
    assert caps['github.list_repositories']['policy'] == 'auto'


def test_app_jwt_signs_with_rs256():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    import jwt as pyjwt
    import time

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM,
                            serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()

    class FakeCtx:
        _settings = {'app_id': '123', 'installation_id': '456'}
        _secrets = {'private_key': pem}

        def settings(self):
            return dict(self._settings)

        def get_secret(self, k):
            return self._secrets.get(k)

    from plugins.github.client import GitHubAppClient
    client = GitHubAppClient(FakeCtx())
    token = client._app_jwt()
    decoded = pyjwt.decode(token, options={'verify_signature': False})
    now = time.time()
    assert decoded['iss'] == '123'
    assert decoded['exp'] - decoded['iat'] == 600
    assert abs(decoded['exp'] - (now + 540)) < 5


def test_missing_config_clear_diagnostic():
    class FakeCtx:
        def settings(self):
            return {}

        def get_secret(self, k):
            return None

    from plugins.github.client import GitHubAppClient, GitHubAuthError
    client = GitHubAppClient(FakeCtx())
    result = client.test_connection()
    assert result['ok'] is False and result['configured'] is False
    with pytest.raises(GitHubAuthError):
        client.token()


def test_client_param_validation():
    class FakeCtx:
        def settings(self):
            return {}

        def get_secret(self, k):
            return None

    from plugins.github.client import GitHubAppClient
    client = GitHubAppClient(FakeCtx())
    with pytest.raises(ValueError):
        client._repo_full({'repository': '../etc'})
    with pytest.raises(ValueError):
        client._repo_full({'repository': 'justname'})
    with pytest.raises(ValueError):
        client.get_tree({'repository': 'o/r', 'ref': '..'})
    with pytest.raises(ValueError):
        client.get_file({'repository': 'o/r', 'path': '../secret'})


def test_git_allowlist():
    from plugins.github import git_service
    with pytest.raises(git_service.GitCommandRejected):
        git_service.run_git(['rm', '-rf', '/'])
    with pytest.raises(git_service.GitCommandRejected):
        git_service.run_git(['status; cat /etc/passwd'])
    with pytest.raises(git_service.GitCommandRejected):
        git_service.run_git(['--upload-pack=evil', 'fetch'])
    assert git_service.run_git(['status', '--porcelain'], cwd=BASE)['code'] in (0, 128)
    assert git_service.is_git_available()


def test_git_helpers():
    from plugins.github import git_service
    assert git_service.validate_repo_path(BASE) is None
    with pytest.raises(git_service.GitCommandRejected):
        git_service.validate_repo_path('/tmp')


# ---------- degraded mode (Этап 4 fix): клиент недоступен — плагин стартует честно ----------

def _make_ctx():
    from core.plugins.loader import load_entry
    from core.plugins.api import PluginAPI

    class FakeManager:
        def __init__(self):
            from core.plugins.events import ActivityJournal, EventBus
            from core.plugins.secrets import SecretManager
            import tempfile
            tmp = tempfile.mkdtemp()
            self.secrets = SecretManager(os.path.join(tmp, 'secrets'))
            self.activity = ActivityJournal(os.path.join(tmp, 'activity'))
            self.events = EventBus()
            self.registry = type('R', (), {'get': lambda self, pid: None})()
            self.settings = type('S', (), {'merged': lambda self, pid, schema: {}})()

    module = load_entry('github', PLUGIN_DIR, 'plugin.py')
    return module, PluginAPI(FakeManager(), 'github')


def test_degraded_mode_starts_when_client_import_fails(monkeypatch):
    """Отсутствует pyjwt/requests -> плагин стартует (True), но только с локальными capability."""
    import plugins.github.plugin as gh_plugin

    # имитируем недоступный модуль зависимости через сброс кэша импорта плагина
    for mod in [m for m in list(sys.modules) if m.startswith('_plugin_github')]:
        del sys.modules[mod]
    saved = {m: sys.modules.get(m) for m in ('jwt', 'requests')}
    for m in saved:
        sys.modules[m] = None  # import поднимет ImportError, как в среде без зависимости
    try:
        # перезагружаем entry, чтобы `from .client import ...` выполнился при подменённых модулях
        from core.plugins.loader import load_entry
        from core.plugins.api import PluginAPI

        class FakeManager:
            def __init__(self):
                from core.plugins.events import ActivityJournal, EventBus
                from core.plugins.secrets import SecretManager
                import tempfile
                tmp = tempfile.mkdtemp()
                self.secrets = SecretManager(os.path.join(tmp, 'secrets'))
                self.activity = ActivityJournal(os.path.join(tmp, 'activity'))
                self.events = EventBus()
                self.registry = type('R', (), {'get': lambda self, pid: None})()
                self.settings = type('S', (), {'merged': lambda self, pid, schema: {}})()

        monkeypatch.setattr(gh_plugin, '_STATE', {'ctx': None, 'client': None, 'client_error': ''}, raising=False)
        module = load_entry('github', PLUGIN_DIR, 'plugin.py')
        ctx = PluginAPI(FakeManager(), 'github')
        assert module.initialize(ctx) is True
        caps = {c['name'] for c in ctx.capabilities()}
        assert 'github.diagnostics' in caps and 'github.test_connection' in caps
        # WRITE/READ сетевые операции не зарегистрированы — неизвестная capability, а не fake
        assert 'github.list_repositories' not in caps
        assert 'github.create_branch' not in caps

        res = module.health()
        assert res['auth_configured'] is False and 'client_error' in res and 'hint' in res
    finally:
        for m, v in saved.items():
            if v is None:
                sys.modules.pop(m, None)
            else:
                sys.modules[m] = v
        # очищаем испорченные сессией entry-модули; следующий тест перезагрузит entry заново
        for mod in [m for m in list(sys.modules) if m.startswith('_plugin_github')]:
            del sys.modules[mod]


def test_degraded_test_connection_reports_reason():
    module, ctx = _make_ctx()
    assert module.initialize(ctx) is True
    module._STATE['client'] = None
    module._STATE['client_error'] = 'No module named jwt'
    res = module.health()
    assert res['auth_configured'] is False and 'jwt' in res['client_error']
