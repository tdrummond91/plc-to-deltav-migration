@echo off
setlocal
cd /d "%~dp0"
if exist "python-parser\.venv\Scripts\python.exe" (
  set "PYTHONPATH=%~dp0python-parser\src"
  "python-parser\.venv\Scripts\python.exe" -B -m plc_workbench.workspace
) else (
  where uv >nul 2>nul
  if errorlevel 1 (
    echo The workbench needs the same Python environment used by run-work-check.
    echo Set up that environment once, then open this file again.
    pause
    exit /b 1
  )
  uv run --project python-parser --locked python -B -m plc_workbench.workspace
)
if errorlevel 1 pause
endlocal
