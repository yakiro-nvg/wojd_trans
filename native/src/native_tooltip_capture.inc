/* Bounded typed display fields share the source-exact native dictionary. */
#include "native_tooltip_profile.h"
#define WOJD_NATIVE_UOBJECT_REUSE_FIELD_SITE_TYPE
#include "native_tooltip_uobject_profile.h"
#include "native_tooltip_plain_context.h"
#include "native_tooltip_resolver.inc"
#include "native_tooltip_plain_resolver.inc"
#include "native_tooltip_notification.inc"
typedef void *(__fastcall *TooltipSerializerFn)(void *,GameString *);
typedef struct TooltipStatus {
    LONG scopes,serializers,fields,captured,invalid,exceptions,origin_rejected;
    DWORD installed;
} TooltipStatus;
static TooltipStatus g_tooltip_status;
/* Keep the prior ABI. Scope counters are retained as zero; TLS no longer gates observation. */
typedef struct TooltipDiagnostics {
    LONG serializer_entry_seen,approved_calls,approved_in_scope,approved_outside_scope;
    LONG first_approved_seen,scope_exits;
    ULONGLONG first_serializer_attach_us,first_approved_attach_us;
} TooltipDiagnostics;
static TooltipDiagnostics g_tooltip_diagnostics;
typedef struct TooltipTypedStatus {LONG plain_fields,native_fields,code_rejected,not_loading,not_empty;} TooltipTypedStatus;
static TooltipTypedStatus g_tooltip_typed_status;
typedef struct TooltipTranslationStatus {LONG lookups,translated,ignored,missing,not_ready,failed;} TooltipTranslationStatus;
static TooltipTranslationStatus g_tooltip_translation_status;
static TooltipSerializerFn g_tooltip_serializer_original;
static void *g_tooltip_serializer_target;
static volatile LONG g_tooltip_active;
static volatile LONG g_tooltip_translation_ready;
static AssignFn g_tooltip_assign;
static ULONGLONG g_tooltip_translator_ready_us,g_tooltip_hook_ready_us;
static BOOL g_tooltip_restart_required,g_tooltip_cache_persisted;
static TooltipNoticeState g_tooltip_notice;
static volatile LONG g_tooltip_notice_queued;
static volatile LONG g_tooltip_notice_dispatch_status=ERROR_IO_PENDING;
typedef struct TooltipNoticeRequest {BOOL success,cache_updated,restart_required,partial_active;DWORD failure;const char *stage;} TooltipNoticeRequest;
static TooltipNoticeRequest g_tooltip_notice_request;
static BOOL g_tooltip_setup_complete;
static BOOL g_tooltip_allow_warm_enable=TRUE;
static BOOL g_tooltip_generic_cache_ready;
static LONG g_tooltip_diag_serializer_logged,g_tooltip_diag_approved_logged;
static __declspec(thread) BOOL g_tooltip_observing;
static void *g_tooltip_test_plain_return,*g_tooltip_test_native_return;
static void *g_tooltip_test_plain_skill_return,*g_tooltip_test_native_skill_return;
static const WojdTooltipFieldSite g_tooltip_test_plain_site={0,0x50,1,"ZCTooltipBuffDoc","TipBuffEffect"};
static const WojdTooltipFieldSite g_tooltip_test_native_site={0,0x68,1,"ZCTooltipBuffDoc","TipBuffEffect"};
static const WojdTooltipFieldSite g_tooltip_test_plain_skill_site={0,0xd8,1,"ZCTooltipSkillDoc","SkillDesc"};
static const WojdTooltipFieldSite g_tooltip_test_native_skill_site={0,0xe8,1,"ZCTooltipSkillDoc","SkillDesc"};
static BOOL g_tooltip_pending=TRUE;
static DWORD g_tooltip_install_error=ERROR_NOT_READY;
static DWORD g_tooltip_deferred_generic_error;
static const char *g_tooltip_deferred_generic_stage;
static BOOL g_tooltip_completion_reported;

