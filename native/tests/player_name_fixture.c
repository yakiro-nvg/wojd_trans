/* Local character readings and rich-label isolation, no game or network. */
#include <windows.h>
#include <stdio.h>
#include "../src/player_names.h"
static unsigned checks;
#define CHECK(x) do {++checks;if(!(x)){printf("FAIL name check=%u line=%d\n",checks,__LINE__);return 1;}}while(0)
int main(void) {
    char out[8192];size_t n=0;CwSpan name,prefix;unsigned i;const char *raw;
    name.data="张三";name.size=strlen(name.data);
    CHECK(pn_convert(name,out,sizeof(out),&n));out[n]=0;CHECK(!strcmp(out,"Trương Tam"));
    name.data="陆雪琪";name.size=strlen(name.data);CHECK(pn_convert(name,out,sizeof(out),&n));out[n]=0;CHECK(!strcmp(out,"Lục Tuyết Kỳ"));
    name.data="爱吃红枣粽子";name.size=strlen(name.data);CHECK(pn_convert(name,out,sizeof(out),&n));out[n]=0;CHECK(!strcmp(out,"Ái Cật Hồng Tảo Tống Tử"));
    name.data="忘川不渡";name.size=strlen(name.data);CHECK(pn_convert(name,out,sizeof(out),&n));out[n]=0;CHECK(!strcmp(out,"Vong Xuyên Bất Độ"));
    name.data="张A007三";name.size=strlen(name.data);CHECK(pn_convert(name,out,sizeof(out),&n));out[n]=0;CHECK(!strcmp(out,"Trương A007 Tam"));
    name.data="Tên Việt007";name.size=strlen(name.data);CHECK(!pn_convert(name,out,sizeof(out),&n));
    name.data="张三";name.size=strlen(name.data);CHECK(!pn_convert(name,out,2,&n));
    prefix.data="<a type='playerName' text='张三' XID='123456789'>张三</>: ";prefix.size=strlen(prefix.data);
    CHECK(pn_prefix(name,prefix,out,sizeof(out),&n));out[n]=0;
    CHECK(strstr(out,"text='张三' XID='123456789'>Trương Tam</>")!=NULL);
    prefix.data="<a type='playerName' text='张三' XID='123456789'></>: ";prefix.size=strlen(prefix.data);
    CHECK(pn_prefix(name,prefix,out,sizeof(out),&n));out[n]=0;
    CHECK(strstr(out,"text='张三' XID='123456789'></>:  【Trương Tam】")!=NULL);
    prefix.data="<a text='unterminated";prefix.size=strlen(prefix.data);CHECK(!pn_prefix(name,prefix,out,sizeof(out),&n));
    raw="\xed\xa0\x80";name.data=raw;name.size=3;CHECK(!pn_convert(name,out,sizeof(out),&n));
    name.data="张三<bad>";name.size=strlen(name.data);CHECK(pn_reading(name,out,sizeof(out),&n));out[n]=0;
    CHECK(!strcmp(out,"Trương Tam‹bad›"));
    name.data="Tên Việt007";name.size=strlen(name.data);CHECK(pn_reading(name,out,sizeof(out),&n));out[n]=0;
    CHECK(!strcmp(out,"Tên Việt007"));
    prefix.data="Cảm ơn <a module='Chat' type='playerName' XID='123' style='PC_Name' text='轻鸿'></>~";prefix.size=strlen(prefix.data);
    CHECK(pn_links(prefix,out,sizeof(out),&n));out[n]=0;
    CHECK(strstr(out,"XID='123' style='PC_Name' text='轻鸿'></> 【Khinh Hồng】~")!=NULL);
    prefix.data="<a type='itemslot' text='轻鸿'></>";prefix.size=strlen(prefix.data);CHECK(!pn_links(prefix,out,sizeof(out),&n));
    prefix.data="<a type='playerName' text='Tom'></>";prefix.size=strlen(prefix.data);CHECK(!pn_links(prefix,out,sizeof(out),&n));
    prefix.data="<a type='playerName' text='张三' text='李四'></>";prefix.size=strlen(prefix.data);CHECK(!pn_links(prefix,out,sizeof(out),&n));
    for(i=0;i<sizeof(pn_readings)/sizeof(pn_readings[0]);++i){CHECK(!i||pn_readings[i-1].codepoint<pn_readings[i].codepoint);CHECK(pn_lookup(pn_readings[i].codepoint)==(const char *)pn_text+pn_readings[i].offset);}
    printf("PASS local player-name fixture checks=%u readings=%u, no network\n",checks,(unsigned)(sizeof(pn_readings)/sizeof(pn_readings[0])));return 0;
}
