# drmAIcu — единый инженерный план развития

**Редакция плана:** 1.3 · 27.11.2026 · **Базовая версия продукта:** 3.19.5 Model (кандидат) · **Репозиторий:** dreamkinRU/drmAIcu · **Следующая задача:** приёмка PATCH-03/04/05/06, затем CI-03.

## 0. Обязательная точка входа для каждого агента

Прочитай этот файл целиком ПЕРЕД анализом задачи, изменением кода или предложением архитектуры. Затем прочитай `docs/HANDOFF.md` (правила и ограничения), `docs/ARCHITECTURE.md` (карта системы), последние записи `docs/CHANGELOG.md`, профильный контракт и реальные исходники. ROADMAP — единственный оперативный список приоритетов, а не замена контрактов безопасности. При противоречии не ослабляй защиту: зафиксируй расхождение и проверь решение владельца и реализацию. Не начинай работу с нуля и не повторяй закрытые задачи без новых доказательств.

Перед изменениями сверяй версию, ветку, HEAD, статус рабочего дерева, открытые PR и актуальную редакцию ROADMAP. Если данные расходятся, не перезаписывай чужую работу. Используй стабильные ID задач из этого файла. После каждого рабочего инкремента обновляй статус, доказательства, ограничения и следующий шаг В ЭТОМ ЖЕ файле и в том же наборе изменений. Не создавай конкурирующие планы в других MD. История чата не является источником истины.

### Неприкосновенные правила

- PATCHMASTER — единственный путь применения AI-правок исходников; Repos Plugin не пишет исходники и не вызывает apply_patch. Не обходить через прямую запись GitHub API, shell или MD API.
- READ автоматически; WRITE с подтверждением; CRITICAL с отдельным подтверждением. Единственное ранее согласованное исключение — `repos.sync` (auto), не расширять. Автономного режима нет. Токены подтверждения single-use, TTL 15 мин, привязка к параметрам.
- Repos Git CLI — через `plugins/repos/git_service.py`, allowlist, argv, shell=False и таймауты. Update Manager остаётся отдельным ограниченным механизмом fast-forward, не смешивать с Sync.
- Не выполнять force push, reset --hard, удаление recovery refs или чужих процессов. Не мержить PR самостоятельно; штатная локальная синхронизация владельцем — отдельный согласованный workflow. Не публиковать секреты, локальные журналы или персональные данные.
- Никаких заглушек, фальшивых тестов, выдуманных метрик или безусловного зелёного статуса. Ошибки видимы, сохраняются и содержат путь исправления. Непроверенное явно обозначать.
- Один инкремент — одна связная задача, минимальный diff, проверка регрессий, документация и передача. Не переписывать работающие подсистемы ради эстетики. Изменение политики безопасности, разрушительная миграция, новый внешний сервис — только после решения владельца.

## 1. Базовое состояние и доказательства

| Подсистема | Что имеется | Основание и границы |
|---|---|---|
| Версия | 3.19.3 в main, патч 171 в manifest | Проверено 27.11.2026: main `697bd1d056a98564ce232abb4e2aaf2c7c5a7a5f`; version.py и patch_manifest.json; CI этого SHA описан ниже |
| Обновление | Три этапа, backup ref/bundle, fast-forward, восстановление индекса, journal, история, restart health | Код и UPDATE_MANAGER.md; пользователь показал COMPLETED перехода 3.19.1 → 3.19.2; это не универсальная приёмка всех сценариев |
| Диагностика | Очистка ANSI, переносы, предупреждения npm, русские подписи | updatePresentation.ts и тестовый файл на main; CI frontend прошёл typecheck/build, но не запускает эти 14 assertions |
| PATCHMASTER | Валидация, TX_LOCK, expected_sha, бэкапы, crash recovery, ротация | README, STORAGE_CONTRACT и выборочное чтение patch_engine.py; внешним читателям не обещать атомарность набора файлов |
| Репозитории | Git capabilities, Sync, preview, recovery, refresh_hints | HANDOFF и RepositoriesTab.tsx; не считать любой открытый репозиторий официальным drmAIcu |
| AI | Девять заявленных провайдеров, fast/judge, SSE, council/pipeline | README и список методов agent_engine.py; доступность моделей и качество ответов не проверены |
| Плагины | Gateway, lifecycle, workers, permissions, resource governor | Архитектура и контракты; не OS sandbox, не жёсткая CPU/RAM quota |
| UI/платформа | React 18, TS, Vite, Tailwind 4; Python/FastAPI/NiceGUI; штатный static frontend и supervisor | Документация, дерево файлов; Windows/MEGA — обязательная отдельная приёмка |

