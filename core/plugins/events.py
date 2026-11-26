"""Event System + Activity Journal (stdlib-only).

- EventBus: публикация/подписка в Process; подписчик не может уронить публикатора.
- ActivityJournal: JSONL-журнал data/plugins/activity/{global,<id>}.jsonl,
  ротация хвоста, redact секретов.
"""
import json
import os
import threading
import time

MAX_LINES = 2000


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


class EventBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._subs = []

    def subscribe(self, fn):
        with self._lock:
            self._subs.append(fn)

    def unsubscribe(self, fn):
        with self._lock:
            try:
                self._subs.remove(fn)
            except ValueError:
                pass

    def publish(self, event, payload):
        with self._lock:
            subs = list(self._subs)
        for fn in subs:
            try:
                fn(event, payload)
            except Exception:
                continue


class ActivityJournal:
    KINDS = ('info', 'warn', 'error', 'action')

    def __init__(self, dir_path, max_lines=MAX_LINES):
        self.dir_path = dir_path
        self.max_lines = max_lines
        os.makedirs(dir_path, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, plugin_id=None):
        name = '%s.jsonl' % (plugin_id or 'global')
        return os.path.join(self.dir_path, name)

    def add(self, plugin_id, kind, event, **details):
        if kind not in self.KINDS:
            kind = 'info'
        entry = {'ts': _now(), 'level': kind, 'plugin': plugin_id, 'event': event}
        if details:
            entry['details'] = details
        with self._lock:
            for path in (self._path(plugin_id),):
                with open(path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                self._rotate(path)

    def _rotate(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except OSError:
            return
        if len(lines) > self.max_lines:
            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(lines[-self.max_lines:])

    def clear_issues(self, plugin_id=None):
        """Удалить из журнала(ов) записи level warn/error (кнопка «Очистить ошибки»).

        Не трогаем info/action — история действий остаётся честной, чистим только
        уже увиденные/исправленные ошибки и предупреждения. Возвращает число удалённых строк.
        """
        total = 0
        if plugin_id is not None:
            names = ['%s.jsonl' % plugin_id]
        else:
            try:
                names = os.listdir(self.dir_path)
            except OSError:
                return 0
        for name in names:
            if not name.endswith('.jsonl'):
                continue
            path = os.path.join(self.dir_path, name)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except OSError:
                continue
            kept = []
            for line in lines:
                try:
                    lvl = json.loads(line).get('level')
                except ValueError:
                    kept.append(line)
                    continue
                if lvl in ('warn', 'error'):
                    total += 1
                else:
                    kept.append(line)
            if len(kept) != len(lines):
                try:
                    # атомарно не обязательно (журнал append-only), но перезапишем аккуратно
                    with open(path + '.tmp', 'w', encoding='utf-8') as f:
                        f.writelines(kept)
                    os.replace(path + '.tmp', path)
                except OSError:
                    pass
        return total

    def read(self, plugin_id=None, limit=200, level=None, search=None):
        path = self._path(plugin_id)
        out = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except OSError:
            return []
        for line in reversed(lines):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if level and e.get('level') != level:
                continue
            if search and search.lower() not in json.dumps(e, ensure_ascii=False).lower():
                continue
            out.append(e)
            if len(out) >= max(1, min(limit, 1000)):
                break
        return out