static const WojdTooltipFieldSite *tooltip_field(void *caller,BOOL *native_layout) {
    *native_layout=FALSE;
    if(!g_game_host) {
        if(g_tooltip_test_plain_skill_return && caller==g_tooltip_test_plain_skill_return)return &g_tooltip_test_plain_skill_site;
        if(g_tooltip_test_native_skill_return && caller==g_tooltip_test_native_skill_return){*native_layout=TRUE;return &g_tooltip_test_native_skill_site;}
        if(caller==g_tooltip_test_plain_return)return &g_tooltip_test_plain_site;
        if(caller==g_tooltip_test_native_return){*native_layout=TRUE;return &g_tooltip_test_native_site;}
        return NULL;
    }
    return tooltip_origin_lookup(caller,native_layout);
}
/* The stable assignment trampoline uses the game's allocator. Its pointer and
   immutable dictionary precede g_tooltip_translation_ready publication. */
static BOOL tooltip_replace(GameString *out,const WideRule *rule) {
    GameString after;SIZE_T n=wcslen(rule->target)+1;
    __try {
        if(g_tooltip_assign(out,rule->target)!=out || !read_exact(out,&after,sizeof(after)) ||
           !after.data || after.count!=(int)n || after.capacity<after.count)return FALSE;
        return !memcmp(after.data,rule->target,n*sizeof(WCHAR));
    }__except(EXCEPTION_EXECUTE_HANDLER){InterlockedIncrement(&g_tooltip_status.exceptions);return FALSE;}
}
static void tooltip_observe(GameString *out,const WojdTooltipFieldSite *site,void *caller,BOOL native_layout) {
    GameString s;WCHAR *original;int i;BOOL cjk=FALSE,ready,translated=FALSE;
    const WideRule *rule=NULL;const char *decision="not_ready";
#if WOJD_CAPTURE
    CaptureContext context;DWORD id,variant=0;BYTE *object;
#else
    (void)caller;
#endif
#if WOJD_CAPTURE
    if((uintptr_t)out<site->field_offset){InterlockedIncrement(&g_tooltip_status.invalid);return;}
    object=(BYTE *)((uintptr_t)out-site->field_offset);
#endif
    if(!read_exact(out,&s,sizeof(s)) || !s.data || s.count<=1)return;
    if(s.count>65536 || s.capacity<s.count){InterlockedIncrement(&g_tooltip_status.invalid);return;}
    /* Work on an owned copy; do not hold the dump lock while reading guest memory. */
    original=s.data;s.data=(WCHAR *)HeapAlloc(GetProcessHeap(),0,(SIZE_T)s.count*sizeof(WCHAR));
    if(!s.data){InterlockedIncrement(&g_status.dropped);return;}
    if(!read_exact(original,s.data,(SIZE_T)s.count*sizeof(WCHAR)) || s.data[s.count-1]!=0)goto invalid;
    for(i=0;i<s.count-1;i++) {
        WCHAR ch=s.data[i];if(!ch)goto invalid;
        if((ch>=0x3400 && ch<=0x9fff) || (ch>=0xf900 && ch<=0xfaff))cjk=TRUE;
    }
    if(!cjk || is_resource(s.data))goto done;
#if WOJD_CAPTURE
    if(!read_exact(object+(native_layout?0x28:0x18),&id,sizeof(id)))goto invalid;
    if(!strcmp(site->namespace_name,"ZCTooltipSkillDoc") && !read_exact(object+(native_layout?0x2c:0x1c),&variant,sizeof(variant)))goto invalid;
#endif
    ready=InterlockedCompareExchange(&g_tooltip_translation_ready,0,0)!=0;
    if(ready) {
        InterlockedIncrement(&g_tooltip_translation_status.lookups);
        rule=lookup_wide(s.data,s.count-1);
        if(!rule){decision="missing";InterlockedIncrement(&g_tooltip_translation_status.missing);}
        else if(rule->decision==DECISION_IGNORE){decision="ignore";InterlockedIncrement(&g_tooltip_translation_status.ignored);}
        else {
            translated=tooltip_replace(out,rule);decision=translated?"translated":"replacement_failed";
            InterlockedIncrement(translated?&g_tooltip_translation_status.translated:&g_tooltip_translation_status.failed);
        }
    }else InterlockedIncrement(&g_tooltip_translation_status.not_ready);
#if WOJD_CAPTURE
    ZeroMemory(&context,sizeof(context));
    context.has_variant=!strcmp(site->namespace_name,"ZCTooltipSkillDoc");
    context.route="native_tooltip_fstring_observation";context.field="ToolTipFStringObservation";
    context.namespace_name=site->namespace_name;context.typed_field=site->field_name;
    context.object_layout=native_layout?"NATIVE_UOBJECT":"PLAIN_STRUCT";
    context.record_id=id;context.variant=variant;
    context.processing_status=decision;context.capture_only=!ready;context.translated=translated;
    if(capture_string(&s,0,caller,rule,&context))InterlockedIncrement(&g_tooltip_status.captured);
#else
    (void)site;(void)native_layout;(void)decision;
#endif
    goto done;
invalid:
    InterlockedIncrement(&g_tooltip_status.invalid);
done:
    HeapFree(GetProcessHeap(),0,s.data);
}
static void * __fastcall tooltip_serializer_hook(void *archive,GameString *out) {
    void *caller=_ReturnAddress(),*result;const WojdTooltipFieldSite *site=NULL;
    DWORD last_error=GetLastError();BYTE flags=0;GameString before;BOOL eligible=FALSE,native_layout=FALSE;
    if(g_tooltip_active && !g_tooltip_observing) {
        if(!g_tooltip_diagnostics.serializer_entry_seen &&
           !InterlockedCompareExchange(&g_tooltip_diagnostics.serializer_entry_seen,-1,0)) {
            g_tooltip_diagnostics.first_serializer_attach_us=diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart);
            InterlockedExchange(&g_tooltip_diagnostics.serializer_entry_seen,1);
        }
        site=tooltip_field(caller,&native_layout);
        if(site) {
            InterlockedIncrement(&g_tooltip_status.serializers);
            InterlockedIncrement(&g_tooltip_diagnostics.approved_calls);
            InterlockedIncrement(&g_tooltip_diagnostics.approved_outside_scope);
            if(!g_tooltip_diagnostics.first_approved_seen &&
               !InterlockedCompareExchange(&g_tooltip_diagnostics.first_approved_seen,-1,0)) {
                g_tooltip_diagnostics.first_approved_attach_us=diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart);
                InterlockedExchange(&g_tooltip_diagnostics.first_approved_seen,1);
            }
            if(!read_exact((BYTE *)archive+0x28,&flags,1) || !(flags&1))InterlockedIncrement(&g_tooltip_typed_status.not_loading);
            else if(!read_exact(out,&before,sizeof(before)) || before.count!=0)InterlockedIncrement(&g_tooltip_typed_status.not_empty);
            else eligible=TRUE;
            if(!eligible)InterlockedIncrement(&g_tooltip_status.origin_rejected);
        }
    }
    SetLastError(last_error);result=g_tooltip_serializer_original(archive,out);last_error=GetLastError();
    if(eligible && g_tooltip_active) {
        InterlockedIncrement(&g_tooltip_status.fields);
        InterlockedIncrement(native_layout?&g_tooltip_typed_status.native_fields:&g_tooltip_typed_status.plain_fields);
        g_tooltip_observing=TRUE;
        __try {tooltip_observe(out,site,caller,native_layout);}
        __except(EXCEPTION_EXECUTE_HANDLER){InterlockedIncrement(&g_tooltip_status.exceptions);}
        g_tooltip_observing=FALSE;
    }
    SetLastError(last_error);return result;
}
/* Physical preparation never publishes an origin or enables target code. */
static DWORD tooltip_prepare_serializer(void *serializer) {
    MH_STATUS status;ImageView view;BYTE current[48];DWORD error;
    if(g_tooltip_active || !serializer)return ERROR_INVALID_STATE;
#if WOJD_CAPTURE
    if(!g_writer)return ERROR_INVALID_STATE;
#endif
    if(g_tooltip_serializer_target && g_tooltip_serializer_target!=serializer)return ERROR_INVALID_DATA;
    if(g_game_host) {
        if(!image_view(g_image_base,&view))return ERROR_NOT_READY;
        error=tooltip_serializer_check(&view,(const BYTE *)serializer);if(error)return error;
    }
    if(!g_tooltip_serializer_target) {
        if(!read_exact(serializer,g_tooltip_serializer_original48,sizeof(g_tooltip_serializer_original48)))return ERROR_NOT_READY;
        if(g_game_host && !masked_match(g_tooltip_serializer_original48,WOJD_FSTRING_SERIALIZER_BYTES48,WOJD_FSTRING_SERIALIZER_MASK48,48))return ERROR_INVALID_DATA;
        status=MH_CreateHook(serializer,(void *)(uintptr_t)tooltip_serializer_hook,(void **)&g_tooltip_serializer_original);
        if(status!=MH_OK)return (DWORD)status+0x10000;
        g_tooltip_serializer_target=serializer;
    }
    /* A created-but-unenabled target remains pinned and can be retried when
       readable, without another CreateHook and without consuming a map slot. */
    if(g_game_host) {
        error=tooltip_serializer_check(&view,(const BYTE *)serializer);if(error)return error;
    }
    if(!read_exact(serializer,current,sizeof(current)))return ERROR_NOT_READY;
    return memcmp(current,g_tooltip_serializer_original48,sizeof(current))?ERROR_INVALID_DATA:ERROR_SUCCESS;
}
static DWORD tooltip_enable_prepared_serializer(void *serializer) {
    MH_STATUS status;
    if(g_tooltip_active || !serializer || serializer!=g_tooltip_serializer_target)return ERROR_INVALID_STATE;
    InterlockedExchange(&g_tooltip_active,1);status=MH_EnableHook(serializer);
    if(status!=MH_OK){InterlockedExchange(&g_tooltip_active,0);return (DWORD)status+0x10000;}
    /* This is the only read after publication. Its failure is terminal for this
       group, not a retry that could consume arbitrary immutable map slots. */
    if(!read_exact(serializer,g_tooltip_serializer_installed48,sizeof(g_tooltip_serializer_installed48))) {
        InterlockedExchange(&g_tooltip_active,0);MH_DisableHook(serializer);return ERROR_READ_FAULT;
    }
    g_tooltip_owned_serializer=(const BYTE *)serializer;
    g_tooltip_status.installed=1;return ERROR_SUCCESS;
}
static DWORD tooltip_install(void *serializer) {
    DWORD error=tooltip_prepare_serializer(serializer);
    return error?error:tooltip_enable_prepared_serializer(serializer);
}
static DWORD tooltip_restore(void) {
    MH_STATUS status;
    if(!g_tooltip_serializer_target)return ERROR_SUCCESS;
    InterlockedExchange(&g_tooltip_active,0);
    status=MH_DisableHook(g_tooltip_serializer_target);
    if(status!=MH_OK && status!=MH_ERROR_DISABLED)return (DWORD)status+0x10000;
    InterlockedExchangePointer(&g_tooltip_origin_map,NULL);
    InterlockedExchange(&g_tooltip_generation,0);g_tooltip_status.installed=0;return ERROR_SUCCESS;
}
/* Diagnostic I/O and optional notification run only on the setup worker. */
static void tooltip_flush_diagnostics(void) {
    if(InterlockedCompareExchange(&g_tooltip_diagnostics.serializer_entry_seen,0,0)==1 && !g_tooltip_diag_serializer_logged) {
        g_tooltip_diag_serializer_logged=1;
        logf_n4("TOOLTIP_SERIALIZER_ENTRY_SEEN","attach_us=%llu source_read=0",g_tooltip_diagnostics.first_serializer_attach_us);
    }
    if(InterlockedCompareExchange(&g_tooltip_diagnostics.first_approved_seen,0,0)==1 && !g_tooltip_diag_approved_logged) {
        g_tooltip_diag_approved_logged=1;
        logf_n4("TOOLTIP_FIRST_APPROVED_SITE","attach_us=%llu translator_ready_us=%llu hook_ready_us=%llu producer_start_verified=0 coverage=UNPROVEN",
            g_tooltip_diagnostics.first_approved_attach_us,g_tooltip_translator_ready_us,g_tooltip_hook_ready_us);
    }
}
static DWORD WINAPI tooltip_notice_worker(void *parameter) {
    const TooltipNoticeRequest *request=(const TooltipNoticeRequest *)parameter;
    HMODULE ui;TooltipMessageFn message;DWORD error;
    ui=LoadLibraryExW(L"user32.dll",NULL,LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!ui) {
        error=GetLastError();g_tooltip_notice.attempted=TRUE;g_tooltip_notice.api_status=error;InterlockedExchange(&g_tooltip_notice_dispatch_status,(LONG)error);
        logf_n4("TOOLTIP_TERMINAL_NOTIFICATION","outcome=%s status=%lu message_result=0 stage=LOAD_USER32",request->success?"RESTART_REQUIRED":"FAILED",error);return error;
    }
    message=(TooltipMessageFn)(uintptr_t)GetProcAddress(ui,"MessageBoxW");
    if(!message) {
        error=GetLastError();if(!error)error=ERROR_PROC_NOT_FOUND;
        g_tooltip_notice.attempted=TRUE;g_tooltip_notice.api_status=error;InterlockedExchange(&g_tooltip_notice_dispatch_status,(LONG)error);
        FreeLibrary(ui);logf_n4("TOOLTIP_TERMINAL_NOTIFICATION","outcome=%s status=%lu message_result=0 stage=GET_MESSAGEBOX_PROC",request->success?"RESTART_REQUIRED":"FAILED",error);return error;
    }
    error=tooltip_notice_dispatch_groups(&g_tooltip_notice,message,request->success,request->failure,request->cache_updated,request->stage,request->restart_required,request->partial_active);
    InterlockedExchange(&g_tooltip_notice_dispatch_status,(LONG)error);
    FreeLibrary(ui);
    logf_n4("TOOLTIP_TERMINAL_NOTIFICATION","outcome=%s status=%lu message_result=%d cause_status=%lu typed_cache_updated=%u stage=%s",request->success?"RESTART_REQUIRED":"FAILED",error,g_tooltip_notice.message_result,request->failure,request->cache_updated,request->stage);
    return error;
}
static DWORD tooltip_notify_terminal(BOOL success,DWORD failure,const char *stage) {
    HMODULE pinned=NULL;HANDLE thread;DWORD error;
    if(InterlockedCompareExchange(&g_tooltip_notice_queued,1,0))return (DWORD)InterlockedCompareExchange(&g_tooltip_notice_dispatch_status,0,0);
    g_tooltip_notice_request.success=success;g_tooltip_notice_request.failure=failure;
    g_tooltip_notice_request.stage=stage; /* all callers pass immutable stage literals */
    g_tooltip_notice_request.cache_updated=g_tooltip_cache_persisted;
    g_tooltip_notice_request.restart_required=g_tooltip_restart_required;
    g_tooltip_notice_request.partial_active=g_tooltip_active && g_tooltip_origin_count>0;
    /* Static request outlives the bootstrap caller. Pin before dispatch; the
       one modal notice never blocks either discovery job or their allocator. */
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCWSTR)g_module,&pinned)) {
        error=GetLastError();InterlockedExchange(&g_tooltip_notice_dispatch_status,(LONG)error);logf_n4("TOOLTIP_NOTICE_DISPATCH_FAILED","stage=PIN status=%lu",error);return error;
    }
    thread=CreateThread(NULL,0,tooltip_notice_worker,&g_tooltip_notice_request,0,NULL);
    if(!thread){error=GetLastError();InterlockedExchange(&g_tooltip_notice_dispatch_status,(LONG)error);logf_n4("TOOLTIP_NOTICE_DISPATCH_FAILED","stage=CREATE_THREAD status=%lu",error);return error;}
    CloseHandle(thread);logf_n4("TOOLTIP_NOTICE_QUEUED","outcome=%s cause_status=%lu typed_cache_updated=%u stage=%s",success?"RESTART_REQUIRED":"FAILED",failure,g_tooltip_cache_persisted,stage);
    return ERROR_IO_PENDING;
}
static void tooltip_report_failure(const char *stage,DWORD error) {
    /* A generic reader failure is independent of typed groups. Defer its modal
       until those groups settle, so it cannot consume the single visible
       restart/failure notice while their valid caches are still being saved. */
    if((g_tooltip_pending || !g_tooltip_setup_complete) && stage && (!strcmp(stage,"GENERIC_DISCOVERY") ||
       !strcmp(stage,"GENERIC_HOOK_INSTALL") || !strcmp(stage,"GENERIC_CACHE_WRITE"))) {
        if(!g_tooltip_deferred_generic_error){g_tooltip_deferred_generic_error=error;g_tooltip_deferred_generic_stage=stage;}
        logf_n4("TOOLTIP_GENERIC_NOTICE_DEFERRED","stage=%s status=%lu typed_groups_continue=1",stage,error);return;
    }
    /* A catalog failure is terminal for every source-exact translation path,
       unlike transient code/allocator materialization. Do not spin 180 seconds. */
    if(stage && !strcmp(stage,"CATALOG")){g_tooltip_pending=FALSE;g_tooltip_install_error=error;g_tooltip_completion_reported=TRUE;}
    logf_n4("TOOLTIP_TERMINAL_FAILURE","stage=%s status=%lu typed_cache_updated=%u skill_ready=0",stage,error,g_tooltip_cache_persisted);
    logf_n4("TOOLTIP_HINT_REJECTIONS","last_context_rva=%lx last_reason=%lu unreadable=%lu mask_mismatch=%lu unwind_invalid=%lu target_invalid=%lu",g_tooltip_last_hint_rva,g_tooltip_last_hint_reason,g_tooltip_hint_reasons[HINT_UNREADABLE],g_tooltip_hint_reasons[HINT_MASK_MISMATCH],g_tooltip_hint_reasons[HINT_UNWIND_INVALID],g_tooltip_hint_reasons[HINT_TARGET_INVALID]);
    tooltip_notify_terminal(FALSE,error,stage);
}
/* Each independently validated group has its own completion. A failed Native,
   Buff or intentionally unsupported Mail route never removes a valid Skill map. */
