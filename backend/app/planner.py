"""Turns a profile + computed targets into a 7-day plan.

Flow: code computes targets -> router picks the model chain -> the model drafts the week (one call on fast
hosts, small parallel calls on slow ones) -> code re-totals every day -> short days get deterministic,
diet-safe top-ups (balance.py).
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from pydantic import ValidationError

from . import graph, kb
from .balance import balance_day
from . import variety
from .config import PROVIDERS, ModelSpec, Route, route
from .observability import agent_span, step_span
from .llm import LLMError, LLMResult, chat_json
from .nutrition import apply_styles, compute_targets
from .region import profile_for
from .schemas import CheckRequest, DayCheck, Plan, PlanDay, PlanResponse, Profile, Recipe, Targets

log = logging.getLogger("mealplanner.planner")

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
KCAL_TOLERANCE = 0.10
PROTEIN_MIN_SHARE = 0.85
MAX_UNIQUE_RECIPES = 10

SYSTEM_PROMPT = f"""You are a home-cooking nutrition planner who knows everyday food cultures around the world.
You build realistic, affordable weekly meal plans that a real person can cook in their own kitchen. Hard rules:
1. Diet type, religious restrictions and allergies are absolute. Never include a forbidden ingredient, even as garnish.
2. Only use cooking methods possible with the listed equipment (no oven => no baking; no fridge => nothing chilled or stored cooked overnight).
3. Prefer ingredients already in the pantry. Keep each day's food cost within the daily budget, using realistic local prices in the given currency.
4. Cook the food they know: build on what they already eat and their food culture, swapping in lighter versions rather than unfamiliar cuisine.
5. Each day's total kcal should be close to the calorie target, and protein should reach the protein target.
6. Use the household portions people use locally (cups, slices, bowls, katori, pieces) and keep them concrete.
7. Respect their meal times and number of meals. Fit cooking time within their daily limit.
8. VARIETY: no two days alike. A lunch or dinner main dish appears at most twice a week (cook once, eat the leftovers the
   next day); each breakfast at most twice; each snack at most 3 times. Drinks like tea or coffee may repeat daily.
9. Up to {MAX_UNIQUE_RECIPES} recipes, kept short (at most 8 ingredients and 6 steps). Trivial items (tea, fruit, yogurt,
   boiled eggs, salad) need no recipe (recipe_id null).
Respond with JSON only."""

OUTPUT_SHAPE = """{
  "summary": "2-3 sentences on the approach for this person",
  "days": [
    {"day": "Monday", "meals": [
      {"slot": "Breakfast", "time": "08:00", "dish": "Lentil and spinach omelette", "recipe_id": "r1",
       "portion": "2 eggs + 1 slice toast", "kcal": 320, "protein_g": 20, "carbs_g": 22, "fat_g": 15, "cost": 1.5}
    ], "day_total_kcal": 1850}
  ],
  "recipes": [
    {"id": "r1", "name": "Lentil and spinach omelette", "servings": 1, "time_min": 15, "equipment": ["stove"],
     "ingredients": [{"item": "Eggs", "qty": "2", "in_pantry": true}],
     "steps": ["Whisk the eggs with salt and pepper.", "..."],
     "tip": "Cook a pot of lentils on Sunday and use it all week."}
  ],
  "shopping_list": [{"item": "Spinach", "qty": "200 g", "est_cost": 1.2, "category": "Vegetables"}],
  "tips": ["short, specific, practical tips"]
}"""


# ---------- prompt pieces ----------

def _cuisines(profile: Profile) -> tuple[kb.CuisineProfile, list[kb.CuisineProfile]]:
    home = profile_for(profile.background.region)
    cultures = []
    for name in profile.background.cultures:
        c = kb.cuisine_for_culture(name)
        if c and c.key != home.key and c not in cultures:
            cultures.append(c)
    return home, cultures


def _describe_typical_day(profile: Profile) -> tuple[str, int]:
    td = profile.typical_day
    lines, known = [], 0.0
    for meal in td.meals:
        parts = []
        for it in meal.items:
            if it.kcal:
                known += it.kcal
            kcal = f", ~{it.kcal:.0f} kcal" if it.kcal else ""
            parts.append(f"{it.name}{' (' + it.portion + kcal + ')' if it.portion or kcal else ''}")
        if parts:
            lines.append(f"- {meal.time} {meal.slot}: " + "; ".join(parts))
    text = "\n".join(lines)
    if td.description and not lines:
        text = td.description[:1500]
    return text or "- (not provided)", round(known)


def _diet_rules(profile: Profile) -> str:
    bg = profile.background
    banned = sorted(kb.excluded_tags(bg.diet_type, bg.restrictions, bg.allergies))
    diet = kb.DIET_TYPES.get(bg.diet_type, kb.DIET_TYPES["omnivore"])
    styles = ", ".join(kb.DIET_STYLES.get(s, s) for s in bg.diet_styles)
    # Preset keys get their labels; the user's own entries ("no food after sunset") pass through verbatim.
    restrictions = ", ".join(kb.RESTRICTIONS[r]["label"] if r in kb.RESTRICTIONS else r for r in bg.restrictions)
    allergies = ", ".join(kb.ALLERGIES.get(a, a) for a in bg.allergies)
    notes = []
    if "halal" in bg.restrictions:
        notes.append("halal: only halal meat, no alcohol in cooking")
    if "kosher" in bg.restrictions:
        notes.append("kosher: never mix meat and dairy in a meal")
    return f"""- Diet type: {diet['label']} ({diet['desc']})
