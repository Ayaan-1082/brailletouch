"""
Gemini service: one call per photo.

Sends the photo once and gets back structured JSON: the exact text on the
page plus a short summary, or (when there is no text) a one-sentence
description of the scene. Failures come back as a clear reason in
Reading.error instead of looking like "no text".
"""

import asyncio
import base64
import json
from dataclasses import dataclass

import httpx
from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TIMEOUT, SUMMARY_MAX_WORDS

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}"
RETRY_DELAY = 2          # seconds before the single retry (rate limit / busy / network blip)

PROMPT = (
    "You are the camera of a Braille reading device used by a blind person. "
    "Look at the photo and answer in JSON.\n"
    "- If it contains readable text: kind = \"text\"; text = all readable text exactly as written, "
    f"in reading order; summary = the most important point in at most {SUMMARY_MAX_WORDS} words.\n"
    "- If it has no readable text: kind = \"scene\"; text = \"\"; summary = one sentence of at most "
    f"{SUMMARY_MAX_WORDS} words describing what is in front of the user, most important first "
    "(obstacles, people, doors, signs).\n"
    "- If the photo is too dark or blurred to tell: kind = \"none\"; text = \"\"; summary = \"\".\n"
    "Write plain sentences: no markdown, bullet points or emoji. Keep numbers as digits."
)

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "kind": {"type": "STRING", "enum": ["text", "scene", "none"]},
        "text": {"type": "STRING"},
        "summary": {"type": "STRING"},
    },
    "required": ["kind", "text", "summary"],
}

REFUSALS = {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "IMAGE_SAFETY", "OTHER"}


@dataclass
class Reading:
    kind: str = "none"          # "text" (a page) or "scene" (no text, described instead)
    text: str = ""              # exact text on the page; "" for a scene
    summary: str = ""           # what gets played in Braille, at most SUMMARY_MAX_WORDS words
    error: str | None = None    # clear reason when nothing usable came back


def image_type(data: bytes) -> str | None:
    """MIME type from the file's first bytes (phones send PNG/HEIC too, not just JPEG)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1", b"msf1", b"hevc"):
        return "image/heic"
    return None


def shorten(text: str) -> str:
    """At most SUMMARY_MAX_WORDS words, so nothing ever plays for minutes."""
    words = text.split()
    return " ".join(words[:SUMMARY_MAX_WORDS])


async def read_image(image_bytes: bytes) -> Reading:
    if not image_bytes:
        return Reading(error="Empty upload: no photo was received")
    mime = image_type(image_bytes)
    if not mime:
        return Reading(error="That file is not a photo (expected JPEG, PNG, WEBP or HEIC)")

    payload = {
        "contents": [{"parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": mime, "data": base64.b64encode(image_bytes).decode()}},
        ]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
            "temperature": 0.2,
        },
    }

    for attempt in (1, 2):
        retry = False
        try:
            async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
                r = await client.post(URL.format(model=GEMINI_MODEL), json=payload,
                                      headers={"x-goog-api-key": GEMINI_API_KEY})
        except httpx.TimeoutException:
            error = f"Gemini took longer than {GEMINI_TIMEOUT}s to answer"
        except httpx.HTTPError as e:
            error = f"Could not reach Gemini ({type(e).__name__}): check the internet connection"
            retry = True
        else:
            if r.status_code == 200:
                return parse(r.json())
            error = http_error(r)
            retry = r.status_code in (429, 500, 502, 503, 504)

        if not (retry and attempt == 1):
            break
        print(f"[gemini] {error}; retrying once")
        await asyncio.sleep(RETRY_DELAY)

    return Reading(error=error)


async def check() -> str | None:
    """Startup check: proves key + model name + internet by reading the model's
    info (uses no generation quota). None = OK, else the reason."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(MODEL_URL.format(model=GEMINI_MODEL), headers={"x-goog-api-key": GEMINI_API_KEY})
    except httpx.HTTPError as e:
        return f"No internet or Gemini unreachable ({type(e).__name__})"
    return None if r.status_code == 200 else http_error(r)


def http_error(r: httpx.Response) -> str:
    try:
        detail = r.json()["error"]["message"]
    except Exception:
        detail = r.text[:120]
    code = r.status_code
    if code == 404:
        return f"Gemini model '{GEMINI_MODEL}' not found: check GEMINI_MODEL in config.py"
    if code == 403 or "api key" in detail.lower():
        return "Gemini rejected the API key: check GEMINI_API_KEY in config.py"
    if code == 429:
        return "Gemini rate limit reached: wait a minute and try again"
    if code >= 500:
        return f"Gemini is busy or down (HTTP {code}): try again shortly"
    return f"Gemini rejected the request (HTTP {code}): {detail}"


def parse(data: dict) -> Reading:
    """Turn Gemini's reply into a Reading; refusals and junk become clear errors."""
    blocked = (data.get("promptFeedback") or {}).get("blockReason")
    if blocked:
        return Reading(error=f"Gemini refused to read this photo ({blocked})")
    candidates = data.get("candidates") or []
    if not candidates:
        return Reading(error="Gemini sent an empty answer")
    candidate = candidates[0]
    reason = candidate.get("finishReason", "")
    parts = (candidate.get("content") or {}).get("parts") or []
    raw = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()

    if not raw:
        if reason in REFUSALS:
            hint = ", e.g. copyrighted book text" if reason == "RECITATION" else ""
            return Reading(error=f"Gemini refused to read this photo ({reason}{hint})")
        return Reading(error=f"Gemini sent an empty answer ({reason or 'no reason given'})")

    try:
        doc = json.loads(raw)
        kind, text, summary = doc.get("kind"), str(doc.get("text", "")).strip(), str(doc.get("summary", "")).strip()
    except (ValueError, AttributeError):
        if reason == "MAX_TOKENS":
            return Reading(error="Gemini's answer was cut off (the page may be too long)")
        kind, text, summary = "text", raw, ""        # not JSON: treat the whole reply as the page text

    if kind == "scene" and summary:
        return Reading(kind="scene", summary=shorten(summary))
    if text:
        return Reading(kind="text", text=text, summary=shorten(summary or text))
    return Reading(error="Photo too dark or blurred: nothing to read or describe")
