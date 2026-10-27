// Checks the simulator against textbook results. Run: node --test studio3d/tests
import test from 'node:test';
import assert from 'node:assert/strict';
import { Sim } from '../web/physics.js';

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol * Math.max(1, Math.abs(b)), `${msg}: got ${a}, expected ${b} (+-${tol * 100}%)`);
const rad = (d) => (d * Math.PI) / 180;

function crossings(sim, i, k = 0, level = 0) {   // times when a quantity crosses `level` going upwards
  const out = []; let prev = sim.value(k, i, 0) - level;
  for (let t = sim.sampleDt; t < sim.duration; t += sim.sampleDt) { const v = sim.value(k, i, t) - level; if (prev < 0 && v >= 0) out.push(t); prev = v; }
  return out;
}

test('projectile: apex height y0 + vy^2 / 2g', () => {
  const s = new Sim({ bodies: [{ id: 'b', kind: 'point', pos: [0, 1], vel: [6, 8] }] }).run(2);
  let top = 0; for (let t = 0; t < 2; t += 0.005) top = Math.max(top, s.value(1, 0, t));
  near(top, 1 + 64 / 19.6, 0.005, 'apex');
  near(s.value(0, 0, 1.5), 9, 0.002, 'x = vx t');
});

test('block sliding down a frictionless 30 degree incline: a = g sin(theta)', () => {
  const a = rad(30), L = 10;
  const s = new Sim({ surfaces: [{ p1: [0, L * Math.sin(a)], p2: [L * Math.cos(a), 0], mu: 0, flip: false }],
    bodies: [{ id: 'b', kind: 'block', m: 1, size: [0.4, 0.2], pos: [0.5 * Math.cos(a) + 0.1 * Math.sin(a), L * Math.sin(a) - 0.5 * Math.sin(a) + 0.1 * Math.cos(a)] }] }).run(1.5);
  near(s.value(6, 0, 1.0), 9.8 * Math.sin(a) * 1.0, 0.03, 'speed after 1 s');
});

test('block on a rough incline: a = g (sin - mu cos)', () => {
  const a = rad(30), L = 10, mu = 0.2;
  const s = new Sim({ surfaces: [{ p1: [0, L * Math.sin(a)], p2: [L * Math.cos(a), 0], mu }],
    bodies: [{ id: 'b', kind: 'block', m: 1, size: [0.4, 0.2], pos: [0.5 * Math.cos(a) + 0.1 * Math.sin(a), L * Math.sin(a) - 0.5 * Math.sin(a) + 0.1 * Math.cos(a)] }] }).run(1.5);
  near(s.value(6, 0, 1.0), 9.8 * (Math.sin(a) - mu * Math.cos(a)), 0.05, 'speed after 1 s');
});

test('disc rolling without slipping: a = g sin(theta) / (1 + I/mr^2) = g sin / 1.5', () => {
  const a = rad(30), L = 10, r = 0.2;
  const s = new Sim({ surfaces: [{ p1: [0, L * Math.sin(a)], p2: [L * Math.cos(a), 0], mu: 1.0 }],
    bodies: [{ id: 'b', kind: 'ball', m: 1, r, pos: [0.5 * Math.cos(a) + r * Math.sin(a), L * Math.sin(a) - 0.5 * Math.sin(a) + r * Math.cos(a)] }] }).run(1.5);
  near(s.value(6, 0, 1.0), (9.8 * Math.sin(a) / 1.5) * 1.0, 0.05, 'speed after 1 s');
});

test('simple pendulum: T = 2 pi sqrt(L/g)', () => {
  const L = 1, th = rad(5);
  const s = new Sim({ joints: [{ type: 'rod', a: [0, 2], b: 'b', length: L }], bodies: [{ id: 'b', kind: 'point', m: 1, pos: [L * Math.sin(th), 2 - L * Math.cos(th)] }] }).run(6);
  const up = crossings(s, 0, 0, 0); assert.ok(up.length >= 2, 'at least two upward crossings');
  near(up[1] - up[0], 2 * Math.PI * Math.sqrt(L / 9.8), 0.02, 'period');
});

