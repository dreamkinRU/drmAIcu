"""Permission Manager: уровни READ/WRITE/CRITICAL, выдача/отзыв (stdlib-only)."""
import json
import os
import threading

from .models import PermissionLevel

CRITICAL_PERMISSIONS = {
    'github.pull_requests.merge',
    'github.repositories.delete',
}


def permission_level(permission):
    p = str(permission or '').split('.')
    action = p[-1].lower() if p else ''
    full = str(permission or '').lower()
    if full in CRITICAL_PERMISSIONS or action in ('merge', 'delete'):
        return PermissionLevel.CRITICAL.value
    if action == 'write':
        return PermissionLevel.WRITE.value
    if action == 'read':
        return PermissionLevel.READ.value
    raise ValueError('unknown permission: %r' % permission)


class PermissionDenied(Exception):
    def __init__(self, permission, reason='permission not granted'):
        super().__init__(reason)
        self.permission = permission
        self.reason = reason


class PermissionManager:
    """Разрешения плагинов в data/plugins/permissions.json (раздельно от настроек)."""

    def __init__(self, path, debug=False):
        self.path = path
        self.debug = debug
        self._lock = threading.Lock()
        self._grants = {}
        self._load()

    def _load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._grants = {k: set(v) for k, v in data.items() if isinstance(v, list)}
        except (OSError, ValueError):
            self._grants = {}

    def _save(self):
        with self._lock:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump({k: sorted(v) for k, v in self._grants.items()}, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)

    def declared_ok(self, manifest_permissions):
        """Раскладка заявленных разрешений по уровням."""
        out = []
        for p in manifest_permissions or []:
            out.append({'permission': p, 'level': permission_level(p)})
        return out

    def levels_of(self, manifest_permissions):
        """Раскладка заявленных разрешений по уровням."""
        out = {}
        for p in manifest_permissions or []:
            out[p] = permission_level(p)
        return out

    def grant(self, plugin_id, permission):
        permission_level(permission)
        with self._lock:
            self._grants.setdefault(plugin_id, set()).add(permission)
        self._save()

    def revoke(self, plugin_id, permission):
        with self._lock:
            g = self._grants.get(plugin_id, set())
            g.discard(permission)
        self._save()

    def is_granted(self, plugin_id, permission):
        return permission in self._grants.get(plugin_id, set())

    def granted_for(self, plugin_id):
        return sorted(self._grants.get(plugin_id, set()))

    def status_for(self, plugin_id, manifest_permissions):
        """[{permission, level, granted}] — для UI и PUT-валидации."""
        out = []
        for p in manifest_permissions or []:
            out.append({
                'permission': p,
                'level': permission_level(p),
                'granted': self.is_granted(plugin_id, p),
            })
        return out

    def grant_all_of_level(self, plugin_id, manifest_permissions, level):
        for p in manifest_permissions or []:
            if permission_level(p) == level:
                self.grant(plugin_id, p)

    def remove_plugin(self, plugin_id):
        with self._lock:
            self._grants.pop(plugin_id, None)
        self._save()
