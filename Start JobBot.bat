@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "tools\launch_jobbot.py"
) else (
    python "tools\launch_jobbot.py"
)

endlocal
