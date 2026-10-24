/* Local Hán–Việt display helper. No network, account IDs or history writes. */
#ifndef WOJD_PLAYER_NAMES_H
#define WOJD_PLAYER_NAMES_H
#include "chat_google_text.h"
#include "player_name_readings.h"
static const char *pn_lookup(unsigned cp) {
    size_t a=0,b=sizeof(pn_readings)/sizeof(pn_readings[0]);
    while(a<b){size_t m=a+(b-a)/2;if(pn_readings[m].codepoint<cp)a=m+1;else b=m;}
    return a<sizeof(pn_readings)/sizeof(pn_readings[0])&&pn_readings[a].codepoint==cp?(const char *)pn_text+pn_readings[a].offset:NULL;
}
static int pn_han(unsigned cp){return (cp>=0x3400&&cp<=0x9fff)||(cp>=0xf900&&cp<=0xfaff)||(cp>=0x20000&&cp<=0x323af);}
static int pn_convert(CwSpan input,char *out,size_t cap,size_t *size) {
    size_t p=0,n=0,start;unsigned cp,lead,extra,i,changed=0,previous=0;
    if(!input.size||input.size>256||!cw_utf8(input))return 0;
    while(p<input.size) {
        start=p;lead=(unsigned char)input.data[p++];cp=lead;extra=0;
        if(lead>=0xf0){cp=lead&7;extra=3;}else if(lead>=0xe0){cp=lead&15;extra=2;}else if(lead>=0xc0){cp=lead&31;extra=1;}
        for(i=0;i<extra;++i)cp=(cp<<6)|((unsigned char)input.data[p++]&63);
        {const char *reading=pn_lookup(cp);unsigned word=pn_han(cp)||(cp<128&&(gt_letter((unsigned char)cp)||gt_digit((unsigned char)cp)));
         if((reading&&previous)||(previous==2&&word))if(n&&out[n-1]!=' '&&!gt_bytes(out,cap,&n," ",1))return 0;
         if(reading){if(!gt_bytes(out,cap,&n,reading,strlen(reading)))return 0;++changed;previous=2;}
         else {if(!gt_bytes(out,cap,&n,input.data+start,p-start))return 0;previous=word?1u:0u;}}
    }
    *size=n;return changed!=0;
}
/* A plain, display-only sender label. Never copy name characters as markup. */
static int pn_reading(CwSpan name,char *out,size_t cap,size_t *size) {
    char plain[2048];size_t n=0,i,written=0;int converted=pn_convert(name,plain,sizeof(plain),&n);
    (void)converted;
    if(!n)return 0;
    for(i=0;i<n;++i)if(!gt_escape(out,cap,&written,plain[i])){SecureZeroMemory(plain,sizeof(plain));return 0;}
    SecureZeroMemory(plain,sizeof(plain));*size=written;return 1;
}
static int pn_attribute(CwSpan input,const GtTag *tag,const char *key,CwSpan *value) {
    size_t p=tag->name+tag->size,start,key_size;unsigned found=0;char quote;
    while(p<tag->end) {
        while(p<tag->end&&gt_space((unsigned char)input.data[p]))++p;
        if(p>=tag->end||input.data[p]=='>'||input.data[p]=='/')break;
        start=p;while(p<tag->end&&(gt_letter((unsigned char)input.data[p])||gt_digit((unsigned char)input.data[p])||input.data[p]=='_'))++p;
        key_size=p-start;if(!key_size)return 0;
        while(p<tag->end&&gt_space((unsigned char)input.data[p]))++p;
        if(p>=tag->end||input.data[p++]!='=')return 0;
        while(p<tag->end&&gt_space((unsigned char)input.data[p]))++p;
        if(p>=tag->end||((quote=input.data[p++])!='\''&&quote!='"'))return 0;
        {size_t begin=p;while(p<tag->end&&input.data[p]!=quote)++p;if(p>=tag->end)return 0;
         if(key_size==strlen(key)&&!memcmp(input.data+start,key,key_size)) {
             if(found++)return 0;value->data=input.data+begin;value->size=p-begin;
         }++p;}
    }
    return found==1;
}
/* Only annotate player-name links in the VI copy. The complete original link
   and every action attribute survive byte-for-byte; item links remain exact. */
static int pn_links(CwSpan input,char *out,size_t cap,size_t *size) {
    size_t p=0,n=0,end;unsigned changed=0;GtTag tag;
    if(!input.size||input.size>CW_TRANSLATION||!cw_utf8(input))return 0;
    while(p<input.size) {
        if(input.data[p]=='<') {
            int status=gt_tag(input,p,&tag);if(status<0)return 0;
            if(status&&gt_opaque(input,&tag)&&!tag.closing) {
                CwSpan kind,name;char converted[2048],escaped[8192];size_t count=0,written=0,i;
                if(!gt_island(input,p,&tag,&end))return 0;
                if(!gt_bytes(out,cap,&n,input.data+p,end-p))return 0;
                if(tag.size==1&&gt_lower((unsigned char)input.data[tag.name])=='a'&&
                   pn_attribute(input,&tag,"type",&kind)&&kind.size==10&&!memcmp(kind.data,"playerName",10)&&
                   pn_attribute(input,&tag,"text",&name)&&pn_convert(name,converted,sizeof(converted),&count)) {
                    for(i=0;i<count;++i)if(!gt_escape(escaped,sizeof(escaped),&written,converted[i]))return 0;
                    if(!gt_bytes(out,cap,&n," 【",4)||!gt_bytes(out,cap,&n,escaped,written)||!gt_bytes(out,cap,&n,"】",3))return 0;
                    ++changed;
                }
                SecureZeroMemory(converted,sizeof(converted));SecureZeroMemory(escaped,sizeof(escaped));p=end;continue;
            }
            if(status){if(!gt_bytes(out,cap,&n,input.data+p,tag.end-p))return 0;p=tag.end;continue;}
        }
        if(!gt_bytes(out,cap,&n,input.data+p,1))return 0;++p;
    }
    *size=n;return changed!=0;
}
/* Change only visible label text, never playerName's text/XID metadata.
   Some native decorators render directly from attributes. In that case add
   a reading beside the untouched original link so its actions stay valid. */
static int pn_prefix(CwSpan name,CwSpan prefix,char *out,size_t cap,size_t *size) {
    char reading[2048];size_t rn=0,p=0,n=0;unsigned replaced=0;GtTag tag;
    if(!prefix.size||prefix.size>6000||!cw_utf8(prefix)||!pn_convert(name,reading,sizeof(reading),&rn))return 0;
    while(p<prefix.size) {
        if(prefix.data[p]=='<') {
            int status=gt_tag(prefix,p,&tag);if(status<0)return 0;
            if(status){if(!gt_bytes(out,cap,&n,prefix.data+p,tag.end-p))return 0;p=tag.end;continue;}
        }
        if(!replaced&&name.size<=prefix.size-p&&!memcmp(prefix.data+p,name.data,name.size)) {
            if(!gt_bytes(out,cap,&n,reading,rn))return 0;p+=name.size;replaced=1;
        } else {if(!gt_bytes(out,cap,&n,prefix.data+p,1))return 0;++p;}
    }
    if(!replaced&&(!gt_bytes(out,cap,&n," 【",4)||!gt_bytes(out,cap,&n,reading,rn)||!gt_bytes(out,cap,&n,"】 ",4)))return 0;
    *size=n;return 1;
}
#endif
