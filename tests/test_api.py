"""
µLearn Concierge — Tests for Flask API Endpoints
"""

import pytest
import json
from app import app, _rate_store


@pytest.fixture
def client(monkeypatch):
    """Create Flask test client with offline fallback enabled for fast, deterministic unit tests."""
    app.config["TESTING"] = True
    monkeypatch.setattr("app.is_api_available", lambda: False)
    # Clear rate limit memory between tests
    _rate_store.clear()
    with app.test_client() as client:
        yield client


def test_index_page(client):
    """GET / should return 200 and serve HTML containing the concierge UI."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"\xc2\xb5Learn" in response.data or b"&micro;Learn" in response.data or b"uLearn" in response.data or "µLearn".encode("utf-8") in response.data
    assert b"chatMessages" in response.data


def test_health_endpoint(client):
    """GET /api/health returns 200, status ok, and knowledge chunks count."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert "api_available" in data
    assert data["knowledge_chunks"] > 0


def test_status_endpoint(client):
    """GET /api/status returns knowledge info and api_mode."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.get_json()
    assert "knowledge_sources" in data
    assert "api_mode" in data


def test_chat_empty_body(client):
    """POST /api/chat with empty or non-JSON payload returns 400."""
    response = client.post("/api/chat", data="", content_type="application/json")
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_chat_empty_message(client):
    """POST /api/chat with empty message returns 400."""
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400
    data = response.get_json()
    assert "empty" in data["error"].lower()


def test_chat_too_long_message(client):
    """POST /api/chat with >1000 characters returns 400."""
    long_msg = "hello " * 200  # 1200 characters
    response = client.post("/api/chat", json={"message": long_msg})
    assert response.status_code == 400
    data = response.get_json()
    assert "too long" in data["error"].lower()


def test_chat_gibberish_message(client):
    """POST /api/chat with no alphabetic characters returns 400."""
    response = client.post("/api/chat", json={"message": "12345 67890 !@#$%^&*()"})
    assert response.status_code == 400
    data = response.get_json()
    assert "readable" in data["error"].lower()


def test_chat_valid_query(client):
    """POST /api/chat with valid question returns 200, reply, and sources."""
    response = client.post("/api/chat", json={"message": "What is µLearn?"})
    assert response.status_code == 200
    data = response.get_json()
    assert "reply" in data
    assert len(data["reply"]) > 20
    assert "sources" in data
    assert isinstance(data["sources"], list)


def test_chat_with_history(client):
    """POST /api/chat handles conversation history cleanly."""
    history = [
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Welcome to µLearn Concierge!"}
    ]
    response = client.post("/api/chat", json={
        "message": "What are Karma points?",
        "history": history
    })
    assert response.status_code == 200
    data = response.get_json()
    assert "karma" in data["reply"].lower() or "point" in data["reply"].lower()


def test_chat_rate_limiting(client):
    """Exceeding 10 requests within the window triggers a 429 response."""
    _rate_store.clear()
    for _ in range(10):
        res = client.post("/api/chat", json={"message": "What is µLearn?"})
        assert res.status_code == 200

    # 11th request should be rate-limited
    res = client.post("/api/chat", json={"message": "What is µLearn?"})
    assert res.status_code == 429
    data = res.get_json()
    assert "too many requests" in data["error"].lower()


def test_small_talk_returns_no_source_chips(client):
    """Small talk queries (hello, how are you, joke) must return used_sources=False and empty sources."""
    _rate_store.clear()
    for greeting in ["hello", "how are you", "tell me a joke", "thank you so much", "who are you"]:
        res = client.post("/api/chat", json={"message": greeting})
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("used_sources") is False, f"Expected no sources for: {greeting}"
        assert data.get("sources") == [], f"Expected empty sources for: {greeting}"
        assert len(data.get("reply", "")) > 5


def test_mulearn_questions_cite_sources(client):
    """µLearn specific questions must cite sources and return used_sources=True."""
    _rate_store.clear()
    for question in ["What is µLearn?", "What are Karma points?", "How do I join an Interest Group?"]:
        res = client.post("/api/chat", json={"message": question})
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("used_sources") is True, f"Expected used_sources=True for: {question}"
        assert len(data.get("sources", [])) > 0, f"Expected sources list for: {question}"
        assert any("mulearn.org" in s.get("url", "") or "discord" in s.get("url", "") for s in data["sources"])


def test_missing_api_key_mode_answers_greetings(client, monkeypatch):
    """When GEMINI_API_KEY is missing (offline fallback), greetings are answered warmly with no source chips."""
    _rate_store.clear()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Greeting
    res = client.post("/api/chat", json={"message": "hi there"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["used_sources"] is False
    assert data["sources"] == []
    assert "hello" in data["reply"].lower() or "concierge" in data["reply"].lower()

    # Joke
    res_joke = client.post("/api/chat", json={"message": "tell me a joke"})
    assert res_joke.status_code == 200
    data_joke = res_joke.get_json()
    assert data_joke["used_sources"] is False
    assert data_joke["sources"] == []
    assert "programmer" in data_joke["reply"].lower() or "bug" in data_joke["reply"].lower()

    # µLearn question in offline mode still cites sources
    res_mulearn = client.post("/api/chat", json={"message": "What is µLearn?"})
    assert res_mulearn.status_code == 200
    data_mulearn = res_mulearn.get_json()
    assert data_mulearn["used_sources"] is True
    assert len(data_mulearn["sources"]) > 0


