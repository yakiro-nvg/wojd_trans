static BOOL readable(DWORD protection) {
    DWORD basic=protection&255;
    if(protection&(PAGE_GUARD|PAGE_NOACCESS))return FALSE;
    return basic==PAGE_READONLY || basic==PAGE_READWRITE || basic==PAGE_WRITECOPY ||
        basic==PAGE_EXECUTE_READ || basic==PAGE_EXECUTE_READWRITE || basic==PAGE_EXECUTE_WRITECOPY;
}
enum { PROBE_NONE,PROBE_QUERY,PROBE_COMMIT,PROBE_PROTECT,PROBE_RPM,PROBE_HEADER,PROBE_RANGE,PROBE_SECTION,PROBE_MASK,PROBE_UNWIND };
/* failed_at is the last VirtualQuery address, not an inferred RPM fault offset. */
typedef struct MemoryProbe {
    DWORD kind,error,protect,state,type,query_attempted,query_succeeded,rpm_attempted;uintptr_t address,failed_at,region_begin,region_end;SIZE_T expected,got;
} MemoryProbe;
static BOOL read_exact_report(const void *address,void *out,SIZE_T size,MemoryProbe *probe) {
    SIZE_T got=0,checked=0;BOOL ok;DWORD error;
    if(probe){ZeroMemory(probe,sizeof(*probe));probe->address=(uintptr_t)address;probe->expected=size;}
    while(checked<size) {
        MEMORY_BASIC_INFORMATION region;uintptr_t start=(uintptr_t)address+checked,end;SIZE_T remaining;
        if(probe){probe->query_attempted=1;probe->query_succeeded=0;probe->region_begin=probe->region_end=0;probe->state=probe->protect=probe->type=0;}
        if(!VirtualQuery((const void *)start,&region,sizeof(region))) {
            error=GetLastError();if(probe){probe->kind=PROBE_QUERY;probe->error=error;probe->failed_at=start;}return FALSE;
        }
        end=(uintptr_t)region.BaseAddress+region.RegionSize;
        if(probe){probe->query_succeeded=1;probe->failed_at=start;probe->region_begin=(uintptr_t)region.BaseAddress;probe->region_end=end;probe->state=region.State;probe->protect=region.Protect;probe->type=region.Type;}
        if(region.State!=MEM_COMMIT){if(probe)probe->kind=PROBE_COMMIT;return FALSE;}
        if(!readable(region.Protect)){if(probe)probe->kind=PROBE_PROTECT;return FALSE;}
        if(end<=start){if(probe)probe->kind=PROBE_RANGE;return FALSE;}
        remaining=end-start;checked+=(remaining<size-checked)?remaining:size-checked;
    }
    if(probe)probe->rpm_attempted=1;
    ok=ReadProcessMemory(GetCurrentProcess(),address,out,size,&got);error=GetLastError();
    if(probe)probe->got=got;
    if(!ok || got!=size){if(probe){probe->kind=PROBE_RPM;probe->error=ok?ERROR_PARTIAL_COPY:error;}return FALSE;}
    return TRUE;
}
static BOOL read_exact(const void *address,void *out,SIZE_T size) {return read_exact_report(address,out,size,NULL);}
static BOOL in_image(const ImageView *view,const void *address,SIZE_T size) {
    uintptr_t start=(uintptr_t)view->base,point=(uintptr_t)address;
    return point>=start && point-start<=view->size && size<=view->size-(point-start);
}
static DWORD section_flags(const ImageView *view,const void *address,SIZE_T size) {
    unsigned i;
    if(!in_image(view,address,size))return 0;
    for(i=0;i<view->section_count;i++) {
        const IMAGE_SECTION_HEADER *section=&view->sections[i];
        SIZE_T offset=(SIZE_T)((const BYTE *)address-view->base);
        DWORD length=section->Misc.VirtualSize;
        if(section->SizeOfRawData>length)length=section->SizeOfRawData;
        if(offset>=section->VirtualAddress && offset-section->VirtualAddress<=length &&
           size<=length-(offset-section->VirtualAddress))return section->Characteristics;
    }
    return 0;
}
static BOOL executable(const ImageView *view,const void *address) {
    return (section_flags(view,address,1)&IMAGE_SCN_MEM_EXECUTE)!=0;
}
static BOOL writable_pointer(void *address) {
    MEMORY_BASIC_INFORMATION region;
    DWORD basic;
    if(((uintptr_t)address&7)!=0 || !VirtualQuery(address,&region,sizeof(region)) || region.State!=MEM_COMMIT || !readable(region.Protect))return FALSE;
    basic=region.Protect&255;
    return (basic==PAGE_READWRITE || basic==PAGE_WRITECOPY || basic==PAGE_EXECUTE_READWRITE || basic==PAGE_EXECUTE_WRITECOPY) &&
        (BYTE *)address+8<=(BYTE *)region.BaseAddress+region.RegionSize;
}
static BOOL image_probe_invalid(MemoryProbe *probe) {if(probe && !probe->kind)probe->kind=PROBE_HEADER;return FALSE;}
static BOOL image_view_report(void *base,ImageView *view,MemoryProbe *probe) {
    IMAGE_DOS_HEADER dos;
    IMAGE_NT_HEADERS64 nt;
    BYTE *table;
    if(!read_exact_report(base,&dos,sizeof(dos),probe) || dos.e_magic!=IMAGE_DOS_SIGNATURE || dos.e_lfanew<64 || dos.e_lfanew>2048)return image_probe_invalid(probe);
    if(!read_exact_report((BYTE *)base+dos.e_lfanew,&nt,sizeof(nt),probe) || nt.Signature!=IMAGE_NT_SIGNATURE ||
       nt.FileHeader.Machine!=IMAGE_FILE_MACHINE_AMD64 || nt.OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC ||
       nt.FileHeader.SizeOfOptionalHeader<sizeof(IMAGE_OPTIONAL_HEADER64) ||
       nt.FileHeader.NumberOfSections==0 || nt.FileHeader.NumberOfSections>96 ||
       nt.OptionalHeader.SizeOfImage==0 || nt.OptionalHeader.SizeOfImage>512u*1024u*1024u)return image_probe_invalid(probe);
    table=(BYTE *)base+dos.e_lfanew+24+nt.FileHeader.SizeOfOptionalHeader;
    if((SIZE_T)(table-(BYTE *)base)+nt.FileHeader.NumberOfSections*sizeof(IMAGE_SECTION_HEADER)>4096)return image_probe_invalid(probe);
    view->base=(BYTE *)base;view->size=nt.OptionalHeader.SizeOfImage;view->section_count=nt.FileHeader.NumberOfSections;
    return read_exact_report(table,view->sections,view->section_count*sizeof(IMAGE_SECTION_HEADER),probe);
}
static BOOL image_view(void *base,ImageView *view) {return image_view_report(base,view,NULL);}
static BOOL masked_match(const BYTE *data,const BYTE *expected,const BYTE *mask,SIZE_T size) {
    SIZE_T i;
    for(i=0;i<size;i++)if((data[i]&mask[i])!=(expected[i]&mask[i]))return FALSE;
    return TRUE;
}
static const BYTE *relative_target_report(const BYTE *instruction,MemoryProbe *probe) {
    LONG displacement;
    if(!read_exact_report(instruction+1,&displacement,sizeof(displacement),probe))return NULL;
    return instruction+5+displacement;
}
static const BYTE *relative_target(const BYTE *instruction) {return relative_target_report(instruction,NULL);}

typedef BOOL (*ScanCallback)(const ImageView *,const BYTE *,const BYTE *,SIZE_T,void *);
#include "native_data_scan.inc"
static DWORD scan_executable(const ImageView *view,ScanCallback callback,void *context) {
    ExecutableScan cursor;DWORD error;BYTE *copy=(BYTE *)HeapAlloc(GetProcessHeap(),0,SCAN_STEP_BYTES);
    if(!copy)return ERROR_NOT_ENOUGH_MEMORY;
    ZeroMemory(&cursor,sizeof(cursor));
    do {error=scan_executable_step(view,&cursor,copy,SCAN_STEP_BYTES,callback,context);}while(error==ERROR_MORE_DATA);
    HeapFree(GetProcessHeap(),0,copy);return error;
}