static BOOL g_tooltip_native_pending=TRUE,g_tooltip_native_cache_persisted;
static DWORD g_tooltip_group_failure;
static const char *g_tooltip_group_failure_stage;
static const BYTE *g_tooltip_confirmed_serializer;
static DWORD tooltip_prepare_group(const BYTE *serializer) {
    /* Only a successfully completed group or actual physical hook pins the
       common serializer. A failed allocator/freshness probe reserves nothing. */
    if(g_tooltip_confirmed_serializer && g_tooltip_confirmed_serializer!=serializer)return ERROR_INVALID_DATA;
    if(g_tooltip_serializer_target && g_tooltip_serializer_target!=(const void *)serializer)return ERROR_INVALID_DATA;
    return tooltip_prepare_for_serializer(serializer);
}
static DWORD tooltip_enable_group(const BYTE *serializer,BOOL native_group,DWORD plain_group) {
    DWORD error,prior_count,prior_groups;LONG prior_generation;PVOID prior_map;
    if(serializer!=(native_group?g_tooltip_resolved.serializer:g_tooltip_plain[plain_group].serializer))return ERROR_INVALID_DATA;
    if(g_tooltip_serializer_target && g_tooltip_serializer_target!=(const void *)serializer)return ERROR_INVALID_DATA;
    if(g_tooltip_confirmed_serializer && g_tooltip_confirmed_serializer!=serializer)return ERROR_INVALID_DATA;
    error=native_group?tooltip_fresh_native_chain():tooltip_fresh_plain_group(plain_group);if(error)return error;
    if(g_tooltip_active) {
        ImageView view;if(!image_view(g_image_base,&view))return ERROR_NOT_READY;
        error=tooltip_serializer_check(&view,serializer);if(error)return error;
    }else {
        error=tooltip_prepare_serializer((void *)serializer);if(error)return error;
        /* Physical preparation may take time. Revalidate all chosen contexts,
           owner, E8 callee and expected48/root again before map publication. */
        error=native_group?tooltip_fresh_native_chain():tooltip_fresh_plain_group(plain_group);if(error)return error;
    }
    prior_map=InterlockedCompareExchangePointer(&g_tooltip_origin_map,NULL,NULL);
    prior_count=g_tooltip_origin_count;prior_groups=g_tooltip_origin_groups;
    prior_generation=InterlockedCompareExchange(&g_tooltip_generation,0,0);
    error=native_group?tooltip_publish_origins():tooltip_publish_plain_origins(plain_group);
    if(error)return error;
    if(!g_tooltip_active)error=tooltip_enable_prepared_serializer((void *)serializer);
    if(error) {
        /* Setup has one writer. Roll back publication atomically; retain the
           retired snapshot forever and never decrement/reuse its slot. Readers
           holding that pointer remain memory-safe, and no failed origin survives
           to be activated by a later independently successful group. */
        InterlockedExchangePointer(&g_tooltip_origin_map,prior_map);
        g_tooltip_origin_count=prior_count;g_tooltip_origin_groups=prior_groups;
        InterlockedExchange(&g_tooltip_generation,prior_generation);return error;
    }
    g_tooltip_confirmed_serializer=serializer;
    if(!g_tooltip_hook_ready_us)g_tooltip_hook_ready_us=diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart);
    return ERROR_SUCCESS;
}
static void tooltip_group_failure(const char *stage,DWORD error) {
    if(!g_tooltip_group_failure){g_tooltip_group_failure=error;g_tooltip_group_failure_stage=stage;}
    logf_n4("TOOLTIP_GROUP_FAILED","group=%s status=%lu other_groups_continue=1",stage,error);
}
static void tooltip_native_step(BOOL deadline) {
    DWORD error;
    if(!g_tooltip_native_pending)return;
    error=tooltip_resolver_step();
    if(error==ERROR_NOT_READY && !deadline)return;
    if(error==ERROR_NOT_READY)error=ERROR_TIMEOUT;
    if(!error && g_tooltip_resolution_scope!=1 && !g_tooltip_native_cache_persisted) {
        error=tooltip_hint_save(&g_tooltip_resolved);
        if(!error){g_tooltip_native_cache_persisted=TRUE;g_tooltip_cache_persisted=TRUE;logf_n4("TOOLTIP_CACHE_PREPARED","group=NATIVE validation_scope=%s",tooltip_scope_name());}
    }
    if(!error)error=tooltip_prepare_group(g_tooltip_resolved.serializer);
    if(!error)error=tooltip_fresh_native_chain();
    if(error==ERROR_NOT_READY && !deadline)return;
    if(error==ERROR_NOT_READY)error=ERROR_TIMEOUT;
    if(!error && g_tooltip_resolution_scope==1)error=tooltip_enable_group(g_tooltip_resolved.serializer,TRUE,0);
    else if(!error){g_tooltip_confirmed_serializer=g_tooltip_resolved.serializer;g_tooltip_restart_required=TRUE;}
    if(error==ERROR_NOT_READY && !deadline)return;
    if(error==ERROR_NOT_READY)error=ERROR_TIMEOUT;
    g_tooltip_native_pending=FALSE;
    if(error){tooltip_group_failure("NATIVE",error);return;}
    logf_n4("TOOLTIP_GROUP_READY","group=NATIVE route=%s validated_contexts=25 enabled_sites=%u attach_us=%llu allocator_independent_of_generic_reader=1 coverage=UNPROVEN",
        g_tooltip_resolution_scope==1?"WARM":"CALIBRATION",g_tooltip_resolution_scope==1?15u:0u,
        diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart));
}
static void tooltip_plain_finish(DWORD index,BOOL deadline) {
    TooltipPlainGroup *group=&g_tooltip_plain[index];DWORD error=group->error;
    if(group->done)return;
    if(!group->ready && !error && !deadline)return;
    if(!group->ready && !error)error=ERROR_TIMEOUT;
    if(!error && group->route!=CACHE_ROUTE_WARM && !group->persisted) {
        error=tooltip_plain_cache_save(group);
        if(!error){group->persisted=TRUE;g_tooltip_cache_persisted=TRUE;}
    }
    if(!error)error=tooltip_prepare_group(group->serializer);
    if(!error)error=tooltip_fresh_plain_group(index);
    if(error==ERROR_NOT_READY && !deadline)return;
    if(error==ERROR_NOT_READY)error=ERROR_TIMEOUT;
    if(!error && group->route==CACHE_ROUTE_WARM)error=tooltip_enable_group(group->serializer,FALSE,index);
    else if(!error){g_tooltip_confirmed_serializer=group->serializer;g_tooltip_restart_required=TRUE;}
    if(error==ERROR_NOT_READY && !deadline)return;
    if(error==ERROR_NOT_READY)error=ERROR_TIMEOUT;
    group->done=TRUE;group->error=error;
    if(error){tooltip_group_failure(g_tooltip_plain_names[index],error);return;}
    logf_n4("TOOLTIP_GROUP_READY","group=%s route=%s anchor_rva=%lx owner_rva=%lx validated_contexts=%lu enabled_sites=%lu attach_us=%llu readable_scan_bytes=%llu skipped_bytes=%llu gaps=%lu allocator_independent_of_generic_reader=1 coverage=UNPROVEN",
        g_tooltip_plain_names[index],group->route==CACHE_ROUTE_WARM?"WARM":"CALIBRATION",group->anchor,group->owner,
        g_tooltip_plain_counts[index],group->route==CACHE_ROUTE_WARM?g_tooltip_plain_counts[index]:0u,
        diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart),g_tooltip_plain_scan.bytes,g_tooltip_plain_scan.skipped_bytes,g_tooltip_plain_scan.gaps);
}
/* Completion notice joins two terminal states; hook readiness does not. */
static BOOL tooltip_completion_join(BOOL typed_pending,BOOL generic_complete) {
    return !typed_pending && generic_complete;
}
static void tooltip_try_completion_notice(void) {
    if(g_tooltip_completion_reported || !tooltip_completion_join(g_tooltip_pending,g_tooltip_setup_complete))return;
    g_tooltip_completion_reported=TRUE;
    g_tooltip_install_error=g_tooltip_group_failure?g_tooltip_group_failure:g_tooltip_deferred_generic_error;
    if(g_tooltip_group_failure)tooltip_report_failure(g_tooltip_group_failure_stage,g_tooltip_group_failure);
    else if(g_tooltip_deferred_generic_error)tooltip_report_failure(g_tooltip_deferred_generic_stage,g_tooltip_deferred_generic_error);
    else if(g_tooltip_restart_required) {
        logf_n4("TOOLTIP_RESTART_REQUIRED","cache_updated=1 independent_group_cache=1 warm_sites_remain_enabled=1 translator_ready=1 plain_mail_enabled=0 generic_setup_terminal=1");
        tooltip_notify_terminal(TRUE,ERROR_SUCCESS,"COMPLETE");
    }
    logf_n4("TOOLTIP_RUNTIME_READY","status=%lu attach_us=%llu translator_ready_us=%llu enabled_sites=%lu plain_mail_enabled=0 immutable_origin_publications=%lu coverage=UNPROVEN",
        g_tooltip_install_error,g_tooltip_hook_ready_us,g_tooltip_translator_ready_us,g_tooltip_origin_count,g_tooltip_origin_publications);
}
static void tooltip_probe_once(void) {
#if !WOJD_CAPTURE
    DWORD group;BOOL deadline,pending;
#endif
    tooltip_flush_diagnostics();
    if(!g_tooltip_pending){tooltip_try_completion_notice();return;}
#if WOJD_CAPTURE
    /* Object/ID capture layouts are not promoted from shipping translation. */
    g_tooltip_install_error=ERROR_NOT_SUPPORTED;g_tooltip_pending=FALSE;
    tooltip_report_failure("DYNAMIC_CAPTURE",g_tooltip_install_error);return;
#else
    deadline=diag_us(diag_ticks()-(ULONGLONG)g_diag_attach.QuadPart)>=180000000ull;
    /* Both jobs advance on each setup tick. Ready typed groups ask directly for
       the stable allocator/dictionary, without waiting for generic reader717. */
    tooltip_native_step(deadline);
    tooltip_plain_resolver_step();
    for(group=0;group<TOOLTIP_PLAIN_GROUPS;group++)tooltip_plain_finish(group,deadline);
    pending=g_tooltip_native_pending;
    for(group=0;group<TOOLTIP_PLAIN_GROUPS;group++)if(!g_tooltip_plain[group].done)pending=TRUE;
    g_tooltip_pending=pending;
    if(pending)return;
    tooltip_try_completion_notice();
#endif
}
