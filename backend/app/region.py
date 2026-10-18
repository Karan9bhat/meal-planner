"""Turn free-text locations ("Lyon", "Baramulla", "Манчестер") into a cuisine profile.

1. Knowledge-base alias match            -> instant
2. Location cache (kb/generated)         -> instant
3. Fast model: place -> country/currency, mapped to a known cuisine when one fits
4. Unknown cuisine: Gemma 4 writes a full profile in the background, saved to the KB for next time
"""

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, ValidationError

from . import kb
from .config import route
from .observability import agent_span
from .llm import LLMError, chat_json
from .schemas import RegionRef

log = logging.getLogger("mealplanner.region")

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kb-gen")
_status: dict[str, str] = {}  # cuisine key -> "generating" | "ready" | "failed"
_status_lock = threading.Lock()


class Resolution(BaseModel):
    region: RegionRef
    status: str  # "ready" | "generating" | "failed"
    source: str  # "knowledge base" | "cache" | model label
    staples: list[str] = []
    meal_times: dict[str, str] = {}
    budget: dict[str, float] = {}
    route_reason: str = ""


def _ref(p: kb.CuisineProfile, place: str, country: str = "") -> RegionRef:
    return RegionRef(
        key=p.key,
        name=p.name,
        place=place,
        country=country or p.region,
        currency_code=p.currency.code,
        currency_symbol=p.currency.symbol,
        budget=p.daily_budget.model_dump(),
    )


def _budget_around(typical: float) -> dict[str, float]:
    return {"low": round(typical * 0.6, 2), "typical": round(typical, 2), "high": round(typical * 1.8, 2)}


def _resolution(ref: RegionRef, source: str, reason: str = "") -> Resolution:
    p = kb.CUISINES.get(ref.key)
    status = "ready" if p else _status.get(ref.key, "failed")
    # The place's own budget wins; a profile's budget only counts when it's in the same currency.
    budget = ref.budget or (p.daily_budget.model_dump() if p and p.currency.code == ref.currency_code else {})
    return Resolution(
        region=ref.model_copy(update={"budget": budget}),
        status=status,
        source=source,
        staples=p.staples if p else [],
        meal_times=p.meal_times if p else {},
        budget=budget,
        route_reason=reason,
    )


def status(key: str) -> Resolution | None:
    p = kb.CUISINES.get(key)
    if p:
        return _resolution(_ref(p, p.region), "knowledge base")
    if key in _status:
        return Resolution(region=RegionRef(key=key, name=key, place=key), status=_status[key], source="generating")
    return None


EXTRACT_SYSTEM = """You map a free-text place name to food-geography facts. Answer with JSON only."""


def _extract(location: str) -> tuple[dict, str, str]:
    known = "\n".join(f"- {p.key}: {p.name} ({p.region})" for p in kb.CUISINES.values() if p.key != "global")
    r = route("extract", location)
    res = chat_json(
        EXTRACT_SYSTEM,
        f"""Place typed by the user: "{location}"

Known cuisine profiles:
{known}

Return JSON:
{{"place": "tidy place name, e.g. 'Lyon, France'", "country": "country in English",
  "currency_code": "ISO 4217", "currency_symbol": "symbol",
  "typical_daily_food_budget": "number: typical home grocery spend per person per day there, in that currency",
  "cuisine_key": "one of the known keys if the everyday home food there is essentially that cuisine, else null",
  "new_cuisine": {{"key": "snake_case key for the local cuisine, e.g. 'polish' or 'kerala_coastal'", "name": "display name"}}}}
If the text is not a real place, return {{"place": null}}.""",
        route=r,
        max_tokens=400,
        temperature=0.1,
    )
    return res.data, res.model.label, r.reason


GENERATE_SYSTEM = """You are a food anthropologist and nutritionist building a knowledge base of everyday home cooking.
Describe what ordinary households in a place actually eat on weekdays, with realistic portions and nutrition.
Answer with JSON only."""


def _generate(key: str, name: str, place: str, country: str, currency: kb.Currency) -> None:
    with agent_span("region-knowledge-writer", **{"region.key": key, "region.place": place}):
        _write_profile(key, name, place, country, currency)


