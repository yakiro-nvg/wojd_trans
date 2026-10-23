/* Setup-only native caller discovery. The existing profile is signature and
   relative-spacing evidence; its absolute RVAs are merely initial hints. */
#define TOOLTIP_GROUPS 3u
#define TOOLTIP_SIGNATURE_REVISION 1u
#define TOOLTIP_MAX_GROUP_PROBES 128u
#define TOOLTIP_SERIALIZER_EXTENT 0x41bu
#define TOOLTIP_COLD_PHASE_LIMIT 8u
#define TOOLTIP_COLD_RETRY_STEPS 32u
#define TOOLTIP_SETUP_STEP_LIMIT 32768u
typedef struct TooltipGroup {DWORD first,count;} TooltipGroup;
static const TooltipGroup g_tooltip_groups[TOOLTIP_GROUPS]={{0,18},{18,2},{20,5}};
typedef struct TooltipResolved {
    const BYTE *serializer;
    DWORD anchors[TOOLTIP_GROUPS],owners[TOOLTIP_GROUPS],matches[TOOLTIP_GROUPS];
    DWORD signature_matches,group_probes,error;
    const BYTE *signature;
} TooltipResolved;
typedef struct TooltipOrigin {const void *caller;const WojdTooltipFieldSite *site;BOOL native_layout;} TooltipOrigin;
#define TOOLTIP_ORIGIN_CAPACITY 36u
/* At most Native + PlainSkill + PlainBuff are added, once each, by one setup
   worker. Readers acquire one immutable snapshot; previous snapshots stay alive. */
typedef struct TooltipOriginMap {DWORD count;TooltipOrigin sites[TOOLTIP_ORIGIN_CAPACITY];} TooltipOriginMap;
static TooltipOriginMap g_tooltip_origin_maps[4];
static PVOID volatile g_tooltip_origin_map;
static DWORD g_tooltip_origin_publications,g_tooltip_origin_groups;
static DWORD g_tooltip_origin_count;
static const BYTE *g_tooltip_owned_serializer;
static BYTE g_tooltip_serializer_original48[48],g_tooltip_serializer_installed48[48];
/* Publication epoch for this immutable origin map, not a code-generation proof. */
static volatile LONG g_tooltip_generation;
static TooltipResolved g_tooltip_resolved;
static ImageView g_tooltip_view;
static ExecutableScan g_tooltip_scan;
static BYTE g_tooltip_scan_copy[SCAN_STEP_BYTES];
static BOOL g_tooltip_resolver_started,g_tooltip_resolver_ready;
static DWORD g_tooltip_resolution_scope; /* 1=current cache, 2=validated hints, 3=readable executable scope */
static DWORD g_tooltip_phases,g_tooltip_retry_steps,g_tooltip_setup_steps;
static BOOL g_tooltip_scan_exhausted,g_tooltip_probing_known_hint;
static ULONGLONG g_tooltip_total_scan_bytes,g_tooltip_total_skipped_bytes;
static DWORD g_tooltip_total_scan_steps,g_tooltip_total_gaps;
static const char *tooltip_scope_name(void) {
    return g_tooltip_resolution_scope==1?"CURRENT_CACHE_CHAIN":
        g_tooltip_resolution_scope==2?"VERIFIED_HINT_CHAIN":"READABLE_EXEC_SCAN";
}
static WCHAR g_tooltip_cache_path[1024];
static BOOL g_tooltip_hint_loaded;
static DWORD g_tooltip_hint_status,g_tooltip_hint_anchors[TOOLTIP_GROUPS],g_tooltip_warm_probes;
enum { HINT_UNREADABLE=1,HINT_MASK_MISMATCH=2,HINT_UNWIND_INVALID=3,HINT_TARGET_INVALID=4 };
static DWORD g_tooltip_hint_reasons[5],g_tooltip_last_hint_rva,g_tooltip_last_hint_reason;
static BOOL tooltip_hint_rejected(DWORD reason,DWORD rva) {
    g_tooltip_hint_reasons[reason]++;g_tooltip_last_hint_rva=rva;g_tooltip_last_hint_reason=reason;return FALSE;
}

/* Shared with the fixture: waiting is valid only while setup is still running.
   Finished setup without its stable allocator/dictionary is a terminal error. */
