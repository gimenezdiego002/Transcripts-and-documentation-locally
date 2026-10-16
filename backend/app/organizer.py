from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import SourceRecord
from .storage import WorkspaceStore, atomic_write_json, atomic_write_text


STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been", "before", "being", "between",
    "both", "but", "can", "could", "did", "does", "each", "from", "had", "has", "have", "into", "its",
    "more", "most", "not", "only", "other", "our", "over", "should", "some", "such", "than", "that",
    "the", "their", "them", "then", "there", "these", "they", "this", "through", "under", "very", "was",
    "were", "what", "when", "where", "which", "while", "will", "with", "would", "you", "your", "como",
    "con", "del", "desde", "donde", "el", "ella", "ellos", "entre", "esta", "este", "para", "pero", "por",
    "que", "sin", "son", "una", "uno", "las", "los", "más", "muy",
}
DATE_PATTERNS = (
    re.compile(r"\b(20\d{2}-[01]\d-[0-3]\d)\b"),
    re.compile(r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+20\d{2})\b", re.I),
)
DECISION_RE = re.compile(r"\b(decided|decision|agreed|approved|resolved|will proceed|acordamos|decidido|aprobado)\b", re.I)
UNCERTAINTY_RE = re.compile(r"\b(uncertain|unintelligible|unknown|unclear|maybe|possibly|contradict|tbd|open question|no está claro|quizá)\b", re.I)
WORD_RE = re.compile(r"[\wÀ-ÿ][\wÀ-ÿ'-]{2,}", re.UNICODE)


@dataclass
class IndexedSource:
    source: SourceRecord
    content: str


def _lines_matching(content: str, pattern: re.Pattern[str], limit: int = 30) -> list[str]:
    results: list[str] = []
    for line in content.splitlines():
        cleaned = line.strip().lstrip("-*># ")
        if cleaned and pattern.search(cleaned):
            results.append(cleaned[:500])
        if len(results) >= limit:
            break
    return results


def _extract_topics(items: list[IndexedSource], limit: int = 12) -> list[tuple[str, list[str], int]]:
    per_topic: dict[str, set[str]] = defaultdict(set)
    counts: Counter[str] = Counter()
    for item in items:
        words = [word.casefold() for word in WORD_RE.findall(item.content)]
        local_counts = Counter(word for word in words if word not in STOP_WORDS and not word.isdigit())
        for word, count in local_counts.items():
            if count >= 2 or len(items) == 1:
                counts[word] += count
                per_topic[word].add(item.source.source_id)
    ranked = sorted(counts, key=lambda word: (len(per_topic[word]), counts[word], len(word)), reverse=True)
    return [(word, sorted(per_topic[word]), counts[word]) for word in ranked[:limit]]


def _extract_dates(content: str) -> list[str]:
    found: list[str] = []
    for pattern in DATE_PATTERNS:
        found.extend(match.group(1) for match in pattern.finditer(content))
    return list(dict.fromkeys(found))[:30]


def _display_date(source: SourceRecord) -> str:
    return source.date or "Not reliably detected"


