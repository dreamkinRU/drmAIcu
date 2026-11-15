@echo off
chcp 65001 >nul
echo [INFO] Generatsiya otcheta... Pozhaluyta, podozhdite.

:: 1. Oshchayem fail otcheta
echo ======================================== > report.txt
echo CENTRALIZOVANNYY OTCHET OSHIBOK drmAIcu >> report.txt
echo Data: %date% %time% >> report.txt
echo ======================================== >> report.txt
echo. >> report.txt

:: 2. Proverka portov
echo [1] STATUS PORTOV (5173 i 8080): >> report.txt
netstat -ano | findstr ":5173 :8080" >> report.txt
if %errorlevel% neq 0 echo Porty svobodny ili ne otvechayut. >> report.txt
echo. >> report.txt

:: 3. Versii
echo [2] VERSII SISTEMY: >> report.txt
node -v >> report.txt
npm -v >> report.txt
echo. >> report.txt

:: 4. Soderzhimoe kriticheskih faylov
echo [3] SODERZHIMOE vite.config.js: >> report.txt
type vite.config.js >> report.txt
echo. >> report.txt

:: 5. Popitka zapuska Vite s perehvatom oshibki
echo [4] POPITKA ZAPUSKA VITE (LOG OSHIBKI): >> report.txt
echo --- NACHALO LOGA VITE --- >> report.txt
:: My ubivaem vse node processy pered proverkoy, chtoby byt' chistymi
taskkill /F /IM node.exe /T >nul 2>&1
:: Zapuskayem i perehvatyvaem vyvod. Yesli upadet srazu, my eto uvidim.
call npm run dev -- --port 5173 > vite_temp.log 2>&1
type vite_temp.log >> report.txt
echo --- KONETS LOGA VITE --- >> report.txt
del vite_temp.log >nul 2>&1

echo. >> report.txt
echo ======================================== >> report.txt
echo GOTovo. 
echo.
echo OTKROYTE FAIL 'report.txt' V FAR MANAGER (F3).
echo VYDELITE VES' TEKST (Ctrl+A ili myshyu), SKOPIRUYTE (Ctrl+Ins) I PRISHLITE MNE.
echo.
pause