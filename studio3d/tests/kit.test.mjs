// Explainer kit helpers: camera tours and pop-word timing. Run: node --test studio3d/tests
import test from 'node:test';
import assert from 'node:assert/strict';
import { makeTour, popTiming, normWord } from '../web/kit.js';

const wp = (at, x, fov) => ({ at, position: [x, 1, 8], target: [x, 1, 0], ...(fov ? { fov } : {}) });

test('tour passes exactly through its waypoints and rests at both ends', () => {
  const tour = makeTour([wp(0, 0), wp(4, 3), wp(8, 3.5)]);
  assert.equal(tour.pos[0]({ t: 0 }), 0);
  assert.ok(Math.abs(tour.pos[0]({ t: 4 }) - 3) < 1e-9);
  assert.equal(tour.pos[0]({ t: 8 }), 3.5);
  assert.equal(tour.pos[0]({ t: 99 }), 3.5);
  assert.equal(tour.pos[0]({ t: -5 }), 0);
  // eased start: barely moving right after t=0, fast in the middle
  const slow = tour.pos[0]({ t: 0.2 }) - tour.pos[0]({ t: 0 }), fast = tour.pos[0]({ t: 3.2 }) - tour.pos[0]({ t: 3 });
  assert.ok(fast > slow * 3, `ease in: ${slow} vs ${fast}`);
});

test('tour is smooth: no jump in position between neighbouring samples', () => {
  const tour = makeTour([wp(0, 0), wp(3, 5), wp(6, 2), wp(10, 9)]);
  let prev = tour.pos[0]({ t: 0 });
  for (let t = 0.01; t <= 10; t += 0.01) { const v = tour.pos[0]({ t }); assert.ok(Math.abs(v - prev) < 0.2, `jump at ${t}`); prev = v; }
});

test('tour interpolates fov and clamps it to a sane range', () => {
  const tour = makeTour([wp(0, 0, 30), wp(4, 0, 50)]);
  assert.equal(tour.fov({ t: 0 }), 30); assert.equal(tour.fov({ t: 4 }), 50);
  assert.ok(tour.fov({ t: 2 }) > 30 && tour.fov({ t: 2 }) < 50);
  assert.equal(makeTour([wp(0, 0, 5), wp(4, 0, 500)]).fov({ t: 4 }), 80);
});

test('bad tours are rejected with a warning instead of crashing', () => {
  const msgs = [];
  assert.equal(makeTour([wp(0, 0)], (m) => msgs.push(m)), null);
  assert.equal(makeTour([wp(0, 0), wp(0.1, 1)], (m) => msgs.push(m)), null);
  assert.equal(makeTour([wp(0, 0), { at: 3, position: ['x', 1, 1], target: [0, 0, 0] }], (m) => msgs.push(m)), null);
  assert.equal(makeTour(undefined, (m) => msgs.push(m)), null);
  assert.equal(msgs.length, 4);
});

const words = [
  { w: 'Oxygen', t0: 1.0, t1: 1.4 }, { w: 'turns', t0: 1.4, t1: 1.7 }, { w: 'it', t0: 1.7, t1: 1.8 }, { w: 'red.', t0: 1.8, t1: 2.2 },
  { w: 'Oxygen,', t0: 5.0, t1: 5.4 }, { w: 'again', t0: 5.4, t1: 5.8 },
];

test('pop word is timed to when the narrator says it, relative to the scene start', () => {
  const t = popTiming(words, 'oxygen', 0.5, 4, 0.9);
  assert.ok(Math.abs(t.at - (1.0 - 0.5 - 0.04)) < 1e-9 && Math.abs(t.until - t.at - 0.9) < 1e-9);
});

test('pop word ignores punctuation, honours the scene window and the occurrence', () => {
  assert.equal(normWord('Red.'), 'red'); assert.equal(normWord('Oxygen,'), 'oxygen');
  assert.ok(popTiming(words, 'red', 0, 4));
  assert.equal(popTiming(words, 'again', 0, 4), null);              // said later, outside this scene
  assert.ok(Math.abs(popTiming(words, 'oxygen', 0, 10, 0.9, 2).at - (5.0 - 0.04)) < 1e-9);   // second occurrence
  assert.equal(popTiming(words, 'oxygen', 0, 10, 0.9, 3), null);
  assert.equal(popTiming(words, '', 0, 10), null);
  assert.equal(popTiming(undefined, 'red', 0, 10), null);
});

import { makeVoice } from '../web/kit.js';

const speech = [{ w: 'Newton', t0: 1.0, t1: 1.6 }, { w: 'said', t0: 1.65, t1: 2.0 }, { w: 'every', t0: 2.2, t1: 2.7 }];