test('spring-mass: T = 2 pi sqrt(m/k)', () => {
  const s = new Sim({ gravity: [0, 0], springs: [{ a: [0, 0], b: 'b', k: 20, L0: 1 }], bodies: [{ id: 'b', kind: 'point', m: 1, pos: [1.3, 0] }] }).run(5);
  const up = crossings(s, 0, 0, 1); assert.ok(up.length >= 2);
  near(up[1] - up[0], 2 * Math.PI / Math.sqrt(20), 0.01, 'period');
});

test('elastic collision of equal masses exchanges velocities and conserves momentum', () => {
  const s = new Sim({ gravity: [0, 0], bodies: [
    { id: 'a', kind: 'ball', m: 1, r: 0.25, pos: [0, 0], vel: [3, 0], restitution: 1 }, { id: 'c', kind: 'ball', m: 1, r: 0.25, pos: [3, 0], restitution: 1 }] }).run(2);
  near(s.value(2, 0, 2), 0, 0.02, 'a stops'); near(s.value(2, 1, 2), 3, 0.01, 'c moves at 3');
  near(s.value(2, 0, 2) + s.value(2, 1, 2), 3, 0.01, 'momentum');
});

test('inelastic collision: common velocity m1 v1 / (m1 + m2)', () => {
  const s = new Sim({ gravity: [0, 0], bodies: [
    { id: 'a', kind: 'ball', m: 2, r: 0.25, pos: [0, 0], vel: [3, 0], restitution: 0 }, { id: 'c', kind: 'ball', m: 1, r: 0.25, pos: [3, 0], restitution: 0 }] }).run(2);
  near(s.value(2, 0, 2), 2, 0.01, 'a'); near(s.value(2, 1, 2), 2, 0.01, 'c');
});

test('Atwood machine: a = (m1 - m2) g / (m1 + m2)', () => {
  const s = new Sim({ joints: [{ type: 'pulley', a: 'm1', b: 'm2', pulley: [0, 5], r: 0.3, length: 5.4 }],
    bodies: [{ id: 'm1', kind: 'point', m: 2, pos: [-0.3, 2] }, { id: 'm2', kind: 'point', m: 1, pos: [0.3, 2.6] }] }).run(1.2);
  near(Math.abs(s.value(5, 0, 0.8)), (2 - 1) * 9.8 / 3, 0.04, 'acceleration');
  near(Math.abs(s.value(5, 1, 0.8)), (2 - 1) * 9.8 / 3, 0.04, 'both masses share the acceleration');
});

test('circular orbit under inverse-square attraction: T = 2 pi sqrt(r^3 / GM)', () => {
  const GM = 100, r = 4, v = Math.sqrt(GM / r);
  const s = new Sim({ gravity: [0, 0], nbody: { G: 1 }, bodies: [
    { id: 'sun', kind: 'point', m: GM, pos: [0, 0], pinned: true }, { id: 'p', kind: 'point', m: 1e-6, pos: [r, 0], vel: [0, v] }] }).run(14);
  const T = 2 * Math.PI * Math.sqrt(r ** 3 / GM); const up = crossings(s, 1, 1, 0);
  near(up[1] - up[0], T, 0.01, 'orbital period');
  for (let t = 0; t < 14; t += 0.5) near(Math.hypot(s.value(0, 1, t), s.value(1, 1, t)), r, 0.01, 'radius stays constant');
});

test('charged particle in a magnetic field moves on a circle of radius mv/qB', () => {
  const m = 1, q = 2, B = 1.5, v = 3;
  const s = new Sim({ gravity: [0, 0], fields: { B }, bodies: [{ id: 'p', kind: 'point', m, q, pos: [0, 0], vel: [v, 0] }] }).run(4);
  const R = m * v / (q * B); let cx = 0, cy = -R;   // force q v x B points to -y for +x velocity with B out of the screen
  for (let t = 0; t < 4; t += 0.25) near(Math.hypot(s.value(0, 0, t) - cx, s.value(1, 0, t) - cy), R, 0.01, 'on the circle');
});