static DWORD tooltip_translation_readiness(BOOL setup_complete,LONG translator_ready) {
    if(translator_ready)return ERROR_SUCCESS;
    return setup_complete?ERROR_NOT_READY:ERROR_IO_PENDING;
}

static BOOL tooltip_function(const ImageView *view,const BYTE *address,const BYTE **root,const BYTE **end) {
    ULONG64 owner=0;PRUNTIME_FUNCTION entry;
    if(!in_image(view,address,1) || !executable(view,address))return FALSE;
    entry=RtlLookupFunctionEntry((DWORD64)(uintptr_t)address,&owner,NULL);
    if(!entry || (const BYTE *)(uintptr_t)owner!=view->base || entry->BeginAddress>=entry->EndAddress ||
       entry->EndAddress>view->size)return FALSE;
    *root=view->base+entry->BeginAddress;*end=view->base+entry->EndAddress;
    return in_image(view,*root,entry->EndAddress-entry->BeginAddress) && executable(view,*end-1);
}
static DWORD tooltip_serializer_check(const ImageView *view,const BYTE *serializer) {
    const BYTE *root,*end;MemoryProbe probe;BYTE bytes[48];
    if(!serializer || !in_image(view,serializer,sizeof(bytes)) || !executable(view,serializer))return ERROR_INVALID_DATA;
    if(!read_exact_report(serializer,bytes,sizeof(bytes),&probe)) {
        if(g_tooltip_probing_known_hint)code_probe_failure(2,&probe);return ERROR_NOT_READY;
    }
    if(serializer==g_tooltip_owned_serializer) {
        if(memcmp(bytes,g_tooltip_serializer_installed48,sizeof(bytes)))return ERROR_INVALID_DATA;
    }else if(!masked_match(bytes,WOJD_FSTRING_SERIALIZER_BYTES48,WOJD_FSTRING_SERIALIZER_MASK48,48)) {
        probe.kind=PROBE_MASK;if(g_tooltip_probing_known_hint)code_probe_failure(2,&probe);return ERROR_INVALID_DATA;
    }
    if(!tooltip_function(view,serializer,&root,&end) || root!=serializer || end-root!=TOOLTIP_SERIALIZER_EXTENT) {
        probe.kind=PROBE_UNWIND;if(g_tooltip_probing_known_hint)code_probe_failure(2,&probe);return ERROR_INVALID_DATA;
    }
    return ERROR_SUCCESS;
}
static BOOL tooltip_serializer_valid(const ImageView *view,const BYTE *serializer) {
    return tooltip_serializer_check(view,serializer)==ERROR_SUCCESS;
}
/* One group is validated in one bounded call, without per-site sleeps. All
   contexts must remain in one unwind function, retain spacing, and agree on E8. */
