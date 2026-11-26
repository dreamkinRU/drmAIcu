# Plugin API Contract v1.0

Контракт взаимодействия плагинов drmAIcu c ядром (Этап 0, зафиксирован). Версия Plugin API независима от версии drmAIcu и хранится в `core/plugins/models.py` (`PLUGIN_API_VERSION = '1.0'`).

## 1. Структура плагина

```
plugins/<id>/                # встроенный каталог
  plugin.json                # манифест
  plugin.py                  # точка входа (entry_point)
  ...                        # модули плагина
```

Установленные из локального каталога/архива плагины копируются в `data/plugins/installed/<id>/` и работают оттуда.

## 2. Манифест `plugin.json`

Обязательные поля:

| Поле | Тип | Описание |
|---|---|---|
| `id` | string | Уникальный идентификатор, `[a-z][a-z0-9_-]*` |
| `name` | string | Отображаемое название |
| `version` | string | Версия плагина, `X.Y.Z` |
| `description` | string | Описание |
| `api_version` | string | Требуемая версия Plugin API (`1.0`) |
| `entry_point` | string | Имя модуля точки входа (обычно `plugin.py`) |
| `permissions` | string[] | Перечень заявляемых разрешений |

Дополнительные: `author`, `homepage`, `settings_schema`.

Валидация манифеста выполняется ядром в фазе VALIDATE. Повреждённый/некорректный манифест → отказ установки/загрузки со структурной диагностикой.

### settings_schema

```json
{
  "app_id":   { "type": "string", "title": "GitHub App ID", "default": "" },
  "mode":     { "type": "enum", "enum": ["a", "b"], "default": "a" },
  "enabled":  { "type": "boolean", "default": false }
}
```

Поддерживаемые типы: `string`, `number`, `boolean`, `enum`.

## 3. Совместимость

- Major версия `api_version` плагина должна совпадать с major ядра, minor плагина — не превышать minor ядра.
- Несовместимый плагин получает статус `incompatible` и не запускается.
- Необязательная возможность отсутствует — ядро продолжает работать.

## 4. Точка входа `plugin.py`

Ядро импортирует плагин как пакет `_plugin_<id>` (важно: относительные импорты разрешены — `from .client import ...`). Обязателен только `initialize`.

```python
def initialize(ctx):     # обязательный: True/False (False → статус error)
def start():             # после initialize
def stop():              # перед выгрузкой
def health():            # -> dict диагностических сведений
def uninstall():         # перед удалением данных
```

## 5. Plugin API (`ctx`)

`initialize(ctx)` получает класс `core.plugins.api.PluginAPI`:

| Метод | Описание |
|---|---|
| `ctx.log(kind, event, **details)` | Журнал активности. Значения секретов автоматически показываются как `***REDACTED***` |
| `ctx.settings()` | Итоговые настройки (defaults + сохранённые, валидированные) |
| `ctx.set_settings(dict)` | Сохранить настройки (валидация по settings_schema) |
| `ctx.get_secret(key)` | Значение секрета или `None`. Никогда не логируется |
| `ctx.set_secret(key, value)` | Сохранить секрет (файл с правами 0600, вне экспортов) |
| `ctx.remove_secret(key)` / `ctx.delete_secrets()` | Удаление секретов |
| `ctx.publish(event, **payload)` | Событие в Event System |
| `ctx.subscribe(fn)` | Подписка на события ядра и плагинов |
| `ctx.load_state()` / `ctx.save_state(dict)` | Персистентное состояние плагина: `data/plugins/state/<id>/state.json` (§9.1, атомарная запись). Доступно с API 1.0 (ядро 3.12.6) |
| `ctx.register_capability(name, permission, handler, confirmation='auto', description='')` | Регистрация операции Capability Gateway |

Правило: плагин не обращается к внутренним объектам ядра напрямую — только через `ctx`.

## 6. Capability Gateway

Операции объявляются как capabilities. Выполнение (для AI Engine и UI) — только через `POST /api/plugins/{id}/exec`:

1. Плагин должен быть в статусе `running`.
2. Capability должна быть зарегистрирована.
3. `permission` capability должна быть выдана (Permission Manager).
4. Политика `confirmation`:

| Режим | Поведение |
|---|---|
| `auto` | Выполняется немедленно (READ-операции) |
| `confirm` | Создаётся pending-подтверждение; результат возвращается только после явного подтверждения пользователя (Repos: add/commit/pull/push/fetch/checkout/sync/rebase --continue|--abort) |
| `critical` | CRITICAL-подтверждение для наиболее опасных операций |

Минимальная политика задаётся ядром и не может быть ослаблена плагином: READ → `auto`, WRITE → не ниже `confirm`, CRITICAL → только `critical`. Repos Plugin предоставляет `repos.sync_preview` как READ/AUTO capability: она возвращает diff и snapshot без изменения рабочего дерева; само выполнение Sync остаётся WRITE/CONFIRM. Восстановление после конфликта rebase: `repos.rebase_state` (READ/AUTO — активен ли rebase, список конфликтных файлов), `repos.rebase_continue` / `repos.rebase_abort` (WRITE/CONFIRM; continue отклоняется, пока конфликты не разрешены). Последний результат Sync хранится персистентно в state плагина: `repos.last_sync` (READ/AUTO — возвращает результат последней попытки с меткой времени, переживает обновление страницы). Плагин вправе запросить более строгую политику. Подтверждения одноразовые (single-use token), привязаны к plugin ID, capability, permission, policy и точным параметрам операции. TTL — 15 минут; повторное использование отклоняется.
Валидация при `register_capability` (с 3.12.5): имя capability уникально (дубликат отклоняется); permission должен быть объявлен в манифесте плагина (иначе регистрация отклоняется); эффективная политика подтверждения вычисляется на момент каждого вызова как максимум объявленной политики и минимальной политики уровня разрешения (READ→`auto`, WRITE→`confirm`, CRITICAL→`critical`); передача confirmation_token в AUTO-capability отклоняется (`unexpected_confirmation`).

