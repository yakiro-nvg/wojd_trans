"""Actual owned Lua/C loader, cache, UI queue and synthetic HTTPS response."""
import ast,ctypes as c,hashlib,json,pathlib,re,tempfile,time,os
from ctypes import wintypes as w
from urllib.parse import parse_qs
import argparse,types
ROOT=pathlib.Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--lua',required=True,type=pathlib.Path,help='Owned public Lua 5.4 DLL; never a game DLL')
parser.add_argument('--fixture',type=pathlib.Path,default=ROOT/'native/build/runtime-test/chat_receive_fixture.dll')
parser.add_argument('--live-google',action='store_true',help='Send only these synthetic fixture strings to Google')
parser.add_argument('--names-only',action='store_true',help='Verify original names and links with cloud chat disabled')
options=parser.parse_args()
if options.names_only and options.live_google:parser.error('--names-only does not use a live translator')
HERE=ROOT/'work/chat-fixtures';HERE.mkdir(parents=True,exist_ok=True)
lua=c.CDLL(str(options.lua.resolve()))
def lua_bind(name,result,args):
 f=getattr(lua,name);f.restype=result;f.argtypes=args;return f
t=types.SimpleNamespace(lua=lua,bind=lua_bind)
t.newstate=lua_bind('luaL_newstate',c.c_void_p,[])
t.openlibs=lua_bind('luaL_openlibs',None,[c.c_void_p])
t.close=lua_bind('lua_close',None,[c.c_void_p])
t.load=lua_bind('luaL_loadbufferx',c.c_int,[c.c_void_p,c.c_char_p,c.c_size_t,c.c_char_p,c.c_char_p])
t.pcall=lua_bind('lua_pcallk',c.c_int,[c.c_void_p,c.c_int,c.c_int,c.c_int,c.c_ssize_t,c.c_void_p])
t.string=lua_bind('lua_tolstring',c.c_char_p,[c.c_void_p,c.c_int,c.c_void_p])
Writer=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_size_t,c.c_void_p)
dump=lua_bind('lua_dump',c.c_int,[c.c_void_p,Writer,c.c_void_p,c.c_int])
def compile_source(source,name):
 L=t.newstate();parts=[]
 @Writer
 def write(L,pointer,size,opaque):parts.append(c.string_at(pointer,size));return 0
 try:
  raw=source.encode('utf-8');assert t.load(L,raw,len(raw),name,b't')==0
  assert dump(L,write,None,0)==0;return b''.join(parts)
 finally:t.close(L)
