# Conceptly Studio — Project Index, Critical Review & Upgrade Plan

*Reviewed 2026-10-26 against the working tree on `main` (uncommitted changes included). Everything marked **verified** was checked in code, on disk, or by running it. Scope limit: I did not run a fresh end-to-end generation, and I did not read `tts_engine.py`, `audio_mixer.py`, `publisher_agent.py` or `web/index.html` line by line.*

---

## 1. Index of the project (what actually exists)

### 1.1 Documents — and how much to trust each

| File | Claims | Trust |
|---|---|---|
| `README.md`, `architecture.md` | Original 10-agent concept (storyboard_agent, voice_agent, render_engine…) | **Stale.** Several named files never existed. |
| `STUDIO_INTEGRATION_CONTRACT.md` | REST/ingest contract with Conceptly Core | Probably valid; not cross-checked against `publisher_agent.py`. |
| `docs/SYSTEM_BLUEPRINT.md`, `docs/ARCHITECTURE_FLOW.md` | "100% 3D" engine at `tier_3d/procedural_3d_engine.py`, `render/composer.py`, `engines/physics/solver.py`, Phase 1–5 complete | **False for this tree.** None of those three files exist (verified). |
| `argon-observations.md` (+ copy in `docs/`, they differ) | Audit + checklist with every task ticked `[x]`, "13/13 tests pass" | **False for this tree.** Those tasks target files that don't exist. Real suite: 9 tests pass. |
| `docs/IMPLEMENTATION_GAP_ANALYSIS.md` | Same gap list as argon | Describes a codebase that no longer matches. |

**What probably happened:** commit `6507119` ("5-tier architecture") replaced the "3D procedural engine" design, but the docs were never rewritten. The docs describe the abandoned design; the code implements the 5-tier one. Treat the code as truth and the docs as history.

### 1.2 Code map (12.2k lines of Python)

```
src/main.py                 FastAPI app, routes, static UI
src/cli.py                  headless generator
src/api/        reels.py(729) auth.py avatars.py
src/core/       config.py (pydantic Settings, all API keys), security.py
src/models/     schemas.py (ReelGenerationTier, SceneBeat, Storyboard, ReelScript…), entities.py (ReelJob, JobStage, ReelArtifact)
src/pipeline/   orchestrator.py  — Stage1 blueprint → Gate1 → Stage2 quiz → Gate2 → Stage3 render → Gate3
src/agents/     domain_intelligence (Stage 0), curriculum, script, scene_director, factcheck, quiz, publisher
src/services/   llm_factory.py(1266: Gemini/OpenAI/Anthropic cascade + giant heuristic fallback)
                avatar_catalog.py(705: built-in personas, custom store, voice matching)
                curriculum_resolver.py
src/engines/
  tts/          tts_engine.py (EdgeTTS/ElevenLabs), phonetic_normalizer.py
  visuals/      visual_factory.py — scene image: FAL→DALL-E→HF→Pollinations→Wikimedia
  render/
    video_clip_engine.py    tier dispatcher
    tier1_flash/            Ken-Burns zoompan over a still
    tier2_avatar/           PIL-drawn avatar-in-world clip
    tier4_cinema/           Fal/Runway/Luma image→video
    tier5_kurzgesagt/       PIL sim (spring / prism / membrane) + avatar bust
    motion_compositor.py    concat clips + audio + ASS subs
    audio_mixer.py, sound_fx_engine.py, subtitle_generator.py, validator.py
    card_renderer.py, ffmpeg_compositor.py   legacy fallback path
    physics_sim_engine.py(894) kurzgesagt_engine.py(786) storytelling_engine.py(323)
    manim_math_engine.py(332)  character_motion_engine.py(207)   ← NOT IMPORTED ANYWHERE (verified)
  storage/      local / R2 / S3
tests/          9 tests, all pass (≈150 s)
output/         115 job dirs, character_store/ (15 personas with avatar_3d.png), caches
```

### 1.3 Real data flow (default tier, which is what you use)

