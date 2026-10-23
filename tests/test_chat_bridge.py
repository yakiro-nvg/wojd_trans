"""Synthetic reference-codec tests with real loopback service and fake provider."""
import hashlib
import os
import secrets
import threading
import time
import unittest
from unittest import mock

from chat_companion.bridge import BridgeError, ReferenceBridge
from chat_companion.providers import TranslationError
from chat_companion.service import TranslationHTTPServer


class SyntheticProvider:
    def __init__(self, *, blocked=False, error=False, output="Bản dịch"):
        self.started, self.release = threading.Event(), threading.Event()
        self.error, self.output, self.calls = error, output, []
        if not blocked:
            self.release.set()

    def translate(self, text, source, target):
        self.calls.append((text, source, target))
        self.started.set()
        self.release.wait(2)
        if self.error:
            raise TranslationError("synthetic original and secret must never be reflected")
        return self.output


class BridgeTests(unittest.TestCase):
    def start(self, provider=None, **bridge_options):
        provider = provider or SyntheticProvider()
        token = secrets.token_hex(32)
        server = TranslationHTTPServer(0, provider, token)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        with mock.patch.dict(os.environ, {"WOJD_CHAT_SERVICE_TOKEN": token}):
            bridge = ReferenceBridge(server.server_port, **bridge_options)
        self.server, self.provider, self.bridge = server, provider, bridge
        def close():
            provider.release.set()
            bridge.close()
            server.shutdown()
            server.server_close()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertFalse(server.jobs.worker.is_alive())
        self.addCleanup(close)
        return bridge

    def snapshot(self, *, original="synthetic message", **extra):
        value = {"request_id": "instance:1", "message_id": "occurrence:one", "session": "session:one",
                 "generation": 3, "source_sha": hashlib.sha256(original.encode("utf-8")).hexdigest(),
                 "original": original, "channel": "party", "role_id": 17,
                 "direction": "incoming", "target_language": "vi"}
        value.update(extra)
        return value

    def step(self, bridge=None):
        bridge = bridge or self.bridge
        result, errors = [], []
        def work():
            try:
                result.append(bridge.background_step())
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=work)
        thread.start()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        if errors:
            raise errors[0]
        return result[0]

    def completion(self, bridge=None):
        bridge = bridge or self.bridge
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            self.step(bridge)
            results = bridge.poll()
            if results:
                self.assertEqual(len(results), 1)
                return results[0]
            time.sleep(0.01)
        self.fail("Synthetic completion not delivered")

    def test_success_maps_long_colon_unicode_ids_and_uses_local_original_metadata(self):
        bridge = self.start()
        source = self.snapshot(request_id="ký-tự:" + "x" * 140,
                               message_id="chat:history:" + "长" * 40, session="session:非ASCII")
        copied = dict(source)
        self.assertTrue(bridge.enqueue(source))
        source.update(original="caller mutation", message_id="different", channel="mutated")
        result = self.completion()
        for field in copied:
            self.assertEqual(result[field], copied[field])
        self.assertEqual(result["status"], "TRANSLATED")
        self.assertEqual(result["translation"], "Bản dịch")
        with self.server.jobs.lock:
            record = next(iter(self.server.jobs.records.values()))
            self.assertRegex(record["session_id"], r"^[a-f0-9]{64}$")
            self.assertRegex(record["request_id"], r"^[a-f0-9]{64}$")
            self.assertEqual(record["source_sha256"], copied["source_sha"])
            self.assertNotIn("original", record)
            self.assertNotIn("message_id", record)
        self.assertEqual(bridge.poll(), [])

    def test_unicode_multiline_exact_utf8_hash_and_original_are_not_normalized(self):
        bridge = self.start(SyntheticProvider(output="Xin chào\nDòng thứ hai"))
        original = "大家好\r\nXin cha\u0300o\nCuối dòng"
        source = self.snapshot(original=original)
        source["source_sha"] = source["source_sha"].upper()
        self.assertTrue(bridge.enqueue(source))
        result = self.completion()
        self.assertEqual(result["original"], original)
        self.assertEqual(result["source_sha"], source["source_sha"])
        self.assertEqual(result["translation"], "Xin chào\nDòng thứ hai")
        self.assertEqual(self.provider.calls[0][0], original)

    def test_provider_error_returns_bound_error_without_raw_exception(self):
        bridge = self.start(SyntheticProvider(error=True))
        source = self.snapshot()
        self.assertTrue(bridge.enqueue(source))
        result = self.completion()
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["original"], source["original"])
        self.assertEqual(result["error_code"], "TRANSLATION_FAILED")
        self.assertIsNone(result["translation"])

    def test_wrong_submission_binding_waits_for_trusted_local_deadline(self):
        for field, wrong in (("session_id", "0" * 64), ("request_id", "0" * 64),
                             ("source_sha256", "0" * 64), ("target_language", "zh-Hans"),
                             ("direction", "outgoing")):
            bridge = self.start(ttl_seconds=0.1)
            source = self.snapshot()
            original_public = self.server.jobs._public
            def changed(record, field=field, wrong=wrong):
                return dict(original_public(record), **{field: wrong})
            with mock.patch.object(self.server.jobs, "_public", changed):
                self.assertTrue(bridge.enqueue(source))
                self.step(bridge)
            self.assertEqual(bridge.poll(), [])
            self.assertEqual(next(iter(bridge._records.values())).phase, "WAIT_DEADLINE")
            self.assertFalse(self.step(bridge))  # No retry of the untrusted reply.
            time.sleep(0.12)
            result = bridge.poll()[0]
            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(result["error_code"], "LOCAL_DEADLINE_EXCEEDED")
            self.assertIsNone(result["translation"])
            for key, value in source.items():
                self.assertEqual(result[key], value)
            self.assertEqual(len(bridge._records), 0)

    def test_wrong_poll_nonce_or_source_binding_cannot_complete(self):
        for field in ("request_nonce", "source_sha256"):
            bridge = self.start(ttl_seconds=0.1)
            self.assertTrue(bridge.enqueue(self.snapshot()))
            self.step(bridge)
            original_public = self.server.jobs._public
            with mock.patch.object(self.server.jobs, "_public", lambda record: dict(original_public(record), **{field: "0" * 64})):
                self.step(bridge)
            self.assertEqual(bridge.poll(), [])
            time.sleep(0.12)
            result = bridge.poll()[0]
            self.assertEqual(result["error_code"], "LOCAL_DEADLINE_EXCEEDED")
            self.assertEqual(result["original"], "synthetic message")
            self.assertIsNone(result["translation"])

    def test_expired_snapshot_emits_local_error_and_completion_ttl_releases_memory(self):
        bridge = self.start(ttl_seconds=0.05, completion_ttl_seconds=0.05)
        self.assertTrue(bridge.enqueue(self.snapshot()))
        time.sleep(0.07)
        result = bridge.poll()[0]
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["error_code"], "LOCAL_DEADLINE_EXCEEDED")
        self.assertEqual(len(bridge._records), 0)
        self.assertEqual(self.provider.calls, [])
        self.assertTrue(bridge.enqueue(self.snapshot()))
        time.sleep(0.07)
        self.step(bridge)  # Emit deadline completion without consuming it.
        self.assertEqual(len(bridge._completed), 1)
        time.sleep(0.07)
        self.assertEqual(bridge.poll(), [])
        self.assertEqual(len(bridge._completed), 0)

    def test_active_local_deadline_returns_original_only_from_owned_snapshot(self):
        provider = SyntheticProvider(blocked=True)
        bridge = self.start(provider, ttl_seconds=0.1)
        source = self.snapshot(original="中文原文，保留不变。", channel="原始频道", role_id="local:role")
        self.assertTrue(bridge.enqueue(source))
        self.step(bridge)
        self.assertTrue(provider.started.wait(1))
        time.sleep(0.12)
        result = bridge.poll()[0]
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["error_code"], "LOCAL_DEADLINE_EXCEEDED")
        self.assertIsNone(result["translation"])
        for key, value in source.items():
            self.assertEqual(result[key], value)
        provider.release.set()
        self.step(bridge)  # Best-effort cancel; late provider text cannot surface.
        self.assertEqual(bridge.poll(), [])

    def test_local_transport_failure_retires_at_local_deadline_without_raw_error(self):
        bridge = self.start(ttl_seconds=0.3, timeout_seconds=0.1)
        self.server.shutdown()
        self.server.server_close()
        self.assertTrue(bridge.enqueue(self.snapshot()))
        self.step(bridge)
        self.assertEqual(bridge.poll(), [])
        time.sleep(0.32)
        result = bridge.poll()[0]
        self.assertEqual(result["error_code"], "LOCAL_DEADLINE_EXCEEDED")
        self.assertEqual(result["original"], "synthetic message")
        self.assertIsNone(result["translation"])

    def test_cancel_context_and_reused_id_do_not_emit_previous_deadline_error(self):
        bridge = self.start(ttl_seconds=0.05)
        self.assertTrue(bridge.enqueue(self.snapshot()))
        self.assertTrue(bridge.cancel("instance:1", session="session:one", generation=3))
        self.assertEqual(bridge.poll()[0]["status"], "CANCELLED")
        self.assertTrue(bridge.enqueue(self.snapshot(original="new occurrence")))
        time.sleep(0.07)
        result = bridge.poll()[0]
        self.assertEqual(result["original"], "new occurrence")
        self.assertEqual(result["error_code"], "LOCAL_DEADLINE_EXCEEDED")
        self.assertEqual(bridge.poll(), [])
        self.assertTrue(bridge.enqueue(self.snapshot()))
        time.sleep(0.07)
        bridge.set_context("session:one", 4)  # Invalidate before publishing expiry.
        self.assertEqual(bridge.poll(), [])
        self.assertTrue(bridge.enqueue(self.snapshot(original="generation four", generation=4)))
        time.sleep(0.07)
        result = bridge.poll()[0]
        self.assertEqual(result["generation"], 4)
        self.assertEqual(result["original"], "generation four")
        self.assertEqual(bridge.poll(), [])

    def test_full_queue_recovers_after_deadline_drain_or_completion_expiry(self):
        bridge = self.start(max_pending=1, ttl_seconds=0.05, completion_ttl_seconds=0.05)
        self.assertTrue(bridge.enqueue(self.snapshot()))
        second = self.snapshot(request_id="instance:2")
        self.assertFalse(bridge.enqueue(second))
        time.sleep(0.07)
        self.assertFalse(bridge.enqueue(second))  # One bounded error awaits caller.
        self.assertEqual(bridge.poll()[0]["error_code"], "LOCAL_DEADLINE_EXCEEDED")
        self.assertTrue(bridge.enqueue(second))
        time.sleep(0.07)
        self.step(bridge)  # Retain, but deliberately do not drain, the local error.
        time.sleep(0.07)
        self.assertTrue(bridge.enqueue(self.snapshot(request_id="instance:3")))
        self.assertEqual(bridge.poll(), [])
        self.assertEqual(len(bridge._records) + len(bridge._completed), 1)

    def test_context_change_discards_stale_results_and_reuses_local_ids_safely(self):
        provider = SyntheticProvider(blocked=True)
        bridge = self.start(provider)
        bridge.set_context("session:one", 3)
        self.assertTrue(bridge.enqueue(self.snapshot()))
        self.step(bridge)
        self.assertTrue(provider.started.wait(1))
        old_wire = next(iter(bridge._records.values())).wire_request
        bridge.set_context("session:one", 4)
        self.assertFalse(bridge.enqueue(self.snapshot()))
        fresh = self.snapshot(original="new occurrence", generation=4)
        self.assertTrue(bridge.enqueue(fresh))
        self.assertNotEqual(next(iter(bridge._records.values())).wire_request, old_wire)
        provider.release.set()
        result = self.completion(bridge)
        self.assertEqual(result["generation"], 4)
        self.assertEqual(result["original"], "new occurrence")
        self.assertEqual(bridge.poll(), [])

    def test_cancel_then_reuse_id_never_delivers_previous_translation(self):
        provider = SyntheticProvider(blocked=True)
        bridge = self.start(provider)
        source = self.snapshot()
        self.assertTrue(bridge.enqueue(source))
        self.step(bridge)
        self.assertTrue(provider.started.wait(1))
        old_wire = next(iter(bridge._records.values())).wire_request
        self.assertTrue(bridge.cancel(source["request_id"], session=source["session"], generation=3))
        cancelled = bridge.poll()[0]
        self.assertEqual(cancelled["status"], "CANCELLED")
        self.assertIsNone(cancelled["translation"])
        self.assertTrue(bridge.enqueue(self.snapshot(original="new source")))
        self.assertNotEqual(next(iter(bridge._records.values())).wire_request, old_wire)
        provider.release.set()
        result = self.completion(bridge)
        self.assertEqual(result["original"], "new source")
        self.assertEqual(result["status"], "TRANSLATED")

    def test_cancel_unconsumed_completion_suppresses_translation(self):
        bridge = self.start()
        source = self.snapshot()
        self.assertTrue(bridge.enqueue(source))
        deadline = time.monotonic() + 1
        while not bridge._completed and time.monotonic() < deadline:
            self.step(bridge)
        self.assertTrue(bridge.cancel(source["request_id"], session=source["session"], generation=3))
        self.assertEqual(bridge.poll()[0]["status"], "CANCELLED")

    def test_cancel_during_submission_ack_then_reused_id_has_distinct_binding(self):
        bridge = self.start()
        submitted, release_ack = threading.Event(), threading.Event()
        original_post = bridge._post
        observed = []
        def delayed_ack(path, payload):
            result = original_post(path, payload)
            if path == "/v1/translate" and not observed:
                observed.append(payload["request_id"])
                submitted.set()
                release_ack.wait(1)
            return result
        self.assertTrue(bridge.enqueue(self.snapshot()))
        with mock.patch.object(bridge, "_post", delayed_ack):
            worker = threading.Thread(target=bridge.background_step)
            worker.start()
            try:
                self.assertTrue(submitted.wait(1))
                self.assertTrue(bridge.cancel("instance:1", session="session:one", generation=3))
                self.assertEqual(bridge.poll()[0]["status"], "CANCELLED")
                self.assertTrue(bridge.enqueue(self.snapshot(original="new occurrence after cancellation")))
                self.assertNotEqual(next(iter(bridge._records.values())).wire_request, observed[0])
            finally:
                release_ack.set()
                worker.join(2)
            self.assertFalse(worker.is_alive())
        result = self.completion(bridge)
        self.assertEqual(result["original"], "new occurrence after cancellation")
        self.assertEqual(result["status"], "TRANSLATED")

    def test_nonblocking_interfaces_have_no_http_and_background_is_explicit(self):
        bridge = self.start()
        with mock.patch("chat_companion.bridge.http.client.HTTPConnection") as connection:
            self.assertTrue(bridge.enqueue(self.snapshot()))
            self.assertEqual(bridge.poll(), [])
            self.assertTrue(bridge.cancel("instance:1", session="session:one", generation=3))
            with self.assertRaisesRegex(BridgeError, "BACKGROUND_THREAD_REQUIRED"):
                bridge.background_step()
            bridge.close()
            connection.assert_not_called()

    def test_invalid_schema_hash_bounds_and_queue_rejection(self):
        bridge = self.start(max_pending=1)
        for source in (self.snapshot(source_sha="0" * 64), self.snapshot(generation=-1),
                       self.snapshot(generation=True), self.snapshot(generation=10**1000),
                       self.snapshot(original="x" * 4097), self.snapshot(channel={"bad": "value"}),
                       self.snapshot(direction="outgoing"), self.snapshot(extra="unexpected")):
            self.assertFalse(bridge.enqueue(source))
        self.assertTrue(bridge.enqueue(self.snapshot()))
        self.assertFalse(bridge.enqueue(self.snapshot(request_id="instance:2")))
        with self.assertRaises(BridgeError):
            bridge.poll(0)
        self.assertEqual(self.provider.calls, [])

    def test_environment_token_and_fixed_loopback_port_only(self):
        with mock.patch.dict(os.environ, {"WOJD_CHAT_SERVICE_TOKEN": ""}):
            with self.assertRaisesRegex(BridgeError, "SERVICE_TOKEN_REQUIRED"):
                ReferenceBridge(18476)
        with mock.patch.dict(os.environ, {"WOJD_CHAT_SERVICE_TOKEN": secrets.token_hex(32)}):
            for port in ("https://example.org", 0, -1, 65536, True):
                with self.assertRaisesRegex(BridgeError, "INVALID_LOOPBACK_PORT"):
                    ReferenceBridge(port)


if __name__ == "__main__":
    unittest.main()
