from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
import os, uuid
from pathlib import Path
from . import audio, config, jobs, tasks
from .service import to_srt, to_vtt

app = FastAPI(title="Transcription service")
MAX_BYTES = config.MAX_UPLOAD_MB * 1024 * 1024

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/transcriptions", status_code=202)
async def create(background: BackgroundTasks, file: UploadFile = File(...),
                 language: str | None = Form(None)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in config.ALLOWED_EXT:
        raise HTTPException(415, f"unsupported type '{ext}'. Allowed: {sorted(config.ALLOWED_EXT)}")
    dest = config.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    size = 0
    try:
        with open(dest, "wb") as f:                      # stream to disk; enforce limit as we go
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, f"file exceeds {config.MAX_UPLOAD_MB} MB")
                f.write(chunk)
        if size == 0:
            raise HTTPException(400, "empty file")
        try:
            dur = audio.inspect(dest)                    # integrity check by content
        except audio.InvalidAudio as e:
            raise HTTPException(422, str(e))
        if dur > config.MAX_DURATION_S:
            raise HTTPException(413, f"audio longer than {config.MAX_DURATION_S}s")
    except Exception:
        dest.unlink(missing_ok=True); raise
    job_id = jobs.create(file.filename, dest, language)
    tasks.enqueue(job_id, background)
    return {"job_id": job_id, "status": "queued", "duration": dur,
            "links": {"status": f"/transcriptions/{job_id}"}}

@app.get("/transcriptions/{job_id}")
def status(job_id: str):
    try:
        j = jobs.get(job_id)
    except KeyError:
        raise HTTPException(404, "unknown job")
    return {k: v for k, v in j.items() if k != "upload_path"}

@app.get("/transcriptions/{job_id}/{fmt}", response_class=PlainTextResponse)
def download(job_id: str, fmt: str):
    try:
        j = jobs.get(job_id)
    except KeyError:
        raise HTTPException(404, "unknown job")
    if j["status"] != "done":
        raise HTTPException(409, f"job is {j['status']}")
    if fmt == "srt": return to_srt(j["result"])
    if fmt == "vtt": return to_vtt(j["result"])
    raise HTTPException(404, "formats: srt, vtt")