`topic` → resolve → persona (`AvatarCatalogService`) → `DomainIntelligenceAgent` (LLM) → `ScriptAgent` → `FactCheck` → `SceneDirectorAgent` (LLM → `Storyboard` of `SceneBeat{visual_prompt, hud_overlay, camera_motion}`) → **per scene `VisualAssetFactory.render_scene_image`** (one still) → *(Gate 1)* → quiz → *(Gate 2)* → TTS + word timestamps → scene times re-aligned → `VideoClipEngine` (zoompan on that still) → concat + audio → validator → *(Gate 3)* → publish.

**So a default-tier "reel" is: one AI/Wikimedia still per scene, slowly zoomed.** That is the core of your visual problem.

---

## 2. What your visual output actually looks like (verified)

I opened the latest storyboard frames (job `0794a496…`, "Newton's Third Law"). Six scenes, observed:

- **Scenes 1, 3, 4, 6 are the same Newton portrait** pasted on the same room. The avatar-composite rule fires on `scene_number in (1, 3)` *or* whenever the avatar's name appears in the prompt — so a 6-scene reel is 4 near-identical frames.
- **Scene 2 shows riot police; scene 5 shows a blank book-cover page ("COLLECTED PHYSICAL PAPERS").** These are Wikimedia Commons keyword-search results used when image generation fails. Nothing in the pipeline checks that the image matches the concept.
- **A `pollinations.ai` watermark is visible** on the generated frames despite `nologo=true`. The free endpoint also returns 576×1024, upscaled to 1080×1920 (soft).
- The formula HUD card sits on top of the subject (scene 2/5) instead of in a reserved zone.
- Nothing on screen illustrates "action and reaction": no forces, no vectors, no motion. It is a portrait slideshow with captions.

---

## 3. Root causes (ranked by damage to reel quality)

**R1 — Diffusion is the wrong tool for the physics/maths content.** The director prompt demands "photorealistic, ZERO text, clean plate" and the HUD is a lone formula. Image models can't draw correct force diagrams, circuits, DNA, or a free-body diagram; they draw plausible-looking scenery. Your actual product is *explanation*, which needs deterministic, parameterised graphics. The repo already contains ~3,000 lines of exactly that (spring, prism, projectile, orbit, cell membrane, manim calculus) — and none of it is wired in.

**R2 — Silent degradation chain.** `FAL → DALL-E → HF → Pollinations → Wikimedia` returns *something* nearly always, so the pipeline never fails loudly and never tells you quality dropped. Almost every provider call is `except Exception: print(...)`. FAL/OpenAI/HF keys are set in `.env`; the frames show Pollinations/Wikimedia output, so the upstream providers are failing (quota/invalid) and you aren't being told. I did not probe the keys.

**R3 — Subtitle path is broken.** The installed ffmpeg (`/opt/homebrew`, 9.0.2) has **no `subtitles`/libass filter** (verified). `FFmpegMotionCompositor._has_libass_filter` returns False, so the kinetic ASS captions are **silently skipped**. What you see instead is the static caption box that `visual_factory._composite_real_photo_vertical` burns into the image. If libass is ever installed, you get both, doubled.

**R4 — No per-scene visual planning.** `SceneBeat` has one free-text `visual_prompt` and a `visual_modality` enum that the renderer ignores. There is no concept of "what should be drawn", "which entities", "what moves", so every engine re-guesses from keywords.

**R5 — Tier plumbing is inconsistent.**
- Gate 1 renders a still for every scene, then Tier 2 / 4 / 5 throw it away or re-render something different. You pay for stills (FAL) that are never used and the reviewer approves frames that don't match the final video.
- `TIER_3_STEM` is documented as Manim but the engine was deleted in your working tree (`tier3_manim/` shows `D`); that tier now silently falls into the Flash slideshow.
- `FREE`/`DEFAULT`/`PREMIUM`/`ULTRA` aliases map implicitly; `ULTRA` goes to Tier 5, `PREMIUM` to Tier 4.

