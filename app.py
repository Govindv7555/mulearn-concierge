"""
µLearn Concierge — Flask Application
Main entry point for the chatbot web app.
"""

import os
import time
import html
from collections import defaultdict
from datetime import datetime

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load .env BEFORE importing our modules (they read env vars)
load_dotenv()

from rag import retrieve, get_store
from llm import generate_answer, is_api_available, is_ai_online, log_startup_chain
from fallback import fallback_answer, _normalize

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# ---------------------------------------------------------------------------
# In-memory question cache (1 hour TTL, max 200 entries)
# ---------------------------------------------------------------------------

class QuestionCache:
    """In-memory cache for identical normalised µLearn questions.

    Caches only grounded µLearn Q&A with retrieved sources.
    Never caches small talk or responses produced by the offline responder.
    """

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 200):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._cache = {}  # norm_key -> {"reply": ..., "sources": ..., "used_sources": ..., "ts": ...}

    def get(self, query: str):
        norm = _normalize(query)
        if norm in self._cache:
            entry = self._cache[norm]
            if time.time() - entry["ts"] < self.ttl:
                return {
                    "reply": entry["reply"],
                    "sources": entry["sources"],
                    "used_sources": entry["used_sources"],
                }
            else:
                del self._cache[norm]
        return None

    def set(self, query: str, reply: str, sources: list, used_sources: bool):
        norm = _normalize(query)
        if len(self._cache) >= self.max_size and norm not in self._cache:
            # Evict oldest
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["ts"])
            del self._cache[oldest_key]
        self._cache[norm] = {
            "reply": reply,
            "sources": sources,
            "used_sources": used_sources,
            "ts": time.time(),
        }

    def clear(self):
        self._cache.clear()


_question_cache = QuestionCache(ttl_seconds=3600, max_size=200)

# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per-IP: 20 messages per 10 minutes)
# ---------------------------------------------------------------------------

DEFAULT_RATE_LIMIT = 20  # requests per window
DEFAULT_RATE_WINDOW = 600  # 10 minutes in seconds

_rate_store = defaultdict(list)  # IP -> [timestamp, ...]


def _get_rate_limit():
    env_val = os.getenv("RATE_LIMIT")
    if env_val:
        return int(env_val)
    if app.config.get("TESTING") and not app.config.get("TEST_RATE_LIMIT_20"):
        return 10
    return DEFAULT_RATE_LIMIT


def _get_rate_window():
    env_val = os.getenv("RATE_WINDOW")
    if env_val:
        return int(env_val)
    if app.config.get("TESTING") and not app.config.get("TEST_RATE_LIMIT_20"):
        return 60
    return DEFAULT_RATE_WINDOW


def _is_rate_limited(ip):
    """Check if an IP has exceeded the rate limit."""
    now = time.time()
    limit = _get_rate_limit()
    window = _get_rate_window()
    window_start = now - window
    # Prune old entries
    _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]
    if len(_rate_store[ip]) >= limit:
        return True
    _rate_store[ip].append(now)
    return False


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

MAX_MESSAGE_LENGTH = 1000


def _validate_message(data):
    """Validate the incoming chat message. Returns (message, error_response)."""
    if not data or not isinstance(data, dict):
        return None, (jsonify({"error": "Invalid request body. Send JSON with a 'message' field."}), 400)

    message = data.get("message", "")
    if not isinstance(message, str):
        return None, (jsonify({"error": "Message must be a string."}), 400)

    message = message.strip()
    if not message:
        return None, (jsonify({"error": "Message cannot be empty."}), 400)

    if len(message) > MAX_MESSAGE_LENGTH:
        return None, (jsonify({
            "error": f"Message too long. Maximum {MAX_MESSAGE_LENGTH} characters.",
            "max_length": MAX_MESSAGE_LENGTH,
        }), 400)

    # Basic gibberish check — message should have at least one letter
    if not any(c.isalpha() for c in message):
        return None, (jsonify({"error": "Please type a readable question."}), 400)

    return message, None


def _validate_history(data):
    """Validate and sanitize conversation history."""
    history = data.get("history", [])
    if not isinstance(history, list):
        return []
    clean = []
    for turn in history[-6:]:  # Cap at 6 turns
        if isinstance(turn, dict) and "role" in turn and "content" in turn:
            role = turn["role"]
            content = str(turn["content"])[:MAX_MESSAGE_LENGTH]
            if role in ("user", "assistant"):
                clean.append({"role": role, "content": content})
    return clean


# ---------------------------------------------------------------------------
# Helper: get news sync timestamp
# ---------------------------------------------------------------------------

def _get_sync_timestamp():
    """Get the last-modified time of discord_news.md."""
    path = os.path.join("knowledge", "discord_news.md")
    try:
        mtime = os.path.getmtime(path)
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main chat interface."""
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    store = get_store()
    return jsonify({
        "status": "ok",
        "api_available": is_api_available(),
        "knowledge_chunks": len(store.chunks),
    })


@app.route("/api/status", methods=["GET"])
def status():
    """Status endpoint with sync timestamp, knowledge info, and AI provider status."""
    store = get_store()
    return jsonify({
        "news_last_synced": _get_sync_timestamp(),
        "knowledge_sources": store.get_all_sources(),
        "api_mode": "gemini" if is_api_available() else "fallback",
        "ai_online": is_ai_online(),
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    """Main chat endpoint. Accepts JSON: {"message": "...", "history": [...]}."""
    # Rate limiting
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if _is_rate_limited(client_ip):
        return jsonify({
            "error": "Too many requests. You've reached the message limit (20 messages per 10 minutes). Please wait a moment and try again.",
            "retry_after": _get_rate_window(),
        }), 429

    # Validate input
    data = request.get_json(silent=True)
    message, error = _validate_message(data)
    if error:
        return error

    history = _validate_history(data)

    # Retrieve relevant knowledge (returns chunks only if score >= min_score threshold)
    chunks = retrieve(message, top_k=5)

    # Check cache for identical normalised µLearn questions (only when grounded context exists)
    if chunks:
        cached = _question_cache.get(message)
        if cached:
            return jsonify(cached)

    # Generate answer via multi-provider chain (Gemini -> OpenAI-compatible -> Offline Fallback)
    try:
        if not is_api_available():
            raise ValueError("No API key configured")
        reply, sources, used_sources = generate_answer(message, chunks, history)
    except Exception as e:
        app.logger.warning(f"LLM generation failed, using fallback: {e}")
        offline_text, sources, used_sources = fallback_answer(message, chunks)
        if is_api_available():
            reply = "AI mode is busy right now, so this answer comes from my offline µLearn knowledge.\n\n" + offline_text
        else:
            reply = offline_text

    # Cache only grounded µLearn Q&A that came from an online provider (never small talk or offline fallback)
    is_offline = "AI mode is busy right now" in reply or not is_api_available()
    if used_sources and not is_offline:
        _question_cache.set(message, reply, sources, used_sources)

    return jsonify({
        "reply": reply,
        "sources": sources,
        "used_sources": used_sources,
    })


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error. Please try again."}), 500


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print(f"\n  µLearn Concierge running at http://localhost:{port}\n")
    print(f"  API mode: {'Gemini (' + os.getenv('GEMINI_MODEL', 'gemini-2.0-flash') + ')' if is_api_available() else 'Fallback (keyword/FAQ)'}")
    print(f"  Knowledge chunks loaded: {len(get_store().chunks)}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
