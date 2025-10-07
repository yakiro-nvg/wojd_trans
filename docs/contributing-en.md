# Localization Contribution Guide

## Just Reporting Translation Issues
1. Open the project’s GitHub Issues tab.
2. Create a new Issue describing:
   - The Vietnamese/Chinese text you saw in game.
   - Where it appears (quest, NPC, system…).
   - A screenshot if available.
3. Maintainers will review and update the catalogs accordingly.
4. After a major game update, please wait a few days before filing new reports so the team has time to refresh the patch.

## Advanced Users (Optional)
For contributors comfortable editing large files and working with Git, you can prototype changes locally before filing issues or PRs.

### Catalog structure
- Locres: `translations/<lang>.ndjson`
- FormatString: `translations/<lang>.fmtstring.ndjson`
Each line is a JSON object with `namespace`, `key`, `source`, `translated`.

### Workflow overview
1. Fork the repository and clone your fork.
2. Open the NDJSON files in an editor that handles large files (Sublime Text, etc.).
3. Use short keywords to locate the entry (strings may contain `<RTP_*>`, `${...}`, `(##Color:*)`, etc.).
4. Edit only the `"translated"` field—preserve placeholders, tags, etc.
5. To build a test PAK locally:
   ```
   npm install -g
   npm run build
   wojd-trans pack artifacts
   ```
6. Verify in game, then summarize your findings in an Issue or submit a PR if you are confident with Git.

> **Note:** Merge conflict resolution and other Git workflows are out of scope for this document. Reach out to maintainers if you run into problems.
