/* Identify the already-executing decoder caller without waiting for its entire body. */
static DWORD verify_assignment_origin(void *base,const BYTE *reader,const BYTE *assign) {
    ImageView view;BYTE prologue[26],window[37];ULONG64 owner_base=0;PRUNTIME_FUNCTION entry;
    if(!image_view(base,&view) || !in_image(&view,reader,sizeof(data_reader_bytes)) ||
       !in_image(&view,assign,sizeof(data_assign_bytes)) || !executable(&view,reader) || !executable(&view,assign))return ERROR_INVALID_DATA;
    if(!read_exact(reader,prologue,sizeof(prologue)) || !read_exact(reader+0x20b,window,sizeof(window)))return ERROR_NOT_READY;
    if(!masked_match(prologue,data_reader_bytes,data_reader_mask,sizeof(prologue)) ||
       !masked_match(window,data_reader_bytes+0x20b,data_reader_mask+0x20b,sizeof(window)) ||
       window[0x21e-0x20b]!=0xe8 || relative_target(reader+0x21e)!=assign)return ERROR_INVALID_DATA;
    entry=RtlLookupFunctionEntry((DWORD64)(uintptr_t)(reader+0x223),&owner_base,NULL);
    if(g_game_host && (!entry || (BYTE *)(uintptr_t)owner_base+entry->BeginAddress!=reader ||
       (BYTE *)(uintptr_t)owner_base+entry->EndAddress!=reader+sizeof(data_reader_bytes)))return ERROR_NOT_READY;
    return ERROR_SUCCESS;
}
