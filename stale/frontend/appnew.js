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

function applyState(state) {
  ocrText.textContent = state.ocrText || "Nothing captured yet.";
  summaryText.textContent = state.summary || "Waiting for a capture.";
  sentenceText.textContent = state.sentence || "—";
  currentWord.textContent = state.word || "—";
  currentChar.textContent = state.character || "—";
  renderBrailleCell(state.dots || []);
  renderMotors(state.motors || [false, false, false, false, false, false]);
  progressWord.textContent = `Word ${state.words ? state.wordIndex + 1 : 0} of ${state.totalWords ?? 0}`;
  progressChar.textContent = `Character ${state.character ? state.characterIndex + 1 : 0} of ${state.totalCharacters ?? 0}`;
}

function connect() {
  ws = new WebSocket(BACKEND_WS);

  ws.onopen = () => {
    connDot.className = "dot dot--on";
    connLabel.textContent = "Connected";
  };

  ws.onmessage = (event) => {
    const state = JSON.parse(event.data);
    applyState(state);

    // If we were waiting on a real capture result, this update is it —
    // clear the "waiting" message and re-enable the Capture button now
    // that we have a definitive outcome, success or otherwise.
    if (captureAwaitingResult) {
      captureAwaitingResult = false;
      btnCapture.disabled = false;
      btnCapture.classList.remove("btn--pending");
      setStatus(state.ocrText ? "Capture complete." : "Capture returned no readable text.");
    } else {
      setStatus("");
    }
  };

  ws.onclose = () => {
    connDot.className = "dot dot--off";
    connLabel.textContent = "Disconnected — retrying…";
    setStatus("Lost connection to the backend — retrying…", true);
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
    return "Can't reach the backend — is 'python main.py' running?";
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
    ocrText.textContent = "Capture failed — see message above.";
    summaryText.textContent = "Capture failed — see message above.";
    return;
  }

  // Trigger succeeded — the camera is now taking the photo and will
  // upload it separately. Keep the button disabled and the message up
  // until the real result arrives over the WebSocket (handled in
  // ws.onmessage above), since we genuinely don't know the outcome yet.
  ocrText.textContent = "Processing…";
  summaryText.textContent = "Processing…";
  setStatus("Photo triggered — waiting for the camera and OCR/AI to finish…");
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

connect();
