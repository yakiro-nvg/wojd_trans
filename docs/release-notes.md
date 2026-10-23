Vietnamese production release: C8 native localization, both locres resources, 296 FormatString files, current Vietnamese font/UI fixes and the Quỳnh Các HUD fix. Includes 230 reviewed obvious-text repairs; remaining full semantic review continues after release.

Download **VI_PATCH.zip**. It is the single complete player package, using the optimized runtime DLL with capture/self-tests disabled. LIM/QFONT font-conversion variants remain in legacy history. No dump/debug package is offered to players.

Close the game, move old `~VI_PATCH*`/`~VI_QFONT*` PAKs outside Content/Paks, extract and run `install.bat`. Use `verify.bat`, `uninstall.bat` or `rollback.bat` as needed. No Python/compiler/admin access is required. If calibration requests a restart, exit normally and reopen through the launcher. No EXE timestamp/size/hash version gate.

The production DLL is built from this source revision in CI. Review the successful workflow, checksums, build inventory and artifact attestation. Original game DLLs/EXEs and private captures are excluded.

Known issues: inherited translations awaiting semantic review, untranslated paths and layouts not tested at every UI scale. Native DLL use carries compatibility, stability and publisher/anti-cheat risk; account safety and acceptance are not guaranteed. Redact private data before sharing logs.
