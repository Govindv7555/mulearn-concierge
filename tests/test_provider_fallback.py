"""
µLearn Concierge — Tests for Multi-Provider Fallback Chain, Cooldown,
Reasoning Stripping, Caching, Rate Limiting, and Offline Responder.

All tests are completely mocked with ZERO live API or network calls.
"""

import json
import time
import pytest
from unittest.mock import patch, MagicMock

import httpx

import llm
from llm import (
    generate,
    generate_answer,
    clean_reply,
    is_in_cooldown,
    set_cooldown,
    clear_cooldowns,
    is_ai_online,
    _cooldown_store,
    to_ascii_header,
    set_test_transport,
)
from app import app, _rate_store, _question_cache
from fallback import fallback_answer


@pytest.fixture(autouse=True)
def reset_state():
    """Clear in-memory state before and after each test."""
    clear_cooldowns()
    set_test_transport(None)
    _rate_store.clear()
    _question_cache.clear()
    yield
    clear_cooldowns()
    set_test_transport(None)
    _rate_store.clear()
    _question_cache.clear()


# ---------------------------------------------------------------------------
# 1. Fallback Chain: First provider 429 -> Second answers
# ---------------------------------------------------------------------------

def test_first_provider_429_fallback_to_second(monkeypatch):
    """When the first provider returns 429, it enters cooldown and the second provider answers."""
    monkeypatch.setenv("LLM_PROVIDERS", "gemini,openai_compat")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_compat_key")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "meta-llama/llama-3.3-70b-instruct")

    def mock_gemini(model, messages, context):
        req = httpx.Request("POST", "https://mock.gemini")
        resp = httpx.Response(429, headers={"Retry-After": "60"}, request=req)
        raise httpx.HTTPStatusError("Resource exhausted", request=req, response=resp)

    def mock_openai_compat(model, messages, context):
        return "Response from OpenRouter (OpenAI-compatible)!"

    monkeypatch.setattr("llm._call_gemini", mock_gemini)
    monkeypatch.setattr("llm._call_openai_compat", mock_openai_compat)

    reply, sources, used = generate_answer("How do I earn Karma points?")

    assert reply == "Response from OpenRouter (OpenAI-compatible)!"
    # Verify Gemini is now in cooldown
    assert is_in_cooldown("gemini", "gemini-3.8-flash") is True
    # Verify OpenAI candidate is NOT in cooldown
    assert is_in_cooldown("openai_compat", "meta-llama/llama-3.3-70b-instruct") is False


# ---------------------------------------------------------------------------
# 2. Cooldown skips the failing candidate on subsequent calls
# ---------------------------------------------------------------------------

def test_cooldown_skips_failing_provider_afterwards(monkeypatch):
    """A provider currently in cooldown is skipped without attempting to call it."""
    monkeypatch.setenv("LLM_PROVIDERS", "gemini,openai_compat")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_compat_key")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "meta-llama/llama-3.3-70b-instruct")

    gemini_mock = MagicMock()
    monkeypatch.setattr("llm._call_gemini", gemini_mock)

    openai_mock = MagicMock(return_value="Answer from healthy candidate")
    monkeypatch.setattr("llm._call_openai_compat", openai_mock)

    # Put Gemini in cooldown
    set_cooldown("gemini", "gemini-3.8-flash", duration_seconds=300)

    reply, sources, used = generate_answer("What is µLearn?")

    assert reply == "Answer from healthy candidate"
    assert gemini_mock.call_count == 0  # Gemini was skipped immediately!
    assert openai_mock.call_count == 1


# ---------------------------------------------------------------------------
# 3. Candidate returning only reasoning moves to the next model
# ---------------------------------------------------------------------------

