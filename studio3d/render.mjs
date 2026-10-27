// Usage: node render.mjs --spec spec.json --out reel.mp4 [--audio a.wav] [--assets dir]
//        node render.mjs --spec spec.json --still 3.2 --png frame.png
// Prints one JSON line on stdout: {ok, frames, seconds, warnings}
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, all) => (v.startsWith('--') ? [...a, [v.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]] : a), []));
if (!args.spec) { console.error('--spec required'); process.exit(2); }

const spec = JSON.parse(fs.readFileSync(args.spec, 'utf8'));
const cfg = JSON.parse(fs.readFileSync(path.join(repo, 'config/render.json'), 'utf8'));
const fps = Number(args.fps || spec.fps || cfg.canvas.fps);
const assetsDir = args.assets ? path.resolve(args.assets) : null;
const log = (...m) => console.error('[studio3d]', ...m);

function findChrome() {
  const c = [process.env.CHROME_PATH, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'];
  return c.find((p) => p && fs.existsSync(p));
}
function findFfmpeg() {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  for (const p of ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg']) if (fs.existsSync(p)) return p;
  try { return execFileSync('which', ['ffmpeg']).toString().trim(); } catch { return null; }
}

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp' };
function loadLooks() {
  const dir = path.join(repo, 'config/looks'); const out = {};
  for (const f of fs.readdirSync(dir)) if (f.endsWith('.json')) { const l = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')); out[l.name || f.replace('.json', '')] = l; }
  return out;
}
function serve() {
  const roots = { '/web/': path.join(here, 'web'), '/nm/': path.join(here, 'node_modules'), '/config/': path.join(repo, 'config') };
  if (assetsDir) roots['/assets/'] = assetsDir;
  return new Promise((resolve) => {
    const s = http.createServer((req, res) => {
      const url = decodeURIComponent(req.url.split('?')[0]);
      if (url === '/') { res.writeHead(200, { 'content-type': 'text/html' }); return res.end(fs.readFileSync(path.join(here, 'web/index.html'))); }
      if (url === '/api/props') {
        const dir = path.join(repo, 'config/props'); const prefabs = {};
        if (fs.existsSync(dir)) for (const f of fs.readdirSync(dir)) if (f.endsWith('.json')) prefabs[f.replace('.json', '')] = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
        const poses = fs.existsSync(path.join(repo, 'config/poses.json')) ? JSON.parse(fs.readFileSync(path.join(repo, 'config/poses.json'), 'utf8')) : {};
        res.writeHead(200, { 'content-type': 'application/json' }); return res.end(JSON.stringify({ prefabs, poses }));
      }
      if (url === '/api/layouts') {
        const dir = path.join(repo, 'config/layouts'); const out = {};
        for (const f of fs.readdirSync(dir)) if (f.endsWith('.json')) { const l = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')); out[l.name || f.replace('.json', '')] = l; }
        res.writeHead(200, { 'content-type': 'application/json' }); return res.end(JSON.stringify(out));
      }
      if (url === '/api/looks') { res.writeHead(200, { 'content-type': 'application/json' }); return res.end(JSON.stringify(loadLooks())); }
      for (const [prefix, dir] of Object.entries(roots)) if (url.startsWith(prefix)) {
        const file = path.resolve(dir, url.slice(prefix.length));
        if (!file.startsWith(dir) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) break;
        res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream' }); return fs.createReadStream(file).pipe(res);
      }
      res.writeHead(404); res.end('not found');
    }).listen(0, '127.0.0.1', () => resolve(s));
  });
}

const chrome = findChrome();
if (!chrome) { console.log(JSON.stringify({ ok: false, error: 'Chrome/Chromium not found. Set CHROME_PATH.' })); process.exit(1); }
const server = await serve(); const port = server.address().port;
const browser = await puppeteer.launch({
  executablePath: chrome, headless: true,
  args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-webgl', '--hide-scrollbars', '--force-device-scale-factor=1', '--disable-background-timer-throttling', '--disable-renderer-backgrounding'],
  defaultViewport: { width: cfg.canvas.width, height: cfg.canvas.height, deviceScaleFactor: 1 },
});
let exitCode = 0; let result = {};
try {
  const page = await browser.newPage();
  page.on('pageerror', (e) => log('pageerror', e.message));
  page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) log('console.' + m.type(), m.text()); });
  await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'load' });
  await page.waitForFunction('window.__ready === true', { timeout: 30000 });
  await page.evaluate((s) => window.__studio.init(s), spec);

  const shot = () => page.screenshot({ type: 'jpeg', quality: cfg.encode.screenshotQuality, optimizeForSpeed: true });
  if (args.lint) {
    const problems = await page.evaluate(() => window.__studio.lint());
    result = { ok: problems.length === 0, problems };
  } else if (args.stills !== undefined) {
    fs.mkdirSync(args.outdir, { recursive: true });
    const files = [];
    for (const [i, tt] of String(args.stills).split(',').entries()) {
      await page.evaluate((t) => window.__studio.renderAt(t), Number(tt));
      const file = path.join(args.outdir, `still_${String(i + 1).padStart(2, '0')}.png`);
      fs.writeFileSync(file, await page.screenshot({ type: 'png' })); files.push(file);
    }
    result = { ok: true, files, warnings: await page.evaluate(() => window.__studio.warnings()) };
  } else if (args.still !== undefined) {
    const T = Number(args.still);
    await page.evaluate((t) => window.__studio.renderAt(t), T);
    const buf = await page.screenshot({ type: 'png' });
    fs.writeFileSync(args.png, buf);
    result = { ok: true, frames: 1, warnings: await page.evaluate(() => window.__studio.warnings()) };
  } else {
    const ffmpeg = findFfmpeg(); if (!ffmpeg) throw new Error('ffmpeg not found. Set FFMPEG.');
    const total = Math.ceil(spec.duration * fps);
    const ff = ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-'];
    if (args.audio) ff.push('-i', args.audio);
    ff.push('-c:v', cfg.encode.codec, '-preset', cfg.encode.preset, '-crf', String(cfg.encode.crf), ...(cfg.encode.maxrate ? ['-maxrate', cfg.encode.maxrate, '-bufsize', cfg.encode.bufsize] : []), '-pix_fmt', cfg.encode.pixFmt, '-r', String(fps));
    if (args.audio) ff.push('-c:a', 'aac', '-b:a', '192k');
    ff.push('-t', (total / fps).toFixed(3));
    ff.push('-movflags', '+faststart', args.out);
    const enc = spawn(ffmpeg, ff, { stdio: ['pipe', 'inherit', 'inherit'] });
    const encDone = new Promise((r) => enc.on('close', r));
    enc.stdin.on('error', () => {}); // ffmpeg exiting early surfaces below via its exit code
    const t0 = Date.now();
    for (let f = 0; f < total; f++) {
      await page.evaluate((t) => window.__studio.renderAt(t), f / fps);
      const buf = await shot();
      if (enc.exitCode !== null) break;
      if (!enc.stdin.write(buf)) await new Promise((r) => enc.stdin.once('drain', r));
      if (f % 30 === 0) log(`frame ${f}/${total} (${((Date.now() - t0) / (f + 1)).toFixed(0)} ms/frame)`);
    }
    enc.stdin.end(); const code = await encDone;
    if (code !== 0) throw new Error(`ffmpeg exited with ${code}`);
    result = { ok: true, frames: total, seconds: (Date.now() - t0) / 1000, warnings: await page.evaluate(() => window.__studio.warnings()) };
  }
} catch (e) {
  result = { ok: false, error: String(e && e.stack || e) }; exitCode = 1;
} finally {
  await browser.close(); server.close();
}
console.log(JSON.stringify(result)); process.exit(exitCode);
