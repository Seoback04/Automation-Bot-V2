$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" "tools\launch_jobbot.py"
} else {
    python "tools\launch_jobbot.py"
}
