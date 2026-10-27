# Vision reference analysis: five shorts → what Conceptly Studio builds

Date: 2026-10-26. Resolution target for now: **720p (720x1280)** is acceptable.

**How these were viewed:** frames sampled in the in-app browser by seeking to specific times, plus on-screen text and page titles. All five have now been seen (the first pass of biology and maths came back black; a second pass with muted, seeked playback fixed that). I did not hear audio, so voice/music notes are inferred.

## 1. The five references at a glance

| # | Domain | Short | Length | What it actually is |
|---|---|---|---|---|
| 1 | History / civics / UPSC | "What Were People Doing When Vesuvius Erupted?" (@SecondsBeforeOfficial) | 61.8 s | Photoreal AI-generated street/market scenes, slow camera moves, calm → disaster countdown story. Small sentence caption on top, large single-word pop caption in the middle. |
| 2 | Physics | "How a Rocket Engine Actually Works" | 25.5 s | Photoreal 3D cutaway of an engine (pipes, turbopump, pre-burner, regenerative cooling channels, spray fuel). Fast camera flythrough, colour-coded flow (blue oxidizer, gold/orange hydrogen), labels written on the geometry, two-line caption. |
| 3 | Chemistry | "Effect of Pressure on Chemical Equilibrium / Le Chatelier – Class 11" | 30 s | Stylised 3D cartoon professor beside a lab cylinder with a plunger and red/blue/white molecules. Equation overlay N₂+3H₂⇌2NH₃, big sticker text ("PRESSURE↑ VOLUME↓", "EQUILIBRIUM SHIFTS LEFT!"), the character points/reacts, particles visibly change count with pressure. |
| 4 | Biology | "How Your Heart Pumps Blood" (@MechYouLabs-style channel) | ~160 s (not a true short; 720x1280) | Photoreal AI/3D anatomical heart: opens in a transparent ribcage, then cutaway close-ups of chambers, valves, chordae tendineae and blood flow, ending on the whole heart pulsing. Top sentence caption plus a large bold bottom caption mirroring the narration. Dark vignette background, no UI chrome, no host. |
| 5 | Maths | "The Mathematics Behind a Parabola in 60 Seconds" (1080x1920) | 60 s | **2D animated, dark-navy, Manim-style**: numbered section tag ("03 / PARABOLAS"), a headline, KaTeX-style formulas (f(−x)=f(x), y=(x−h)²+k, a=−1), axes with a curve that draws and a moving point, a "vertex (h,k)" label, and a small blue **"M" mascot** that wanders the frame. Sentence caption at the top. |

## 2. What each one tells us we must build

### 1. History / civics / UPSC — the "scene world" format
- The hook is a **question about people** ("what were they doing when…"), and the story is a **time countdown**. Retention comes from narrative tension, not from diagrams.
- The visuals are **generated imagery with a slow virtual camera**. That is exactly what Premium's "generated stills + 3D camera moves (parallax / Ken Burns)" is. Short generated video clips are a bonus, not the base.
- Two caption layers: a small full sentence (comprehension) and a big single-word pop (rhythm). Our caption system must support **both** and the pop word must be timed to the narration.
- UPSC adds needs this reference does not show: dates, a **timeline strip**, a **map**, a source/citation line, and a fact-check gate. Rendering real politicians or events with AI faces is a risk — use archival media with licensing metadata or obviously stylised/silhouette figures.
- **Engine implication:** `history_civics` pack = story-beat director + image generation + camera-move compositor + timeline/map kit + citation pack.

