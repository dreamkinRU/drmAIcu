@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title drmAIcu Launcher [WATCHDOG]
color 0A

echo ========================================
echo   drmAIcu WATCHDOG Launcher v2.0
echo   This window must stay open!
echo ========================================
echo.

:check_deps
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found!
    pause
    exit /b 1
)
if not exist "node_modules" (
    echo [INFO] Installing dependencies, first run...
    call npm install
    if !errorlevel! neq 0 (
        echo [ERROR] npm install failed. Check Node.js: node --version, npm --version
        pause
        exit /b 1
    )
) else (
    echo [INFO] Syncing dependencies with package-lock.json...
    call npm install --no-audit --no-fund
)
if not exist "patch" mkdir "patch"
if not exist "logs" mkdir "logs"
echo [OK] Systems ready.
echo.
set BROWSER_OPENED=0

:main_loop
:: === УБИВАЕМ СТАРЫЕ ОКНА ПО ЗАГОЛОВКУ (решение проблемы пустых окон) ===
echo [%time%] Cleaning up old windows...
taskkill /F /FI "WINDOWTITLE eq drmAIcu Core" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq drmAIcu UI" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq drmAIcu Core *" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq drmAIcu UI *" >nul 2>&1
timeout /t 1 /nobreak >nul

:: === ЗАПУСК ===
echo [%time%] Starting Python Core...
start "drmAIcu Core" /MIN cmd /c "python main.py"
timeout /t 3 /nobreak >nul

echo [%time%] Starting React UI...
start "drmAIcu UI" /MIN cmd /c "npm run dev -- --port 5173 --strictPort"
timeout /t 4 /nobreak >nul

if "%BROWSER_OPENED%"=="0" (
    echo [%time%] Opening browser...
    start http://127.0.0.1:5173
    set BROWSER_OPENED=1
)
echo.
echo ========================================
echo   SYSTEM RUNNING (watchdog active)
echo   Press Ctrl+C to stop completely
echo   Panel restart button works!
echo ========================================
echo.

:: === ЦИКЛ НАБЛЮДЕНИЯ ===
:watch_loop
timeout /t 5 /nobreak >nul

:: Проверяем флаг перезапуска от панели
if exist restart.flag (
    echo [%time%] Restart flag detected! Restarting...
    del restart.flag >nul 2>&1
    goto main_loop
)

:: Проверяем жив ли Python (порт 8080)
netstat -ano | findstr ":8080" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo [%time%] WARNING: Python Core is DOWN! Restarting...
    goto main_loop
)

:: Проверяем жив ли React (порт 5173)
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo [%time%] WARNING: React UI is DOWN! Restarting...
    goto main_loop
)

goto watch_loop
