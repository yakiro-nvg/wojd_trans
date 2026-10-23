# Installation

Download **VI_PATCH.zip** from [Releases](https://github.com/yakiro-nvg/wojd_trans/releases/latest). This complete production package includes the optimized native hook, Vietnamese translation/fonts and UI fixes. Capture and self-tests are disabled. Legacy LIM/QFONT conversion packages are not part of this lineup.

Extract the ZIP, close the client normally and run `install.bat`. Select Game, ZhuxianClient or Binaries\Win64. Move old `~VI_PATCH*`/`~VI_QFONT*` PAKs outside Content/Paks first. No Python, compiler or administrator access is required. Start through the launcher; restart normally if an address-calibration message requests it.

Use the new package's installer to update. `verify.bat` checks files; `uninstall.bat` removes the patch; `rollback.bat` restores a recorded install/uninstall transaction. Caches, settings, logs and backups are retained. Other modified files are preserved on a conflict. No original game DLL or EXE is distributed.

The native hook is rebuilt from public source in CI. Check the release revision, workflow, checksums and attestation. The installer has no EXE hash/timestamp/size version gate; runtime code still needs validation. Compatibility, stability, account safety and publisher/anti-cheat acceptance are not guaranteed. Redact private information before sharing logs. This release contains Vietnamese; English legacy catalogs are reuse inputs only.
