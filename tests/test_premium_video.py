"""Premium Video tier: clips from accepted stills, with every failure falling back to the still."""
import base64
import os

import pytest

from src.engines.render.tier_free.studio3d_engine import Studio3DEngine
from src.models.schemas import ReelGenerationTier
from src.services import quality_gate
from src.services.media.cache import ImageCache
from src.services.media.ledger import SpendLedger
from src.services.media.providers import ClipRequest, FakeClipProvider, FakeImageProvider, GeminiClipProvider, MediaGateway, ProviderError
from src.services.premium import clips, planner, stills
from src.services.premium.planner import Shot, ShotPlan
from src.services.tiers import get_tier
from tests.test_premium_pipeline import _planner, _run

TIER = ReelGenerationTier.PREMIUM_VIDEO


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(stills.time, "sleep", lambda s: None)


def _clip_planner(beats_with_clips=(1, 3)):
    def plan(topic, subject, beats, pack, tier, provider):
        out = _planner(topic, subject, beats, pack, tier, provider)
        for s in out["shots"]:
            if s.beat in beats_with_clips and not s.real_photo_query:
                s.clip_motion = "villagers walk slowly along the shore"
        return out
    return plan


def _gw(cap=3.0, clip=None, **kw):
    return MediaGateway(SpendLedger(cap), FakeImageProvider(**kw), clip or FakeClipProvider())


def _go(tmp_path, gw, **kw):
    args = dict(tier=TIER, planner_fn=_clip_planner(), clip_judge=lambda p, n, m: {"score": 8, "issues": []})
    args.update(kw)
    return _run(tmp_path, gw, **args)


def test_tier_is_configured():
    t = get_tier("PREMIUM_VIDEO")
    assert t["key"] == "premium_video" and t["status"] == "available" and t["scene_mode"] == "generated_clips" and t["renderer"] == "studio3d"
    assert get_tier("PREMIUM")["key"] == "premium"


def test_clips_are_made_from_accepted_stills_and_composed(tmp_path):
    gw = _gw()
    (res, assets) = _go(tmp_path, gw)
    rec = res["premium"]
    assert rec["clips"]["planned"] == 2 and rec["clips"]["made"] == 2 and rec["clips"]["cost_usd"] > 0
    assert len(gw.clip_provider.calls) == 2 and gw.ledger.to_dict()["by_kind"]["video"] > 0 and rec["cost"]["spent_usd"] <= rec["cost"]["cap_usd"]
    for n in (1, 3):
        scene = next(s for s in res["storyboard"].scenes if s.scene_number == n)
        still = next(o for o in scene.scene3d["objects"] if o["id"] == "still")
        assert still["frames"] == f"clip_{n}" and still["frame_count"] >= 20 and os.path.exists(os.path.join(assets, still["frames"], "f_0001.jpg"))
        assert scene.scene3d["staging"].endswith("steady camera")
    plain = next(s for s in res["storyboard"].scenes if s.scene_number == 2)
    assert "frames" not in next(o for o in plain.scene3d["objects"] if o["id"] == "still")


def test_the_renderer_plays_clip_frames(tmp_path):
    (res, assets) = _go(tmp_path, _gw())
    sb = res["storyboard"]; spec = Studio3DEngine.build_spec(sb, look=sb.style_bible)
    sc = next(s for s in sb.scenes if s.scene_number == 1)
    out = str(tmp_path / "frames")
    files = Studio3DEngine.render_stills(spec, [sc.start_sec + 0.8, sc.start_sec + 2.4], out, assets_dir=assets)
    assert len(files) == 2 and open(files[0], "rb").read() != open(files[1], "rb").read()   # the picture moves between the two times


def test_a_drifting_clip_falls_back_to_its_still(tmp_path):
    (res, assets) = _go(tmp_path, _gw(), clip_judge=lambda p, n, m: {"score": 2, "issues": ["face melts"]})
    rec = res["premium"]
    assert rec["clips"]["made"] == 0 and len(rec["clips"]["notes"]) == 2 and "face melts" in rec["clips"]["notes"][0]
    assert not any(os.path.isdir(os.path.join(assets, f"clip_{n}")) for n in (1, 3))
    assert all("frames" not in o for s in res["storyboard"].scenes for o in s.scene3d["objects"])
    assert any("clip" in (n or "") for n in res["storyboard"].qa)


