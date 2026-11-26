"""PluginManager: оркестрация Discovery→Run, изоляция ошибок, gateway.

Данные (раздельные файлы, §9.1):
  data/plugins/registry.json         — реестр
  data/plugins/permissions.json      — разрешения
  data/plugins/confirmations.json    — pending-подтверждения
  data/plugins/state/<id>/settings.json, state.json
  data/plugins/secrets/<id>.secrets.json
  data/plugins/activity/*.jsonl      — журнал
"""
import os
import re
import shutil
import threading
import time

from .api import PendingConfirmation, PluginAPI
from .confirmations import ConfirmationError, ConfirmationManager
from .events import ActivityJournal, EventBus
from .loader import Loader, load_entry, unload
from .models import (PLUGIN_API_VERSION, PluginRecord, PluginStatus, api_compatible)
from .permissions import PermissionLevel, PermissionManager, permission_level
from .secrets import SecretManager
from .settings import SettingsManager, SettingsValidationError


class PluginInstallError(Exception):
    pass


class PluginNotRunningError(Exception):
    pass


class PluginManager:
    def __init__(self, base_dir, data_dir=None, builtin_dir=None):
        self.base = os.path.abspath(base_dir)
        self.data_dir = os.path.abspath(data_dir) if data_dir else os.path.join(self.base, 'data', 'plugins')
        self.builtin_dir = os.path.abspath(builtin_dir) if builtin_dir else os.path.join(self.base, 'plugins')
        p = self.data_dir
        os.makedirs(p, exist_ok=True)
        os.makedirs(os.path.join(p, 'activity'), exist_ok=True)
        os.makedirs(os.path.join(p, 'state'), exist_ok=True)
        os.makedirs(os.path.join(p, 'secrets'), exist_ok=True)
        from .registry import PluginRegistry
        self.registry = PluginRegistry(os.path.join(p, 'registry.json'))
        self.permissions = PermissionManager(os.path.join(p, 'permissions.json'))
        self.settings = SettingsManager(os.path.join(p, 'state'))
        self.secrets = SecretManager(os.path.join(p, 'secrets'))
        self.confirmations = ConfirmationManager(os.path.join(p, 'confirmations.json'))
        self.events = EventBus()
        self.activity = ActivityJournal(os.path.join(p, 'activity'))
        self.loader = Loader(self.builtin_dir, os.path.join(p, 'installed'))
        self._modules = {}
        self._apis = {}
        self._hooks = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ catalog

    def catalog(self):
        """Встроенный каталог: доступные плагины + совместимость + разрешения."""
        out = []
        for item in self.loader.builtin_manifests():
            entry = {'available': item['manifest'] is not None, 'errors': item['errors']}
            if item['manifest']:
                m = item['manifest']
                rec = self.registry.get(m['id'])
                entry['manifest'] = PluginRecord.from_manifest(m).public(details=True)
                entry['installed'] = rec is not None
                entry['compatible'] = api_compatible(m.get('api_version', ''))
                entry['permissions'] = [
                    {'permission': pp, 'level': permission_level(pp)} for pp in m.get('permissions', [])
                ]
            out.append(entry)
        return out

    # ------------------------------------------------------------------ install

    def install(self, source, grant_read=True):
        """Установка из builtin:<id> / каталога / архива: VALIDATE → REGISTER → AUTHORIZE."""
        plugin_dir, manifest, errors = self.loader.resolve_source(source)
        if errors:
            self.activity.add(None, 'error', 'install_rejected', source=str(source), error='; '.join(errors))
            raise PluginInstallError('; '.join(errors))
        pid = manifest['id']
        if not api_compatible(manifest.get('api_version', '')):
            err = 'incompatible Plugin API version: %s (core %s)' % (manifest.get('api_version'), PLUGIN_API_VERSION)
            self.activity.add(None, 'error', 'install_rejected', source=str(source), error=err)
            raise PluginInstallError(err)
        rec = self.registry.get(pid)
        if rec:
            err = 'plugin already installed: %s v%s (delete it first or wait for controlled update)' % (pid, rec.version)
            self.activity.add(None, 'error', 'install_rejected', source=str(source), error=err)
            raise PluginInstallError(err)
        with self._lock:
            builtin_path = os.path.abspath(os.path.join(self.builtin_dir, pid))
            is_builtin = os.path.abspath(plugin_dir) == builtin_path
            if not is_builtin:
                plugin_dir = self.loader.install_copy(pid, plugin_dir)
            rec = PluginRecord.from_manifest(manifest)
            rec.source = 'builtin' if is_builtin else 'installed'
            rec.path = plugin_dir
            rec.enabled = False
            rec.status = PluginStatus.INSTALLED.value
            rec.installed_at = self._ts()
            self.registry.upsert(rec)
            if grant_read:
                self.permissions.grant_all_of_level(pid, manifest.get('permissions', []), PermissionLevel.READ.value)
            self.activity.add(pid, 'action', 'installed', version=rec.version, source=rec.source)
        return self.info(pid)

    def _ts(self):
        return time.strftime('%Y-%m-%dT%H:%M:%S')

    # ------------------------------------------------------------------ lifecycle

    def load_all(self):
        """Запуск включённых плагинов при старте приложения. Ошибки изолированы."""
        for rec in self.registry.all():
            if rec.enabled and rec.status != PluginStatus.INCOMPATIBLE.value:
                try:
                    self._start(rec.id)
                except Exception as e:
                    self.registry.update(rec.id, status=PluginStatus.ERROR.value,
                                         enabled=False, last_error=str(e))
                    self.activity.add(rec.id, 'error', 'startup_load_failed', error=str(e))

    def _start(self, pid):
        rec = self.registry.get(pid)
        if rec is None:
            raise KeyError(pid)
        if not api_compatible(rec.api_version):
            self.registry.update(pid, status=PluginStatus.INCOMPATIBLE.value,
                                 last_error='requires Plugin API %s, core has %s' % (rec.api_version, PLUGIN_API_VERSION))
            self.activity.add(pid, 'error', 'incompatible_api', api=rec.api_version)
            raise PluginInstallError('plugin %s incompatible' % pid)
        self.registry.update(pid, status=PluginStatus.LOADING.value, last_error='')
        self.activity.add(pid, 'info', 'loading')
        try:
            module = load_entry(pid, rec.path, rec.entry_point)
            api = PluginAPI(self, pid)
            if not hasattr(module, 'initialize'):
                raise ImportError('entry_point does not define initialize(ctx)')
            ok = module.initialize(api)
            if ok is False:
                raise RuntimeError('initialize() returned False')
            self._modules[pid] = module
            self._apis[pid] = api
            hooks = {k: getattr(module, k) for k in ('start', 'stop', 'health', 'uninstall') if hasattr(module, k)}
            if 'start' in hooks:
                hooks['start']()
            self._hooks[pid] = hooks
        except Exception as e:
            unload(pid)
            with self._lock:
                self._modules.pop(pid, None)
                self._apis.pop(pid, None)
                self._hooks.pop(pid, None)
            self.registry.update(pid, status=PluginStatus.ERROR.value, enabled=False,
                                 last_error=str(e))
            self.activity.add(pid, 'error', 'initialize_failed', error=str(e))
            raise
        self.registry.update(pid, status=PluginStatus.RUNNING.value, enabled=True, last_error='')
        self.activity.add(pid, 'info', 'running')

    def enable(self, pid):
        if self.registry.get(pid) is None:
            raise KeyError(pid)
        self._start(pid)
        return self.info(pid)

    def disable(self, pid):
        if self.registry.get(pid) is None:
            raise KeyError(pid)
        self._hooks_stop(pid)
        self.registry.update(pid, status=PluginStatus.DISABLED.value, enabled=False)
        self.activity.add(pid, 'action', 'disabled')
        return self.info(pid)

    def _hooks_stop(self, pid):
        hooks = self._hooks.pop(pid, None)
        api = self._apis.get(pid)
        if hooks and 'stop' in hooks:
            try:
                hooks['stop']()
            except Exception as e:
                if api:
                    api.log('error', 'stop_failed', error=str(e))
        unload(pid)
        with self._lock:
            self._modules.pop(pid, None)
            self._apis.pop(pid, None)
            self._hooks.pop(pid, None)

    def uninstall(self, pid):
        rec = self.registry.get(pid)
        if rec is None:
            raise KeyError(pid)
        module = self._modules.get(pid)
        if module is not None and hasattr(module, 'uninstall'):
            try:
                module.uninstall()
            except Exception:
                pass
        self._hooks_stop(pid)
        if rec.source == 'installed' and rec.path and os.path.isdir(rec.path):
            shutil.rmtree(rec.path, ignore_errors=True)
        self.secrets.delete_all(pid)
        self.permissions.remove_plugin(pid)
        self.settings.remove_plugin(pid, keep=False)
        self.registry.remove(pid)
        self.activity.add(pid, 'action', 'uninstalled')

    # ------------------------------------------------------------------ info / health

    def info(self, pid, details=False):
        rec = self.registry.get(pid)
        if rec is None:
            raise KeyError(pid)
        d = rec.public(details=details)
        api = self._apis.get(pid)
        if api:
            d['capabilities'] = api.capabilities()
        return d

    def list_plugins(self):
        return [r.public(details=True) for r in self.registry.all()]

    def health(self, pid):
        rec = self.registry.get(pid)
        if rec is None:
            raise KeyError(pid)
        result = {'status': rec.status, 'enabled': rec.enabled, 'last_error': rec.last_error}
        if rec.status == PluginStatus.RUNNING.value and pid in self._modules:
            module = self._modules[pid]
            if hasattr(module, 'health'):
                try:
                    h = module.health() or {}
                    if isinstance(h, dict):
                        result.update(h)
                except Exception as e:
                    result['health_error'] = str(e)
        return result

    # ------------------------------------------------------------------ gateway

    def exec(self, pid, capability, params=None, confirmation_token=None):
        api = self._apis.get(pid)
        if api is None:
            raise PluginNotRunningError('plugin %s is not running' % pid)
        try:
            result = api.call(capability, params=params, confirmation_token=confirmation_token)
        except PendingConfirmation as e:
            return {'status': 'confirmation_required', 'confirmation': e.confirmation}
        return {'status': 'done', 'result': result}

    def confirm(self, cid, approve):
        if not approve:
            item = self.confirmations.reject(cid)
            self.activity.add(item['plugin'], 'action', 'confirmation_rejected',
                              capability=item['capability'])
            return {'status': 'rejected', 'plugin': item['plugin']}
        item = self.confirmations.peek(cid)
        if item is None:
            raise ConfirmationError('unknown or already used confirmation')
        pid = item['plugin']
        api = self._apis.get(pid)
        if api is None:
            raise PluginNotRunningError('plugin %s is not running' % pid)
        params = item.get('params')
        result = api.call(item['capability'], params=params, confirmation_token=cid)
        self.activity.add(pid, 'action', 'confirmation_approved', capability=item['capability'])
        return {'status': 'done', 'plugin': pid, 'capability': item['capability'], 'result': result}

    def pending_confirmations(self, pid=None):
        return self.confirmations.pending(pid)

    # ------------------------------------------------------------------ permissions / settings

    def permissions_status(self, pid):
        rec = self.registry.get(pid)
        if rec is None:
            raise KeyError(pid)
        return {'plugin': pid,
                'permissions': self.permissions.status_for(pid, rec.permissions),
                'granted': self.permissions.granted_for(pid)}

    def permissions_put(self, pid, grants):
        rec = self.registry.get(pid)
        if rec is None:
            raise KeyError(pid)
        declared = set(rec.permissions)
        for item in grants or []:
            if not isinstance(item, dict) or 'permission' not in item or 'granted' not in item:
                raise ValueError('grants items must contain permission and granted')
            perm = item['permission']
            if perm not in declared:
                raise ValueError('permission not declared in manifest: %s' % perm)
            if item['granted']:
                self.permissions.grant(pid, perm)
            else:
                self.permissions.revoke(pid, perm)
        self.activity.add(pid, 'action', 'permissions_updated', count=len(grants or []))
        return self.permissions_status(pid)

    def settings_get(self, pid):
        rec = self.registry.get(pid)
        if rec is None:
            raise KeyError(pid)
        return {'plugin': pid, 'settings': self.settings.merged(pid, rec.settings_schema),
                'schema': rec.settings_schema}

    def settings_put(self, pid, updates):
        rec = self.registry.get(pid)
        if rec is None:
            raise KeyError(pid)
        try:
            self.settings.set_many(pid, rec.settings_schema, updates)
        except SettingsValidationError as e:
            raise PluginInstallError(str(e))
        self.activity.add(pid, 'action', 'settings_updated', keys=sorted((updates or {}).keys()))
        return self.settings_get(pid)

    # ------------------------------------------------------------------ secrets (write-only: значения не возвращаются)

    _SECRET_KEY_RE = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')

    def secrets_put(self, pid, updates):
        """Записать секреты плагина. Возвращает только имена ключей, значения не читаются обратно."""
        rec = self.registry.get(pid)
        if rec is None:
            raise KeyError(pid)
        if not isinstance(updates, dict) or not updates:
            raise ValueError('secrets payload must be a non-empty object')
        clean = {}
        for k, v in updates.items():
            if not isinstance(k, str) or not self._SECRET_KEY_RE.match(k):
                raise ValueError('invalid secret key: %r' % (k,))
            if not isinstance(v, str) or not v.strip():
                raise ValueError('secret value for %r must be a non-empty string' % (k,))
            clean[k] = v
        for k, v in clean.items():
            self.secrets.set_secret(pid, k, v)
        self.activity.add(pid, 'action', 'secret_set', keys=sorted(clean.keys()))
        return self.secret_keys(pid)

    def secret_delete(self, pid, key):
        rec = self.registry.get(pid)
        if rec is None:
            raise KeyError(pid)
        if not isinstance(key, str) or not self._SECRET_KEY_RE.match(key):
            raise ValueError('invalid secret key: %r' % (key,))
        self.secrets.remove_secret(pid, key)
        self.activity.add(pid, 'action', 'secret_deleted', key=key)
        return self.secret_keys(pid)

    def secret_keys(self, pid):
        rec = self.registry.get(pid)
        if rec is None:
            raise KeyError(pid)
        return {'plugin': pid, 'secrets': sorted(self.secrets.keys(pid))}

    def activity_read(self, pid=None, limit=200, level=None, search=None):
        return self.activity.read(plugin_id=pid, limit=limit, level=level, search=search)

    def clear_issues(self):
        """Стереть ошибки/предупреждения всех плагинов из журналов активности (warn/error).

        Нужно для кнопки «Очистить ошибки» во вкладке «Логи»: старые ошибки
        остаются только до тех пор, пока пользователь их не закроет сам.
        """
        return self.activity.clear_issues()

    def recent_issues(self, limit=60):
        """Ошибки и предупреждения всех плагинов из журналов активности (data/plugins/activity/*.jsonl).

        Нужно для вкладки Логи: раньше /api/logs отдавал только ядро (main.py LOG),
        и ошибки плагинов (sync/confirm/deny и т.п.) туда не попадали.
        Формат элемента совпадает с ядром: {'time' (HH:MM:SS), 'level', 'message', 'source'}.
        """
        entries = []
        try:
            names = os.listdir(self.activity.dir_path)
        except OSError:
            return []
        for name in names:
            if not name.endswith('.jsonl'):
                continue
            pid = name[:-len('.jsonl')]
            read_pid = None if pid == 'global' else pid
            try:
                rows = self.activity.read(plugin_id=read_pid, limit=500)
            except Exception:
                continue
            for row in rows:
                if row.get('level') not in ('error', 'warn'):
                    continue
                details = row.get('details') or {}
                who = 'core' if read_pid is None else pid
                parts = ['%s: %s' % (who, row.get('event', '?'))]
                for k in ('error', 'reason', 'capability', 'source'):
                    v = details.get(k)
                    if v:
                        parts.append('%s=%s' % (k, str(v)[:300]))
                ts = row.get('ts') or ''
                entries.append({
                    'time': ts.split('T', 1)[1] if 'T' in ts else ts,
                    'level': row.get('level'),
                    'message': '; '.join(parts[:4]),
                    'source': ('plugin/' + who) if read_pid is not None else 'plugins',
                })
        entries.sort(key=lambda e: e.get('time') or '')
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 60
        return entries[-limit:] if limit > 0 else entries
