# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

BrailleTouch: a hardware prototype that photographs printed text, OCRs and summarizes it with Gemini, converts it to Braille, and plays each Braille cell on 6 vibration motors (plus a spoken letter clip). Three parts talk over HTTP on a shared Wi-Fi hotspot:

```
frontend (dashboard) ──POST /api/trigger-capture──▶ backend (FastAPI :8000)
backend ──POST/GET /capture──▶ ESP32-CAM ──POST raw JPEG──▶ backend /api/capture
backend: one Gemini call (page text + ≤15-word summary, or a scene description) → split sentences/words → cells → motors
backend ──POST /motors {"motors":[6 bools],"character":"a"}──▶ ESP32 motor controller
backend ──WebSocket /ws (full session state on every change)──▶ dashboard
```

Not a git repo. No build step, no test framework, no linter.

## Commands

Run everything from `backend/` (imports are relative to it, e.g. `from services import ...`, `from config import ...`):

```bash
pip install -r requirements.txt     # fastapi, uvicorn, httpx (test_speaker/testmotors also need `requests`)
python main.py                      # backend on 0.0.0.0:8000; first prints startup checks (Gemini key/model/internet via a model-info GET, motor board via one all-off command; if the saved ESP32_CONTROLLER_IP doesn't answer it finds the board on the current /24 by ESP32_CONTROLLER_MAC via `arp -a` and rewrites only that line of config.py) and the phone URL; never blocks startup
python test_braille_engine.py       # tables of a–z, numbers, punctuation + text splitting; no hardware/network
python test_session.py              # playback/position checks with fake motors; no hardware/network
python test_fake_board.py           # fake ESP32 over real HTTP: checks /motors requests + cells; no hardware
python test_gemini_offline.py       # fake Gemini: every error/retry/refusal case, 15-word cap; no key/network
python test_gemini.py photo.jpg     # real Gemini call (key in config.py): kind, text, summary, time
python test_capture_offline.py      # phone path with fake Gemini: /upload page, results, errors, double tap
python testmotors.py <motor_ip>     # cycles each motor, bypasses backend
python test_speaker.py <motor_ip>   # plays letter WAVs, bypasses backend
```

Dashboard: open `frontend/index.html` directly in a browser; it hardcodes `localhost:8000` in `frontend/app.js`.

Phone capture (the main capture path; the ESP32-CAM is parked for now): `python main.py` prints `Phone upload page: http://<laptop-ip>:8000/upload`; open that on a phone on the same Wi-Fi/hotspot, or scan the QR code in the dashboard's top bar (`GET /api/phone-qr.svg`, drawn with the `qrcode` package from the current LAN IP; app.js reloads it on every WebSocket connect). The page is served by the backend (`GET /upload` → `mobile upload/mobile_upload.html`) and posts to the relative `/api/capture`, so no IP is hardcoded. It shrinks photos to ≤1600 px JPEG in the browser before upload and shows the real result or error. One-time on the laptop (admin PowerShell), or Windows Firewall blocks the phone on hotspot ("Public") networks: `New-NetFirewallRule -DisplayName "BrailleTouch 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow`.

Firmware: Arduino IDE. Camera = AI-Thinker ESP32-CAM, partition "Huge APP (3MB No OTA/1MB SPIFFS)". Motor controller = ESP32 Dev Kit, needs ArduinoJson + ESP8266Audio and `data/*.wav` uploaded to LittleFS.

## Architecture notes

