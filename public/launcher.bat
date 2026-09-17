@echo off
chcp 65001 >nul
title drmAIcu v3.0.5 FORTRESS
color 0A

python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ОШИБКА] Python не найден! Установите Python 3.10+
    pause
    exit /b 1
)

if not exist main.py (
    color 0C
    echo [ОШИБКА] main.py не найден!
    pause
    exit /b 1
)

if not exist logs mkdir logs

echo ========================================
echo   drmAIcu v3.0.5 FORTRESS
echo ========================================
echo.

:loop
echo [%time%] Запуск ЦУ...
python main.py
set EXITCODE=%errorlevel%

if exist restart.flag (
    del restart.flag >nul 2>&1
    echo [%time%] Перезапуск...
    timeout /t 2 /nobreak >nul
    goto loop
)

if %EXITCODE%==0 (
    echo [%time%] Остановлено.
    pause
    exit /b 0
)

echo.
echo [%time%] Сбой (код %EXITCODE%). Перезапуск через 3 сек...
timeout /t 3 /nobreak >nul
goto loop
