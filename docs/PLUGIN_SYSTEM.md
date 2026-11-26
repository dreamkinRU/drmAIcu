# Plugin System drmAIcu v1.0

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

## Граница доверия (важно)

Динамическая загрузка Python-модуля в основном процессе **не является песочницей**. Permission Manager контролирует вызовы через Plugin API, но не гарантирует, что код плагина не обратится к файловой системе/сети напрямую. Поэтому в v1.0:

- устанавливаются только плагины из встроенного каталога или проверенного локального источника;
- входные параметры capability валидируются только по JSON-структуре;
- ядро принудительно задаёт минимальную политику: READ — AUTO, WRITE — CONFIRM, CRITICAL — отдельное подтверждение; плагин может только усилить эту политику;
- токен подтверждения привязан к plugin ID, capability, permission, policy и точным параметрам операции;
- полная процессная изоляция сторонних плагинов — отдельный этап развития (вне v1.0).

## Интеграция с ядром

- `main.py` монтирует `plugin_router` две строки (`include_router`) — production-логика ядра не изменяется.
- Repos Plugin никогда не применяет AI-патчи сам: изменения исходников только через PATCHMASTER (`patch_engine.apply_patch`), Repos Plugin анализирует `git diff` и выполняет push только после подтверждения (этап 5+).
- Git CLI вызывается только через `plugins/repos/git_service.py`: allowlist команд, аргументы списком (без shell-строки), таймауты, проверка путей. Перед WRITE-подтверждением Sync capability `repos.sync_preview` (READ/AUTO) показывает diff staged + unstaged + untracked файлов, список файлов и snapshot. Для бинарных/слишком больших файлов и обрезанного diff UI показывает предупреждение и требует явного подтверждения неполного preview. Preview не меняет index/worktree. Затем Sync получает snapshot изменённых файлов, сверяет его перед `git add -A` и повторно после staging; при расхождении commit/push не выполняются. Операции одного Git common-dir сериализуются межпоточной и межпроцессной блокировкой; snapshot учитывает рабочее содержимое, поэтому штатное обновление index командой `git add -A` не считается подменой подтверждённых файлов. `read_file` отклоняет symlink и Windows reparse points на всех компонентах пути.

## Статусы и хранение

См. §8–9 контракта. Реестр persistируется в `data/plugins/registry.json` и переживает рестарт (`restart.flag` → launcher.bat).

## Что не входит в v1.0

Удалённый Marketplace, автопубликация, автообновления, произвольная загрузка React-компонентов (frontend отображает только заранее определённые представления), песочница сторонних Python-плагинов, автономный AI-режим без подтверждений.
