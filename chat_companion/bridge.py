"""Pure-Python reference codec between a copied Lua envelope and local service.

enqueue(), poll(), cancel(), set_context() and close() perform no network I/O.
The caller must drive background_step() from a background thread. This module
supplies no game binding, UI dispatcher, capture, process access or send action.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
import hashlib
import hmac
import http.client
import json
import math
import os
import re
import secrets
import threading
import time

from .service import MAX_BODY_BYTES, MAX_SOURCE_CHARS

_HEX = re.compile(r"[a-f0-9]{64}\Z")
_FIELDS = {"request_id", "message_id", "session", "generation", "source_sha", "original",
           "channel", "role_id", "direction", "target_language"}
_REQUIRED = _FIELDS - {"channel", "role_id"}
_WIRE_FIELDS = {"session_id", "request_id", "source_sha256", "request_nonce", "direction",
                "target_language", "state", "translation", "error_code"}
_STATES = {"QUEUED", "TRANSLATING", "TRANSLATED", "ERROR", "CANCELLED"}


class BridgeError(Exception):
    """Fixed local error; source text, tokens and HTTP bodies are never included."""


def _identifier(value, max_bytes):
    if not isinstance(value, str) or not value or "\0" in value:
        return False
    try:
        return len(value.encode("utf-8")) <= max_bytes
    except UnicodeError:
        return False


def _generation(value):
    try:
        return (not isinstance(value, bool) and isinstance(value, (int, float))
                and math.isfinite(value) and 0 <= value <= 2**53 - 1 and int(value) == value)
    except (ValueError, OverflowError):
        return False


def _scalar(value):
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, str):
        try:
            return "\0" not in value and len(value.encode("utf-8")) <= 256
        except UnicodeError:
            return False
    return isinstance(value, (int, float)) and math.isfinite(value) and abs(value) <= 2**53 - 1


def _snapshot(value):
    if not isinstance(value, dict) or not _REQUIRED.issubset(value) or not set(value).issubset(_FIELDS):
        raise BridgeError("INVALID_SNAPSHOT")
    if (not _identifier(value["request_id"], 256) or not _identifier(value["message_id"], 256)
            or not _identifier(value["session"], 128) or not _generation(value["generation"])):
        raise BridgeError("INVALID_IDENTITY")
    text, digest = value["original"], value["source_sha"]
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_SOURCE_CHARS:
        raise BridgeError("INVALID_SOURCE")
    try:
        encoded = text.encode("utf-8")
    except UnicodeError:
        raise BridgeError("INVALID_SOURCE") from None
    if len(encoded) > 32000 or not isinstance(digest, str) or not _HEX.fullmatch(digest.lower()):
        raise BridgeError("INVALID_SOURCE")
    actual = hashlib.sha256(encoded).hexdigest()
    if not hmac.compare_digest(actual, digest.lower()):
        raise BridgeError("SOURCE_HASH_MISMATCH")
    if value["direction"] != "incoming" or value["target_language"] != "vi":
        raise BridgeError("UNSUPPORTED_SNAPSHOT_DIRECTION")
    if not all(_scalar(value.get(key)) for key in ("channel", "role_id")):
        raise BridgeError("INVALID_METADATA")
    # Only bounded copied scalars are retained; later mutation of the caller's
    # dictionary cannot change this request's trusted completion envelope.
    return {key: value[key] for key in _FIELDS if key in value}, actual


@dataclass
class _Record:
    snapshot: dict
    digest: str
    wire_session: str
    wire_request: str
    expires: float
    phase: str = "NEW"
    nonce: str | None = None

    def lookup(self):
        return {"session_id": self.wire_session, "request_id": self.wire_request,
                "request_nonce": self.nonce}


class ReferenceBridge:
    """Bounded reference transport, not an implementation of a game host ABI.

    The service token is read only from WOJD_CHAT_SERVICE_TOKEN. Constructing
    this object creates no threads/listeners/connections. HTTP uses127.0.0.1
    and an explicit port only, without proxy/redirect support.
    """
    def __init__(self, port: int, *, max_pending=32, ttl_seconds=60,
                 completion_ttl_seconds=30, timeout_seconds=5):
        token = os.environ.get("WOJD_CHAT_SERVICE_TOKEN", "")
        if not _HEX.fullmatch(token):
            raise BridgeError("SERVICE_TOKEN_REQUIRED")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise BridgeError("INVALID_LOOPBACK_PORT")
        if isinstance(max_pending, bool) or not isinstance(max_pending, int) or not 1 <= max_pending <= 32:
            raise BridgeError("INVALID_PENDING_BOUND")
        if not isinstance(ttl_seconds, (int, float)) or not 0.05 <= ttl_seconds <= 60:
            raise BridgeError("INVALID_MEMORY_LIFETIME")
        if not isinstance(completion_ttl_seconds, (int, float)) or not 0.05 <= completion_ttl_seconds <= 60:
            raise BridgeError("INVALID_COMPLETION_LIFETIME")
        if not isinstance(timeout_seconds, (int, float)) or not 0.1 <= timeout_seconds <= 10:
            raise BridgeError("INVALID_TIMEOUT")
        self._port, self._token = port, token
        self._limit, self._ttl, self._timeout = max_pending, ttl_seconds, timeout_seconds
        self._completion_ttl = completion_ttl_seconds
        self._instance = secrets.token_bytes(32)
        self._creator = threading.get_ident()
        self._lock, self._background_lock = threading.Lock(), threading.Lock()
        self._records, self._completed = OrderedDict(), OrderedDict()
        self._cancels = deque(maxlen=32)
        self._context = None
        self._closed = False

    def _retire(self, record):
        if record.nonce and len(self._cancels) < 32:
            # No original text or local UI metadata in a cleanup request.
            self._cancels.append((record.lookup(), record.expires))

    def _purge(self):
        now = time.monotonic()
        for key in [key for key, record in self._records.items() if record.expires <= now]:
            record = self._records.pop(key)
            self._retire(record)
            # This terminal error is certified only by our own accepted snapshot
            # and elapsed local deadline. No field or translation from an invalid
            # service reply contributes to its UI identity or contents.
            self._completed[key] = (self._completion(record, "ERROR", error="LOCAL_DEADLINE_EXCEEDED"),
                                    now + self._completion_ttl)
        for key in [key for key, (_, expires) in self._completed.items() if expires <= now]:
            del self._completed[key]

    @staticmethod
    def _key(snapshot):
        return snapshot["session"], int(snapshot["generation"]), snapshot["request_id"]

    @staticmethod
    def _completion(record, status, translation=None, error=None):
        return dict(record.snapshot, status=status, translation=translation, error_code=error)

    def enqueue(self, snapshot) -> bool:
        try:
            copied, digest = _snapshot(snapshot)
        except (BridgeError, ValueError, TypeError, OverflowError):
            return False
        key = self._key(copied)
        with self._lock:
            self._purge()
            if (self._closed or len(self._records) + len(self._completed) >= self._limit
                    or key in self._records or key in self._completed
                    or (self._context is not None and key[:2] != self._context)):
                return False
            session_material = copied["session"].encode("utf-8") + b"\0" + str(key[1]).encode("ascii")
            wire_session = hashlib.sha256(self._instance + b"\0" + session_material).hexdigest()
            self._records[key] = _Record(copied, digest, wire_session, secrets.token_hex(32),
                                         time.monotonic() + self._ttl)
            return True

    def poll(self, max_results=128) -> list[dict]:
        if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 128:
            raise BridgeError("INVALID_POLL_BOUND")
        with self._lock:
            self._purge()
            results = []
            while self._completed and len(results) < max_results:
                _, (result, _) = self._completed.popitem(last=False)
                results.append(dict(result))
            return results

    def set_context(self, session: str, generation):
        """Optional local invalidation supplied by caller; it proves no game context."""
        if not _identifier(session, 128) or not _generation(generation):
            raise BridgeError("INVALID_CONTEXT")
        current = session, int(generation)
        with self._lock:
            self._context = current
            for key in [key for key in self._records if key[:2] != current]:
                self._retire(self._records.pop(key))
            for key in [key for key in self._completed if key[:2] != current]:
                del self._completed[key]

    def cancel(self, request_id, *, session, generation) -> bool:
        if not _identifier(request_id, 256) or not _identifier(session, 128) or not _generation(generation):
            return False
        key = session, int(generation), request_id
        with self._lock:
            self._purge()
            record = self._records.pop(key, None)
            if record is None:
                completed = self._completed.get(key)
                if completed is not None:
                    result, expires = completed
                    self._completed[key] = (dict(result, status="CANCELLED", translation=None, error_code=None), expires)
                    return True
                return False
            self._retire(record)
            self._completed[key] = (self._completion(record, "CANCELLED"),
                                    time.monotonic() + self._completion_ttl)
            return True

    def _post(self, path, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(body) > MAX_BODY_BYTES:
            raise BridgeError("REQUEST_TOO_LARGE")
        connection = http.client.HTTPConnection("127.0.0.1", self._port, timeout=self._timeout)
        try:
            connection.request("POST", path, body, {"Content-Type": "application/json; charset=utf-8",
                               "Authorization": "Bearer " + self._token})
            response = connection.getresponse()
            raw = response.read(MAX_BODY_BYTES + 1)
            if len(raw) > MAX_BODY_BYTES:
                raise BridgeError("INVALID_SERVICE_RESPONSE")
            if response.status not in (200, 202):
                raise BridgeError("SERVICE_REJECTED")
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError
                    result[key] = value
                return result
            result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            return response.status, result
        except BridgeError:
            raise
        except (OSError, http.client.HTTPException, ValueError, UnicodeError, RecursionError):
            raise BridgeError("SERVICE_UNAVAILABLE") from None
        finally:
            connection.close()

    @staticmethod
    def _validate_reply(record, reply, *, submission):
        if not isinstance(reply, dict) or set(reply) != _WIRE_FIELDS:
            raise BridgeError("INVALID_SERVICE_RESPONSE")
        expected = {"session_id": record.wire_session, "request_id": record.wire_request,
                    "source_sha256": record.digest, "direction": "incoming", "target_language": "vi"}
        if any(reply[key] != value for key, value in expected.items()):
            raise BridgeError("INVALID_SERVICE_BINDING")
        nonce, state = reply["request_nonce"], reply["state"]
        if not isinstance(nonce, str) or not _HEX.fullmatch(nonce):
            raise BridgeError("INVALID_SERVICE_BINDING")
        if record.nonce is not None and not hmac.compare_digest(nonce, record.nonce):
            raise BridgeError("INVALID_SERVICE_BINDING")
        if state not in _STATES or (submission and state != "QUEUED"):
            raise BridgeError("INVALID_SERVICE_RESPONSE")
        if state == "TRANSLATED":
            text = reply["translation"]
            if (not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 64000
                    or reply["error_code"] is not None):
                raise BridgeError("INVALID_SERVICE_RESPONSE")
        elif reply["translation"] is not None or reply["error_code"] != ("TRANSLATION_FAILED" if state == "ERROR" else None):
            raise BridgeError("INVALID_SERVICE_RESPONSE")
        return state, nonce

    def background_step(self) -> bool:
        """Perform at most one bounded HTTP action, called on a background thread.

        The creator-thread check catches a common accidental blocking call; it
        does not discover or certify the game's UI thread or any Lua integration.
        """
        if threading.get_ident() == self._creator:
            raise BridgeError("BACKGROUND_THREAD_REQUIRED")
        if not self._background_lock.acquire(blocking=False):
            return False
        try:
            with self._lock:
                self._purge()
                if self._closed:
                    return False
                if self._cancels:
                    cleanup, _ = self._cancels.popleft()
                    action = "cancel"
                elif any(record.phase in ("NEW", "WAIT") for record in self._records.values()):
                    key, record = next((key, record) for key, record in self._records.items()
                                       if record.phase in ("NEW", "WAIT"))
                    self._records.move_to_end(key)
                    action = "submit" if record.phase == "NEW" else "poll"
                else:
                    return False
            if action == "cancel":
                try:
                    self._post("/v1/cancel", cleanup)
                except BridgeError:
                    pass  # Bounded best-effort cleanup; service TTL is the fallback.
                return True
            reply, error, nonce = None, None, None
            try:
                if action == "submit":
                    payload = {"session_id": record.wire_session, "request_id": record.wire_request,
                               "source_sha256": record.digest, "source_text": record.snapshot["original"],
                               "source_language": None, "target_language": "vi", "direction": "incoming"}
                    status, reply = self._post("/v1/translate", payload)
                else:
                    status, reply = self._post("/v1/result", record.lookup())
                if status != (202 if action == "submit" else 200):
                    raise BridgeError("INVALID_SERVICE_RESPONSE")
                state, nonce = self._validate_reply(record, reply, submission=action == "submit")
            except BridgeError as caught:
                error = str(caught)
            except Exception:
                error = "INVALID_SERVICE_RESPONSE"
            with self._lock:
                self._purge()
                # Compare object identity as well as wire binding: a reused local
                # request ID never inherits a prior occurrence's delayed result.
                if self._closed or self._records.get(key) is not record:
                    if nonce is not None and not self._closed and len(self._cancels) < 32:
                        self._cancels.append(({"session_id": record.wire_session, "request_id": record.wire_request,
                                               "request_nonce": nonce}, record.expires))
                    return True
                if error:
                    # Quarantine failures until the trusted local deadline. There
                    # are no retries and no identity/content derived from the bad
                    # reply. The eventual local ERROR lets the caller retire it.
                    record.phase = "WAIT_DEADLINE"
                    return True
                record.nonce, record.phase = nonce, "WAIT"
                if state in ("TRANSLATED", "ERROR", "CANCELLED"):
                    result = self._completion(record, state, reply["translation"], reply["error_code"])
                    self._completed[key] = (result, time.monotonic() + self._completion_ttl)
                    del self._records[key]
            return True
        finally:
            self._background_lock.release()

    def close(self):
        """Release local snapshots/secrets without performing network I/O."""
        with self._lock:
            self._closed = True
            self._records.clear()
            self._completed.clear()
            self._cancels.clear()
            self._token = ""
