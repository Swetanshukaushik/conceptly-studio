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

## Decisions needed from the owner (blocking)

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