- Diet styles: {styles or 'none'}
- Treat every restriction and allergy below as absolute, including ones the user wrote in their own words.
- Restrictions: {restrictions or 'none'}{' (' + '; '.join(notes) + ')' if notes else ''}
- Allergies: {allergies or 'none'}
- Foods they want to avoid: {', '.join(bg.avoid_foods) or 'none'}
- Forbidden ingredient tags: {', '.join(banned) or 'none'}"""


def _kitchen(profile: Profile, currency: kb.Currency) -> str:
    k = profile.kitchen
    equipment = ", ".join(kb.EQUIPMENT.get(e, e) for e in k.equipment) or "a basic stove only"
    return f"""- Equipment: {equipment}
- Pantry: {', '.join(k.pantry) or 'nearly empty'}
- Budget: {currency.symbol}{k.daily_budget:g} ({currency.code}) per day for this person
- Cooking time: about {k.cook_minutes_per_day} min per day, skill: {k.skill}
- Batch cooking / meal prep: {'yes, they like cooking in batches' if k.batch_cooking else 'no, prefers cooking fresh'}"""


def build_context(profile: Profile, t: Targets) -> str:
    b, bg, td = profile.basics, profile.background, profile.typical_day
    home, cultures = _cuisines(profile)
    banned = kb.excluded_tags(bg.diet_type, bg.restrictions, bg.allergies)
    typical, typical_kcal = _describe_typical_day(profile)
    slots = ", ".join(f"{m.slot} at {m.time}" for m in td.meals if m.time) or ", ".join(
        f"{k.replace('_', ' ')} at {v}" for k, v in home.meal_times.items()
    )
    culture_lines = "\n".join(f"- They also grew up with {c.name} food: {', '.join(c.staples[:8])}" for c in cultures)
    keys = [home.key, *[c.key for c in cultures]]
    # Knowledge graph traversal (cuisine → dish → tag) when Atlas is up; same data from memory otherwise.
    refs = graph.allowed_dishes(keys, banned) or kb.reference_dishes(keys, banned)
    ref_lines = "\n".join(f"- {d.name} | {d.portion} | {d.kcal:g} kcal | {d.protein_g:g} g protein" for d in refs)

    return f"""PERSON
- {b.age}-year-old {b.sex}, {b.height_cm:g} cm, {b.weight_kg:g} kg -> goal: {t.goal} to {t.planned_target_weight_kg} kg
- Activity: {b.activity.replace('_', ' ')}

DAILY TARGETS (computed, do not change)
- Calories: {t.target_kcal} kcal
- Protein: at least {t.protein_g} g/day, about {round(t.protein_g * 0.28)} g in each main meal; every main meal needs a protein anchor.
- Carbs: ~{t.carbs_g} g | Fat: ~{t.fat_g} g

