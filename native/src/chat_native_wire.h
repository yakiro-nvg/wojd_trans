#ifndef WOJD_CHAT_NATIVE_WIRE_H
#define WOJD_CHAT_NATIVE_WIRE_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
enum { CW_SOURCE=16000,CW_TRANSLATION=64000,CW_PACKET=80100 };
typedef struct CwSpan {const char *data;size_t size;} CwSpan;
typedef struct CwPacket {unsigned code;CwSpan session,id,source,translation;} CwPacket;
static unsigned cw_u16(const unsigned char *p){return (unsigned)p[0]|((unsigned)p[1]<<8);}
static uint32_t cw_u32(const unsigned char *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void cw_write16(unsigned char *p,size_t n){p[0]=(unsigned char)n;p[1]=(unsigned char)(n>>8);}
static void cw_write32(unsigned char *p,size_t n){p[0]=(unsigned char)n;p[1]=(unsigned char)(n>>8);p[2]=(unsigned char)(n>>16);p[3]=(unsigned char)(n>>24);}
static int cw_utf8(CwSpan text) {
    size_t i=0,j;unsigned lead,count,first;
    while(i<text.size) {
        lead=(unsigned char)text.data[i++];if(lead<128){if(!lead)return 0;continue;}
        if(lead>=0xc2 && lead<=0xdf)count=1;
        else if(lead>=0xe0 && lead<=0xef)count=2;
        else if(lead>=0xf0 && lead<=0xf4)count=3;
        else return 0;
        if(count>text.size-i)return 0;first=(unsigned char)text.data[i];
        if((lead==0xe0 && first<0xa0) || (lead==0xed && first>=0xa0) ||
           (lead==0xf0 && first<0x90) || (lead==0xf4 && first>=0x90))return 0;
        for(j=0;j<count;++j)if(((unsigned char)text.data[i++]&0xc0)!=0x80)return 0;
    }
    return 1;
}
static int cw_valid(const CwPacket *p,int response) {
    size_t i;
    if(!p || p->code<1 || p->code>(response?3u:2u) || !p->session.data || p->session.size!=32 ||
       !p->id.data || p->id.size<1 || p->id.size>20 || !p->source.data ||
       !p->source.size || p->source.size>CW_SOURCE || p->translation.size>CW_TRANSLATION ||
       (p->translation.size && !p->translation.data))return 0;
    for(i=0;i<32;++i)if(!((p->session.data[i]>='0' && p->session.data[i]<='9') ||
                          (p->session.data[i]>='a' && p->session.data[i]<='f')))return 0;
    if(p->id.data[0]=='0')return 0;
    for(i=0;i<p->id.size;++i)if(p->id.data[i]<'0' || p->id.data[i]>'9')return 0;
    if(!cw_utf8(p->source) || !cw_utf8(p->translation))return 0;
    if(response)return (p->code==2)==(p->translation.size!=0);
    return !p->translation.size;
}
/* Output is disjoint from all input spans. No allocation, Lua or I/O. */
static int cw_encode(const CwPacket *p,int response,unsigned char *out,size_t capacity,size_t *written) {
    size_t n,offset;
    if(!written)return 0;*written=0;
    if(!cw_valid(p,response))return 0;
    n=43+p->id.size+p->source.size+(response?4+p->translation.size:0);
    if(n>CW_PACKET)return 0;*written=n;if(!out)return 1;if(capacity<n)return 0;
    memcpy(out,response?"WJR1":"WJC1",4);out[4]=(unsigned char)p->code;
    memcpy(out+5,p->session.data,32);cw_write16(out+37,p->id.size);
    memcpy(out+39,p->id.data,p->id.size);offset=39+p->id.size;
    cw_write32(out+offset,p->source.size);offset+=4;memcpy(out+offset,p->source.data,p->source.size);offset+=p->source.size;
    if(response){cw_write32(out+offset,p->translation.size);offset+=4;if(p->translation.size)memcpy(out+offset,p->translation.data,p->translation.size);}
    return 1;
}
static int cw_decode(const unsigned char *raw,size_t n,int response,CwPacket *output) {
    CwPacket p;size_t offset,size;
    if(!raw || !output || n<44 || n>CW_PACKET || memcmp(raw,response?"WJR1":"WJC1",4))return 0;
    memset(&p,0,sizeof(p));p.code=raw[4];p.session.data=(const char *)raw+5;p.session.size=32;
    size=cw_u16(raw+37);if(size<1 || size>20 || 39+size+4>n)return 0;
    p.id.data=(const char *)raw+39;p.id.size=size;offset=39+size;
    size=cw_u32(raw+offset);offset+=4;if(!size || size>CW_SOURCE || size>n-offset)return 0;
    p.source.data=(const char *)raw+offset;p.source.size=size;offset+=size;
    if(response) {
        if(n-offset<4)return 0;size=cw_u32(raw+offset);offset+=4;
        if(size>CW_TRANSLATION || size>n-offset)return 0;
        p.translation.data=(const char *)raw+offset;p.translation.size=size;offset+=size;
    }
    if(offset!=n || !cw_valid(&p,response))return 0;*output=p;return 1;
}
#endif
