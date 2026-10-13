import httpx
from config import ESP32_CONTROLLER_IP


async def send_motor_state(motors: list[bool]) -> None:
    """
    Sends the 6 motor on/off states to the ESP32 motor-controller board.

    Fails soft: if the ESP32 isn't reachable (e.g. while doing pure Phase
    2/3 development on the dashboard with no hardware plugged in), this
    logs a message and lets the session continue in mock mode instead of
    crashing the backend.
    """
    url = f"http://{ESP32_CONTROLLER_IP}/motors"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            await client.post(url, json={"motors": motors})
    except Exception as e:
        print(f"[motor_service] Could not reach ESP32 controller ({e}) — "
              f"continuing without hardware.")
