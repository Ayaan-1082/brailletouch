// Adds "Role" + "How it works" to each node's Semantic Passport (click) and
// tooltip (hover). Archify's schema has no description field, so this
// post-processes the checked HTML into a separate file.
// Run after every finalize:  node add-notes.mjs
import { readFileSync, writeFileSync } from 'node:fs';

const NOTES = {
  dashboard: ['Control panel and live mirror of the device.',
    'Buttons POST to /api/*. A WebSocket on /ws receives the full session state after every change and redraws the text, Braille cell and motor list. Reconnects every 2s if the backend drops.'],
  api: ['Entry point for every request; owns the WebSocket.',
    'FastAPI on :8000. /api/trigger-capture asks the ESP32-CAM to shoot, /api/capture receives the JPEG, and start/pause/next/previous/repeat call SessionManager. broadcast() pushes state to every open dashboard.'],
  camera: ['Takes the photo of the printed page.',
    'On /capture it grabs one 800×600 JPEG from the OV2640, POSTs the raw bytes to the backend\'s /api/capture, and only then replies 200 (500 if capture or upload failed). No OCR on the board.'],
  session: ['Single source of truth for the reading session.',
    'capture(): OCR → summary → sentences → words. The play loop sends a cell to the motors, waits 1.2s, sends all-off, waits 0.4s, then advances char → word → sentence. Every change is broadcast.'],
  gemini: ['Reads the text in the photo and shortens it.',
    'Two generateContent calls (20s timeout each): the base64 JPEG with an OCR prompt, then the text with a "summarize simply" prompt. No OCR → empty text; no summary → raw OCR text is used.'],
  braille: ['Turns letters into dot patterns.',
    'Splits the summary on . ! ?, keeps only letters and apostrophes, looks each letter up in the UEB Grade 1 table (a–z) and maps dot N to motor N as 6 booleans.'],
  motorEsp: ['Executes motor and speaker commands; no Braille logic.',
    'POST /motors {motors: [6 bools], character}. Sets each GPIO HIGH/LOW, then plays /<character>.wav if one was given. Replies 400 on a missing body or bad JSON.'],
  motors: ['The tactile Braille cell.',
    'Six vibration motors laid out as dots 1-2-3 (left) and 4-5-6 (right), switched through transistors with flyback diodes from a separate supply that shares ground with the ESP32.'],
  speaker: ['Speaks the current letter aloud.',
    'Plays a pre-recorded WAV from LittleFS through the internal DAC (GPIO25) into a PAM8403 amp. Currently silent: the session never sends a character.'],
};

const inject = `
<style>
  .node-notes { margin-top: 10px; padding-top: 10px; border-top: 1px solid currentColor; border-top-color: color-mix(in srgb, currentColor 15%, transparent); max-width: 260px; }
  .node-notes h4 { margin: 8px 0 2px; font-size: 10px; letter-spacing: .08em; text-transform: uppercase; opacity: .6; }
  .node-notes h4:first-child { margin-top: 0; }
  .node-notes p { margin: 0; font-size: 12px; line-height: 1.45; }
</style>
<script>
(() => {
  const NOTES = ${JSON.stringify(NOTES)};
  // Hover: native tooltip with the role.
  for (const [id, [role]] of Object.entries(NOTES)) {
    const t = document.querySelector('#node-' + CSS.escape(id) + ' > title');
    if (t) t.textContent += ' — ' + role;
  }
  // Click: extend the passport whenever its focused node changes.
  const idEl = document.getElementById('focus-id');
  const meta = document.getElementById('focus-passport-meta');
  if (!idEl || !meta) return;
  const box = document.createElement('div');
  box.className = 'node-notes';
  meta.after(box);
  const render = () => {
    const n = NOTES[idEl.textContent.trim()];
    box.hidden = !n;
    if (!n) return;
    box.replaceChildren(...[['Role', n[0]], ['How it works', n[1]]].flatMap(([h, p]) => {
      const hEl = document.createElement('h4'); hEl.textContent = h;
      const pEl = document.createElement('p'); pEl.textContent = p;
      return [hEl, pEl];
    }));
  };
  new MutationObserver(render).observe(idEl, { childList: true, characterData: true, subtree: true });
  render();
})();
</script>
`;

const src = 'brailletouch-edge-cases.html';
const out = 'brailletouch-edge-cases.explained.html';
const html = readFileSync(new URL(src, import.meta.url), 'utf8');
if (!html.includes('</body>')) throw new Error('no </body> in ' + src);
writeFileSync(new URL(out, import.meta.url), html.replace(/<\/body>(?![\s\S]*<\/body>)/, inject + '</body>'));
console.log('wrote', out);
