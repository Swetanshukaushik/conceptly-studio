// Pure helpers for the explainer kit (no three.js, so node can test them): camera tours and
// pop-word timing against the narration.

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
export const normWord = (s) => String(s ?? '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '');

// Finds the spoken moment of `word` inside [t0, t1] (absolute seconds) and returns scene-local at/until.
// `occurrence` picks the 1st, 2nd... match when a word is said more than once.
export function popTiming(words, word, t0, t1, hold = 0.9, occurrence = 1) {
  const want = normWord(word); if (!want || !words) return null;
  let seen = 0;
  for (const w of words) {
    if (w.t0 < t0 - 1e-6 || w.t0 >= t1) continue;
    if (normWord(w.w) === want && ++seen === occurrence) return { at: Math.max(0, w.t0 - t0 - 0.04), until: Math.max(0, w.t0 - t0 - 0.04) + hold };
  }
  return null;
}

// Cubic Hermite through waypoints with time-aware Catmull-Rom tangents; the camera eases to rest at both ends.
function hermite(ts, vs, t) {
  const n = ts.length; if (t <= ts[0]) return vs[0]; if (t >= ts[n - 1]) return vs[n - 1];
  let i = 0; while (i < n - 2 && t > ts[i + 1]) i++;
  const dt = ts[i + 1] - ts[i], u = (t - ts[i]) / dt;
  const tan = (k) => (k <= 0 || k >= n - 1 ? 0 : (vs[k + 1] - vs[k - 1]) / (ts[k + 1] - ts[k - 1]));
  const m0 = tan(i) * dt, m1 = tan(i + 1) * dt, u2 = u * u, u3 = u2 * u;
  return (2 * u3 - 3 * u2 + 1) * vs[i] + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * vs[i + 1] + (u3 - u2) * m1;
}

// waypoints: [{at, position:[x,y,z], target:[x,y,z], fov?}] with `at` in scene seconds. Returns per-axis functions of (ctx).
export function makeTour(waypoints, warn = () => {}) {
  const pts = (waypoints || []).filter((w) => Number.isFinite(Number(w.at)) && Array.isArray(w.position) && Array.isArray(w.target) && w.position.length === 3 && w.target.length === 3)
    .map((w) => ({ at: Number(w.at), position: w.position.map(Number), target: w.target.map(Number), fov: w.fov === undefined ? undefined : Number(w.fov) }))
    .sort((a, b) => a.at - b.at);
  if (pts.length < 2) { warn('camera.tour needs at least 2 waypoints with at, position [x,y,z] and target [x,y,z] (numbers)'); return null; }
  for (let i = 1; i < pts.length; i++) if (pts[i].at - pts[i - 1].at < 0.2) { warn('camera.tour waypoints must be at least 0.2 s apart'); return null; }
  if (pts.some((p) => p.position.concat(p.target).some((v) => !Number.isFinite(v)))) { warn('camera.tour positions and targets must be plain numbers'); return null; }
  const ts = pts.map((p) => p.at);
  const axis = (key, k) => { const vs = pts.map((p) => p[key][k]); return (c) => hermite(ts, vs, c.t); };
  const fovs = pts.map((p) => p.fov ?? 40);
  return { pos: [axis('position', 0), axis('position', 1), axis('position', 2)], tgt: [axis('target', 0), axis('target', 1), axis('target', 2)], fov: (c) => clamp(hermite(ts, fovs, c.t), 15, 80), span: [ts[0], ts[ts.length - 1]] };
}

// Mouth openness 0..1 at absolute time T from the narration word timings: each word opens and closes the mouth once per
// syllable (about one per three letters), with a small per-word variation so the motion does not look mechanical.
export function makeVoice(words, cfg = {}) {
  const ws = (words || []).filter((w) => Number.isFinite(w.t0) && Number.isFinite(w.t1) && w.t1 > w.t0);
  const per = cfg.lettersPerSyllable ?? 3, floor = cfg.restOpen ?? 0, sharp = cfg.sharpness ?? 0.7;
  let last = 0;
  return (T) => {
    // words are sorted by time: continue from the last hit when time moves forward, else binary search
    let lo = 0, hi = ws.length - 1, hit = -1;
    while (lo <= hi) { const mid = (lo + hi) >> 1; if (T < ws[mid].t0) hi = mid - 1; else if (T >= ws[mid].t1) lo = mid + 1; else { hit = mid; break; } }
    if (hit < 0) return floor;
    last = hit; const w = ws[hit], u = (T - w.t0) / (w.t1 - w.t0), letters = String(w.w).replace(/[^\p{L}\p{N}]/gu, '').length || 1;
    const syl = Math.max(1, Math.round(letters / per)), vary = 0.65 + 0.35 * (((hit * 7919) % 13) / 12);
    const env = Math.sin(Math.PI * u) ** 0.5;   // fade in and out of the word so consecutive words do not clip
    return floor + (1 - floor) * Math.pow(Math.abs(Math.sin(Math.PI * u * syl)), sharp) * vary * env;
  };
}
