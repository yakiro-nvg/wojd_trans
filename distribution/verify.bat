@echo off
setlocal
set "PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Installer.ps1" -Action Verify
set "WOJD_EXIT=%ERRORLEVEL%"
if /I not "%~1"=="--no-pause" pause
exit /b %WOJD_EXIT%
