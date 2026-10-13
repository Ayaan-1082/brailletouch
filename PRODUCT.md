# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The team operating BrailleTouch on a laptop at the Zéphyr 2026 AI Hackathon (Microsoft AI Innovators Hub, problem statement PS-10), while judges and visitors watch the screen and the device. The operator uploads a photo from a phone, presses Start, and the audience follows what the six motors are playing. Blind and low-vision people are the end beneficiaries of the device, but they are not the operators of this dashboard (confirmed).

## Product Purpose

BrailleTouch is a hardware prototype that turns a photo of any printed page, or of the user's surroundings, into Braille the user feels on six coin vibration motors. The dashboard is the live control console for that device: it shows the text Gemini read, the short summary that is played, the sentence being read, the current Braille cell and which motors are on, and playback controls. Success is a judge understanding in seconds what the device is doing right now and trusting that the screen matches the motors.

## Positioning

A photo of any page becomes Braille you can feel, on a low-cost device built from off-the-shelf parts (ESP32 boards, coin motors, Python, one Gemini call). Reading apps such as Seeing AI and Lookout speak the page; refreshable Braille displays cost US$799 and up; BrailleTouch is touch output from a camera photo on cheap hardware (confirmed as the headline claim).

## Operating Context

Run from `backend/` with `python main.py`; the dashboard is `frontend/index.html` opened in a browser on the same laptop, talking to the FastAPI backend at `localhost:8000` over WebSocket. The operator's phone, the laptop and the ESP32 motor board share one Wi-Fi hotspot. The phone uploads photos at `/upload`, reached by scanning a QR code shown in the dashboard. Playback is one Braille cell at a time: each cell is felt for 1.2 seconds, with a pause between cells and words.

## Capabilities and Constraints

- The dashboard must keep every control and data field: Capture (ESP32-CAM, parked), Start, Pause, Previous, Next, Repeat, the phone QR code, detected text, AI summary, current sentence, the Braille cell, the six motor states, and word/character progress (confirmed).
- The drawn Braille cell, the highlighted letter and the motor states must always match the UEB patterns the motors are playing (confirmed). Dots are numbered 1-2-3 down the left and 4-5-6 down the right; dot N drives motor N.
- Content shown comes from one Gemini call: the exact text on a page plus a summary of at most 15 words, or a one-sentence scene description when the photo has no text. Numbers play as the UEB number sign plus a letter; punctuation plays as its own cell.
- The dashboard is plain HTML, CSS and JavaScript with no build step; `app.js` depends on fixed element IDs and on the WebSocket state message keys (`ocrText`, `summary`, `sentence`, `word`, `character`, `dots`, `motors`, `wordIndex`, `totalWords`, `isPlaying`, and the rest of `to_dict()`).
- Speaker output, the ESP32-CAM path, and a multi-cell raised-dot display are planned and not part of the dashboard today.

## Brand Commitments

The name is "BrailleTouch". The Braille letter "b" (dots 1 and 2) appears as the dashboard's brand mark in the current demo; this has not been confirmed as a binding identity.

## Evidence on Hand

- Real prototype photos of the six-motor board in `ppt/` (WhatsApp Image files).
- A submitted hackathon deck, `ppt/BrailleTouch_Zephyr2026_v5.pptx`, with the claims and sources used for the device.
- Backend checks that pass without hardware: `test_braille_engine.py`, `test_session.py`, `test_fake_board.py`, `test_gemini_offline.py`, `test_capture_offline.py`.
- Two demo dashboards were built and shown in `frontend-demo/` (dark and light themes) and have not yet replaced `frontend/`. No user testing, usage data or testimonials exist; none may be invented.

## Product Principles

1. The screen must never disagree with the motors: what is drawn is what is felt.
2. A judge should understand the current state, what is being read and which cell is playing, within a few seconds of looking.
3. Plain, truthful words about a working prototype; planned features are labelled as planned.
4. Every control stays available and obvious during a live demo; failures say what went wrong.

## Accessibility & Inclusion

The product serves blind and low-vision people through the device, so the dashboard should itself be legible and usable by keyboard. No specific standard (such as WCAG AA) was set by the user; this is an open decision.
