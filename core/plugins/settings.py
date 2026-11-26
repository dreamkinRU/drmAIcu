"""Settings Manager: настройки плагинов по settings_schema (stdlib-only).

Каждый плагин — отдельный файл data/plugins/state/<id>/settings.json; состояние
(произвольные данные плагина) — рядом в state.json. Настройки валидируются типами.
"""
import json
import os
import threading

from .atomicio import atomic_write_json


class SettingsValidationError(Exception):
    pass


class SettingsManager:
    def __init__(self, state_dir):
        self.state_dir = state_dir
        self._lock = threading.Lock()
        os.makedirs(state_dir, exist_ok=True)

    def _plugin_dir(self, plugin_id):
        d = os.path.join(self.state_dir, plugin_id)
        os.makedirs(d, exist_ok=True)
        return d

    # ---------------- settings.json ----------------

    def _path(self, plugin_id):
        return os.path.join(self._plugin_dir(plugin_id), 'settings.json')

    def _read(self, plugin_id):
        try:
            with open(self._path(plugin_id), 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self, plugin_id, data):
        path = self._path(plugin_id)
        # atomic_write_json: retry при WinError 5 (антивирус/облако держат файл)
        atomic_write_json(path, data)

    @staticmethod
    def validate_value(schema, key, value):
        rule = schema.get(key)
        if rule is None:
            raise SettingsValidationError('unknown setting: %s' % key)
        t = rule.get('type')
        if t == 'string' and not isinstance(value, str):
            raise SettingsValidationError('%s must be a string' % key)
        if t == 'number' and not isinstance(value, (int, float)) or isinstance(value, bool) and t == 'number':
            raise SettingsValidationError('%s must be a number' % key)
        if t == 'boolean' and not isinstance(value, bool):
            raise SettingsValidationError('%s must be a boolean' % key)
        if t == 'enum':
            if value not in rule.get('enum', []):
                raise SettingsValidationError('%s must be one of %s' % (key, rule.get('enum')))
        return value

    def merged(self, plugin_id, schema):
        stored = self._read(plugin_id)
        out = {}
        for key, rule in (schema or {}).items():
            if key in stored:
                out[key] = stored[key]
            elif 'default' in rule:
                out[key] = rule['default']
        return out

    def get(self, plugin_id, schema, key, default=None):
        merged = self.merged(plugin_id, schema)
        return merged.get(key, default)

    def set_many(self, plugin_id, schema, updates):
        if not isinstance(updates, dict):
            raise SettingsValidationError('settings payload must be an object')
        with self._lock:
            stored = self._read(plugin_id)
            for k, v in (updates or {}).items():
                if k not in schema:
                    raise SettingsValidationError('unknown setting: %s' % k)
                stored[k] = self.validate_value(schema, k, v)
            self._write(plugin_id, stored)

    def remove_plugin(self, plugin_id, keep=False):
        d = os.path.join(self.state_dir, plugin_id)
        if keep:
            return
        for name in ('settings.json', 'state.json', 'settings.json.tmp'):
            try:
                os.remove(os.path.join(d, name))
            except FileNotFoundError:
                pass
        try:
            os.rmdir(d)
        except OSError:
            pass

    # ---------------- state.json ----------------

    def load_state(self, plugin_id):
        try:
            with open(os.path.join(self._plugin_dir(plugin_id), 'state.json'), 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_state(self, plugin_id, state):
        with self._lock:
            with open(os.path.join(self._plugin_dir(plugin_id), 'state.json'), 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
