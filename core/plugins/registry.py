"""Plugin Registry: реестр установленных плагинов (data/plugins/registry.json)."""
import json
import os
import threading
import time

from .models import PluginRecord, PluginStatus

from .atomicio import atomic_write_json


class PluginRegistry:
    def __init__(self, path, now=None):
        self.path = path
        self._now = now or (lambda: time.strftime('%Y-%m-%dT%H:%M:%S'))
        self._lock = threading.Lock()
        self._records = {}
        # Деградация: если файл реестра удерживается другим процессом (WinError 5 —
        # облачная синхронизация/антивирус), состояние ЖИВЁТ В ПАМЯТИ, сбой записи
        # фиксируется в persist_error и виден в health — но плагин НЕ падает.
        self.persist_error = ''
        self._load()

    def _load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        plugins = data.get('plugins') if isinstance(data, dict) else None
        if not isinstance(plugins, list):
            return
        for item in plugins:
            try:
                rec = PluginRecord(
                    id=item['id'], name=item['name'], version=item['version'],
                    description=item.get('description', ''), author=item.get('author', ''),
                    api_version=item.get('api_version', ''), entry_point=item.get('entry_point', 'plugin.py'),
                    permissions=list(item.get('permissions', [])),
                    settings_schema=dict(item.get('settings_schema', {})),
                    status=item.get('status', PluginStatus.INSTALLED.value),
                    source=item.get('source', 'installed'),
                    path=item.get('path', ''), enabled=bool(item.get('enabled')),
                    installed_at=item.get('installed_at', ''),
                    last_error=item.get('last_error', ''),
                )
            except (KeyError, TypeError):
                continue
            self._records[rec.id] = rec

    def _save(self):
        data = {'version': 1, 'updated_at': self._now(), 'plugins': []}
        for rec in self._records.values():
            data['plugins'].append({
                'id': rec.id, 'name': rec.name, 'version': rec.version,
                'description': rec.description, 'author': rec.author,
                'api_version': rec.api_version, 'entry_point': rec.entry_point,
                'permissions': list(rec.permissions),
                'settings_schema': dict(rec.settings_schema),
                'status': rec.status, 'source': rec.source, 'path': rec.path,
                'enabled': rec.enabled, 'installed_at': rec.installed_at,
                'last_error': rec.last_error,
            })
        # atomic_write_json: retry при WinError 5 (антивирус/облако держат файл)
        atomic_write_json(self.path, data)

    def _safe_save(self):
        """Запись best-effort: сбой диска не роняет вызванного (плагин остаётся в памяти)."""
        try:
            self._save()
            self.persist_error = ''
            return True
        except OSError as exc:
            self.persist_error = str(exc)
            return False

    def upsert(self, record):
        """Идемпотентная регистрация: повторная установка не создаёт дублей."""
        with self._lock:
            self._records[record.id] = record
            self._safe_save()

    def get(self, plugin_id):
        return self._records.get(plugin_id)

    def all(self):
        return list(self._records.values())

    def update(self, plugin_id, **fields):
        with self._lock:
            rec = self._records.get(plugin_id)
            if rec is None:
                return None
            for k, v in fields.items():
                if hasattr(rec, k):
                    setattr(rec, k, v)
            self._safe_save()
            return rec

    def remove(self, plugin_id):
        with self._lock:
            self._records.pop(plugin_id, None)
            self._safe_save()
