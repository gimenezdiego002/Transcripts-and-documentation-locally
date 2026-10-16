# Architecture

## Folder structure

```text
backend/app/            FastAPI API and processing modules
backend/tests/          deterministic storage/generation tests
frontend/src/           React application and visual system
workspace/              default user workspace (runtime data)
  originals/            immutable imported files
  transcripts/          Whisper output and correction history
  extracted/            document Markdown
  metadata/             one atomic JSON record per source
  indexes/              rebuildable lexical indexes
  exports/              master Markdown/TXT and reports
  logs/                 application log
  archive/              recoverable removed sources
```

The workspace location is configurable and all paths persisted in metadata are relative to its root, so a workspace can be moved between computers.

## Processing pipeline

1. Stream uploads to a temporary file while calculating SHA-256.
2. Reject exact duplicates using metadata hashes.
3. Atomically move the original into `originals/` and atomically write source metadata.
4. Run the matching extractor in a background job. Documents preserve content order; audio runs Faster-Whisper locally.
5. Atomically save Markdown and update metadata. Interrupted `processing` items become resumable on the next launch.
6. Regenerate the master document deterministically from saved Markdown files.
7. Rebuild lexical search in memory from the saved artifacts; no database is used.

## Performance targets

- Uploads are streamed in 1 MiB chunks instead of being buffered in memory.
- File processing is serialized by default to avoid CPU/RAM exhaustion on typical Windows laptops.
- PDF and document extraction is page/element ordered.
- Faster-Whisper selects CPU `int8` by default and CUDA `float16` when available.
- The UI polls lightweight job/source endpoints while work is active.
- Master generation and lexical indexing are incremental-safe and rebuildable.

## Optional local models

Core import, document extraction, source management, lexical search, and master generation need no AI model. Audio transcription needs a downloaded Faster-Whisper model. Speaker diarization is exposed as capability metadata but requires a separately installed compatible local model. Ollama is optional and only improves topic organization and cited question answering; its output is labeled as an interpretation and is never inserted as original content.