t.compile_source=compile_source
parts={}
parts['BASE']=r'''
fixture_originals={};fixture_annotations={};fixture_sends={};fixture_bindings={};fixture_error={}
GameContext={HostData={},ChatLogManager={}}
function GameContext.ChatLogManager:AddMessageToListVerticalBox(scroll,channel,tag,prefix,text,system,flag,role)
 assert(system==true and flag==true and channel==1 and role==9223372036854775807)
 fixture_annotations[#fixture_annotations+1]={text=text,prefix=prefix};scroll.row.content=text
end
function SetObjectScript(object,event,callback,...)
 fixture_bindings[object]={callback=callback,args=table.pack(...)}
 if event=='OnUITimerNextTick' then object.callback=callback end
 return nil,'bound'
end
fixture_stock_setscript=SetObjectScript
function CreateUITimer()
 fixture_timer={SetTimerForNextTick=setmetatable({}, {__call=function(_,self)self.armed=true end})};return fixture_timer
end
function TransformEmojiRichTextBack(value)return value end
function ChatSendMessage(value,channel)assert(channel==1);fixture_sends[#fixture_sends+1]=value end
load=nil;getmetatable=nil;print=nil

GameContext.ChatLogManager.MessageItemLimit=64
fixture_scrolls=0;fixture_clears=0
'''
parts['SCROLL']=r'''
local function resend(widget)
 if widget.GetContentPlainText and widget.GetChannel then
  local value=widget:GetContentPlainText()
  value=TransformEmojiRichTextBack(value)
  ChatSendMessage(value,widget:GetChannel())
 end
 return nil,8
end
local methods={}
function methods.NewScrollBox(scroll,button)
 local row={Btn_AddOne={},content=''}
 function row:GetContentPlainText()return self.content end
 function row:GetChannel()return 1 end
 scroll.row=row
 SetObjectScript(row.Btn_AddOne,'OnClicked',resend,row)
 local handle
 scroll.height=0;scroll.offset=0;scroll.viewport=80
 function scroll:IsAtBottom()return self.offset>=math.max(0,self.height-self.viewport) end
 function scroll:CommitLayout()
  local height=0
  for _,item in ipairs(self.rows or {}) do height=height+#tostring(item.ContentText) end
  self.height=height
 end
 function scroll:Clear(flag)
  self.rows={};self.offset=0;fixture_clears=fixture_clears+1
  -- Clearing a live list can change the stock bottom flag synchronously.
  handle.bIsAtBottom=self:IsAtBottom()
 end
 function scroll:ScrollToBottom(flag)
  fixture_scrolls=fixture_scrolls+1;self.offset=math.max(0,self.height-self.viewport)
 end
 handle={Scroll=scroll,bIsAtBottom=true}
 function handle:UpdateButtonVisibility()end
 function handle:Reset(flag)self.bIsAtBottom=true;self.Scroll:Clear(flag);return nil,99 end
 function handle:TryScrollToEnd(force)if force or self.bIsAtBottom then self.Scroll:ScrollToBottom(false) end end
 return handle,nil,'tail'
end
function ProvideChatScrollBox()return methods end
fixture_cached_scroll=ProvideChatScrollBox
'''
parts['ITEM']=r'''
local methods={}
function methods.BuildChatMessageItem(channel,sender,body,system,role,title,extra,head)
 if body=='ERROR' then error(fixture_error,0) end
 return {ChannelEnum=channel,ChannelText='channel',Prefix=extra or sender..': ',ContentText=body,
   bIsSystem=system,RoleID=role,TextStyleSet='original-style'},nil,'tail'
end
function methods.AddItemToList(scroll,item,flag)
 fixture_originals[#fixture_originals+1]=item
 scroll.rows=scroll.rows or {};scroll.rows[#scroll.rows+1]=item
 if #scroll.rows>GameContext.ChatLogManager.MessageItemLimit then table.remove(scroll.rows,1) end
 scroll.row.content=item.ContentText;return nil,42
end
function ProvideChatMessageItem()return methods,nil,77 end
fixture_cached_item=ProvideChatMessageItem
'''
parts['HARNESS']=r'''
assert(SetObjectScript==fixture_stock_setscript)
ProvideChatMessageItem=function()error('must use cached provider')end
ProvideChatScrollBox=function()error('must use cached provider')end
fixture_methods=fixture_cached_item();fixture_scroll={}
fixture_handle=fixture_cached_scroll().NewScrollBox(fixture_scroll)
function fixture_receive(body,system,channel)
 local r=table.pack(fixture_methods.BuildChatMessageItem(channel or 1,'张三',body,system,9223372036854775807))
 assert(r.n==3 and r[2]==nil and r[3]=='tail')
 local a=table.pack(fixture_methods.AddItemToList(fixture_scroll,r[1],true))
 assert(a.n==2 and a[1]==nil and a[2]==42)
 fixture_last=r[1];return fixture_last
end
function fixture_tick()
 fixture_timer.callback()
 -- Rich text desired sizes commit after the UI callback, not within Add.
 fixture_scroll:CommitLayout()
end
function fixture_click()
 local b=fixture_bindings[fixture_scroll.row.Btn_AddOne]
 return b.callback(table.unpack(b.args,1,b.args.n))
end
function fixture_translated(item)
 return type(item.ContentText)=='string' and item.ContentText:find('\n----- [VI] -----\n',1,true)~=nil
end
fixture_tick()
'''
fixture=c.WinDLL(str(options.fixture.resolve()))
def bind(name,result,args):
 f=getattr(fixture,name);f.restype=result;f.argtypes=args;return f
