/* DeepL official XML placeholder transport. Game markup never leaves the PC. */
#ifndef WOJD_CHAT_DEEPL_TEXT_H
#define WOJD_CHAT_DEEPL_TEXT_H
#include "chat_google_text.h"
static int dt_xml(CwSpan protected_text,char *out,size_t cap,size_t *written) {
    size_t p=0,n=0;char c;if(!out||!written||!cw_utf8(protected_text))return 0;*written=0;
    if(!gt_bytes(out,cap,&n,"<r>",3))return 0;
    while(p<protected_text.size) {
        if(gt_prefix(protected_text,p,"__WOJD_T")) {
            if(protected_text.size-p<13||!gt_bytes(out,cap,&n,"<x>",3)||
               !gt_bytes(out,cap,&n,protected_text.data+p,13)||!gt_bytes(out,cap,&n,"</x>",4))return 0;
            p+=13;continue;
        }
        c=protected_text.data[p++];
        if(c=='&'){if(!gt_bytes(out,cap,&n,"&amp;",5))return 0;}
        else if(c=='<'){if(!gt_bytes(out,cap,&n,"&lt;",4))return 0;}
        else if(c=='>'){if(!gt_bytes(out,cap,&n,"&gt;",4))return 0;}
        else if(!gt_bytes(out,cap,&n,&c,1))return 0;
    }
    if(!gt_bytes(out,cap,&n,"</r>",4))return 0;*written=n;return 1;
}
static int dt_form(CwSpan protected_text,char *out,size_t cap,size_t *written) {
    static const char options[]="&source_lang=ZH&target_lang=VI&tag_handling=xml&tag_handling_version=v2&ignore_tags=x&non_splitting_tags=x&preserve_formatting=1";
    char xml[GT_TEXT*2];size_t n=0,size;CwSpan span;
    if(!written)return 0;*written=0;
    if(!dt_xml(protected_text,xml,sizeof(xml),&size))return 0;
    span.data=xml;span.size=size;
    if(cap<3||!gt_form(span,out,cap-3,&n))return 0;
    memmove(out+5,out+2,n-2);memcpy(out,"text=",5);n+=3;
    if(!gt_bytes(out,cap,&n,options,sizeof(options)-1))return 0;*written=n;return 1;
}
/* r/x are transport wrappers, not exact target text spans. DeepL v2 can
   associate adjacent translated prose with an x element, including ignored
   non-splitting x elements. Flatten their text in order, decode entities once,
   then validate every opaque marker in the common codec. No game tag is XML. */
static int dt_unxml(CwSpan xml,char *out,size_t cap,size_t *written) {
    size_t p=0,n=0,end;int closed=0;unsigned value,h,depth=0;char c;CwSpan result;
    if(!written||!out||!cw_utf8(xml))return 0;*written=0;
    while(p<xml.size&&gt_space((unsigned char)xml.data[p]))++p;
    if(!gt_prefix(xml,p,"<r>"))return 0;p+=3;
    while(p<xml.size) {
        if(gt_prefix(xml,p,"</r>")){if(depth)return 0;p+=4;closed=1;break;}
        if(gt_prefix(xml,p,"<x>")) {
            if(depth>=GT_TOKENS)return 0;++depth;p+=3;continue;
        }
        if(gt_prefix(xml,p,"</x>")){if(!depth)return 0;--depth;p+=4;continue;}
        if(gt_prefix(xml,p,"<x/>")){p+=4;continue;}
        if(gt_prefix(xml,p,"<x />")){p+=5;continue;}
        c=xml.data[p++];if(c=='<')return 0;
        if(c=='&') {
            end=p;while(end<xml.size&&end-p<16&&xml.data[end]!=';')++end;
            if(end==xml.size||xml.data[end]!=';')return 0;
            if(end-p==3&&!memcmp(xml.data+p,"amp",3))c='&';
            else if(end-p==2&&!memcmp(xml.data+p,"lt",2))c='<';
            else if(end-p==2&&!memcmp(xml.data+p,"gt",2))c='>';
            else if(end-p==4&&!memcmp(xml.data+p,"quot",4))c='"';
            else if(end-p==4&&!memcmp(xml.data+p,"apos",4))c='\'';
            else if(xml.data[p]=='#') {
                size_t q=p+1;unsigned base=10;value=0;
                if(q<end&&(xml.data[q]=='x'||xml.data[q]=='X')){base=16;++q;}
                if(q==end)return 0;
                for(;q<end;++q){int digit=gt_hex((unsigned char)xml.data[q]);if(digit<0||(unsigned)digit>=base||value>0x10ffff/base)return 0;h=(unsigned)digit;value=value*base+h;}
                if(!gt_codepoint(value,out,cap,&n))return 0;p=end+1;continue;
            } else return 0;
            p=end+1;
        }
        if(!gt_bytes(out,cap,&n,&c,1))return 0;
    }
    while(p<xml.size&&gt_space((unsigned char)xml.data[p]))++p;
    result.data=out;result.size=n;if(!closed||p!=xml.size||!n||!cw_utf8(result))return 0;*written=n;return 1;
}
static int dt_key(GtJson *j,char *out,size_t cap,size_t *n) {*n=0;return gt_json_string(j,out,cap,n);}
static int dt_translation(GtJson *j,char *out,size_t cap,size_t *written) {
    char key[64];size_t n;unsigned seen=0;
    if(!gt_take(j,'{'))return 0;
    do {
        if(!dt_key(j,key,sizeof(key),&n)||!gt_take(j,':'))return 0;
        if(n==4&&!memcmp(key,"text",4)){if(seen++)return 0;if(!gt_json_string(j,out,cap,written))return 0;}
        else if(!gt_json_value(j,1))return 0;
        if(gt_take(j,'}'))return seen==1;
    }while(gt_take(j,','));return 0;
}
static int dt_response(CwSpan raw,char *out,size_t cap,size_t *written) {
    GtJson j;char key[64];size_t n;unsigned seen=0;CwSpan result;
    if(!written||!out||!raw.size||raw.size>GT_JSON||!cw_utf8(raw))return 0;*written=0;
    j.input=raw;j.at=0;j.budget=20000;
    if(!gt_take(&j,'{'))return 0;
    do {
        if(!dt_key(&j,key,sizeof(key),&n)||!gt_take(&j,':'))return 0;
        if(n==12&&!memcmp(key,"translations",12)) {
            if(seen++||!gt_take(&j,'[')||!dt_translation(&j,out,cap,written)||!gt_take(&j,']'))return 0;
        } else if(!gt_json_value(&j,1))return 0;
        if(gt_take(&j,'}'))break;
        if(!gt_take(&j,','))return 0;
    }while(1);
    gt_ws(&j);result.data=out;result.size=*written;
    return seen==1&&j.at==raw.size&&result.size&&cw_utf8(result);
}
#endif
