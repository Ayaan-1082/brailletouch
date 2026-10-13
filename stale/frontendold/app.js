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
  };

  ws.onclose = () => {
    connDot.className = "dot dot--off";
    connLabel.textContent = "Disconnected — retrying…";
    setTimeout(connect, 2000);
  };

  ws.onerror = () => ws.close();
}

async function callApi(path) {
  try {
    await fetch(`${BACKEND_HTTP}${path}`, { method: "POST" });
  } catch (e) {
    console.error(`Request to ${path} failed:`, e);
  }
}

document.getElementById("btnCapture").onclick = () => callApi("/api/trigger-capture");
document.getElementById("btnStart").onclick = () => callApi("/api/start");
document.getElementById("btnPause").onclick = () => callApi("/api/pause");
document.getElementById("btnPrev").onclick = () => callApi("/api/previous");
document.getElementById("btnNext").onclick = () => callApi("/api/next");
document.getElementById("btnRepeat").onclick = () => callApi("/api/repeat");

connect();
