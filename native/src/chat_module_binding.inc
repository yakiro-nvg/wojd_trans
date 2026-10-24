/* Bind the actual tables captured by the stock provider closures. Global
   provider replacement is unnecessary: private module scopes may cache them.
   Only a certified zero-result root return is changed, inside our envelope. */
typedef struct LcmString {const BYTE *bytes;unsigned size;} LcmString;
typedef struct LcmDetail {
    SIZE_T code;unsigned count,constants,children;
    LcmString strings[256];LcFunction child[32];
} LcmDetail;
typedef struct LcmLayout {unsigned methods,resend,upvalue;} LcmLayout;
static unsigned lcm_word(const BYTE *raw,SIZE_T code,unsigned index) {
    uint32_t value;memcpy(&value,raw+code+(SIZE_T)index*4,4);return value;
}
static int lcm_details(const BYTE *raw,SIZE_T size,const LcFunction *function,LcmDetail *out) {
    LcReader r;unsigned i,n,tag;
    ZeroMemory(out,sizeof(*out));ZeroMemory(&r,sizeof(r));r.data=raw;r.size=size;r.pos=function->begin;
    lc_string(&r);lc_integer(&r);lc_integer(&r);lc_take(&r,3);
    out->count=lc_integer(&r);out->code=r.pos;
    if(out->count<1 || out->count>4096 || !lc_take(&r,(SIZE_T)out->count*4))return 0;
    out->constants=lc_integer(&r);if(out->constants>256)return 0;
    for(i=0;i<out->constants;++i) {
        tag=lc_byte(&r);
        if(tag==3 || tag==19)lc_take(&r,8);
        else if(tag==4 || tag==20) {
            n=lc_integer(&r);if(!n)return 0;
            out->strings[i].bytes=raw+r.pos;out->strings[i].size=n-1;lc_take(&r,n-1);
        } else if(tag!=0 && tag!=1 && tag!=17)return 0;
    }
    n=lc_integer(&r);if(n>255 || !lc_take(&r,(SIZE_T)n*3))return 0;
    out->children=lc_integer(&r);if(out->children>32)return 0;
    for(i=0;i<out->children;++i)if(!lc_function(&r,1,&out->child[i],NULL))return 0;
    return !r.error;
}
static int lcm_key(const LcmDetail *d,const char *name) {
    unsigned i,count=0;int index=-1;SIZE_T length=strlen(name);
    for(i=0;i<d->constants;++i)if(d->strings[i].size==length && d->strings[i].bytes &&
       !memcmp(d->strings[i].bytes,name,length)){index=(int)i;++count;}
    return count==1?index:-1;
}
static int lcm_closure(const BYTE *raw,const LcmDetail *d,unsigned word,unsigned params,LcFunction *child) {
    unsigned index=word>>15;
    if((word&127)!=79 || index>=d->children)return 0;
    *child=d->child[index];return child->params==params && !child->vararg && child->upvalues<256 && raw!=NULL;
}
static int lcm_expose(BYTE *raw,SIZE_T size,unsigned kind,LcmLayout *layout) {
    LcRoot root;LcmDetail detail,resend_detail;
    unsigned producer[256]={0},position[256]={0},i,j,word,op,a,b,c,flag;
    unsigned table=256,table_position=0,bindings=0,provider=256,provider_word=0,resend_register=256,slot=0;
    int key1,key2,key_provider;LcFunction child,create={0},provider_child;int parsed;
    if(!raw || !layout || (kind!=1 && kind!=2))return LC_ARGUMENT;
    parsed=lc_parse(raw,size,&root);if(parsed)return parsed;
    if(!lc_root_shape(raw,&root) || !lcm_details(raw,size,&root.main,&detail))return LC_SOURCE;
    key1=lcm_key(&detail,kind==1?"BuildChatMessageItem":"NewScrollBox");
    key2=kind==1?lcm_key(&detail,"AddItemToList"):-1;
    key_provider=lcm_key(&detail,kind==1?"ProvideChatMessageItem":"ProvideChatScrollBox");
    if(key1<0 || key_provider<0 || (kind==1 && key2<0))return LC_SOURCE;
    for(i=0;i<detail.count;++i) {
        word=lcm_word(raw,detail.code,i);op=word&127;a=(word>>7)&255;flag=(word>>15)&1;b=(word>>16)&255;c=word>>24;
        if(i==detail.count-1) {
            if(op!=70 || b!=1 || c!=1 || !flag)return LC_SOURCE;
            break;
        }
        if(op==18 && !flag && ((int)b==key1 || (kind==1 && (int)b==key2))) {
            if(table!=256 && table!=a)return LC_SOURCE;
            if(!lcm_closure(raw,&detail,producer[c],kind==2?2u:(int)b==key1?8u:3u,&child) || position[c]>=i)return LC_SOURCE;
            if(kind==2)create=child;
            table=a;table_position=i;++bindings;
        }
        if(op==15 && !flag && a==0 && (int)b==key_provider) {
            if(provider!=256 || position[c]>=i)return LC_SOURCE;
            provider=c;provider_word=producer[c];
        }
        if(op==0 || op==1 || op==2 || op==3 || op==4 || op==5 || op==7 || op==9 || op==11 ||
           op==12 || op==13 || op==14 || op==19 || op==79) {producer[a]=word;position[a]=i;}
        else if(op==8) {
            if(a+b>255)return LC_SOURCE;
            for(j=a;j<=a+b;++j){producer[j]=word;position[j]=i;}
        } else if(op!=15 && op!=16 && op!=17 && op!=18 && op!=81 && op!=82)return LC_SOURCE;
    }
    if(table>31 || bindings!=(kind==1?2u:1u) || (producer[table]&127)!=19 || position[table]>=table_position ||
       provider>255 || !lcm_closure(raw,&detail,provider_word,0,&provider_child))return LC_SOURCE;
    bindings=0;
    for(i=0;i<provider_child.upvalues;++i)if(raw[provider_child.descriptors+i*3]==1 &&
        raw[provider_child.descriptors+i*3+1]==table && raw[provider_child.descriptors+i*3+2]==0)++bindings;
    if(bindings!=1)return LC_SOURCE;
    if(kind==2) {
        if(!create.upvalues)return LC_SOURCE;
        for(i=0;i<create.upvalues;++i) {
            const BYTE *descriptor=raw+create.descriptors+i*3;unsigned reg=descriptor[1];
            if(descriptor[0]!=1 || descriptor[2]!=0 || !lcm_closure(raw,&detail,producer[reg],1,&child))continue;
            if(!lcm_details(raw,size,&child,&resend_detail))return LC_SOURCE;
            if(lcm_key(&resend_detail,"GetContentPlainText")<0 || lcm_key(&resend_detail,"GetChannel")<0 ||
               lcm_key(&resend_detail,"TransformEmojiRichTextBack")<0 || lcm_key(&resend_detail,"ChatSendMessage")<0)continue;
            if(resend_register!=256 || reg>31)return LC_SOURCE;
            resend_register=reg;slot=i+1;
        }
        if(resend_register==256 || !slot)return LC_SOURCE;
    }
    ZeroMemory(layout,sizeof(*layout));layout->methods=table+1;
    a=table;if(kind==2){layout->resend=resend_register+1;layout->upvalue=slot;if(resend_register>a)a=resend_register;}
    /* The internal results are consumed only by finish(); its public module
       return stays zero. All 4-byte instructions except this return survive. */
    word=70u|(1u<<15)|((a+2u)<<16)|(1u<<24);
    memcpy(raw+detail.code+(SIZE_T)(detail.count-1)*4,&word,4);return LC_OK;
}
