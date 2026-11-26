"""Plugin API: контекст плагина (`ctx`) и Capability Gateway.

Power-of-core принцип: плагин получает контролируемые возможности, а не доступ
ко внутренним объектам drmAIcu. Группы: log, settings, secrets (без выдачи значений
в логи), events, register_capability + выполнение через gateway при совпадении
политики (§6 контракта).
"""
import threading
import traceback

from .confirmations import ConfirmationError
from .models import ConfirmationPolicy
from .permissions import PermissionDenied, permission_level


class GatewayBlocked(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class PendingConfirmation(Exception):
    """Операция требует подтверждения пользователя (не является ошибкой ядра)."""

    def __init__(self, confirmation):
        self.confirmation = confirmation
        super().__init__('confirmation required')


class Capability:
    def __init__(self, name, permission, handler, policy, description=''):
        self.name = name
        self.permission = permission
        self.handler = handler
        self.policy = policy
        self.description = description


class PluginAPI:
    def __init__(self, manager, plugin_id):
        self._manager = manager
        self._plugin_id = plugin_id
        self._caps = {}
        self._caps_lock = threading.Lock()

    # --- журнал ---

    def log(self, kind, event, **details):
        safe_details = {
            k: (self._manager.secrets.redact(self._plugin_id, v) if isinstance(v, str) else v)
            for k, v in details.items()
        }
        self._manager.activity.add(self._plugin_id, kind, event, **safe_details)

    # --- настройки ---

    def settings(self):
        rec = self._manager.registry.get(self._plugin_id)
        schema = rec.settings_schema if rec else {}
        return self._manager.settings.merged(self._plugin_id, schema)

    def set_settings(self, updates):
        rec = self._manager.registry.get(self._plugin_id)
        schema = rec.settings_schema if rec else {}
        self._manager.settings.set_many(self._plugin_id, schema, updates)

    # --- секреты (никогда не логируются) ---

    def get_secret(self, key):
        return self._manager.secrets.get_secret(self._plugin_id, key)

    def set_secret(self, key, value):
        self._manager.secrets.set_secret(self._plugin_id, key, value)

    def remove_secret(self, key):
        self._manager.secrets.remove_secret(self._plugin_id, key)

    def delete_secrets(self):
        self._manager.secrets.delete_all(self._plugin_id)

    # --- события ---

    def publish(self, event, **payload):
        self._manager.events.publish(event, {'plugin': self._plugin_id, **payload})

    def subscribe(self, fn):
        self._manager.events.subscribe(fn)

    # --- capabilities ---

    def register_capability(self, name, permission, handler, confirmation='auto', description=''):
        ConfirmationPolicy(confirmation)
        try:
            permission_level(permission)
        except ValueError as e:
            raise ValueError('capability uses an unknown permission: %s' % permission) from e
        rec = self._manager.registry.get(self._plugin_id)
        if rec is None or permission not in rec.permissions:
            raise ValueError('capability permission is not declared in plugin manifest: %s' % permission)
        with self._caps_lock:
            if name in self._caps:
                raise ValueError('capability already registered: %s' % name)
            self._caps[name] = Capability(name, permission, handler, confirmation, description or '')

    def _effective_policy(self, cap):
        """Плагин может ужесточить, но не ослабить политику ядра."""
        try:
            level = permission_level(cap.permission)
        except ValueError as e:
            raise GatewayBlocked('invalid_permission', str(e)) from e
        minimum = {
            'read': ConfirmationPolicy.AUTO.value,
            'write': ConfirmationPolicy.CONFIRM.value,
            'critical': ConfirmationPolicy.CRITICAL.value,
        }[level]
        rank = {
            ConfirmationPolicy.AUTO.value: 0,
            ConfirmationPolicy.CONFIRM.value: 1,
            ConfirmationPolicy.CRITICAL.value: 2,
        }
        return max((cap.policy, minimum), key=lambda value: rank[value])

    def capabilities(self):
        with self._caps_lock:
            caps = list(self._caps.values())
        return [dict(name=c.name, permission=c.permission, policy=self._effective_policy(c),
                     description=c.description) for c in caps]

    def _get_cap(self, name):
        with self._caps_lock:
            return self._caps.get(name)

    def call(self, name, params=None, confirmation_token=None):
        """Выполнение capability: разрешение → политика → вызов/подтверждение."""
        cap = self._get_cap(name)
        if cap is None:
            raise GatewayBlocked('unknown_capability', 'unknown capability: %s' % name)
        rec = self._manager.registry.get(self._plugin_id)
        if rec is None or rec.status != 'running':
            raise GatewayBlocked('plugin_not_running', 'plugin %s is not running' % self._plugin_id)
        policy = self._effective_policy(cap)
        if not self._manager.permissions.is_granted(self._plugin_id, cap.permission):
            raise PermissionDenied(cap.permission)
        params = params or {}
        if not isinstance(params, dict):
            raise GatewayBlocked('invalid_params', 'params must be an object')

        if policy in (ConfirmationPolicy.CONFIRM.value, ConfirmationPolicy.CRITICAL.value):
            if confirmation_token:
                try:
                    self._manager.confirmations.consume(
                        confirmation_token, params=params, plugin_id=self._plugin_id,
                        capability=name, permission=cap.permission, policy=policy)
                except ConfirmationError as e:
                    raise GatewayBlocked('confirmation_invalid', str(e))
                return self._invoke(cap, params)
            conf = self._manager.confirmations.create(
                self._plugin_id, name, params, cap.permission, policy)
            self.log('warn', 'confirmation_required', capability=name, policy=policy)
            raise PendingConfirmation(conf)

        if confirmation_token:
            raise GatewayBlocked('unexpected_confirmation', 'this capability does not require confirmation')

        return self._invoke(cap, params)

    def _invoke(self, cap, params):
        try:
            result = cap.handler(params or {})
        except Exception as e:
            self.log('error', 'capability_failed', capability=cap.name, error=str(e))
            raise
        self.log('info', 'capability_ok', capability=cap.name)
        return result
