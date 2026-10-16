from __future__ import annotations

import asyncio
import json
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .jobs import JobManager
from .models import AssistantRequest, CorrectionRequest, WorkspaceSettings, WorkspaceUpdate
from .organizer import generate_master
from .search import answer_with_evidence, search
from .storage import WorkspaceStore, atomic_write_text, load_settings, relative_posix, save_settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
settings = load_settings(PROJECT_ROOT)
store = WorkspaceStore(Path(settings.workspace_path))
jobs = JobManager(store, lambda: settings.transcription_quality, lambda: settings.diarization_model_path)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Sources interrupted by a prior shutdown are safe to resume from their immutable originals.
    for source in reversed(store.list_sources()):
        if source.status in {"queued", "processing"}:
            jobs.submit(source.source_id)
    yield
    jobs.executor.shutdown(wait=False, cancel_futures=False)


app = FastAPI(title="Local Knowledge Studio", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "local_only": True, "workspace": str(store.root), "version": app.version}


@app.get("/api/settings")
def get_settings():
    return settings


@app.put("/api/settings/workspace")
def update_workspace(request: WorkspaceUpdate):
    global settings
    requested = Path(request.workspace_path).expanduser()
    try:
        store.set_root(requested)
    except OSError as exc:
        raise HTTPException(400, f"Cannot use that workspace: {exc}") from exc
    settings.workspace_path = str(store.root)
    save_settings(PROJECT_ROOT, settings)
    return settings


@app.put("/api/settings")
def update_settings(request: WorkspaceSettings):
    global settings
    try:
        store.set_root(Path(request.workspace_path))
    except OSError as exc:
        raise HTTPException(400, f"Cannot use that workspace: {exc}") from exc
    settings = request.model_copy(update={"workspace_path": str(store.root)})
    save_settings(PROJECT_ROOT, settings)
    return settings


@app.get("/api/stats")
def stats():
    sources = store.list_sources()
    master_path = store.root / "exports" / "MASTER_KNOWLEDGE.md"
    return {
        "total_files": len(sources),
        "recordings": sum(source.file_type == "audio" for source in sources),
        "documents": sum(source.file_type == "document" for source in sources),
        "transcripts": sum(source.file_type == "audio" and source.status == "completed" for source in sources),
        "completed": sum(source.status == "completed" for source in sources),
        "processing": sum(source.status in {"queued", "processing"} for source in sources),
        "failed": sum(source.status == "failed" for source in sources),
        "duration_seconds": sum(source.duration_seconds or 0 for source in sources),
        "master_exists": master_path.exists(),
        "master_updated_at": master_path.stat().st_mtime if master_path.exists() else None,
    }


@app.get("/api/sources")
def list_sources():
    return [source.model_dump() for source in store.list_sources()]


@app.get("/api/sources/{source_id}")
def get_source(source_id: str):
    try:
        source = store.get_source(source_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "Source not found") from exc
    return {**source.model_dump(), "content": store.read_content(source)}


@app.post("/api/import")
async def import_files(files: list[UploadFile] = File(...), quality: str | None = Form(None)):
    if quality in {"fast", "balanced", "accurate"}:
        settings.transcription_quality = quality
        save_settings(PROJECT_ROOT, settings)
    imported, duplicates, errors = [], [], []
    for upload in files:
        try:
            source, duplicate = await asyncio.to_thread(store.import_stream, upload.filename or "unnamed", upload.file)
            if duplicate:
                duplicates.append({"filename": upload.filename, "source_id": duplicate.source_id})
            elif source:
                job = jobs.submit(source.source_id)
                imported.append({"source": source.model_dump(), "job": job.model_dump()})
        except Exception as exc:
            errors.append({"filename": upload.filename, "error": str(exc)})
        finally:
            await upload.close()
    return {"imported": imported, "duplicates": duplicates, "errors": errors}


@app.get("/api/jobs")
def list_jobs():
    return [job.model_dump() for job in jobs.list_jobs()]


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    if not jobs.cancel(job_id):
        raise HTTPException(409, "Job cannot be cancelled")
    return {"cancelled": True}


