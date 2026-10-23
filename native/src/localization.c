#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
#include <intrin.h>
#include "../vendor/minhook/include/MinHook.h"
#ifndef WOJD_CAPTURE
#define WOJD_CAPTURE 0
#endif
#ifndef WOJD_SELFTEST
#define WOJD_SELFTEST 0
#endif
#include "portable_paths.h"
#define GAME_EXE g_host_path
#define MARKER g_bootstrap_path
#define SELFTEST_OBSERVATIONS g_selftest_path
#define TEXT_CATALOG g_catalog_path
#define READER_CACHE g_cache_path
#define STOP_FILE g_stop_path
#define SCAN_CHUNK (1024u*1024u)
#define DUMP_LIMIT (128u*1024u*1024u)
#define QUEUE_LIMIT (8u*1024u*1024u)
#define SEEN_BUCKETS 32768u
typedef struct ImageView { BYTE *base;DWORD size;WORD section_count;IMAGE_SECTION_HEADER sections[96]; } ImageView;
typedef struct GameString { WCHAR *data;int count,capacity; } GameString;
typedef BYTE (__fastcall *ReadStringFn)(void *,GameString *,DWORD);
typedef GameString *(__fastcall *AssignFn)(GameString *,const WCHAR *);
typedef struct DataResult { DWORD status,candidates;ULONGLONG reader,assign,raw_reader; } DataResult;
typedef struct DataStatus { LONG calls,failed,strings,translated,unknown,invalid,exceptions,dropped;DWORD restored; } DataStatus;
static volatile LONG g_active;
static volatile LONG g_force_far;
static BOOL g_prefer_far;
static BOOL g_game_host;static HMODULE g_module;
static AssignFn g_original_assign,g_assign;static void *g_target;
static BYTE *g_decoder_reader,*g_decoder_return;
static volatile LONG g_origin_verified,g_origin_rejected;

static DataStatus g_status;
static BYTE *g_image_base;
#include "native_session_logging.h"
static NativeSession g_session;
static volatile LONG g_session_ready;
#include "archive_start.inc"
static void logf_n4(const char *event,const char *format,...) {
    char buffer[2048];SYSTEMTIME time;HANDLE file;va_list args;int prefix,count;DWORD written;
    GetSystemTime(&time);
    prefix=_snprintf_s(buffer,sizeof(buffer),_TRUNCATE,"WOJD_LOCALIZATION event=%s pid=%lu tid=%lu utc=%04u-%02u-%02uT%02u:%02u:%02uZ ",event,GetCurrentProcessId(),GetCurrentThreadId(),time.wYear,time.wMonth,time.wDay,time.wHour,time.wMinute,time.wSecond);
    if(prefix<0)return;
    va_start(args,format);count=_vsnprintf_s(buffer+prefix,sizeof(buffer)-(SIZE_T)prefix-3,_TRUNCATE,format,args);va_end(args);
    if(count<0)count=(int)strlen(buffer+prefix);buffer[prefix+count]='\r';buffer[prefix+count+1]='\n';
    file=CreateFileW(g_game_host && g_session_ready?g_session.marker:MARKER,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE)return;WriteFile(file,buffer,(DWORD)(prefix+count+2),&written,NULL);CloseHandle(file);
}
#include "native_data_memory.inc"
#include "native_data_signatures.h"
#include "native_data_catalog.inc"
static LARGE_INTEGER g_diag_frequency,g_diag_attach;
static ULONGLONG diag_ticks(void){LARGE_INTEGER value;QueryPerformanceCounter(&value);return (ULONGLONG)value.QuadPart;}
static ULONGLONG diag_us(ULONGLONG ticks){return g_diag_frequency.QuadPart?((ticks/(ULONGLONG)g_diag_frequency.QuadPart)*1000000ull+(ticks%(ULONGLONG)g_diag_frequency.QuadPart)*1000000ull/(ULONGLONG)g_diag_frequency.QuadPart):0;}
static BOOL signature_at(const ImageView *view,const BYTE *address,const BYTE *expected,const BYTE *mask,SIZE_T n){
    BYTE bytes[1024];return n<=sizeof(bytes) && in_image(view,address,n) && executable(view,address) && read_exact(address,bytes,n) && masked_match(bytes,expected,mask,n);
}
#include "native_data_probe_diagnostics.inc"
static void (*g_discovery_pump)(void);
#include "native_data_assignment_signature.inc"
#include "native_data_resolver.inc"
#include "native_data_cache.inc"
#include "native_data_origin_gate.inc"
#include "native_data_executing_origin.inc"

