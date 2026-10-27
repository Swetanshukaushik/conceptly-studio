"""Builds docs/tracker/index.html from config/syllabus/*.json: topics covered, reels, counts per chapter.

Run: python scripts/build_tracker.py   (re-run after updating config/syllabus/progress.json)
"""
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYL = os.path.join(ROOT, "config", "syllabus")
OUT = os.path.join(ROOT, "docs", "tracker", "index.html")

books = [("c11", "Class 11 Physics", json.load(open(os.path.join(SYL, "physics_11.json")))),
         ("c12", "Class 12 Physics", json.load(open(os.path.join(SYL, "physics_12.json"))))]
progress = json.load(open(os.path.join(SYL, "progress.json")))
LABEL = {"reel": "Reel rendered", "plan": "Plan only", "todo": "Not started", "approved": "Approved"}


def status_of(key):
    return progress["topics"].get(key, {}).get("status", "todo")


def counts(prefix, chapters):
    c = {"reel": 0, "plan": 0, "todo": 0, "approved": 0}; total = 0
    for ch in chapters:
        for t in ch["topics"]:
            c[status_of(f"{prefix}:{ch['no']}:{t}")] += 1; total += 1
    return c, total


def esc(x):
    return html.escape(str(x))


sections, cards = [], []
for prefix, name, book in books:
    c, total = counts(prefix, book["chapters"])
    covered = c["reel"] + c["approved"] + c["plan"]
    cards.append(f'<div class="card"><h3>{esc(name)}</h3><div class="big">{c["reel"] + c["approved"]}<span> / {total}</span></div>'
                 f'<div class="sub">topics with a full reel · {c["approved"]} approved · {c["plan"]} plan only</div>'
                 f'<div class="bar"><i class="a" style="width:{100 * c["approved"] / total:.1f}%"></i><i class="r" style="width:{100 * c["reel"] / total:.1f}%"></i><i class="p" style="width:{100 * c["plan"] / total:.1f}%"></i></div></div>')
    rows = []
    for ch in book["chapters"]:
        cc, n = counts(prefix, [ch])
        chips = []
        for t in ch["topics"]:
            key = f"{prefix}:{ch['no']}:{t}"; info = progress["topics"].get(key, {}); st = status_of(key)
            tag = f'<a class="chip {st}" href="#{key.replace(":", "-").replace(" ", "_")}" title="{esc(LABEL[st])}">{esc(t)}</a>' if info.get("reel") else f'<span class="chip {st}" title="{esc(LABEL[st])}">{esc(t)}</span>'
            chips.append(tag)
        tools = "".join(f'<span class="tool {"planned" if "planned" in tl else ""}">{esc(tl)}</span>' for tl in ch.get("tools", []))
        rows.append(f'<tr><td class="no">{ch["no"]}</td><td><b>{esc(ch["title"])}</b><div class="tools">{tools}</div></td>'
                    f'<td class="chips">{"".join(chips)}</td><td class="cnt">{cc["reel"] + cc["approved"]} / {n}</td></tr>')
    sections.append(f'<h2>{esc(name)}</h2><p class="edition">{esc(book["edition"])}</p>'
                    f'<table><thead><tr><th>#</th><th>Chapter and tools</th><th>Topics</th><th>Reels</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')

reels = []
for key, info in progress["topics"].items():
    if info.get("reel"):
        reels.append((key, info, "Syllabus topic"))
for i, info in enumerate(progress["pilots"]):
    reels.append((f"pilot-{i}", info, info.get("subject", "Pilot")))
gallery = []
for key, info, kind in reels:
    anchor = key.replace(":", "-").replace(" ", "_")
    gallery.append(f'<div class="reel" id="{anchor}"><video controls preload="metadata" poster="{esc(info.get("poster", ""))}" src="{esc(info["reel"])}"></video>'
                   f'<h4>{esc(info.get("title", key))}</h4><div class="meta">{esc(kind)} · job {esc(info.get("job", ""))} · {esc(info.get("model", ""))}</div><p>{esc(info.get("notes", ""))}</p></div>')
