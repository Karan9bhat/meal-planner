"""End-to-end evaluation: real plans for many region / diet / budget profiles, scored and compared.

    python -m evals.region_plans            # from backend/, writes evals/report.md and evals/results.json

Each profile goes through the real pipeline (region lookup -> router -> model -> variety pass -> balancer) and is scored on:
currency vs internet data, diet compliance (keyword scan of every meal for banned foods), calories / protein / budget per
day, variety, and regional relevance (share of meals that use the region's known dishes or staples).
Uses the hosted models: expect ~1 minute per profile on free tiers.
"""

import json
import re
import sys
import time
from pathlib import Path

from app import kb, region, variety
from app.llm import LLMError
from app.planner import generate_plan
from app.schemas import Profile

HERE = Path(__file__).parent
CURRENCY = json.loads((HERE.parent / "tests" / "fixtures" / "reference_currency.json").read_text(encoding="utf-8"))

# Words that reveal a banned ingredient in a dish name or portion.
BANNED_WORDS = {
    "poultry": ["chicken", "turkey", "duck"],
    "beef": ["beef", "steak", "brisket"],
    "pork": ["pork", "ham", "bacon", "lardon", "pancetta", "chorizo", "sausage", "prosciutto"],
    "lamb_mutton": ["lamb", "mutton", "goat"],
    "fish": ["fish", "salmon", "tuna", "cod", "hilsa", "sardine", "mackerel", "herring", "anchov"],
    "shellfish": ["prawn", "shrimp", "crab", "lobster", "mussel", "clam", "oyster", "squid"],
    "egg": ["egg", "omelette", "omelet", "tamagoyaki", "frittata"],
    "dairy": ["milk", "cheese", "paneer", "yogurt", "yoghurt", "curd", "butter", "ghee", "cream", "kefir", "tvorog", "quark", "dahi", "lassi"],
    "gluten": ["wheat", "bread", "roti", "chapati", "naan", "pasta", "noodle", "couscous", "flour tortilla", "barley", "seitan", "croissant", "baguette"],
    "peanut": ["peanut"],
    "onion_garlic": ["onion", "garlic"],
    "alcohol": ["wine", "beer", "rum", "vodka", "sake", "mirin"],
}
# Plant-based look-alikes that must not count as violations.
SAFE_PHRASES = ["tofu yogurt", "tofu yoghurt", "soy yoghurt", "vegan yogurt", "plant milk", "soy milk", "oat milk", "almond milk", "coconut milk", "vegan cheese", "tofu", "peanut-free",
                "gluten-free", "eggplant", "egg-free", "dairy-free", "nut butter", "coconut yogurt", "soy yogurt", "rice noodle",
                "buckwheat", "butternut", "cream of", "almond butter", "butter beans", "goat cheese", "goat's cheese",
                "goats cheese", "chevre", "chèvre"]

PROFILES = [
    # name, location, country (for currency check), diet, styles, restrictions, allergies, day description, budget multiplier
    ("Pune · vegetarian", "Pune", "India", "vegetarian", [], [], [],
     "Tea with sugar at 7, poha at 9, lunch at 1:30 is two chapatis with dal and a sabzi, evening chai with biscuits, dinner is rice and varan with a vegetable.", 1.0),
    ("Baramulla · halal", "Baramulla", "India", "omnivore", [], ["halal"], [],
     "Noon chai with girda bread in the morning, rice with haak and rajma for lunch, kahwa in the evening, rice with mutton yakhni for dinner.", 1.0),
    ("London · tight budget", "London", "United Kingdom", "omnivore", [], [], [],
     "Cereal with milk, a meal deal sandwich and crisps for lunch, biscuits with tea, pasta bake or a curry for dinner.", 0.7),
    ("Lyon · vegetarian, peanut allergy", "Lyon", "France", "vegetarian", [], [], ["peanut"],
     "Croissant and coffee, baguette sandwich with cheese for lunch, yogurt at 4, pasta in the evening.", 1.0),
    ("Moscow · pescatarian", "Moscow", "Russia", "pescatarian", [], [], [],
     "Buckwheat kasha with milk, borscht and bread for lunch, tea with a pastry, fish with potatoes for dinner.", 1.0),
    ("Mexico City · gluten-free", "Mexico City", "Mexico", "omnivore", [], [], ["gluten"],
     "Coffee and a pan dulce, chilaquiles mid-morning, comida at 3 with rice, beans and chicken, a light cena of quesadillas.", 1.0),
    ("Tokyo · high protein", "Tokyo", "Japan", "omnivore", ["high_protein"], [], [],
     "Rice, miso soup and natto for breakfast, a convenience-store bento for lunch, ramen or a rice bowl for dinner.", 1.0),
    ("New York · vegan", "New York", "United States", "vegan", [], [], [],
     "Oatmeal with almond milk, a big salad bowl for lunch, hummus and crackers, a tofu stir-fry with rice for dinner.", 1.0),
    ("Kraków · keto", "Kraków", "Poland", "omnivore", ["keto"], [], [],
     "Scrambled eggs with sausage, żurek soup for lunch, cheese snacks, pork chop with salad for dinner.", 1.0),
    ("Chennai · eggetarian, no onion/garlic", "Chennai", "India", "eggetarian", [], ["no_onion_garlic"], [],
     "Filter coffee, idli with sambar, lunch is rice with rasam and a poriyal, evening snack is sundal, dinner is dosa or an egg curry.", 1.0),
]


