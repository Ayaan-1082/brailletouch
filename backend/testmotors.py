"""
Phase 4 verification script — cycles each of the 6 motors on/off, one at a
time, talking directly to the ESP32 motor controller. This bypasses the
backend and Braille logic entirely, so if a motor doesn't fire here, the
problem is in the wiring or the ESP32 firmware — not in Python.

Run from anywhere (only needs the 'requests' package: pip install requests):
    python test_motors.py 192.168.1.50
(replace with your ESP32 controller's actual IP, printed on its Serial Monitor)
"""

import sys
import time
import requests

if len(sys.argv) != 2:
    print("Usage: python test_motors.py <esp32_ip>")
    sys.exit(1)

ESP32_IP = sys.argv[1]
URL = f"http://{ESP32_IP}/motors"
ON_DURATION = 2.0

def set_motors(states: list[bool]):
    try:
        r = requests.post(URL, json={"motors": states}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"  Request failed: {e}")
        return False

def all_off():
    set_motors([False] * 6)

print(f"Testing 6 motors against {URL}\n")
all_off()

for i in range(6):
    states = [False] * 6
    states[i] = True
    print(f"Motor {i + 1}: ON", end=" ")
    ok = set_motors(states)
    print("(sent)" if ok else "(FAILED to send)")
    time.sleep(ON_DURATION)
    all_off()
    time.sleep(0.3)
    input(f"  Did Motor {i + 1} physically vibrate? Press Enter to continue...")

print("\nDone. Review above for any motor that didn't respond as expected —")
print("check its transistor wiring and confirm its GPIO number matches")
print("motorPins[] in motor_controller.ino.")