prepare=bind('WojdChatReceiveFixturePrepare',w.DWORD,[c.c_wchar_p,c.c_void_p])
attach=bind('WojdChatReceiveFixtureBind',w.DWORD,[c.c_void_p,c.c_void_p,w.DWORD,w.DWORD,c.c_void_p,c.c_void_p])
invoke=bind('WojdChatReceiveFixtureLoad',c.c_int,[c.c_void_p,c.c_void_p,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p])
stats=bind('WojdChatReceiveFixtureStats',w.DWORD,[c.c_void_p,w.DWORD])
gstats=bind('WojdChatReceiveFixtureGoogleStats',w.DWORD,[c.c_void_p,w.DWORD])
transport=bind('WojdChatReceiveFixtureGoogleTransport',w.DWORD,[c.c_void_p])
stop=bind('WojdChatReceiveFixtureStop',w.DWORD,[])
settop=t.bind('lua_settop',None,[c.c_void_p,c.c_int]);gettop=t.bind('lua_gettop',c.c_int,[c.c_void_p])
Load=c.WINFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p)
Pop=c.WINFUNCTYPE(None,c.c_void_p,c.c_void_p,c.c_int)
Transport=c.CFUNCTYPE(w.DWORD,c.c_void_p,c.c_void_p,w.DWORD,c.c_void_p,c.POINTER(c.c_size_t),c.POINTER(w.DWORD))
checks=0;http_inputs=[];http_errors=[];behaviour='normal';LIVE=options.live_google
def check(value):
 global checks
 checks+=1;assert value,checks
@Transport
def fake_http(connection,form,size,out,written,status):
 try:
  request=c.string_at(form,size).decode('utf-8')
  if request.startswith('{'):
   data=json.loads(request)
   if 'contents' in data:
    segments=json.loads(data['contents'][0]['parts'][0]['text'])
    raw=json.dumps({'candidates':[{'content':{'parts':[{'text':json.dumps({'segments':['Gemini '+x for x in segments['segments']]})}]},'finishReason':'STOP'}]}).encode()
   else:
    segments=json.loads(data['messages'][-1]['content'])
    raw=json.dumps({'choices':[{'message':{'role':'assistant','content':json.dumps({'segments':['DeepSeek '+x for x in segments['segments']]})},'finish_reason':'stop'}]}).encode()
   http_inputs.append(request)
   assert 'Emoji22' not in request and 'itemslot' not in request
   c.memmove(out,raw,len(raw));written[0]=len(raw);status[0]=200;return 0
  protected=parse_qs(request,strict_parsing=True)['q'][0]
  assert 'module=' not in protected and 'Emoji' not in protected and 'itemslot' not in protected
  http_inputs.append(protected)
  if behaviour=='429':status[0]=429;written[0]=0;return 58
  text='Xin chào '+' '.join(re.findall(r'__WOJD_T\d{3}__',protected))
  if behaviour=='inject':text+=' <evil>new</>'
  if behaviour=='missing':text=text.replace('__WOJD_T000__','')
  raw=json.dumps([[[text,protected,None,None,1]],None,'zh-CN'],ensure_ascii=True).encode()
  c.memmove(out,raw,len(raw));written[0]=len(raw);status[0]=200;return 0
 except BaseException as error:
  http_errors.append(type(error).__name__);status[0]=500;written[0]=0;return 13
@Load
def load(self,state,pointer,size,name,mode):
 return t.load(state,c.string_at(pointer,size),size,c.string_at(name) if name else None,c.string_at(mode) if mode else None)
