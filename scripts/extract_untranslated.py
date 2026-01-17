#!/usr/bin/env python3
"""Extract untranslated entries from vi.ndjson, group by unique source text."""

import json
import re
from collections import defaultdict
from pathlib import Path

# Load skip rules
skip_rules = []
skip_file = Path(__file__).parent.parent / "config" / "translation-skip.json"
if skip_file.exists():
    with open(skip_file, "r", encoding="utf-8") as f:
        config = json.load(f)
        skip_rules = config.get("rules", [])

def should_skip(entry):
    """Check if entry matches any skip rule."""
    namespace = entry.get("namespace", "")
    key = entry.get("key", "")
    source = entry.get("source") or entry.get("locresImport") or ""

    for rule in skip_rules:
        rule_ns = rule.get("namespace", "")
        key_regex = rule.get("keyRegex")
        source_pattern = rule.get("sourcePattern")

        # Check namespace match
        if rule_ns and namespace != rule_ns:
            continue

        # Check key regex if specified
        if key_regex:
            if not re.match(key_regex, key):
                continue

        # Check source pattern if specified
        if source_pattern:
            if not re.match(source_pattern, source):
                continue

        # All conditions matched - skip this entry
        return True

    return False

def is_technical_text(text):
    """Check if text is technical/placeholder that shouldn't be translated."""
    if not text:
        return True

    # Skip pure numbers
    if re.match(r'^[\d.,/\-\+\*%]+$', text):
        return True

    # Skip format specifiers like \10, \1, \100
    if re.match(r'^\\[\d]+$', text):
        return True

    # Skip placeholders like (@@Name)(/Name)
    if re.match(r'^\(@@\w+\)\(/\w+\)$', text):
        return True

    # Skip __NULL__
    if text == '__NULL__':
        return True

    # Skip pure punctuation
    if re.match(r'^[…？！。、，；：""''【】《》（）\-—/\\.,!?;:\'"()\[\]<>]+$', text):
        return True

    # Skip pure ASCII identifiers (PascalCase, camelCase, snake_case)
    if re.match(r'^[A-Za-z][A-Za-z0-9_]*$', text):
        return True

    # Skip pure Pinyin-like (capitalized words without Chinese)
    if re.match(r'^[A-Z][a-z]+(\d+)?$', text):
        return True

    return False

def has_chinese(text):
    """Check if text contains Chinese characters."""
    if not text:
        return False
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def is_untranslated(entry):
    """Check if an entry is untranslated."""
    source = entry.get("source")
    locres_import = entry.get("locresImport")
    translated = entry.get("translated")

    # Get the original text (source or locresImport)
    original = source if source is not None else locres_import

    if original is None:
        return False

    # If translated is missing or same as original, it's untranslated
    if translated is None:
        return True
    if translated == original:
        return True

    return False

def main():
    vi_file = Path(__file__).parent.parent / "translations" / "vi.ndjson"

    # Group by unique source text
    untranslated_groups = defaultdict(list)
    skipped_technical = 0

    print("Reading vi.ndjson...")
    with open(vi_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if should_skip(entry):
                continue

            if is_untranslated(entry):
                # Get the original text for grouping
                source = entry.get("source")
                locres_import = entry.get("locresImport")
                original = source if source is not None else locres_import

                if original:
                    # Skip technical text
                    if is_technical_text(original):
                        skipped_technical += 1
                        continue

                    # Only include if has Chinese characters
                    if not has_chinese(original):
                        skipped_technical += 1
                        continue

                    untranslated_groups[original].append({
                        "key": entry.get("key"),
                        "namespace": entry.get("namespace"),
                    })

    # Sort by number of occurrences (most common first)
    sorted_groups = sorted(untranslated_groups.items(), key=lambda x: -len(x[1]))

    print(f"\nFound {len(sorted_groups)} unique Chinese texts needing translation")
    print(f"Total entries: {sum(len(v) for v in untranslated_groups.values())}")
    print(f"Skipped technical entries: {skipped_technical}")

    # Output for manual translation - simple format
    output_file = Path(__file__).parent.parent / "translations" / "to_translate.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        for i, (source_text, entries) in enumerate(sorted_groups, 1):
            # Clean up newlines for display
            display_text = source_text.replace('\n', '\\n')
            f.write(f"{i}. [{len(entries)}x] {display_text}\n")
            f.write(f"   → \n")
            f.write("\n")

    print(f"\nSaved to: {output_file}")

    # Also save JSON for programmatic use
    json_output = Path(__file__).parent.parent / "translations" / "to_translate.json"
    output_data = []
    for source_text, entries in sorted_groups:
        output_data.append({
            "zh": source_text,
            "vi": "",
            "count": len(entries),
        })

    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"JSON saved to: {json_output}")

if __name__ == "__main__":
    main()