enum { DECISION_TRANSLATED=1,DECISION_IGNORE=2 };
typedef struct WideRule { WCHAR *source,*target;int source_length;DWORD decision;const TextRule *rule; } WideRule;
static volatile LONG g_ignored;
static WideRule *g_wide;static DWORD g_wide_count;
static WCHAR *g_wide_arena;static BOOL g_wide_ready;
static int wide_compare(const void *a,const void *b) {return wcscmp(((const WideRule *)a)->source,((const WideRule *)b)->source);}
static DWORD prepare_wide(void) {
    DWORD i,count=0,field=catalog_field("NativeString"),ignore=catalog_field("NativeIgnore");SIZE_T characters=0;
    WideRule *next;WCHAR *arena,*cursor;
    if(g_wide_ready)return ERROR_SUCCESS;
    if(field==MAXDWORD)return ERROR_INVALID_DATA;
    for(i=0;i<g_catalog.rule_count;i++) {
        const TextRule *r=&g_catalog.rules[i];int sn,tn;
        if(r->field!=field && r->field!=ignore)continue;
        if((r->field==field)!=!!r->target_length)return ERROR_INVALID_DATA;
        sn=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,r->source,(int)r->source_length,NULL,0);
        tn=r->target_length?MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,r->target,(int)r->target_length,NULL,0):0;
        if(sn<1 || (r->target_length && tn<1))return ERROR_INVALID_DATA;
        characters+=(SIZE_T)sn+(SIZE_T)tn+2;count++;
    }
    next=(WideRule *)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,(count?count:1)*sizeof(WideRule));
    if(!next)return ERROR_NOT_ENOUGH_MEMORY;
    arena=(WCHAR *)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,(characters?characters:1)*sizeof(WCHAR));
    if(!arena){HeapFree(GetProcessHeap(),0,next);return ERROR_NOT_ENOUGH_MEMORY;}
    cursor=arena;count=0;
    for(i=0;i<g_catalog.rule_count;i++) {
        const TextRule *r=&g_catalog.rules[i];WideRule *w;int sn,tn;
        if(r->field!=field && r->field!=ignore)continue;
        sn=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,r->source,(int)r->source_length,NULL,0);
        tn=r->target_length?MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,r->target,(int)r->target_length,NULL,0):0;
        w=&next[count++];w->source=cursor;w->source_length=sn;w->rule=r;
        w->decision=r->field==field?DECISION_TRANSLATED:DECISION_IGNORE;
        if(MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,r->source,(int)r->source_length,cursor,sn)!=sn)goto fail;
        cursor+=sn+1;w->target=cursor;
        if(tn && MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,r->target,(int)r->target_length,cursor,tn)!=tn)goto fail;
        cursor+=tn+1;
    }
    qsort(next,count,sizeof(WideRule),wide_compare);
    for(i=1;i<count;i++)if(!wcscmp(next[i-1].source,next[i].source))goto fail;
    g_wide=next;g_wide_count=count;g_wide_arena=arena;g_wide_ready=TRUE;
#if !WOJD_CAPTURE
    for(i=0;i<count;i++)next[i].rule=NULL;
    catalog_free(&g_catalog);
#endif
    return ERROR_SUCCESS;
