"""Атомарная запись JSON-файлов состояния с защитой от временных блокировок Windows.

Проблема (реальный кейс, скриншот пользователя):
    [WinError 5] Отказано в доступе:
    '...\\data\\plugins\\confirmations.json.tmp' -> '...\\data\\plugins\\confirmations.json'

На Windows os.replace()/os.rename() между каталогами одного диска атомарны, НО
выбрасывают PermissionError (WinError 5), если целевой файл в этот момент открыт
другим процессом. Парадокс в том, что чаще всего «виноват» не человек, а
файловые сканеры: антивирус, индексатор поиска и облачная синхронизация (папка
пользователя лежала в G:\\Mega\\ — облачный клиент Mega держит файлы открытыми
первую секунду после появления .tmp).

Почему ошибка была только при синхронизации С изменениями: без изменений
add/commit пропускаются, и все записи состояния (confirmations.json и т.п.)
успевают до того, как сканер находит новые .tmp-файлы. С коммитом git + антивирус
начинают читать сотни файлов, облако синхронизирует изменённые — и окно, в
которое os.replace попадает в чужой file-lock, резко растёт.

Решение: такие блокировки кратковременные, поэтому делаем несколько повторных
попыток os.replace с нарастающей паузой (0.05 c → 0.5 c) и только после
исчерпания попыток отдаём пользователю честную ошибку с путём исправления.
"""
import json
import os
import time

# 20 попыток суммарно ~16 с — облачный клиент (Mega/OneDrive) при синхронизации целого
# апдейта держит сотни файлов открытыми заметно дольше, чем одиночный скан антивируса.
RETRY_ATTEMPTS = 20
RETRY_BASE_DELAY = 0.05
RETRY_MAX_DELAY = 1.0

FIX_PATH = (
    'Путь исправления: закройте программы, которые могли удерживать файл '
    '(антивирус, облачная синхронизация Mega/OneDrive/Dropbox, редактор); '
    'запустите панель от имени пользователя-владельца папки проекта и повторите действие. '
    'Если путь лежит на сетевом/облачном диске — временно приостановите его синхронизацию.'
)


def _replace_with_retry(tmp, path):
    last = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as exc:
            last = exc
            time.sleep(min(RETRY_MAX_DELAY, RETRY_BASE_DELAY * (2 ** attempt)))
    raise PermissionError(
        '[WinError 5] Отказано в доступе: файл %r удерживается другой программой — '
        'не удалось перезаписать его после %d повторных попыток. %s'
        % (path, RETRY_ATTEMPTS, FIX_PATH)
    ) from last


def atomic_write(path, text, chmod=None):
    """Записать text в path атомарно (tmp + os.replace) с retry при блокировке."""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    if chmod is not None:
        try:
            os.chmod(tmp, chmod)
        except OSError:
            pass  # chmod 0600 — best effort (на Windows игнорируем честно)
    _replace_with_retry(tmp, path)


def atomic_write_json(path, obj, chmod=None):
    """Записать obj в path как JSON атомарно (tmp + os.replace) с retry."""
    atomic_write(path, json.dumps(obj, indent=2, ensure_ascii=False), chmod=chmod)
