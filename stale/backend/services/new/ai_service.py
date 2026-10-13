"""
AI summarization service — Phase 7: real implementation using the Gemini API.

Takes OCR text, returns a short summary. Same signature as the mock version
it replaces, so nothing else in the codebase needed to change.
"""

import httpx
from config import GEMINI_API_KEY, GEMINI_MODEL

SYSTEM_PROMPT = (
    "You are assisting a tactile Braille learning device. Summarize the "
    "following text in simple English. Preserve the main meaning. Do not "
    "add information. Keep the summary short. Prefer simple vocabulary and "
    "short sentences. Return only the summary."
)


async def summarize(text: str) -> str:
    if not text.strip():
        return ""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": text}]}],
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload)

        if response.status_code != 200:
            print(f"[ai_service] Gemini request failed: "
                  f"{response.status_code} {response.text}")
            # Fail-soft: fall back to the original OCR text rather than
            # losing the reading session entirely if summarization fails.
            return text

        data = response.json()
        summary = data["candidates"][0]["content"]["parts"][0]["text"]
        return summary.strip()

    except Exception as e:
        print(f"[ai_service] Summarization call failed: {type(e).__name__}: {e}")
        return text
