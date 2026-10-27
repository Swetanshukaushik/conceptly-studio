// Deterministic 2D motion simulator for school physics (side view, x right, y up, SI units).
// A scene plan describes bodies, forces, surfaces and joints as data; the simulation is run once when the scene
// is built and then sampled by time, so rendering stays a pure function of time. No DOM or three.js here.
//
// Supported physics:
//   gravity, constant forces, linear/quadratic drag, springs, uniform electric field (qE), uniform magnetic field
//   (q v x B), torque, inverse-square attraction between bodies (orbits), rods and ropes, ropes over a pulley,
//   contacts with straight surfaces (restitution, Coulomb friction, rolling of balls), ball-ball collisions.

const EPS = 1e-9;
const dot = (a, b) => a[0] * b[0] + a[1] * b[1];
const cross = (a, b) => a[0] * b[1] - a[1] * b[0];

export const FIELDS = ['x', 'y', 'vx', 'vy', 'ax', 'ay', 'speed', 'ke', 'pe', 'theta', 'omega'];

export class Sim {
  constructor(spec = {}, warn = () => {}) {
    this.warn = warn;
    this.g = spec.gravity ?? [0, -9.8];
    this.E = spec.fields?.E ?? [0, 0];
    this.B = spec.fields?.B ?? 0;           // out of the screen is positive
    this.nbodyG = spec.nbody?.G ?? 0;       // pairwise attraction G (in the units of the scene)
    this.dt = spec.dt ?? 1 / 960;
    this.sampleDt = 1 / 120;
    this.surfaces = (spec.surfaces || []).map((s) => this.makeSurface(s));
    this.bodies = (spec.bodies || []).map((b, i) => this.makeBody(b, i));
    this.byId = Object.fromEntries(this.bodies.map((b) => [b.id, b]));
    this.springs = (spec.springs || []).map((s) => ({ ...s, a: this.anchor(s.a), b: this.anchor(s.b), k: s.k ?? 10, L0: s.L0 ?? 1, c: s.c ?? 0 }));
    this.joints = (spec.joints || []).map((j) => ({ ...j, a: this.anchor(j.a), b: this.anchor(j.b), type: j.type || 'rod' }));
    this.samples = []; this.duration = 0;
  }

  anchor(a) {
    if (typeof a === 'string') { const b = this.byId?.[a] ?? this.bodies?.find((x) => x.id === a); if (!b) this.warn(`sim: unknown body "${a}"`); return { body: b || null, p: [0, 0] }; }
    if (Array.isArray(a)) return { body: null, p: [a[0], a[1]] };
    this.warn('sim: an anchor must be a body id or [x, y]'); return { body: null, p: [0, 0] };
  }

  makeSurface(s) {
    const [x1, y1] = s.p1, [x2, y2] = s.p2; const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1;
    const t = [dx / L, dy / L]; let n = [-t[1], t[0]]; if (s.flip) n = [-n[0], -n[1]];   // normal points to the free side (left of p1 -> p2)
    return { ...s, p1: [x1, y1], p2: [x2, y2], t, n, L, mu: s.mu ?? 0, e: s.e ?? 0 };
  }

  makeBody(b, i) {
    const kind = b.kind || 'ball';
    const m = b.m ?? 1;
    const r = b.r ?? (kind === 'block' ? (b.size ? b.size[1] / 2 : 0.25) : 0.25);   // contact radius (half height for blocks)
    let I = b.I;
    if (I === undefined) I = kind === 'ball' ? 0.5 * m * r * r : kind === 'ring' ? m * r * r : Infinity;   // blocks and points do not rotate
    return {
      id: b.id ?? `b${i}`, idx: i, kind, m, invM: b.pinned ? 0 : 1 / m, I, invI: b.pinned || !Number.isFinite(I) ? 0 : 1 / I, r,
      rc: b.rc ?? (kind === 'block' && b.size ? b.size[0] / 2 : r),
      x: b.pos?.[0] ?? 0, y: b.pos?.[1] ?? 0, vx: b.vel?.[0] ?? 0, vy: b.vel?.[1] ?? 0,
      th: b.theta ?? 0, om: b.omega ?? 0, q: b.q ?? 0, e: b.restitution ?? 0.9,
      drag: b.drag || {}, forces: b.forces || [], torque: b.torque ?? 0, pinned: !!b.pinned, ax: 0, ay: 0, fx: 0, fy: 0,
      align: kind === 'block', contactAngle: null,
    };
  }

