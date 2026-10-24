#ifndef WOJD_LUA_ENVELOPE_H
#define WOJD_LUA_ENVELOPE_H
#include <stddef.h>
enum { LC_OK=0,LC_ARGUMENT=1,LC_FORMAT=2,LC_LIMIT=3,LC_SOURCE=4,LC_TEMPLATE=5,LC_BUFFER=6 };
/* Inputs are owned readable buffers. Output must not overlap either input.
   A NULL output queries the required size. No Lua API is invoked. */
int lc_envelope(const unsigned char *,size_t,const unsigned char *,size_t,
                unsigned char *,size_t,size_t *);
/* Explicit two-upvalue adapter template: _ENV first, native callback second.
   The caller must bind upvalue 2 before allowing the module to execute. */
int lc_callback_envelope(const unsigned char *,size_t,const unsigned char *,size_t,
                         unsigned char *,size_t,size_t *);
#endif