### 2. Physics — the "explorable machine" format
- This is **not simulation of equations**; it is a **hero 3D object explained by a camera tour**. The value is clear spatial understanding: flow arrows, colour-coded fluids, labels pinned to parts.
- Our Free tier already has the right substrate (three.js, props, camera fit, labels, derivation overlay) and a **real physics sim** for mechanics. What is missing: **cutaway/exploded-view props, flow/particle streams, a scripted camera tour per beat, and a pinned-label system**.
- Photorealism of the reference (PBR metals, glow) is reachable with a better look (environment map, bloom) at 720p; true photoreal machinery models are a Premium (asset-library or image-to-3D) concern.
- **Engine implication:** `physics` pack = sim-driven scenes (have) + **hero-prop explorer** (cutaway, flow, tour). Machine topics (engines, circuits, optics benches) are props, not new engines.

### 3. Chemistry — the "host plus particle lab" format
- Closest to the Rutherford-narrator vision: a **character beside a live apparatus**, reacting to the visual. Gestures (pointing), expressions, and a cutaway beaker with **particles whose numbers respond to the concept**.
- The learning value comes from particle behaviour matching the claim (pressure ↑ → molecules compress → equilibrium shifts). Our `reaction_chamber`/`concentration_graph` props and the sim recipes are the right foundation; we need a **particle-ensemble kit** (counts, colours by species, volume change, piston) driven by the same declarative numbers.
- Sticker-style text ("PRESSURE↑ | VOLUME↓", arrow callouts) is a **callout kit**, not a hard-coded overlay.
- **Engine implication:** `chemistry` pack = particle lab + equation renderer (KaTeX, have) + **chemistry verification** (balance equations, ratios) + persona host.

### 4. Biology — the "anatomy tour" format
- Re-observed: the visuals are close-up **cutaways with motion** (valves opening, blood moving) — the hard part is the asset, not the layout. Captions are double-layered (small top sentence + large bold bottom line).
- A single hero model (heart, ribcage, vessels) with colour coding (oxygenated red / deoxygenated blue) and a **cycle** (beat sequence). The reference is also long (~160 s), so for our 30–70 s target we cut to one cycle explained in 3–4 beats.
- Needs **anatomical assets**. Procedural props (like our `helix`) will not carry a heart; options are open-licensed anatomy models (check licence), or generated stills with camera moves at Premium.
- **Engine implication:** `biology` pack = asset-backed hero model + highlight/dim-by-part + animated flow along paths (we can reuse the same flow kit as the rocket) + label pins.

### 5. Maths — the "construct it live" format
- Re-observed correction: this one is **clean 2D vector animation** (dark navy, light-blue curve, serif formulas, tidy section numbering). It is good because it is restrained and precise, not because it is 3D. That contradicts "no 2D": the user's rule is *no bad* 2D, and this is the good kind. Our maths pack should target this look (axes, drawing curve, moving point, parameter sliders like a = −1, vertex label), with a small mascot for continuity.
- Pure caption-driven reasoning: pick x values, compute y, plot, notice symmetry. We can do this **better in-house**: animated axes, point-by-point plotting, a curve that draws, a table that fills, KaTeX for the equation. We already have the `graph` prefab (curve plot mode) and the derivation overlay.
- Verification matters most here: values and curve must come from a **symbolic/numeric evaluator**, not from the LLM's arithmetic.
- **Engine implication:** `maths` pack = function graph + table + step-by-step derivation + number-line/geometry primitives; no third party needed.

## 3. The Einstein / Rutherford 3D narrator

The user wants a **3D character host** in physics (Einstein-like) and chemistry (Rutherford-like). The chemistry reference shows the style: a stylised, friendly cartoon professor, not photoreal.

Recommended approach (decision needed on the exact route):
- **Free tier:** a rigged low-poly/stylised humanoid in three.js (we already have `humanoid` prop and `poses.json`), with a **voice-driven mouth (amplitude/viseme from the TTS audio)**, blink, head turn, point/gesture poses chosen per beat by the director. Costs nothing per reel.
- **Likeness caution:** "Einstein-like" and "Rutherford-like" should be **stylised archetypes** (wild white hair + moustache; mutton-chop sideburns, tweed) rather than photographic likenesses, to stay on safe ground for a commercial product. Historical figures are public domain in spirit, but AI-generated realistic faces speaking invented words are a misinformation risk; keep it clearly cartoon and label them as "inspired by".
- **Premium tier:** same character, higher-fidelity model and lip-sync, plus optional generated cutaway/scene imagery.
- Character is one **actor** the director places and animates, not a separate engine — it plugs into every domain pack (a different persona per subject).

