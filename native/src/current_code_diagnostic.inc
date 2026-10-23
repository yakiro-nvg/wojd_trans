/* INERT SOURCE PROPOSAL; never built/run. Include AFTER native_tooltip_capture.inc.
   Optional user-run calibration only; production default is OFF.
   Reads only selected own-main-module code/header/unwind metadata via existing
   read_exact. Does not emit raw bytes, dereference game objects or install hooks. */
#ifndef WOJD_CURRENT_CODE_DIAGNOSTIC
#define WOJD_CURRENT_CODE_DIAGNOSTIC 0
#endif
#if WOJD_CURRENT_CODE_DIAGNOSTIC
#if WOJD_CAPTURE || WOJD_SELFTEST
#error Metadata-only calibration requires runtime profile, WOJD_CAPTURE=0, WOJD_SELFTEST=0
#endif
#include <bcrypt.h>
#pragma comment(lib,"bcrypt.lib")
#define CD_PHASES 2u
#define CD_WINDOWS 48u
#define CD_BYTE_LIMIT 32768u
#define CD_STEP_LIMIT 128u
#define CD_STEP_BYTES 4096u
#define CD_RECORD_LIMIT 272u
typedef struct CodeDiagWindow {
    DWORD rva,size; const BYTE *bytes,*mask; BOOL context;
} CodeDiagWindow;
typedef struct CodeDiagState {
    BOOL started,done,budget_exhausted; DWORD phase,index,steps,bytes,step_bytes,records;
    BOOL faulted,fault_log_failed,fault_quarantined; DWORD exception_code;
    DWORD exception_rva,exception_size;
    ImageView view; BCRYPT_ALG_HANDLE algorithm; BYTE object[8192]; DWORD object_size;
    BYTE first_digest[256][32]; DWORD first_rva[256],first_size[256];
    BOOL first_valid[256]; BYTE *raw_anchor;
} CodeDiagState;
static CodeDiagState g_code_diag;
static void code_diag_raw_anchor(const BYTE *raw) {g_code_diag.raw_anchor=(BYTE *)raw;}
static BOOL code_diag_record(void) {
    if(g_code_diag.records>=CD_RECORD_LIMIT)return FALSE;
    g_code_diag.records++;return TRUE;
}
/* A catchable diagnostic fault must never re-enter an unwinder/provider that
   may have faulted part way through an operation. Quarantine its one-shot
   diagnostic state; do not retry close/destroy/zero of possibly in-use state.
   Resource release is UNPROVEN until process exit, not claimed successful. */
