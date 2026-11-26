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
from .permissions import PermissionDenied


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
        with self._caps_lock:
            self._caps[name] = Capability(name, permission, handler, confirmation, description or '')

    def capabilities(self):
        with self._caps_lock:
            return [dict(name=c.name, permission=c.permission, policy=c.policy,
                         description=c.description)
                    for c in self._caps.values()]

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
        if not self._manager.permissions.is_granted(self._plugin_id, cap.permission):
            raise PermissionDenied(cap.permission)
        params = params or {}
        if not isinstance(params, dict):
            raise GatewayBlocked('invalid_params', 'params must be an object')

        if cap.policy in (ConfirmationPolicy.CONFIRM.value, ConfirmationPolicy.CRITICAL.value):
            if confirmation_token:
                try:
                    self._manager.confirmations.consume(confirmation_token, params=params)
                except ConfirmationError as e:
                    raise GatewayBlocked('confirmation_invalid', str(e))
                return self._invoke(cap, params)
            conf = self._manager.confirmations.create(
                self._plugin_id, name, params, cap.permission, cap.policy)
            # Это НЕ ошибка: штатная механика подтверждения WRITE — ждём решения
            # пользователя, поэтому уровень info, чтобы строка не попадала в
            # фильтр «Ошибки и предупреждения» во вкладке Логи.
            self.log('info', 'confirmation_required', capability=name, policy=cap.policy)
            raise PendingConfirmation(conf)

        return self._invoke(cap, params)

    def _invoke(self, cap, params):
        try:
            result = cap.handler(params or {})
        except Exception as e:
            self.log('error', 'capability_failed', capability=cap.name, error=str(e))
            raise
        self.log('info', 'capability_ok', capability=cap.name)
        return result
