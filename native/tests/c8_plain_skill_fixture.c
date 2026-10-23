/* Private Windows x64 fixture. Compiles the actual proposed helpers, not a
   Python reimplementation. It never opens the game or hooks executable code.
   Example: cl /nologo /W4 /Od shared_resolver_fixture.c /Fe:fixture.exe */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef struct ImageView {BYTE *base;DWORD size;WORD section_count;IMAGE_SECTION_HEADER sections[96];} ImageView;
typedef struct DataResult {DWORD status,candidates;ULONGLONG reader,assign,raw_reader;} DataResult;
static BOOL g_game_host=TRUE;
static BYTE *g_image_base;
static WCHAR g_root_path[1024],g_host_path[1024];
#define GAME_EXE g_host_path
#include "../src/native_data_memory.inc"
#include "../src/native_data_signatures.h"
static BOOL signature_at(const ImageView *view,const BYTE *address,const BYTE *expected,const BYTE *mask,SIZE_T n) {
    BYTE bytes[1024];return n<=sizeof(bytes) && in_image(view,address,n) && executable(view,address) && read_exact(address,bytes,n) && masked_match(bytes,expected,mask,n);
}
static DWORD fixture_probe_log_count;
static void fixture_probe_log(const char *event,const char *format,...) {(void)event;(void)format;fixture_probe_log_count++;}
#define WOJD_PROBE_LOG fixture_probe_log
#include "../src/native_data_probe_diagnostics.inc"
static void (*g_discovery_pump)(void);
#include "../src/native_data_resolver.inc"
#include "../src/native_data_cache.inc"
#include "../src/native_tooltip_profile.h"
#define WOJD_NATIVE_UOBJECT_REUSE_FIELD_SITE_TYPE
#include "../src/native_tooltip_uobject_profile.h"
#include "../src/native_tooltip_plain_context.h"
#include "../src/native_tooltip_resolver.inc"
#include "../src/native_tooltip_plain_resolver.inc"
static RUNTIME_FUNCTION functions[7];
static DWORD plain_anchors[2];
static int checks,failures;
#define CHECK(test,label) do {checks++;if(!(test)){printf("FAIL %s line=%d\n",label,__LINE__);failures++;}else printf("PASS %s\n",label);}while(0)
static void call_to(BYTE *call,const BYTE *target) {LONG delta=(LONG)(target-(call+5));call[0]=0xe8;memcpy(call+1,&delta,4);}
static void plant_plain(DWORD group,DWORD anchor,const BYTE *target) {
    DWORD i;const WojdNativeUobjectSiteContext *first=&WOJD_PLAIN_SITE_CONTEXTS[g_tooltip_plain_indices[group][0]];
    for(i=0;i<g_tooltip_plain_counts[group];i++) {
        const WojdNativeUobjectSiteContext *context=&WOJD_PLAIN_SITE_CONTEXTS[g_tooltip_plain_indices[group][i]];
        BYTE *at=g_image_base+anchor+(LONGLONG)context->context_rva-first->return_rva;
        memcpy(at,context->bytes,context->size);call_to(at+context->size-5,target);
    }
}
static void plant_native(DWORD group,DWORD anchor) {
    DWORD j;const TooltipGroup *g=&g_tooltip_groups[group];
    const WojdNativeUobjectSiteContext *first=&WOJD_NATIVE_UOBJECT_SITE_CONTEXTS[g->first];
    for(j=0;j<g->count;j++) {
        const WojdNativeUobjectSiteContext *context=&WOJD_NATIVE_UOBJECT_SITE_CONTEXTS[g->first+j];
        BYTE *at=g_image_base+anchor+(LONGLONG)context->context_rva-first->return_rva;
        memcpy(at,context->bytes,context->size);call_to(at+context->size-5,g_image_base+0x40000);
    }
}
static BOOL make_image(void) {
    IMAGE_DOS_HEADER *dos;IMAGE_NT_HEADERS64 *nt;IMAGE_SECTION_HEADER *section;DWORD i;
    g_image_base=(BYTE *)VirtualAlloc(NULL,0x90000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    if(!g_image_base)return FALSE;
    dos=(IMAGE_DOS_HEADER *)g_image_base;dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;
    nt=(IMAGE_NT_HEADERS64 *)(g_image_base+0x80);nt->Signature=IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine=IMAGE_FILE_MACHINE_AMD64;nt->FileHeader.NumberOfSections=1;
    nt->FileHeader.SizeOfOptionalHeader=sizeof(IMAGE_OPTIONAL_HEADER64);nt->FileHeader.TimeDateStamp=0x12345678;
    nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR64_MAGIC;nt->OptionalHeader.SizeOfImage=0x90000;
    section=IMAGE_FIRST_SECTION(nt);section->VirtualAddress=0x1000;section->Misc.VirtualSize=0x7f000;
    section->Characteristics=IMAGE_SCN_MEM_EXECUTE|IMAGE_SCN_MEM_READ;
    g_image_base[0x80000]=1;
    for(i=0;i<7;i++) {
        functions[i].BeginAddress=(i+1)*0x10000;
        functions[i].EndAddress=functions[i].BeginAddress+((i==3 || i==5)?TOOLTIP_SERIALIZER_EXTENT:0x1000);
        functions[i].UnwindData=0x80000;
    }
    if(!RtlAddFunctionTable(functions,7,(DWORD64)(uintptr_t)g_image_base))return FALSE;
    memcpy(g_image_base+0x40000,WOJD_FSTRING_SERIALIZER_BYTES48,48);
    plain_anchors[0]=0x1004f;plain_anchors[1]=0x2004f;
    plant_plain(0,plain_anchors[0],g_image_base+0x40000);plant_plain(1,plain_anchors[1],g_image_base+0x40000);
    return image_view(g_image_base,&g_tooltip_plain_view);
}
static void reset_plain(DWORD identity_status) {
    DWORD i;ZeroMemory(g_tooltip_plain,sizeof(g_tooltip_plain));
    ZeroMemory(&g_tooltip_plain_scan,sizeof(g_tooltip_plain_scan));g_tooltip_plain_started=TRUE;
    g_tooltip_plain_exhausted=FALSE;g_tooltip_plain_phases=0;g_tooltip_plain_retry_steps=0;
    for(i=0;i<2;i++) {
        g_tooltip_plain[i].hint_status=identity_status;g_tooltip_plain[i].hint_anchor=plain_anchors[i];
        g_tooltip_plain[i].hint_serializer=0x40000;g_tooltip_plain[i].hint_owner=(i+1)*0x10000;
    }
}
static void run_plain_pass(void) {DWORD i;for(i=0;i<1000 && !g_tooltip_plain_exhausted &&
    !(g_tooltip_plain[0].ready && g_tooltip_plain[1].ready);i++)tooltip_plain_resolver_step();}
static volatile LONG reader_go,reader_bad;
static DWORD WINAPI map_reader(void *unused) {
    DWORD i,j;(void)unused;
    while(!InterlockedCompareExchange(&reader_go,0,0))SwitchToThread();
    for(i=0;i<50000;i++) {
        const TooltipOriginMap *map=(const TooltipOriginMap *)InterlockedCompareExchangePointer(&g_tooltip_origin_map,NULL,NULL);
        if(!map || (map->count!=9 && map->count!=11 && map->count!=26)){InterlockedExchange(&reader_bad,1);break;}
        for(j=0;j<map->count;j++)if(!map->sites[j].caller || !map->sites[j].site ||
           map->sites[j].native_layout!=(j>=11)){InterlockedExchange(&reader_bad,1);break;}
    }
    return 0;
}
int main(void) {
    DWORD i,owner,old,scan_steps;const BYTE *target;BOOL layout;BYTE saved,patched[48];
    TooltipPlainGroup *group;const TooltipOriginMap *old_map;HANDLE reader;
    GetModuleFileNameW(NULL,g_host_path,1024);wcscpy_s(g_root_path,1024,L".");
    if(!make_image()){printf("setup error=%lu\n",GetLastError());return 2;}
    for(i=0;i<2;i++)CHECK(tooltip_plain_group_valid(&g_tooltip_plain_view,i,plain_anchors[i],&target,&owner) &&
        target==g_image_base+0x40000 && owner==(i+1)*0x10000,"relocated Plain full group + unique unwind owner + E8 consensus");
    saved=g_image_base[plain_anchors[0]-15];g_image_base[plain_anchors[0]-15]^=1;
    CHECK(!tooltip_plain_group_valid(&g_tooltip_plain_view,0,plain_anchors[0],&target,&owner),"one changed full context rejected");
    CHECK(tooltip_plain_group_valid(&g_tooltip_plain_view,1,plain_anchors[1],&target,&owner),"Skill context failure does not invalidate Buff");
    g_image_base[plain_anchors[0]-15]=saved;
    call_to(g_image_base+plain_anchors[0]-5,g_image_base+0x60000);
    CHECK(!tooltip_plain_group_valid(&g_tooltip_plain_view,0,plain_anchors[0],&target,&owner),"single inconsistent E8 fails full Skill group");
    plant_plain(0,plain_anchors[0],g_image_base+0x40000);
    functions[3].EndAddress--;CHECK(!tooltip_serializer_valid(&g_tooltip_plain_view,g_image_base+0x40000),"serializer extent change rejected");functions[3].EndAddress++;
    reset_plain(ERROR_INVALID_DATA);run_plain_pass();
    CHECK(g_tooltip_plain[0].ready && g_tooltip_plain[1].ready && g_tooltip_plain[0].route==CACHE_ROUTE_CALIBRATION &&
        g_tooltip_plain_scan.steps>1,"cold signature scan resolves two groups independently in bounded steps");
    plant_plain(0,0x5004f,g_image_base+0x40000);reset_plain(ERROR_INVALID_DATA);run_plain_pass();
    CHECK(g_tooltip_plain[0].error==ERROR_DUP_NAME && g_tooltip_plain[1].ready,"ambiguous Skill fails closed while Buff completes");
    ZeroMemory(g_image_base+0x50000,0x1000);
    plant_plain(1,0x7004f,g_image_base+0x40000);reset_plain(ERROR_INVALID_DATA);run_plain_pass();
    CHECK(g_tooltip_plain[1].error==ERROR_DUP_NAME && g_tooltip_plain[0].ready,"ambiguous Buff fails closed while Skill completes");
    ZeroMemory(g_image_base+0x70000,0x1000);
    reset_plain(ERROR_SUCCESS);tooltip_plain_resolver_step();
    CHECK(g_tooltip_plain[0].ready && g_tooltip_plain[1].ready && g_tooltip_plain[0].route==CACHE_ROUTE_WARM &&
        g_tooltip_plain_scan.steps==0,"current exact cache chain enables without relocation scan");
    reset_plain(ERROR_SUCCESS);g_tooltip_plain[0].hint_serializer=0x60000;run_plain_pass();
    CHECK(g_tooltip_plain[0].ready && g_tooltip_plain[0].route==CACHE_ROUTE_CALIBRATION &&
        g_tooltip_plain[1].route==CACHE_ROUTE_WARM,"current identity with changed callee cannot masquerade as warm");
    reset_plain(ERROR_REVISION_MISMATCH);run_plain_pass();
    CHECK(g_tooltip_plain[0].ready && g_tooltip_plain[0].route==CACHE_ROUTE_CALIBRATION,"stale valid hints require relocation validation and restart");
    reset_plain(ERROR_SUCCESS);VirtualProtect(g_image_base+0x40000,0x1000,PAGE_NOACCESS,&old);
    for(i=0;i<128;i++)tooltip_plain_resolver_step();
    CHECK(!g_tooltip_plain[0].ready && !g_tooltip_plain[0].error,"current cache survives more than 32 unreadable startup probes");
    g_tooltip_plain_exhausted=TRUE;scan_steps=g_tooltip_plain_scan.steps;
    for(i=0;i<128;i++)tooltip_plain_resolver_step();
    CHECK(g_tooltip_plain_scan.steps==scan_steps && !g_tooltip_plain[0].error,"retained current cache waits without charging exhausted scan quota");
    VirtualProtect(g_image_base+0x40000,0x1000,old,&old);tooltip_plain_resolver_step();
    CHECK(g_tooltip_plain[0].ready && g_tooltip_plain[0].route==CACHE_ROUTE_WARM,"late code recovery retains warm eligibility");
    reset_plain(ERROR_REVISION_MISMATCH);VirtualProtect(g_image_base+0x40000,0x1000,PAGE_NOACCESS,&old);
    g_tooltip_plain_exhausted=TRUE;tooltip_plain_resolver_step();
    VirtualProtect(g_image_base+0x40000,0x1000,old,&old);tooltip_plain_resolver_step();run_plain_pass();
    CHECK(g_tooltip_plain[0].ready && g_tooltip_plain[0].route==CACHE_ROUTE_CALIBRATION,"stale late hint restarts bounded full uniqueness scan");
    memcpy(g_tooltip_serializer_original48,g_image_base+0x40000,48);
    memset(g_image_base+0x40000,0x99,14);memcpy(g_tooltip_serializer_installed48,g_image_base+0x40000,48);
    memcpy(patched,g_tooltip_serializer_installed48,48);g_tooltip_owned_serializer=g_image_base+0x40000;
    CHECK(tooltip_serializer_valid(&g_tooltip_plain_view,g_image_base+0x40000),"owned actual fourteen-byte patch snapshot accepted without guessing patch length");
    g_image_base[0x4000b]^=1;
    CHECK(!tooltip_serializer_valid(&g_tooltip_plain_view,g_image_base+0x40000),"unexpected change inside owned patch fails closed");
    memcpy(g_image_base+0x40000,patched,48);g_image_base[0x40020]^=1;
    CHECK(!tooltip_serializer_valid(&g_tooltip_plain_view,g_image_base+0x40000),"unexpected change after owned patch fails closed");
    memcpy(g_image_base+0x40000,g_tooltip_serializer_original48,48);g_tooltip_owned_serializer=NULL;
    reset_plain(ERROR_SUCCESS);tooltip_plain_resolver_step();
    saved=g_image_base[plain_anchors[0]-15];g_image_base[plain_anchors[0]-15]^=1;
    CHECK(tooltip_fresh_plain_group(0)==ERROR_INVALID_DATA && tooltip_publish_plain_origins(0)==ERROR_INVALID_DATA &&
        !g_tooltip_origin_count && !InterlockedCompareExchangePointer(&g_tooltip_origin_map,NULL,NULL),
        "resolved Skill context changed during allocator wait cannot publish stale origins");
    g_image_base[plain_anchors[0]-15]=saved;
    VirtualProtect(g_image_base+0x10000,0x1000,PAGE_NOACCESS,&old);
    CHECK(tooltip_fresh_plain_group(0)==ERROR_NOT_READY && tooltip_publish_plain_origins(0)==ERROR_NOT_READY && !g_tooltip_origin_count,
        "transient unreadable resolved Skill stays pending without origin publication");
    VirtualProtect(g_image_base+0x10000,0x1000,old,&old);
    CHECK(tooltip_fresh_plain_group(0)==ERROR_SUCCESS,"resolved Skill can freshly validate after transient allocator wait");
    CHECK(tooltip_publish_plain_origins(0)==ERROR_SUCCESS && g_tooltip_origin_count==9,"publish only nine approved Skill origins");
    old_map=(const TooltipOriginMap *)InterlockedCompareExchangePointer(&g_tooltip_origin_map,NULL,NULL);
    reader=CreateThread(NULL,0,map_reader,NULL,0,NULL);InterlockedExchange(&reader_go,1);
    CHECK(tooltip_publish_plain_origins(1)==ERROR_SUCCESS && g_tooltip_origin_count==11,"add independent Buff map while reader is active");
    CHECK(old_map->count==9 && old_map->sites[0].native_layout==FALSE,"previous immutable snapshot remains coherent after publication");
    for(i=0;i<3;i++) {
        g_tooltip_resolved.owners[i]=0x30000+i*0x20000;
        g_tooltip_resolved.anchors[i]=g_tooltip_resolved.owners[i]+0x50;
        plant_native(i,g_tooltip_resolved.anchors[i]);
    }
    g_tooltip_resolved.serializer=g_image_base+0x40000;g_tooltip_view=g_tooltip_plain_view;g_tooltip_resolver_ready=TRUE;
    CHECK(tooltip_publish_origins()==ERROR_SUCCESS && g_tooltip_origin_count==26,"add Native approved policy without replacing Plain map");
    WaitForSingleObject(reader,INFINITE);CloseHandle(reader);
    CHECK(!reader_bad,"concurrent acquire reader sees count, caller, metadata and layout from one immutable snapshot");
    CHECK(tooltip_origin_lookup(g_image_base+plain_anchors[0],&layout)==&WOJD_PLAIN_APPROVED_FIELD_SITES[0] && !layout,
        "Plain exact return address and layout preserved, no call/return off-by-five");
    CHECK(!tooltip_origin_lookup(g_image_base+plain_anchors[0]-5,&layout),"E8 instruction address is not approved return address");
    CHECK(tooltip_origin_lookup(g_image_base+0x30050,&layout)==&WOJD_NATIVE_UOBJECT_FIELD_SITES[0] && layout,
        "Native origin independently retains Native layout");
    CHECK(!tooltip_origin_lookup(g_image_base+0x3367fc0,&layout),"unverified Plain Mail remains disabled");
    CHECK(tooltip_publish_plain_origins(0)==ERROR_INVALID_STATE,"group cannot mutate a published origin snapshot");
    group=&g_tooltip_plain[0];GetFullPathNameW(L"source-plain-skill-fixture.ini",1024,group->cache_path,NULL);DeleteFileW(group->cache_path);
    CHECK(tooltip_plain_cache_save(group)==ERROR_SUCCESS,"per-group cache written with current file identity");
    group->hint_anchor=group->hint_serializer=group->hint_owner=0;
    CHECK(tooltip_plain_cache_load(group)==ERROR_SUCCESS && group->hint_anchor==plain_anchors[0] &&
        group->hint_serializer==0x40000 && group->hint_owner==0x10000,"cache load retains complete anchor/callee/owner hint chain");
    WritePrivateProfileStringW(L"PlainTooltip",L"file_size",L"1",group->cache_path);
    CHECK(tooltip_plain_cache_load(group)==ERROR_REVISION_MISMATCH && group->hint_anchor==plain_anchors[0],"identity change marks stale and retains usable hint");
    DeleteFileW(group->cache_path);
    RtlDeleteFunctionTable(functions);VirtualFree(g_image_base,0,MEM_RELEASE);
    printf("SUMMARY checks=%d failures=%d\n",checks,failures);return failures?1:0;
}
