"""Core pipeline: normalize -> chunk -> transcribe -> offset/merge -> postprocess."""
import re, collections, tempfile
from pathlib import Path
from . import audio, config
from .engine import get_engine

def plan_chunks(duration, sil, min_len, max_len, overlap):
    """Returns [(own_a, own_b, win_a, win_b)]. Cut in the latest silence between
    min_len and max_len; if none, hard cut at max_len (overlap protects boundary words)."""
    cuts, pos = [0.0], 0.0
    while duration - pos > max_len:
        mids = [(s + e) / 2 for s, e in sil if pos + min_len <= (s + e) / 2 <= pos + max_len]
        cut = max(mids) if mids else pos + max_len
        cuts.append(cut); pos = cut
    cuts.append(duration)
    return [(a, b, max(0.0, a - overlap), min(duration, b + overlap)) for a, b in zip(cuts, cuts[1:])]

def transcribe_file(path, engine=None, language=None, on_progress=None,
                    min_len=None, max_len=None, overlap=None):
    engine = engine or get_engine()
    min_len = min_len or config.CHUNK_MIN_S
    max_len = max_len or config.CHUNK_TARGET_S
    overlap = config.CHUNK_OVERLAP_S if overlap is None else overlap
    with tempfile.TemporaryDirectory() as td:
        audio.inspect(path)                       # permanent-failure gate (InvalidAudio, never retried)
        wav = audio.normalize(path, Path(td) / "norm.wav")
        dur = audio.inspect(wav)
        chunks = plan_chunks(dur, audio.silences(wav, dur), min_len, max_len, overlap)
        out, lang, prob = [], language, None
        for i, (own_a, own_b, win_a, win_b) in enumerate(chunks):
            part = Path(td) / f"c{i}.wav"
            audio.cut(wav, part, win_a, win_b)
            res = engine.transcribe(str(part), language=lang)
            if lang is None:                      # detect on chunk 0, reuse for the rest
                lang, prob = res.language, res.language_probability
            last = i == len(chunks) - 1
            for s in res.segments:
                st, en = s.start + win_a, s.end + win_a      # chunk-local -> global time
                mid = (st + en) / 2
                if own_a <= mid < own_b or (last and mid >= own_a):   # dedupe by midpoint ownership
                    out.append({"start": round(max(st, own_a), 2),
                                "end": round(min(en, own_b), 2), "text": s.text})
            if on_progress:
                on_progress(i + 1, len(chunks))
        out.sort(key=lambda s: s["start"])
        return postprocess({"duration": round(dur, 2), "language": lang,
                            "language_probability": prob, "chunks": len(chunks), "segments": out})

STOP = set("the a an and or of to in is it that this for on with as at by be are was i you we".split())

def postprocess(r, top_k=5):
    text = " ".join(s["text"] for s in r["segments"])
    words = re.findall(r"\w+'?\w*", text.lower())
    kw = collections.Counter(w for w in words if w not in STOP and len(w) > 2)
    speech = sum(s["end"] - s["start"] for s in r["segments"])
    r["text"] = text
    r["stats"] = {"words": len(words), "segments": len(r["segments"]),
                  "speech_seconds": round(speech, 2),
                  "words_per_minute": round(len(words) / speech * 60, 1) if speech else 0,
                  "keywords": [w for w, _ in kw.most_common(top_k)]}
    return r

def _ts(t, sep):
    h, rem = divmod(t, 3600); m, s = divmod(rem, 60)
    return f"{int(h):02}:{int(m):02}:{int(s):02}{sep}{int(round((s % 1) * 1000)):03}"

def to_srt(r):
    return "\n".join(f"{i}\n{_ts(s['start'], ',')} --> {_ts(s['end'], ',')}\n{s['text']}\n"
                     for i, s in enumerate(r["segments"], 1))

def to_vtt(r):
    return "WEBVTT\n\n" + "\n".join(f"{_ts(s['start'], '.')} --> {_ts(s['end'], '.')}\n{s['text']}\n"
                                    for s in r["segments"])
