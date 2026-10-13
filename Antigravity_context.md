# BrailleTouch — Antigravity Project Context

## 1. PROJECT OVERVIEW

BrailleTouch is a hardware + software prototype that takes text captured by a camera, processes it with OCR and AI, converts the result into Braille, and represents Braille characters using six vibration motors.

The intended architecture is:

ESP32-CAM
    ↓
Wi-Fi
    ↓
FastAPI Backend
    ↓
OCR
    ↓
AI Summarization
    ↓
Braille Conversion
    ↓
Motor ESP32
    ↓
6 Vibration Motors

The project is being developed incrementally and hardware is being tested independently before integrating the complete pipeline.

---

# 2. CURRENT PROJECT STRUCTURE

brailletouch/
├── README.md
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── data/
│   │   └── braille_map.py
│   ├── services/
│   │   ├── ocr_service.py
│   │   ├── ai_service.py
│   │   ├── braille_service.py
│   │   ├── motor_service.py
│   │   └── session_service.py
│   └── models/
│       └── session.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── esp32/
    ├── camera/
    │   └── camera.ino
    └── controller/
        └── motor_controller.ino

---

# 3. HARDWARE STATUS

## 3.1 Motor ESP32

The motor controller is an ESP32 development board.

Motor GPIO mapping:

M1 → GPIO26
M2 → GPIO27
M3 → GPIO14
M4 → GPIO12
M5 → GPIO13
M6 → GPIO33

Physical motor arrangement:

M1   M4
M2   M5
M3   M6

Braille dot arrangement:

1   4
2   5
3   6

Therefore:

M1 = Braille dot 1
M2 = Braille dot 2
M3 = Braille dot 3
M4 = Braille dot 4
M5 = Braille dot 5
M6 = Braille dot 6

The motor controller firmware uses HTTP POST:

POST /motors

JSON:

{
  "motors": [true, false, false, ...]
}

The ESP32 sets the corresponding GPIOs HIGH/LOW.

---

## 3.2 Motor hardware

The vibration motors are powered from a separate motor power supply.

They are NOT powered directly from ESP32 GPIO pins.

Each motor uses a transistor switching circuit and flyback diode.

Important wiring requirement discovered during testing:

- ESP32 GND must connect to motor power negative/common ground.
- Breadboard left/right positive rails must be electrically bridged.
- Breadboard left/right negative rails must be electrically bridged.
- All transistor emitters connect to common ground.
- Motor positive connects to motor power positive.
- Motor negative connects to transistor collector.
- Diode striped/banded end connects to motor power positive.
- Other diode end connects to motor negative/collector side.

The exact physical transistor leg order depends on the transistor model and must NOT be assumed without knowing the transistor part number.

---

# 4. MOTOR ESP32 USB ISSUE

The onboard USB/CP2102 interface of the motor ESP32 development board is broken.

Windows previously showed:

USB\DEVICE_DESCRIPTOR_FAILURE
Code 43

Multiple cables, ports and PCs were tested.

The ESP32 itself works correctly over Wi-Fi.

Do NOT waste time repeatedly reinstalling drivers.

Wi-Fi should be used for motor testing.

Motor ESP32 MAC address:

b0-cb-d8-5c-8f-ac

Its IP is assigned dynamically by the phone hotspot and can change after reconnecting.

Always determine its current IP before testing.

The backend config value:

ESP32_CONTROLLER_IP

must contain the motor ESP32's CURRENT IP.

---

# 5. MOTOR TESTING STATUS

The complete six-motor hardware test has been performed successfully.

The original issue was caused by:

1. Missing common ground.
2. Breadboard power rails not being bridged between left and right sides.

After fixing those, the motors physically vibrated correctly.

The direct motor test script exists as:

testmotors.py

The backend → Braille → motor path has also been designed and tested incrementally.

---

# 6. BRAILLE ENGINE

The project uses UEB Grade 1 alphabet mapping.

