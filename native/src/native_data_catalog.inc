/* Generic field/source dictionary. Binary framing is generated from editable JSON. */
typedef struct TextField { const char *name;DWORD length; } TextField;
typedef struct TextRule { DWORD field,source_length,target_length;const char *source,*target; } TextRule;
typedef struct TextCatalog { BYTE *data;TextField *fields;TextRule *rules;DWORD field_count,rule_count; } TextCatalog;
static TextCatalog g_catalog;
static BOOL catalog_u32(const BYTE **cursor,const BYTE *end,DWORD *value) {
    if((SIZE_T)(end-*cursor)<4)return FALSE;memcpy(value,*cursor,4);*cursor+=4;return TRUE;
}
static BOOL catalog_string(const BYTE **cursor,const BYTE *end,const char **text,DWORD *length,DWORD maximum) {
    if(!catalog_u32(cursor,end,length) || !*length || *length>maximum || (SIZE_T)(end-*cursor)<(SIZE_T)*length+1)return FALSE;
    if((*cursor)[*length]!=0 || memchr(*cursor,0,*length) || !MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,(const char *)*cursor,(int)*length,NULL,0))return FALSE;
    *text=(const char *)*cursor;*cursor+=(SIZE_T)*length+1;return TRUE;
}
static BOOL catalog_target(const BYTE **cursor,const BYTE *end,const char **text,DWORD *length) {
    const BYTE *start=*cursor;
    if(!catalog_u32(cursor,end,length))return FALSE;
    if(!*length) {
        if(*cursor==end || **cursor!=0)return FALSE;
        *text=(const char *)*cursor;(*cursor)++;return TRUE;
    }
    *cursor=start;return catalog_string(cursor,end,text,length,65535);
}
static int text_compare(const char *left,SIZE_T ln,const char *right,SIZE_T rn) {
    SIZE_T common=ln<rn?ln:rn;int result=memcmp(left,right,common);
    return result?result:(ln<rn?-1:(ln>rn?1:0));
}
static void catalog_free(TextCatalog *catalog) {
    if(catalog->rules)HeapFree(GetProcessHeap(),0,catalog->rules);
    if(catalog->fields)HeapFree(GetProcessHeap(),0,catalog->fields);
    if(catalog->data)HeapFree(GetProcessHeap(),0,catalog->data);
    ZeroMemory(catalog,sizeof(*catalog));
}
static DWORD catalog_load(const WCHAR *path) {
    TextCatalog next;HANDLE file;LARGE_INTEGER size;DWORD got,i,j,error=ERROR_INVALID_DATA;
    const BYTE *cursor,*end;
    if(g_active)return ERROR_INVALID_STATE;
    ZeroMemory(&next,sizeof(next));
    file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE)return GetLastError();
    if(!GetFileSizeEx(file,&size) || size.QuadPart<16 || size.QuadPart>128u*1024u*1024u){CloseHandle(file);return ERROR_INVALID_DATA;}
    next.data=(BYTE *)HeapAlloc(GetProcessHeap(),0,(SIZE_T)size.QuadPart);
    if(!next.data){CloseHandle(file);return ERROR_NOT_ENOUGH_MEMORY;}
    if(!ReadFile(file,next.data,(DWORD)size.QuadPart,&got,NULL) || got!=(DWORD)size.QuadPart){CloseHandle(file);catalog_free(&next);return ERROR_READ_FAULT;}
    CloseHandle(file);cursor=next.data;end=cursor+(SIZE_T)size.QuadPart;
    if(memcmp(cursor,"WJTXT2\r\n",8))goto fail;cursor+=8;
    if(!catalog_u32(&cursor,end,&next.field_count) || !catalog_u32(&cursor,end,&next.rule_count) ||
       !next.field_count || next.field_count>4096 || next.rule_count>300000)goto fail;
    next.fields=(TextField *)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,next.field_count*sizeof(TextField));
    next.rules=(TextRule *)HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,(next.rule_count?next.rule_count:1)*sizeof(TextRule));
    if(!next.fields || !next.rules){error=ERROR_NOT_ENOUGH_MEMORY;goto fail;}
    for(i=0;i<next.field_count;i++) {
        if(!catalog_string(&cursor,end,&next.fields[i].name,&next.fields[i].length,63))goto fail;
        for(j=0;j<next.fields[i].length;j++) {
            unsigned char ch=(unsigned char)next.fields[i].name[j];
            if(!(ch=='_' || (ch>='A' && ch<='Z') || (ch>='a' && ch<='z') || (j && ch>='0' && ch<='9')))goto fail;
        }
        if(i && strcmp(next.fields[i-1].name,next.fields[i].name)>=0)goto fail;
    }
    for(i=0;i<next.rule_count;i++) {
        TextRule *rule=&next.rules[i];
        if(!catalog_u32(&cursor,end,&rule->field) || rule->field>=next.field_count ||
           !catalog_string(&cursor,end,&rule->source,&rule->source_length,65535) ||
           !catalog_target(&cursor,end,&rule->target,&rule->target_length))goto fail;
        if(i && (next.rules[i-1].field>rule->field || (next.rules[i-1].field==rule->field &&
           text_compare(next.rules[i-1].source,next.rules[i-1].source_length,rule->source,rule->source_length)>=0)))goto fail;
    }
    if(cursor!=end)goto fail;
    catalog_free(&g_catalog);g_catalog=next;
    logf_n4("CATALOG_LOADED","fields=%lu rules=%lu bytes=%llu",next.field_count,next.rule_count,(ULONGLONG)size.QuadPart);
    return ERROR_SUCCESS;
fail:catalog_free(&next);return error;
}
static DWORD catalog_field(const char *name) {
    DWORD low=0,high=g_catalog.field_count;
    while(low<high) {
        DWORD mid=low+(high-low)/2;int cmp=strcmp(name,g_catalog.fields[mid].name);
        if(!cmp)return mid;if(cmp<0)high=mid;else low=mid+1;
    }
    return MAXDWORD;
}
static const TextRule *catalog_lookup(DWORD field,const char *source,SIZE_T length) {
    DWORD low=0,high=g_catalog.rule_count;
    while(low<high) {
        DWORD mid=low+(high-low)/2;const TextRule *rule=&g_catalog.rules[mid];
        int cmp=field<rule->field?-1:(field>rule->field?1:text_compare(source,length,rule->source,rule->source_length));
        if(!cmp)return rule;if(cmp<0)high=mid;else low=mid+1;
    }
    return NULL;
}
