@echo off
chcp 65001 >nul
title CU Agent Launcher
color 0A

python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] Python not found! Install Python 3.10+
    pause
    exit /b 1
)

if not exist main.py (
    color 0C
    echo [ERROR] main.py not found!
    pause
    exit /b 1
)

if not exist logs mkdir logs

echo ========================================
echo   CU Agent Launcher
echo ========================================
echo.

:loop
echo [%time%] Starting...
python main.py
set EXITCODE=%errorlevel%

if exist restart.flag (
    del restart.flag >nul 2>&1
    echo [%time%] Restart flag found. Restarting...
    timeout /t 2 /nobreak >nul
    goto loop
)

if %EXITCODE%==0 (
    echo [%time%] Stopped normally.
    pause
    exit /b 0
)

echo.
echo [%time%] Crashed (code %EXITCODE%). Restart in 3 sec...
timeout /t 3 /nobreak >nul
goto loop