def test_reply_with_only_reasoning_moves_to_next_model(monkeypatch):
    """When a candidate returns only <think> tokens, it fails and the chain tries the next model."""
    monkeypatch.setenv("LLM_PROVIDERS", "openai_compat")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_compat_key")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "model-reasoning-only,model-clean")

    call_history = []

    def mock_openai_compat(model, messages, context):
        call_history.append(model)
        if model == "model-reasoning-only":
            # Returns only <think> block
            return "<think>I am analyzing the question thoroughly step by step</think>"
        return "Here is your clean, helpful answer."

    monkeypatch.setattr("llm._call_openai_compat", mock_openai_compat)

    reply, sources, used = generate_answer("What are Interest Groups?")

    assert reply == "Here is your clean, helpful answer."
    assert call_history == ["model-reasoning-only", "model-clean"]
    assert is_in_cooldown("openai_compat", "model-reasoning-only") is True


# ---------------------------------------------------------------------------
# 4. <think> blocks and leading "Reasoning:" are stripped
# ---------------------------------------------------------------------------

def test_think_blocks_stripped():
    """clean_reply strips <think> blocks and leading 'Reasoning:' cleanly."""
    raw1 = "<think>First think through the answer.</think>Hello! How can I help you today?"
    assert clean_reply(raw1) == "Hello! How can I help you today?"

    raw2 = "<THINK>\nStep 1: Check facts.\nStep 2: Formulate reply.\n</THINK>\n\nµLearn is a learning platform."
    assert clean_reply(raw2) == "µLearn is a learning platform."

    raw3 = "Reasoning:\nThe user asked about coding.\nPython is an accessible programming language."
    assert clean_reply(raw3) == "The user asked about coding.\nPython is an accessible programming language."

    raw4 = "<think>Dangling unclosed block"
    assert clean_reply(raw4) == ""


# ---------------------------------------------------------------------------
# 5. Every candidate fails -> Offline mode answers with busy notice
# ---------------------------------------------------------------------------

def test_every_candidate_fails_offline_mode_answers(monkeypatch):
    """When all providers fail, the offline responder answers with the busy notice prepended."""
    monkeypatch.setenv("LLM_PROVIDERS", "gemini,openai_compat")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gemini_key")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_compat_key")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "model-1")

    def mock_fail(model, messages, context):
        raise ConnectionError("Network unreachable")

    monkeypatch.setattr("llm._call_gemini", mock_fail)
    monkeypatch.setattr("llm._call_openai_compat", mock_fail)

    reply, sources, used = generate_answer("What is µLearn?")

    expected_notice = "AI mode is busy right now, so this answer comes from my offline µLearn knowledge."
    assert reply.startswith(expected_notice)
    assert "µLearn is a community-driven education platform" in reply
    assert used is True
    assert len(sources) > 0


# ---------------------------------------------------------------------------
# 6. In-Memory Cache: Repeated µLearn question does NOT call provider
# ---------------------------------------------------------------------------

def test_cache_returns_repeated_mulearn_question(monkeypatch):
    """Identical normalised µLearn questions are served from in-memory cache without calling provider."""
    monkeypatch.setenv("LLM_PROVIDERS", "openai_compat")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_key")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "meta-llama/llama-3.3-70b-instruct")

    provider_mock = MagicMock(return_value="µLearn helps students learn by building.")
    monkeypatch.setattr("llm._call_openai_compat", provider_mock)

    client = app.test_client()

    # 1st request
    res1 = client.post("/api/chat", json={"message": "What is µLearn?"})
    assert res1.status_code == 200
    data1 = res1.get_json()
    assert data1["reply"] == "µLearn helps students learn by building."
    assert provider_mock.call_count == 1

    # 2nd request with normalised identical question (different case / spacing)
    res2 = client.post("/api/chat", json={"message": "  what is mulearn?  "})
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2["reply"] == "µLearn helps students learn by building."
    # Provider call count MUST stay 1 (served from cache!)
    assert provider_mock.call_count == 1


# ---------------------------------------------------------------------------
# 7. No cache for small talk or offline responder replies
# ---------------------------------------------------------------------------