fail:
    HeapFree(GetProcessHeap(),0,arena);HeapFree(GetProcessHeap(),0,next);return ERROR_INVALID_DATA;
}
static const WideRule *lookup_wide(const WCHAR *source,int n) {
    DWORD lo=0,hi=g_wide_count;
    while(lo<hi) {DWORD mid=lo+(hi-lo)/2;int cmp=wcscmp(source,g_wide[mid].source);
        if(!cmp)return n==g_wide[mid].source_length?&g_wide[mid]:NULL;
        if(cmp<0)hi=mid;else lo=mid+1;
    }return NULL;
}
#if WOJD_CAPTURE
typedef struct CaptureContext {
    const char *route,*field,*namespace_name,*typed_field,*object_layout;
    const char *processing_status;
    DWORD record_id,variant;BOOL has_variant,capture_only,translated;
} CaptureContext;
typedef struct DumpNode { struct DumpNode *next;DWORD size;char line[1]; } DumpNode;
typedef struct SeenNode { struct SeenNode *next;ULONGLONG hash,caller;DWORD key,length,record_id,variant;BOOL observation;const char *processing_status;WCHAR source[1]; } SeenNode;
static SRWLOCK g_dump_lock=SRWLOCK_INIT;
static DumpNode *g_queue_head,*g_queue_tail;static SIZE_T g_queue_bytes,g_dump_bytes,g_seen_bytes;
static SeenNode *g_seen[SEEN_BUCKETS];static HANDLE g_writer,g_dump_event;static volatile LONG g_writer_stop;
static SIZE_T json_text(char *out,const char *source,SIZE_T length) {
    static const char hex[]="0123456789abcdef";SIZE_T n=0,i;out[n++]='"';
    for(i=0;i<length;i++) {unsigned char c=(unsigned char)source[i];
        if(c=='"' || c=='\\'){out[n++]='\\';out[n++]=(char)c;}
        else if(c<32){out[n++]='\\';out[n++]='u';out[n++]='0';out[n++]='0';out[n++]=hex[c>>4];out[n++]=hex[c&15];}
        else out[n++]=(char)c;
    }out[n++]='"';return n;
}
static BOOL capture_string(const GameString *s,DWORD key,void *caller,const WideRule *translation,const CaptureContext *context) {
    SeenNode *seen;DumpNode *node;SIZE_T n,capacity;ULONGLONG hash=1469598103934665603ull,where=(ULONGLONG)(uintptr_t)caller;unsigned bucket;int i,bytes;
    BOOL wake;char *utf8;ULONGLONG source_hash;const TextRule *rule=translation && translation->decision==DECISION_TRANSLATED && (!context || context->translated)?translation->rule:NULL;
    const char *decision=!translation?"missing":(translation->decision==DECISION_TRANSLATED?"translated":"ignore");
    for(i=0;i<s->count-1;i++){hash^=s->data[i];hash*=1099511628211ull;}
    source_hash=hash;hash^=key;hash*=1099511628211ull;hash^=where;
    if(context){hash^=context->record_id;hash*=1099511628211ull;hash^=context->variant;hash*=1099511628211ull;}
    bucket=(unsigned)hash&(SEEN_BUCKETS-1);
    AcquireSRWLockExclusive(&g_dump_lock);
    for(seen=g_seen[bucket];seen;seen=seen->next)if(seen->hash==hash && seen->key==key && seen->caller==where && seen->observation==!!context && (!context || (seen->record_id==context->record_id && seen->variant==context->variant && !strcmp(seen->processing_status,context->processing_status))) && seen->length==(DWORD)(s->count-1) && !memcmp(seen->source,s->data,(SIZE_T)(s->count-1)*2)){ReleaseSRWLockExclusive(&g_dump_lock);return FALSE;}
    if(g_dump_bytes>=DUMP_LIMIT || g_seen_bytes>=DUMP_LIMIT || g_queue_bytes>=QUEUE_LIMIT){ReleaseSRWLockExclusive(&g_dump_lock);InterlockedIncrement(&g_status.dropped);return FALSE;}
    bytes=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s->data,s->count-1,NULL,0,NULL,NULL);
    if(bytes<=0 || bytes>65535){ReleaseSRWLockExclusive(&g_dump_lock);return FALSE;}
    utf8=(char *)HeapAlloc(GetProcessHeap(),0,(SIZE_T)bytes);capacity=1024+6*((SIZE_T)bytes+(rule?rule->target_length:0));
    node=(DumpNode *)HeapAlloc(GetProcessHeap(),0,sizeof(DumpNode)+capacity);
    seen=(SeenNode *)HeapAlloc(GetProcessHeap(),0,sizeof(SeenNode)+(SIZE_T)(s->count-1)*2);
    if(!utf8 || !node || !seen){if(utf8)HeapFree(GetProcessHeap(),0,utf8);if(node)HeapFree(GetProcessHeap(),0,node);if(seen)HeapFree(GetProcessHeap(),0,seen);ReleaseSRWLockExclusive(&g_dump_lock);InterlockedIncrement(&g_status.dropped);return FALSE;}
    WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s->data,s->count-1,utf8,bytes,NULL,NULL);
    n=(SIZE_T)_snprintf_s(node->line,capacity,_TRUNCATE,"{\"pid\":%lu,\"tid\":%lu,\"route\":\"%s\",\"field\":\"%s\",\"field_key_available\":false,\"key\":\"%08lx\",\"caller\":\"%p\",\"caller_rva\":\"%llx\",\"translated\":%s,\"status\":\"%s\",\"source_hash_u16\":\"%016llx\",",GetCurrentProcessId(),GetCurrentThreadId(),context?context->route:"native_data_decoder_assignment",context?context->field:"NativeDataString",key,caller,g_image_base?(ULONGLONG)((BYTE *)caller-g_image_base):0,rule?"true":"false",context?context->processing_status:decision,source_hash);
    if(context)n+=(SIZE_T)_snprintf_s(node->line+n,capacity-n,_TRUNCATE,"\"capture_only\":%s,\"origin_scope\":\"TYPED_DISPLAY_FIELD_SITE\",\"file_origin_available\":false,\"file_origin\":\"UNVERIFIED\",\"object_layout\":\"%s\",\"archive_completion\":\"UNVERIFIED\",\"namespace\":\"%s\",\"typed_field\":\"%s\",\"record_id\":%lu,\"variant\":%lu,\"variant_available\":%s,",context->capture_only?"true":"false",context->object_layout,context->namespace_name,context->typed_field,context->record_id,context->variant,context->has_variant?"true":"false");
    memcpy(node->line+n,"\"source\":",9);n+=9;
    n+=json_text(node->line+n,utf8,(SIZE_T)bytes);memcpy(node->line+n,",\"target\":",10);n+=10;
    n+=json_text(node->line+n,rule?rule->target:"",rule?rule->target_length:0);node->line[n++]='}';node->line[n++]='\n';
    HeapFree(GetProcessHeap(),0,utf8);
    if(g_dump_bytes+n>DUMP_LIMIT || g_queue_bytes+n>QUEUE_LIMIT){HeapFree(GetProcessHeap(),0,node);HeapFree(GetProcessHeap(),0,seen);ReleaseSRWLockExclusive(&g_dump_lock);InterlockedIncrement(&g_status.dropped);return FALSE;}
    seen->hash=hash;seen->key=key;seen->caller=where;seen->length=(DWORD)s->count-1;seen->observation=!!context;seen->processing_status=context?context->processing_status:NULL;seen->record_id=context?context->record_id:0;seen->variant=context?context->variant:0;memcpy(seen->source,s->data,(SIZE_T)(s->count-1)*2);seen->next=g_seen[bucket];g_seen[bucket]=seen;g_seen_bytes+=sizeof(SeenNode)+(SIZE_T)(s->count-1)*2;
    wake=g_queue_head==NULL;node->size=(DWORD)n;node->next=NULL;if(g_queue_tail)g_queue_tail->next=node;else g_queue_head=node;g_queue_tail=node;g_queue_bytes+=n;g_dump_bytes+=n;
    ReleaseSRWLockExclusive(&g_dump_lock);if(wake && g_dump_event)SetEvent(g_dump_event);return TRUE;
}
static DWORD WINAPI dump_worker(void *unused) {
    HANDLE file;DWORD written;DumpNode *list;(void)unused;
    if(g_game_host && !g_session_ready){InterlockedIncrement(&g_status.dropped);return ERROR_PATH_NOT_FOUND;}
    file=CreateFileW(g_game_host?g_session.observations:SELFTEST_OBSERVATIONS,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,g_game_host?CREATE_NEW:OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE){InterlockedIncrement(&g_status.dropped);return GetLastError();}
    for(;;) {
        AcquireSRWLockExclusive(&g_dump_lock);list=g_queue_head;g_queue_head=g_queue_tail=NULL;g_queue_bytes=0;ReleaseSRWLockExclusive(&g_dump_lock);
        if(!list && g_writer_stop)break;
        while(list){DumpNode *next=list->next;if(!WriteFile(file,list->line,list->size,&written,NULL) || written!=list->size)InterlockedIncrement(&g_status.dropped);HeapFree(GetProcessHeap(),0,list);list=next;}
        if(!g_writer_stop)WaitForSingleObject(g_dump_event,50);
    }FlushFileBuffers(file);CloseHandle(file);return ERROR_SUCCESS;
}
#else
static HANDLE g_writer;static volatile LONG g_writer_stop;
#endif
static BOOL is_resource(const WCHAR *s) {
    return !wcsncmp(s,L"/Game/",6) || !wcsncmp(s,L"/Script/",8) || !wcsncmp(s,L"Texture2D'",10) || !wcsncmp(s,L"Material'",9);
}
static void process_string(GameString *out,DWORD key,void *caller) {
    const WideRule *rule;int i;BOOL cjk=FALSE;
    if(!out || !out->data || out->count<=1)return;
    if(out->count>65536 || out->capacity<out->count || out->data[out->count-1]!=0){InterlockedIncrement(&g_status.invalid);return;}
#if WOJD_CAPTURE
    for(i=0;i<out->count-1;i++) {WCHAR c=out->data[i];if(!c){InterlockedIncrement(&g_status.invalid);return;}if((c>=0x3400 && c<=0x9fff) || (c>=0xf900 && c<=0xfaff))cjk=TRUE;}
    if(!cjk || is_resource(out->data))return;
#else
    (void)i;(void)cjk;
#endif
#if WOJD_CAPTURE
    InterlockedIncrement(&g_status.strings);
#endif
    rule=lookup_wide(out->data,out->count-1);
#if WOJD_CAPTURE
    capture_string(out,key,caller,rule,NULL);
#else
    (void)key;(void)caller;
#endif
    if(rule && rule->decision==DECISION_TRANSLATED) {
        g_assign(out,rule->target);
#if WOJD_CAPTURE
        {LONG number=InterlockedIncrement(&g_status.translated);
        if(number<=20)logf_n4("DATA_TRANSLATED","key=%08lx caller=%p source_bytes=%lu target_bytes=%lu",key,caller,rule->rule->source_length,rule->rule->target_length);}
#endif
    }
#if WOJD_CAPTURE
    else if(!rule)InterlockedIncrement(&g_status.unknown);
    else InterlockedIncrement(&g_ignored);
#endif
}
static GameString * __fastcall assignment_hook(GameString *out,const WCHAR *text){
    void *caller=_ReturnAddress();GameString *result;DWORD last_error;
    result=g_original_assign(out,text);last_error=GetLastError();
    if(!g_active || (g_game_host?!executing_origin(caller):caller!=g_decoder_return)){
        SetLastError(last_error);return result;
    }
#if WOJD_CAPTURE
    if(InterlockedIncrement(&g_status.calls)==1)logf_n4("FIRST_DECODED_ASSIGNMENT","attach_us=%llu original_first_call_unknown=1",diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart));
