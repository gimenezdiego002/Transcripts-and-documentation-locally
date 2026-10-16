from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from uuid import uuid4

from .extractors import extract_document
from .models import JobRecord, utc_now
from .organizer import generate_master
from .storage import WorkspaceStore, atomic_write_text, relative_posix
from .transcriber import transcribe_audio


class JobManager:
    def __init__(self, store: WorkspaceStore, quality_getter, diarization_getter=lambda: ""):
        self.store = store
        self.quality_getter = quality_getter
        self.diarization_getter = diarization_getter
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-processor")
        self.jobs: dict[str, JobRecord] = {}
        self.cancel_events: dict[str, Event] = {}
        self.lock = Lock()

    def list_jobs(self) -> list[JobRecord]:
        with self.lock:
            return sorted(self.jobs.values(), key=lambda job: job.created_at, reverse=True)

    def submit(self, source_id: str) -> JobRecord:
        job = JobRecord(job_id=f"JOB_{uuid4().hex[:10].upper()}", source_id=source_id)
        with self.lock:
            self.jobs[job.job_id] = job
            self.cancel_events[job.job_id] = Event()
        self.executor.submit(self._run, job.job_id)
        return job

    def cancel(self, job_id: str) -> bool:
        with self.lock:
            event = self.cancel_events.get(job_id)
            job = self.jobs.get(job_id)
            if not event or not job or job.status in {"completed", "failed", "cancelled"}:
                return False
            event.set()
            job.stage = "Cancellation requested"
            job.updated_at = utc_now()
            return True

    def _update(self, job_id: str, progress: int, stage: str) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.progress = progress
            job.stage = stage
            job.updated_at = utc_now()

    def _run(self, job_id: str) -> None:
        job = self.jobs[job_id]
        event = self.cancel_events[job_id]
        try:
            job.status = "processing"
            self._update(job_id, 5, "Preparing source")
            source = self.store.get_source(job.source_id)
            source.status = "processing"
            source.error = None
            self.store.save_source(source)
            if event.is_set():
                raise InterruptedError("Processing cancelled")
            source_path = self.store.resolve_relative(source.original_path)
            if source.file_type == "audio":
                result = transcribe_audio(
                    source_path,
                    self.quality_getter(),
                    self.diarization_getter(),
                    lambda p, s: self._update(job_id, p, s),
                )
                content = result.markdown
                source.language = result.language
                source.duration_seconds = result.duration_seconds
                source.warnings = result.warnings
                source.speaker_ids = result.speaker_ids
                output = self.store.root / "transcripts" / f"{source.source_id}.md"
            else:
                self._update(job_id, 25, "Extracting document content")
                result = extract_document(source_path)
                content = result.markdown
                source.language = result.language
                source.warnings = result.warnings
                output = self.store.root / "extracted" / f"{source.source_id}.md"
            if event.is_set():
                raise InterruptedError("Processing cancelled")
            self._update(job_id, 94, "Saving Markdown artifact")
            header = (
                f"# {source.original_filename}\n\n"
                f"> Source ID: `{source.source_id}`  \n"
                f"> Original: `{source.original_path}`  \n"
                f"> SHA-256: `{source.sha256}`\n\n"
            )
            atomic_write_text(output, header + content.rstrip() + "\n")
            source.content_path = relative_posix(output, self.store.root)
            source.status = "completed"
            self.store.save_source(source)
            self._update(job_id, 97, "Refreshing master knowledge file")
            generate_master(self.store)
            job.status = "completed"
            self._update(job_id, 100, "Completed")
        except InterruptedError:
            job.status = "cancelled"
            job.stage = "Cancelled"
            try:
                source = self.store.get_source(job.source_id)
                source.status = "cancelled"
                self.store.save_source(source)
            except Exception:
                pass
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.stage = "Failed"
            job.updated_at = utc_now()
            try:
                source = self.store.get_source(job.source_id)
                source.status = "failed"
                source.error = str(exc)
                source.warnings.append(traceback.format_exc(limit=3))
                self.store.save_source(source)
            except Exception:
                pass

