@echo off
chcp 65001 >nul
echo === Синхронизация с GitHub ===

:: 1. Проверяем, есть ли локальные изменения
git add .
git diff --cached --quiet
if %errorlevel% equ 0 goto pull_changes

git status -s
set /p commit_msg="Введите сообщение коммита: "
git commit -m "%commit_msg%"

:pull_changes
:: 2. Забираем новые коммиты с GitHub
echo === Получаем изменения с GitHub ===
git pull --rebase origin main
if %errorlevel% neq 0 (
    echo [ОШИБКА] Возник конфликт при получении изменений!
    echo Разрешите конфликт вручную, затем выполните: git rebase --continue
    pause
    exit /b 1
)

:: 3. Отправляем изменения на GitHub
echo === Отправляем изменения на GitHub ===
git push origin main

echo === Готово! ===
pause