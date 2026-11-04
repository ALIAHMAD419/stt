# Transcription service

FastAPI + faster-whisper, ffmpeg normalization, chunked processing, Celery/Redis background jobs.

## Run
    docker compose up --build            # api :8000, worker, redis
    curl -F file=@talk.mp3 localhost:8000/transcriptions          # -> {"job_id": ...}  (202)
    curl localhost:8000/transcriptions/<job_id>                   # status, progress, result
    curl localhost:8000/transcriptions/<job_id>/srt               # also /vtt

Dev without Docker/Redis: `QUEUE_MODE=eager BACKEND=mock uvicorn app.api:app`
Tests: `pytest tests` (API tests auto-skip if fastapi/httpx are missing)

## Result shape
    {"language":"en","language_probability":0.98,"duration":1834.2,"chunks":4,
     "segments":[{"start":0.0,"end":4.2,"text":"..."}],
     "text":"...","stats":{"words":..,"segments":..,"speech_seconds":..,"words_per_minute":..,"keywords":[..]}}

## Design decisions
- **Async by default**: upload returns 202 + job id; a worker does the slow part. HTTP requests never wait on a model.
- **Validation at the door** (cheap, before queueing): extension allowlist (415), streamed size cap (413, enforced while
  writing so a huge upload can't fill memory), empty file (400), ffprobe integrity/audio-stream/duration check (422).
  Format is judged by content, not by extension.
- **Formats**: ffmpeg decodes anything, output is 16 kHz mono PCM WAV, so the ASR step sees one format.
- **Language**: auto-detected on chunk 1 and reused for the rest, so a long file doesn't flip language mid-way on a noisy
  chunk. Pass `language=` form field to override.
- **Long audio**: 5-10 min chunks, cut in the latest silence in that range; hard cut + 2 s overlap if none. Timestamps are
  shifted by the chunk window offset. Each chunk owns a time span and keeps only segments whose midpoint is inside it,
  clamped to it, so the overlap never produces duplicate text.
- **Retries**: transient failures (ffmpeg/IO errors) retry with exponential backoff + jitter, max 3; permanent ones
  (corrupt audio) fail immediately with the reason. `acks_late` + `reject_on_worker_lost` re-queue a job if a worker
  dies; concurrency 1 per worker since the model is CPU/RAM-heavy (scale by adding workers).
- **Model loaded once per worker process**, not per job.
- **Job store**: JSON files on a shared volume, atomic writes. Simple and inspectable; swap for Postgres/Redis for
  querying or multi-host.

## Known limits / next steps
- A retry restarts the whole file (no per-chunk checkpoint), so a failure on chunk 9 redoes chunks 1-8.
- No auth/rate limiting; uploads and finished jobs are not auto-expired (add a TTL sweep).
- Speaker diarization and word-level timestamps are not included (faster-whisper supports word timestamps).
- Multi-channel audio is downmixed to mono.

## Verification status
Verified in a sandbox with a mock engine on generated audio: formats (wav/mp3/flac/ogg/m4a), chunk planning, offsets and
dedupe across chunk boundaries, validation errors, SRT/VTT, job lifecycle (success, permanent failure).
NOT run there: real Whisper transcription, FastAPI endpoints, Celery/Redis, Docker (packages blocked by sandbox proxy).
Those layers are written to the libraries' documented APIs; run `docker compose up` and `pytest` locally to confirm.