test('voice: closed outside words, open inside, always within 0..1', () => {
  const v = makeVoice(speech);
  assert.equal(v(0.5), 0); assert.equal(v(2.1), 0); assert.equal(v(9), 0);
  let max = 0; for (let t = 1.0; t < 2.7; t += 0.01) { const x = v(t); assert.ok(x >= 0 && x <= 1.0001, `range at ${t}: ${x}`); max = Math.max(max, x); }
  assert.ok(max > 0.4, `mouth opens (${max})`);
});

test('voice: the mouth closes between syllables and at the end of each word', () => {
  const v = makeVoice([{ w: 'banana', t0: 0, t1: 1 }]);   // 6 letters -> 2 syllables
  assert.ok(v(0.001) < 0.1 && v(0.999) < 0.1 && v(0.5) < 0.2, 'closed at the start, the syllable gap and the end');
  assert.ok(v(0.25) > 0.3 && v(0.75) > 0.3, 'open in the middle of each syllable');
});

test('voice: does not need sorted lookups and ignores malformed words', () => {
  const v = makeVoice([...speech, { w: 'bad', t0: NaN, t1: 3 }, { w: 'flat', t0: 4, t1: 4 }]);
  assert.ok(v(2.4) > 0 && v(1.3) > 0 && v(1.3) === v(1.3));
  assert.equal(v(4), 0);
});

import fs from 'node:fs';
import { jawDisplacement, browDisplacement, blinkAmount, headMotion } from '../web/photo_narrator.js';
const photo = JSON.parse(fs.readFileSync(new URL('../../config/characters/einstein_photo.json', import.meta.url), 'utf8'));
const { landmarks: L, motion: PM } = photo;

test('photo jaw: nothing moves above the mouth line, the chin drops by the full amount, the neck and far cheeks stay', () => {
  assert.equal(jawDisplacement(L, PM, L.mouthCx, L.mouthY - 1, 1), 0);
  assert.ok(Math.abs(jawDisplacement(L, PM, L.mouthCx, L.mouthY + 1, 1) - PM.jawDrop) < 1e-9);
  assert.ok(Math.abs(jawDisplacement(L, PM, L.mouthCx, L.chinY - 5, 1) - PM.jawDrop) < 1e-9);
  assert.equal(jawDisplacement(L, PM, L.mouthCx, L.neckY + 50, 1), 0);
  assert.equal(jawDisplacement(L, PM, L.mouthCx + PM.jawFalloffX[1] + 10, L.mouthY + 5, 1), 0);
  assert.equal(jawDisplacement(L, PM, L.mouthCx, L.mouthY + 5, 0), 0);
});

test('photo jaw: displacement fades smoothly (no jumps) from the chin to the neck and scales with openness', () => {
  let prev = jawDisplacement(L, PM, L.mouthCx, L.chinY, 1);
  for (let y = L.chinY; y <= L.neckY; y += 2) { const d = jawDisplacement(L, PM, L.mouthCx, y, 1); assert.ok(d <= prev + 1e-9 && prev - d < 3, `smooth at ${y}`); prev = d; }
  assert.ok(Math.abs(jawDisplacement(L, PM, L.mouthCx, L.mouthY + 5, 0.5) - PM.jawDrop / 2) < 1e-9);
  assert.ok(jawDisplacement(L, PM, L.mouthCx, L.mouthY + 5, 9) <= PM.jawDrop + 1e-9);   // openness is clamped
});

test('photo brows rise (negative y) only near the brows; blinks are brief and periodic; head motion stays small', () => {
  assert.ok(browDisplacement(L, PM, L.browCx, L.browY, 1) < -PM.browLift * 0.9);
  assert.ok(Math.abs(browDisplacement(L, PM, L.browCx, L.mouthY, 1)) < 0.01);
  let closed = 0, n = 0; for (let t = 0; t < 40; t += 0.01) { n++; if (blinkAmount(PM, t) > 0.5) closed++; }
  assert.ok(closed / n > 0.005 && closed / n < 0.06, `blink share ${closed / n}`);
  const h = headMotion(PM, 3.3, [3.0]);
  assert.ok(Math.abs(h.rollDeg) <= PM.headSwayDeg + 1e-9 && h.pitch > 0 && h.pitch <= PM.nodDeg + 1e-9 && Math.abs(h.scale - 1) <= PM.breath + 1e-9);
  assert.equal(headMotion(PM, 10, [3.0]).pitch, 0);   // the nod is over
});

import { numeric } from '../web/expr.js';

test('a one-item list where a number belongs is accepted with a warning; longer lists still fail', () => {
  const warned = []; const f = numeric([2.5], (m) => warned.push(m));
  assert.equal(f({}), 2.5); assert.equal(warned.length, 1);
  assert.equal(numeric(['t*2'], () => {})({ t: 3 }), 6);
  assert.throws(() => numeric([1, 2], () => {}), /Expected number or expression/);
});
