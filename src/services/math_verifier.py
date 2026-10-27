"""Deterministic checks for the numbers a reel narrates.

The writer lists every checkable statement as a `MathClaim` (kind, the exact quote from the narration, the numbers the
quote says, and the data needed to recompute it). This module recomputes each claim with a small safe evaluator (no
eval, no imports, whitelisted functions), checks that the quote really occurs in the narration and really contains the
stated numbers, and reports sentences that state numbers but no claim covers. Tolerances and word lists live in
config/math_verify.json.
"""
import ast
import math
import random
import re
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from src.services.config_loader import load_json

CLAIM_KINDS = ("value", "holds", "identity", "distance", "distance_to_line", "table", "root", "derivative", "derivative_expr", "balanced", "molar_mass")


class MathClaim(BaseModel):
    kind: Literal[CLAIM_KINDS]  # type: ignore[valid-type]
    quote: str = Field(..., description="The exact words from the narration that state this fact (copy them verbatim, at most one sentence)")
    stated: List[float] = Field(default_factory=list, description="Every number the quote says, as plain numbers (spoken words converted to digits)")
    expr: Optional[str] = None
    lhs: Optional[str] = None
    rhs: Optional[str] = None
    function: Optional[str] = None
    derivative: Optional[str] = None
    var: Optional[str] = "x"
    at: Optional[Dict[str, float]] = None
    equals: Optional[float] = None
    a: Optional[List[float]] = None
    b: Optional[List[float]] = None
    point: Optional[List[float]] = None
    line: Optional[List[float]] = Field(None, description="[A, B, C] of the line A*x + B*y + C = 0")
    rows: Optional[List[List[float]]] = Field(None, description="[[x, y], ...] pairs for a value table")
    roots: Optional[List[float]] = None
    tol: Optional[float] = Field(None, description="Relative tolerance for rounded values, for example 0.005 for 'about 3.14'")


class ClaimError(ValueError):
    pass


def _cfg() -> Dict[str, Any]:
    return load_json("math_verify.json")


# ---------------------------------------------------------------- safe expression evaluation
def _prepare(src: str) -> str:
    s = str(src).replace("−", "-").replace("×", "*").replace("·", "*").replace("^", "**").strip()
    s = re.sub(r"(\d)\s*([A-Za-z(])", r"\1*\2", s)                 # 2x, 4ax, 3(x+1)
    s = re.sub(r"(\))\s*([A-Za-z0-9(])", r"\1*\2", s)              # (x+1)(x-1), (x)2
    return s


_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b, ast.Mod: lambda a, b: a % b}


def evaluate(src: str, env: Optional[Dict[str, float]] = None) -> float:
    cfg = _cfg(); env = env or {}
    if len(str(src)) > cfg["limits"]["max_expression_chars"]:
        raise ClaimError("expression too long")
    try:
        tree = ast.parse(_prepare(src), mode="eval")
    except SyntaxError as e:
        raise ClaimError(f"cannot parse '{src}'") from e
    funcs = {name: getattr(math, name) for name in cfg["functions"] if hasattr(math, name)}
    funcs["ln"] = math.log; funcs["pow"] = math.pow; funcs["abs"] = abs; funcs["min"] = min; funcs["max"] = max

    def ev(n: ast.AST) -> float:
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id in env:
                return float(env[n.id])
            if n.id in cfg["constants"]:
                return cfg["constants"][n.id]
            if len(n.id) > 1 and all(ch in env or ch in cfg["constants"] for ch in n.id):   # implicit product such as 4ax or xy
                out = 1.0
                for ch in n.id:
                    out *= float(env[ch]) if ch in env else cfg["constants"][ch]
                return out
            raise ClaimError(f"unknown variable '{n.id}' in '{src}'")
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand); return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            if isinstance(n.op, ast.Pow):
                base, exp = ev(n.left), ev(n.right)
                if abs(exp) > cfg["limits"]["max_exponent"]:
                    raise ClaimError("exponent too large")
                try:
                    out = base ** exp
                except (ZeroDivisionError, OverflowError) as e:
                    raise ClaimError(str(e)) from e
                if isinstance(out, complex):
                    raise ClaimError("complex result")
                return float(out)
            if type(n.op) in _BIN:
                try:
                    return float(_BIN[type(n.op)](ev(n.left), ev(n.right)))
                except ZeroDivisionError as e:
                    raise ClaimError("division by zero") from e
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in funcs and not n.keywords:
            try:
                return float(funcs[n.func.id](*[ev(a) for a in n.args]))
            except (ValueError, ZeroDivisionError, OverflowError) as e:
                raise ClaimError(f"{n.func.id}: {e}") from e
        raise ClaimError(f"unsupported syntax in '{src}'")
    return ev(tree)


