/* The developer profile alone starts the public, readable log archiver. */
#if WOJD_CAPTURE
static DWORD start_archiver(void){
    WCHAR executable[1024],script[1200],command[4096];STARTUPINFOW startup;PROCESS_INFORMATION process;UINT n;
    n=GetSystemDirectoryW(executable,1024);if(!n || n>=1024)return ERROR_FILENAME_EXCED_RANGE;
    if(wcscat_s(executable,1024,L"\\WindowsPowerShell\\v1.0\\powershell.exe"))return ERROR_FILENAME_EXCED_RANGE;
    if(_snwprintf_s(script,1200,_TRUNCATE,L"%s\\Archive-Session.ps1",g_root_path)<0 ||
       _snwprintf_s(command,4096,_TRUNCATE,L"\"%s\" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"%s\" -Session \"%s\"",executable,script,g_session.directory)<0)return ERROR_FILENAME_EXCED_RANGE;
    ZeroMemory(&startup,sizeof(startup));startup.cb=sizeof(startup);startup.dwFlags=STARTF_USESHOWWINDOW;startup.wShowWindow=SW_HIDE;
    ZeroMemory(&process,sizeof(process));
    if(!CreateProcessW(executable,command,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,g_root_path,&startup,&process))return GetLastError();
    CloseHandle(process.hThread);CloseHandle(process.hProcess);return ERROR_SUCCESS;
}
#endif