#endif
    __try{process_string(out,0,caller);}__except(EXCEPTION_EXECUTE_HANDLER){InterlockedIncrement(&g_status.exceptions);}
    SetLastError(last_error);return result;
}
static DWORD tooltip_prepare_for_serializer(const BYTE *serializer);
#include "native_tooltip_allocator.inc"
#include "native_tooltip_capture.inc"
#include "current_code_diagnostic.inc"
VOID WojdMhTrace(const char *event,const void *address,const void *result,SIZE_T size,DWORD error){
    (void)event;(void)address;(void)result;(void)size;(void)error;
}
static void trace_stage(const char *stage,MH_STATUS status,DWORD error){logf_n4("HOOK_STAGE","stage=%s status=%ld win32_error=%lu",stage,(LONG)status,error);}
BOOL WojdMhForceFarAllocation(VOID) {return g_game_host?g_prefer_far:InterlockedCompareExchange(&g_force_far,0,0)!=0;}
static DWORD runtime_initialize(void) {
    MH_STATUS status;
#if WOJD_CAPTURE
    if(!g_writer) {
        g_writer_stop=0;g_dump_event=CreateEventW(NULL,FALSE,FALSE,NULL);
        if(!g_dump_event)return GetLastError();
        g_writer=CreateThread(NULL,0,dump_worker,NULL,0,NULL);
        if(!g_writer){DWORD error=GetLastError();CloseHandle(g_dump_event);g_dump_event=NULL;return error;}
    }
#endif
    status=MH_Initialize();
    return status==MH_OK || status==MH_ERROR_ALREADY_INITIALIZED?ERROR_SUCCESS:(DWORD)status+0x10000;
}
static TooltipAllocatorPrepared g_tooltip_allocator_prepared;
static DWORD tooltip_allocator_create_runtime(const BYTE *assign,void **trampoline) {
    ULONGLONG phase=diag_ticks();MH_STATUS status=MH_CreateHook((void *)assign,(void *)(uintptr_t)assignment_hook,trampoline);
    trace_stage("create",status,GetLastError());logf_n4("PHASE_TIMING","phase=create us=%llu",diag_us(diag_ticks()-phase));
    return status==MH_OK?ERROR_SUCCESS:(DWORD)status+0x10000;
}
static DWORD enable_assignment(void) {
    MH_STATUS status;DWORD error;ULONGLONG phase;
    if(g_active)return ERROR_SUCCESS;
    if(!g_target || !g_original_assign)return ERROR_INVALID_STATE;
    phase=diag_ticks();InterlockedExchange(&g_active,1);status=MH_EnableHook(g_target);
    trace_stage("enable",status,GetLastError());
    logf_n4("PHASE_TIMING","phase=enable us=%llu",diag_us(diag_ticks()-phase));
    if(status!=MH_OK){InterlockedExchange(&g_active,0);return (DWORD)status+0x10000;}
    if(g_game_host) {
        error=assignment_signature_record((const BYTE *)g_target,(const void *)(uintptr_t)assignment_hook);
        if(error){InterlockedExchange(&g_active,0);MH_DisableHook(g_target);return error;}
    }
    logf_n4("ASSIGNMENT_ENABLED","attach_us=%llu decoder_entry_patched=0 executing_origin_validation=1",
        diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart));
    return ERROR_SUCCESS;
}
static DWORD prepare_assignment(void *assign) {
    ImageView view;DWORD error;
    if(!g_wide_ready)return ERROR_NOT_READY;
    if(g_target){if(g_target!=assign || !g_original_assign)return ERROR_INVALID_DATA;return g_game_host?enable_assignment():ERROR_SUCCESS;}
    if(g_game_host && (!image_view(g_image_base,&view) || !tooltip_allocator_valid(&view,(const BYTE *)assign)))return ERROR_NOT_READY;
    if(g_game_host && !read_exact(assign,g_assignment_signature.original,sizeof(g_assignment_signature.original)))return ERROR_NOT_READY;
    error=runtime_initialize();if(error)return error;
    error=tooltip_allocator_create_once(&g_tooltip_allocator_prepared,(const BYTE *)assign,tooltip_allocator_create_runtime);if(error)return error;
    g_target=assign;g_original_assign=(AssignFn)(uintptr_t)g_tooltip_allocator_prepared.trampoline;g_assign=g_original_assign;
    g_tooltip_assign=g_original_assign;g_tooltip_translator_ready_us=diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart);
    InterlockedExchange(&g_tooltip_translation_ready,1);
    logf_n4("TOOLTIP_TRANSLATOR_READY","attach_us=%llu rules=%lu stable_allocator_trampoline=1 target=%p generic_enabled=%ld",g_tooltip_translator_ready_us,g_wide_count,g_target,g_active);
    return g_game_host?enable_assignment():ERROR_SUCCESS;
}
static DWORD tooltip_prepare_for_serializer(const BYTE *serializer) {
    ImageView view;const BYTE *assign;DWORD error;
    if(!g_wide_ready)return ERROR_NOT_READY;
    /* Generic preparation already establishes the exact same203-byte ABI. */
    if(g_target && g_original_assign && InterlockedCompareExchange(&g_tooltip_translation_ready,0,0))return ERROR_SUCCESS;
    if(!image_view(g_image_base,&view))return ERROR_NOT_READY;
    error=tooltip_allocator_find(&view,serializer,&assign);
    if(error)return error==ERROR_NOT_FOUND?ERROR_NOT_READY:error;
    return prepare_assignment((void *)assign);
}
static DWORD install_assignment(void *assign) {
    DWORD error;
    if(!assign || !g_decoder_return)return ERROR_INVALID_STATE;
    error=prepare_wide();if(error)return error;
    error=prepare_assignment(assign);if(error)return error;
    error=enable_assignment();if(error)return error;
    if(g_executing_first_us)logf_n4("EXECUTING_ORIGIN_VERIFIED","caller_rva=%llx first_us=%llu full_decoder_and_raw_reader=1",
        (ULONGLONG)((BYTE *)InterlockedCompareExchangePointer(&g_executing_return,NULL,NULL)-g_image_base),g_executing_first_us);
    logf_n4("ASSIGNMENT_INSTALLED","assign=%p reader_return=%p rules=%lu attach_us=%llu decoder_entry_patched=0",assign,g_decoder_return,g_wide_count,diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart));
    return ERROR_SUCCESS;
}
static DWORD restore_data(void) {
    DWORD error=tooltip_restore();MH_STATUS status;
    InterlockedExchange(&g_active,0);InterlockedExchange(&g_assignment_signature.ready,0);InterlockedExchange(&g_tooltip_translation_ready,0);
    if(g_target) {
        status=MH_DisableHook(g_target);
        if(status!=MH_OK && status!=MH_ERROR_DISABLED && status!=MH_ERROR_NOT_CREATED)error=(DWORD)status+0x10000;
    }
    g_status.restored=1;
    /* Keep trampolines/DLL alive for calls in flight. Fixture joins its callers before drain. */
    if(!g_game_host){InterlockedExchange(&g_writer_stop,1);
#if WOJD_CAPTURE
        if(g_dump_event)SetEvent(g_dump_event);
#endif
        if(g_writer)WaitForSingleObject(g_writer,10000);
    }
    return error;
}
static DWORD WINAPI probe_worker(void *parameter){
    HMODULE held=(HMODULE)parameter;DataResult result,probed;ReaderCache cache;DataDiscoveryJob discovery;
    DWORD error,cache_error,cache_stage,probe_error,scan_error,route,attempts=0;BOOL cached,generic_calibrated=FALSE;ULONGLONG start=diag_ticks(),last;
    error=paths_init(g_module);if(error){tooltip_report_failure("PATHS",error);FreeLibraryAndExitThread(held,error);}
    error=session_create_current(&g_session,g_logs_path,WOJD_CAPTURE?"dump":"runtime");
    if(!error)InterlockedExchange(&g_session_ready,1);
    logf_n4("ATTACH","game_host=1 capture=%u session_status=%lu",WOJD_CAPTURE,error);
#if WOJD_CAPTURE
    if(error){FreeLibraryAndExitThread(held,error);}
#endif
    g_image_base=(BYTE *)GetModuleHandleW(NULL);g_prefer_far=TRUE;
    /* Pin before either independent hook can become visible to game threads. */
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCWSTR)g_module,&held)){error=GetLastError();tooltip_report_failure("PIN",error);return error;}
    error=runtime_initialize();
    if(error){logf_n4("CAPTURE_INITIALIZE_FAILED","status=%lu",error);tooltip_report_failure("RUNTIME_INITIALIZE",error);return error;}
    g_discovery_pump=tooltip_probe_once;
    g_discovery_pump(); /* Before catalog preparation and all generic decoder discovery. */
