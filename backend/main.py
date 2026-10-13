import asyncio
import socket
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
import qrcode
import qrcode.image.svg

from services.session_service import SessionManager
from services import camera_service, gemini_service, motor_service
from config import HOST, PORT, GEMINI_MODEL

app = FastAPI(title="BrailleTouch Backend")

# Open CORS for local development — tighten this before any public deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_dashboards: set[WebSocket] = set()
UPLOAD_PAGE = Path(__file__).resolve().parent.parent / "mobile upload" / "mobile_upload.html"


async def broadcast(state: dict) -> None:
    """Push the current session state to every connected dashboard."""
    dead = set()
    for ws in list(connected_dashboards):   # a copy: dashboards can join/leave during the awaits
        try:
            await ws.send_json(state)
        except Exception:
            dead.add(ws)
    connected_dashboards.difference_update(dead)


session = SessionManager(broadcast)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_dashboards.add(websocket)
    try:
        # send current state immediately so a newly-opened dashboard isn't blank
        await websocket.send_json(session.state.to_dict())
        while True:
            # the dashboard doesn't need to send anything; this just keeps
            # the connection open and detects disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected_dashboards.discard(websocket)


@app.post("/api/trigger-capture")
async def trigger_capture():
    """Called by the dashboard's Capture button. Tells the ESP32-CAM to
    take a photo remotely — the resulting image arrives separately via
    the /api/capture endpoint below, once the camera finishes uploading."""
    ok = await camera_service.trigger_capture()
    if not ok:
        return {"status": "error", "detail": "Could not reach the ESP32-CAM"}
    return {"status": "triggered"}


@app.post("/api/capture")
async def capture(request: Request):
    """Receives a raw photo from the phone upload page (or the ESP32-CAM).
    Replies {"status":"ok","kind","summary"} or {"status":"error","detail"}."""
    image_bytes = await request.body()
    # HTTP 200 either way: camera.ino treats anything else as "upload failed"
    return await session.capture(image_bytes)


@app.get("/upload")
async def upload_page():
    """Phone upload page. Open http://<laptop-ip>:8000/upload on the phone;
    the page posts to the relative /api/capture, so no IP is hardcoded."""
    return FileResponse(UPLOAD_PAGE)


@app.get("/api/phone-qr.svg")
async def phone_qr():
    """QR code of the phone upload page for the dashboard: scan it instead of sending the link."""
    img = qrcode.make(f"http://{lan_ip()}:{PORT}/upload", image_factory=qrcode.image.svg.SvgPathImage, border=2)
    return Response(img.to_string(), media_type="image/svg+xml")


@app.post("/api/start")
async def start():
    return await session.start() or {"status": "ok"}


@app.post("/api/pause")
async def pause():
    await session.pause()
    return {"status": "ok"}


@app.post("/api/next")
async def next_character():
    return await session.next() or {"status": "ok"}


@app.post("/api/previous")
async def previous_character():
    return await session.previous() or {"status": "ok"}


@app.post("/api/repeat")
async def repeat_character():
    return await session.repeat() or {"status": "ok"}


def lan_ip() -> str:
    """This laptop's address on the Wi-Fi/hotspot (UDP connect sends no packet)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


async def startup_checks() -> None:
    """Gemini and the motor board, checked before anyone is watching. Never blocks startup."""
    gemini, board = await asyncio.gather(gemini_service.check(), motor_service.check())
    print(f"\n  Gemini:            {'OK (' + GEMINI_MODEL + ')' if gemini is None else 'PROBLEM: ' + gemini}")
    saved_ip = motor_service.ESP32_CONTROLLER_IP
    if board is None:
        print(f"  Motor board:       OK at {saved_ip}")
        return
    # saved IP didn't answer: look for the board on this network by its MAC address
    found = await motor_service.discover(lan_ip())
    if found and found != saved_ip:
        motor_service.ESP32_CONTROLLER_IP = found
        if await motor_service.check() is None:
            motor_service.save_ip(found)
            print(f"  Motor board:       OK at {found} (found by its MAC; config.py updated from {saved_ip})")
            return
        motor_service.ESP32_CONTROLLER_IP = saved_ip
    print(f"  Motor board:       NOT found ({board} at {saved_ip}, and not on this network by its MAC):"
          f" is it powered on and on the same hotspot as this laptop?")


if __name__ == "__main__":
    import uvicorn
    asyncio.run(startup_checks())
    print(f"  Phone upload page: http://{lan_ip()}:{PORT}/upload   (phone on the same Wi-Fi)")
    print("  Dashboard:         open frontend/index.html on this laptop\n")
    uvicorn.run(app, host=HOST, port=PORT)
