import pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from catalog_core import write_ndjson,source_id
from quality_tracking import mark,report

class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.root=pathlib.Path(self.temp.name)
        self.catalog=self.root/'catalog.ndjson';self.other=self.root/'other.ndjson';self.ledger=self.root/'quality.ndjson';self.review=self.root/'review.ndjson'
    def tearDown(self):self.temp.cleanup()
    def decision(self,target='Giáp%d'):
        return dict(source='甲%d',source_sha256=source_id('甲%d'),status='translated',translated=target)
    def test_structural_pass_does_not_grant_language_review(self):
        write_ndjson(self.catalog,[self.decision()])
        result=report([self.catalog],self.ledger)
        self.assertEqual(result['unique_source_quality'],{'unreviewed':1});self.assertEqual(result['structural_qa_failures'],0)
    def test_evidence_is_bound_to_target_and_survives_runtime_id_changes(self):
        write_ndjson(self.catalog,[dict(self.decision(),key='first')]);write_ndjson(self.review,[self.decision()])
        mark(self.ledger,self.review,[self.catalog],'source_reviewed','reviewer','Compared with CN')
        write_ndjson(self.catalog,[dict(self.decision(),key='new-id')])
        self.assertEqual(report([self.catalog],self.ledger)['unique_source_quality'],{'source_reviewed':1})
        write_ndjson(self.catalog,[self.decision('Ất%d')])
        result=report([self.catalog],self.ledger)
        self.assertEqual(result['unique_source_quality'],{'unreviewed':1});self.assertEqual(result['unused_evidence_records'],1)
    def test_same_source_different_route_translation_requires_separate_review(self):
        write_ndjson(self.catalog,[self.decision()]);write_ndjson(self.other,[self.decision('Giáp khác%d')]);write_ndjson(self.review,[self.decision()])
        mark(self.ledger,self.review,[self.catalog,self.other],'source_reviewed','reviewer','Compared with CN')
        self.assertEqual(report([self.catalog,self.other],self.ledger)['unique_source_quality'],{'unreviewed':1})
    def test_stale_or_invalid_import_is_atomic_and_ignore_is_separate(self):
        write_ndjson(self.catalog,[self.decision(),dict(source='内部',status='ignore',translated=None)])
        write_ndjson(self.review,[self.decision(),self.decision('Sai%s')])
        with self.assertRaises(ValueError):mark(self.ledger,self.review,[self.catalog],'source_reviewed','reviewer','evidence')
        self.assertFalse(self.ledger.exists())
        self.assertEqual(report([self.catalog],self.ledger)['unique_source_quality'],{'ignore':1,'unreviewed':1})

if __name__=='__main__':unittest.main()