#if WOJD_CAPTURE
    if(g_session_ready){DWORD archive_error=start_archiver();logf_n4("ARCHIVER_STARTED","status=%lu",archive_error);}
#endif
    error=catalog_load(TEXT_CATALOG);if(!error)error=prepare_wide();
    if(error){logf_n4("CATALOG_FAILED","status=%lu",error);tooltip_report_failure("CATALOG",error);}
    else {
        logf_n4("CATALOG_READY","rules=%lu elapsed_us=%llu",g_wide_count,diag_us(diag_ticks()-start));
        ZeroMemory(&result,sizeof(result));cache_error=cache_load(READER_CACHE,&cache);cached=cache_error==ERROR_SUCCESS || cache_error==ERROR_REVISION_MISMATCH;
        logf_n4(cached?"CACHE_LOADED":"CACHE_MISS","status=%lu cold_discovery_coverage_unproven=%u",cache_error,!cached);
        ZeroMemory(&discovery,sizeof(discovery));error=ERROR_NOT_READY;
        do {
            if(g_discovery_pump)g_discovery_pump();
            if(GetFileAttributesW(STOP_FILE)!=INVALID_FILE_ATTRIBUTES){error=ERROR_CANCELLED;break;}
            attempts++;
            if(!executing_origin_result(&probed)) {
                result=probed;route=cache_result_route(cache_error,&cache,g_image_base,&result);
                if(route==CACHE_ROUTE_WARM)g_tooltip_generic_cache_ready=TRUE;
                else generic_calibrated=TRUE;
                logf_n4("GENERIC_CHAIN_READY","source=EXECUTING_CALL route=%s attach_us=%llu",route==CACHE_ROUTE_WARM?"WARM":"CALIBRATION",diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart));
                error=ERROR_SUCCESS;break;
            }
            if(cached) {
                probe_error=cache_probe(g_image_base,&cache,&probed,&cache_stage);
                if(!probe_error) {
                    result=probed;route=cache_result_route(cache_error,&cache,g_image_base,&result);
                    if(route==CACHE_ROUTE_WARM)g_tooltip_generic_cache_ready=TRUE;
                    else generic_calibrated=TRUE;
                    logf_n4("GENERIC_CHAIN_READY","source=KNOWN_HINT route=%s attach_us=%llu",route==CACHE_ROUTE_WARM?"WARM":"CALIBRATION",diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart));
                    error=ERROR_SUCCESS;break;
                }
                error=probe_error;
                if(!cache_probe_may_retry(cache_error,probe_error)) {
                    logf_n4("CACHE_HINT_REJECTED","status=%lu stage=%lu fallback=BOUNDED_DISCOVERY",probe_error,cache_stage);
                    cached=FALSE;
                }
            }
            if(!discovery.complete) {
                scan_error=data_discovery_step(g_image_base,&discovery);
                if(!scan_error) {
                    result=discovery.result;route=cache_result_route(cache_error,&cache,g_image_base,&result);
                    if(route==CACHE_ROUTE_WARM)g_tooltip_generic_cache_ready=TRUE;
                    else generic_calibrated=TRUE;
                    logf_n4("GENERIC_CHAIN_READY","source=READABLE_SCAN route=%s attach_us=%llu scan_steps=%lu scan_bytes=%llu skipped_bytes=%llu",route==CACHE_ROUTE_WARM?"WARM":"CALIBRATION",diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart),discovery.total_steps,discovery.total_bytes,discovery.total_skipped);
                    error=ERROR_SUCCESS;break;
                }
                if(scan_error!=ERROR_IO_PENDING && scan_error!=ERROR_NOT_READY)error=scan_error;
            }
            /* An exhausted relocation search cannot discard a current known
               hint. It continues to be validated until the global watchdog. */
            if(data_discovery_terminal(&discovery,cached,g_active!=0,g_tooltip_pending)) {error=discovery.status;break;}
            Sleep(2);
        }while(diag_us(diag_ticks()-start)<180000000ull);
        if(error && error!=ERROR_CANCELLED && diag_us(diag_ticks()-start)>=180000000ull)error=ERROR_TIMEOUT;
        if(error){logf_n4("DISCOVERY_FAILED","status=%lu attempts=%lu",error,attempts);tooltip_report_failure("GENERIC_DISCOVERY",error);}
        else {
            g_decoder_reader=(BYTE *)(uintptr_t)result.reader;g_decoder_return=g_decoder_reader+0x223;
            code_diag_raw_anchor((const BYTE *)(uintptr_t)result.raw_reader);
            error=install_assignment((void *)(uintptr_t)result.assign);
            if(error){logf_n4("INSTALL_FAILED","status=%lu",error);tooltip_report_failure("GENERIC_HOOK_INSTALL",error);}
            else {
                cache_error=cache_save(READER_CACHE,g_image_base,&result,1);
                if(!cache_error) {
                    g_tooltip_generic_cache_ready=TRUE;
                    if(generic_calibrated){g_tooltip_cache_persisted=TRUE;g_tooltip_restart_required=TRUE;}
                }
                logf_n4("CACHE_SAVED","status=%lu calibration=%u",cache_error,generic_calibrated);
                if(cache_error)tooltip_report_failure("GENERIC_CACHE_WRITE",cache_error);
            }
        }
    }
    g_tooltip_setup_complete=TRUE;tooltip_probe_once();
    /* A generic-hook failure cannot make a valid stable allocator unsafe. */
    last=diag_ticks();
    while((g_active || g_tooltip_active || g_tooltip_pending) && GetFileAttributesW(STOP_FILE)==INVALID_FILE_ATTRIBUTES){
        tooltip_probe_once();
        code_diag_step(); /* Optional calibration only; existing worker yields below. */
        ULONGLONG now=diag_ticks();
        if(diag_us(now-last)>=30000000ull){
            logf_n4("COUNTERS","calls=%ld strings=%ld translated=%ld missing=%ld ignored=%ld invalid=%ld exceptions=%ld dropped=%ld origin_rejected=%ld",g_status.calls,g_status.strings,g_status.translated,g_status.unknown,g_ignored,g_status.invalid,g_status.exceptions,g_status.dropped,g_origin_rejected);last=now;
            logf_n4("TOOLTIP_COUNTERS","installed=%lu scopes=%ld serializers=%ld fields=%ld captured=%ld invalid=%ld exceptions=%ld rejected=%ld",g_tooltip_status.installed,g_tooltip_status.scopes,g_tooltip_status.serializers,g_tooltip_status.fields,g_tooltip_status.captured,g_tooltip_status.invalid,g_tooltip_status.exceptions,g_tooltip_status.origin_rejected);
            logf_n4("TOOLTIP_DIAGNOSTICS","serializer_entry_seen=%ld approved_calls=%ld approved_in_scope=%ld approved_outside_scope=%ld scope_exits=%ld",g_tooltip_diagnostics.serializer_entry_seen,g_tooltip_diagnostics.approved_calls,g_tooltip_diagnostics.approved_in_scope,g_tooltip_diagnostics.approved_outside_scope,g_tooltip_diagnostics.scope_exits);
            logf_n4("TOOLTIP_TYPED_COUNTERS","plain_fields=%ld native_fields=%ld code_rejected=%ld not_loading=%ld not_empty=%ld",g_tooltip_typed_status.plain_fields,g_tooltip_typed_status.native_fields,g_tooltip_typed_status.code_rejected,g_tooltip_typed_status.not_loading,g_tooltip_typed_status.not_empty);
            logf_n4("TOOLTIP_TRANSLATION_COUNTERS","lookups=%ld translated=%ld ignored=%ld missing=%ld not_ready=%ld failed=%ld",g_tooltip_translation_status.lookups,g_tooltip_translation_status.translated,g_tooltip_translation_status.ignored,g_tooltip_translation_status.missing,g_tooltip_translation_status.not_ready,g_tooltip_translation_status.failed);
        }
        Sleep(g_tooltip_pending?2:1000);
    }
    g_discovery_pump=NULL;
