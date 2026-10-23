/* Pure notification adapter shared with fixture stubs. The caller supplies
   MessageBoxW (worker only). One terminal attempt per process, including an
   API failure; no repeated modal loop and no success inferred from return0. */
typedef int (WINAPI *TooltipMessageFn)(HWND,LPCWSTR,LPCWSTR,UINT);
typedef struct TooltipNoticeState {
    BOOL attempted,success,cache_updated;DWORD api_status;int message_result;
} TooltipNoticeState;
static const WCHAR *tooltip_notice_stage(const char *stage) {
    if(stage && !strcmp(stage,"PLAIN_SKILL"))return L"\u0110\u1ecdc d\u1eef li\u1ec7u k\u1ef9 n\u0103ng";
    if(stage && !strcmp(stage,"PLAIN_BUFF"))return L"\u0110\u1ecdc d\u1eef li\u1ec7u hi\u1ec7u \u1ee9ng";
    if(stage && !strcmp(stage,"NATIVE"))return L"\u0110\u1ecdc nh\u00e1nh d\u1eef li\u1ec7u g\u1ed1c";
    if(stage && !strcmp(stage,"CATALOG"))return L"\u0110\u1ecdc danh m\u1ee5c b\u1ea3n d\u1ecbch";
    if(stage && !strcmp(stage,"TYPED_DISCOVERY"))return L"T\u00ecm \u0111\u1ecba ch\u1ec9 skill";
    if(stage && !strcmp(stage,"GENERIC_DISCOVERY"))return L"T\u00ecm b\u1ed9 n\u1ea1p d\u1eef li\u1ec7u";
    if(stage && !strcmp(stage,"TRANSLATOR_READINESS"))return L"Chu\u1ea9n b\u1ecb b\u1ed9 d\u1ecbch";
    if(stage && !strcmp(stage,"TRANSLATOR_CALIBRATION"))return L"Chu\u1ea9n b\u1ecb b\u1ed9 d\u1ecbch";
    if(stage && !strcmp(stage,"TYPED_CACHE_WRITE"))return L"L\u01b0u \u0111\u1ecba ch\u1ec9 skill";
    if(stage && !strcmp(stage,"GENERIC_CACHE_WRITE"))return L"L\u01b0u \u0111\u1ecba ch\u1ec9 b\u1ed9 n\u1ea1p";
    if(stage && !strcmp(stage,"TYPED_HOOK_INSTALL"))return L"K\u00edch ho\u1ea1t Vi\u1ec7t h\u00f3a skill";
    if(stage && !strcmp(stage,"GENERIC_HOOK_INSTALL"))return L"K\u00edch ho\u1ea1t b\u1ed9 d\u1ecbch";
    if(stage && !strcmp(stage,"RUNTIME_INITIALIZE"))return L"Kh\u1edfi t\u1ea1o b\u1ed9 d\u1ecbch";
    if(stage && !strcmp(stage,"PATHS"))return L"M\u1edf th\u01b0 m\u1ee5c b\u1ea3n d\u1ecbch";
    if(stage && !strcmp(stage,"PIN"))return L"Kh\u1edfi t\u1ea1o b\u1ed9 d\u1ecbch";
    if(stage && !strcmp(stage,"DYNAMIC_CAPTURE"))return L"Ch\u1ecdn ch\u1ebf \u0111\u1ed9 ch\u1ea1y";
    return L"Kh\u1edfi t\u1ea1o Vi\u1ec7t h\u00f3a skill";
}
static DWORD tooltip_notice_dispatch_groups(TooltipNoticeState *state,TooltipMessageFn message,
        BOOL success,DWORD failure,BOOL cache_updated,const char *stage,BOOL restart_required,BOOL partial_active) {
    WCHAR text[512];DWORD error;
    if(state->attempted)return state->api_status;
    state->attempted=TRUE;state->success=success;state->cache_updated=cache_updated;
    if(!message)return state->api_status=ERROR_PROC_NOT_FOUND;
    if(success)wcscpy_s(text,512,L"\u0110\u00e3 c\u1eadp nh\u1eadt \u0111\u1ecba ch\u1ec9 Vi\u1ec7t h\u00f3a skill. Vui l\u00f2ng tho\u00e1t game v\u00e0 m\u1edf l\u1ea1i.");
    else {
        if(_snwprintf_s(text,512,_TRUNCATE,L"L\u1ed7i \u1edf b\u01b0\u1edbc: %s (m\u00e3 %lu).",tooltip_notice_stage(stage),failure)<0)return state->api_status=ERROR_INSUFFICIENT_BUFFER;
        if(partial_active)wcscat_s(text,512,L"\nC\u00e1c nh\u00e1nh \u0111\u00e3 k\u00edch ho\u1ea1t v\u1eabn ti\u1ebfp t\u1ee5c d\u1ecbch.");
        if(restart_required)wcscat_s(text,512,L"\n\u0110\u00e3 l\u01b0u \u0111\u1ecba ch\u1ec9 m\u1edbi cho c\u00e1c nh\u00e1nh \u0111\u00e3 x\u00e1c minh. Vui l\u00f2ng tho\u00e1t game v\u00e0 m\u1edf l\u1ea1i \u0111\u1ec3 \u00e1p d\u1ee5ng.");
        else wcscat_s(text,512,L"\nVui l\u00f2ng g\u1eedi l\u1ea1i th\u00f4ng b\u00e1o l\u1ed7i n\u00e0y.");
    }
    SetLastError(ERROR_SUCCESS);
    state->message_result=message(NULL,text,L"WO Vi\u1ec7t h\u00f3a skill",MB_OK|(success?MB_ICONINFORMATION:MB_ICONERROR)|MB_SETFOREGROUND|MB_TOPMOST);
    error=GetLastError();
    state->api_status=state->message_result?ERROR_SUCCESS:(error?error:ERROR_GEN_FAILURE);
    return state->api_status;
}
static DWORD tooltip_notice_dispatch(TooltipNoticeState *state,TooltipMessageFn message,
        BOOL success,DWORD failure,BOOL cache_updated,const char *stage) {
    return tooltip_notice_dispatch_groups(state,message,success,failure,cache_updated,stage,success,FALSE);
}
