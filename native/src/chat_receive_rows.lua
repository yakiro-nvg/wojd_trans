-- Owned receive adapter. No I/O, outgoing send API, game history mutation,
-- load/require or native pointer is used on the UI thread.
local native
return function(...)
    local environment = _ENV
    local function original(...) end
    local function finish(...)
        local marker = "WOJD_CHAT_CALLBACK_V1:"
        local mode = "__WOJD_MODULE_MODE__"
        if type(native) ~= "function" or type(_G) ~= "table" then return end
        local session = native("session")
        if type(session) ~= "string" or #session ~= 32 then return end
        local key = "__WOJD_INCOMING_LOCAL_V1"
        local state = _G[key]
        if state ~= nil and (type(state) ~= "table" or state.session ~= session) then return end
        if not state then
            state = {
                session=session, next_id=0, pending={}, pending_count=0,
                items=setmetatable({}, {__mode="k"}), views=setmetatable({}, {__mode="k"}),
                bound=setmetatable({}, {__mode="k"}), readonly=0, active=true, owner_ready=false,
            }
            _G[key] = state
            local function context() return GameContext and GameContext.HostData end
            local function length(value) return type(value)=="string" and #value or 0 end
            local player_channels={[0]=true,[1]=true,[2]=true,[3]=true,[4]=true,[5]=true,[6]=true,[7]=true,
                [11]=true,[12]=true,[14]=true,[15]=true,[16]=true,[17]=true,[20]=true,[21]=true}
            local function player(args,item)
                if type(item) ~= "table" or args[4] ~= false or item.bIsSystem ~= false then return false end
                if type(args[1]) ~= "number" or args[1] % 1 ~= 0 or item.ChannelEnum ~= args[1] then return false end
                -- Recruitment rows already expand the translated static game
                -- templates. Never send these channels to a cloud translator.
                if not player_channels[args[1]] then return false end
                if type(args[2]) ~= "string" or args[2] == "" or type(args[3]) ~= "string" or args[3] == "" then return false end
                if type(args[5]) ~= "number" or args[5] <= 0 or args[5] % 1 ~= 0 or item.RoleID ~= args[5] then return false end
                return type(item.ContentText)=="string" and #item.ContentText>0 and #item.ContentText<=16000
            end
            local function valid(record)
                local item=record.item
                return record.owner==context() and item.ContentText==record.source
                    and item.ChannelEnum==record.channel and item.RoleID==record.role and item.bIsSystem==false
            end
            local function dirty(record)
                for scroll,generation in pairs(record.views) do
                    local view=state.views[scroll]
                    if view and view.generation==generation then view.dirty=true end
                end
            end
            local function failed(record,code,provider)
                if not valid(record) then return end
                local messages={
                    auth="Key không dùng được. Chạy chat-settings.bat để nhập lại key rồi mở lại game.",
                    quota="Đã hết hạn mức hoặc số dư. Kiểm tra tài khoản dịch vụ hoặc đổi lựa chọn trong chat-settings.bat.",
                    limited="Dịch vụ đang giới hạn yêu cầu. Các tin mới sẽ được thử sau khoảng một phút.",
                    offline="Chưa kết nối được dịch vụ. Kiểm tra mạng; các tin mới sẽ được thử lại.",
                    invalid="Chưa ghép được bản dịch của tin này. Tin gốc vẫn hiển thị.",
                    configuration="Dịch vụ không chấp nhận model hoặc thiết lập. Chọn lại trong chat-settings.bat rồi mở lại game.",
                    expired="Tin này đã hết thời gian chờ dịch.",
                    busy="Hàng đợi dịch đang đầy; tin này giữ nguyên bản gốc.",
                    failed="Chưa dịch được tin này. Tin gốc vẫn hiển thị.",
                }
                local prefix=(provider=="Google" or provider=="DeepL" or provider=="DeepSeek" or provider=="Gemini") and provider..": " or ""
                record.error=prefix..(messages[code] or messages.failed);dirty(record)
            end
            local function display(row)
                local record=row.record
                if record and (record.translation or record.error) and valid(record) and state.readonly>0 then
                    local copy={}
                    for k,v in pairs(row.item) do copy[k]=v end
                    local translated=record.translation and ((record.name and "【"..record.name.."】: " or "")..record.translation)
                    copy.ContentText=record.source..(translated and "\n----- [VI] -----\n" or "\n----- [WOJD] -----\n")..(translated or record.error)
                    if not row.shown then row.shown=true;native("rendered") end
                    return copy
                end
                return row.item
            end
            local function queue(record,view)
                if not record or not valid(record) then return end
                record.views[view.scroll]=view.generation
                if not state.owner_ready or record.attempted or record.translation or record.error or record.id then return end
                local status,text=native("cached",record.source,tostring(record.channel))
                if status=="translated_rich" and type(text)=="string" and #text>0 and #text<=64000 then
                    record.translation=native("namedlinks",text) or text;view.dirty=true;return
                end
                if state.pending_count>=32 then failed(record,"busy");return end
                record.attempted=true
                state.next_id=state.next_id+1
                local id=tostring(state.next_id)
                local accepted,deadline=native("enqueue",id,record.source,tostring(record.channel))
                if accepted=="queued" and tonumber(deadline) then
                    record.id=id;record.deadline=tonumber(deadline)
                    state.pending[id]=record;state.pending_count=state.pending_count+1
                elseif accepted=="rejected" then
                    failed(record,deadline)
                end
            end
            local function remember(view,row)
                if view.owner~=context() then view.rows={};view.bytes=0;view.dirty=false;view.owner=context();view.complete=false end
                if not view.complete then return false end
                if type(row.item.ContentText)~="string" then view.complete=false;view.rows={};view.bytes=0;return false end
                -- Keep the same capacity as the stock list. An unexpected size
                -- or memory budget stops rebuilding rather than dropping game rows.
                local limit=state.manager and tonumber(state.manager.MessageItemLimit)
                if limit and limit%1==0 and limit>=1 and limit<=2048 then
                    if #view.rows>=limit then
                        local first=table.remove(view.rows,1);view.bytes=view.bytes-first.bytes
                    end
                elseif #view.rows>=256 then view.complete=false;view.rows={};view.bytes=0;return false end
                row.bytes=length(row.item.ContentText)+length(row.item.Prefix)+length(row.item.ChannelText)+256
                    +(row.record and row.record.translation and #row.record.translation or 0)+(row.record and row.record.error and #row.record.error or 0)
                if view.bytes+row.bytes>2097152 then view.complete=false;view.rows={};view.bytes=0;return false end
                view.rows[#view.rows+1]=row;view.bytes=view.bytes+row.bytes
                return true
            end
            local function scroll_bottom(view)
                -- Same native operation as the stock "back to bottom" button.
                -- Rich-text sizes can still be pending when Add returns.
                if view.scroll.ForceLayoutPrepass then view.scroll:ForceLayoutPrepass();native("scroll","prepass") end
                view.scroll:ScrollToBottom(true)
            end
            local function follow(view,was_following)
                if not was_following then return end
                -- Clear/Add can synchronously change the stock bottom flag.
                -- Restore only the intent captured before our own UI mutation.
                scroll_bottom(view)
                view.handle.bIsAtBottom=true
                if view.handle.UpdateButtonVisibility then view.handle:UpdateButtonVisibility() end
                view.follow={generation=view.generation,turns=0,stable=0}
                native("scroll","follow")
            end
            local function settle(view)
                local pending=view.follow
                if not pending then return end
                if view.owner~=context() or pending.generation~=view.generation or view.handle.bIsAtBottom~=true then
                    view.follow=nil;native("scroll","cancelled");return
                end
                -- Work on later UI turns, after the original Add/Clear call.
                -- Never call TryScrollToEnd(true), which would override a user
                -- scroll. Stock OnUserScrolled clears bIsAtBottom to cancel us.
                scroll_bottom(view)
                pending.turns=pending.turns+1
                pending.stable=view.scroll:IsAtBottom() and pending.stable+1 or 0
                if pending.turns>=2 and pending.stable>=2 then view.follow=nil;native("scroll","settled")
                elseif pending.turns>=8 then view.follow=nil;native("scroll","unsettled") end
            end
            local function flush(view)
                if not view.dirty or not view.complete or view.owner~=context() or view.handle.bIsAtBottom~=true then return end
                local bytes=0
                for _,row in ipairs(view.rows) do
                    row.bytes=length(row.item.ContentText)+length(row.item.Prefix)+length(row.item.ChannelText)+256
                        +(row.record and row.record.translation and #row.record.translation or 0)+(row.record and row.record.error and #row.record.error or 0)
                    bytes=bytes+row.bytes
                end
                if bytes>2097152 then view.rows={};view.bytes=0;view.complete=false;view.dirty=false;return end
                view.bytes=bytes
                -- This custom native list exposes Clear/Add but no verified
                -- item setter. Rebuild only at the bottom, one entry per source,
                -- in its original order; never append a second translated entry.
                local was_following=view.handle.bIsAtBottom==true
                view.scroll:Clear(false)
                for _,row in ipairs(view.rows) do state.add(view.scroll,display(row),table.unpack(row.args,1,row.args.n)) end
                view.dirty=false
                follow(view,was_following)
            end
            state.bind_items=function(methods,env)
                if state.bound[methods] then return end
                local build,add=methods.BuildChatMessageItem,methods.AddItemToList
                if type(build)~="function" or type(add)~="function" then return end
                state.manager=env.GameContext.ChatLogManager;state.add=add;state.bound[methods]=true
                native("stage","items_bound")
                local function tracked(args,...)
                    local item=...
                    native("stage","item_built")
                    -- The source prefix and its PC_Name link remain exact.
                    -- A local reading belongs only to the translated section.
                    if player(args,item) then
                        local reading
                        if args[1]~=12 and args[1]~=16 then reading=native("namereading",args[2]) end
                        state.items[item]={item=item,source=item.ContentText,channel=item.ChannelEnum,role=item.RoleID,
                            owner=context(),name=type(reading)=="string" and reading or nil,views=setmetatable({}, {__mode="k"})}
                    elseif type(item)=="table" then state.items[item]=nil end
                    return ...
                end
                methods.BuildChatMessageItem=function(...)
                    local args=table.pack(...);return tracked(args,build(...))
                end
                methods.AddItemToList=function(scroll,item,...)
                    native("stage","view_added")
                    local view=state.views[scroll]
                    if not view or type(item)~="table" then return add(scroll,item,...) end
                    local row={item=item,record=state.items[item],args=table.pack(...)}
                    -- Pure memory cache lookup makes history replay synchronous.
                    -- A tab reload reconstructs items; their position never
                    -- depends on the time a worker translation happens to finish.
                    queue(row.record,view)
                    remember(view,row)
                    view.last_item=item
                    local rendered=display(row)
                    local was_following=view.handle.bIsAtBottom==true
                    local function added(...)
                        if rendered~=item then follow(view,was_following) end
                        return ...
                    end
                    return added(add(scroll,rendered,...))
                end
                if not state.timer and type(env.CreateUITimer)=="function" and type(env.SetObjectScript)=="function" then
                    local timer=env.CreateUITimer()
                    native("method","timer",timer and type(timer.SetTimerForNextTick) or "nil")
                    if timer and timer.SetTimerForNextTick then
                        native("stage","timer_created");state.timer=timer
                        env.SetObjectScript(timer,"OnUITimerNextTick",function()
                            if not state.active then return end
                            native("stage","timer_tick");state.owner_ready=native("ui")=="owner"
                            if state.owner_ready then
                                for _,view in pairs(state.views) do
                                    if view.owner==context() then
                                        settle(view)
                                        for _,row in ipairs(view.rows) do queue(row.record,view) end
                                    end
                                end
                                -- Service failures belong to the affected record, not a new chat row.
                                native("notice") -- drain aggregate diagnostic state without rendering it
                                local now=tonumber(native("clock"))
                                if now then
                                    for id,record in pairs(state.pending) do
                                        if now>=record.deadline then state.pending[id]=nil;state.pending_count=state.pending_count-1;failed(record,"expired") end
                                    end
                                end
                                local id,source,status,text,provider=native("poll")
                                local record=state.pending[id]
                                if record then
                                    state.pending[id]=nil;state.pending_count=state.pending_count-1
                                    if (status=="translated" or status=="translated_rich") and source==record.source
                                        and type(text)=="string" and #text>0 and #text<=64000 and valid(record) then
                                        record.translation=status=="translated_rich" and (native("namedlinks",text) or text) or (text:gsub("<","‹"):gsub(">","›"))
                                        dirty(record)
                                    elseif status=="error" and source==record.source then
                                        failed(record,text,provider)
                                    end
                                end
                                for _,view in pairs(state.views) do flush(view) end
                            end
                            timer:SetTimerForNextTick()
                        end)
                        timer:SetTimerForNextTick()
                    end
                end
            end
            state.bind_scroll=function(methods,env,resend)
                if state.bound[methods] or type(methods.NewScrollBox)~="function" or type(resend)~="function" then return end
                local create=methods.NewScrollBox
                local function guarded(widget,...)
                    if widget.GetContentPlainText and widget.GetChannel then
                        local content=widget:GetContentPlainText()
                        if type(content)=="string" and (content:find("[VI] ",1,true) or content:find("[WOJD] ",1,true)) then return end
                    end
                    return resend(widget,...)
                end
                if native("readonly",create,guarded)~="bound" then return end
                state.readonly=state.readonly+1;native("stage","row_guarded");state.bound[methods]=true;native("stage","scroll_bound")
                local function made(scroll,...)
                    local handle=...
                    if type(handle)=="table" and handle.Scroll==scroll and type(handle.Reset)=="function"
                        and type(handle.TryScrollToEnd)=="function" and scroll.Clear and scroll.ScrollToBottom and scroll.IsAtBottom then
                        local view={scroll=scroll,generation=0,handle=handle,rows={},bytes=0,complete=true,owner=context()}
                        state.views[scroll]=view
                        local reset=handle.Reset
                        handle.Reset=function(self,...)
                            if self==handle then
                                view.generation=view.generation+1;view.rows={};view.bytes=0;view.last_item=nil
                                view.complete=true;view.dirty=false;view.owner=context()
                                view.follow=nil
                            end
                            return reset(self,...)
                        end
                    end
                    return ...
                end
                methods.NewScrollBox=function(scroll,...) return made(scroll,create(scroll,...)) end
            end
        end
        local index,resend_index=native("layout",mode)
        local exported=table.pack(...)
        local methods=exported[tonumber(index) or 0]
        if type(methods)=="table" then
            if mode=="item" then state.bind_items(methods,environment)
            elseif mode=="scroll" then state.bind_scroll(methods,environment,exported[tonumber(resend_index) or 0]) end
        end
        native("module",mode,marker)
        return
    end
    return finish(original(...))
end