static DWORD tooltip_group_check(const ImageView *view,DWORD group,DWORD anchor,
        const BYTE **serializer,DWORD *owner_rva) {
    const TooltipGroup *g=&g_tooltip_groups[group];
    const WojdNativeUobjectSiteContext *first=&WOJD_NATIVE_UOBJECT_SITE_CONTEXTS[g->first];
    const BYTE *owner=NULL,*owner_end=NULL,*target=NULL;DWORD i,error;
    if(!anchor || anchor>=view->size)return ERROR_INVALID_DATA;
    for(i=0;i<g->count;i++) {
        const WojdNativeUobjectSiteContext *c=&WOJD_NATIVE_UOBJECT_SITE_CONTEXTS[g->first+i];
        LONGLONG offset=(LONGLONG)anchor+(LONGLONG)c->context_rva-(LONGLONG)first->return_rva;
        BYTE bytes[24];const BYTE *address,*root,*end,*callee;MemoryProbe probe;
        if(c->size<5 || c->size>sizeof(bytes) || offset<0 || offset>view->size ||
           c->size>view->size-(SIZE_T)offset)return ERROR_INVALID_DATA;
        address=view->base+(SIZE_T)offset;
        if(!read_exact_report(address,bytes,c->size,&probe)) {
            if(g_tooltip_probing_known_hint)code_probe_failure(1,&probe);
            tooltip_hint_rejected(HINT_UNREADABLE,(DWORD)offset);return ERROR_NOT_READY;
        }
        if(!masked_match(bytes,c->bytes,c->mask,c->size)) {
            probe.kind=PROBE_MASK;if(g_tooltip_probing_known_hint)code_probe_failure(1,&probe);
            tooltip_hint_rejected(HINT_MASK_MISMATCH,(DWORD)offset);return ERROR_INVALID_DATA;
        }
        if(!tooltip_function(view,address,&root,&end) || address+c->size>end) {
            probe.kind=PROBE_UNWIND;if(g_tooltip_probing_known_hint)code_probe_failure(1,&probe);
            tooltip_hint_rejected(HINT_UNWIND_INVALID,(DWORD)offset);return ERROR_INVALID_DATA;
        }
        if(bytes[c->size-5]!=0xe8){tooltip_hint_rejected(HINT_TARGET_INVALID,(DWORD)offset);return ERROR_INVALID_DATA;}
        if(!owner){owner=root;owner_end=end;}else if(root!=owner || end!=owner_end)return ERROR_INVALID_DATA;
        callee=relative_target_report(address+c->size-5,&probe);
        if(!callee && probe.kind!=PROBE_NONE) {
            if(g_tooltip_probing_known_hint)code_probe_failure(1,&probe);
            tooltip_hint_rejected(HINT_UNREADABLE,(DWORD)offset);return ERROR_NOT_READY;
        }
        if(!callee || (target && target!=callee)){tooltip_hint_rejected(HINT_TARGET_INVALID,(DWORD)offset);return ERROR_INVALID_DATA;}
        target=callee;
    }
    error=tooltip_serializer_check(view,target);
    if(error){tooltip_hint_rejected(HINT_TARGET_INVALID,anchor-5);return error;}
    *serializer=target;*owner_rva=(DWORD)(owner-view->base);return ERROR_SUCCESS;
}
static BOOL tooltip_group_valid(const ImageView *view,DWORD group,DWORD anchor,const BYTE **serializer,DWORD *owner_rva) {
    return tooltip_group_check(view,group,anchor,serializer,owner_rva)==ERROR_SUCCESS;
}
static DWORD tooltip_fresh_native_chain(void) {
    DWORD group,error,owner;const BYTE *serializer;
    if(!g_tooltip_resolver_ready)return ERROR_NOT_READY;
    for(group=0;group<TOOLTIP_GROUPS;group++) {
        error=tooltip_group_check(&g_tooltip_view,group,g_tooltip_resolved.anchors[group],&serializer,&owner);
        if(error)return error;
        if(serializer!=g_tooltip_resolved.serializer || owner!=g_tooltip_resolved.owners[group])return ERROR_INVALID_DATA;
    }
    return ERROR_SUCCESS;
}
static BOOL tooltip_accept_group(TooltipResolved *out,DWORD group,DWORD anchor,const BYTE *serializer,DWORD owner) {
    if(out->matches[group] && out->anchors[group]==anchor)return TRUE; /* overlap or repeated hint */
    if(++out->matches[group]!=1){out->error=ERROR_DUP_NAME;return FALSE;}
    if(out->serializer && out->serializer!=serializer){out->error=ERROR_INVALID_DATA;return FALSE;}
    out->serializer=serializer;out->anchors[group]=anchor;out->owners[group]=owner;return TRUE;
}
static DWORD tooltip_complete(const TooltipResolved *out,BOOL full_scan) {
    DWORD g,j;
    if(out->error)return out->error;
    for(g=0;g<TOOLTIP_GROUPS;g++)if(out->matches[g]!=1)return ERROR_NOT_FOUND;
    for(g=0;g<TOOLTIP_GROUPS;g++)for(j=g+1;j<TOOLTIP_GROUPS;j++)
        if(out->owners[g]==out->owners[j])return ERROR_INVALID_DATA;
    if(!out->serializer)return ERROR_NOT_FOUND;
    if(full_scan) {
        /* Another independent group may already own this serializer. Its live
           installed snapshot was checked above; its original prologue no longer
           appears in the scan. Any other matching serializer still rejects. */
        if(out->serializer==g_tooltip_owned_serializer) {
            if(out->signature_matches && (out->signature_matches!=1 || out->signature!=out->serializer))return ERROR_DUP_NAME;
        }else if(out->signature_matches!=1 || out->signature!=out->serializer)return ERROR_DUP_NAME;
    }
    return ERROR_SUCCESS;
}
static BOOL tooltip_scan_chunk(const ImageView *view,const BYTE *live,const BYTE *copy,SIZE_T n,void *parameter) {
    TooltipResolved *out=(TooltipResolved *)parameter;SIZE_T i;DWORD g;
    for(i=0;i<n;i++) {
        if(i+48<=n && copy[i]==WOJD_FSTRING_SERIALIZER_BYTES48[0] &&
           masked_match(copy+i,WOJD_FSTRING_SERIALIZER_BYTES48,WOJD_FSTRING_SERIALIZER_MASK48,48) &&
           tooltip_serializer_valid(view,live+i) && out->signature!=live+i) {
            out->signature=live+i;if(++out->signature_matches>1){out->error=ERROR_DUP_NAME;return FALSE;}
        }
        for(g=0;g<TOOLTIP_GROUPS;g++) {
            const WojdNativeUobjectSiteContext *c=&WOJD_NATIVE_UOBJECT_SITE_CONTEXTS[g_tooltip_groups[g].first];
            const BYTE *target;DWORD owner,anchor;
            if(i+c->size>n || copy[i]!=c->bytes[0] || !masked_match(copy+i,c->bytes,c->mask,c->size))continue;
            anchor=(DWORD)((live+i)-view->base)+c->size;
            if(out->matches[g] && out->anchors[g]==anchor)continue;
            if(++out->group_probes>TOOLTIP_MAX_GROUP_PROBES){out->error=ERROR_TIMEOUT;return FALSE;}
            if(tooltip_group_valid(view,g,anchor,&target,&owner) && !tooltip_accept_group(out,g,anchor,target,owner))return FALSE;
        }
    }
    return TRUE;
}
static DWORD tooltip_hint_load(DWORD anchors[TOOLTIP_GROUPS]) {
    CacheIdentity now,saved;ULONGLONG number;DWORD i,error;
    static const WCHAR *keys[TOOLTIP_GROUPS]={L"skill_anchor",L"buff_anchor",L"mail_anchor"};
    ZeroMemory(&saved,sizeof(saved));
    error=cache_identity(&now);if(error)return error;
    if(!cache_number_section(g_tooltip_cache_path,L"NativeTooltip",L"format_version",&number) || number!=1 ||
       !cache_number_section(g_tooltip_cache_path,L"NativeTooltip",L"signature_revision",&number) || number!=TOOLTIP_SIGNATURE_REVISION ||
       !cache_number_section(g_tooltip_cache_path,L"NativeTooltip",L"file_size",&saved.size) ||
       !cache_number_section(g_tooltip_cache_path,L"NativeTooltip",L"file_mtime",&saved.mtime) ||
       !cache_number_section(g_tooltip_cache_path,L"NativeTooltip",L"file_index",&saved.index) ||
       !cache_number_section(g_tooltip_cache_path,L"NativeTooltip",L"volume_serial",&number) || number>MAXDWORD)return ERROR_INVALID_DATA;
    saved.volume=(DWORD)number;
    for(i=0;i<TOOLTIP_GROUPS;i++) {
        if(!cache_number_section(g_tooltip_cache_path,L"NativeTooltip",keys[i],&number) || !number || number>MAXDWORD)return ERROR_INVALID_DATA;
        anchors[i]=(DWORD)number;
    }
    /* Identity decides freshness only; stale parsed RVAs may still be probed. */
    return cache_identity_equal(&now,&saved)?ERROR_SUCCESS:ERROR_REVISION_MISMATCH;
}
static DWORD tooltip_hint_save(const TooltipResolved *resolved) {
    CacheIdentity id;char text[768];WCHAR temporary[1100];HANDLE file;DWORD error,written;int n;
    error=cache_identity(&id);if(error)return error;
    n=_snprintf_s(text,sizeof(text),_TRUNCATE,
        "; RVAs are hints, revalidated against loaded code. No PE identity gate.\r\n[NativeTooltip]\r\n"
        "format_version=1\r\nsignature_revision=%u\r\nfile_size=%llu\r\nfile_mtime=%llu\r\nfile_index=%llu\r\nvolume_serial=%lu\r\n"
        "serializer_rva=0x%llx\r\nskill_anchor=0x%lx\r\nbuff_anchor=0x%lx\r\nmail_anchor=0x%lx\r\n",
        TOOLTIP_SIGNATURE_REVISION,id.size,id.mtime,id.index,id.volume,(ULONGLONG)(resolved->serializer-g_image_base),
        resolved->anchors[0],resolved->anchors[1],resolved->anchors[2]);
    if(n<0 || _snwprintf_s(temporary,1100,_TRUNCATE,L"%s.pid-%lu.tmp",g_tooltip_cache_path,GetCurrentProcessId())<0)return ERROR_INSUFFICIENT_BUFFER;
    file=CreateFileW(temporary,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE)return GetLastError();
    if(!WriteFile(file,text,(DWORD)n,&written,NULL) || written!=(DWORD)n){error=GetLastError();CloseHandle(file);return error?error:ERROR_WRITE_FAULT;}
    if(!FlushFileBuffers(file)){error=GetLastError();CloseHandle(file);return error;}
    CloseHandle(file);return MoveFileExW(temporary,g_tooltip_cache_path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)?ERROR_SUCCESS:GetLastError();
}
/* Historical/current/stale RVAs have exactly the same role: candidate hints.
   Each accepted chain revalidates all25 contexts,3 distinct unwind owners,
   relative E8 agreement and serializer signature/root/extent against live code. */
