/* Validate the already-executing decoder at its first assignment. This avoids
 * missing records while a background scan is still waiting for readable code.
 * No I/O, waits, cache identity or text-dependent approval in this callback. */
static PVOID volatile g_executing_return;
static volatile ULONGLONG g_executing_first_us;
static PVOID volatile g_executing_other_callers[256];
static DWORD check_executing_origin(void *caller) {
    ImageView view;const BYTE *reader,*raw;ULONG64 owner_base=0;PRUNTIME_FUNCTION owner;
    if(!g_image_base || !g_target || (uintptr_t)caller<(uintptr_t)g_image_base+0x223)return ERROR_INVALID_DATA;
    reader=(const BYTE *)caller-0x223;
    if(!image_view(g_image_base,&view) || !in_image(&view,reader,sizeof(data_reader_bytes)))return ERROR_INVALID_DATA;
    owner=RtlLookupFunctionEntry((DWORD64)(uintptr_t)caller,&owner_base,NULL);
    if(!owner)return ERROR_NOT_READY;
    if((BYTE *)(uintptr_t)owner_base!=view.base || owner->BeginAddress!=(DWORD)(reader-view.base) ||
       owner->EndAddress-owner->BeginAddress!=sizeof(data_reader_bytes))return ERROR_INVALID_DATA;
    if(!signature_at(&view,reader,data_reader_bytes,data_reader_mask,sizeof(data_reader_bytes)))return ERROR_NOT_READY;
    if(relative_target(reader+0x21e)!=(const BYTE *)g_target)return ERROR_INVALID_DATA;
    raw=relative_target(reader+0x10e);
    if(!raw || !signature_at(&view,raw,data_read_bytes_bytes,data_read_bytes_mask,sizeof(data_read_bytes_bytes)))return ERROR_NOT_READY;
    return ERROR_SUCCESS;
}
static BOOL executing_origin(void *caller) {
    PVOID known;DWORD slot,error;
    if(!InterlockedCompareExchange(&g_active,0,0))return FALSE;
    known=InterlockedCompareExchangePointer(&g_executing_return,NULL,NULL);
    if(known)return known==caller;
    slot=(DWORD)(((uintptr_t)caller>>4)^((uintptr_t)caller>>12))&255u;
    if(InterlockedCompareExchangePointer(&g_executing_other_callers[slot],NULL,NULL)==caller)return FALSE;
    error=check_executing_origin(caller);
    if(error) {
        /* Protection/readiness failures must be retried; unwind mismatches are
         * stable metadata and can be rejected without repeated inspection. */
        if(error==ERROR_INVALID_DATA)InterlockedExchangePointer(&g_executing_other_callers[slot],caller);
        return FALSE;
    }
    if(!InterlockedCompareExchangePointer(&g_executing_return,caller,NULL))
        g_executing_first_us=diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart);
    return InterlockedCompareExchangePointer(&g_executing_return,NULL,NULL)==caller;
}
/* Setup-thread handoff of the same proof. The cold-start path must not depend
 * on the background scanner having observed a page before its first use. */
static DWORD executing_origin_result(DataResult *out) {
    const BYTE *caller=(const BYTE *)InterlockedCompareExchangePointer(&g_executing_return,NULL,NULL),*reader,*raw;
    ImageView view;MemoryProbe probe;DWORD error;
    ZeroMemory(out,sizeof(*out));if(!caller)return ERROR_NOT_READY;
    error=check_executing_origin((void *)caller);if(error)return error;
    reader=caller-0x223;raw=relative_target(reader+0x10e);
    if(!image_view(g_image_base,&view) || !assignment_signature_at_report(&view,(const BYTE *)g_target,&probe))return ERROR_NOT_READY;
    out->candidates=1;out->reader=(ULONGLONG)(uintptr_t)reader;out->assign=(ULONGLONG)(uintptr_t)g_target;
    out->raw_reader=(ULONGLONG)(uintptr_t)raw;return ERROR_SUCCESS;
}