pilots_ok = sum(1 for p in progress["pilots"] if p.get("reel"))
cards.append(f'<div class="card"><h3>Pilots (outside the syllabus board)</h3><div class="big">{pilots_ok}<span> reels</span></div><div class="sub">pulley systems, chemical equilibrium</div></div>')

page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>STEM reel tracker</title>
<style>
:root{{--bg:#0d1220;--panel:#151c2f;--ink:#e8edf7;--muted:#8d9ab3;--line:#26304a;--reel:#3ddc97;--plan:#ffc23d;--todo:#3a4562;--appr:#5aa9ff}}
@media (prefers-color-scheme: light){{:root{{--bg:#f4f6fb;--panel:#fff;--ink:#16213a;--muted:#5d6b86;--line:#dbe1ee;--todo:#c7cfe0}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Inter","Segoe UI",sans-serif;padding:24px 16px 80px;max-width:1180px;margin-inline:auto}}
h1{{font-size:26px;margin:0 0 4px}}h2{{margin:36px 0 4px;font-size:20px}}.lead{{color:var(--muted);margin:0 0 20px}}.edition{{color:var(--muted);font-size:13px;margin:0 0 12px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}}
.card h3{{margin:0 0 6px;font-size:14px;color:var(--muted);font-weight:600}}.big{{font-size:34px;font-weight:800}}.big span{{font-size:16px;color:var(--muted);font-weight:600}}.sub{{color:var(--muted);font-size:13px}}
.bar{{display:flex;height:8px;background:var(--todo);border-radius:6px;overflow:hidden;margin-top:12px}}.bar i{{display:block;height:100%}}.bar .a{{background:var(--appr)}}.bar .r{{background:var(--reel)}}.bar .p{{background:var(--plan)}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0;font-size:13px;color:var(--muted)}}.legend b{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}}
table{{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}}th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}}th{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
td.no{{color:var(--muted);width:32px}}td.cnt{{white-space:nowrap;color:var(--muted);width:70px}}.tools{{margin-top:4px}}.tool{{display:inline-block;font-size:11px;padding:1px 7px;margin:2px 4px 0 0;border-radius:999px;background:var(--line);color:var(--muted)}}.tool.planned{{opacity:.55;border:1px dashed var(--muted);background:none}}
.chip{{display:inline-block;margin:2px 4px 2px 0;padding:3px 9px;border-radius:999px;font-size:12.5px;border:1px solid var(--line);color:var(--muted);text-decoration:none}}
.chip.reel{{background:rgba(61,220,151,.16);border-color:var(--reel);color:var(--ink)}}.chip.plan{{background:rgba(255,194,61,.16);border-color:var(--plan);color:var(--ink)}}.chip.approved{{background:rgba(90,169,255,.18);border-color:var(--appr);color:var(--ink)}}
a.chip:hover{{filter:brightness(1.2)}}
.gallery{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px;margin-top:12px}}.reel{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px}}.reel video{{width:100%;aspect-ratio:9/16;background:#000;border-radius:10px}}.reel h4{{margin:10px 0 2px}}.meta{{font-size:12px;color:var(--muted)}}.reel p{{font-size:13px;margin:6px 0 0}}
</style></head><body>
<h1>STEM reel tracker</h1><p class="lead">Free tier, physics first. Generated from <code>config/syllabus</code> by <code>scripts/build_tracker.py</code>. A topic counts as done only after you approve it.</p>
<div class="cards">{"".join(cards)}</div>
<div class="legend"><span><b style="background:var(--reel)"></b>Reel rendered</span><span><b style="background:var(--plan)"></b>Plan only</span><span><b style="background:var(--appr)"></b>Approved by you</span><span><b style="background:var(--todo)"></b>Not started</span><span>Dashed tool tags are planned, not built</span></div>
<h2>Reels so far</h2><div class="gallery">{"".join(gallery)}</div>
{"".join(sections)}
</body></html>"""
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(page)
print("wrote", OUT)
for prefix, name, book in books:
    c, total = counts(prefix, book["chapters"]); print(name, total, "topics:", c)
