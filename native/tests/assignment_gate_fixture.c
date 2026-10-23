#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <wchar.h>
#include <string.h>
typedef struct GameString { WCHAR *data;int count,capacity; } GameString;
typedef struct Stream { const BYTE *data;SIZE_T size,position;DWORD calls,last_key; } Stream;
__declspec(dllexport) GameString * __fastcall WojdFixtureAssignImpl(GameString *out,const WCHAR *text) {
    SIZE_T n=wcslen(text)+1;WCHAR *copy=(WCHAR *)HeapAlloc(GetProcessHeap(),0,n*sizeof(WCHAR));
    if(!copy)return out;memcpy(copy,text,n*sizeof(WCHAR));
    if(out->data)HeapFree(GetProcessHeap(),0,out->data);out->data=copy;out->count=(int)n;out->capacity=(int)n;return out;
}
__declspec(dllexport) void __fastcall WojdFixtureFree(GameString *out) {if(out->data)HeapFree(GetProcessHeap(),0,out->data);ZeroMemory(out,sizeof(*out));}
extern GameString * __fastcall WojdFixtureAssignmentOrigin(GameString *,const WCHAR *);
__declspec(dllexport) __declspec(noinline) BYTE __fastcall WojdFixtureRead(Stream *stream,GameString *out,DWORD key) {
    DWORD n,i;BYTE *decoded;WCHAR *wide;int chars;stream->calls++;stream->last_key=key;
    if(stream->position+4>stream->size)return 0;
    memcpy(&n,stream->data+stream->position,4);stream->position+=4;
    if(n>65535 || n>stream->size-stream->position)return 0;
    decoded=(BYTE *)HeapAlloc(GetProcessHeap(),0,(SIZE_T)n+1);if(!decoded)return 0;
    for(i=0;i<n;i++)decoded[i]=stream->data[stream->position+i]^((BYTE *)&key)[i%4];decoded[n]=0;stream->position+=n;
    chars=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,(char *)decoded,(int)n,NULL,0);
    if(chars<1){HeapFree(GetProcessHeap(),0,decoded);return 0;}
    wide=(WCHAR *)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,((SIZE_T)chars+1)*2);if(!wide){HeapFree(GetProcessHeap(),0,decoded);return 0;}
    MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,(char *)decoded,(int)n,wide,chars);
    WojdFixtureAssignmentOrigin(out,wide);HeapFree(GetProcessHeap(),0,wide);HeapFree(GetProcessHeap(),0,decoded);return 1;
}

/* Unreachable RIP-relative relocation must fail closed in forced-far tests. */
static volatile ULONGLONG g_fixture_rip_value=0x713579ab2468ace0ull;
__declspec(dllexport) __declspec(noinline) ULONGLONG WojdFixtureRipRelative(void) {return g_fixture_rip_value;}
