/* Fixed-provider HTTPS, worker only. UI cache lookup never performs I/O. */
#include "chat_google_text.h"
#include "chat_deepl_text.h"
#include "chat_llm_text.h"
enum {CG_CACHE=1024,CG_BYTES=64*1024*1024};
typedef struct CgCache {
    ULONGLONG expires,used;SIZE_T source_size,translation_size;
    unsigned provider;char model[97];char *payload;
} CgCache;
typedef struct CgNetwork {
    ULONGLONG cooldown;BOOL terminal,recoverable_outage;
    unsigned notice_seen,issue;ULONGLONG notice_at[8];
} CgNetwork;
static struct {
    CgCache *cache;unsigned capacity,last_profile;SIZE_T cache_bytes;
    ULONGLONG last_request;CgNetwork network[CQ_PROFILES];
    DWORD last_ms,http_status,last_error;
    LONG cache_hits,requests,decode_errors,placeholder_errors;
} g_cg;
static SRWLOCK g_cg_lock=SRWLOCK_INIT;
static const CqProfile *cg_profile(unsigned index) {
    return index<CQ_PROFILES?&g_cq.config.profiles[index]:NULL;
}
static void cg_notice_profile(unsigned profile,unsigned code) {
    ULONGLONG now=GetTickCount64();CgNetwork *net;
    if(profile>=CQ_PROFILES||code<1||code>7)return;net=&g_cg.network[profile];net->issue=code==6?0:code;
    if(!(net->notice_seen&(1u<<code))||now-net->notice_at[code]>=300000) {
        net->notice_seen|=1u<<code;net->notice_at[code]=now;
        InterlockedExchange(&g_cq.notice,(LONG)(((profile+1)<<8)|code));
    }
}
static void cg_notice(unsigned code){cg_notice_profile(0,code);}
#if defined(WOJD_CHAT_OBSERVER_TEST) && WOJD_CHAT_OBSERVER_TEST
typedef DWORD (*CgTestTransport)(HINTERNET,const char *,DWORD,unsigned char *,SIZE_T *,DWORD *);
static CgTestTransport g_cg_test_transport;
static const CqProfile *g_cg_test_profile;
#endif
static DWORD cg_http(HINTERNET connection,const CqProfile *profile,const char *form,DWORD bytes,unsigned char *response,SIZE_T *size,DWORD *status) {
    HINTERNET call;DWORD n=sizeof(*status),got,total=0,error=ERROR_SUCCESS;WCHAR path[256],model[98];unsigned i;
    DWORD disabled=WINHTTP_DISABLE_COOKIES|WINHTTP_DISABLE_REDIRECTS|WINHTTP_DISABLE_AUTHENTICATION;
    const CqCredential *credential=&g_cq.config.credentials[profile->provider];
    *size=0;*status=0;
#if defined(WOJD_CHAT_OBSERVER_TEST) && WOJD_CHAT_OBSERVER_TEST
    if(g_cg_test_transport){g_cg_test_profile=profile;return g_cg_test_transport(connection,form,bytes,response,size,status);}
#endif
    if(profile->provider==CQ_GEMINI) {
        for(i=0;profile->model[i];++i)model[i]=(WCHAR)profile->model[i];model[i]=0;
        if(_snwprintf_s(path,256,_TRUNCATE,L"/v1beta/models/%s:generateContent",model)<0)return ERROR_INVALID_DATA;
    }
    call=WinHttpOpenRequest(connection,L"POST",profile->provider==CQ_DEEPL?L"/v2/translate":profile->provider==CQ_GEMINI?path:
        profile->provider==CQ_DEEPSEEK?L"/chat/completions":L"/translate_a/single?client=gtx&sl=zh-CN&tl=vi&dt=t",
        NULL,WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,WINHTTP_FLAG_SECURE);
    if(!call)return GetLastError();
    if(!WinHttpSetOption(call,WINHTTP_OPTION_DISABLE_FEATURE,&disabled,sizeof(disabled))||
       (profile->provider!=CQ_GOOGLE&&!WinHttpAddRequestHeaders(call,credential->authorization,(DWORD)-1,WINHTTP_ADDREQ_FLAG_ADD|WINHTTP_ADDREQ_FLAG_REPLACE))||
       !WinHttpAddRequestHeaders(call,profile->provider==CQ_GEMINI||profile->provider==CQ_DEEPSEEK?
            L"Content-Type: application/json; charset=UTF-8\r\nAccept: application/json\r\n":L"Content-Type: application/x-www-form-urlencoded; charset=UTF-8\r\nAccept: application/json\r\n",
            (DWORD)-1,WINHTTP_ADDREQ_FLAG_ADD|WINHTTP_ADDREQ_FLAG_REPLACE)||
       !WinHttpSendRequest(call,WINHTTP_NO_ADDITIONAL_HEADERS,0,(void *)form,bytes,bytes,0)||
       !WinHttpReceiveResponse(call,NULL)||
       !WinHttpQueryHeaders(call,WINHTTP_QUERY_STATUS_CODE|WINHTTP_QUERY_FLAG_NUMBER,WINHTTP_HEADER_NAME_BY_INDEX,status,&n,WINHTTP_NO_HEADER_INDEX))error=GetLastError();
    if(!error&&*status!=200)error=ERROR_BAD_NET_RESP;
    while(!error) {
        if(total==GT_JSON){error=ERROR_INSUFFICIENT_BUFFER;break;}
        if(!WinHttpReadData(call,response+total,GT_JSON-total,&got)){error=GetLastError();break;}
        if(!got)break;total+=got;
    }
    WinHttpCloseHandle(call);if(!error)*size=total;return error;
}
static void cg_free_entry(CgCache *entry) {
    SIZE_T size=entry->source_size+entry->translation_size;
    if(entry->payload){SecureZeroMemory(entry->payload,size);HeapFree(GetProcessHeap(),0,entry->payload);g_cg.cache_bytes-=size;}
    SecureZeroMemory(entry,sizeof(*entry));
}
static void cg_close(void) {
    unsigned i;AcquireSRWLockExclusive(&g_cg_lock);
    if(g_cg.cache){for(i=0;i<g_cg.capacity;++i)cg_free_entry(&g_cg.cache[i]);HeapFree(GetProcessHeap(),0,g_cg.cache);}
    SecureZeroMemory(&g_cg,sizeof(g_cg));ReleaseSRWLockExclusive(&g_cg_lock);
}
static void cg_purge(ULONGLONG now) {
    unsigned i;AcquireSRWLockExclusive(&g_cg_lock);
    if(g_cg.cache)for(i=0;i<g_cg.capacity;++i)
        if(g_cg.cache[i].payload&&g_cg.cache[i].expires<=now)cg_free_entry(&g_cg.cache[i]);
    ReleaseSRWLockExclusive(&g_cg_lock);
}
static BOOL cg_lookup_profile(const CqProfile *profile,CwSpan source,char *out,SIZE_T *size,ULONGLONG now) {
    unsigned i;BOOL found=FALSE;ULONGLONG ttl=g_cq.config.cache_idle_ms?g_cq.config.cache_idle_ms:600000;
    if(!profile||!profile->provider||!TryAcquireSRWLockExclusive(&g_cg_lock))return FALSE;
    if(g_cg.cache)for(i=0;i<g_cg.capacity;++i) {
        CgCache *entry=&g_cg.cache[i];
        if(entry->payload&&entry->expires<=now)cg_free_entry(entry);
        if(entry->payload&&entry->provider==profile->provider&&!strcmp(entry->model,profile->model)&&
           entry->source_size==source.size&&source.size&&!memcmp(entry->payload,source.data,source.size)) {
            memcpy(out,entry->payload+entry->source_size,entry->translation_size);*size=entry->translation_size;
            entry->used=now;entry->expires=now+ttl;InterlockedIncrement(&g_cg.cache_hits);found=TRUE;break;
        }
    }
    ReleaseSRWLockExclusive(&g_cg_lock);return found;
}
static BOOL cg_lookup(CwSpan source,char *out,SIZE_T *size,ULONGLONG now) {
    return cg_lookup_profile(cg_profile(0),source,out,size,now);
}
static unsigned cg_oldest(void) {
    unsigned i,slot=g_cg.capacity;
    for(i=0;i<g_cg.capacity;++i)if(g_cg.cache[i].payload&&
        (slot==g_cg.capacity||g_cg.cache[i].used<g_cg.cache[slot].used))slot=i;
    return slot;
}
static void cg_store_profile(const CqProfile *profile,const CqRecord *row,ULONGLONG now) {
    unsigned i,slot;CgCache *entry;SIZE_T bytes=row->source_size+row->translation_size;
    ULONGLONG ttl=g_cq.config.cache_idle_ms?g_cq.config.cache_idle_ms:600000;
    if(!profile||!profile->provider||!row->source_size||!row->translation_size||
       row->source_size>CW_SOURCE||row->translation_size>CW_TRANSLATION||bytes>CG_BYTES)return;
    AcquireSRWLockExclusive(&g_cg_lock);
    if(!g_cg.cache) {
        unsigned capacity=g_cq.config.cache_entries?g_cq.config.cache_entries:CG_CACHE;
        if(capacity<16||capacity>8192)capacity=CG_CACHE;
        g_cg.cache=(CgCache *)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,sizeof(CgCache)*capacity);
        if(g_cg.cache)g_cg.capacity=capacity;
    }
    if(g_cg.cache) {
        for(i=0;i<g_cg.capacity;++i) {
            CgCache *old=&g_cg.cache[i];
            if(old->payload&&(old->expires<=now||(old->provider==profile->provider&&!strcmp(old->model,profile->model)&&
               old->source_size==row->source_size&&!memcmp(old->payload,row->source,row->source_size))))cg_free_entry(old);
        }
        while(g_cg.cache_bytes+bytes>CG_BYTES){slot=cg_oldest();if(slot==g_cg.capacity)break;cg_free_entry(&g_cg.cache[slot]);}
        for(slot=0;slot<g_cg.capacity&&g_cg.cache[slot].payload;++slot){}
        if(slot==g_cg.capacity)slot=cg_oldest();
        if(slot<g_cg.capacity) {
            entry=&g_cg.cache[slot];cg_free_entry(entry);
            entry->payload=(char *)HeapAlloc(GetProcessHeap(),0,bytes);
            if(entry->payload) {
                entry->provider=profile->provider;strcpy_s(entry->model,sizeof(entry->model),profile->model);
                entry->source_size=row->source_size;entry->translation_size=row->translation_size;
                memcpy(entry->payload,row->source,row->source_size);
                memcpy(entry->payload+row->source_size,row->translation,row->translation_size);
                entry->used=now;entry->expires=now+ttl;g_cg.cache_bytes+=bytes;
            }
        }
    }
    ReleaseSRWLockExclusive(&g_cg_lock);
}
static void cg_store(const CqRecord *row,ULONGLONG now){cg_store_profile(cg_profile(0),row,now);}
static DWORD cg_translate(HINTERNET connection,CqRecord *row,char *scratch,unsigned char *response) {
    GtText prepared;CwSpan span;ULONGLONG now=GetTickCount64(),start;SIZE_T bytes,size=0,n;DWORD error;
    const CqProfile *profile=cg_profile(row->profile);CgNetwork *net;const CqCredential *credential;unsigned kind;
    if(!profile||profile->provider<CQ_GOOGLE||profile->provider>=CQ_PROVIDERS)return ERROR_ACCESS_DENIED;
    kind=profile->provider;credential=&g_cq.config.credentials[kind];net=&g_cg.network[row->profile];g_cg.last_profile=row->profile;row->issue=0;
    span.data=row->source;span.size=row->source_size;
    if(cg_lookup_profile(profile,span,row->translation,&row->translation_size,now)){g_cg.last_error=0;return ERROR_SUCCESS;}
    if(kind!=CQ_GOOGLE&&credential->key_error){row->issue=1;cg_notice_profile(row->profile,1);g_cg.last_error=ERROR_ACCESS_DENIED;return ERROR_ACCESS_DENIED;}
    if(net->terminal){row->issue=net->issue;g_cg.last_error=ERROR_ACCESS_DENIED;return ERROR_ACCESS_DENIED;}
    if(now<net->cooldown){row->issue=net->issue;g_cg.last_error=ERROR_RETRY;return ERROR_RETRY;}
    if(!(kind==CQ_GEMINI||kind==CQ_DEEPSEEK?ll_prepare(span,&prepared):gt_prepare(span,&prepared))){row->issue=5;++g_cg.placeholder_errors;g_cg.last_error=ERROR_INVALID_DATA;return ERROR_INVALID_DATA;}
    span.data=prepared.text;span.size=prepared.size;
    if(!(kind==CQ_DEEPL?dt_form(span,scratch,CW_PACKET,&bytes):
        kind==CQ_GEMINI||kind==CQ_DEEPSEEK?ll_request(kind==CQ_GEMINI,profile->model,&prepared,scratch,CW_PACKET,&bytes):
        gt_form(span,scratch,CW_PACKET,&bytes))){row->issue=5;g_cg.last_error=ERROR_INSUFFICIENT_BUFFER;return ERROR_INSUFFICIENT_BUFFER;}
    now=GetTickCount64();if(g_cg.last_request&&now-g_cg.last_request<500)Sleep((DWORD)(500-(now-g_cg.last_request)));
    if(!g_cq.online||GetTickCount64()>=row->expires){row->issue=8;g_cg.last_error=ERROR_TIMEOUT;return ERROR_TIMEOUT;}
    start=GetTickCount64();g_cg.last_request=start;++g_cg.requests;
    error=cg_http(connection,profile,scratch,(DWORD)bytes,response,&size,&g_cg.http_status);
    g_cg.last_ms=(DWORD)(GetTickCount64()-start);
    if(error) {
        if(kind!=CQ_GOOGLE&&(g_cg.http_status==401||g_cg.http_status==403||g_cg.http_status==456||g_cg.http_status==402||g_cg.http_status==400||g_cg.http_status==404)) {
            net->terminal=TRUE;cg_notice_profile(row->profile,g_cg.http_status==456||g_cg.http_status==402?2u:g_cg.http_status==400||g_cg.http_status==404?7u:1u);
        } else if(g_cg.http_status==403||g_cg.http_status==429){net->cooldown=GetTickCount64()+60000;net->recoverable_outage=TRUE;cg_notice_profile(row->profile,3);}
        else if(g_cg.http_status>=500){net->cooldown=GetTickCount64()+10000;net->recoverable_outage=TRUE;cg_notice_profile(row->profile,4);}
        else {net->cooldown=GetTickCount64()+3000;net->recoverable_outage=TRUE;cg_notice_profile(row->profile,4);}
    } else {
        span.data=(const char *)response;span.size=size;
        if(!(kind==CQ_DEEPL?dt_response(span,scratch,CW_TRANSLATION,&n):
            kind==CQ_GEMINI||kind==CQ_DEEPSEEK?ll_response(kind==CQ_GEMINI,span,&prepared,scratch,CW_TRANSLATION,&n):
            gt_response(span,scratch,CW_TRANSLATION,&n))){error=ERROR_INVALID_DATA;++g_cg.decode_errors;}
        else {
            if(kind==CQ_DEEPL) {
                span.data=scratch;span.size=n;
                if(!dt_unxml(span,(char *)response,CW_TRANSLATION,&n)){error=ERROR_INVALID_DATA;++g_cg.decode_errors;}
                else memcpy(scratch,response,n);
            }
            span.data=scratch;span.size=n;
            if(!error&&!gt_restore_chat(&prepared,span,row->translation,CW_TRANSLATION,&row->translation_size)) {
                error=ERROR_INVALID_DATA;++g_cg.placeholder_errors;
            }
        }
    }
    if(error==ERROR_INVALID_DATA)cg_notice_profile(row->profile,5);
    if(!error&&net->recoverable_outage){net->recoverable_outage=FALSE;cg_notice_profile(row->profile,6);}
    row->issue=error?net->issue:0;g_cg.last_error=error;if(!error)cg_store_profile(profile,row,GetTickCount64());
    SecureZeroMemory(&prepared,sizeof(prepared));return error;
}
