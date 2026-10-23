# Build and release

Clone with Git LFS and fetch its objects. Python 3.12 with `requirements.txt`, MSVC x64 Build Tools and the pinned repak packer are build dependencies; players need none of these.

`.github/workflows/build.yml` builds on master, release and refactor branches, pull requests and manual dispatch. The Windows job installs pinned dependencies, checks catalogs, executes independent inert installer/archive fixtures, compiles runtime/dump and both test profiles, tests every native dictionary rule in normal/far modes, runs 73 C8 setup checks and rejects test exports or external MSVC runtime dependencies in production DLLs. Capture and client coverage remain distinct from fixture coverage.

The package builder renders 296 FormatString files, cooks both V3 locres resources from exact route-specific bindings and validates the complete 643-file approved base inventory. Source keys, CRCs, target whitespace and newline forms are preserved. This includes validated stock and generated widget bindings that residual misses alone cannot reconstruct. Keep `resources/locres/manifest.json` and `config/base-payload.json` synchronized with reviewed changes; do not regenerate identity mappings from literal .data overlap.

`config/packages.json` declares one complete production player ZIP, VI_PATCH.zip. It uses the freshly built runtime DLL (CAPTURE=0, SELFTEST=0, O2) and the four-file HUD PAK at priority203. Base text/assets stay in the main PAK at priority103. The builder binds the DLL hash to its production PE/profile checks and rejects dump/test profiles. LIM/QFONT conversion fonts are historical only. Runtime editor metadata and game captures are excluded. Every PAK is fully extracted and compared to its staged bytes; every ZIP is fully reread. Vendor DbgHelp is copied from the user's installation, never shipped.

Development builds upload reviewable artifacts without publishing. After a green source-branch run, fast-forward master/release to the reviewed revision. A push to release publishes only after its own successful build, using that run's artifacts, source revision, checksums and GitHub artifact attestation. Actions and repak are pinned. `local-unpublished` denotes a local build, not a hosted CI release.

Local checks mirror the workflow: install requirements; run unittest discovery; compile `work/catalog.bin` with `scripts/wojd.py compile-runtime`; run `native/build.cmd` for all four profiles, both `native/test_runtime.py` profiles, `native/test_c8_setup.py` and `native/check_artifacts.py`; finally run `scripts/build_package.py --repak <path>`.

The dump DLL remains a developer build target. The public player ZIP uses runtime; no dump ZIP is advertised in this release. Fresh capture runs must omit translated locres from both resource routes. Do not infer translation completeness, every UI layout or anti-cheat acceptance from passing build checks.
