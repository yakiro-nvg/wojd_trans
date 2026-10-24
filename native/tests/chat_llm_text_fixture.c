/* Contract/hostile response cases, no service or game dependency. */
#include <windows.h>
#include <stdio.h>
#include "../src/chat_llm_text.h"
static unsigned checks;
static int check(int value,int line){++checks;if(!value){printf("FAIL llm line=%d check=%u\n",line,checks);return 0;}return 1;}
#define CHECK(x) do {if(!check(!!(x),__LINE__))return 1;}while(0)
static GtText empty;
static int parse(int gemini,const char *s,char *out,size_t *n){CwSpan raw;raw.data=s;raw.size=strlen(s);return ll_response(gemini,raw,&empty,out,CW_TRANSLATION,n);}
int main(void) {
    char *out=(char *)HeapAlloc(GetProcessHeap(),0,CW_PACKET),restored[CW_TRANSLATION];size_t n,k;CwSpan s;GtText prepared;
    const char *valid="{\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"{\\\"segments\\\":[\\\"Xin chao\\\"]}\"}],\"role\":\"model\"},\"finishReason\":\"STOP\"}],\"usageMetadata\":{\"promptTokenCount\":10}}";
    const char *deep="{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"{\\\"segments\\\":[\\\"Chao ban\\\"]}\",\"reasoning_content\":\"not display text\"},\"finish_reason\":\"stop\"}]}";
    CHECK(out!=NULL);
    CHECK(parse(1,valid,out,&n)&&n==8&&!memcmp(out,"Xin chao",8));
    CHECK(parse(0,deep,out,&n)&&n==8&&!memcmp(out,"Chao ban",8));
    CHECK(!parse(0,valid,out,&n));CHECK(!parse(1,deep,out,&n));
    CHECK(!parse(1,"{\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"{}\"}]},\"finishReason\":\"MAX_TOKENS\"}]}",out,&n));
    CHECK(!parse(1,"{\"candidates\":[]}",out,&n));
    CHECK(!parse(1,"{\"candidates\":[],\"candidates\":[]}",out,&n));
    CHECK(!parse(1,"{\"candidates\":[{\"finishReason\":\"STOP\",\"content\":{\"parts\":[{\"functionCall\":{\"name\":\"do_it\"}}]}}]}",out,&n));
    CHECK(!parse(1,"{\"candidates\":[{\"finishReason\":\"STOP\",\"content\":{\"parts\":[{\"thought\":true,\"text\":\"hidden\"}]}}]}",out,&n));
    CHECK(parse(1,"{\"candidates\":[{\"finishReason\":\"STOP\",\"content\":{\"parts\":[{\"thought\":true,\"text\":\"hidden\"},{\"text\":\"{\\\"segments\\\":[\\\"Xin \"},{\"text\":\"chao\\\"]}\"}]}}]}",out,&n)&&n==8);
    s.data="{\"segments\":[\"yes\"],\"segments\":[\"no\"]}";s.size=strlen(s.data);CHECK(!ll_translation(s,&empty,out,CW_PACKET,&n));
    s.data="{\"segments\":[\"yes\"],\"action\":\"send\"}";s.size=strlen(s.data);CHECK(!ll_translation(s,&empty,out,CW_PACKET,&n));
    s.data="{\"segments\":[\"a\\u0000b\"]}";s.size=strlen(s.data);CHECK(!ll_translation(s,&empty,out,CW_PACKET,&n));
    s.data="{\"segments\":[\"\\ud83d\\ude00\"]}";s.size=strlen(s.data);CHECK(ll_translation(s,&empty,out,CW_PACKET,&n)&&n==4);
    s.data="队伍4等1 <img module=\"Chat\" type=\"Emoji\" id=\"Emoji22\"></>";s.size=strlen(s.data);
    CHECK(gt_prepare(s,&prepared));
    CHECK(ll_request(1,"gemini-3.6-flash",&prepared,out,CW_PACKET,&n));out[n]=0;
    CHECK(strstr(out,"anchors")&&strstr(out,"\\\"4\\\"")&&strstr(out,"\\\"1\\\"")&&!strstr(out,"Emoji22")&&!strstr(out,"module=")&&!strstr(out,"__WOJD_T"));
    CHECK(strstr(out,"responseJsonSchema")&&strstr(out,"MINIMAL")&&!strstr(out,"\"temperature\""));
    CHECK(ll_request(0,"deepseek-flash",&prepared,out,CW_PACKET,&n));out[n]=0;
    CHECK(strstr(out,"json_object")&&strstr(out,"\"thinking\":{\"type\":\"disabled\"}")&&!strstr(out,"Emoji22"));
    CHECK(!ll_request(1,"../wrong?api-key=value",&prepared,out,CW_PACKET,&n));
    CHECK(!ll_request(1,"gemini-3.6-flash",&prepared,out,10,&n));
    s.data="{\"segments\":[\"To doi \",\" cho \",\" \",\"\"]}";s.size=strlen(s.data);
    CHECK(ll_translation(s,&prepared,out,CW_PACKET,&n));
    s.data=out;s.size=n;CHECK(gt_restore_chat(&prepared,s,restored,sizeof(restored),&k));restored[k]=0;
    CHECK(strstr(restored,"4 cho 1")&&strstr(restored,"Emoji22"));
    s.data="{\"segments\":[\"lost span\"]}";s.size=strlen(s.data);CHECK(!ll_translation(s,&prepared,out,CW_PACKET,&n));
    s.data="{\"segments\":[\"extra\",\"span\"]}";s.size=strlen(s.data);CHECK(!ll_translation(s,&empty,out,CW_PACKET,&n));
    s.data="To doi __WOJD_T000__ cho __WOJD_T001__ __WOJD_T002__";s.size=strlen(s.data);
    CHECK(gt_restore_chat(&prepared,s,restored,sizeof(restored),&k));restored[k]=0;
    CHECK(strstr(restored,"4 cho 1")&&strstr(restored,"Emoji22"));
    s.data="To doi __WOJD_T000__ __WOJD_T000__";s.size=strlen(s.data);CHECK(!gt_restore_chat(&prepared,s,restored,sizeof(restored),&k));
    s.data="妙法5次q1";s.size=strlen(s.data);CHECK(ll_prepare(s,&prepared)&&prepared.count==0&&prepared.size==s.size);
    HeapFree(GetProcessHeap(),0,out);printf("PASS native LLM contract fixture checks=%u, no network\n",checks);return 0;
}
