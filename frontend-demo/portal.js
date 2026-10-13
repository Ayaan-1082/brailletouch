// Hero and nav behaviour only. The console logic lives in app.js.

// Phone QR panel under the nav.
const qrToggle = document.getElementById("qrToggle");
const qrPanel = document.getElementById("qrPanel");
qrToggle.onclick = () => {
  qrPanel.hidden = !qrPanel.hidden;
  qrToggle.setAttribute("aria-expanded", String(!qrPanel.hidden));
};
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !qrPanel.hidden) { qrToggle.click(); qrToggle.focus(); }
});

// The hero "photograph": a macro field of Braille cells. Most raised dots are bone, a few are amber or
// teal, so the interface accents come from the picture. Deterministic, so it never changes between loads.
(function buildField() {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 1600 900");
  svg.setAttribute("preserveAspectRatio", "xMidYMid slice");
  let seed = 7;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const PITCH = 36, CELL_W = 108, CELL_H = 144;
  for (let r = 0; r < 7; r++) {
    for (let c = 0; c < 16; c++) {
      for (let i = 0; i < 6; i++) {
        const dot = document.createElementNS(NS, "circle");
        dot.setAttribute("cx", 30 + c * CELL_W + (i < 3 ? 0 : PITCH));
        dot.setAttribute("cy", 30 + r * CELL_H + (i % 3) * PITCH);
        dot.setAttribute("r", 11);
        const raised = rnd() < 0.5;
        const pick = rnd();
        dot.setAttribute("class", !raised ? "o" : pick < 0.1 ? "a" : pick < 0.2 ? "t" : "b");
        svg.appendChild(dot);
      }
    }
  }
  document.getElementById("portalImg").appendChild(svg);
})();

// The portal. Every value is a function of scroll position, so it plays backwards on the way up.
// Without .portal-live (reduced motion) the CSS already shows the finished hero.
(function portal() {
  if (!document.documentElement.classList.contains("portal-live")) return;
  const root = document.querySelector(".portal");
  const img = document.getElementById("portalImg");
  const wash = root.querySelector(".portal-wash");
  const [panelL, panelR] = root.querySelectorAll(".portal-panel");
  const [dotA, dotB] = root.querySelectorAll(".portal-dot");
  const title = document.getElementById("portalTitle");
  const [first, last] = title.children;

  const clamp = (v) => Math.min(1, Math.max(0, v));
  const ease = (t) => t * t * (3 - 2 * t);

  function draw() {
    const range = root.offsetHeight - window.innerHeight;
    const p = clamp((window.scrollY - root.offsetTop) / range);
    const open = ease(clamp(p / 0.8));          // panels, image and dots finish at 80% of the hero
    const w1 = first.offsetWidth, w2 = last.offsetWidth;   // read before writing

    panelL.style.transform = `translateX(${-open * 110}%)`;
    panelR.style.transform = `translateX(${open * 110}%)`;
    img.style.transform = `scale(${1.15 - 0.15 * open})`;
    wash.style.opacity = 0.3 * open;
    dotA.style.transform = `translate(${-open * 42}vw, ${-open * 34}vh)`;
    dotB.style.transform = `translate(${open * 42}vw, ${open * 34}vh)`;

    // the title grows and tightens at the same time while its halves travel apart
    title.style.transform = `scale(${1 + 0.28 * p})`;
    title.style.letterSpacing = `${-0.02 - 0.03 * p}em`;
    first.style.transform = `translateX(${-w1 * 0.5 * p}px)`;
    last.style.transform = `translateX(${w2 * 0.5 * p}px)`;
  }
  addEventListener("scroll", draw, { passive: true });
  addEventListener("resize", draw);
  draw();
})();