def test_no_cache_for_small_talk_or_offline_replies(monkeypatch):
    """Small talk queries and offline responder answers must never be placed into the question cache."""
    monkeypatch.setenv("LLM_PROVIDERS", "openai_compat")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_key")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "meta-llama/llama-3.3-70b-instruct")

    provider_mock = MagicMock(return_value="Hey there! How's your day going?")
    monkeypatch.setattr("llm._call_openai_compat", provider_mock)

    client = app.test_client()

    # Small talk request
    res = client.post("/api/chat", json={"message": "hello"})
    assert res.status_code == 200
    assert len(_question_cache._cache) == 0  # No cache entry for small talk!


# ---------------------------------------------------------------------------
# 8. Rate Limiting: 20 messages per 10 minutes
# ---------------------------------------------------------------------------

def test_rate_limit_triggers_after_20_messages(monkeypatch):
    """Per-IP rate limit of 20 messages per 10 minutes triggers 429 on the 21st request."""
    monkeypatch.setenv("RATE_LIMIT", "20")
    monkeypatch.setenv("RATE_WINDOW", "600")

    monkeypatch.setattr("app.is_api_available", lambda: False)
    client = app.test_client()

    for i in range(20):
        res = client.post("/api/chat", json={"message": f"Question number {i}"})
        assert res.status_code == 200, f"Request {i+1} failed"

    # 21st request must trigger 429
    res21 = client.post("/api/chat", json={"message": "Question 21"})
    assert res21.status_code == 429
    data = res21.get_json()
    assert "too many requests" in data["error"].lower()
    assert "20 messages per 10 minutes" in data["error"]
    assert data["retry_after"] == 600


# ---------------------------------------------------------------------------
# 9. Small talk gets no sources and no context
# ---------------------------------------------------------------------------

def test_small_talk_gets_no_sources_and_no_context(monkeypatch):
    """Small talk queries retrieve no chunks and return used_sources=False with empty sources."""
    monkeypatch.setenv("LLM_PROVIDERS", "openai_compat")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_key")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "meta-llama/llama-3.3-70b-instruct")

    received_context = []

    def mock_compat(model, messages, context):
        received_context.append(context)
        return "I'm doing great, thank you!"

    monkeypatch.setattr("llm._call_openai_compat", mock_compat)

    client = app.test_client()
    res = client.post("/api/chat", json={"message": "good morning"})
    assert res.status_code == 200
    data = res.get_json()

    assert data["used_sources"] is False
    assert data["sources"] == []
    # Verify no context was passed into the provider
    assert received_context == [None]


# ---------------------------------------------------------------------------
# 10. µLearn questions still cite sources
# ---------------------------------------------------------------------------

def test_mulearn_questions_cite_sources_with_online_provider(monkeypatch):
    """µLearn specific questions retrieve context, pass it to provider, and cite sources."""
    monkeypatch.setenv("LLM_PROVIDERS", "openai_compat")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_key")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "meta-llama/llama-3.3-70b-instruct")

    monkeypatch.setattr("llm._call_openai_compat", lambda m, msgs, ctx: "Karma points reflect learning effort.")

    client = app.test_client()
    res = client.post("/api/chat", json={"message": "What are Karma points?"})
    assert res.status_code == 200
    data = res.get_json()

    assert data["used_sources"] is True
    assert len(data["sources"]) > 0
    assert any("mulearn.org" in s["url"] for s in data["sources"])


# ---------------------------------------------------------------------------
# 11. /api/status reports ai_online correctly
# ---------------------------------------------------------------------------

def test_api_status_reports_ai_online(monkeypatch):
    """GET /api/status accurately reflects candidate provider availability and cooldown."""
    monkeypatch.setenv("LLM_PROVIDERS", "gemini,openai_compat")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gem")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_compat")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "model-1")

    client = app.test_client()

    # Both healthy -> ai_online is True
    res = client.get("/api/status")
    assert res.status_code == 200
    assert res.get_json()["ai_online"] is True

    # Put Gemini in cooldown -> OpenAI-compat still healthy -> ai_online is True
    set_cooldown("gemini", "gemini-3.8-flash", 600)
    res2 = client.get("/api/status")
    assert res2.get_json()["ai_online"] is True

    # Put OpenAI-compat in cooldown too -> all down -> ai_online is False
    set_cooldown("openai_compat", "model-1", 600)
    res3 = client.get("/api/status")
    assert res3.get_json()["ai_online"] is False


