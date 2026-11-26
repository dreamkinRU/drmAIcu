"""Confirmation Manager: одноразовые подтверждения WRITE/CRITICAL-операций."""
import hashlib
import json
import os
import secrets as _secrets
import threading
import time

TTL_SECONDS = 900


class ConfirmationError(Exception):
    pass


class ConfirmationManager:
    """Pending-подтверждения Capability Gateway.

    Одноразовый токен, привязан к (plugin, capability, params_hash, level, policy).
    TTL 15 минут; повторный approve/reject — ошибка (защита от переиспользования).
    """

    def __init__(self, path=None, ttl=TTL_SECONDS, now=None):
        self.path = path
        self.ttl = ttl
        self._now = now or time.time
        self._lock = threading.Lock()
        self._pending = {}
        self._snapshot()
        self._drop_expired()

    def _snapshot(self):
        if not self.path:
            return
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data.get('pending', []):
                cid = item.get('id')
                if cid:
                    self._pending[cid] = item
        except (OSError, ValueError):
            pass

    def _save(self):
        if not self.path:
            return
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'pending': list(self._pending.values())}, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def _drop_expired(self):
        cutoff = self._now() - self.ttl
        for cid in [c for c, p in self._pending.items() if p.get('created', 0) < cutoff]:
            self._pending.pop(cid, None)

    @staticmethod
    def params_hash(plugin_id, capability, params):
        raw = json.dumps({'p': plugin_id, 'c': capability, 'a': params}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def create(self, plugin_id, capability, params, permission, policy):
        with self._lock:
            self._drop_expired()
            cid = _secrets.token_urlsafe(24)
            item = {
                'id': cid,
                'plugin': plugin_id,
                'capability': capability,
                'params_hash': self.params_hash(plugin_id, capability, params),
                'params': params,
                'permission': permission,
                'policy': policy,
                'created': self._now(),
                'expires_in': self.ttl,
            }
            self._pending[cid] = item
            self._save()
            return dict(item)

    def peek(self, cid):
        """Item без изъятия (consume изымает); None если нет/истёк."""
        with self._lock:
            self._drop_expired()
            item = self._pending.get(cid)
            return dict(item) if item else None

    def pending(self, plugin_id=None):
        with self._lock:
            self._drop_expired()
            items = [dict(p) for p in self._pending.values() if plugin_id is None or p['plugin'] == plugin_id]
        items.sort(key=lambda p: p.get('created', 0))
        return items

    def consume(self, cid, params=None):
        """Валидация и изъятие подтверждения (single-use). Возвращает item."""
        with self._lock:
            item = self._pending.get(cid)
            if item is None:
                raise ConfirmationError('unknown or already used confirmation')
            if self._now() - item.get('created', 0) > self.ttl:
                self._pending.pop(cid, None)
                self._save()
                raise ConfirmationError('confirmation expired')
            if params is not None:
                given = self._hash_params_safe(item['plugin'], item['capability'], params)
                if given != item['params_hash']:
                    raise ConfirmationError('confirmation does not match provided params')
            self._pending.pop(cid, None)
            self._save()
            return item

    def _hash_params_safe(self, plugin_id, capability, params):
        return self.params_hash(plugin_id, capability, params)

    def reject(self, cid):
        with self._lock:
            if cid not in self._pending:
                raise ConfirmationError('unknown or already used confirmation')
            item = self._pending.pop(cid)
            self._save()
            return dict(item)
