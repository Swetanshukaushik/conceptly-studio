# Premium tier: readiness verdict and roadmap

Status as of 2026-10-27. Written after the Free tier reached a working quality gate and Conceptly Core publishing.

## Verdict

**Ready to start the provider-independent foundations (phases 0 and 1). Not ready for the full build, and this is not yet an absolute roadmap.**
Three things the Free tier built carry straight over: the Concept Router and packs, the scene engine and layout lint, the quality gate and publishing.
Four open decisions and two unknowns (real image-model quality and real cost per reel) must be settled by a short spike before the rest can be scheduled with dates.

## What exists today

| Piece | State |
| --- | --- |
| Tier config, pricing popup, `require_available` guard | Done. Premium is `planned`, so it cannot be selected. |
| Concept Router, packs for biology, history/civics, tech | Prompts and routing exist; the packs are `planned` (no kits behind them). |
| Scene engine (three.js), camera tours, `image` object, layout lint, vision QA | Done. An `image` plane with a camera tour already gives a Ken Burns move. |
| Image resolver (Wikimedia) with vision verification | Done. Real archival photos for history; no generation. |
| Quality gate, quiz and figure cross-checks, publishing | Done. Reused as-is. |
| Provider adapters for image/video generation | **Legacy only.** `video_clip_engine.py` has Fal, Runway, Luma and Kling calls from the old tier design: no spend cap, no ledger, not wired to the new engine, never exercised. |
| Spend ledger and hard cap | Missing. `cost_cap_usd` is in config but nothing enforces it. |
| Image-generation provider key | Missing. `.env` has Gemini and OpenAI (no credits); nothing for images or video. |
| Premium voice | Missing. Only an ElevenLabs voice id, no key. |
| Likeness and licence policy for generated people | Missing. |

## Phase 0 spike result (2026-10-27)

- The Gemini key lists four image models: `gemini-3.1-flash-lite-image`, `gemini-3.1-flash-image`, `gemini-3-pro-image` and `gemini-2.5-flash-image` (shut down 2026-10-02 per the pricing page), plus Gemini TTS models.
- **Every image call returned 429 with a free-tier limit of 0.** The key's project has no billing enabled, so no image can be generated until billing is turned on. Nothing was generated or spent.
- Published prices (Google pricing page, 2026-10-27): flash-lite-image about $0.034 per 1K image, flash-image $0.045 to $0.151 by size, pro-image $0.134. A reel with 8 stills is therefore about $0.27 (flash-lite) to $0.54 (flash-image at 1K), before regenerations, well under the $0.50 to $2 budget.
- Gemini TTS (`gemini-3.8-flash-tts`) is about $0.00225 per 10 s of audio, so a premium voice would add under a cent per reel; worth testing in Phase 5 on the same key once billing is on.
- The spike script is `scripts/premium_spike.py` (3 topics x 4 shots per model); it is ready to run as soon as billing is enabled.

## Phase 1 status (2026-10-28): built and tested offline

- `src/services/media/ledger.py`: `SpendLedger` reserves each call's estimate before it is made and refuses it when spent + in flight + estimate would pass the cap (`BudgetExceeded`). Failed calls are released and not billed.
- `src/services/media/providers.py`: `ImageProvider` interface, `FakeImageProvider` (offline, can inject failures), `GeminiImageProvider` (REST, flat per-image price from config, errors mapped to `ProviderError`), and `MediaGateway`, the only place that spends. `generate_clip` is deliberately not implemented (clips are out of v1).
- `config/providers.json`: image models, prices with their source and date, default cap. Premium `cost_cap_usd` in `config/tiers.json` is now 1.5 (was 3.0) and the price label is about $0.30 to $1.50.
- `tests/test_premium_ledger.py`: 8 tests, including cap refusal before the provider is reached.
- Not yet wired into the pipeline; that happens in Phase 2. Prices are published, not measured; the spike replaces them.

## Build status (2026-10-28): phases 1 to 8 built and tested offline; nothing has generated a real image yet

| Piece | Where | State |
| --- | --- | --- |
| Spend ledger, provider interface, fake and Gemini image providers | `src/services/media/` | Built, tested. Cap checked before every call |
| Style bible, people/text policy, shot planner | `src/services/premium/style.py`, `planner.py`, `config/premium.json`, `config/prompts/premium_planner.md` | Built, tested with a fake planner (the real planner prompt has not run against a live model) |
| Stills pipeline: generate, vision-judge, regenerate once, archive fallback, stop on credit errors, per-reel consistency review | `src/services/premium/stills.py` | Built, tested with fakes |
| Camera and composition: 9:16 plane, push/pull/pan/drift as expressions of progress, dust layer, label pins, title and pop word | `src/services/premium/composer.py` | Built; passes the real renderer lint; rendered a demo frame |
| Source-backed fact check (Wikipedia extracts + one model call) | `src/services/premium/facts.py` | Built, tested with fakes; blocks the reel when a claim is contradicted |
| Premium voice (Gemini TTS, spend on the ledger, Edge fallback) | `src/engines/tts/tts_engine.py` | Built, tested with a fake transport; real voice quality unheard |
| Quality gate: images generated, image quality, consistency, facts, cost | `src/services/quality_gate.py` | Built, tested |
| Orchestrator wiring; Premium tier available; only history/civics, biology and generic go through generated stills (maths, physics, chemistry stay on the Free engine inside Premium) | `src/pipeline/orchestrator.py`, `config/tiers.json` | Built |
| Gate 1 header shows spend and generated stills | `src/web/index.html` | Built |
| Pilot harness with per-reel cost report | `scripts/premium_pilot.py` | Written, not run |
| Video clips (old phase 4) | | Deliberately not built; decide after the pilot |

