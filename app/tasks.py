"""Background processing. Celery (Redis broker) in production; eager mode for dev."""
import os
from . import config, jobs
from .audio import InvalidAudio, ToolError
from .service import transcribe_file

def run_job(job_id, attempt=0):
    """Do the work. Permanent errors -> failed. Transient errors propagate for retry."""
    job = jobs.update(job_id, status="processing", attempts=attempt + 1)
    def progress(done, total):
        jobs.update(job_id, progress=round(done / total, 3))
    try:
        result = transcribe_file(job["upload_path"], language=job.get("language"), on_progress=progress)
    except InvalidAudio as e:
        jobs.update(job_id, status="failed", error=str(e))      # retrying won't help
        return
    jobs.update(job_id, status="done", progress=1.0, result=result)
    try: os.remove(job["upload_path"])                           # keep disk bounded
    except OSError: pass

try:
    from celery import Celery
    celery_app = Celery("stt", broker=config.REDIS_URL, backend=config.REDIS_URL)
    celery_app.conf.update(task_acks_late=True, worker_prefetch_multiplier=1,   # long tasks: one at a time
                           task_reject_on_worker_lost=True, task_track_started=True)

    @celery_app.task(bind=True, autoretry_for=(ToolError, OSError), retry_backoff=True,
                     retry_backoff_max=300, retry_jitter=True, max_retries=3)
    def transcribe_task(self, job_id):
        try:
            run_job(job_id, attempt=self.request.retries)
        except Exception as e:
            if self.request.retries >= self.max_retries:
                jobs.update(job_id, status="failed", error=f"gave up after retries: {e}")
            raise
except ImportError:
    celery_app = None

def enqueue(job_id, background=None):
    if config.QUEUE_MODE == "eager":
        # dev: run after the response via FastAPI BackgroundTasks (single process, no retries)
        if background is not None: background.add_task(run_job, job_id)
        else: run_job(job_id)
    else:
        transcribe_task.delay(job_id)
