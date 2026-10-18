"""Knowledge base: cuisines (curated + model-generated), diet rules, and fast lookups.

Curated profiles live in kb/cuisines.json. Profiles for places the curated set doesn't cover are
generated once by a model (see region.py) and saved under kb/generated/, so every later lookup is
an instant file read instead of a model call.
"""

import json
import re
import threading
import unicodedata
from pathlib import Path

from pydantic import BaseModel, Field

from .config import BACKEND_DIR

KB_DIR = BACKEND_DIR / "kb"
GENERATED_DIR = KB_DIR / "generated"
GENERATED_CUISINES = GENERATED_DIR / "cuisines"
LOCATIONS_FILE = GENERATED_DIR / "locations.json"


# ---------- models ----------

class Dish(BaseModel):
    name: str
    portion: str
    kcal: float
    protein_g: float
    contains: list[str] = []


class Currency(BaseModel):
    code: str
    symbol: str


class Budget(BaseModel):
    low: float
    typical: float
    high: float


class CuisineProfile(BaseModel):
    key: str
    name: str
    region: str
    aliases: list[str] = []
    staples: list[str]
    meal_pattern: str = ""
    meal_times: dict[str, str] = {}
    currency: Currency
    daily_budget: Budget
    pantry_basics: list[str] = []
    dishes: list[Dish] = Field(default_factory=list)
    source: str = "curated"


# ---------- diet rules (tags match Dish.contains) ----------

# Ingredient tag hierarchy: rules can exclude a broad group and every tag beneath it is excluded too.
# The knowledge graph stores this as INCLUDES edges and expands it with $graphLookup.
TAG_HIERARCHY = {
    "animal_product": ["meat", "seafood", "egg", "dairy"],
    "meat": ["poultry", "red_meat"],
    "red_meat": ["beef", "pork", "lamb_mutton"],
    "seafood": ["fish", "shellfish"],
}


def expand_tags(tags: set[str] | list[str]) -> set[str]:
    out, stack = set(), list(tags)
    while stack:
        t = stack.pop()
        if t not in out:
            out.add(t)
            stack.extend(TAG_HIERARCHY.get(t, []))
    return out


DIET_TYPES = {
    "omnivore": {"label": "Everything", "desc": "No restrictions", "excludes": []},
    "flexitarian": {"label": "Flexitarian", "desc": "Mostly plants, meat now and then", "excludes": []},
    "pollotarian": {"label": "Pollotarian", "desc": "Poultry, no red meat or seafood", "excludes": ["red_meat", "seafood"]},
    "pescatarian": {"label": "Pescatarian", "desc": "Fish & seafood, no meat", "excludes": ["meat"]},
    "eggetarian": {"label": "Eggetarian", "desc": "Vegetarian plus eggs", "excludes": ["meat", "seafood"]},
    "vegetarian": {"label": "Vegetarian", "desc": "Dairy ok; no meat, fish or eggs", "excludes": ["meat", "seafood", "egg"]},
    "vegan": {"label": "Vegan", "desc": "No animal products", "excludes": ["animal_product"]},
    "jain": {"label": "Jain", "desc": "Vegetarian, no root veg, onion or garlic", "excludes": ["meat", "seafood", "egg", "onion_garlic", "root_veg"]},
    "sattvic": {"label": "Sattvic", "desc": "Vegetarian, no onion, garlic or stimulants", "excludes": ["meat", "seafood", "egg", "onion_garlic", "alcohol", "caffeine"]},
    "paleo": {"label": "Paleo", "desc": "No grains, legumes or dairy", "excludes": ["grains", "gluten", "legumes", "dairy"]},
}

# Styles shape macros and cooking rather than banning ingredients outright.
DIET_STYLES = {
    "high_protein": "High protein",
    "low_carb": "Low carb",
    "keto": "Keto",
    "mediterranean": "Mediterranean",
    "low_sodium": "Low sodium",
    "whole_foods": "Whole foods, little processed food",
    "budget_first": "Cheapest possible",
}