def _profile(location: str, diet: str, styles, restrictions, allergies, description: str, budget_mult: float) -> tuple[Profile, object]:
    res = region.resolve(location)
    budget = (res.region.budget or res.budget).get("typical") or 10
    p = Profile.model_validate({
        "basics": {"sex": "female", "age": 32, "height_cm": 164, "weight_kg": 72, "target_weight_kg": 65, "activity": "light", "pace": "steady"},
        "background": {"location": location, "region": res.region.model_dump(), "cultures": [], "diet_type": diet,
                       "diet_styles": styles, "restrictions": restrictions, "allergies": allergies, "avoid_foods": []},
        "typical_day": {"description": description, "meals": [], "eat_out_per_week": 1},
        "kitchen": {"equipment": ["stove", "pressure_cooker", "refrigerator", "microwave"], "pantry": [],
                    "daily_budget": round(budget * budget_mult, 2), "cook_minutes_per_day": 45, "skill": "comfortable",
                    "batch_cooking": True},
    })
    return p, res


def _violations(plan, banned: set[str]) -> list[str]:
    found = []
    for d in plan.days:
        for m in d.meals:
            text = f"{m.dish} {m.portion}".lower()
            for phrase in SAFE_PHRASES:
                text = text.replace(phrase, " ")
            for tag in banned & BANNED_WORDS.keys():
                for w in BANNED_WORDS[tag]:
                    if re.search(rf"\b{re.escape(w)}", text):
                        found.append(f"{d.day} {m.slot}: '{m.dish}' ({tag})")
                        break
    return found


def _regional_share(plan, cuisine: kb.CuisineProfile) -> float:
    vocab = {w for d in cuisine.dishes for w in kb.normalize(d.name).split() if len(w) > 3}
    vocab |= {w for s in cuisine.staples for w in kb.normalize(s).split() if len(w) > 3}
    meals = [m for d in plan.days for m in d.meals if not m.top_up]
    hits = sum(1 for m in meals if set(kb.normalize(m.dish).split()) & vocab)
    return hits / max(1, len(meals))


