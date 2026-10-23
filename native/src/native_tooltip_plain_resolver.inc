/* Independent Plain Skill/Buff discovery. Mail intentionally has no group. */
#define TOOLTIP_PLAIN_GROUPS 2u
static const DWORD g_tooltip_plain_indices[TOOLTIP_PLAIN_GROUPS][9]={{0,1,2,3,4,5,6,13,14},{7,8}};
static const DWORD g_tooltip_plain_counts[TOOLTIP_PLAIN_GROUPS]={9,2};
static const DWORD g_tooltip_plain_current_hints[TOOLTIP_PLAIN_GROUPS]={0x335081au,0x335065eu};
static const WCHAR *g_tooltip_plain_cache_names[TOOLTIP_PLAIN_GROUPS]={L"tooltip-plain-skill-cache.ini",L"tooltip-plain-buff-cache.ini"};
static const char *g_tooltip_plain_names[TOOLTIP_PLAIN_GROUPS]={"PLAIN_SKILL","PLAIN_BUFF"};
typedef struct TooltipPlainGroup {
    DWORD anchor,owner,matches,probes,error,route;
    const BYTE *serializer;
    DWORD hint_anchor,hint_serializer,hint_owner,hint_status;
    BOOL ready,persisted,done;
    WCHAR cache_path[1024];
} TooltipPlainGroup;
static TooltipPlainGroup g_tooltip_plain[TOOLTIP_PLAIN_GROUPS];
static ImageView g_tooltip_plain_view;
static ExecutableScan g_tooltip_plain_scan;
static BYTE g_tooltip_plain_scan_copy[SCAN_STEP_BYTES];
static BOOL g_tooltip_plain_started,g_tooltip_plain_exhausted;
static DWORD g_tooltip_plain_phases,g_tooltip_plain_retry_steps;

