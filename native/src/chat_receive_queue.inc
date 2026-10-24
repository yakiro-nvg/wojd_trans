/* Opt-in incoming translator. Lua callbacks copy bounded strings and
   never perform I/O. The worker owns synchronous HTTPS/loopback HTTP; it never calls
   Lua/game/UI APIs. No message content or token is written to our logs. */
#include <winhttp.h>
#include <bcrypt.h>
#include "chat_cloud_types.h"
static struct {
    SRWLOCK lock;LcrApis api;CqRecord records[CQ_SLOTS];
    char session[33];INTERNET_PORT port;CqConfiguration config;
    void *owner_state;DWORD owner_thread;
    volatile LONG online,modules,received,completed,rendered,dropped,network_errors,owner_rejections;
    volatile LONG stages[7],timer_method,notice,notices_rendered;
    volatile LONG scroll_follow,scroll_settled,scroll_cancelled,scroll_unsettled,scroll_prepass;
    LcmLayout layout[3];
    ULONGLONG serial;HANDLE worker;
} g_cq;
#include "chat_google_provider.inc"
#include "chat_deepl_key.inc"
#include "player_names.h"
static BOOL cq_configuration(WCHAR *path) {
    DWORD attributes;
    if(_snwprintf_s(path,1024,_TRUNCATE,L"%s\\chat.ini",g_root_path)<0)return FALSE;
    attributes=GetFileAttributesW(path);
    if(attributes==INVALID_FILE_ATTRIBUTES) {
#if defined(WOJD_CHAT_OBSERVER_TEST) && WOJD_CHAT_OBSERVER_TEST
        if(GetLastError()!=ERROR_FILE_NOT_FOUND)return FALSE;
        if(_snwprintf_s(path,1024,_TRUNCATE,L"%s\\chat-local.ini",g_root_path)<0)return FALSE;
        attributes=GetFileAttributesW(path);
#else
        return FALSE;
#endif
    }
    return attributes!=INVALID_FILE_ATTRIBUTES&&!(attributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT));
}
static int cq_equal(CwSpan span,const char *text,SIZE_T size) {
    return span.size==size && !memcmp(span.data,text,size);
}
static int cq_string(void *L,int index,CwSpan *value,SIZE_T minimum,SIZE_T maximum) {
    if(g_cq.api.bind.type(L,index)!=4)return 0;
    value->data=g_cq.api.tostring(L,index,&value->size);
    return value->data && value->size>=minimum && value->size<=maximum;
}
static int cq_is(CwSpan value,const char *word) {return cq_equal(value,word,strlen(word));}
static BOOL cq_has_han(CwSpan text) {
    SIZE_T i=0,j;unsigned value,lead,count;
    while(i<text.size) {
        lead=(unsigned char)text.data[i++];if(lead<128)continue;
        if(lead<0xe0){value=lead&31u;count=1;}
        else if(lead<0xf0){value=lead&15u;count=2;}
        else {value=lead&7u;count=3;}
        for(j=0;j<count;++j)value=(value<<6)|((unsigned char)text.data[i++]&63u);
        if((value>=0x3400 && value<=0x9fff) || (value>=0xf900 && value<=0xfaff) ||
           (value>=0x20000 && value<=0x323af))return TRUE;
    }
    return FALSE;
}
static int cq_return(void *L,const char *text) {g_cq.api.pushstring(L,text,strlen(text));return 1;}
static int cq_callback(void *L) {
    CwSpan op,id,source;int count=g_cq.api.bind.gettop(L);unsigned i;BOOL accepted=FALSE;
    if(count<1 || count>4 || !cq_string(L,1,&op,1,16))return 0;
    if(cq_is(op,"session") && count==1)return cq_return(L,g_cq.session);
    if(cq_is(op,"layout") && count==2) {
        CwSpan module;unsigned kind=0;char index[16];
        if(cq_string(L,2,&module,1,8)){if(cq_is(module,"item"))kind=1;else if(cq_is(module,"scroll"))kind=2;}
        if(!kind || !g_cq.layout[kind].methods)return 0;
        _snprintf_s(index,sizeof(index),_TRUNCATE,"%u",g_cq.layout[kind].methods);cq_return(L,index);
        _snprintf_s(index,sizeof(index),_TRUNCATE,"%u",g_cq.layout[kind].resend);cq_return(L,index);return 2;
    }
    if(cq_is(op,"readonly") && count==3) {
        if(!g_cq.layout[2].upvalue || g_cq.layout[2].upvalue>255 ||
           g_cq.api.bind.type(L,2)!=6 || g_cq.api.bind.type(L,3)!=6)return 0;
        /* The certified NewScrollBox prototype captures this exact stock
           resend closure. Replace its closed cell, covering generated rows
           without writing the game's global SetObjectScript function. */
        if(g_cq.api.bind.setupvalue(L,2,(int)g_cq.layout[2].upvalue))return cq_return(L,"bound");
        return 0;
    }
    if(cq_is(op,"clock") && count==1) {
        char clock[32];_snprintf_s(clock,sizeof(clock),_TRUNCATE,"%llu",GetTickCount64());return cq_return(L,clock);
    }
    if(cq_is(op,"namereading")&&count==2) {
        CwSpan name;char converted[8192];SIZE_T size=0;
        if(cq_string(L,2,&name,1,256)&&pn_reading(name,converted,sizeof(converted),&size)) {
            g_cq.api.pushstring(L,converted,size);SecureZeroMemory(converted,sizeof(converted));return 1;
        }
        SecureZeroMemory(converted,sizeof(converted));return 0;
    }
    if(cq_is(op,"namedlinks")&&count==2) {
        CwSpan text;char converted[CW_TRANSLATION];SIZE_T size=0;
        if(cq_string(L,2,&text,1,CW_TRANSLATION)&&pn_links(text,converted,sizeof(converted),&size)) {
            g_cq.api.pushstring(L,converted,size);SecureZeroMemory(converted,sizeof(converted));return 1;
        }
        SecureZeroMemory(converted,sizeof(converted));return 0;
    }
    if(cq_is(op,"stage") && count==2) {
        static const char *names[]={"items_bound","scroll_bound","timer_created","timer_tick","item_built","view_added","row_guarded"};
        CwSpan stage;
        if(cq_string(L,2,&stage,1,20))for(i=0;i<7;++i)if(cq_is(stage,names[i])){InterlockedIncrement(&g_cq.stages[i]);break;}
        return 0;
    }
    if(cq_is(op,"method") && count==3) {
        CwSpan name,kind;
        if(cq_string(L,2,&name,1,10) && cq_is(name,"timer") && cq_string(L,3,&kind,1,10)) {
            if(cq_is(kind,"function"))InterlockedExchange(&g_cq.timer_method,1);
            else if(cq_is(kind,"userdata"))InterlockedExchange(&g_cq.timer_method,2);
            else if(cq_is(kind,"table"))InterlockedExchange(&g_cq.timer_method,3);
            else InterlockedExchange(&g_cq.timer_method,4);
        }
        return 0;
    }
    if(cq_is(op,"module") && count==3) {
        CwSpan module,marker;
        if(cq_string(L,2,&module,1,8) && cq_string(L,3,&marker,1,64) && cq_is(marker,"WOJD_CHAT_CALLBACK_V1:")) {
            if(cq_is(module,"item"))InterlockedOr(&g_cq.modules,1);
            if(cq_is(module,"scroll"))InterlockedOr(&g_cq.modules,2);
            if(g_cq.modules==3)InterlockedExchange(&g_lco_executed,1);
        }
        return 0;
    }
    if(!g_cq.online)return 0;
    if(cq_is(op,"ui") && count==1) {
        if(!TryAcquireSRWLockExclusive(&g_cq.lock))return 0;
        if(!g_cq.owner_state){g_cq.owner_state=L;g_cq.owner_thread=GetCurrentThreadId();}
        accepted=g_cq.owner_thread==GetCurrentThreadId();
        ReleaseSRWLockExclusive(&g_cq.lock);
        return accepted?cq_return(L,"owner"):0;
    }
    /* A Lua coroutine has its own lua_State pointer while sharing the same
       module tables. Ownership follows the actual UI thread, not that pointer.
       Only our two certified private module closures receive this callback. */
    if(g_cq.owner_thread!=GetCurrentThreadId()){InterlockedIncrement(&g_cq.owner_rejections);return 0;}
    if(cq_is(op,"notice")&&count==1) {
        static const char *codes[]={"","auth","quota","limited","offline","invalid","resumed","configuration"};
        LONG packed=InterlockedExchange(&g_cq.notice,0);unsigned code=(unsigned)packed&255u,profile=((unsigned)packed>>8)-1,kind;
        if(code<1||code>7||profile>=CQ_PROFILES)return 0;kind=g_cq.config.profiles[profile].provider;
        cq_return(L,codes[code]);cq_return(L,kind==CQ_DEEPL?"DeepL":kind==CQ_GEMINI?"Gemini":kind==CQ_DEEPSEEK?"DeepSeek":"Google");return 2;
    }
    if(cq_is(op,"notice_rendered")&&count==1){InterlockedIncrement(&g_cq.notices_rendered);return 0;}
    if(cq_is(op,"scroll")&&count==2) {
        CwSpan event;if(!cq_string(L,2,&event,1,12))return 0;
        if(cq_is(event,"follow"))InterlockedIncrement(&g_cq.scroll_follow);
        else if(cq_is(event,"settled"))InterlockedIncrement(&g_cq.scroll_settled);
        else if(cq_is(event,"cancelled"))InterlockedIncrement(&g_cq.scroll_cancelled);
        else if(cq_is(event,"unsettled"))InterlockedIncrement(&g_cq.scroll_unsettled);
        else if(cq_is(event,"prepass"))InterlockedIncrement(&g_cq.scroll_prepass);
        return 0;
    }
    if(cq_is(op,"cached")&&count==3) {
        char copy[CW_TRANSLATION];SIZE_T size=0;BOOL found;CwSpan channel;unsigned profile;
        if(!cq_string(L,2,&source,1,CW_SOURCE)||!cq_string(L,3,&channel,1,2)||!cq_channel_profile(channel,&profile)||
            g_cq.config.profiles[profile].provider<CQ_GOOGLE)return 0;
        found=cg_lookup_profile(&g_cq.config.profiles[profile],source,copy,&size,GetTickCount64());
        if(found){cq_return(L,"translated_rich");g_cq.api.pushstring(L,copy,size);}
        SecureZeroMemory(copy,sizeof(copy));return found?2:0;
    }
    if(cq_is(op,"enqueue") && count==4) {
        CwPacket check;CwSpan channel;unsigned profile;
        if(!cq_string(L,2,&id,1,20) || !cq_string(L,3,&source,1,CW_SOURCE)||!cq_string(L,4,&channel,1,2)||
           !cq_channel_profile(channel,&profile)||!g_cq.config.profiles[profile].provider)return 0;
        ZeroMemory(&check,sizeof(check));check.code=1;check.session.data=g_cq.session;check.session.size=32;check.id=id;check.source=source;
        if(!cw_valid(&check,0) || !cq_has_han(source))return 0;
        if(TryAcquireSRWLockExclusive(&g_cq.lock)) {
            BOOL duplicate=FALSE;
            for(i=0;i<CQ_SLOTS;++i)if(g_cq.records[i].state && g_cq.records[i].id_size==id.size &&
                !memcmp(g_cq.records[i].id,id.data,id.size)){duplicate=TRUE;break;}
            if(!duplicate)for(i=0;i<CQ_SLOTS;++i)if(!g_cq.records[i].state) {
                CqRecord *row=&g_cq.records[i];row->profile=profile;row->id_size=id.size;row->source_size=source.size;
                memcpy(row->id,id.data,id.size);row->id[id.size]=0;memcpy(row->source,source.data,source.size);
                row->serial=++g_cq.serial;row->expires=GetTickCount64()+30000;row->state=CQ_NEW;
                accepted=TRUE;break;
            }
            ReleaseSRWLockExclusive(&g_cq.lock);
        }
        if(accepted){
            char deadline[32];_snprintf_s(deadline,sizeof(deadline),_TRUNCATE,"%llu",GetTickCount64()+30000);
            InterlockedIncrement(&g_cq.received);cq_return(L,"queued");cq_return(L,deadline);return 2;
        }
        InterlockedIncrement(&g_cq.dropped);cq_return(L,"rejected");cq_return(L,"busy");return 2;
    }
    if(cq_is(op,"rendered") && count==1){InterlockedIncrement(&g_cq.rendered);return 0;}
    if(cq_is(op,"poll") && count==1) {
        /* Stack-owned copies survive a Lua allocation error or reentrant GC.
           No host lock, heap allocation or inflight flag spans a Lua push. */
        CqRecord copy={0};unsigned selected=CQ_SLOTS;
        if(!TryAcquireSRWLockExclusive(&g_cq.lock))return 0;
        for(i=0;i<CQ_SLOTS;++i)if(g_cq.records[i].state==CQ_DONE){copy=g_cq.records[i];selected=i;break;}
        ReleaseSRWLockExclusive(&g_cq.lock);if(selected==CQ_SLOTS)return 0;
        g_cq.api.pushstring(L,copy.id,copy.id_size);g_cq.api.pushstring(L,copy.source,copy.source_size);
        if(copy.status==CQ_RICH)g_cq.api.pushstring(L,"translated_rich",15);
        else if(copy.status==2)g_cq.api.pushstring(L,"translated",10);else g_cq.api.pushstring(L,"error",5);
        if(copy.status==CQ_RICH||copy.status==2)g_cq.api.pushstring(L,copy.translation,copy.translation_size);
        else {
            static const char *issues[]={"failed","auth","quota","limited","offline","invalid","failed","configuration","expired"};
            const char *issue=copy.issue<9?issues[copy.issue]:issues[0];g_cq.api.pushstring(L,issue,strlen(issue));
        }
        {unsigned provider=g_cq.config.profiles[copy.profile].provider;const char *name=provider==CQ_GEMINI?"Gemini":provider==CQ_DEEPSEEK?"DeepSeek":provider==CQ_DEEPL?"DeepL":"Google";
         g_cq.api.pushstring(L,name,strlen(name));}
        if(TryAcquireSRWLockExclusive(&g_cq.lock)) {
            if(g_cq.records[selected].state==CQ_DONE && g_cq.records[selected].serial==copy.serial)
                SecureZeroMemory(&g_cq.records[selected],sizeof(CqRecord));
            ReleaseSRWLockExclusive(&g_cq.lock);
        }
        SecureZeroMemory(&copy,sizeof(copy));return 5;
    }
    return 0;
}
static DWORD cq_http(HINTERNET connection,const CqRecord *row,unsigned char *request,unsigned char *response,SIZE_T *response_size) {
    CwPacket packet;SIZE_T bytes;HINTERNET call;DWORD status=0,n=sizeof(status),got,total=0,error=ERROR_SUCCESS;
    DWORD disabled=WINHTTP_DISABLE_COOKIES|WINHTTP_DISABLE_REDIRECTS|WINHTTP_DISABLE_AUTHENTICATION;
    ZeroMemory(&packet,sizeof(packet));packet.code=row->state==CQ_NEW?1u:2u;
    packet.session.data=g_cq.session;packet.session.size=32;packet.id.data=row->id;packet.id.size=row->id_size;
    packet.source.data=row->source;packet.source.size=row->source_size;
    if(!cw_encode(&packet,0,request,CW_PACKET,&bytes))return ERROR_INVALID_DATA;
    call=WinHttpOpenRequest(connection,L"POST",L"/v1/exchange",NULL,WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,0);
    if(!call)return GetLastError();
    if(!WinHttpSetOption(call,WINHTTP_OPTION_DISABLE_FEATURE,&disabled,sizeof(disabled)) ||
       !WinHttpAddRequestHeaders(call,g_cq.config.credentials[CQ_LOCAL].authorization,(DWORD)-1,WINHTTP_ADDREQ_FLAG_ADD|WINHTTP_ADDREQ_FLAG_REPLACE) ||
       !WinHttpAddRequestHeaders(call,L"Content-Type: application/octet-stream\r\n",(DWORD)-1,WINHTTP_ADDREQ_FLAG_ADD|WINHTTP_ADDREQ_FLAG_REPLACE) ||
       !WinHttpSendRequest(call,WINHTTP_NO_ADDITIONAL_HEADERS,0,request,(DWORD)bytes,(DWORD)bytes,0) ||
       !WinHttpReceiveResponse(call,NULL) ||
       !WinHttpQueryHeaders(call,WINHTTP_QUERY_STATUS_CODE|WINHTTP_QUERY_FLAG_NUMBER,WINHTTP_HEADER_NAME_BY_INDEX,&status,&n,WINHTTP_NO_HEADER_INDEX))error=GetLastError();
    if(!error && status!=200)error=ERROR_BAD_NET_RESP;
    while(!error) {
        if(total==CW_PACKET){error=ERROR_INSUFFICIENT_BUFFER;break;}
        if(!WinHttpReadData(call,response+total,CW_PACKET-total,&got)){error=GetLastError();break;}
        if(!got)break;total+=got;
    }
    WinHttpCloseHandle(call);if(!error)*response_size=total;return error;
}
static DWORD WINAPI cq_worker(void *unused) {
    HINTERNET session,connection,connections[CQ_PROVIDERS]={0};CqRecord copy={0};unsigned i,cursor=0,selected,kind;ULONGLONG last_log=GetTickCount64();
    unsigned char *request,*response;SIZE_T response_size;CwPacket reply;DWORD error;
    (void)unused;
    request=(unsigned char *)HeapAlloc(GetProcessHeap(),0,CW_PACKET*2u);
    if(!request){InterlockedExchange(&g_cq.online,0);return ERROR_NOT_ENOUGH_MEMORY;}response=request+CW_PACKET;
    session=WinHttpOpen(L"WOJD incoming chat/1",WINHTTP_ACCESS_TYPE_NO_PROXY,WINHTTP_NO_PROXY_NAME,WINHTTP_NO_PROXY_BYPASS,0);
    if(!session){error=GetLastError();InterlockedExchange(&g_cq.online,0);HeapFree(GetProcessHeap(),0,request);return error;}
    if(!WinHttpSetTimeouts(session,3000,3000,5000,5000)) {
        error=GetLastError();InterlockedExchange(&g_cq.online,0);WinHttpCloseHandle(session);HeapFree(GetProcessHeap(),0,request);return error;
    }
    while(g_cq.online) {
        selected=CQ_SLOTS;AcquireSRWLockExclusive(&g_cq.lock);
        for(i=0;i<CQ_SLOTS;++i) {
            unsigned index=(cursor+i)%CQ_SLOTS;CqRecord *row=&g_cq.records[index];
            if(row->state && row->expires+30000<=GetTickCount64())SecureZeroMemory(row,sizeof(*row));
            else if(row->state && row->state!=CQ_DONE && row->expires<=GetTickCount64()) {
                row->state=CQ_DONE;row->status=3;row->issue=8;
            }
            if((row->state==CQ_NEW || row->state==CQ_WAIT) && selected==CQ_SLOTS){copy=*row;selected=index;}
        }
        ReleaseSRWLockExclusive(&g_cq.lock);
        if(selected!=CQ_SLOTS) {
            cursor=(selected+1)%CQ_SLOTS;response_size=0;ZeroMemory(&reply,sizeof(reply));
            kind=copy.profile<CQ_PROFILES?g_cq.config.profiles[copy.profile].provider:0;
            error=ERROR_SUCCESS;connection=NULL;
            if(!kind||kind>=CQ_PROVIDERS)error=ERROR_INVALID_DATA;
            else {
                if(!connections[kind])connections[kind]=WinHttpConnect(session,kind==CQ_GOOGLE?L"translate.googleapis.com":
                    kind==CQ_DEEPL?(g_cq.config.credentials[kind].deepl_free?L"api-free.deepl.com":L"api.deepl.com"):
                    kind==CQ_GEMINI?L"generativelanguage.googleapis.com":kind==CQ_DEEPSEEK?L"api.deepseek.com":L"127.0.0.1",
                    kind==CQ_LOCAL?g_cq.port:INTERNET_DEFAULT_HTTPS_PORT,0);
                connection=connections[kind];if(!connection){error=GetLastError();copy.issue=4;cg_notice_profile(copy.profile,4);}
            }
            if(!error&&kind!=CQ_LOCAL) {
                error=cg_translate(connection,&copy,(char *)request,response);
                if(!error){reply.code=CQ_RICH;reply.translation.data=copy.translation;reply.translation.size=copy.translation_size;}
            } else if(!error)error=cq_http(connection,&copy,request,response,&response_size);
            if(kind==CQ_LOCAL && !error && (!cw_decode(response,response_size,1,&reply) ||
               !cq_equal(reply.session,g_cq.session,32) || !cq_equal(reply.id,copy.id,copy.id_size) ||
               !cq_equal(reply.source,copy.source,copy.source_size)))error=ERROR_INVALID_DATA;
            AcquireSRWLockExclusive(&g_cq.lock);
            if(g_cq.records[selected].serial==copy.serial && g_cq.records[selected].state!=CQ_FREE) {
                CqRecord *row=&g_cq.records[selected];
                if(row->expires<=GetTickCount64()){row->status=3;row->state=CQ_DONE;row->issue=8;}
                else if(!error) {
                    if(reply.code==1)row->state=CQ_WAIT;
                    else {
                        row->status=reply.code;row->state=CQ_DONE;row->translation_size=reply.translation.size;
                        if(reply.translation.size)memcpy(row->translation,reply.translation.data,reply.translation.size);
                        InterlockedIncrement(&g_cq.completed);
                    }
                } else {row->status=3;row->state=CQ_DONE;row->issue=copy.issue;InterlockedIncrement(&g_cq.network_errors);}
            }
            ReleaseSRWLockExclusive(&g_cq.lock);SecureZeroMemory(&copy,sizeof(copy));
            SecureZeroMemory(request,CW_PACKET*2u);
        }
        if(GetTickCount64()-last_log>=10000) {
            cg_purge(GetTickCount64());
            last_log=GetTickCount64();logf_n4("CHAT_RECEIVE_STATUS","modules=%ld owner=%u received=%ld completed=%ld rendered=%ld dropped=%ld network_errors=%ld owner_rejections=%ld",
                g_cq.modules,g_cq.owner_thread!=0,g_cq.received,g_cq.completed,g_cq.rendered,g_cq.dropped,g_cq.network_errors,g_cq.owner_rejections);
            logf_n4("CHAT_RECEIVE_BINDING","items=%ld scroll=%ld timer=%ld ticks=%ld builds=%ld adds=%ld readonly=%ld timer_method=%ld",
                g_cq.stages[0],g_cq.stages[1],g_cq.stages[2],g_cq.stages[3],g_cq.stages[4],g_cq.stages[5],g_cq.stages[6],g_cq.timer_method);
            logf_n4("CHAT_RECEIVE_SCROLL","follow=%ld settled=%ld cancelled=%ld unsettled=%ld prepass=%ld",
                g_cq.scroll_follow,g_cq.scroll_settled,g_cq.scroll_cancelled,g_cq.scroll_unsettled,g_cq.scroll_prepass);
            kind=g_cq.config.profiles[g_cg.last_profile].provider;
            if(kind!=CQ_LOCAL)logf_n4(kind==CQ_DEEPL?"CHAT_DEEPL_STATUS":kind==CQ_GEMINI?"CHAT_GEMINI_STATUS":kind==CQ_DEEPSEEK?"CHAT_DEEPSEEK_STATUS":"CHAT_GOOGLE_STATUS","requests=%ld cache_hits=%ld last_ms=%lu http_status=%lu error=%lu decode_errors=%ld placeholder_errors=%ld cooldown=%u notices=%ld profile=%u cache_capacity=%u cache_bytes=%llu",
                g_cg.requests,g_cg.cache_hits,g_cg.last_ms,g_cg.http_status,g_cg.last_error,g_cg.decode_errors,g_cg.placeholder_errors,GetTickCount64()<g_cg.network[g_cg.last_profile].cooldown,g_cq.notices_rendered,g_cg.last_profile,g_cg.capacity,(unsigned long long)g_cg.cache_bytes);
        }
        Sleep(selected==CQ_SLOTS?50:10);
    }
    for(i=0;i<CQ_PROVIDERS;++i)if(connections[i])WinHttpCloseHandle(connections[i]);
    WinHttpCloseHandle(session);cg_close();SecureZeroMemory(g_cq.config.credentials,sizeof(g_cq.config.credentials));
    SecureZeroMemory(request,CW_PACKET*2u);HeapFree(GetProcessHeap(),0,request);
    AcquireSRWLockExclusive(&g_cq.lock);SecureZeroMemory(g_cq.records,sizeof(g_cq.records));ReleaseSRWLockExclusive(&g_cq.lock);
    return ERROR_SUCCESS;
}
static DWORD cq_read_profile(const WCHAR *path,const WCHAR *section,const CqProfile *fallback,CqProfile *profile) {
    WCHAR provider[32],model[98];DWORD n;unsigned i;
    GetPrivateProfileStringW(section,L"provider",fallback?L"inherit":L"none",provider,32,path);
    ZeroMemory(profile,sizeof(*profile));
    if(fallback&&!wcscmp(provider,L"inherit")){*profile=*fallback;return 0;}
    if(!wcscmp(provider,L"none")||!wcscmp(provider,L"off"))return 0;
    if(!wcscmp(provider,L"google-web"))profile->provider=CQ_GOOGLE;
    else if(!wcscmp(provider,L"deepl"))profile->provider=CQ_DEEPL;
    else if(!wcscmp(provider,L"deepseek"))profile->provider=CQ_DEEPSEEK;
    else if(!wcscmp(provider,L"gemini"))profile->provider=CQ_GEMINI;
#if defined(WOJD_CHAT_OBSERVER_TEST) && WOJD_CHAT_OBSERVER_TEST
    else if(!wcscmp(provider,L"local-bridge"))profile->provider=CQ_LOCAL;
#endif
    else return ERROR_INVALID_DATA;
    if(profile->provider==CQ_DEEPSEEK||profile->provider==CQ_GEMINI) {
        WCHAR default_model[98];const WCHAR *default_name=profile->provider==CQ_GEMINI?L"gemini-3.6-flash":L"deepseek-flash";
        if(fallback&&fallback->provider==profile->provider) {
            for(i=0;fallback->model[i];++i)default_model[i]=(WCHAR)fallback->model[i];default_model[i]=0;default_name=default_model;
        }
        n=GetPrivateProfileStringW(section,L"model",default_name,model,98,path);
        if(!n||n>96)return ERROR_INVALID_DATA;
        for(i=0;i<n;++i){if(model[i]>127)return ERROR_INVALID_DATA;profile->model[i]=(char)model[i];}
        if(!ll_model(profile->model))return ERROR_INVALID_DATA;
    }
    return 0;
}
static DWORD cq_prepare(const LcrApis *api) {
    WCHAR path[1024],token[80],section[80];CqConfiguration config={0};DWORD n,port=0,error;
    BYTE random[16];unsigned i,used=0,ttl;HANDLE thread;
    if(!cq_configuration(path))return ERROR_FILE_NOT_FOUND;
    error=cq_read_profile(path,L"chat",NULL,&config.profiles[0]);if(error)return error;
    for(i=0;i<sizeof(cq_channels)/sizeof(cq_channels[0]);++i) {
        if(_snwprintf_s(section,80,_TRUNCATE,L"channel.%s",cq_channels[i].key)<0)return ERROR_INVALID_DATA;
        error=cq_read_profile(path,section,&config.profiles[0],&config.profiles[cq_channels[i].id+1]);if(error)return error;
    }
    for(i=0;i<sizeof(cq_channels)/sizeof(cq_channels[0]);++i)
        if(config.profiles[cq_channels[i].id+1].provider)used|=1u<<config.profiles[cq_channels[i].id+1].provider;
    /* Player names are a local display feature even with cloud chat off. */
    if(GetPrivateProfileIntW(L"chat",L"enabled",0,path)!=1){ZeroMemory(config.profiles,sizeof(config.profiles));used=0;}
    config.cache_entries=GetPrivateProfileIntW(L"chat",L"cache_entries",CG_CACHE,path);
    ttl=GetPrivateProfileIntW(L"chat",L"cache_idle_minutes",10,path);
    if(config.cache_entries<16||config.cache_entries>8192||ttl<1||ttl>60)return ERROR_INVALID_DATA;
    config.cache_idle_ms=(ULONGLONG)ttl*60000;
    ZeroMemory(token,sizeof(token));
    if(used&(1u<<CQ_LOCAL)) {
        n=GetPrivateProfileStringW(L"chat",L"token",L"",token,80,path);if(n!=64)return ERROR_INVALID_DATA;
        for(i=0;i<64;++i)if(!((token[i]>=L'0'&&token[i]<=L'9')||(token[i]>=L'a'&&token[i]<=L'f')))return ERROR_INVALID_DATA;
        port=GetPrivateProfileIntW(L"chat",L"port",0,path);if(port<1||port>65535)return ERROR_INVALID_DATA;
    }
    if(BCryptGenRandom(NULL,random,sizeof(random),BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0)return ERROR_INVALID_DATA;
    ZeroMemory(&g_cq,sizeof(g_cq));InitializeSRWLock(&g_cq.lock);g_cq.api=*api;g_cq.port=(INTERNET_PORT)port;g_cq.config=config;
    for(i=CQ_DEEPL;i<CQ_PROVIDERS;++i)if(used&(1u<<i))
        g_cq.config.credentials[i].key_error=cd_load_key(i,g_cq.config.credentials[i].authorization,320,&g_cq.config.credentials[i].deepl_free);
    for(i=0;i<16;++i){g_cq.session[i*2]="0123456789abcdef"[random[i]>>4];g_cq.session[i*2+1]="0123456789abcdef"[random[i]&15];}
    SecureZeroMemory(random,sizeof(random));
    if((used&(1u<<CQ_LOCAL))&&_snwprintf_s(g_cq.config.credentials[CQ_LOCAL].authorization,320,_TRUNCATE,L"Authorization: Bearer %s\r\n",token)<0)return ERROR_INVALID_DATA;
    SecureZeroMemory(token,sizeof(token));InterlockedExchange(&g_cq.online,1);
    thread=CreateThread(NULL,0,cq_worker,NULL,0,NULL);
    if(!thread){error=GetLastError();InterlockedExchange(&g_cq.online,0);SecureZeroMemory(g_cq.config.credentials,sizeof(g_cq.config.credentials));return error;}
    g_cq.worker=thread;return ERROR_SUCCESS;
}
