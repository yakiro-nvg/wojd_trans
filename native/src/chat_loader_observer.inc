/* One-shot Lua module adapter. Player admission requires explicit chat.ini
 * opt-in. The original module remains the first child of the Lua envelope;
 * no operation is inserted into a pending Lua pcall frame. */
#include "chat_lua_envelope.inc"
#include "chat_module_observer.h"
enum { LCO_GETTOP,LCO_POP,LCO_TOSTRING,LCO_LOAD,LCO_PCALL,LCO_API_COUNT };
typedef struct LcoSignature {
    const char *name;const BYTE *wrapper,*wrapper_mask;SIZE_T wrapper_size,branch_offset;
    const BYTE *callee,*callee_mask;SIZE_T callee_size;
} LcoSignature;
#include "chat_lua_signatures.h"
enum { LCO_MAX_SLOTS=128,LCO_MAX_FACTORIES=8 };
typedef int (__fastcall *LcoLoadFn)(void *,void *,const char *,SIZE_T,const char *,const char *);
typedef int (__fastcall *LcoBareLoadFn)(void *,const char *,SIZE_T,const char *,const char *);
typedef void (__fastcall *LcoPopFn)(void *,void *,int);
typedef struct LcoResult {
    DWORD factory,initializer,table,global,slots,api_slots[LCO_API_COUNT];
    const BYTE *functions[LCO_API_COUNT];void *object;
} LcoResult;
static void *g_lco_shadow[LCO_MAX_SLOTS+1];
static void **g_lco_original_table;static void *g_lco_object;
static LcoLoadFn g_lco_load;static LcoPopFn g_lco_pop;
static LcoBareLoadFn g_lco_bare_load;static void *g_lco_bare_target;
static volatile LONG g_lco_executed,g_lco_marker_taken,g_lco_bare_inflight;static char g_lco_kinds[9];
static volatile LONG g_lco_active,g_lco_taken,g_lco_ready,g_lco_seen,g_lco_lua_chunks,g_lco_inflight;
static __declspec(thread) unsigned g_lco_depth;
static struct {DWORD source_bytes,output_bytes,codec_status,load_status,restored,envelope_loaded,envelope_status; } g_lco_observation;
#include "chat_type_signal.inc"
#if WOJD_CHAT_RUNTIME
#include "chat_callback_resolver.inc"
#include "chat_module_binding.inc"
#include "chat_receive_queue.inc"
#include "chat_receive_templates.h"
static LcrApis g_lcr_apis;
static volatile LONG g_lcr_taken[3];
#endif
static BOOL lco_marker(const char *buffer,SIZE_T size,const char *name,const char *mode) {
    static const char prefix[]="WOJD_CHAT_LOADER_OBSERVER_V2:";
    char source[8],marker[sizeof(prefix)+8],mode_bytes[2];unsigned i;
    if(size!=sizeof(source) || !buffer || !name || !mode || g_lco_executed ||
       !read_exact(buffer,source,sizeof(source)) || memcmp(source,"return 0",sizeof(source)) ||
       !read_exact(mode,mode_bytes,sizeof(mode_bytes)) || memcmp(mode_bytes,"t",2) ||
       !read_exact(name,marker,sizeof(marker)) || memcmp(marker,prefix,sizeof(prefix)-1) || marker[sizeof(marker)-1])return FALSE;
    for(i=0;i<8;++i)if(!marker[sizeof(prefix)-1+i] || !strchr("ntfusdbr?",marker[sizeof(prefix)-1+i]))return FALSE;
    if(InterlockedCompareExchange(&g_lco_marker_taken,1,0))return FALSE;
    memcpy(g_lco_kinds,marker+sizeof(prefix)-1,8);g_lco_kinds[8]=0;
    MemoryBarrier();InterlockedExchange(&g_lco_executed,1);return TRUE;
}
static int __fastcall lco_bare_load_hook(void *state,const char *buffer,SIZE_T size,const char *name,const char *mode) {
    DWORD saved=GetLastError(),after;int status;
    InterlockedIncrement(&g_lco_bare_inflight);
    if(g_lco_active)lco_marker(buffer,size,name,mode);
    SetLastError(saved);status=g_lco_bare_load(state,buffer,size,name,mode);after=GetLastError();
    InterlockedDecrement(&g_lco_bare_inflight);SetLastError(after);return status;
}
#if defined(WOJD_CHAT_OBSERVER_TEST) && WOJD_CHAT_OBSERVER_TEST
static LONG g_lco_alloc_calls,g_lco_alloc_live,g_lco_alloc_fail;
#endif
static void *lco_alloc(SIZE_T size) {
    void *result;
#if defined(WOJD_CHAT_OBSERVER_TEST) && WOJD_CHAT_OBSERVER_TEST
    if(InterlockedIncrement(&g_lco_alloc_calls)==g_lco_alloc_fail)return NULL;
#endif
    result=HeapAlloc(GetProcessHeap(),0,size);
#if defined(WOJD_CHAT_OBSERVER_TEST) && WOJD_CHAT_OBSERVER_TEST
    if(result)InterlockedIncrement(&g_lco_alloc_live);
#endif
    return result;
}
static void lco_free(void *address) {
    if(!address)return;
    HeapFree(GetProcessHeap(),0,address);
#if defined(WOJD_CHAT_OBSERVER_TEST) && WOJD_CHAT_OBSERVER_TEST
    InterlockedDecrement(&g_lco_alloc_live);
#endif
}

