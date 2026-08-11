/**
 * A small, dependency-free confetti burst — the payoff moment at the end of
 * a roulette spin. Deliberately simple (CSS-animated divs, not canvas):
 * this fires once per spin, so the perf ceiling that would justify canvas
 * never applies, and CSS animations respect `prefers-reduced-motion`
 * automatically via the stylesheet rule in roulette.css.
 */

const COLORS = ["#ff6b6b", "#f4b942", "#4ade80", "#4ea8de"];

export function fireConfetti(pieceCount = 80) {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const layer = document.createElement("div");
  layer.className = "confetti-layer";
  document.body.appendChild(layer);

  for (let i = 0; i < pieceCount; i++) {
    const piece = document.createElement("span");
    piece.className = "confetti-piece";
    piece.style.left = `${Math.random() * 100}%`;
    piece.style.backgroundColor = COLORS[i % COLORS.length];
    piece.style.animationDuration = `${1.8 + Math.random() * 1.2}s`;
    piece.style.animationDelay = `${Math.random() * 0.4}s`;
    piece.style.transform = `rotate(${Math.random() * 360}deg)`;
    layer.appendChild(piece);
  }

  window.setTimeout(() => layer.remove(), 3500);
}
