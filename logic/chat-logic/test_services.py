"""
Spark — Service Diagnostics
==============================
Tests every component in the pipeline.

Usage: python test_services.py

Pipeline: Mic -> Whisper(local) -> Ollama(11434) -> Kokoro(local) -> Speaker
Bot: FastAPI on port 7860
"""

import os
import sys
import json
import time
import traceback
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/v1")
BOT_URL = f"http://127.0.0.1:{os.getenv('BOT_PORT', '7860')}"
LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:4b")

OLLAMA_BASE = OLLAMA_URL.rstrip("/").removesuffix("/v1")

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

results = []


def log(icon, message, detail=""):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"  [{ts}] {icon}  {message}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


def section(title):
    print()
    print(f"  {'=' * 60}")
    print(f"  {title}")
    print(f"  {'=' * 60}")


def timed_request(method, url, **kwargs):
    """Make a request and return (response, elapsed_ms)."""
    import urllib.request
    import urllib.error

    start = time.perf_counter()
    try:
        if method == "GET":
            req = urllib.request.Request(url)
            for k, v in kwargs.get("headers", {}).items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                elapsed = (time.perf_counter() - start) * 1000
                return {"status": resp.status, "body": body}, elapsed

        elif method == "POST":
            data = kwargs.get("data", None)
            headers = kwargs.get("headers", {})
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
                elapsed = (time.perf_counter() - start) * 1000
                return {"status": resp.status, "body": body}, elapsed

    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - start) * 1000
        body = e.read() if hasattr(e, "read") else b""
        return {"status": e.code, "body": body, "error": str(e)}, elapsed
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {"status": 0, "body": b"", "error": str(e)}, elapsed


# ---------------------------------------------------------------------------
# TEST 1: Ollama LLM
# ---------------------------------------------------------------------------
def test_ollama():
    section("TEST 1: OLLAMA LLM")
    log(INFO, f"URL: {OLLAMA_BASE}")
    log(INFO, f"Model: {LLM_MODEL}")

    # Health check
    log(INFO, "Checking Ollama server...")
    resp, ms = timed_request("GET", f"{OLLAMA_BASE}/api/version")
    if resp and resp["status"] == 200:
        try:
            ver = json.loads(resp["body"]).get("version", "?")
            log(PASS, f"Ollama server OK", f"v{ver} ({ms:.0f}ms)")
        except Exception:
            log(PASS, f"Ollama server OK", f"{ms:.0f}ms")
        results.append(("Ollama Server", True))
    else:
        resp2, ms2 = timed_request("GET", f"{OLLAMA_BASE}")
        if resp2 and resp2["status"] == 200:
            log(PASS, f"Ollama server OK", f"{ms2:.0f}ms")
            results.append(("Ollama Server", True))
        else:
            err = resp.get("error", "Connection refused") if resp else "Connection refused"
            log(FAIL, f"Ollama server FAILED", f"{err}")
            results.append(("Ollama Server", False))
            return

    # Check model
    log(INFO, f"Checking if {LLM_MODEL} is available...")
    resp, ms = timed_request("GET", f"{OLLAMA_BASE}/api/tags")
    if resp and resp["status"] == 200:
        try:
            tags = json.loads(resp["body"])
            models = [m["name"] for m in tags.get("models", [])]
            if LLM_MODEL in models or any(LLM_MODEL in m for m in models):
                log(PASS, f"Model '{LLM_MODEL}' found", f"Available: {models}")
                results.append(("Ollama Model", True))
            else:
                log(FAIL, f"Model '{LLM_MODEL}' NOT found", f"Available: {models}")
                log(INFO, f"Run: ollama pull {LLM_MODEL}")
                results.append(("Ollama Model", False))
                return
        except Exception as e:
            log(WARN, f"Could not parse model list", f"{e}")
            results.append(("Ollama Model", None))
    else:
        log(FAIL, "Could not list models")
        results.append(("Ollama Model", False))
        return

    # Generation test
    log(INFO, f"Testing generation...")
    payload = json.dumps({
        "model": LLM_MODEL,
        "prompt": "Say 'Hello, I am working!' in exactly 5 words.",
        "stream": False,
        "options": {"num_predict": 20},
    }).encode()
    resp, ms = timed_request(
        "POST", f"{OLLAMA_BASE}/api/generate",
        data=payload, headers={"Content-Type": "application/json"},
    )
    if resp and resp["status"] == 200:
        try:
            result = json.loads(resp["body"])
            text = result.get("response", "(empty)")[:100]
            log(PASS, f"Generation OK", f'"{text}" ({ms:.0f}ms)')
        except Exception:
            log(PASS, f"Generation OK", f"{ms:.0f}ms")
        results.append(("Ollama Generation", True))
    else:
        err = resp.get("error", "Unknown") if resp else "No response"
        log(FAIL, f"Generation FAILED", f"{err} ({ms:.0f}ms)")
        results.append(("Ollama Generation", False))