#if WOJD_CAPTURE
    logf_n4("TOOLTIP_CAPTURE_STOP","status=%lu fields=%ld captured=%ld dropped_total=%ld",g_tooltip_install_error,g_tooltip_status.fields,g_tooltip_status.captured,g_status.dropped);
#endif
    logf_n4("TOOLTIP_TRANSLATION_FINAL","installed=%lu serializers=%ld eligible_fields=%ld native_fields=%ld lookups=%ld translated=%ld missing=%ld ignored=%ld not_ready=%ld failed=%ld",g_tooltip_status.installed,g_tooltip_status.serializers,g_tooltip_status.fields,g_tooltip_typed_status.native_fields,g_tooltip_translation_status.lookups,g_tooltip_translation_status.translated,g_tooltip_translation_status.missing,g_tooltip_translation_status.ignored,g_tooltip_translation_status.not_ready,g_tooltip_translation_status.failed);
    error=restore_data();logf_n4("RESTORE","status=%lu",error);return error;
}
__declspec(dllexport) DWORD WINAPI WojdTranslationVersion(void){return 0x00010000;}
#if WOJD_SELFTEST
__declspec(dllexport) DWORD WINAPI WojdTooltipSelfTestInstallTyped(void *serializer,void *plain_return,void *native_return) {
    DWORD error;if(g_game_host || !serializer || !plain_return || !native_return)return ERROR_ACCESS_DENIED;
    error=paths_init(g_module);if(!error)error=runtime_initialize();if(error)return error;
    g_tooltip_test_plain_return=plain_return;g_tooltip_test_native_return=native_return;
    return tooltip_install(serializer);
}
__declspec(dllexport) DWORD WINAPI WojdTooltipSelfTestSetSkillReturns(void *plain_return,void *native_return) {
    if(g_game_host || !plain_return || !native_return || g_tooltip_test_plain_skill_return || g_tooltip_test_native_skill_return)return ERROR_ACCESS_DENIED;
    g_tooltip_test_plain_skill_return=plain_return;g_tooltip_test_native_skill_return=native_return;return ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdTooltipSelfTestTypedStatus(TooltipTypedStatus *out) {if(g_game_host || !out)return ERROR_ACCESS_DENIED;*out=g_tooltip_typed_status;return ERROR_SUCCESS;}
__declspec(dllexport) DWORD WINAPI WojdTooltipSelfTestStatus(TooltipStatus *out) {if(g_game_host || !out)return ERROR_ACCESS_DENIED;*out=g_tooltip_status;return ERROR_SUCCESS;}
__declspec(dllexport) DWORD WINAPI WojdTooltipSelfTestDiagnostics(TooltipDiagnostics *out) {if(g_game_host || !out)return ERROR_ACCESS_DENIED;*out=g_tooltip_diagnostics;return ERROR_SUCCESS;}
__declspec(dllexport) DWORD WINAPI WojdTooltipSelfTestTranslationStatus(TooltipTranslationStatus *out) {if(g_game_host || !out)return ERROR_ACCESS_DENIED;*out=g_tooltip_translation_status;return ERROR_SUCCESS;}
__declspec(dllexport) DWORD WINAPI WojdTooltipSelfTestRestore(void) {if(g_game_host)return ERROR_ACCESS_DENIED;return tooltip_restore();}
__declspec(dllexport) DWORD WINAPI WojdNativeCanaryVersion(void){return 0x4e3a;}
__declspec(dllexport) DWORD WINAPI WojdN10ResolveImage(void *base,DataResult *out) {if(g_game_host || !out)return ERROR_ACCESS_DENIED;return resolve_data(base,out);}
__declspec(dllexport) DWORD WINAPI WojdN10SelfTestLoadCatalog(const WCHAR *path) {if(g_game_host || !path)return ERROR_ACCESS_DENIED;{DWORD error=paths_init(g_module);return error?error:catalog_load(path);}}
__declspec(dllexport) DWORD WINAPI WojdN10SelfTestPrepareCatalog(void) {if(g_game_host)return ERROR_ACCESS_DENIED;return prepare_wide();}
__declspec(dllexport) DWORD WINAPI WojdN10SelfTestInstall(void *assign,void *origin) {if(g_game_host || !origin)return ERROR_ACCESS_DENIED;g_decoder_return=(BYTE *)origin;g_origin_verified=1;return install_assignment(assign);}
__declspec(dllexport) DWORD WINAPI WojdN10SelfTestStatus(DataStatus *out) {if(g_game_host || !out)return ERROR_ACCESS_DENIED;*out=g_status;return ERROR_SUCCESS;}
__declspec(dllexport) DWORD WINAPI WojdN10SelfTestRestore(void) {if(g_game_host)return ERROR_ACCESS_DENIED;return restore_data();}
__declspec(dllexport) DWORD WINAPI WojdN10SelfTestOrigin(void *base,const BYTE *reader,const BYTE *assign) {if(g_game_host)return ERROR_ACCESS_DENIED;return verify_assignment_origin(base,reader,assign);}
__declspec(dllexport) DWORD WINAPI WojdN10SelfTestForceFar(DWORD mode) {if(g_game_host || g_active)return ERROR_ACCESS_DENIED;InterlockedExchange(&g_force_far,mode?1:0);return ERROR_SUCCESS;}
__declspec(dllexport) DWORD WINAPI WojdN10SelfTestWriteCache(const WCHAR *path,void *base,const DataResult *result) {if(g_game_host || !path || !result)return ERROR_ACCESS_DENIED;return cache_save(path,base,result,1);}
__declspec(dllexport) DWORD WINAPI WojdN10SelfTestResolveCache(const WCHAR *path,void *base,DataResult *result,DWORD *stage) {ReaderCache cache;DWORD error;if(g_game_host || !path || !result || !stage)return ERROR_ACCESS_DENIED;error=cache_load(path,&cache);return error?error:cache_probe(base,&cache,result,stage);}
#endif
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved) {
    (void)reserved;if(reason==DLL_PROCESS_ATTACH) {
        WCHAR host[512];DWORD n;g_module=module;n=GetModuleFileNameW(NULL,host,512);g_game_host=n && n<512 && !_wcsicmp(wcsrchr(host,L'\\')?wcsrchr(host,L'\\')+1:host,L"ZhuxianClient-Win64-Shipping.exe");
        QueryPerformanceFrequency(&g_diag_frequency);QueryPerformanceCounter(&g_diag_attach);
        if(g_game_host) {HMODULE held=NULL;if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,(LPCWSTR)module,&held)){HANDLE thread=CreateThread(NULL,0,probe_worker,held,0,NULL);if(thread)CloseHandle(thread);}}
    }return TRUE;
}