WHERE THEY LIVE
- {bg.region.place if bg.region else bg.location or 'unknown'}: {home.name} home cooking ({home.region})
- Local staples: {', '.join(home.staples)}
- Local meal pattern: {home.meal_pattern}
{culture_lines}

DIET RULES
{_diet_rules(profile)}

WHAT THEY EAT ON A TYPICAL DAY (~{typical_kcal} kcal from items with estimates)
{typical}
- Eats out / orders in about {td.eat_out_per_week} meals per week (plan those as lighter restaurant choices).

MEAL SLOTS TO PLAN: {slots}

KITCHEN
{_kitchen(profile, home.currency)}

REFERENCE DISHES THEY CAN EAT (approx. values per portion)
{ref_lines or '- (none)'}

All costs are in {home.currency.code} ({home.currency.symbol})."""


# ---------- drafting ----------

def _draft_single(profile: Profile, t: Targets, r: Route) -> LLMResult:
    return chat_json(
        SYSTEM_PROMPT,
        f"""{build_context(profile, t)}

Plan all 7 days ({', '.join(DAYS)}). Before finishing each day, add up its meal kcal into day_total_kcal and
adjust portions until it lands within 5% of {t.target_kcal}. The shopping list should contain only items NOT already in the pantry.
Return JSON exactly in this shape:
{OUTPUT_SHAPE}""",
        route=r,
        # Groq's free tier rejects (413) any request whose prompt + max_tokens exceeds its per-minute budget.
        max_tokens=6500,
    )


DAY_GROUPS = [DAYS[0:3], DAYS[3:5], DAYS[5:7]]
RECIPES_PER_CALL = 4

OUTLINE_SHAPE = """{
  "summary": "2-3 sentences on the approach for this person",
  "week_menu": {"Monday": {"Breakfast": "Lentil and spinach omelette", "Lunch": "...", "Dinner": "..."}, "Tuesday": {}},
  "recipes": [{"id": "r1", "name": "Lentil and spinach omelette", "for": "Breakfast"}],
  "shopping_list": [{"item": "Spinach", "qty": "200 g", "est_cost": 1.2, "category": "Vegetables"}],
  "tips": ["short, specific, practical tips"]
}"""

DAYS_SHAPE = """{"days": [
  {"day": "Monday", "meals": [
    {"slot": "Breakfast", "time": "08:00", "dish": "Lentil and spinach omelette", "recipe_id": "r1",
     "portion": "2 eggs + 1 slice toast", "kcal": 320, "protein_g": 20, "carbs_g": 22, "fat_g": 15, "cost": 1.5}
  ], "day_total_kcal": 1850}
]}"""

RECIPES_SHAPE = """{"recipes": [
  {"id": "r1", "name": "Lentil and spinach omelette", "servings": 1, "time_min": 15, "equipment": ["stove"],
   "ingredients": [{"item": "Eggs", "qty": "2", "in_pantry": true}],
   "steps": ["Whisk the eggs with salt and pepper.", "..."],
   "tip": "Cook a pot of lentils on Sunday and use it all week."}
]}"""


def _menu(stubs: list[dict]) -> str:
    return "\n".join(f"- {r.get('id')}: {r.get('name')} ({r.get('for', 'any meal')})" for r in stubs)


def _draft_chunked(profile: Profile, t: Targets, r: Route) -> LLMResult:
    """One outline call, then day groups and recipe batches in parallel. Same Plan shape as the single call."""
    ctx = build_context(profile, t)
    home, _ = _cuisines(profile)
    outline = chat_json(
        SYSTEM_PROMPT,
        f"""{ctx}

