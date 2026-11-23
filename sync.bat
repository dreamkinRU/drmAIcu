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

:: 2. Забираем
echo === Получаем изменения с GitHub ===
git pull --rebase origin main
if %errorlevel% neq 0 (
    echo [ОШИБКА] Конфликт при pull --rebase.
    echo Разрешите вручную, затем: git rebase --continue
    pause & exit /b 1
)

:: 2.5. Отчёт по PR: видно, с чем синхронизировались
echo === Последний merged PR ===
gh pr list --state merged --limit 1
if %errorlevel% neq 0 (
    echo [?] gh CLI недоступен - смотри PR на сайте репозитория.
)
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