@Pop
def pop(self,state,count):settop(state,-count-1)
state=t.newstate();t.openlibs(state)
def run(source):
 raw=source.encode('utf-8');status=t.load(state,raw,len(raw),b'@owned-ordered-chat.lua',b't')
 if not status:status=t.pcall(state,0,0,0,0,None)
 if status:raise AssertionError((t.string(state,-1,None) or b'fixture error').decode(errors='replace'))
def snapshot():
 values=(w.LONG*8)();check(stats(values,8)==0);return list(values)
def google():
 values=(w.DWORD*7)();check(gstats(values,7)==0);return list(values)
def pump(count):
 until=time.monotonic()+12
 while time.monotonic()<until:
  run('fixture_tick()');values=snapshot()
  if values[2]+values[5]>=count:run('fixture_tick()');return
  time.sleep(.015)
 raise AssertionError('native fixture deadline exceeded')
def receive(text,system='false'):run('fixture_receive('+json.dumps(text,ensure_ascii=False)+','+system+')')
def synthetic_key(path,provider):
 # Windows DPAPI uses an explicitly synthetic value; no developer env/key is read.
 class Blob(c.Structure):_fields_=[('size',w.DWORD),('data',c.c_void_p)]
 key=b'synthetic-native-routing-fixture-key';entropy=('WOJD-CHAT-KEY-V2:'+provider).encode()
 a=c.create_string_buffer(key);b=c.create_string_buffer(entropy)
 source=Blob(len(key),c.cast(a,c.c_void_p));salt=Blob(len(entropy),c.cast(b,c.c_void_p));out=Blob()
 protect=c.WinDLL('crypt32').CryptProtectData
 protect.argtypes=[c.POINTER(Blob),c.c_void_p,c.POINTER(Blob),c.c_void_p,c.c_void_p,w.DWORD,c.POINTER(Blob)]
 check(protect(c.byref(source),None,c.byref(salt),None,None,1,c.byref(out))!=0)
 free=c.WinDLL('kernel32').LocalFree;free.argtypes=[c.c_void_p]
 try:path.write_bytes((b'WJDK25' if provider=='gemini' else b'WJDK24')+c.string_at(out.data,out.size))
 finally:c.memset(out.data,0,out.size);free(out.data)
