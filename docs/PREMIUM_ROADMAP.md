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