def run() -> list[dict]:
    results = []
    for name, location, country, diet, styles, restrictions, allergies, description, mult in PROFILES:
        print(f"→ {name}", flush=True)
        row: dict = {"profile": name, "location": location}
        try:
            profile, res = _profile(location, diet, styles, restrictions, allergies, description, mult)
            row["currency"] = res.region.currency_code
            row["currency_ok"] = res.region.currency_code in CURRENCY["currencies"][country]
            r = generate_plan(profile)
            cuisine = region.profile_for(profile.background.region, wait_s=0)
            banned = kb.excluded_tags(diet, restrictions, allergies)
            bad_days, _ = variety.check(r.plan)
            violations = _violations(r.plan, banned)
            row.update({
                "model": r.model_label, "seconds": r.seconds, "target_kcal": r.targets.target_kcal,
                "kcal_days_ok": sum(c.kcal_ok for c in r.checks), "protein_days_ok": sum(c.protein_ok for c in r.checks),
                "budget_days_ok": sum(c.budget_ok for c in r.checks), "days": len(r.checks),
                "avg_kcal": round(sum(c.kcal for c in r.checks) / max(1, len(r.checks))),
                "avg_protein": round(sum(c.protein_g for c in r.checks) / max(1, len(r.checks))), "protein_target": r.targets.protein_g,
                "avg_cost": round(sum(c.cost for c in r.checks) / max(1, len(r.checks)), 2), "budget": profile.kitchen.daily_budget,
                "distinct_dishes": variety.distinct_dishes(r.plan), "repetitive_days": len(bad_days),
                "diet_violations": violations, "regional_share": round(_regional_share(r.plan, cuisine), 2),
                "sample_day": [f"{m.slot}: {m.dish}" for m in r.plan.days[2].meals if not m.top_up] if len(r.plan.days) > 2 else [],
            })
        except LLMError as e:
            row["error"] = str(e)
        results.append(row)
        print(f"  {json.dumps({k: v for k, v in row.items() if k not in ('sample_day', 'diet_violations')}, ensure_ascii=False)}", flush=True)
        time.sleep(20)  # stay inside free-tier per-minute token limits
    return results


def report(results: list[dict]) -> str:
    ok = [r for r in results if "error" not in r]
    lines = [
        "# Regional plan evaluation", "",
        f"{len(ok)}/{len(results)} profiles planned. Each plan is 7 days; ✓ counts are days within limits "
        "(calories ±10%, protein ≥85% of target, cost ≤110% of budget). Currency is checked against the "
        "mledoze/countries dataset; diet violations are a keyword scan of every meal.", "",
        "| Profile | Model | Time | Currency | kcal ✓ | Protein ✓ (avg/target) | Budget ✓ (avg/budget) | Distinct dishes | Repetitive days | Diet violations | Regional share |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if "error" in r:
            lines.append(f"| {r['profile']} | — | — | {r.get('currency', '—')} | error: {r['error']} | | | | | | |")
            continue
        lines.append(
            f"| {r['profile']} | {r['model']} | {r['seconds']}s | {r['currency']} {'✓' if r['currency_ok'] else '✗'} | "
            f"{r['kcal_days_ok']}/{r['days']} | {r['protein_days_ok']}/{r['days']} ({r['avg_protein']}/{r['protein_target']} g) | "
            f"{r['budget_days_ok']}/{r['days']} ({r['avg_cost']}/{r['budget']}) | {r['distinct_dishes']} | {r['repetitive_days']} | "
            f"{len(r['diet_violations'])} | {r['regional_share']:.0%} |"
        )
    if ok:
        n = len(ok)
        lines += ["", "## Totals", "",
                  f"- Calories on target: {sum(r['kcal_days_ok'] for r in ok)}/{sum(r['days'] for r in ok)} days",
                  f"- Protein on target: {sum(r['protein_days_ok'] for r in ok)}/{sum(r['days'] for r in ok)} days",
                  f"- Within budget: {sum(r['budget_days_ok'] for r in ok)}/{sum(r['days'] for r in ok)} days",
                  f"- Currency correct: {sum(r['currency_ok'] for r in ok)}/{n}",
                  f"- Diet violations: {sum(len(r['diet_violations']) for r in ok)} meals",
                  f"- Average distinct dishes per week: {sum(r['distinct_dishes'] for r in ok) / n:.1f}",
                  f"- Average regional share: {sum(r['regional_share'] for r in ok) / n:.0%}"]
        lines += ["", "## Diet violations found", ""] + [f"- {r['profile']}: {v}" for r in ok for v in r["diet_violations"]] or ["- none"]
        lines += ["", "## Sample day (Wednesday) per profile", ""]
        for r in ok:
            lines.append(f"**{r['profile']}**: " + " · ".join(r["sample_day"]))
            lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    only = sys.argv[1:]
    if only:
        PROFILES[:] = [p for p in PROFILES if any(o.lower() in p[0].lower() for o in only)]
    results = run()
    (HERE / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    (HERE / "report.md").write_text(report(results), encoding="utf-8")
    print(f"\nwrote {HERE / 'report.md'}")
