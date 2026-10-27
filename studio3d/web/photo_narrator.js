// Photo narrator: a real photograph animated like a puppet. The head sways, the eyelids blink, the brows lift and the jaw drops
// with the voice. The face is cut along the mouth line into an upper and a lower mesh; the lower one (lips, chin) moves down and a
// dark cavity quad shows in the gap. All motion is a pure function of time, so frames stay reproducible.
// The warp functions are exported without any three.js dependency so node can test them.

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const smooth = (a, b, x) => { const k = clamp((x - a) / (b - a || 1e-9), 0, 1); return k * k * (3 - 2 * k); };

// Jaw displacement in original-photo pixels (down is positive): zero above the mouth line, the full drop over the chin,
// fading out to the neck, and fading out sideways beyond the cheeks.
export function jawDisplacement(L, M, x, y, open) {
  if (y < L.mouthY) return 0;
  const wy = 1 - smooth(L.chinY, L.neckY, y);
  const wx = 1 - smooth(M.jawFalloffX[0], M.jawFalloffX[1], Math.abs(x - L.mouthCx));
  return M.jawDrop * clamp(open, 0, 1) * wy * wx;
}

// Brow lift in original-photo pixels (up is negative), a soft blob over the brows.
export function browDisplacement(L, M, x, y, amount) {
  const gx = (x - L.browCx) / 560, gy = (y - L.browY) / 110;
  return -M.browLift * clamp(amount, 0, 1) * Math.exp(-0.5 * (gx * gx + gy * gy));
}

// 0 = open eye, 1 = closed. One quick blink every `every` seconds, with a small deterministic variation between blinks.
export function blinkAmount(M, t) {
  const every = M.blinkEvery, n = Math.floor(t / every), jitter = ((n * 2654435761) % 1000) / 1000;
  const start = n * every + 0.5 + jitter * (every - 1.2), k = (t - start) / M.blinkSeconds;
  return k < 0 || k > 1 ? 0 : Math.sin(Math.PI * k);
}

// Head motion: gentle sway and breathing, plus a short nod after each cue time.
export function headMotion(M, t, nods = []) {
  let nod = 0;
  for (const c of nods) { const k = (t - c) / 0.7; if (k >= 0 && k <= 1) nod += Math.sin(Math.PI * k) * Math.exp(-2 * k); }
  return { rollDeg: M.headSwayDeg * Math.sin(t * 0.62), pitch: nod * M.nodDeg, yawDeg: 0.8 * M.headSwayDeg * Math.sin(t * 0.37 + 1), scale: 1 + M.breath * Math.sin(t * 1.3) };
}

