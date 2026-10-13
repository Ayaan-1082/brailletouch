"""
OCR service — Phase 6: real implementation using the Gemini API.

Takes raw image bytes, returns the recognized text. Same signature as the
mock version it replaces, so nothing else in the codebase needed to change.
"""

import base64
import httpx
from config import GEMINI_API_KEY, GEMINI_MODEL

OCR_PROMPT = (
    "Read the text visible in this image. Return ONLY the raw text exactly "
    "as written, with no extra commentary, no quotes, no formatting."
)


async def run_ocr(image_bytes: bytes) -> str:
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{
            "parts": [
                {"text": OCR_PROMPT},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}},
            ]
        }]
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload)

        if response.status_code != 200:
            print(f"[ocr_service] Gemini request failed: "
                  f"{response.status_code} {response.text}")
            return ""

        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip()

    except Exception as e:
        print(f"[ocr_service] OCR call failed: {e}")
        return ""