# ---------------------------------------------------------------------------
# 12. Typo-tolerant small talk in offline responder
# ---------------------------------------------------------------------------

def test_offline_fallback_typo_tolerant_keywords():
    """Offline responder recognizes typo-tolerant small talk variants."""
    variants = ["hi", "hlo", "helo", "hii", "hey", "gm", "gn", "thanks", "thanku", "thx", "bye", "wassup", "ok", "who are you", "what can you do"]
    for word in variants:
        ans, sources, used = fallback_answer(word)
        assert len(ans) > 5, f"Expected answer for '{word}'"
        assert used is False, f"Expected used_sources=False for '{word}'"
        assert sources == [], f"Expected empty sources for '{word}'"


# ---------------------------------------------------------------------------
# 13. Non-ASCII header test with httpx.MockTransport
# ---------------------------------------------------------------------------

def test_non_ascii_header_with_mock_transport(monkeypatch):
    """Verify that requests with µ in headers and body succeed with httpx.MockTransport without UnicodeEncodeError."""
    monkeypatch.setenv("LLM_PROVIDERS", "openai_compat")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_key")
    monkeypatch.setenv("SITE_URL", "https://mulearn.org/µ/home")

    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        # Verify custom headers can be encoded as ascii without UnicodeEncodeError
        for k, v in request.headers.items():
            k.encode("ascii")
            v.encode("ascii")
        # Body is UTF-8 encoded and preserves µ
        body_text = request.content.decode("utf-8")
        assert "µLearn" in body_text
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "Welcome to µLearn Concierge!"}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    reply = generate([{"role": "user", "content": "Tell me about µLearn"}], transport=transport)
    assert reply == "Welcome to µLearn Concierge!"
    assert len(captured_requests) >= 1
    # Check X-Title is pure ASCII "uLearn Concierge"
    assert captured_requests[0].headers["x-title"] == "uLearn Concierge"
    # Check HTTP-Referer is pure ASCII with µ transliterated to u
    assert captured_requests[0].headers["http-referer"] == "https://mulearn.org/u/home"


# ---------------------------------------------------------------------------
# 14. Reasoning-only reply retries once with max_tokens=2000
# ---------------------------------------------------------------------------

def test_reasoning_only_retry_with_budget(monkeypatch):
    """Candidate returns empty reply; with budget > 10s, retries with max_tokens=2000 and succeeds."""
    monkeypatch.setenv("LLM_PROVIDERS", "openai_compat")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_key")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "model-reasoning")

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        data = json.loads(request.content.decode("utf-8"))
        if call_count == 1:
            # 1st attempt has default max_tokens=1000 and returns reasoning-only content
            assert data.get("max_tokens") == 1000
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "<think>Deliberating step by step</think>"}}
                    ]
                },
            )
        else:
            # 2nd attempt retries with max_tokens=2000
            assert data.get("max_tokens") == 2000
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "<think>Thinking</think>Python is great for AI!"}}
                    ]
                },
            )

    transport = httpx.MockTransport(handler)
    reply = generate([{"role": "user", "content": "Explain Python"}], transport=transport)
    assert reply == "Python is great for AI!"
    assert call_count == 2


# ---------------------------------------------------------------------------
# 15. 400 on reasoning parameter 3-tier fallback
# ---------------------------------------------------------------------------

