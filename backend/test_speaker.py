"""
Standalone speaker test — talks directly to the ESP32 motor controller's
/motors endpoint, bypassing the backend entirely. Useful for testing audio
playback on its own, separate from OCR/AI/motor logic.

Run from anywhere (only needs the 'requests' package: pip install requests):
    python test_speaker.py 192.168.1.50
(replace with your ESP32 controller's actual current IP)
"""

import sys
import time
import requests

if len(sys.argv) != 2:
    print("Usage: python test_speaker.py <esp32_ip>")
    sys.exit(1)

ESP32_IP = sys.argv[1]
URL = f"http://{ESP32_IP}/motors"


def speak(character: str):
    try:
        r = requests.post(
            URL,
            json={"motors": [False] * 6, "character": character},
            timeout=5,  # audio playback blocks the ESP32 until the clip finishes
        )
        return r.status_code == 200
    except Exception as e:
        print(f"  Request failed: {e}")
        return False


print(f"Testing speaker against {URL}\n")

# Test a handful of letters and digits first
for ch in ["a", "b", "m", "z", "1", "9", "0"]:
    print(f"Playing '{ch}'...", end=" ")
    ok = speak(ch)
    print("(sent)" if ok else "(FAILED to send)")
    input("  Did you hear it clearly? Press Enter to continue...")

print("\nNow testing the full alphabet + digits back to back:")
for ch in "abcdefghijklmnopqrstuvwxyz0123456789":
    print(f"  {ch}", end=" ", flush=True)
    speak(ch)
    time.sleep(0.2)  # small gap so clips don't overlap oddly

print("\n\nDone. Any letters that were silent or wrong likely mean that")
print("specific .wav file is missing or misnamed in the ESP32's LittleFS —")
print("check Serial Monitor for 'Missing audio file' messages during this run.")