**Cost levers (2026-10-28):** (1) a still can be shared by two beats with a different camera move (`reuse_previous`, capped at 60% unique images, never for pinned or real-subject shots); (2) the bigger image model is used only for the first generated shot (`hero` in `config/premium.json`); (3) an image cache keyed on model and full prompt returns reviewed-and-accepted images for free (rejected images are never cached), and cache hits show in the cost report. The Premium cap is now $0.75 and the price label about $0.15 to $0.75. Estimate for a 9-beat reel: about 5 to 6 paid images, roughly $0.20 to $0.30 with the hero shot. Still to check on the first real run: smaller image size tiers and whether batch pricing covers image models.

Without image credits every still falls back to an archive photo and the gate blocks the reel (`images_generated`), so a Premium reel cannot ship looking like a Free one by accident.

## Pilot result (2026-10-28, real images, Gemini flash-lite-image plus flash-image for the first shot)

Six reels, stage 1 each; Salt March also rendered end to end with the Gemini voice (720x1280, 54 s).

| Reel | Gate | Spend (config prices) | Consistency | Facts |
| --- | --- | --- | --- | --- |
| The Salt March | 16/16 passed | $0.215 | 7 | 8 supported |
| The Revolt of 1857 | 16/16 passed | $0.237 | 7 | 3 supported |
| How the Indian Constitution was drafted | 16/16 passed | $0.237 | 7 | 2 supported, 1 unverified |
| How the human heart pumps blood | 16/16 passed | $0.237 | 6 | 5 supported, 1 unverified |
| How a neuron fires | 15/16 passed | $0.305 | 6 | 0 of 2 supported (warning) |
| How DNA is copied | 14/16 **blocked** | $0.305 | 7 | 6 supported; the reviewer found letters drawn on the base structures in two images |

Average $0.26 per reel against the $0.75 cap. Spend is the configured flat price per image, not billing data: compare with AI Studio usage before trusting it.

Found and fixed during the pilot: a legacy guard still demanded a video-model key for Premium; the fact check retrieved one unrelated article (the API gives a full-text extract for only one page per request); archive photos left black bars (blurred backdrop added); title and pop word collided; the consistency reviewer penalised scene changes instead of style; one generated face resembled a real person (prompt, planner and reviewer tightened); the Gemini voice speaks at about 2.0 words per second against 2.6 assumed, so Premium now has its own pacing and writer word range; the gate now re-checks duration after narration timing exists.

Still open: text in biology diagrams slips through generation and can only be blocked or retried (no archive photo exists for a concept); fact coverage is weak for neuroscience-style topics where the retrieved article is long and the claims are specific; the reviewer's scores cluster at 7, so its sensitivity is unproven; only one reel has been listened to and watched in full; one stylised figure of a real historical person still appears in the Salt March reel (stylised, not a likeness, but the policy needs an owner decision).

## Cost tracking (2026-10-28)

The first pilot used about twice the credits the ledger reported, because only images and the voice were counted. Now every paid call is recorded:

- `src/services/media/usage.py` wraps `generate_content` of the Gemini SDK once, so every text, vision, planner, fact-check and review call is priced from its token counts (thinking tokens bill as output; the Gemini 3.8 and 3.6 Flash prices double on 2027-01-01 and the config switches by date). OpenAI and Anthropic calls are recorded the same way. Image and voice calls were already on the ledger.
- Each pipeline stage runs inside a per-job ledger (`orchestrator._costed`); stages that auto-advance share one ledger, and the total is saved with the job as `script_data.cost` for every tier. The Gate 1 header shows it; the quality gate has a `cost` check (blocking for Premium, informational for Free). The Premium image gateway uses the same ledger, so one cap covers everything.
- Optional calls (image review, frame QA, fact check, quiz check) are refused once the reel's cap is used up; required calls (script, scenes) are never blocked but always recorded.
- Every entry is appended to `output/usage_log.jsonl`. `scripts/spend_report.py --since 2026-10-28 --by model|job|kind|day` sums it in USD and approximate rupees. Compare its total with the AI Studio billing page: a gap means a call that is not instrumented or a changed price.
- Tests never spend money: `tests/conftest.py` sets `CONCEPTLY_BLOCK_LIVE=1`, every paid-call site refuses to run, and tests that need a real model are marked `@pytest.mark.live` and skipped unless `pytest --live`.
- Not verified against a real call: the credits were exhausted when I tried, so the token fields were checked against the installed SDK's definitions and a fake response, not a live one. Calls made before today are not in the log.

