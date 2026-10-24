"""Bounded binary transport for the native incoming-chat bridge.

All text is copied UTF-8. No Lua objects, pointers, file paths or game send
operations are carried by this protocol. Identity includes a fresh session and
an occurrence ID; equal source text is never an occurrence identifier.
"""
from dataclasses import dataclass
import re
import struct

MAX_SOURCE = 16000
MAX_TRANSLATION = 64000
MAX_PACKET = 80100
_SESSION = re.compile(r"[0-9a-f]{32}\Z")
_ID = re.compile(r"[1-9][0-9]{0,19}\Z")

class WireError(ValueError):
    pass

@dataclass(frozen=True)
class Packet:
    code: int
    session: str
    occurrence: str
    source: str
    translation: str = ""

def encode(packet: Packet, *, response=False):
    if (not isinstance(packet, Packet) or type(packet.code) is not int
            or packet.code not in ((1,2,3) if response else (1,2))
            or not isinstance(packet.session,str) or not isinstance(packet.occurrence,str)
            or not _SESSION.fullmatch(packet.session) or not _ID.fullmatch(packet.occurrence)):
        raise WireError("INVALID_IDENTITY")
    try:
        source = packet.source.encode("utf-8")
        translation = packet.translation.encode("utf-8")
    except (UnicodeError,AttributeError):
        raise WireError("INVALID_TEXT") from None
    if (not 0 < len(source) <= MAX_SOURCE or b"\0" in source
            or len(translation)>MAX_TRANSLATION or b"\0" in translation
            or (not response and translation)
            or (response and ((packet.code == 2) != bool(translation)))):
        raise WireError("INVALID_TEXT")
    identity=packet.occurrence.encode("ascii")
    result=(b"WJR1" if response else b"WJC1")+bytes([packet.code])+packet.session.encode("ascii")
    result+=struct.pack("<H",len(identity))+identity+struct.pack("<I",len(source))+source
    if response:result+=struct.pack("<I",len(translation))+translation
    return result

def decode(raw: bytes, *, response=False):
    if not isinstance(raw,bytes) or not 44 <= len(raw) <= MAX_PACKET:
        raise WireError("INVALID_PACKET")
    if raw[:4] != (b"WJR1" if response else b"WJC1"):
        raise WireError("INVALID_VERSION")
    try:
        code=raw[4];session=raw[5:37].decode("ascii");count=struct.unpack_from("<H",raw,37)[0]
        if not 1<=count<=20:raise WireError("INVALID_IDENTITY")
        end=39+count;occurrence=raw[39:end].decode("ascii")
        count=struct.unpack_from("<I",raw,end)[0];end+=4
        if not 1<=count<=MAX_SOURCE or end+count>len(raw):raise WireError("INVALID_TEXT")
        source=raw[end:end+count].decode("utf-8");end+=count;translation=""
        if response:
            count=struct.unpack_from("<I",raw,end)[0];end+=4
            if count>MAX_TRANSLATION or end+count>len(raw):raise WireError("INVALID_TEXT")
            translation=raw[end:end+count].decode("utf-8");end+=count
        if end!=len(raw):raise WireError("TRAILING_BYTES")
        packet=Packet(code,session,occurrence,source,translation)
        if encode(packet,response=response)!=raw:raise WireError("NONCANONICAL_PACKET")
        return packet
    except (UnicodeError,struct.error,IndexError):
        raise WireError("INVALID_PACKET") from None
