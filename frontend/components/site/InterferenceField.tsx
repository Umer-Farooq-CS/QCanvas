/**
 * Background texture: horizontal "wires" bent by a two-source interference
 * pattern, with each line's brightness following the fringe intensity where
 * it leaves the frame. Computed on the server (no client JS), coloured by
 * --qc-field via currentColor and faded at the edges by the .qc-field mask.
 */

const W = 1600;
const H = 900;

function buildPaths(lines: number, seed: number) {
  const k = (2 * Math.PI) / 210; // wavelength in px
  const s1 = { x: -260, y: H * 0.36 + seed };
  const s2 = { x: -260, y: H * 0.64 - seed };
  const out: { d: string; o: number }[] = [];
  for (let i = 0; i < lines; i++) {
    const y0 = (H * (i + 0.5)) / lines;
    let d = "";
    for (let x = 0; x <= W; x += 20) {
      const r1 = Math.hypot(x - s1.x, y0 - s1.y);
      const r2 = Math.hypot(x - s2.x, y0 - s2.y);
      // Amplitude grows left to right so the field "develops" across the hero.
      const amp = 2 + 9 * (x / W);
      const dy = amp * (Math.cos(k * r1) + Math.cos(k * r2)) * 0.5;
      d += `${x === 0 ? "M" : "L"}${x} ${(y0 + dy).toFixed(1)}`;
    }
    // Fringe intensity at the right edge: cos^2 of half the path difference.
    const dr = Math.hypot(W - s1.x, y0 - s1.y) - Math.hypot(W - s2.x, y0 - s2.y);
    const intensity = Math.cos((k * dr) / 2) ** 2;
    out.push({ d, o: 0.1 + 0.42 * intensity });
  }
  return out;
}

const HERO = buildPaths(44, 0);
const ALT = buildPaths(36, 40);

export default function InterferenceField({
  variant = "hero",
  className = "",
}: {
  variant?: "hero" | "center";
  className?: string;
}) {
  const paths = variant === "hero" ? HERO : ALT;
  return (
    <div
      aria-hidden="true"
      className={`qc-field ${variant === "center" ? "qc-field--center" : ""} ${className}`}
    >
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" focusable="false">
        <g className="qc-field__drift" fill="none" stroke="currentColor" strokeWidth={1} strokeLinejoin="round">
          {paths.map((p, i) => (
            <path key={i} d={p.d} strokeOpacity={p.o} vectorEffect="non-scaling-stroke" />
          ))}
        </g>
      </svg>
    </div>
  );
}
