"""Explicitly started, authenticated loopback service for the native bridge.

No HTTP or model work runs on the game's Lua/UI thread. Request bodies and
translations are kept only in bounded memory; HTTP access logging is disabled.
"""
from __future__ import annotations
import argparse
from collections import OrderedDict
from dataclasses import dataclass
import hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import os,re,threading,time
from pathlib import Path
from .core import ChatService,MAX_MESSAGE_CHARS
from .native_wire import Packet,WireError,encode,decode,MAX_PACKET
from .service import load_provider
from .providers import TranslationError

@dataclass
class _Record:
    packet: Packet
    event: str
    expires: float
    status: int = 1
    translation: str = ""

class NativeJobs:
    def __init__(self,provider,*,limit=32,ttl=30):
        if not 1<=limit<=32 or not 0<ttl<=60:raise ValueError("INVALID_BOUNDS")
        self.service=ChatService(provider,max_pending=limit,cache_size=256)
        self.limit,self.ttl=limit,ttl
        self.lock=threading.Lock();self.records=OrderedDict();self.events={}

    def _collect(self):
        now=time.monotonic()
        for key in [key for key,row in self.records.items() if row.expires<=now]:
            row=self.records.pop(key);self.events.pop(row.event,None)
        for event in self.service.poll():
            key=self.events.get(event.id);row=self.records.get(key)
            if row is None or row.packet.source!=event.original:continue
            if event.status=="TRANSLATED":row.status,row.translation=2,event.translation
            elif event.status in ("ERROR","SKIPPED"):row.status=3

    def exchange(self,packet):
        if packet.code not in (1,2) or len(packet.source)>MAX_MESSAGE_CHARS:
            raise WireError("INVALID_REQUEST")
        key=(packet.session,packet.occurrence)
        with self.lock:
            self._collect();row=self.records.get(key)
            if row is not None:
                if row.packet.source!=packet.source:raise WireError("OCCURRENCE_CONFLICT")
            elif packet.code==1 and sum(row.status==1 for row in self.records.values())<self.limit:
                while len(self.records)>=128:
                    oldest=next((key for key,row in self.records.items() if row.status!=1),None)
                    if oldest is None:break
                    retired=self.records.pop(oldest);self.events.pop(retired.event,None)
                event=self.service.submit(packet.source,source_language='zh-Hans',target_language='vi',direction='incoming')
                if event is not None:
                    row=_Record(packet,event,time.monotonic()+self.ttl)
                    self.records[key]=row;self.events[event]=key
            if row is None:return Packet(3,packet.session,packet.occurrence,packet.source)
            return Packet(row.status,packet.session,packet.occurrence,packet.source,row.translation)

    def purge(self):
        with self.lock:self._collect()

    def close(self):
        self.service.close()
        with self.lock:self.records.clear();self.events.clear()

class NativeHTTPServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=False
    def __init__(self,port,provider,token,**options):
        if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{64}',token):raise ValueError('TOKEN_REQUIRED')
        if type(port) is not int or not 1<=port<=65535:raise ValueError('PORT_REQUIRED')
        self.token=token;self.jobs=NativeJobs(provider,**options)
        try:super().__init__(('127.0.0.1',port),NativeHandler)
        except BaseException:self.jobs.close();raise
        self.slots=threading.BoundedSemaphore(8)
    def get_request(self):
        request,address=super().get_request();request.settimeout(2);return request,address
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):request.close();return
        try:super().process_request(request,address)
        except BaseException:self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()
    def service_actions(self):self.jobs.purge()
    def server_close(self):
        super().server_close();self.jobs.close()

class NativeHandler(BaseHTTPRequestHandler):
    server_version='WOJDChat';sys_version='';protocol_version='HTTP/1.0'
    def log_message(self,*args):pass
    def _reply(self,status,body=b''):
        self.close_connection=True;self.send_response(status)
        self.send_header('Content-Type','application/octet-stream')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('Connection','close')
        self.end_headers();self.wfile.write(body)
    def send_error(self,code,message=None,explain=None):self._reply(code)
    def do_POST(self):
        try:
            if self.headers.get_all('Origin') or self.headers.get_all('Transfer-Encoding'):self._reply(403);return
            if self.headers.get_all('Host')!=[f'127.0.0.1:{self.server.server_port}']:self._reply(403);return
            auth=self.headers.get_all('Authorization',[])
            if len(auth)!=1 or not auth[0].isascii() or not hmac.compare_digest(auth[0],'Bearer '+self.server.token):self._reply(401);return
            if self.path!='/v1/exchange':self._reply(404);return
            length=self.headers.get_all('Content-Length',[])
            if len(length)!=1 or not re.fullmatch('[0-9]{1,6}',length[0]) or not 44<=int(length[0])<=MAX_PACKET:self._reply(413);return
            if self.headers.get_all('Content-Type')!=['application/octet-stream']:self._reply(415);return
            raw=self.rfile.read(int(length[0]))
            if len(raw)!=int(length[0]):self._reply(400);return
            packet=decode(raw)
            self._reply(200,encode(self.server.jobs.exchange(packet),response=True))
        except WireError:self._reply(400)
        except (TimeoutError,OSError):self.close_connection=True
        except Exception:self._reply(500)
    def do_GET(self):self._reply(405)
    do_OPTIONS=do_GET

def main(argv=None):
    parser=argparse.ArgumentParser(description='Run the local incoming-chat bridge.')
    parser.add_argument('--settingspath',type=Path,required=True);parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args(argv)
    try:server=NativeHTTPServer(args.port,load_provider(args.settingspath),os.environ.get('WOJD_CHAT_SERVICE_TOKEN',''))
    except (OSError,ValueError,TranslationError):parser.exit(2,'Local chat bridge configuration is invalid.\n')
    try:server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