def _close(a: float, b: float, rel: Optional[float] = None) -> bool:
    t = _cfg()["tolerance"]
    return abs(a - b) <= max(t["absolute"], (rel if rel is not None else t["relative"]) * max(abs(a), abs(b)))


def _tol(claim: MathClaim) -> Optional[float]:
    if claim.tol is None:
        return None
    return min(abs(claim.tol), _cfg()["tolerance"]["max_claim_relative"])


# ---------------------------------------------------------------- spoken numbers
def _norm_text(text: str) -> str:
    t = text.lower().replace("−", "-").replace("—", " ").replace("–", " ").replace("…", " ")
    t = re.sub(r"[^a-z0-9.\-/%\s]", " ", t)
    t = re.sub(r"\.(?!\d)", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def numbers_in(text: str) -> List[float]:
    """All numbers in a piece of narration, digits and spoken words, as absolute values (signs are checked by the claim itself)."""
    cfg = _cfg(); words, mult = cfg["number_words"], cfg["multipliers"]
    out: List[float] = []; tokens = _norm_text(text).split(); i = 0
    while i < len(tokens):
        tok = tokens[i]
        m = re.fullmatch(r"-?(\d+(?:\.\d+)?)(?:/(\d+(?:\.\d+)?))?%?", tok)
        if m:
            v = float(m.group(1)); out.append(v / float(m.group(2)) if m.group(2) else v); i += 1; continue
        if tok in words or tok in mult:
            cur = None
            while i < len(tokens) and (tokens[i] in words or tokens[i] in mult or (tokens[i] == "and" and cur is not None and tokens[i - 1] in mult and i + 1 < len(tokens) and tokens[i + 1] in words)):
                t = tokens[i]
                if t == "and":   # "one hundred and five"
                    i += 1; continue
                if t in mult:
                    cur = (cur if cur is not None else 1) * mult[t]
                else:
                    if cur is not None and words[t] >= 10 and tokens[i - 1] not in mult:
                        break   # "twenty thirty" are two numbers
                    if cur is not None and tokens[i - 1] in words and words[tokens[i - 1]] < 20 and words[tokens[i - 1]] >= 10:
                        break
                    cur = (cur or 0) + words[t]
                i += 1
            if i + 1 < len(tokens) and tokens[i] in cfg["decimal_words"] and tokens[i + 1] in words and words[tokens[i + 1]] < 10:
                frac = ""; j = i + 1
                while j < len(tokens) and tokens[j] in words and words[tokens[j]] < 10:
                    frac += str(words[tokens[j]]); j += 1
                cur = float(f"{int(cur)}.{frac}"); i = j
            out.append(float(cur)); continue
        i += 1
    return out


def _has_ambiguous_only(tokens: List[str], cfg: Dict[str, Any]) -> bool:
    return False


def sentence_has_number(sentence: str) -> bool:
    cfg = _cfg(); toks = _norm_text(sentence).split()
    nums = [t for t in toks if re.fullmatch(r"-?\d+(?:\.\d+)?(?:/\d+)?%?", t) or (t in cfg["number_words"] and t not in cfg["ambiguous_number_words"]) or t in cfg["multipliers"]]
    if nums:
        return True
    ambiguous = [t for t in toks if t in cfg["ambiguous_number_words"]]
    return bool(ambiguous) and any(t in cfg["math_context_words"] for t in toks)


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\s*…\s*|\.\.\.\s*|\s+—\s+", text.strip())
    return [p.strip() for p in parts if p and p.strip()]


# ---------------------------------------------------------------- chemistry: balanced equations and molar masses
_STATE = re.compile(r"\((?:g|l|s|aq)\)")


def parse_formula(formula: str) -> Dict[str, int]:
    """Atom counts of a formula such as Ca(OH)2 or CuSO4.5H2O. Charges and state symbols are ignored."""
    f = _STATE.sub("", str(formula)).replace("\u00b7", ".").replace("*", ".")
    f = re.sub(r"\^?\d*[+\-]$", "", f.strip())                       # trailing charge such as ^2+ or -
    total: Dict[str, int] = {}
    for part in f.split("."):
        m = re.match(r"^(\d+)(.*)$", part.strip())
        mult, body = (int(m.group(1)), m.group(2)) if m else (1, part.strip())
        pos = 0; stack: List[Dict[str, int]] = [{}]
        for t in re.finditer(r"([A-Z][a-z]?)(\d*)|(\()|(\))(\d*)", body):
            if t.start() != pos:
                raise ClaimError(f"cannot read the formula '{formula}'")
            pos = t.end()
            if t.group(1):
                stack[-1][t.group(1)] = stack[-1].get(t.group(1), 0) + int(t.group(2) or 1)
            elif t.group(3):
                stack.append({})
            else:
                if len(stack) < 2:
                    raise ClaimError(f"unbalanced brackets in '{formula}'")
                inner = stack.pop(); k = int(t.group(5) or 1)
                for el, n in inner.items():
                    stack[-1][el] = stack[-1].get(el, 0) + n * k
        if pos != len(body) or len(stack) != 1 or not stack[0]:
            raise ClaimError(f"cannot read the formula '{formula}'")
        for el, n in stack[0].items():
            total[el] = total.get(el, 0) + n * mult
    return total


def _side(text: str) -> Dict[str, float]:
    atoms: Dict[str, float] = {}
    for term in re.split(r"\s+\+\s+|(?<=[A-Za-z0-9)])\+(?=\d*[A-Z(])", text.strip()):
        term = term.strip()
        if not term:
            continue
        m = re.match(r"^(\d+(?:/\d+)?(?:\.\d+)?)\s*(.*)$", term)
        coef, formula = (float(eval_fraction(m.group(1))), m.group(2)) if m else (1.0, term)
        if coef <= 0:
            raise ClaimError(f"coefficient in '{term}' must be positive")
        for el, n in parse_formula(formula).items():
            atoms[el] = atoms.get(el, 0) + coef * n
    return atoms


def eval_fraction(s: str) -> float:
    a, _, b = s.partition("/")
    return float(a) / float(b) if b else float(a)


def check_balanced(equation: str) -> Optional[str]:
    parts = re.split(r"<=>|<->|\u21cc|\u2192|->|=>|=", str(equation))
    if len(parts) != 2:
        return f"cannot split '{equation}' into reactants and products"
    left, right = _side(parts[0]), _side(parts[1])
    bad = [f"{el}: {left.get(el, 0):g} on the left, {right.get(el, 0):g} on the right" for el in sorted(set(left) | set(right)) if abs(left.get(el, 0) - right.get(el, 0)) > 1e-9]
    return None if not bad else "not balanced (" + "; ".join(bad) + ")"


def molar_mass(formula: str) -> float:
    masses = load_json("periodic_table.json")["masses"]; total = 0.0
    for el, n in parse_formula(formula).items():
        if el not in masses:
            raise ClaimError(f"unknown element '{el}'")
        total += masses[el] * n
    return total


# ---------------------------------------------------------------- claim checks
def _need(v: Any, name: str, kind: str) -> Any:
    if v is None or v == []:
        raise ClaimError(f"a '{kind}' claim needs `{name}`")
    return v


def _samples(var: str) -> List[float]:
    s = _cfg()["identity_samples"]; rnd = random.Random(s["seed"])
    return [rnd.uniform(s["low"], s["high"]) for _ in range(s["count"])]


def _deriv(fn: str, var: str, x0: float, env: Dict[str, float]) -> float:
    h = _cfg()["tolerance"]["derivative_step"]
    return (evaluate(fn, {**env, var: x0 + h}) - evaluate(fn, {**env, var: x0 - h})) / (2 * h)


def check_claim(c: MathClaim) -> Optional[str]:
    """Return None when the claim is true, else a short message saying what is wrong and what the correct value is."""
    k, rel, var = c.kind, _tol(c), (c.var or "x")
    try:
        if k == "value":
            got = evaluate(_need(c.expr, "expr", k)); want = _need(c.equals, "equals", k)
            return None if _close(got, want, rel) else f"'{c.expr}' equals {got:g}, not {want:g}"
        if k == "holds":
            at = _need(c.at, "at", k); l, r = evaluate(_need(c.lhs, "lhs", k), at), evaluate(_need(c.rhs, "rhs", k), at)
            return None if _close(l, r, rel) else f"at {at} the left side is {l:g} and the right side is {r:g}, so '{c.lhs} = {c.rhs}' does not hold there"
        if k == "identity":
            bad = []; ok = 0
            for x in _samples(var):
                try:
                    l, r = evaluate(_need(c.lhs, "lhs", k), {var: x}), evaluate(_need(c.rhs, "rhs", k), {var: x})
                except ClaimError:
                    continue
                ok += 1
                if not _close(l, r, rel):
                    bad.append(f"{var}={x:.3g}: {l:g} vs {r:g}")
            if ok < _cfg()["identity_samples"]["min_valid"]:
                return "could not evaluate the identity at enough points"
            return None if not bad else f"'{c.lhs}' and '{c.rhs}' are not equal for all {var} (e.g. {bad[0]})"
        if k == "distance":
            a, b = _need(c.a, "a", k), _need(c.b, "b", k)
            if len(a) != len(b):
                return "points a and b must have the same dimension"
            got = math.dist(a, b); want = _need(c.equals, "equals", k)
            return None if _close(got, want, rel) else f"the distance between {a} and {b} is {got:g}, not {want:g}"
        if k == "distance_to_line":
            p, ln = _need(c.point, "point", k), _need(c.line, "line", k)
            if len(p) != 2 or len(ln) != 3 or (ln[0] == 0 and ln[1] == 0):
                return "distance_to_line needs point [x, y] and line [A, B, C]"
            got = abs(ln[0] * p[0] + ln[1] * p[1] + ln[2]) / math.hypot(ln[0], ln[1]); want = _need(c.equals, "equals", k)
            return None if _close(got, want, rel) else f"the distance from {p} to the line {ln[0]:g}x + {ln[1]:g}y + {ln[2]:g} = 0 is {got:g}, not {want:g}"
        if k == "table":
            fn = _need(c.function, "function", k); wrong = []
            for row in _need(c.rows, "rows", k):
                if len(row) != 2:
                    return "each table row must be [x, y]"
                got = evaluate(fn, {var: row[0]})
                if not _close(got, row[1], rel):
                    wrong.append(f"{fn} at {var}={row[0]:g} is {got:g}, not {row[1]:g}")
            return None if not wrong else "; ".join(wrong)
        if k == "root":
            wrong = []
            for r in _need(c.roots, "roots", k):
                l, rr = evaluate(_need(c.lhs, "lhs", k), {var: r}), evaluate(_need(c.rhs, "rhs", k), {var: r})
                if not _close(l, rr, rel):
                    wrong.append(f"{var}={r:g} gives {l:g} on the left and {rr:g} on the right")
            return None if not wrong else "not a root: " + "; ".join(wrong)
        if k == "derivative":
            fn = _need(c.function, "function", k); x0 = _need(c.at, "at", k).get(var)
            if x0 is None:
                return f"`at` must give a value for {var}"
            got = _deriv(fn, var, x0, {}); want = _need(c.equals, "equals", k)
            return None if _close(got, want, rel if rel is not None else _cfg()["tolerance"]["derivative_relative"]) else f"the derivative of {fn} at {var}={x0:g} is {got:.6g}, not {want:g}"
        if k == "balanced":
            return check_balanced(_need(c.expr, "expr", k))
        if k == "molar_mass":
            got = molar_mass(_need(c.expr, "expr", k)); want = _need(c.equals, "equals", k)
            return None if _close(got, want, rel if rel is not None else 0.01) else f"the molar mass of {c.expr} is {got:.4g} g/mol, not {want:g}"
        if k == "derivative_expr":
            fn, d = _need(c.function, "function", k), _need(c.derivative, "derivative", k); bad = []
            for x in _samples(var):
                try:
                    got, want = _deriv(fn, var, x, {}), evaluate(d, {var: x})
                except ClaimError:
                    continue
                if not _close(got, want, _cfg()["tolerance"]["derivative_relative"]):
                    bad.append(f"{var}={x:.3g}: {got:.5g} vs {want:.5g}")
            return None if not bad else f"the derivative of {fn} is not {d} (e.g. {bad[0]})"
    except ClaimError as e:
        return f"cannot check this claim: {e}"
    return f"unknown claim kind '{k}'"


def verify(claims: List[MathClaim], narration: str, require: bool = False, coverage: str = "note") -> Tuple[List[str], List[str]]:
    """Returns (blocking problems, notes). Blocking: false claims, quotes that are not in the narration, stated numbers the quote does not say."""
    cfg = _cfg(); problems: List[str] = []; notes: List[str] = []
    norm = _norm_text(narration)
    if len(claims) > cfg["limits"]["max_claims"]:
        problems.append(f"too many claims ({len(claims)}); list at most {cfg['limits']['max_claims']}, the most important ones")
        claims = claims[: cfg["limits"]["max_claims"]]
    for i, c in enumerate(claims, 1):
        label = f"claim {i} ({c.kind}, \"{c.quote[:60]}\")"
        q = _norm_text(c.quote)
        if not q or q not in norm:
            problems.append(f"{label}: the quote is not a verbatim part of the narration; copy the exact words")
            continue
        spoken = numbers_in(c.quote)
        missing = [s for s in c.stated if not any(_close(abs(s), v, 1e-9) for v in spoken)]
        if missing:
            problems.append(f"{label}: the quote does not say {', '.join(f'{m:g}' for m in missing)} (it says {', '.join(f'{v:g}' for v in spoken) or 'no numbers'}); the narration and the claim disagree")
        wrong = check_claim(c)
        if wrong:
            problems.append(f"{label}: {wrong}")
    sentences = [s for s in split_sentences(narration) if len(s.split()) >= cfg["coverage"]["min_sentence_words"] and sentence_has_number(s)]
    quotes = [_norm_text(c.quote) for c in claims]
    uncovered = [s for s in sentences if not any(q and (q in _norm_text(s) or _norm_text(s) in q) for q in quotes)]
    if require and sentences and not claims:
        problems.append("the narration states numbers but no claims were listed; list every checkable statement as a claim")
    elif uncovered:
        msg = "numbers not covered by any claim: " + " | ".join(f"\"{s[:80]}\"" for s in uncovered[:6])
        (problems if coverage == "block" else notes).append(msg)
    return problems, notes
