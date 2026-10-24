/* Personal API key, DPAPI CurrentUser; no plaintext key file or content logs. */
#include <wincrypt.h>
static DWORD cd_load_key(unsigned provider,WCHAR *authorization,SIZE_T capacity,BOOL *free_api) {
    const char *entropy_text=provider==CQ_GEMINI?"WOJD-CHAT-KEY-V2:gemini":provider==CQ_DEEPSEEK?"WOJD-CHAT-KEY-V2:deepseek":"WOJD-CHAT-KEY-V1";
    const WCHAR *filename=provider==CQ_GEMINI?L"chat-key-gemini.bin":provider==CQ_DEEPSEEK?L"chat-key-deepseek.bin":L"chat-key-deepl.bin";
    unsigned header=provider==CQ_DEEPL?5u:6u;
    WCHAR path[1024];BYTE bytes[4096];DATA_BLOB input,entropy,clear={0};
    HANDLE file;DWORD attributes,size,got,error=ERROR_SUCCESS;unsigned i;
    if(_snwprintf_s(path,1024,_TRUNCATE,L"%s\\%s",g_root_path,filename)<0)return ERROR_FILENAME_EXCED_RANGE;
    attributes=GetFileAttributesW(path);
    if(attributes==INVALID_FILE_ATTRIBUTES&&GetLastError()==ERROR_FILE_NOT_FOUND) {
        /* Explicit legacy-file migration only; the provider binding below
           prevents a saved key being sent to a different service. */
        if(_snwprintf_s(path,1024,_TRUNCATE,L"%s\\chat-key.bin",g_root_path)<0)return ERROR_FILENAME_EXCED_RANGE;
        attributes=GetFileAttributesW(path);
    }
    if(attributes==INVALID_FILE_ATTRIBUTES)return GetLastError();
    if(attributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))return ERROR_INVALID_DATA;
    file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,NULL);
    if(file==INVALID_HANDLE_VALUE)return GetLastError();
    size=GetFileSize(file,NULL);
    if(size<6||size>sizeof(bytes)||!ReadFile(file,bytes,size,&got,NULL)||got!=size)error=ERROR_INVALID_DATA;
    CloseHandle(file);if(error)return error;
    if((header==5&&memcmp(bytes,"WJDK1",5))||(header==6&&(memcmp(bytes,"WJDK2",5)||bytes[5]!=(BYTE)('0'+provider)))){SecureZeroMemory(bytes,sizeof(bytes));return ERROR_INVALID_DATA;}
    input.pbData=bytes+header;input.cbData=size-header;entropy.pbData=(BYTE *)entropy_text;entropy.cbData=(DWORD)strlen(entropy_text);
    if(!CryptUnprotectData(&input,NULL,&entropy,NULL,NULL,CRYPTPROTECT_UI_FORBIDDEN,&clear))error=GetLastError();
    SecureZeroMemory(bytes,sizeof(bytes));if(error)return error;
    if(clear.cbData<16||clear.cbData>256||capacity<clear.cbData+32)error=ERROR_INVALID_DATA;
    if(!error)for(i=0;i<clear.cbData;++i)if(clear.pbData[i]<=32||clear.pbData[i]>=127){error=ERROR_INVALID_DATA;break;}
    if(!error) {
        const WCHAR *prefix=provider==CQ_GEMINI?L"x-goog-api-key: ":provider==CQ_DEEPSEEK?L"Authorization: Bearer ":L"Authorization: DeepL-Auth-Key ";SIZE_T n=wcslen(prefix);
        memcpy(authorization,prefix,n*sizeof(WCHAR));
        for(i=0;i<clear.cbData;++i)authorization[n+i]=(WCHAR)clear.pbData[i];
        authorization[n+clear.cbData]=L'\r';authorization[n+clear.cbData+1]=L'\n';authorization[n+clear.cbData+2]=0;
        *free_api=clear.cbData>=3&&!memcmp(clear.pbData+clear.cbData-3,":fx",3);
    }
    SecureZeroMemory(clear.pbData,clear.cbData);LocalFree(clear.pbData);return error;
}