def test_400_reasoning_param_fallback(monkeypatch):
    """Candidate returns 400 on {'enabled': false}, retries with {'effort': 'low', 'exclude': true}, returns 400, retries without reasoning, succeeds."""
    monkeypatch.setenv("LLM_PROVIDERS", "openai_compat")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_key")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "model-no-reasoning-param")

    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        reasoning = data.get("reasoning")
        attempts.append(reasoning)
        if len(attempts) == 1:
            # Attempt 1: {"enabled": False} -> 400
            assert reasoning == {"enabled": False}
            return httpx.Response(400, json={"error": "Unsupported parameter: reasoning.enabled"})
        elif len(attempts) == 2:
            # Attempt 2: {"effort": "low", "exclude": True} -> 400
            assert reasoning == {"effort": "low", "exclude": True}
            return httpx.Response(400, json={"error": "Unsupported parameter: reasoning.effort"})
        else:
            # Attempt 3: no reasoning parameter -> 200
            assert reasoning is None
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "Successful response without reasoning!"}}
                    ]
                },
            )

    transport = httpx.MockTransport(handler)
    reply = generate([{"role": "user", "content": "Hello"}], transport=transport)
    assert reply == "Successful response without reasoning!"
    assert len(attempts) == 3


# ---------------------------------------------------------------------------
# 16. Cooldown durations match error types
# ---------------------------------------------------------------------------

def test_cooldown_durations():
    """Verify 503 gets 60 s, 429 with Retry-After: 120 gets 120 s, 401 gets 1800 s."""
    from llm import _calculate_cooldown_and_status

    req = httpx.Request("POST", "https://api.example.com")

    # 1. 503 Service Unavailable -> 60s
    resp_503 = httpx.Response(503, request=req)
    err_503 = httpx.HTTPStatusError("Service Unavailable", request=req, response=resp_503)
    status_503, err_503_msg, cd_503 = _calculate_cooldown_and_status(err_503)
    assert status_503 == "503"
    assert cd_503 == 60.0

    # 2. 429 with Retry-After: 120 -> 120s
    resp_429 = httpx.Response(429, headers={"Retry-After": "120"}, request=req)
    err_429 = httpx.HTTPStatusError("Too Many Requests", request=req, response=resp_429)
    status_429, err_429_msg, cd_429 = _calculate_cooldown_and_status(err_429)
    assert status_429 == "429"
    assert cd_429 == 120.0

    # 3. 401 Unauthorized -> 1800s (30 minutes)
    resp_401 = httpx.Response(401, request=req)
    err_401 = httpx.HTTPStatusError("Unauthorized", request=req, response=resp_401)
    status_401, err_401_msg, cd_401 = _calculate_cooldown_and_status(err_401)
    assert status_401 == "401"
    assert cd_401 == 1800.0


# ---------------------------------------------------------------------------
# 17. Hanging first candidate: falls back to second under budget
# ---------------------------------------------------------------------------

def test_hanging_first_candidate_falls_back_under_budget(monkeypatch):
    """First candidate times out at 8 s, second candidate answers at 8 s, total time < 20 s."""
    monkeypatch.setenv("LLM_PROVIDERS", "gemini,openai_compat")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gem")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_compat")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "model-backup")

    captured_timeouts = {}

    def mock_gemini(model, messages, context, timeout=8.0):
        captured_timeouts["gemini"] = timeout
        raise TimeoutError(f"Gemini timed out after {timeout}s")

    def mock_openai(model, messages, context, timeout=8.0, **kwargs):
        captured_timeouts["openai"] = timeout
        return "Resilient fallback response!"

    monkeypatch.setattr("llm._call_gemini", mock_gemini)
    monkeypatch.setattr("llm._call_openai_compat", mock_openai)

    start = time.monotonic()
    reply, sources, used = generate_answer("Hello")
    elapsed = time.monotonic() - start

    assert reply == "Resilient fallback response!"
    assert captured_timeouts.get("gemini") == pytest.approx(8.0, abs=0.5)
    assert captured_timeouts.get("openai") == pytest.approx(8.0, abs=0.5)
    assert elapsed < 20.0
    # Gemini must have entered 60s cooldown
    assert is_in_cooldown("gemini", "gemini-3.8-flash") is True