  pointOf(a) { return a.body ? [a.body.x, a.body.y] : a.p; }
  velOf(a) { return a.body ? [a.body.vx, a.body.vy] : [0, 0]; }
  invMOf(a) { return a.body ? a.body.invM : 0; }

  // ---------- forces ----------
  computeForces(time) {
    for (const b of this.bodies) {
      if (b.pinned) { b.fx = b.fy = b.ax = b.ay = 0; continue; }
      let fx = b.m * this.g[0], fy = b.m * this.g[1];
      if (b.q) { fx += b.q * this.E[0]; fy += b.q * this.E[1]; }   // the magnetic part is applied as an exact rotation in run()
      const sp = Math.hypot(b.vx, b.vy);
      if (b.drag.lin) { fx -= b.drag.lin * b.vx; fy -= b.drag.lin * b.vy; }
      if (b.drag.quad) { fx -= b.drag.quad * sp * b.vx; fy -= b.drag.quad * sp * b.vy; }
      for (const f of b.forces) {
        if (time < (f.from ?? 0) || time > (f.to ?? Infinity)) continue;
        fx += f.F[0]; fy += f.F[1];
      }
      b.fx = fx; b.fy = fy;
    }
    if (this.nbodyG) {
      for (let i = 0; i < this.bodies.length; i++) for (let j = i + 1; j < this.bodies.length; j++) {
        const a = this.bodies[i], c = this.bodies[j]; const dx = c.x - a.x, dy = c.y - a.y; const d2 = dx * dx + dy * dy + 1e-6, d = Math.sqrt(d2);
        const F = this.nbodyG * a.m * c.m / d2; const fx = F * dx / d, fy = F * dy / d;
        a.fx += fx; a.fy += fy; c.fx -= fx; c.fy -= fy;
      }
    }
    for (const s of this.springs) {
      const pa = this.pointOf(s.a), pb = this.pointOf(s.b); const dx = pb[0] - pa[0], dy = pb[1] - pa[1], L = Math.hypot(dx, dy) || EPS;
      const ux = dx / L, uy = dy / L; const va = this.velOf(s.a), vb = this.velOf(s.b);
      const F = s.k * (L - s.L0) + s.c * ((vb[0] - va[0]) * ux + (vb[1] - va[1]) * uy);   // tension positive when stretched
      if (s.a.body && !s.a.body.pinned) { s.a.body.fx += F * ux; s.a.body.fy += F * uy; }
      if (s.b.body && !s.b.body.pinned) { s.b.body.fx -= F * ux; s.b.body.fy -= F * uy; }
    }
    for (const b of this.bodies) { b.ax = b.invM * b.fx; b.ay = b.invM * b.fy; }
  }