Статусы задач: OPEN (готова к работе), AUDIT (сначала собрать доказательства), DOING (указать исполнителя и scope), BLOCKED (причина), REVIEW (патч готов, не принят), DONE (проверено по критериям и указаны доказательства), DEFERRED (отложено решением). Приоритеты: P0 — риск потери данных/секретов или обхода полномочий; P1 — корректность и надёжность; P2 — поддерживаемость/UX; P3 — улучшение после стабилизации. Приоритет аудита не означает, что уязвимость уже обнаружена.

## 2. Очередь ближайших релизов (предложение, не обещание сроков)

| Порядок | ID | Задача | Приоритет | Статус |
|---|---|---|---|---|
| 0 | CI-00 | Устранить подтверждённое падение Ubuntu на CRLF CHANGELOG | P1 | DONE — PR 68, проверенный head d3b51df |
| 0a | UPD-04 | Входящая синхронизация одним нажатием | P1 | REVIEW |
| 0b | GIT-UX-01 | Прокрутка и подсветка после Sync preview | P2 | REVIEW |
| 0c | DOC-01 | Каталог MD: ROADMAP/HANDOFF | P2 | REVIEW |
| 0d | PATCH-03 | Архивация и честная диагностика применения | P1 | REVIEW |
| 0e | PATCH-04 | Постоянный отчёт PATCHMASTER | P1 | REVIEW |
| 0f | PATCH-05 | JSON-патчи в TXT | P2 | REVIEW |
| 0g | PATCH-06 | Защита от повторного предложения применённого патча | P1 | REVIEW |
| 0h | CI-03 | Adaptive CI, полный gate перед merge | P2 | OPEN |
| 0i | UPD-03 | Объединённая история обновлений и патчей | P2 | OPEN |
| 1 | UPD-01 | Разделить актуальные версии и историческую операцию обновления | P1 | OPEN |
| 2 | CI-01 | Подключить реальные frontend regression tests к CI | P1 | OPEN |
| 3 | UPD-02 | Проверить восстановление и диагностику апдейтера | P1 | AUDIT |
| 4 | STORE-01 | Инвентаризация legacy persistence и миграции по одному владельцу | P1 | AUDIT |
| 5 | PATCH-01 | Проверка итогового staged-кода и конкурентных записей PATCHMASTER | P1 | AUDIT |
| 6 | SEC-01 | Сквозной аудит локальных API, секретов и границ прав | P1 | AUDIT |
| 7 | PLUG-01 | Приёмка Plugin System v1.0 по контракту (бывший этап 9) | P1 | AUDIT |
| 8 | AI-01 | Структурированные действия AI через Gateway (бывший этап 8) | P1 | OPEN после PLUG-01 |
| 9 | AI-02 | Унификация транспорта LLM, SSE, отмены и метрик | P2 | AUDIT |
| 10 | UI-01 | Типизированное состояние и декомпозиция больших экранов | P2 | AUDIT |
| 11 | OPS-01 | Windows/MEGA, self-check и воспроизводимый запуск | P1 | AUDIT |
| 12 | DEP-01 | Управление зависимостями, включая Recharts 3 | P2 | AUDIT |

Сначала восстановить зелёный CI (CI-00; инфраструктурный инкремент, номер продукта по согласованным правилам). Первый целевой продуктовый релиз — 3.19.4 для UPD-01 при условии, что CI-00 не потребует продуктового bump (CI-01 допустим отдельно или как проверка этого же изменения, если scope согласован). Дальнейшие номера назначать по фактическому объёму и состоянию main. 3.20.x — возможный следующий минор для Gateway/AI после приёмки защиты. 4.0 — только при обоснованной несовместимости контрактов, не маркетинговый номер.

