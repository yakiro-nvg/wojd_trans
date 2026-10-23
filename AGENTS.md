# Project work

- Use the Git repository and CI as the release authority. Do not treat local artifacts as a hosted release.
- Player packages contain only optimized native runtime (CAPTURE=0, SELFTEST=0); dump/test DLLs remain development targets. Build native binaries from source.
- Preserve exact source, targets, markup, placeholders, numeric meaning and newline/escape depth. Reuse by literal source is not semantic approval or proof of runtime origin.
- Quality evidence binds both source and target. Keep unreviewed/draft/source_reviewed/client_verified distinct. Structural or native fixtures do not certify translation meaning or universal UI fit.
- Keep both exact locres route bindings, all current FormatString templates and the approved UI/HUD payload manifests synchronized with reviewed changes. Preserve the two PAK priorities.
- For authorized parallel editorial/review work, use disjoint immutable batches and an independent reviewer. Only the coordinator imports approved catalog subsets and builds packages.
- Preserve unrelated user changes. Never commit raw captures, account/chat logs, credentials or original game DLL/EXE/.data. Keep work and build outputs ignored; use D: for local scratch in the current workspace.
- Do not launch/login/kill the game unattended. Install only while the user has closed it. Never inspect the protected game process with external debugging tools.
- Run the relevant checks in .github/workflows/build.yml. Review source and staged files before committing; publication requires the user's release authorization.
