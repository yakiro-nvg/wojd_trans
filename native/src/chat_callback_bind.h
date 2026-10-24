#ifndef WOJD_CHAT_CALLBACK_BIND_H
#define WOJD_CHAT_CALLBACK_BIND_H
/* Normal Lua C API only. No VM field offsets, pending-pcall work, globals,
   registry entries or worker-thread Lua access. Root shape is codec-certified. */
typedef int (*LcbFunction)(void *);
typedef struct LcbApi {
    int (*gettop)(void *);
    int (*type)(void *,int);
    int (*checkstack)(void *,int);
    void (*pushcclosure)(void *,LcbFunction,int);
    const char *(*setupvalue)(void *,int,int);
    void (*settop)(void *,int);
} LcbApi;
enum { LCB_OK=0,LCB_ARGUMENT=1,LCB_ROOT=2,LCB_CAPACITY=3,LCB_UPVALUE=4 };
static int lcb_bind(const LcbApi *api,void *state,LcbFunction callback) {
    int before;
    const char *name;
    if(!api || !state || !callback || !api->gettop || !api->type || !api->checkstack ||
       !api->pushcclosure || !api->setupvalue || !api->settop)return LCB_ARGUMENT;
    before=api->gettop(state);
    if(before<1 || api->type(state,-1)!=6)return LCB_ROOT;
    if(!api->checkstack(state,1))return LCB_CAPACITY;
    /* Zero-upvalue light C functions do not allocate a closure or run Lua.
       setupvalue replaces only the certified private second upvalue. */
    api->pushcclosure(state,callback,0);
    name=api->setupvalue(state,-2,2);
    if(!name) {
        api->settop(state,before); /* Remove our one unconsumed C function. */
        return LCB_UPVALUE;
    }
    return LCB_OK;
}
#endif
