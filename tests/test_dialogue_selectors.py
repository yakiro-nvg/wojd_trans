import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from translation_quality import validate,visible_text

class DialogueSelectorTests(unittest.TestCase):
    def test_branch_labels_and_colon_forms_are_immutable(self):
        source='青云女:师兄。\n灵汐萝莉：师兄。'
        self.assertFalse(validate(source,'青云女:Sư huynh.\n灵汐萝莉：Sư huynh.'))
        self.assertIn('dialogue_variant_selector_changed',validate(source,'Nữ Thanh Vân:Sư huynh.\nLinh Tịch bé gái：Sư huynh.'))
        self.assertIn('dialogue_variant_selector_changed',validate(source,'青云女：Sư huynh.\n灵汐萝莉：Sư huynh.'))

    def test_literal_newline_order_and_variant_visible_text(self):
        source='原版：你好\\n焚香少女：师兄'
        target='原版：Xin chào\\n焚香少女：Sư huynh'
        self.assertFalse(validate(source,target))
        self.assertNotIn('焚香少女',visible_text(target))
        self.assertIn('dialogue_variant_selector_changed',validate(source,'焚香少女：Xin chào\\n原版：Sư huynh'))

    def test_single_speaker_in_ordinary_prose_is_not_branch_contract(self):
        self.assertFalse(validate('青云：你好','Thanh Vân: Xin chào'))

    def test_numeric_sexif_keeps_both_original_colon_forms(self):
        for colon in (':','：'):
            with self.subTest(colon=colon):
                self.assertFalse(validate(f'(@@SexIf)12(/SexIf){colon}你好。',
                                          f'(@@SexIf)12(/SexIf){colon}Xin chào.'))

    def test_numeric_sexif_colon_conversion_or_removal_is_rejected(self):
        source='(@@SexIf)12(/SexIf)：你好。'
        for prefix in ('(@@SexIf)12(/SexIf):','(@@SexIf)12(/SexIf)'):
            with self.subTest(prefix=prefix):
                self.assertIn('numeric_sexif_prefix_changed',validate(source,prefix+'Xin chào.'))

    def test_numeric_sexif_id_and_closing_marker_are_preserved(self):
        source='(@@SexIf)12(/SexIf)：你好。'
        for target in ('(@@SexIf)13(/SexIf)：Xin chào.',
                       '(@@SexIf)12(/ClassIf)：Xin chào.'):
            with self.subTest(target=target):
                self.assertIn('numeric_sexif_prefix_changed',validate(source,target))

    def test_numeric_sexif_cannot_be_created_or_moved(self):
        source='(@@SexIf)12(/SexIf)：你好。'
        self.assertIn('numeric_sexif_prefix_changed',
                      validate(source,'Xin chào.(@@SexIf)12(/SexIf)：'))
        self.assertIn('numeric_sexif_prefix_changed',
                      validate('你好。','(@@SexIf)12(/SexIf)：Xin chào.'))

    def test_body_colons_are_not_numeric_sexif_prefixes(self):
        self.assertFalse(validate('提示：你好。','Gợi ý: Xin chào.'))
        self.assertFalse(validate('(@@SexIf)12(/SexIf)：提示：你好。',
                                  '(@@SexIf)12(/SexIf)：Gợi ý: Xin chào.'))
