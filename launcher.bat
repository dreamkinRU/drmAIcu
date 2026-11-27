@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
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
if not exist "dist\index.html" (
    echo [INFO] Building production frontend...
    call npm ci --no-audit --no-fund
    if !errorlevel! neq 0 (
        echo [ERROR] npm ci failed. Stop other drmAIcu instances and pause cloud sync.
        pause
        exit /b 1
    )
    call npm run build
    if !errorlevel! neq 0 (
        echo [ERROR] Frontend build failed.
        pause
        exit /b 1
    )
)
if not exist "patch" mkdir "patch"
if not exist "logs" mkdir "logs"
echo [OK] Systems ready.
echo.
python launcher_supervisor.py
if errorlevel 1 pause