## 7. Разрешения

Формат: `<service>.<resource>.<action>`.

| Действие | Уровень |
|---|---|
| `*.read` | READ |
| `*.write` | WRITE |
| `*.merge`, `*.delete` (и явно перечисленные) | CRITICAL |

- Выдать разрешение, не заявленное в манифесте, невозможно.
- По умолчанию при установке выдаются только READ.
- WRITE/CRITICAL выдаются пользователем явно (`PUT /api/plugins/{id}/permissions`).
- Отзыв разрешения немедленно блокирует последующие вызовы.

## 8. Жизненный цикл и статусы

```
DISCOVER → VALIDATE → REGISTER → AUTHORIZE → LOAD → INITIALIZE → RUNNING
RUNNING → STOP / DISABLE / ERROR / UNINSTALL
```

Статусы: `installed`, `disabled`, `loading`, `running`, `error`, `update_available`, `incompatible`.

- `installed` — зарегистрирован, не запущен;
- `disabled` — отключён пользователем;
- `-loading`/`running`/`error` — фазы запуска и работы;
- `incompatible` — отказ по версии Plugin API.

Ошибка инициализации одного плагина не влияет на остальные и на ядро.

## 9. Секреты

- Секреты хранятся в `data/plugins/secrets/<id>.secrets.json`, права 0600 (best-effort на Windows).
- Секреты никогда не возвращаются REST API, не попадают в журнал, экспорт и исключения.
- Журнал активности пропускает все значения через `redact()` по известным секретам плагина.
- Удаление плагина удаляет его секреты (обрабатываются отдельно от настроек).

## 10. REST-контракт (Этап 1)

| Метод | Endpoint | Назначение |
|---|---|---|
| GET | `/api/plugins` | Список плагинов |
| GET | `/api/plugins/catalog` | Встроенный каталог |
| GET | `/api/plugins/{id}` | Информация о плагине |
| POST | `/api/plugins/install` | Установка (builtin/локальный каталог/архив) |
| POST | `/api/plugins/{id}/enable` | Включение |
| POST | `/api/plugins/{id}/disable` | Отключение |
| DELETE | `/api/plugins/{id}` | Удаление (`?keep_settings=`) |
| GET | `/api/plugins/{id}/permissions` | Просмотр разрешений |
| PUT | `/api/plugins/{id}/permissions` | Изменение разрешений |
| GET | `/api/plugins/{id}/settings` | Настройки |
| PUT | `/api/plugins/{id}/settings` | Сохранение настроек |
| GET | `/api/plugins/{id}/secrets` | Только имена секретов (значения не возвращаются) |
| PUT | `/api/plugins/{id}/secrets` | Запись секретов (write-only, `{"secrets": {key: value}}`) |
| DELETE | `/api/plugins/{id}/secrets/{key}` | Удаление секрета |
| GET | `/api/plugins/{id}/capabilities` | Список операций плагина |
| POST | `/api/plugins/{id}/exec` | Выполнение (политики §6) |
| GET | `/api/plugins/confirmations` | Ожидающие подтверждения |
| POST | `/api/plugins/confirmations/{cid}/approve` | Одобрить |
| POST | `/api/plugins/confirmations/{cid}/reject` | Отклонить |
| GET | `/api/plugins/{id}/health` | Состояние |
| GET | `/api/plugins/activity` | Журнал активности |

Единый формат ответа: `{'success': True, ...}` или `{'success': False, 'error': <текст>, 'code': <машинный код>}` — соответствует существующему стилю API drmAIcu.

Специфичные для конкретного плагина маршруты (например `/api/plugins/repos/*`) реализуются поверх `exec`-механизма на этапах 4–8.

## 10.1. Секреты через REST (Этап 4)

Секреты плагина записываются с frontend только через `PUT /api/plugins/{id}/secrets`. Контракт write-only: GET возвращает **только имена ключей**, значения недоступны через REST в принципе; журнал активности фиксирует только имена (`secret_set`, `secret_deleted`). Формат ключа: `[A-Za-z0-9_.-]{1,64}`; пустые значения отвергаются (HTTP 422).


## 13. ИЗОЛЯЦИЯ ИСПОЛНЕНИЯ PYTHON-ПЛАГИНОВ

- Встроенные плагины считаются доверенным кодом и выполняются внутри процесса drmAIcu.
- Вручную установленные плагины запускаются в отдельном Python worker-процессе. Родительский процесс владеет PluginAPI, проверкой разрешений, токенами подтверждения, настройками, секретами и журналом активности; дочерний процесс получает ограниченный JSON-RPC-контекст.
- Worker использует framed JSON-сообщения с ограничением размера, тайм-аутами запуска и вызовов, а также явным управлением жизненным циклом.
- Эта граница изолирует память Python и многие сбои плагина, но **не обеспечивает OS-level security containment**. Worker работает под той же учётной записью ОС и сохраняет доступ к ресурсам этой учётной записи. Нельзя считать, что файловая система или сеть заблокированы.
- Установка архивов запрещает traversal, symbolic/hard links, специальные файлы, чрезмерный распакованный размер и чрезмерное число элементов. Локальные каталоги проверяются до и после staging-копирования.
- Полноценная OS-песочница должна отдельно реализовать системные ограничения (например, Windows AppContainer/restricted token или Linux namespaces/seccomp) и иметь независимые тесты запрета доступа к файлам и сети.
