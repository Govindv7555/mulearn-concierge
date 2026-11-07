"""
µLearn Concierge — Diagnostic Script for LLM Providers
Checks each candidate in LLM_PROVIDERS with a trivial prompt: "Say hi in five words".

Usage:
    python scripts/check_llm.py

Security & Policy:
- Loads .env safely via python-dotenv.
- NEVER prints keys or headers.
- Does NOT crash if a candidate fails; tests all candidates in sequence.
- Prints status, latency in ms, empty flag, and first 80 chars of reply.
"""

import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from llm import get_configured_candidates, _call_gemini, _call_openai_compat, clean_reply


def main():
    candidates = get_configured_candidates()
    print("=" * 75)
    print("µLearn Concierge — LLM Provider Diagnostic Check")
    print("=" * 75)

    if not candidates:
        print("❌ No LLM providers configured in environment.")
        print("   (Ensure LLM_PROVIDERS, GEMINI_API_KEY, and/or OPENAI_COMPAT_API_KEY are set in .env)")
        return

    print(f"Found {len(candidates)} configured candidate(s):")
    for idx, (p, m) in enumerate(candidates, 1):
        print(f"  [{idx}] Provider: {p:<15} | Model: {m}")
    print("-" * 75)

    test_messages = [{"role": "user", "content": "Say hi in five words"}]
    results = []

    for idx, (provider, model) in enumerate(candidates, 1):
        print(f"\nTesting [{idx}/{len(candidates)}] Provider='{provider}', Model='{model}'...")
        t0 = time.time()
        status_code = "UNKNOWN"
        latency_ms = 0.0
        is_empty = True
        reply_preview = ""

        try:
            if provider == "gemini":
                raw_reply = _call_gemini(model, test_messages, context=None, timeout=15.0)
            elif provider == "openai_compat":
                raw_reply = _call_openai_compat(model, test_messages, context=None, timeout=15.0)
            else:
                raise ValueError(f"Unknown provider '{provider}'")

            latency_ms = (time.time() - t0) * 1000.0
            status_code = "200 OK"
            cleaned = clean_reply(raw_reply)
            is_empty = (len(cleaned) == 0)
            reply_preview = cleaned[:80].replace("\n", " ")

        except Exception as e:
            latency_ms = (time.time() - t0) * 1000.0
            is_empty = True
            err_cls = e.__class__.__name__
            err_str = str(e).strip()
            # Extract status code if available
            code = getattr(e, "status_code", getattr(e, "code", None))
            if hasattr(e, "response") and hasattr(e.response, "status_code"):
                code = e.response.status_code
            status_code = f"HTTP {code}" if code else err_cls
            reply_preview = f"ERROR: {err_cls}: {err_str[:60]}"

        print(f"  Status:        {status_code}")
        print(f"  Latency:       {latency_ms:.1f} ms")
        print(f"  Content Empty: {is_empty}")
        print(f"  Reply (80c):   {reply_preview}")

        results.append({
            "provider": provider,
            "model": model,
            "status": status_code,
            "latency_ms": latency_ms,
            "empty": is_empty,
            "preview": reply_preview,
        })

    print("\n" + "=" * 75)
    print("DIAGNOSTIC SUMMARY TABLE")
    print("=" * 75)
    print(f"{'Provider':<15} {'Model':<30} {'Status':<12} {'Latency':<10} {'Empty':<6}")
    print("-" * 75)
    for r in results:
        prov = r["provider"][:14]
        mod = r["model"][:29]
        stat = str(r["status"])[:11]
        lat = f"{r['latency_ms']:.0f}ms"
        emp = str(r["empty"])
        print(f"{prov:<15} {mod:<30} {stat:<12} {lat:<10} {emp:<6}")
    print("=" * 75)


if __name__ == "__main__":
    main()

