from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any, BinaryIO, Iterable

from .models import SourceRecord, WorkspaceSettings, utc_now


AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".flac", ".aac"}
DOCUMENT_EXTENSIONS = {".docx", ".doc", ".pdf", ".txt", ".md", ".markdown", ".srt", ".vtt"}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | DOCUMENT_EXTENSIONS


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    stem = re.sub(r"[^\w.()\- ]+", "_", Path(name).stem, flags=re.UNICODE).strip(" .") or "source"
    suffix = Path(name).suffix.lower()
    return f"{stem[:140]}{suffix}"


def relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


class WorkspaceStore:
    directories = ("originals", "transcripts", "extracted", "metadata", "indexes", "exports", "logs", "archive")

    def __init__(self, root: Path):
        self._lock = RLock()
        self.set_root(root)

    def set_root(self, root: Path) -> None:
        resolved = root.expanduser().resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        for directory in self.directories:
            (resolved / directory).mkdir(parents=True, exist_ok=True)
        self.root = resolved

    def resolve_relative(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Path is outside the active workspace") from exc
        return candidate

    def metadata_path(self, source_id: str) -> Path:
        if not re.fullmatch(r"SRC_\d{4,}", source_id):
            raise ValueError("Invalid source ID")
        return self.root / "metadata" / f"{source_id}.json"

    def next_source_id(self) -> str:
        with self._lock:
            values = []
            for path in (self.root / "metadata").glob("SRC_*.json"):
                try:
                    values.append(int(path.stem.split("_")[1]))
                except (IndexError, ValueError):
                    continue
            for path in (self.root / "originals").glob("SRC_*_*"):
                try:
                    values.append(int(path.name.split("_")[1]))
                except (IndexError, ValueError):
                    continue
            for path in (self.root / "archive").glob("SRC_*_*"):
                try:
                    values.append(int(path.name.split("_")[1]))
                except (IndexError, ValueError):
                    continue
            return f"SRC_{(max(values, default=0) + 1):04d}"

    def list_sources(self) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        for path in sorted((self.root / "metadata").glob("SRC_*.json")):
            try:
                records.append(SourceRecord.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get_source(self, source_id: str) -> SourceRecord:
        path = self.metadata_path(source_id)
        if not path.exists():
            raise FileNotFoundError(source_id)
        return SourceRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def save_source(self, source: SourceRecord) -> None:
        source.updated_at = utc_now()
        atomic_write_json(self.metadata_path(source.source_id), source.model_dump())

    def find_duplicate(self, digest: str) -> SourceRecord | None:
        return next((source for source in self.list_sources() if source.sha256 == digest), None)

    def import_stream(self, filename: str, stream: BinaryIO) -> tuple[SourceRecord | None, SourceRecord | None]:
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {extension or '(none)'}")
        clean_name = safe_filename(filename)
        temp_path = self.root / "originals" / f".{clean_name}.uploading"
        digest = hashlib.sha256()
        with temp_path.open("wb") as target:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                target.write(chunk)
        with self._lock:
            existing = self.find_duplicate(digest.hexdigest())
            if existing:
                temp_path.unlink(missing_ok=True)
                return None, existing

            source_id = self.next_source_id()
            stored_name = f"{source_id}_{clean_name}"
            original_path = self.root / "originals" / stored_name
            os.replace(temp_path, original_path)
            source = SourceRecord(
                source_id=source_id,
                original_filename=Path(filename).name,
                stored_filename=stored_name,
                sha256=digest.hexdigest(),
                file_type="audio" if extension in AUDIO_EXTENSIONS else "document",
                extension=extension,
                original_path=relative_posix(original_path, self.root),
            )
            self.save_source(source)
            return source, None

    def read_content(self, source: SourceRecord) -> str:
        relative = source.corrected_path or source.content_path
        if not relative:
            return ""
        path = self.resolve_relative(relative)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def archive_source(self, source_id: str) -> Path:
        source = self.get_source(source_id)
        destination = self.root / "archive" / f"{source_id}_{utc_now().replace(':', '-') }"
        destination.mkdir(parents=True)
        paths: Iterable[str | None] = (
            source.original_path,
            source.content_path,
            source.corrected_path,
            *source.correction_history,
        )
        for relative in paths:
            if not relative:
                continue
            path = self.resolve_relative(relative)
            if path.exists():
                shutil.move(str(path), destination / path.name)
        shutil.move(str(self.metadata_path(source_id)), destination / f"{source_id}.json")
        return destination


def load_settings(project_root: Path) -> WorkspaceSettings:
    settings_file = project_root / "local_settings.json"
    default_workspace = Path(os.getenv("TRANSCRIPT_WORKSPACE") or project_root / "workspace").resolve()
    if not settings_file.exists():
        return WorkspaceSettings(
            workspace_path=str(default_workspace),
            transcription_quality=os.getenv("TRANSCRIPTION_QUALITY", "balanced"),
            ollama_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", ""),
            diarization_model_path=os.getenv("DIARIZATION_MODEL_PATH", ""),
        )
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    return WorkspaceSettings.model_validate(data)


def save_settings(project_root: Path, settings: WorkspaceSettings) -> None:
    atomic_write_json(project_root / "local_settings.json", settings.model_dump())