## 3. Подробный backlog: обновление и Git

### UPD-01 — текущая версия GitHub отдельно от истории (P1, OPEN)

**Подтверждённый дефект UX:** `core/updater/manager.py:state()` возвращает актуальные running_version и (при наличии remote_head) installed_version, но target_version берёт из журнала предыдущей операции. `check()` записывает target_version после fetch. `UpdateWizardTab.tsx` отображает эти поля вместе, поэтому после Sync показано 3.19.3 / 3.19.3 / 3.19.2 при COMPLETED. В `src/App.tsx` мастер монтируется при выборе вкладки; `RepositoriesTab.tsx` имеет отдельный syncResult. Не считать текущую версию GitHub известной без факта свежего fetch.

**Решение:** отдельный read-model для запущенной версии, Git HEAD, локально изменённого version.py (если нужно), последней подтверждённой remote версии и времени её проверки; исторический target_version остаётся неизменным. При успешном Sync именно официального репозитория инвалидировать remote snapshot и инициировать безопасную повторную проверку либо явно предложить её; не перезаписывать активный план и не делать fetch для чужих репозиториев. Протокол refresh должен выдерживать offline, ошибки fetch, гонки, ahead/behind/diverged, одинаковую версию при разных SHA и отсутствие upstream. Не определять актуальность только semver.

**Приёмка:** старт без журнала; старый COMPLETED; локальный патч без commit; commit без push; успешный push; неуспешный push; чужой репозиторий; offline; новый remote commit; равные версии при разных HEAD; активный RESTART_REQUIRED; неизменность исторического отчёта. UI показывает источник и свежесть данных, а не ложное «доступно». Проверить 3.19.3 → 3.19.4 на Windows и отсутствие повторных fetch в бесконечном polling.

### UPD-02 — завершение и восстановление (P1, AUDIT)

Проверить `core/updater/manager.py`, `api/routes_updates.py`, `launcher_supervisor.py`, `frontend_server.py`: журнал, lock, восстановление после каждого прерывания, restart identity, фактическую версию статического frontend, повтор только неуспешных environment steps, сохранение диагностических ошибок после refresh, отсутствие зависаний при read-model. В 3.19.3 screenshot ещё показывал английский COMPLETED; код main уже использует updateStateLabel — проверить свежесть static snapshot, не считать исправление сломанным без воспроизведения. Тестировать повреждённый journal, оставшийся tmp, PID reuse, неуспешный запуск, Windows EPERM/EBUSY, старый watchdog. Не придумывать отсутствующие timestamps и не обещать rollback side effects npm/pip. Приёмка: сохранность исходных данных, корректное состояние recovery, явное сообщение причины, новый API и frontend подтверждены независимо.

### GIT-01 — достоверность Sync и планов (P1, AUDIT)

Проверить `plugins/repos/repos_service.py`, `git_service.py`, `RepositoriesTab.tsx`: race между preview и staging, внешние writers, advisory locks, branch/upstream identity, результат после push, refresh_hints, redaction, rebase recovery. Уже реализованные защиты не дублировать. Сценарии с реальными bare remote: отказ push, diverged, конфликт, untracked/binary, смена файла между шагами, чужой repo. Приёмка: ложный success невозможен, неподтверждённые изменения не уходят, ошибки не исчезают, не используется force. Исключение auto-sync не расширять.

## 4. PATCHMASTER и хранилища

### PATCH-01 — проверка итогового состояния (P1, AUDIT)

В просмотренном `patch_engine.py` check_ts_full() вызывается до записи целевых файлов; необходимо проверить, видит ли полная проверка именно кандидатный multi-file snapshot, а не только старое дерево. Синтаксическая проверка каждого файла не заменяет проверку межфайловых типов. Исследовать изолированный staging/overlay с ограниченным ресурсом; не применять непроверенный патч в основное дерево. Тест: исходный проект проходит tsc, патч синтаксически корректен, но ломает типы между файлами — preview/apply обязан отказать до изменения исходников; совместимое multi-file изменение проходит. Отдельно проверить rollback, Windows CRLF и UNAVAILABLE.

