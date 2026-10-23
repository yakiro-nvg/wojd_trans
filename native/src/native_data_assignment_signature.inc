/* The allocator is validated before patching. Discovery after early enable
 * must accept only the exact entry patch owned by this detour, rather than
 * comparing that patch with pristine game bytes or skipping validation. */
typedef struct AssignmentSignature {
    const BYTE *target;
    BYTE original[sizeof(data_assign_bytes)],patched[sizeof(data_assign_bytes)],mask[sizeof(data_assign_bytes)];
    volatile LONG ready;
} AssignmentSignature;
static AssignmentSignature g_assignment_signature;
static BOOL assignment_jump_owned(const BYTE *target,const BYTE *bytes,const void *detour,DWORD *size) {
    uintptr_t destination;LONG offset;BYTE relay[14];
    if(bytes[0]==0xff && bytes[1]==0x25 && !memcmp(bytes+2,"\0\0\0\0",4)) {
        memcpy(&destination,bytes+6,sizeof(destination));*size=14;return destination==(uintptr_t)detour;
    }
    if(bytes[0]!=0xe9)return FALSE;
    memcpy(&offset,bytes+1,4);destination=(uintptr_t)(target+5)+offset;*size=5;
    if(destination==(uintptr_t)detour)return TRUE;
    if(!read_exact((const void *)destination,relay,sizeof(relay)) || relay[0]!=0xff || relay[1]!=0x25 ||
       memcmp(relay+2,"\0\0\0\0",4))return FALSE;
    memcpy(&destination,relay+6,sizeof(destination));return destination==(uintptr_t)detour;
}
static DWORD assignment_signature_record(const BYTE *target,const void *detour) {
    BYTE bytes[sizeof(data_assign_bytes)];DWORD size;
    if(!masked_match(g_assignment_signature.original,data_assign_bytes,data_assign_mask,sizeof(data_assign_bytes)))return ERROR_INVALID_DATA;
    if(!read_exact(target,bytes,sizeof(bytes)))return ERROR_NOT_READY;
    if(!assignment_jump_owned(target,bytes,detour,&size) ||
       memcmp(bytes+size,g_assignment_signature.original+size,sizeof(bytes)-size))return ERROR_INVALID_DATA;
    g_assignment_signature.target=target;memcpy(g_assignment_signature.patched,bytes,sizeof(bytes));
    memset(g_assignment_signature.mask,0xff,sizeof(bytes));InterlockedExchange(&g_assignment_signature.ready,1);
    return ERROR_SUCCESS;
}
static BOOL assignment_signature_at_report(const ImageView *view,const BYTE *target,MemoryProbe *probe) {
    if(InterlockedCompareExchange(&g_assignment_signature.ready,0,0) && target==g_assignment_signature.target)
        return signature_at_report(view,target,g_assignment_signature.patched,g_assignment_signature.mask,sizeof(data_assign_bytes),probe);
    return signature_at_report(view,target,data_assign_bytes,data_assign_mask,sizeof(data_assign_bytes),probe);
}
