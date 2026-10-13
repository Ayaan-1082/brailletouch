"""
Session/playback check — no hardware, Gemini or server needed.

Run from inside the backend/ folder:
    python test_session.py

Fakes the motor board and the dashboard, shortens the timings, and checks
the bugs that used to break the demo: crash at the end of the text, Start
after the end, Next past the end, motors left buzzing after Next/Previous/
Repeat, and two play loops after a quick Pause -> Start.
"""

import asyncio

from services import session_service, motor_service
from data.braille_map import dots_to_motors
from services.session_service import SessionManager, OFF

session_service.MOTOR_ON_DURATION = 0.02
session_service.PAUSE_BETWEEN_CHARACTERS = 0.01
session_service.WORD_PAUSE = 0.01

sent = []          # every motor pattern "sent to the board"
states = []        # every state broadcast to the dashboard


async def fake_motors(motors, speak_char=""):
    sent.append(list(motors))


async def fake_broadcast(state):
    states.append(state)


motor_service.send_motor_state = fake_motors


def letters_played():
    """Cells whose dot pattern was switched on, in order (letters win over
    digits/punctuation that share a pattern)."""
    from data.braille_map import BRAILLE_MAP
    by_pattern = {tuple(dots_to_motors(d)): ch.upper() for ch, d in BRAILLE_MAP.items() if ch.isalpha()}
    for ch, d in BRAILLE_MAP.items():
        by_pattern.setdefault(tuple(dots_to_motors(d)), ch)
    return "".join(by_pattern[tuple(m)] for m in sent if m != OFF)


async def main():
    s = SessionManager(fake_broadcast)

    # nothing captured yet
    assert (await s.start())["status"] == "error"
    assert (await s.next())["status"] == "error"

    # play to the end: no crash, stops, motors off, dashboard state still valid
    await s.load_text("raw", "Hi. Go.")
    await s.start()
    await s._task
    assert letters_played() == "HI.GO.", letters_played()      # full stops are cells too
    assert not s.state.is_playing and s.finished and sent[-1] == OFF
    assert states[-1]["isPlaying"] is False and states[-1]["character"] == "."

    # Start after the end replays from the beginning
    sent.clear()
    await s.start()
    await s._task
    assert letters_played() == "HI.GO.", letters_played()

    # Next past the end: no error, stays on the last letter, motors end off
    assert await s.next() is None
    await s._task
    assert s.state.character == "." and sent[-1] == OFF

    # Previous crosses back into the previous sentence's last cell
    await s.previous()          # . -> O
    await s.previous()          # O -> G
    await s.previous()          # G -> . (end of "Hi.")
    await s._task
    assert s.state.character == "." and s.state.sentence_index == 0 and sent[-1] == OFF

    # Repeat while paused pulses the current letter, then turns motors off
    sent.clear()
    await s.repeat()
    await s._task
    # one pulse of the current letter; the safety net may send OFF twice
    assert sent[0] == dots_to_motors(s.state.dots) and all(m == OFF for m in sent[1:]), sent

    # Pause -> Start quickly: exactly one play loop, motors off after pause
    await s.load_text("raw", "Hello there.")
    await s.start()
    await asyncio.sleep(0.03)
    await s.pause()
    assert not s.state.is_playing and sent[-1] == OFF
    await s.start()
    others = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    assert others == [s._task], others
    await s._task
    assert s.finished and sent[-1] == OFF

    print("All session checks passed.")


asyncio.run(main())