## Decisions needed from the owner (blocking)

0. **Enable billing on the Gemini project** (owner action). Without it Premium image generation cannot be tested at all.

1. **Image provider.** Candidates: Gemini image models on the existing key, Imagen/other via API, Fal-hosted models. Cheapest path first: test what the Gemini key can already generate.
2. **Clip provider and whether clips ship at all in v1.** Image-to-video costs the most and is the least controllable; stills with camera moves may be enough for v1.
3. **Per-reel budget.** Config says about $0.50 to $2 with a $3 cap. Confirm or change; the ledger enforces whatever is chosen.
4. **Scope of v1 domains.** Recommended: history/civics and biology only (the Free tier cannot do them well). Maths, physics and chemistry stay Free.

## Phases (each ends in a test or a measured number)

**Phase 0. Spike, one day.** Generate 20 stills for three real topics (a history event, a biology structure, a civics scene) with the candidate model. Measure cost per image, style consistency across one reel, text-in-image artefacts, and how many need regeneration. Output: a go/no-go and a measured cost per reel. This answers the two unknowns.

**Phase 1. Provider adapter and spend ledger.** One interface (`generate_image`, `generate_clip`), a fake provider for tests, a ledger that records every call and refuses the next call when the reel's cap would be exceeded (checked before the call, not after). Fully testable offline.

**Phase 2. Premium scene planner and stills pipeline.** A shot list per beat with image prompts that share a style bible (same palette, lens, era), a negative prompt list, and a policy for real people (stylised, never a claimed likeness; named historical figures only through the Wikimedia resolver). Generated stills go through the existing vision judge; failures regenerate once; the cap forces fallback to a resolver photo.

**Phase 3. Camera and composition.** Parallax from the generated still (layer split or depth map, to be chosen after the spike), tours with the existing `camera.tour`, captions, pop words and stickers from the Free kit on top. Output at 720p like Free.

**Phase 4. Selective clips (optional, after the owner decides).** 2 to 4 beats per reel, image-to-video, hard cap, automatic fallback to the still with a camera move when the cap or a provider error hits.

**Phase 5. Premium voice.** ElevenLabs (or chosen provider) behind the existing TTS interface, with the cost added to the ledger; Free voice remains the fallback.

**Phase 6. Domain packs go from `planned` to `partial`.** History/civics: timeline kit, date check against retrieved sources. Biology: label pins on generated anatomy stills, source retrieval for facts. Both feed the quality gate (new checks: image consistency, artefacts, citations present).

**Phase 7. Pilot.** Three reels per domain, scored by the extended quality gate, with a printed cost report per reel. Exit bar: gate passes, measured cost at or under the cap, owner approves the look.

## Risks

- Generated images carry text artefacts and inconsistent faces; mitigations are the vision judge, no-text prompts and the resolver fallback.
- Cost can run away on regenerations; the pre-call cap is the control, and the pilot measures it.
- Facts in history and biology are where a wrong claim does the most harm. The Free tier's number verifier does not cover dates and names; Phase 6 must add source-backed checks before Premium is offered for those subjects.
- Licensing of generated and archival images needs a written policy before publishing.

## Recommendation

Make decisions 1 and 4 now, run Phase 0, then build Phases 1 to 3 in order. Decision 2 (clips) can wait until Phase 3 is judged.

## Premium Video tier (built offline, not yet run on real credits)

A fourth tier, `premium_video` (`scene_mode: generated_clips`), reuses the whole Premium pipeline and adds real video on a few beats.

- **Planner** marks up to 3 beats with `clip_motion` (what moves). Code keeps only plain beats of 3.5 s or more: no diagrams, pinned labels, archive photos or shared stills.
- **Clips** (`src/services/premium/clips.py`): image-to-video from the beat's accepted still (score 7+), through `MediaGateway.generate_clip` (reserve, call, commit measured cost). Model `gemini-omni-1.1-flash`, 720p, 9:16, about $0.10 per second (Google pricing page, 2026-10-28). Clip length is chosen by the model, so cost is `measured seconds x price`; 6 s is reserved before each call.
- **Drift check:** six frames on a contact sheet go to the vision judge; a score under 6 discards the clip.
- **Fallbacks:** cap, provider error, drift, ffmpeg failure all leave the beat as its still with a camera move. Auth, balance and rate-limit errors stop further clips. One retry for transient errors.
- **Saved work:** clips are in the job checkpoint and the shared cache (keyed by still bytes + motion), so retries and repeat topics do not pay twice.
- **Renderer:** `image` objects accept `frames`, `frame_count`, `frame_fps`; `studio3d/web/engine.js` swaps in the numbered JPEG for each rendered frame (frame-exact, holds the last frame).
- **Gate:** `clips_generated` (blocking, at least 1 clip) and `clip_quality`; spend appears in the Gate 1 header.
- **Open:** the request format follows Google's Omni docs but has never run against the real API; real cost per clip and clip length are unmeasured; veo models were retired 2026-10-22.