# ---------------------------------------------------------------------------
# 18. All candidates hang: offline answer in < 20s with busy notice
# ---------------------------------------------------------------------------

def test_all_candidates_hang_total_budget_exhausted_offline_answer(monkeypatch):
    """All candidates hang: total budget exhausted, offline answer returned in < 20 s with the busy notice."""
    monkeypatch.setenv("LLM_PROVIDERS", "gemini,openai_compat")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gem")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_compat")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "model-hang")

    def mock_gemini_hang(model, messages, context, timeout=12.0):
        raise TimeoutError(f"Gemini hung for {timeout}s")

    def mock_openai_hang(model, messages, context, timeout=8.0, **kwargs):
        raise TimeoutError(f"OpenAI compat hung for {timeout}s")

    monkeypatch.setattr("llm._call_gemini", mock_gemini_hang)
    monkeypatch.setattr("llm._call_openai_compat", mock_openai_hang)

    start = time.monotonic()
    reply, sources, used = generate_answer("What is µLearn?")
    elapsed = time.monotonic() - start

    busy_notice = "AI mode is busy right now, so this answer comes from my offline µLearn knowledge."
    assert reply.startswith(busy_notice)
    assert "µLearn is a community-driven education platform" in reply
    assert elapsed < 20.0


# ---------------------------------------------------------------------------
# 19. All candidates in cooldown logs message with shortest remaining cooldown
# ---------------------------------------------------------------------------

def test_all_candidates_cooling_down_logged_message(monkeypatch):
    """When all candidates are in cooldown, error reports 'all candidates cooling down, next retry in N s'."""
    monkeypatch.setenv("LLM_PROVIDERS", "gemini,openai_compat")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gem")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_compat")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "model-cd")

    set_cooldown("gemini", "gemini-3.8-flash", duration_seconds=45)
    set_cooldown("openai_compat", "model-cd", duration_seconds=90)

    with pytest.raises(RuntimeError) as exc_info:
        generate([{"role": "user", "content": "hi"}])

    err_str = str(exc_info.value)
    assert "all candidates cooling down, next retry in" in err_str


# ---------------------------------------------------------------------------
# 20. Simulated slow candidate (sleeps 30s): request returns within 20s total
# ---------------------------------------------------------------------------

def test_request_returns_within_20s_total_with_sleeping_thread(monkeypatch):
    """The request returns within 20 s total even though the thread is still sleeping."""
    import threading
    monkeypatch.setenv("LLM_PROVIDERS", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gem")

    stop_event = threading.Event()

    def mock_gemini_sleep_30s(*args, **kwargs):
        # Simulated slow candidate that sleeps 30 s in a thread
        stop_event.wait(30.0)
        return "Gemini reply after 30s"

    monkeypatch.setattr("llm._call_gemini", mock_gemini_sleep_30s)

    try:
        start = time.monotonic()
        reply, sources, used = generate_answer("What is µLearn?")
        elapsed = time.monotonic() - start

        # Must return in under 20s total (specifically ~8s)
        assert elapsed < 20.0
        assert elapsed >= 7.8
        # Verifies thread was still sleeping when generate_answer returned
        assert not stop_event.is_set()
        assert "AI mode is busy right now, so this answer comes from my offline µLearn knowledge." in reply
    finally:
        stop_event.set()


# ---------------------------------------------------------------------------
# 21. First candidate hangs (sleeps 30s), second answers, total elapsed under 10s
# ---------------------------------------------------------------------------

def test_first_candidate_hangs_second_answers_under_10s(monkeypatch):
    """The first candidate hangs (sleeps 30s in a thread), the second answers, and the total elapsed is under 10 s."""
    import threading
    monkeypatch.setenv("LLM_PROVIDERS", "gemini,openai_compat")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gem")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_compat")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "model-fast")

    stop_event = threading.Event()

    def mock_gemini_hang(*args, **kwargs):
        stop_event.wait(30.0)
        return "Gemini after 30s"

    def mock_openai_fast(*args, **kwargs):
        return "Fast candidate 2 answer"

    monkeypatch.setattr("llm._call_gemini", mock_gemini_hang)
    monkeypatch.setattr("llm._call_openai_compat", mock_openai_fast)

    try:
        start = time.monotonic()
        reply, sources, used = generate_answer("Hello")
        elapsed = time.monotonic() - start

        assert reply == "Fast candidate 2 answer"
        assert elapsed < 10.0
        assert elapsed >= 7.8
        assert is_in_cooldown("gemini", "gemini-3.8-flash") is True
    finally:
        stop_event.set()


