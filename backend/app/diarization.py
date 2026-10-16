from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


def diarize_audio(audio_path: Path, model_path: str) -> list[SpeakerTurn]:
    """Run an explicitly configured pyannote model from a local path."""
    path = Path(model_path).expanduser().resolve()
    if not path.exists():
        raise RuntimeError(f"Local diarization model was not found: {path}")
    try:
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise RuntimeError(
            "A diarization model is configured, but pyannote.audio is not installed. "
            "Install requirements-optional-diarization.txt or clear the model path."
        ) from exc
    pipeline = Pipeline.from_pretrained(str(path))
    output = pipeline(str(audio_path))
    annotation = getattr(output, "speaker_diarization", output)
    return [
        SpeakerTurn(float(turn.start), float(turn.end), str(speaker))
        for turn, _, speaker in annotation.itertracks(yield_label=True)
    ]


def speaker_for_segment(start: float, end: float, turns: list[SpeakerTurn]) -> str | None:
    overlaps = [
        (max(0.0, min(end, turn.end) - max(start, turn.start)), turn.speaker)
        for turn in turns
    ]
    best = max(overlaps, default=(0.0, None), key=lambda item: item[0])
    return best[1] if best[0] > 0 else None

