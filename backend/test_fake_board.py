"""
End-to-end check without hardware: a fake ESP32 motor board on this laptop.

Run from inside the backend/ folder:
    python test_fake_board.py

Starts a tiny HTTP server that reads POST /motors exactly like handleMotors()
in motor_controller.ino (JSON {"motors": [6 bools], "character": ""}, one
pin per motor), then plays a sentence through the real backend code
(session_service -> motor_service -> real HTTP). Prints each cell the "pins"
showed and checks the board got valid requests and ended with all motors off.
"""

import asyncio
import contextlib
import io
import json
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

from services import motor_service, session_service
from services.session_service import SessionManager
from services.braille_service import split_words
from data.braille_map import BRAILLE_MAP, dots_to_motors

TEXT = 'Take 2 pills, "now!"'
pins = [False] * 6       # M1..M6 = GPIO 26, 27, 14, 12, 13, 33
log = []                 # pin states after every request
bad = []                 # requests the firmware would reject or misread


class FakeBoard(BaseHTTPRequestHandler):
    fail_next_off = False    # answer the next "all off" with HTTP 500 (simulated Wi-Fi blip)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path != "/motors" or not body:
            bad.append((self.path, body))
            self.send_response(400)
            self.end_headers()
            return
        doc = json.loads(body)
        motors = doc.get("motors", [])
        if len(motors) != 6 or not all(isinstance(m, bool) for m in motors) or doc.get("character", "") != "":
            bad.append(doc)
        if FakeBoard.fail_next_off and not any(motors):
            FakeBoard.fail_next_off = False
            self.send_response(500)
            self.end_headers()
            return
        for i in range(min(6, len(motors))):
            pins[i] = bool(motors[i])
        log.append(list(pins))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


async def no_dashboard(state):
    pass


