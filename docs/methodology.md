# Translation Workflow Methodology

## Why This Pipeline Exists
Most UE5 localization projects revolve around editing existing `.locres` files. The Zhuxian China client ships with sparse `Game.locres` data, leaving a large portion of UI and quest text missing. Reversing every widget to discover `FText` sources is impractical and the assets only expose empty-namespace strings. Instead, we rely on the runtime localization manager to reveal what the game actually looks up.

Enabling very-verbose localization logging records every failed lookup with namespace, key, and source text. Coupled with our hash calculator, we can regenerate the required `locres` entries and ship an override PAK.

## One-Time Engine Configuration
Add this block to `ZhuxianClient/Saved/Config/Windows/Engine.ini` (or platform equivalent) to capture every missing lookup:

```
[Core.Log]
LogTextLocalizationManager=VeryVerbose
```

After launching the client, the engine writes detailed messages to `ZhuxianClient.log`. Each record includes namespace, key, and source text whenever the localization manager falls back to source. Those lines become the authoritative catalog for strings the base game is missing.

## Data Flow Overview
```
ZhuxianClient.log   --collect   -->  collected.json
                       │
                       └─ sync  --> translations/<lang>.ndjson
FormatString/*.txt  --fmtstring --> translations/<lang>.fmtstring.ndjson
                                     ▲         ▲
                        import locres│         │manual edits / PRs
                                     │         ▼
                                     └─ translate (AI) → updated NDJSON catalogs
                                                  │
                                                  └─ pack → Game.locres + FormatString txt → <LANG>_PATCH.pak
```

Each language now uses two NDJSON catalogs under `translations/`: `<lang>.ndjson` for standard locres data and `<lang>.fmtstring.ndjson` for FormatString overrides. Records track namespace (or relative file path), key, source text, optional locres imports, and translated text. Steps can be repeated at any time—new logs, fresh TXT exports, official patches, or community PRs all converge through the same flow.

## Step-by-Step Guide

### 1. Collect Unreal log output
1. Run the client with verbose logging enabled until the desired content is exercised.
2. Copy `ZhuxianClient.log` beside the CLI and run:
   ```
   wojd-trans collect collected.json --force
   ```
   `--force` rewrites the snapshot. The resulting array contains every (namespace, key, source) observed in the log.

### 2. Sync the locres catalog(s)
`sync` hydrates (or updates) per-language locres NDJSON files from the collected snapshot:
```
wojd-trans sync collected.json
```
- Adds new entries to each catalog.
- Resets translations when sources change (use `--force` to wipe all translations).
- Reports pending counts so you know what remains.

### 3. Sync FormatString text files
Traverse the game's FormatString folder to materialise `<lang>.fmtstring.ndjson`:
```
wojd-trans fmtstring FormatString
```
- Walks every `.txt` file (other extensions are ignored).
- Captures the relative file path, key, and source text; translations remain `null` initially.
- Re-run with `--force` to reset existing fmtstring translations if necessary.

### 4. Import official Game.locres
When the vendor ships `Game.locres`, some strings will already be localized. Importing ensures we reuse those and capture hashes for entries not present in logs:
```
wojd-trans import Game.locres
```
- For matching namespace/key pairs, the tool compares the computed source hash with the file’s stored hash. Matching rows copy the official text into `locresImport` for later reuse.
- For previously unseen keys, it appends records with the file’s hash so we can pack them back even without knowing the original source.
- The original `collected.json` is untouched.

### 5. AI-assisted translation
Translate pending entries per language:
```
wojd-trans translate
```
The CLI prompts for Bedrock Claude credentials, model, and reuses the language-specific system prompt (`prompts/<lang>/system-prompt.txt`).

Key behaviors:
- Grouping is by runtime text (`locresImport` when present; otherwise the collected source, or the raw FormatString value) so identical strings translate once across both catalogs.
- `--batch-size` controls how many unique strings are bundled into a single Bedrock request (default 5). Larger values reduce per-request overhead but require more tokens; smaller values are safer if the model struggles with long prompts.
- `--concurrency` defines how many requests are sent in parallel; `--checkpoint` dictates how often translation files are flushed to disk; `--limit` restricts how many unique strings are processed in the session.

### 6. Human review and edits
Manual tweaks happen directly in `translations/<lang>.ndjson` and `translations/<lang>.fmtstring.ndjson` (or via PRs). Each line is a standalone JSON object; update the `translated` field as needed. Re-running `sync`/`fmtstring` merges fresh inputs without disturbing reviewed translations unless the source itself changes.

### 7. Build locres + PAK
After translations are in place:
```
wojd-trans pack artifacts
```
- Generates `Game.locres` per language using the appropriate hash pipeline (`utf32le_alt` with OpenCC simplification). Imported hashes are reused when available.
- Recreates the necessary `FormatString/*.txt` files, falling back to the source text whenever a translation is missing so the game never displays blanks.
- Creates `<LANG>_PATCH.pak` inside `artifacts/`, preserving both `ZhuxianClient/gamedata/client/ZCTranslateData/Game/zh-Hans/Game.locres` and `ZhuxianClient/gamedata/client/FormatString/*.txt`.
- Temporary working directories are cleaned unless `--keep-temp` is set.

## Iterating on Updates
- **New gameplay logs**: rerun `collect` and `sync`. Existing translations remain unless the source text changes.
- **Official patches**: rerun `import` with the updated locres, then translate or manually adjust any new entries.
- **New FormatString exports**: rerun `wojd-trans fmtstring` to fold in the latest TXT content before translating.
- **Community contributions**: reviewers edit the NDJSON files, commit/PR, and rebuild PAK assets via `pack`.

Because every artifact derives from NDJSON catalogs, the repository stays review-friendly, and rebuilds are deterministic. This method scales to additional languages by adding entries to `languages.json`, provisioning a prompt file, and following the same cycle.
