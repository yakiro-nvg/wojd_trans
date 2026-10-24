/* Bounded, allocation-free Google wire text and rich-text placeholder codec.
   No game/Lua/HTTP API. Only exact source islands may become live markup. */
#ifndef WOJD_CHAT_GOOGLE_TEXT_H
#define WOJD_CHAT_GOOGLE_TEXT_H
#include "chat_native_wire.h"

enum { GT_TOKENS=128, GT_TEXT=20000, GT_FORM=GT_TEXT*3+4, GT_JSON=80100 };
typedef struct GtToken {CwSpan value;unsigned structural;} GtToken;
typedef struct GtText {
    GtToken tokens[GT_TOKENS];unsigned count;
    char text[GT_TEXT];size_t size;
} GtText;
typedef struct GtTag {size_t end,name,size;unsigned closing,self;} GtTag;
static int gt_letter(unsigned char c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z');}
static int gt_digit(unsigned char c){return c>='0'&&c<='9';}
static int gt_space(unsigned char c){return c==' '||c=='\t'||c=='\r'||c=='\n';}
static unsigned char gt_lower(unsigned char c){return c>='A'&&c<='Z'?(unsigned char)(c+32):c;}
static int gt_bytes(char *out,size_t cap,size_t *n,const char *p,size_t size) {
    if(size>cap-*n)return 0;if(size)memcpy(out+*n,p,size);*n+=size;return 1;
}
static int gt_same(CwSpan s,size_t a,size_t an,size_t b,size_t bn) {
    size_t i;if(an!=bn)return 0;
    for(i=0;i<an;++i)if(gt_lower((unsigned char)s.data[a+i])!=gt_lower((unsigned char)s.data[b+i]))return 0;
    return 1;
}
/* 0 is ordinary '<' text; -1 is malformed tag-looking input. Quotes may
   contain '>', so a regex ending at the next greater-than is insufficient. */
static int gt_tag(CwSpan s,size_t at,GtTag *tag) {
    size_t p=at+1,start;unsigned char quote=0,c;
    memset(tag,0,sizeof(*tag));if(at>=s.size||s.data[at]!='<')return 0;
    if(p<s.size&&s.data[p]=='/'){tag->closing=1;++p;}
    if(tag->closing&&p<s.size&&s.data[p]=='>'){tag->end=p+1;return 1;}
    if(p>=s.size||!gt_letter((unsigned char)s.data[p]))return 0;
    start=p++;
    while(p<s.size&&(gt_letter((unsigned char)s.data[p])||gt_digit((unsigned char)s.data[p])||
          s.data[p]=='_'||s.data[p]==':'||s.data[p]=='-'||s.data[p]=='.'))++p;
    tag->name=start;tag->size=p-start;if(tag->size>48)return -1;
    if(p<s.size&&!gt_space((unsigned char)s.data[p])&&s.data[p]!='>'&&s.data[p]!='/'&&s.data[p]!='=')return -1;
    for(;p<s.size&&p-at<=2048;++p) {
        c=(unsigned char)s.data[p];
        if(c=='\r'||c=='\n')return -1;
        if(quote){if(c==quote)quote=0;continue;}
        if(c=='"'||c=='\''){if(tag->closing)return -1;quote=c;continue;}
        if(c=='<')return -1;
        if(c=='>') {tag->end=p+1;tag->self=p>at&&s.data[p-1]=='/';return 1;}
        if(tag->closing&&!gt_space(c))return -1;
    }
    return -1;
}
static int gt_opaque(CwSpan s,const GtTag *tag) {
    return (tag->size==1&&gt_lower((unsigned char)s.data[tag->name])=='a')||
        (tag->size==3&&gt_lower((unsigned char)s.data[tag->name])=='i'&&
         gt_lower((unsigned char)s.data[tag->name+1])=='m'&&gt_lower((unsigned char)s.data[tag->name+2])=='g');
}
static int gt_island(CwSpan s,size_t at,const GtTag *first,size_t *end) {
    GtTag stack[32],tag;unsigned depth=1;size_t p=first->end;int status;
    (void)at;if(first->self){*end=p;return 1;}stack[0]=*first;
    while(p<s.size) {
        if(s.data[p]!='<'){++p;continue;}
        status=gt_tag(s,p,&tag);if(status<0)return 0;if(!status){++p;continue;}
        if(tag.closing) {
            if(!depth||(tag.size&&!gt_same(s,stack[depth-1].name,stack[depth-1].size,tag.name,tag.size)))return 0;
            if(!--depth){*end=tag.end;return 1;}
        } else if(!tag.self) {if(depth==32)return 0;stack[depth++]=tag;}
        p=tag.end;
    }
    return 0;
}
static int gt_token(GtText *t,CwSpan source,size_t at,size_t end,unsigned structural) {
    char marker[13]={'_','_','W','O','J','D','_','T','0','0','0','_','_'};unsigned index=t->count;
    if(index>=GT_TOKENS||end<=at||end>source.size)return 0;
    marker[8]=(char)('0'+index/100);marker[9]=(char)('0'+index/10%10);marker[10]=(char)('0'+index%10);
    if(!gt_bytes(t->text,sizeof(t->text),&t->size,marker,sizeof(marker)))return 0;
    t->tokens[index].value.data=source.data+at;t->tokens[index].value.size=end-at;
    t->tokens[index].structural=structural;++t->count;return 1;
}
static int gt_prefix(CwSpan s,size_t at,const char *word) {
    size_t n=strlen(word);return n<=s.size-at&&!memcmp(s.data+at,word,n);
}
static int gt_prepare(CwSpan source,GtText *text) {
    size_t p=0,end,j;GtTag stack[32],tag;unsigned depth=0;int status;
    if(!text||!source.size||source.size>CW_SOURCE||!cw_utf8(source))return 0;
    memset(text,0,sizeof(*text));
    while(p<source.size) {
        if(gt_prefix(source,p,"__WOJD_T"))return 0;
        if(source.data[p]=='<') {
            status=gt_tag(source,p,&tag);if(status<0)return 0;
            if(status) {
                if(tag.closing) {
                    if(!depth||(tag.size&&!gt_same(source,stack[depth-1].name,stack[depth-1].size,tag.name,tag.size)))return 0;
                    --depth;if(!gt_token(text,source,p,tag.end,1))return 0;
                } else if(gt_opaque(source,&tag)) {
                    if(!gt_island(source,p,&tag,&end)||!gt_token(text,source,p,end,0))return 0;
                    p=end;continue;
                } else {
                    if(!tag.self){if(depth==32)return 0;stack[depth++]=tag;}
                    if(!gt_token(text,source,p,tag.end,1))return 0;
                }
                p=tag.end;continue;
            }
        }
        if(gt_prefix(source,p,"https://")||gt_prefix(source,p,"http://")) {
            end=p;while(end<source.size&&!gt_space((unsigned char)source.data[end])&&source.data[end]!='<'&&source.data[end]!='>')++end;
            if(!gt_token(text,source,p,end,0))return 0;p=end;continue;
        }
        if(source.data[p]=='{') {
            end=p+1;while(end<source.size&&end-p<=200&&source.data[end]!='}'&&source.data[end]!='{'&&source.data[end]!='\n')++end;
            if(end<source.size&&source.data[end]=='}'){if(!gt_token(text,source,p,end+1,0))return 0;p=end+1;continue;}
        }
        if(gt_digit((unsigned char)source.data[p])||((source.data[p]=='+'||source.data[p]=='-')&&p+1<source.size&&gt_digit((unsigned char)source.data[p+1]))) {
            end=p+1;while(end<source.size) {
                if(gt_digit((unsigned char)source.data[end])){++end;continue;}
                if((source.data[end]=='.'||source.data[end]==','||source.data[end]==':'||source.data[end]=='/')&&
                   end+1<source.size&&gt_digit((unsigned char)source.data[end+1])){end+=2;continue;}
                break;
            }
            if(end<source.size&&(source.data[end]=='%'||source.data[end]=='w'||source.data[end]=='W'))++end;
            if(!gt_token(text,source,p,end,0))return 0;p=end;continue;
        }
        /* Preserve printf placeholders and game bracket identities as data. */
        if(source.data[p]=='%') {
            end=p+1;while(end<source.size&&end-p<24&&strchr("0123456789$-+0 #.*",source.data[end]))++end;
            if(end<source.size&&strchr("sdifuxX",source.data[end])){if(!gt_token(text,source,p,end+1,0))return 0;p=end+1;continue;}
        }
        if(source.data[p]=='['&&(gt_prefix(source,p,"[item:")||gt_prefix(source,p,"[link:")||gt_prefix(source,p,"[player:")||gt_prefix(source,p,"[skill:"))) {
            end=p+1;while(end<source.size&&end-p<=320&&source.data[end]!=']'&&source.data[end]!='\n')++end;
            if(end<source.size&&source.data[end]==']'){if(!gt_token(text,source,p,end+1,0))return 0;p=end+1;continue;}
        }
        j=p++;if(!gt_bytes(text->text,sizeof(text->text),&text->size,source.data+j,1))return 0;
    }
    return !depth&&text->size!=0;
}
static int gt_form(CwSpan text,char *out,size_t capacity,size_t *written) {
    static const char hex[]="0123456789ABCDEF";size_t i,n=0;unsigned char c;char bytes[3];
    if(!written||!out||!cw_utf8(text))return 0;*written=0;
    if(!gt_bytes(out,capacity,&n,"q=",2))return 0;
    for(i=0;i<text.size;++i) {
        c=(unsigned char)text.data[i];
        if(gt_letter(c)||gt_digit(c)||c=='-'||c=='_'||c=='.'||c=='~') {if(!gt_bytes(out,capacity,&n,text.data+i,1))return 0;}
        else {bytes[0]='%';bytes[1]=hex[c>>4];bytes[2]=hex[c&15];if(!gt_bytes(out,capacity,&n,bytes,3))return 0;}
    }
    *written=n;return 1;
}
static int gt_escape(char *out,size_t cap,size_t *n,char c) {
    if(c=='&')return gt_bytes(out,cap,n,"&amp;",5);
    if(c=='<')return gt_bytes(out,cap,n,"\xe2\x80\xb9",3);
    if(c=='>')return gt_bytes(out,cap,n,"\xe2\x80\xba",3);
    return gt_bytes(out,cap,n,&c,1);
}
/* Escape only translated prose, THEN restore exact opaque source markup.
   Every token must survive exactly once; structural wrapper order is fixed. */
static int gt_restore_mode(const GtText *text,CwSpan translated,char *out,size_t capacity,size_t *written,int prose_numbers) {
    unsigned char seen[GT_TOKENS]={0};unsigned index,i,last=0,has_last=0,han=0,latin=0;size_t p=0,n=0;
    if(!text||!out||!written||!translated.size||!cw_utf8(translated))return 0;*written=0;
    while(p<translated.size) {
        if(gt_prefix(translated,p,"__WOJD_T")) {
            if(translated.size-p<13||!gt_digit((unsigned char)translated.data[p+8])||
               !gt_digit((unsigned char)translated.data[p+9])||!gt_digit((unsigned char)translated.data[p+10])||
               memcmp(translated.data+p+11,"__",2))return 0;
            index=(unsigned)(translated.data[p+8]-'0')*100+(unsigned)(translated.data[p+9]-'0')*10+(unsigned)(translated.data[p+10]-'0');
            if(index>=text->count||seen[index]++)return 0;
            if(text->tokens[index].structural){if(has_last&&index<=last)return 0;last=index;has_last=1;}
            if(!gt_bytes(out,capacity,&n,text->tokens[index].value.data,text->tokens[index].value.size))return 0;
            p+=13;
        } else {
            unsigned char lead=(unsigned char)translated.data[p];unsigned value=lead,count=0,k;
            /* Exact source numeric literals remain protected. In live chat,
               ordinary translated prose may localize Chinese number words,
               e.g. "one ten-thousand" to "10.000". That is not a wire error. */
            if((!prose_numbers&&gt_digit(lead))||(lead<32&&lead!='\n'&&lead!='\r'&&lead!='\t'))return 0;
            if(lead>=0xc2&&lead<0xe0){value=lead&31u;count=1;}
            else if(lead>=0xe0&&lead<0xf0){value=lead&15u;count=2;}
            else if(lead>=0xf0){value=lead&7u;count=3;}
            if(count)for(k=1;k<=count;++k)value=(value<<6)|((unsigned char)translated.data[p+k]&63u);
            if((value>=0x3400&&value<=0x9fff)||(value>=0xf900&&value<=0xfaff)||(value>=0x20000&&value<=0x323af))++han;
            else if(gt_letter(lead)||(value>=0xc0&&value<=0x24f)||(value>=0x1e00&&value<=0x1eff))++latin;
            for(k=0;k<=count;++k)if(!gt_escape(out,capacity,&n,translated.data[p+k]))return 0;
            p+=count+1;
        }
    }
    for(i=0;i<text->count;++i)if(seen[i]!=1)return 0;
    /* Conservative wrong-script rejection, not semantic certification. */
    if(han>=4&&han>latin)return 0;*written=n;return n!=0;
}
static int gt_restore(const GtText *text,CwSpan translated,char *out,size_t capacity,size_t *written) {
    return gt_restore_mode(text,translated,out,capacity,written,0);
}
static int gt_restore_chat(const GtText *text,CwSpan translated,char *out,size_t capacity,size_t *written) {
    return gt_restore_mode(text,translated,out,capacity,written,1);
}

typedef struct GtJson {CwSpan input;size_t at;unsigned budget;} GtJson;
static void gt_ws(GtJson *j){while(j->at<j->input.size&&gt_space((unsigned char)j->input.data[j->at]))++j->at;}
static int gt_take(GtJson *j,char c){gt_ws(j);if(j->at>=j->input.size||j->input.data[j->at]!=c)return 0;++j->at;return 1;}
static int gt_hex(unsigned char c) {
    if(c>='0'&&c<='9')return c-'0';c=gt_lower(c);return c>='a'&&c<='f'?c-'a'+10:-1;
}
static int gt_u16(GtJson *j,unsigned *value) {
    unsigned i,v=0;int h;if(j->input.size-j->at<4)return 0;
    for(i=0;i<4;++i){h=gt_hex((unsigned char)j->input.data[j->at++]);if(h<0)return 0;v=v*16+(unsigned)h;}*value=v;return 1;
}
static int gt_codepoint(unsigned value,char *out,size_t cap,size_t *n) {
    char b[4];size_t size;
    if(!value||value>0x10ffff||(value>=0xd800&&value<=0xdfff))return 0;
    if(value<128){b[0]=(char)value;size=1;}
    else if(value<0x800){b[0]=(char)(0xc0|(value>>6));b[1]=(char)(0x80|(value&63));size=2;}
    else if(value<0x10000){b[0]=(char)(0xe0|(value>>12));b[1]=(char)(0x80|((value>>6)&63));b[2]=(char)(0x80|(value&63));size=3;}
    else {b[0]=(char)(0xf0|(value>>18));b[1]=(char)(0x80|((value>>12)&63));b[2]=(char)(0x80|((value>>6)&63));b[3]=(char)(0x80|(value&63));size=4;}
    return out?gt_bytes(out,cap,n,b,size):1;
}
static int gt_json_string(GtJson *j,char *out,size_t cap,size_t *n) {
    unsigned char c;unsigned value,low;char decoded;
    if(!gt_take(j,'"'))return 0;
    while(j->at<j->input.size) {
        c=(unsigned char)j->input.data[j->at++];if(c=='"')return 1;if(c<32)return 0;
        if(c!='\\'){if(out&&!gt_bytes(out,cap,n,(const char *)&c,1))return 0;continue;}
        if(j->at==j->input.size)return 0;c=(unsigned char)j->input.data[j->at++];
        if(c=='u') {
            if(!gt_u16(j,&value))return 0;
            if(value>=0xd800&&value<=0xdbff) {
                if(j->input.size-j->at<6||memcmp(j->input.data+j->at,"\\u",2))return 0;j->at+=2;
                if(!gt_u16(j,&low)||low<0xdc00||low>0xdfff)return 0;value=0x10000+((value-0xd800)<<10)+(low-0xdc00);
            }
            if(!gt_codepoint(value,out,cap,n))return 0;continue;
        }
        if(c=='"'||c=='\\'||c=='/')decoded=(char)c;
        else if(c=='n')decoded='\n';else if(c=='r')decoded='\r';else if(c=='t')decoded='\t';
        else if(c=='b')decoded='\b';else if(c=='f')decoded='\f';else return 0;
        if(out&&!gt_bytes(out,cap,n,&decoded,1))return 0;
    }
    return 0;
}
static int gt_json_value(GtJson *j,unsigned depth) {
    char c;size_t start,ignored=0;
    if(depth>32||!j->budget--)return 0;gt_ws(j);if(j->at==j->input.size)return 0;c=j->input.data[j->at];
    if(c=='"')return gt_json_string(j,NULL,0,&ignored);
    if(c=='['||c=='{') {
        char close=c=='['?']':'}';++j->at;gt_ws(j);if(gt_take(j,close))return 1;
        do {
            if(c=='{'&&(!gt_json_string(j,NULL,0,&ignored)||!gt_take(j,':')))return 0;
            if(!gt_json_value(j,depth+1))return 0;
            if(gt_take(j,close))return 1;
        }while(gt_take(j,','));return 0;
    }
    if(gt_prefix(j->input,j->at,"null")){j->at+=4;return 1;}
    if(gt_prefix(j->input,j->at,"true")){j->at+=4;return 1;}
    if(gt_prefix(j->input,j->at,"false")){j->at+=5;return 1;}
    start=j->at;if(c=='-')++j->at;
    if(j->at==j->input.size||!gt_digit((unsigned char)j->input.data[j->at]))return 0;
    if(j->input.data[j->at]=='0')++j->at;else while(j->at<j->input.size&&gt_digit((unsigned char)j->input.data[j->at]))++j->at;
    if(j->at<j->input.size&&j->input.data[j->at]=='.') {
        ++j->at;if(j->at==j->input.size||!gt_digit((unsigned char)j->input.data[j->at]))return 0;
        while(j->at<j->input.size&&gt_digit((unsigned char)j->input.data[j->at]))++j->at;
    }
    if(j->at<j->input.size&&(j->input.data[j->at]=='e'||j->input.data[j->at]=='E')) {
        ++j->at;if(j->at<j->input.size&&(j->input.data[j->at]=='+'||j->input.data[j->at]=='-'))++j->at;
        if(j->at==j->input.size||!gt_digit((unsigned char)j->input.data[j->at]))return 0;
        while(j->at<j->input.size&&gt_digit((unsigned char)j->input.data[j->at]))++j->at;
    }
    return j->at>start;
}
static int gt_response(CwSpan raw,char *out,size_t capacity,size_t *written) {
    GtJson j;unsigned segments=0;size_t n=0;CwSpan result;
    if(!out||!written||!raw.size||raw.size>GT_JSON||!cw_utf8(raw))return 0;*written=0;
    j.input=raw;j.at=0;j.budget=20000;
    if(!gt_take(&j,'[')||!gt_take(&j,'['))return 0;
    do {
        if(++segments>256||!gt_take(&j,'[')||!gt_json_string(&j,out,capacity,&n))return 0;
        while(gt_take(&j,','))if(!gt_json_value(&j,1))return 0;
        if(!gt_take(&j,']'))return 0;
        if(gt_take(&j,']'))break;
        if(!gt_take(&j,','))return 0;
    }while(1);
    while(gt_take(&j,','))if(!gt_json_value(&j,1))return 0;
    if(!gt_take(&j,']'))return 0;gt_ws(&j);if(j.at!=raw.size)return 0;
    result.data=out;result.size=n;if(!n||!cw_utf8(result))return 0;*written=n;return 1;
}
#endif