async def main():
    server = HTTPServer(("127.0.0.1", 0), FakeBoard)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    motor_service.ESP32_CONTROLLER_IP = f"127.0.0.1:{server.server_port}"
    session_service.MOTOR_ON_DURATION = 0.05
    session_service.PAUSE_BETWEEN_CHARACTERS = 0.02
    session_service.WORD_PAUSE = 0.02

    s = SessionManager(no_dashboard)
    await s.load_text("raw", TEXT)
    await s.start()
    await s._task

    expected = "".join(split_words(TEXT))
    on = [p for p in log if any(p)]
    print(f"Text: {TEXT}")
    print(f"Requests received: {len(log)}, malformed: {len(bad)}")
    print("Cells shown on the pins (M1..M6):")
    for pattern, ch in zip(on, expected):
        print("  ", "".join("1" if m else "0" for m in pattern), " ", ch)
    assert [tuple(p) for p in on] == [tuple(dots_to_motors(BRAILLE_MAP[c.lower()])) for c in expected], on
    assert not bad, bad
    assert log[-1] == [False] * 6
    print("Fake board check passed: valid requests, right cells, motors off at the end.")

    # Board switched off (unroutable IP): playback must not crawl, and only one log line.
    off = [False] * 6
    motor_service.ESP32_CONTROLLER_IP = "10.255.255.1"
    motor_service._failures, motor_service._skip_until = 0, 0.0
    out = io.StringIO()
    started = time.perf_counter()
    with contextlib.redirect_stdout(out):
        await s.load_text("raw", "Hello there, reader.")
        await s.start()
        await s._task
    seconds = time.perf_counter() - started
    assert out.getvalue().count("not reachable") == 1 and seconds < 8, (seconds, out.getvalue())
    cells = len("".join(split_words("Hello there, reader.")))
    print(f"Board off: {cells} cells played in {seconds:.1f}s (was about 3 s per cell), one log line.")

    # Board back on: after the retry window the next command reaches it again.
    motor_service.ESP32_CONTROLLER_IP = f"127.0.0.1:{server.server_port}"
    motor_service._skip_until = 0.0
    log.clear()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        await s.start()
        await s._task
    assert out.getvalue().count("back online") == 1 and log and log[-1] == off, out.getvalue()
    print("Board back on: commands reach it again, ends all-off.")

    # A failed "all off" (Wi-Fi blip) is retried at once, so motors don't stay on.
    FakeBoard.fail_next_off = True
    log.clear()
    await motor_service.send_motor_state(off)
    assert not FakeBoard.fail_next_off and log == [off] and motor_service._failures == 0, log
    print("Failed 'all off' was retried: motors off.")

    # Startup check: board answers (and motors are set off); an unreachable board gives a reason.
    log.clear()
    assert await motor_service.check() is None and log == [off], log
    motor_service.ESP32_CONTROLLER_IP = "10.255.255.1"
    reason = await motor_service.check()
    assert reason, reason
    print(f"Startup check: board found and set off; unreachable board -> '{reason}'.")

    # Auto-discovery: reading the MAC table (Windows / macOS / Linux formats) and rewriting only the IP line.
    mac = motor_service.ESP32_CONTROLLER_MAC
    windows = "Interface: 192.168.140.111 --- 0x7\r\n  192.168.140.117       b0-cb-d8-5c-8f-ac     dynamic\r\n"
    mac_os = "? (192.168.140.117) at b0:cb:d8:5c:8f:ac on en0 ifscope [ethernet]\n"
    linux = "? (192.168.140.117) at b0:cb:d8:5c:8f:ac [ether] on wlan0\n"
    assert all(motor_service.ip_for_mac(t, mac) == "192.168.140.117" for t in (windows, mac_os, linux))
    assert motor_service.ip_for_mac("  192.168.140.5  aa-bb-cc-dd-ee-ff  dynamic", mac) is None
    sample = 'A = 1\r\nESP32_CONTROLLER_IP = "10.205.125.91"\r\nESP32_CONTROLLER_MAC = "b0-cb-d8-5c-8f-ac"\r\n'
    assert motor_service.set_config_ip(sample, "192.168.140.117") == sample.replace("10.205.125.91", "192.168.140.117")

    # Whole startup flow on a temporary copy of config.py: saved IP dead -> board found by MAC -> copy updated.
    import shutil
    import tempfile
    import main
    from services import gemini_service

    async def gemini_ok():
        return None

    async def found_board(own_ip):
        return f"127.0.0.1:{server.server_port}"          # the fake board stands in for the found IP

    real_config, real_discover, real_check = motor_service.CONFIG_FILE, motor_service.discover, gemini_service.check
    tmp = Path(tempfile.mkdtemp()) / "config.py"
    shutil.copyfile(real_config, tmp)
    real_before = real_config.read_bytes()
    motor_service.CONFIG_FILE, motor_service.discover, gemini_service.check = tmp, found_board, gemini_ok
    motor_service.ESP32_CONTROLLER_IP = "10.255.255.1"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        await main.startup_checks()
    motor_service.CONFIG_FILE, motor_service.discover, gemini_service.check = real_config, real_discover, real_check
    saved = tmp.read_bytes()
    assert "found by its MAC; config.py updated" in out.getvalue(), out.getvalue()
    assert f'ESP32_CONTROLLER_IP = "127.0.0.1:{server.server_port}"'.encode() in saved and b"\r\n" in saved
    assert real_config.read_bytes() == real_before                     # your real config.py untouched
    print("Auto-discovery: MAC table read on all OS formats; startup finds the board and updates config.py (temp copy).")

    # One real search of this laptop's current network, timed (the board is probably not on it right now).
    started = time.perf_counter()
    result = await real_discover(main.lan_ip())
    seconds = time.perf_counter() - started
    assert seconds < 5, seconds
    print(f"Real network search took {seconds:.1f}s -> {result or 'board not on this network'}.")
    server.shutdown()


asyncio.run(main())