RESTRICTIONS = {
    "halal": {"label": "Halal", "excludes": ["pork", "alcohol"]},
    "kosher": {"label": "Kosher", "excludes": ["pork", "shellfish"]},
    "no_beef": {"label": "No beef", "excludes": ["beef"]},
    "no_pork": {"label": "No pork", "excludes": ["pork"]},
    "no_onion_garlic": {"label": "No onion / garlic", "excludes": ["onion_garlic"]},
    "no_alcohol": {"label": "No alcohol in cooking", "excludes": ["alcohol"]},
    "no_caffeine": {"label": "No caffeine", "excludes": ["caffeine"]},
}

ALLERGIES = {
    "dairy": "Dairy / lactose",
    "gluten": "Gluten",
    "peanut": "Peanuts",
    "tree_nut": "Tree nuts",
    "egg": "Eggs",
    "soy": "Soy",
    "fish": "Fish",
    "shellfish": "Shellfish",
    "sesame": "Sesame",
}

EQUIPMENT = {
    "stove": "Stove / hob",
    "induction": "Induction plate",
    "oven": "Oven",
    "microwave": "Microwave",
    "air_fryer": "Air fryer",
    "pressure_cooker": "Pressure cooker / Instant Pot",
    "slow_cooker": "Slow cooker",
    "rice_cooker": "Rice cooker",
    "blender": "Blender / mixer",
    "toaster": "Toaster",
    "grill": "Grill",
    "kettle": "Kettle",
    "refrigerator": "Fridge",
    "freezer": "Freezer",
}


def excluded_tags_local(diet_type: str, restrictions: list[str], allergies: list[str]) -> set[str]:
    """In-memory rule expansion; the fallback when the knowledge graph isn't reachable."""
    tags = set(DIET_TYPES.get(diet_type, DIET_TYPES["omnivore"])["excludes"])
    for r in restrictions:
        tags.update(RESTRICTIONS.get(r, {}).get("excludes", []))
    tags.update(allergies)
    return expand_tags(tags)


def excluded_tags(diet_type: str, restrictions: list[str], allergies: list[str]) -> set[str]:
    from . import graph  # local import: graph depends on this module

    found = graph.excluded_tags(diet_type, restrictions, allergies)
    return found if found is not None else excluded_tags_local(diet_type, restrictions, allergies)


# ---------- loading ----------

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s&'-]", " ", text)).strip()


_lock = threading.Lock()
CUISINES: dict[str, CuisineProfile] = {}
_ALIASES: dict[str, str] = {}


def _index(p: CuisineProfile) -> None:
    CUISINES[p.key] = p
    for alias in [p.name, p.region, *p.aliases]:
        a = normalize(alias)
        if len(a) >= 2:
            _ALIASES.setdefault(a, p.key)


def load() -> None:
    with _lock:
        CUISINES.clear()
        _ALIASES.clear()
        data = json.loads((KB_DIR / "cuisines.json").read_text(encoding="utf-8"))
        for raw in data["cuisines"]:
            _index(CuisineProfile.model_validate(raw))
        if GENERATED_CUISINES.exists():
            for f in sorted(GENERATED_CUISINES.glob("*.json")):
                try:
                    _index(CuisineProfile.model_validate_json(f.read_text(encoding="utf-8")))
                except ValueError:
                    continue  # a corrupt cache file must not break startup


def save_generated(p: CuisineProfile) -> None:
    from . import graph

    GENERATED_CUISINES.mkdir(parents=True, exist_ok=True)
    (GENERATED_CUISINES / f"{p.key}.json").write_text(p.model_dump_json(indent=2), encoding="utf-8")
    graph.save_cuisine(p)  # Atlas copy survives redeploys; the file is a local cache
    with _lock:
        _index(p)


def merge_graph_cuisines() -> int:
    """Pull model-written profiles saved in the knowledge graph into memory (e.g. after a redeploy)."""
    from . import graph

    added = 0
    for p in graph.generated_cuisines():
        if p.key not in CUISINES:
            with _lock:
                _index(p)
            added += 1
    return added