## 4. Capability map (what the references demand vs. what exists)

| Capability | Needed by | Status today |
|---|---|---|
| Declarative 3D scenes, props, camera fit | 2, 3, 4 | Have |
| Real physics simulator | 2 (mechanics), 3 | Have (mechanics/fields); no fluid/particle-ensemble |
| Graph + derivation + KaTeX | 3, 5 | Have |
| Caption: sentence + pop-word, timed | 1, 2, 3 | Sentence only; pop-word missing |
| Pinned labels, flow arrows, colour-coded streams | 2, 3, 4 | Missing |
| Cutaway / exploded-view hero prop | 2, 4 | Missing |
| Particle ensemble (counts respond to concept) | 3 | Partial (`reaction_chamber`) |
| Scripted camera tour per beat | 1, 2, 4 | Auto-fit only |
| 3D narrator with lip-sync + gestures | 3 (+ vision) | Missing (static humanoid prop) |
| Generated stills + parallax camera | 1 | Missing (image resolver exists) |
| Timeline / map / citation kit | 1 | Missing |
| Domain verification (symbolic maths, chem balance, source retrieval) | 1, 3, 5 | Missing |

## 5. Options reconsidered at 720p

720p changes costs and feasibility, not the architecture.

**Free tier (in-house, zero marginal cost)**
- Render at 720x1280: roughly 2× fewer pixels than 1080x1920 → faster frames (est. ~25–30 ms vs ~56 ms in our headless Chrome pipeline) and smaller files. This makes 60 s reels well under a minute of render time on this machine. Not benchmarked yet.
- Everything above for physics, chemistry, maths, and the narrator is buildable here. Biology and history are the weak spots (assets / photoreal imagery).

**Premium tier (paid APIs, behind a provider adapter)**
- Photoreal history scenes: generated stills ($0.003–$0.05 each) with in-house camera moves ≈ a few cents per reel. Short i2v clips from cheap 720p models (reported at roughly $0.025–$0.084/s, third-party prices from Oct 2026, **unverified**) only for 2–4 hero moments per reel, so budget stays around $0.5–$2 per reel instead of $6–15.
- Anatomy/machinery: generated or licensed stills with camera tours, or an image-to-3D step feeding the same three.js scene — evaluate per asset.
- Premium voice and lip-sync as an add-on.

**Ultra:** marked "later" in UI and config; no build.

## 6. Build order (recommended)

1. **Tier config + UI to three tiers** (Free, Premium, Ultra "later"); Generate popup reads the engine/persona options from config instead of the hardcoded "Newton narration persona".
2. **Concept Router + engine registry** (domain pack + capability kit selection per scene).
3. **Universal explainer kit:** pop-word captions, pinned labels, flow arrows, callout stickers, timeline, camera tours. These serve all five references.
4. **3D narrator** (Free): stylised Einstein/Rutherford archetypes, TTS-driven mouth, gesture poses via director.
5. **Domain packs in order of leverage:** maths (cheapest, fully in-house) → physics hero-prop explorer → chemistry particle lab → biology anatomy → history/civics (needs Premium imagery).
6. **Premium MVP:** provider adapter, spend ledger with hard caps, stills + parallax, selective short clips.

## 7. Open decisions

- Narrator likeness: stylised archetype (recommended) vs closer likeness.
- Biology/anatomy asset source (licensed model library vs generated).
- Whether history/civics ships only at Premium (recommended) or gets a Free fallback (silhouette/archival + timeline + map).
- Tier audience (internal creators vs paying users) — still unanswered.
