/* Standalone owned data only; no game, network or Lua. */
#include <stdio.h>
#include "../src/chat_google_text.h"
#include "../src/chat_deepl_text.h"
#if defined(_WIN32)
#define GT_EXPORT __declspec(dllexport)
#else
#define GT_EXPORT
#endif
GT_EXPORT int GtFixturePrepare(const char *source,size_t size,char *out,size_t cap,size_t *written) {
    GtText text;CwSpan span={source,size};if(!written)return 0;*written=0;
    if(!source||!gt_prepare(span,&text)||text.size>cap)return 0;
    memcpy(out,text.text,text.size);*written=text.size;return 1;
}
GT_EXPORT int GtFixtureRestore(const char *source,size_t size,const char *translated,size_t n,char *out,size_t cap,size_t *written) {
    GtText text;CwSpan span={source,size},target={translated,n};if(!written)return 0;*written=0;
    if(!source||!translated||!gt_prepare(span,&text))return 0;
    return gt_restore(&text,target,out,cap,written);
}
GT_EXPORT int GtFixtureRestoreChat(const char *source,size_t size,const char *translated,size_t n,char *out,size_t cap,size_t *written) {
    GtText text;CwSpan span={source,size},target={translated,n};if(!written)return 0;*written=0;
    if(!source||!translated||!gt_prepare(span,&text))return 0;
    return gt_restore_chat(&text,target,out,cap,written);
}
GT_EXPORT int GtFixtureResponse(const char *input,size_t size,char *out,size_t cap,size_t *written) {
    CwSpan span={input,size};return gt_response(span,out,cap,written);
}
GT_EXPORT int GtFixtureForm(const char *input,size_t size,char *out,size_t cap,size_t *written) {
    CwSpan span={input,size};return gt_form(span,out,cap,written);
}
GT_EXPORT int DtFixtureForm(const char *input,size_t size,char *out,size_t cap,size_t *written) {CwSpan span={input,size};return dt_form(span,out,cap,written);}
GT_EXPORT int DtFixtureResponse(const char *input,size_t size,char *out,size_t cap,size_t *written) {CwSpan span={input,size};return dt_response(span,out,cap,written);}
GT_EXPORT int DtFixtureUnxml(const char *input,size_t size,char *out,size_t cap,size_t *written) {CwSpan span={input,size};return dt_unxml(span,out,cap,written);}
#if !defined(GT_FIXTURE_LIBRARY)
static unsigned checks,failed;
#define CHECK(x) do {++checks;if(!(x)){++failed;fprintf(stderr,"failed line %u\n",(unsigned)__LINE__);}}while(0)
static void roundtrip(const char *source) {
    char prepared[GT_TEXT],restored[CW_TRANSLATION];size_t a=0,b=0,n=strlen(source);
    CHECK(GtFixturePrepare(source,n,prepared,sizeof(prepared),&a));
    CHECK(GtFixtureRestore(source,n,prepared,a,restored,sizeof(restored),&b));
    CHECK(b==n&&!memcmp(source,restored,n));
}
int main(void) {
    static const char *sources[]={
        "hello", "xin chao <img module=\"Chat\" type=\"Emoji\" id=\"Emoji10\"></>",
        "<a module=\"Chat\" type=\"itemslot\" text=\"item name\" id=\"123\"></>",
        "<a title=\"x > y\"><b>visible</></>", "<red>hello <a id=\"3\">item</></>",
        "<red><b>nested</b></red>", "<img id=\"1\"/>", "<red/>hello", "50% -12 +3 20:30 1/2 40w",
        "https://example.org/3?q=2 {player} %s [item:123]", "<red>one</> and <blue>two</>",
    };
    static const char *bad[]={"<img id=\"3\">", "</>", "<a>one</b>", "<a x=\"unterminated>",
        "<red>hello", "<red>hello</blue>", "__WOJD_T000__", "<a><b>item</></x>", "<a>\0"};
    static const char json[]="[[[\"xin \\u0063hao \\ud83d\\ude00\",\"source\",null,null,1],[\"!\",null]],null,\"zh-CN\",null,[],{\"a\":[true,false,-1.2e+3]}]";
    static const char *invalid[]={"[[[]]]", "[[[null]]]", "[[[\"x\",]]]", "[[[\"x\"]]]garbage", "[[[\"\\u0000\"]]]",
        "[[[\"\\ud800\"]]]", "[[[\"\\udc00\"]]]", "[[[\"\\ud800\\u0001\"]]]", "[[[\"x\"]],01]", "[[[\"x\"]],truex]"};
    char out[CW_TRANSLATION];size_t n=0,i;GtText t;CwSpan span;
    for(i=0;i<sizeof(sources)/sizeof(sources[0]);++i)roundtrip(sources[i]);
    for(i=0;i<sizeof(bad)/sizeof(bad[0]);++i)CHECK(!GtFixturePrepare(bad[i],strlen(bad[i]),out,sizeof(out),&n));
    CHECK(GtFixtureResponse(json,strlen(json),out,sizeof(out),&n));
    CHECK(n==14&&!memcmp(out,"xin chao \xf0\x9f\x98\x80!",14));
    for(i=0;i<strlen(json);++i)CHECK(!GtFixtureResponse(json,i,out,sizeof(out),&n));
    for(i=0;i<sizeof(invalid)/sizeof(invalid[0]);++i)CHECK(!GtFixtureResponse(invalid[i],strlen(invalid[i]),out,sizeof(out),&n));
    CHECK(GtFixturePrepare("<red>x</>",9,out,sizeof(out),&n));
    CHECK(!GtFixtureRestore("<red>x</>",9,"__WOJD_T001__x__WOJD_T000__",27,out,sizeof(out),&n));
    CHECK(!GtFixtureRestore("<red>x</>",9,"__WOJD_T000__x",14,out,sizeof(out),&n));
    CHECK(!GtFixtureRestore("x",1,"__WOJD_T000__",13,out,sizeof(out),&n));
    CHECK(!GtFixtureRestore("x",1,"invented 123",12,out,sizeof(out),&n));
    CHECK(GtFixtureRestore("x",1,"<img>new</>",11,out,sizeof(out),&n));
    CHECK(n==19&&!memcmp(out,"\xe2\x80\xb9img\xe2\x80\xbanew\xe2\x80\xb9/\xe2\x80\xba",19));
    CHECK(GtFixtureForm("a &\n",4,out,sizeof(out),&n));CHECK(n==12&&!memcmp(out,"q=a%20%26%0A",12));
    CHECK(GtFixtureRestore("x",1,"&lt;evil&gt;",12,out,sizeof(out),&n));
    CHECK(n==20&&!memcmp(out,"&amp;lt;evil&amp;gt;",20));
    CHECK(GtFixtureRestore("x",1,"\\b",2,out,sizeof(out),&n)); /* Literal backslash remains ordinary text. */
    CHECK(!GtFixtureRestore("x",1,"\b",1,out,sizeof(out),&n));
    CHECK(!GtFixtureForm("x",1,out,2,&n));
    CHECK(DtFixtureUnxml("<r>A &amp; B <x>__WOJD_T000__</x></r>",strlen("<r>A &amp; B <x>__WOJD_T000__</x></r>"),out,sizeof(out),&n));
    CHECK(n==19&&!memcmp(out,"A & B __WOJD_T000__",19));
    {
        static const char xml[]="<r>Vui long <x>doi __WOJD_T000__ phut</x> roi quay lai.</r>";
        static const char flat[]="Vui long doi __WOJD_T000__ phut roi quay lai.";
        CHECK(DtFixtureUnxml(xml,strlen(xml),out,sizeof(out),&n));
        CHECK(n==strlen(flat)&&!memcmp(out,flat,n));
        for(i=0;i<strlen(xml);++i)CHECK(!DtFixtureUnxml(xml,i,out,sizeof(out),&n));
        CHECK(DtFixtureUnxml("<r><x>one <x>two</x> three</x><x/> end</r>",strlen("<r><x>one <x>two</x> three</x><x/> end</r>"),out,sizeof(out),&n));
        CHECK(n==17&&!memcmp(out,"one two three end",17));
        CHECK(!DtFixtureUnxml("<r><x>unclosed</r>",strlen("<r><x>unclosed</r>"),out,sizeof(out),&n));
        CHECK(!DtFixtureUnxml("<r>unopened</x></r>",strlen("<r>unopened</x></r>"),out,sizeof(out),&n));
        CHECK(GtFixtureRestoreChat("一万车票等2",strlen("一万车票等2"),"10.000 ve xe __WOJD_T000__",strlen("10.000 ve xe __WOJD_T000__"),out,sizeof(out),&n));
        CHECK(n==14&&!memcmp(out,"10.000 ve xe 2",14));
        CHECK(!GtFixtureRestoreChat("等2",strlen("等2"),"doi 3",strlen("doi 3"),out,sizeof(out),&n));
        CHECK(!GtFixtureRestoreChat("等2",strlen("等2"),"__WOJD_T000__ __WOJD_T000__",strlen("__WOJD_T000__ __WOJD_T000__"),out,sizeof(out),&n));
    }
    CHECK(!DtFixtureUnxml("<r><evil>x</evil></r>",20,out,sizeof(out),&n));
    CHECK(DtFixtureResponse("{\"translations\":[{\"text\":\"<r>xin chao</r>\",\"detected_source_language\":\"ZH\"}]}",strlen("{\"translations\":[{\"text\":\"<r>xin chao</r>\",\"detected_source_language\":\"ZH\"}]}"),out,sizeof(out),&n));
    CHECK(n==15&&!memcmp(out,"<r>xin chao</r>",15));
    CHECK(!DtFixtureResponse("{\"translations\":[{\"text\":\"a\",\"text\":\"b\"}]}",strlen("{\"translations\":[{\"text\":\"a\",\"text\":\"b\"}]}"),out,sizeof(out),&n));
    span.data="<red>x</>";span.size=9;CHECK(gt_prepare(span,&t));
    span.data=t.text;span.size=t.size;CHECK(!gt_restore(&t,span,out,2,&n));
    printf("{\"status\":\"%s\",\"checks\":%u,\"failed\":%u,\"network\":false,\"game_access\":false}\n",failed?"FAIL":"PASS",checks,failed);
    return failed?1:0;
}
#endif
