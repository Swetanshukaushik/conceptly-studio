// Equilibrium helpers behind the chemistry particle lab. Run: node --test studio3d/tests
import test from 'node:test';
import assert from 'node:assert/strict';
import { FUNCTIONS as F } from '../web/expr.js';

const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol * Math.max(1, Math.abs(b)), `${msg}: got ${a}, expected ${b}`);
// N2 + 3 H2 <=> 2 NH3 as particle counts at a reference equilibrium (V = 1)
const ref = [1, 3, 2, 0, 10, 30, 20, 0];   // a b c d nA nB nC nD
const K = F.Keq(1, 3, 2, 0, 10, 30, 20, 0, 1);
const at = (V, Kx = K, d = [0, 0, 0, 0]) => { const x = F.eqext(1, 3, 2, 0, 10 + d[0], 30 + d[1], 20 + d[2], 0, Kx, V); return [10 + d[0] - x, 30 + d[1] - 3 * x, 20 + d[2] + 2 * x, x]; };

test('Keq is the textbook quotient', () => {
  near(F.Keq(1, 1, 2, 0, 1, 1, 2, 0, 1), 4, 1e-12, 'H2 + I2 <=> 2HI Q');
  near(F.Keq(1, 3, 2, 0, 10, 30, 20, 0, 2), (20 / 2) ** 2 / ((10 / 2) * (30 / 2) ** 3), 1e-12, 'N2 + 3H2 <=> 2NH3 Q at V = 2');
});

test('at the reference volume nothing moves (extent 0)', () => { near(at(1)[3], 0, 1e-6, 'xi'); });

test('Le Chatelier: compressing N2 + 3H2 <=> 2NH3 makes more NH3, expanding makes less', () => {
  const squeezed = at(0.5), relaxed = at(2);
  assert.ok(squeezed[2] > 20 && relaxed[2] < 20, `NH3 ${squeezed[2]} > 20 > ${relaxed[2]}`);
  assert.ok(squeezed[0] < 10 && relaxed[0] > 10, 'N2 moves the other way');
});

test('the new state is a real equilibrium (Q equals K) and conserves atoms', () => {
  for (const V of [0.4, 0.7, 1.5, 3]) {
    const n = at(V); near(F.Keq(1, 3, 2, 0, n[0], n[1], n[2], 0, V), K, 1e-6, `Q at V=${V}`);
    near(2 * n[0] + 2 * 0 + 0 * n[1] + 1 * n[2], 2 * 10 + 20, 1e-9, 'N atoms');   // N2 has 2 N, NH3 has 1 N
    near(2 * n[1] + 3 * n[2], 2 * 30 + 3 * 20, 1e-9, 'H atoms');
  }
});

test('equal gas moles on both sides: volume changes do not shift H2 + I2 <=> 2HI', () => {
  const k = F.Keq(1, 1, 2, 0, 5, 5, 10, 0, 1);
  for (const V of [0.3, 1, 4]) near(F.eqext(1, 1, 2, 0, 5, 5, 10, 0, k, V), 0, 1e-6, `xi at V=${V}`);
});

test('adding reactant shifts toward products; removing product shifts toward products too', () => {
  assert.ok(at(1, K, [0, 10, 0, 0])[3] > 0.5, 'more H2 -> forward');
  assert.ok(at(1, K, [0, 0, -8, 0])[3] > 0.5, 'less NH3 -> forward');
  assert.ok(at(1, K, [0, 0, 8, 0])[3] < -0.5, 'more NH3 -> backward');
});

test("van 't Hoff: heating an exothermic reaction lowers K and shifts it back; an endothermic one the other way", () => {
  const hot = F.vanthoff(K, -92, 400, 500), cold = F.vanthoff(K, -92, 400, 300), hotEndo = F.vanthoff(K, 92, 400, 500);
  assert.ok(hot < K && cold > K && hotEndo > K);
  assert.ok(at(1, hot)[2] < 20 && at(1, cold)[2] > 20, 'NH3 amount follows K');
  near(F.vanthoff(K, -92, 400, 400), K, 1e-12, 'no change at the same temperature');
});

test('absent species (stoichiometric number 0) are ignored: PCl5 <=> PCl3 + Cl2', () => {
  const k = F.Keq(1, 0, 1, 1, 10, 0, 5, 5, 1);
  const x = F.eqext(1, 0, 1, 1, 10, 0, 5, 5, k, 0.5);   // compressing favours the side with fewer moles (PCl5)
  assert.ok(x < 0, `extent ${x}`);
  near(F.Keq(1, 0, 1, 1, 10 - x, 0, 5 + x, 5 + x, 0.5), k, 1e-6, 'Q = K');
});

test('smoothint is the integral of smooth(a, b, s)', () => {
  let acc = 0; const dt = 0.001, a = 1, b = 3; for (let s = 0; s < 4; s += dt) acc += F.smooth(a, b, s + dt / 2) * dt;
  near(F.smoothint(a, b, 4), acc, 2e-3, 'integral to 4'); assert.equal(F.smoothint(a, b, 0.5), 0);
});
