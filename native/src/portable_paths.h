#ifndef WOJD_PORTABLE_PATHS_H
#define WOJD_PORTABLE_PATHS_H
static WCHAR g_root_path[1024],g_host_path[1024],g_catalog_path[1024],g_cache_path[1024];
static WCHAR g_logs_path[1024],g_bootstrap_path[1024],g_selftest_path[1024],g_stop_path[1024];
static BOOL g_paths_ready;
static DWORD paths_init(HMODULE module){
    WCHAR *last;DWORD n;
    if(g_paths_ready)return ERROR_SUCCESS;
    n=GetModuleFileNameW(NULL,g_host_path,1024);if(!n || n>=1024)return ERROR_FILENAME_EXCED_RANGE;
    n=GetModuleFileNameW(module,g_root_path,1024);if(!n || n>=1024)return ERROR_FILENAME_EXCED_RANGE;
    last=wcsrchr(g_root_path,L'\\');if(!last)return ERROR_BAD_PATHNAME;*last=0;
    if(wcscat_s(g_root_path,1024,L"\\wojd"))return ERROR_FILENAME_EXCED_RANGE;
    if(!CreateDirectoryW(g_root_path,NULL) && GetLastError()!=ERROR_ALREADY_EXISTS)return GetLastError();
#define WOJD_PATH(destination,suffix) if(_snwprintf_s(destination,1024,_TRUNCATE,L"%s\\%s",g_root_path,L##suffix)<0)return ERROR_FILENAME_EXCED_RANGE
    WOJD_PATH(g_catalog_path,"catalog.bin");WOJD_PATH(g_cache_path,"reader-cache.ini");
    WOJD_PATH(g_logs_path,"logs");WOJD_PATH(g_bootstrap_path,"startup.log");
    WOJD_PATH(g_selftest_path,"selftest-data.ndjson");WOJD_PATH(g_stop_path,"stop.txt");
#undef WOJD_PATH
    g_paths_ready=TRUE;return ERROR_SUCCESS;
}
#endif
