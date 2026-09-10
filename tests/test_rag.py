import json

from src.services.db import add_document_chunk, add_file, create_project, create_user
from src.services.rag import cosine_similarity, retrieve_relevant_chunks, split_text


def test_split_text_uses_small_overlapping_chunks():
    text = " ".join(f"kelime{i}" for i in range(400))
    chunks = split_text(text, chunk_size=300, overlap=50)
    assert len(chunks) > 2
    assert all(len(chunk) <= 300 for chunk in chunks)


def test_cosine_similarity():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_semantic_retrieval_returns_closest_chunk():
    user_id = create_user("RAG User", "rag@example.com", "hash")
    create_project("project-1", user_id, "Test")
    add_file("file-1", user_id, "project-1", "notlar.txt", "text/plain", 20)
    add_document_chunk(
        "chunk-1", user_id, "project-1", "file-1", 1, 0,
        "Elma kırmızı bir meyvedir.", json.dumps([1.0, 0.0]), "test-embedding",
    )
    add_document_chunk(
        "chunk-2", user_id, "project-1", "file-1", 1, 1,
        "Gökyüzü açık havada mavidir.", json.dumps([0.0, 1.0]), "test-embedding",
    )

    results = retrieve_relevant_chunks(
        user_id, "project-1", "Hangi meyve kırmızı?", [0.9, 0.1], limit=1
    )
    assert results[0]["id"] == "chunk-1"
    assert results[0]["retrieval_method"] == "semantic"


def test_semantic_retrieval_rejects_unrelated_chunks():
    user_id = create_user("Threshold User", "threshold@example.com", "hash")
    create_project("project-threshold", user_id, "Test")
    add_file("file-threshold", user_id, "project-threshold", "notlar.txt", "text/plain", 20)
    add_document_chunk(
        "chunk-threshold", user_id, "project-threshold", "file-threshold", 1, 0,
        "Bu parça soruyla ilgili değildir.", json.dumps([1.0, 0.0]), "test-embedding",
    )

    results = retrieve_relevant_chunks(
        user_id, "project-threshold", "Kuantum dolaşıklığı nedir", [0.0, 1.0], limit=1
    )
    assert results == []
