"""Speech-to-text backends behind one interface."""
from dataclasses import dataclass
from . import audio, config

@dataclass
class Segment:
    start: float
    end: float
    text: str

@dataclass
class Result:
    segments: list
    language: str
    language_probability: float

class WhisperEngine:
    def __init__(self):
        from faster_whisper import WhisperModel   # optional import; heavy
        kw = dict(device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE)
        try:   # cached model: no Hub round-trip (it can hang on flaky networks)
            self.model = WhisperModel(config.WHISPER_MODEL, local_files_only=True, **kw)
        except Exception:   # not cached yet -> download
            self.model = WhisperModel(config.WHISPER_MODEL, **kw)

    def transcribe(self, wav, language=None) -> Result:
        # language=None -> Whisper auto-detects (multilingual models)
        segs, info = self.model.transcribe(wav, language=language, vad_filter=True)
        return Result([Segment(s.start, s.end, s.text.strip()) for s in segs],
                      info.language, info.language_probability)

class MockEngine:
    """Deterministic stand-in (one segment per non-silent span) for tests/demo."""
    def transcribe(self, wav, language=None) -> Result:
        dur = audio.inspect(wav)
        segs, t = [], 0.0
        for s, e in audio.silences(wav, dur) + [(dur, dur)]:
            if s - t > 0.05:
                segs.append(Segment(round(t, 2), round(s, 2), f"[mock speech {t:.1f}-{s:.1f}s]"))
            t = e
        return Result(segs, language or "en", 1.0)

_engine = None
def get_engine():
    """Load the model once per process (worker), not per job."""
    global _engine
    if _engine is None:
        _engine = MockEngine() if config.BACKEND == "mock" else WhisperEngine()
    return _engine
