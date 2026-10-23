/* Setup-only metadata for known code hints. Never emits code/string bytes.
   The read primitive records the actual failed operation; no posthoc guess. */
#ifndef WOJD_PROBE_LOG
#define WOJD_PROBE_LOG logf_n4
#endif
#define PROBE_RECORD_LIMIT 16u
typedef struct ProbeLogState {MemoryProbe last;DWORD count,records;BOOL seen;} ProbeLogState;
static ProbeLogState g_code_probe_logs[3];
static ULONGLONG code_probe_rva(uintptr_t address) {
    uintptr_t base=(uintptr_t)g_image_base;return address>=base?(ULONGLONG)(address-base):0;
}
static void code_probe_failure(DWORD slot,const MemoryProbe *probe) {
    static const char *routes[3]={"GENERIC_CACHE","TYPED_CONTEXT_HINT","TYPED_SERIALIZER_HINT"};
    static const char *kinds[]={"NONE","QUERY","COMMIT","PROTECT","RPM","IMAGE_HEADER","RANGE","SECTION","MASK","UNWIND"};
    ProbeLogState *state=&g_code_probe_logs[slot];BOOL changed;
    state->count++;
    changed=!state->seen || state->last.kind!=probe->kind || state->last.error!=probe->error ||
        state->last.protect!=probe->protect || state->last.state!=probe->state || state->last.type!=probe->type;
    state->last=*probe;state->seen=TRUE;
    if(changed && state->records<PROBE_RECORD_LIMIT) {
        state->records++;
        WOJD_PROBE_LOG("CODE_HINT_VALIDATION_FAILURE","route=%s kind=%s win32=%lu address_rva=%llx query_at_rva=%llx region_begin_rva=%llx region_end_rva=%llx protect=%lx state=%lx type=%lx query_attempted=%lu query_succeeded=%lu rpm_attempted=%lu bytes_expected=%llu bytes_read=%llu failures=%lu records=%lu",
            routes[slot],kinds[probe->kind],probe->error,code_probe_rva(probe->address),code_probe_rva(probe->failed_at),
            code_probe_rva(probe->region_begin),code_probe_rva(probe->region_end),probe->protect,probe->state,probe->type,probe->query_attempted,probe->query_succeeded,probe->rpm_attempted,
            (ULONGLONG)probe->expected,(ULONGLONG)probe->got,state->count,state->records);
    }
}
static BOOL signature_at_report(const ImageView *view,const BYTE *address,const BYTE *expected,const BYTE *mask,SIZE_T n,MemoryProbe *probe) {
    BYTE bytes[1024];ZeroMemory(probe,sizeof(*probe));probe->address=(uintptr_t)address;probe->expected=n;
    if(n>sizeof(bytes) || !in_image(view,address,n)){probe->kind=PROBE_RANGE;return FALSE;}
    if(!executable(view,address)){probe->kind=PROBE_SECTION;return FALSE;}
    if(!read_exact_report(address,bytes,n,probe))return FALSE;
    if(!masked_match(bytes,expected,mask,n)){probe->kind=PROBE_MASK;return FALSE;}
    return TRUE;
}
