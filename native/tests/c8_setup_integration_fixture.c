/* Full actual runtime TU + actual MinHook, synthetic private image only.
   Copied signature bytes are decoded/patched, NEVER executed or called. */
#define WOJD_CAPTURE 0
#define WOJD_SELFTEST 0
#include "../src/localization.c"
static int checks,failures;
#define CHECK(t,label) do{checks++;if(!(t)){printf("FAIL %s line=%d\n",label,__LINE__);failures++;}else printf("PASS %s\n",label);}while(0)
int main(void) {
    BYTE *image,*trampoline,before[sizeof(data_assign_bytes)];IMAGE_DOS_HEADER *dos;IMAGE_NT_HEADERS64 *nt;void *blocked_trampoline=NULL;
    IMAGE_SECTION_HEADER *section;RUNTIME_FUNCTION functions[9];ImageView view;DWORD error,g,j;
    static const DWORD anchors[3]={0x2050,0x3050,0x4050},owners[3]={0x2000,0x3000,0x4000};
    /* Unconstrained allocation often lands beside another private allocation.
       That did not exercise the absolute entry used by the real EXE. Reserve
       a low synthetic image, then assert the actual 14-byte layout below. */
    image=NULL;
    for(j=0;j<16 && !image;j++)image=(BYTE *)VirtualAlloc((void *)(uintptr_t)(0x180000000ull+j*0x100000000ull),
        0xc000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);
    if(!image)return 2;
    dos=(IMAGE_DOS_HEADER *)image;dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;
    nt=(IMAGE_NT_HEADERS64 *)(image+0x80);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=IMAGE_FILE_MACHINE_AMD64;
    nt->FileHeader.SizeOfOptionalHeader=sizeof(IMAGE_OPTIONAL_HEADER64);nt->FileHeader.NumberOfSections=1;
    nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR64_MAGIC;nt->OptionalHeader.SizeOfImage=0xc000;
    section=IMAGE_FIRST_SECTION(nt);section->VirtualAddress=0x400;section->Misc.VirtualSize=0xbc00;
    section->Characteristics=IMAGE_SCN_MEM_EXECUTE|IMAGE_SCN_MEM_READ;
    memcpy(image+0x600,data_assign_bytes,sizeof(data_assign_bytes));
    memcpy(image+0x800,WOJD_FSTRING_SERIALIZER_BYTES48,48);image[0xf00]=1;
    functions[0].BeginAddress=0x600;functions[0].EndAddress=0x619;functions[0].UnwindData=0xf00;
    functions[1].BeginAddress=0x800;functions[1].EndAddress=0xc1b;functions[1].UnwindData=0xf00;
    for(g=0;g<3;g++) {
        functions[g+2].BeginAddress=owners[g];functions[g+2].EndAddress=owners[g]+0x600;functions[g+2].UnwindData=0xf00;
        for(j=0;j<g_tooltip_groups[g].count;j++) {
            const WojdNativeUobjectSiteContext *first=&WOJD_NATIVE_UOBJECT_SITE_CONTEXTS[g_tooltip_groups[g].first];
            const WojdNativeUobjectSiteContext *context=&WOJD_NATIVE_UOBJECT_SITE_CONTEXTS[g_tooltip_groups[g].first+j];
            BYTE *at=image+anchors[g]+((LONG)context->context_rva-(LONG)first->return_rva);LONG displacement;
            memcpy(at,context->bytes,context->size);displacement=(LONG)((image+0x800)-(at+context->size));
            memcpy(at+context->size-4,&displacement,4);
        }
    }
    for(g=0;g<2;g++) {
        functions[g+5].BeginAddress=0x5000+g*0x1000;functions[g+5].EndAddress=0x5600+g*0x1000;functions[g+5].UnwindData=0xf00;
        for(j=0;j<g_tooltip_plain_counts[g];j++) {
            const WojdNativeUobjectSiteContext *first=&WOJD_PLAIN_SITE_CONTEXTS[g_tooltip_plain_indices[g][0]];
            const WojdNativeUobjectSiteContext *context=&WOJD_PLAIN_SITE_CONTEXTS[g_tooltip_plain_indices[g][j]];
            BYTE *at=image+functions[g+5].BeginAddress+0x50+((LONG)context->context_rva-(LONG)first->return_rva);LONG displacement;
            memcpy(at,context->bytes,context->size);displacement=(LONG)((image+0x800)-(at+context->size));
            memcpy(at+context->size-4,&displacement,4);
        }
    }
    memcpy(image+0x8000,data_reader_bytes,sizeof(data_reader_bytes));
    memcpy(image+0xa000,data_read_bytes_bytes,sizeof(data_read_bytes_bytes));
    {
        LONG displacement=(LONG)((image+0x600)-(image+0x8223));memcpy(image+0x821f,&displacement,4);
        displacement=(LONG)((image+0xa000)-(image+0x8113));memcpy(image+0x810f,&displacement,4);
    }
    functions[7].BeginAddress=0x8000;functions[7].EndAddress=0x8000+sizeof(data_reader_bytes);functions[7].UnwindData=0xf00;
    functions[8].BeginAddress=0xa000;functions[8].EndAddress=0xa000+sizeof(data_read_bytes_bytes);functions[8].UnwindData=0xf00;
    if(!RtlAddFunctionTable(functions,9,(DWORD64)(uintptr_t)image))return 2;
    memcpy(before,image+0x600,sizeof(before));g_game_host=TRUE;g_image_base=image;g_prefer_far=TRUE;
    g_wide_ready=TRUE;g_wide_count=1;QueryPerformanceFrequency(&g_diag_frequency);QueryPerformanceCounter(&g_diag_attach);
    CHECK(image_view(image,&view),"synthetic PE and registered unwind metadata ready");
    error=tooltip_prepare_for_serializer(image+0x800);
    CHECK(error==ERROR_SUCCESS && g_target==image+0x600 &&
        g_tooltip_translation_ready && g_original_assign && g_active && g_assignment_signature.ready && !g_executing_return,
        "validated allocator detour enables before generic decoder is discovered");
    if(error){printf("FAILED_EARLY_ENABLE status=%lu distant_target=%p trampoline=%p\n",error,image+0x600,(void *)(uintptr_t)g_original_assign);
        restore_data();MH_Uninitialize();RtlDeleteFunctionTable(functions);VirtualFree(image,0,MEM_RELEASE);return 1;}
    {
        ReaderCache cache={0};DataResult result;MemoryProbe probe;DWORD stage;BYTE saved;
        cache.reader=0x8000;cache.assign=0x600;cache.raw=0xa000;
        CHECK(memcmp(before,image+0x600,sizeof(before)) && assignment_signature_at_report(&view,image+0x600,&probe),
            "actual MinHook patch is recognized as owned rather than pristine code");
        {
            BYTE entry[14];DWORD patch_size=0;
            CHECK(read_exact(image+0x600,entry,sizeof(entry)) &&
                assignment_jump_owned(image+0x600,entry,(void *)(uintptr_t)assignment_hook,&patch_size) && patch_size==14,
                "distant synthetic EXE exercises an actual absolute entry through MinHook relay");
            {
                uintptr_t destination=(uintptr_t)(image+0xb000),wrong=(uintptr_t)assignment_hook+16;
                memcpy(entry+6,&destination,8);memcpy(image+0xb000,entry,6);memcpy(image+0xb006,&wrong,8);
                CHECK(!assignment_jump_owned(image+0x600,entry,(void *)(uintptr_t)assignment_hook,&patch_size),
                    "absolute entry through relay to a different detour is rejected");
                destination=(uintptr_t)(image+0xb100);memcpy(image+0xb006,&destination,8);
                memcpy(image+0xb100,entry,6);destination=(uintptr_t)assignment_hook;memcpy(image+0xb106,&destination,8);
                CHECK(!assignment_jump_owned(image+0x600,entry,(void *)(uintptr_t)assignment_hook,&patch_size),
                    "relay validation follows exactly one hop instead of an arbitrary jump chain");
            }
        }
        CHECK(check_executing_origin(image+0x8223)==ERROR_SUCCESS,"full executing decoder and raw-reader chain validate");
        CHECK(!executing_origin(image+0x8224) && !g_executing_return,"unrelated caller cannot publish decoder origin");
        image[0x815e]^=1;
        CHECK(!executing_origin(image+0x8223) && !g_executing_return,"not-yet-matching decoder remains pending");
        image[0x815e]^=1;
        CHECK(executing_origin(image+0x8223) && g_executing_return==image+0x8223 && g_executing_first_us,
            "first valid executing call is accepted without waiting for setup scan");
        CHECK(executing_origin_result(&result)==ERROR_SUCCESS && result.candidates==1 &&
            result.reader==(ULONGLONG)(uintptr_t)(image+0x8000) && result.raw_reader==(ULONGLONG)(uintptr_t)(image+0xa000),
            "cold start hands executing proof to setup without a cache or completed scan");
        {
            DataDiscoveryJob exhausted={0};exhausted.complete=TRUE;exhausted.status=ERROR_NOT_FOUND;
            CHECK(!data_discovery_terminal(&exhausted,FALSE,TRUE,FALSE) &&
                !data_discovery_terminal(&exhausted,FALSE,FALSE,TRUE),
                "early scan exhaustion waits for executing hook or pending typed setup");
            CHECK(data_discovery_terminal(&exhausted,FALSE,FALSE,FALSE),"no remaining discovery route terminates normally");
            exhausted.status=ERROR_DUP_NAME;
            CHECK(data_discovery_terminal(&exhausted,TRUE,TRUE,TRUE),"ambiguous scanned origins remain a terminal error");
        }
        CHECK(!executing_origin(image+0x8224),"published decoder origin still rejects other callers");
        CHECK(cache_probe(image,&cache,&result,&stage)==ERROR_SUCCESS && stage==15 && result.assign==(ULONGLONG)(uintptr_t)(image+0x600),
            "warm cache completes after early patch instead of reporting a false mask failure");
        ZeroMemory(&result,sizeof(result));reader_scan(&view,image+0x8000,image+0x8000,sizeof(data_reader_bytes),&result);
        CHECK(result.candidates==1,"relocation scan also recognizes the exact owned assignment patch");
        saved=image[0x606];image[0x606]^=1;
        CHECK(!assignment_signature_at_report(&view,image+0x600,&probe) && cache_probe(image,&cache,&result,&stage)!=ERROR_SUCCESS,
            "different detour destination is rejected by both signature and cache validation");
        image[0x606]=saved;
        CHECK(assignment_signature_at_report(&view,image+0x600,&probe),"restoring owned patch recovers validation");
        image[0x650]^=1;
        CHECK(!assignment_signature_at_report(&view,image+0x600,&probe),"changed instruction after owned jump is rejected");
        image[0x650]^=1;memcpy(image+0x9000,image+0x600,sizeof(data_assign_bytes));
        CHECK(!assignment_signature_at_report(&view,image+0x9000,&probe),"owned patch bytes copied to another address grant no authority");
        functions[7].EndAddress--;
        CHECK(check_executing_origin(image+0x8223)!=ERROR_SUCCESS,"wrong unwind owner size is rejected");
        functions[7].EndAddress++;
        CHECK(check_executing_origin(image+0x8223)==ERROR_SUCCESS,"restored complete origin validates again");
        {
            void *near_trampoline=NULL;BYTE entry[14];DWORD patch_size=0;
            memcpy(image+0x9000,before,sizeof(before));g_prefer_far=FALSE;
            CHECK(MH_CreateHook(image+0x9000,(void *)(uintptr_t)assignment_hook,&near_trampoline)==MH_OK &&
                MH_EnableHook(image+0x9000)==MH_OK && read_exact(image+0x9000,entry,sizeof(entry)) &&
                assignment_jump_owned(image+0x9000,entry,(void *)(uintptr_t)assignment_hook,&patch_size) && patch_size==5,
                "actual near MinHook relay is also recognized as this detour");
            CHECK(MH_DisableHook(image+0x9000)==MH_OK && MH_RemoveHook(image+0x9000)==MH_OK &&
                !memcmp(before,image+0x9000,sizeof(before)),"near ownership fixture restores all original instructions");
            g_prefer_far=TRUE;
        }
    }
    trampoline=(BYTE *)(uintptr_t)g_original_assign;
    g_tooltip_plain_view=view;
    for(g=0;g<2;g++) {
        g_tooltip_plain[g].ready=TRUE;g_tooltip_plain[g].anchor=functions[g+5].BeginAddress+0x50;
        g_tooltip_plain[g].owner=functions[g+5].BeginAddress;g_tooltip_plain[g].serializer=image+0x800;
    }
    CHECK(MH_CreateHook(image+0x800,(void *)(uintptr_t)tooltip_serializer_hook,&blocked_trampoline)==MH_OK,
        "fixture reserves actual MinHook target to induce deterministic first-install failure");
    error=tooltip_enable_group(image+0x800,FALSE,0);
    CHECK(error!=ERROR_SUCCESS && !g_tooltip_active && g_tooltip_origin_count==0 &&
        !InterlockedCompareExchangePointer(&g_tooltip_origin_map,NULL,NULL),
        "failed first Plain Skill install leaves no published or active Skill origins");
    CHECK(MH_RemoveHook(image+0x800)==MH_OK,"fixture removes only its unenabled failure reservation");
    CHECK(tooltip_enable_group(image+0x800,FALSE,1)==ERROR_SUCCESS && g_tooltip_active && g_tooltip_origin_count==2,
        "later Buff group enables independently after failed Skill install");
    {
        BOOL layout;const WojdTooltipFieldSite *site;
        site=tooltip_origin_lookup(image+g_tooltip_plain[0].anchor,&layout);
        CHECK(!site && tooltip_origin_lookup(image+g_tooltip_plain[1].anchor,&layout) && !layout,
            "active Buff map excludes all failed Skill origins and preserves plain layout");
    }
    g_tooltip_resolver_ready=TRUE;g_tooltip_resolved.serializer=image+0x800;g_tooltip_view=view;g_tooltip_resolution_scope=1;
    g_tooltip_resolved.signature=image+0x800;g_tooltip_resolved.signature_matches=1;
    for(g=0;g<3;g++){g_tooltip_resolved.anchors[g]=anchors[g];g_tooltip_resolved.owners[g]=owners[g];g_tooltip_resolved.matches[g]=1;g_tooltip_hint_anchors[g]=anchors[g];}
    {
        const WojdNativeUobjectSiteContext *first=&WOJD_NATIVE_UOBJECT_SITE_CONTEXTS[0];
        BYTE *at=image+anchors[0]+((LONG)first->context_rva-(LONG)first->return_rva);
        *at^=1;error=tooltip_enable_group(image+0x800,TRUE,0);
        CHECK(error!=ERROR_SUCCESS && g_tooltip_active && g_tooltip_origin_count==2,
            "context changed after resolution cannot publish origins or disrupt existing Buff hook");
        *at^=1;
    }
    CHECK(tooltip_enable_group(image+0x800,TRUE,0)==ERROR_SUCCESS && g_tooltip_active && g_active && !g_tooltip_setup_complete,
        "both detours are enabled while generic setup is incomplete");
    CHECK(tooltip_serializer_valid(&view,image+0x800),"later group validates complete owned installed48 snapshot including actual far detour");
    g_decoder_reader=image+0x1000;g_decoder_return=image+0x1223;
    error=install_assignment(image+0x600);
    CHECK(error==ERROR_SUCCESS && g_active && (BYTE *)(uintptr_t)g_original_assign==trampoline &&
        g_tooltip_assign==g_original_assign && g_assign==g_original_assign,"later actual generic enable reuses exact same stable trampoline");
    CHECK(prepare_assignment(image+0x400)==ERROR_INVALID_DATA && (BYTE *)(uintptr_t)g_original_assign==trampoline,
        "different later generic target cannot replace published allocator");
    g_tooltip_pending=FALSE;g_tooltip_setup_complete=FALSE;g_tooltip_completion_reported=FALSE;
    tooltip_probe_once();
    CHECK(!g_tooltip_completion_reported && !g_tooltip_notice_queued && g_tooltip_active,
        "typed completion preserves early hook and waits for generic terminal state before final notice");
    g_tooltip_setup_complete=TRUE;tooltip_probe_once();
    CHECK(g_tooltip_completion_reported && !g_tooltip_notice_queued && g_tooltip_install_error==ERROR_SUCCESS,
        "all-warm completion needs no restart modal after generic finishes");
    g_tooltip_setup_complete=FALSE;g_tooltip_completion_reported=FALSE;g_tooltip_restart_required=TRUE;
    tooltip_report_failure("GENERIC_CACHE_WRITE",ERROR_ACCESS_DENIED);tooltip_probe_once();
    CHECK(g_tooltip_deferred_generic_error==ERROR_ACCESS_DENIED && !g_tooltip_notice_queued && !g_tooltip_completion_reported,
        "late generic cache failure cannot consume notice before generic setup is terminal");
    /* Interlock suppresses actual MessageBox thread in this private fixture. */
    InterlockedExchange(&g_tooltip_notice_queued,1);g_tooltip_setup_complete=TRUE;tooltip_probe_once();
    CHECK(g_tooltip_completion_reported && g_tooltip_install_error==ERROR_ACCESS_DENIED &&
        g_tooltip_restart_required && g_tooltip_active && !g_tooltip_notice.attempted,
        "late completion joins error and restart while preserving active hooks without displaying UI in fixture");
    CHECK(restore_data()==ERROR_SUCCESS && !g_active && !g_tooltip_active && !g_tooltip_translation_ready,
        "explicit fixture stop disables both hooks after no target calls");
    MH_Uninitialize();RtlDeleteFunctionTable(functions);VirtualFree(image,0,MEM_RELEASE);
    printf("RESULT checks=%d failures=%d no_target_code_executed=1\n",checks,failures);return failures?1:0;
}