STEP 1 of 2: write the week_menu (the dish for every meal slot of all 7 days, following the VARIETY rule), the recipe
list behind it (at most {MAX_UNIQUE_RECIPES}; trivial items like tea, fruit, yogurt or boiled eggs need no recipe), the
weekly shopping list (only items NOT in the pantry) and a few tips. Portions and nutrition come in step 2.
Return JSON exactly in this shape:
{OUTLINE_SHAPE}""",
        route=r,
        max_tokens=2500,
    )
    # Keep the rest of the job on the model that answered the outline.
    same = Route(r.task, [outline.model], r.reason)
    stubs = [s for s in outline.data.get("recipes", []) if isinstance(s, dict) and s.get("id")][:MAX_UNIQUE_RECIPES]
    menu = _menu(stubs)
    week_menu = outline.data.get("week_menu") if isinstance(outline.data.get("week_menu"), dict) else {}

    def assigned(days: list[str]) -> str:
        # Parallel day calls can't see each other, so the outline's menu is what keeps the week varied.
        lines = []
        for d in days:
            slots = week_menu.get(d)
            if isinstance(slots, dict) and slots:
                lines.append(f"- {d}: " + "; ".join(f"{k}: {v}" for k, v in slots.items()))
        return "\n".join(lines)

    def plan_days(days: list[str]) -> list[dict]:
        res = chat_json(
            SYSTEM_PROMPT,
            f"""{ctx}

THE WEEK'S RECIPES (use these recipe_id values; trivial items get recipe_id null)
{menu}

Plan ONLY these days: {', '.join(days)}.
{('Use exactly these dishes (from the week menu):' + chr(10) + assigned(days)) if assigned(days) else 'Follow the VARIETY rule; vary every meal between days.'}
Aim for about {t.target_kcal} kcal per day and put the sum in day_total_kcal. Don't deliberate over exact numbers:
our code re-checks every total and fine-tunes portions afterwards.
Return JSON exactly in this shape:
{DAYS_SHAPE}""",
            route=same,
            max_tokens=1500 * len(days),
        )
        return [d for d in res.data.get("days", []) if isinstance(d, dict) and d.get("day") in days]

    def write_recipes(batch: list[dict]) -> list[dict]:
        res = chat_json(
            SYSTEM_PROMPT,
            f"""Write full home recipes for these dishes, keeping each id exactly:
{_menu(batch)}

DIET RULES (absolute)
{_diet_rules(profile)}

KITCHEN
{_kitchen(profile, home.currency)}

Mark in_pantry true only for ingredients in the pantry list. Steps must be short and doable with the equipment above.
Return JSON exactly in this shape:
{RECIPES_SHAPE}""",
            route=same,
            max_tokens=1200 * len(batch),
        )
        out = [x for x in res.data.get("recipes", []) if isinstance(x, dict)]
        # Keep ids aligned with the outline even if the model renamed them.
        for stub, rec in zip(batch, out):
            if rec.get("id") not in {s["id"] for s in batch}:
                rec["id"] = stub["id"]
        return out

    batches = [stubs[i : i + RECIPES_PER_CALL] for i in range(0, len(stubs), RECIPES_PER_CALL)]
    with ThreadPoolExecutor(max_workers=len(DAY_GROUPS) + len(batches)) as pool:
        day_jobs = [pool.submit(plan_days, g) for g in DAY_GROUPS]
        recipe_jobs = [pool.submit(write_recipes, b) for b in batches]
        days = [d for job in day_jobs for d in job.result()]
        recipes: list[dict] = []
        missing_recipes = False
        for batch, job in zip(batches, recipe_jobs):
            try:
                recipes += job.result()
            except LLMError as e:
                # A plan without some recipe steps is still useful; a plan without days is not.
                log.warning("recipe batch failed: %s", e)
                recipes += [{"id": s["id"], "name": s.get("name", s["id"])} for s in batch]
                missing_recipes = True

    days.sort(key=lambda d: DAYS.index(d["day"]))
    data = {
        "summary": outline.data.get("summary", ""),
        "days": days,
        "recipes": recipes,
        "shopping_list": outline.data.get("shopping_list", []),
        "tips": outline.data.get("tips", []),
        "_missing_recipes": missing_recipes,
    }
    return LLMResult(data, outline.model, outline.reason)


VARIED_SHAPE = """{"days": [ ...same day shape as before, only the days asked for... ],
 "recipes": [ ...full recipes for any NEW dish, same shape as before, ids "v1", "v2"... ]}"""


def _vary(profile: Profile, t: Targets, plan: Plan, bad_days: list[str], overused: dict[str, int]) -> Plan:
    """Re-plan only the repetitive days, steering away from dishes the rest of the week already uses."""
    kept = [d for d in plan.days if d.day not in bad_days]
    used = sorted({variety.dish_key(m.dish) for d in kept for m in d.meals if not m.top_up})
    recipes = ", ".join(f"{r.id}={r.name}" for r in plan.recipes)
    res = chat_json(
        SYSTEM_PROMPT,
        f"""{build_context(profile, t)}

