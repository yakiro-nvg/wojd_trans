"""Prevent a canonical UI fix from shipping with stale embedded bytecode."""
import hashlib
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class ChatTemplateSourceTests(unittest.TestCase):
    def test_compiled_adapter_is_pinned_to_current_canonical_source(self):
        source = (ROOT/'native/src/chat_receive_rows.lua').read_bytes()
        header = (ROOT/'native/src/chat_receive_templates.h').read_text(encoding='utf-8')
        self.assertIn('/* source-sha256: '+hashlib.sha256(source).hexdigest()+' */', header)

if __name__ == '__main__':
    unittest.main()