static DWORD tooltip_plain_group_check(const ImageView *view,DWORD group,DWORD anchor,const BYTE **serializer,DWORD *owner_rva) {
    DWORD i,error,first_index=g_tooltip_plain_indices[group][0];
    const WojdNativeUobjectSiteContext *first=&WOJD_PLAIN_SITE_CONTEXTS[first_index];
    const BYTE *owner=NULL,*owner_end=NULL,*target=NULL;
    if(!anchor || anchor>=view->size)return ERROR_INVALID_DATA;
    for(i=0;i<g_tooltip_plain_counts[group];i++) {
        DWORD index=g_tooltip_plain_indices[group][i];
        const WojdNativeUobjectSiteContext *context=&WOJD_PLAIN_SITE_CONTEXTS[index];
        LONGLONG offset=(LONGLONG)anchor+(LONGLONG)context->context_rva-(LONGLONG)first->return_rva;
        BYTE bytes[24];const BYTE *address,*root,*end,*callee;MemoryProbe probe;
        if(context->size<5 || context->size>sizeof(bytes) || offset<0 || offset>view->size ||
           context->size>view->size-(SIZE_T)offset)return ERROR_INVALID_DATA;
        address=view->base+(SIZE_T)offset;
        if(!in_image(view,address,context->size) || !executable(view,address))return ERROR_INVALID_DATA;
        if(!read_exact_report(address,bytes,context->size,&probe))return ERROR_NOT_READY;
        if(!masked_match(bytes,context->bytes,context->mask,context->size) || bytes[context->size-5]!=0xe8 ||
           !tooltip_function(view,address,&root,&end) || address+context->size>end)return ERROR_INVALID_DATA;
        if(!owner){owner=root;owner_end=end;}else if(root!=owner || end!=owner_end)return ERROR_INVALID_DATA;
        callee=relative_target_report(address+context->size-5,&probe);
        if(!callee)return probe.kind==PROBE_NONE?ERROR_INVALID_DATA:ERROR_NOT_READY;
        if(target && target!=callee)return ERROR_INVALID_DATA;
        target=callee;
    }
    error=tooltip_serializer_check(view,target);if(error)return error;
    *serializer=target;*owner_rva=(DWORD)(owner-view->base);return ERROR_SUCCESS;
}
static BOOL tooltip_plain_group_valid(const ImageView *view,DWORD group,DWORD anchor,const BYTE **serializer,DWORD *owner_rva) {
    return tooltip_plain_group_check(view,group,anchor,serializer,owner_rva)==ERROR_SUCCESS;
}
static DWORD tooltip_fresh_plain_group(DWORD group) {
    const TooltipPlainGroup *resolved=&g_tooltip_plain[group];const BYTE *serializer;DWORD owner,error;
    if(!resolved->ready)return ERROR_NOT_READY;
    error=tooltip_plain_group_check(&g_tooltip_plain_view,group,resolved->anchor,&serializer,&owner);if(error)return error;
    return serializer==resolved->serializer && owner==resolved->owner?ERROR_SUCCESS:ERROR_INVALID_DATA;
}
/* A duplicate affects this group only. Repeated overlap/hints are one anchor. */
static void tooltip_plain_accept(TooltipPlainGroup *out,DWORD anchor,const BYTE *serializer,DWORD owner) {
    if(out->matches && out->anchor==anchor)return;
    if(++out->matches!=1){out->error=ERROR_DUP_NAME;return;}
    out->anchor=anchor;out->owner=owner;out->serializer=serializer;
}
static DWORD tooltip_plain_route(const TooltipPlainGroup *group,DWORD anchor,const BYTE *serializer,DWORD owner) {
    return group->hint_status==ERROR_SUCCESS && group->hint_anchor==anchor &&
        group->hint_serializer==(DWORD)(serializer-g_image_base) && group->hint_owner==owner?CACHE_ROUTE_WARM:CACHE_ROUTE_CALIBRATION;
}
static DWORD tooltip_plain_cache_load(TooltipPlainGroup *out) {
    CacheIdentity now,saved;ULONGLONG number;DWORD error;
    ZeroMemory(&saved,sizeof(saved));error=cache_identity(&now);if(error)return error;
    if(!cache_number_section(out->cache_path,L"PlainTooltip",L"format_version",&number) || number!=1 ||
       !cache_number_section(out->cache_path,L"PlainTooltip",L"signature_revision",&number) || number!=1 ||
       !cache_number_section(out->cache_path,L"PlainTooltip",L"file_size",&saved.size) ||
       !cache_number_section(out->cache_path,L"PlainTooltip",L"file_mtime",&saved.mtime) ||
       !cache_number_section(out->cache_path,L"PlainTooltip",L"file_index",&saved.index) ||
       !cache_number_section(out->cache_path,L"PlainTooltip",L"volume_serial",&number) || number>MAXDWORD)return ERROR_INVALID_DATA;
    saved.volume=(DWORD)number;
    if(!cache_number_section(out->cache_path,L"PlainTooltip",L"anchor",&number) || !number || number>MAXDWORD)return ERROR_INVALID_DATA;
    out->hint_anchor=(DWORD)number;
    if(!cache_number_section(out->cache_path,L"PlainTooltip",L"serializer_rva",&number) || !number || number>MAXDWORD)return ERROR_INVALID_DATA;
    out->hint_serializer=(DWORD)number;
    if(!cache_number_section(out->cache_path,L"PlainTooltip",L"owner_rva",&number) || !number || number>MAXDWORD)return ERROR_INVALID_DATA;
    out->hint_owner=(DWORD)number;
    return cache_identity_equal(&now,&saved)?ERROR_SUCCESS:ERROR_REVISION_MISMATCH;
}
static DWORD tooltip_plain_cache_save(const TooltipPlainGroup *group) {
    CacheIdentity id;char text[768];WCHAR temporary[1100];HANDLE file;DWORD error,written;int n;
    error=cache_identity(&id);if(error)return error;
    n=_snprintf_s(text,sizeof(text),_TRUNCATE,
        "; Per-group hints; every full context and callee is revalidated.\r\n[PlainTooltip]\r\n"
        "format_version=1\r\nsignature_revision=1\r\nfile_size=%llu\r\nfile_mtime=%llu\r\nfile_index=%llu\r\nvolume_serial=%lu\r\n"
        "anchor=0x%lx\r\nserializer_rva=0x%llx\r\nowner_rva=0x%lx\r\n",id.size,id.mtime,id.index,id.volume,
        group->anchor,(ULONGLONG)(group->serializer-g_image_base),group->owner);
    if(n<0 || _snwprintf_s(temporary,1100,_TRUNCATE,L"%s.pid-%lu.tmp",group->cache_path,GetCurrentProcessId())<0)return ERROR_INSUFFICIENT_BUFFER;
    file=CreateFileW(temporary,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE)return GetLastError();
    if(!WriteFile(file,text,(DWORD)n,&written,NULL) || written!=(DWORD)n) {
        error=GetLastError();CloseHandle(file);return error?error:ERROR_WRITE_FAULT;
    }
    if(!FlushFileBuffers(file)){error=GetLastError();CloseHandle(file);return error;}
    CloseHandle(file);return MoveFileExW(temporary,group->cache_path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)?ERROR_SUCCESS:GetLastError();
}
static BOOL tooltip_plain_scan_chunk(const ImageView *view,const BYTE *live,const BYTE *copy,SIZE_T size,void *unused) {
    SIZE_T i;DWORD group;(void)unused;
    for(i=0;i<size;i++)for(group=0;group<TOOLTIP_PLAIN_GROUPS;group++) {
        TooltipPlainGroup *out=&g_tooltip_plain[group];
        const WojdNativeUobjectSiteContext *first=&WOJD_PLAIN_SITE_CONTEXTS[g_tooltip_plain_indices[group][0]];
        const BYTE *target;DWORD owner,anchor;
        if(out->ready || out->done || out->error || i+first->size>size || copy[i]!=first->bytes[0] ||
           !masked_match(copy+i,first->bytes,first->mask,first->size))continue;
        anchor=(DWORD)(live+i-view->base)+first->size;
        if(out->matches && out->anchor==anchor)continue;
        if(++out->probes>TOOLTIP_MAX_GROUP_PROBES){out->error=ERROR_TIMEOUT;continue;}
        if(tooltip_plain_group_valid(view,group,anchor,&target,&owner))tooltip_plain_accept(out,anchor,target,owner);
    }
    return TRUE;
}
static DWORD tooltip_plain_begin(void) {
    DWORD i;MemoryProbe probe;
    if(!image_view_report(g_image_base,&g_tooltip_plain_view,&probe))return ERROR_NOT_READY;
    for(i=0;i<TOOLTIP_PLAIN_GROUPS;i++) {
        TooltipPlainGroup *group=&g_tooltip_plain[i];
        if(_snwprintf_s(group->cache_path,1024,_TRUNCATE,L"%s\\%s",g_root_path,g_tooltip_plain_cache_names[i])<0)return ERROR_FILENAME_EXCED_RANGE;
        group->hint_status=tooltip_plain_cache_load(group);
    }
    g_tooltip_plain_started=TRUE;return ERROR_SUCCESS;
}
static void tooltip_plain_resolver_step(void) {
    DWORD group,error;BOOL any_unresolved=FALSE;
    if(!g_tooltip_plain_started) {
        error=tooltip_plain_begin();
        if(error==ERROR_NOT_READY)return;
        if(error){for(group=0;group<TOOLTIP_PLAIN_GROUPS;group++)g_tooltip_plain[group].error=error;return;}
    }
    for(group=0;group<TOOLTIP_PLAIN_GROUPS;group++) {
        TooltipPlainGroup *out=&g_tooltip_plain[group];const BYTE *target;DWORD owner;
        if(out->ready || out->done || out->error)continue;
        /* An exact current cache remains eligible on every worker tick even
           after scan exhaustion or unreadable startup pages. No timed discard. */
        if(out->hint_status==ERROR_SUCCESS &&
           tooltip_plain_group_valid(&g_tooltip_plain_view,group,out->hint_anchor,&target,&owner) &&
           tooltip_plain_route(out,out->hint_anchor,target,owner)==CACHE_ROUTE_WARM) {
            out->anchor=out->hint_anchor;out->owner=owner;out->serializer=target;
            out->matches=1;out->route=CACHE_ROUTE_WARM;out->ready=TRUE;continue;
        }
        any_unresolved=TRUE;
        /* Stale/current historical hints seed validation, never uniqueness or
           a warm classification. Cold groups wait for the bounded scan scope. */
        if(!out->matches) {
            DWORD hints[3],h;
            hints[0]=out->hint_anchor;hints[1]=g_tooltip_plain_current_hints[group];
            hints[2]=WOJD_PLAIN_SITE_CONTEXTS[g_tooltip_plain_indices[group][0]].return_rva;
            for(h=0;h<3;h++)if(hints[h] && tooltip_plain_group_valid(&g_tooltip_plain_view,group,hints[h],&target,&owner))
                tooltip_plain_accept(out,hints[h],target,owner);
            /* A newly readable retained hint warrants a fresh uniqueness pass,
               even if earlier relocation passes exhausted before it appeared. */
            if(out->matches==1 && g_tooltip_plain_exhausted) {
                ZeroMemory(&g_tooltip_plain_scan,sizeof(g_tooltip_plain_scan));
                g_tooltip_plain_exhausted=FALSE;g_tooltip_plain_phases=0;
            }
        }
    }
    if(!any_unresolved || g_tooltip_plain_exhausted)return;
    if(g_tooltip_plain_retry_steps){g_tooltip_plain_retry_steps--;return;}
    error=scan_executable_step(&g_tooltip_plain_view,&g_tooltip_plain_scan,g_tooltip_plain_scan_copy,
        sizeof(g_tooltip_plain_scan_copy),tooltip_plain_scan_chunk,NULL);
    if(error==ERROR_MORE_DATA)return;
    if(error) {
        /* Current cache candidates survive finite relocation work. */
        for(group=0;group<TOOLTIP_PLAIN_GROUPS;group++)if(!g_tooltip_plain[group].ready &&
           !cache_probe_may_retry(g_tooltip_plain[group].hint_status,ERROR_NOT_READY))g_tooltip_plain[group].error=error;
        g_tooltip_plain_exhausted=TRUE;return;
    }
    g_tooltip_plain_phases++;
    any_unresolved=FALSE;
    for(group=0;group<TOOLTIP_PLAIN_GROUPS;group++) {
        TooltipPlainGroup *out=&g_tooltip_plain[group];
        if(out->ready || out->done || out->error)continue;
        if(out->matches==1) {
            /* Revalidate a scan candidate after the pass. Changed/unreadable
               candidates remain unresolved rather than enabling a stale map. */
            const BYTE *target;DWORD owner;
            if(tooltip_plain_group_valid(&g_tooltip_plain_view,group,out->anchor,&target,&owner) &&
               target==out->serializer && owner==out->owner) {
                out->route=tooltip_plain_route(out,out->anchor,target,owner);out->ready=TRUE;continue;
            }
        }
        any_unresolved=TRUE;
        if(g_tooltip_plain_phases>=TOOLTIP_COLD_PHASE_LIMIT && !cache_probe_may_retry(out->hint_status,ERROR_NOT_READY))out->error=ERROR_NOT_FOUND;
        out->anchor=0;out->owner=0;out->serializer=NULL;out->matches=0;out->probes=0;
    }
    if(any_unresolved && g_tooltip_plain_phases<TOOLTIP_COLD_PHASE_LIMIT) {
        ZeroMemory(&g_tooltip_plain_scan,sizeof(g_tooltip_plain_scan));g_tooltip_plain_retry_steps=TOOLTIP_COLD_RETRY_STEPS;
    }else g_tooltip_plain_exhausted=TRUE;
}
static DWORD tooltip_publish_plain_origins(DWORD group) {
    const TooltipPlainGroup *resolved=&g_tooltip_plain[group];TooltipOrigin additions[9];DWORD i,error;
    DWORD baseline=WOJD_PLAIN_SITE_CONTEXTS[g_tooltip_plain_indices[group][0]].return_rva;
    error=tooltip_fresh_plain_group(group);if(error)return error;
    for(i=0;i<g_tooltip_plain_counts[group];i++) {
        const WojdTooltipFieldSite *site=&WOJD_PLAIN_APPROVED_FIELD_SITES[g_tooltip_plain_indices[group][i]];
        additions[i].caller=g_image_base+resolved->anchor+(site->return_rva-baseline);
        additions[i].site=site;additions[i].native_layout=FALSE;
    }
    return tooltip_publish_origin_additions(additions,g_tooltip_plain_counts[group],2u<<group);
}