  // ---------- constraints and contacts ----------
  solveJoints(dt) {
    for (const j of this.joints) {
      let pairs;   // each entry: [anchorA, anchorB, rest length segment weight]
      if (j.type === 'pulley') {
        const r = j.r ?? 0; const PA = [j.pulley[0] - r, j.pulley[1]], PB = [j.pulley[0] + r, j.pulley[1]];   // tangent points of the vertical strands
        const pa = this.pointOf(j.a), pb = this.pointOf(j.b);
        const da = Math.hypot(pa[0] - PA[0], pa[1] - PA[1]) || EPS, db = Math.hypot(pb[0] - PB[0], pb[1] - PB[1]) || EPS;
        const na = [(pa[0] - PA[0]) / da, (pa[1] - PA[1]) / da], nb = [(pb[0] - PB[0]) / db, (pb[1] - PB[1]) / db];
        const C = da + db - j.length; if (C < 0) continue;      // slack rope
        const va = this.velOf(j.a), vb = this.velOf(j.b);
        const Jv = dot(na, va) + dot(nb, vb); const w = (this.invMOf(j.a)) + (this.invMOf(j.b)); if (w < EPS) continue;
        let lam = -(Jv + 0.2 * C / dt) / w; if (lam > 0) lam = 0 - 0;   // the rope can only pull
        if (j.a.body) { j.a.body.vx += lam * na[0] * j.a.body.invM; j.a.body.vy += lam * na[1] * j.a.body.invM; }
        if (j.b.body) { j.b.body.vx += lam * nb[0] * j.b.body.invM; j.b.body.vy += lam * nb[1] * j.b.body.invM; }
        continue;
      }
      const pa = this.pointOf(j.a), pb = this.pointOf(j.b); const dx = pb[0] - pa[0], dy = pb[1] - pa[1], L = Math.hypot(dx, dy) || EPS;
      const n = [dx / L, dy / L]; const C = L - j.length;
      if (j.type === 'rope' && C < 0) continue;
      const va = this.velOf(j.a), vb = this.velOf(j.b); const Jv = (vb[0] - va[0]) * n[0] + (vb[1] - va[1]) * n[1];
      const w = this.invMOf(j.a) + this.invMOf(j.b); if (w < EPS) continue;
      const lam = -(Jv + 0.2 * C / dt) / w;
      if (j.a.body) { j.a.body.vx -= lam * n[0] * j.a.body.invM; j.a.body.vy -= lam * n[1] * j.a.body.invM; }
      if (j.b.body) { j.b.body.vx += lam * n[0] * j.b.body.invM; j.b.body.vy += lam * n[1] * j.b.body.invM; }
    }
  }

  contactSurface(b, s) {
    if (b.pinned) return;
    const px = b.x - s.p1[0], py = b.y - s.p1[1]; let u = (px * s.t[0] + py * s.t[1]); u = Math.max(0, Math.min(s.L, u));
    const cx = s.p1[0] + s.t[0] * u, cy = s.p1[1] + s.t[1] * u; let dx = b.x - cx, dy = b.y - cy; const d = Math.hypot(dx, dy);
    if (d >= b.r) return;
    let n = d > EPS ? [dx / d, dy / d] : s.n;
    if (dot(n, s.n) < -0.2 && u > 0 && u < s.L) n = s.n;    // body centre went through: keep it on the free side
    const pen = b.r - d; b.x += n[0] * pen; b.y += n[1] * pen;
    const rv = [-n[0] * b.r, -n[1] * b.r];                    // from the centre to the contact point
    const vc = [b.vx + (-b.om * rv[1]), b.vy + (b.om * rv[0])];   // velocity of the contact point (omega z-axis)
    const vn = dot(vc, n); if (vn >= 0) return;
    const rn = cross(rv, n), invMeff = b.invM + rn * rn * b.invI;
    const e = Math.abs(vn) > 0.5 ? Math.min(b.e, s.e || 0) : 0;
    const jn = -(1 + e) * vn / invMeff;
    b.vx += jn * n[0] * b.invM; b.vy += jn * n[1] * b.invM; b.om += jn * rn * b.invI;
    const t = [-n[1], n[0]]; const vc2 = [b.vx + (-b.om * rv[1]), b.vy + (b.om * rv[0])]; const vt = dot(vc2, t);
    const rt = cross(rv, t), invMt = b.invM + rt * rt * b.invI;
    let jt = -vt / invMt; const maxF = (s.mu || 0) * jn; jt = Math.max(-maxF, Math.min(maxF, jt));
    b.vx += jt * t[0] * b.invM; b.vy += jt * t[1] * b.invM; b.om += jt * rt * b.invI;
    b.contactAngle = Math.atan2(t[1], t[0]);
  }