The week is too repetitive ({', '.join(f'{k} ×{v}' for k, v in overused.items())}).
Re-plan ONLY these days with fresh dishes: {', '.join(bad_days)}.
Do NOT use any of these dishes again: {', '.join(used) or 'none'}.
Every breakfast, lunch and dinner on these days must differ from each other and from that list; leftovers of the
previous day's dinner are allowed once. Existing recipes you may still use: {recipes or 'none'}.
Aim for about {t.target_kcal} kcal and {t.protein_g} g protein per day; put the sum in day_total_kcal.
Return JSON exactly in this shape (day shape as in this example):
{DAYS_SHAPE}
plus, for new dishes that need cooking:
{VARIED_SHAPE}""",
        route=route("plan"),
        max_tokens=1300 * len(bad_days) + 1500,
    )
    # Validate each returned day and recipe on its own: one malformed entry shouldn't discard the rest.
    new_days: dict[str, PlanDay] = {}
    for raw in res.data.get("days", []):
        if isinstance(raw, dict) and raw.get("day") in bad_days:
            try:
                day = PlanDay.model_validate(raw)
                if day.meals:
                    new_days[day.day] = day
            except ValidationError as e:
                log.warning("variety pass: dropped malformed %s (%d errors)", raw.get("day"), e.error_count())
    recipes = list(plan.recipes)
    known = {r.id for r in recipes}
    for raw in res.data.get("recipes", []):
        try:
            rec = Recipe.model_validate(raw)
            if rec.id not in known:
                recipes.append(rec)
                known.add(rec.id)
        except ValidationError:
            continue
    return plan.model_copy(update={"days": [new_days.get(d.day, d) for d in plan.days], "recipes": recipes})


def _validated(result: LLMResult) -> tuple[Plan, bool]:
    missing_recipes = bool(result.data.pop("_missing_recipes", False))
    try:
        plan = Plan.model_validate(result.data)
    except ValidationError as e:
        where = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()[:3])
        log.warning("%s returned an invalid plan (%s)", result.model.label, where)
        raise LLMError("The model returned a plan in an unexpected format. Please try again.", 502) from e
    if not plan.days:
        raise LLMError("The model returned an empty plan. Please try again.", 502)
    return plan, missing_recipes


def _draft(profile: Profile, t: Targets) -> tuple[Plan, bool, LLMResult]:
    """Walk the plan route: single call on fast hosts, chunked on slow ones. Capacity errors and invalid output
    both fall through to the next model."""
    r = route("plan")
    if not r.models:
        raise LLMError("No model is configured. Add an API key to .env (see .env.example).", 500)
    last: LLMError | None = None
    for spec in r.models:
        one = Route(r.task, [spec], r.reason)
        try:
            result = _draft_chunked(profile, t, one) if PROVIDERS[spec.provider].chunked else _draft_single(profile, t, one)
            plan, missing = _validated(result)
            return plan, missing, result
        except LLMError as e:
            if e.status not in (429, 502, 503):
                raise
            log.warning("plan with %s failed (%s); trying next model", spec.label, e)
            last = e
    raise last or LLMError("No model could plan right now.", 503)


# ---------- checks ----------

def check_days(plan: Plan, t: Targets, budget: float) -> list[DayCheck]:
    checks = []
    for d in plan.days:
        kcal = sum(m.kcal for m in d.meals)
        cost = sum(m.cost for m in d.meals)
        protein = sum(m.protein_g for m in d.meals)
        checks.append(
            DayCheck(
                day=d.day,
                kcal=round(kcal),
                protein_g=round(protein),
                cost=round(cost, 2),
                kcal_ok=abs(kcal - t.target_kcal) <= t.target_kcal * KCAL_TOLERANCE,
                protein_ok=protein >= t.protein_g * PROTEIN_MIN_SHARE,
                budget_ok=cost <= budget * 1.1,
            )
        )
    return checks


def recheck(req: CheckRequest) -> list[DayCheck]:
    return check_days(req.plan, req.targets, req.daily_budget)


def generate_plan(profile: Profile) -> PlanResponse:
    bg = profile.background
    with agent_span("planner", **{"plan.region": bg.region.key if bg.region else "none", "plan.diet": bg.diet_type,
                                  "plan.styles": ",".join(bg.diet_styles)}) as span:
        res = _generate_plan(profile)
        if span is not None:
            span.set_data("gen_ai.request.model", res.model)
            span.set_data("plan.route_reason", res.route_reason)
            span.set_data("plan.kcal_days_ok", sum(c.kcal_ok for c in res.checks))
            span.set_data("plan.protein_days_ok", sum(c.protein_ok for c in res.checks))
            span.set_data("plan.budget_days_ok", sum(c.budget_ok for c in res.checks))
            span.set_data("plan.distinct_dishes", variety.distinct_dishes(res.plan))
        return res


def _generate_plan(profile: Profile) -> PlanResponse:
    started = time.perf_counter()
    bg = profile.background
    targets = apply_styles(compute_targets(profile.basics), profile.basics, bg.diet_styles)
    warnings = list(targets.warnings)
    home, _ = _cuisines(profile)

    with step_span("plan.draft"):
        plan, missing_recipes, result = _draft(profile, targets)
    if missing_recipes:
        warnings.append("Some recipes came back without steps — tap 'Try another week' to regenerate.")

    # Variety is checked by code, like calories: only the repetitive days go back to the model.
    bad_days, overused = variety.check(plan)
    if bad_days:
        log.info("re-planning repetitive days %s (%s)", bad_days, overused)
        try:
            with step_span("plan.variety_pass", days=",".join(bad_days)):
                plan = _vary(profile, targets, plan, bad_days, overused)
        except (LLMError, ValidationError) as e:
            log.warning("variety pass failed: %s", e)
        still, _ = variety.check(plan)
        if still:
            warnings.append(f"A few meals repeat more than we'd like ({', '.join(still)}) — ask the assistant for a swap.")

    budget = profile.kitchen.daily_budget
    banned = kb.excluded_tags(bg.diet_type, bg.restrictions, bg.allergies)
    # Custom allergies (e.g. "kiwi") aren't tags, so the balancer avoids them by name.
    avoid = {a.lower() for a in bg.avoid_foods} | {a.lower() for a in bg.allergies if a not in kb.ALLERGIES}
    # Top-up costs are a share of the user's own daily budget, so they're always in the right currency.
    with step_span("plan.balance"):
        topped = [d.day for d in plan.days if balance_day(d, targets, banned, avoid, budget)]
    if topped:
        log.info("balancer adjusted %s", topped)
    checks = check_days(plan, targets, budget)

    still_off = [c.day for c in checks if not c.kcal_ok]
    if still_off:
        warnings.append(f"Calories on {', '.join(still_off)} are more than 10% off target; tweak portions there.")
    if any(not c.protein_ok for c in checks):
        warnings.append("Protein is below target on some days — an extra serving of yogurt, eggs, beans or tofu closes the gap.")
    if any(not c.budget_ok for c in checks):
        warnings.append("A few days run over your daily budget — swap meat or cheese for beans, lentils or eggs to save.")

    spec: ModelSpec = result.model
    return PlanResponse(
        targets=targets,
        plan=plan,
        checks=checks,
        warnings=warnings,
        currency_symbol=home.currency.symbol,
        currency_code=home.currency.code,
        model=spec.model,
        model_label=spec.label,
        provider=spec.provider,
        route_reason=result.reason,
        seconds=round(time.perf_counter() - started, 1),
    )
