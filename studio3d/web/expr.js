// Safe math-expression compiler. Scene specs come from an LLM, so nothing here may touch
// globals, properties or code: expressions are parsed into closures over a plain variable bag.
//
// Grammar: numbers, identifiers, + - * / % ^, unary - !, comparisons, && ||, f(a, b), ( ).
// Comparisons and logic return 1 or 0; use if(cond, a, b) to branch.

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const mix = (a, b, k) => a + (b - a) * k;
const smooth = (a, b, x) => { const k = clamp((x - a) / (b - a || 1e-9), 0, 1); return k * k * (3 - 2 * k); };
const smoother = (a, b, x) => { const k = clamp((x - a) / (b - a || 1e-9), 0, 1); return k * k * k * (k * (k * 6 - 15) + 10); };
const pop = (a, b, x) => { // ease-out-back: quick overshoot, the "pop in" feel
  const k = clamp((x - a) / (b - a || 1e-9), 0, 1), c1 = 1.70158, c3 = c1 + 1;
  return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2);
};
const pulse = (a, b, x) => (x >= a && x <= b ? 1 : 0);
const hash = (n) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
const noise = (x) => { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return mix(hash(i), hash(i + 1), u) * 2 - 1; };

export const FUNCTIONS = {
  sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
  atan2: Math.atan2, sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh, sqrt: Math.sqrt, abs: Math.abs,
  exp: Math.exp, log: Math.log, ln: Math.log, log10: Math.log10, pow: Math.pow, min: Math.min, max: Math.max,
  floor: Math.floor, ceil: Math.ceil, round: Math.round, sign: Math.sign,
  mod: (a, b) => ((a % b) + b) % b,
  clamp, mix, smooth, smoother, pop, pulse, noise, hash,
  if: (c, a, b) => (c ? a : b),
};
let simProvider = null;
export function setSimProvider(fn) { simProvider = fn; }   // fn(k, i, tau) -> number, set by the engine for scenes with a `sim` block
FUNCTIONS.sim = (k, i, tau) => (simProvider ? simProvider(k, i, tau) : 0);
let voiceProvider = null;
export function setVoiceProvider(fn) { voiceProvider = fn; }   // fn(T) -> mouth openness 0..1 from the narration timings
FUNCTIONS.voice = (T) => (voiceProvider ? voiceProvider(T) : 0);
// ---- chemistry: equilibrium counts that follow the equilibrium constant, so a particle picture can never contradict Le Chatelier.
// Reaction a A + b B <=> c C + d D (a stoichiometric number of 0 means "not present"). Counts are particle numbers, V is the volume.
// Q = ((nC/V)^c (nD/V)^d) / ((nA/V)^a (nB/V)^b); Keq returns Q for given counts, eqext returns how far the reaction must run
// (extent xi, products positive) from the given starting counts for Q to equal K at volume V.
const quotient = (st, n, V) => {
  let num = 1, den = 1;
  for (let i = 0; i < 4; i++) { const c = n[i] / V; if (st[i] > 0 && i >= 2) num *= Math.pow(Math.max(c, 1e-12), st[i]); else if (st[i] > 0) den *= Math.pow(Math.max(c, 1e-12), st[i]); }
  return num / den;
};
FUNCTIONS.Keq = (a, b, c, d, nA, nB, nC, nD, V) => quotient([a, b, c, d], [nA, nB, nC, nD], V);
FUNCTIONS.eqext = (a, b, c, d, nA, nB, nC, nD, K, V) => {
  const st = [a, b, c, d], n = [nA, nB, nC, nD], nu = [-a, -b, c, d];
  if (st.every((x) => x <= 0)) return 0;   // no reaction (a pure gas-law picture)
  let lo = -Infinity, hi = Infinity;   // keep every count above (almost) zero
  for (let i = 0; i < 4; i++) { if (st[i] <= 0) continue; const room = n[i] / st[i]; if (nu[i] < 0) hi = Math.min(hi, room); else lo = Math.max(lo, -room); }
  if (!Number.isFinite(lo)) lo = -hi; if (!Number.isFinite(hi)) hi = -lo; if (!(hi > lo)) return 0;
  const eps = 1e-9 * Math.max(1, hi - lo); let l = lo + eps, h = hi - eps;
  const f = (x) => quotient(st, n.map((v, i) => v + nu[i] * x), V) - K;
  if (f(l) > 0) return l; if (f(h) < 0) return h;
  for (let k = 0; k < 80; k++) { const m = (l + h) / 2; if (f(m) < 0) l = m; else h = m; }
  return (l + h) / 2;
};
// van 't Hoff: equilibrium constant K1 at T1 (kelvin) becomes K2 at T2 for reaction enthalpy dH in kJ/mol (negative = exothermic).
FUNCTIONS.vanthoff = (K1, dH, T1, T2) => K1 * Math.exp(-((dH * 1000) / 8.314) * (1 / T2 - 1 / T1));
// Integral of smooth(a, b, s) over s from 0 to x: lets a clock follow a speed that eases from 1 to 1 + k (clock = t + k*smoothint(a,b,t)).
FUNCTIONS.smoothint = (a, b, x) => { if (x <= a) return 0; if (x >= b) return (b - a) / 2 + (x - b); const u = (x - a) / (b - a); return (b - a) * (u * u * u - u * u * u * u / 2); };
export const CONSTANTS = { pi: Math.PI, tau: Math.PI * 2, e: Math.E };

