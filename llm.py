"""
µLearn Concierge — LLM Provider Layer & Automatic Fallback Chain
Common interface generate(messages, context) supporting:
1. Google Gemini via google-genai SDK
2. Generic OpenAI-compatible providers (e.g. OpenRouter) via HTTP POST

Features:
- Resilient fallback chain ordered by LLM_PROVIDERS with dynamic reordering when Gemini recently failed.
- Hard timeouts for every candidate using module-level ThreadPoolExecutor with abandoned futures.
- 20-second end-to-end hard time budget, 8s per-call timeout, skipping candidates when < 2s remain.
- Gemini SDK timeout (HttpOptions in ms) with internal retries disabled (attempts=1).
- OpenAI-compatible timeout (httpx.Timeout(connect=4, read=timeout, write=5, pool=5)) with retries=0.
- Cooldown durations: timeouts and 5xx (60s), 429 (Retry-After, cap 15m), 401/403 (30m).
- Real elapsed time logged for every failed call: provider=... model=... status=... elapsed=...ms error=<class>: <msg>.
- Pure ASCII custom headers (transliterating µ to u) preventing UnicodeEncodeError.
- Reasoning model handling: default max_tokens=1000, 3-tier reasoning param fallback on 400, retry once at max_tokens=2000 if budget > 10s.
- Strict reasoning block (<think>...</think>, "Reasoning:") stripping.
- Startup log displaying resolved candidate order (names only, never secrets).
"""

import os
import re
import time
import inspect
import logging
import concurrent.futures
from typing import List, Dict, Tuple, Optional, Any, Callable

import httpx
from dotenv import load_dotenv

# Ensure environment is loaded
load_dotenv()

from fallback import fallback_answer

logger = logging.getLogger("mulearn.llm")

# ---------------------------------------------------------------------------
# System Prompt (Unified across all providers)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are µLearn Concierge, an intelligent, warm, and conversational assistant.

PERSONA & ROLE:
1. You are a friendly, natural conversational assistant first, and a µLearn specialist second.
2. For greetings ("hi", "hello", "hey"), thanks, small talk, jokes, "who are you", general knowledge, study help, and coding help (e.g. Python, web development, algorithms):
   - Answer normally, warmly, and helpfully in a concise, natural way.
   - Do NOT refuse or redirect off-topic questions. Answer them directly and warmly.
   - Do NOT attach µLearn sources or citations to off-topic or general knowledge questions.
   - You may gently mention µLearn only where it genuinely fits (e.g. "If you enjoy coding in Python, you might also like the µLearn Web or AI Interest Groups!"), but never force it.
3. For questions about the µLearn platform (what it is, Interest Groups, Karma points, µID, Learning Circles, campus chapters, College of Engineering Chengannur / CHN, events, or news):
   - Answer ONLY from the retrieved context provided with the question.
   - Cite the source clearly.
   - NEVER invent or assume facts, events, dates, point values, links, or names.
   - If the context does not contain enough information to answer a µLearn question, honestly say: "I'm not certain about that. Please check mulearn.org or the µLearn Discord for the latest information."
   - When sharing news or announcements from Discord, always mention that it comes from the central µLearn announcements feed (GTech µLearn), not CHN specifically.