Current mapping:

a → [1]
b → [1,2]
c → [1,4]
d → [1,4,5]
e → [1,5]
f → [1,2,4]
g → [1,2,4,5]
h → [1,2,5]
i → [2,4]
j → [2,4,5]
k → [1,3]
l → [1,2,3]
m → [1,3,4]
n → [1,3,4,5]
o → [1,3,5]
p → [1,2,3,4]
q → [1,2,3,4,5]
r → [1,2,3,5]
s → [2,3,4]
t → [2,3,4,5]
u → [1,3,6]
v → [1,2,3,6]
w → [2,4,5,6]
x → [1,3,4,6]
y → [1,3,4,5,6]
z → [1,3,5,6]

The Braille service converts characters into six boolean motor states in dot order:

[dot1, dot2, dot3, dot4, dot5, dot6]

Do not replace this mapping with a different Braille convention unless explicitly requested.

---

# 7. BACKEND

Backend framework:

FastAPI

Server:

uvicorn

Default:

HOST = "0.0.0.0"
PORT = 8000

The backend contains:

- OCR service
- AI service
- Braille service
- Motor service
- Session service

---

# 8. BACKEND CAPTURE ENDPOINT

Current endpoint:

POST /api/capture

The current implementation reads the raw request body:

image_bytes = await request.body()

and passes it to:

session.capture(image_bytes)

The endpoint is intended to receive raw JPEG bytes.

Current implementation conceptually:

@app.post("/api/capture")
async def capture(request: Request):
    image_bytes = await request.body()
    await session.capture(image_bytes)
    return {"status": "ok"}

---

# 9. CURRENT OCR SERVICE

OCR is implemented using Gemini.

It receives image bytes, base64 encodes the image and sends the image to the Gemini API.

The OCR service expects an actual JPEG image.

IMPORTANT:

Do not expose or print the Gemini API key.

A Gemini API key was previously included in config and should be considered compromised if it was exposed. Use a newly rotated key if needed.

---

# 10. CURRENT AI SERVICE

AI summarization is also implemented using Gemini.

It takes the OCR text and generates a summary.

The AI service is intentionally isolated from the OCR service.

If Gemini fails, the current implementation can fail-soft by using the original text.

---

# 11. SESSION FLOW

The session service approximately works like:

capture image
    ↓
OCR
    ↓
AI summary
    ↓
sentence/word processing
    ↓
Braille conversion
    ↓
motor state
    ↓
broadcast to frontend

During playback:

_update_character()
    ↓
send motor state
    ↓
wait MOTOR_ON_DURATION
    ↓
turn all motors off
    ↓
pause
    ↓
advance

Current timing values:

MOTOR_ON_DURATION = 1.2 seconds
PAUSE_BETWEEN_CHARACTERS = 0.4 seconds
WORD_PAUSE = 0.6 seconds

---

# 12. FRONTEND

The frontend is a dashboard consisting of:

frontend/index.html
frontend/style.css
frontend/app.js

It communicates with the FastAPI backend.

There is a Capture button in the frontend.

IMPORTANT CURRENT LIMITATION:

The frontend Capture button currently sends an empty body to:

POST /api/capture

That is NOT a real camera capture.

The backend expects JPEG bytes, so an empty request causes the real OCR service to fail because there is no image.

The frontend Capture button must eventually trigger the ESP32-CAM capture process.

---

# 13. ESP32-CAM

Camera board:

AI-Thinker ESP32-CAM

Camera sensor:

OV2640

Camera pin mapping:

PWDN_GPIO_NUM     32
RESET_GPIO_NUM    -1
XCLK_GPIO_NUM      0
SIOD_GPIO_NUM     26
SIOC_GPIO_NUM     27
Y9_GPIO_NUM       35
Y8_GPIO_NUM       34
Y7_GPIO_NUM       39
Y6_GPIO_NUM       36
Y5_GPIO_NUM       21
Y4_GPIO_NUM       19
Y3_GPIO_NUM       18
Y2_GPIO_NUM        5
VSYNC_GPIO_NUM    25
HREF_GPIO_NUM     23
PCLK_GPIO_NUM     22

