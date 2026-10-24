#ifndef WOJD_CHAT_CLOUD_TYPES_H
#define WOJD_CHAT_CLOUD_TYPES_H
#include "chat_native_wire.h"
enum {CQ_SLOTS=32,CQ_FREE=0,CQ_NEW=1,CQ_WAIT=2,CQ_DONE=3,CQ_RICH=4,
      CQ_LOCAL=1,CQ_GOOGLE=2,CQ_DEEPL=3,CQ_DEEPSEEK=4,CQ_GEMINI=5,CQ_PROVIDERS=6,CQ_PROFILES=23};
typedef struct CqProfile {unsigned provider;char model[97];} CqProfile;
typedef struct CqCredential {WCHAR authorization[320];DWORD key_error;BOOL deepl_free;} CqCredential;
typedef struct CqConfiguration {
    CqProfile profiles[CQ_PROFILES];CqCredential credentials[CQ_PROVIDERS];
    unsigned cache_entries;ULONGLONG cache_idle_ms;
} CqConfiguration;
typedef struct CqRecord {
    unsigned state,status,profile,issue;ULONGLONG expires,serial;
    SIZE_T id_size,source_size,translation_size;
    char id[21],source[CW_SOURCE],translation[CW_TRANSLATION];
} CqRecord;
typedef struct CqChannel {unsigned id;const WCHAR *key;} CqChannel;
/* Reviewed current ChatData Enum mapping, not color IDs. System/recruitment
   channels are intentionally absent. Unknown channels never enter the queue. */
static const CqChannel cq_channels[]={
    {0,L"local"},{1,L"world"},{2,L"squad"},{3,L"team"},{4,L"gang"},{5,L"sect"},
    {6,L"battlefield"},{7,L"friend"},{11,L"broadcast"},{12,L"broadcast_anonymous"},
    {14,L"region"},{15,L"all_broadcast"},{16,L"all_broadcast_anonymous"},
    {17,L"force"},{20,L"arena"},{21,L"observe"}
};
static int cq_channel_profile(CwSpan text,unsigned *profile) {
    size_t i;unsigned value=0,j;
    if(!text.size||text.size>2)return 0;
    for(i=0;i<text.size;++i){if(text.data[i]<'0'||text.data[i]>'9')return 0;value=value*10+(unsigned)(text.data[i]-'0');}
    for(j=0;j<sizeof(cq_channels)/sizeof(cq_channels[0]);++j)if(cq_channels[j].id==value){*profile=value+1;return 1;}
    return 0;
}
#endif
