/* Setup-only resumable generic discovery, shared with the actual fixture.
   A completed scan does not invalidate a still-pending current cache hint. */
#define DATA_DISCOVERY_PHASE_LIMIT 8u
#define DATA_DISCOVERY_WORK_LIMIT 32768u
typedef struct DataDiscoveryJob {
    ImageView view;ExecutableScan scan;DataResult result;
    BYTE copy[SCAN_STEP_BYTES];BOOL initialized,complete;
    DWORD status,phases,total_steps;ULONGLONG total_bytes,total_skipped;
} DataDiscoveryJob;
static BOOL data_discovery_terminal(const DataDiscoveryJob *job,BOOL cached,BOOL early_active,BOOL typed_pending) {
    if(!job->complete)return FALSE;
    if(job->status==ERROR_DUP_NAME)return TRUE;
    return !cached && !early_active && !typed_pending;
}
static BOOL reader_scan(const ImageView *v,const BYTE *live,const BYTE *copy,SIZE_T n,void *parameter) {
    DataResult *out=(DataResult *)parameter;SIZE_T i;
    if(g_discovery_pump)g_discovery_pump();
    for(i=0;i+sizeof(data_reader_bytes)<=n;i++) {
        const BYTE *reader=live+i,*assign,*raw;ULONG64 base=0;PRUNTIME_FUNCTION entry;MemoryProbe probe;
        if(copy[i]!=data_reader_bytes[0] || !masked_match(copy+i,data_reader_bytes,data_reader_mask,sizeof(data_reader_bytes)))continue;
        entry=RtlLookupFunctionEntry((DWORD64)(uintptr_t)reader,&base,NULL);
        if(g_game_host && (!entry || (BYTE *)(uintptr_t)base+entry->BeginAddress!=reader))continue;
        assign=relative_target(reader+0x21e);raw=relative_target(reader+0x10e);
        if(!assign || !raw || !assignment_signature_at_report(v,assign,&probe) ||
           !signature_at(v,raw,data_read_bytes_bytes,data_read_bytes_mask,sizeof(data_read_bytes_bytes)))continue;
        if(out->reader==(ULONGLONG)(uintptr_t)reader)continue;
        out->candidates++;out->reader=(ULONGLONG)(uintptr_t)reader;out->assign=(ULONGLONG)(uintptr_t)assign;out->raw_reader=(ULONGLONG)(uintptr_t)raw;
    }
    return TRUE;
}
static DWORD data_discovery_step(void *base,DataDiscoveryJob *job) {
    DWORD error,steps;ULONGLONG bytes,skipped;
    if(job->complete)return job->status;
    if(!job->initialized) {
        if(!image_view(base,&job->view))return ERROR_NOT_READY;
        job->initialized=TRUE;job->result.status=ERROR_IO_PENDING;
    }
    if(job->total_steps>=DATA_DISCOVERY_WORK_LIMIT)error=ERROR_TIMEOUT;
    else {
        steps=job->scan.steps;bytes=job->scan.bytes;skipped=job->scan.skipped_bytes;
        error=scan_executable_step(&job->view,&job->scan,job->copy,sizeof(job->copy),reader_scan,&job->result);
        job->total_steps+=job->scan.steps-steps;job->total_bytes+=job->scan.bytes-bytes;
        job->total_skipped+=job->scan.skipped_bytes-skipped;
    }
    if(error==ERROR_MORE_DATA)return ERROR_IO_PENDING;
    if(!error) {
        job->phases++;
        if(job->result.candidates!=1)error=job->result.candidates?ERROR_DUP_NAME:ERROR_NOT_FOUND;
        if(error==ERROR_NOT_FOUND && job->phases<DATA_DISCOVERY_PHASE_LIMIT) {
            ZeroMemory(&job->scan,sizeof(job->scan));ZeroMemory(&job->result,sizeof(job->result));
            job->result.status=ERROR_IO_PENDING;return ERROR_IO_PENDING;
        }
    }
    job->complete=TRUE;job->status=error;job->result.status=error;return error;
}
static DWORD resolve_data(void *base,DataResult *out) {
    DataDiscoveryJob *job=(DataDiscoveryJob *)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,sizeof(DataDiscoveryJob));
    DWORD error;if(!job){ZeroMemory(out,sizeof(*out));return out->status=ERROR_NOT_ENOUGH_MEMORY;}
    do {error=data_discovery_step(base,job);}while(error==ERROR_IO_PENDING);
    *out=job->result;out->status=error;HeapFree(GetProcessHeap(),0,job);return error;
}
