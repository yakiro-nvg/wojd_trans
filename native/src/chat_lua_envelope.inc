#include "chat_lua_envelope.h"
#include <stdint.h>
#include <string.h>

#define LC_MAX_BYTES (1024u*1024u)
typedef struct LcReader { const unsigned char *data;size_t size,pos;unsigned functions;int error; } LcReader;
typedef struct LcFunction { size_t begin,end,source_end,descriptors;unsigned upvalues,params,vararg,children; } LcFunction;
typedef struct LcRoot { LcFunction main,first;unsigned upvalues; } LcRoot;
static const unsigned char lc_header[]={0x1b,0x4c,0x75,0x61,0x54,0,0x19,0x93,0x0d,0x0a,0x1a,0x0a,4,8,8,0x78,0x56,0,0,0,0,0,0,0,0,0,0,0,0x28,0x77,0x40};
static const char lc_marker[]="WOJD_CHAT_LOADER_OBSERVER_V1:";
static const char lc_callback_marker[]="WOJD_CHAT_CALLBACK_V1:";

static int lc_take(LcReader *r,size_t count) {
    if(r->error)return 0;
    if(count>r->size-r->pos){r->error=LC_FORMAT;return 0;}
    r->pos+=count;return 1;
}
static unsigned lc_byte(LcReader *r) {size_t pos=r->pos;return lc_take(r,1)?r->data[pos]:0;}
static unsigned lc_integer(LcReader *r) {
    unsigned value=0,i,part;
    for(i=0;i<5 && !r->error;++i) {
        part=lc_byte(r);
        if((i==0 && part==0) || value>(0x7fffffffu>>7)){r->error=LC_FORMAT;return 0;}
        value=(value<<7)|(part&127u);
        if(value>0x7fffffffu){r->error=LC_FORMAT;return 0;}
        if(part&128u)return value;
    }
    r->error=LC_FORMAT;return 0;
}
static unsigned lc_string(LcReader *r) {unsigned size=lc_integer(r);if(size)lc_take(r,size-1u);return size;}
static int lc_count(LcReader *r,unsigned count,unsigned limit,size_t minimum) {
    if(r->error)return 0;
    if(count>limit || (minimum && count>(r->size-r->pos)/minimum)){r->error=LC_LIMIT;return 0;}
    return 1;
}
static int lc_function(LcReader *r,unsigned depth,LcFunction *result,LcFunction *first) {
    unsigned stack,count,i,tag;
    LcFunction child;
    memset(result,0,sizeof(*result));result->begin=r->pos;
    if(depth>64 || ++r->functions>2048){r->error=LC_LIMIT;return 0;}
    lc_string(r);result->source_end=r->pos;lc_integer(r);lc_integer(r);
    result->params=lc_byte(r);result->vararg=lc_byte(r);stack=lc_byte(r);
    if(r->error)return 0;
    if(result->vararg>1 || stack<2 || stack>250 || result->params>stack){r->error=LC_FORMAT;return 0;}
    count=lc_integer(r);if(!lc_count(r,count,LC_MAX_BYTES,4) || !lc_take(r,(size_t)count*4))return 0;
    count=lc_integer(r);if(!lc_count(r,count,LC_MAX_BYTES,1))return 0;
    for(i=0;i<count && !r->error;++i) {
        tag=lc_byte(r);
        if(tag==0 || tag==1 || tag==17)continue;
        if(tag==3 || tag==19)lc_take(r,8);
        else if(tag==4 || tag==20){if(!lc_string(r))r->error=LC_FORMAT;}
        else r->error=LC_FORMAT;
    }
    result->upvalues=lc_integer(r);result->descriptors=r->pos;
    if(!lc_count(r,result->upvalues,255,3) || !lc_take(r,(size_t)result->upvalues*3))return 0;
    result->children=lc_integer(r);if(!lc_count(r,result->children,2048,1))return 0;
    for(i=0;i<result->children;++i) {
        if(!lc_function(r,depth+1,&child,NULL))return 0;
        if(first && i==0)*first=child;
    }
    count=lc_integer(r);if(!lc_take(r,count))return 0;
    count=lc_integer(r);if(!lc_count(r,count,LC_MAX_BYTES,2))return 0;
    for(i=0;i<count;++i){lc_integer(r);lc_integer(r);}
    count=lc_integer(r);if(!lc_count(r,count,LC_MAX_BYTES,3))return 0;
    for(i=0;i<count;++i){lc_string(r);lc_integer(r);lc_integer(r);}
    count=lc_integer(r);if(!lc_count(r,count,result->upvalues,1))return 0;
    for(i=0;i<count;++i)lc_string(r);
    result->end=r->pos;return !r->error;
}
static int lc_parse(const unsigned char *data,size_t size,LcRoot *root) {
    LcReader reader;
    if(!data || size<=sizeof(lc_header)+1 || size>LC_MAX_BYTES)return LC_ARGUMENT;
    if(memcmp(data,lc_header,sizeof(lc_header)))return LC_FORMAT;
    memset(&reader,0,sizeof(reader));reader.data=data;reader.size=size;reader.pos=sizeof(lc_header);
    memset(root,0,sizeof(*root));root->upvalues=lc_byte(&reader);
    if(!lc_function(&reader,0,&root->main,&root->first))return reader.error?reader.error:LC_FORMAT;
    if(reader.pos!=size || root->main.upvalues!=root->upvalues)return LC_FORMAT;
    return LC_OK;
}
static int lc_contains(const unsigned char *data,size_t size,const char *marker,size_t length) {
    size_t i;
    if(size<length)return 0;
    for(i=0;i<=size-length;++i)if(data[i]=='W' && !memcmp(data+i,marker,length))return 1;
    return 0;
}
static int lc_contains_marker(const unsigned char *data,size_t size) {
    return lc_contains(data,size,lc_marker,sizeof(lc_marker)-1) ||
        lc_contains(data,size,lc_callback_marker,sizeof(lc_callback_marker)-1);
}
static int lc_root_shape(const unsigned char *data,const LcRoot *root) {
    return root->main.params==0 && root->main.vararg==1 && root->upvalues==1 &&
        data[root->main.descriptors]==1 && data[root->main.descriptors+1]==0 && data[root->main.descriptors+2]==0;
}
static int lc_overlaps(const void *a,size_t as,const void *b,size_t bs) {
    uintptr_t ap=(uintptr_t)a,bp=(uintptr_t)b;
    if(as>UINTPTR_MAX-ap || bs>UINTPTR_MAX-bp)return 1;
    return ap<bp+bs && bp<ap+as;
}
static int lc_envelope_mode(const unsigned char *original,size_t original_size,const unsigned char *wrapper,size_t wrapper_size,
                            unsigned char *output,size_t capacity,size_t *written,int callback) {
    LcRoot source,template_root;size_t child_size,needed,offset,source_size,template_source_size,prefix_size;int error;
    if(!written)return LC_ARGUMENT;
    *written=0;
    error=lc_parse(original,original_size,&source);if(error)return error;
    error=lc_parse(wrapper,wrapper_size,&template_root);if(error)return error;
    if(!lc_root_shape(original,&source) || lc_contains_marker(original,original_size))return LC_SOURCE;
    if((callback ? (template_root.main.params!=0 || template_root.main.vararg!=1 || template_root.upvalues!=2 ||
                   memcmp(wrapper+template_root.main.descriptors,"\x01\x00\x00\x01\x01\x00",6) ||
                   !lc_contains(wrapper,wrapper_size,lc_callback_marker,sizeof(lc_callback_marker)-1)) :
                  (!lc_root_shape(wrapper,&template_root) ||
                   !lc_contains(wrapper,wrapper_size,lc_marker,sizeof(lc_marker)-1))) || template_root.main.children!=2 ||
       template_root.first.upvalues || template_root.first.params || template_root.first.vararg!=1 ||
       template_root.first.children)return LC_TEMPLATE;
    child_size=source.main.end-source.main.begin;
    source_size=source.main.source_end-source.main.begin;
    template_source_size=template_root.main.source_end-template_root.main.begin;
    prefix_size=template_root.first.begin-template_source_size+source_size;
    needed=wrapper_size-(template_root.first.end-template_root.first.begin)+child_size-template_source_size+source_size;
    if(needed>LC_MAX_BYTES)return LC_LIMIT;
    *written=needed;
    if(!output)return LC_OK;
    if(capacity<needed)return LC_BUFFER;
    if(lc_overlaps(output,needed,original,original_size) || lc_overlaps(output,needed,wrapper,wrapper_size))return LC_ARGUMENT;
    /* The host can use the loaded root's source to select its module scope.
       Preserve that identity as well as the original child's debug metadata. */
    offset=template_root.main.begin;
    memcpy(output,wrapper,offset);
    memcpy(output+offset,original+source.main.begin,source_size);offset+=source_size;
    memcpy(output+offset,wrapper+template_root.main.source_end,template_root.first.begin-template_root.main.source_end);
    offset=prefix_size;
    memcpy(output+offset,original+source.main.begin,child_size);
    output[offset+source.main.descriptors-source.main.begin]=0;
    memcpy(output+offset+child_size,wrapper+template_root.first.end,wrapper_size-template_root.first.end);
    return LC_OK;
}
int lc_envelope(const unsigned char *original,size_t original_size,const unsigned char *wrapper,size_t wrapper_size,
                unsigned char *output,size_t capacity,size_t *written) {
    return lc_envelope_mode(original,original_size,wrapper,wrapper_size,output,capacity,written,0);
}
int lc_callback_envelope(const unsigned char *original,size_t original_size,const unsigned char *wrapper,size_t wrapper_size,
                         unsigned char *output,size_t capacity,size_t *written) {
    return lc_envelope_mode(original,original_size,wrapper,wrapper_size,output,capacity,written,1);
}

#ifdef LC_FIXTURE_DLL
__declspec(dllexport) int __cdecl WojdLuaEnvelope(const unsigned char *a,size_t an,const unsigned char *b,size_t bn,
                                                unsigned char *output,size_t capacity,size_t *written) {
    return lc_envelope(a,an,b,bn,output,capacity,written);
}
__declspec(dllexport) int __cdecl WojdLuaCallbackEnvelope(const unsigned char *a,size_t an,const unsigned char *b,size_t bn,
                                                        unsigned char *output,size_t capacity,size_t *written) {
    return lc_callback_envelope(a,an,b,bn,output,capacity,written);
}
#endif
