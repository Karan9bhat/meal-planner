"""Live: places outside the curated knowledge base resolve to the currency the internet data says (run with --live)."""

import pytest

from app import region

PLACES = [
    ("São Paulo", "Brazil"), ("Toronto", "Canada"), ("Dubai", "United Arab Emirates"), ("Santiago, Chile", "Chile"),
    ("Kraków", "Poland"), ("Sydney", "Australia"), ("Lagos", "Nigeria"), ("Seoul", "South Korea"),
    ("Istanbul", "Türkiye"), ("Madrid", "Spain"), ("Nairobi", "Kenya"), ("Hanoi", "Vietnam"),
]


@pytest.mark.live
@pytest.mark.parametrize("place,country", PLACES)
def test_unknown_place_gets_correct_currency(place, country, reference_currency):
    res = region.resolve(place)
    assert res.region.currency_code in reference_currency["currencies"][country], (place, res.region)
    # A budget estimate in that currency arrives immediately, even while a new cuisine profile is being written.
    assert res.region.budget.get("typical", 0) > 0
