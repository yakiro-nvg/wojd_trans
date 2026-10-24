# Dynamic text translation service (development)

The player release now implements received-chat translation in the native runtime, configured through `chat-settings.bat`; it does not require this Python service. This directory documents separate development prototypes and fixtures. See [the player chat guide](../distribution/CHAT_GUIDE.txt) for the shipped feature.

This module is the background translation component for planned **in-game** dynamic text translation. It does not capture the screen, replace the game's chat window, read game memory, install a DLL or send game messages. The current localization package does not yet connect chat to this service.

The intended integration keeps Chinese originals and structured message metadata intact. A game-side adapter submits an owned text snapshot without blocking the UI, then applies the result to the matching local message on the UI thread. The chat history and scroll view must retain that result. Replies require a separate, explicit translation/preview/confirmation action; normal input stays unchanged. Received translations must never enter a game-send path, including the game's resend button.

The Lua adapter has synthetic tests, but actual callback environment, UI-thread identity, history identity/refresh and source-only resend are still integration gates. Offline tests do not establish client compatibility or publisher acceptance. These particular prototype adapters are not the shipped native chat adapter.

## Providers

`providers.py` supports an explicitly configured local OpenAI-compatible translation server and official Azure Translator. Local endpoints are restricted to loopback. Azure uses official HTTPS endpoints and credentials from an environment variable; there is no automatic cloud fallback. Choosing Azure submits message text to that provider.

For a local Hy-MT2 translation model, the explicit service settings are:

```json
{
  "kind": "local",
  "endpoint": "http://127.0.0.1:18475/v1",
  "model": "hy-mt2-1.8b-q4",
  "prompt_style": "hy-mt"
}
```

The model/server must already be installed and running. This module does not download them. `hy-mt` selects the model publisher's translation prompt; other compatible models can use `general`. A small local model can mistranslate roles or follow an instruction inside a message. Marker/number/script checks catch some failures and are not semantic review.

Azure settings use `kind: "azure"`, an optional region, and optionally `api_key_env` naming the secret environment variable. The default key variable is `WOJD_AZURE_TRANSLATOR_KEY`. Plaintext `api_key` in the settings file is rejected.

As checked on 2026-10-18, [Azure F0](https://azure.microsoft.com/en-us/pricing/details/translator/) includes 2 million characters/month, subject to service limits. [Hy-MT2 standard GGUF](https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF) is an offline option after setup; the tested Q4 model is about 1.13 GB. Free allowance is not unlimited, and model benchmarks are not game-performance tests.

## Local protocol

`python -m chat_companion.service --port PORT --settingspath FILE` explicitly starts the service. `WOJD_CHAT_SERVICE_TOKEN` must contain a new 64-character lowercase hexadecimal token. Do not commit settings with credentials, tokens, chat or raw captures. No listener starts merely by importing the module.

The service binds only 127.0.0.1. Authenticated POST submission, polling and cancellation accept bounded JSON; there is no command execution, arbitrary URL, capture or game-send endpoint. Responses retain session/request/source-digest bindings and a per-request nonce. The native host must additionally validate its own row occurrence and lifecycle generation before updating any UI.

There is one provider worker, at most 32 pending requests, 128 retained records and a 60-second lifetime by default. Errors retain the original text on the game side. Bodies, screenshots, API keys and request content are not logged or persisted. An already running provider request cannot be recalled; cancellation discards its result and prevents waiting work from starting. Runtime diagnostics should collect counts/latency, not player text.

`bridge.py` provides a reference mapping between the abstract Lua host envelope and this HTTP protocol. It keeps the original and lifecycle metadata locally, maps IDs, validates every response binding and runs network work only through an explicit background step. A local deadline produces an error from the saved local envelope, allowing the host to retire a pending request while keeping Chinese visible. The real native/UI host is still unimplemented and must drive the bridge and drain results within its bounded lifetime.

Run `python -m unittest discover -s tests -p "test_chat*.py"` for transport, queue, binding, cancellation, deadlines and structural guards. These use synthetic text and mock providers or loopback fixtures, not real player chat.
