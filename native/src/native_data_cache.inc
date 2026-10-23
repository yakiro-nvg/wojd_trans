/* Cache is an optimization hint: every target is revalidated before patching. */
typedef struct CacheIdentity { ULONGLONG size,mtime,index;DWORD volume; } CacheIdentity;
typedef struct ReaderCache { CacheIdentity identity;DWORD reader,assign,raw,prefer_far; } ReaderCache;
/* A parsed candidate remains pending until validation or the worker's global
   watchdog. Starting/exhausting a relocation scan does not make it stale. */
static BOOL cache_probe_may_retry(DWORD identity_status,DWORD probe_status) {
    return (identity_status==ERROR_SUCCESS || identity_status==ERROR_REVISION_MISMATCH) &&
        (probe_status==ERROR_NOT_READY || probe_status==ERROR_NOT_FOUND);
}
enum { CACHE_ROUTE_PENDING=0,CACHE_ROUTE_WARM=1,CACHE_ROUTE_CALIBRATION=2 };
/* Input must be the result of full reader/callee/root validation, from either
   the cache probe or the shared discovery job. File identity alone grants none. */
static DWORD cache_result_route(DWORD identity_status,const ReaderCache *cache,void *base,const DataResult *result) {
    ULONGLONG image=(ULONGLONG)(uintptr_t)base;
    if(result->status || result->candidates!=1)return CACHE_ROUTE_PENDING;
    return identity_status==ERROR_SUCCESS && result->reader==image+cache->reader &&
        result->assign==image+cache->assign && result->raw_reader==image+cache->raw?CACHE_ROUTE_WARM:CACHE_ROUTE_CALIBRATION;
}
static DWORD cache_identity(CacheIdentity *out) {
    HANDLE file;BY_HANDLE_FILE_INFORMATION info;DWORD error;
    file=CreateFileW(GAME_EXE,FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE)return GetLastError();
    if(!GetFileInformationByHandle(file,&info)){error=GetLastError();CloseHandle(file);return error;}
    CloseHandle(file);ZeroMemory(out,sizeof(*out));
    out->size=((ULONGLONG)info.nFileSizeHigh<<32)|info.nFileSizeLow;
    out->mtime=((ULONGLONG)info.ftLastWriteTime.dwHighDateTime<<32)|info.ftLastWriteTime.dwLowDateTime;
    out->index=((ULONGLONG)info.nFileIndexHigh<<32)|info.nFileIndexLow;out->volume=info.dwVolumeSerialNumber;
    return ERROR_SUCCESS;
}
static BOOL cache_identity_equal(const CacheIdentity *a,const CacheIdentity *b) {
    return a->size==b->size && a->mtime==b->mtime && a->index==b->index && a->volume==b->volume;
}
static BOOL cache_number_section(const WCHAR *path,const WCHAR *section,const WCHAR *key,ULONGLONG *out) {
    WCHAR value[80],*end;DWORD n=GetPrivateProfileStringW(section,key,L"",value,80,path);
    if(!n || n>=79 || value[0]=='-' || value[0]=='+')return FALSE;
    *out=_wcstoui64(value,&end,0);return end!=value && !*end;
}
static BOOL cache_number(const WCHAR *path,const WCHAR *key,ULONGLONG *out) {
    return cache_number_section(path,L"NativeReader",key,out);
}
static DWORD cache_load(const WCHAR *path,ReaderCache *out) {
    CacheIdentity current;ULONGLONG value;DWORD error;ZeroMemory(out,sizeof(*out));
    error=cache_identity(&current);if(error)return error;
    if(!cache_number(path,L"format_version",&value) || value!=1 ||
       !cache_number(path,L"signature_revision",&value) || value!=1)return ERROR_INVALID_DATA;
    if(!cache_number(path,L"file_size",&out->identity.size) ||
       !cache_number(path,L"file_mtime",&out->identity.mtime) ||
       !cache_number(path,L"file_index",&out->identity.index) ||
       !cache_number(path,L"volume_serial",&value) || value>MAXDWORD)return ERROR_INVALID_DATA;
    out->identity.volume=(DWORD)value;
    if(!cache_number(path,L"reader_rva",&value) || !value || value>MAXDWORD)return ERROR_INVALID_DATA;out->reader=(DWORD)value;
    if(!cache_number(path,L"assign_rva",&value) || !value || value>MAXDWORD)return ERROR_INVALID_DATA;out->assign=(DWORD)value;
    if(!cache_number(path,L"raw_reader_rva",&value) || !value || value>MAXDWORD)return ERROR_INVALID_DATA;out->raw=(DWORD)value;
    if(!cache_number(path,L"prefer_far",&value) || value>1)return ERROR_INVALID_DATA;out->prefer_far=(DWORD)value;
    return cache_identity_equal(&current,&out->identity)?ERROR_SUCCESS:ERROR_REVISION_MISMATCH;
}
static DWORD cache_probe(void *base,const ReaderCache *cache,DataResult *out,DWORD *stage) {
    ImageView v;const BYTE *reader,*assign,*raw;ULONG64 owner_base=0;PRUNTIME_FUNCTION entry;MemoryProbe probe,reader_probe;
    ZeroMemory(out,sizeof(*out));*stage=0;
    if(!image_view_report(base,&v,&probe)){code_probe_failure(0,&probe);return out->status=ERROR_NOT_READY;}
    /* A stale reader RVA is still a hint. Relearn both E8 callees from CURRENT
       reader bytes; never promote cached assign/raw RVAs into authority. */
    reader=v.base+cache->reader;
    if(!signature_at_report(&v,reader,data_reader_bytes,data_reader_mask,sizeof(data_reader_bytes),&probe)) {
        code_probe_failure(0,&probe);return out->status=(probe.kind==PROBE_RANGE || probe.kind==PROBE_SECTION)?ERROR_INVALID_DATA:ERROR_NOT_READY;
    }
    reader_probe=probe;
    *stage|=1;assign=relative_target_report(reader+0x21e,&probe);
    if(!assign && probe.kind!=PROBE_NONE){code_probe_failure(0,&probe);return out->status=ERROR_NOT_READY;}
    raw=relative_target_report(reader+0x10e,&probe);
    if(!raw && probe.kind!=PROBE_NONE){code_probe_failure(0,&probe);return out->status=ERROR_NOT_READY;}
    if(!assign || !raw || !in_image(&v,assign,sizeof(data_assign_bytes)) ||
       !in_image(&v,raw,sizeof(data_read_bytes_bytes))) {
        ZeroMemory(&probe,sizeof(probe));probe.kind=PROBE_RANGE;
        probe.address=(uintptr_t)(!assign || !in_image(&v,assign,sizeof(data_assign_bytes))?assign:raw);
        code_probe_failure(0,&probe);return out->status=ERROR_INVALID_DATA;
    }
    if(signature_at_report(&v,assign,data_assign_bytes,data_assign_mask,sizeof(data_assign_bytes),&probe))*stage|=2;
    else code_probe_failure(0,&probe);
    if(signature_at_report(&v,raw,data_read_bytes_bytes,data_read_bytes_mask,sizeof(data_read_bytes_bytes),&probe))*stage|=4;
    else code_probe_failure(0,&probe);
    if(*stage!=7)return out->status=ERROR_NOT_READY;
    entry=RtlLookupFunctionEntry((DWORD64)(uintptr_t)reader,&owner_base,NULL);
    if(g_game_host && (!entry || (BYTE *)(uintptr_t)owner_base+entry->BeginAddress!=reader)){reader_probe.kind=PROBE_UNWIND;code_probe_failure(0,&reader_probe);return out->status=ERROR_NOT_READY;}
    *stage|=8;out->candidates=1;out->reader=(ULONGLONG)(uintptr_t)reader;
    out->assign=(ULONGLONG)(uintptr_t)assign;out->raw_reader=(ULONGLONG)(uintptr_t)raw;
    return out->status=ERROR_SUCCESS;
}
static DWORD cache_save(const WCHAR *path,void *base,const DataResult *result,DWORD prefer_far) {
    CacheIdentity id;WCHAR temporary[768];char text[1024];DWORD error,written;int n;HANDLE file;
    ULONGLONG image=(ULONGLONG)(uintptr_t)base;
    if(result->reader<=image || result->reader-image>MAXDWORD || result->assign<=image || result->assign-image>MAXDWORD ||
       result->raw_reader<=image || result->raw_reader-image>MAXDWORD)return ERROR_INVALID_DATA;
    error=cache_identity(&id);if(error)return error;
    n=_snprintf_s(text,sizeof(text),_TRUNCATE,
        "; Automatically learned; RVAs are hints; assignment signature and decoder origin are independently checked.\r\n"
        "[NativeReader]\r\nformat_version=1\r\nsignature_revision=1\r\nfile_size=%llu\r\nfile_mtime=%llu\r\n"
        "file_index=%llu\r\nvolume_serial=%lu\r\nreader_rva=0x%llx\r\nassign_rva=0x%llx\r\nraw_reader_rva=0x%llx\r\nprefer_far=%lu\r\n",
        id.size,id.mtime,id.index,id.volume,result->reader-image,result->assign-image,result->raw_reader-image,prefer_far?1ul:0ul);
    if(n<0)return ERROR_INSUFFICIENT_BUFFER;
    _snwprintf_s(temporary,768,_TRUNCATE,L"%s.pid-%lu.tmp",path,GetCurrentProcessId());
    file=CreateFileW(temporary,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE)return GetLastError();
    if(!WriteFile(file,text,(DWORD)n,&written,NULL) || written!=(DWORD)n){error=GetLastError();CloseHandle(file);return error?error:ERROR_WRITE_FAULT;}
    if(!FlushFileBuffers(file)){error=GetLastError();CloseHandle(file);return error;}
    CloseHandle(file);
    if(!MoveFileExW(temporary,path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))return GetLastError();
    return ERROR_SUCCESS;
}