export class PhotoNarrator {
  constructor(THREE, cfg, texture) {
    this.THREE = THREE; this.cfg = cfg; const { crop, landmarks: L, motion: M, frame: F } = cfg;
    this.W = crop.x1 - crop.x0; this.H = crop.y1 - crop.y0; this.aspect = this.W / this.H;
    this.group = new THREE.Group(); this.pivot = new THREE.Group(); this.group.add(this.pivot);
    const mat = () => {
      const m = new THREE.MeshBasicMaterial({ map: texture, transparent: true, toneMapped: false, color: new THREE.Color(F.exposure, F.exposure, F.exposure) });
      m.onBeforeCompile = (sh) => {   // rounded-rectangle mask with a soft edge, evaluated in texture space
        sh.fragmentShader = sh.fragmentShader.replace('#include <map_fragment>', `#include <map_fragment>
          { vec2 q = abs(vMapUv - 0.5) - (vec2(0.5) - vec2(${F.radius.toFixed(4)} / ${this.aspect.toFixed(4)}, ${F.radius.toFixed(4)}));
            float d = length(max(q, 0.0) * vec2(${this.aspect.toFixed(4)}, 1.0)) + min(max(q.x * ${this.aspect.toFixed(4)}, q.y), 0.0) - ${F.radius.toFixed(4)};
            diffuseColor.a *= 1.0 - smoothstep(-${F.feather.toFixed(4)}, 0.0, d); }`);
      };
      return m;
    };
    const hi = this.hi = (x) => (x - crop.x0) / this.W, vi = (y) => (y - crop.y0) / this.H;   // original px -> 0..1 of the crop
    const build = (y0, y1, nx, ny) => {
      const geo = new THREE.BufferGeometry(), n = (nx + 1) * (ny + 1);
      const base = new Float32Array(n * 2), uv = new Float32Array(n * 2), idx = [];
      for (let j = 0; j <= ny; j++) for (let i = 0; i <= nx; i++) {
        const k = j * (nx + 1) + i, x = crop.x0 + (this.W * i) / nx, y = y0 + ((y1 - y0) * j) / ny;
        base[k * 2] = x; base[k * 2 + 1] = y; uv[k * 2] = hi(x); uv[k * 2 + 1] = 1 - vi(y);
        if (i < nx && j < ny) { const a = k, b = k + 1, c = k + nx + 1, d = k + nx + 2; idx.push(a, c, b, b, c, d); }
      }
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3)); geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); geo.setIndex(idx);
      const mesh = new THREE.Mesh(geo, mat()); mesh.frustumCulled = false; mesh.renderOrder = 2;
      return { mesh, geo, base, n };
    };
    this.upper = build(crop.y0, L.mouthY, 40, 52); this.lower = build(L.mouthY, crop.y1, 40, 24);
    this.cavity = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: this.makeCavityTexture(M), transparent: true, toneMapped: false })); this.cavity.renderOrder = 1; this.cavity.position.z = -0.001;
    this.lids = M.lidColors.map(() => new THREE.Mesh(new THREE.CircleGeometry(1, 32), new THREE.MeshBasicMaterial({ transparent: true, toneMapped: false })));
    this.lids.forEach((l, i) => { l.material.color.set(M.lidColors[i]); l.renderOrder = 3; l.position.z = 0.001; });
    this.border = this.makeBorder(THREE, F);
    this.pivot.add(this.cavity, this.upper.mesh, this.lower.mesh, ...this.lids, this.border);
  }

  // The mouth interior: dark at the top, a little warmer below (tongue and lower teeth in shadow), soft at both corners.
  makeCavityTexture(M) {
    const c = document.createElement('canvas'); c.width = 256; c.height = 64; const x = c.getContext('2d');
    const v = x.createLinearGradient(0, 0, 0, 64); v.addColorStop(0, M.cavityColor); v.addColorStop(1, M.cavityLow || '#2b1514'); x.fillStyle = v; x.fillRect(0, 0, 256, 64);
    const h = x.createLinearGradient(0, 0, 256, 0); h.addColorStop(0, 'rgba(0,0,0,0)'); h.addColorStop(0.18, 'rgba(0,0,0,1)'); h.addColorStop(0.82, 'rgba(0,0,0,1)'); h.addColorStop(1, 'rgba(0,0,0,0)');
    x.globalCompositeOperation = 'destination-in'; x.fillStyle = h; x.fillRect(0, 0, 256, 64);
    const t = new this.THREE.CanvasTexture(c); t.colorSpace = this.THREE.SRGBColorSpace; return t;
  }

  makeBorder(THREE, F) {
    const w = 512, h = Math.round(512 / this.aspect), c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d');
    const r = F.radius * h, bw = F.borderWidth * h; x.strokeStyle = F.borderColor; x.lineWidth = bw; x.beginPath();
    x.roundRect(bw / 2 + 1, bw / 2 + 1, w - bw - 2, h - bw - 2, r); x.stroke();
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(this.aspect, 1), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true, toneMapped: false }));
    mesh.renderOrder = 4; mesh.position.z = 0.002; return mesh;
  }

  // local units: the crop is 1 unit tall and `aspect` units wide, y up
  pos(x, y) { return [(this.hi(x) - 0.5) * this.aspect, 0.5 - (y - this.cfg.crop.y0) / this.H]; }

  update(T, t, voice, nods = []) {
    const { landmarks: L, motion: M } = this.cfg, v = voice(T), pxu = this.aspect / this.W, open = clamp(v * 1.15, 0, 1);
    const brow = clamp(0.6 * v + 0.4 * Math.max(0, Math.sin(t * 0.9)) * v, 0, 1);
    const set = (m, jaw) => {
      const p = m.geo.attributes.position;
      for (let k = 0; k < m.n; k++) {
        let x = m.base[k * 2], y = m.base[k * 2 + 1];
        y += jaw ? jawDisplacement(L, M, x, y, open) : browDisplacement(L, M, x, y, brow);
        const q = this.pos(x, y); p.setXYZ(k, q[0], q[1], 0);
      }
      p.needsUpdate = true;
    };
    set(this.upper, false); set(this.lower, true);
    // cavity quad fills the gap between the mouth line and the dropped lower lip
    const gap = Math.max(1e-4, M.jawDrop * open * 1.05), c0 = this.pos(L.mouthCx, L.mouthY - 6), c1 = this.pos(L.mouthCx, L.mouthY + gap);
    this.cavity.scale.set(2 * M.cavityHalfWidth * pxu, Math.max(1e-4, c0[1] - c1[1]), 1); this.cavity.position.set(c0[0], (c0[1] + c1[1]) / 2, -0.001);
    // eyelids come down from the top of each eye
    const b = blinkAmount(M, t);
    this.lids.forEach((lid, i) => {
      const e = i === 0 ? L.eyeL : L.eyeR, ry = L.eyeRy * pxu, rx = L.eyeRx * pxu, top = this.pos(e[0], e[1])[1] + ry;
      lid.visible = b > 0.02; lid.scale.set(rx, Math.max(1e-4, ry * 2 * b), 1); lid.position.set(this.pos(e[0], e[1])[0], top - ry * b, 0.001);
    });
    const h = headMotion(M, t, nods), D = Math.PI / 180;
    this.pivot.rotation.set(h.pitch * D, h.yawDeg * D, h.rollDeg * D); this.pivot.scale.setScalar(h.scale);
  }
}
