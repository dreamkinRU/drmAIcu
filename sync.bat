@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
echo === Синхронизация с GitHub ===

:: 1. Что есть локального
git add -A
git diff --cached --quiet
if %errorlevel% neq 0 (
    git status -s
    set /p commit_msg="Введите сообщение коммита: "
    if "!commit_msg!"=="" (
        echo [ОШИБКА] Пустое сообщение — коммит отменён, изменения остались в индексе.
        pause & exit /b 1
    )
    git commit -m "!commit_msg!"
    if !errorlevel! neq 0 (
        echo [ОШИБКА] Коммит не создан.
        pause & exit /b 1
    )
) else (
    echo Локальных изменений нет.
)

:: 1.5. Запоминаем коммит ДО pull (для обнаружения обновления зависимостей)
for /f "delims=" %%i in ('git rev-parse HEAD') do set "old_head=%%i"

:: 2. Забираем
echo === Получаем изменения с GitHub ===
git pull --rebase origin main
if %errorlevel% neq 0 (
    echo [ОШИБКА] Конфликт при pull --rebase.
    echo Разрешите вручную, затем: git rebase --continue
    pause & exit /b 1
)

:: 2.7. npm-зависимости: если package-lock.json обновился после pull — ставим зависимости
echo === Проверка npm-зависимостей ===
if defined old_head (
    git diff --quiet "!old_head!" HEAD -- package-lock.json
    if !errorlevel! neq 0 (
        echo package-lock.json изменился - устанавливаем: npm install...
        call npm install --no-audit --no-fund
        if !errorlevel! neq 0 (
            echo [ОШИБКА] npm install завершился с ошибкой.
            echo Пути исправления:
            echo   1^) проверьте установлен ли Node.js: node --version и npm --version
            echo   2^) при битых зависимостях: удалите папку node_modules и файл package-lock.json, затем снова npm install
            echo   3^) Подробнее: docs\USER_GUIDE.md - раздел "Типовые ошибки и пути исправления"
            pause & exit /b 1
        )
    ) else (
        echo npm-зависимости не менялись.
    )
)


:: 2.5. Отчёт по PR: видно, с чем синхронизировались
echo === Последний merged PR ===
where gh >nul 2>nul
if errorlevel 1 (
    echo [?] gh CLI недоступен - описание последнего мержа:
    git log -1 --grep="Merge pull request #" --format="%%s" -1
    goto pr_done
)
gh pr list --state merged --limit 1 --json number,title --template "{{range .}}#{{.number}} - {{.title}}{{end}}"
if errorlevel 1 (
    echo [?] Не удалось получить PR - описание последнего мержа:
    git log -1 --grep="Merge pull request #" --format="%%s" -1
    goto pr_done
)
echo.
:pr_done
echo Текущий HEAD:
git log -1 --oneline

:: 3. Отправляем
echo === Отправляем изменения на GitHub ===
git push origin main
if %errorlevel% neq 0 (
    echo [ОШИБКА] push не прошёл (защита ветки / сеть). Изменения остались локально в main.
    pause & exit /b 1
)

echo === Готово! ===
pause