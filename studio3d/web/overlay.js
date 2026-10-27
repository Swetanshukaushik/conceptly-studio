// DOM overlay layer drawn over the WebGL canvas: titles, LaTeX formulas, callouts, stats,
// tags that follow 3D objects, word-timed captions and scene dips. Everything is a pure
// function of time so frames are reproducible.
import katex from 'katex';
import 'katex/contrib/mhchem';   // enables \ce{N2 + 3H2 <=> 2NH3} for chemical formulas and equations
import * as THREE from 'three';
import { popTiming } from './kit.js';

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const ease = (k) => 1 - Math.pow(1 - clamp(k, 0, 1), 3);

export class Overlays {
  constructor(cfg, warn) { this.cfg = cfg; this.warn = warn; this.items = []; this.tmp = new THREE.Vector3(); }

  // Layout: where the 3D window sits, optional headline block, caption position. Window-relative placement of cards and tags.
  setLayout(layout, header) {
    this.layout = layout; this.win = layout.window; this.headerLines = Array.isArray(header) ? header : (header && header.lines) || [];
    this.fade.style.left = `${this.win.x}px`; this.fade.style.top = `${this.win.y}px`; this.fade.style.width = `${this.win.width}px`; this.fade.style.height = `${this.win.height}px`;
    this.headerEl = null;
  }

  mount(root) {
    this.root = root; root.innerHTML = '';
    this.cards = el('div', 'layer cards'); this.tags = el('div', 'layer tags'); this.caps = el('div', 'layer caps'); this.fade = el('div', 'layer fade');
    root.append(this.cards, this.tags, this.caps, this.fade);
  }

  color(c) { return (this.look && this.look.palette[c]) || c || this.look.palette.ink; }

  setScene(spec, look) {
    this.look = look; this.cards.innerHTML = ''; this.tags.innerHTML = ''; this.items = [];
    const hdr = this.layout.header;
    if (this.headerEl) this.headerEl.remove();
    if (hdr && this.headerLines.length) {
      // Per-line overrides (sizes, weights, uppercaseLines, tracking) let a layout style a tag, a headline and a subtitle differently.
      const sz = (i) => (hdr.sizes && hdr.sizes[i]) || hdr.size, up = (i) => (hdr.uppercaseLines ? !!hdr.uppercaseLines[i] : hdr.uppercase);
      const gap = (i) => (Array.isArray(hdr.lineGaps) ? hdr.lineGaps[i - 1] ?? hdr.lineGap : hdr.lineGap);
      const el0 = el('div', 'header'); el0.style.fontWeight = hdr.weight; let h = 0;
      this.headerLines.forEach((txt, i) => {
        const l = el('span', 'hl'); l.textContent = up(i) ? String(txt).toUpperCase() : txt; l.style.color = this.color(hdr.colors[Math.min(i, hdr.colors.length - 1)]);
        l.style.fontSize = `${sz(i)}px`; if (hdr.weights && hdr.weights[i]) l.style.fontWeight = hdr.weights[i];
        if (hdr.tracking && hdr.tracking[i]) l.style.letterSpacing = `${hdr.tracking[i]}em`;
        l.style.marginTop = i ? `${gap(i)}px` : '0'; el0.append(l); h += sz(i) + (i ? gap(i) : 0);
      });
      this.root.append(el0); this.headerEl = el0; el0.style.top = `${hdr.centerY - h / 2}px`;
      if (hdr.fit) {   // keep each line on one row: shrink the font until it fits the width (never below 60%)
        const avail = this.cfg.canvas.width - 2 * this.cfg.safeZone.side;
        [...el0.children].forEach((l, i) => { l.style.whiteSpace = 'nowrap'; l.style.display = 'inline-block'; let fs = sz(i); while (l.scrollWidth > avail && fs > sz(i) * 0.6) { fs -= 2; l.style.fontSize = `${fs}px`; } });
        [...el0.children].forEach((l) => { l.style.display = 'block'; });
      }
    }
    const p = look.palette, st = this.root.style;
    for (const [k, v] of Object.entries(p)) st.setProperty(`--${k}`, v);
    const dark = parseInt(p.surface.slice(1, 3), 16) < 128; st.setProperty('--card-bg', dark ? 'rgba(10,16,32,0.62)' : 'rgba(255,255,255,0.72)');
    st.setProperty('--card-border', `${p.primary}66`); st.setProperty('--shadow', dark ? '0 18px 60px rgba(0,0,0,.45)' : '0 18px 50px rgba(30,50,90,.18)');
    st.setProperty('--cap-stroke', dark ? 'rgba(0,0,0,.85)' : 'rgba(255,255,255,.9)');
    const o = this.cfg.overlays;
    for (const it0 of spec.overlays || []) {
      let it = it0;
      if (it0.kind === 'pop') {   // time the big word to the moment the narrator says it
        const word = it0.word ?? it0.text, hit = popTiming(this.words, word, spec.start, spec.end, o.popHold ?? 0.9, it0.occurrence ?? 1);
        if (!hit) { this.warn(`pop word "${word}" is not spoken in this scene's narration, so it is not shown`); continue; }   // decorative: dropped, never fails the reel
        it = { ...it0, text: it0.text ?? it0.word, ...(hit || {}) };
      }
      const node = el('div', `card ${it.kind}`);
      const col = this.color(it.color);
      node.style.setProperty('--c', col);
      if (it.kind === 'title') { node.textContent = it.text; node.style.fontSize = `${o.titleSize}px`; }
      else if (it.kind === 'formula') {
        try { node.innerHTML = katex.renderToString(it.latex || it.text || '', { throwOnError: true, displayMode: true }); }
        catch (e) { this.warn(`LaTeX error: ${e.message}`); node.textContent = it.latex || it.text || ''; }
        node.style.fontSize = `${it.size || o.formulaSize}px`;
        if (it.caption) { const cap = el('div', 'sub'); cap.textContent = it.caption; node.append(cap); }
      } else if (it.kind === 'derivation') {
        node.style.fontSize = `${it.size || o.formulaSize * 0.8}px`; node.style.textAlign = 'left'; node.lines = [];
        (it.lines || []).forEach((ln) => { const row = el('div', 'dline'); try { row.innerHTML = katex.renderToString(ln, { throwOnError: true, displayMode: false }); } catch (e) { this.warn(`LaTeX error: ${e.message}`); row.textContent = ln; } row.style.opacity = 0; node.append(row); node.lines.push(row); });
        if (it.caption) { const cap = el('div', 'sub'); cap.textContent = it.caption; node.append(cap); }
      } else if (it.kind === 'callout') { node.textContent = it.text; node.style.fontSize = `${o.calloutSize}px`; }
      else if (it.kind === 'stat') {
        const v = el('div', 'val'); v.textContent = it.value; v.style.fontSize = `${o.statSize}px`;
        const l = el('div', 'sub'); l.textContent = it.label || ''; node.append(v, l);
      } else if (it.kind === 'pop') {
        const txt = String(it.text ?? '').toUpperCase(); node.textContent = txt;
        const W = this.cfg.canvas.width, usable = W - 2 * this.cfg.safeZone.side;
        node.style.fontSize = `${Math.min(it.size || o.popSize, usable / Math.max(3, txt.length * 0.66))}px`;
      } else if (it.kind === 'sticker') { const hex = (col.startsWith('#') ? col : '#888888').slice(1), lum = (0.2126 * parseInt(hex.slice(0, 2), 16) + 0.7152 * parseInt(hex.slice(2, 4), 16) + 0.0722 * parseInt(hex.slice(4, 6), 16)) / 255; node.style.color = lum > 0.55 ? '#0b1020' : '#ffffff'; node.textContent = it.text; node.style.fontSize = `${it.size || o.stickerSize}px`; node.style.transform = `rotate(${it.tilt ?? -3}deg)`; }
      else if (it.kind === 'tag') {
        node.textContent = it.text; node.style.fontSize = `${o.tagSize}px`;
        if (it.style === 'pin') {   // pinned label: dot on the part, a leader line to the label
          node.classList.add('pin'); const line = el('i', 'pinline'), dot = el('i', 'pindot'); node.append(line, dot); node.pin = { line, dot };
        }
        this.tags.append(node); this.items.push({ it, node, tag: true }); continue;
      }
      else { this.warn(`Unknown overlay kind "${it.kind}"`); continue; }
      this.cards.append(node); this.items.push({ it, node });
    }
  }

