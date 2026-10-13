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
  const ws = new WebSocket(BACKEND_WS);

  ws.onopen = () => {
    connDot.className = "dot dot--on";
    connLabel.textContent = "Connected";
  };

  ws.onmessage = (event) => {
    const state = JSON.parse(event.data);
    applyState(state);
    setStatus(""); // clear any "waiting for..." message once real state arrives
  };

  ws.onclose = () => {
    connDot.className = "dot dot--off";
    connLabel.textContent = "Disconnected — retrying…";
    setTimeout(connect, 2000);
  };

  ws.onerror = () => ws.close();
}

async function callApi(path, button, { pendingText, doneText, keepMessage } = {}) {
  if (pendingText) setStatus(pendingText);

  if (button) {
    button.disabled = true;
    button.classList.add("btn--pending");
  }

  try {
    const res = await fetch(`${BACKEND_HTTP}${path}`, { method: "POST" });
    if (!res.ok) throw new Error(`Server responded ${res.status}`);
    if (doneText) setStatus(doneText);
    else if (!keepMessage) setStatus("");
  } catch (e) {
    console.error(`Request to ${path} failed:`, e);
    setStatus("Something went wrong — check the backend is running.", true);
  } finally {
    if (button) {
      button.disabled = false;
      button.classList.remove("btn--pending");
    }
  }
}

const btnCapture = document.getElementById("btnCapture");

btnCapture.onclick = async () => {
  ocrText.textContent = "Processing…";
  summaryText.textContent = "Processing…";
  await callApi("/api/trigger-capture", btnCapture, {
    pendingText: "Telling the camera to take a photo…",
    keepMessage: true, // leave the message up until real OCR/AI results arrive over the WebSocket
  });
  setStatus("Photo sent — waiting for OCR and AI summary…");
};

document.getElementById("btnStart").onclick = (e) =>
  callApi("/api/start", e.target, { pendingText: "Starting playback…", doneText: "Playing…" });

document.getElementById("btnPause").onclick = (e) =>
  callApi("/api/pause", e.target, { pendingText: "Pausing…", doneText: "Paused." });

document.getElementById("btnPrev").onclick = (e) =>
  callApi("/api/previous", e.target, { pendingText: "Moving to previous character…", doneText: "" });

document.getElementById("btnNext").onclick = (e) =>
  callApi("/api/next", e.target, { pendingText: "Moving to next character…", doneText: "" });

document.getElementById("btnRepeat").onclick = (e) =>
  callApi("/api/repeat", e.target, { pendingText: "Repeating current character…", doneText: "" });

connect();
