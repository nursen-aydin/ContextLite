"""Small, local RAG helpers used by the HTTP layer.

Embeddings are stored as JSON in SQLite because the student project has a
small knowledge base.  This keeps the implementation inspectable and avoids a
separate vector database.
"""

import json
import math
import re
from typing import Iterable, List, Optional

from src.services.db import get_connection, search_chunks


def split_text(text: str, chunk_size: int = 900, overlap: int = 150) -> List[str]:
    """Split on a nearby whitespace boundary with a small overlap."""
    normalized = re.sub(r"\r\n?", "\n", text or "")
    normalized = re.sub(r"[ \t]+", " ", normalized).strip()
    if not normalized:
        return []

    chunks: List[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            boundary = max(normalized.rfind("\n", start + chunk_size // 2, end),
                           normalized.rfind(" ", start + chunk_size // 2, end))
            if boundary > start:
                end = boundary
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        next_start = max(end - overlap, start + 1)
        boundary = normalized.find(" ", next_start, min(end + 1, length))
        start = boundary + 1 if boundary >= 0 else next_start
    return chunks


def build_fts_query(text: str) -> str:
    words = re.findall(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]+", text or "")
    unique = []
    seen = set()
    for word in words:
        folded = word.casefold()
        if len(folded) < 3 or folded in seen:
            continue
        seen.add(folded)
        unique.append(word)
    return " OR ".join(f'"{word}"*' for word in unique[:12])


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = list(left)
    right_values = list(right)
    if not left_values or len(left_values) != len(right_values):
        return -1.0
    dot = sum(a * b for a, b in zip(left_values, right_values))
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if left_norm == 0 or right_norm == 0:
        return -1.0
    return dot / (left_norm * right_norm)


def project_has_embeddings(user_id: int, project_id: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT 1 FROM document_chunks
            WHERE user_id = ? AND project_id = ? AND embedding_json IS NOT NULL
            LIMIT 1
            """,
            (user_id, project_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def retrieve_relevant_chunks(
    user_id: int,
    project_id: str,
    query: str,
    query_embedding: Optional[List[float]] = None,
    limit: int = 3,
    min_semantic_score: float = 0.25,
) -> List[dict]:
    """Use semantic retrieval when possible, otherwise fall back to FTS5."""
    if query_embedding:
        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT c.id, c.content, c.page_number, c.chunk_index,
                       c.embedding_json, c.embedding_model, f.filename
                FROM document_chunks c
                JOIN files f ON f.id = c.file_id
                WHERE c.user_id = ? AND c.project_id = ?
                  AND c.embedding_json IS NOT NULL
                """,
                (user_id, project_id),
            ).fetchall()
        finally:
            conn.close()

        scored = []
        for row in rows:
            try:
                embedding = json.loads(row["embedding_json"])
                score = cosine_similarity(query_embedding, embedding)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            # Returning an unrelated "best" chunk is worse than returning no
            # context: it encourages a small model to invent an answer.  A
            # deliberately conservative floor keeps project answers grounded.
            if score >= min_semantic_score:
                item = dict(row)
                item.pop("embedding_json", None)
                item["score"] = round(score, 4)
                item["retrieval_method"] = "semantic"
                scored.append(item)
        if scored:
            scored.sort(key=lambda item: item["score"], reverse=True)
            return scored[:limit]

    fts_query = build_fts_query(query)
    if not fts_query:
        return []
    rows = search_chunks(user_id, project_id, fts_query, limit)
    return [dict(row, retrieval_method="keyword", score=None) for row in rows]
