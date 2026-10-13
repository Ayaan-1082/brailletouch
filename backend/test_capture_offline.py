"""
Phone-capture check — no phone, API key or internet needed.

Run from inside the backend/ folder:
    python test_capture_offline.py

Runs the real FastAPI app with a fake Gemini and checks the phone path:
/upload serves the page (which posts to the relative /api/capture), a good
photo loads text and returns its summary, a Gemini failure returns the
reason and keeps the previous text, bad uploads get a clear error, and a
second photo sent while the first is still being read is refused.
"""

import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from services import gemini_service, motor_service

gemini_service.RETRY_DELAY = 0
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 20
replies = []


def gemini_answer(kind, text, summary):
    doc = json.dumps({"kind": kind, "text": text, "summary": summary})
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": doc}]}, "finishReason": "STOP"}]})


def handler(request):
    return replies.pop(0)


class FakeClient(httpx.AsyncClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, transport=httpx.MockTransport(lambda r: handler(r)), **kwargs)


httpx.AsyncClient = FakeClient


async def no_motors(motors, speak_char=""):
    pass


motor_service.send_motor_state = no_motors

import main  # noqa: E402  (after the fakes are in place)


def http_checks():
    with TestClient(main.app) as c:
        page = c.get("/upload")
        assert page.status_code == 200 and 'const BACKEND_URL = "/api/capture"' in page.text
        qr = c.get("/api/phone-qr.svg")
        assert qr.status_code == 200 and qr.headers["content-type"] == "image/svg+xml" and "<svg" in qr.text

        replies[:] = [gemini_answer("text", "Take 2 tablets after food.", "Take 2 tablets after food.")]
        r = c.post("/api/capture", content=JPEG, headers={"Content-Type": "image/jpeg"}).json()
        assert r == {"status": "ok", "kind": "text", "summary": "Take 2 tablets after food."}, r
        assert main.session.state.summary == "Take 2 tablets after food."

        replies[:] = [httpx.Response(429, json={}), httpx.Response(429, json={})]
        r = c.post("/api/capture", content=JPEG).json()
        assert r["status"] == "error" and "rate limit" in r["detail"], r
        assert main.session.state.summary == "Take 2 tablets after food."      # previous text kept

        assert "Empty upload" in c.post("/api/capture", content=b"").json()["detail"]
        assert "not a photo" in c.post("/api/capture", content=b"hello").json()["detail"]

        replies[:] = [gemini_answer("scene", "", "Stairs going down ahead.")]
        r = c.post("/api/capture", content=JPEG).json()
        assert r == {"status": "ok", "kind": "scene", "summary": "Stairs going down ahead."}, r


async def double_tap_check():
    global handler
    release = asyncio.Event()

    async def slow_gemini(request):
        await release.wait()
        return gemini_answer("text", "First photo.", "First photo.")

    handler = slow_gemini
    first = asyncio.create_task(main.session.capture(JPEG))
    await asyncio.sleep(0.05)                                      # first photo is now with "Gemini"
    second = await main.session.capture(JPEG)
    assert second == {"status": "error", "detail": "A capture is already in progress"}, second
    release.set()
    assert (await first)["status"] == "ok" and main.session.state.summary == "First photo."


http_checks()
main.session = main.SessionManager(main.broadcast)                 # fresh session on this event loop
asyncio.run(double_tap_check())
print("All phone-capture checks passed (/upload page, results, errors, previous text kept, double tap).")