Camera configuration:

PIXFORMAT_JPEG
FRAMESIZE_SVGA
JPEG quality = 12
frame buffer count = 1

Partition scheme:

Huge APP (3MB No OTA/1MB SPIFFS)

---

# 14. ESP32-CAM HARDWARE TEST STATUS

The ESP32-CAM has been completely verified.

It successfully:

- Powers on.
- Accepts firmware.
- Boots.
- Initializes the camera.
- Connects to Wi-Fi.
- Captures JPEG frames.
- Serves captured images through HTTP.
- Provides a working live MJPEG stream.

The ESP32-CAM is therefore considered HARDWARE VERIFIED.

---

# 15. ESP32-CAM NETWORK

Current Wi-Fi:

SSID:
YOUR_WIFI_NAME

Password:
YOUR_WIFI_PASSWORD

Current camera IP observed during testing:

192.168.175.188

IMPORTANT:

The camera IP is DHCP assigned and can change.

Do not hard-code the camera IP permanently without considering DHCP changes.

The laptop during the successful camera test had:

192.168.175.111

Subnet:

255.255.255.0

Both devices were on the same phone hotspot.

The camera was successfully pinged from the laptop.

The live camera stream was successfully opened from Chrome.

---

# 16. ESP32-CAM LIVE STREAM TEST

A temporary firmware was created that exposes:

GET /

and:

GET /stream

The browser successfully displayed the camera feed.

The stream is MJPEG, not H.264.

This was ONLY a diagnostic/test feature.

It is NOT required in the final BrailleTouch architecture unless explicitly requested.

---

# 17. CAMERA ORIENTATION

For the camera stream, these sensor settings were used:

sensor_t *s = esp_camera_sensor_get();
s->set_hmirror(s, 0);
s->set_vflip(s, 0);

This produces normal non-mirrored/non-vertically-flipped orientation.

Keep this behavior when creating the final camera firmware unless there is a reason to change it.

---

# 18. CURRENT CAMERA ARCHITECTURE DECISION

The physical CAPTURE button on the ESP32-CAM is being removed from the design.

Do NOT implement the final system around a physical capture button.

The desired flow is:

Frontend Capture button
        ↓
Backend
        ↓
Request ESP32-CAM to capture
        ↓
ESP32-CAM returns JPEG
        ↓
Backend /api/capture processing
        ↓
OCR
        ↓
AI
        ↓
Braille
        ↓
Motor ESP32

The camera should not independently run OCR or AI.

---

# 19. DESIRED FINAL CAMERA COMMUNICATION

The desired behavior is:

Frontend Capture button
        ↓
POST request to backend
        ↓
Backend asks ESP32-CAM for one JPEG
        ↓
ESP32-CAM captures one frame
        ↓
ESP32-CAM returns raw JPEG
        ↓
Backend passes JPEG to session.capture()
        ↓
OCR and AI processing

The camera should NOT continuously send frames to Gemini.

Continuous streaming is only for optional local preview/debugging.

---

# 20. IMPORTANT IMPLEMENTATION DETAIL

A clean implementation would be:

ESP32-CAM:

GET /capture

returns:

Content-Type: image/jpeg

with the current camera frame.

Backend:

POST /api/capture

should be able to operate in two modes if useful:

1. If a JPEG body is provided:
   process that JPEG directly.

2. If the body is empty:
   request one JPEG from ESP32-CAM using its configured camera IP, then process the returned JPEG.

This allows the existing frontend Capture button to remain simple.

Potential configuration:

CAMERA_IP = "192.168.175.188"

CAMERA_CAPTURE_URL = f"http://{CAMERA_IP}/capture"

However, the IP should ideally be configurable because DHCP can change it.

