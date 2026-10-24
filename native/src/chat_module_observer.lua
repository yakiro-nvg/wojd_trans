-- Original module prototype is inserted as the first child by the bounded codec.
local function original(...) end

local function finish(...)
    local kinds = { ["nil"]="n", table="t", ["function"]="f", userdata="u",
                    string="s", number="d", boolean="b", thread="r" }
    -- Resolve the same globals that ordinary game Lua uses. This client does
    -- not expose getmetatable; no reflective helper is required here.
    local values = { GameContext, PrivateG, SetObjectScript, CreateUITimer,
                     ProvideChatMessageItem, ProvideChatMain, ChatLogManager, MainUI }
    local summary = ""
    for index = 1, 8 do
        summary = summary .. (kinds[type(values[index])] or "?")
    end
    -- The client deliberately removes load/getmetatable from its Lua globals.
    -- The normal type call is observed only for this fixed metadata protocol.
    type("WOJD_CHAT_NATIVE_SIGNAL_V1:" .. summary)
    if type(print) == "function" then
        print("WOJD_CHAT_LOADER_OBSERVER_V1:" .. summary)
    end
    return ...
end

return finish(original(...))
