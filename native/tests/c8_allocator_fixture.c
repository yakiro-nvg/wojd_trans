#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef struct ImageView {BYTE *base;DWORD size;WORD section_count;IMAGE_SECTION_HEADER sections[96];} ImageView;
typedef struct DataResult {DWORD status,candidates;ULONGLONG reader,assign,raw_reader;} DataResult;
#include "../src/native_data_memory.inc"
#include "../src/native_data_signatures.h"
static BOOL signature_at(const ImageView *v,const BYTE *at,const BYTE *b,const BYTE *m,SIZE_T n) {
    BYTE copy[1024];return n<=sizeof(copy) && in_image(v,at,n) && executable(v,at) && read_exact(at,copy,n) && masked_match(copy,b,m,n);
}
static BOOL signature_at_report(const ImageView *v,const BYTE *at,const BYTE *b,const BYTE *m,SIZE_T n,MemoryProbe *probe) {
    BYTE copy[1024];return n<=sizeof(copy) && in_image(v,at,n) && executable(v,at) && read_exact_report(at,copy,n,probe) && masked_match(copy,b,m,n);
}
static void code_probe_failure(DWORD route,const MemoryProbe *p){(void)route;(void)p;}
#define GAME_EXE L"D:\\unused-fixture-only"
static BOOL g_game_host;
#include "../src/native_data_assignment_signature.inc"
#include "../src/native_data_cache.inc"
#include "../src/native_tooltip_allocator.inc"
#include "../src/native_tooltip_notification.inc"
static int checks,failures,creates;static DWORD create_status;
static WCHAR notice_text[512];static int notices;
static int WINAPI notice_stub(HWND window,LPCWSTR text,LPCWSTR title,UINT flags) {
    (void)window;(void)title;(void)flags;wcscpy_s(notice_text,512,text);notices++;return IDOK;
}
#define CHECK(t,label) do{checks++;if(!(t)){printf("FAIL %s line=%d\n",label,__LINE__);failures++;}else printf("PASS %s\n",label);}while(0)
static DWORD create_stub(const BYTE *target,void **out) {
    (void)target;creates++;*out=create_status?NULL:(void *)(uintptr_t)0x1234;return create_status;
}
int main(void) {
    ImageView v;RUNTIME_FUNCTION functions[3];const BYTE *found;DWORD old;TooltipAllocatorPrepared state;TooltipNoticeState notice;
    ZeroMemory(&v,sizeof(v));v.size=0x2000;v.base=(BYTE *)VirtualAlloc(NULL,v.size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    if(!v.base)return 2;v.section_count=1;v.sections[0].Misc.VirtualSize=v.size;v.sections[0].Characteristics=IMAGE_SCN_MEM_EXECUTE|IMAGE_SCN_MEM_READ;
    ZeroMemory(functions,sizeof(functions));functions[0].BeginAddress=0x400;functions[0].EndAddress=0x419;functions[0].UnwindData=0xf00;
    functions[1].BeginAddress=0x600;functions[1].EndAddress=0x619;functions[1].UnwindData=0xf00;
    functions[2].BeginAddress=0x800;functions[2].EndAddress=0xc1b;functions[2].UnwindData=0xf00;
    v.base[0xf00]=1;
    if(!RtlAddFunctionTable(functions,3,(DWORD64)(uintptr_t)v.base))return 2;
    memcpy(v.base+0x600,data_assign_bytes,sizeof(data_assign_bytes));
    CHECK(tooltip_allocator_find(&v,v.base+0x800,&found)==ERROR_SUCCESS && found==v.base+0x600,"relocated assignment found without fixed-d0 distance");
    CHECK(tooltip_allocator_valid(&v,v.base+0x600),"25byte unwind root accepts full203byte signature");
    v.base[0x600+16]^=1;CHECK(tooltip_allocator_find(&v,v.base+0x800,&found)==ERROR_NOT_FOUND,"full signature rejects changed meaningful instruction");v.base[0x600+16]^=1;
    memcpy(v.base+0x400,data_assign_bytes,sizeof(data_assign_bytes));
    CHECK(tooltip_allocator_find(&v,v.base+0x800,&found)==ERROR_DUP_NAME && !found,"multiple valid assignment bodies fail closed");ZeroMemory(v.base+0x400,sizeof(data_assign_bytes));
    CHECK(VirtualProtect(v.base,4096,PAGE_NOACCESS,&old),"own unreadable fixture page set");
    CHECK(tooltip_allocator_find(&v,v.base+0x800,&found)==ERROR_NOT_READY,"unreadable candidate remains pending");
    CHECK(VirtualProtect(v.base,4096,old,&old),"own fixture page restored");
    CHECK(tooltip_allocator_find(&v,v.base+0x800,&found)==ERROR_SUCCESS,"later readable page recovers without deadline classification");
    CHECK(tooltip_allocator_find(&v,v.base+0x1040,&found)==ERROR_NOT_FOUND,"page-fringe search does not read previous inaccessible page");
    ZeroMemory(&state,sizeof(state));creates=0;create_status=0;
    CHECK(tooltip_allocator_create_once(&state,v.base+0x600,create_stub)==0 && creates==1 && state.trampoline==(void *)(uintptr_t)0x1234,"prepare establishes one stable trampoline");
    CHECK(tooltip_allocator_create_once(&state,v.base+0x600,create_stub)==0 && creates==1,"generic reuse never creates duplicate hook");
    CHECK(tooltip_allocator_create_once(&state,v.base+0x400,create_stub)==ERROR_INVALID_DATA && creates==1 && state.target==v.base+0x600,"published assignment cannot retarget");
    ZeroMemory(&state,sizeof(state));creates=0;create_status=ERROR_NOT_ENOUGH_MEMORY;
    CHECK(tooltip_allocator_create_once(&state,v.base+0x600,create_stub)==ERROR_NOT_ENOUGH_MEMORY && creates==1 && !state.trampoline,"failed creation never publishes trampoline");
    CHECK(tooltip_allocator_create_once(&state,v.base+0x600,create_stub)==ERROR_NOT_ENOUGH_MEMORY && creates==1,"failed attempt cannot accidentally create twice");
    CHECK(cache_probe_may_retry(ERROR_REVISION_MISMATCH,ERROR_NOT_READY),"parsed stale cache retained during code unreadability");
    CHECK(cache_probe_may_retry(ERROR_REVISION_MISMATCH,ERROR_NOT_FOUND),"parsed stale typed hint retained alongside relocation work");
    CHECK(!cache_probe_may_retry(ERROR_INVALID_DATA,ERROR_NOT_READY) && !cache_probe_may_retry(ERROR_SUCCESS,ERROR_INVALID_DATA),"malformed cache and invalid chain never get transient treatment");
    ZeroMemory(&notice,sizeof(notice));notices=0;
    CHECK(tooltip_notice_dispatch_groups(&notice,notice_stub,FALSE,ERROR_NOT_FOUND,TRUE,"PLAIN_BUFF",TRUE,TRUE)==0 &&
        wcsstr(notice_text,L"hi\u1ec7u \u1ee9ng") && wcsstr(notice_text,L"v\u1eabn ti\u1ebfp t\u1ee5c d\u1ecbch") &&
        wcsstr(notice_text,L"tho\u00e1t game v\u00e0 m\u1edf l\u1ea1i"),"partial failure names group, retains active routes and visible restart action");
    CHECK(tooltip_notice_dispatch_groups(&notice,notice_stub,FALSE,ERROR_NOT_FOUND,FALSE,"NATIVE",FALSE,FALSE)==0 && notices==1,"one terminal modal remains bounded");
    ZeroMemory(&notice,sizeof(notice));
    CHECK(tooltip_notice_dispatch_groups(&notice,notice_stub,FALSE,ERROR_INVALID_DATA,FALSE,"PLAIN_SKILL",FALSE,TRUE)==0 &&
        !wcsstr(notice_text,L"m\u1edf l\u1ea1i") && wcsstr(notice_text,L"v\u1eabn ti\u1ebfp t\u1ee5c d\u1ecbch"),"active unaffected groups do not imply cache or restart success");
    RtlDeleteFunctionTable(functions);VirtualFree(v.base,0,MEM_RELEASE);printf("RESULT checks=%d failures=%d\n",checks,failures);return failures?1:0;
}
