@echo off
setlocal
chcp 65001 >nul
set "PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0ChatSettings.ps1"
set "WOJD_EXIT=%ERRORLEVEL%"
if /I not "%~1"=="--no-pause" pause
exit /b %WOJD_EXIT%
