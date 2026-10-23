"""Archive lifecycle tests with independent, short-lived Python processes."""
import ctypes,hashlib,json,pathlib,subprocess,sys,tempfile,time,unittest
from ctypes import wintypes
ROOT=pathlib.Path(__file__).resolve().parents[1]

def wait_for(test,seconds=12):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if test():return
        time.sleep(.05)
    raise AssertionError('Timed out waiting for fixture')

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='Việt archive ',dir=ROOT/'work');self.root=pathlib.Path(self.temp.name)
        self.data=self.root/'wojd';self.session=self.data/'logs/fixture';self.session.mkdir(parents=True)
        self.log=self.root/'Game.log';self.stop=self.root/'stop';self.child=None;self.archive=None
        self.exe=self.root/'inert.exe';self.exe.write_bytes(b'never executed')
        (self.data/'catalog.bin').write_bytes(b'catalog fixture')
        (self.data/'settings.json').write_text(json.dumps(dict(ue_log_path=str(self.log))))
        (self.data/'install-state.json').write_text(json.dumps(dict(game_exe=str(self.exe),source_revision='fixture',profile='dump')))
        self.child=subprocess.Popen([sys.executable,'-c',
            "import pathlib,sys,time; p=pathlib.Path(sys.argv[1]); p.write_bytes(b'first\\n'); stop=pathlib.Path(sys.argv[2]);\nwhile not stop.exists():time.sleep(.03)\nwith p.open('ab') as f:f.write(b'last\\n')",
            str(self.log),str(self.stop)],creationflags=subprocess.CREATE_NO_WINDOW)
        wait_for(self.log.exists)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
        times=[wintypes.FILETIME() for _ in range(4)]
        assert kernel.GetProcessTimes(int(self.child._handle),*[ctypes.byref(t) for t in times])
        birth=times[0].dwLowDateTime+(times[0].dwHighDateTime<<32)
        self.metadata=dict(pid=self.child.pid,process_creation_filetime=birth)
        self.write_metadata()
    def write_metadata(self):
        (self.session/'session.json').write_text(json.dumps(self.metadata))
    def run_archive(self):
        self.archive=subprocess.Popen(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'distribution/Archive-Session.ps1'),'-Session',str(self.session)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    def wait_archive_ready(self,seconds=60):
        """Observe copied/flushed fixture bytes; a pathname alone is too early."""
        until=time.monotonic()+seconds
        archived=self.session/'ZhuxianClient.log'
        last_read_error=None
        while time.monotonic()<until:
            if self.archive.poll() is not None:
                out,err=self.archive.communicate(timeout=5)
                result=self.session/'archive-result.json'
                report=result.read_text(encoding='utf-8-sig') if result.exists() else '<no result>'
                self.fail(f'Archive observer exited before readiness: exit={self.archive.returncode}; stdout={out!r}; stderr={err!r}; report={report}')
            try:
                if archived.read_bytes()==b'first\n':return
            except OSError as error:
                last_read_error=repr(error)
            time.sleep(.05)
        # The child intentionally stays alive until readiness. Do not call
        # communicate here: a healthy observer is still waiting for that child.
        result=self.session/'archive-result.json'
        report=result.read_text(encoding='utf-8-sig') if result.exists() else '<no result>'
        source_stat=self.log.stat() if self.log.exists() else None
        self.fail(f'Archive readiness deadline: observer_exit={self.archive.poll()}; child_exit={self.child.poll()}; claim={(self.session/"archive.claim").exists()}; build={(self.session/"build.json").exists()}; source_stat={source_stat}; process_birth={self.metadata["process_creation_filetime"]}; last_read_error={last_read_error}; report={report}')
    def finish(self,success=True):
        out,err=self.archive.communicate(timeout=45)
        report=json.loads((self.session/'archive-result.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(report['complete'],success,(out,err,report))
        self.assertEqual(self.archive.returncode,0 if success else 1,(out,err))
        return report
    def tearDown(self):
        for process in [self.child,self.archive]:
            if process and process.poll() is None:process.kill();process.wait(timeout=5)
        self.temp.cleanup()
    def test_exit_and_rotation_archive_retained_handle_not_replacement(self):
        self.run_archive();self.wait_archive_ready()
        rotated=self.root/'Game-previous.log';self.log.rename(rotated)
        self.log.write_bytes(b'different new log')
        with rotated.open('ab') as dst:dst.write(b'kept on old handle\n')
        self.child.kill();self.child.wait(timeout=5);report=self.finish()
        self.assertEqual((self.session/'ZhuxianClient.log').read_bytes(),rotated.read_bytes())
        self.assertEqual(report['sha256'],hashlib.sha256(rotated.read_bytes()).hexdigest())
        before=(self.session/'archive-result.json').read_bytes();self.run_archive()
        self.archive.communicate(timeout=10);self.assertNotEqual(self.archive.returncode,0)
        self.assertEqual((self.session/'archive-result.json').read_bytes(),before)
    def test_normal_exit_includes_tail(self):
        self.run_archive();self.wait_archive_ready()
        self.stop.touch();self.child.wait(timeout=5);self.finish()
        self.assertEqual((self.session/'ZhuxianClient.log').read_bytes(),b'first\nlast\n')
    def test_pid_generation_mismatch_never_archives_another_run(self):
        self.metadata['process_creation_filetime']+=1;self.write_metadata();self.run_archive()
        report=self.finish(False);self.assertIn('generation mismatch',report['error'])
        self.assertFalse((self.session/'ZhuxianClient.log').exists())

if __name__=='__main__':unittest.main()
