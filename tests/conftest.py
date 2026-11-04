import os, subprocess, sys, tempfile
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
os.environ["BACKEND"] = "mock"
os.environ["QUEUE_MODE"] = "eager"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest

def make_audio(path, pattern, codec=()):
    parts, labels = [], []
    for i, (kind, d) in enumerate(pattern):
        src = f"sine=frequency=440:duration={d}" if kind == "tone" else f"anullsrc=r=44100:cl=mono:d={d}"
        parts += ["-f", "lavfi", "-i", src]; labels.append(f"[{i}:a]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *parts, "-filter_complex",
                    "".join(labels) + f"concat=n={len(pattern)}:v=0:a=1[o]", "-map", "[o]", *codec, str(path)], check=True)

@pytest.fixture
def mk(tmp_path):
    def _mk(name, pattern, codec=()):
        p = tmp_path / name; make_audio(p, pattern, codec); return p
    return _mk