**R6 — Failures are swallowed or faked.** FFmpeg stderr is `DEVNULL` in the PIL engines. `composite_storyboard` writes a **fake stub MP4** if ffmpeg fails (defined twice). `LLMFactory.is_llm_configured()` only checks that a key string exists. `scene_director.py:106` references `settings` but never imports it (verified: imports are lines 1–4), so when the LLM fails the handler itself raises `NameError` and hides the real error.

---

## 4. Hardcoding audit (your "no hardcoding" requirement)

| Where | What's hardcoded |
|---|---|
| `llm_factory.py` `_generate_heuristic_fallback` (~1000 lines) | Topic branches: Gandhi, Bose, Ambedkar, Napoleon, Bhagat Singh, thermo, magnetism, chloroplast, DNA, Curie, Newton rocket, Ohm. Full scripts, quizzes and storyboards written inline. Unknown topic → "Core Curriculum Principle". |
| `scene_director._generate_heuristic_storyboard` (~300 lines) | Four canned storyboards + generic template. |
| `tier5 master_engine` | Keyword → sim type (`prism`, `cell`, else SHM). **Every other topic gets a spring-mass oscillator.** Avatar chosen by `"einstein" in prompt`. |
| `tier2 avatar_engine` | `PERSONA_HUD` dict: per-persona location/formula text. |
| `visual_factory` | Regex stop-list with `einstein, kalam, kurzgesagt, duck…`; scene numbers `(1, 3)` for avatar; HUD layout px; Pollinations seed formula. |
| `avatar_catalog` | Topic-keyword → persona routing; built-in persona table. |
| Everywhere | `1080/1920/30` repeated in 15 files; `_find_ffmpeg` copy-pasted 11×; `_get_font` 8×; hex palettes per engine; `/System/Library/Fonts/...` macOS paths. |
| `orchestrator` | `target_duration_sec=60`, log text "…with Isaac Newton persona…". |
| `config.py` | Default `SECRET_KEY`, `ADMIN_PASSWORD="admin123456"`, `CORS_ORIGINS=["*"]`. |

Principle for the fix: **the LLM decides content, a schema carries it, a registry of renderers executes it, and config holds every constant.** No topic names, persona names or keywords in code.

---

## 5. Upgrade plan

### Phase 0 — Make failures visible (½ day, do first)
1. Fix `scene_director.py` missing `settings` import. Remove the stub-MP4 fallback; raise with ffmpeg stderr.
2. Capture ffmpeg stderr in every engine; one `FFmpeg` helper (`src/engines/render/ffmpeg.py`) replaces the 11 `_find_ffmpeg` copies, and fails loudly.
3. Provider health: `ProviderRegistry.check()` at startup + per-call status record on each scene (`provider_used`, `fallback_depth`, `error`). Surface it in the Gate 1 UI and job log. A scene that fell to a "last-resort" source is flagged red, not approved silently.
4. Install libass (`brew install ffmpeg` build with libass, or `brew tap homebrew-ffmpeg/ffmpeg`), and add a startup check. Remove the baked-in caption box from `visual_factory` so there is exactly one caption system.

### Phase 1 — Declarative scene spec (the core fix, ~2–3 days)
Replace free-text `visual_prompt` with a structured visual plan produced by the director LLM:

```
SceneBeat.visual:
  kind: "sim" | "diagram" | "image" | "avatar_talk" | "text_card" | "video"
  sim:   {template_id, params{…}, entities[…], duration_curve}     # e.g. template "projectile", params from the LLM
  image: {query, style_ref, avoid[…]}                              # for photos/atmosphere only
  layout: {zone_map}                                               # where HUD, subject, avatar, captions go
  overlay: {formula, label, units, reveal_t}
  continuity: {entities_from_prev_scene}
```

- Renderer **registry**: `@register("projectile")`, `@register("circuit")`, `@register("vector_diagram")`… Each template takes numeric params, is deterministic, tested, and self-describes in a JSON manifest (`templates/*.json`: name, params, ranges, topics it suits).
- The director prompt is **generated from the registry manifest** (so adding a template needs zero prompt edits and zero keyword code). If no template fits, the director picks `image`/`text_card`, never a wrong sim.
- **Revive the dead code as templates**: split `physics_sim_engine.py` (rocket, collisions, orbit, wave/Snell, cell) and `kurzgesagt_engine.py` into registry entries; `manim_math_engine` as the `math_scene` template (real Manim if installed, else skip with a logged reason).
- Remove `master_engine`'s `SHM` default entirely.

