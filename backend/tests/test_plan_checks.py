"""Deterministic plan post-processing: the balancer and the variety check."""

from app import variety
from app.balance import balance_day
from app.nutrition import compute_targets
from app.schemas import Basics, Plan, PlanDay, PlannedMeal

TARGETS = compute_targets(Basics(sex="female", age=30, height_cm=165, weight_kg=70, target_weight_kg=63, activity="light"))


def meal(slot, dish, kcal=400, protein=15):
    return PlannedMeal(slot=slot, time="12:00", dish=dish, kcal=kcal, protein_g=protein, carbs_g=40, fat_g=10, cost=2)


def test_balancer_tops_up_a_short_day_without_breaking_diet():
    day = PlanDay(day="Monday", meals=[meal("Breakfast", "Oats", 300, 8), meal("Lunch", "Salad", 350, 10), meal("Dinner", "Pasta", 450, 14)])
    banned = {"dairy", "egg", "poultry", "beef", "pork", "lamb_mutton", "fish", "shellfish", "red_meat", "meat", "seafood", "animal_product"}
    assert balance_day(day, TARGETS, banned, set(), 10) > 0
    added = [m for m in day.meals if m.top_up]
    assert added and not any(w in m.dish.lower() for m in added for w in ("yogurt", "egg", "cottage"))
    assert sum(m.kcal for m in day.meals) <= TARGETS.target_kcal * 1.05


def test_balancer_trims_a_staple_to_make_room_for_protein():
    day = PlanDay(day="Monday", meals=[meal("Breakfast", "Toast", 500, 8), meal("Lunch", "Rice", 600, 8), meal("Dinner", "Pasta", 520, 10)])
    balance_day(day, TARGETS, set(), set(), 10)
    assert any(m.top_up and m.kcal < 0 for m in day.meals)  # "Swap out"
    assert sum(m.protein_g for m in day.meals) > 26


def test_balancer_respects_custom_allergy_words():
    day = PlanDay(day="Monday", meals=[meal("Lunch", "Soup", 300, 5)])
    balance_day(day, TARGETS, set(), {"banana", "bread"}, 10)
    assert not any(w in m.dish.lower() for m in day.meals for w in ("banana", "bread"))


def week(menu: list[tuple[str, str, str]]) -> Plan:
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return Plan(days=[PlanDay(day=d, meals=[meal("Breakfast", b), meal("Lunch", l), meal("Dinner", n), meal("Evening", "Masala chai")])
                      for d, (b, l, n) in zip(days, menu)])


def test_variety_flags_rotation():
    plan = week([("Poha", "Dal rice", "Paneer curry")] * 7)
    bad, over = variety.check(plan)
    assert bad == ["Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] or len(bad) >= 5
    assert "poha" in over and "dal rice" in over


def test_variety_allows_leftovers_and_daily_tea():
    plan = week([
        ("Poha", "Rajma rice", "Palak paneer"), ("Idli", "Leftover palak paneer", "Chole"), ("Upma", "Chole", "Egg curry"),
        ("Poha", "Dal khichdi", "Fish curry"), ("Dosa", "Fish curry", "Veg pulao"), ("Paratha", "Sambar rice", "Kadhi"),
        ("Oats", "Kadhi", "Mixed veg"),
    ])
    assert variety.check(plan) == ([], {})
    assert variety.distinct_dishes(plan) >= 15


def test_dish_key_ignores_portions_and_sides():
    assert variety.dish_key("Pasta with lentil bolognese (1 plate) + side salad") == "pasta with lentil bolognese"