static BOOL tooltip_known_group_valid(DWORD group,DWORD anchor,const BYTE **target,DWORD *owner) {
    BOOL valid;g_tooltip_probing_known_hint=TRUE;
    valid=tooltip_group_valid(&g_tooltip_view,group,anchor,target,owner);
    g_tooltip_probing_known_hint=FALSE;return valid;
}
static DWORD tooltip_probe_hint_chain(BOOL historical,TooltipResolved *out) {
    DWORD g;ZeroMemory(out,sizeof(*out));
    for(g=0;g<TOOLTIP_GROUPS;g++) {
        const BYTE *target;DWORD owner;
        DWORD cached=g_tooltip_hint_anchors[g];
        DWORD baseline=WOJD_NATIVE_UOBJECT_SITE_CONTEXTS[g_tooltip_groups[g].first].return_rva;
        if((g_tooltip_hint_status==ERROR_SUCCESS || g_tooltip_hint_status==ERROR_REVISION_MISMATCH) &&
           tooltip_known_group_valid(g,cached,&target,&owner))
            if(!tooltip_accept_group(out,g,cached,target,owner))return out->error;
        if(historical && baseline!=cached && tooltip_known_group_valid(g,baseline,&target,&owner))
            if(!tooltip_accept_group(out,g,baseline,target,owner))return out->error;
    }
    return tooltip_complete(out,FALSE);
}
static DWORD tooltip_result_route(DWORD identity_status,const DWORD anchors[TOOLTIP_GROUPS],const TooltipResolved *result) {
    DWORD g;if(tooltip_complete(result,FALSE))return CACHE_ROUTE_PENDING;
    if(identity_status!=ERROR_SUCCESS)return CACHE_ROUTE_CALIBRATION;
    for(g=0;g<TOOLTIP_GROUPS;g++)if(result->anchors[g]!=anchors[g])return CACHE_ROUTE_CALIBRATION;
    return CACHE_ROUTE_WARM;
}
static DWORD tooltip_resolver_begin(void) {
    MemoryProbe probe;
    if(!image_view_report(g_image_base,&g_tooltip_view,&probe)){code_probe_failure(1,&probe);return ERROR_NOT_READY;}
    if(_snwprintf_s(g_tooltip_cache_path,1024,_TRUNCATE,L"%s\\tooltip-cache.ini",g_root_path)<0)return ERROR_FILENAME_EXCED_RANGE;
    if(!g_tooltip_hint_loaded){g_tooltip_hint_status=tooltip_hint_load(g_tooltip_hint_anchors);g_tooltip_hint_loaded=TRUE;}
    ZeroMemory(&g_tooltip_resolved,sizeof(g_tooltip_resolved));ZeroMemory(&g_tooltip_scan,sizeof(g_tooltip_scan));
    g_tooltip_resolution_scope=3;g_tooltip_resolver_started=TRUE;return ERROR_SUCCESS;
}
static DWORD tooltip_resolver_step(void) {
    DWORD error,route;TooltipResolved hinted;BOOL current_pending=FALSE;
    ULONGLONG prior_bytes,prior_skipped;DWORD prior_steps,prior_gaps;
    if(g_tooltip_resolver_ready)return ERROR_SUCCESS;
    if(!g_tooltip_resolver_started){error=tooltip_resolver_begin();if(error)return error;}
    /* Current known anchors remain candidates alongside relocation work. A
       fully validated exact cached chain wins regardless of elapsed scan work. */
    error=tooltip_probe_hint_chain(FALSE,&hinted);
    if(!error) {
        route=tooltip_result_route(g_tooltip_hint_status,g_tooltip_hint_anchors,&hinted);
        g_tooltip_resolved=hinted;g_tooltip_resolution_scope=route==CACHE_ROUTE_WARM?1:2;
        g_tooltip_resolver_ready=TRUE;return ERROR_SUCCESS;
    }
    if(error!=ERROR_NOT_FOUND && error!=ERROR_NOT_READY)return error;
    current_pending=cache_probe_may_retry(g_tooltip_hint_status,error);
    if(current_pending)g_tooltip_warm_probes++;
    error=tooltip_probe_hint_chain(TRUE,&hinted);
    if(!error) {
        route=tooltip_result_route(g_tooltip_hint_status,g_tooltip_hint_anchors,&hinted);
        g_tooltip_resolved=hinted;g_tooltip_resolution_scope=route==CACHE_ROUTE_WARM?1:2;
        g_tooltip_resolver_ready=TRUE;return ERROR_SUCCESS;
    }
    if(error!=ERROR_NOT_FOUND)return error;
    if(g_tooltip_scan_exhausted)return current_pending?ERROR_NOT_READY:ERROR_NOT_FOUND;
    if(g_tooltip_retry_steps){g_tooltip_retry_steps--;return ERROR_NOT_READY;}
    if(g_tooltip_setup_steps>=TOOLTIP_SETUP_STEP_LIMIT) {
        g_tooltip_scan_exhausted=TRUE;return current_pending?ERROR_NOT_READY:ERROR_TIMEOUT;
    }
    g_tooltip_setup_steps++;
    prior_bytes=g_tooltip_scan.bytes;prior_skipped=g_tooltip_scan.skipped_bytes;
    prior_steps=g_tooltip_scan.steps;prior_gaps=g_tooltip_scan.gaps;
    error=scan_executable_step(&g_tooltip_view,&g_tooltip_scan,g_tooltip_scan_copy,sizeof(g_tooltip_scan_copy),tooltip_scan_chunk,&g_tooltip_resolved);
    g_tooltip_total_scan_bytes+=g_tooltip_scan.bytes-prior_bytes;
    g_tooltip_total_skipped_bytes+=g_tooltip_scan.skipped_bytes-prior_skipped;
    g_tooltip_total_scan_steps+=g_tooltip_scan.steps-prior_steps;
    g_tooltip_total_gaps+=g_tooltip_scan.gaps-prior_gaps;
    if(g_tooltip_resolved.error) {
        if(g_tooltip_resolved.error==ERROR_TIMEOUT && current_pending){g_tooltip_scan_exhausted=TRUE;return ERROR_NOT_READY;}
        return g_tooltip_resolved.error;
    }
    if(error==ERROR_MORE_DATA)return ERROR_NOT_READY;
    if(error) {
        if(error==ERROR_TIMEOUT && current_pending){g_tooltip_scan_exhausted=TRUE;return ERROR_NOT_READY;}
        return error;
    }
    g_tooltip_phases++;
    error=tooltip_complete(&g_tooltip_resolved,TRUE);
    if(error==ERROR_NOT_FOUND && g_tooltip_phases<TOOLTIP_COLD_PHASE_LIMIT) {
        ZeroMemory(&g_tooltip_resolved,sizeof(g_tooltip_resolved));ZeroMemory(&g_tooltip_scan,sizeof(g_tooltip_scan));
        g_tooltip_retry_steps=TOOLTIP_COLD_RETRY_STEPS;return ERROR_NOT_READY;
    }
    if(error) {
        if(error==ERROR_NOT_FOUND && current_pending){g_tooltip_scan_exhausted=TRUE;return ERROR_NOT_READY;}
        return error;
    }
    route=tooltip_result_route(g_tooltip_hint_status,g_tooltip_hint_anchors,&g_tooltip_resolved);
    g_tooltip_resolution_scope=route==CACHE_ROUTE_WARM?1:3;
    g_tooltip_resolver_ready=TRUE;return ERROR_SUCCESS;
}
/* Translation uses the actual serializer RDX GameString*, with literal-source
   lookup. Full caller-group identity preserves the existing 15-site policy;
   no object reconstruction, record ID, or variant is used in noncapture mode. */
