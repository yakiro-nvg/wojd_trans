import pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from sanitize_editorial_metadata import clean

class PublicMetadataTests(unittest.TestCase):
    def test_only_local_evidence_paths_change(self):
        row=dict(source=r'C:\Game\甲.png',translated='Tương truyền\nDòng',namespace='NS',key='id',source_sha256='f'*64,status='translated',level='source_reviewed',note=r'Review D:\private\review.json SHA abc',context=dict(file=dict(path='/home/person/work/proof.ndjson',sha256='a'*64),source='甲'))
        result=clean(row)
        for key in ['source','translated','namespace','key','source_sha256','status','level']:
            self.assertEqual(result[key],row[key])
        self.assertEqual(result['context']['source'],'甲')
        self.assertEqual(result['context']['file'],dict(path='local-evidence/proof.ndjson',sha256='a'*64))
        self.assertEqual(result['note'],'Review local-evidence/review.json SHA abc')

if __name__=='__main__':unittest.main()
