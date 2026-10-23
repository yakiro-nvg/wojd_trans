/* Per-process diagnostic files. Call outside DllMain, before starting the writer. */
#ifndef WOJD_NATIVE_SESSION_LOGGING_H
#define WOJD_NATIVE_SESSION_LOGGING_H
#define SESSION_PATH_CHARS 1024
typedef struct NativeSession {
    WCHAR directory[SESSION_PATH_CHARS],marker[SESSION_PATH_CHARS];
    WCHAR observations[SESSION_PATH_CHARS],metadata[SESSION_PATH_CHARS];
    ULONGLONG process_creation;
    DWORD pid;
} NativeSession;

static DWORD session_create(NativeSession *out,const WCHAR *root,const char *variant,
                            DWORD pid,ULONGLONG creation,ULONGLONG started) {
    NativeSession next;unsigned attempt;HANDLE file;char json[768];DWORD written,error;
    const char *p;int length;
    if(!out || !root || !variant || !*variant)return ERROR_INVALID_PARAMETER;
    for(p=variant;*p;p++)if(!((*p>='A' && *p<='Z') || (*p>='a' && *p<='z') ||
                           (*p>='0' && *p<='9') || *p=='-' || *p=='_'))return ERROR_INVALID_PARAMETER;
    if(p-variant>32)return ERROR_INVALID_PARAMETER;
    ZeroMemory(&next,sizeof(next));next.pid=pid;next.process_creation=creation;
    if(!CreateDirectoryW(root,NULL) && GetLastError()!=ERROR_ALREADY_EXISTS)return GetLastError();
    for(attempt=0;attempt<128;attempt++) {
        if(_snwprintf_s(next.directory,SESSION_PATH_CHARS,_TRUNCATE,L"%s\\%S-%016llx-pid-%lu-%03u",root,variant,started,pid,attempt)<0)return ERROR_FILENAME_EXCED_RANGE;
        if(CreateDirectoryW(next.directory,NULL))break;
        error=GetLastError();if(error!=ERROR_ALREADY_EXISTS)return error;
    }
    if(attempt==128)return ERROR_ALREADY_EXISTS;
    if(_snwprintf_s(next.marker,SESSION_PATH_CHARS,_TRUNCATE,L"%s\\native.log",next.directory)<0 ||
       _snwprintf_s(next.observations,SESSION_PATH_CHARS,_TRUNCATE,L"%s\\data.ndjson",next.directory)<0 ||
       _snwprintf_s(next.metadata,SESSION_PATH_CHARS,_TRUNCATE,L"%s\\session.json",next.directory)<0)return ERROR_FILENAME_EXCED_RANGE;
    length=_snprintf_s(json,sizeof(json),_TRUNCATE,
        "{\"format_version\":1,\"variant\":\"%s\",\"pid\":%lu,\"process_creation_filetime\":%llu,\"started_filetime\":%llu,\"state\":\"started\",\"completion_requires_archiver_report\":true}\n",
        variant,pid,creation,started);
    if(length<0)return ERROR_INSUFFICIENT_BUFFER;
    file=CreateFileW(next.metadata,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE)return GetLastError();
    error=ERROR_SUCCESS;
    if(!WriteFile(file,json,(DWORD)length,&written,NULL))error=GetLastError();
    else if(written!=(DWORD)length)error=ERROR_WRITE_FAULT;
    CloseHandle(file);if(error)return error;
    *out=next;return ERROR_SUCCESS;
}

static DWORD session_create_current(NativeSession *out,const WCHAR *root,const char *variant) {
    FILETIME created,exited,kernel,user,now;ULARGE_INTEGER birth,start;
    if(!GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user))return GetLastError();
    GetSystemTimeAsFileTime(&now);birth.LowPart=created.dwLowDateTime;birth.HighPart=created.dwHighDateTime;
    start.LowPart=now.dwLowDateTime;start.HighPart=now.dwHighDateTime;
    return session_create(out,root,variant,GetCurrentProcessId(),birth.QuadPart,start.QuadPart);
}
#endif
