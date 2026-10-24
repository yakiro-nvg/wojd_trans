/* Synthetic host only. No game process is opened, started or inspected. */
#define WOJD_CHAT_OBSERVER 1
#define WOJD_CHAT_OBSERVER_TEST 1
#define WOJD_CAPTURE 0
#define WOJD_SELFTEST 0
#include "../src/localization.c"
#include "../src/chat_callback_resolver.inc"

__declspec(dllexport) DWORD WINAPI WojdChatFixtureResolveCallbacks(void *base,const LcoResult *binding,DWORD *hints,void **pointers,BOOL hints_only) {
    ImageView view;LcrApis result;DWORD error;
    if(g_game_host || !binding || !hints || !pointers || !image_view(base,&view))return ERROR_ACCESS_DENIED;
    ZeroMemory(&result,sizeof(result));result.setup=hints[0];result.check=hints[1];result.string=hints[2];
    error=lcr_resolve(&view,binding,&result,hints_only);if(error)return error;
    hints[0]=result.setup;hints[1]=result.check;hints[2]=result.string;
    pointers[0]=(void *)(uintptr_t)result.bind.gettop;pointers[1]=(void *)(uintptr_t)result.bind.type;
    pointers[2]=(void *)(uintptr_t)result.bind.checkstack;pointers[3]=(void *)(uintptr_t)result.bind.pushcclosure;
    pointers[4]=(void *)(uintptr_t)result.bind.setupvalue;pointers[5]=(void *)(uintptr_t)result.bind.settop;
    pointers[6]=(void *)(uintptr_t)result.tostring;pointers[7]=(void *)(uintptr_t)result.pushstring;
    return ERROR_SUCCESS;
}

