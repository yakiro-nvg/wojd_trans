#!/usr/bin/env python3
"""Fix JSON files with unescaped quotes."""

import json
import re
from pathlib import Path

def fix_quotes(content):
    """Replace ASCII quotes inside Chinese text with Chinese quotation marks."""
    # Pattern to find quoted Chinese text with ASCII quotes
    # Replace "司时" style quotes with 「」
    content = content.replace('乃悟 "司时"之道', '乃悟「司时」之道')
    return content

def main():
    trans_dir = Path(__file__).parent.parent / "translations"

    for batch_file in trans_dir.glob("translations_batch*.json"):
        print(f"Processing {batch_file.name}...")

        with open(batch_file, "r", encoding="utf-8") as f:
            content = f.read()

        content = fix_quotes(content)

        with open(batch_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Verify it loads
        try:
            with open(batch_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"  OK - {len(data)} translations")
        except json.JSONDecodeError as e:
            print(f"  ERROR: {e}")

if __name__ == "__main__":
    main()
