/* Owned public-Lua and loopback fixture only. Never opens a game process. */
#define WOJD_CHAT_OBSERVER 1
#define WOJD_CHAT_RUNTIME 1
#define WOJD_CHAT_OBSERVER_TEST 1
#define WOJD_CAPTURE 0
#define WOJD_SELFTEST 0
#include "../src/localization.c"
__declspec(dllexport) DWORD WINAPI WojdChatReceiveFixtureGoogleTransport(CgTestTransport callback) {
    if(g_game_host||g_cq.worker)return ERROR_ACCESS_DENIED;g_cg_test_transport=callback;return ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdChatReceiveFixtureGoogleStats(DWORD *out,DWORD size) {
    if(g_game_host||!out||size!=7)return ERROR_ACCESS_DENIED;
    out[0]=(DWORD)g_cg.requests;out[1]=(DWORD)g_cg.cache_hits;out[2]=g_cg.last_ms;out[3]=g_cg.http_status;
    out[4]=g_cg.last_error;out[5]=(DWORD)g_cg.decode_errors;out[6]=(DWORD)g_cg.placeholder_errors;return ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdChatReceiveFixtureScrollStats(LONG *out,DWORD size) {
    if(g_game_host||!out||size!=5)return ERROR_ACCESS_DENIED;
    out[0]=g_cq.scroll_follow;out[1]=g_cq.scroll_settled;out[2]=g_cq.scroll_cancelled;
    out[3]=g_cq.scroll_unsettled;out[4]=g_cq.scroll_prepass;return ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdChatReceiveFixtureExpose(BYTE *bytes,SIZE_T size,unsigned kind,unsigned *out) {
    LcmLayout layout;int status;if(g_game_host || !bytes || !out)return ERROR_ACCESS_DENIED;
    status=lcm_expose(bytes,size,kind,&layout);if(status)return (DWORD)status;
    out[0]=layout.methods;out[1]=layout.resend;out[2]=layout.upvalue;return ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdChatReceiveFixturePrepare(const WCHAR *root,void **pointers) {
    if(g_game_host || !root || !pointers || g_cq.worker || wcscpy_s(g_root_path,1024,root))return ERROR_ACCESS_DENIED;
    ZeroMemory(&g_lcr_apis,sizeof(g_lcr_apis));
    g_lcr_apis.bind.gettop=(int (*)(void *))(uintptr_t)pointers[0];
    g_lcr_apis.bind.type=(int (*)(void *,int))(uintptr_t)pointers[1];
    g_lcr_apis.bind.checkstack=(int (*)(void *,int))(uintptr_t)pointers[2];
    g_lcr_apis.bind.pushcclosure=(void (*)(void *,LcbFunction,int))(uintptr_t)pointers[3];
    g_lcr_apis.bind.setupvalue=(const char *(*)(void *,int,int))(uintptr_t)pointers[4];
    g_lcr_apis.bind.settop=(void (*)(void *,int))(uintptr_t)pointers[5];
    g_lcr_apis.tostring=(LcoStringLengthFn)(uintptr_t)pointers[6];
    g_lcr_apis.pushstring=(LcrPushString)(uintptr_t)pointers[7];
    return cq_prepare(&g_lcr_apis);
}
__declspec(dllexport) DWORD WINAPI WojdChatReceiveFixtureBind(void *object,void **table,DWORD slots,DWORD slot,LcoLoadFn load,LcoPopFn pop) {
    if(g_game_host)return ERROR_ACCESS_DENIED;return lco_bind(object,table,slots,slot,load,pop);
}
__declspec(dllexport) int WINAPI WojdChatReceiveFixtureLoad(void *self,void *L,const char *buffer,SIZE_T size,const char *name,const char *mode) {
    if(g_game_host || !g_lco_load)return ERROR_ACCESS_DENIED;
    return lco_load_hook(self,L,buffer,size,name,mode);
}
__declspec(dllexport) DWORD WINAPI WojdChatReceiveFixtureStats(LONG *out,DWORD size) {
    if(g_game_host || !out || size!=8)return ERROR_ACCESS_DENIED;
    out[0]=g_cq.modules;out[1]=g_cq.received;out[2]=g_cq.completed;out[3]=g_cq.rendered;
    out[4]=g_cq.dropped;out[5]=g_cq.network_errors;out[6]=g_cq.owner_rejections;out[7]=g_cq.online;
    return ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdChatReceiveFixtureStop(void) {
    DWORD status;if(g_game_host)return ERROR_ACCESS_DENIED;
    lco_restore();InterlockedExchange(&g_cq.online,0);
    if(g_cq.worker) {
        status=WaitForSingleObject(g_cq.worker,5000);if(status!=WAIT_OBJECT_0)return ERROR_TIMEOUT;
        CloseHandle(g_cq.worker);g_cq.worker=NULL;
    }
    return ERROR_SUCCESS;
}