def test_a_failed_clip_never_fails_the_reel_and_auth_errors_stop_further_clips(tmp_path):
    gw = _gw(clip=FakeClipProvider(fail_on=[1, 2, 3], status=402))
    (res, _) = _go(tmp_path, gw)
    assert res["premium"]["clips"]["made"] == 0 and len(gw.clip_provider.calls) == 1   # 402 stops generation for the rest of the reel
    assert res["premium"]["images"]["generated"] > 0 and res["premium"]["cost"]["spent_usd"] > 0


def test_a_transient_clip_error_retries_once(tmp_path):
    gw = _gw(clip=FakeClipProvider(fail_on=[1], status=500))
    (res, _) = _go(tmp_path, gw)
    assert res["premium"]["clips"]["made"] == 2 and len(gw.clip_provider.calls) == 3


def test_the_spend_cap_holds_before_any_clip_call(tmp_path):
    gw = _gw(cap=0.45)   # enough for the stills, not for a 6 s clip reservation
    (res, _) = _go(tmp_path, gw)
    assert res["premium"]["clips"]["made"] == 0 and len(gw.clip_provider.calls) == 0 and res["premium"]["cost"]["spent_usd"] <= 0.45


def test_rerun_keeps_finished_clips_and_new_job_hits_the_cache(tmp_path):
    gw1 = _gw(); (r1, _) = _go(tmp_path, gw1)
    gw2 = _gw(); (r2, _) = _go(tmp_path, gw2)   # same job folder: the plan, stills and clips are all kept
    assert r2["premium"]["clips"]["made"] == 2 and len(gw2.clip_provider.calls) == 0 and r2["premium"]["cost"]["spent_usd"] == 0
    gw3 = _gw(); (r3, _) = _go(tmp_path, gw3, assets_dir=str(tmp_path / "other" / "assets"))   # a new job: stills and clips come from the shared cache
    assert r3["premium"]["clips"]["made"] == 2 and len(gw3.clip_provider.calls) == 0 and r3["premium"]["cost"]["spent_usd"] == 0


def test_plan_limits_clips_to_long_plain_beats():
    beats = [{"beat": i, "text": "x", "seconds": 2.0 if i == 2 else 6.0} for i in range(1, 7)]
    shots = [Shot(beat=i, prompt="a road", clip_motion="walking", shot_type="diagram" if i == 3 else "medium", pins=[] if i != 4 else [planner.Pin(text="a")]) for i in range(1, 7)]
    notes = planner.enforce_clips(shots, beats, True)
    kept = [s.beat for s in shots if s.clip_motion]
    assert kept == [1, 5, 6] and any("too short" in n for n in notes) and any("diagram" in n or "pinned" in n for n in notes)
    assert planner.enforce_clips([Shot(beat=1, prompt="x", clip_motion="m")], beats, False) == []   # plain Premium never keeps a clip


def test_gemini_provider_reads_inline_video_and_prices_measured_seconds():
    data = FakeClipProvider(seconds=4.0).generate(ClipRequest(b"x", "image/png", "p")).data
    seen = {}

    def transport(url, body, headers):
        seen["body"] = body
        return 200, {"steps": [{"content": [{"type": "video", "mime_type": "video/mp4", "data": base64.b64encode(data).decode()}]}]}
    res = GeminiClipProvider("k", transport=transport).generate(ClipRequest(b"img", "image/png", "move"))
    assert seen["body"]["response_format"]["aspect_ratio"] == "9:16" and seen["body"]["input"][0]["type"] == "image"
    assert 3.8 <= res.seconds <= 4.3 and abs(res.cost_usd - res.seconds * 0.10) < 1e-6
    with pytest.raises(ProviderError):
        GeminiClipProvider("k", transport=lambda u, b, h: (429, {"error": {"message": "quota"}})).generate(ClipRequest(b"i", "image/png", "m"))


def test_gate_flags_a_video_reel_with_no_clips(tmp_path):
    (res, _) = _go(tmp_path, _gw(), clip_judge=lambda p, n, m: {"score": 2, "issues": ["x"]})
    script = {"storyboard": res["storyboard"].dict(), "premium": res["premium"]}
    chk = {c["id"]: c for c in quality_gate.evaluate(script)["checks"]}
    assert not chk["clips_generated"]["ok"] and chk["clips_generated"]["blocking"]
    (res2, _) = _go(tmp_path, _gw(), assets_dir=str(tmp_path / "ok" / "assets"))
    chk2 = {c["id"]: c for c in quality_gate.evaluate({"storyboard": res2["storyboard"].dict(), "premium": res2["premium"]})["checks"]}
    assert chk2["clips_generated"]["ok"] and chk2["clip_quality"]["ok"]
