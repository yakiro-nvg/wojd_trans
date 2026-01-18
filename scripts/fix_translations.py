#!/usr/bin/env python3
"""Fix translations JSON file - escape or replace problematic quotes."""

import json
import re
from pathlib import Path

def fix_json_quotes(content):
    """Fix ASCII quotes inside Chinese text by replacing with Chinese quotation marks."""
    # Replace common patterns with Chinese quotation marks「」
    # Pattern: Chinese char + "text" + Chinese char
    # We need to be careful to only replace quotes inside the JSON string values

    # Split by lines and fix each
    lines = content.split('\n')
    fixed_lines = []

    for line in lines:
        # Skip empty lines or structural lines
        if not line.strip() or line.strip() in ['{', '}', '[', ']']:
            fixed_lines.append(line)
            continue

        # For lines with key-value pairs, we need to be careful
        # Pattern: "key": "value"
        # The quotes in Chinese text are typically inside the key or value

        # Replace known problematic patterns
        # "好戏" -> 「好戏」
        # "司时" -> 「司时」
        # etc.

        problematic_patterns = [
            ('"好戏"', '「好戏」'),
            ('"主人"', '「主人」'),
            ('"解脱"', '「解脱」'),
            ('"病苦"', '「病苦」'),
            ('"求不得苦"', '「求不得苦」'),
            ('"爱别离苦"', '「爱别离苦」'),
            ('"五阴炽盛"', '「五阴炽盛」'),
            ('"后卿"', '「后卿」'),
            ('"寂灭"', '「寂灭」'),
            ('"通慧戒师"', '「通慧戒师」'),
            ('"司时"', '「司时」'),
            ('APP"吾家有徒初长成第三赛季"活动', 'APP「吾家有徒初长成第三赛季」活动'),
        ]

        for old, new in problematic_patterns:
            line = line.replace(old, new)

        fixed_lines.append(line)

    return '\n'.join(fixed_lines)

def main():
    trans_file = Path(__file__).parent.parent / "translations" / "translations_all.json"

    with open(trans_file, "r", encoding="utf-8") as f:
        content = f.read()

    fixed_content = fix_json_quotes(content)

    with open(trans_file, "w", encoding="utf-8") as f:
        f.write(fixed_content)

    # Verify
    try:
        with open(trans_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Fixed! Loaded {len(data)} translations successfully.")
    except json.JSONDecodeError as e:
        print(f"Still has errors: {e}")
        # Find the problematic line
        lines = fixed_content.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line in ['{', '}']:
                continue
            test_line = line.rstrip(',')
            test_obj = '{' + test_line + '}'
            try:
                json.loads(test_obj)
            except json.JSONDecodeError as e:
                print(f"Line {i+1}: {e}")
                print(f"Content: {line[:100]}...")
                break

if __name__ == "__main__":
    main()
