@echo off
title drmAIcu Launcher
color 0A
echo ========================================
echo   drmAIcu Bulletproof Launcher
echo ========================================
echo.
echo [1/5] Checking Python and Node.js
python --version >nul 2>&1
if %errorlevel% neq 0 ( color 0C & echo ERROR: Python not found & pause & exit /b 1 )
node --version >nul 2>&1
if %errorlevel% neq 0 ( color 0C & echo ERROR: Node.js not found & pause & exit /b 1 )
echo [OK] Systems ready
echo.
echo [2/5] KILLING old processes and freeing ports
taskkill /F /IM node.exe /T >nul 2>&1
taskkill /F /IM python.exe /T >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8080') do taskkill /F /PID %%a >nul 2>&1
echo [OK] Ports 5173 and 8080 are free
echo.
echo [3/5] Checking React dependencies
if not exist "node_modules" (
    echo [INFO] Running npm install. Please wait.
    call npm install
    if %errorlevel% neq 0 ( color 0C & echo ERROR: npm install failed & pause & exit /b 1 )
    echo [OK] Dependencies installed
) else (
    echo [OK] Dependencies already exist
)
echo.
echo [4/5] Starting systems
if not exist "logs" mkdir "logs"
echo [1/3] Starting Python Core (Port 8080)
start "drmAIcu Core" cmd /k "python main.py"
timeout /t 3 /nobreak >nul
echo [2/3] Starting React UI (Strictly Port 5173)
start "drmAIcu UI" cmd /k "npm run dev -- --port 5173"
timeout /t 5 /nobreak >nul
echo [3/3] Opening browser
start http://127.0.0.1:5173
echo.
echo ========================================
echo   SYSTEM LAUNCHED SUCCESSFULLY
echo ========================================
timeout /t 3 /nobreak >nul
exit /b 0
"@
$batContent | Out-File -FilePath "launcher.bat" -Encoding ASCII