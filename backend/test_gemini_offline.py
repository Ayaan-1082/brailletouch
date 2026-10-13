"""
Gemini service check — no API key or internet needed.

Run from inside the backend/ folder:
    python test_gemini_offline.py

A fake Gemini answers each request with a prepared reply (good page, scene,
rate limit then success, busy twice, wrong model, bad key, refusals, broken
JSON, cut-off answer, timeout) and the check confirms the backend turns each
one into the right result or a clear error reason, retries only when it
should, caps summaries at SUMMARY_MAX_WORDS, and keeps the previous text
loaded when a capture fails.
"""

import asyncio
import json

import httpx

from services import gemini_service, motor_service
from services.session_service import SessionManager
from config import SUMMARY_MAX_WORDS

gemini_service.RETRY_DELAY = 0
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20

replies = []      # queue of fake answers for the next requests
requests = []     # what the backend actually sent


def answer(doc=None, raw=None, finish="STOP"):
    text = raw if raw is not None else json.dumps(doc)
    return 200, {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}]}


def handler(request: httpx.Request) -> httpx.Response:
    requests.append(request)
    reply = replies.pop(0)
    if reply == "timeout":
        raise httpx.ReadTimeout("slow", request=request)
    if reply == "offline":
        raise httpx.ConnectError("no route", request=request)
    status, body = reply
    return httpx.Response(status, json=body)


class FakeClient(httpx.AsyncClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, transport=httpx.MockTransport(handler), **kwargs)


httpx.AsyncClient = FakeClient


async def read(image, *queued):
    replies[:] = list(queued)
    requests.clear()
    return await gemini_service.read_image(image)


async def main():
    long_text = " ".join(f"word{i}" for i in range(40))

    # a page: exact text + summary capped at SUMMARY_MAX_WORDS
    r = await read(JPEG, answer({"kind": "text", "text": "Library closes at 6 pm.", "summary": long_text}))
    assert r.kind == "text" and r.text == "Library closes at 6 pm." and not r.error
    assert len(r.summary.split()) == SUMMARY_MAX_WORDS, r.summary
    sent = json.loads(requests[0].content)
    assert requests[0].headers["x-goog-api-key"] and "key=" not in str(requests[0].url)   # key in header, not URL
    assert sent["contents"][0]["parts"][1]["inline_data"]["mime_type"] == "image/jpeg"
    assert sent["generationConfig"]["responseMimeType"] == "application/json"

    # no text: scene description
    r = await read(PNG, answer({"kind": "scene", "text": "", "summary": "Door ahead, chair on your left."}))
    assert r.kind == "scene" and r.summary == "Door ahead, chair on your left." and not r.error
    assert json.loads(requests[0].content)["contents"][0]["parts"][1]["inline_data"]["mime_type"] == "image/png"

    # rate limit, then success: one retry
    r = await read(JPEG, (429, {"error": {"message": "Resource exhausted"}}), answer({"kind": "text", "text": "Hi.", "summary": "Hi."}))
    assert r.text == "Hi." and len(requests) == 2

    # busy twice: gives up after one retry with a clear reason
    r = await read(JPEG, (503, {"error": {"message": "overloaded"}}), (503, {"error": {"message": "overloaded"}}))
    assert "busy" in r.error and len(requests) == 2

    # wrong model / bad key: no retry, says what to fix
    r = await read(JPEG, (404, {"error": {"message": "models/x is not found"}}))
    assert "GEMINI_MODEL" in r.error and len(requests) == 1
    r = await read(JPEG, (400, {"error": {"message": "API key not valid. Please pass a valid API key."}}))
    assert "API key" in r.error and len(requests) == 1

    # refusals
    r = await read(JPEG, (200, {"candidates": [{"finishReason": "RECITATION"}]}))
    assert "RECITATION" in r.error and "copyrighted" in r.error
    r = await read(JPEG, (200, {"promptFeedback": {"blockReason": "SAFETY"}}))
    assert "SAFETY" in r.error

    # not JSON: the reply is used as the page text, summary capped
    r = await read(JPEG, answer(raw=long_text))
    assert r.kind == "text" and r.text == long_text and len(r.summary.split()) == SUMMARY_MAX_WORDS

    # cut-off JSON, dark photo, timeout (no retry), empty or non-image upload (no call at all)
    r = await read(JPEG, answer(raw='{"kind": "text", "text": "Half a pa', finish="MAX_TOKENS"))
    assert "cut off" in r.error
    r = await read(JPEG, answer({"kind": "none", "text": "", "summary": ""}))
    assert "dark or blurred" in r.error
    r = await read(JPEG, "timeout")
    assert "longer than" in r.error and len(requests) == 1
    r = await read(b"")
    assert "Empty upload" in r.error and not requests
    r = await read(b"hello, not a photo")
    assert "not a photo" in r.error and not requests

    # startup check: reads the model's info with a GET (no generation), key in the header
    replies[:] = [(200, {"name": "models/x"})]
    requests.clear()
    assert await gemini_service.check() is None
    assert requests[0].method == "GET" and str(requests[0].url).endswith("/models/" + gemini_service.GEMINI_MODEL)
    assert requests[0].headers["x-goog-api-key"]
    replies[:] = [(404, {"error": {"message": "not found"}})]
    assert "GEMINI_MODEL" in await gemini_service.check()
    replies[:] = [(403, {"error": {"message": "Permission denied"}})]
    assert "API key" in await gemini_service.check()
    replies[:] = ["offline"]
    assert "No internet" in await gemini_service.check()

    # session: a failed capture keeps the previous text and returns the reason
    async def nothing(state):
        pass

    async def no_motors(motors, speak_char=""):
        pass

    motor_service.send_motor_state = no_motors
    s = SessionManager(nothing)
    replies[:] = [answer({"kind": "text", "text": "Take 2 pills.", "summary": "Take 2 pills."})]
    assert await s.capture(JPEG) == {"status": "ok", "kind": "text", "summary": "Take 2 pills."}
    assert s.state.summary == "Take 2 pills."
    replies[:] = [(429, {}), (429, {})]
    result = await s.capture(JPEG)
    assert result["status"] == "error" and "rate limit" in result["detail"]
    assert s.state.summary == "Take 2 pills."          # previous text kept
    replies[:] = [answer({"kind": "scene", "text": "", "summary": "Stairs going down ahead."})]
    await s.capture(JPEG)
    assert s.state.summary == "Stairs going down ahead." and "scene" in s.state.ocr_text

    print("All Gemini checks passed (one call, retries, errors, refusals, 15-word cap, scene mode).")


asyncio.run(main())