### PATCH-02 — stale preview, транзакции и UX (P1, AUDIT)

Проверить передачу expected_sha из UI, snapshot ID, гонки между preview/apply и другими процессами, область TX_LOCK, восстановление journal/backup и ротацию с учётом pending recovery. Прочитать STORAGE_CONTRACT: внешние readers не получают атомарную видимость нескольких файлов. Не менять формат манифеста без миграции. Приёмка: fault injection на каждом durable boundary, отказ при stale, tampered, неизвестной схеме, повторном ID; восстановление не теряет оригинал; отчёт различает preview, validation, applied, recovered.

### STORE-01 — долговечность данных (P1, AUDIT)

Инвентаризировать `patch_manifest.json`, journal, `data/plugins/registry.json`, permissions, confirmations, settings/state/secrets/activity, provider config, agents/pipelines, project history и updater journal. В STORAGE_CONTRACT задокументированы legacy-долги; проверить фактический статус каждого до миграции. Для каждого записать владельца, схему, атомарность, fsync, ошибки, retention, конкурентный доступ, backup и секретность. Мигрировать по одному хранилищу: legacy reader → snapshot → schema validation → atomic replace → recovery. Unknown schema — fail closed; corrupted/unavailable не равны empty. Проверки: прерывания, replace fail, unknown schema, параллельная запись, restart, деградация и видимая ошибка. Не внедрять общую БД без измеренной необходимости и плана миграции.

### FILE-01 — безопасность управления файлами (P1, AUDIT)

`api/routes_project.py`, `guards.py`, `ProjectTab.tsx`: проверить классификацию мусора, исключение .git/data/backups/recovery, symlink/reparse, stale preview, bulk archive, restore при конфликте, integrity и историю действий. Найденные в дереве docs/111.docx и docs/~$111.docx — кандидаты на проверку назначения, не удалять автоматически. Приёмка: никакая рекомендация удаления не является автоматическим удалением; критические данные защищены, архив обратим, stale файлы не затронуты, причины и отчёт доступны.

## 5. Безопасность и плагины

### SEC-01 — карта границ доверия (P1, AUDIT)

Составить матрицу всех mutating API в `api/routes_*.py`, `core/plugins/routes.py`, origin/host/client guard, путей, SSRF, provider credentials и raw diagnostic output. Loopback/CORS — не аутентификация против локального процесса. Проверить cross-site browser запросы, DNS/rebind/redirect поведение, allowlist внешних хостов, secret redaction перед записью/выдачей, защищённость Markdown endpoints, prompt injection в документах и выводе инструментов. Не объявлять уязвимость без воспроизводимого теста. Локальные провайдеры сохраняют штатный доступ. Приёмка: negative tests на каждый изменённый boundary; секреты не видны в тестовых логах, API, экспорте и Git.

### PLUG-01 — приёмка Plugin System v1.0 (P1, AUDIT)

Проверить `docs/PLUGIN_API_CONTRACT.md` и `docs/PLUGIN_SYSTEM.md` пункт за пунктом: registry, loader, permissions, confirmations, state, secrets, lifecycle, event delivery, Resource Governor, worker timeout, crash и cleanup. Составить матрицу требование → реализация → тест → gap → ID. Worker process не считать OS sandbox; quotas не считать CPU/RAM isolation. Проверить capability names, params hash, expiry/replay, минимальные permissions, отказ при повреждении состояния, ограниченные очереди. Приёмка: все обязательные требования подтверждены или явно отложены владельцем; нет расширения auto WRITE; тесты отказов и Windows cleanup.

### PLUG-02 — диагностика и расширяемость (P2, AUDIT)