---

# 21. DO NOT BREAK EXISTING WORKING FEATURES

When modifying the project:

Do NOT break:

- Motor ESP32 HTTP protocol.
- Braille mapping.
- Session playback.
- Existing frontend WebSocket behavior.
- Existing OCR service.
- Existing AI service.
- Motor timing.
- Current motor GPIO mapping.

Make changes incrementally.

Prefer small isolated changes over rewriting the whole project.

---

# 22. CURRENT IMMEDIATE TASK

The next implementation task is:

CONNECT ESP32-CAM TO BACKEND.

Requirements:

1. Remove physical CAPTURE button dependency.
2. Add a simple ESP32-CAM endpoint:

   GET /capture

3. Endpoint captures one JPEG and returns it.
4. Configure backend with the ESP32-CAM IP.
5. Modify backend /api/capture so that an empty frontend request causes the backend to request one JPEG from the ESP32-CAM.
6. Pass that JPEG to the existing session.capture() method.
7. Do not change OCR/AI/Braille logic unnecessarily.
8. Test camera → backend before testing Gemini.
9. Only after camera → backend works, test OCR.
10. Then test AI.
11. Then test complete Braille → motor playback.

---

# 23. TESTING ORDER

Use this exact testing order:

PHASE A
ESP32-CAM camera capture
        ↓
verified already

PHASE B
ESP32-CAM HTTP /capture
        ↓
Laptop requests JPEG
        ↓
verify HTTP 200 + JPEG

PHASE C
Backend requests ESP32-CAM
        ↓
verify backend receives JPEG
        ↓
do not invoke Gemini initially if possible

PHASE D
Backend + real OCR

PHASE E
Backend + AI

PHASE F
OCR + AI + Braille

PHASE G
Braille + Motor ESP32

PHASE H
Frontend Capture button → complete pipeline

Do not skip directly to the full system if an intermediate test fails.

---

# 24. CURRENT VERIFIED NETWORK TOPOLOGY

During the latest successful test:

Phone hotspot
    │
    ├── Laptop
    │     192.168.175.111
    │
    └── ESP32-CAM
          192.168.175.188

The laptop successfully pinged:

192.168.175.188

and successfully opened the ESP32-CAM webpage in Chrome.

Therefore the ESP32-CAM and laptop network connectivity is known to work when both are connected to the same hotspot.

---

# 25. DEVELOPMENT STYLE

Work incrementally.

Do not dump a huge number of steps at once.

For each change:

1. Explain what will change.
2. Give the exact file.
3. Give the exact code change.
4. Tell the developer what command to run.
5. Define the expected output.
6. Wait for confirmation before moving to the next stage.

Do not assume hardware behavior that has not been tested.

Do not change multiple independent subsystems simultaneously.

---

# 26. CURRENT STATUS SUMMARY

MOTOR HARDWARE:
✅ Working

MOTOR ESP32:
✅ Working over Wi-Fi
⚠️ USB interface broken

BRAILLE ENGINE:
✅ Implemented

BACKEND:
✅ Runs successfully

FRONTEND:
✅ Runs
⚠️ Capture button currently sends empty request

ESP32-CAM:
✅ Working
✅ Camera initialized
✅ JPEG capture verified
✅ Wi-Fi verified
✅ Browser image verified
✅ MJPEG stream verified

ESP32-CAM → BACKEND:
⏳ NEXT TASK

BACKEND → OCR:
⏳ After camera/backend connection

OCR → AI:
⏳ After OCR verification

AI → BRAILLE → MOTORS:
⏳ Complete integration test

---

# 27. IMPORTANT RULE FOR ANTIGRAVITY

Before modifying code, inspect the existing files.

Do not assume the repository is identical to this document if the actual source code differs.

Use the actual current source code as the authority for implementation details.

Preserve working functionality.

When uncertain, stop and ask rather than inventing hardware pin assignments, API behavior, or project architecture.