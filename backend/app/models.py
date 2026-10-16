from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkspaceSettings(BaseModel):
    workspace_path: str
    transcription_quality: Literal["fast", "balanced", "accurate"] = "balanced"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    diarization_model_path: str = ""


class SourceRecord(BaseModel):
    source_id: str
    original_filename: str
    stored_filename: str
    sha256: str
    file_type: Literal["audio", "document"]
    extension: str
    status: Literal["queued", "processing", "completed", "failed", "cancelled"] = "queued"
    language: str | None = None
    date: str | None = None
    duration_seconds: float | None = None
    speaker_ids: list[str] = Field(default_factory=list)
    original_path: str
    content_path: str | None = None
    corrected_path: str | None = None
    correction_history: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class JobRecord(BaseModel):
    job_id: str
    source_id: str
    status: Literal["queued", "processing", "completed", "failed", "cancelled"] = "queued"
    progress: int = 0
    stage: str = "Queued"
    error: str | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class AssistantRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    source_ids: list[str] = Field(default_factory=list)
    use_ollama: bool = True


class CorrectionRequest(BaseModel):
    content: str = Field(min_length=1)


class WorkspaceUpdate(BaseModel):
    workspace_path: str = Field(min_length=1)


class QualityUpdate(BaseModel):
    quality: Literal["fast", "balanced", "accurate"]

