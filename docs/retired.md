# Migration inventory

The former Node/TypeScript CLI and provider-driven translation harness are replaced by Python offline catalog/review tools, native C source, readable installation scripts and a Windows CI build. Legacy VI/EN catalogs remain under `translations/legacy/` for reuse. Local migration backups, captures and orchestration state stay ignored.

Base Vietnamese font/dialogue/line-breaking assets and current UI derivatives are retained, with the separate HUD layer. Legacy LIM/XF/MVH and QFONT font-conversion choices are historical only: the current release offers a full runtime ZIP with a Legacy choice and a separate DLL-free Legacy ZIP. The new scoped/main-outline Han-Viet fonts are built from the current base font and a reading table; they do not restore the historical LIM/QFONT outline packages. Old packages remain in Git/Releases history.

The current runtime locres routes use exact approved namespace/key/CRC/target bindings; fresh residual catalogs remain editorial inputs, not a complete replacement for stock/generated widget identities. Source equality with .data is translation reuse evidence, not proof of producer identity or completed substitution.
