"""Plugin Loader: обнаружение каталогов, валидация, импорт точки входа.

- Встроенный каталог: <BASE>/plugins/<id>/plugin.json
- Установленные вручную: <data>/installed/<id>/plugin.json (копия источника)
- Плагин импортируется как пакет _plugin_<id> — работают относительные импорты;
  файлы каталога плагина при загрузке не создаются и не изменяются.
- Ошибка фазы LOAD не затрагивает другие плагины — изоляцию обеспечивает PluginManager.
"""
import importlib.util
import json
import os
import shutil
import sys
import tarfile
import types
import zipfile

from .models import api_compatible, validate_manifest

MAX_PACKAGE_BYTES = 50 * 1024 * 1024

MANIFEST_NAME = 'plugin.json'


def find_manifest_dir(root):
    root = os.path.abspath(root)
    if os.path.isfile(os.path.join(root, MANIFEST_NAME)):
        return root
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, MANIFEST_NAME)):
            return d
    return None


def read_manifest(plugin_dir):
    path = os.path.join(plugin_dir, MANIFEST_NAME)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f), path


def discover_builtin(builtin_dir):
    """Список (dir, manifest, errors) для всех плагинов встроенного каталога."""
    out = []
    if not os.path.isdir(builtin_dir):
        return out
    for name in sorted(os.listdir(builtin_dir)):
        d = os.path.join(builtin_dir, name)
        if not os.path.isdir(d):
            continue
        mp = os.path.join(d, MANIFEST_NAME)
        if not os.path.isfile(mp):
            continue
        try:
            manifest, _ = read_manifest(d)
        except (OSError, ValueError) as e:
            out.append((d, None, ['unreadable manifest: %s' % e]))
            continue
        manifest, errors = validate_manifest(manifest)
        out.append((d, manifest, errors))
    return out


def load_entry(plugin_id, plugin_dir, entry_point):
    """Импорт entry_point как пакета _plugin_<id> (без записи в plugin_dir)."""
    pkg_name = '_plugin_%s' % plugin_id
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [os.path.abspath(plugin_dir)]
    sys.modules[pkg_name] = pkg
    entry_name = '%s.%s' % (pkg_name, entry_point[:-3])
    spec = importlib.util.spec_from_file_location(entry_name, os.path.join(plugin_dir, entry_point))
    if spec is None or spec.loader is None:
        raise ImportError('entry_point not found: %s' % entry_point)
    entry = importlib.util.module_from_spec(spec)
    entry.__package__ = pkg_name
    sys.modules[entry_name] = entry
    spec.loader.exec_module(entry)
    return entry


def unload(plugin_id, entry_point='plugin.py'):
    """Выгрузка модулей плагина из sys.modules (для reload/disable)."""
    pkg_name = '_plugin_%s' % plugin_id
    for name in list(sys.modules):
        if name == pkg_name or name.startswith(pkg_name + '.'):
            del sys.modules[name]


class Loader:
    def __init__(self, builtin_dir, installed_dir):
        self.builtin_dir = os.path.abspath(builtin_dir)
        self.installed_dir = os.path.abspath(installed_dir)
        os.makedirs(self.installed_dir, exist_ok=True)

    # ---------- источники установки ----------

    def builtin_manifests(self):
        out = []
        for d, manifest, errors in discover_builtin(self.builtin_dir):
            out.append({'path': d, 'manifest': manifest, 'errors': errors})
        return out

    def resolve_source(self, source):
        """'builtin:<id>' | каталог | .zip/.tar.gz → (plugin_dir, manifest, errors)."""
        if isinstance(source, str) and source.startswith('builtin:'):
            pid = source.split(':', 1)[1]
            d = os.path.join(self.builtin_dir, pid)
            if not os.path.isfile(os.path.join(d, MANIFEST_NAME)):
                return None, None, ['unknown builtin plugin: %s' % pid]
            manifest, errors = validate_manifest(*read_manifest(d)[:1])
            return d, manifest, errors
        src = os.path.abspath(source)
        if not os.path.exists(src):
            return None, None, ['source not found: %s' % source]
        if zip_is_archive(src):
            d = self._extract(src)
        elif os.path.isdir(src):
            d = find_manifest_dir(src)
            if d is None:
                return None, None, ['plugin.json not found in: %s' % src]
        else:
            return None, None, ['unsupported source: %s' % src]
        manifest, errors = validate_manifest(*read_manifest(d)[:1])
        return d, manifest, errors

    @staticmethod
    def _extract(src):
        lower = src.lower()
        if lower.endswith('.zip'):
            if not zipfile.is_zipfile(src):
                raise ValueError('not a valid zip archive: %s' % src)
            out = src + '.extracted'
            if os.path.isdir(out):
                shutil.rmtree(out)
            with zipfile.ZipFile(src) as z:
                names = z.namelist()
                for n in names:
                    if n.startswith('/') or '..' in n.replace('\\', '/').split('/'):
                        raise ValueError('unsafe path in archive: %s' % n)
                z.extractall(out)
        elif lower.endswith(('.tar.gz', '.tgz')):
            out = src + '.extracted'
            if os.path.isdir(out):
                shutil.rmtree(out)
            with tarfile.open(src, 'r:gz') as t:
                for m in t.getmembers():
                    if m.name.startswith('/') or '..' in m.name.split('/'):
                        raise ValueError('unsafe path in archive: %s' % m.name)
                t.extractall(out)
        else:
            raise ValueError('unsupported archive type: %s' % src)
        d = find_manifest_dir(out)
        if d is None:
            raise ValueError('plugin.json not found in archive')
        return d

    def install_copy(self, plugin_id, source_dir):
        """Копия для посторонних источников (builtin остаётся на месте)."""
        target = os.path.join(self.installed_dir, plugin_id)
        if os.path.isdir(target):
            shutil.rmtree(target)
        shutil.copytree(source_dir, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        return target


def zip_is_archive(path):
    return os.path.isfile(path) and path.lower().endswith(('.zip', '.tar.gz', '.tgz'))


__all__ = ['Loader', 'load_entry', 'unload', 'discover_builtin', 'read_manifest',
           'find_manifest_dir', 'MANIFEST_NAME', 'MAX_PACKAGE_BYTES']
