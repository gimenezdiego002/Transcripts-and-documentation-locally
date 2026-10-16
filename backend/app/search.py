from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .storage import WorkspaceStore


TOKEN_RE = re.compile(r"[\wÀ-ÿ][\wÀ-ÿ'-]{1,}", re.UNICODE)
TIMESTAMP_RE = re.compile(r"\[(\d{2}:\d{2}:\d{2}\.\d{3})\s*→")


@dataclass
class SearchHit:
    source_id: str
    filename: str
    excerpt: str
    score: float
    timestamp: str | None = None


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text)]


def search(store: WorkspaceStore, query: str, source_ids: list[str] | None = None, limit: int = 12) -> list[SearchHit]:
    terms = tokenize(query)
    if not terms:
        return []
    selected = set(source_ids or [])
    sources = [
        source for source in store.list_sources()
        if source.status == "completed" and source.content_path and (not selected or source.source_id in selected)
    ]
    chunks: list[tuple[object, str]] = []
    for source in sources:
        content = store.read_content(source)
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
        chunks.extend((source, "\n".join(paragraphs[index:index + 3])) for index in range(0, len(paragraphs), 3))
    if not chunks:
        return []
    document_frequency = Counter(term for term in set(terms) for _, chunk in chunks if term in set(tokenize(chunk)))
    hits: list[SearchHit] = []
    for source, chunk in chunks:
        counts = Counter(tokenize(chunk))
        score = 0.0
        for term in terms:
            tf = counts[term]
            if tf:
                inverse = math.log((len(chunks) + 1) / (document_frequency[term] + 0.5)) + 1
                score += (1 + math.log(tf)) * inverse
        phrase = query.casefold() in chunk.casefold()
        if phrase:
            score *= 1.8
        if score > 0:
            timestamp_match = TIMESTAMP_RE.search(chunk)
            compact = re.sub(r"\s+", " ", chunk).strip()
            hits.append(SearchHit(source.source_id, source.original_filename, compact[:700], score, timestamp_match.group(1) if timestamp_match else None))
    return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]


def answer_with_evidence(store: WorkspaceStore, question: str, source_ids: list[str] | None = None) -> dict:
    hits = search(store, question, source_ids, limit=6)
    if not hits:
        return {
            "answer": "I could not verify an answer in the selected local sources.",
            "grounded": False,
            "citations": [],
            "mode": "lexical",
        }
    citations = [
        {
            "source_id": hit.source_id,
            "filename": hit.filename,
            "timestamp": hit.timestamp,
            "excerpt": hit.excerpt,
        }
        for hit in hits
    ]
    answer = "Relevant evidence found in the local sources:\n\n" + "\n\n".join(
        f"[{hit.source_id}{' @ ' + hit.timestamp if hit.timestamp else ''}] {hit.excerpt}" for hit in hits[:4]
    )
    return {"answer": answer, "grounded": True, "citations": citations, "mode": "lexical"}

