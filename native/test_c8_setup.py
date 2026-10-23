"""Run C8 setup fixtures in private build output; never opens the game."""
import json,os,pathlib,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'native/build/c8-setup'
assert OUT.is_dir(),'Build runtime-test first'
temporary=OUT/'tmp';temporary.mkdir(exist_ok=True)
environment=dict(os.environ,TEMP=str(temporary),TMP=str(temporary))
results=[]
for name,wanted in [('allocator_fixture',20),('plain_skill_fixture',35),('setup_integration_fixture',37)]:
    completed=subprocess.run([str(OUT/(name+'.exe'))],cwd=OUT,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='strict',timeout=90)
    (OUT/(name+'.log')).write_text(completed.stdout,encoding='utf-8')
    match=re.search(r'(?:RESULT|SUMMARY) checks=(\d+) failures=(\d+)',completed.stdout)
    passed=completed.returncode==0 and match is not None and int(match[1])==wanted and int(match[2])==0
    results.append(dict(fixture=name,status='PASS' if passed else 'FAIL',exit_code=completed.returncode,expected_checks=wanted,checks=int(match[1]) if match else None,failures=int(match[2]) if match else None))
    if not passed:
        (ROOT/'native/build/c8-setup-results.json').write_text(json.dumps(dict(status='FAIL',results=results),indent=2),encoding='utf-8')
        raise AssertionError((name,completed.returncode,completed.stdout))
(ROOT/'native/build/c8-setup-results.json').write_text(json.dumps(dict(status='PASS',checks=92,failures=0,game_opened=False,captured_code_executed=False,results=results),indent=2),encoding='utf-8')
print('C8 setup fixtures: 92 checks passed')