static void code_diag_fault_stop(DWORD exception_code) {
    g_code_diag.faulted=TRUE;g_code_diag.done=TRUE;
    g_code_diag.exception_code=exception_code;g_code_diag.fault_quarantined=TRUE;
    __try {
        if(code_diag_record())logf_n4("CODE_DIAG_FAULT","exception=%08lx terminal=1 sticky=1 result=UNPROVEN diagnostic_reads_disabled=1 resources_quarantined=1 cleanup_proven=0 coverage=UNPROVEN current_profile=UNRESOLVED",exception_code);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        /* No second logger, cleanup API, recursion or retry after this fault. */
        g_code_diag.fault_log_failed=TRUE;
    }
}
static void code_diag_stop(const char *reason) {
    if(g_code_diag.done)return;
    g_code_diag.done=TRUE;
    if(code_diag_record())logf_n4("CODE_DIAG_END","reason=%s phase=%lu requested_bytes=%lu steps=%lu attempted_records=%lu coverage=UNPROVEN current_profile=UNRESOLVED no_hook_targets_enabled=1 raw_bytes_emitted=0",reason,g_code_diag.phase,g_code_diag.bytes,g_code_diag.steps,g_code_diag.records);
    if(g_code_diag.algorithm){BCryptCloseAlgorithmProvider(g_code_diag.algorithm,0);g_code_diag.algorithm=NULL;}
    SecureZeroMemory(g_code_diag.object,sizeof(g_code_diag.object));
}
static BOOL code_diag_read(DWORD rva,void *out,DWORD n,BOOL header) {
    if(g_code_diag.faulted || g_code_diag.done)return FALSE;
    if(!n || n>CD_STEP_BYTES || n>CD_BYTE_LIMIT-g_code_diag.bytes ||
       n>CD_STEP_BYTES-g_code_diag.step_bytes){g_code_diag.budget_exhausted=TRUE;return FALSE;}
    if(header){if(rva || n!=4096u)return FALSE;}
    else if(rva>g_code_diag.view.size || n>g_code_diag.view.size-rva)return FALSE;
    /* Charge requested bytes even when the safe read fails. OS API internal
       metadata/crypto costs are not represented as measured process I/O. */
    g_code_diag.bytes+=n;g_code_diag.step_bytes+=n;
    return read_exact(g_image_base+rva,out,n);
}
static BOOL code_diag_hash(const BYTE *bytes,DWORD n,BYTE digest[32]) {
    BCRYPT_HASH_HANDLE hash=NULL;NTSTATUS status;
    if(g_code_diag.faulted || g_code_diag.done)return FALSE;
    status=BCryptCreateHash(g_code_diag.algorithm,&hash,g_code_diag.object,g_code_diag.object_size,NULL,0,0);
    if(status<0)return FALSE;
    status=BCryptHashData(hash,(PUCHAR)bytes,n,0);
    if(status>=0)status=BCryptFinishHash(hash,digest,32,0);
    BCryptDestroyHash(hash);return status>=0;
}
static BOOL code_diag_fingerprint(DWORD id,DWORD rva,DWORD n,const BYTE *bytes,char hex[65],BOOL *pair_equal) {
    static const char digits[]="0123456789abcdef";BYTE digest[32];DWORD i;
    if(id>=256u || !code_diag_hash(bytes,n,digest))return FALSE;
    for(i=0;i<32u;i++){hex[2u*i]=digits[digest[i]>>4];hex[2u*i+1u]=digits[digest[i]&15u];}hex[64]=0;
    *pair_equal=FALSE;
    if(g_code_diag.phase==1u){
        memcpy(g_code_diag.first_digest[id],digest,32);g_code_diag.first_rva[id]=rva;
        g_code_diag.first_size[id]=n;g_code_diag.first_valid[id]=TRUE;
    }else if(g_code_diag.first_valid[id]){
        *pair_equal=g_code_diag.first_rva[id]==rva && g_code_diag.first_size[id]==n &&
            !memcmp(g_code_diag.first_digest[id],digest,32);
    }
    SecureZeroMemory(digest,sizeof(digest));return TRUE;
}
static BOOL code_diag_header(void) {
    BYTE bytes[4096];IMAGE_DOS_HEADER dos;IMAGE_NT_HEADERS64 nt;SIZE_T table;
    DWORD i;char hex[65];BOOL equal=FALSE;ImageView next;
    if(!code_diag_read(0,bytes,sizeof(bytes),TRUE))return FALSE;
    memcpy(&dos,bytes,sizeof(dos));
    if(dos.e_magic!=IMAGE_DOS_SIGNATURE || dos.e_lfanew<64 || dos.e_lfanew>2048)return FALSE;
    if((SIZE_T)dos.e_lfanew+sizeof(nt)>sizeof(bytes))return FALSE;
    memcpy(&nt,bytes+dos.e_lfanew,sizeof(nt));
    if(nt.Signature!=IMAGE_NT_SIGNATURE || nt.FileHeader.Machine!=IMAGE_FILE_MACHINE_AMD64 ||
       nt.OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC ||
       nt.FileHeader.SizeOfOptionalHeader<sizeof(IMAGE_OPTIONAL_HEADER64) ||
       !nt.FileHeader.NumberOfSections || nt.FileHeader.NumberOfSections>96 ||
       !nt.OptionalHeader.SizeOfImage || nt.OptionalHeader.SizeOfImage>512u*1024u*1024u ||
       nt.OptionalHeader.NumberOfRvaAndSizes<=IMAGE_DIRECTORY_ENTRY_EXCEPTION)return FALSE;
    table=(SIZE_T)dos.e_lfanew+24u+nt.FileHeader.SizeOfOptionalHeader;
    if(table>sizeof(bytes) || nt.FileHeader.NumberOfSections>(sizeof(bytes)-table)/sizeof(IMAGE_SECTION_HEADER))return FALSE;
    ZeroMemory(&next,sizeof(next));next.base=g_image_base;next.size=nt.OptionalHeader.SizeOfImage;
    next.section_count=nt.FileHeader.NumberOfSections;
    memcpy(next.sections,bytes+table,next.section_count*sizeof(IMAGE_SECTION_HEADER));
    for(i=0;i<next.section_count;i++){
        DWORD len=next.sections[i].Misc.VirtualSize;
        if(next.sections[i].SizeOfRawData>len)len=next.sections[i].SizeOfRawData;
        if(next.sections[i].VirtualAddress>next.size || len>next.size-next.sections[i].VirtualAddress)return FALSE;
    }
    g_code_diag.view=next;
    g_code_diag.exception_rva=nt.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXCEPTION].VirtualAddress;
    g_code_diag.exception_size=nt.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXCEPTION].Size;
    if(g_code_diag.exception_rva>next.size || g_code_diag.exception_size>next.size-g_code_diag.exception_rva)return FALSE;
    if(!code_diag_fingerprint(0,0,sizeof(bytes),bytes,hex,&equal))return FALSE;
    SecureZeroMemory(bytes,sizeof(bytes));
    if(code_diag_record())logf_n4("CODE_DIAG_HEADER","phase=%lu timestamp=%08lx image_size=%08lx header_sha256=%s observed_pair_equal=%u global_generation_proven=0 typed_guard_retained=1",g_code_diag.phase,nt.FileHeader.TimeDateStamp,next.size,hex,equal);
    return TRUE;
}
static BOOL code_diag_unwind(DWORD rva,DWORD *begin,DWORD *end) {
    ULONG64 owner=0;PRUNTIME_FUNCTION p;RUNTIME_FUNCTION entry;uintptr_t offset;
    *begin=0;*end=0;
    if(g_code_diag.faulted || g_code_diag.done)return FALSE;
    p=RtlLookupFunctionEntry((DWORD64)(uintptr_t)(g_image_base+rva),&owner,NULL);
    if(!p || (BYTE *)(uintptr_t)owner!=g_image_base || (uintptr_t)p<(uintptr_t)g_image_base)return FALSE;
    offset=(uintptr_t)p-(uintptr_t)g_image_base;
    if(offset>MAXDWORD || offset<g_code_diag.exception_rva ||
       offset-g_code_diag.exception_rva>g_code_diag.exception_size ||
       sizeof(entry)>g_code_diag.exception_size-(offset-g_code_diag.exception_rva) ||
       !code_diag_read((DWORD)offset,&entry,sizeof(entry),FALSE))return FALSE;
    if(entry.BeginAddress>rva || entry.EndAddress<=rva || entry.EndAddress>g_code_diag.view.size)return FALSE;
    *begin=entry.BeginAddress;*end=entry.EndAddress;return TRUE;
}
static BOOL code_diag_anchor_rva(const void *anchor,DWORD *rva) {
    uintptr_t base=(uintptr_t)g_image_base,point=(uintptr_t)anchor;
    if(point<base || point-base>MAXDWORD || point-base>=g_code_diag.view.size)return FALSE;
    *rva=(DWORD)(point-base);return TRUE;
}
static BOOL code_diag_selected(DWORD index,CodeDiagWindow *out) {
    const WojdNativeUobjectSiteContext *context;
    ZeroMemory(out,sizeof(*out));
    if(index==0u){out->rva=WOJD_FSTRING_SERIALIZER_RVA;out->size=48u;out->bytes=WOJD_FSTRING_SERIALIZER_BYTES48;out->mask=WOJD_FSTRING_SERIALIZER_MASK48;}
    else if(index==1u){out->rva=WOJD_TOOLTIP_LOADER_RVA;out->size=48u;out->bytes=WOJD_TOOLTIP_LOADER_BYTES48;out->mask=WOJD_TOOLTIP_LOADER_MASK48;}
    else if(index==2u || index==5u){if(index==2u)out->rva=0x2bb5610u;else if(!code_diag_anchor_rva(g_decoder_reader,&out->rva))return FALSE;out->size=sizeof(data_reader_bytes);out->bytes=data_reader_bytes;out->mask=data_reader_mask;}
    else if(index==3u || index==6u){if(index==3u)out->rva=0x495b590u;else if(!code_diag_anchor_rva(g_target,&out->rva))return FALSE;out->size=sizeof(data_assign_bytes);out->bytes=data_assign_bytes;out->mask=data_assign_mask;}
    else if(index==4u || index==7u){if(index==4u)out->rva=0x2bb4d50u;else if(!code_diag_anchor_rva(g_code_diag.raw_anchor,&out->rva))return FALSE;out->size=sizeof(data_read_bytes_bytes);out->bytes=data_read_bytes_bytes;out->mask=data_read_bytes_mask;}
    else{
        index-=8u;
        if(index<WOJD_PLAIN_SITE_CONTEXT_COUNT)context=WOJD_PLAIN_SITE_CONTEXTS+index;
        else{index-=WOJD_PLAIN_SITE_CONTEXT_COUNT;if(index>=WOJD_NATIVE_UOBJECT_FIELD_SITE_COUNT)return FALSE;context=WOJD_NATIVE_UOBJECT_SITE_CONTEXTS+index;}
        out->rva=context->context_rva;out->size=context->size;out->bytes=context->bytes;out->mask=context->mask;out->context=TRUE;
    }
    return out->size && out->size<=1024u;
}
static BOOL code_diag_probe(DWORD id,const CodeDiagWindow *window,BOOL follow_context) {
    BYTE bytes[1024];char hex[65];BOOL same=FALSE,match,unwind;DWORD begin=0,end=0;
    if(window->rva>g_code_diag.view.size || window->size>g_code_diag.view.size-window->rva ||
       !(section_flags(&g_code_diag.view,g_image_base+window->rva,window->size)&IMAGE_SCN_CNT_CODE) ||
       !executable(&g_code_diag.view,g_image_base+window->rva) ||
       !code_diag_read(window->rva,bytes,window->size,FALSE))return FALSE;
    if(!code_diag_fingerprint(id,window->rva,window->size,bytes,hex,&same))return FALSE;
    match=masked_match(bytes,window->bytes,window->mask,window->size);
    unwind=code_diag_unwind(window->rva,&begin,&end);
    if(code_diag_record())logf_n4("CODE_DIAG_WINDOW","phase=%lu id=%lu rva=%08lx n=%lu sha256=%s historical_mask_match=%u unwind_present=%u unwind_begin=%08lx unwind_end=%08lx observed_pair_equal=%u assignment_entry_instrumented=%u profile_approved=0",g_code_diag.phase,id,window->rva,window->size,hex,match,unwind,begin,end,same,g_image_base+window->rva==(BYTE *)g_target);
    if(follow_context && window->context && match && window->size>=5u && bytes[window->size-5u]==0xe8){
        LONG displacement;LONGLONG target;CodeDiagWindow candidate;
        memcpy(&displacement,bytes+window->size-4u,sizeof(displacement));
        target=(LONGLONG)window->rva+window->size+(LONGLONG)displacement;
        if(target>=0 && target<=MAXDWORD){
            candidate.rva=(DWORD)target;candidate.size=48u;candidate.bytes=WOJD_FSTRING_SERIALIZER_BYTES48;
            candidate.mask=WOJD_FSTRING_SERIALIZER_MASK48;candidate.context=FALSE;
            if(code_diag_record())logf_n4("CODE_DIAG_E8_CANDIDATE","phase=%lu context_id=%lu target_rva=%08lx target_is_data_only=1 hook_target_approved=0",g_code_diag.phase,id,candidate.rva);
            if(!code_diag_probe(128u+id,&candidate,FALSE)){
                if(code_diag_record())logf_n4("CODE_DIAG_TARGET_UNPROVEN","phase=%lu context_id=%lu target_rva=%08lx reason=bounded_code_read_or_hash_unavailable",g_code_diag.phase,id,candidate.rva);
            }
        }
    }
    SecureZeroMemory(bytes,sizeof(bytes));return TRUE;
}
static void code_diag_step_impl(void) {
    CodeDiagWindow window;DWORD bytes=0;NTSTATUS status;
    if(g_code_diag.done)return;
    /* Existing independently validated generic origin is a calibration phase
       signal, not proof that every typed function has finished loading. */
    if(!g_game_host || !InterlockedCompareExchange(&g_active,0,0) ||
       !InterlockedCompareExchange(&g_origin_verified,0,0) || !g_wide_ready ||
       g_tooltip_active || g_tooltip_pending || g_tooltip_install_error!=ERROR_REVISION_MISMATCH){
        if(g_code_diag.started)code_diag_stop("CALIBRATION_READINESS_LOST");
        return;
    }
    if(!g_code_diag.started){
        g_code_diag.started=TRUE;g_code_diag.phase=1u;
        if(WOJD_PLAIN_SITE_CONTEXT_COUNT!=15u || WOJD_NATIVE_UOBJECT_FIELD_SITE_COUNT!=25u ||
           WOJD_TOOLTIP_FIELD_SITE_COUNT!=25u){code_diag_stop("FINITE_PLAN_COUNT_MISMATCH");return;}
        status=BCryptOpenAlgorithmProvider(&g_code_diag.algorithm,BCRYPT_SHA256_ALGORITHM,NULL,0);
        if(status<0){code_diag_stop("HASH_PROVIDER_UNAVAILABLE");return;}
        status=BCryptGetProperty(g_code_diag.algorithm,BCRYPT_OBJECT_LENGTH,(PUCHAR)&g_code_diag.object_size,sizeof(g_code_diag.object_size),&bytes,0);
        if(status<0 || bytes!=sizeof(g_code_diag.object_size) || !g_code_diag.object_size || g_code_diag.object_size>sizeof(g_code_diag.object)){code_diag_stop("HASH_OBJECT_BOUND");return;}
        if(code_diag_record())logf_n4("CODE_DIAG_BEGIN","mode=USER_RUN_CALIBRATION only_own_main_module=1 old_guard_error=%lu old_typed_active=0 generic_origin_verified=1 coverage=UNPROVEN global_generation_proven=0 byte_limit=%u step_limit=%u",g_tooltip_install_error,CD_BYTE_LIMIT,CD_STEP_LIMIT);
    }
    if(g_code_diag.steps>=CD_STEP_LIMIT){code_diag_stop("STEP_BUDGET");return;}
    g_code_diag.steps++;g_code_diag.step_bytes=0;
    if(!g_code_diag.index){
        if(!code_diag_header()){code_diag_stop(g_code_diag.budget_exhausted?"BYTE_BUDGET":"HEADER_UNPROVEN");return;}
        g_code_diag.index=1u;return; /* Existing outer worker must yield. */
    }
    if(g_code_diag.index<=CD_WINDOWS){
        if(!code_diag_selected(g_code_diag.index-1u,&window)){code_diag_stop("FINITE_PLAN_INVALID");return;}
        if(!code_diag_probe(g_code_diag.index,&window,TRUE)){
            if(code_diag_record())logf_n4("CODE_DIAG_WINDOW_UNPROVEN","phase=%lu id=%lu rva=%08lx n=%lu",g_code_diag.phase,g_code_diag.index,window.rva,window.size);
        }
        if(g_code_diag.budget_exhausted){code_diag_stop("BYTE_BUDGET");return;}
        g_code_diag.index++;return; /* No scan; one selected window per worker yield. */
    }
    if(g_code_diag.phase<CD_PHASES){g_code_diag.phase++;g_code_diag.index=0;return;}
    code_diag_stop("FINITE_PLAN_COMPLETE_MAPPING_STILL_UNRESOLVED");
}
static void code_diag_step(void) {
    DWORD saved=GetLastError();
    __try {
        __try {
            if(!g_code_diag.faulted && !g_code_diag.done)code_diag_step_impl();
        } __except(EXCEPTION_EXECUTE_HANDLER) {
            code_diag_fault_stop(GetExceptionCode());
        }
    } __finally {
        /* Applies to ordinary return and the contained diagnostic fault path. */
        SetLastError(saved);
    }
}
#else
#define code_diag_raw_anchor(raw) ((void)0)
#define code_diag_step() ((void)0)
#endif
