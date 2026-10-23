/* Shared setup-only, page-aware READABLE-SCOPE scan. Unreadable or changed
   pages are counted as gaps; completion never certifies unseen code. */
#define SCAN_STEP_BYTES (64u*1024u)
#define SCAN_OVERLAP 1024u
#define SCAN_PHASE_LIMIT (512ull*1024ull*1024ull)
#define SCAN_STEP_LIMIT 32768u
typedef struct ExecutableScan {
    WORD section;
    SIZE_T offset;
    ULONGLONG bytes,skipped_bytes;
    DWORD steps,gaps,read_failures;
    BOOL started,complete;
    SIZE_T tail_size,tail_end;
    BYTE tail[SCAN_OVERLAP];
} ExecutableScan;
static DWORD scan_executable_step(const ImageView *view,ExecutableScan *cursor,
        BYTE *copy,SIZE_T capacity,ScanCallback callback,void *context) {
    DWORD operations=0;
    if(cursor->complete)return ERROR_SUCCESS;
    if(capacity<SCAN_STEP_BYTES || ++cursor->steps>SCAN_STEP_LIMIT)return ERROR_TIMEOUT;
    while(cursor->section<view->section_count && operations++<96) {
        const IMAGE_SECTION_HEADER *section=&view->sections[cursor->section];
        SIZE_T start=section->VirtualAddress,end=start+section->Misc.VirtualSize,amount,available,prefix;
        MEMORY_BASIC_INFORMATION region;uintptr_t region_end;BOOL can_read;
        if(!(section->Characteristics&IMAGE_SCN_MEM_EXECUTE)) {cursor->section++;cursor->started=FALSE;cursor->tail_size=0;continue;}
        if(end<start || end>view->size)return ERROR_BAD_EXE_FORMAT;
        if(!cursor->started){cursor->offset=start;cursor->started=TRUE;cursor->tail_size=0;}
        if(cursor->offset>=end){cursor->section++;cursor->started=FALSE;cursor->tail_size=0;continue;}
        if(!VirtualQuery(view->base+cursor->offset,&region,sizeof(region)))return ERROR_INVALID_ADDRESS;
        region_end=(uintptr_t)region.BaseAddress+region.RegionSize;
        if(region_end<=(uintptr_t)(view->base+cursor->offset))return ERROR_INVALID_ADDRESS;
        available=region_end-(uintptr_t)(view->base+cursor->offset);
        if(available>end-cursor->offset)available=end-cursor->offset;
        can_read=region.State==MEM_COMMIT && readable(region.Protect);
        prefix=(can_read && cursor->tail_end==cursor->offset)?cursor->tail_size:0;
        amount=available;if(amount>SCAN_STEP_BYTES-prefix)amount=SCAN_STEP_BYTES-prefix;
        if(cursor->bytes+cursor->skipped_bytes+amount>SCAN_PHASE_LIMIT)return ERROR_TIMEOUT;
        if(can_read) {
            if(prefix)memcpy(copy,cursor->tail,prefix);
            can_read=read_exact(view->base+cursor->offset,copy+prefix,amount);
            if(!can_read) {
                /* Protection can change between query and read. Count a page
                   gap and advance; a later bounded phase may find it readable. */
                SYSTEM_INFO info;SIZE_T page_remaining;
                GetSystemInfo(&info);page_remaining=info.dwPageSize-((uintptr_t)(view->base+cursor->offset)%info.dwPageSize);
                if(amount>page_remaining)amount=page_remaining;
                cursor->read_failures++;
            }
        }
        if(!can_read) {
            cursor->gaps++;cursor->skipped_bytes+=amount;cursor->tail_size=0;
            cursor->offset+=amount;cursor->tail_end=cursor->offset;return ERROR_MORE_DATA;
        }
        cursor->bytes+=amount;
        if(!callback(view,view->base+cursor->offset-prefix,copy,prefix+amount,context))return ERROR_CANCELLED;
        cursor->tail_size=prefix+amount;if(cursor->tail_size>SCAN_OVERLAP)cursor->tail_size=SCAN_OVERLAP;
        memcpy(cursor->tail,copy+prefix+amount-cursor->tail_size,cursor->tail_size);
        cursor->offset+=amount;cursor->tail_end=cursor->offset;
        return ERROR_MORE_DATA;
    }
    if(cursor->section>=view->section_count){cursor->complete=TRUE;return ERROR_SUCCESS;}
    return ERROR_MORE_DATA;
}
