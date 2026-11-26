"""Secret Manager: раздельное хранение секретов плагинов (stdlib-only).

- Файл на плагин: data/plugins/secrets/<id>.secrets.json, права 0600 (best-effort, Windows limited).
- Ни один метод не логирует значения; get/set не возвращают секрет в исключениях.
- redact() заменяет известные значения секретов на ***REDACTED*** — используется журналом.
"""
import json
import os
import threading

from .atomicio import atomic_write_json


class SecretManager:
    def __init__(self, dir_path):
        self.dir_path = dir_path
        self._lock = threading.Lock()
        os.makedirs(dir_path, exist_ok=True)
        self._harden_dir()

    def _harden_dir(self):
        try:
            os.chmod(self.dir_path, 0o700)
        except OSError:
            pass

    def _path(self, plugin_id):
        return os.path.join(self.dir_path, '%s.secrets.json' % plugin_id)

    def _load(self, plugin_id):
        try:
            with open(self._path(plugin_id), 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, plugin_id, data):
        path = self._path(plugin_id)
        # atomic_write_json: retry при WinError 5 + chmod 0600 для tmp-файла
        atomic_write_json(path, data, chmod=0o600)

    def set_secret(self, plugin_id, key, value):
        if not key or not isinstance(key, str):
            raise ValueError('secret key required')
        with self._lock:
            data = self._load(plugin_id)
            data[key] = str(value)
            self._save(plugin_id, data)

    def get_secret(self, plugin_id, key):
        if not key or not isinstance(key, str):
            return None
        with self._lock:
            return self._load(plugin_id).get(key)

    def keys(self, plugin_id):
        return sorted(self._load(plugin_id).keys())

    def remove_secret(self, plugin_id, key):
        with self._lock:
            data = self._load(plugin_id)
            if key in data:
                del data[key]
                self._save(plugin_id, data)

    def delete_all(self, plugin_id):
        with self._lock:
            try:
                os.remove(self._path(plugin_id))
            except FileNotFoundError:
                pass

    def redact(self, plugin_id, text):
        if not isinstance(text, str) or not text:
            return text
        for v in self._load(plugin_id).values():
            if v and len(v) >= 6 and v in text:
                text = text.replace(v, '***REDACTED***')
        return text

    @staticmethod
    def mask(value):
        if not value:
            return ''
        v = str(value)
        return '***' + v[-4:] if len(v) >= 8 else '***'