static const WojdTooltipFieldSite *tooltip_origin_lookup(const void *caller,BOOL *native_layout) {
    const TooltipOriginMap *map=(const TooltipOriginMap *)InterlockedCompareExchangePointer(&g_tooltip_origin_map,NULL,NULL);
    DWORD i;*native_layout=FALSE;
    if(!map)return NULL;
    for(i=0;i<map->count;i++)if(map->sites[i].caller==caller) {
        *native_layout=map->sites[i].native_layout;return map->sites[i].site;
    }
    return NULL;
}
static DWORD tooltip_publish_origin_additions(const TooltipOrigin *additions,DWORD count,DWORD group_bit) {
    const TooltipOriginMap *prior=(const TooltipOriginMap *)InterlockedCompareExchangePointer(&g_tooltip_origin_map,NULL,NULL);
    TooltipOriginMap *next;DWORD i,j,n=prior?prior->count:0;
    if(g_tooltip_origin_groups&group_bit)return ERROR_INVALID_STATE;
    if(!count || count>TOOLTIP_ORIGIN_CAPACITY-n || g_tooltip_origin_publications>=4)return ERROR_INSUFFICIENT_BUFFER;
    for(i=0;i<count;i++) {
        if(!additions[i].caller || !additions[i].site)return ERROR_INVALID_DATA;
        for(j=0;j<n;j++)if(prior->sites[j].caller==additions[i].caller)return ERROR_DUP_NAME;
        for(j=0;j<i;j++)if(additions[j].caller==additions[i].caller)return ERROR_DUP_NAME;
    }
    next=&g_tooltip_origin_maps[g_tooltip_origin_publications];
    if(prior)*next=*prior;else ZeroMemory(next,sizeof(*next));
    for(i=0;i<count;i++)next->sites[n+i]=additions[i];
    next->count=n+count;
    /* Interlocked publication is the release/acquire boundary for count, site,
       exact return address, and layout together. Never mutate or free next. */
    InterlockedExchangePointer(&g_tooltip_origin_map,next);
    g_tooltip_origin_publications++;g_tooltip_origin_groups|=group_bit;
    g_tooltip_origin_count=next->count;InterlockedExchange(&g_tooltip_generation,1);
    return ERROR_SUCCESS;
}
static DWORD tooltip_publish_origins(void) {
    TooltipOrigin additions[25];DWORD g,j,count=0,error;
    error=tooltip_fresh_native_chain();if(error)return error;
    for(g=0;g<TOOLTIP_GROUPS;g++)for(j=0;j<g_tooltip_groups[g].count;j++) {
        DWORD i=g_tooltip_groups[g].first+j;
        const WojdTooltipFieldSite *site=&WOJD_NATIVE_UOBJECT_FIELD_SITES[i];
        DWORD baseline=WOJD_NATIVE_UOBJECT_SITE_CONTEXTS[g_tooltip_groups[g].first].return_rva;
        if(!site->approved_capture)continue;
        additions[count].caller=g_image_base+g_tooltip_resolved.anchors[g]+(site->return_rva-baseline);
        additions[count].site=site;additions[count].native_layout=TRUE;count++;
    }
    return tooltip_publish_origin_additions(additions,count,1u);
}
