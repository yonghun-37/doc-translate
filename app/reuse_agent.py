"""Exact-text translation memory at docutranslate's agent boundary."""
import re
import time


class TranslationError(RuntimeError):
    pass


# Only measurements/numbers, never arbitrary short words or model names.
_MEASUREMENT = re.compile(
    r'^[\s+−\-±.,\d()/:%‰°²³×*^]*(?:mm|cm|km|m|mg|kg|g|ml|mL|L|l|ms|s|h|Hz|kHz|MHz|GHz|'
    r'V|kV|A|mA|W|kW|MW|Pa|kPa|MPa|bar|N|Nm|J|kJ|Wh|kWh|B|KB|MB|GB|TB|℃|℉|C|F)'
    r'(?:[\s\d²³/^.*·−\-]+(?:s|h|m|kg|K))?[\s²³]*$'
)


def needs_translation(text: str) -> bool:
    value = text.strip()
    scientific = re.fullmatch(r'[+\-]?\d+(?:\.\d+)?[eE][+\-]?\d+', value)
    return any(c.isalpha() for c in text) and not _MEASUREMENT.fullmatch(value) and not scientific


class FakeAgent:
    def __init__(self, lang: str, *, identity: bool = False):
        self.lang = lang
        self.identity = identity
        self.calls: list[list[str]] = []
        self.glossary: dict[str, str] = {}

    def send_segments(self, segments: list[str], chunk_size: int) -> list[str]:
        self.calls.append(list(segments))
        return [s if self.identity else f'[{self.lang}] {s}' for s in segments]

    def update_glossary_dict(self, d):
        self.glossary.update(d or {})


class ReuseAgent:
    def __init__(self, memory: dict[str, str], inner, recorder: list | None = None,
                 *, progress_batch: int = 40, callback=None):
        if type(progress_batch) is not int or progress_batch < 1:
            raise ValueError('progress_batch는 양의 정수여야 합니다.')
        self.progress_batch = progress_batch
        self.callback = callback
        self._cache = dict(memory)
        self._reusable = frozenset(memory)
        self.memory: dict[str, str] = {}  # Only this job's strings.
        self.inner = inner
        self.recorder = recorder
        self.stats = {'segments': 0, 'reused': 0, 'translated': 0}

    def send_segments(self, segments: list[str], chunk_size: int) -> list[str]:
        missing = list(dict.fromkeys(s for s in segments if s not in self._cache and needs_translation(s)))
        self.stats['segments'] += len(segments)
        self.stats['reused'] += sum(s in self._reusable and needs_translation(s) for s in segments)
        if self.callback:
            self.callback('reuse', dict(self.stats))
        batches = (len(missing) + self.progress_batch - 1) // self.progress_batch
        for index, start in enumerate(range(0, len(missing), self.progress_batch), 1):
            batch = missing[start:start + self.progress_batch]
            if self.recorder is not None:
                self.recorder.extend(batch)
            if self.callback:
                self.callback('llm', dict(self.stats))
            started = time.monotonic()
            result = self.inner.send_segments(batch, chunk_size)
            if (not isinstance(result, list) or len(result) != len(batch)
                    or any(not isinstance(s, str) or not s.strip() for s in result)):
                raise TranslationError('번역 결과의 개수 또는 내용이 올바르지 않습니다.')
            if hasattr(self.inner, 'get_full_stats') and self.inner.get_full_stats().get('unresolved_errors', 0):
                raise TranslationError('번역 엔진에서 일부 세그먼트 처리에 실패했습니다.') from getattr(self.inner, 'last_request_error', None)
            self._cache.update(zip(batch, result))
            self.stats['translated'] += len(batch)
            if self.callback:
                self.callback('batch', {**self.stats, 'count': len(batch), 'batch': index,
                                       'batches': batches, 'elapsed': time.monotonic() - started})
        result = [self._cache[s] if s in self._cache else s for s in segments]
        self.memory.update(zip(segments, result))
        if self.callback:
            self.callback('write', dict(self.stats))
        return result

    def update_glossary_dict(self, d):
        self.inner.update_glossary_dict(d)
