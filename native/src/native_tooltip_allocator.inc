/* Setup only. Find the same full203-byte assignment used by the .data route
   near a validated serializer. Distance is a search hint, never an ABI proof. */
#define TOOLTIP_ALLOCATOR_LOOKBACK 1024u
typedef struct TooltipAllocatorPrepared {const BYTE *target;void *trampoline;DWORD status;BOOL attempted;} TooltipAllocatorPrepared;
typedef DWORD (*TooltipAllocatorCreate)(const BYTE *,void **);
static BOOL tooltip_allocator_owner(const ImageView *view,const BYTE *target) {
    ULONG64 base=0;PRUNTIME_FUNCTION entry=RtlLookupFunctionEntry((DWORD64)(uintptr_t)target,&base,NULL);
    /* Assignment's first unwind fragment is25bytes, not the203signature size. */
    return entry && (const BYTE *)(uintptr_t)base==view->base &&
        entry->BeginAddress<entry->EndAddress && entry->EndAddress<=view->size &&
        view->base+entry->BeginAddress==target && executable(view,view->base+entry->EndAddress-1);
}
static BOOL tooltip_allocator_valid(const ImageView *view,const BYTE *target) {
    return in_image(view,target,sizeof(data_assign_bytes)) &&
        (section_flags(view,target,sizeof(data_assign_bytes))&IMAGE_SCN_MEM_EXECUTE)!=0 &&
        signature_at(view,target,data_assign_bytes,data_assign_mask,sizeof(data_assign_bytes)) && tooltip_allocator_owner(view,target);
}
static DWORD tooltip_allocator_find(const ImageView *view,const BYTE *serializer,const BYTE **out) {
    BYTE copy[TOOLTIP_ALLOCATOR_LOOKBACK];SIZE_T size,i;uintptr_t page,begin;DWORD matches=0;
    *out=NULL;
    if(!in_image(view,serializer,1) || !executable(view,serializer))return ERROR_INVALID_DATA;
    page=(uintptr_t)serializer&~(uintptr_t)4095u;
    begin=(uintptr_t)serializer>TOOLTIP_ALLOCATOR_LOOKBACK?(uintptr_t)serializer-TOOLTIP_ALLOCATOR_LOOKBACK:0;
    if(begin<page)begin=page;if(begin<(uintptr_t)view->base)begin=(uintptr_t)view->base;
    size=(uintptr_t)serializer-begin;
    if(size<sizeof(data_assign_bytes) || !in_image(view,(const BYTE *)begin,size) ||
       !(section_flags(view,(const BYTE *)begin,size)&IMAGE_SCN_MEM_EXECUTE))return ERROR_NOT_FOUND;
    if(!read_exact((const BYTE *)begin,copy,size))return ERROR_NOT_READY;
    for(i=0;i+sizeof(data_assign_bytes)<=size;i++) {
        const BYTE *candidate=(const BYTE *)begin+i;
        if(copy[i]!=data_assign_bytes[0] || !masked_match(copy+i,data_assign_bytes,data_assign_mask,sizeof(data_assign_bytes)))continue;
        if(!tooltip_allocator_valid(view,candidate))continue;
        *out=candidate;if(++matches>1){*out=NULL;return ERROR_DUP_NAME;}
    }
    return matches==1?ERROR_SUCCESS:ERROR_NOT_FOUND;
}
/* A single stable trampoline, even if both independent routes request it.
   A different target may never replace the function already published. */
static DWORD tooltip_allocator_create_once(TooltipAllocatorPrepared *state,const BYTE *target,TooltipAllocatorCreate create) {
    if(state->attempted)return state->target==target?state->status:ERROR_INVALID_DATA;
    if(!target || !create)return ERROR_INVALID_PARAMETER;
    state->attempted=TRUE;state->target=target;state->status=create(target,&state->trampoline);
    if(!state->status && !state->trampoline)state->status=ERROR_INVALID_DATA;
    return state->status;
}
