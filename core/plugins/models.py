"""Модели Plugin System (stdlib-only, без UI-зависимостей)."""
import re
from dataclasses import dataclass, field
from enum import Enum

PLUGIN_API_VERSION = '1.0'

RP_ID = re.compile(r'^[a-z][a-z0-9_-]*$')
RP_VERSION = re.compile(r'^\d+\.\d+\.\d+$')
RP_API_VERSION = re.compile(r'^(\d+)\.(\d+)$')

REQUIRED_FIELDS = ('id', 'name', 'version', 'description', 'api_version', 'entry_point', 'permissions')


class PluginStatus(str, Enum):
    INSTALLED = 'installed'
    DISABLED = 'disabled'
    LOADING = 'loading'
    RUNNING = 'running'
    ERROR = 'error'
    UPDATE_AVAILABLE = 'update_available'
    INCOMPATIBLE = 'incompatible'


class PluginState(str, Enum):
    DISCOVER = 'discover'
    VALIDATE = 'validate'
    REGISTER = 'register'
    AUTHORIZE = 'authorize'
    LOAD = 'load'
    INITIALIZE = 'initialize'
    RUNNING = 'running'
    STOP = 'stop'
    DISABLE = 'disable'
    ERROR = 'error'
    UNINSTALL = 'uninstall'


class PermissionLevel(str, Enum):
    READ = 'read'
    WRITE = 'write'
    CRITICAL = 'critical'


class ConfirmationPolicy(str, Enum):
    AUTO = 'auto'
    CONFIRM = 'confirm'
    CRITICAL = 'critical'


@dataclass
class PermissionEntry:
    permission: str
    level: str
    granted: bool


@dataclass
class PluginRecord:
    id: str
    name: str
    version: str
    description: str = ''
    author: str = ''
    api_version: str = PLUGIN_API_VERSION
    entry_point: str = 'plugin.py'
    permissions: list = field(default_factory=list)
    settings_schema: dict = field(default_factory=dict)
    status: str = PluginStatus.INSTALLED.value
    source: str = 'builtin'
    path: str = ''
    enabled: bool = False
    installed_at: str = ''
    last_error: str = ''

    @classmethod
    def from_manifest(cls, m):
        return cls(
            id=m['id'], name=m['name'], version=m['version'], description=m.get('description', ''),
            author=m.get('author', ''), api_version=m.get('api_version', PLUGIN_API_VERSION),
            entry_point=m.get('entry_point', 'plugin.py'),
            permissions=list(m.get('permissions', [])),
            settings_schema=dict(m.get('settings_schema', {})),
        )

    def public(self, details=False):
        d = {
            'id': self.id, 'name': self.name, 'version': self.version,
            'description': self.description, 'author': self.author,
            'api_version': self.api_version, 'status': self.status,
            'source': self.source, 'enabled': self.enabled,
            'last_error': self.last_error,
        }
        if details:
            d.update({
                'entry_point': self.entry_point,
                'permissions': list(self.permissions),
                'settings_schema': dict(self.settings_schema),
                'installed_at': self.installed_at,
            })
        return d


def validate_manifest(data):
    """-> (manifest|None, errors:list[str])"""
    errors = []
    if not isinstance(data, dict):
        return None, ['manifest must be a JSON object']
    for f in REQUIRED_FIELDS:
        if f not in data:
            errors.append('missing field: %s' % f)
    if errors:
        return None, errors
    if not RP_ID.match(str(data['id'] or '')):
        errors.append('invalid plugin id: %r' % data['id'])
    if not RP_VERSION.match(str(data['version'] or '')):
        errors.append('invalid version (expected X.Y.Z): %r' % data['version'])
    m = RP_API_VERSION.match(str(data['api_version'] or ''))
    if not m:
        errors.append('invalid api_version (expected X.Y): %r' % data['api_version'])
    ep = str(data['entry_point'])
    if not ep.endswith('.py') or '/' in ep or '\\' in ep or ep.startswith('.'):
        errors.append('invalid entry_point: %r' % ep)
    perms = data['permissions']
    if not isinstance(perms, list) or any(not isinstance(p, str) or not p.strip() for p in perms):
        errors.append('permissions must be a list of non-empty strings')
    if len(set(perms)) != len(perms):
        errors.append('duplicate permissions in manifest')
    schema = data.get('settings_schema', {})
    if not isinstance(schema, dict):
        errors.append('settings_schema must be an object')
    else:
        for k, v in schema.items():
            if not isinstance(v, dict) or 'type' not in v:
                errors.append('settings_schema.%s: object with "type" required' % k)
                continue
            if v['type'] not in ('string', 'number', 'boolean', 'enum'):
                errors.append('settings_schema.%s: unsupported type %r' % (k, v['type']))
            if v['type'] == 'enum' and not isinstance(v.get('enum'), list):
                errors.append('settings_schema.%s: enum list required' % k)
    return (None if errors else data), errors


def api_compatible(required, current=PLUGIN_API_VERSION):
    """True — major совпадает, minor требуемой <= minor ядра."""
    a, b = RP_API_VERSION.match(required or ''), RP_API_VERSION.match(current)
    if not a or not b:
        return False
    if a.group(1) != b.group(1):
        return False
    return int(a.group(2)) <= int(b.group(2))
