from typing import Literal

from pydantic import BaseModel, Field

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
    cook_minutes_per_day: int = Field(default=45, ge=5, le=300)
    skill: Literal["beginner", "comfortable", "expert"] = "comfortable"
    batch_cooking: bool = False


class Profile(BaseModel):
    basics: Basics
    background: Background
    typical_day: TypicalDay
    kitchen: Kitchen


# ---------- Plan output (validated from the model's JSON) ----------

class PlannedMeal(BaseModel):
    slot: str
    time: str = ""
    dish: str
    recipe_id: str | None = None
    portion: str = ""
    kcal: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    cost: float = 0  # local currency
    top_up: bool = False  # added by the deterministic balancer, not the model


class PlanDay(BaseModel):
    day: str
    meals: list[PlannedMeal]
    day_total_kcal: float | None = None  # the model's own sum; we re-add it ourselves


class Ingredient(BaseModel):
    item: str
    qty: str = ""
    in_pantry: bool = False


class Recipe(BaseModel):
    id: str
    name: str
    servings: int = 1
    time_min: int = 0
    equipment: list[str] = []
    ingredients: list[Ingredient] = []
    steps: list[str] = []
    tip: str = ""


class ShoppingItem(BaseModel):
    item: str
    qty: str = ""
    est_cost: float = 0
    category: str = "Other"


class Plan(BaseModel):
    summary: str = ""
    days: list[PlanDay]
    recipes: list[Recipe] = []
    shopping_list: list[ShoppingItem] = []
    tips: list[str] = []


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
    model: str
    model_label: str
    provider: str
    route_reason: str
    seconds: float


class CheckRequest(BaseModel):
    plan: Plan
    targets: Targets
    daily_budget: float
