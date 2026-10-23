# Translation development

Use Python 3.12, Git LFS, MSVC x64 Build Tools and pinned repak. Work from the repository root on a drive with enough room. No translation provider or API key is required.

~~~powershell
git lfs pull
python -m venv work/venv
.\work\venv\Scripts\python.exe -m pip install -r requirements.txt
~~~

Activate that venv for the commands below.

## Clean collection

Dump is a developer build target, not a player ZIP in this release. For a separate diagnostic collection, close the game and prepare the dump DLL with **both translated locres routes omitted**. Remove other translated locres PAKs, including custom-named older patches; their hits hide misses. Keep original game resources.

If missing-localization logging is disabled, back up the user Saved/Config/WindowsClient/Engine.ini (some builds use Windows) and merge, preserving the rest:

~~~ini
[Core.Log]
LogTextLocalizationManager=VeryVerbose
~~~

Check a fresh game log actually reports localization misses before a long run. Logging can be very large; restore your previous settings afterward. The installer does not modify game INI files automatically.

Binaries/Win64/wojd/settings.json contains ue_log_path. Set it to the actual active game log before launching if the default differs. Exercise the relevant screens and exit normally if possible. Each run creates a unique directory in wojd/logs/:

| File | Purpose |
|---|---|
| session.json | PID, process generation, unique session |
| build.json | Game/catalog hashes and source revision |
| native.log | Readiness, counters, capture errors |
| data.ndjson | Deduplicated decoded sources and decisions |
| ZhuxianClient.log | This run's retained UE log |
| archive-result.json | Completeness/hash result; require PASS |

The dump-only companion is readable PowerShell. It retains a file handle across renames and verifies the process generation. Failed/truncated/oversized archives retain their prefix with a failed result. Compare source sets and counters for equivalent repeated runs; investigate drops, errors or unexplained differences before release. Different content can legitimately differ. Runtime collects no per-string usage.

## Schema and reuse

Capture rows contain route, source, target, status, translated, PID and diagnostic context. They have no stable field ID; numeric diagnostic keys are not localization IDs.

Editable native rows contain source, source_sha256, translated, translation_source_sha256, status and optional reason. States are **translated, missing, ignore**. Ignore deliberately keeps CN and requires a reason in review submissions. Missing/ignored entries never assign an empty display string. Preserve exact source, including whitespace, markup, literal escapes and real newlines.

Legacy catalogs save translation effort only. Reuse eligibility is literal source equality across all indexed routes; namespace, key and original file/route do not restrict matching. Output identities still place the accepted translation in the correct current locres or FormatString entry. Structural QA remains required.

~~~powershell
python scripts/wojd.py index translations/legacy/vi.ndjson translations/legacy/vi.fmtstring.ndjson --out work/reuse.sqlite
python scripts/wojd.py native-sync work/session/data.ndjson --index work/reuse.sqlite --reviewed translations/vi.native.ndjson --out translations/vi.native.ndjson
~~~

Previously reviewed entries absent from the newest input are retained. Inspect usage across representative sessions/builds before removing possible garbage:

When current native, FormatString and residual catalogs already exist, include those VI catalogs in the next index build as well. This shares reviewed exact-source translations across all three routes, including reviewed additions absent from the historical files. Keep language indexes separate.

~~~powershell
python scripts/wojd.py native-usage work/session/data.ndjson --catalog translations/vi.native.ndjson --out work/usage.json
~~~

not_observed means absent only from those inputs, not proven dead. No entries are automatically deleted.

## Fresh fallback and independent FormatString

~~~powershell
python scripts/wojd.py fallback-sync work/session/ZhuxianClient.log --native work/session/data.ndjson --index work/reuse.sqlite --out translations/vi.residual.ndjson
python scripts/wojd.py fmt-sync resources/FormatString --previous translations/vi.fmtstring.ndjson --index work/reuse.sqlite --out translations/vi.fmtstring.ndjson
~~~

Fresh CN namespace/key/source observations are retained even when their literal source also appears in native data. Exclude only actual substituted native output text. Producer identity needs route evidence; source equality permits translation reuse. The public release cooks exact content/gamedata bindings from resources/locres/, preserving stock/generated widget identities and source CRCs that miss logs alone cannot recover.

Never merge historical locres identities back in. Use a different output filename to compare generations. The next clean dump must again omit translated locres: filtering cannot recover misses a loaded locres hid. Establish reader-capture completeness first; an unseen source is only a non-data candidate until sufficient coverage is available.

FormatString is independent. Refresh current source templates with whole-file patch precedence before syncing; do not recreate TXT files from old keys. The .sources.json manifest guards source-file hashes; rendering preserves BOM, comments and line endings. Here only, dated can identify an unresolved changed source under the same file/key. It stays CN. Do not remove FormatString entries merely because their source also appears in native captures.

## Review batches

~~~powershell
python scripts/wojd.py review-export translations/vi.native.ndjson work/review-native
python scripts/wojd.py review-import translations/vi.native.ndjson work/review-native/0000.ndjson --out translations/vi.native.ndjson
python scripts/wojd.py validate translations/vi.native.ndjson translations/vi.residual.ndjson translations/vi.fmtstring.ndjson
~~~

Fill translated and set status=translated, or choose ignore with a reason. Keep source/SHA unchanged. Unknown sources or structural failures reject the entire import. Preserve logical attributes/IDs, tag names, placeholder order, numbers and newline forms. Prompts under prompts/<language>/ are editorial guidance, not a service integration. Structural checks cannot prove a translation's meaning. Some captures are internal labels, file paths or technical data.

A translated native row can additionally have review_required=true with a review_reason. It remains a native translation task; review-export includes its original source and current_translation context. Completing review-import clears that flag. CJK inside valid technical markers is preserved; CJK left in visible translated prose is a review candidate.

