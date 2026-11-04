import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
UPLOAD_DIR = DATA_DIR / "uploads"
JOB_DIR = DATA_DIR / "jobs"

ALLOWED_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".webm", ".mp4"}
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", 500))
MAX_DURATION_S = int(os.environ.get("MAX_DURATION_S", 4 * 3600))

# Chunking: 5-10 min windows, cut at silence when possible, 2 s overlap otherwise.
CHUNK_TARGET_S = float(os.environ.get("CHUNK_TARGET_S", 600))   # upper bound (10 min)
CHUNK_MIN_S = float(os.environ.get("CHUNK_MIN_S", 300))         # lower bound (5 min)
CHUNK_OVERLAP_S = float(os.environ.get("CHUNK_OVERLAP_S", 2))

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8")
BACKEND = os.environ.get("BACKEND", "whisper")  # whisper | mock (tests/demo)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
# eager = run jobs in-process (dev/tests, no Redis); celery = real queue
QUEUE_MODE = os.environ.get("QUEUE_MODE", "celery")

for d in (UPLOAD_DIR, JOB_DIR):
    d.mkdir(parents=True, exist_ok=True)
