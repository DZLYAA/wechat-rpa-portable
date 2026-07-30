@echo off
setlocal
set "ROOT=%~dp0"
python "%ROOT%runtime\doctor.py"
echo.
pause
exit /b %errorlevel%