## Translation quality evidence

Prioritize missing sources before broad revision of legacy text. Structural validation is independent of language review. The sparse `translations/<language>.quality.ndjson` ledger binds evidence to SHA-256 of both source and target. A changed target/source does not inherit the old review; changed runtime IDs do not invalidate identical text. Different active translations of one source require separate evidence. The hook never loads this ledger.

Levels: `unreviewed` (default for reused/imported text), `draft`, `source_reviewed` (compared against CN), and `client_verified` (specific in-game observation recorded in the note). General startup/ABI tests never verify every translation. Missing/dated/ignore remain catalog decisions, independent of these language levels.

After importing reviewed text:

~~~powershell
python scripts/wojd.py quality-mark translations/vi.native.ndjson translations/vi.fmtstring.ndjson translations/vi.residual.ndjson --ledger translations/vi.quality.ndjson --review work/reviewed.ndjson --level source_reviewed --reviewer maintainer --note "Compared each sentence with CN and its context"
python scripts/wojd.py quality-report translations/vi.native.ndjson translations/vi.fmtstring.ndjson translations/vi.residual.ndjson --ledger translations/vi.quality.ndjson --out reports/quality-vi.json --sources-out work/review/quality-by-source.ndjson
~~~

Use `--glossary-revision` when a particular terminology revision was used. A glossary should record the Chinese term, approved Vietnamese name, entity type, aliases, context/scope, reference and approval state. Adopt a chosen Vietnamese Tru Tiên reference and existing project decisions; report inconsistencies for contextual review instead of replacing prose mechanically. Review related dialogues/items together to preserve speaker relationships, meaning and tone.

Preserve CJK placeholders, resource filenames, internal lookup strings and parsing-sensitive text. Historical fixes `4755881` (pet literal newline escape), `ec5c4dd` (ranking keys), and `5a5935f`/`69e94ce` (dye naming consistency) are regression evidence, not a general rule to remove every Chinese character. Image payloads and `@p/@P` paths, `@t` headers and separators are immutable.

Preserve the complete backslash run in literal escapes. One backslash before `n`, two backslashes before `n`, and an actual newline are distinct. QA checks the full escape depth, including CRLF and tab forms; do not add another escaping layer when writing NDJSON.

Numeric QA recognizes exact `线路` channel labels with canonical written Chinese numbers from 1 to 999 and permits the equivalent Arabic value in the target. The current WorldPlane table reaches channel 245. Wrong or additional values still fail. This narrow display-label check neither translates text nor establishes that arbitrary Chinese numerals or lookup tables are safe to change; those require their own context decision. Legacy matches accepted by structural QA remain `unreviewed` until someone compares the complete source and target.

## Local build

~~~powershell
python -m unittest discover -s tests -v
python scripts/wojd.py compile-runtime translations/vi.native.ndjson work/catalog.bin
.\native\build.cmd runtime
.\native\build.cmd dump
.\native\build.cmd runtime-test
.\native\build.cmd dump-test
python native/test_runtime.py --profile runtime --language vi
python native/test_runtime.py --profile dump --language vi
python native/test_c8_setup.py
python native/check_artifacts.py
python scripts/build_package.py --language vi --repak work/tools/repak/repak.exe
~~~

The packer fully extracts and verifies both PAKs and creates one complete production runtime ZIP. It includes the verified DLL/dictionary, dual exact locres, current FormatString and common UI/HUD layers. Dump/test binaries are excluded from player ZIPs. See [release process](release-process.md).

English legacy catalogs remain reuse inputs. An EN fork must create its own current catalogs, exact runtime bindings, package matrix and matching checks; this release intentionally builds Vietnamese only.

Never commit raw account/chat logs, credentials, game DLL/EXE, or unpacked .data files. Share sanitized necessary excerpts without changing source strings used for decisions.

## Parallel editorial work

`scripts/batch_workflow.py --help` provides a durable offline SQLite queue. The coordinator refreshes the current missing-source inventory, including exact SHA and context references, and makes immutable batches bounded by both count and characters. Retain the database across sessions. Translators claim `TRANSLATE` work and submit immutable attempts; a different reviewer claims `REVIEW`, reads complete CN/target text and records a reason for every decision. Renew live leases with `heartbeat`; expiry alone does not prove a worker stopped.

Workflow enums are separate from language quality levels. Draft decisions are `TRANSLATED`, `IGNORE` and `NEEDS_CONTEXT`; review decisions are `APPROVE`, `REJECT` and `NEEDS_CONTEXT`. Preserve Chinese class/gender selectors and exact colon forms in multi-variant dialogue while their consumer remains unknown. Ordinary prose still requires contextual translation.

Only the coordinator imports an inspected export with its matching SHA manifest. An export does not mutate catalogs or replace an import receipt. Import approved subsets, retain unresolved sources and old attempts, record quality evidence, then refresh remaining inventory to avoid duplicate imports. New targets require new review bindings. Compact review evidence may reference immutable source/target hashes without repeating the full prose; tools can derive hashes and metadata, while reviewers must still read and assess complete meaning.

If QA becomes stricter after an attempt was frozen, a reviewer can still record `REJECT` or `NEEDS_CONTEXT` for a newly invalid target. Every `APPROVE` is checked against current structural rules again, including at export. Recording a rejection never permits an invalid target into a catalog; the frozen canonical content and source/target hash bindings remain mandatory.

Track translated, deliberately retained and unresolved sources separately. Measure drafting, independent review, corrections and import time across short, medium and long samples. Recalibrate ETA from completed work, not draft-generation speed alone. A source absent from one capture is not proven dead.
