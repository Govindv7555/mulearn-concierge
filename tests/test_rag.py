"""
µLearn Concierge — Tests for RAG Retrieval Engine
"""

import os
import pytest
from rag import KnowledgeStore, retrieve, get_store


@pytest.fixture
def store(tmp_path):
    """Create a KnowledgeStore with sample knowledge files in a temp directory."""
    kb_dir = tmp_path / "knowledge"
    kb_dir.mkdir()

    # Sample website file
    site_file = kb_dir / "website.md"
    site_file.write_text(
        "# µLearn Platform\n\n"
        "## What is µLearn\n"
        "µLearn is a community-driven education platform backed by GTech and IEEE. "
        "It focuses on peer learning and real-world skills.\n\n"
        "## Karma Points\n"
        "Karma points are gamified learning points earned by submitting proof of work, "
        "coding tasks, and helping peers.\n\n"
        "## Interest Groups\n"
        "Interest Groups (IGs) are domain-specific communities for AI, Web, Mobile, and IoT.\n",
        encoding="utf-8"
    )

    # Sample discord file
    discord_file = kb_dir / "discord_news.md"
    discord_file.write_text(
        "# Discord Announcements\n\n"
        "## 2026-11-01 — Hackathon Kickoff\n"
        "<!-- msg_id: 1001 -->\n"
        "Join our annual hackathon with exciting prizes and 500 Karma points reward.\n",
        encoding="utf-8"
    )

    return KnowledgeStore(knowledge_dir=str(kb_dir))


def test_chunking_and_sources(store):
    """Verify that markdown sections are parsed into chunks with correct sources."""
    assert len(store.chunks) == 4
    
    titles = [c["title"] for c in store.chunks]
    assert "What is µLearn" in titles
    assert "Karma Points" in titles
    assert "Interest Groups" in titles
    assert "2026-11-01 — Hackathon Kickoff" in titles

    sources = [c["source"] for c in store.chunks]
    assert sources.count("website") == 3
    assert sources.count("discord") == 1


def test_tokenization(store):
    """Verify tokenization preserves µ and lowercases tokens."""
    tokens = store._tokenize("What are µLearn Karma Points? Visit https://mulearn.org!")
    assert "what" in tokens
    assert "µlearn" in tokens
    assert "karma" in tokens
    assert "points" in tokens
    # URL and punctuation should be stripped
    assert "https" not in tokens
    assert "mulearn.org" not in tokens


def test_retrieval_relevance(store):
    """Verify BM25 retrieves the most relevant chunk first."""
    results = store.retrieve("How do I earn Karma points?", top_k=2)
    assert len(results) > 0
    assert results[0]["title"] == "Karma Points"
    assert "proof of work" in results[0]["text"]
    assert results[0]["source"] == "website"


def test_retrieval_discord_announcements(store):
    """Verify BM25 correctly matches discord news entries."""
    results = store.retrieve("hackathon kickoff prizes", top_k=2)
    assert len(results) > 0
    assert results[0]["title"] == "2026-11-01 — Hackathon Kickoff"
    assert results[0]["source"] == "discord"


def test_empty_and_whitespace_query(store):
    """Verify empty queries return empty results without error."""
    assert store.retrieve("") == []
    assert store.retrieve("    ") == []
    assert store.retrieve("!@#$%^&*()") == []


def test_get_all_sources(store):
    """Verify source summary includes files and chunk counts."""
    sources = store.get_all_sources()
    assert "website.md" in sources
    assert sources["website.md"]["source"] == "website"
    assert sources["website.md"]["chunks"] == 3

    assert "discord_news.md" in sources
    assert sources["discord_news.md"]["source"] == "discord"
    assert sources["discord_news.md"]["chunks"] == 1


def test_actual_workspace_knowledge():
    """Verify the default KnowledgeStore loads the actual workspace knowledge files."""
    actual_store = get_store()
    assert len(actual_store.chunks) > 0
    results = retrieve("What is µLearn?")
    assert len(results) > 0
    assert any("mulearn" in c["text"].lower() for c in results)

