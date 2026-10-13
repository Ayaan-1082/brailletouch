import httpx
from config import ESP32_CONTROLLER_IP


async def send_motor_state(motors: list[bool], speak_char: str = "") -> None:
    """
    Sends the 6 motor on/off states, plus which character to speak (if any),
    to the ESP32 motor-controller board in one request. speak_char is a
    single lowercase letter/digit, or "" if this cell has no audio (e.g.
    punctuation, the number-sign marker).

    Fails soft: if the ESP32 isn't reachable, this logs a message and lets
    the session continue in mock mode instead of crashing the backend.
    """
    url = f"http://{ESP32_CONTROLLER_IP}/motors"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            await client.post(url, json={"motors": motors, "character": speak_char})
    except Exception as e:
        print(f"[motor_service] Could not reach ESP32 controller ({type(e).__name__}: {e}) — "
              f"continuing without hardware.")