def _read_locations() -> dict[str, dict]:
    try:
        return json.loads(LOCATIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def cached_location(text: str) -> dict | None:
    from . import graph

    return _read_locations().get(normalize(text)) or graph.find_place(text)


def cache_location(text: str, entry: dict) -> None:
    from . import graph

    graph.save_place(text, entry)
    with _lock:
        locations = _read_locations()
        locations[normalize(text)] = entry
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        LOCATIONS_FILE.write_text(json.dumps(locations, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- lookups ----------

def match_location(text: str) -> tuple[str, str] | None:
    """(cuisine key, matched alias) for free text like 'Lyon, France' or 'baramulla'; most specific part first."""
    parts = [normalize(p) for p in re.split(r"[,/;|\n]", text) if normalize(p)]
    for part in parts or [normalize(text)]:
        if part in _ALIASES:
            return _ALIASES[part], part
        words = part.split()
        for n in range(min(4, len(words)), 0, -1):  # longest n-grams first: "new york" before "york"
            for i in range(len(words) - n + 1):
                gram = " ".join(words[i : i + n])
                if len(gram) >= 3 and gram in _ALIASES:
                    return _ALIASES[gram], gram
    return None


def cuisine_for_culture(name: str) -> CuisineProfile | None:
    hit = match_location(name)
    if hit:
        return CUISINES.get(hit[0])
    n = normalize(name)
    for p in CUISINES.values():
        if n and (n in normalize(p.name) or normalize(p.name) in n):
            return p
    return None


_FILLER = {"with", "and", "the", "for", "style", "plain", "mixed", "cup", "bowl", "small", "large", "fresh", "home", "made"}


def _tokens(text: str) -> set[str]:
    return {w for w in normalize(text).split() if len(w) > 2 and w not in _FILLER}


def search_dishes(query: str, *, prefer: list[str] | None = None, banned: set[str] | None = None, limit: int = 8) -> list[dict]:
    """Token-overlap dish search across the whole KB, preferring the user's cuisines."""
    q = _tokens(query)
    prefer = prefer or []
    banned = banned or set()
    scored = []
    for p in CUISINES.values():
        for d in p.dishes:
            overlap = len(q & _tokens(d.name))
            if not overlap:
                continue
            score = overlap + (0.5 if p.key in prefer else 0)
            scored.append((score, d, p))
    scored.sort(key=lambda x: -x[0])
    out = []
    for _, d, p in scored[: limit * 3]:
        if banned.intersection(d.contains):
            continue
        out.append({**d.model_dump(), "cuisine": p.name})
        if len(out) >= limit:
            break
    return out


def mentioned_dishes(text: str, keys: list[str], limit: int = 25) -> list[dict]:
    """Dishes whose names appear in free text (for grounding the intake agent), plus the user's regional staples."""
    t = _tokens(text)
    hits, seen = [], set()
    for p in CUISINES.values():
        for d in p.dishes:
            name_tokens = _tokens(d.name)
            overlap = len(t & name_tokens)
            if overlap and d.name not in seen:
                seen.add(d.name)
                # Rank: user's own cuisines first, then how much of the dish name the text covers.
                hits.append(((p.key in keys), overlap / len(name_tokens), {**d.model_dump(), "cuisine": p.name}))
    hits.sort(key=lambda x: (not x[0], -x[1]))
    out = [h for _, _, h in hits][:limit]
    for key in keys:
        for d in CUISINES[key].dishes if key in CUISINES else []:
            if len(out) >= limit:
                break
            if d.name not in seen:
                seen.add(d.name)
                out.append({**d.model_dump(), "cuisine": CUISINES[key].name})
    return out


def reference_dishes(keys: list[str], banned: set[str], limit: int = 40) -> list[Dish]:
    out: list[Dish] = []
    for key in keys:
        if key in CUISINES:
            out += [d for d in CUISINES[key].dishes if not banned.intersection(d.contains)]
    return out[:limit]


def options_payload() -> dict:
    return {
        "diet_types": DIET_TYPES,
        "diet_styles": DIET_STYLES,
        "restrictions": {k: v["label"] for k, v in RESTRICTIONS.items()},
        "allergies": ALLERGIES,
        "equipment": EQUIPMENT,
        "cuisines": [{"key": p.key, "name": p.name, "region": p.region} for p in CUISINES.values() if p.key != "global"],
    }


load()
