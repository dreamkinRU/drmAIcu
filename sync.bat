@echo off
echo === Синхронизация с GitHub ===
git add .
git status
set /p commit_msg="Введите сообщение коммита: "
git commit -m "%commit_msg%"
git push origin main
echo === Готово! ===
pause