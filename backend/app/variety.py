"""Week variety check.

Models happily rotate the same three dishes. This counts dishes per meal type across the week and flags the
days that go over the limits, so the planner can ask for just those days again. Drinks (tea, coffee) may repeat.
"""

import re
from collections import Counter

from .schemas import Plan

# Lunch and dinner share one limit: cooking a main once and eating it again the next day is fine, a third time isn't.
LIMITS = {"breakfast": 2, "main": 2, "snack": 3}

_DRINKS = {
    "tea", "chai", "coffee", "water", "milk", "kahwa", "juice", "lassi", "buttermilk", "chaas", "kefir",
    "espresso", "latte", "cappuccino", "smoothie", "soda", "noon", "masala", "green", "black", "herbal", "filter",
}


def meal_kind(slot: str) -> str:
    s = slot.lower()
    if "breakfast" in s:
        return "breakfast"
    if any(w in s for w in ("lunch", "dinner", "supper")):
        return "main"
    return "snack"


def dish_key(name: str) -> str:
    """'Pasta with lentil bolognese (1 plate) + salad' -> 'pasta with lentil bolognese'."""
    s = re.sub(r"\(.*?\)", "", name.lower())
    s = re.split(r"\s*[+,;/&]\s*|\s+and\s+", s)[0]
    return re.sub(r"\s+", " ", s).strip(" .-")


def _is_drink(key: str) -> bool:
    words = key.split()
    return bool(words) and (words[0] in _DRINKS or all(w in _DRINKS or w in {"with", "sugar", "no"} for w in words))


def check(plan: Plan) -> tuple[list[str], dict[str, int]]:
    """(days to re-plan, {dish: times used}) — empty when the week is varied enough."""
    seen: Counter = Counter()
    overused: dict[str, int] = {}
    bad_days: list[str] = []
    signatures: set[tuple[str, ...]] = set()
    for day in plan.days:
        day_bad = False
        keys = []
        for m in day.meals:
            if m.top_up:
                continue
            key = dish_key(m.dish)
            if not key or _is_drink(key):
                continue
            keys.append(key)
            kind = meal_kind(m.slot)
            seen[(kind, key)] += 1
            if seen[(kind, key)] > LIMITS[kind]:
                overused[key] = seen[(kind, key)]
                day_bad = True
        signature = tuple(sorted(keys))
        if signature and signature in signatures:  # an exact copy of an earlier day
            day_bad = True
        signatures.add(signature)
        if day_bad:
            bad_days.append(day.day)
    return bad_days, overused


def distinct_dishes(plan: Plan) -> int:
    return len({dish_key(m.dish) for d in plan.days for m in d.meals if not m.top_up and not _is_drink(dish_key(m.dish))})