4. Keep all responses concise, friendly, and easy to read. Remember the last few turns of conversation for natural context."""

# ---------------------------------------------------------------------------
# Configuration Defaults & Budget Limits
# ---------------------------------------------------------------------------

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_OPENAI_COMPAT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENAI_COMPAT_MODEL = "meta-llama/llama-3.3-70b-instruct"

TOTAL_TIME_BUDGET_SECONDS = 20.0
PER_CALL_TIMEOUT_SECONDS = 8.0
MIN_BUDGET_TO_ATTEMPT_SECONDS = 2.0

DEFAULT_429_COOLDOWN = 600.0   # 10 minutes
MAX_429_COOLDOWN = 900.0       # 15 minutes cap
SHORT_COOLDOWN = 60.0          # 60s for timeouts, 5xx, connection, reasoning-only
AUTH_COOLDOWN = 1800.0         # 30 minutes for 401/403

GEMINI_FAILURE_COOLOFF_SECONDS = 600.0  # 10 minutes

# Module-level ThreadPoolExecutor (max_workers=8) for hard asynchronous candidate timeouts
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm_candidate")

# Global test transport hook (allows tests to mock httpx transport cleanly)
_custom_transport: Optional[httpx.BaseTransport] = None


def set_test_transport(transport: Optional[httpx.BaseTransport]) -> None:
    """Set global httpx transport for testing (MockTransport)."""
    global _custom_transport
    _custom_transport = transport


# ---------------------------------------------------------------------------
# In-Memory Cooldown & Failure Tracking State (per-process)
# ---------------------------------------------------------------------------

# Key: (provider_name, model_slug) -> cooldown_expiration_timestamp (float)
_cooldown_store: Dict[Tuple[str, str], float] = {}

# Timestamp of last Gemini failure or cooldown
_gemini_last_failure_time: float = 0.0


def is_in_cooldown(provider: str, model: str) -> bool:
    """Check if a candidate provider and model is currently in cooldown."""
    expiry = _cooldown_store.get((provider, model), 0.0)
    return time.time() < expiry


def set_cooldown(provider: str, model: str, duration_seconds: float = SHORT_COOLDOWN) -> None:
    """Put a candidate provider and model in cooldown for a specified duration."""
    retry_secs = max(5.0, float(duration_seconds))
    _cooldown_store[(provider, model)] = time.time() + retry_secs
    if provider == "gemini":
        record_gemini_failure()


def record_gemini_failure() -> None:
    """Record that Gemini has failed or was cooled down."""
    global _gemini_last_failure_time
    _gemini_last_failure_time = time.time()


def clear_cooldowns() -> None:
    """Clear all in-memory cooldowns and failure history (useful for tests)."""
    global _gemini_last_failure_time
    _cooldown_store.clear()
    _gemini_last_failure_time = 0.0


def get_cooldown_expiry(provider: str, model: str) -> Optional[float]:
    """Get cooldown expiration timestamp if active, else None."""
    expiry = _cooldown_store.get((provider, model), 0.0)
    return expiry if time.time() < expiry else None


# ---------------------------------------------------------------------------
# ASCII Header Sanitizer
# ---------------------------------------------------------------------------

def to_ascii_header(val: Optional[str]) -> str:
    """Guarantee custom header values are strictly ASCII.

    Transliterates 'µ' and 'μ' to 'u', and drops any other non-ASCII characters.
    Prevents UnicodeEncodeError when httpx or http.client processes headers.
    """
    if not val:
        return ""
    transliterated = val.replace("µ", "u").replace("\u03bc", "u")
    return transliterated.encode("ascii", "ignore").decode("ascii").strip()


# ---------------------------------------------------------------------------
# Candidate Resolution & Dynamic Reordering
# ---------------------------------------------------------------------------

def get_configured_candidates() -> List[Tuple[str, str]]:
    """Resolve ordered candidate list [(provider, model), ...] based on LLM_PROVIDERS.

    For openai_compat, splits OPENAI_COMPAT_MODEL on commas into individual candidates.
    """
    providers_str = os.getenv("LLM_PROVIDERS", "gemini,openai_compat")
    provider_names = [p.strip().lower() for p in providers_str.split(",") if p.strip()]

    candidates = []
    for p_name in provider_names:
        if p_name == "gemini":
            if os.getenv("GEMINI_API_KEY"):
                model = os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL
                candidates.append(("gemini", model))
        elif p_name in ("openai_compat", "openrouter", "openai"):
            if os.getenv("OPENAI_COMPAT_API_KEY"):
                model_str = os.getenv("OPENAI_COMPAT_MODEL", "").strip() or DEFAULT_OPENAI_COMPAT_MODEL
                models = [m.strip() for m in model_str.split(",") if m.strip()]
                for m in models:
                    candidates.append(("openai_compat", m))

    return candidates


def get_ordered_candidates() -> List[Tuple[str, str]]:
    """Return candidates in execution order.

    Rule: If the configured chain would try Gemini first, but Gemini failed or was
    cooled down in the last 10 minutes, try the other provider first on this request.
    """
    candidates = get_configured_candidates()
    if not candidates:
        return []

    # Check if first candidate is Gemini
    if candidates[0][0] == "gemini":
        gemini_model = candidates[0][1]
        now = time.time()
        gemini_cooled = is_in_cooldown("gemini", gemini_model)
        gemini_recent_failure = (now - _gemini_last_failure_time < GEMINI_FAILURE_COOLOFF_SECONDS)

        if gemini_cooled or gemini_recent_failure:
            # Shift other providers ahead of Gemini
            non_gemini = [c for c in candidates if c[0] != "gemini"]
            gemini_cands = [c for c in candidates if c[0] == "gemini"]
            return non_gemini + gemini_cands

    return candidates


def format_candidate_chain(candidates: Optional[List[Tuple[str, str]]] = None) -> str:
    """Format candidate list into a human-readable startup string.

    Names and model slugs only, never keys or secrets.
    Example:
    'LLM chain: openai_compat[nvidia/nemotron-3.5-lightning:free, nvidia/nemotron-3-ultra-550b-a55b:free] -> gemini[gemini-3.8-flash]'
    """
    if candidates is None:
        candidates = get_configured_candidates()
    if not candidates:
        return "LLM chain: none (offline fallback only)"

    groups = []
    current_provider = None
    current_models = []
    for provider, model in candidates:
        if provider != current_provider:
            if current_provider is not None:
                groups.append(f"{current_provider}[{', '.join(current_models)}]")
            current_provider = provider
            current_models = [model]
        else:
            current_models.append(model)
    if current_provider is not None:
        groups.append(f"{current_provider}[{', '.join(current_models)}]")

    return "LLM chain: " + " -> ".join(groups)


def log_startup_chain() -> str:
    """Log and print the resolved candidate chain at startup."""
    chain_str = format_candidate_chain()
    logger.info(chain_str)
    print(chain_str)
    return chain_str


def is_api_available() -> bool:
    """Check if any LLM API provider credentials are configured in the environment."""
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_COMPAT_API_KEY"))


def is_ai_online() -> bool:
    """Return True if at least one configured provider candidate is not in cooldown."""
    candidates = get_configured_candidates()
    if not candidates:
        return False
    now = time.time()
    for provider, model in candidates:
        if now >= _cooldown_store.get((provider, model), 0.0):
            return True
    return False


# ---------------------------------------------------------------------------
# Reply Cleaning & Formatting
# ---------------------------------------------------------------------------

def clean_reply(text: str) -> str:
    """Strip <think>...</think> blocks and leading 'Reasoning:' text.

    Ensures the user never sees internal chain-of-thought tokens.
    """
    if not text:
        return ""

    # Strip complete <think>...</think> blocks (case-insensitive, multi-line)
    cleaned = re.sub(r'(?is)<\s*think\s*>.*?<\s*/\s*think\s*>', '', text)

    # Strip unclosed <think> if response was cut off
    cleaned = re.sub(r'(?is)<\s*think\s*>.*$', '', cleaned)

    # Strip leading "Reasoning:" or "Reasoning:\n"
    cleaned = re.sub(r'(?i)^\s*reasoning\s*:\s*', '', cleaned)

    return cleaned.strip()


def _build_context_block(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved knowledge chunks into a grounded context string."""
    if not chunks:
        return ""

    parts = []
    for i, chunk in enumerate(chunks, 1):
        source_label = (
            "µLearn Website"
            if chunk.get("source") == "website"
            else "µLearn Discord #announcements"
        )
        parts.append(f"[Context {i} — {source_label}]\n{chunk['text']}")

    return "\n\n---\n\n".join(parts)


