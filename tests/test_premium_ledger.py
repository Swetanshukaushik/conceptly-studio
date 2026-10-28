import base64

import pytest

from src.services.media.ledger import BudgetExceeded, SpendLedger
from src.services.media.providers import (FakeImageProvider, GeminiImageProvider, ImageRequest, MediaGateway, ProviderError, model_price,
                                          new_gateway)
from src.services.tiers import get_tier


def gw(cap, **kw):
    return MediaGateway(SpendLedger(cap), FakeImageProvider(**kw))


def test_ledger_records_cost_and_remaining():
    g = gw(1.0, price=0.25)
    g.generate_image(ImageRequest("a", label="s1"))
    g.generate_image(ImageRequest("b", label="s2"))
    d = g.ledger.to_dict()
    assert d["spent_usd"] == 0.5 and d["remaining_usd"] == 0.5 and d["calls"] == 2 and d["by_kind"] == {"image": 0.5}


def test_cap_refused_before_the_call_is_made():
    g = gw(0.5, price=0.25)
    g.generate_image(ImageRequest("a"))
    g.generate_image(ImageRequest("b"))
    with pytest.raises(BudgetExceeded):
        g.generate_image(ImageRequest("c"))
    assert len(g.image_provider.calls) == 2        # the third never reached the provider
    assert g.ledger.spent == 0.5


def test_failed_call_releases_hold_and_is_not_billed():
    g = gw(0.5, price=0.25, fail_on=[1])
    with pytest.raises(ProviderError):
        g.generate_image(ImageRequest("a"))
    assert g.ledger.spent == 0 and g.ledger.reserved == 0 and g.ledger.to_dict()["failed_calls"] == 1
    g.generate_image(ImageRequest("a"))
    assert g.ledger.spent == 0.25


def test_reservation_counts_against_cap():
    led = SpendLedger(0.5)
    t = led.reserve("image", "m", 0.3)
    with pytest.raises(BudgetExceeded):
        led.reserve("image", "m", 0.3)
    led.release(t, "cancelled")
    led.reserve("image", "m", 0.3)


def test_default_prices_come_from_config_and_unknown_model_is_rejected():
    assert model_price("gemini-3.1-flash-lite-image") == 0.034
    with pytest.raises(ProviderError):
        model_price("nonexistent-model")


def test_gemini_provider_parses_image_and_maps_errors():
    png = FakeImageProvider().generate(ImageRequest("x")).data
    ok = lambda url, body, headers: (200, {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png).decode()}}]}}]})
    g = MediaGateway(SpendLedger(1.0), GeminiImageProvider("k", transport=ok))
    res = g.generate_image(ImageRequest("a"))
    assert res.data == png and g.ledger.spent == 0.034
    credits = lambda url, body, headers: (402, {"error": {"message": "credits depleted"}})
    g2 = MediaGateway(SpendLedger(1.0), GeminiImageProvider("k", transport=credits))
    with pytest.raises(ProviderError) as e:
        g2.generate_image(ImageRequest("a"))
    assert e.value.status == 402 and g2.ledger.spent == 0
    empty = lambda url, body, headers: (200, {"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]})
    with pytest.raises(ProviderError):
        MediaGateway(SpendLedger(1.0), GeminiImageProvider("k", transport=empty)).generate_image(ImageRequest("a"))


def test_gateway_uses_tier_cap_and_premium_cap_is_configured():
    cap = get_tier("premium")["cost_cap_usd"]
    assert cap == 0.75
    assert new_gateway(cap, FakeImageProvider()).ledger.cap_usd == 0.75


def test_missing_key_is_a_clear_error():
    with pytest.raises(ProviderError):
        GeminiImageProvider(api_key="")