link='<a where="100" module="Chat" type="itemslot" tmplID="555" text="Vật phẩm thử"></>'
emoji='<img module="Chat" type="Emoji" id="Emoji22"></>'
name_link="<a module='Chat' type='playerName' XID='123' style='PC_Name' text='轻鸿'></>"
A='你好 '+link+' '+emoji+' 50% '+name_link;B='你好 第二 '+emoji
try:
 with tempfile.TemporaryDirectory(dir=HERE) as directory:
  config='[chat]\nenabled=1\nprovider=google-web\ncache_entries=256\n[channel.squad]\nprovider=none\n'
  if not LIVE:
   config+='[channel.team]\nprovider=gemini\nmodel=gemini-3.6-flash\n[channel.gang]\nprovider=deepseek\nmodel=deepseek-flash\n'
   for provider in ('gemini','deepseek'):synthetic_key(pathlib.Path(directory)/('chat-key-'+provider+'.bin'),provider)
  if options.names_only:config='[chat]\nenabled=0\nprovider=none\n'
  (pathlib.Path(directory)/'chat.ini').write_text(config,encoding='ascii')
  check(transport(None if LIVE else fake_http)==0)
  names=['lua_gettop','lua_type','lua_checkstack','lua_pushcclosure','lua_setupvalue','lua_settop','lua_tolstring','lua_pushlstring']
  pointers=(c.c_void_p*8)(*[c.cast(getattr(t.lua,name),c.c_void_p).value for name in names])
  check(prepare(directory,pointers)==0)
  table=(c.c_void_p*33)(*[c.cast(load,c.c_void_p).value]*33);owner=c.c_void_p(c.addressof(table)+8)
  check(attach(c.byref(owner),c.addressof(table)+8,32,4,load,pop)==0)
  run(parts['BASE'])
  for name in ('ChatScrollBox','ChatMessageItem'):
   raw=t.compile_source(parts['SCROLL' if name=='ChatScrollBox' else 'ITEM'],name=('@C:/fixture/UI/Chat/'+name+'.lua').encode())
   check(invoke(c.byref(owner),state,raw,len(raw),b'@synthetic-module.lua',b'b')==0)
   check(gettop(state)==1);check(t.pcall(state,0,0,0,0,None)==0)
  check(snapshot()[0]==3);run(parts['HARNESS'])
  # Exercise the loaded Lua adapter and native callback together. Name
  # conversion must retain role IDs, message text and original call arguments.
  name_requests=google()[0]
  run(r'''
local player=fixture_methods.BuildChatMessageItem(1,'张三','unchanged 007',false,123)
assert(player.Prefix=='张三: ' and player.RoleID==123 and player.ContentText=='unchanged 007')
local link="<a type='playerName' XID='123' style='PC_Name' text='张三'></>: "
local linked=fixture_methods.BuildChatMessageItem(1,'张三','unchanged',false,123,nil,link)
assert(linked.Prefix==link and linked.RoleID==123)
local vietnamese=fixture_methods.BuildChatMessageItem(1,'Tên Việt007','unchanged',false,123)
assert(vietnamese.Prefix=='Tên Việt007: ')
local system=fixture_methods.BuildChatMessageItem(1,'张三','unchanged',true,123)
assert(system.Prefix=='张三: ')
local recruitment=fixture_methods.BuildChatMessageItem(18,'陆雪琪','unchanged',false,123)
assert(recruitment.Prefix=='陆雪琪: ')
for _,channel in ipairs({12,16}) do
 local npc=fixture_methods.BuildChatMessageItem(channel,'张三','unchanged',false,123)
 assert(npc.Prefix=='张三: ')
end
''')
  check(google()[0]==name_requests)
  if options.names_only:
   run("fixture_receive('你好',false,1);fixture_tick();assert(fixture_last.Prefix=='张三: ');assert(fixture_last.ContentText=='你好')")
   check(google()[0]==0 and snapshot()[1]==0 and not http_inputs)
   report=dict(status='PASS',source_name_links_unchanged=True,no_name_annotation_without_translation=True,network_requests=0,game_access=False,fixture_sha256=hashlib.sha256(options.fixture.read_bytes()).hexdigest())
   (HERE/'player-names-offline-proof.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
   print(json.dumps(report,indent=2));raise SystemExit()
  # A source remains intact; exactly one translated entry, rich islands exact.
  started=time.monotonic();receive(A);run('savedA=fixture_last;assert(select(2,fixture_click())==8)');pump(1)
  first_seconds=time.monotonic()-started
  run('assert(#fixture_scroll.rows==1);assert(fixture_translated(fixture_scroll.rows[1]));assert(fixture_scrolls>0)')
  run('assert(fixture_scroll.rows[1].ContentText:find("\\n----- [VI] -----\\n【Trương Tam】: ",1,true));assert(fixture_scroll.rows[1].Prefix=="张三: ")')
  run('assert(fixture_scroll.rows[1].ContentText:find('+json.dumps(name_link+' 【Khinh Hồng】',ensure_ascii=False)+',1,true));assert(not savedA.ContentText:find("Khinh Hồng",1,true))')
  run('fixture_tick();fixture_tick();assert(fixture_scroll:IsAtBottom(),"scroll used pre-layout height")')
  run('assert(fixture_scroll.rows[1].ContentText:sub(1,#savedA.ContentText)==savedA.ContentText);assert(savedA.ContentText=='+json.dumps(A,ensure_ascii=False)+');assert(fixture_scroll.rows[1].Prefix==savedA.Prefix)')
  for text in (link,emoji,'50%'):run('assert(fixture_scroll.rows[1].ContentText:find('+json.dumps(text,ensure_ascii=False)+',1,true))')
  run('fixture_click();assert(#fixture_sends==1)')
  # Cached B can appear before pending A2 completes, without reordering.
  receive(B);pump(2);calls=google()[0]
  run('fixture_handle:Reset(false)');A2=A.replace('555','556');receive(A2);receive(B)
  run('assert(#fixture_scroll.rows==2 and not fixture_translated(fixture_scroll.rows[1]) and fixture_translated(fixture_scroll.rows[2]))')
  pump(3);run('assert(#fixture_scroll.rows==2);assert(fixture_scroll.rows[1].ContentText:find("556",1,true));assert(fixture_scroll.rows[2].ContentText:find("Emoji22",1,true))')
  # Switching tabs rebuilds original source items, every VI stays in its slot.
  calls=google()[0];run('fixture_handle:Reset(false)');receive(A2);receive(B);receive('系统通知','true')
  run('assert(#fixture_scroll.rows==3);assert(fixture_scroll.rows[1].ContentText:find("556",1,true));assert(fixture_translated(fixture_scroll.rows[2]));assert(fixture_scroll.rows[3].ContentText=="系统通知")')
  check(google()[0]==calls)
  # Reading older messages: completion never clears/jumps/appends.
  run('fixture_handle.bIsAtBottom=false;before_scroll=fixture_scrolls;before_clear=fixture_clears')
  receive('你好 慢 '+emoji);pump(4)
  run('assert(fixture_scrolls==before_scroll and fixture_clears==before_clear and #fixture_scroll.rows==4);assert(not fixture_translated(fixture_scroll.rows[4]))')
  run('fixture_handle.bIsAtBottom=true;fixture_tick();assert(#fixture_scroll.rows==4 and fixture_translated(fixture_scroll.rows[4]));assert(fixture_scrolls>before_scroll)')
  # Cancel a deferred post-layout scroll as soon as the user scrolls up.
  run('fixture_handle.bIsAtBottom=false;before_scroll=fixture_scrolls;fixture_tick();fixture_tick();assert(fixture_scrolls==before_scroll);fixture_handle.bIsAtBottom=true')
  # Reset/context/source changes prevent stale rendering.
  receive('你好 过期 '+emoji);run('fixture_handle:Reset(false)');pump(5);run('assert(#fixture_scroll.rows==0)')
  receive('你好 改动 '+emoji);run('fixture_last.ContentText="changed"');pump(6)
  run('assert(#fixture_scroll.rows==1 and fixture_scroll.rows[1].ContentText=="changed")')
  receive('你好 角色 '+emoji);run('GameContext.HostData={}');pump(7)
  run('assert(not fixture_translated(fixture_scroll.rows[2]))')
  run('fixture_handle:Reset(false)')
  if not LIVE:
   behaviour='inject';receive('你好 注入 '+emoji);pump(8)
   run('assert(#fixture_scroll.rows==1 and fixture_scroll.rows[1].ContentText:find("‹evil›new‹/›",1,true))')
   behaviour='missing';receive('你好 缺失 '+emoji);pump(9)
   run('assert(not fixture_translated(fixture_scroll.rows[2]))')
   # Every failure annotates its own row, with no extra system messages.
   run('fixture_handle:Reset(false);fixture_handle.bIsAtBottom=true');behaviour='429';receive('你好 限流');pump(10);run('fixture_tick()')
   run('assert(#fixture_scroll.rows==1 and fixture_scroll.rows[1].ContentText:find("[WOJD]",1,true),tostring(fixture_scroll.rows[1].ContentText));fixture_click();assert(#fixture_sends==1)')
   calls=google()[0];receive('你好 再试');pump(11);check(google()[0]==calls)
   run('assert(#fixture_scroll.rows==2);for _,row in ipairs(fixture_scroll.rows) do assert(row.ContentText:find("[WOJD]",1,true)) end')
   check(not http_errors)
  # Stock capacity and unusual system data must never gain extra rows or
  # introduce a new Lua type error while the original game path accepts them.
  run('fixture_prepasses=0;function fixture_scroll:ForceLayoutPrepass()fixture_prepasses=fixture_prepasses+1;self:CommitLayout()end')
  run('GameContext.ChatLogManager.MessageItemLimit=2;fixture_handle:Reset(false);fixture_handle.bIsAtBottom=true')
  receive(A2);receive(B);receive('系统通知','true');run('fixture_tick()')
  run('assert(#fixture_scroll.rows==2 and fixture_translated(fixture_scroll.rows[1]) and fixture_scroll.rows[2].ContentText=="系统通知")')
  run('assert(fixture_prepasses>0)')
  run('fixture_handle:Reset(false);local item=fixture_methods.BuildChatMessageItem(1,"system","system",true,1);item.ContentText=17;fixture_methods.AddItemToList(fixture_scroll,item,true);fixture_tick();assert(fixture_scroll.rows[1].ContentText==17)')
  # Turned-off, recruitment, system (even a false system flag) and unknown
  # channels cannot hit cache or consume a request. Provider selection follows
  # the message's original channel even while displayed in the same tab.
  before=snapshot()[1];requests=google()[0]
  for channel in (2,8,9,10,13,18,19,99):run('fixture_receive("你好 路由",false,'+str(channel)+');fixture_tick()')
  check(snapshot()[1]==before and google()[0]==requests)
  if not LIVE:
   behaviour='normal'
   run('GameContext.ChatLogManager.MessageItemLimit=64;fixture_handle:Reset(false);fixture_handle.bIsAtBottom=true')
   run('fixture_receive("你好 '+emoji.replace('"','\\"')+'",false,3)');pump(before+1)
   run('assert(fixture_translated(fixture_scroll.rows[1]) and fixture_scroll.rows[1].ContentText:find("Gemini",1,true))')
   run('fixture_receive("你好 '+emoji.replace('"','\\"')+'",false,4)');pump(before+2)
   run('assert(fixture_translated(fixture_scroll.rows[2]) and fixture_scroll.rows[2].ContentText:find("DeepSeek",1,true))')
   requests=google()[0]
   run('fixture_handle:Reset(false);fixture_receive("你好 '+emoji.replace('"','\\"')+'",false,4);fixture_tick()')
   run('assert(fixture_translated(fixture_scroll.rows[1]) and fixture_scroll.rows[1].ContentText:find("DeepSeek",1,true))')
   check(google()[0]==requests and not http_errors)
  run("local ok,err=pcall(fixture_methods.BuildChatMessageItem,1,'玩家','ERROR',false,1);assert(not ok and err==fixture_error)")
  scroll_stats=(w.LONG*5)()
  scroll_api=bind('WojdChatReceiveFixtureScrollStats',w.DWORD,[c.c_void_p,w.DWORD])
  check(scroll_api(scroll_stats,5)==0);check(scroll_stats[0]>0 and scroll_stats[1]>0 and scroll_stats[2]>0 and scroll_stats[3]==0 and scroll_stats[4]>0)
  final=snapshot();check(final[6]==0);gs=google();check(stop()==0)
finally:stop();t.close(state)
report=dict(status='PASS',checks=checks,synthetic_only=True,live_google=LIVE,first_seconds=round(first_seconds,3),stats=final,cloud_stats=gs,scroll_stats=list(scroll_stats),
 one_entry_per_source=True,original_and_vi_same_entry=True,deferred_layout_scroll=True,manual_scroll_cancels_follow=True,tab_order_preserved=True,cache_replay_no_requests=True,autoscroll_at_bottom=True,scrolled_up_no_jump=True,stale_rejected=True,rich_islands_exact=True,errors_inline_per_message=not LIVE,source_name_links_unchanged=True,name_reading_below_vi=True,inline_player_link_reading=True,game_access=False)
report['fixture_sha256']=hashlib.sha256(options.fixture.read_bytes()).hexdigest()
(HERE/('ordered-native-live-proof.json' if LIVE else 'ordered-native-proof.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