static const BYTE lco_factory_bytes[]={0x48,0x83,0xec,0x28,0xb9,8,0,0,0,0xe8,0,0,0,0,0x48,0x85,0xc0,0x74,0,0x48,0x8d,0x0d,0,0,0,0,0x48,0x89,8,0x48,0x83,0xc4,0x28,0xc3};
static const BYTE lco_factory_mask[]={255,255,255,255,255,255,255,255,255,255,0,0,0,0,255,255,255,255,0,255,255,255,0,0,0,0,255,255,255,255,255,255,255,255};
static BOOL lco_api_match(const ImageView *view,const BYTE *method,unsigned api) {
    const LcoSignature *s=&k_lco_signatures[api];const BYTE *target;
    if(!signature_at(view,method,s->wrapper,s->wrapper_mask,s->wrapper_size))return FALSE;
    target=relative_target(method+s->branch_offset);
    return target && signature_at(view,target,s->callee,s->callee_mask,s->callee_size);
}
static BOOL lco_table(const ImageView *view,LcoResult *result) {
    const BYTE *table=view->base+result->table;unsigned slot,api,counts[LCO_API_COUNT]={0};
    if(((uintptr_t)table&7) ||
       (section_flags(view,table,8)&(IMAGE_SCN_MEM_READ|IMAGE_SCN_MEM_WRITE|IMAGE_SCN_MEM_EXECUTE))!=IMAGE_SCN_MEM_READ)return FALSE;
    for(slot=0;slot<LCO_MAX_SLOTS;++slot) {
        const BYTE *method;
        if(!in_image(view,table+slot*8,8) || !read_exact(table+slot*8,&method,8) || !executable(view,method))break;
        for(api=0;api<LCO_API_COUNT;++api)if(lco_api_match(view,method,api)) {
            ++counts[api];result->api_slots[api]=slot;result->functions[api]=method;
        }
    }
    if(slot<16 || slot==LCO_MAX_SLOTS)return FALSE;
    for(api=0;api<LCO_API_COUNT;++api)if(counts[api]!=1)return FALSE;
    result->slots=slot;return TRUE;
}
static BOOL lco_metadata(const ImageView *view,LcoResult *result) {
    BYTE factory[sizeof(lco_factory_bytes)],initializer[21];LONG branch,store;const BYTE *table;
    if(!result->factory || !result->initializer || !result->table || !result->global ||
       result->factory>=view->size || result->initializer>=view->size || result->table>=view->size || result->global>=view->size ||
       !signature_at(view,view->base+result->factory,lco_factory_bytes,lco_factory_mask,sizeof(factory)) ||
       !read_exact(view->base+result->factory,factory,sizeof(factory)))return FALSE;
    memcpy(&branch,factory+22,4);table=view->base+result->factory+26+branch;
    if(table!=view->base+result->table || !executable(view,view->base+result->initializer) ||
       !in_image(view,view->base+result->initializer,sizeof(initializer)) ||
       !read_exact(view->base+result->initializer,initializer,sizeof(initializer)) ||
       memcmp(initializer,"\x48\x83\xec\x28\xe8",5) ||
       memcmp(initializer+9,"\x48\x89\x05",3) || memcmp(initializer+16,"\x48\x83\xc4\x28\xc3",5))return FALSE;
    memcpy(&branch,initializer+5,4);memcpy(&store,initializer+12,4);
    if(view->base+result->initializer+9+branch!=view->base+result->factory ||
       view->base+result->initializer+16+store!=view->base+result->global ||
       !(section_flags(view,view->base+result->global,8)&IMAGE_SCN_MEM_WRITE) ||
       (result->global&7))return FALSE;
    return lco_table(view,result);
}
static DWORD lco_object_ready(const ImageView *view,LcoResult *result) {
    void *object,*table;
    if(!read_exact(view->base+result->global,&object,8))return ERROR_NOACCESS;
    if(!object)return ERROR_NOT_READY;
    if(!writable_pointer(object) || !read_exact(object,&table,8))return ERROR_NOACCESS;
    if(table!=view->base+result->table)return ERROR_INVALID_STATE;
    result->object=object;return ERROR_SUCCESS;
}
typedef struct LcoFactories {LcoResult hits[LCO_MAX_FACTORIES];unsigned count;BOOL overflow;} LcoFactories;
static BOOL lco_scan_factory(const ImageView *view,const BYTE *live,const BYTE *copy,SIZE_T size,void *parameter) {
    LcoFactories *hits=(LcoFactories *)parameter;SIZE_T pos;
    for(pos=0;pos+sizeof(lco_factory_bytes)<=size;++pos) {
        LcoResult candidate;LONG displacement;const BYTE *table;unsigned i;
        if(copy[pos]!=0x48 || !masked_match(copy+pos,lco_factory_bytes,lco_factory_mask,sizeof(lco_factory_bytes)))continue;
        memcpy(&displacement,copy+pos+22,4);table=live+pos+26+displacement;
        if(!in_image(view,table,8))continue;
        ZeroMemory(&candidate,sizeof(candidate));candidate.factory=(DWORD)(live+pos-view->base);candidate.table=(DWORD)(table-view->base);
        if(!lco_table(view,&candidate))continue;
        for(i=0;i<hits->count;++i)if(hits->hits[i].factory==candidate.factory)break;
        if(i<hits->count)continue;
        if(hits->count==LCO_MAX_FACTORIES){hits->overflow=TRUE;continue;}
        hits->hits[hits->count++]=candidate;
    }
    return TRUE;
}
typedef struct LcoGlobals {LcoFactories *factories;LcoResult result;unsigned matches;} LcoGlobals;
static BOOL lco_scan_global(const ImageView *view,const BYTE *live,const BYTE *copy,SIZE_T size,void *parameter) {
    LcoGlobals *globals=(LcoGlobals *)parameter;SIZE_T pos;
    for(pos=0;pos+21<=size;++pos) {
        LONG call,store;const BYTE *factory,*global;LcoResult candidate;unsigned i;
        if(memcmp(copy+pos,"\x48\x83\xec\x28\xe8",5) || memcmp(copy+pos+9,"\x48\x89\x05",3) ||
           memcmp(copy+pos+16,"\x48\x83\xc4\x28\xc3",5))continue;
        memcpy(&call,copy+pos+5,4);factory=live+pos+9+call;
        for(i=0;i<globals->factories->count;++i)if(view->base+globals->factories->hits[i].factory==factory)break;
        if(i==globals->factories->count)continue;
        memcpy(&store,copy+pos+12,4);global=live+pos+16+store;
        if(!in_image(view,global,8))continue;
        candidate=globals->factories->hits[i];candidate.initializer=(DWORD)(live+pos-view->base);candidate.global=(DWORD)(global-view->base);
        if(!lco_metadata(view,&candidate))continue;
        if(globals->matches && candidate.global==globals->result.global && candidate.factory==globals->result.factory)continue;
        ++globals->matches;globals->result=candidate;
    }
    return TRUE;
}
static DWORD lco_discover(const ImageView *view,LcoResult *result) {
    LcoFactories factories;LcoGlobals globals;DWORD error;
    ZeroMemory(&factories,sizeof(factories));ZeroMemory(&globals,sizeof(globals));globals.factories=&factories;
    error=scan_executable(view,lco_scan_factory,&factories);if(error)return error;
    if(factories.overflow)return ERROR_DUP_NAME;
    if(!factories.count)return ERROR_NOT_FOUND;
    error=scan_executable(view,lco_scan_global,&globals);if(error)return error;
    if(globals.matches!=1)return globals.matches?ERROR_DUP_NAME:ERROR_NOT_FOUND;
    *result=globals.result;return ERROR_SUCCESS;
}
static DWORD lco_restore(void) {
    void *previous;InterlockedExchange(&g_lco_active,0);
    if(!g_lco_object || !g_lco_original_table)return ERROR_INVALID_STATE;
    if(!writable_pointer(g_lco_object))return ERROR_NOACCESS;
    previous=InterlockedCompareExchangePointer((PVOID volatile *)g_lco_object,g_lco_original_table,g_lco_shadow+1);
    return previous==g_lco_shadow+1 || previous==g_lco_original_table?ERROR_SUCCESS:ERROR_RETRY;
}
static BOOL lco_source_suffix(const BYTE *bytes,SIZE_T size,const char *suffix) {
    SIZE_T suffix_size=strlen(suffix);
    LcReader reader;unsigned length;SIZE_T begin,i,offset;
    if(size<=sizeof(lc_header)+1 || memcmp(bytes,lc_header,sizeof(lc_header)))return FALSE;
    ZeroMemory(&reader,sizeof(reader));reader.data=bytes;reader.size=size;reader.pos=sizeof(lc_header)+1;
    length=lc_integer(&reader);begin=reader.pos;
    if(reader.error || !length || length-1<suffix_size || length-1>1024 || length-1>size-begin)return FALSE;
    offset=begin+length-1-suffix_size;
    for(i=0;i<suffix_size;++i) {
        BYTE value=bytes[offset+i],wanted=(BYTE)suffix[i];
        if(value=='\\')value='/';
        if(value>='A' && value<='Z')value=(BYTE)(value+('a'-'A'));
        if(wanted>='A' && wanted<='Z')wanted=(BYTE)(wanted+('a'-'A'));
        if(value!=wanted)return FALSE;
    }
    return TRUE;
}
static BOOL lco_chat_source(const BYTE *bytes,SIZE_T size) {
    return lco_source_suffix(bytes,size,"/UI/Chat/ChatMessageItem.lua");
}
static int __fastcall lco_load_hook(void *self,void *state,const char *buffer,SIZE_T size,const char *name,const char *mode) {
    DWORD saved=GetLastError(),after;BYTE prefix[1200],*original=NULL,*output=NULL;SIZE_T prefix_size,needed=0;
    int status,codec;BOOL selected=FALSE;
#if WOJD_CHAT_RUNTIME
    unsigned kind=0;const BYTE *template_bytes;SIZE_T template_size;
#endif
    InterlockedIncrement(&g_lco_inflight);InterlockedIncrement(&g_lco_seen);
    if(!g_lco_active || g_lco_depth || !buffer || size<=sizeof(lc_header)+1 || size>LC_MAX_BYTES)goto forward;
    prefix_size=size<sizeof(prefix)?size:sizeof(prefix);
    if(!read_exact(buffer,prefix,prefix_size) || memcmp(prefix,lc_header,sizeof(lc_header)))goto forward;
    InterlockedIncrement(&g_lco_lua_chunks);
#if WOJD_CHAT_RUNTIME
    if(lco_chat_source(prefix,prefix_size))kind=1;
    else if(lco_source_suffix(prefix,prefix_size,"/UI/Chat/ChatScrollBox.lua"))kind=2;
    if(!kind || InterlockedCompareExchange(&g_lcr_taken[kind],1,0)!=0)goto forward;
    InterlockedIncrement(&g_lco_taken);
    template_bytes=kind==1?lcr_item_template:lcr_scroll_template;
    template_size=kind==1?sizeof(lcr_item_template):sizeof(lcr_scroll_template);
#else
    if(!lco_chat_source(prefix,prefix_size) || InterlockedCompareExchange(&g_lco_taken,1,0)!=0)goto forward;
#endif
    selected=TRUE;++g_lco_depth;
    g_lco_observation.source_bytes=(DWORD)size;
    original=(BYTE *)lco_alloc(size);
    if(!original || !read_exact(buffer,original,size)){g_lco_observation.codec_status=LC_ARGUMENT;goto cleanup_forward;}
#if WOJD_CHAT_RUNTIME
    codec=lcm_expose(original,size,kind,&g_cq.layout[kind]);
    g_lco_observation.codec_status=(DWORD)codec;if(codec)goto cleanup_forward;
#endif
#if WOJD_CHAT_RUNTIME
    codec=lc_callback_envelope(original,size,template_bytes,template_size,NULL,0,&needed);
#else
    codec=lc_envelope(original,size,lco_module_template,sizeof(lco_module_template),NULL,0,&needed);
#endif
    g_lco_observation.codec_status=(DWORD)codec;
    if(codec)goto cleanup_forward;
    output=(BYTE *)lco_alloc(needed);
    if(!output){g_lco_observation.codec_status=LC_BUFFER;goto cleanup_forward;}
#if WOJD_CHAT_RUNTIME
    codec=lc_callback_envelope(original,size,template_bytes,template_size,output,needed,&needed);
#else
    codec=lc_envelope(original,size,lco_module_template,sizeof(lco_module_template),output,needed,&needed);
#endif
    g_lco_observation.codec_status=(DWORD)codec;if(codec)goto cleanup_forward;
    g_lco_observation.output_bytes=(DWORD)needed;
    if(!g_lco_active)goto cleanup_forward;
    SetLastError(saved);status=g_lco_load(self,state,(const char *)output,needed,name,mode);after=GetLastError();
    g_lco_observation.envelope_status=(DWORD)status;
#if WOJD_CHAT_RUNTIME
    if(!status) {
        int bound=lcb_bind(&g_lcr_apis.bind,state,cq_callback);
        if(bound) {
            /* Binding did not execute Lua. Drop the owned wrapper closure and
               load the original module so optional chat failure stays local. */
            g_lco_pop(self,state,1);SetLastError(saved);
            status=g_lco_load(self,state,buffer,size,name,mode);after=GetLastError();
            logf_n4("CHAT_CALLBACK_BIND_FAILED","module=%u status=%d",kind,bound);
            g_lco_observation.load_status=(DWORD)status;
            goto loaded;
        }
    }
#endif
    if(!status)g_lco_observation.envelope_loaded=1;
    if(status) {
        /* Normal load returns one error value in place of its one closure.
           Remove that value, then forward the untouched original buffer. */
        g_lco_pop(self,state,1);SetLastError(saved);
        status=g_lco_load(self,state,buffer,size,name,mode);after=GetLastError();
    }
    g_lco_observation.load_status=(DWORD)status;
#if WOJD_CHAT_RUNTIME
loaded:
#endif
    lco_free(output);lco_free(original);--g_lco_depth;
    MemoryBarrier();InterlockedExchange(&g_lco_ready,1);InterlockedDecrement(&g_lco_inflight);SetLastError(after);return status;
cleanup_forward:
    lco_free(output);lco_free(original);
    --g_lco_depth;
forward:
    SetLastError(saved);status=g_lco_load(self,state,buffer,size,name,mode);after=GetLastError();
    if(selected){g_lco_observation.load_status=(DWORD)status;MemoryBarrier();InterlockedExchange(&g_lco_ready,1);}
    InterlockedDecrement(&g_lco_inflight);SetLastError(after);return status;
}
/* The caller certifies table identity/ABI before this serialized binding step. */
static DWORD lco_bind(void *object,void **table,DWORD slots,DWORD load_slot,LcoLoadFn load,LcoPopFn pop) {
    if(g_lco_active || g_lco_inflight || !object || !table || !load || !pop ||
       slots<16 || slots>=LCO_MAX_SLOTS || load_slot>=slots || !writable_pointer(object))return ERROR_INVALID_STATE;
    if(!read_exact(table,g_lco_shadow+1,slots*8) || !read_exact(table-1,g_lco_shadow,8))return ERROR_NOACCESS;
    g_lco_object=object;g_lco_original_table=table;g_lco_load=load;g_lco_pop=pop;
    g_lco_shadow[load_slot+1]=(void *)lco_load_hook;
    ZeroMemory(&g_lco_observation,sizeof(g_lco_observation));
    g_lco_observation.envelope_status=MAXDWORD;
    InterlockedExchange(&g_lco_taken,0);InterlockedExchange(&g_lco_ready,0);InterlockedExchange(&g_lco_seen,0);InterlockedExchange(&g_lco_lua_chunks,0);
    InterlockedExchange(&g_lco_executed,0);InterlockedExchange(&g_lco_marker_taken,0);ZeroMemory(g_lco_kinds,sizeof(g_lco_kinds));
    MemoryBarrier();InterlockedExchange(&g_lco_active,1);
    if(InterlockedCompareExchangePointer((PVOID volatile *)g_lco_object,g_lco_shadow+1,table)!=table){InterlockedExchange(&g_lco_active,0);return ERROR_RETRY;}
    return ERROR_SUCCESS;
}
static DWORD lco_install(const ImageView *view,LcoResult *result) {
#if !WOJD_CHAT_RUNTIME
    LcoKindFn kind;LcoStringLengthFn string_length;void *type_target;
#endif
    DWORD error=lco_object_ready(view,result);if(error)return error;
    if(!lco_metadata(view,result))return ERROR_INVALID_STATE;
#if WOJD_CHAT_RUNTIME
    error=lcr_resolve(view,result,&g_lcr_apis,FALSE);if(error)return error;
    error=cq_prepare(&g_lcr_apis);if(error)return error;
#else
    error=lco_type_resolve(view,result,&kind,&string_length,&type_target);if(error)return error;
    error=lco_type_attach(type_target,string_length);if(error)return error;
#endif
    error=lco_bind(result->object,(void **)(view->base+result->table),result->slots,result->api_slots[LCO_LOAD],
                    (LcoLoadFn)(uintptr_t)result->functions[LCO_LOAD],(LcoPopFn)(uintptr_t)result->functions[LCO_POP]);
    if(error && g_lco_type_target){MH_DisableHook(g_lco_type_target);lco_type_remove();}
    return error;
}
static BOOL lco_path(WCHAR *output,const WCHAR *name) {
    return _snwprintf_s(output,1024,_TRUNCATE,L"%s\\%s",g_root_path,name)>=0;
}
static BOOL lco_cache_value(const WCHAR *path,const WCHAR *key,DWORD limit,DWORD *output) {
    WCHAR text[24],*end;unsigned long value;
    DWORD n=GetPrivateProfileStringW(L"lua-observer",key,L"",text,24,path);
    if(!n || n>=23)return FALSE;
    value=wcstoul(text,&end,16);if(*end || !value || value>=limit)return FALSE;
    *output=(DWORD)value;return TRUE;
}
static DWORD lco_cache_load(const ImageView *view,LcoResult *result) {
    WCHAR path[1024];DWORD attributes;
    if(!lco_path(path,L"chat-lua-cache.ini"))return ERROR_FILENAME_EXCED_RANGE;
    attributes=GetFileAttributesW(path);if(attributes==INVALID_FILE_ATTRIBUTES)return ERROR_FILE_NOT_FOUND;
    if(attributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))return ERROR_INVALID_DATA;
    ZeroMemory(result,sizeof(*result));
    if(GetPrivateProfileIntW(L"lua-observer",L"version",0,path)!=1 ||
       !lco_cache_value(path,L"factory",view->size,&result->factory) ||
       !lco_cache_value(path,L"initializer",view->size,&result->initializer) ||
       !lco_cache_value(path,L"table",view->size,&result->table) ||
       !lco_cache_value(path,L"global",view->size,&result->global))return ERROR_INVALID_DATA;