  update({ T, t, dur, S, camera, captions, scenes, idx }) {
    const { W, H } = { W: this.cfg.canvas.width, H: this.cfg.canvas.height };
    const z = this.cfg.safeZone, o = this.cfg.overlays; const usable = H - z.top - z.bottom;
    const inS = o.inSeconds, outS = o.outSeconds;
    for (const { it, node, tag } of this.items) {
      const t0 = it.at ?? 0, t1 = it.until ?? dur;
      const vis = t >= t0 && t <= t1;
      if (!vis) { node.style.opacity = 0; continue; }
      const a = ease((t - t0) / inS) * ease((t1 - t) / outS); node.style.opacity = a;
      if (node.lines) node.lines.forEach((row, i) => { row.style.opacity = ease((t - (t0 + 0.2 + i * (it.step ?? 1.2))) / 0.4); });
      if (tag) {
        const target = S.objIndex[it.target]; if (!target) { this.warn(`Tag target "${it.target}" not found`); node.style.opacity = 0; continue; }
        target.updateWorldMatrix(true, false); this.tmp.setFromMatrixPosition(target.matrixWorld);
        if (it.offset) this.tmp.add(new THREE.Vector3(...it.offset));
        this.tmp.project(camera);
        const x = this.win.x + (this.tmp.x * 0.5 + 0.5) * this.win.width, y = this.win.y + (-this.tmp.y * 0.5 + 0.5) * this.win.height;
        if (node.pin) {
          const dist = it.distance ?? o.pinDistance, dirs = { right: [1, 0], left: [-1, 0], up: [0, -1], down: [0, 1] };
          const [ux, uy] = it.dx !== undefined || it.dy !== undefined ? [0, 0] : (dirs[it.side || 'right'] || dirs.right);
          const dx = it.dx ?? ux * dist, dy = it.dy ?? uy * dist, len = Math.hypot(dx, dy);
          node.style.transform = `translate(${x + dx}px, ${y + dy}px) translate(-50%, -50%) scale(${0.85 + 0.15 * a})`;
          node.pin.dot.style.transform = `translate(${-dx - 8}px, ${-dy - 8}px)`;
          node.pin.line.style.width = `${len}px`; node.pin.line.style.transform = `rotate(${Math.atan2(-dy, -dx)}rad)`;
        } else node.style.transform = `translate(${x}px, ${y}px) translate(-50%, -140%) scale(${0.85 + 0.15 * a})`;
      } else {
        const anchors = this.layout.overlayAnchors || o.anchors;
        const anchor = anchors[it.anchor || 'upper'] ?? anchors.upper;
        const full = this.win.height === H;
        const y = full ? z.top + usable * anchor : this.win.y + this.win.height * anchor;
        node.style.left = `${this.win.x + z.side}px`; node.style.right = `${W - this.win.x - this.win.width + z.side}px`; node.style.top = `${y}px`;
        if (it.kind === 'pop' || it.kind === 'sticker') {   // overshoot pop-in, quick fade-out
          const k = clamp((t - t0) / 0.28, 0, 1), c1 = 1.70158, back = 1 + (c1 + 1) * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2);
          node.style.transform = `scale(${Math.max(0.01, back)}) rotate(${it.tilt ?? (it.kind === 'sticker' ? -3 : 0)}deg)`;
        } else node.style.transform = `translateY(${(1 - a) * 28}px) scale(${0.96 + 0.04 * a})`;
      }
    }
    this.updateCaptions(T);
    this.updateFade(T, t, dur, scenes, idx);
  }

  updateCaptions(T) { this._renderCaptions(T, this.cfg.captions); }

  setCaptions(words) {
    this.words = words;
    const n = this.cfg.captions.wordsPerChunk; this.chunks = [];
    let cur = [];
    words.forEach((w, i) => {
      cur.push(w);
      const endsSentence = /[.!?,;:]$/.test(w.w);
      if (cur.length >= n || (endsSentence && cur.length >= 2) || i === words.length - 1) { this.chunks.push(cur); cur = []; }
    });
  }

  _renderCaptions(T, c) {
    if (!this.chunks) return;
    const H = this.cfg.canvas.height, z = this.cfg.safeZone;
    let chunk = null;
    for (let i = 0; i < this.chunks.length; i++) {
      const ch = this.chunks[i]; const next = this.chunks[i + 1];
      const start = ch[0].t0, end = next ? Math.min(ch[ch.length - 1].t1 + 0.35, next[0].t0) : ch[ch.length - 1].t1 + 0.4;
      if (T >= start - 0.02 && T < end) { chunk = ch; break; }
    }
    if (!chunk) { this.caps.innerHTML = ''; this.lastChunk = null; return; }
    if (chunk !== this.lastChunk) {
      this.caps.innerHTML = ''; const box = el('div', 'capbox'); this.spans = chunk.map((w) => { const s = el('span', 'w'); s.textContent = w.w; box.append(s); return s; });
      this.caps.append(box); this.lastChunk = chunk; box.style.fontSize = `${c.fontSize}px`; box.style.fontWeight = c.weight;
      const lc = this.layout.captions || {};
      if (lc.strokeColor) box.style.setProperty('--cap-stroke', lc.strokeColor); // captions sit on the layout's own background, not on the look
      box.style.bottom = `${lc.bottom ?? z.bottom + c.bottomOffsetFromSafe}px`; if (lc.fontSize) box.style.fontSize = `${lc.fontSize}px`;
    }
    chunk.forEach((w, i) => {
      const s = this.spans[i]; const active = T >= w.t0 && T < w.t1; const done = T >= w.t1;
      const k = active ? clamp((T - w.t0) / c.popSeconds, 0, 1) : 1;
      const scale = active ? 1 + (c.activeScale - 1) * Math.sin(k * Math.PI * 0.5) : 1;
      s.style.transform = `scale(${scale})`;
      const lcap = this.layout.captions || {};
      s.style.color = active ? this.color(lcap.activeColor ?? c.activeColor) : this.color(lcap.idleColor ?? c.idleColor);
      s.style.opacity = active || done ? 1 : 0.55;
    });
  }

  updateFade(T, t, dur, scenes, idx) {
    const def = this.cfg.transitions.default; let a = 0;
    const own = scenes[idx].transition || def; const next = scenes[idx + 1]; const nxt = next ? (next.transition || def) : null;
    if (own.type !== 'none' && own.duration > 0 && idx > 0) a = Math.max(a, 1 - t / (own.duration / 2));
    if (nxt && nxt.type !== 'none' && nxt.duration > 0) a = Math.max(a, 1 - (dur - t) / (nxt.duration / 2));
    this.fade.style.opacity = clamp(a, 0, 1); this.fade.style.background = this.look.background.bottom;
  }
}

function el(tag, cls) { const e = document.createElement(tag); e.className = cls; return e; }
