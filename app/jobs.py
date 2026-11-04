"""Tiny file-backed job store on a shared volume (API + workers see the same files).
Atomic writes via rename. Swap for Redis/Postgres if you need querying."""
import json, os, time, uuid
from . import config

def _path(job_id):
    if not job_id.isalnum():
        raise KeyError(job_id)            # blocks path traversal
    return config.JOB_DIR / f"{job_id}.json"

def create(filename, upload_path, language=None) -> str:
    job_id = uuid.uuid4().hex
    save(job_id, {"id": job_id, "status": "queued", "filename": filename,
                  "upload_path": str(upload_path), "language": language,
                  "progress": 0.0, "created": time.time(), "attempts": 0})
    return job_id

def save(job_id, doc):
    p = _path(job_id); tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc)); os.replace(tmp, p)

def get(job_id):
    try:
        return json.loads(_path(job_id).read_text())
    except FileNotFoundError:
        raise KeyError(job_id)

def update(job_id, **fields):
    d = get(job_id); d.update(fields); save(job_id, d); return d