# ---------------------------------------------------------------------------
# TEST 2: Bot Server
# ---------------------------------------------------------------------------
def test_bot():
    section("TEST 2: TEACHING ASSISTANT BOT (FastAPI)")
    log(INFO, f"URL: {BOT_URL}")

    # Main page
    log(INFO, "Checking main page...")
    resp, ms = timed_request("GET", f"{BOT_URL}/")
    if resp and resp["status"] == 200:
        body_str = resp["body"].decode("utf-8", errors="replace")
        has_html = "<html" in body_str.lower()
        log(PASS, f"Main page OK", f"HTML={'Yes' if has_html else 'No'} ({ms:.0f}ms)")
        results.append(("Bot Main Page", True))
    else:
        err = resp.get("error", "Connection refused") if resp else "Connection refused"
        log(FAIL, f"Main page FAILED", f"{err}")
        log(INFO, "Start the bot first: python bot_teaching_assistant.py")
        results.append(("Bot Main Page", False))
        return

    # Config API
    log(INFO, "Checking config API...")
    resp, ms = timed_request("GET", f"{BOT_URL}/api/config")
    if resp and resp["status"] == 200:
        try:
            config = json.loads(resp["body"])
            mode = config.get("mode", "?")
            style = config.get("teachingStyle", "?")
            log(PASS, f"Config API OK", f"mode={mode}, style={style} ({ms:.0f}ms)")
        except Exception:
            log(PASS, f"Config API OK", f"{ms:.0f}ms")
        results.append(("Bot Config API", True))
    else:
        log(FAIL, "Config API FAILED")
        results.append(("Bot Config API", False))

    # Materials reload
    log(INFO, "Checking materials reload API...")
    resp, ms = timed_request(
        "POST", f"{BOT_URL}/api/materials/reload",
        data=b"", headers={"Content-Type": "application/json"},
    )
    if resp and resp["status"] == 200:
        try:
            data = json.loads(resp["body"])
            materials = data.get("materials", {})
            total = sum(len(v) for v in materials.values())
            log(PASS, f"Materials API OK", f"{total} files loaded ({ms:.0f}ms)")
        except Exception:
            log(PASS, f"Materials API OK", f"{ms:.0f}ms")
        results.append(("Bot Materials API", True))
    else:
        log(FAIL, "Materials API FAILED")
        results.append(("Bot Materials API", False))


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
def print_summary():
    section("DIAGNOSTIC SUMMARY")

    passed = sum(1 for _, v in results if v is True)
    failed = sum(1 for _, v in results if v is False)
    warned = sum(1 for _, v in results if v is None)
    total = len(results)

    print()
    for name, status in results:
        if status is True:
            icon = PASS
        elif status is False:
            icon = FAIL
        else:
            icon = WARN
        print(f"    {icon}  {name}")

    print()
    print(f"  ----------------------------------------------")
    print(f"  Results: {passed} passed, {failed} failed, {warned} warnings / {total} total")
    print()

    if failed == 0:
        print(f"  ALL TESTS PASSED!")
        print(f"  Open http://localhost:{os.getenv('BOT_PORT', '7860')} and click 'Start Session'")
    else:
        print(f"  Some tests failed. Fix the issues above and re-run.")

    print()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print()
    print("  +============================================================+")
    print("  |                                                            |")
    print("  |   SPARK -- SERVICE DIAGNOSTICS                              |")
    print("  |                                                            |")
    print("  |   Testing: Ollama LLM + Pipecat Bot                       |")
    print("  |                                                            |")
    print("  +============================================================+")

    start = time.perf_counter()

    try:
        test_ollama()
    except Exception as e:
        log(FAIL, f"Ollama test crashed: {e}")
        traceback.print_exc()

    try:
        test_bot()
    except Exception as e:
        log(FAIL, f"Bot test crashed: {e}")
        traceback.print_exc()

    elapsed = time.perf_counter() - start
    print(f"\n  Total diagnostic time: {elapsed:.1f}s")

    print_summary()