  collideBodies() {
    for (let i = 0; i < this.bodies.length; i++) for (let j = i + 1; j < this.bodies.length; j++) {
      const a = this.bodies[i], c = this.bodies[j]; if (a.pinned && c.pinned) continue;
      if (a.kind === 'point' || c.kind === 'point' || a.noCollide || c.noCollide) continue;
      let dx = c.x - a.x, dy = c.y - a.y; const d = Math.hypot(dx, dy), minD = a.rc + c.rc;
      if (d >= minD || d < EPS) continue; const n = [dx / d, dy / d];
      const wsum = a.invM + c.invM; const pen = minD - d;
      a.x -= n[0] * pen * a.invM / wsum; a.y -= n[1] * pen * a.invM / wsum; c.x += n[0] * pen * c.invM / wsum; c.y += n[1] * pen * c.invM / wsum;
      const vn = (c.vx - a.vx) * n[0] + (c.vy - a.vy) * n[1]; if (vn >= 0) continue;
      const e = Math.min(a.e, c.e); const jn = -(1 + e) * vn / wsum;
      a.vx -= jn * n[0] * a.invM; a.vy -= jn * n[1] * a.invM; c.vx += jn * n[0] * c.invM; c.vy += jn * n[1] * c.invM;
    }
  }

  // ---------- run ----------
  record(time) {
    this.samples.push({ t: time, s: this.bodies.map((b) => ({
      x: b.x, y: b.y, vx: b.vx, vy: b.vy, ax: b.ax, ay: b.ay, fx: b.fx, fy: b.fy, th: b.th, om: b.om,
      ke: 0.5 * b.m * (b.vx * b.vx + b.vy * b.vy) + (Number.isFinite(b.I) ? 0.5 * b.I * b.om * b.om : 0),
      pe: -b.m * (this.g[0] * b.x + this.g[1] * b.y),
    })) });
  }

  run(duration) {
    const dt = this.dt; this.duration = duration; let next = 0, time = 0;
    this.computeForces(0); this.record(0); next = this.sampleDt;
    const steps = Math.ceil(duration / dt);
    for (let k = 0; k < steps; k++) {
      time = k * dt;
      this.computeForces(time);
      for (const b of this.bodies) {
        if (b.pinned) continue;
        b.vx += b.ax * dt; b.vy += b.ay * dt; b.om += b.invI * b.torque * dt;
        if (b.q && this.B) { const w = (b.q * this.B / b.m) * dt, c = Math.cos(w), sn = Math.sin(w), vx = b.vx; b.vx = vx * c + b.vy * sn; b.vy = -vx * sn + b.vy * c; }
      }
      for (let it = 0; it < 6; it++) { this.solveJoints(dt); }
      for (const b of this.bodies) { b.contactAngle = null; }
      for (let it = 0; it < 3; it++) { for (const b of this.bodies) for (const s of this.surfaces) this.contactSurface(b, s); this.collideBodies(); }
      for (const b of this.bodies) {
        if (b.pinned) continue;
        b.x += b.vx * dt; b.y += b.vy * dt; b.th += b.om * dt;
        if (b.align && b.contactAngle !== null) b.th = b.contactAngle;
      }
      if (time + dt >= next - 1e-12) { this.record(time + dt); next += this.sampleDt; }
    }
    const S = this.samples;   // acceleration = central difference of velocity, so contacts, ropes and springs are included
    for (let n = 0; n < S.length; n++) {
      const a = S[Math.max(0, n - 1)], b = S[Math.min(S.length - 1, n + 1)], h = (b.t - a.t) || 1;
      S[n].s.forEach((st, i) => { st.ax = (b.s[i].vx - a.s[i].vx) / h; st.ay = (b.s[i].vy - a.s[i].vy) / h; });
    }
    return this;
  }

