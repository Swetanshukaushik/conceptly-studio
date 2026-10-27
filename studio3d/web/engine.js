// Declarative 3D scene interpreter. A spec (JSON) describes objects, materials, camera and overlays;
// every numeric field may be a number or an expression of time (see expr.js), so motion, physics
// curves and reveals are data, not code. Rendering is a pure function of time: renderAt(T).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { numeric, compile, setSimProvider, setVoiceProvider } from './expr.js';
import { Sim, expandSim, simValue } from './physics.js';
import { Overlays } from './overlay.js';
import { makeTour, makeVoice } from './kit.js';
import { PhotoNarrator } from './photo_narrator.js';

const DEG = Math.PI / 180;

const SanitizeShader = {
  uniforms: { tDiffuse: { value: null } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
  // A single NaN pixel would spread through the bloom blur and blank the whole frame; clamp hot pixels too.
  fragmentShader: 'uniform sampler2D tDiffuse; varying vec2 vUv; void main(){ vec4 c = texture2D(tDiffuse, vUv); if (any(isnan(c)) || any(isinf(c))) c = vec4(0.0, 0.0, 0.0, 1.0); gl_FragColor = vec4(min(c.rgb, vec3(24.0)), 1.0); }',
};

const FinishShader = {
  uniforms: {
    tDiffuse: { value: null }, vignette: { value: 0.3 }, grain: { value: 0.02 }, chroma: { value: 0.0005 },
    contrast: { value: 1.05 }, saturation: { value: 1.05 }, time: { value: 0 },
  },
  vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
  fragmentShader: `
    uniform sampler2D tDiffuse; uniform float vignette, grain, chroma, contrast, saturation, time; varying vec2 vUv;
    float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453); }
    void main(){
      vec2 d = vUv - 0.5; float r = dot(d,d);
      vec2 off = d * chroma * (1.0 + r * 6.0);
      vec3 c = vec3(texture2D(tDiffuse, vUv + off).r, texture2D(tDiffuse, vUv).g, texture2D(tDiffuse, vUv - off).b);
      float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
      c = mix(vec3(l), c, saturation);
      c = (c - 0.5) * contrast + 0.5;
      c *= 1.0 - vignette * smoothstep(0.12, 0.62, r * 1.6);
      c += (h(vUv * 1000.0 + time) - 0.5) * grain;
      gl_FragColor = vec4(c, 1.0);
    }`,
};

export class Engine {
  constructor(spec, renderCfg, looks, layouts = {}, assetBase = '/assets/') {
    this.spec = spec; this.cfg = renderCfg; this.looks = looks; this.layouts = layouts; this.assetBase = assetBase;
    this.warnings = new Set();
    this.warn = (m) => this.warnings.add(m);
    this.current = null; this.currentIdx = -1;
  }

  async init(canvas) {
    this.layout = this.layouts[this.spec.layout || 'full'] || this.layouts.full || { window: { x: 0, y: 0, width: this.cfg.canvas.width, height: this.cfg.canvas.height } };
    if (this.spec.layout && !this.layouts[this.spec.layout]) this.warn(`Unknown layout "${this.spec.layout}", using full`);
    const win = this.win = this.layout.window;
    const W = win.width, H = win.height;
    this.W = W; this.H = H;
    if (canvas.parentElement && this.layout.background) canvas.parentElement.style.background = this.layout.background;   // the area around the 3D window
    canvas.width = W; canvas.height = H; canvas.style.left = `${win.x}px`; canvas.style.top = `${win.y}px`; canvas.style.width = `${W}px`; canvas.style.height = `${H}px`;
    const r = this.renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance', preserveDrawingBuffer: true });
    r.setPixelRatio(this.cfg.renderer.pixelRatio);
    r.setSize(W, H, false);
    r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.toneMapping = THREE.ACESFilmicToneMapping;
    this.pmrem = new THREE.PMREMGenerator(r);
    this.envTex = this.pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

    const fam = this.cfg.typography.family;
    await Promise.all(this.cfg.typography.fonts.map((f) => document.fonts.load(`${f.weight} 40px "${fam}"`)));

    this.camera = new THREE.PerspectiveCamera(40, W / H, 0.05, 200);
    const props = await (await fetch('/api/props')).json(); this.prefabs = props.prefabs; this.poses = props.poses;
    this.overlays = new Overlays(this.cfg, this.warn);
    this.overlays.mount(document.getElementById('overlay-root'));
    this.overlays.setLayout(this.layout, this.spec.header);
    this.captions = (this.spec.captions || []).slice().sort((a, b) => a.t0 - b.t0);
    this.overlays.setCaptions(this.captions);
    this.narrator = this.spec.narrator && this.layout.narrator ? this.spec.narrator : null;   // character layer: needs a layout with a narrator slot
    this.voiceFn = makeVoice(this.captions, (this.spec.narrator && this.spec.narrator.voice) || {}); setVoiceProvider(this.voiceFn);
    if (this.narrator && this.narrator.kind === 'photo') {   // a real photograph animated as a puppet (photo_narrator.js)
      const tex = await new THREE.TextureLoader().loadAsync(this.narrator.photo.image); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8; this.photoTexture = tex;
    }
    this.scenes = this.spec.scenes.slice().sort((a, b) => a.start - b.start);
    this.lookCache = {};
  }

  look(name) {
    const n = name || this.spec.look;
    const l = this.looks[n] || this.looks[Object.keys(this.looks)[0]];
    if (!this.looks[n]) this.warn(`Unknown look "${n}", using "${l.name}"`);
    return l;
  }

  color(c, look) {
    if (typeof c === 'string' && look.palette[c]) return new THREE.Color(look.palette[c]);
    try { return new THREE.Color(c); } catch { this.warn(`Bad colour "${c}"`); return new THREE.Color('#ffffff'); }
  }

  // ---------- scene building ----------
  buildScene(spec) {
    const look = this.look(spec.look);
    const scene = new THREE.Scene();
    const ctxScope = { dyn: [], mats: [], lineMats: [], pending: [], ctxExtra: spec.params || {} };

    // Background gradient via a big canvas texture
    const g = document.createElement('canvas'); g.width = 4; g.height = 512;
    const gc = g.getContext('2d'); const grad = gc.createLinearGradient(0, 0, 0, 512);
    const bg = { ...look.background, ...(spec.background || {}) };
    grad.addColorStop(0, bg.top); grad.addColorStop(1, bg.bottom); gc.fillStyle = grad; gc.fillRect(0, 0, 4, 512);
    const bgTex = new THREE.CanvasTexture(g); bgTex.colorSpace = THREE.SRGBColorSpace;
    scene.background = bgTex;
    scene.environment = this.envTex; scene.environmentIntensity = look.environment.intensity;
    const fogCfg = { ...look.fog, ...(spec.fog || {}) };
    if (fogCfg && fogCfg.far) scene.fog = new THREE.Fog(new THREE.Color(fogCfg.color), fogCfg.near, fogCfg.far);

    for (const l of look.lights) scene.add(this.makeLight(l, look));
    if (look.floor && look.floor.enabled && spec.floor !== false && !(spec.sim && spec.floor === undefined)) scene.add(this.makeFloor({ ...look.floor, ...(typeof spec.floor === 'object' ? spec.floor : {}) }, look));

    const root = new THREE.Group(); scene.add(root);
    const objIndex = {};
    let objects = this.expandProps(spec.objects || []);
    let photo = null, nods = [];
    if (this.narrator && this.narrator.kind === 'photo') {
      photo = new PhotoNarrator(THREE, this.narrator.photo, this.photoTexture); root.add(photo.group);
      nods = (spec.overlays || []).filter((o) => (this.narrator.pose_by_overlay || {})[o.kind] && typeof o.at === 'number').map((o) => spec.start + o.at);
    } else if (this.narrator) {   // the narrator is part of every scene: same place, same size; it gestures while the scene shows something to point at
      const nr = this.narrator, dur = spec.end - spec.start, base = nr.default_pose || 'speak';
      const isLast = this.scenes[this.scenes.length - 1] === spec;
      const wins = [];
      for (const o of spec.overlays || []) {
        const pose = (nr.pose_by_overlay || {})[o.kind], a = typeof o.at === 'number' ? o.at : (o.at === undefined ? 0 : NaN);
        if (pose && pose !== base && Number.isFinite(a)) wins.push({ pose, a, b: typeof o.until === 'number' ? o.until : Math.min(dur, a + 4) });
      }
      if (isLast && nr.last_scene_pose) wins.push({ pose: nr.last_scene_pose, a: Math.max(0, dur - 3), b: dur });
      const gesture = spec.narrator_pose || (wins[0] && wins[0].pose);
      const params = { ...(nr.params || {}), pose: base };
      const P0 = this.poses[base] || {}, P1 = this.poses[gesture] || {};
      if (gesture && gesture !== base) {   // blend joint angles between the speaking pose and the gesture pose with a gate that is open during the windows
        const gate = (spec.narrator_pose ? [{ a: 0, b: dur }] : wins.filter((w) => w.pose === gesture)).map((w) => `smooth(${w.a - 0.3},${w.a},t)*(1-smooth(${w.b},${w.b + 0.3},t))`);
        const G = gate.length > 1 ? `max(${gate.join(',')})` : gate[0];
        for (const k of new Set([...Object.keys(P0), ...Object.keys(P1)])) params[k] = `mix(${P0[k] ?? 0},${P1[k] ?? 0},${G})`;
      }
      objects = objects.concat(this.expandProps([{ type: 'prop', prefab: 'narrator', id: '__narrator', params }]));
    }
    let sim = null;
    if (spec.sim) {
      // Bodies need something to land on: with gravity and no surfaces declared, add the ground at y = 0 (sim.ground:false opts out)
      const g = spec.sim.gravity ?? [0, -9.8];
      if (!(spec.sim.surfaces || []).length && spec.sim.ground !== false && (g[0] || g[1])) spec.sim = { ...spec.sim, surfaces: [{ p1: [-60, 0], p2: [60, 0], mu: 0.5, e: 0.4, bounds: false }] };
      sim = new Sim(spec.sim, this.warn); const rate = spec.sim.timeScale ?? 1;
      const runFor = ((spec.end - spec.start) - (spec.sim.start ?? 0)) * rate + 0.25;
      sim.run(runFor);
      // A floor that is too short for the motion is almost always a mistake: bodies would fall off its end forever.
      // Extend the lowest horizontal surface to cover the bodies' horizontal reach and run again (sim.autoGround:false opts out).
      const flat = (spec.sim.surfaces || []).filter((sf) => Math.abs(sf.p1[1] - sf.p2[1]) < 1e-6);
      if (flat.length && spec.sim.autoGround !== false) {
        const floor = flat.reduce((a, b) => (b.p1[1] < a.p1[1] ? b : a));
        const bb0 = sim.bounds();
        if (bb0 && bb0.y0 < floor.p1[1] - 3) {
          const lo = Math.min(floor.p1[0], floor.p2[0], bb0.x0 - 1), hi = Math.max(floor.p1[0], floor.p2[0], bb0.x1 + 1);
          spec.sim = { ...spec.sim, surfaces: spec.sim.surfaces.map((sf) => (sf === floor ? { ...sf, p1: [lo, floor.p1[1]], p2: [hi, floor.p2[1]] } : sf)) };
          sim = new Sim(spec.sim, this.warn); sim.run(runFor);
        }
      }
      const bb = sim.bounds(); if (bb && (bb.y0 < -40 || bb.y1 > 400 || bb.x1 - bb.x0 > 400)) this.warn(`sim: bodies travel far out of the picture (extent ${Math.round(bb.x1 - bb.x0)} x ${Math.round(bb.y1 - bb.y0)} units; lowest point ${Math.round(bb.y0)}): add floors or walls as sim surfaces (scene objects do not stop bodies), or shorten the run`);
      objects = objects.concat(expandSim(spec.sim, objects, this.warn));
    }
    ctxScope.sim = sim;
    for (const o of objects) this.buildObject(o, root, look, ctxScope, objIndex);

    // Camera expressions
    const cam = spec.camera || { position: [0, 2.5, 7], target: [0, 1, 0], fov: 40 };
    let fit = null;   // scenes with a `sim` frame the whole simulated motion automatically unless camera.fit is false
    if (sim && cam.fit !== false) {
      const b = sim.bounds();
      if (b) {
        const m = cam.margin ?? 0.18, w = (b.x1 - b.x0) * (1 + 2 * m) + 0.6, h = (b.y1 - b.y0) * (1 + 2 * m) + 0.6, t = Math.tan((cam.fov ?? 40) * DEG / 2);
        const d = Math.max(h / (2 * t), w / (2 * t * (this.W / this.H))); const cx = (b.x0 + b.x1) / 2, cy = (b.y0 + b.y1) / 2;
        fit = { pos: [() => cx, () => cy, () => d], tgt: [() => cx, () => cy, () => 0] };
      }
    }
    const tour = cam.tour ? makeTour(cam.tour, this.warn) : null;   // explainer kit: waypoints flown with eased spline motion
    const cexp = {
      pos: tour ? tour.pos : fit ? fit.pos : (cam.position || [0, 2.5, 7]).map((v) => numeric(v, this.warn)),
      tgt: tour ? tour.tgt : fit ? fit.tgt : (cam.target || [0, 1, 0]).map((v) => numeric(v, this.warn)),
      fov: tour ? tour.fov : numeric(cam.fov ?? 40, this.warn), roll: numeric(cam.roll ?? 0, this.warn),
    };
    const dispose = () => { scene.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) [].concat(o.material).forEach((m) => { Object.values(m).forEach((v) => v && v.isTexture && v.dispose()); m.dispose(); }); }); bgTex.dispose(); };
    return { spec, look, scene, root, objIndex, ctxScope, cexp, dispose, photo, nods };
  }

  // ---------- prefabs (data-driven props: config/props/*.json) ----------
  subst(value, params) {
    if (typeof value === 'string') {
      const out = value.replace(/\$\{([^}]+)\}/g, (_, expr) => {
        if (expr.startsWith('pick:')) {
          const [, name, list] = expr.split(':'); if (params[name] === undefined) return `\${${expr}}`;
          const opts = list.split('|'); const k = Math.floor(Number(params[name])); return opts[((k % opts.length) + opts.length) % opts.length];
        }
        const v = params[expr.trim()];
        if (v === undefined) return `\${${expr}}`; // resolved later by an enclosing repeat, else reported after expansion
        return String(v);
      });
      return /^-?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i.test(out) ? Number(out) : out;
    }
    if (Array.isArray(value)) return value.map((v) => this.subst(v, params));
    if (value && typeof value === 'object') { const o = {}; for (const [k, v] of Object.entries(value)) if (v !== undefined) o[k] = this.subst(v, params); return o; }
    return value;
  }

  expandProps(list, depth = 0) {
    const out = [];
    if (depth > 8) { this.warn('Props nested too deeply'); return out; }
    for (const o of list) {
      const reps = o.repeat ? Math.min(300, Math.max(1, Math.floor(Number(o.repeat)))) : 1;
      for (let i = 0; i < reps; i++) {
        const obj = o.repeat ? this.subst({ ...o, repeat: undefined }, { i, n: reps }) : o;
        out.push(...this.expandOne(obj, depth));
      }
    }
    if (depth === 0) { const left = JSON.stringify(out).match(/\$\{[^}]*\}/g); if (left) this.warn(`Unresolved prop parameters: ${[...new Set(left)].slice(0, 5).join(', ')}`); }
    return out;
  }

  expandOne(o, depth) {
    if (o.type !== 'prop') { const c = { ...o }; if (c.children) c.children = this.expandProps(c.children, depth + 1); return [c]; }
    const pf = this.prefabs[o.prefab];
    if (!pf) { this.warn(`Unknown prefab "${o.prefab}"`); return []; }
    const poseName = o.pose || o.params?.pose || pf.params?.pose;
    const pose = pf.poseable && poseName ? this.poses[poseName] : null;
    if (pf.poseable && poseName && !pose) this.warn(`Unknown pose "${poseName}" (available: ${Object.keys(this.poses).join(', ')})`);
    const merged = { ...pf.params, ...(pose || {}), ...(o.params || {}), ...(poseName ? { pose: poseName } : {}) };
    let params = {}; // expression-valued parameters are parenthesised so they compose safely inside larger expressions
    for (const [k, v] of Object.entries(merged)) params[k] = typeof v === 'string' && !v.startsWith('#') && /[-+*/^(),<>!&|%]/.test(v) ? `(${v})` : v;
    for (let pass = 0; pass < 6; pass++) params = this.subst(params, params); // parameters may reference one another (poses use ${speed})
    const tree = this.subst(JSON.parse(JSON.stringify(pf.objects)), params);
    return [{ type: 'group', id: o.id || o.prefab, background: pf.background || o.background, helper: pf.helper || o.helper, position: o.position, rotation: o.rotation, scale: o.scale, appear: o.appear, vanish: o.vanish, visible: o.visible, parent: o.parent, children: this.expandProps(tree, depth + 1) }];
  }

  makeLight(l, look) {
    const col = this.color(l.color, look);
    let L;
    if (l.type === 'ambient') L = new THREE.AmbientLight(col, l.intensity);
    else if (l.type === 'point') { L = new THREE.PointLight(col, l.intensity, l.distance || 0, 2); L.position.fromArray(l.position); }
    else if (l.type === 'spot') { L = new THREE.SpotLight(col, l.intensity, l.distance || 0, (l.angle || 30) * DEG, 0.5, 2); L.position.fromArray(l.position); if (l.target) L.target.position.fromArray(l.target); }
    else {
      L = new THREE.DirectionalLight(col, l.intensity); L.position.fromArray(l.position);
      if (l.castShadow) {
        L.castShadow = true; L.shadow.mapSize.set(this.cfg.renderer.shadowMapSize, this.cfg.renderer.shadowMapSize);
        const s = 10; Object.assign(L.shadow.camera, { left: -s, right: s, top: s, bottom: -s, near: 0.5, far: 50 });
        L.shadow.bias = -0.0004; L.shadow.normalBias = 0.03; L.shadow.radius = 4;
      }
    }
    return L;
  }

  makeFloor(f, look) {
    const size = f.size || f.grid?.size || 60; const spacing = f.grid?.spacing || 1;
    const grid = document.createElement('canvas'); grid.width = grid.height = 512; const gx = grid.getContext('2d');
    gx.fillStyle = '#000'; gx.fillRect(0, 0, 512, 512);
    if (f.grid) { gx.strokeStyle = f.grid.color; gx.lineWidth = 3; gx.strokeRect(0, 0, 512, 512); }
    const gridTex = new THREE.CanvasTexture(grid); gridTex.wrapS = gridTex.wrapT = THREE.RepeatWrapping; gridTex.repeat.set(size / spacing, size / spacing);
    gridTex.anisotropy = 16; gridTex.colorSpace = THREE.SRGBColorSpace;
    const fade = document.createElement('canvas'); fade.width = fade.height = 256; const fx = fade.getContext('2d');
    const rg = fx.createRadialGradient(128, 128, 20, 128, 128, 128); rg.addColorStop(0, '#fff'); rg.addColorStop(0.55, '#aaa'); rg.addColorStop(1, '#000');
    fx.fillStyle = rg; fx.fillRect(0, 0, 256, 256);
    const mat = new THREE.MeshStandardMaterial({
      color: this.color(f.color, look), roughness: f.roughness, metalness: f.metalness, envMapIntensity: f.reflectMix ?? 0.6,
      emissive: new THREE.Color('#ffffff'), emissiveMap: gridTex, emissiveIntensity: (f.grid?.opacity ?? 0.1) * 5,
      alphaMap: new THREE.CanvasTexture(fade), transparent: true, depthWrite: true,
    });
    const geo = new THREE.PlaneGeometry(size, size); geo.rotateX(-Math.PI / 2);
    const floor = new THREE.Mesh(geo, mat); floor.position.y = f.y ?? 0; floor.receiveShadow = true;
    return floor;
  }

  // Closest preset by word: configured aliases first (steel -> metal), then shared letters, then the first preset of the look.
  resolveMaterialName(name, look) {
    const names = Object.keys(look.materials), aliases = this.cfg.materialAliases || {}, words = String(name).toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
    for (const w of words) { const a = aliases[w]; if (a && look.materials[a]) return a; if (look.materials[w]) return w; }
    const grams = (t) => { const g = new Set(); for (let i = 0; i < t.length - 1; i++) g.add(t.slice(i, i + 2)); return g; };
    let best = null, bestScore = 0; const mine = grams(String(name).toLowerCase());
    for (const n of names) { const o = grams(n.toLowerCase()); let hit = 0; for (const g of mine) if (o.has(g)) hit++; const sc = hit / Math.max(1, Math.max(mine.size, o.size)); if (sc > bestScore) { bestScore = sc; best = n; } }
    return best && bestScore >= 0.25 ? best : (names.includes('matte') ? 'matte' : names[0]);
  }

  makeMaterial(m, look, scope) {
    let spec = typeof m === 'string' ? { preset: m } : { ...(m || {}) };
    if (!spec.preset && !spec.color) spec.preset = Object.keys(look.materials).includes('plastic') ? 'plastic' : Object.keys(look.materials)[0];
    let base = {};
    if (spec.preset) {
      if (look.materials[spec.preset]) base = look.materials[spec.preset];
      else {   // a preset the model invented ("dark_steel"): use the closest real one instead of failing the reel
        const alias = this.resolveMaterialName(spec.preset, look);
        base = look.materials[alias]; this.warn(`Unknown material preset "${spec.preset}", using "${alias}"`);
      }
    }
    const p = { ...base, ...spec }; delete p.preset;
    const dyn = {};
    for (const k of ['opacity', 'emissiveIntensity']) if (typeof p[k] === 'string') { dyn[k] = numeric(p[k], this.warn); p[k] = 1; }
    const params = { color: this.color(p.color ?? '#ffffff', look), metalness: p.metalness ?? 0, roughness: p.roughness ?? 0.5 };
    if (p.emissive) { params.emissive = this.color(p.emissive, look); params.emissiveIntensity = p.emissiveIntensity ?? 1; }
    for (const k of ['transmission', 'thickness', 'ior', 'clearcoat', 'clearcoatRoughness', 'sheen', 'iridescence']) if (p[k] !== undefined) params[k] = p[k];
    if ((p.opacity ?? 1) < 1 || dyn.opacity) { params.transparent = true; params.opacity = p.opacity ?? 1; }
    if (p.wireframe) params.wireframe = true;
    if (p.pattern) params.map = this.patternTexture(p.pattern, params.color, look);
    params.side = p.doubleSided ? THREE.DoubleSide : THREE.FrontSide;
    const mat = new THREE.MeshPhysicalMaterial(params);
    if (p.transmission) { mat.attenuationColor = this.color(p.color ?? '#ffffff', look); mat.attenuationDistance = 2; }
    const entry = { mat, dyn, baseOpacity: params.opacity ?? 1, baseEmissive: params.emissiveIntensity ?? 1 };
    scope.mats.push(entry);
    return mat;
  }

  // Procedural surface textures: lines (text-like), grid, checker, stripes, dots, bricks, planks, noise.
  patternTexture(pat, baseColor, look) {
    const kind = typeof pat === 'string' ? pat : pat.kind; const o = typeof pat === 'string' ? {} : pat;
    const size = 512, c = document.createElement('canvas'); c.width = c.height = size; const x = c.getContext('2d');
    const base = '#' + baseColor.getHexString(); const ink = o.color2 ? this.color(o.color2, look).getStyle() : 'rgba(30,25,20,0.55)';
    x.fillStyle = base; x.fillRect(0, 0, size, size); x.strokeStyle = ink; x.fillStyle = ink; x.lineWidth = 3;
    const n = Math.max(2, Math.round(o.count ?? 12));
    if (kind === 'lines') { for (let i = 0; i < n; i++) { const y = size * (0.12 + 0.76 * i / (n - 1)); const w = size * (0.55 + 0.4 * Math.abs(Math.sin(i * 12.9898))); x.globalAlpha = 0.5; x.fillRect(size * 0.1, y, w, 4); x.globalAlpha = 1; } }
    else if (kind === 'grid') { for (let i = 0; i <= n; i++) { const p = size * i / n; x.beginPath(); x.moveTo(p, 0); x.lineTo(p, size); x.moveTo(0, p); x.lineTo(size, p); x.stroke(); } }
    else if (kind === 'checker') { for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if ((i + j) % 2) x.fillRect(i * size / n, j * size / n, size / n, size / n); }
    else if (kind === 'stripes') { for (let i = 0; i < n; i += 2) x.fillRect(i * size / n, 0, size / n, size); }
    else if (kind === 'dots') { for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { x.beginPath(); x.arc((i + 0.5) * size / n, (j + 0.5) * size / n, size / n / 4, 0, 7); x.fill(); } }
    else if (kind === 'bricks') { const h = size / n; for (let j = 0; j < n; j++) { x.fillRect(0, j * h, size, 3); const off = (j % 2) * h; for (let i = 0; i < n / 2 + 1; i++) x.fillRect(off + i * h * 2, j * h, 3, h); } }
    else if (kind === 'planks') { const h = size / n; for (let j = 0; j < n; j++) { x.fillRect(0, j * h, size, 3); x.fillRect((j * 97) % size, j * h, 3, h); } }
    else if (kind === 'noise') { const d = x.getImageData(0, 0, size, size); for (let i = 0; i < d.data.length; i += 4) { const v = (Math.sin(i * 0.0137) * 43758.5453 % 1) * 28 - 14; d.data[i] += v; d.data[i + 1] += v; d.data[i + 2] += v; } x.putImageData(d, 0, 0); }
    else this.warn(`Unknown material pattern "${kind}"`);
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.anisotropy = 8;
    tex.repeat.set(o.repeat?.[0] ?? 1, o.repeat?.[1] ?? 1);
    return tex;
  }

  buildObject(o, parent, look, scope, index) {
    const warn = this.warn;
    let node; let geoUpdate = null; let castShadow = o.castShadow !== false; let lineMat = null;
    const mat = () => this.makeMaterial(o.material, look, scope);
    const N = (v, d) => numeric(v ?? d, warn);
    const st = (v, d, name) => this.staticNum(v, d, name, o, scope);

    switch (o.type) {
      case 'group': node = new THREE.Group(); break;
      case 'sphere': {
        const r = N(o.radius, 0.5); node = new THREE.Mesh(new THREE.SphereGeometry(1, 64, 48), mat());
        node.userData.sizeFn = (c) => { const k = r(c); return [k, k, k]; }; break;
      }
      case 'box': {
        const sz = (o.size || [1, 1, 1]).map((v) => N(v, 1));
        node = new THREE.Mesh(new RoundedBoxGeometry(1, 1, 1, 5, st(o.bevel, 0.06, 'bevel')), mat());
        node.userData.sizeFn = (c) => sz.map((f) => f(c)); break;
      }
      case 'cylinder': {
        const r = N(o.radius, 0.5), h = N(o.height, 1);
        const rb = st(o.radiusBottom, 1, 'radiusBottom'), rt = st(o.radiusTop, 1, 'radiusTop'); // relative to `radius`
        node = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, 1, 64, 1, !!o.openEnded), mat());
        node.userData.sizeFn = (c) => { const k = r(c); return [k, h(c), k]; }; break;
      }
      case 'cone': {
        const r = N(o.radius, 0.5), h = N(o.height, 1);
        node = new THREE.Mesh(new THREE.ConeGeometry(1, 1, 64), mat());
        node.userData.sizeFn = (c) => { const k = r(c); return [k, h(c), k]; }; break;
      }
      case 'torus': {
        const r = N(o.radius, 1), r0 = Math.max(1e-3, r({ ...scope.ctxExtra, t: 0, p: 0, T: 0 }));
        node = new THREE.Mesh(new THREE.TorusGeometry(1, st(o.tube, 0.15, 'tube') / r0, 32, 128), mat());
        node.userData.sizeFn = (c) => { const k = r(c); return [k, k, k]; }; break;
      }
      case 'capsule': node = new THREE.Mesh(new THREE.CapsuleGeometry(st(o.radius, 0.3, 'radius'), st(o.length, 1, 'length'), 12, 32), mat()); break;
      case 'plane': {
        const sz = (o.size || [1, 1]).map((v) => N(v, 1));
        node = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat()); if (!o.material?.doubleSided) node.material.side = THREE.DoubleSide;
        node.userData.sizeFn = (c) => [sz[0](c), sz[1](c), 1]; break;
      }
      case 'ring': node = new THREE.Mesh(new THREE.RingGeometry(st(o.inner, 0.7, 'inner'), st(o.outer, 1, 'outer'), 96), mat()); node.material.side = THREE.DoubleSide; break;
      case 'lathe': {
        const pts = (o.profile || [[0.3, 0], [0.5, 0.5], [0.3, 1]]).map(([r, y]) => new THREE.Vector2(r, y));
        const smooth = o.smooth ? new THREE.SplineCurve(pts).getPoints(Math.max(24, pts.length * 12)) : pts;
        node = new THREE.Mesh(new THREE.LatheGeometry(smooth, 96), mat()); node.material.side = THREE.DoubleSide; break;
      }
      case 'extrude': {
        const shape = new THREE.Shape((o.shape || [[-1, -1], [1, -1], [0, 1]]).map(([x, y]) => new THREE.Vector2(x, y)));
        const geo = new THREE.ExtrudeGeometry(shape, { depth: st(o.depth, 0.4, 'depth'), bevelEnabled: true, bevelThickness: st(o.bevel, 0.04, 'bevel'), bevelSize: st(o.bevel, 0.04, 'bevel'), bevelSegments: 4, curveSegments: 32 });
        geo.translate(0, 0, -st(o.depth, 0.4, 'depth') / 2); node = new THREE.Mesh(geo, mat()); break;
      }
      case 'tube': {
        const pts = (o.points || [[0, 0, 0], [1, 1, 0], [2, 0, 0]]).map((p) => new THREE.Vector3(...p));
        node = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), o.segments ?? 128, st(o.radius, 0.05, 'radius'), 16, !!o.closed), mat()); break;
      }
      case 'image': {
        const w = o.size?.[0] ?? 3, h = o.size?.[1] ?? 4;
        const m = new THREE.MeshBasicMaterial({ transparent: true, side: THREE.DoubleSide, toneMapped: false, color: new THREE.Color().setScalar(o.dim ?? 0.82) });
        node = new THREE.Mesh(new THREE.PlaneGeometry(w, h), m); castShadow = false;
        if (o.src) {
          scope.pending.push(new THREE.TextureLoader().loadAsync(this.assetBase + o.src).then((tex) => {
            tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8; m.map = tex; m.needsUpdate = true;
            const img = tex.image; const asp = img.width / img.height; // contain-fit inside the requested box
            const fit = asp > w / h ? [1, (w / asp) / h, 1] : [(h * asp) / w, 1, 1];
            node.userData.baseScale = fit;
          }).catch(() => warn(`Image failed to load: ${o.src}`)));
        } else { node.userData.noImage = true; if (!o.query) warn(`Image object "${o.id}" has neither src nor query`); }
        break;
      }
      case 'glow': {
        const c = document.createElement('canvas'); c.width = c.height = 256; const x = c.getContext('2d');
        const gr = x.createRadialGradient(128, 128, 0, 128, 128, 128); gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.25, 'rgba(255,255,255,0.35)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
        x.fillStyle = gr; x.fillRect(0, 0, 256, 256);
        const m = new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), color: this.color(o.color ?? 'primary', look), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.9, fog: false });
        node = new THREE.Sprite(m); const size = N(o.size, 1.5), inten = N(o.intensity, 0.9);
        node.userData.isSprite = true; node.userData.intensity = inten;
        node.userData.sizeFn = (cx) => { const k = size(cx); return [k, k, 1]; }; castShadow = false; break;
      }
      case 'label': node = this.makeLabel(o, look); castShadow = false; break;
      case 'light': {
        node = this.makeLight({ type: o.kind || 'point', color: o.color ?? '#ffffff', intensity: 1, position: [0, 0, 0], distance: st(o.distance, 0, 'distance') }, look);
        node.userData.lightIntensity = N(o.intensity, 20); break;
      }
      case 'curve': { const r = this.makeCurve(o, look, scope); node = r.node; geoUpdate = r.update; lineMat = r.mat; castShadow = false; break; }
      case 'rope': {
        const pts = (o.points || [[0, 0, 0], [0, 1, 0]]).map((p) => p.map((v) => N(v, 0)));
        const radius = st(o.radius, 0.03, 'radius');
        node = new THREE.Mesh(new THREE.BufferGeometry(), mat());
        geoUpdate = (c) => {
          const v = pts.map((p) => new THREE.Vector3(p[0](c), p[1](c), p[2](c))); const path = new THREE.CurvePath();
          for (let i = 1; i < v.length; i++) if (v[i].distanceToSquared(v[i - 1]) > 1e-10) path.add(new THREE.LineCurve3(v[i - 1], v[i]));
          if (!path.curves.length) return;
          node.geometry.dispose(); node.geometry = new THREE.TubeGeometry(path, Math.min(800, v.length * 3), radius, 10, false);
        };
        break;
      }
      case 'arrow': { const r = this.makeArrow(o, look, scope); node = r.node; geoUpdate = r.update; break; }
      case 'surface': { const r = this.makeSurface(o, look, scope); node = r.node; geoUpdate = r.update; break; }
      case 'particles': { const r = this.makeParticles(o, look, scope); node = r.node; geoUpdate = r.update; break; }
      case 'flow': { const r = this.makeFlow(o, look, scope); node = r.node; geoUpdate = r.update; castShadow = false; break; }
      case 'vectorfield': { const r = this.makeVectorField(o, look, scope); node = r.node; geoUpdate = r.update; break; }
      default: warn(`Unknown object type "${o.type}"`); node = new THREE.Group();
    }

    node.name = o.id || o.type; node.userData.kind = o.type; node.userData.background = !!o.background; node.userData.helper = !!o.helper;
    if (o.id) index[o.id] = node;
    node.traverse((n) => { if (n.isMesh) { n.castShadow = castShadow; n.receiveShadow = o.receiveShadow !== false; } });

    const pos = (o.position || [0, 0, 0]).map((v) => numeric(v, warn));
    const rot = (o.rotation || [0, 0, 0]).map((v) => numeric(v, warn));
    let scl;
    if (o.scale === undefined) scl = [() => 1, () => 1, () => 1];
    else if (Array.isArray(o.scale)) scl = o.scale.map((v) => numeric(v, warn));
    else { const f = numeric(o.scale, warn); scl = [f, f, f]; }
    const sizeFn = node.userData.sizeFn;
    const appear = o.appear ? { t0: numeric(o.appear.at ?? 0, warn), dur: o.appear.duration ?? 0.5, style: o.appear.style || 'pop' } : null;
    const vanish = o.vanish ? { t0: numeric(o.vanish.at, warn), dur: o.vanish.duration ?? 0.3 } : null;
    const visible = o.visible !== undefined ? numeric(o.visible, warn) : null;

    // `vars` binds extra expression variables for this object only (e.g. {X: 'ts'}), so one expression can be reused at another X
    const varFns = o.vars ? Object.entries(o.vars).map(([k, v]) => [k, numeric(v, warn)]) : null;
    const rec = {
      node, o,
      update: (c0) => {
        let c = c0; if (varFns) { c = { ...c0 }; for (const [k, f] of varFns) c[k] = f(c); }   // variables may use the ones defined before them
        node.position.set(pos[0](c), pos[1](c), pos[2](c));
        node.rotation.set(rot[0](c) * DEG, rot[1](c) * DEG, rot[2](c) * DEG);
        let k = 1, alpha = 1, show = true;
        if (appear) { const a = appear.t0(c); const x = (c.t - a) / appear.dur; if (x <= 0) show = false; else { const xx = Math.min(1, x); k = appear.style === 'fade' ? 1 : popEase(xx); alpha = Math.min(1, xx * 1.6); } }
        if (vanish) { const v = vanish.t0(c); const x = (c.t - v) / vanish.dur; if (x >= 1) show = false; else if (x > 0) { k *= 1 - x * 0.35; alpha *= 1 - x; } }
        if (visible && visible(c) <= 0) show = false;
        node.visible = show && !node.userData.noImage;
        const baseS = node.userData.baseScale || [1, 1, 1];
        const sz = sizeFn ? sizeFn(c) : [1, 1, 1];
        node.scale.set(baseS[0] * scl[0](c) * sz[0] * k, baseS[1] * scl[1](c) * sz[1] * k, baseS[2] * scl[2](c) * sz[2] * k);
        node.userData.alpha = alpha;
        if (node.userData.lightIntensity) node.intensity = Math.max(0, node.userData.lightIntensity(c)) * alpha;
        if (node.userData.isSprite) node.material.opacity = Math.max(0, Math.min(1.5, node.userData.intensity(c))) * alpha;
        if (geoUpdate && show) geoUpdate(c, alpha);
      },
      materials: [],
    };
    scope.dyn.push(rec);
    // propagate fade to materials of this node (only when appear/vanish present)
    if (appear || vanish) rec.fadeMats = true;

    if (o.parent && index[o.parent]) index[o.parent].add(node); else parent.add(node);
    if (o.children) for (const ch of o.children) this.buildObject({ ...ch }, node, look, scope, index);
    return node;
  }

  // Fields that shape geometry once (not per frame) must be plain numbers; expressions are evaluated at t=0 and flagged.
  staticNum(v, d, name, o, scope) {
    if (v === undefined || v === null) return d;
    if (typeof v === 'number') return v;
    this.warn(`${o.type} "${o.id || ''}": field "${name}" must be a plain number, not an expression`);
    try { const f = numeric(v, this.warn)({ ...scope.ctxExtra, t: 0, p: 0, T: 0 }); return Number.isFinite(f) ? f : d; } catch { return d; }
  }

  sizeRef(o, node, key, scope, toVec) {
    const f = numeric(o[key] ?? 0.5, this.warn);
    node.userData.sizeFn = (c) => toVec(f(c));
  }

  makeLabel(o0, look) {
    const o = { ...o0, text: String(o0.text ?? '').replace(/^\((-?\d+(?:\.\d+)?)\)$/, '$1') };   // prefab params that contain an operator arrive parenthesised: show plain numbers as numbers
    const res = this.cfg.renderer.labelResolution; const fam = this.cfg.typography.family;
    const size = 96; const c = document.createElement('canvas'); const x = c.getContext('2d');
    x.font = `800 ${size}px "${fam}"`; const w = Math.ceil(x.measureText(o.text).width) + 40;
    c.width = w * res / 2 * 2; c.height = (size + 40) * res; const s = res;
    const x2 = c.getContext('2d'); x2.scale(s, s); x2.font = `800 ${size}px "${fam}"`; x2.textBaseline = 'middle'; x2.textAlign = 'center';
    const col = this.color(o.color ?? 'ink', look).getStyle();
    x2.shadowColor = col; x2.shadowBlur = o.glow ? 24 : 0; x2.fillStyle = col; x2.fillText(o.text, (c.width / s) / 2, (c.height / s) / 2);
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
    const h = this.staticNum(o.size, 0.5, 'size', o, { ctxExtra: {} }); const aspect = c.width / c.height;
    const m = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(h * aspect, h), m);
    mesh.userData.billboard = o.billboard !== false;
    return mesh;
  }

  makeCurve(o, look, scope) {
    const n = o.samples ?? 160; const [u0, u1] = o.range || [0, 1];
    const fx = numeric(o.x ?? 'u', this.warn), fy = numeric(o.y ?? '0', this.warn), fz = numeric(o.z ?? '0', this.warn);
    const pts = o.points ? o.points.map((p) => p.map((v) => numeric(v, this.warn))) : null;
    const geo = new LineGeometry(); const arr = new Float32Array(n * 3);
    const mat = new LineMaterial({ color: this.color(o.color ?? 'primary', look), linewidth: o.width ?? 6, worldUnits: false, transparent: true, opacity: o.opacity ?? 1, dashed: !!o.dashed, dashSize: 0.15, gapSize: 0.1 });
    mat.resolution.set(this.W, this.H);
    const line = new Line2(geo, mat);
    const draw = numeric(o.draw ?? 1, this.warn); // fraction 0..1 of the curve drawn so far
    const plot = o.plot; const vname = o.var || 'X';
    const rng = (r) => r && r.map((v) => (typeof v === 'number' ? v : numeric(v, this.warn)({})));   // plot ranges may arrive as constant expressions (prefab parameters)
    const pr = plot ? { x: rng(plot.x), y: rng(plot.y), s: rng(plot.s) } : null;
    const update = (c, alpha) => {
      const nn = pts ? pts.length : n; const a = pts ? new Float32Array(nn * 3) : arr; const cc = { ...c };
      if (plot) {   // data-space plotting: x and y are expressions of the variable (default X) over plot.x, mapped into a w x h box
        const [x0, x1] = pr.x, [y0, y1] = pr.y, Wd = plot.w ?? 2, Hd = plot.h ?? 1.5;
        let last = -1, firstIn = -1; const inside = new Array(nn);
        for (let i = 0; i < nn; i++) {
          const [s0, s1] = pr.s || pr.x; const X = s0 + (s1 - s0) * (i / (nn - 1)); cc.u = i / (nn - 1); cc[vname] = X;   // plot.s: parameter range when it differs from the x range (sideways curves)
          const xv = o.x === undefined ? X : fx(cc), yv = fy(cc), yn = (yv - y0) / (y1 - y0);
          a[i * 3] = ((xv - x0) / (x1 - x0)) * Wd; a[i * 3 + 1] = Math.max(-0.05, Math.min(1.05, yn)) * Hd; a[i * 3 + 2] = 0;
          inside[i] = yn >= -0.05 && yn <= 1.05; if (inside[i] && firstIn < 0) firstIn = i;
        }
        if (o.clip !== false && firstIn >= 0) {   // a curve leaving the plot area is cut there, not drawn flat along its edge
          for (let i = 0; i < nn; i++) {
            if (inside[i]) { last = i; continue; }
            const src = last >= 0 ? last : firstIn; a[i * 3] = a[src * 3]; a[i * 3 + 1] = a[src * 3 + 1];
          }
        }
        const frac = Math.max(0.0001, Math.min(1, draw(c))); const cnt = Math.max(2, Math.floor(nn * frac));
        geo.setPositions(a); geo.instanceCount = cnt - 1; mat.opacity = (o.opacity ?? 1) * alpha; if (o.dashed) line.computeLineDistances();
        return;
      }
      for (let i = 0; i < nn; i++) {
        if (pts) { a[i * 3] = pts[i][0](c); a[i * 3 + 1] = pts[i][1](c); a[i * 3 + 2] = pts[i][2](c); }
        else { cc.u = u0 + (u1 - u0) * (i / (nn - 1)); a[i * 3] = fx(cc); a[i * 3 + 1] = fy(cc); a[i * 3 + 2] = fz(cc); }
      }
      const frac = Math.max(0.0001, Math.min(1, draw(c))); const cnt = Math.max(2, Math.floor(nn * frac));
      // Always upload the full path (same buffer size every frame) and limit what is drawn: re-uploading a growing array leaves a stale GPU buffer.
      geo.setPositions(a); geo.instanceCount = cnt - 1; mat.opacity = (o.opacity ?? 1) * alpha;
      if (o.dashed) line.computeLineDistances();
    };
    scope.lineMats.push(mat);
    return { node: line, update, mat };
  }

  makeArrow(o, look, scope) {
    const g = new THREE.Group(); const col = this.color(o.color ?? 'accent', look);
    const m = () => this.makeMaterial({ color: o.color ?? 'accent', emissive: o.color ?? 'accent', emissiveIntensity: o.glow ?? 0.6, roughness: 0.35 }, look, scope);
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, 1, 24), m()); const head = new THREE.Mesh(new THREE.ConeGeometry(1, 1, 32), m());
    g.add(shaft, head);
    const from = (o.from || [0, 0, 0]).map((v) => numeric(v, this.warn)), to = (o.to || [0, 1, 0]).map((v) => numeric(v, this.warn));
    const thick = numeric(o.thickness ?? 0.04, this.warn); const up = new THREE.Vector3(0, 1, 0);
    const update = (c) => {
      const a = new THREE.Vector3(from[0](c), from[1](c), from[2](c)), b = new THREE.Vector3(to[0](c), to[1](c), to[2](c));
      const dir = b.clone().sub(a); const len = dir.length();
      if (len < 1e-5) { g.visible = false; return; }
      const th = thick(c); const headLen = Math.min(len * 0.45, th * 5), headR = th * 2.4, shaftLen = Math.max(len - headLen, 1e-4);
      dir.normalize(); const q = new THREE.Quaternion().setFromUnitVectors(up, dir);
      shaft.scale.set(th, shaftLen, th); shaft.position.copy(a).addScaledVector(dir, shaftLen / 2); shaft.quaternion.copy(q);
      head.scale.set(headR, headLen, headR); head.position.copy(a).addScaledVector(dir, shaftLen + headLen / 2); head.quaternion.copy(q);
    };
    g.userData.noTransform = true;
    return { node: g, update };
  }

  makeSurface(o, look, scope) {
    const [nu, nv] = o.resolution || [64, 64]; const [u0, u1] = o.uRange || [-1, 1], [v0, v1] = o.vRange || [-1, 1];
    const fx = numeric(o.x ?? 'u', this.warn), fy = numeric(o.y ?? '0', this.warn), fz = numeric(o.z ?? 'v', this.warn);
    const geo = new THREE.PlaneGeometry(1, 1, nu, nv); const posAttr = geo.attributes.position;
    const mesh = new THREE.Mesh(geo, this.makeMaterial({ doubleSided: true, ...(typeof o.material === 'string' ? { preset: o.material } : o.material || {}) }, look, scope));
    if (o.wireframe) { const w = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: this.color(o.wireColor ?? 'ink', look), wireframe: true, transparent: true, opacity: 0.25 })); mesh.add(w); }
    const update = (c) => {
      const cc = { ...c };
      for (let j = 0; j <= nv; j++) for (let i = 0; i <= nu; i++) {
        cc.u = u0 + (u1 - u0) * (i / nu); cc.v = v0 + (v1 - v0) * (j / nv);
        posAttr.setXYZ(j * (nu + 1) + i, fx(cc), fy(cc), fz(cc));
      }
      posAttr.needsUpdate = true; geo.computeVertexNormals(); geo.computeBoundingSphere();
    };
    return { node: mesh, update };
  }

  makeParticles(o, look, scope) {
    const n = Math.min(o.count ?? 200, 4000); const fx = numeric(o.x ?? '0', this.warn), fy = numeric(o.y ?? '0', this.warn), fz = numeric(o.z ?? '0', this.warn);
    const rad = numeric(o.radius ?? 0.05, this.warn);
    const mesh = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 16, 12), this.makeMaterial(o.material ?? { color: o.color ?? 'primary', emissive: o.color ?? 'primary', emissiveIntensity: 0.7, roughness: 0.6 }, look, scope), n);
    mesh.frustumCulled = false; const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
    const update = (c) => {
      const cc = { ...c, n };
      for (let i = 0; i < n; i++) { cc.i = i; cc.f = i / Math.max(1, n - 1); const r = rad(cc); p.set(fx(cc), fy(cc), fz(cc)); s.set(r, r, r); m4.compose(p, q, s); mesh.setMatrixAt(i, m4); }
      mesh.instanceMatrix.needsUpdate = true;
    };
    return { node: mesh, update };
  }

  // Explainer kit: dots travelling along a path (blood, current, fuel, data), optionally inside a translucent pipe.
  makeFlow(o, look, scope) {
    const raw = Array.isArray(o.points) ? o.points : [];
    const pts = raw.filter((p) => Array.isArray(p) && p.length === 3 && p.every((v) => Number.isFinite(Number(v)))).map((p) => new THREE.Vector3(...p.map(Number)));
    if (pts.length < 2) { this.warn('flow needs `points`: at least 2 [x,y,z] numbers'); return { node: new THREE.Group(), update: () => {} }; }
    const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
    const n = Math.min(Math.max(1, Math.floor(o.count ?? 40)), 600); const speed = numeric(o.speed ?? 0.25, this.warn); const size = Number(o.size ?? 0.06); const spread = Number(o.spread ?? 0.0);
    const g = new THREE.Group();
    if (o.pipe) {
      const r = typeof o.pipe === 'number' ? o.pipe : Math.max(spread * 1.6, size * 3);
      g.add(new THREE.Mesh(new THREE.TubeGeometry(curve, Math.max(24, pts.length * 24), r, 16, false), this.makeMaterial({ color: o.pipeColor ?? 'muted', opacity: 0.22, roughness: 0.2, doubleSided: true }, look, scope)));
    }
    const mesh = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 14, 10), this.makeMaterial(o.material ?? { color: o.color ?? 'primary', emissive: o.color ?? 'primary', emissiveIntensity: 0.8, roughness: 0.5 }, look, scope), n);
    mesh.frustumCulled = false; g.add(mesh);
    const hash = (k) => { const x = Math.sin(k * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
    const off = Array.from({ length: n }, (_, i) => [(hash(i) - 0.5) * 2 * spread, (hash(i + 101) - 0.5) * 2 * spread, (hash(i + 202) - 0.5) * 2 * spread]);
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(size, size, size), p = new THREE.Vector3();
    const update = (c) => {
      const base = speed(c) * c.t;
      for (let i = 0; i < n; i++) {
        let u = i / n + base; u = o.loop === false ? Math.min(1, Math.max(0, u)) : u - Math.floor(u);
        curve.getPointAt(u, p); p.x += off[i][0]; p.y += off[i][1]; p.z += off[i][2];
        m4.compose(p, q, s); mesh.setMatrixAt(i, m4);
      }
      mesh.instanceMatrix.needsUpdate = true;
    };
    return { node: g, update };
  }

  makeVectorField(o, look, scope) {
    const [nx, ny, nz] = o.grid || [5, 5, 1]; const [[x0, x1], [y0, y1], [z0, z1]] = o.bounds || [[-2, 2], [-2, 2], [0, 0]];
    const fx = numeric(o.vx ?? '0', this.warn), fy = numeric(o.vy ?? '0', this.warn), fz = numeric(o.vz ?? '0', this.warn);
    const scale = numeric(o.scale ?? 0.4, this.warn); const n = nx * ny * nz;
    const geo = new THREE.ConeGeometry(0.06, 0.3, 14); geo.translate(0, 0.15, 0);
    const mesh = new THREE.InstancedMesh(geo, this.makeMaterial(o.material ?? { color: o.color ?? 'primary', emissive: o.color ?? 'primary', emissiveIntensity: 0.9, roughness: 0.4 }, look, scope), n);
    mesh.frustumCulled = false; const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0), d = new THREE.Vector3();
    const update = (c) => {
      const cc = { ...c }; let k = 0;
      for (let a = 0; a < nx; a++) for (let b = 0; b < ny; b++) for (let e = 0; e < nz; e++) {
        cc.x = nx > 1 ? x0 + (x1 - x0) * a / (nx - 1) : x0; cc.y = ny > 1 ? y0 + (y1 - y0) * b / (ny - 1) : y0; cc.z = nz > 1 ? z0 + (z1 - z0) * e / (nz - 1) : z0;
        d.set(fx(cc), fy(cc), fz(cc)); const len = d.length(); p.set(cc.x, cc.y, cc.z);
        if (len < 1e-6) s.set(0, 0, 0); else { d.normalize(); q.setFromUnitVectors(up, d); const m = Math.min(len * scale(c), 1.6); s.set(1, m * 3, 1); }
        m4.compose(p, q, s); mesh.setMatrixAt(k++, m4);
      }
      mesh.instanceMatrix.needsUpdate = true;
    };
    return { node: mesh, update };
  }

  // Screen rectangle (window pixels) covered by the narrator's portrait, or null when there is none or it is not a photo.
  narratorRect() {
    if (!this.narrator || this.narrator.kind !== 'photo') return null;
    const F = this.narrator.photo.frame, W = this.win.width, H = this.win.height, side = this.narrator.side || this.layout.narrator.side;
    const ph = F.heightFrac * H, pw = (this.narrator.photo.crop.x1 - this.narrator.photo.crop.x0) / (this.narrator.photo.crop.y1 - this.narrator.photo.crop.y0) * ph, y1 = H - F.bottomFrac * H;
    const x0 = side === 'left' ? F.marginFrac * W : W - F.marginFrac * W - pw;
    return { x0, x1: x0 + pw, y0: y1 - ph, y1, side };
  }

  // Photo narrator: a framed portrait pinned to a corner of the picture, flat to the screen.
  placePhoto(pn, cam) {
    const slot = this.layout.narrator, F = this.narrator.photo.frame, d = this.narrator.distance ?? 2.4;
    const visH = 2 * d * Math.tan(cam.fov * DEG / 2), visW = visH * (this.win.width / this.win.height), sc = F.heightFrac * visH;
    const sign = (this.narrator.side || slot.side) === 'left' ? -1 : 1;
    const x = sign * (visW / 2 - F.marginFrac * visW - (pn.aspect * sc) / 2), y = -visH / 2 + F.bottomFrac * visH + sc / 2;
    pn.group.position.copy(cam.position).add(new THREE.Vector3(x, y, -d).applyQuaternion(cam.quaternion));
    pn.group.quaternion.copy(cam.quaternion); pn.group.scale.setScalar(sc); pn.group.updateMatrixWorld(true);
  }

  // Narrator layer: keeps the character at a fixed place on screen whatever the camera does. The layout's `narrator` slot gives the
  // side, the share of the window height the visible part (hips up) fills, and where the hips sit relative to the bottom edge.
  placeNarrator(node, cam) {
    const slot = this.layout.narrator, nr = this.narrator, d = nr.distance ?? 2.4, bust = 1.25 /* hips to top of head at scale 1 */;
    const visH = 2 * d * Math.tan(cam.fov * DEG / 2), visW = visH * (this.win.width / this.win.height);
    const sc = (slot.heightFrac * visH) / bust, halfW = 0.5 * sc;
    const sign = (nr.side || slot.side) === 'left' ? -1 : 1;
    const x = sign * (visW / 2 - slot.marginFrac * visW - halfW);
    const hipsY = -visH / 2 + slot.bottomFrac * visH;
    const local = new THREE.Vector3(x, hipsY - 0.91 * sc, -d).applyQuaternion(cam.quaternion);
    node.position.copy(cam.position).add(local);
    const yaw = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, (nr.yaw_degrees ?? -14) * DEG * -sign, 0));
    node.quaternion.copy(cam.quaternion).multiply(yaw);
    node.scale.set(sc * sign, sc, sc);   // a negative x scale mirrors the character when it stands on the left
    node.updateMatrixWorld(true);
  }

  // ---------- post-processing ----------
  setupComposer(look) {
    const { W, H } = this;
    const rt = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: this.cfg.renderer.msaaSamples });
    const comp = new EffectComposer(this.renderer, rt); comp.setSize(W, H);
    const rp = new RenderPass(null, this.camera); comp.addPass(rp);
    comp.addPass(new ShaderPass(SanitizeShader));
    const b = look.post.bloom; const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), b.strength, b.radius, b.threshold); comp.addPass(bloom);
    comp.addPass(new OutputPass());
    const fin = new ShaderPass(FinishShader); comp.addPass(fin);
    return { comp, rp, bloom, fin };
  }

  applyPost(look) {
    if (!this.post) this.post = this.setupComposer(look);
    const p = look.post, b = p.bloom;
    Object.assign(this.post.bloom, { strength: b.strength, radius: b.radius, threshold: b.threshold });
    const u = this.post.fin.uniforms;
    u.vignette.value = p.vignette; u.grain.value = p.grain; u.chroma.value = p.chromatic; u.contrast.value = p.contrast; u.saturation.value = p.saturation;
    this.renderer.toneMappingExposure = look.exposure ?? 1;
  }

  // ---------- timeline ----------
  sceneAt(T) {
    let idx = this.scenes.findIndex((s) => T >= s.start && T < s.end);
    if (idx < 0) idx = T < this.scenes[0].start ? 0 : this.scenes.length - 1;
    return idx;
  }

  async renderAt(T) {
    const idx = this.sceneAt(T);
    if (idx !== this.currentIdx) {
      if (this.current) this.current.dispose();
      this.current = this.buildScene(this.scenes[idx]); this.currentIdx = idx;
      this.overlays.setScene(this.scenes[idx], this.current.look);
      await Promise.all(this.current.ctxScope.pending);
    }
    const S = this.current, spec = S.spec; const t = T - spec.start; const dur = spec.end - spec.start;
    const sm = S.ctxScope.sim; setSimProvider(sm ? (k, i, tau) => simValue(sm, k, i, tau) : null);
    const ts = sm ? Math.max(0, Math.min((t - (spec.sim.start ?? 0)) * (spec.sim.timeScale ?? 1), sm.duration)) : 0;
    const ctx = { ...S.ctxScope.ctxExtra, t, p: Math.min(1, t / dur), T, dur, ts };
    this.applyPost(S.look);

    for (const r of S.ctxScope.dyn) r.update(ctx);
    // fade child materials for appear/vanish and apply dynamic material expressions
    for (const r of S.ctxScope.dyn) {
      if (r.node.userData.billboard) r.node.quaternion.copy(this.camera.quaternion);
    }
    for (const e of S.ctxScope.mats) {
      if (e.dyn.opacity) e.mat.opacity = e.dyn.opacity(ctx);
      if (e.dyn.emissiveIntensity) e.mat.emissiveIntensity = e.dyn.emissiveIntensity(ctx);
    }
    this.applyFades(S, ctx);

    const c = S.cexp; const cam = this.camera;
    cam.position.set(c.pos[0](ctx), c.pos[1](ctx), c.pos[2](ctx));
    cam.fov = c.fov(ctx); cam.updateProjectionMatrix();
    cam.up.set(Math.sin(c.roll(ctx) * DEG), Math.cos(c.roll(ctx) * DEG), 0);
    cam.lookAt(c.tgt[0](ctx), c.tgt[1](ctx), c.tgt[2](ctx)); cam.updateMatrixWorld(true);
    S.root.traverse((n) => { if (n.userData.billboard) n.quaternion.copy(cam.quaternion); });
    if (S.photo) { this.placePhoto(S.photo, cam); S.photo.update(T, t, this.voiceFn, S.nods); }
    const nrNode = this.narrator && S.objIndex.__narrator;
    if (nrNode) this.placeNarrator(nrNode, cam);

    this.post.rp.scene = S.scene; this.post.fin.uniforms.time.value = (T * 60) % 97;
    this.post.comp.render();

    this.overlays.update({ T, t, dur, S, camera: cam, captions: this.captions, scenes: this.scenes, idx, ctx });
  }

  // Screen-space layout checks (free, deterministic): cropped subjects, cards covering subjects, titles on bright areas.
  layoutReport() {
    const S = this.current, cam = this.camera, W = this.win.width, H = this.win.height, out = [];
    const skip = new Set(['particles', 'flow', 'glow', 'light', 'plane', 'curve', 'vectorfield', 'surface', 'label', 'image']);
    const v = new THREE.Vector3(), box = new THREE.Box3(), objs = [];
    for (const n of S.root.children) {
      if (!n.visible || !n.userData.kind || n.userData.background || n.userData.helper || skip.has(n.userData.kind)) continue;   // (no kind: the look's floor, not a scene object)
      box.setFromObject(n); if (box.isEmpty()) continue;
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, behind = false;
      for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) {
        v.set(x, y, z).project(cam); if (v.z > 1) behind = true;
        const sx = (v.x * 0.5 + 0.5) * W, sy = (-v.y * 0.5 + 0.5) * H; x0 = Math.min(x0, sx); x1 = Math.max(x1, sx); y0 = Math.min(y0, sy); y1 = Math.max(y1, sy);
      }
      const area = (x1 - x0) * (y1 - y0); if (behind || area < 0.01 * W * H || (['box', 'cylinder'].includes(n.userData.kind) && area > 0.55 * W * H)) continue;
      const iw = Math.max(0, Math.min(x1, W) - Math.max(x0, 0)), ih = Math.max(0, Math.min(y1, H) - Math.max(y0, 0));
      objs.push({ id: n.name, x0, y0, x1, y1, area, visibleShare: (iw * ih) / area });
    }
    for (let a = 0; a < objs.length; a++) for (let b = a + 1; b < objs.length; b++) {
      const A = objs[a], B = objs[b], iw = Math.max(0, Math.min(A.x1, B.x1) - Math.max(A.x0, B.x0)), ih = Math.max(0, Math.min(A.y1, B.y1) - Math.max(A.y0, B.y0));
      const part = (iw * ih) / Math.min(A.area, B.area); // fully contained (> 0.85) means stacked or inside, which is intentional
      if (part > 0.35 && part < 0.85) out.push(`"${A.id}" and "${B.id}" overlap each other on screen: move them apart or re-frame`);
    }
    if (S.ctxScope.sim) {   // simulated bodies must stay large enough to read
      for (const b of S.ctxScope.sim.bodies) {
        const n = S.objIndex[b.id]; if (!n || !n.visible) continue; box.setFromObject(n); if (box.isEmpty()) continue;
        let y0 = 1e9, y1 = -1e9;
        for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) { v.set(x, y, z).project(cam); const sy = (-v.y * 0.5 + 0.5) * H; y0 = Math.min(y0, sy); y1 = Math.max(y1, sy); }
        if (y1 - y0 < 0.035 * H) out.push(`simulated body "${b.id}" is tiny on screen (the motion covers too large an area): shorten the run, slow it with timeScale, add a floor or wall to stop it, or enlarge the body`);
      }
    }
    // the subject must fill a reasonable part of the picture, and must stay clear of the narrator's corner
    let hx0 = 1e9, hy0 = 1e9, hx1 = -1e9, hy1 = -1e9, anyHero = false;
    for (const n of S.root.children) {
      if (!n.visible || !n.userData.kind || n.userData.background || n.userData.helper || ['particles', 'flow', 'glow', 'light', 'plane', 'surface', 'label', 'image', 'vectorfield'].includes(n.userData.kind)) continue;
      box.setFromObject(n); if (box.isEmpty()) continue; anyHero = true;
      for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) { v.set(x, y, z).project(cam); if (v.z > 1) continue; hx0 = Math.min(hx0, (v.x * 0.5 + 0.5) * W); hx1 = Math.max(hx1, (v.x * 0.5 + 0.5) * W); hy0 = Math.min(hy0, (-v.y * 0.5 + 0.5) * H); hy1 = Math.max(hy1, (-v.y * 0.5 + 0.5) * H); }
    }
    const minShare = this.cfg.layoutChecks?.minSubjectShare ?? 0.06;
    if (anyHero && hx1 > hx0 && ((Math.min(hx1, W) - Math.max(hx0, 0)) * (Math.min(hy1, H) - Math.max(hy0, 0))) / (W * H) < minShare) out.push(`the subject fills only ${Math.round(100 * (Math.min(hx1, W) - Math.max(hx0, 0)) * (Math.min(hy1, H) - Math.max(hy0, 0)) / (W * H))}% of the picture: move the camera closer or make the objects bigger so the viewer can read them`);
    const nr = this.narratorRect();
    if (nr) for (const o of objs) {
      const iw = Math.max(0, Math.min(o.x1, nr.x1) - Math.max(o.x0, nr.x0)), ih = Math.max(0, Math.min(o.y1, nr.y1) - Math.max(o.y0, nr.y0));
      if ((iw * ih) / (o.area * Math.max(o.visibleShare, 0.05)) > (this.cfg.layoutChecks?.narratorOverlap ?? 0.3)) out.push(`"${o.id || 'an object'}" sits behind the narrator's portrait in the lower ${nr.side} corner: move it or re-frame so the narrator does not cover it`);
    }
    for (const o of objs) if (o.visibleShare < 0.9) out.push(`"${o.id}" is cropped by the edge of the 3D window (${Math.round(o.visibleShare * 100)}% visible): move the camera back or re-target it`);
    const probe = document.createElement('canvas'); probe.width = 108; probe.height = Math.round(108 * H / W); const px = probe.getContext('2d', { willReadFrequently: true });
    px.drawImage(this.renderer.domElement, 0, 0, probe.width, probe.height);
    for (const { it, node, tag } of this.overlays.items) {
      if (tag || parseFloat(node.style.opacity || '0') < 0.5) continue;
      const r = node.getBoundingClientRect(), cx0 = r.left - this.win.x, cy0 = r.top - this.win.y, cx1 = r.right - this.win.x, cy1 = r.bottom - this.win.y;
      if (it.kind !== 'title' && (cy1 > H + 2 || cx1 > W + 2 || cx0 < -2 || cy0 < -2)) out.push(`the ${it.kind} card "${(it.text || it.latex || it.value || '').toString().slice(0, 30)}" runs past the edge of the 3D window: shorten it, shrink it or use another anchor`);
      if (it.kind !== 'title') {
        for (const o of objs) {
          const iw = Math.max(0, Math.min(cx1, o.x1) - Math.max(cx0, o.x0)), ih = Math.max(0, Math.min(cy1, o.y1) - Math.max(cy0, o.y0));
          const share = (iw * ih) / (o.area * Math.max(o.visibleShare, 0.05));
          if (share > 0.4) out.push(`the ${it.kind} card "${(it.text || it.latex || it.value || '').toString().slice(0, 30)}" covers ${Math.round(Math.min(1, share) * 100)}% of "${o.id}": use another anchor, shrink the card, or move the subject`);
        }
      } else {
        const sx = probe.width / W, d = px.getImageData(Math.max(0, Math.floor(cx0 * sx)), Math.max(0, Math.floor(cy0 * sx)), Math.max(1, Math.floor((Math.min(cx1, W) - Math.max(cx0, 0)) * sx)), Math.max(1, Math.floor((Math.min(cy1, H) - Math.max(cy0, 0)) * sx))).data;
        let sum = 0; for (let i = 0; i < d.length; i += 4) sum += (0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2]) / 255;
        if (sum / (d.length / 4) > 0.45) out.push(`the title "${(it.text || '').slice(0, 30)}" sits on a bright area (white text is hard to read): move the camera/subject or use another anchor`);
      }
    }
    return [...new Set(out)];
  }

  // Mean luminance and share of clipped pixels of the last rendered frame (used by lint to catch black or blown-out scenes).
  frameStats() {
    const c = document.createElement('canvas'); c.width = 54; c.height = 96; const x = c.getContext('2d', { willReadFrequently: true });
    x.drawImage(this.renderer.domElement, 0, 0, 54, 96); const d = x.getImageData(0, 0, 54, 96).data;
    let sum = 0, sq = 0, clipped = 0, bright = 0; const n = d.length / 4;
    for (let i = 0; i < d.length; i += 4) { const l = (0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2]) / 255; sum += l; sq += l * l; if (l > 0.2) bright++; if (d[i] > 245 && d[i + 1] > 245 && d[i + 2] > 245) clipped++; }
    return { mean: sum / n, bright: bright / n, clipped: clipped / n, contrast: Math.sqrt(Math.max(0, sq / n - (sum / n) ** 2)) };
  }

  applyFades(S, ctx) {
    for (const r of S.ctxScope.dyn) {
      if (!r.fadeMats || r.node.userData.alpha === undefined) continue;
      const a = r.node.userData.alpha;
      r.node.traverse((n) => {
        if (!n.isMesh || !n.material || n.material.isLineMaterial) return;
        const m = n.material;
        if (m.userData.baseOp === undefined) { m.userData.baseOp = m.opacity; m.userData.baseTransparent = m.transparent; }
        m.transparent = a < 0.999 || m.userData.baseTransparent; m.opacity = m.userData.baseOp * a;
      });
    }
  }
}

function popEase(x) { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); }
