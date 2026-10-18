import pytest

from app.nutrition import apply_styles, bmi_category, compute_targets
from app.schemas import Basics


def basics(**kw) -> Basics:
    base = dict(sex="male", age=30, height_cm=175, weight_kg=80, target_weight_kg=72, activity="light", pace="steady")
    return Basics(**{**base, **kw})


def test_mifflin_st_jeor_bmr():
    # 10*80 + 6.25*175 - 5*30 + 5 = 1748.75
    assert compute_targets(basics()).bmr == 1749
    # female offset is -161: 10*60 + 6.25*165 - 5*25 - 161 = 1345.25
    assert compute_targets(basics(sex="female", weight_kg=60, height_cm=165, age=25, target_weight_kg=55)).bmr == 1345


def test_deficit_matches_pace():
    t = compute_targets(basics(pace="steady"))
    # 0.5 kg/week ≈ 550 kcal/day below maintenance
    assert t.goal == "lose"
    assert abs((t.tdee - t.target_kcal) - 550) <= 10
    assert t.weeks_to_goal == pytest.approx(16, abs=0.1)


@pytest.mark.parametrize("sex,floor", [("female", 1200), ("male", 1500), ("other", 1350)])
def test_calorie_floor_is_never_crossed(sex, floor):
    t = compute_targets(basics(sex=sex, weight_kg=50, height_cm=150, age=60, target_weight_kg=45, activity="sedentary", pace="fast"))
    assert t.target_kcal >= floor


def test_target_below_healthy_bmi_is_raised():
    t = compute_targets(basics(height_cm=180, weight_kg=70, target_weight_kg=50))
    assert t.planned_target_weight_kg == pytest.approx(18.5 * 1.8**2, abs=0.1)
    assert any("healthy BMI" in w for w in t.warnings)


def test_weight_loss_capped_at_one_percent_per_week():
    t = compute_targets(basics(weight_kg=55, height_cm=170, target_weight_kg=50, pace="fast"))
    assert t.weekly_change_kg <= 0.55


@pytest.mark.parametrize("bmi,label", [(17, "Underweight"), (22, "Healthy"), (27, "Overweight"), (31, "Obese")])
def test_who_bmi_categories(bmi, label):
    assert bmi_category(bmi) == label


def test_styles_reshape_macros_not_calories():
    b = basics()
    t = compute_targets(b)
    keto = apply_styles(t, b, ["keto"])
    assert keto.target_kcal == t.target_kcal
    assert keto.carbs_g == 30 and keto.fat_g > t.fat_g
    hp = apply_styles(t, b, ["high_protein"])
    assert hp.protein_g >= t.protein_g
    assert hp.protein_g * 4 <= hp.target_kcal * 0.30 + 4  # capped at 30% of calories