  // Extent of everything the bodies do during the run (with their radii): used to frame the camera automatically.
  bounds() {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const sm of this.samples) sm.s.forEach((st, i) => { const r = Math.max(this.bodies[i].r, this.bodies[i].rc || 0); x0 = Math.min(x0, st.x - r); x1 = Math.max(x1, st.x + r); y0 = Math.min(y0, st.y - r); y1 = Math.max(y1, st.y + r); });
    for (const sf of this.surfaces) if (sf.draw !== false && sf.bounds === true) { x0 = Math.min(x0, sf.p1[0], sf.p2[0]); x1 = Math.max(x1, sf.p1[0], sf.p2[0]); y0 = Math.min(y0, sf.p1[1], sf.p2[1]); y1 = Math.max(y1, sf.p1[1], sf.p2[1]); }
    return Number.isFinite(x0) ? { x0, y0, x1, y1 } : null;
  }

  // k: index into FIELDS (0 x, 1 y, 2 vx, 3 vy, 4 ax, 5 ay, 6 speed, 7 ke, 8 pe, 9 theta, 10 omega)
  value(k, i, tau) {
    const S = this.samples; if (!S.length || !this.bodies[i]) return 0;
    const f = Math.max(0, Math.min(tau, this.duration)) / this.sampleDt; const a = Math.min(S.length - 1, Math.floor(f)), b = Math.min(S.length - 1, a + 1), w = f - Math.floor(f);
    const get = (sm) => { const s = sm.s[i]; switch (k) { case 0: return s.x; case 1: return s.y; case 2: return s.vx; case 3: return s.vy; case 4: return s.ax; case 5: return s.ay; case 6: return Math.hypot(s.vx, s.vy); case 7: return s.ke; case 8: return s.pe; case 9: return s.th; case 10: return s.om; default: return 0; } };
    return get(S[a]) * (1 - w) + get(S[b]) * w;
  }
}

