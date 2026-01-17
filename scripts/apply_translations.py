#!/usr/bin/env python3
"""Apply translations from batch files to vi.ndjson."""

import json
import re
from pathlib import Path
from collections import defaultdict

def load_translations():
    """Load all translation files."""
    translations = {}
    trans_dir = Path(__file__).parent.parent / "translations"

    # Load main translations file
    main_file = trans_dir / "translations_all.json"
    if main_file.exists():
        print(f"Loading {main_file.name}...")
        with open(main_file, "r", encoding="utf-8") as f:
            batch = json.load(f)
            for zh, vi in batch.items():
                if vi:  # Only add non-empty translations
                    translations[zh] = vi

    # Also load any batch files if they exist
    for batch_file in trans_dir.glob("translations_batch*.json"):
        print(f"Loading {batch_file.name}...")
        with open(batch_file, "r", encoding="utf-8") as f:
            batch = json.load(f)
            for zh, vi in batch.items():
                if vi:  # Only add non-empty translations
                    translations[zh] = vi

    print(f"Loaded {len(translations)} translations")
    return translations

def main():
    trans_dir = Path(__file__).parent.parent / "translations"
    vi_file = trans_dir / "vi.ndjson"
    output_file = trans_dir / "vi.ndjson.new"

    translations = load_translations()

    updated_count = 0
    total_count = 0

    print("Processing vi.ndjson...")
    with open(vi_file, "r", encoding="utf-8") as f_in, \
         open(output_file, "w", encoding="utf-8") as f_out:

        for line in f_in:
            line = line.strip()
            if not line:
                f_out.write("\n")
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                f_out.write(line + "\n")
                continue

            total_count += 1

            # Get original text
            source = entry.get("source")
            locres_import = entry.get("locresImport")
            original = source if source is not None else locres_import
            translated = entry.get("translated")

            # Check if this needs translation
            if original and original in translations:
                # Check if currently untranslated (translated == original)
                if translated == original or translated is None:
                    entry["translated"] = translations[original]
                    updated_count += 1

            f_out.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\nProcessed {total_count} entries")
    print(f"Updated {updated_count} translations")
    print(f"\nOutput written to: {output_file}")
    print("\nTo apply changes, run:")
    print(f"  mv {output_file} {vi_file}")

if __name__ == "__main__":
    main()
