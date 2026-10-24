"""Windows settings/DPAPI behavior on inert owned client trees, no key/network."""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'distribution/ChatSettings.ps1'

@unittest.skipUnless(os.name == 'nt', 'Windows DPAPI/PowerShell fixture')
class ChatSettingsTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / 'work/chat-settings-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.game = self.root / 'Game có dấu'
        self.bin = self.game / 'Binaries/Win64'
        self.data = self.bin / 'wojd'
        self.data.mkdir(parents=True)
        exe = self.bin / 'ZhuxianClient-Win64-Shipping.exe'
        exe.write_bytes(b'INERT NEVER EXECUTED')
        (self.data / 'ownership.json').write_text(json.dumps({
            'owner': 'wojd-localization', 'game_exe': str(exe),
        }), encoding='utf-8')
        self.ps = str(pathlib.Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
        self.env = dict(os.environ, PSModulePath=str(pathlib.Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/Modules'))

    def run_settings(self, mode, key=None, script=SCRIPT, prefix='', success=True, use_env=False, env=None, model=None, extra=''):
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        # Only these inert trees: keep the suite independent of a real user's
        # running game. The open-game refusal has a separate explicit fixture.
        guard = "function Get-Process { @() }\n"
        if env is not None and script == SCRIPT:
            # Synthetic Process values only; do not consume a developer's
            # real persistent User/Machine credentials in this inert test.
            source = SCRIPT.read_text(encoding='utf-8-sig').replace(
                '$keyText=[Environment]::GetEnvironmentVariable($Name,$scope)',
                "$keyText=if($scope -eq 'Process'){[Environment]::GetEnvironmentVariable($Name,'Process')}else{$null}")
            script = self.root / 'process-env-fixture.ps1'
            script.write_text(source, encoding='utf-8-sig')
        text = "$ErrorActionPreference='Stop'\n" + guard + prefix + '\n& ' + quote(script) + ' -GameRoot ' + quote(self.game) + ' -Mode ' + mode
        text += ' ' + extra
        if model is not None:
            text += ' -Model ' + quote(model)
        if use_env:
            text += ' -UseEnvironmentKey'
        if key is not None:
            text += (' -DeepLKey (New-Object Security.SecureString)' if key == '' else
                     ' -DeepLKey (ConvertTo-SecureString ' + quote(key) + ' -AsPlainText -Force)')
        shim = self.root / 'run.ps1'
        shim.write_text(text, encoding='utf-8-sig')
        result = subprocess.run([self.ps, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(shim)],
                                capture_output=True, timeout=20, env=env or self.env)
        if success:
            self.assertEqual(result.returncode, 0, (result.stdout + result.stderr).decode(errors='replace'))
        else:
            self.assertNotEqual(result.returncode, 0)
        if key:
            self.assertNotIn(key.encode(), result.stdout + result.stderr)
        return result

    def config(self):
        return (self.data / 'chat.ini').read_bytes()

    def test_off_google_keep_and_no_legacy_activation(self):
        (self.data / 'chat-local.ini').write_bytes(b'old development settings preserved')
        self.run_settings('Off')
        self.assertEqual(self.config(), b'[chat]\r\nenabled=0\r\nprovider=none\r\n')
        self.run_settings('Google')
        before = self.config()
        self.assertIn(b'provider=google-web', before)
        self.run_settings('Keep')
        self.assertEqual(before, self.config())
        self.assertEqual((self.data / 'chat-local.ini').read_bytes(), b'old development settings preserved')

    def test_dpapi_key_roundtrip_reuse_and_removal(self):
        key = '00000000-0000-0000-0000-000000000000:fx'
        self.run_settings('DeepL', key)
        blob = (self.data / 'chat-key-deepl.bin').read_bytes()
        self.assertTrue(blob.startswith(b'WJDK1'))
        self.assertNotIn(key.encode(), blob)
        self.assertIn(b'provider=deepl', self.config())
        self.run_settings('DeepL', '')
        self.assertEqual(blob, (self.data / 'chat-key-deepl.bin').read_bytes())
        # Decrypt with the Windows account/entropy shared with native C.
        verify = self.root / 'verify.ps1'
        verify.write_text("Add-Type -AssemblyName System.Security\n"
            "$b=[IO.File]::ReadAllBytes('" + str(self.data / 'chat-key-deepl.bin').replace("'", "''") + "')\n"
            "$p=[Security.Cryptography.ProtectedData]::Unprotect($b[5..($b.Length-1)],"
            "[Text.Encoding]::ASCII.GetBytes('WOJD-CHAT-KEY-V1'),[Security.Cryptography.DataProtectionScope]::CurrentUser)\n"
            "if([Text.Encoding]::ASCII.GetString($p) -cne '" + key + "'){exit 1}\n[Array]::Clear($p,0,$p.Length)\n",
            encoding='utf-8-sig')
        result = subprocess.run([self.ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(verify)], capture_output=True, timeout=20, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.run_settings('Google')
        self.assertFalse((self.data / 'chat-key-deepl.bin').exists())
        self.run_settings('DeepL', key)
        self.run_settings('Off')
        self.assertFalse((self.data / 'chat-key-deepl.bin').exists())

    def test_invalid_input_and_open_game_leave_files_untouched(self):
        self.run_settings('Google')
        before = self.config()
        self.run_settings('DeepL', 'bad key with spaces', success=False)
        self.assertEqual(before, self.config())
        self.run_settings('Off', prefix="function Get-Process { [pscustomobject]@{ProcessName='ZhuxianClient'} }", success=False)
        self.assertEqual(before, self.config())
        self.assertFalse((self.data / 'chat-key-deepl.bin').exists())

    def test_final_publish_failure_restores_config_and_encrypted_key(self):
        self.run_settings('DeepL', '00000000-0000-0000-0000-000000000000:fx')
        before = self.config()
        blob = (self.data / 'chat-key-deepl.bin').read_bytes()
        source = SCRIPT.read_text(encoding='utf-8-sig')
        needle = '    Chat-Closed\n    Chat-Require (Chat-Same (Chat-Read $Path) $Expected)'
        self.assertEqual(source.count(needle), 1)
        source = source.replace(needle,
            '    $script:fixtureWrites++\n    if($script:fixtureWrites -eq 6){throw "inert final publish fault"}\n' + needle)
        source = source.replace("$lock=$null;$createdKeys=", "$script:fixtureWrites=0\n$lock=$null;$createdKeys=")
        fault = self.root / 'fault.ps1'
        fault.write_text(source, encoding='utf-8-sig')
        self.run_settings('Google', script=fault, success=False)
        self.assertEqual(before, self.config())
        self.assertEqual(blob, (self.data / 'chat-key-deepl.bin').read_bytes())

    def test_environment_key_opt_in_and_interactive_choice(self):
        key = '11111111-1111-1111-1111-111111111111:fx'
        env = dict(self.env, DEEPL_KEY=key)
        result = self.run_settings('DeepL', use_env=True, env=env)
        self.assertNotIn(key.encode(), result.stdout+result.stderr)
        blob = (self.data/'chat-key-deepl.bin').read_bytes()
        self.assertTrue(blob.startswith(b'WJDK1'))
        self.assertNotIn(key.encode(), blob)
        self.run_settings('Off')
        result = self.run_settings('Menu', env=env, prefix="""
function Read-Host {
 param([string]$Prompt,[switch]$AsSecureString)
 if($Prompt.StartsWith('Chọn')){return '2'}
 if($Prompt.StartsWith('Đổi riêng') -or $Prompt.StartsWith('Số mục cache')){return ''}
 if($Prompt.StartsWith('Dùng key')){return ''}
 throw 'Unexpected prompt in inert fixture'
}
""")
        self.assertNotIn(key.encode(), result.stdout+result.stderr)
        self.assertIn(b'provider=deepl',self.config())

    def test_persistent_environment_refresh_without_touching_user_variables(self):
        key = '22222222-2222-2222-2222-222222222222:fx'
        source = SCRIPT.read_text(encoding='utf-8-sig')
        needle = "$keyText=[Environment]::GetEnvironmentVariable($Name,$scope)"
        self.assertEqual(source.count(needle),1)
        # Simulate a stale parent process and a freshly added User variable.
        # Never modify the developer's real Windows environment or key.
        source = source.replace(needle,"$keyText=if($scope -eq 'User'){'"+key+"'}else{$null}")
        script = self.root/'refresh-fixture.ps1'
        script.write_text(source,encoding='utf-8-sig')
        result = self.run_settings('DeepL',script=script,use_env=True)
        self.assertNotIn(key.encode(),result.stdout+result.stderr)
        self.assertIn(b'provider=deepl',self.config())
        self.assertNotIn(key.encode(),(self.data/'chat-key-deepl.bin').read_bytes())

    def test_llm_provider_key_binding_and_model_switch(self):
        key = 'synthetic-key-for-native-llm-only-123456'
        self.run_settings('Gemini', key, model='gemini-3.6-flash')
        before = (self.data/'chat-key-gemini.bin').read_bytes()
        self.assertTrue(before.startswith(b'WJDK25'))
        self.assertNotIn(key.encode(), before)
        self.assertIn(b'model=gemini-3.6-flash', self.config())
        self.run_settings('Gemini', '', model='gemini-3.1-flash-lite')
        self.assertEqual(before, (self.data/'chat-key-gemini.bin').read_bytes())
        self.assertIn(b'model=gemini-3.1-flash-lite', self.config())
        self.run_settings('DeepSeek', '', success=False)
        self.assertEqual(before, (self.data/'chat-key-gemini.bin').read_bytes())
        self.run_settings('DeepSeek', key)
        self.assertFalse((self.data/'chat-key-gemini.bin').exists())
        self.assertTrue((self.data/'chat-key-deepseek.bin').read_bytes().startswith(b'WJDK24'))
        self.assertIn(b'model=deepseek-flash', self.config())
        before_config = self.config()
        self.run_settings('Gemini', key, model='../arbitrary?api-key=', success=False)
        self.assertEqual(before_config, self.config())

    def test_gemini_model_menu_and_key_security_notice(self):
        env = dict(self.env, GEMINI_API_KEY='synthetic-gemini-environment-key-123456')
        result = self.run_settings('Menu', env=env, prefix="""
function Read-Host {
 param([string]$Prompt,[switch]$AsSecureString)
 if($Prompt.StartsWith('Chọn model')){return '2'}
 if($Prompt.StartsWith('Chọn')){return '4'}
 if($Prompt.StartsWith('Đổi riêng') -or $Prompt.StartsWith('Số mục cache')){return ''}
 if($Prompt.StartsWith('Dùng key')){return ''}
 throw 'Unexpected prompt in inert fixture'
}
""")
        self.assertIn(b'provider=gemini', self.config())
        self.assertIn(b'model=gemini-3.1-flash-lite', self.config())
        text = result.stdout.decode('utf-8', errors='replace')
        self.assertIn('livestream', text)
        self.assertNotIn(env['GEMINI_API_KEY'].encode(), result.stdout+result.stderr)

    def test_multiple_services_channel_models_cache_and_cleanup(self):
        env = dict(self.env, GEMINI_API_KEY='synthetic-gemini-key-123456789',
                   DEEPSEEK_API_KEY='synthetic-deepseek-key-123456789')
        routes = "-Channels @{world=@{Provider='google-web'};squad=@{Provider='deepseek'};team=@{Provider='gemini';Model='gemini-3.1-flash-lite'};friend=@{Provider='none'}} -CacheEntries 512"
        result = self.run_settings('Gemini', use_env=True, env=env, extra=routes)
        config = self.config()
        for text in (b'cache_entries=512', b'cache_idle_minutes=10',
                     b'[channel.world]\r\nprovider=google-web',
                     b'[channel.squad]\r\nprovider=deepseek\r\nmodel=deepseek-flash',
                     b'[channel.team]\r\nprovider=gemini\r\nmodel=gemini-3.1-flash-lite',
                     b'[channel.friend]\r\nprovider=none'):
            self.assertIn(text, config)
        for provider, header in (('gemini', b'WJDK25'), ('deepseek', b'WJDK24')):
            blob = (self.data / ('chat-key-'+provider+'.bin')).read_bytes()
            self.assertTrue(blob.startswith(header))
            self.assertNotIn(env[provider.upper()+'_API_KEY'].encode(), blob+result.stdout+result.stderr)
        self.assertFalse((self.data/'chat-key.bin').exists())
        before = {p.name:p.read_bytes() for p in self.data.glob('chat*')}
        self.run_settings('Google', extra="-Channels @{recruitment=@{Provider='google-web'}}", success=False)
        self.run_settings('Google', extra='-CacheEntries 8193', success=False)
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.data.glob('chat*')})
        self.run_settings('Off')
        self.assertFalse(list(self.data.glob('chat-key*.bin')))

    def test_legacy_key_migration_and_multiple_key_final_publish_rollback(self):
        self.run_settings('Gemini', 'synthetic-gemini-key-123456789')
        saved = (self.data/'chat-key-gemini.bin').read_bytes()
        (self.data/'chat-key-gemini.bin').rename(self.data/'chat-key.bin')
        self.run_settings('Gemini', '')
        self.assertFalse((self.data/'chat-key.bin').exists())
        self.assertEqual(saved, (self.data/'chat-key-gemini.bin').read_bytes())
        env = dict(self.env, GEMINI_API_KEY='synthetic-gemini-key-123456789',
                   DEEPSEEK_API_KEY='synthetic-deepseek-key-123456789')
        self.run_settings('Gemini', use_env=True, env=env,
                          extra="-Channels @{squad=@{Provider='deepseek'}}")
        before = {p.name:p.read_bytes() for p in self.data.glob('chat*')}
        source = SCRIPT.read_text(encoding='utf-8-sig')
        needle = '    Chat-Closed\n    Chat-Require (Chat-Same (Chat-Read $Path) $Expected)'
        source = source.replace(needle, '    $script:fixtureWrites++\n    if($script:fixtureWrites -eq 6){throw "inert commit fault"}\n'+needle)
        source = source.replace('$lock=$null;$createdKeys=', '$script:fixtureWrites=0\n$lock=$null;$createdKeys=')
        fault = self.root/'multi-fault.ps1'
        fault.write_text(source, encoding='utf-8-sig')
        self.run_settings('Google', script=fault, success=False)
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.data.glob('chat*')})

    def test_menu_only_selected_channels_and_cache(self):
        env = dict(self.env, GEMINI_API_KEY='synthetic-gemini-key-123456789')
        result = self.run_settings('Menu', env=env, prefix="""
$global:channelsChosen=0
function Read-Host {
 param([string]$Prompt,[switch]$AsSecureString)
 if($Prompt.StartsWith('Chọn dịch vụ')){return '6'}
 if($Prompt.StartsWith('Số kênh')){ $global:channelsChosen++; if($global:channelsChosen -eq 1){return '3'}else{return ''} }
 if($Prompt.StartsWith('Dịch vụ cho')){return '5'}
 if($Prompt.StartsWith('Chọn model')){return '2'}
 if($Prompt.StartsWith('Số mục cache')){return '512'}
 if($Prompt.StartsWith('Dùng key')){return ''}
 throw 'Unexpected prompt in inert fixture'
}
""")
        self.assertIn(b'enabled=1\r\nprovider=none', self.config())
        self.assertIn(b'[channel.squad]\r\nprovider=gemini\r\nmodel=gemini-3.1-flash-lite', self.config())
        self.assertIn(b'cache_entries=512', self.config())
        self.assertNotIn(env['GEMINI_API_KEY'].encode(), result.stdout+result.stderr)

if __name__ == '__main__':
    unittest.main()
