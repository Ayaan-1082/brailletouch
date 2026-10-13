# Central timing configuration — all durations in seconds.
# Nothing else in the codebase should hardcode timing; change it here.

MOTOR_ON_DURATION = 1.2          # how long a Braille cell stays vibrating
PAUSE_BETWEEN_CHARACTERS = 0.4   # gap after motors turn off, before next char
WORD_PAUSE = 0.6                 # extra pause when moving to a new word

# IP address of the ESP32 motor-controller board on your local network.
# The ESP32 prints this to Serial on boot — copy it here.
ESP32_CONTROLLER_IP = "10.205.125.91"
# The board's fixed hardware ID. If the IP above stops answering, `python main.py`
# finds the board on the current network by this MAC and rewrites the IP above.
ESP32_CONTROLLER_MAC = "b0-cb-d8-5c-8f-ac"
MOTOR_RETRY_SECONDS = 10         # board offline: skip motor commands this long, then try again

# IP address of the ESP32-CAM on your local network. It also prints this
# to Serial on boot. Used to remotely trigger a capture from the dashboard.
ESP32_CAMERA_IP = "192.168.81.188"

# Host/port for this backend itself
HOST = "0.0.0.0"
PORT = 8000

# Gemini API (used by services/gemini_service.py). Get a free key from aistudio.google.com.
# Check the current Flash-Lite model name there before running — model names
# get versioned over time.
GEMINI_API_KEY = "PASTE_YOUR_GEMINI_API_KEY_HERE"
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_TIMEOUT = 30            # seconds to wait for Gemini's answer
SUMMARY_MAX_WORDS = 15         # longest summary / scene sentence played (~8 s per word on the device)
