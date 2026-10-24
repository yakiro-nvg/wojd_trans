"""Rebuild owned adapter bytecode with a public Lua 5.4 DLL, never game Lua.

Developer tool only. Player/CI builds consume the committed, source-pinned
header. --check verifies a local Lua compiler reproduces that header exactly.
"""
import argparse
import ctypes as c
import hashlib
import pathlib
import struct

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER = b'\x1bLua\x54\0\x19\x93\r\n\x1a\n\x04\x08\x08' + struct.pack('<qd', 0x5678, 370.5)

def root_descriptors(data):
    """Locate only our compiler's root captures; runtime fully parses chunks."""
    assert data.startswith(HEADER) and data[len(HEADER)] == 2
    p = len(HEADER) + 1
    def take(n):
        nonlocal p
        assert 0 <= n <= len(data) - p
        result = data[p:p+n]
        p += n
        return result
    def integer():
        value = 0
        for _ in range(5):
            part = take(1)[0]
            value = (value << 7) | (part & 127)
            assert value <= 0x7fffffff
            if part & 128:
                return value
        raise ValueError('Invalid compiler output')
    def string():
        n = integer()
        if n:
            take(n-1)
    string()
    integer(); integer()
    assert take(3)[:2] == b'\0\x01'
    take(integer()*4)
    for _ in range(integer()):
        tag = take(1)[0]
        if tag in (0, 1, 17):
            pass
        elif tag in (3, 19):
            take(8)
        elif tag in (4, 20):
            string()
        else:
            raise ValueError('Unexpected compiler constant')
    assert integer() == 2
    return p

def generate(lua_path):
    lua = c.CDLL(str(lua_path))
    def bind(name, result, args):
        f = getattr(lua, name)
        f.restype, f.argtypes = result, args
        return f
    new = bind('luaL_newstate', c.c_void_p, [])
    close = bind('lua_close', None, [c.c_void_p])
    load = bind('luaL_loadbufferx', c.c_int, [c.c_void_p,c.c_char_p,c.c_size_t,c.c_char_p,c.c_char_p])
    call = bind('lua_pcallk', c.c_int, [c.c_void_p,c.c_int,c.c_int,c.c_int,c.c_ssize_t,c.c_void_p])
    upvalue = bind('lua_getupvalue', c.c_char_p, [c.c_void_p,c.c_int,c.c_int])
    settop = bind('lua_settop', None, [c.c_void_p,c.c_int])
    Writer = c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_size_t,c.c_void_p)
    dump = bind('lua_dump', c.c_int, [c.c_void_p,Writer,c.c_void_p,c.c_int])
    source = (ROOT/'native/src/chat_receive_rows.lua').read_bytes()
    lines = ['/* Generated from chat_receive_rows.lua; scripts/compile_chat_templates.py. */',
             '/* source-sha256: '+hashlib.sha256(source).hexdigest()+' */']
    for mode in ('item', 'scroll'):
        state = new()
        assert state
        parts = []
        @Writer
        def write(state, pointer, size, opaque):
            parts.append(c.string_at(pointer, size))
            return 0
        try:
            text = source.replace(b'__WOJD_MODULE_MODE__', mode.encode())
            assert load(state,text,len(text),b'@wojd-chat-adapter.lua',b't') == 0
            assert call(state,0,1,0,0,None) == 0  # Execute only our factory.
            assert upvalue(state,-1,1) == b'_ENV'
            settop(state,1)
            assert upvalue(state,-1,2) == b'native'
            settop(state,1)
            assert dump(state,write,None,1) == 0
        finally:
            close(state)
        template = bytearray(b''.join(parts))
        start = root_descriptors(template)
        template[start:start+6] = b'\x01\0\0\x01\x01\0'
        lines.append('static const unsigned char lcr_'+mode+'_template[]={')
        lines.extend(','.join('0x%02x'%b for b in template[i:i+20])+',' for i in range(0,len(template),20))
        lines.append('};')
    return '\n'.join(lines)+'\n'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lua', required=True, type=pathlib.Path, help='Owned public Windows Lua 5.4 DLL, never a game DLL')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = generate(args.lua.resolve())
    destination = ROOT/'native/src/chat_receive_templates.h'
    if args.check:
        assert destination.read_text(encoding='utf-8') == result, 'Recompile committed chat adapter templates'
    else:
        destination.write_text(result, encoding='utf-8', newline='\n')
    print('PASS: owned Lua adapter templates match canonical source')
