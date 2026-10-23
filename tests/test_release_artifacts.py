import hashlib,json,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from stage_release_artifacts import stage_release

class ReleaseArtifactTests(unittest.TestCase):
    def make(self,root,nested):
        source=root/'download';content=source/'artifacts' if nested else source;content.mkdir(parents=True)
        data=b'inert player archive';sha=hashlib.sha256(data).hexdigest()
        (content/'VI_PATCH.zip').write_bytes(data)
        (content/'checksums.txt').write_text(sha+'  VI_PATCH.zip\n',encoding='ascii')
        (content/'vi-build.json').write_text(json.dumps(dict(source_revision='fixture',variants=dict(base=dict(file='VI_PATCH.zip',sha256=sha)))),encoding='utf-8')
        return source,content,sha

    def test_flat_and_common_root_artifacts_produce_same_release_files(self):
        for nested in [False,True]:
            with tempfile.TemporaryDirectory(dir=ROOT/'work') as directory:
                root=pathlib.Path(directory);source,content,sha=self.make(root,nested)
                (source/'reports').mkdir();(source/'reports/quality.json').write_text('{}')
                self.assertEqual(stage_release(source,root/'release','fixture'),sha)
                self.assertEqual(sorted(p.name for p in (root/'release').iterdir()),['VI_PATCH.zip','checksums.txt','vi-build.json'])

    def test_wrong_revision_checksum_and_ambiguous_members_reject_before_copy(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as directory:
            root=pathlib.Path(directory);source,content,sha=self.make(root,True)
            with self.assertRaises(ValueError):stage_release(source,root/'release','other-revision')
            (content/'checksums.txt').write_text('bad VI_PATCH.zip\n')
            with self.assertRaises(ValueError):stage_release(source,root/'release','fixture')
            (source/'VI_PATCH.zip').write_bytes(b'duplicate')
            with self.assertRaises(ValueError):stage_release(source,root/'release','fixture')
            self.assertFalse((root/'release').exists())

if __name__=='__main__':unittest.main()