typedef int (__fastcall *FixtureKindFn)(void *,int);
__declspec(dllexport) DWORD WINAPI WojdChatFixtureAttachType(void *target,FixtureKindFn kind,LcoStringLengthFn string_length) {
    if(g_game_host || !kind || target!=(void *)(uintptr_t)kind)return ERROR_ACCESS_DENIED;
    return lco_type_attach(target,string_length);
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureRestoreType(void) {
    if(g_game_host)return ERROR_ACCESS_DENIED;
    if(g_lco_type_target)MH_DisableHook(g_lco_type_target);
    return lco_type_remove();
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureTypeMarker(const char *text,SIZE_T size) {
    if(g_game_host)return ERROR_ACCESS_DENIED;return lco_type_marker(text,size)?ERROR_SUCCESS:ERROR_INVALID_DATA;
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureResolveType(void *base,const LcoResult *binding,void **output) {
    ImageView view;LcoKindFn kind;LcoStringLengthFn string_length;void *target;DWORD error;
    if(g_game_host || !binding || !output || !image_view(base,&view))return ERROR_ACCESS_DENIED;
    error=lco_type_resolve(&view,binding,&kind,&string_length,&target);if(error)return error;
    output[0]=(void *)(uintptr_t)kind;output[1]=(void *)(uintptr_t)string_length;output[2]=target;return ERROR_SUCCESS;
}

__declspec(dllexport) DWORD WINAPI WojdChatFixtureBind(void *object,void **table,DWORD slots,DWORD load_slot,LcoLoadFn load,LcoPopFn pop) {
    if(g_game_host)return ERROR_ACCESS_DENIED;
    return lco_bind(object,table,slots,load_slot,load,pop);
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureRestore(void) {
    if(g_game_host)return ERROR_ACCESS_DENIED;return lco_restore();
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureAttachBare(void *target) {
    MH_STATUS mh;if(g_game_host || !target || g_lco_bare_target)return ERROR_INVALID_STATE;
    mh=MH_Initialize();if(mh!=MH_OK && mh!=MH_ERROR_ALREADY_INITIALIZED)return ERROR_INVALID_STATE;
    mh=MH_CreateHook(target,(void *)(uintptr_t)lco_bare_load_hook,(void **)&g_lco_bare_load);if(mh!=MH_OK)return ERROR_INVALID_FUNCTION;
    mh=MH_EnableHook(target);if(mh!=MH_OK){MH_RemoveHook(target);return ERROR_INVALID_FUNCTION;}
    g_lco_bare_target=target;return ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureRestoreBare(void) {
    if(g_game_host || g_lco_bare_inflight)return ERROR_INVALID_STATE;
    if(g_lco_bare_target){MH_DisableHook(g_lco_bare_target);MH_RemoveHook(g_lco_bare_target);g_lco_bare_target=NULL;g_lco_bare_load=NULL;}
    return ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureExecution(char *output,DWORD size) {
    if(g_game_host || !output || size!=9)return ERROR_ACCESS_DENIED;
    if(g_lco_executed!=1)return ERROR_NOT_READY;memcpy(output,g_lco_kinds,9);return ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureMarker(const char *buffer,SIZE_T size,const char *name,const char *mode) {
    if(g_game_host)return ERROR_ACCESS_DENIED;return lco_marker(buffer,size,name,mode)?ERROR_SUCCESS:ERROR_INVALID_DATA;
}
__declspec(dllexport) int WINAPI WojdChatFixtureLoad(void *self,void *state,const char *buffer,SIZE_T size,const char *name,const char *mode) {
    if(g_game_host || !g_lco_load)return ERROR_INVALID_STATE;
    return lco_load_hook(self,state,buffer,size,name,mode);
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureStatus(DWORD *output,DWORD count) {
    if(g_game_host || !output || count!=13)return ERROR_ACCESS_DENIED;
    output[0]=(DWORD)g_lco_active;output[1]=(DWORD)g_lco_taken;output[2]=(DWORD)g_lco_ready;
    output[3]=(DWORD)g_lco_seen;output[4]=(DWORD)g_lco_lua_chunks;output[5]=(DWORD)g_lco_inflight;
    output[6]=g_lco_observation.source_bytes;output[7]=g_lco_observation.output_bytes;
    output[8]=g_lco_observation.codec_status;output[9]=g_lco_observation.load_status;
    output[10]=g_lco_observation.restored;output[11]=g_lco_observation.envelope_loaded;output[12]=g_lco_observation.envelope_status;
    return ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureResolve(void *base,LcoResult *output) {
    ImageView view;if(g_game_host || !output)return ERROR_ACCESS_DENIED;
    if(!image_view(base,&view))return ERROR_BAD_EXE_FORMAT;
    return lco_discover(&view,output);
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureValidate(void *base,LcoResult *output) {
    ImageView view;if(g_game_host || !output)return ERROR_ACCESS_DENIED;
    if(!image_view(base,&view))return ERROR_BAD_EXE_FORMAT;
    return lco_metadata(&view,output)?ERROR_SUCCESS:ERROR_INVALID_DATA;
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureAllocationFailure(DWORD ordinal) {
    if(g_game_host || g_lco_inflight || g_lco_alloc_live || ordinal>2)return ERROR_INVALID_STATE;
    g_lco_alloc_calls=0;g_lco_alloc_fail=(LONG)ordinal;return ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureAllocations(void) {return (DWORD)g_lco_alloc_live;}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureSetRoot(const WCHAR *path) {
    if(g_game_host || !path)return ERROR_ACCESS_DENIED;
    return wcscpy_s(g_root_path,1024,path)?ERROR_FILENAME_EXCED_RANGE:ERROR_SUCCESS;
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureTakeArm(void) {
    if(g_game_host)return ERROR_ACCESS_DENIED;return lco_take_arm()?ERROR_SUCCESS:ERROR_INVALID_DATA;
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureCacheSave(const LcoResult *result) {
    if(g_game_host || !result)return ERROR_ACCESS_DENIED;return lco_cache_save(result);
}
__declspec(dllexport) DWORD WINAPI WojdChatFixtureCacheLoad(void *base,LcoResult *result) {
    ImageView view;if(g_game_host || !result)return ERROR_ACCESS_DENIED;
    if(!image_view(base,&view))return ERROR_BAD_EXE_FORMAT;return lco_cache_load(&view,result);
}
