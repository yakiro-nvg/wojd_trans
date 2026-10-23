import pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_package import residual_bindings

class ResidualBindingTests(unittest.TestCase):
    def test_cn_widget_identity_is_kept_while_actual_native_vi_is_rejected(self):
        widget=dict(namespace='',key='widget-guid',source='聚灵',translated='Tụ Linh',status='translated')
        self.assertEqual(residual_bindings([widget],{'Tụ Linh'}),{('', 'widget-guid'):widget})
        already_vi=dict(widget,source='Tụ Linh')
        with self.assertRaisesRegex(ValueError,'already substituted'):
            residual_bindings([already_vi],{'Tụ Linh'})

    def test_same_key_with_distinct_source_variants_cannot_silently_overwrite(self):
        a=dict(namespace='',key='shared',source='聚灵',translated='Tụ Linh')
        b=dict(namespace='',key='shared',source='升级',translated='Nâng cấp')
        with self.assertRaisesRegex(ValueError,'runtime binding resolution'):
            residual_bindings([a,b],set())

if __name__=='__main__':unittest.main()
