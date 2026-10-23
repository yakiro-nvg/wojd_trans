"""Bounded asynchronous translation with memory-only history and exact token guards."""
from __future__ import annotations

from collections import Counter, OrderedDict
from dataclasses import dataclass, replace
import queue
import re
import threading
import uuid

from .providers import TranslationError

MAX_MESSAGE_CHARS = 4000
_PROTECTED = re.compile(
    r'https?://[^\s<>]+'
    r'|</?[A-Za-z][^<>\r\n]{0,1000}>'
    r'|\{[^{}\r\n]{1,200}\}'
    r'|%(?:\d+\$)?[-+0 #]*(?:\d+|\*)?(?:\.\d+)?[sdifuxX]'
    r'|\[(?:item|link|player|skill):[^\]\r\n]{1,300}\]', re.IGNORECASE)
_NUMBER = re.compile(r'[-+−]?\d+(?:[.,:]\d+)*(?:[%％])?')
_SENTINEL = re.compile(r'__WOJD_T\d+__')


@dataclass(frozen=True)
class ChatEvent:
    id: str
    original: str
    translation: str | None = None
    status: str = 'QUEUED'
    error: str = ''
    direction: str = 'incoming'
    channel: str = ''
    sender: str = ''


def protect_text(text: str):
    """Protect recognized syntax only; this is not a parser for unknown game links."""
    if _SENTINEL.search(text):
        raise TranslationError('The message contains a reserved translation marker.')
    tokens = []
    def save(match):
        token = f'__WOJD_T{len(tokens)}__'
        tokens.append((token, match.group()))
        return token
    return _PROTECTED.sub(save, text), tokens


def restore_text(source: str, translated: str, tokens) -> str:
    if not isinstance(translated, str) or not translated.strip():
        raise TranslationError('The translation is empty.')
    expected = Counter(token for token, _ in tokens)
    if Counter(_SENTINEL.findall(translated)) != expected:
        raise TranslationError('A link or placeholder changed. Original text retained.')
    # Plain numeric values must survive exactly; do not trust invented/omitted amounts.
    plain_source = source
    plain_target = translated
    for token, value in tokens:
        plain_source = plain_source.replace(token, '')
        plain_target = plain_target.replace(token, '')
    if Counter(_NUMBER.findall(plain_source)) != Counter(_NUMBER.findall(plain_target)):
        raise TranslationError('A numeric value changed. Original text retained.')
    for token, value in tokens:
        translated = translated.replace(token, value)
    if len(translated) > MAX_MESSAGE_CHARS * 4:
        raise TranslationError('The translation is too long.')
    return translated


def validate_target_language(text: str, target_language: str):
    # A conservative wrong-script check, not semantic or language certification.
    # In particular a Chinese-only answer to a VI request must not look successful.
    if target_language.lower().startswith('vi'):
        han = sum('\u3400' <= c <= '\u9fff' for c in text)
        other_letters = sum(c.isalpha() and not '\u3400' <= c <= '\u9fff' for c in text)
        if han >= 4 and han > other_letters:
            raise TranslationError('The result appears to be Chinese instead of Vietnamese. Original text retained.')


class ChatService:
    """One background worker; no I/O, history, or screenshots are written to disk.

    Repeated messages get separate event IDs. Only translation work is cached.
    This does not certify meaning or reliably detect the language of short text.
    """
    def __init__(self, provider, max_pending=32, cache_size=512):
        if not 1 <= max_pending <= 256 or not 0 <= cache_size <= 4096:
            raise ValueError('Invalid queue/cache limit')
        self.provider = provider
        self._jobs = queue.Queue(maxsize=max_pending)
        self._limit = max_pending
        self._cache_size = cache_size
        self._cache = OrderedDict()
        # Coalesce state changes by ID, retaining enough latest records for the
        # UI's200-row history plus all pending jobs. A transition is not a new row.
        self._events = OrderedDict()
        self._event_limit = max(256, max_pending * 8)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._pending = 0
        self._dropped = 0
        self._worker = threading.Thread(target=self._run, name='wojd-chat-translate', daemon=True)
        self._worker.start()

    @property
    def pending_count(self):
        with self._lock:
            return self._pending

    @property
    def dropped_events(self):
        with self._lock:
            return self._dropped

    def _emit(self, event):
        with self._lock:
            if event.id not in self._events and len(self._events) >= self._event_limit:
                self._events.popitem(last=False)
                self._dropped += 1
            self._events[event.id] = event
            self._events.move_to_end(event.id)

    def submit(self, original, source_language=None, target_language='vi',
               direction='incoming', channel='', sender=''):
        if not isinstance(original, str) or not original.strip():
            return None
        if direction not in ('incoming', 'outgoing'):
            raise ValueError('Unknown direction')
        event = ChatEvent(uuid.uuid4().hex, original[:MAX_MESSAGE_CHARS], direction=direction,
                          channel=str(channel)[:100], sender=str(sender)[:200])
        if len(original) > MAX_MESSAGE_CHARS:
            self._emit(replace(event, status='ERROR', error='Message too long; split it before translation.'))
            return event.id
        if direction == 'outgoing' and original.lstrip().startswith('/'):
            self._emit(replace(event, status='SKIPPED', error='Commands require manual editing; no translation was sent.'))
            return event.id
        with self._lock:
            if self._stop.is_set() or self._pending >= self._limit:
                self._dropped += 1
                return None
            self._pending += 1
        self._emit(event)
        self._jobs.put_nowait((event, source_language, target_language))
        return event.id

    def poll(self):
        with self._lock:
            result = list(self._events.values())
            self._events.clear()
        return result

    def _run(self):
        while not self._stop.is_set():
            try:
                event, source_language, target_language = self._jobs.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._emit(replace(event, status='TRANSLATING'))
                key = (event.original, source_language, target_language, event.direction)
                if key in self._cache:
                    output = self._cache.pop(key)
                    self._cache[key] = output
                else:
                    text, tokens = protect_text(event.original)
                    if self._stop.is_set():
                        continue
                    raw = self.provider.translate(text, source_language, target_language)
                    validate_target_language(_SENTINEL.sub('', raw), target_language)
                    output = restore_text(text, raw, tokens)
                    if self._cache_size:
                        self._cache[key] = output
                        while len(self._cache) > self._cache_size:
                            self._cache.popitem(last=False)
                if not self._stop.is_set():
                    self._emit(replace(event, translation=output, status='TRANSLATED'))
            except TranslationError as exc:
                if not self._stop.is_set():
                    self._emit(replace(event, status='ERROR', error=str(exc)))
            except Exception:
                if not self._stop.is_set():
                    self._emit(replace(event, status='ERROR', error='Translation failed; original text retained.'))
            finally:
                with self._lock:
                    self._pending -= 1
                self._jobs.task_done()
        # Release references to queued private text when the companion is closed.
        while True:
            try:
                self._jobs.get_nowait()
                self._jobs.task_done()
                with self._lock:
                    self._pending -= 1
            except queue.Empty:
                break
        self._cache.clear()

    def close(self):
        self._stop.set()
        with self._lock:
            self._events.clear()
