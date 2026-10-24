"""Lifecycle, ownership, migration, rollback, race and fault tests on inert trees."""
import os,pathlib,subprocess,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.name=='nt','Windows PowerShell 5.1 fixture')
class InstallerTests(unittest.TestCase):
    def test_62_independent_synthetic_tree_scenarios(self):
        result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tests/installer_scenarios.py')],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=360)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('"tests": 62',result.stdout)

if __name__=='__main__':unittest.main()
