"""ffmpeg/ffprobe helpers: validation, normalization, silence detection."""
import re, subprocess
from pathlib import Path

SR = 16000

class InvalidAudio(ValueError):
    """Permanent input problem (don't retry)."""

class ToolError(RuntimeError):
    """ffmpeg failed unexpectedly (may be transient)."""

def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise ToolError(f"{cmd[0]}: {p.stderr.strip()[-300:]}")
    return p

def inspect(path) -> float:
    """Return duration in seconds or raise InvalidAudio. Detects by content, not extension."""
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                        "-show_entries", "stream=codec_name:format=duration",
                        "-of", "default=nw=1", str(path)], capture_output=True, text=True)
    if p.returncode != 0 or "codec_name" not in p.stdout:
        raise InvalidAudio("file is corrupted, unsupported, or has no audio stream")
    m = re.search(r"duration=([\d.]+)", p.stdout)
    dur = float(m.group(1)) if m else 0.0
    if dur <= 0:
        raise InvalidAudio("audio has zero or unknown duration")
    return dur

def normalize(src, dst):
    """Anything ffmpeg can decode -> 16 kHz mono 16-bit PCM WAV."""
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1",
          "-ar", str(SR), "-c:a", "pcm_s16le", str(dst)])
    return dst

def cut(src, dst, start, end):
    _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
          "-i", str(src), "-c:a", "pcm_s16le", str(dst)])

def silences(wav, duration, noise_db=-35, min_len=0.4):
    p = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav), "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_len}", "-f", "null", "-"],
                       capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    if len(st) > len(en):
        en.append(duration)
    return list(zip(st, en))
