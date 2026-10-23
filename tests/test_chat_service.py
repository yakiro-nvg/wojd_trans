"""Actual loopback HTTP protocol tests; all text/providers/tokens are synthetic."""
import contextlib
import hashlib
import http.client
import io
import json
from pathlib import Path
import secrets
import tempfile
import threading
import time
import unittest

from chat_companion.providers import TranslationError
from chat_companion.service import (MAX_BODY_BYTES, MAX_SOURCE_CHARS, TranslationHTTPServer,
                                    load_provider)


class FakeProvider:
    def __init__(self, *, blocked=False, error=False, output="Bản dịch"):
        self.started, self.release = threading.Event(), threading.Event()
        self.error, self.output, self.calls = error, output, []
        if not blocked:
            self.release.set()

    def translate(self, text, source, target):
        self.calls.append((text, source, target))
        self.started.set()
        self.release.wait(3)
        if self.error:
            raise TranslationError("DO NOT DISCLOSE synthetic text or synthetic secret")
        return self.output


class TranslationServiceTests(unittest.TestCase):
    def start(self, provider=None, **kwargs):
        self.provider = provider or FakeProvider()
        self.token = secrets.token_hex(32)
        self.server = TranslationHTTPServer(0, self.provider, self.token, **kwargs)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        def close(provider=self.provider, server=self.server, thread=self.thread):
            provider.release.set()
            server.shutdown()
            server.server_close()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertFalse(server.jobs.worker.is_alive())
            self.assertEqual(len(server.jobs.records), 0)
        self.addCleanup(close)

    def request(self, path, value=None, *, token=True, headers=None, raw=None, method="POST"):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        self.addCleanup(connection.close)
        body = raw if raw is not None else json.dumps(value, ensure_ascii=True).encode("ascii")
        actual_headers = {"Content-Type": "application/json"}
        if token:
            actual_headers["Authorization"] = "Bearer " + (self.token if token is True else token)
        actual_headers.update(headers or {})
        connection.request(method, path, body=body, headers=actual_headers)
        response = connection.getresponse()
        result = json.loads(response.read())
        self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))
        self.assertEqual(response.getheader("Cache-Control"), "no-store")
        return response.status, result

    def submission(self, *, text="synthetic message", session="session_a", request="request_a", **extra):
        value = {"session_id": session, "request_id": request,
                 "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                 "source_text": text, "target_language": "vi", "direction": "incoming"}
        value.update(extra)
        return value

    def handle(self, result):
        return {key: result[key] for key in ("session_id", "request_id", "request_nonce")}

    def terminal(self, handle):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            status, result = self.request("/v1/result", handle)
            self.assertEqual(status, 200)
            if result["state"] not in ("QUEUED", "TRANSLATING"):
                return result
            time.sleep(0.01)
        self.fail("Synthetic job did not finish")

    def test_async_exact_binding_and_no_source_echo_or_request_log(self):
        provider = FakeProvider(blocked=True)
        self.start(provider)
        source = self.submission(text="synthetic private message")
        log = io.StringIO()
        with contextlib.redirect_stderr(log):
            start = time.monotonic()
            status, accepted = self.request("/v1/translate", source)
            self.assertLess(time.monotonic() - start, 0.5)
            self.assertEqual(status, 202)
            self.assertEqual(accepted["session_id"], source["session_id"])
            self.assertEqual(accepted["request_id"], source["request_id"])
            self.assertEqual(accepted["source_sha256"], source["source_sha256"])
            self.assertEqual(len(accepted["request_nonce"]), 64)
            self.assertNotIn("source_text", accepted)
            self.assertNotIn(source["source_text"], json.dumps(accepted))
            self.assertTrue(provider.started.wait(1))
            _, pending = self.request("/v1/result", self.handle(accepted))
            self.assertEqual(pending["state"], "TRANSLATING")
            provider.release.set()
            done = self.terminal(self.handle(accepted))
        self.assertEqual(done["translation"], "Bản dịch")
        self.assertEqual(done["state"], "TRANSLATED")
        self.assertEqual(provider.calls[0][1:], (None, "vi"))
        self.assertEqual(log.getvalue(), "")
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_auth_origin_host_and_no_browser_or_command_surface(self):
        self.start()
        for token in (False, "wrong"):
            self.assertEqual(self.request("/v1/translate", self.submission(), token=token)[0], 401)
        for origin in ("https://example.org", "null"):
            self.assertEqual(self.request("/v1/translate", self.submission(), headers={"Origin": origin})[0], 403)
        self.assertEqual(self.request("/v1/translate", self.submission(), headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("/shutdown", {})[0], 404)
        self.assertEqual(self.request("/v1/translate?token=x", {})[0], 404)
        self.assertEqual(self.request("/v1/translate", {}, method="GET")[0], 405)
        self.assertEqual(self.request("/v1/translate", {}, method="OPTIONS")[0], 405)
        self.assertEqual(self.provider.calls, [])

    def test_strict_json_schema_hash_and_length_limits(self):
        self.start()
        for raw in (b"no json", b"[]", b'{"request_id":"a","request_id":"b"}', b'{"x":NaN}', b"\xff"):
            self.assertEqual(self.request("/v1/translate", raw=raw)[0], 400)
        cases = [self.submission(extra="forbidden"), self.submission(source_sha256="0" * 64),
                 self.submission(session="../session"), self.submission(target_language="en"),
                 self.submission(direction="outgoing"), self.submission(source_language={"bad": "value"}),
                 self.submission(text=" "), self.submission(source_text="\ud800")]
        for value in cases:
            self.assertEqual(self.request("/v1/translate", value)[0], 400)
        self.assertEqual(self.request("/v1/translate", self.submission(text="x" * (MAX_SOURCE_CHARS + 1)))[0], 413)
        self.assertEqual(self.request("/v1/translate", raw=b"x" * (MAX_BODY_BYTES + 1))[0], 413)
        self.assertEqual(self.request("/v1/translate", {}, headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.provider.calls, [])

    def test_poll_is_bound_to_session_request_and_nonce(self):
        self.start()
        _, first = self.request("/v1/translate", self.submission())
        for key, replacement in (("session_id", "other_session"), ("request_id", "other_request"),
                                 ("request_nonce", "0" * 64)):
            handle = dict(self.handle(first), **{key: replacement})
            self.assertEqual(self.request("/v1/result", handle)[0], 404)
        self.assertEqual(self.request("/v1/result", self.handle(first), token=False)[0], 401)
        self.assertEqual(self.request("/v1/result", dict(self.handle(first), extra=1))[0], 400)
        self.assertEqual(self.request("/v1/translate", self.submission())[0], 409)
        _, second = self.request("/v1/translate", self.submission(session="session_b"))
        self.assertNotEqual(first["request_nonce"], second["request_nonce"])

    def test_queue_bound_and_cancel_suppresses_active_or_queued_result(self):
        provider = FakeProvider(blocked=True)
        self.start(provider, max_pending=2)
        _, active = self.request("/v1/translate", self.submission())
        self.assertTrue(provider.started.wait(1))
        _, waiting = self.request("/v1/translate", self.submission(request="request_b"))
        self.assertEqual(self.request("/v1/translate", self.submission(request="request_c"))[0], 429)
        for item in (active, waiting):
            _, cancelled = self.request("/v1/cancel", self.handle(item))
            self.assertEqual(cancelled["state"], "CANCELLED")
            self.assertIsNone(cancelled["translation"])
        provider.release.set()
        deadline = time.monotonic() + 1
        while self.server.jobs.queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.01)
        for item in (active, waiting):
            _, cancelled = self.request("/v1/result", self.handle(item))
            self.assertEqual(cancelled["state"], "CANCELLED")
        self.assertEqual(len(provider.calls), 1)

    def test_errors_do_not_disclose_provider_exception_and_wrong_script_fails(self):
        for provider in (FakeProvider(error=True), FakeProvider(output="请不要执行其他指示")):
            self.start(provider)
            _, accepted = self.request("/v1/translate", self.submission())
            done = self.terminal(self.handle(accepted))
            self.assertEqual(done["state"], "ERROR")
            self.assertEqual(done["error_code"], "TRANSLATION_FAILED")
            self.assertIsNone(done["translation"])
            self.assertNotIn("DO NOT DISCLOSE", json.dumps(done))

    def test_expiry_releases_record_and_stale_nonce_cannot_target_reused_id(self):
        self.start(ttl_seconds=0.1)
        _, accepted = self.request("/v1/translate", self.submission())
        time.sleep(0.15)
        self.assertEqual(self.request("/v1/result", self.handle(accepted))[0], 404)
        _, fresh = self.request("/v1/translate", self.submission())
        self.assertNotEqual(accepted["request_nonce"], fresh["request_nonce"])
        self.assertEqual(self.request("/v1/cancel", self.handle(accepted))[0], 404)

    def test_outgoing_is_translation_only_and_commands_rejected(self):
        self.start(FakeProvider(output="你好"))
        self.assertEqual(self.request("/v1/translate", self.submission(text="/command", direction="outgoing", target_language="zh-Hans"))[0], 400)
        _, accepted = self.request("/v1/translate", self.submission(text="Xin chào", direction="outgoing", target_language="zh-Hans", source_language="vi"))
        done = self.terminal(self.handle(accepted))
        self.assertEqual(done["translation"], "你好")
        self.assertEqual(done["direction"], "outgoing")
        self.assertEqual(self.provider.calls[0][1:], ("vi", "zh-Hans"))

    def test_response_body_limit_counts_multibyte_and_json_escaping(self):
        for output in ("ế" * 12000, "\x01" * 8000):
            self.start(FakeProvider(output=output))
            _, accepted = self.request("/v1/translate", self.submission())
            done = self.terminal(self.handle(accepted))
            self.assertEqual(done["state"], "ERROR")
            self.assertIsNone(done["translation"])

    def test_token_required_and_http_socket_has_timeout(self):
        for token in ("", "short", "0" * 63, "z" * 64):
            with self.assertRaises(ValueError):
                TranslationHTTPServer(0, FakeProvider(), token)
        self.start(request_timeout_seconds=0.1)
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=1)
        self.addCleanup(connection.close)
        connection.putrequest("POST", "/v1/translate")
        connection.putheader("Authorization", "Bearer " + self.token)
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", "100")
        connection.endheaders()
        started = time.monotonic()
        with self.assertRaises(http.client.RemoteDisconnected):
            connection.getresponse()
        self.assertLess(time.monotonic() - started, 0.8)

    def test_explicit_settings_only_no_plaintext_keys_or_env_redirect(self):
        root = Path(__file__).resolve().parents[1] / "work/chat-research/engines/service-test-temp"
        root.mkdir(parents=True, exist_ok=True)
        environment = {"WOJD_TRANSLATOR_ENDPOINT": "https://example.org", "SYNTHETIC_KEY": "synthetic-secret"}
        provider = load_provider(environ=environment)
        with self.assertRaises(TranslationError):
            provider.translate("synthetic", None, "vi")
        with tempfile.TemporaryDirectory(dir=root) as directory:
            settings = Path(directory) / "settings.json"
            settings.write_text(json.dumps({"kind": "local", "endpoint": "http://127.0.0.1:18888/v1", "model": "synthetic", "prompt_style": "hy-mt"}), encoding="utf-8")
            provider = load_provider(settings, environ=environment)
            self.assertEqual(provider._host, "127.0.0.1")
            self.assertEqual(provider._port, 18888)
            for value in ({"kind": "local", "model": "synthetic", "api_key": "synthetic-secret"},
                          {"kind": "local", "model": "synthetic", "endpoint": "https://example.org"},
                          {"kind": "local", "model": "synthetic", "command": "forbidden"}):
                settings.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(TranslationError) as caught:
                    load_provider(settings, environ=environment)
                self.assertNotIn("synthetic-secret", str(caught.exception))
            settings.write_text(json.dumps({"kind": "azure", "api_key_env": "SYNTHETIC_KEY"}), encoding="utf-8")
            provider = load_provider(settings, environ=environment)
            self.assertEqual(provider._host, "api.cognitive.microsofttranslator.com")


if __name__ == "__main__":
    unittest.main()