- `backend/config.py` is the single place for timing (`MOTOR_ON_DURATION`, `PAUSE_BETWEEN_CHARACTERS`, `WORD_PAUSE`), device IPs (`ESP32_CONTROLLER_IP`, `ESP32_CAMERA_IP`), and Gemini key/model/`GEMINI_TIMEOUT`/`SUMMARY_MAX_WORDS`. The key stays in config.py by choice (local only, changed often); it is sent in the `x-goog-api-key` header, never the URL. Device IPs are DHCP-assigned by a phone hotspot and change: the motor board's IP is auto-found at startup (by MAC) and saved back into config.py; the camera IP (parked) is still manual. The motor board's firmware only joins the Wi-Fi SSID hardcoded in motor_controller.ino, so the laptop and phone must join that same hotspot (2.4 GHz). Wi-Fi creds and the backend URL are also hardcoded in each `.ino`.
- `services/session_service.py` `SessionManager` is the single source of truth. It owns `SessionState` (`models/session.py`), and broadcasts `state.to_dict()` after every change. The position always points at a real letter (`_step()` returns the boundary crossed, or `None` at either end; `finished` marks played-past-the-end). Only one motor activity (play loop or single `_pulse`) runs at a time via `_run()`/`_stop()`, and `_guard` always ends it motors-off. `state.motors` is the live motor output; the letter's pattern comes from `state.dots`. `to_dict()` is the dashboard's sync contract (camelCase keys); changing keys requires updating `frontend/app.js`.
- `/api/capture` (phone page, or the ESP32-CAM) runs `session.capture()` and replies `{"status":"ok","kind","summary"}` or `{"status":"error","detail"}`, always HTTP 200. Only one capture runs at a time (`_capturing` guard: a second returns "A capture is already in progress"). The dashboard sees new text over WebSocket and shows "New photo read" when the summary changes. ESP32-CAM path (parked, unchanged): `/api/trigger-capture` only pokes the camera; the camera then POSTs the JPEG to `/api/capture` (20s timeout in `camera.ino`, laptop IP hardcoded there).
- `services/gemini_service.py` `read_image(bytes) -> Reading(kind, text, summary, error)`: one generateContent call with a JSON response schema (`kind` text/scene/none). Text photos give the exact text + a summary; no-text photos give a one-sentence scene description. Summaries are hard-capped at `SUMMARY_MAX_WORDS`. Image type is detected from magic bytes (JPEG/PNG/WEBP/HEIC). Errors come back as clear reasons in `Reading.error` (bad key, wrong model, 429, 5xx, timeout, SAFETY/RECITATION refusals, cut-off reply); one retry on 429/5xx/network errors only. `session.capture()` logs the reason, keeps the previous text loaded, and returns `{"status":"error","detail":...}`; `/api/capture` still answers HTTP 200 because `camera.ino` treats any other code as an upload failure. `motor_service` fails soft: after 2 failed commands in a row the board counts as offline and commands are skipped for `MOTOR_RETRY_SECONDS` (config.py, 10 s) so playback runs at normal speed without hardware; it logs once on going offline and once on coming back; a failed "all off" is retried once immediately.
- Braille: `data/braille_map.py` holds UEB Grade 1 a–z, numbers (number sign `#` = 3-4-5-6, digits reuse a–j) and single-cell punctuation checked against iceb.org/symbs.html (`' . , ; : ! ? -` and directional quotes “ ”); `dots_to_motors` maps dot N → motor N (layout M1 M4 / M2 M5 / M3 M6). `braille_service.normalize` straightens curly quotes and strips accents; `split_words` returns one string per word with punctuation attached, one character per cell (`'He said, "Take 2."'` → `['He', 'said,', '“Take', '#2.”']`). Other symbols are dropped. Line breaks split sentences.
- Motor GPIOs: M1–M6 = GPIO 26, 27, 14, 12, 13, 33. Motors are driven through transistors + flyback diodes on a separate supply; ESP32 GND must share ground with motor supply.
- `motor_service.send_motor_state` accepts `speak_char`, but `session_service` never passes it yet. The ESP32 blocks on WAV playback inside the request, so the 1.5s client timeout can trip on audio.

## Gotchas

- Motor ESP32 was replaced (Oct 2026) with a new board whose USB works, so it can be flashed and monitored over USB. Its MAC differs from the old board's (`b0-cb-d8-5c-8f-ac`, broken USB): set `ESP32_CONTROLLER_MAC` in config.py to the new one (shown as `MAC: …` in the Arduino IDE upload log) or auto-discovery won't find it.
- Old copies of files (previous dashboard, pre-Gemini-rewrite services, firmware template, older phone page) live in `stale/` under their original relative paths. Nothing uses them; don't edit them by mistake. Live: `backend/services/*.py`, `frontend/app.js|index.html|style.css`, `mobile upload/mobile_upload.html`, `esp32/camera/camera.ino`.
- `backend/requirements.txt` pins the tested versions (Python 3.12); `requests` is only for `testmotors.py` / `test_speaker.py`.
- `README.md` is partly outdated (describes OCR/AI as mocked). `Antigravity_context.md` is a more recent status/handoff doc; it requests incremental, one-subsystem-at-a-time changes, verified in phase order (camera → backend → OCR → AI → Braille → motors → full UI flow). Trust the source over both docs.
