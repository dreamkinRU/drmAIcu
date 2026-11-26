# Plugin System drmAIcu v1.1

Архитектура утверждена: Dynamic Plugin System, Repos Plugin с интеграцией через локальный Git CLI, авторизация средствами настроенного Git (Credential Manager / SSH), установка из Built-in Catalog + Manual, Controlled Automation. Отдельная GitHub App-интеграция не используется. Контракт API — [PLUGIN_API_CONTRACT.md](PLUGIN_API_CONTRACT.md).

## Состав

| Компонент | Модуль | Ответственность |
|---|---|---|
| Plugin Registry | `core/plugins/registry.py` | Реестр установленных и доступных плагинов |
| Plugin Loader | `core/plugins/loader.py` | Обнаружение, валидация, импорт модулей |
| Lifecycle Manager | `core/plugins/lifecycle.py` | Переходы состояний |
| Permission Manager | `core/plugins/permissions.py` | Уровни READ/WRITE/CRITICAL, выдача/отзыв |
| Settings Manager | `core/plugins/settings.py` | Настройки по settings_schema |
| Secret Manager | `core/plugins/secrets.py` | Секреты per-plugin, 0600, вне экспортов |
| Plugin API | `core/plugins/api.py` | Контекст `ctx` плагина |
| Capability Gateway | `core/plugins/api.py` | Разрешения + политики подтверждений |
| Event System | `core/plugins/events.py` | Публикация/подписка событий |
| Activity Journal | `core/plugins/events.py` | JSONL-журнал, redact секретов |
| HTTP API | `core/plugins/routes.py` | REST-маршруты `/api/plugins/*` |

Оркестрация — `core/plugins/manager.py` (`PluginManager`). Данные — `data/plugins/` (реестр, права, настройки, состояние, секреты, журнал — в раздельных файлах, не смешиваются).

## Граница доверия и исполнение Python-плагинов

Python-плагины имеют два режима исполнения:

- **Built-in (trusted_in_process)** — код из доверенного каталога выполняется в процессе drmAIcu. Это привилегированный код проекта.
- **Manual (isolated_process)** — вручную установленные плагины запускаются в отдельном Python-процессе через framed JSON-RPC. В процесс не передаётся объект PluginManager; доступ к настройкам, секретам, журналу, событиям и capabilities идёт через узкий RPC-контекст.

Важно: isolated_process — это граница отказов и памяти процесса, **но не полноценная OS-песочница**. Дочерний процесс всё ещё работает под той же учётной записью ОС и потенциально может обращаться к доступным ей файлам, сети и запускать subprocess. Поэтому этот режим не следует считать защитой от целенаправленного вредоносного кода. Полноценная OS-изоляция (Windows AppContainer/restricted token и Linux namespaces/seccomp) остаётся отдельным этапом.

Дополнительные гарантии установки ручных плагинов:
- ZIP/TAR распаковываются вручную; traversal, symlink/hardlink, device/FIFO и reparse points запрещены;
- лимиты: 50 MiB распакованных данных, 5000 элементов, manifest не более 1 MiB;
- локальный каталог плагина проверяется на symlink/reparse points и превышение лимитов до копирования и после staging-копии;
- READ/WRITE/CRITICAL policy и одноразовые confirmation tokens продолжают применяться ядром к RPC-вызовам.

## Интеграция с ядром

- `main.py` монтирует `plugin_router` две строки (`include_router`) — production-логика ядра не изменяется.
- Repos Plugin никогда не применяет AI-патчи сам: изменения исходников только через PATCHMASTER (`patch_engine.apply_patch`), Repos Plugin анализирует `git diff` и выполняет push только после подтверждения (этап 5+).
- Git CLI вызывается только через `plugins/repos/git_service.py`: allowlist команд, аргументы списком (без shell-строки), таймауты, проверка путей. Перед WRITE-подтверждением Sync capability `repos.sync_preview` (READ/AUTO) показывает diff staged + unstaged + untracked файлов, список файлов и snapshot. Для бинарных/слишком больших файлов и обрезанного diff UI показывает предупреждение и требует явного подтверждения неполного preview. Preview не меняет index/worktree. Затем Sync получает snapshot изменённых файлов, сверяет его перед `git add -A` и повторно после staging; при расхождении commit/push не выполняются. Операции одного Git common-dir сериализуются межпоточной и межпроцессной блокировкой; snapshot учитывает рабочее содержимое, поэтому штатное обновление index командой `git add -A` не считается подменой подтверждённых файлов. `read_file` отклоняет symlink и Windows reparse points на всех компонентах пути.

## Статусы и хранение

См. §8–9 контракта. Реестр persistируется в `data/plugins/registry.json` и переживает рестарт (`restart.flag` → launcher.bat).

## Что не входит в v1.0

Удалённый Marketplace, автопубликация, автообновления, произвольная загрузка React-компонентов (frontend отображает только заранее определённые представления), песочница сторонних Python-плагинов, автономный AI-режим без подтверждений.