// ---------- scene integration: turns a `sim` block into objects driven by sim() expressions ----------
// Returns the objects to add to the scene (default meshes, trails, vectors, surfaces) and rewrites bound objects in place.
export function expandSim(simSpec, objects, warn = () => {}) {
  const extra = []; const byId = {}; for (const o of objects) if (o.id) byId[o.id] = o;
  const ts = 'ts';   // simulated time variable, supplied by the engine every frame
  const bodies = simSpec.bodies || [];
  bodies.forEach((b, i) => {
    const pos = [`sim(0,${i},${ts})`, `sim(1,${i},${ts})`, 0], rot = [0, 0, `sim(9,${i},${ts})*57.29578`];
    const target = b.bind ? byId[b.bind] : null;
    if (b.bind && !target) warn(`sim: body "${b.id}" is bound to unknown object "${b.bind}"`);
    if (target) { target.position = pos; target.rotation = rot; }
    else {
      const kind = b.kind || 'ball'; const mat = b.material || { color: b.color || 'accent', roughness: 0.35, metalness: 0.1 };   // no look-specific preset names
      if (kind === 'block') extra.push({ id: b.id, type: 'box', size: [...(b.size || [0.6, 0.4]), 0.4], bevel: 0.03, material: mat, position: pos, rotation: rot });
      else extra.push({ id: b.id, type: 'sphere', radius: b.r ?? 0.25, material: mat, position: pos, rotation: rot });
    }
    const ref = b.id ?? `b${i}`;
    if (b.trail) extra.push({ helper: true, id: `${ref}_trail`, type: 'curve', x: `sim(0,${i},u*${ts})`, y: `sim(1,${i},u*${ts})`, z: 0, samples: 160, color: b.trail.color || b.color || 'accent', width: b.trail.width || 4, castShadow: false });
    for (const v of b.vectors || []) {
      const spec = typeof v === 'string' ? { of: v } : v; const scale = spec.scale ?? (spec.of === 'v' ? 0.3 : spec.of === 'a' ? 0.25 : 0.05);
      const kx = spec.of === 'v' ? 2 : spec.of === 'a' ? 4 : 'F';
      const dir = spec.of === 'F' ? [`(${scale})*sim(11,${i},${ts})`, `(${scale})*sim(12,${i},${ts})`] : [`${scale}*sim(${kx},${i},${ts})`, `${scale}*sim(${kx + 1},${i},${ts})`];
      extra.push({ helper: true, type: 'arrow', from: [pos[0], pos[1], 0], to: [`${pos[0]}+${dir[0]}`, `${pos[1]}+${dir[1]}`, 0], color: spec.color || (spec.of === 'v' ? 'good' : spec.of === 'a' ? 'warn' : 'accent'), thickness: spec.thickness ?? 0.03 });
    }
  });
  const pointExpr = (a) => {   // anchor -> [x, y] expressions
    if (typeof a === 'string') { const i = bodies.findIndex((b, k) => (b.id ?? `b${k}`) === a); return i < 0 ? ['0', '0'] : [`sim(0,${i},${ts})`, `sim(1,${i},${ts})`]; }
    return [String(a[0]), String(a[1])];
  };
  (simSpec.springs || []).forEach((sp, n) => {   // coil between the two ends, drawn automatically (spring.draw:false opts out)
    if (sp.draw === false) return;
    const A = pointExpr(sp.a), B = pointExpr(sp.b), turns = sp.turns ?? 9, amp = sp.radius ?? 0.14;
    extra.push({ helper: true, type: 'curve', color: sp.color || 'muted', width: sp.width ?? 5, samples: 140, castShadow: false,
      vars: { ax: A[0], ay: A[1], dx: `(${B[0]})-(${A[0]})`, dy: `(${B[1]})-(${A[1]})`, L: 'sqrt(dx*dx+dy*dy)+0.0001' },
      x: `ax+dx*u-dy/L*${amp}*sin(u*${turns * 6.28318})*min(1,min(u,1-u)*12)`, y: `ay+dy*u+dx/L*${amp}*sin(u*${turns * 6.28318})*min(1,min(u,1-u)*12)`, z: 0, id: `spring_${n}` });
  });
  (simSpec.joints || []).forEach((j, n) => {   // rods, ropes and pulley ropes as lines, drawn automatically (joint.draw:false opts out)
    if (j.draw === false) return;
    const col = j.color || 'muted', width = j.width ?? (j.type === 'rod' ? 6 : 4);
    if (j.type === 'pulley') {
      const r = j.r ?? 0, PA = [String(j.pulley[0] - r), String(j.pulley[1])], PB = [String(j.pulley[0] + r), String(j.pulley[1])], a = pointExpr(j.a), b = pointExpr(j.b);
      extra.push({ helper: true, type: 'curve', color: col, width, samples: 2, castShadow: false, points: [[a[0], a[1], 0], [PA[0], PA[1], 0], [PB[0], PB[1], 0], [b[0], b[1], 0]], id: `joint_${n}` });
    } else {
      const a = pointExpr(j.a), b = pointExpr(j.b);
      extra.push({ helper: true, type: 'curve', color: col, width, samples: 2, castShadow: false, points: [[a[0], a[1], 0], [b[0], b[1], 0]], id: `joint_${n}` });
    }
  });
  (simSpec.surfaces || []).forEach((s) => {
    if (s.draw === false) return;
    const dx = s.p2[0] - s.p1[0], dy = s.p2[1] - s.p1[1], L = Math.hypot(dx, dy), ang = Math.atan2(dy, dx) * 180 / Math.PI; const th = s.thickness ?? 0.12;
    const nx = -dy / L, ny = dx / L, sgn = s.flip ? -1 : 1;
    extra.push({ background: true, type: 'box', size: [L, th, s.depth ?? 1.0], bevel: 0.02, material: s.material || { color: '#7d8798', roughness: 0.75 },   // mid grey: a pale slab blows out under the key light
      position: [(s.p1[0] + s.p2[0]) / 2 - sgn * nx * th / 2, (s.p1[1] + s.p2[1]) / 2 - sgn * ny * th / 2, 0], rotation: [0, 0, ang] });
  });
  return extra;
}

// Extra derived series available to expressions: force on a body (F = m a) as sim(11/12, i, tau)
export function simValue(sim, k, i, tau) {
  if (k === 11) return sim.bodies[i] ? sim.value(4, i, tau) * sim.bodies[i].m : 0;
  if (k === 12) return sim.bodies[i] ? sim.value(5, i, tau) * sim.bodies[i].m : 0;
  return sim.value(k, i, tau);
}
