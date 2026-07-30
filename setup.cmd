@echo off
setlocal
set "ROOT=%~dp0"
for /f "delims=" %%P in ('where pythonw.exe 2^>nul') do (
  start "" "%%P" "%ROOT%runtime\setup_gui.py"
  exit /b 0
)
echo [ERROR] Python not found. Install ShadowBot or Python 3.10+ first.
pause
exit /b 3
