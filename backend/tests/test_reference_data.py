"""Compare the knowledge base against public internet data (fixtures built by tests/tools/build_reference_data.py).

- Currencies: every curated cuisine's currency matches its country's official currency (mledoze/countries).
- Nutrition: per-portion calories and protein of matched dishes vs USDA FoodData Central (FNDDS 2024).
  Home recipes vary a lot, so individual dishes may differ; the suite fails on extreme outliers and on a high
  overall error, and prints the full comparison table.
"""

import statistics

import pytest

from app import kb

KCAL_OUTLIER = 0.60  # a single dish more than 60% off USDA is almost certainly a wrong KB value
MEDIAN_KCAL_ERROR = 0.25


def test_curated_currencies_match_country_data(reference_currency):
    for cuisine, country in reference_currency["cuisine_country"].items():
        expected = reference_currency["currencies"][country]
        assert kb.CUISINES[cuisine].currency.code in expected, (cuisine, country)


def _rows(reference_nutrition):
    rows = []
    for ref in reference_nutrition["items"]:
        dish = next((d for d in kb.CUISINES[ref["cuisine"]].dishes if d.name == ref["dish"]), None)
        assert dish is not None, f"KB dish missing: {ref['cuisine']}/{ref['dish']}"
        err = (dish.kcal - ref["usda_kcal"]) / ref["usda_kcal"]
        rows.append((ref, dish, err))
    return rows


def test_nutrition_vs_usda(reference_nutrition, capsys):
    rows = _rows(reference_nutrition)
    with capsys.disabled():
        print(f"\n{'dish':38} {'KB kcal':>8} {'USDA':>6} {'diff':>6}   {'KB P':>5} {'USDA P':>6}   basis")
        for ref, dish, err in sorted(rows, key=lambda r: -abs(r[2])):
            print(f"{dish.name[:38]:38} {dish.kcal:>8.0f} {ref['usda_kcal']:>6} {err:>+6.0%}   {dish.protein_g:>5.0f} "
                  f"{ref['usda_protein_g']:>6}   {ref['usda_food']} · {ref['grams_basis']}")
        median = statistics.median(abs(e) for *_, e in rows)
        print(f"median absolute calorie difference: {median:.0%} over {len(rows)} dishes")
    outliers = [(d.name, f"{e:+.0%}") for _, d, e in rows if abs(e) > KCAL_OUTLIER]
    assert not outliers, f"KB calories far from USDA: {outliers}"
    assert statistics.median(abs(e) for *_, e in rows) <= MEDIAN_KCAL_ERROR


@pytest.mark.parametrize("cuisine", [k for k, p in kb.CUISINES.items() if p.source == "curated"])
def test_dish_values_are_plausible(cuisine):
    for d in kb.CUISINES[cuisine].dishes:
        assert 0 <= d.kcal <= 1200, d.name
        assert 0 <= d.protein_g * 4 <= max(d.kcal, 1) * 0.9, f"{d.name}: protein calories exceed total"