function tokenize(src) {
  const out = []; let i = 0;
  const re = /\s*(?:(\d+\.?\d*(?:e[+-]?\d+)?|\.\d+)|([A-Za-z_][A-Za-z_0-9]*)|(&&|\|\||<=|>=|==|!=|[-+*/%^(),<>!]))/iy;
  while (i < src.length) {
    re.lastIndex = i;
    const m = re.exec(src);
    if (!m) { if (/^\s*$/.test(src.slice(i))) break; throw new Error(`Unexpected character at ${i} in "${src}"`); }
    i = re.lastIndex;
    if (m[1] !== undefined) out.push({ k: 'num', v: parseFloat(m[1]) });
    else if (m[2] !== undefined) out.push({ k: 'id', v: m[2] });
    else out.push({ k: 'op', v: m[3] });
  }
  return out;
}

const BINARY = [
  ['||'], ['&&'], ['==', '!='], ['<', '>', '<=', '>='], ['+', '-'], ['*', '/', '%'],
];

export function compile(src, warn = () => {}) {
  const toks = tokenize(String(src)); let pos = 0;
  const peek = () => toks[pos], next = () => toks[pos++];
  const isOp = (v) => peek() && peek().k === 'op' && peek().v === v;

  function parseLevel(level) {
    if (level === BINARY.length) return parseUnary();
    let left = parseLevel(level + 1);
    while (peek() && peek().k === 'op' && BINARY[level].includes(peek().v)) {
      const op = next().v, right = parseLevel(level + 1), l = left;
      left = binary(op, l, right);
    }
    return left;
  }
  function binary(op, l, r) {
    switch (op) {
      case '+': return (c) => l(c) + r(c);
      case '-': return (c) => l(c) - r(c);
      case '*': return (c) => l(c) * r(c);
      case '/': return (c) => l(c) / r(c);
      case '%': return (c) => ((l(c) % r(c)) + r(c)) % r(c);
      case '<': return (c) => +(l(c) < r(c));
      case '>': return (c) => +(l(c) > r(c));
      case '<=': return (c) => +(l(c) <= r(c));
      case '>=': return (c) => +(l(c) >= r(c));
      case '==': return (c) => +(l(c) === r(c));
      case '!=': return (c) => +(l(c) !== r(c));
      case '&&': return (c) => +(!!l(c) && !!r(c));
      case '||': return (c) => +(!!l(c) || !!r(c));
    }
  }
  function parseUnary() {
    if (isOp('-')) { next(); const f = parseUnary(); return (c) => -f(c); }
    if (isOp('+')) { next(); return parseUnary(); }
    if (isOp('!')) { next(); const f = parseUnary(); return (c) => +!f(c); }
    return parsePower();
  }
  function parsePower() {
    const base = parsePrimary();
    if (isOp('^')) { next(); const exp = parseUnary(); return (c) => Math.pow(base(c), exp(c)); }
    return base;
  }
  function parsePrimary() {
    const t = next();
    if (!t) throw new Error(`Unexpected end of expression "${src}"`);
    if (t.k === 'num') return () => t.v;
    if (t.k === 'op' && t.v === '(') {
      const f = parseLevel(0);
      if (!isOp(')')) throw new Error(`Missing ) in "${src}"`);
      next(); return f;
    }
    if (t.k === 'id') {
      const name = t.v;
      if (isOp('(')) {
        next(); const args = [];
        if (!isOp(')')) { do { args.push(parseLevel(0)); } while (isOp(',') && next()); }
        if (!isOp(')')) throw new Error(`Missing ) after ${name}( in "${src}"`);
        next();
        const fn = Object.prototype.hasOwnProperty.call(FUNCTIONS, name) ? FUNCTIONS[name] : null;
        if (!fn) throw new Error(`Unknown function "${name}" in "${src}"`);
        return (c) => fn(...args.map((a) => a(c)));
      }
      if (Object.prototype.hasOwnProperty.call(CONSTANTS, name)) return () => CONSTANTS[name];
      return (c) => {
        const v = c[name];
        if (typeof v !== 'number') { warn(`Unknown variable "${name}" in "${src}"`); return 0; }
        return v;
      };
    }
    throw new Error(`Unexpected token "${t.v}" in "${src}"`);
  }

  const fn = parseLevel(0);
  if (pos < toks.length) throw new Error(`Unexpected "${toks[pos].v}" in "${src}"`);
  return fn;
}

// A numeric field is either a literal number or an expression string.
export function numeric(value, warn) {
  if (Array.isArray(value) && value.length === 1 && (typeof value[0] === 'number' || typeof value[0] === 'string')) {   // a one-item list where a number belongs: a common model slip
    warn(`a field should be a plain number or expression, not a list (${JSON.stringify(value)}): used its single item`); return numeric(value[0], warn);
  }
  if (typeof value === 'number') return () => value;
  if (typeof value === 'string') { const f = compile(value, warn); return (c) => { const v = f(c); return Number.isFinite(v) ? v : 0; }; }
  throw new Error(`Expected number or expression, got ${JSON.stringify(value)}`);
}
