from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


MODEL_BY_QUALITY = {"fast": "tiny", "balanced": "small", "accurate": "large-v3"}


@dataclass
class TranscriptionResult:
    markdown: str
    language: str | None
    duration_seconds: float | None
    warnings: list[str]
    speaker_ids: list[str]


def format_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def transcribe_audio(
    path: Path,
    quality: str,
    diarization_model_path: str = "",
    progress: Callable[[int, str], None] | None = None,
) -> TranscriptionResult:
    # The optimized Xet transport can stall behind corporate proxies. Standard HTTPS is
    # slower but substantially more reliable for the one-time local model download.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Faster-Whisper is not installed. Run setup.bat, then retry this source.") from exc

    model_name = MODEL_BY_QUALITY.get(quality, "small")
    if progress:
        progress(20, f"Loading local Whisper model: {model_name}")
    device, compute_type = "cpu", "int8"
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            device, compute_type = "cuda", "float16"
    except Exception:
        pass
    try:
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
    except Exception as exc:
        raise RuntimeError(
            f"Could not load the local Whisper model '{model_name}'. Models download once on first use; "
            "an internet connection is needed for that initial download. Details: {exc}"
        ) from exc

    if progress:
        progress(35, "Detecting language and transcribing")
    segments, info = model.transcribe(
        str(path),
        beam_size=5 if quality != "fast" else 1,
        vad_filter=True,
        condition_on_previous_text=True,
        word_timestamps=False,
    )
    captured_segments: list[tuple[float, float, str, bool]] = []
    warnings: list[str] = []
    duration = getattr(info, "duration", None)
    for index, segment in enumerate(segments):
        text = segment.text.strip()
        confidence_low = getattr(segment, "avg_logprob", 0.0) < -1.0 or getattr(segment, "no_speech_prob", 0.0) > 0.6
        if confidence_low:
            text = text or "[unintelligible speech]"
            warnings.append(f"Low-confidence audio near {format_timestamp(segment.start)}.")
        captured_segments.append((float(segment.start), float(segment.end), text, confidence_low))
        if progress and duration:
            progress(min(92, 35 + int((segment.end / duration) * 57)), "Transcribing audio locally")
    language = getattr(info, "language", None)
    speaker_ids: list[str] = []
    turns = []
    if diarization_model_path:
        if progress:
            progress(93, "Identifying speakers with local diarization model")
        try:
            from .diarization import diarize_audio

            turns = diarize_audio(path, diarization_model_path)
            speaker_ids = sorted({turn.speaker for turn in turns})
        except Exception as exc:
            warnings.append(f"Speaker diarization was unavailable: {exc}")
    lines: list[str] = []
    for start, end, text, confidence_low in captured_segments:
        speaker = None
        if turns:
            from .diarization import speaker_for_segment

            speaker = speaker_for_segment(start, end, turns)
        marker = "[uncertain] " if confidence_low else ""
        label = f"**{speaker}:** " if speaker else ""
        lines.append(f"[{format_timestamp(start)} → {format_timestamp(end)}] {label}{marker}{text}")
    header = f"<!-- language: {language or 'unknown'}; model: {model_name}; device: {device} -->"
    return TranscriptionResult(
        markdown=f"{header}\n\n" + "\n\n".join(lines),
        language=language,
        duration_seconds=duration,
        warnings=warnings,
        speaker_ids=speaker_ids,
    )

