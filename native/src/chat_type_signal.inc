/* A fixed type(string) call confirms execution without load/print or new Lua
 * globals. Observe the already-validated, read-only Lua type API; no stack
 * values are added and the original numeric type result remains unchanged. */
#include "chat_type_signatures.h"
typedef int (__fastcall *LcoKindFn)(void *,void *,int);
typedef const char *(__fastcall *LcoStringLengthFn)(void *,int,SIZE_T *);
typedef int (__fastcall *LcoTypeFn)(void *,int);
static LcoStringLengthFn g_lco_string_length;
static LcoTypeFn g_lco_type_original;
static void *g_lco_type_target;
static volatile LONG g_lco_type_inflight;
static __declspec(thread) unsigned g_lco_type_depth;
static const char lco_type_prefix[]="WOJD_CHAT_NATIVE_SIGNAL_V1:";

static BOOL lco_type_marker(const char *buffer,SIZE_T size) {
    char marker[sizeof(lco_type_prefix)-1+8];unsigned i;
    if(!buffer || size!=sizeof(marker) || g_lco_executed || !read_exact(buffer,marker,sizeof(marker)) ||
       memcmp(marker,lco_type_prefix,sizeof(lco_type_prefix)-1))return FALSE;
    for(i=0;i<8;++i)if(!marker[sizeof(lco_type_prefix)-1+i] || !strchr("ntfusdbr?",marker[sizeof(lco_type_prefix)-1+i]))return FALSE;
    if(InterlockedCompareExchange(&g_lco_marker_taken,1,0))return FALSE;
    memcpy(g_lco_kinds,marker+sizeof(lco_type_prefix)-1,8);g_lco_kinds[8]=0;
    MemoryBarrier();InterlockedExchange(&g_lco_executed,1);return TRUE;
}
static int __fastcall lco_type_hook(void *state,int index) {
    DWORD saved=GetLastError(),after;int result;
    InterlockedIncrement(&g_lco_type_inflight);
    SetLastError(saved);result=g_lco_type_original(state,index);after=GetLastError();
    if(g_lco_active && !g_lco_executed && !g_lco_type_depth && index==1 && result==4) {
        SIZE_T size=0;const char *value;
        ++g_lco_type_depth;
        value=g_lco_string_length(state,1,&size);
        lco_type_marker(value,size);
        --g_lco_type_depth;
    }
    InterlockedDecrement(&g_lco_type_inflight);SetLastError(after);return result;
}
static DWORD lco_type_resolve(const ImageView *view,const LcoResult *binding,LcoKindFn *kind,LcoStringLengthFn *string_length,void **target) {
    unsigned slot,matches=0;const BYTE *wrapper=NULL,*callee=NULL;
    for(slot=0;slot<binding->slots;++slot) {
        const BYTE *candidate;
        if(!read_exact(view->base+binding->table+slot*8,&candidate,8))return ERROR_NOACCESS;
        if(!signature_at(view,candidate,lco_type_api_wrapper_bytes,lco_type_api_wrapper_mask,sizeof(lco_type_api_wrapper_bytes)))continue;
        callee=relative_target(candidate+6);
        if(callee && signature_at(view,callee,lco_type_api_callee_bytes,lco_type_api_callee_mask,sizeof(lco_type_api_callee_bytes))) {
            wrapper=candidate;++matches;
        }
    }
    if(matches!=1)return matches?ERROR_DUP_NAME:ERROR_NOT_FOUND;
    callee=relative_target(wrapper+6);
    *kind=(LcoKindFn)(uintptr_t)wrapper;
    *string_length=(LcoStringLengthFn)(uintptr_t)relative_target(binding->functions[LCO_TOSTRING]+k_lco_signatures[LCO_TOSTRING].branch_offset);
    if(!*string_length)return ERROR_INVALID_FUNCTION;
    *target=(void *)callee;return ERROR_SUCCESS;
}
static DWORD lco_type_attach(void *target,LcoStringLengthFn string_length) {
    MH_STATUS mh;
    if(!target || !string_length || g_lco_type_target)return ERROR_INVALID_STATE;
    mh=MH_Initialize();if(mh!=MH_OK && mh!=MH_ERROR_ALREADY_INITIALIZED)return ERROR_INVALID_STATE;
    g_lco_string_length=string_length;
    mh=MH_CreateHook(target,(void *)(uintptr_t)lco_type_hook,(void **)&g_lco_type_original);
    if(mh!=MH_OK)return ERROR_INVALID_FUNCTION;
    mh=MH_EnableHook(target);
    if(mh!=MH_OK){MH_RemoveHook(target);return ERROR_INVALID_FUNCTION;}
    g_lco_type_target=target;return ERROR_SUCCESS;
}
static DWORD lco_type_remove(void) {
    if(g_lco_type_inflight)return ERROR_BUSY;
#if !defined(WOJD_CHAT_OBSERVER_TEST) || !WOJD_CHAT_OBSERVER_TEST
    /* The DLL is pinned. Keep the disabled detour's trampoline allocated for
       a thread that entered just before disabling but has not incremented its
       callback counter yet. The one-shot observer does not reattach. */
    return ERROR_SUCCESS;
#else
    if(g_lco_type_target){
        MH_STATUS status=MH_RemoveHook(g_lco_type_target);
        if(status!=MH_OK)return ERROR_INVALID_FUNCTION;
        g_lco_type_target=NULL;g_lco_type_original=NULL;
    }
    return ERROR_SUCCESS;
#endif
}