### Phase 2 — Image sourcing you can trust (~1–2 days)
1. One `ImageProvider` interface; providers ordered **by config** (`VISUAL_PROVIDERS=fal,openai,hf,pollinations`), each with timeout, retry, cost note.
2. **Relevance gate** after generation/retrieval: a cheap vision-LLM check ("does this image match: {scene intent}? yes/no + reason"). Reject and retry with a revised prompt; never fall through to a random Wikimedia hit. Wikimedia becomes an *explicit* `kind: image` with `source: archive` chosen by the director for real historical photos, with a title/caption match check.
3. Request correct resolution at source; for Pollinations either use the paid key (`POLLEN_KEY` exists) or drop it from the default order (watermark).
4. Avatar handling: a real *character sheet* per persona (transparent PNG cut-out, 2–3 poses) in `character_store/`; avatar appears only when `visual.kind == "avatar_talk"` or the director sets `layout.avatar`, with a per-reel cap from config. Stop pasting a rectangular portrait.
5. Image-to-video (Tier 4) runs **only on the approved Gate-1 still** — Gate 1 previews are then the exact inputs of Stage 3.

### Phase 3 — Remove the hardcoded knowledge (~2 days)
1. Delete `_generate_heuristic_fallback` and `_generate_heuristic_storyboard`. If no LLM works, fail with a clear error (the code already half does this via `ALLOW_OFFLINE_DEV_FALLBACK`). For tests, use recorded LLM fixtures in `tests/fixtures/`, not production branches.
2. Persona routing: the LLM already returns `chosen_character_name`; drop keyword routing in `avatar_catalog`. Built-ins move to `config/personas.yaml` (data, editable, no code change).
3. `config/render.yaml`: canvas size, fps, safe zones, palette, fonts (bundled font files in repo, incl. glyphs for superscripts — fixes tofu boxes and macOS-only paths), caption style, scene duration bounds.
4. Remove default secrets from `config.py`; require them via env; tighten CORS.

### Phase 4 — Quality loop & performance (~2 days)
- **Auto-QA per scene**: sample frame → vision check (matches narration? text legible? subject not covered by HUD?) → auto-regenerate once.
- **Motion budget**: PIL-per-frame at 30 fps is why tests take 150 s. Render sims at lower internal res / use numpy or `skia`/`cairo`, cache per `(template, params)` hash, render scenes in parallel.
- Validator extended: no repeated identical frame across consecutive scenes (perceptual-hash distance), caption present, ≥N distinct visuals.
- Real E2E test with a fixture LLM + one sim scene + one image scene that asserts the produced frames differ and the captions burn in.

### Phase 5 — Docs & cleanup (½ day)
Replace `SYSTEM_BLUEPRINT`/`ARCHITECTURE_FLOW`/`argon-observations`/`IMPLEMENTATION_GAP_ANALYSIS` with one doc that matches the code; archive the rest. Delete `card_renderer`/`ffmpeg_compositor` legacy path or make them the explicit "text-card" template. Delete the ~240 lines of dead `_generate_*_clip` in `video_clip_engine.py` (duplicates of `cinema_engine`).

### Suggested order
Phase 0 → Phase 1 (with 2–3 flagship templates ported first: forces/vectors, projectile, circuit) → Phase 2 → Phase 3 → 4 → 5. Phase 0 alone will tell you *which* image provider is actually failing and give you working captions.

---

## 6. Open questions that change the plan
1. Is Tier 2/5 "stylised PIL characters" acceptable long-term, or do you want real rigged/Lottie/Spine-style characters? (Affects Phase 2.4.)
2. Budget per reel? It decides how much goes to Tier 4 video diffusion versus deterministic sims.
3. Which of FAL / OpenAI / HF keys in `.env` are meant to be live? Quota is the likely reason frames come from Pollinations/Wikimedia.
