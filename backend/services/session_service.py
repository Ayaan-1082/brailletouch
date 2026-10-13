import asyncio
from typing import Callable, Awaitable

from models.session import SessionState
from services import gemini_service, braille_service, motor_service
from data.braille_map import dots_to_motors
from config import MOTOR_ON_DURATION, PAUSE_BETWEEN_CHARACTERS, WORD_PAUSE

OFF = [False] * 6
NOTHING_LOADED = {"status": "error", "detail": "Nothing to play — capture first"}


class SessionManager:
    """The single source of truth for the current reading session.
    Every state change goes through here and is broadcast to the dashboard,
    and (where relevant) pushed to the ESP32 motor controller.

    Invariant: while text is loaded, (sentence_index, word_index,
    character_index) always points at a real letter. Only one motor activity
    (play loop or a single pulse) runs at a time; it always ends motors-off."""

    def __init__(self, broadcast_fn: Callable[[dict], Awaitable[None]]):
        self.state = SessionState()
        self.broadcast = broadcast_fn
        self.finished = False          # played past the last letter
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()    # serialises commands so two can't start two activities
        self._capturing = False        # one photo at a time (double tap, two phones)

    # ---------- Capture / OCR / Summarize ----------

    async def capture(self, image_bytes: bytes) -> dict:
        """One Gemini call, one photo at a time. Returns {"status": "ok", "kind",
        "summary"} or {"status": "error", "detail"}; on failure the previous
        text stays loaded."""
        if self._capturing:
            return {"status": "error", "detail": "A capture is already in progress"}
        self._capturing = True
        try:
            reading = await gemini_service.read_image(image_bytes)
            if reading.error:
                print(f"[capture] {reading.error}")
                return {"status": "error", "detail": reading.error}
            text = reading.text if reading.kind == "text" else "(No text in this photo: describing the scene)"
            await self.load_text(text, reading.summary)
            return {"status": "ok", "kind": reading.kind, "summary": reading.summary}
        finally:
            self._capturing = False

    async def load_text(self, text: str, summary: str) -> None:
        async with self._lock:
            await self._stop()
            s = self.state
            s.ocr_text, s.summary = text, summary
            # sentences with no letters (e.g. "2024.") would be empty cells
            s.sentences = [x for x in braille_service.split_sentences(summary)
                           if braille_service.split_words(x)]
            s.sentence_index = 0
            self.finished = False
            self._load_words()
            await self._broadcast()

    # ---------- Position (never leaves the valid range) ----------

    def _load_words(self, last: bool = False) -> None:
        s = self.state
        s.words = braille_service.split_words(s.sentences[s.sentence_index]) if s.sentences else []
        s.word_index = len(s.words) - 1 if last and s.words else 0
        s.character_index = len(s.words[s.word_index]) - 1 if last and s.words else 0
        self._update_character()

    def _update_character(self) -> None:
        s = self.state
        if not s.words:
            s.character, s.dots, s.total_characters = "", [], 0
            return
        word = s.words[s.word_index]
        ch = word[s.character_index]
        s.total_characters = len(word)
        s.character = ch.upper()
        s.dots, _ = braille_service.char_to_braille(ch)

    def _step(self, delta: int) -> str | None:
        """Move one letter forward (+1) or back (-1). Returns the boundary
        crossed ('char', 'word', 'sentence'), or None at either end, in
        which case the position is unchanged."""
        s = self.state
        if not s.words:
            return None
        if 0 <= s.character_index + delta < len(s.words[s.word_index]):
            s.character_index += delta
            crossed = "char"
        elif 0 <= s.word_index + delta < len(s.words):
            s.word_index += delta
            s.character_index = 0 if delta > 0 else len(s.words[s.word_index]) - 1
            crossed = "word"
        elif 0 <= s.sentence_index + delta < len(s.sentences):
            s.sentence_index += delta
            self._load_words(last=delta < 0)
            return "sentence"
        else:
            return None
        self._update_character()
        return crossed

    # ---------- Motor activity (one at a time) ----------

    async def _broadcast(self) -> None:
        await self.broadcast(self.state.to_dict())

    async def _set_motors(self, motors: list[bool]) -> None:
        # state.motors = what the motors are doing now; state.dots = current letter
        self.state.motors = motors
        await motor_service.send_motor_state(motors)
        await self._broadcast()

    async def _pulse(self) -> None:
        await self._set_motors(dots_to_motors(self.state.dots))
        await asyncio.sleep(MOTOR_ON_DURATION)
        await self._set_motors(OFF)

    async def _play_loop(self) -> None:
        while True:
            await self._pulse()
            await asyncio.sleep(PAUSE_BETWEEN_CHARACTERS)
            crossed = self._step(+1)
            if crossed is None:
                self.finished = True
                return
            if crossed != "char":
                await asyncio.sleep(WORD_PAUSE)

    async def _guard(self, job: Callable[[], Awaitable[None]]) -> None:
        try:
            await job()
        except Exception as e:
            print(f"[session] playback error: {type(e).__name__}: {e}")
        finally:
            self.state.is_playing = False
            await self._set_motors(OFF)

    async def _stop(self) -> None:
        """Cancel the running activity and wait until its motors-off has been sent."""
        task, self._task = self._task, None
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _run(self, job: Callable[[], Awaitable[None]], playing: bool) -> None:
        await self._stop()
        self.state.is_playing = playing
        self._task = asyncio.create_task(self._guard(job))

    # ---------- Playback controls ----------

    async def start(self) -> dict | None:
        async with self._lock:
            if not self.state.words:
                return NOTHING_LOADED
            if self.state.is_playing:
                return None
            if self.finished:                      # replay from the beginning
                self.state.sentence_index = 0
                self._load_words()
                self.finished = False
            await self._run(self._play_loop, playing=True)

    async def pause(self) -> None:
        async with self._lock:
            await self._stop()                     # motors off now; position stays on this letter
            await self._broadcast()

    async def next(self) -> dict | None:
        return await self._jump(+1)

    async def previous(self) -> dict | None:
        return await self._jump(-1)

    async def _jump(self, delta: int) -> dict | None:
        """While playing: jump and keep playing. While paused: jump and pulse once.
        At either end the position stays put and the current letter is pulsed."""
        async with self._lock:
            if not self.state.words:
                return NOTHING_LOADED
            playing = self.state.is_playing
            await self._stop()                     # so the loop can't move the position under us
            self._step(delta)
            self.finished = False
            await self._run(self._play_loop if playing else self._pulse, playing)

    async def repeat(self) -> dict | None:
        async with self._lock:
            if not self.state.words:
                return NOTHING_LOADED
            playing = self.state.is_playing
            await self._run(self._play_loop if playing else self._pulse, playing)
