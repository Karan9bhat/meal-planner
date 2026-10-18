"""Deterministic nutrition math. The LLM never decides calorie targets — this module does.

Formulas: Mifflin-St Jeor BMR, standard activity multipliers, ~7700 kcal per kg of body weight.
Safety rails: calorie floors, a max loss rate of 1% body weight / week, and no targets below BMI 18.5.
"""

from .schemas import Basics, Targets

ACTIVITY_FACTOR = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}
PACE_KG_PER_WEEK = {"gentle": 0.25, "steady": 0.5, "fast": 0.75}
MAX_GAIN_KG_PER_WEEK = 0.5
KCAL_PER_KG = 7700
SEX_OFFSET = {"male": 5, "female": -161, "other": -78}
KCAL_FLOOR = {"male": 1500, "female": 1200, "other": 1350}
MIN_HEALTHY_BMI = 18.5
MAINTAIN_BAND_KG = 1.0


def bmi_category(bmi: float) -> str:
    # WHO adult categories.
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Healthy"
    if bmi < 30:
        return "Overweight"
    return "Obese"


def apply_styles(t: Targets, b: Basics, styles: list[str]) -> Targets:
    """Reshape macros (not calories) for diet styles chosen in step 2."""
    t = t.model_copy()
    kcal = t.target_kcal
    if "high_protein" in styles:
        ref_w = min(b.weight_kg, 25 * (b.height_cm / 100) ** 2)
        # 1.8 g/kg, but never more than 30% of calories: beyond that a low-calorie plan can't hit it.
        t.protein_g = max(t.protein_g, round(min(ref_w * 1.8, kcal * 0.30 / 4)))
    if "keto" in styles:
        t.carbs_g = 30
    elif "low_carb" in styles:
        t.carbs_g = min(t.carbs_g, 100)
    else:
        t.carbs_g = max(0, round((kcal - t.protein_g * 4 - t.fat_g * 9) / 4))
        return t
    # Low-carb styles: whatever carbs give up goes to fat.
    t.fat_g = max(0, round((kcal - t.protein_g * 4 - t.carbs_g * 4) / 9))
    return t


def compute_targets(b: Basics) -> Targets:
    h_m = b.height_cm / 100
    bmi = b.weight_kg / h_m**2
    bmr = 10 * b.weight_kg + 6.25 * b.height_cm - 5 * b.age + SEX_OFFSET[b.sex]
    tdee = bmr * ACTIVITY_FACTOR[b.activity]
    warnings: list[str] = []

    target_w = b.target_weight_kg
    min_w = MIN_HEALTHY_BMI * h_m**2
    if target_w < min_w:
        target_w = round(min_w, 1)
        warnings.append(
            f"Your target is below a healthy BMI (18.5) for your height, so we're planning toward {target_w} kg instead."
        )

    diff = target_w - b.weight_kg
    if abs(diff) < MAINTAIN_BAND_KG:
        goal, rate, kcal = "maintain", 0.0, tdee
    elif diff < 0:
        goal = "lose"
        rate = min(PACE_KG_PER_WEEK[b.pace], 0.01 * b.weight_kg)
        kcal = tdee - rate * KCAL_PER_KG / 7
        floor = KCAL_FLOOR[b.sex]
        if kcal < floor:
            kcal = floor
            rate = max(0.0, (tdee - floor) * 7 / KCAL_PER_KG)
            if rate < 0.1:
                warnings.append(
                    "At your current activity level there's very little room to cut calories safely. "
                    "Adding activity is the main lever here — try a higher activity level."
                )
            else:
                warnings.append(
                    f"We kept you at a safe minimum of {floor} kcal/day, so expect about {rate:.2f} kg/week."
                )
    else:
        goal = "gain"
        rate = min(PACE_KG_PER_WEEK[b.pace], MAX_GAIN_KG_PER_WEEK)
        kcal = tdee + rate * KCAL_PER_KG / 7

    weeks = round(abs(diff) / rate, 1) if rate > 0 and goal != "maintain" else None

    # Protein on a "reference" weight so very high body weights don't produce absurd numbers.
    # 1.3 g/kg while changing weight (above ICMR's ~0.8 g/kg baseline) is reachable on Indian veg diets.
    ref_w = min(b.weight_kg, 25 * h_m**2)
    protein = ref_w * (1.0 if goal == "maintain" else 1.3)
    fat = kcal * 0.27 / 9
    carbs = max(0.0, (kcal - protein * 4 - fat * 9) / 4)

    if bmi >= 35 or b.age >= 65:
        warnings.append("Given your age/BMI, it's worth checking this plan with a doctor or dietitian.")

    return Targets(
        bmi=round(bmi, 1),
        bmi_category=bmi_category(bmi),
        target_bmi=round(target_w / h_m**2, 1),
        bmr=round(bmr),
        tdee=round(tdee),
        goal=goal,
        target_kcal=int(round(kcal / 10) * 10),
        weekly_change_kg=round(rate, 2),
        weeks_to_goal=weeks,
        planned_target_weight_kg=round(target_w, 1),
        protein_g=round(protein),
        carbs_g=round(carbs),
        fat_g=round(fat),
        water_l=round(b.weight_kg * 0.035, 1),
        warnings=warnings,
    )
