@echo off
setlocal

rem Change to project root (parent of this script directory)
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo [space_aces_bot] Python virtual environment not found in .venv.
    exit /b 1
)

".venv\Scripts\python.exe" -m space_aces_bot %*

endlocal

