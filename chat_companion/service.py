"""Authenticated loopback translation service; no game capture, UI, or send API.

POST /v1/translate submits a bounded source snapshot. POST /v1/result and
POST /v1/cancel require its session, request ID and returned random nonce.
Only an explicitly started CLI (or a caller constructing the server) listens.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import re
import secrets
import threading
import time

from .core import protect_text, restore_text, validate_target_language
from .providers import ProviderConfig, TranslationError, make_provider

MAX_SOURCE_CHARS = 4096
MAX_BODY_BYTES = 32768
MAX_PENDING = 32
MAX_RECORDS = 128
_ID = re.compile(r"[A-Za-z0-9_-]{1,96}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_ACTIVE = frozenset(("QUEUED", "TRANSLATING"))
_SUBMIT_FIELDS = frozenset(("session_id", "request_id", "source_sha256", "source_text",
                            "source_language", "target_language", "direction"))
_LOOKUP_FIELDS = frozenset(("session_id", "request_id", "request_nonce"))


class ServiceError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _object(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise ServiceError(400, "INVALID_JSON") from None


def _identifier(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _submission(value: dict) -> dict:
    required = _SUBMIT_FIELDS - {"source_language"}
    if not required.issubset(value) or not set(value).issubset(_SUBMIT_FIELDS):
        raise ServiceError(400, "INVALID_SCHEMA")
    if not _identifier(value["session_id"]) or not _identifier(value["request_id"]):
        raise ServiceError(400, "INVALID_BINDING")
    text = value["source_text"]
    if not isinstance(text, str) or not text.strip():
        raise ServiceError(400, "INVALID_TEXT")
    if len(text) > MAX_SOURCE_CHARS:
        raise ServiceError(413, "TEXT_TOO_LONG")
    try:
        raw = text.encode("utf-8")
    except UnicodeError:
        raise ServiceError(400, "INVALID_TEXT") from None
    digest = value["source_sha256"]
    if not isinstance(digest, str) or not _SHA.fullmatch(digest):
        raise ServiceError(400, "INVALID_HASH")
    if not hmac.compare_digest(digest, hashlib.sha256(raw).hexdigest()):
        raise ServiceError(400, "SOURCE_HASH_MISMATCH")
    direction, target = value["direction"], value["target_language"]
    if direction not in ("incoming", "outgoing") or target not in ("vi", "zh-Hans"):
        raise ServiceError(400, "INVALID_DIRECTION_OR_TARGET")
    if (direction == "incoming" and target != "vi") or (direction == "outgoing" and target != "zh-Hans"):
        raise ServiceError(400, "INVALID_DIRECTION_OR_TARGET")
    source = value.get("source_language")
    if source is not None and (not isinstance(source, str) or len(source) > 32
                               or not re.fullmatch(r"(?:auto|[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)", source)):
        raise ServiceError(400, "INVALID_SOURCE_LANGUAGE")
    if direction == "outgoing" and text.lstrip().startswith("/"):
        raise ServiceError(400, "COMMAND_NOT_TRANSLATED")
    return dict(value, source_language=source)


class _Jobs:
    def __init__(self, provider, *, max_pending=MAX_PENDING, ttl_seconds=60):
        if not isinstance(max_pending, int) or not 1 <= max_pending <= MAX_PENDING:
            raise ValueError("Invalid pending limit")
        if not isinstance(ttl_seconds, (int, float)) or not 0.1 <= ttl_seconds <= 300:
            raise ValueError("Invalid memory lifetime")
        self.provider, self.ttl = provider, ttl_seconds
        self.limit = max_pending
        self.records = OrderedDict()
        self.queue = queue.Queue(maxsize=max_pending)
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self._run, name="wojd-translation-service", daemon=True)
        self.worker.start()

    def _purge(self):
        now = time.monotonic()
        for key in [key for key, record in self.records.items() if record["expires"] <= now]:
            del self.records[key]

    @staticmethod
    def _public(record):
        fields = ("session_id", "request_id", "source_sha256", "request_nonce", "direction",
                  "target_language", "state", "translation", "error_code")
        return {key: record[key] for key in fields}

    def submit(self, value):
        value = _submission(value)
        key = (value["session_id"], value["request_id"])
        with self.lock:
            self._purge()
            if self.stop.is_set():
                raise ServiceError(503, "SERVICE_STOPPING")
            if key in self.records:
                raise ServiceError(409, "DUPLICATE_REQUEST")
            if sum(record["state"] in _ACTIVE for record in self.records.values()) >= self.limit:
                raise ServiceError(429, "QUEUE_FULL")
            while len(self.records) >= MAX_RECORDS:
                terminal = next((k for k, v in self.records.items() if v["state"] not in _ACTIVE), None)
                if terminal is None:
                    raise ServiceError(429, "QUEUE_FULL")
                del self.records[terminal]
            record = dict(value, request_nonce=secrets.token_hex(32), state="QUEUED", translation=None,
                          error_code=None, expires=time.monotonic() + self.ttl)
            self.records[key] = record
            try:
                self.queue.put_nowait(key)
            except queue.Full:
                del self.records[key]
                raise ServiceError(429, "QUEUE_FULL") from None
            return self._public(record)

    def lookup(self, value, *, cancel=False):
        if set(value) != _LOOKUP_FIELDS or not all(_identifier(value.get(k)) for k in ("session_id", "request_id")):
            raise ServiceError(400, "INVALID_SCHEMA")
        nonce = value["request_nonce"]
        if not isinstance(nonce, str) or not _SHA.fullmatch(nonce):
            raise ServiceError(400, "INVALID_NONCE")
        key = (value["session_id"], value["request_id"])
        with self.lock:
            self._purge()
            record = self.records.get(key)
            if record is None or not hmac.compare_digest(record["request_nonce"], nonce):
                raise ServiceError(404, "REQUEST_NOT_FOUND")
            if cancel:
                # Cannot interrupt an already active provider call; its eventual result
                # is discarded. Queued snapshots and terminal output are released now.
                record.update(state="CANCELLED", source_text=None, translation=None, error_code=None)
            return self._public(record)

    def _run(self):
        while not self.stop.is_set():
            try:
                key = self.queue.get(timeout=0.05)
            except queue.Empty:
                with self.lock:
                    self._purge()
                continue
            try:
                with self.lock:
                    self._purge()
                    record = self.records.get(key)
                    if record is None or record["state"] != "QUEUED":
                        continue
                    record["state"] = "TRANSLATING"
                    text, source, target = record["source_text"], record["source_language"], record["target_language"]
                    nonce = record["request_nonce"]
                    record["source_text"] = None
                output, error = None, None
                try:
                    protected, tokens = protect_text(text)
                    raw = self.provider.translate(protected, source, target)
                    validate_target_language(re.sub(r"__WOJD_T\d+__", "", raw), target)
                    output = restore_text(protected, raw, tokens)
                    # Leave room for the bounded binding fields in the HTTP JSON body.
                    # Count JSON-escaped bytes, not just Unicode code points.
                    if len(json.dumps(output, ensure_ascii=False).encode("utf-8")) > MAX_BODY_BYTES - 2048:
                        raise TranslationError("The translated output is too large.")
                except Exception:
                    # Provider exceptions, including unexpected ones, can contain
                    # submitted text, credentials or HTTP bodies: never reflect them.
                    output, error = None, "TRANSLATION_FAILED"
                with self.lock:
                    self._purge()
                    record = self.records.get(key)
                    if (record is not None and record["request_nonce"] == nonce
                            and record["state"] == "TRANSLATING" and not self.stop.is_set()):
                        record.update(state="ERROR" if error else "TRANSLATED", translation=output, error_code=error)
            finally:
                # Do not retain the previous private message while idle on the next job.
                text = source = target = output = raw = protected = tokens = record = None
                self.queue.task_done()

    def close(self):
        self.stop.set()
        with self.lock:
            self.records.clear()
        while True:
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except queue.Empty:
                break
        self.worker.join(timeout=2)


class TranslationHTTPServer(ThreadingHTTPServer):
    """Construction binds only IPv4 loopback. The caller explicitly starts serving."""
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False
    request_queue_size = 16

    def __init__(self, port: int, provider, token: str, *, max_pending=MAX_PENDING, ttl_seconds=60,
                 request_timeout_seconds=5):
        if not isinstance(token, str) or not _SHA.fullmatch(token):
            raise ValueError("A 256-bit hexadecimal service token is required")
        if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
            raise ValueError("Invalid loopback port")
        if not isinstance(request_timeout_seconds, (int, float)) or not 0.1 <= request_timeout_seconds <= 30:
            raise ValueError("Invalid request timeout")
        self._token = token
        self.request_timeout_seconds = request_timeout_seconds
        self._slots = threading.BoundedSemaphore(16)
        self.jobs = _Jobs(provider, max_pending=max_pending, ttl_seconds=ttl_seconds)
        try:
            super().__init__(("127.0.0.1", port), _Handler)
        except Exception:
            self.jobs.close()
            raise

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(self.request_timeout_seconds)
        return connection, address

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def handle_error(self, request, client_address):
        pass  # No raw exceptions, request lines, source text or secrets in logs.

    def service_actions(self):
        # Expire retained results even while the single provider worker is busy.
        with self.jobs.lock:
            self.jobs._purge()

    def server_close(self):
        super().server_close()
        self.jobs.close()
        self._token = ""


class _Handler(BaseHTTPRequestHandler):
    server_version = "WOJDTranslation"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def log_message(self, format, *args):
        pass

    def _reply(self, status, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        self._reply(code, {"error_code": "INVALID_HTTP_REQUEST"})

    def do_POST(self):
        try:
            if self.headers.get_all("Origin"):
                raise ServiceError(403, "BROWSER_ORIGIN_FORBIDDEN")
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}" or len(self.headers.get_all("Host", [])) != 1:
                raise ServiceError(403, "INVALID_HOST")
            authorization = self.headers.get_all("Authorization", [])
            expected = "Bearer " + self.server._token
            if (not self.server._token or len(authorization) != 1 or not authorization[0].isascii()
                    or not hmac.compare_digest(authorization[0], expected)):
                raise ServiceError(401, "UNAUTHORIZED")
            if self.path not in ("/v1/translate", "/v1/result", "/v1/cancel"):
                raise ServiceError(404, "UNKNOWN_ENDPOINT")
            if self.headers.get("Transfer-Encoding") is not None:
                raise ServiceError(400, "INVALID_BODY_LENGTH")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,8}", lengths[0]):
                raise ServiceError(400, "INVALID_BODY_LENGTH")
            length = int(lengths[0])
            if not 1 <= length <= MAX_BODY_BYTES:
                # Consume at most one bounded over-limit probe so a near-limit
                # caller can receive413 without Windows resetting unread bytes.
                if MAX_BODY_BYTES < length <= MAX_BODY_BYTES + 1:
                    self.rfile.read(length)
                raise ServiceError(413, "BODY_TOO_LARGE")
            content_types = self.headers.get_all("Content-Type", [])
            if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/json":
                raise ServiceError(415, "JSON_REQUIRED")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ServiceError(400, "INCOMPLETE_BODY")
            value = _object(raw)
            if self.path == "/v1/translate":
                self._reply(202, self.server.jobs.submit(value))
            else:
                self._reply(200, self.server.jobs.lookup(value, cancel=self.path == "/v1/cancel"))
        except ServiceError as error:
            self._reply(error.status, {"error_code": error.code})
        except (TimeoutError, OSError):
            self.close_connection = True
        except Exception:
            self._reply(500, {"error_code": "SERVICE_ERROR"})

    def do_GET(self):
        self._reply(405, {"error_code": "POST_REQUIRED"})

    do_OPTIONS = do_GET


def load_provider(settings_path=None, *, environ=None):
    """Read an explicit flat settings file; only credentials may come from env."""
    environment = os.environ if environ is None else environ
    if settings_path is None:
        return make_provider(ProviderConfig())
    try:
        with Path(settings_path).open("rb") as stream:
            raw = stream.read(16385)
        if len(raw) > 16384:
            raise ValueError
        value = _object(raw)
        allowed = {"kind", "endpoint", "model", "region", "timeout_seconds", "prompt_style", "api_key_env"}
        if not set(value).issubset(allowed):
            raise ValueError
        kind = value.get("kind", "unconfigured")
        key_name = value.pop("api_key_env", "WOJD_AZURE_TRANSLATOR_KEY" if kind == "azure" else "")
        if not isinstance(key_name, str) or (key_name and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", key_name)):
            raise ValueError
        value["api_key"] = environment.get(key_name, "") if key_name else ""
        return make_provider(ProviderConfig(**value))
    except (OSError, ValueError, TypeError, ServiceError, TranslationError):
        raise TranslationError("The explicit translation service settings are invalid.") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the authenticated loopback translation service.")
    parser.add_argument("--settingspath", type=Path)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("Choose a port between 1 and 65535.")
    try:
        provider = load_provider(args.settingspath)
        server = TranslationHTTPServer(args.port, provider, os.environ.get("WOJD_CHAT_SERVICE_TOKEN", ""))
    except (ValueError, OSError, TranslationError):
        parser.exit(2, "Translation service configuration is invalid.\n")
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
