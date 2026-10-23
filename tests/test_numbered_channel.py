import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from translation_quality import validate,numbered_channel_value

class NumberedChannelTests(unittest.TestCase):
    def test_equivalent_channel_numbers_and_boundaries(self):
        for source,target in [('线路一','Kênh 1'),('线路七十一','Kênh 71'),('线路一百零一','Kênh 101'),('线路二百','Kênh 200'),('线路二百零一','Kênh 201'),('线路二百一十','Kênh 210'),('线路二百四十五','Kênh 245'),('线路三百','Kênh 300'),('线路九百九十九','Kênh 999')]:
            self.assertFalse(validate(source,target))
    def test_wrong_or_additional_numbers_still_fail(self):
        for target in ['Kênh 72','Kênh 71, nhóm 2','Kênh 7.1','Kênh 071']:
            self.assertIn('literal_numeric_value_changed',validate('线路七十一',target))
        for target in ['Kênh 204','Kênh 245, nhóm 1','Kênh 0245']:
            self.assertIn('literal_numeric_value_changed',validate('线路二百四十五',target))
    def test_other_chinese_numbers_and_malformed_channels_are_not_waived(self):
        self.assertIsNone(numbered_channel_value('线路一一'))
        self.assertIsNone(numbered_channel_value('线路一百一'))
        self.assertIsNone(numbered_channel_value('线路二百一'))
        self.assertIsNone(numbered_channel_value('线路一千'))
        self.assertIn('literal_numeric_value_changed',validate('第十一章','Chương 11'))
        self.assertIn('literal_numeric_value_changed',validate('技能十一层','Kỹ năng tầng 11'))
