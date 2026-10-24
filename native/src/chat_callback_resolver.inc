/* Developer chat bridge APIs. Derive the push function from the validated
   interface; discover three remaining ordinary APIs in executable sections.
   Cached addresses are hints and never replace full ABI/call-edge validation. */
#include "chat_callback_bind.h"
#include "chat_callback_signatures.h"
typedef const char *(*LcrPushString)(void *,const char *,SIZE_T);
typedef struct LcrApis {
    LcbApi bind;
    LcoStringLengthFn tostring;
    LcrPushString pushstring;
    DWORD setup,check,string;
} LcrApis;
typedef struct LcrCandidates {const BYTE *address[3];unsigned count[3];} LcrCandidates;
static BOOL lcr_scan(const ImageView *view,const BYTE *live,const BYTE *copy,SIZE_T size,void *opaque) {
    LcrCandidates *found=(LcrCandidates *)opaque;SIZE_T pos;unsigned i;
    const BYTE *bytes[3]={lcr_setup_bytes,lcr_check_bytes,lcr_string_bytes};
    const BYTE *masks[3]={lcr_setup_mask,lcr_check_mask,lcr_string_mask};
    const SIZE_T lengths[3]={sizeof(lcr_setup_bytes),sizeof(lcr_check_bytes),sizeof(lcr_string_bytes)};
    (void)view;
    for(pos=0;pos<size;++pos)for(i=0;i<3;++i) {
        if(copy[pos]!=bytes[i][0] || lengths[i]>size-pos ||
           !masked_match(copy+pos,bytes[i],masks[i],lengths[i]))continue;
        if(found->address[i]==live+pos)continue; /* Section-scan overlap. */
        ++found->count[i];found->address[i]=live+pos;
    }
    return TRUE;
}
static DWORD lcr_resolve(const ImageView *view,const LcoResult *binding,LcrApis *output,BOOL hints_only) {
    const BYTE *push=NULL,*wrapper,*candidate,*type_target,*indexer,*grow;unsigned slot,matches=0;
    LcoKindFn kind;LcoStringLengthFn string_length;void *target;LcrCandidates found;DWORD error;
    LcrApis result;
    if(!view || !binding || !output)return ERROR_INVALID_PARAMETER;
    error=lco_type_resolve(view,binding,&kind,&string_length,&target);if(error)return error;
    type_target=(const BYTE *)target;indexer=relative_target(type_target+4);
    if(!executable(view,indexer))return ERROR_INVALID_FUNCTION;
    for(slot=0;slot<binding->slots;++slot) {
        if(!read_exact(view->base+binding->table+slot*8,&wrapper,8))return ERROR_NOACCESS;
        if(!signature_at(view,wrapper,lcr_push_wrapper_bytes,lcr_push_wrapper_mask,sizeof(lcr_push_wrapper_bytes)))continue;
        candidate=relative_target(wrapper+12);
        if(!candidate || !signature_at(view,candidate,lcr_push_bytes,lcr_push_mask,sizeof(lcr_push_bytes)))continue;
        push=candidate;++matches;
    }
    if(matches!=1)return matches?ERROR_DUP_NAME:ERROR_NOT_FOUND;
    ZeroMemory(&found,sizeof(found));
    if(output->setup && output->setup<view->size && output->check && output->check<view->size &&
       output->string && output->string<view->size &&
       signature_at(view,view->base+output->setup,lcr_setup_bytes,lcr_setup_mask,sizeof(lcr_setup_bytes)) &&
       signature_at(view,view->base+output->check,lcr_check_bytes,lcr_check_mask,sizeof(lcr_check_bytes)) &&
       signature_at(view,view->base+output->string,lcr_string_bytes,lcr_string_mask,sizeof(lcr_string_bytes))) {
        found.address[0]=view->base+output->setup;found.address[1]=view->base+output->check;
        found.address[2]=view->base+output->string;found.count[0]=found.count[1]=found.count[2]=1;
    } else {
        if(hints_only)return ERROR_NOT_FOUND;
        error=scan_executable(view,lcr_scan,&found);if(error)return error;
    }
    for(slot=0;slot<3;++slot)if(found.count[slot]!=1)return found.count[slot]?ERROR_DUP_NAME:ERROR_NOT_FOUND;
    if(relative_target(found.address[0]+12)!=indexer ||
       relative_target(found.address[2]+75)!=relative_target(push+173))return ERROR_INVALID_FUNCTION;
    grow=relative_target(found.address[1]+97);
    if(!grow || !signature_at(view,grow,lcr_grow_bytes,lcr_grow_mask,sizeof(lcr_grow_bytes)))return ERROR_INVALID_FUNCTION;
    ZeroMemory(&result,sizeof(result));
    result.bind.gettop=(int (*)(void *))(uintptr_t)relative_target(binding->functions[LCO_GETTOP]+k_lco_signatures[LCO_GETTOP].branch_offset);
    result.bind.type=(int (*)(void *,int))(uintptr_t)type_target;
    result.bind.checkstack=(int (*)(void *,int))(uintptr_t)found.address[1];
    result.bind.pushcclosure=(void (*)(void *,LcbFunction,int))(uintptr_t)push;
    result.bind.setupvalue=(const char *(*)(void *,int,int))(uintptr_t)found.address[0];
    result.bind.settop=(void (*)(void *,int))(uintptr_t)relative_target(binding->functions[LCO_POP]+k_lco_signatures[LCO_POP].branch_offset);
    result.tostring=string_length;result.pushstring=(LcrPushString)(uintptr_t)found.address[2];
    result.setup=(DWORD)(found.address[0]-view->base);result.check=(DWORD)(found.address[1]-view->base);result.string=(DWORD)(found.address[2]-view->base);
    *output=result;return ERROR_SUCCESS;
}
