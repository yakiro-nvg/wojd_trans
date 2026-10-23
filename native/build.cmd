@echo off
setlocal
set "VSCMD_SKIP_SENDTELEMETRY=1"
for %%I in ("%~dp0..") do set "WOJD_REPO=%%~fI"
if defined VCToolsInstallDir goto build
for /f "usebackq tokens=*" %%I in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "WOJD_VS=%%I"
if not defined WOJD_VS exit /b 1
call "%WOJD_VS%\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
:build
set "WOJD_PROFILE=%~1"
if not defined WOJD_PROFILE set "WOJD_PROFILE=runtime"
set "WOJD_CAPTURE=0"
set "WOJD_SELFTEST=0"
if "%WOJD_PROFILE%"=="dump" set "WOJD_CAPTURE=1"
if "%WOJD_PROFILE%"=="dump-test" set "WOJD_CAPTURE=1"
if "%WOJD_PROFILE%"=="dump-test" set "WOJD_SELFTEST=1"
if "%WOJD_PROFILE%"=="runtime-test" set "WOJD_SELFTEST=1"
if not "%WOJD_PROFILE%"=="runtime" if not "%WOJD_PROFILE%"=="dump" if not "%WOJD_PROFILE%"=="runtime-test" if not "%WOJD_PROFILE%"=="dump-test" exit /b 2
set "WOJD_OUT=%WOJD_REPO%\native\build\%WOJD_PROFILE%"
if not exist "%WOJD_OUT%" mkdir "%WOJD_OUT%"
if not exist "%WOJD_OUT%\tmp" mkdir "%WOJD_OUT%\tmp"
set "TEMP=%WOJD_OUT%\tmp"
set "TMP=%TEMP%"
cd /d "%WOJD_OUT%"
cl /nologo /c /TC /MT /O2 /W3 /I"%WOJD_REPO%\native\vendor\minhook\include" "%WOJD_REPO%\native\vendor\minhook\src\buffer.c" "%WOJD_REPO%\native\vendor\minhook\src\hook.c" "%WOJD_REPO%\native\vendor\minhook\src\trampoline.c" "%WOJD_REPO%\native\vendor\minhook\src\hde\hde64.c"
if errorlevel 1 exit /b 1
cl /nologo /c /TC /MT /O2 /Ob0 /W4 /WX /wd4505 /DWOJD_CAPTURE=%WOJD_CAPTURE% /DWOJD_SELFTEST=%WOJD_SELFTEST% /Fo"localization.obj" "%WOJD_REPO%\native\src\localization.c"
if errorlevel 1 exit /b 1
lib /nologo /DEF:"%WOJD_REPO%\native\original.def" /OUT:"wojd_dbghelp_original.lib" /MACHINE:X64
if errorlevel 1 exit /b 1
link /nologo /DLL /Brepro /OUT:"dbghelp.dll" /DEF:"%WOJD_REPO%\native\exports.def" /IMPLIB:"dbghelp.lib" /MACHINE:X64 /DYNAMICBASE /NXCOMPAT localization.obj buffer.obj hook.obj trampoline.obj hde64.obj kernel32.lib wojd_dbghelp_original.lib
if errorlevel 1 exit /b 1
>build-profile.json echo {"profile":"%WOJD_PROFILE%","capture":%WOJD_CAPTURE%,"selftest":%WOJD_SELFTEST%,"optimization":"O2","static_crt":true}
if "%WOJD_SELFTEST%"=="0" exit /b 0
ml64 /nologo /c /Fo"assignment_origin_frame.obj" "%WOJD_REPO%\native\tests\assignment_gate_fixture.asm"
if errorlevel 1 exit /b 1
cl /nologo /LD /TC /MT /O2 /Ob0 /W4 /WX /Fe"data_reader_fixture.dll" "%WOJD_REPO%\native\tests\assignment_gate_fixture.c" /link assignment_origin_frame.obj /IMPLIB:"data_reader_fixture.lib" /EXPORT:WojdFixtureAssignTarget /EXPORT:WojdFixtureAssignmentOrigin /EXPORT:WojdFixtureAssignmentReturn
if errorlevel 1 exit /b 1
rem The three C8 setup fixtures are independent of test-only DLL exports.
rem Build them once, with MinHook objects compiled from this checkout above.
if not "%WOJD_PROFILE%"=="runtime-test" exit /b 0
set "WOJD_C8_OUT=%WOJD_REPO%\native\build\c8-setup"
if not exist "%WOJD_C8_OUT%" mkdir "%WOJD_C8_OUT%"
cd /d "%WOJD_C8_OUT%"
cl /nologo /TC /MT /O2 /W4 /WX /wd4505 /Fe"allocator_fixture.exe" /Fo"allocator_fixture.obj" "%WOJD_REPO%\native\tests\c8_allocator_fixture.c"
if errorlevel 1 exit /b 1
cl /nologo /TC /MT /Od /W4 /WX /wd4505 /Fe"plain_skill_fixture.exe" /Fo"plain_skill_fixture.obj" "%WOJD_REPO%\native\tests\c8_plain_skill_fixture.c"
if errorlevel 1 exit /b 1
cl /nologo /c /TC /MT /O2 /Ob0 /W4 /WX /wd4505 /Fo"setup_integration_fixture.obj" "%WOJD_REPO%\native\tests\c8_setup_integration_fixture.c"
if errorlevel 1 exit /b 1
link /nologo /OUT:"setup_integration_fixture.exe" /MACHINE:X64 setup_integration_fixture.obj "%WOJD_OUT%\buffer.obj" "%WOJD_OUT%\hook.obj" "%WOJD_OUT%\trampoline.obj" "%WOJD_OUT%\hde64.obj" kernel32.lib
exit /b %errorlevel%
