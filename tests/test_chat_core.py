import threading
import time
import unittest

from chat_companion.core import ChatService, protect_text, restore_text, validate_target_language
from chat_companion.providers import TranslationError


class ChatCoreTests(unittest.TestCase):
    def wait_result(self, service, count=1):
        events=[]
        until=time.monotonic()+3
        while time.monotonic()<until:
            events.extend(service.poll())
            done=[e for e in events if e.status in ('TRANSLATED','ERROR','SKIPPED')]
            if len(done)>=count: return done
            time.sleep(.005)
        self.fail('Translation did not complete')

    def test_token_roundtrip_and_duplicates(self):
        text='你好 {玩家} 20:30 <color=red>3</color> https://example.org/8'
        protected,tokens=protect_text(text)
        self.assertEqual(restore_text(protected,protected,tokens),text)
        with self.assertRaises(TranslationError):
            restore_text(protected,protected+' __WOJD_T0__',tokens)
        with self.assertRaises(TranslationError):
            restore_text(protected,protected.replace('20:30','20:31'),tokens)
        for source,target in [('-125','125'), ('20%','20'), ('+3','3')]:
            with self.assertRaises(TranslationError): restore_text(source,target,[])

    def test_cache_does_not_suppress_repeated_messages(self):
        class Provider:
            calls=0
            def translate(self,*args):
                self.calls+=1
                return 'Xin chào'
        provider=Provider(); service=ChatService(provider)
        try:
            first=service.submit('你好')
            second=service.submit('你好')
            done=self.wait_result(service,2)
            self.assertNotEqual(first,second)
            self.assertEqual(provider.calls,1)
            self.assertTrue(all(e.original=='你好' and e.translation=='Xin chào' for e in done))
        finally: service.close()

    def test_bounded_queue_is_nonblocking_and_commands_are_not_translated(self):
        gate=threading.Event()
        class Provider:
            def translate(self,*args): gate.wait(2); return 'xin chào'
        service=ChatService(Provider(),max_pending=1)
        try:
            self.assertIsNotNone(service.submit('你好'))
            self.assertIsNone(service.submit('再见'))
            self.assertEqual(service.pending_count,1)
            self.assertEqual(service.dropped_events,1)
            service.submit('/party hi',direction='outgoing')
            self.assertEqual(self.wait_result(service)[0].status,'SKIPPED')
        finally: gate.set(); service.close()

    def test_bad_output_retains_original_without_translation(self):
        class Provider:
            def translate(self,*args): return 'Có 2 người'
        service=ChatService(Provider())
        try:
            service.submit('有3个人')
            result=self.wait_result(service)[0]
            self.assertEqual(result.status,'ERROR')
            self.assertEqual(result.original,'有3个人')
            self.assertIsNone(result.translation)
        finally: service.close()

    def test_provider_error_does_not_expose_unhandled_exception(self):
        class Provider:
            def translate(self,*args): raise RuntimeError('private payload')
        service=ChatService(Provider())
        try:
            service.submit('你好')
            result=self.wait_result(service)[0]
            self.assertNotIn('private payload',result.error)
        finally: service.close()

    def test_obviously_wrong_chinese_script_is_not_marked_vietnamese(self):
        with self.assertRaises(TranslationError): validate_target_language('这是一段中文翻译。','vi')
        validate_target_language('Gặp Linh tại cổng thành.','vi')
        validate_target_language('你好','zh-Hans')

    def test_terminal_events_survive_other_status_transitions(self):
        gate=threading.Event()
        class Provider:
            def translate(self,*args): gate.wait(2); return 'xin chào'
        service=ChatService(Provider(),max_pending=32)
        try:
            for _ in range(32): service.submit('你好')
            ids=[service.submit('中'*4001) for _ in range(200)]
            gate.set()
            until=time.monotonic()+2
            while service.pending_count and time.monotonic()<until: time.sleep(.005)
            events={e.id:e for e in service.poll()}
            self.assertTrue(all(events[i].status=='ERROR' for i in ids))
            self.assertEqual(service.dropped_events,0)
        finally: gate.set(); service.close()

    def test_close_discards_waiting_provider_calls(self):
        started=threading.Event(); gate=threading.Event()
        class Provider:
            calls=0
            def translate(self,*args):
                self.calls+=1; started.set(); gate.wait(2); return 'xin chào'
        provider=Provider(); service=ChatService(provider)
        try:
            service.submit('你好'); service.submit('再见')
            self.assertTrue(started.wait(1))
            service.close(); gate.set(); service._worker.join(2)
            self.assertEqual(provider.calls,1)
            self.assertEqual(service.pending_count,0)
        finally: gate.set(); service.close()


if __name__=='__main__': unittest.main()
