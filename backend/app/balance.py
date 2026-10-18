"""Deterministic day balancer.

Models are good at picking dishes and bad at arithmetic, so after the plan comes back we re-add each
day ourselves and, where it falls short, add small diet-safe top-ups (a pot of yogurt, a slice of bread).
When protein is short but calories are already at the ceiling, one serving of a staple is trimmed to
make room. Every change is flagged so the UI can show what the code did.
"""

from dataclasses import dataclass
from math import ceil

from .schemas import PlanDay, PlannedMeal, Targets


@dataclass(frozen=True)
class Food:
    name: str
    portion: str
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    cost_share: float  # cost as a share of the region's typical daily food budget
    contains: tuple[str, ...]


PROTEIN_BOOSTERS = [
    Food("Plain yogurt", "1 cup (150 g)", 100, 8, 7, 4, 0.06, ("dairy",)),
    Food("Boiled eggs", "2 eggs", 140, 12, 1, 10, 0.07, ("egg",)),
    Food("Cooked lentils", "1/2 cup", 115, 9, 20, 0.5, 0.04, ("legumes",)),
    Food("Chickpeas", "1/2 cup cooked", 135, 7, 22, 2, 0.04, ("legumes",)),
    Food("Firm tofu", "100 g", 145, 15, 3, 8, 0.08, ("soy", "legumes")),
    Food("Cottage cheese", "1/2 cup", 110, 13, 5, 4, 0.08, ("dairy",)),
]
ENERGY_FILLERS = [
    Food("Bread", "1 slice", 90, 3, 16, 1, 0.02, ("gluten", "grains")),
    Food("Cooked rice", "1/2 cup", 100, 2, 22, 0.2, 0.02, ("grains",)),
    Food("Banana", "1 medium", 105, 1, 27, 0.4, 0.03, ()),
    Food("Boiled potato", "1 medium", 130, 3, 30, 0.2, 0.02, ("root_veg",)),
]
PROTEIN_SLOTS = ["snack", "breakfast", "lunch", "dinner"]
ENERGY_SLOTS = ["lunch", "dinner", "breakfast"]
MAX_TOPUPS_PER_DAY = 4


def _allowed(foods: list[Food], banned: set[str], avoid: set[str]) -> list[Food]:
    return [f for f in foods if not banned.intersection(f.contains) and not any(a in f.name.lower() for a in avoid)]


def _host_meal(day: PlanDay, slots: list[str]) -> int:
    names = [m.slot.lower() for m in day.meals]
    for s in slots:
        for i, n in enumerate(names):
            if s in n:
                return i
    return len(day.meals) - 1


def _add(day: PlanDay, food: Food, n: int, slots: list[str], unit_cost: float, label: str = "Top-up") -> None:
    host = _host_meal(day, slots)
    day.meals.insert(
        host + 1,
        PlannedMeal(
            slot=day.meals[host].slot,
            time=day.meals[host].time,
            dish=f"{label}: {food.name}",
            portion=f"{abs(n)} × {food.portion}",
            kcal=food.kcal * n,
            protein_g=food.protein_g * n,
            carbs_g=food.carbs_g * n,
            fat_g=food.fat_g * n,
            cost=round(food.cost_share * unit_cost * n, 2),
            top_up=True,
        ),
    )


def balance_day(day: PlanDay, t: Targets, banned: set[str], avoid: set[str], typical_budget: float) -> int:
    """Adjusts the day in place; returns how many changes were made."""
    if not day.meals:
        return 0
    changes = 0
    kcal = sum(m.kcal for m in day.meals)
    protein = sum(m.protein_g for m in day.meals)
    ceiling = t.target_kcal * 1.05
    boosters = _allowed(PROTEIN_BOOSTERS, banned, avoid)
    fillers = _allowed(ENERGY_FILLERS, banned, avoid)

    # Protein short and no calorie room: trim one staple serving first.
    if boosters and fillers and protein < t.protein_g * 0.9 and kcal + boosters[0].kcal > ceiling:
        _add(day, fillers[0], -1, ENERGY_SLOTS[::-1], typical_budget, label="Swap out")
        kcal -= fillers[0].kcal
        protein -= fillers[0].protein_g
        changes += 1

    for food in boosters:
        if protein >= t.protein_g * 0.9 or changes >= MAX_TOPUPS_PER_DAY:
            break
        n = min(2, ceil((t.protein_g * 0.9 - protein) / food.protein_g))
        while n and kcal + food.kcal * n > ceiling:
            n -= 1
        if n:
            _add(day, food, n, PROTEIN_SLOTS, typical_budget)
            kcal += food.kcal * n
            protein += food.protein_g * n
            changes += 1

    # Then fill remaining energy with a plain staple.
    if fillers and kcal < t.target_kcal * 0.95 and changes < MAX_TOPUPS_PER_DAY:
        food = fillers[0]
        n = min(4, round((t.target_kcal - kcal) / food.kcal))
        if n:
            first = ceil(n / 2)
            _add(day, food, first, ENERGY_SLOTS, typical_budget)
            if n - first:
                _add(day, food, n - first, ENERGY_SLOTS[1:], typical_budget)
            changes += 1
    return changes
