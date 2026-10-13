import asyncio
import ipaddress
import re
import subprocess
import time
from pathlib import Path

import httpx
from config import ESP32_CONTROLLER_IP, ESP32_CONTROLLER_MAC, MOTOR_RETRY_SECONDS

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.py"

_failures = 0        # consecutive failed commands
_skip_until = 0.0    # while the board is offline, calls before this time.monotonic() are skipped


# ---------- Finding the board when its IP changed (startup only) ----------

def ip_for_mac(arp_table: str, mac: str) -> str | None:
    """The IPv4 address that `arp -a` lists for this MAC (Windows, macOS and Linux formats)."""
    mac = mac.lower().replace(":", "-")
    for line in arp_table.splitlines():
        if mac in line.lower().replace(":", "-"):
            found = re.search(r"\d+\.\d+\.\d+\.\d+", line)
            if found:
                return found.group()
    return None


async def discover(own_ip: str) -> str | None:
    """Find the board on the laptop's current network by ESP32_CONTROLLER_MAC: knock
    on every address of the /24 at once so the laptop learns who is there, then
    look the MAC up in `arp -a`. Takes about a second."""
    async def knock(ip: str) -> None:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(ip, 80), 0.8)
            writer.close()
        except Exception:
            pass

    net = ipaddress.ip_network(f"{own_ip}/24", strict=False)   # phone hotspots are /24
    await asyncio.gather(*(knock(str(ip)) for ip in net.hosts() if str(ip) != own_ip))
    arp = subprocess.run(["arp", "-a"], capture_output=True, text=True).stdout
    return ip_for_mac(arp, ESP32_CONTROLLER_MAC)


def set_config_ip(text: str, ip: str) -> str:
    """config.py text with only the ESP32_CONTROLLER_IP value replaced."""
    return re.sub(r'^(ESP32_CONTROLLER_IP\s*=\s*")[^"]*(")', rf"\g<1>{ip}\g<2>", text, count=1, flags=re.M)


def save_ip(ip: str) -> None:
    """Write the found board address into config.py (line endings kept), so the next start is instant."""
    with open(CONFIG_FILE, encoding="utf-8", newline="") as f:
        text = f.read()
    with open(CONFIG_FILE, "w", encoding="utf-8", newline="") as f:
        f.write(set_config_ip(text, ip))


async def _post(url: str, body: dict) -> str | None:
    """One request to the board. Returns None on success, else the reason."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(1.5, connect=1.0)) as client:
            r = await client.post(url, json=body)
        return None if r.status_code == 200 else f"HTTP {r.status_code} {r.text.strip()[:60]}"
    except Exception as e:
        return f"{type(e).__name__} {e}".strip()


async def check() -> str | None:
    """Startup check: one all-off command (so motors also start off).
    None = the board answered, else the reason."""
    return await _post(f"http://{ESP32_CONTROLLER_IP}/motors", {"motors": [False] * 6, "character": ""})


async def send_motor_state(motors: list[bool], speak_char: str = "") -> None:
    """
    Sends the 6 motor on/off states, plus which character to speak (if any),
    to the ESP32 motor-controller board in one request. speak_char is a
    single lowercase letter/digit, or "" if this cell has no audio (e.g.
    punctuation, the number-sign marker).

    Fails soft: if the ESP32 isn't reachable the session carries on without
    hardware. After 2 failures in a row the board counts as offline and calls
    are skipped for MOTOR_RETRY_SECONDS, so playback isn't slowed by timeouts;
    then the next command tries again. An "all off" that fails is retried once
    at once, so a single Wi-Fi blip can't leave the motors buzzing.
    """
    global _failures, _skip_until
    if time.monotonic() < _skip_until:
        return

    url = f"http://{ESP32_CONTROLLER_IP}/motors"
    body = {"motors": motors, "character": speak_char}
    reason = await _post(url, body)
    if reason and not any(motors):
        reason = await _post(url, body)

    if reason is None:
        if _failures >= 2:
            print(f"[motor_service] Motor board back online at {ESP32_CONTROLLER_IP}.")
        _failures = 0
        return

    _failures += 1
    if _failures == 2:
        print(f"[motor_service] Motor board not reachable at {ESP32_CONTROLLER_IP} ({reason}): "
              f"playing without hardware, retrying every {MOTOR_RETRY_SECONDS} s.")
    if _failures >= 2:
        _skip_until = time.monotonic() + MOTOR_RETRY_SECONDS