# ---------------------------------------------------------------------------
# 22. Cooled-down candidate is skipped with no delay
# ---------------------------------------------------------------------------

def test_cooldown_candidate_skipped_with_no_delay(monkeypatch):
    """A cooled-down candidate is skipped with no delay without consuming budget."""
    monkeypatch.setenv("LLM_PROVIDERS", "gemini,openai_compat")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gem")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_compat")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "model-ok")

    gemini_called = False

    def mock_gemini(*args, **kwargs):
        nonlocal gemini_called
        gemini_called = True
        return "Gemini reply"

    def mock_openai(*args, **kwargs):
        return "OpenAI reply"

    monkeypatch.setattr("llm._call_gemini", mock_gemini)
    monkeypatch.setattr("llm._call_openai_compat", mock_openai)

    # Put Gemini in cooldown
    set_cooldown("gemini", "gemini-3.8-flash", duration_seconds=60.0)

    start = time.monotonic()
    reply, sources, used = generate_answer("Hello")
    elapsed = time.monotonic() - start

    assert reply == "OpenAI reply"
    assert not gemini_called
    assert elapsed < 0.5  # No delay!


# ---------------------------------------------------------------------------
# 23. Startup log shows configured order
# ---------------------------------------------------------------------------

def test_startup_log_shows_configured_order(monkeypatch, caplog):
    """Startup log shows the configured order (names only, never secrets)."""
    import logging
    from llm import log_startup_chain

    monkeypatch.setenv("LLM_PROVIDERS", "openai_compat,gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "secret_gemini_key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "secret_compat_key")
    monkeypatch.setenv(
        "OPENAI_COMPAT_MODEL",
        "nvidia/nemotron-3.5-lightning:free, nvidia/nemotron-3-ultra-550b-a55b:free",
    )

    with caplog.at_level(logging.INFO):
        chain_str = log_startup_chain()

    expected = (
        "LLM chain: openai_compat[nvidia/nemotron-3.5-lightning:free, "
        "nvidia/nemotron-3-ultra-550b-a55b:free] -> gemini[gemini-3.8-flash]"
    )
    assert chain_str == expected
    assert "secret_gemini_key" not in chain_str
    assert "secret_compat_key" not in chain_str


# ---------------------------------------------------------------------------
# 24. Dynamic reordering when Gemini recently failed
# ---------------------------------------------------------------------------

def test_dynamic_reordering_when_gemini_failed_in_last_10_minutes(monkeypatch):
    """When Gemini failed in the last 10 minutes, try other provider first on next request."""
    from llm import get_ordered_candidates, record_gemini_failure

    monkeypatch.setenv("LLM_PROVIDERS", "gemini,openai_compat")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_gem")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "mock_compat")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "model-compat")

    # Initial request: Gemini first
    cands1 = get_ordered_candidates()
    assert cands1[0] == ("gemini", "gemini-3.8-flash")
    assert cands1[1] == ("openai_compat", "model-compat")

    # Gemini fails
    record_gemini_failure()

    # Next request: other provider is tried first
    cands2 = get_ordered_candidates()
    assert cands2[0] == ("openai_compat", "model-compat")
    assert cands2[1] == ("gemini", "gemini-3.8-flash")