Self-check persistence при старте, видимое состояние деградации, понятные версии API и health, структурированные коды ошибок, проверка совместимости плагинов перед активацией. Не подключать marketplace, произвольный frontend или внешние плагины автоматически. Приёмка: invalid manifest, version mismatch, worker crash, недоступное хранилище дают конкретный путь восстановления и не ломают работающие плагины.

## 6. AI Engine и агентная работа

### AI-01 — структурированные действия через Capability Gateway (P1, OPEN после PLUG-01)

Использовать существующий Gateway, а не второй параллельный исполнитель. Модель предлагает типизированный action (capability ID, schema-validated params, объяснение и correlation ID), ядро проверяет доверие/права, UI показывает реальный scope и результат. READ auto; WRITE/CRITICAL по существующему контракту, sync-исключение не превращать в право модели на произвольный push. AI-правки только PATCHMASTER. Tool output и repo docs — недоверенные данные, не источник повышения полномочий. Никаких arbitrary shell, auto retry side-effect или автономного выполнения цепочки без нужного подтверждения.

Приёмка: mock LLM + реальный Gateway, неизвестная capability, malformed params, denied, replay, expired confirmation, изменение params, injection, cancel, timeout, частичный сбой, retry без дублирования, корреляция журналов, пользовательский контроль. Начать с одной READ capability и только затем отдельно согласовывать WRITE-сценарии. Изменение security policy не входит в этот этап.

### AI-02 — провайдеры и потоковый протокол (P2, AUDIT)

`agent_engine.py`, `api/routes_agents.py`, `api/routes_providers.py`, `src/hooks/useConsole.ts`, `ProvidersTab.tsx`: составить матрицу девяти провайдеров, синхронные и SSE-пути, ошибки авторизации/лимитов, streaming cancellation, timeout, fallback, retries, model capabilities, context limits. Унифицировать envelope событий и адаптеры постепенно. Фактические токены, оценки и TTFT маркировать отдельно; отмена UI не гарантирует остановку вычисления у провайдера. Проверки через fake servers: split UTF-8/SSE chunks, malformed event, disconnect, slow stream, 429, 401, timeout, cancel, concurrent calls, secrets redacted. Не отправлять локальные данные облачному провайдеру без явного выбора/политики.

### AI-03 — council, judge и pipeline (P2, AUDIT)

Проверить выбор кандидатов, критерии судьи, provenance ответа, сбой части агентов, step dependencies, лимиты контекста и стоимости, сохранение состояния задач. Разделить «модель выбрала» и «код проверен тестами». Приёмка: детерминированные fixtures, частичные сбои не маскируются, повтор не повторяет WRITE, пользователь видит источник и статус каждого шага.

### AI-04 — контекст проекта и память агентов (P2, OPEN после AI-01)

ROADMAP + HANDOFF + профильные документы — явный bootstrap-контекст агента; добавить ограниченный по размеру и permissions read-only механизм получения актуального плана, HEAD и выбранной задачи. Не загружать весь repo, credentials, raw logs или произвольные файлы в cloud model. Фиксировать использованные пути/ревизии и различать policy и недоверенный текст. Приёмка: новый агент на тестовом fixture определяет следующую задачу без истории чата, соблюдает границы доступа и не воспринимает текст README как разрешение на WRITE. До реализации этого этапа чтение ROADMAP остаётся обязательной инструкцией, а не автоматическим runtime enforcement.

## 7. Frontend, UX и наблюдаемость

### UI-01 — типизация и декомпозиция (P2, AUDIT)

Крупные файлы по дереву main: RepositoriesTab.tsx ~59 KB, AgentsTab.tsx ~35 KB, ProvidersTab.tsx ~30 KB, UpdateWizardTab.tsx ~28 KB, App.tsx ~20 KB; `src/services/api.ts` ~27 KB. Это индикатор сложности, не самостоятельный баг. В UpdateWizardTab присутствуют any и строковые состояния. Выделять typed API contracts, discriminated unions, hooks и небольшие presentation компоненты только вместе с regression tests. Измерить render/polling и network before/after. Приёмка: тот же UX, ошибки сохраняются, нет jitter, stale response не затирает новую, typecheck/build/E2E проходят.