@app.post("/api/sources/{source_id}/reprocess")
def reprocess_source(source_id: str):
    try:
        source = store.get_source(source_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "Source not found") from exc
    source.status = "queued"
    source.error = None
    store.save_source(source)
    return jobs.submit(source_id)


@app.put("/api/sources/{source_id}/correction")
def correct_source(source_id: str, request: CorrectionRequest):
    try:
        source = store.get_source(source_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "Source not found") from exc
    if not source.content_path:
        raise HTTPException(409, "Source has no completed content to correct")
    version = len(source.correction_history) + 1
    path = store.root / "transcripts" / f"{source.source_id}.corrected.v{version}.md"
    atomic_write_text(path, request.content.rstrip() + "\n")
    if source.corrected_path:
        source.correction_history.append(source.corrected_path)
    elif source.content_path not in source.correction_history:
        source.correction_history.append(source.content_path)
    source.corrected_path = relative_posix(path, store.root)
    store.save_source(source)
    generate_master(store)
    return {**source.model_dump(), "content": request.content}


@app.delete("/api/sources/{source_id}")
def archive_source(source_id: str):
    try:
        destination = store.archive_source(source_id)
        generate_master(store)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "Source not found") from exc
    return {"archived": True, "archive_path": str(destination)}


@app.post("/api/master/generate")
def regenerate_master():
    path, report = generate_master(store)
    return {"path": str(path), "report": report}


@app.get("/api/master", response_class=PlainTextResponse)
def get_master():
    path = store.root / "exports" / "MASTER_KNOWLEDGE.md"
    if not path.exists():
        path, _ = generate_master(store)
    return path.read_text(encoding="utf-8")


@app.get("/api/master/download")
def download_master(format: str = "md"):
    if format not in {"md", "txt"}:
        raise HTTPException(400, "Format must be md or txt")
    generate_master(store)
    name = "MASTER_KNOWLEDGE.md" if format == "md" else "MASTER_KNOWLEDGE.txt"
    media_type = "text/markdown" if format == "md" else "text/plain"
    return FileResponse(store.root / "exports" / name, filename=name, media_type=media_type)


@app.get("/api/search")
def search_sources(q: str, source_ids: str = ""):
    selected = [value for value in source_ids.split(",") if value]
    return [hit.__dict__ for hit in search(store, q, selected)]


async def _ollama_answer(question: str, citations: list[dict]) -> str | None:
    if not settings.ollama_model or not citations:
        return None
    context = "\n\n".join(
        f"[{item['source_id']}{' @ ' + item['timestamp'] if item.get('timestamp') else ''}] {item['excerpt']}"
        for item in citations
    )
    prompt = (
        "Answer only from the evidence below. Cite every factual claim with [SRC_####] and timestamps when supplied. "
        "If evidence is insufficient or conflicts, say so. Do not invent or import outside knowledge.\n\n"
        f"QUESTION:\n{question}\n\nEVIDENCE:\n{context}"
    )
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{settings.ollama_url.rstrip('/')}/api/generate",
                json={"model": settings.ollama_model, "prompt": prompt, "stream": False, "options": {"temperature": 0}},
            )
            response.raise_for_status()
            answer = response.json().get("response", "").strip()
            if answer and any(item["source_id"] in answer for item in citations):
                return answer
    except Exception:
        return None
    return None


@app.post("/api/assistant")
async def assistant(request: AssistantRequest):
    result = answer_with_evidence(store, request.question, request.source_ids)
    if request.use_ollama and result["grounded"]:
        ollama_answer = await _ollama_answer(request.question, result["citations"])
        if ollama_answer:
            result["answer"] = ollama_answer
            result["mode"] = "ollama-grounded"
    return result


@app.post("/api/workspace/open")
def open_workspace_folder():
    if os.name != "nt":
        raise HTTPException(501, "Opening the folder is currently supported on Windows")
    os.startfile(str(store.root / "exports"))  # type: ignore[attr-defined]
    return {"opened": True}


FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def frontend(full_path: str):
        candidate = (FRONTEND_DIST / full_path).resolve()
        try:
            candidate.relative_to(FRONTEND_DIST.resolve())
        except ValueError:
            raise HTTPException(404)
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

