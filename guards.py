"""UI-free security guards: защита критичных файлов и SSRF-гейт для исходящих URL.

Модуль не тянет nicegui/fastapi — импортируется и панелью (main.py), и тестами.
"""
import ipaddress
import os
import socket
from urllib.parse import urlparse

CRIT_FILES = {'main.py', 'patch_engine.py', 'agent_engine.py', 'guards.py', 'settings.json', 'config.json', 'agents.json', 'pipelines.json', 'launcher.bat', 'sync.bat', 'package.json', 'package-lock.json', 'vite.config.js', 'tsconfig.json', 'index.html', 'README.md', '.project-important.json', '.project-history.json', 'patch_manifest.json'}
CRIT_DIRS = ('src/', 'patch/', 'docs/', 'tests/', 'core/', 'plugins/', 'data/plugins/')

CRIT_FILES_LOWER = {f.lower() for f in CRIT_FILES}
CRIT_DIRS_LOWER = tuple(d.lower() for d in CRIT_DIRS)

MD_EXT = '.md'


def is_critical_rel(rel):
    """True — rel-путь указывает на критичный файл/каталог проекта.

    Сравнение case-insensitive: файловая система Windows не различает регистр,
    поэтому 'MAIN.PY' и 'settings.JSON' — те же критичные цели.
    """
    if not rel:
        return False
    norm = str(rel).replace('\\', '/')
    if os.path.basename(norm).lower() in CRIT_FILES_LOWER:
        return True
    return norm.lower().startswith(CRIT_DIRS_LOWER)


def is_doc_rel(name):
    """True — путь разрешён для маршрута /api/md (чтение/запись Markdown).

    Разрешены только *.md в корне проекта и в docs/. Исходники, конфиги и
    прочие файлы через MD-маршрут недоступны.
    """
    if not name:
        return False
    norm = str(name).replace('\\', '/')
    parts = norm.split('/')
    if any(q == '' for q in parts):
        return False
    if any(q in ('.', '..') for q in parts):
        return False
    if not parts[-1].lower().endswith(MD_EXT):
        return False
    return len(parts) == 1 or parts[0] == 'docs'


def validate_url(url, allowed_hosts=None):
    """SSRF-gate для исходящих HTTP-запросов. Возвращает (ok, reason).

    Правила:
    - схема только http/https, хост обязателен, без user:pass@;
    - ссылка-литерал или резолв: запрещены link-local/metadata
      (169.254.0.0/16, fe80::/10 — в т.ч. 169.254.169.254), multicast,
      reserved и unspecified-адреса;
    - если задан allowed_hosts — хост обязан входить в allow-лист, а
      резолвиться во внешние (публичные) адреса: секретные запросы не
      должны уходить на loopback/внутренние сети.
    """
    raw = str(url or '').strip()
    try:
        parts = urlparse(raw)
    except ValueError:
        return False, 'URL не распознан'
    if parts.scheme not in ('http', 'https'):
        return False, f'схема {parts.scheme!r} не разрешена — только http/https'
    host = (parts.hostname or '').lower()
    if not host:
        return False, 'URL без хоста'
    if parts.username is not None or parts.password is not None:
        return False, 'URL с логином/паролем запрещён'
    try:
        port = parts.port
        if port is not None and not (0 < port < 65536):
            return False, f'некорректный порт {parts.port}'
    except ValueError:
        return False, 'некорректный порт'
    if allowed_hosts is not None and host not in {h.lower() for h in allowed_hosts}:
        return False, f'хост {host} не входит в allow-лист провайдера'

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    addresses = []
    if literal is not None:
        addresses.append((literal, None))
    else:
        try:
            addr_infos = socket.getaddrinfo(host, None)
        except OSError:
            return False, f'хост {host} не резолвится'
        for info in addr_infos:
            try:
                ip = ipaddress.ip_address(str(info[4][0]).split('%')[0])
            except ValueError:
                return False, f'не удалось разобрать адрес {info[4][0]}'
            addresses.append((ip, None))

    for ip, _ in addresses:
        if ip.is_link_local:
            return False, f'{ip} — link-local/metadata адрес запрещён'
        if ip.is_multicast or ip.is_unspecified:
            return False, f'{ip} — зарезервированный адрес запрещён'
        if ip.is_loopback or ip.is_private:
            if allowed_hosts is not None:
                return False, f'{ip} — внутренний адрес запрещён для внешнего провайдера'
            continue
        if ip.is_reserved:
            return False, f'{ip} — зарезервированный адрес запрещён'
    return True, ''