#if WOJD_CHAT_RUNTIME
    lco_cache_value(path,L"callback_setup",view->size,&g_lcr_apis.setup);
    lco_cache_value(path,L"callback_check",view->size,&g_lcr_apis.check);
    lco_cache_value(path,L"callback_string",view->size,&g_lcr_apis.string);
#endif
    return lco_metadata(view,result)?ERROR_SUCCESS:ERROR_REVISION_MISMATCH;
}
static DWORD lco_cache_save(const LcoResult *result) {
    WCHAR path[1024],temporary[1024];char text[256];HANDLE file;DWORD written,error=ERROR_SUCCESS;int length;
    if(!lco_path(path,L"chat-lua-cache.ini") ||
       _snwprintf_s(temporary,1024,_TRUNCATE,L"%s.tmp.%lu.%llu",path,GetCurrentProcessId(),GetTickCount64())<0)return ERROR_FILENAME_EXCED_RANGE;
    length=_snprintf_s(text,sizeof(text),_TRUNCATE,"[lua-observer]\r\nversion=1\r\nfactory=%08lx\r\ninitializer=%08lx\r\ntable=%08lx\r\nglobal=%08lx\r\n",result->factory,result->initializer,result->table,result->global);
#if WOJD_CHAT_RUNTIME
    if(length>=0 && g_lcr_apis.setup && g_lcr_apis.check && g_lcr_apis.string) {
        int extra=_snprintf_s(text+length,sizeof(text)-(SIZE_T)length,_TRUNCATE,
            "callback_setup=%08lx\r\ncallback_check=%08lx\r\ncallback_string=%08lx\r\n",
            g_lcr_apis.setup,g_lcr_apis.check,g_lcr_apis.string);
        if(extra<0)return ERROR_INSUFFICIENT_BUFFER;length+=extra;
    }
#endif
    if(length<0)return ERROR_INSUFFICIENT_BUFFER;
    file=CreateFileW(temporary,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);if(file==INVALID_HANDLE_VALUE)return GetLastError();
    if(!WriteFile(file,text,(DWORD)length,&written,NULL) || written!=(DWORD)length || !FlushFileBuffers(file))error=GetLastError()?GetLastError():ERROR_WRITE_FAULT;
    CloseHandle(file);if(!error && !MoveFileExW(temporary,path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))error=GetLastError();
    return error;
}
static BOOL lco_take_arm(void) {
    static const char expected[]="WOJD_CHAT_LOADER_OBSERVER_V1\n";
    WCHAR path[1024],used[1024];char bytes[sizeof(expected)];HANDLE file;LARGE_INTEGER size;DWORD got,attributes;BOOL ok;
    if(!lco_path(path,L"chat-observer.arm"))return FALSE;
    attributes=GetFileAttributesW(path);if(attributes==INVALID_FILE_ATTRIBUTES || (attributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)))return FALSE;
    file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
    if(file==INVALID_HANDLE_VALUE)return FALSE;
    ok=GetFileSizeEx(file,&size) && size.QuadPart==sizeof(expected)-1 && ReadFile(file,bytes,sizeof(expected),&got,NULL) && got==sizeof(expected)-1 && !memcmp(bytes,expected,sizeof(expected)-1);
    CloseHandle(file);if(!ok)return FALSE;
    if(_snwprintf_s(used,1024,_TRUNCATE,L"%s.used.%lu.%llu",path,GetCurrentProcessId(),GetTickCount64())<0)return FALSE;
    return MoveFileExW(path,used,MOVEFILE_WRITE_THROUGH);
}
static void lco_notify(const WCHAR *text) {
    typedef int (WINAPI *MessageBoxFn)(HWND,LPCWSTR,LPCWSTR,UINT);
    HMODULE module=LoadLibraryW(L"user32.dll");MessageBoxFn message;
    if(!module)return;
    message=(MessageBoxFn)(uintptr_t)GetProcAddress(module,"MessageBoxW");
    if(message)message(NULL,text,
#if WOJD_CHAT_RUNTIME
        L"WOJD — dịch chat Việt",
#else
        L"WOJD — bộ thử kết nối chat",
#endif
        MB_OK|MB_ICONINFORMATION|MB_SETFOREGROUND);
    FreeLibrary(module);
}
static DWORD WINAPI lco_worker(void *unused) {
    ImageView view;LcoResult result,hint;DWORD error=ERROR_NOT_READY,cache_error,attempts=0;ULONGLONG start=GetTickCount64(),last_scan=0,installed_at;
    (void)unused;
#if WOJD_CHAT_RUNTIME
    {
        WCHAR configuration[1024];
        if(!cq_configuration(configuration))return ERROR_CANCELLED;
    }
#else
    if(!lco_take_arm())return ERROR_CANCELLED;
#endif
#if WOJD_CHAT_RUNTIME
    logf_n4("CHAT_RECEIVE_ARMED","mode=PLAYER_INCOMING_CONFIGURED original_rows_unchanged=1");
#else
    logf_n4("CHAT_OBSERVER_ARMED","mode=LOADER_ONLY capture_chat=0");
#endif
    if(!image_view(g_image_base,&view)){error=ERROR_BAD_EXE_FORMAT;goto failed;}
    ZeroMemory(&result,sizeof(result));cache_error=lco_cache_load(&view,&result);hint=result;
    if(!cache_error)error=ERROR_SUCCESS;
    else do {
        ULONGLONG now=GetTickCount64();
        /* Hints can point into pages unpacked after our DLL starts. Retry
           only their bounded ABI validation; a stored RVA never grants trust. */
        if(hint.factory && hint.initializer && hint.table && hint.global && lco_metadata(&view,&hint)) {
            result=hint;error=ERROR_SUCCESS;break;
        }
        if(!last_scan || now-last_scan>=10000) {
            last_scan=now;++attempts;error=lco_discover(&view,&result);
            logf_n4("CHAT_OBSERVER_DISCOVERY","attempt=%lu status=%lu",attempts,error);
            if(error==ERROR_SUCCESS)break;
            if(error!=ERROR_NOT_FOUND && error!=ERROR_NOT_READY)goto failed;
        }
        Sleep(50);
    }while(GetTickCount64()-start<300000);
    if(error)goto failed;
    if(cache_error){DWORD save_error=lco_cache_save(&result);logf_n4("CHAT_OBSERVER_CACHE","status=%lu",save_error);}
    do {
        error=lco_object_ready(&view,&result);if(error!=ERROR_NOT_READY)break;
        Sleep(1);
    }while(GetTickCount64()-start<300000);
    if(error)goto failed;
    error=lco_install(&view,&result);if(error)goto failed;
#if WOJD_CHAT_RUNTIME
    logf_n4("CHAT_CALLBACK_CACHE","status=%lu",lco_cache_save(&result));
#endif
    logf_n4("CHAT_OBSERVER_READY","cached=%u elapsed_ms=%llu",!cache_error,GetTickCount64()-start);
    installed_at=GetTickCount64();
    while(!g_lco_executed && GetTickCount64()-installed_at<300000)Sleep(50);
    error=lco_restore();g_lco_observation.restored=error;
    if(g_lco_type_target)MH_DisableHook(g_lco_type_target);
    installed_at=GetTickCount64();while((g_lco_inflight || g_lco_type_inflight) && GetTickCount64()-installed_at<30000)Sleep(10);
    if(g_lco_inflight || g_lco_type_inflight){logf_n4("CHAT_OBSERVER_BUSY","inflight=%ld restore_status=%lu",g_lco_inflight,error);return ERROR_BUSY;}
    lco_type_remove();
    logf_n4("CHAT_OBSERVER_RESULT","seen=%ld lua_chunks=%ld selected=%ld source_bytes=%lu output_bytes=%lu codec=%lu load_status=%lu restore_status=%lu envelope_loaded=%lu envelope_status=%lu",
        g_lco_seen,g_lco_lua_chunks,g_lco_taken,g_lco_observation.source_bytes,g_lco_observation.output_bytes,
        g_lco_observation.codec_status,g_lco_observation.load_status,error,g_lco_observation.envelope_loaded,g_lco_observation.envelope_status);
#if WOJD_CHAT_RUNTIME
    logf_n4("CHAT_RECEIVE_EXECUTION","executed=%ld modules=%ld",g_lco_executed,g_cq.modules);
    if(g_lco_executed)logf_n4("CHAT_RECEIVE_MODULES_READY","modules=%ld model_io_on_ui=0",g_cq.modules);
    else lco_notify(L"Chưa nối đủ hai phần hiển thị chat trong lần chạy này. Dịch chat chưa sẵn sàng.\n\nBạn có thể tiếp tục chơi; tin gốc vẫn được giữ nguyên.");
#else
    logf_n4("CHAT_OBSERVER_EXECUTION","executed=%ld kinds=%s",g_lco_executed,g_lco_executed?g_lco_kinds:"UNAVAILABLE");
    if(g_lco_executed)lco_notify(L"Đã xác nhận phần mở rộng chạy trong module chat. Chưa bật dịch tin nhắn.\n\nBạn có thể thoát game bình thường để kiểm tra kết quả.");
    else if(g_lco_ready)lco_notify(L"Game đã nạp phần mở rộng chat nhưng chưa nhận được tín hiệu xác nhận nó chạy. Chưa bật dịch tin nhắn.\n\nBạn hãy thoát game bình thường để kiểm tra kết quả.");
    else lco_notify(L"Chưa gặp lượt nạp module chat trong lần chạy này. Bộ thử đã dừng.\n\nBạn hãy thoát game bình thường để kiểm tra log và vị trí đã lưu.");
#endif
    return error;
failed:
    logf_n4("CHAT_OBSERVER_FAILED","status=%lu attempts=%lu elapsed_ms=%llu",error,attempts,GetTickCount64()-start);
#if WOJD_CHAT_RUNTIME
    lco_notify(L"Dịch chat chưa sẵn sàng trong lần chạy này. Phần Việt hóa game vẫn hoạt động.\n\nBạn có thể tiếp tục chơi và báo lại thông báo này để kiểm tra.");
#else
    lco_notify(L"Bộ thử chưa nối được vào phần nạp chat. Chưa bật dịch tin nhắn.\n\nBạn hãy thoát game bình thường để kiểm tra nguyên nhân trong kết quả thử.");
#endif
    return error;
}
static void lco_start(void) {
    HANDLE thread=CreateThread(NULL,0,lco_worker,NULL,0,NULL);
    if(thread)CloseHandle(thread);else logf_n4("CHAT_OBSERVER_FAILED","stage=THREAD status=%lu",GetLastError());
}
