/* Actual provider/cache/DPAPI code, synthetic transport and key only.
   This executable never loads a game module or connects to a service. */
#include <windows.h>
#include <winhttp.h>
#include <stdio.h>
#include <string.h>
#include "../src/chat_native_wire.h"
#define WOJD_CHAT_OBSERVER_TEST 1
#include "../src/chat_cloud_types.h"
static struct {CqConfiguration config;LONG online,notice;} g_cq;
#define PROFILE g_cq.config.profiles[0]
#define CRED g_cq.config.credentials[PROFILE.provider]
static WCHAR g_root_path[1024];
#include "../src/chat_google_provider.inc"
#include "../src/chat_deepl_key.inc"
static unsigned checks,calls,response_kind;static DWORD response_status=200;
static int check(int value,int line) {++checks;if(!value){printf("FAIL line=%d check=%u\n",line,checks);return 0;}return 1;}
#define CHECK(x) do {if(!check(!!(x),__LINE__))return 1;}while(0)
static DWORD transport(HINTERNET connection,const char *form,DWORD bytes,unsigned char *out,SIZE_T *size,DWORD *status) {
    static const char result[]="{\"translations\":[{\"text\":\"<r>Xin chao <x>__WOJD_T000__</x></r>\"}]}";
    static const char surrounding[]="{\"translations\":[{\"text\":\"<r>Xin chao <x>ban __WOJD_T000__ nhe</x></r>\"}]}";
    static const char malformed[]="{\"translations\":[{\"text\":\"<r><x>unclosed</r>\"}]}";
    static const char duplicate[]="{\"translations\":[{\"text\":\"<r><x>__WOJD_T000__ __WOJD_T000__</x></r>\"}]}";
    const char *selected;
    static char body[CW_PACKET+1];
    (void)connection;++calls;*status=response_status;*size=0;
    if(response_status!=200)return ERROR_BAD_NET_RESP;
    if(bytes<5||bytes>CW_PACKET)return ERROR_INVALID_DATA;memcpy(body,form,bytes);body[bytes]=0;
    if(g_cg_test_profile->provider==CQ_GEMINI||g_cg_test_profile->provider==CQ_DEEPSEEK) {
        static const char gemini[]="{\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"{\\\"segments\\\":[\\\"Xin chao \\\",\\\"\\\"]}\"}]},\"finishReason\":\"STOP\"}]}";
        static const char deepseek[]="{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"{\\\"segments\\\":[\\\"Chao ban \\\",\\\"\\\"]}\"},\"finish_reason\":\"stop\"}]}";
        if(!strstr(body,"anchors")||strstr(body,"Emoji22")||strstr(body,"__WOJD_T"))return ERROR_INVALID_DATA;
        selected=g_cg_test_profile->provider==CQ_GEMINI?gemini:deepseek;*size=strlen(selected);memcpy(out,selected,*size);return 0;
    }
    if(g_cg_test_profile->provider==CQ_GOOGLE) {
        static const char google[]="[[[\"Google __WOJD_T000__\",null,null,null,1]]]";
        if(memcmp(body,"q=",2)||strstr(body,"Emoji"))return ERROR_INVALID_DATA;
        *size=strlen(google);memcpy(out,google,*size);return 0;
    }
    if(memcmp(body,"text=",5)||!strstr(body,"ignore_tags=x")||strstr(body,"Emoji"))return ERROR_INVALID_DATA;
    selected=response_kind==1?surrounding:response_kind==2?malformed:response_kind==3?duplicate:result;
    *size=strlen(selected);memcpy(out,selected,*size);return 0;
}
int main(void) {
    CqRecord row={0};CwSpan source;unsigned i;SIZE_T size;BOOL free_key;
    char *scratch=(char *)HeapAlloc(GetProcessHeap(),0,CW_PACKET*2u),copy[CW_TRANSLATION];
    WCHAR temp[MAX_PATH],file[1100];HANDLE stream;DWORD wrote;DATA_BLOB input,output;BYTE bytes[4096];
    static BYTE entropy[]="WOJD-CHAT-KEY-V1";DATA_BLOB salt={sizeof(entropy)-1,entropy};
    static char key[]="00000000-0000-0000-0000-000000000000:fx";
    CHECK(scratch!=NULL);g_cq.config.cache_entries=64;PROFILE.provider=CQ_DEEPL;g_cq.online=1;g_cg_test_transport=transport;
    for(i=0;i<64;++i) {
        row.source_size=(SIZE_T)_snprintf_s(row.source,sizeof(row.source),_TRUNCATE,"source-%u",i);
        memcpy(row.translation,"translated",10);row.translation_size=10;cg_store(&row,1000+i);
    }
    source.data="source-0";source.size=8;CHECK(cg_lookup(source,copy,&size,2000)&&size==10);
    CHECK(g_cg.cache[0].expires==602000); /* hit extends idle TTL */
    memcpy(row.source,"source-64",9);row.source_size=9;cg_store(&row,3000);
    source.data="source-1";CHECK(!cg_lookup(source,copy,&size,4000)); /* true LRU */
    source.data="source-0";CHECK(cg_lookup(source,copy,&size,4000));
    cg_purge(603000);CHECK(cg_lookup(source,copy,&size,603000));
    cg_purge(1203000);CHECK(!cg_lookup(source,copy,&size,1203000));
    cg_close();
    /* Increased default, idle expiry, dynamic payload accounting and the hard
       byte ceiling are independent of the configured entry count. */
    g_cq.config.cache_entries=0;g_cq.config.cache_idle_ms=60000;
    row.source_size=4;memcpy(row.source,"same",4);row.translation_size=10;
    cg_store(&row,1000);cg_store(&row,2000);
    CHECK(g_cg.capacity==1024&&g_cg.cache_bytes==14); /* replace, not duplicate */
    source.data="same";source.size=4;CHECK(cg_lookup(source,copy,&size,61000));
    cg_purge(120999);CHECK(g_cg.cache_bytes==14);cg_purge(121000);CHECK(g_cg.cache_bytes==0);
    cg_close();g_cq.config.cache_entries=2048;
    memset(row.source,'s',CW_SOURCE);row.source_size=CW_SOURCE;
    memset(row.translation,'t',CW_TRANSLATION);row.translation_size=CW_TRANSLATION;
    for(i=0;i<1200;++i){memcpy(row.source,&i,sizeof(i));cg_store(&row,200000+i);}
    CHECK(g_cg.capacity==2048&&g_cg.cache_bytes<=CG_BYTES&&g_cg.cache_bytes>=CG_BYTES-80000);
    source.data=row.source;source.size=CW_SOURCE;CHECK(cg_lookup(source,copy,&size,201201)&&size==CW_TRANSLATION);
    cg_purge(262000);CHECK(g_cg.cache_bytes==0);cg_close();g_cq.config.cache_idle_ms=0;g_cq.config.cache_entries=1024;
    CHECK(GetTempPathW(MAX_PATH,temp)>0);CHECK(GetTempFileNameW(temp,L"wjc",0,g_root_path)>0);
    CHECK(DeleteFileW(g_root_path));CHECK(CreateDirectoryW(g_root_path,NULL));
    _snwprintf_s(file,1100,_TRUNCATE,L"%s\\chat-key.bin",g_root_path);
    input.pbData=(BYTE *)key;input.cbData=sizeof(key)-1;
    CHECK(CryptProtectData(&input,NULL,&salt,NULL,NULL,CRYPTPROTECT_UI_FORBIDDEN,&output));
    CHECK(output.cbData+5<=sizeof(bytes));memcpy(bytes,"WJDK1",5);memcpy(bytes+5,output.pbData,output.cbData);
    SecureZeroMemory(output.pbData,output.cbData);LocalFree(output.pbData);
    stream=CreateFileW(file,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);CHECK(stream!=INVALID_HANDLE_VALUE);
    CHECK(WriteFile(stream,bytes,output.cbData+5,&wrote,NULL)&&wrote==output.cbData+5);CloseHandle(stream);
    CHECK(cd_load_key(PROFILE.provider,CRED.authorization,320,&free_key)==0&&free_key);
    CHECK(wcsstr(CRED.authorization,L"Authorization: DeepL-Auth-Key ")==CRED.authorization);
    CHECK(DeleteFileW(file));CHECK(RemoveDirectoryW(g_root_path));
    CHECK(cd_load_key(PROFILE.provider,CRED.authorization,320,&free_key)!=0);
    /* A key encrypted for one cloud cannot be reused for another provider. */
    CHECK(CreateDirectoryW(g_root_path,NULL));PROFILE.provider=CQ_GEMINI;
    salt.pbData=(BYTE *)"WOJD-CHAT-KEY-V2:gemini";salt.cbData=(DWORD)strlen((const char *)salt.pbData);
    CHECK(CryptProtectData(&input,NULL,&salt,NULL,NULL,CRYPTPROTECT_UI_FORBIDDEN,&output));
    memcpy(bytes,"WJDK25",6);memcpy(bytes+6,output.pbData,output.cbData);size=output.cbData+6;
    SecureZeroMemory(output.pbData,output.cbData);LocalFree(output.pbData);
    stream=CreateFileW(file,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);CHECK(stream!=INVALID_HANDLE_VALUE);
    CHECK(WriteFile(stream,bytes,(DWORD)size,&wrote,NULL)&&wrote==size);CloseHandle(stream);
    CHECK(cd_load_key(PROFILE.provider,CRED.authorization,320,&free_key)==0&&wcsstr(CRED.authorization,L"x-goog-api-key: ")==CRED.authorization);
    PROFILE.provider=CQ_DEEPSEEK;CHECK(cd_load_key(PROFILE.provider,CRED.authorization,320,&free_key)==ERROR_INVALID_DATA);
    PROFILE.provider=CQ_DEEPL;CHECK(cd_load_key(PROFILE.provider,CRED.authorization,320,&free_key)==ERROR_INVALID_DATA);
    CHECK(DeleteFileW(file));CHECK(RemoveDirectoryW(g_root_path));
    strcpy_s(row.source,sizeof(row.source),"\xe4\xbd\xa0\xe5\xa5\xbd <img module=\"Chat\" type=\"Emoji\" id=\"Emoji22\"></>");
    row.source_size=strlen(row.source);row.expires=GetTickCount64()+30000;calls=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0);
    CHECK(row.translation_size<CW_TRANSLATION);row.translation[row.translation_size]=0;
    CHECK(calls==1&&strstr(row.translation,"<img module=\"Chat\" type=\"Emoji\" id=\"Emoji22\"></>")!=NULL);
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0&&calls==1);
    cg_close();response_status=456;g_cg.last_request=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)!=0&&(g_cq.notice&255)==2&&g_cg.network[0].terminal);
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)!=0&&calls==2); /* no fallback */
    cg_close();response_status=403;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)!=0&&(g_cq.notice&255)==1&&g_cg.network[0].terminal);
    cg_close();response_status=429;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)!=0&&(g_cq.notice&255)==3&&!g_cg.network[0].terminal);
    i=calls;g_cq.notice=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)!=0&&calls==i&&(g_cq.notice&255)==0);
    response_status=200;g_cg.network[0].cooldown=0;g_cg.last_request=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0&&(g_cq.notice&255)==6);
    cg_close();CRED.key_error=ERROR_INVALID_DATA;i=calls;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)!=0&&(g_cq.notice&255)==1&&calls==i);
    cg_close();CRED.key_error=0;g_cq.notice=0;response_kind=1;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0);
    row.translation[row.translation_size]=0;CHECK(strstr(row.translation,"ban <img")&&strstr(row.translation," nhe"));
    cg_purge(GetTickCount64()+600001);response_kind=2;g_cg.last_request=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==ERROR_INVALID_DATA&&(g_cq.notice&255)==5);
    g_cq.notice=0;response_kind=1;g_cg.last_request=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0&&(g_cq.notice&255)==0); /* no fake network recovery */
    cg_purge(GetTickCount64()+600001);response_kind=2;g_cg.last_request=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==ERROR_INVALID_DATA&&(g_cq.notice&255)==0); /* per-code throttle */
    response_status=500;g_cg.last_request=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)!=0&&(g_cq.notice&255)==4);
    response_status=200;response_kind=1;g_cg.network[0].cooldown=0;g_cg.last_request=0;g_cq.notice=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0&&(g_cq.notice&255)==6);
    cg_purge(GetTickCount64()+600001);response_kind=3;g_cg.last_request=0;g_cq.notice=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==ERROR_INVALID_DATA&&(g_cq.notice&255)==0&&g_cg.placeholder_errors==1);
    cg_close();response_kind=0;response_status=200;PROFILE.provider=CQ_GEMINI;strcpy_s(PROFILE.model,sizeof(PROFILE.model),"gemini-3.6-flash");i=calls;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0&&calls==i+1);
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0&&calls==i+1);
    strcpy_s(PROFILE.model,sizeof(PROFILE.model),"gemini-3.1-flash-lite");g_cg.last_request=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0&&calls==i+2); /* model cache isolation */
    PROFILE.provider=CQ_DEEPSEEK;strcpy_s(PROFILE.model,sizeof(PROFILE.model),"deepseek-flash");g_cg.last_request=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0&&calls==i+3); /* provider isolation */
    cg_close();g_cq.notice=0;response_status=402;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)!=0&&(g_cq.notice&255)==2&&g_cg.network[0].terminal);
    cg_close();PROFILE.provider=CQ_GEMINI;g_cq.notice=0;response_status=400;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)!=0&&(g_cq.notice&255)==7&&g_cg.network[0].terminal);
    /* Routing: a rejected Gemini model does not block Google or DeepSeek;
       equal profiles share cache across channels, other models cannot. */
    g_cq.config.profiles[2].provider=CQ_GOOGLE;
    g_cq.config.profiles[3].provider=CQ_DEEPSEEK;strcpy_s(g_cq.config.profiles[3].model,97,"deepseek-flash");
    g_cq.config.profiles[4]=g_cq.config.profiles[3];
    response_status=200;row.profile=2;g_cg.last_request=0;i=calls;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0&&calls==i+1);
    row.profile=3;g_cg.last_request=0;
    CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0&&calls==i+2);
    row.profile=4;CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)==0&&calls==i+2);
    row.profile=0;CHECK(cg_translate(NULL,&row,scratch,(unsigned char *)scratch+CW_PACKET)!=0&&calls==i+2);
    {unsigned profile=0;CwSpan channel={"18",2};CHECK(!cq_channel_profile(channel,&profile));
     channel.data="8";channel.size=1;CHECK(!cq_channel_profile(channel,&profile));
     channel.data="99";channel.size=2;CHECK(!cq_channel_profile(channel,&profile));
     channel.data="2";channel.size=1;CHECK(cq_channel_profile(channel,&profile)&&profile==3);}
    SecureZeroMemory(CRED.authorization,sizeof(CRED.authorization));cg_close();HeapFree(GetProcessHeap(),0,scratch);
    printf("PASS native cloud/cache/key fixture checks=%u, no network\n",checks);return 0;
}