def _extract_sources(chunks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Extract unique source label and URL dicts from retrieved chunks."""
    source_map = {
        "website": {"label": "µLearn Website", "url": "https://mulearn.org"},
        "discord": {
            "label": "µLearn Discord #announcements",
            "url": "https://discord.gg/5xdYHfjFt",
        },
    }
    seen = set()
    sources = []
    for chunk in chunks:
        s = chunk.get("source")
        if s and s not in seen:
            seen.add(s)
            if s in source_map:
                sources.append(source_map[s])
    return sources


# ---------------------------------------------------------------------------
# Cooldown & Status Computation Helper
# ---------------------------------------------------------------------------

def _calculate_cooldown_and_status(e: Exception) -> Tuple[str, str, float]:
    """Derive (status, short_error, cooldown_seconds) from an exception.

    Rules:
    - 429: use Retry-After header if present, capped at 15 min (900s), default 10 min (600s).
    - 5xx, timeouts, connection errors, empty/reasoning-only: 60s.
    - 401 / 403: 30 minutes (1800s).
    - Never exposes keys, passwords, or full traces.
    """
    err_cls = e.__class__.__name__
    err_msg = str(e).strip()
    if len(err_msg) > 100:
        err_msg = err_msg[:100] + "..."

    status = "error"
    cooldown = SHORT_COOLDOWN
    short_error = f"{err_cls}: {err_msg}" if err_msg else err_cls

    status_code: Optional[int] = None

    if isinstance(e, httpx.HTTPStatusError):
        status_code = e.response.status_code
        status = str(status_code)
        if status_code == 429:
            retry_header = e.response.headers.get("retry-after") or e.response.headers.get("Retry-After")
            if retry_header:
                try:
                    retry_val = float(retry_header)
                    cooldown = min(max(5.0, retry_val), MAX_429_COOLDOWN)
                except (ValueError, TypeError):
                    cooldown = DEFAULT_429_COOLDOWN
            else:
                cooldown = DEFAULT_429_COOLDOWN
        elif status_code in (401, 403):
            cooldown = AUTH_COOLDOWN
        else:
            # 5xx or other status codes
            cooldown = SHORT_COOLDOWN

    elif isinstance(e, (TimeoutError, httpx.TimeoutException, concurrent.futures.TimeoutError)):
        status = "timeout"
        cooldown = SHORT_COOLDOWN

    elif isinstance(e, (ConnectionError, httpx.RequestError)):
        status = "connection_error"
        cooldown = SHORT_COOLDOWN

    elif isinstance(e, ValueError):
        status = "empty_or_reasoning_only"
        cooldown = SHORT_COOLDOWN

    else:
        # Check code or status_code attributes (e.g. google-genai or custom SDK errors)
        code = getattr(e, "code", getattr(e, "status_code", None))
        if code is not None:
            try:
                status_code = int(code)
                status = str(status_code)
            except (ValueError, TypeError):
                status = str(code)

        if status_code is None:
            # Check for HTTP status embedded in message (e.g. 503, 429, 401)
            m = re.search(r'\b(429|503|500|502|504|401|403)\b', err_msg)
            if m:
                status_code = int(m.group(1))
                status = str(status_code)

        if status_code == 429:
            cooldown = DEFAULT_429_COOLDOWN
        elif status_code in (401, 403):
            cooldown = AUTH_COOLDOWN
        else:
            cooldown = SHORT_COOLDOWN

    return status, short_error, cooldown


# ---------------------------------------------------------------------------
# Dynamic Provider Invocation Wrapper
# ---------------------------------------------------------------------------

def _invoke_provider(fn: Callable, model: str, messages: List[Dict[str, str]], context: Optional[str], timeout: float, **extra_kwargs) -> str:
    """Call provider function passing timeout and extra kwargs only if its signature accepts them.

    Guarantees backward compatibility with mock provider functions taking only (model, messages, context).
    """
    sig = inspect.signature(fn)
    params = sig.parameters
    kwargs = {}
    has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

    if "timeout" in params or has_varkw:
        kwargs["timeout"] = timeout

    for k, v in extra_kwargs.items():
        if k in params or has_varkw:
            kwargs[k] = v

    return fn(model, messages, context, **kwargs)


# ---------------------------------------------------------------------------
# Provider Call Implementations
# ---------------------------------------------------------------------------

def _call_gemini(
    model_slug: str,
    messages: List[Dict[str, str]],
    context: Optional[str],
    timeout: float = PER_CALL_TIMEOUT_SECONDS,
) -> str:
    """Execute generation via google-genai SDK with SDK-level timeout and retries disabled."""
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    # Set SDK's own timeout (types.HttpOptions(timeout=<ms>)) and disable internal retries (attempts=1)
    http_opts = types.HttpOptions(
        timeout=int(timeout * 1000),
        retry_options=types.HttpRetryOptions(attempts=1),
    )
    client = genai.Client(api_key=api_key, http_options=http_opts)

    contents = []
    for i, turn in enumerate(messages):
        role = "user" if turn.get("role") == "user" else "model"
        text = turn.get("content", "")
        if i == len(messages) - 1 and role == "user" and context:
            text = f"RETRIEVED µLEARN CONTEXT:\n{context}\n\nUSER QUESTION:\n{text}"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=text)],
            )
        )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.6,
        max_output_tokens=1000,
    )

    # Call directly; the module-level ThreadPoolExecutor handles caller-level timeout
    response = client.models.generate_content(
        model=model_slug,
        contents=contents,
        config=config,
    )

    raw_text = response.text if (response and response.text) else ""
    cleaned = clean_reply(raw_text)
    if not cleaned:
        raise ValueError("Gemini returned empty or reasoning-only content")

    return cleaned


def _send_openai_compat_request(
    client: httpx.Client,
    endpoint: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout: Any = None,
) -> httpx.Response:
    """Send request to OpenAI-compatible endpoint with 3-tier reasoning param fallback on HTTP 400.

    1. Attempts {"enabled": False}.
    2. If 400, retries ONCE with {"effort": "low", "exclude": True}.
    3. If that also returns 400, retries ONCE without any reasoning parameter.
    """
    p1 = dict(payload)
    p1["reasoning"] = {"enabled": False}
    resp = client.post(endpoint, json=p1, headers=headers, timeout=timeout)
    if resp.status_code == 400:
        logger.info("ℹ️ [OpenAI Compat] 400 on reasoning={'enabled': False}, retrying with {'effort': 'low', 'exclude': True}")
        p2 = dict(payload)
        p2["reasoning"] = {"effort": "low", "exclude": True}
        resp = client.post(endpoint, json=p2, headers=headers, timeout=timeout)
        if resp.status_code == 400:
            logger.info("ℹ️ [OpenAI Compat] 400 on reasoning effort=low, retrying without reasoning parameter")
            p3 = dict(payload)
            p3.pop("reasoning", None)
            resp = client.post(endpoint, json=p3, headers=headers, timeout=timeout)
    return resp


def _call_openai_compat(
    model_slug: str,
    messages: List[Dict[str, str]],
    context: Optional[str],
    timeout: float = PER_CALL_TIMEOUT_SECONDS,
    remaining_budget_fn: Optional[Callable[[], float]] = None,
    transport: Optional[httpx.BaseTransport] = None,
) -> str:
    """Execute generation via generic OpenAI-compatible HTTP chat completions endpoint."""
    base_url = (os.getenv("OPENAI_COMPAT_BASE_URL", "").strip() or DEFAULT_OPENAI_COMPAT_BASE_URL).rstrip("/")
    api_key = os.getenv("OPENAI_COMPAT_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_COMPAT_API_KEY is not set")

    if base_url.endswith("/chat/completions"):
        endpoint = base_url
    else:
        endpoint = f"{base_url}/chat/completions"

    # Ensure all custom header values are strictly ASCII (µ -> u)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": to_ascii_header("uLearn Concierge"),
    }
    site_url = os.getenv("SITE_URL", "").strip()
    if site_url:
        headers["HTTP-Referer"] = to_ascii_header(site_url)

    # Format messages array including system prompt (JSON body is UTF-8)
    formatted_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for i, turn in enumerate(messages):
        role = turn.get("role", "user")
        if role == "model":
            role = "assistant"
        content = turn.get("content", "")
        if i == len(messages) - 1 and role == "user" and context:
            content = f"RETRIEVED µLEARN CONTEXT:\n{context}\n\nUSER QUESTION:\n{content}"
        formatted_messages.append({"role": role, "content": content})

    # Default max_tokens is raised to 1000
    payload = {
        "model": model_slug,
        "messages": formatted_messages,
        "temperature": 0.6,
        "max_tokens": 1000,
    }

    # httpx.Timeout(connect=4, read=timeout, write=5, pool=5) with no automatic retries
    timeout_config = httpx.Timeout(connect=4.0, read=timeout, write=5.0, pool=5.0)

    client_kwargs: Dict[str, Any] = {
        "timeout": timeout_config,
    }
    active_transport = transport or _custom_transport
    if active_transport is not None:
        client_kwargs["transport"] = active_transport
    else:
        # Disable automatic retries in HTTPTransport
        client_kwargs["transport"] = httpx.HTTPTransport(retries=0)

    try:
        with httpx.Client(**client_kwargs) as client:
            response = _send_openai_compat_request(client, endpoint, payload, headers, timeout_config)

            if response.status_code != 200:
                err_msg = f"HTTP {response.status_code}"
                raise httpx.HTTPStatusError(
                    message=err_msg,
                    request=response.request,
                    response=response,
                )

            try:
                data = response.json()
            except Exception as e:
                raise ValueError(f"Failed to parse JSON response: {e}")

            choices = data.get("choices", [])
            if not choices:
                raise ValueError("No choices returned from chat completions API")

            msg = choices[0].get("message", {})
            raw_content = msg.get("content") or ""
            cleaned = clean_reply(raw_content)

            # If empty/reasoning-only, retry ONCE with max_tokens: 2000 ONLY IF remaining budget > 10.0s
            if not cleaned:
                rem_budget = remaining_budget_fn() if remaining_budget_fn else (timeout - 1.0)
                if rem_budget > 10.0:
                    logger.info(
                        f"ℹ️ [OpenAI Compat] Empty/reasoning reply with remaining budget {rem_budget:.1f}s > 10s. "
                        f"Retrying once with max_tokens=2000."
                    )
                    retry_payload = dict(payload)
                    retry_payload["max_tokens"] = 2000
                    retry_timeout = min(timeout, rem_budget)
                    timeout_retry_config = httpx.Timeout(connect=4.0, read=retry_timeout, write=5.0, pool=5.0)
                    resp_retry = _send_openai_compat_request(
                        client, endpoint, retry_payload, headers, timeout_retry_config
                    )
                    if resp_retry.status_code == 200:
                        try:
                            data_retry = resp_retry.json()
                            choices_retry = data_retry.get("choices", [])
                            if choices_retry:
                                raw_retry = choices_retry[0].get("message", {}).get("content") or ""
                                cleaned = clean_reply(raw_retry)
                        except Exception:
                            pass

            if not cleaned:
                raise ValueError("Model returned empty reply or only reasoning text")

            return cleaned

    except httpx.TimeoutException:
        raise TimeoutError(f"OpenAI-compatible endpoint timed out after {timeout:.1f}s")
    except httpx.RequestError as exc:
        raise ConnectionError(f"OpenAI-compatible connection failed: {exc}")


def _execute_candidate_call(
    provider: str,
    model: str,
    messages: List[Dict[str, str]],
    context: Optional[str],
    timeout: float,
    remaining_budget_fn: Callable[[], float],
    transport: Optional[httpx.BaseTransport],
) -> str:
    """Helper to dispatch candidate call to the appropriate provider function."""
    if provider == "gemini":
        return _invoke_provider(
            _call_gemini,
            model,
            messages,
            context,
            timeout=timeout,
        )
    elif provider == "openai_compat":
        return _invoke_provider(
            _call_openai_compat,
            model,
            messages,
            context,
            timeout=timeout,
            remaining_budget_fn=remaining_budget_fn,
            transport=transport,
        )
    else:
        raise ValueError(f"Unknown provider '{provider}'")


# ---------------------------------------------------------------------------
# Common Interface & Fallback Chain
# ---------------------------------------------------------------------------

def generate(
    messages: List[Dict[str, str]],
    context: Optional[str] = None,
    transport: Optional[httpx.BaseTransport] = None,
) -> str:
    """Common interface for generating text with automatic provider fallback.

    Enforces:
    - 20-second end-to-end hard time budget.
    - 8s per-call timeout for every candidate, capped by remaining budget.
    - Skip candidate if less than 2s remain.
    - Candidates in cooldown skipped without consuming any budget.
    - Hard timeouts using module-level ThreadPoolExecutor: on timeout, future is abandoned immediately.
    - Real elapsed time logged for every failed call:
      provider=... model=... status=... elapsed=...ms error=<class>: <msg>.
    - Dynamic reordering: if Gemini recently failed or cooled down, try other provider first.
    - Winner provider and latency logging on success.

    Args:
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
        context: Optional retrieved context string.
        transport: Optional httpx transport for testing.

    Returns:
        Cleaned reply string.

    Raises:
        RuntimeError: If all candidate providers fail, are in cooldown, or budget runs out.
    """
    candidates = get_ordered_candidates()
    if not candidates:
        raise RuntimeError("No LLM providers configured.")

    start_monotonic = time.monotonic()
    deadline = start_monotonic + TOTAL_TIME_BUDGET_SECONDS

    last_error = None
    attempted_any = False
    attempted_candidates = set()

    for idx, (provider, model) in enumerate(candidates):
        cand_key = (provider, model)
        if cand_key in attempted_candidates:
            continue

        # Check cooldown — skipped without consuming budget
        now_wall = time.time()
        expiry = _cooldown_store.get(cand_key, 0.0)
        if now_wall < expiry:
            remaining = int(expiry - now_wall)
            logger.info(f"ℹ️ [LLM Skip] Provider '{provider}' ({model}) in cooldown for {remaining}s more.")
            continue

        # Check remaining time budget: skip candidate if less than 2s remain
        now_mono = time.monotonic()
        remaining_budget = deadline - now_mono
        if remaining_budget < MIN_BUDGET_TO_ATTEMPT_SECONDS:
            logger.warning(
                f"⚠️ [LLM Budget] Time budget exhausted ({remaining_budget:.2f}s remaining < {MIN_BUDGET_TO_ATTEMPT_SECONDS}s). "
                f"Skipping remaining candidates."
            )
            break

        # Per-call timeout: 8s for candidate 1, 8s for subsequent, capped by remaining budget
        call_timeout = min(PER_CALL_TIMEOUT_SECONDS, remaining_budget)
        if call_timeout < MIN_BUDGET_TO_ATTEMPT_SECONDS:
            logger.warning(
                f"⚠️ [LLM Budget] Call timeout ({call_timeout:.2f}s) < {MIN_BUDGET_TO_ATTEMPT_SECONDS}s. Skipping candidate."
            )
            break

        attempted_any = True
        attempted_candidates.add(cand_key)

        def remaining_budget_fn() -> float:
            return max(0.0, deadline - time.monotonic())

        cand_start_mono = time.monotonic()
        try:
            # Submit to module-level ThreadPoolExecutor with hard timeout
            future = _EXECUTOR.submit(
                _execute_candidate_call,
                provider,
                model,
                messages,
                context,
                call_timeout,
                remaining_budget_fn,
                transport,
            )

            # Hard timeout — on timeout, abandon the future immediately (no wait, no shutdown)
            reply = future.result(timeout=call_timeout)

            cleaned_reply = clean_reply(reply)
            if not cleaned_reply:
                raise ValueError("Model returned empty reply or only reasoning text")

            candidate_elapsed_ms = (time.monotonic() - cand_start_mono) * 1000.0
            total_latency_ms = (time.monotonic() - start_monotonic) * 1000.0
            logger.info(
                f"✅ [LLM Winner] Provider='{provider}', Model='{model}', "
                f"CandidateLatency={candidate_elapsed_ms:.1f}ms, TotalLatency={total_latency_ms:.1f}ms"
            )
            return cleaned_reply

        except concurrent.futures.TimeoutError:
            # Thread hung or took too long: abandon future immediately
            elapsed_ms = (time.monotonic() - cand_start_mono) * 1000.0
            timeout_err = TimeoutError(f"Provider timed out after {call_timeout:.1f}s")
            last_error = timeout_err
            status, short_error, cooldown_secs = _calculate_cooldown_and_status(timeout_err)
            set_cooldown(provider, model, cooldown_secs)
            if provider == "gemini":
                record_gemini_failure()
            logger.warning(
                f"⚠️ [LLM Fallback] provider={provider} model={model} status={status} "
                f"elapsed={elapsed_ms:.1f}ms error=TimeoutError: {short_error}"
            )

        except Exception as e:
            elapsed_ms = (time.monotonic() - cand_start_mono) * 1000.0
            last_error = e
            status, short_error, cooldown_secs = _calculate_cooldown_and_status(e)
            set_cooldown(provider, model, cooldown_secs)
            if provider == "gemini":
                record_gemini_failure()
            err_cls = e.__class__.__name__
            err_msg = str(e).strip()
            if len(err_msg) > 100:
                err_msg = err_msg[:100] + "..."
            logger.warning(
                f"⚠️ [LLM Fallback] provider={provider} model={model} status={status} "
                f"elapsed={elapsed_ms:.1f}ms error={err_cls}: {err_msg}"
            )

    # If every candidate was skipped because of an active cooldown
    if not attempted_any:
        now_wall = time.time()
        active_cooldowns = [
            _cooldown_store[c] - now_wall
            for c in candidates
            if _cooldown_store.get(c, 0.0) > now_wall
        ]
        if active_cooldowns:
            shortest = max(1, int(round(min(active_cooldowns))))
            msg = f"all candidates cooling down, next retry in {shortest} s"
            logger.warning(f"⚠️ [LLM Cooldown] {msg}")
            raise RuntimeError(f"All LLM candidates failed. {msg}")

    raise RuntimeError(f"All LLM candidates failed. Last error: {last_error}")


def generate_answer(
    message: str,
    chunks: Optional[List[Dict[str, Any]]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    transport: Optional[httpx.BaseTransport] = None,
) -> Tuple[str, List[Dict[str, str]], bool]:
    """Generate an answer using the multi-provider fallback chain.

    Falls back smoothly to the offline responder if all candidates fail or time out.
    When the offline responder is used due to provider failure, prepends:
    "AI mode is busy right now, so this answer comes from my offline µLearn knowledge.\n\n"

    Args:
        message: The user's query or greeting.
        chunks: Optional retrieved knowledge chunks from rag.py.
        history: Optional list of conversation turns.
        transport: Optional httpx transport for testing.

    Returns:
        Tuple of (reply_text, sources_list, used_sources_bool).
    """
    # If no API providers configured at all, run pure offline fallback
    if not is_api_available():
        logger.info("ℹ️ [LLM] No API keys configured. Using offline responder.")
        return fallback_answer(message, chunks)

    # Format context and sources from chunks
    if chunks:
        context = _build_context_block(chunks)
        sources = _extract_sources(chunks)
        used_sources = True
    else:
        context = None
        sources = []
        used_sources = False

    # Build conversation history (up to last 6 turns)
    messages = []
    if history:
        for turn in history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant", "model"):
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})

    try:
        reply_text = generate(messages, context, transport=transport)
        return reply_text, sources, used_sources
    except Exception as e:
        logger.warning(f"⚠️ [LLM Provider Exhausted] {e}. Switching to offline responder with busy notice.")
        offline_reply, off_sources, off_used = fallback_answer(message, chunks)
        busy_prefix = "AI mode is busy right now, so this answer comes from my offline µLearn knowledge.\n\n"
        return busy_prefix + offline_reply, off_sources, off_used


# Log startup candidate order on initial module import
log_startup_chain()
