import re
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

Sex = Literal["male", "female", "other"]
Activity = Literal["sedentary", "light", "moderate", "active", "very_active"]
Pace = Literal["gentle", "steady", "fast"]


# ---------- Step 1: body basics ----------

class Basics(BaseModel):
    sex: Sex
    age: int = Field(ge=18, le=80)
    height_cm: float = Field(ge=120, le=220)
    weight_kg: float = Field(ge=30, le=250)
    target_weight_kg: float = Field(ge=30, le=250)
    activity: Activity
    pace: Pace = "steady"


class Targets(BaseModel):
    bmi: float
    bmi_category: str
    target_bmi: float
    bmr: int
    tdee: int
    goal: Literal["lose", "gain", "maintain"]
    target_kcal: int
    weekly_change_kg: float
    weeks_to_goal: float | None
    planned_target_weight_kg: float
    protein_g: int
    carbs_g: int
    fat_g: int
    water_l: float
    warnings: list[str] = []


# ---------- Step 2: where you live & how you eat ----------

class RegionRef(BaseModel):
    key: str  # cuisine profile key in the knowledge base
    name: str  # cuisine name, e.g. "French"
    place: str  # what the user typed, tidied, e.g. "Lyon, France"
    country: str = ""
    currency_code: str = "USD"
    currency_symbol: str = "$"
    # Groceries per person per day in THIS place's currency: {"low", "typical", "high"}.
    budget: dict[str, float] = {}


class Background(BaseModel):
    location: str = ""
    region: RegionRef | None = None
    cultures: list[str] = []
    diet_type: str = "omnivore"
    diet_styles: list[str] = []
    restrictions: list[str] = []
    allergies: list[str] = []
    avoid_foods: list[str] = []


# ---------- Step 3: a typical day (natural language, parsed by the intake agent) ----------

class DayItem(BaseModel):
    name: str
    portion: str = ""
    kcal: float | None = None
    protein_g: float | None = None


class DayMeal(BaseModel):
    slot: str
    time: str = ""
    items: list[DayItem] = []


class TypicalDay(BaseModel):
    description: str = ""
    meals: list[DayMeal] = []
    eat_out_per_week: int = Field(default=0, ge=0, le=21)


# ---------- Step 4: kitchen & budget ----------

class Kitchen(BaseModel):
    equipment: list[str] = []
    pantry: list[str] = []
    daily_budget: float = Field(default=10, gt=0)
    budget_currency: str = ""  # currency the budget was set in; reset when the region's currency changes
    cook_minutes_per_day: int = Field(default=45, ge=5, le=300)
    skill: Literal["beginner", "comfortable", "expert"] = "comfortable"
    batch_cooking: bool = False


class Profile(BaseModel):
    basics: Basics
    background: Background
    typical_day: TypicalDay
    kitchen: Kitchen


# ---------- Plan output (validated from the model's JSON) ----------
# Models slip in small ways ("350 kcal", "₹40", recipe_id 3, null lists); coerce instead of discarding a whole plan.


def _number(v):
    if isinstance(v, str):
        m = re.search(r"-?\d+(?:[.,]\d+)?", v.replace(",", ""))
        return float(m.group().replace(",", ".")) if m else 0
    return 0 if v is None else v


def _opt_str(v):
    return None if v in (None, "", "null") else str(v)


def _str(v):
    return "" if v is None else str(v)


def _list(v):
    return [] if v is None else v


Num = Annotated[float, BeforeValidator(_number)]
Int = Annotated[int, BeforeValidator(lambda v: int(_number(v)))]
OptStr = Annotated[str | None, BeforeValidator(_opt_str)]
Str = Annotated[str, BeforeValidator(_str)]

class PlannedMeal(BaseModel):
    slot: Str
    time: Str = ""
    dish: Str
    recipe_id: OptStr = None
    portion: Str = ""
    kcal: Num = 0
    protein_g: Num = 0
    carbs_g: Num = 0
    fat_g: Num = 0
    cost: Num = 0  # local currency
    top_up: bool = False  # added by the deterministic balancer, not the model


class PlanDay(BaseModel):
    day: str
    meals: Annotated[list[PlannedMeal], BeforeValidator(_list)]
    day_total_kcal: Annotated[float | None, BeforeValidator(lambda v: None if v is None else _number(v))] = None  # the model's own sum; we re-add it ourselves


class Ingredient(BaseModel):
    item: Str
    qty: Str = ""
    in_pantry: bool = False


class Recipe(BaseModel):
    id: Str
    name: Str
    servings: Int = 1
    time_min: Int = 0
    equipment: Annotated[list[str], BeforeValidator(_list)] = []
    ingredients: Annotated[list[Ingredient], BeforeValidator(_list)] = []
    steps: Annotated[list[str], BeforeValidator(_list)] = []
    tip: Str = ""


class ShoppingItem(BaseModel):
    item: Str
    qty: Str = ""
    est_cost: Num = 0
    category: Str = "Other"


class Plan(BaseModel):
    summary: Str = ""
    days: list[PlanDay]
    recipes: Annotated[list[Recipe], BeforeValidator(_list)] = []
    shopping_list: Annotated[list[ShoppingItem], BeforeValidator(_list)] = []
    tips: Annotated[list[str], BeforeValidator(_list)] = []


class DayCheck(BaseModel):
    day: str
    kcal: int
    protein_g: int
    cost: float
    kcal_ok: bool
    protein_ok: bool
    budget_ok: bool


class PlanResponse(BaseModel):
    targets: Targets
    plan: Plan
    checks: list[DayCheck]
    warnings: list[str] = []
    currency_symbol: str
    currency_code: str
    model: str
    model_label: str
    provider: str
    route_reason: str
    seconds: float


class CheckRequest(BaseModel):
    plan: Plan
    targets: Targets
    daily_budget: float
