// Point these at your backend. If you're running the backend locally on
// your laptop and opening this file directly in a browser, localhost is
// correct. If your backend runs elsewhere, change both.
const BACKEND_HTTP = "http://localhost:8000";
const BACKEND_WS = "ws://localhost:8000/ws";

const DOT_ORDER = [1, 4, 2, 5, 3, 6]; // matches the physical layout M1 M4 / M2 M5 / M3 M6

const connDot = document.getElementById("connDot");
const connLabel = document.getElementById("connLabel");
const ocrText = document.getElementById("ocrText");
const summaryText = document.getElementById("summaryText");
const sentenceText = document.getElementById("sentenceText");
const currentWord = document.getElementById("currentWord");
const currentChar = document.getElementById("currentChar");
const brailleCell = document.getElementById("brailleCell");
const motorList = document.getElementById("motorList");
const progressWord = document.getElementById("progressWord");
const progressChar = document.getElementById("progressChar");
const statusMessage = document.getElementById("statusMessage");

let ws = null;
let captureAwaitingResult = false;
let lastSummary = null;   // detects new text arriving from the phone upload page

function setStatus(text, isError = false) {
  statusMessage.textContent = text;
  statusMessage.classList.toggle("status-message--error", isError);
}

function renderMotors(motors) {
  motorList.innerHTML = "";
  motors.forEach((on, i) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span>Motor ${i + 1}</span>
      <span class="motor-state ${on ? "on" : ""}">${on ? "ON" : "OFF"}</span>
    `;
    motorList.appendChild(li);
  });
}

function renderBrailleCell(dots) {
  const dotEls = brailleCell.querySelectorAll(".d");
  dotEls.forEach((el) => {
    const dotNum = parseInt(el.dataset.dot, 10);
    el.classList.toggle("active", dots.includes(dotNum));
  });
}

// Same tokens as backend braille_service.split_words: optional opening quote,
// a word (inner ' or -) or a number (inner . or ,), then trailing punctuation.
const TOKEN = /(")?([a-zA-Z]+(?:['-][a-zA-Z]+)*|\d+(?:[.,]\d+)*)([.,;:!?"]*)/g;

// Where the current Braille cell sits in the sentence text: the word's span and
// the letter's position. The number sign (#) points at the number's first digit.
function cellPosition(sentence, wordIndex, charIndex) {
  const m = [...sentence.matchAll(TOKEN)][wordIndex];
  if (!m) return null;
  const [all, quote, core, tail] = m;
  const positions = [];
  let p = m.index;
  if (quote) positions.push(p++);
  if (/\d/.test(core[0])) positions.push(p);
  for (let i = 0; i < core.length + tail.length; i++) positions.push(p++);
  const letter = positions[charIndex];
  return letter === undefined ? null : { start: m.index, end: m.index + all.length, letter };
}

// The sentence with the current word emphasised and the current letter highlighted.
// Built from text nodes, so photo text can never inject HTML.
function renderSentence(state) {
  const s = state.sentence || "";
  const pos = s && state.word ? cellPosition(s, state.wordIndex, state.characterIndex) : null;
  if (!pos) {
    sentenceText.textContent = s || "Send a photo to start reading.";
    return;
  }
  const word = document.createElement("span");
  word.className = "cur-word";
  const mark = document.createElement("mark");
  mark.className = "cur-letter";
  mark.textContent = s[pos.letter];
  word.append(s.slice(pos.start, pos.letter), mark, s.slice(pos.letter + 1, pos.end));
  sentenceText.replaceChildren(s.slice(0, pos.start), word, s.slice(pos.end));
  // sentence longer than its three-line window: centre the current word in it
  const clamped = sentenceText.scrollHeight > sentenceText.clientHeight + 1;
  sentenceText.classList.toggle("is-clamped", clamped);
  sentenceText.scrollTop = clamped ? Math.max(0, word.offsetTop - (sentenceText.clientHeight - word.offsetHeight) / 2) : 0;
}

// Playback state, worked out from what the backend already sends (no backend change):
// waiting (no text) / ready (at the very start) / playing / paused / finished (stopped on the last cell).
const STATE_LABEL = { waiting: "Waiting for a photo", ready: "Ready", playing: "Playing", paused: "Paused",
                      finished: "Finished", offline: "Offline" };
function playbackState(state) {
  const sentence = (state.sentence || "").trim();
  if (!sentence || !state.word) return "waiting";
  if (state.isPlaying) return "playing";
  const summary = (state.summary || "").trim();
  const atStart = state.wordIndex === 0 && state.characterIndex === 0 && summary.startsWith(sentence);
  const atEnd = state.wordIndex === state.totalWords - 1 && state.characterIndex === state.totalCharacters - 1 &&
                summary.endsWith(sentence);
  if (atEnd) return "finished";
  return atStart ? "ready" : "paused";
}

const stateChip = document.getElementById("stateChip");
const stateLabel = document.getElementById("stateLabel");
function showState(name) {
  stateChip.dataset.state = name;
  stateLabel.textContent = STATE_LABEL[name];
  // only the button that makes sense right now is the highlighted one
  document.getElementById("btnStart").classList.toggle("btn--primary", name !== "playing");
  document.getElementById("btnPause").classList.toggle("btn--primary", name === "playing");
}

function applyState(state) {
  ocrText.textContent = state.ocrText || "Nothing captured yet.";
  summaryText.textContent = state.summary || "Waiting for a capture.";
  renderSentence(state);
  currentWord.textContent = state.word || "—";
  currentChar.textContent = state.character || "·";
  renderBrailleCell(state.dots || []);
  renderMotors(state.motors || [false, false, false, false, false, false]);
  progressWord.textContent = `Word ${state.word ? state.wordIndex + 1 : 0} of ${state.totalWords ?? 0}`;
  progressChar.textContent = `Character ${state.character ? state.characterIndex + 1 : 0} of ${state.totalCharacters ?? 0}`;
  // the letter's dots glow only while the motors are actually on
  brailleCell.classList.toggle("buzzing", (state.motors || []).some(Boolean));
  const bar = document.getElementById("progressBar");
  showState(playbackState(state));
  if (bar) bar.style.transform = `scaleX(${state.word && state.totalWords ? (state.wordIndex + 1) / state.totalWords : 0})`;
}

function connect() {
  ws = new WebSocket(BACKEND_WS);

  ws.onopen = () => {
    connDot.className = "dot dot--on";
    connLabel.textContent = "Connected";
    document.body.classList.remove("is-offline");
    document.getElementById("offlineBanner").hidden = true;
    // fresh on every (re)connect: the laptop's IP may have changed
    const phoneQr = document.getElementById("phoneQr");
    if (phoneQr) phoneQr.src = `${BACKEND_HTTP}/api/phone-qr.svg?t=${Date.now()}`;
  };

  ws.onmessage = (event) => {
    const state = JSON.parse(event.data);
    applyState(state);
    // new text that didn't come from this page's Capture button = a phone upload
    const newPhoto = lastSummary !== null && state.summary !== lastSummary;
    lastSummary = state.summary;

    // If we were waiting on a real capture result, this update is it —
    // clear the "waiting" message and re-enable the Capture button now
    // that we have a definitive outcome, success or otherwise.
    if (captureAwaitingResult) {
      captureAwaitingResult = false;
      btnCapture.disabled = false;
      btnCapture.classList.remove("btn--pending");
      setStatus(state.ocrText ? "Capture complete." : "Capture returned no readable text.");
    } else if (newPhoto) {
      setStatus("New photo read. Press Start to feel it.");
    } else {
      setStatus("");
    }
  };

  ws.onclose = () => {
    connDot.className = "dot dot--off";
    connLabel.textContent = "Disconnected, retrying…";
    document.body.classList.add("is-offline");
    document.getElementById("offlineBanner").hidden = false;
    showState("offline");
    setStatus("Lost connection to the backend. Retrying…", true);
    setTimeout(connect, 2000);
  };

  ws.onerror = () => ws.close();
}

/**
 * Calls the backend and returns a structured result instead of assuming
 * success. Distinguishes three outcomes:
 *   - networkError: the fetch itself failed (backend not running/unreachable)
 *   - ok=false: backend responded, but with a non-2xx HTTP status
 *   - ok=true, data.status === "error": backend responded 200, but reported
 *     a logical failure in the body (e.g. "could not reach the ESP32-CAM")
 *   - ok=true, data.status !== "error": genuine success
 */
async function callApi(path, button, pendingText) {
  if (pendingText) setStatus(pendingText);
  if (button) {
    button.disabled = true;
    button.classList.add("btn--pending");
  }

  let result;
  try {
    const res = await fetch(`${BACKEND_HTTP}${path}`, { method: "POST" });
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      // no JSON body — fine, some endpoints may not return one
    }
    result = { networkError: false, ok: res.ok, data };
  } catch (e) {
    console.error(`Request to ${path} failed:`, e);
    result = { networkError: true, ok: false, data: null };
  } finally {
    if (button && !captureAwaitingResult) {
      button.disabled = false;
      button.classList.remove("btn--pending");
    }
  }
  return result;
}

function describeFailure(result) {
  if (result.networkError) {
    return "Can't reach the backend. Is 'python main.py' running?";
  }
  if (!result.ok) {
    return "The backend reported an error for that request.";
  }
  if (result.data && result.data.status === "error") {
    return result.data.detail || "The backend reported a problem.";
  }
  return null; // no failure
}

const btnCapture = document.getElementById("btnCapture");

btnCapture.onclick = async () => {
  captureAwaitingResult = true;
  const result = await callApi(
    "/api/trigger-capture",
    btnCapture,
    "Telling the camera to take a photo…"
  );

  const failureMessage = describeFailure(result);
  if (failureMessage) {
    captureAwaitingResult = false;
    btnCapture.disabled = false;
    btnCapture.classList.remove("btn--pending");
    setStatus(failureMessage, true);
    ocrText.textContent = "Capture failed. See the message below.";
    summaryText.textContent = "Capture failed. See the message below.";
    return;
  }

  // Trigger succeeded — the camera is now taking the photo and will
  // upload it separately. Keep the button disabled and the message up
  // until the real result arrives over the WebSocket (handled in
  // ws.onmessage above), since we genuinely don't know the outcome yet.
  ocrText.textContent = "Processing…";
  summaryText.textContent = "Processing…";
  setStatus("Photo taken. Waiting for the camera upload and Gemini…");
};

async function handleControlClick(path, button, pendingText, doneText) {
  const result = await callApi(path, button, pendingText);
  const failureMessage = describeFailure(result);
  if (failureMessage) {
    setStatus(failureMessage, true);
    return;
  }
  setStatus(doneText);
}

document.getElementById("btnStart").onclick = (e) =>
  handleControlClick("/api/start", e.target, "Starting playback…", "Playing…");

document.getElementById("btnPause").onclick = (e) =>
  handleControlClick("/api/pause", e.target, "Pausing…", "Paused.");

document.getElementById("btnPrev").onclick = (e) =>
  handleControlClick("/api/previous", e.target, "Moving to previous character…", "");

document.getElementById("btnNext").onclick = (e) =>
  handleControlClick("/api/next", e.target, "Moving to next character…", "");

document.getElementById("btnRepeat").onclick = (e) =>
  handleControlClick("/api/repeat", e.target, "Repeating current character…", "");

// Theme: dark "slate" or light "paper", remembered on this computer.
const themeToggle = document.getElementById("themeToggle");
function showTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeToggle.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
}
themeToggle.onclick = () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  showTheme(next);
  try { localStorage.setItem("bt-theme", next); } catch (_) {}
};
showTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");

connect();
