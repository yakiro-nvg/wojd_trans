# Release Process

This project publishes translated PAKs automatically when the `release` branch is updated. Maintainers prepare releases as follows:

1. **Open a PR from `master` to `release`.**
   - Finalise translations and commit them on `master`.
   - No version bump is required; releases are timestamped automatically.

2. **Merge the PR into `release`.**
   - The GitHub Actions workflow (`.github/workflows/release.yml`) triggers on every push to `release`.

3. **CI performs the build.**
   - Installs Node.js and Python toolchains.
   - Runs `npm ci` and `npm run build` to compile the CLI.
   - Installs Python requirements (`pylocres`, `opencc`).
   - Installs the `repak` CLI from the official installer script.
   - Executes `wojd-trans pack artifacts`, which builds `Game.locres` plus regenerated `FormatString/*.txt` files and packs them into `<LANG>_PATCH.pak` files.
   - Renames the outputs to `~<LANG>_PATCH.pak` to ensure proper load order.
   - Generates `checksums.txt` for verification.

4. **Artifacts are published automatically.**
   - The workflow creates a GitHub Release tagged `v<YYYYMMDD-HHMMSS>`, based on the UTC timestamp when CI ran.
   - `~*.pak` files and `checksums.txt` are attached to the release.

If a release needs to be rebuilt (e.g., translation fix), repeat the process: update `master`, merge into `release`, and CI will produce a fresh timestamped tag with new assets. Keep the pipeline simple by letting CI handle all packaging from the catalogs—no manual artifact uploads are required.