### UI-02 — единый язык диагностики и доступность (P2, AUDIT)

Согласовать статусные цвета, русские подписи при сохранении машинных кодов, keyboard navigation, focus, readable logs, длинные пути, responsive layout, loading/empty/degraded states, confirmation dialogs. Проверить все вкладки: Провайдеры, Файлы, Патчи, Код, Задачи, Плагины, Репозитории, Обновление, MD, а также console/agents/models где доступны. Не скрывать warning/error в целях визуальной чистоты. Приёмка: проверяемая матрица состояний и сценарии клавиатуры; frontend snapshot действительно обновлён.

### OBS-01 — структурированные события и метрики (P2, AUDIT)

Разделить ошибки приложения, provider failures, Git, patch, update и plugin activity. Correlation IDs, уровни, bounded retention, redaction, export без raw secrets, состояние degraded. RAM/VRAM измерять с учётом платформы, unsupported ≠ 0. Не вводить внешний telemetry collector без решения владельца. Приёмка: отказ прослеживается от UI до события, журнал не растёт бесконечно, экспорт безопасен, метрики не выдумываются.

## 8. CI, тестирование и эксплуатация

### CI-00 — восстановить зелёный baseline (P1, OPEN, первая задача)

**Подтверждено GitHub Actions:** [run 46043319757](https://github.com/dreamkinRU/drmAIcu/actions/runs/46043319757) для main `697bd1d056a98564ce232abb4e2aaf2c5a7a5f`: frontend typecheck/build — SUCCESS; Windows pytest — 358 passed, 1 skipped; Ubuntu pytest — 357 passed, 1 skipped, 1 failed. Единственный упавший тест: `tests/test_docs_hygiene.py::test_changelog_is_crlf`; checkout CHANGELOG содержит LF, а контракт требует CRLF. В `.gitattributes` только `*.bat text eol=crlf` и `*.cmd text eol=crlf`; правило для CHANGELOG отсутствует. Причина расхождения checkout должна быть проверена на чистом clone, а не замаскирована пропуском теста.

**Решение-кандидат:** явное правило `docs/CHANGELOG.md text eol=crlf` (LF в Git object, CRLF в checkout на Windows/Linux), проверить совместимость с PATCHMASTER и существующим Git index. Не менять весь CHANGELOG ради переноса строк и не отключать assert. Приёмка: чистый checkout на обеих ОС сохраняет требуемый CRLF, тест проходит, история содержательно не изменена, повторная запись PATCHMASTER сохраняет CRLF, вся матрица CI зелёная на новом SHA. Если нужен renormalize, показать scope и diff до commit. До подтверждения CI не объявлять базовую версию полностью принятой.

### CI-01 — реальные frontend-тесты в CI (P1, OPEN)

**Подтверждено:** `.github/workflows/ci.yml` запускает pytest на Ubuntu/Windows и npm typecheck/build на Ubuntu, но не запускает `tests/update_presentation.test.mjs`. Тест импортирует TS напрямую; CI использует Node 20, поэтому выбрать совместимый способ запуска (например, компиляция fixture в изолированный temp или согласованный runner), а не просто добавить неподдерживаемую команду. Зафиксировать npm script, добавить CI step с реальным ненулевым exit на ошибке, проверить негативный контроль. Приёмка: существующие 14 assertions выполняются автоматически и падение одного ломает CI; typecheck/build остаются; результаты конкретного SHA доступны. Не объявлять CI зелёным без проверки.

### CI-02 — интеграционные и e2e сценарии (P1, AUDIT)

Составить карту покрытия: patch transactions, Git Sync, updater, plugin gateway, provider SSE, project archive, MD. Использовать реальные временные Git repos и fake LLM, не пользовательский checkout. Добавлять UI smoke tests (включая 3 версии, история, restart, warnings) и проверку штатного supervisor/static server. Windows и Linux, offline и отказные сценарии. Никаких реальных API-ключей и сетевых расходов в CI. Приёмка: воспроизводимые fixtures, отсутствие flaky retry masking, лог тестов и ссылка на конкретный run.

### OPS-01 — Windows, MEGA и запуск (P1, AUDIT)

Проверить supervisor ownership, ports, stale restart.flag, dist snapshot, self-check Node/Python/Git, доступность persistence и lock diagnostics. MEGA/антивирус могут удерживать файлы; не убивать чужие процессы. Рассмотреть отделение runtime data/cache от synced checkout с явной миграцией и обратимостью, но не переносить данные автоматически. Приёмка: Windows локально и с MEGA, initial install, restart, failed build, занятый порт, повреждённый journal, отсутствие node_modules; понятные recovery instructions.

### DEP-01 — зависимости и поставка (P2, AUDIT)

Recharts 2.15.4 предупреждал о deprecation на пользовательском скриншоте; это warning, не failure. Провести inventory импортов и миграцию на 3.x отдельным релизом с визуальными и typecheck тестами; не обновлять React/Vite/Tailwind массово без необходимости. Проверить pinning Python deps (requirements.txt использует нижние границы), lockfile consistency, reproducibility, security advisories и лицензии. Не выполнять blind npm audit fix --force. Приёмка: чистая установка, lock согласован, known vulnerabilities triaged с доказательствами, build и визуальные регрессии проверены.

### DOC-01 — гигиена документации и преемственность (P2, OPEN)

HANDOFF содержит исторические дубли и устаревшие версии; ARCHITECTURE ещё описывает Vite dev/watchdog, хотя UPDATE_MANAGER документирует static supervisor; формулировки atomic multi-file и Sync confirm противоречат уточнениям STORAGE_CONTRACT/HANDOFF. Сверить код, оставить историю в CHANGELOG, исправить активные инструкции без удаления значимых решений. Проверить ссылки README, актуальность диапазона патчей и числа тестов, Markdown renderer, CRLF CHANGELOG, отсутствие лишних временных файлов. Добавить проверку существования ROADMAP и входных ссылок; включить ROADMAP и HANDOFF в каталог MD (`src/utils/constants.ts:mdFiles`) отдельным проверенным UI-инкрементом, поскольку текущий список статический и не включает эти документы. Приёмка: новый агент по README → ROADMAP → HANDOFF получает непротиворечивую инструкцию; история не выдаётся за состояние main.

## 9. Матрица архитектурных решений и отложенных работ

| ID | Решение | Статус |
|---|---|---|
| ADR-01 | PATCHMASTER — единственный механизм AI source edits | Зафиксировано ранее; не менять |
| ADR-02 | Sync auto — исключение только repos.sync; остальные WRITE confirm | Решение владельца 26.11.2026 из HANDOFF |
| ADR-03 | Update Manager отделён от Sync, только official fast-forward | Действующий контракт |
| ADR-04 | Документы в docs/, корень только README | Действующее правило; не добавлять root AGENTS.md без отдельного согласования |
| ADR-05 | ROADMAP — единый оперативный план; HANDOFF — правила/история передачи | Предложено текущим планом, принять применением патча |
| ADR-06 | GitHub App / PR-Issues manager (бывший этап 6) | DEFERRED / ранее отклонено владельцем; не предлагать заново без его инициативы |
| ADR-07 | Marketplace, автономный WRITE, удалённая публикация плагинов | Вне v1.0; требуется отдельное решение |
| ADR-08 | Большой rewrite, переход на БД, контейнеризация, удалённый доступ | Не утверждены; сначала доказать необходимость и оценить риски |

## 10. Definition of Done и передача задач

- Перед стартом: ID, статус, конкретная проблема, доказательство, scope, зависимости, риски, ветка/HEAD, критерии приёмки. Не брать одновременно одну задачу двумя агентами без согласования.
- Изменения: создать PATCHMASTER JSON с уникальным patch_id, однозначными операциями и expected_sha там, где проверены реальные байты checkout; preview и test-apply, применение только штатным механизмом. Проверить diff, исключить secrets и unrelated changes. Для документации не смешивать CRLF/LF.
- Проверки по области: `python -m pytest tests -q`, `npm run typecheck`, `npm run build`, frontend regression suite (после CI-01), профильные integration/e2e и Windows при необходимости. Записать точную команду, результат/exit, среду, SHA. Незапущенное помечать NOT RUN; нельзя подменять прогон чтением кода.
- Релиз: version.py, package.json и package-lock.json синхронно; README, USER_GUIDE, ARCHITECTURE, HANDOFF, CHANGELOG и профильные документы обновлены по факту. Документальная правка без продуктового кода может не повышать версию, если это явно указано. Диапазоны PR/патчей только по факту. CI относится к конкретному SHA.
- Передача: в ROADMAP обновить статус и запись ниже; приложить патч/PR, список изменённых файлов, риски, откат, результаты и следующий ID. GitHub main не менять напрямую агентом; PR или штатная локальная Sync владельцем. DONE только при выполненной приёмке, а не при создании патча.

### Шаблон записи передачи (копировать для каждой задачи)

```text
Дата / исполнитель:
ID / статус:
Базовая версия / ветка / SHA:
Проблема и доказательство:
Изменённые файлы / patch_id / PR:
Проверки (команда, exit, среда, SHA):
Не проверено / ограничения:
Решения и причины:
Откат / восстановление:
Следующая задача и зависимость:
```

### Журнал передачи

| Дата | ID | Статус | Итог / следующий шаг |
|---|---|---|---|
| 27.11.2026 | BASE-3193 | REVIEW | 3.19.3 и patch 171 найдены в main; пользователь подтвердил restart 3.19.2; CI 697bd1d: Windows и frontend PASS, Ubuntu FAIL (CRLF); следующий CI-00; полная пользовательская приёмка 3.19.3 не подтверждена |
| 27.11.2026 | DOC-BOOT | REVIEW | План 1.0 и входные указатели подготовлены для PATCHMASTER 172; применение владельцем и появление в main ещё не подтверждены |

## 11. Следующая команда новому агенту

Инкремент 3.19.5: PATCH-03/04/05/06 — REVIEW. База 527804b, PR 69 merged, три CI PASS; владелец подтвердил рестарт 3.19.4, UI one-click ещё требует отдельной проверки. Отчёт PATCHMASTER читается из applied-манифеста, прежние записи имеют unknown, сбой архивации не означает сбой применения. Приёмка: JSON/TXT/BOM, обычный TXT игнорируется, collision и lock сохраняют данные, повторное применение блокируется; локальный CI и Windows/MEGA NOT RUN. Следом CI-03; UPD-03 и полная история rollback остаются отдельными задачами.

PR 68 содержал только JSON 173 и исправление .gitattributes, не продуктовый релиз. Не считать наличие JSON или зелёный CI на нём применением исходников. Новый PR содержит реальные исходники; исходный 173 не применять поверх этого релиза. UPD-04: владелец явно разрешил входящую синхронизацию одним кликом, без расширения прав плагинов; приёмка — штатные три шага, отсутствие входящих коммитов, блокировки, отказ этапа и проверенный restart. Тесты CI и Windows/MEGA ещё не подтверждены. UPD-01 остаётся частично открытым (свежесть remote, отдельный read-model). Следующий инкремент после приёмки — PATCH-03/04/05/06.

Начни с CI-00: проверь последний SHA и CI, воспроизведи CRLF failure на чистом checkout и устрани его без ослабления теста. После зелёного CI переходи к UPD-01. Прочитай этот файл, HANDOFF, UPDATE_MANAGER и STORAGE_CONTRACT; проверь `manager.py:state/check`, `routes_updates.py`, `UpdateWizardTab.tsx`, `RepositoriesTab.tsx`, App и тесты. Воспроизведи stale target_version после Sync на безопасном fixture. Предложи минимальный read-model, сохрани неизменность active journal/history, подготовь PATCHMASTER, тесты, версию и документацию. Если актуальный main уже содержит исправление, не повторяй его: проверь критерии и обнови статус, затем переходи к CI-01. Не изменяй механизмы Git/restart без отдельного доказанного дефекта.