def generate_master(store: WorkspaceStore) -> tuple[Path, dict]:
    completed = [source for source in reversed(store.list_sources()) if source.status == "completed" and source.content_path]
    items = [IndexedSource(source, store.read_content(source)) for source in completed]
    topics = _extract_topics(items)
    total_audio = sum(source.duration_seconds or 0 for source in completed if source.file_type == "audio")
    decisions: list[tuple[str, str]] = []
    uncertainties: list[tuple[str, str]] = []
    timeline: list[tuple[str, str, str]] = []
    for item in items:
        decisions.extend((item.source.source_id, text) for text in _lines_matching(item.content, DECISION_RE))
        uncertainties.extend((item.source.source_id, text) for text in _lines_matching(item.content, UNCERTAINTY_RE))
        timeline.extend((date, item.source.source_id, item.source.original_filename) for date in _extract_dates(item.content))

    output: list[str] = [
        "# Master Knowledge Base",
        "",
        "## 1. Overview",
        "",
        f"This knowledge base contains {len(items)} fully processed local source(s): "
        f"{sum(i.source.file_type == 'audio' for i in items)} audio recording(s) and "
        f"{sum(i.source.file_type == 'document' for i in items)} document(s). "
        f"The included audio duration is {total_audio / 3600:.2f} hours. "
        "Organized sections are deterministic indexes; complete preserved content appears in section 8.",
        "",
        "## 2. Source Index",
        "",
        "| Source ID | Original filename | Type | Date | Language | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in items:
        source = item.source
        output.append(
            f"| `{source.source_id}` | {source.original_filename.replace('|', '\\|')} | {source.file_type} "
            f"| {_display_date(source)} | {source.language or 'Unknown'} | {source.status} |"
        )

    output.extend(["", "## 3. Topic Index", ""])
    if topics:
        for topic, source_ids, count in topics:
            links = ", ".join(f"[{source_id}](#{source_id.lower()})" for source_id in source_ids)
            output.append(f"- **{topic.title()}** — {links} ({count} occurrence(s))")
    else:
        output.append("No reliable recurring topics were detected.")

    output.extend(["", "## 4. Projects and Discussions", ""])
    shared_topics = [topic for topic in topics if len(topic[1]) > 1]
    if shared_topics:
        output.append("The following lexical topics occur in multiple sources. This is an index, not a claim that the sources describe the same project.")
        output.append("")
        for topic, source_ids, _ in shared_topics:
            output.append(f"### {topic.title()}\n\nSupporting sources: " + ", ".join(f"`{source_id}`" for source_id in source_ids))
    else:
        output.append("No cross-source project grouping was made automatically. This avoids merging unrelated material on weak evidence.")

    output.extend(["", "## 5. Chronological Timeline", ""])
    if timeline:
        for date, source_id, filename in sorted(timeline, key=lambda row: row[0]):
            output.append(f"- **{date}** — referenced in `{source_id}` ({filename})")
    else:
        output.append("No reliable explicit dates were detected in source content.")

    output.extend(["", "## 6. Decisions and Important Facts", ""])
    if decisions:
        output.extend(f"- [{source_id}] {text}" for source_id, text in decisions)
    else:
        output.append("No statements using explicit decision language were detected. Review complete source content for implicit decisions.")

    output.extend(["", "## 7. Uncertainties and Contradictions", ""])
    if uncertainties:
        output.extend(f"- [{source_id}] {text}" for source_id, text in uncertainties)
    else:
        output.append("No explicit uncertainty markers were detected. Absence of a marker does not prove that all source claims agree.")

    output.extend(["", "## 8. Complete Original Content", ""])
    for item in items:
        source = item.source
        output.extend([
            f"<a id=\"{source.source_id.lower()}\"></a>",
            f"### {source.source_id} — {source.original_filename}",
            "",
            f"- **Source ID:** `{source.source_id}`",
            f"- **Original filename:** {source.original_filename}",
            f"- **File type:** {source.file_type} ({source.extension})",
            f"- **Date:** {_display_date(source)}",
            f"- **Language:** {source.language or 'Unknown'}",
            f"- **Speakers:** {', '.join(source.speaker_ids) if source.speaker_ids else 'Not available'}",
            f"- **Original file:** `{source.original_path}`",
            f"- **Content artifact:** `{source.corrected_path or source.content_path}`",
        ])
        if source.corrected_path:
            output.append("- **Content note:** Manually corrected version shown; original machine output remains preserved in correction history.")
        if source.warnings:
            output.extend(["- **Extraction/transcription warnings:**", *[f"  - {warning}" for warning in source.warnings]])
        output.extend(["", item.content.rstrip(), "", "---", ""])

    master = "\n".join(output).rstrip() + "\n"
    export_dir = store.root / "exports"
    markdown_path = export_dir / "MASTER_KNOWLEDGE.md"
    atomic_write_text(markdown_path, master)
    atomic_write_text(export_dir / "MASTER_KNOWLEDGE.txt", master)
    index = [
        {
            "source_id": item.source.source_id,
            "original_filename": item.source.original_filename,
            "file_type": item.source.file_type,
            "content_path": item.source.corrected_path or item.source.content_path,
            "original_path": item.source.original_path,
            "sha256": item.source.sha256,
        }
        for item in items
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(items),
        "topic_count": len(topics),
        "decision_count": len(decisions),
        "uncertainty_count": len(uncertainties),
        "sources_with_warnings": [item.source.source_id for item in items if item.source.warnings],
        "failed_sources": [source.source_id for source in store.list_sources() if source.status == "failed"],
    }
    atomic_write_json(export_dir / "SOURCE_INDEX.json", index)
    atomic_write_json(export_dir / "PROCESSING_REPORT.json", report)
    return markdown_path, report

