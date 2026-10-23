# Native localization component

Use build.cmd runtime or dump with MSVC x64 Build Tools. Test profiles expose fixture-only exports and must never be distributed. test_runtime.py checks an independent synthetic decoder/allocator, the full dictionary, source/origin guards, original export forwarding, concurrent calls and entry restoration. It never executes captured game code.

Runtime performs exact-source substitution on decoded data strings without per-string hit collection. Dump adds deduplicated captures/counters and the public archive helper. There is no translation service, remote command endpoint, gameplay Lua injection or signature bypass. Documentation intentionally omits interception recipes.

Dump currently captures the generic data route; dynamic typed Skill/Buff capture is disabled. Player ZIPs contain only the optimized runtime build with WOJD_CAPTURE=0 and WOJD_SELFTEST=0. Dump and test DLLs are never packaged for players.

Independently validated display fields read by a separate tooltip FString serializer also use the source-exact native dictionary. Runtime replacement and diagnostic capture remain separate build choices. Captured observations record archive completion as unverified and remain excluded from automatic native catalog import. Synthetic fixture success does not establish client coverage or installation timing.

The proxy forwards original DbgHelp exports to a local copy of the user's original DLL; that DLL is not distributed. Cached locations are hints and require current signature/origin validation. The portable installer checks x64 client structure and owned payload integrity; it does not reject a client merely because its EXE hash, timestamp or size changed.

vendor/minhook is 1.3.4 under its included BSD license, with tested local allocation modifications. Real-client validation remains required; thread patch coordination is not a zero-race/crash guarantee.

Public CI compiles runtime, dump, runtime-test and dump-test directly from this checkout. Production packages use only freshly compiled non-test DLLs. After building runtime-test, run `python native/test_c8_setup.py` for 73 independent allocator, notice, full-group, immutable-origin and actual MinHook setup checks. These fixtures use private synthetic memory and never execute captured code or open the game. Optional current-code diagnostics remain disabled by default.
