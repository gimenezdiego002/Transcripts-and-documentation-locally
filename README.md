# Local Knowledge Studio

A private Windows application that imports recordings and documents, transcribes or extracts them locally, and produces a traceable `MASTER_KNOWLEDGE.md`. Persistent data is ordinary files and folders—no SQLite, database server, cloud account, or mandatory external API.

## What works

- Batch file and folder import for M4A, MP3, WAV, FLAC, AAC, DOCX, DOC, PDF, TXT, Markdown, SRT, and VTT.
- Streaming SHA-256 duplicate detection and atomic JSON metadata updates.
- Ordered Word, PDF, text, Markdown, and subtitle extraction without summarizing the original.
- Local Faster-Whisper transcription with automatic language detection, timestamps, English/Spanish support, CPU `int8`, optional CUDA `float16`, and low-confidence markers.
- Fast, Balanced, and Accurate model profiles.
- Per-source Markdown, manual correction versions, reprocessing, interruption recovery, and recoverable archival.
- Deterministic master Markdown/TXT generation with source, topic, timeline, decision, and uncertainty indexes plus complete source content.
- File-backed lexical search and a source-cited assistant.
- Optional local Ollama synthesis; answers are rejected if they do not cite retrieved source IDs.
- Responsive React/TypeScript/Tailwind dashboard on `localhost`.

Speaker diarization is capability-gated: no model is bundled, and the app does not pretend to identify speakers without one. Install `requirements-optional-diarization.txt`, point Settings at an already downloaded local pyannote pipeline, and reprocess audio to add speaker labels. Legacy `.doc` extraction uses an installed copy of LibreOffice, Antiword, or Catdoc.

## Windows setup

Requirements:

- Windows 10 or 11
- Python 3.11, 3.12, or 3.13
- Node.js 20+
- Enough local disk space for files and Whisper models

Double-click `setup.bat`. It creates a local `.venv`, installs Python and frontend packages, and builds the dashboard. Then double-click `start.bat`; the app opens at [http://127.0.0.1:8000](http://127.0.0.1:8000).

The first audio transcription downloads the selected Whisper model once. After dependencies and desired models have been downloaded, the core app works offline.

## Optional Ollama

1. Install Ollama locally.
2. Download a model, for example `ollama pull llama3.2:3b`.
3. In **Settings**, enter that exact model name and keep the endpoint at `http://127.0.0.1:11434`.

Ollama receives only the locally retrieved excerpts through its loopback API. Leaving the model blank keeps the assistant in deterministic lexical mode.

## Workspace layout

```text
workspace/
  originals/       immutable imported files
  transcripts/     Whisper output and correction versions
  extracted/       document Markdown
  metadata/        one JSON file per source
  indexes/         reserved for rebuildable local indexes
  exports/
    MASTER_KNOWLEDGE.md
    MASTER_KNOWLEDGE.txt
    SOURCE_INDEX.json
    PROCESSING_REPORT.json
  logs/
  archive/         recoverable removed sources
```

The active workspace can be changed from **Settings** to paths such as `D:\Transcripts\MyKnowledge`. Artifact links are stored relative to the workspace root, so copied workspaces remain portable.

## Development

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Frontend (a second terminal):

```powershell
cd frontend
npm run dev
```

Tests and production build:

```powershell
.\.venv\Scripts\python.exe -m pytest backend
cd frontend
npm run build
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for processing details and [DESIGN.md](DESIGN.md) for the interface system.

## Accuracy notes

- Complete extracted or transcribed content is always included in the master document; indexes do not replace it.
- Topic grouping is described as lexical support, not proof that sources refer to the same project.
- Dates are indexed only when explicitly present in source content.
- Corrected transcript versions never overwrite the original machine output.
- Scanned PDFs need OCR before import; pages with no extractable text are reported.
- Cancellation is cooperative between processing stages. A native Whisper inference already in progress finishes its current call before cancellation is finalized.

