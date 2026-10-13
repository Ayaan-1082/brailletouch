"""
Camera trigger service — tells the ESP32-CAM to take a photo remotely, so
the dashboard's Capture button can act as the real trigger instead of the
camera's own physical button.

This does NOT return the photo or the OCR result — it just fires the
request. The ESP32-CAM captures on its own and separately POSTs the real
JPEG to this backend's /api/capture endpoint, which is what actually runs
OCR/AI and updates the session. This function just kicks that off.
"""

import httpx
from config import ESP32_CAMERA_IP


async def trigger_capture() -> bool:
    url = f"http://{ESP32_CAMERA_IP}/capture"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url)
        return response.status_code == 200
    except Exception as e:
        print(f"[camera_service] Could not reach ESP32-CAM ({e}) — "
              f"is it powered on and on the same WiFi?")
        return False