def _write_profile(key: str, name: str, place: str, country: str, currency: kb.Currency) -> None:
    try:
        r = route("knowledge")
        res = chat_json(
            GENERATE_SYSTEM,
            f"""Write the cuisine profile for everyday home food in {place} ({country}). Cuisine name: {name}.
Return JSON exactly in this shape (12-16 dishes covering breakfast, lunch, dinner and snacks; kcal and protein per stated portion;
'contains' uses only these tags: poultry, beef, pork, lamb_mutton, fish, shellfish, egg, dairy, gluten, grains, legumes,
peanut, tree_nut, soy, sesame, onion_garlic, root_veg, alcohol, caffeine; daily_budget is groceries per person per day in {currency.code}):
{{"staples": ["..."], "meal_pattern": "one sentence", "meal_times": {{"breakfast": "08:00", "lunch": "13:00", "snack": "16:30", "dinner": "19:30"}},
 "daily_budget": {{"low": 0, "typical": 0, "high": 0}}, "pantry_basics": ["..."],
 "dishes": [{{"name": "...", "portion": "...", "kcal": 0, "protein_g": 0, "contains": ["..."]}}]}}""",
            route=r,
            max_tokens=3500,
            temperature=0.3,
        )
        profile = kb.CuisineProfile.model_validate(
            {
                **res.data,
                "key": key,
                "name": name,
                "region": place,
                "aliases": [place, place.split(",")[0]],
                "currency": currency.model_dump(),
                "source": f"generated by {res.model.label}",
            }
        )
        if len(profile.dishes) < 5:
            raise ValueError("too few dishes")
        kb.save_generated(profile)
        _status[key] = "ready"
        log.info("generated cuisine profile %s with %s", key, res.model.label)
    except (LLMError, ValidationError, ValueError) as e:
        log.warning("cuisine generation failed for %s: %s", key, e)
        _status[key] = "failed"


def resolve(location: str) -> Resolution:
    location = location.strip()
    hit = kb.match_location(location)
    if hit:
        p = kb.CUISINES[hit[0]]
        return _resolution(_ref(p, location.title() if location.islower() else location), "knowledge base")

    cached = kb.cached_location(location)
    if cached:
        ref = RegionRef.model_validate(cached)
        if ref.key not in kb.CUISINES:
            _start_generation(ref)  # e.g. the server restarted mid-generation
        return _resolution(ref, "cache")

    data, model_label, reason = _extract(location)
    if not data.get("place"):
        raise LLMError(f"Couldn't recognise “{location}” as a place. Try a city, region or country.", 422)

    place, country = data["place"], data.get("country", "")
    currency = kb.Currency(code=data.get("currency_code") or "USD", symbol=data.get("currency_symbol") or "$")
    try:
        estimate = _budget_around(float(data.get("typical_daily_food_budget") or 0))
    except (TypeError, ValueError):
        estimate = {"typical": 0}
    if estimate["typical"] <= 0:
        estimate = {}
    key = data.get("cuisine_key")
    if key in kb.CUISINES:
        p = kb.CUISINES[key]
        # e.g. Toronto -> American food but CAD prices: keep the place's currency and budget.
        same_currency = p.currency.code == currency.code
        ref = RegionRef(key=p.key, name=p.name, place=place, country=country,
                        currency_code=currency.code, currency_symbol=currency.symbol,
                        budget=p.daily_budget.model_dump() if same_currency else estimate)
    else:
        new = data.get("new_cuisine") or {}
        key = re.sub(r"[^a-z0-9_]", "_", (new.get("key") or country or place).lower()).strip("_")[:40] or "local"
        name = new.get("name") or f"{country} home cooking"
        ref = RegionRef(key=key, name=name, place=place, country=country,
                        currency_code=currency.code, currency_symbol=currency.symbol, budget=estimate)
        _start_generation(ref)

    kb.cache_location(location, ref.model_dump())
    return _resolution(ref, model_label, reason)


def _start_generation(ref: RegionRef) -> None:
    with _status_lock:
        if ref.key not in kb.CUISINES and _status.get(ref.key) != "generating":
            _status[ref.key] = "generating"
            currency = kb.Currency(code=ref.currency_code, symbol=ref.currency_symbol)
            _pool.submit(_generate, ref.key, ref.name, ref.place, ref.country, currency)


def profile_for(ref: RegionRef | None, wait_s: float = 90) -> kb.CuisineProfile:
    """The cuisine profile to plan with, waiting for a background generation if one is running."""
    if ref is None:
        return kb.CUISINES["global"]
    deadline = time.monotonic() + wait_s
    while ref.key not in kb.CUISINES and _status.get(ref.key) == "generating" and time.monotonic() < deadline:
        time.sleep(1)
    if ref.key in kb.CUISINES:
        p = kb.CUISINES[ref.key]
        # Plan in the place's currency even when its food maps to a cuisine priced elsewhere.
        if p.currency.code != ref.currency_code:
            p = p.model_copy(update={"currency": kb.Currency(code=ref.currency_code, symbol=ref.currency_symbol)})
        return p
    # Generation failed or timed out: plan with the generic profile in the user's currency.
    g = kb.CUISINES["global"]
    return g.model_copy(update={"currency": kb.Currency(code=ref.currency_code, symbol=ref.currency_symbol),
                                "name": ref.name, "region": ref.place})
