"""Plugin Loader: обнаружение, валидация и безопасная установка Python-плагинов."""
import importlib.util
import json
import ntpath
import os
import shutil
import stat
import sys
import tarfile
import tempfile
import types
import zipfile

from .models import api_compatible, validate_manifest

MAX_PACKAGE_BYTES = 50 * 1024 * 1024
MAX_PACKAGE_FILES = 5000
MAX_MANIFEST_BYTES = 1024 * 1024
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
    before = os.lstat(path)
    before_reparse = bool(getattr(before, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
    if stat.S_ISLNK(before.st_mode) or before_reparse or not stat.S_ISREG(before.st_mode):
        raise ValueError('plugin manifest must be a regular non-reparse file')
    if before.st_size > MAX_MANIFEST_BYTES:
        raise ValueError('plugin manifest exceeds size limit')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        opened_reparse = bool(getattr(opened, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
        if not stat.S_ISREG(opened.st_mode) or opened_reparse or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError('plugin manifest changed while opening')
        if opened.st_size > MAX_MANIFEST_BYTES:
            raise ValueError('plugin manifest exceeds size limit')
        with os.fdopen(fd, 'r', encoding='utf-8') as f:
            fd = None
            return json.load(f), path
    finally:
        if fd is not None:
            os.close(fd)


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

    def builtin_manifests(self):
        out = []
        for d, manifest, errors in discover_builtin(self.builtin_dir):
            out.append({'path': d, 'manifest': manifest, 'errors': errors})
        return out

    def validate_source_tree(self, source_dir):
        """Проверяет размер и запрещает symlink/reparse points в ручном источнике."""
        root = os.path.abspath(source_dir)
        root_info = os.lstat(root)
        root_reparse = bool(getattr(root_info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
        if stat.S_ISLNK(root_info.st_mode) or root_reparse or not stat.S_ISDIR(root_info.st_mode):
            raise ValueError('plugin source must be a real directory')
        total = 0
        count = 0
        for current, dirs, files in os.walk(root, followlinks=False):
            for name in dirs + files:
                path = os.path.join(current, name)
                info = os.lstat(path)
                reparse = bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
                if stat.S_ISLNK(info.st_mode) or reparse:
                    raise ValueError('symlink/reparse point is not allowed in plugin source: %s' % path)
                if stat.S_ISREG(info.st_mode):
                    total += info.st_size
                elif not stat.S_ISDIR(info.st_mode):
                    raise ValueError('unsupported file type in plugin source: %s' % path)
                count += 1
                if count > MAX_PACKAGE_FILES or total > MAX_PACKAGE_BYTES:
                    raise ValueError('plugin source exceeds package limits')
        return True

    def resolve_source(self, source):
        """'builtin:<id>' | каталог | .zip/.tar.gz → (plugin_dir, manifest, errors)."""
        if isinstance(source, str) and source.startswith('builtin:'):
            pid = source.split(':', 1)[1]
            d = os.path.join(self.builtin_dir, pid)
            if not os.path.isfile(os.path.join(d, MANIFEST_NAME)):
                return None, None, ['unknown builtin plugin: %s' % pid]
            manifest, _ = read_manifest(d)
            manifest, errors = validate_manifest(manifest)
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
            self.validate_source_tree(d)
        else:
            return None, None, ['unsupported source: %s' % src]
        manifest, _ = read_manifest(d)
        manifest, errors = validate_manifest(manifest)
        return d, manifest, errors

    @staticmethod
    def _archive_target(root, name):
        normalized = str(name).replace('\\', '/')
        while normalized.startswith('./'):
            normalized = normalized[2:]
        if normalized.endswith('/'):
            normalized = normalized[:-1]
        if normalized in ('', '.'):
            return os.path.abspath(root)
        if normalized.startswith('/') or ntpath.splitdrive(normalized)[0] or '\x00' in normalized:
            raise ValueError('unsafe path in plugin archive: %r' % name)
        parts = normalized.split('/')
        if any(part in ('', '.', '..') for part in parts):
            raise ValueError('unsafe path in plugin archive: %r' % name)
        if os.name == 'nt':
            reserved = {'CON', 'PRN', 'AUX', 'NUL'}
            reserved.update('COM%d' % i for i in range(1, 10))
            reserved.update('LPT%d' % i for i in range(1, 10))
            for part in parts:
                if part.endswith(('.', ' ')) or ':' in part or part.split('.', 1)[0].upper() in reserved:
                    raise ValueError('Windows-incompatible path in plugin archive: %r' % name)
        target = os.path.abspath(os.path.join(root, *parts))
        try:
            if os.path.commonpath([os.path.abspath(root), target]) != os.path.abspath(root):
                raise ValueError('archive path escapes extraction root: %r' % name)
        except ValueError:
            raise ValueError('archive path escapes extraction root: %r' % name)
        return target

    @staticmethod
    def _prepare_extract_dir(src):
        out = src + '.extracted'
        if os.path.lexists(out):
            info = os.lstat(out)
            reparse = bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
            if stat.S_ISLNK(info.st_mode) or reparse:
                raise ValueError('extraction target must not be a symlink/reparse point')
            if stat.S_ISDIR(info.st_mode):
                shutil.rmtree(out)
            else:
                os.remove(out)
        os.makedirs(out)
        return out

    @staticmethod
    def _extract(src):
        lower = src.lower()
        if os.path.getsize(src) > MAX_PACKAGE_BYTES:
            raise ValueError('plugin archive exceeds compressed size limit')
        out = Loader._prepare_extract_dir(src)
        seen = set()
        total_written = 0

        def reserve_path(name, is_dir):
            target = Loader._archive_target(out, name)
            if target == os.path.abspath(out) and not is_dir:
                raise ValueError('archive member cannot write to extraction root')
            key = os.path.normcase(os.path.relpath(target, out))
            if key in seen:
                raise ValueError('duplicate archive path: %s' % name)
            seen.add(key)
            return target

        try:
            if lower.endswith('.zip'):
                if not zipfile.is_zipfile(src):
                    raise ValueError('not a valid zip archive: %s' % src)
                with zipfile.ZipFile(src) as archive:
                    infos = archive.infolist()
                    if len(infos) > MAX_PACKAGE_FILES:
                        raise ValueError('plugin archive contains too many files')
                    declared_total = sum(info.file_size for info in infos if not info.is_dir())
                    if declared_total > MAX_PACKAGE_BYTES:
                        raise ValueError('plugin archive exceeds uncompressed size limit')
                    for info in infos:
                        mode = (info.external_attr >> 16) & 0o170000
                        if mode == stat.S_IFLNK or mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                            raise ValueError('links/special files are not allowed in plugin archives: %s' % info.filename)
                        is_dir = info.is_dir() or mode == stat.S_IFDIR
                        target = reserve_path(info.filename, is_dir)
                        if is_dir:
                            os.makedirs(target, exist_ok=True)
                            continue
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        written = 0
                        with archive.open(info, 'r') as source, open(target, 'xb') as destination:
                            while True:
                                chunk = source.read(1024 * 1024)
                                if not chunk:
                                    break
                                written += len(chunk)
                                total_written += len(chunk)
                                if written > info.file_size or total_written > MAX_PACKAGE_BYTES:
                                    raise ValueError('plugin archive exceeded declared size')
                                destination.write(chunk)
                        if written != info.file_size:
                            raise ValueError('truncated archive member: %s' % info.filename)
            elif lower.endswith(('.tar.gz', '.tgz')):
                with tarfile.open(src, 'r:gz') as archive:
                    members = archive.getmembers()
                    if len(members) > MAX_PACKAGE_FILES:
                        raise ValueError('plugin archive contains too many files')
                    declared_total = sum(member.size for member in members if member.isfile())
                    if declared_total > MAX_PACKAGE_BYTES:
                        raise ValueError('plugin archive exceeds uncompressed size limit')
                    for member in members:
                        if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                            raise ValueError('links/devices are not allowed in plugin archives: %s' % member.name)
                        if not (member.isfile() or member.isdir()) or member.size < 0:
                            raise ValueError('unsupported TAR member type: %s' % member.name)
                        target = reserve_path(member.name, member.isdir())
                        if member.isdir():
                            os.makedirs(target, exist_ok=True)
                            continue
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        source = archive.extractfile(member)
                        if source is None:
                            raise ValueError('cannot read TAR member: %s' % member.name)
                        written = 0
                        with source, open(target, 'xb') as destination:
                            while True:
                                chunk = source.read(1024 * 1024)
                                if not chunk:
                                    break
                                written += len(chunk)
                                total_written += len(chunk)
                                if written > member.size or total_written > MAX_PACKAGE_BYTES:
                                    raise ValueError('plugin archive exceeded declared size')
                                destination.write(chunk)
                        if written != member.size:
                            raise ValueError('truncated TAR member: %s' % member.name)
            else:
                raise ValueError('unsupported archive type: %s' % src)

            d = find_manifest_dir(out)
            if d is None:
                raise ValueError('plugin.json not found in archive')
            return d
        except Exception:
            shutil.rmtree(out, ignore_errors=True)
            raise

    def install_copy(self, plugin_id, source_dir):
        """Безопасная staging-копия ручного плагина с повторной проверкой после копирования."""
        self.validate_source_tree(source_dir)
        target = os.path.join(self.installed_dir, plugin_id)
        staging = tempfile.mkdtemp(prefix=plugin_id + '.staging-', dir=self.installed_dir)
        try:
            shutil.copytree(source_dir, staging, symlinks=True, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            self.validate_source_tree(staging)
            if os.path.lexists(target):
                target_info = os.lstat(target)
                target_reparse = bool(getattr(target_info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
                if stat.S_ISLNK(target_info.st_mode) or target_reparse:
                    if stat.S_ISDIR(target_info.st_mode):
                        os.rmdir(target)
                    else:
                        os.remove(target)
                elif stat.S_ISDIR(target_info.st_mode):
                    shutil.rmtree(target)
                else:
                    os.remove(target)
            os.replace(staging, target)
            return target
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise


def zip_is_archive(path):
    return os.path.isfile(path) and path.lower().endswith(('.zip', '.tar.gz', '.tgz'))


__all__ = ['Loader', 'load_entry', 'unload', 'discover_builtin', 'read_manifest',
           'find_manifest_dir', 'MANIFEST_NAME', 'MAX_PACKAGE_BYTES', 'MAX_PACKAGE_FILES']
