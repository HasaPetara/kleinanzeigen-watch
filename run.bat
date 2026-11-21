@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
echo [%DATE% %TIME%] --- Lauf --- >> logs\watch.log
python -m watcher >> logs\watch.log 2>&1
exit /b %ERRORLEVEL%