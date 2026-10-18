// Mirrors backend/app/schemas.py and backend/app/kb.py

export type Sex = "male" | "female" | "other";
export type Activity = "sedentary" | "light" | "moderate" | "active" | "very_active";
export type Pace = "gentle" | "steady" | "fast";

export interface Basics {
  sex: Sex;
  age: number;
  height_cm: number;
  weight_kg: number;
  target_weight_kg: number;
  activity: Activity;
  pace: Pace;
}

export interface RegionRef {
  key: string;
  name: string;
  place: string;
  country: string;
  currency_code: string;
  currency_symbol: string;
}

export interface RegionResolution {
  region: RegionRef;
  status: "ready" | "generating" | "failed";
  source: string;
  staples: string[];
  meal_times: Record<string, string>;
  budget: { low?: number; typical?: number; high?: number };
  route_reason: string;
}

export interface Background {
  location: string;
  region: RegionRef | null;
  cultures: string[];
  diet_type: string;
  diet_styles: string[];
  restrictions: string[];
  allergies: string[];
  avoid_foods: string[];
}

export interface DayItem {
  name: string;
  portion: string;
  kcal: number | null;
  protein_g: number | null;
}

export interface DayMeal {
  slot: string;
  time: string;
  items: DayItem[];
}

export interface TypicalDay {
  description: string;
  meals: DayMeal[];
  eat_out_per_week: number;
}

export interface Kitchen {
  equipment: string[];
  pantry: string[];
  daily_budget: number;
  cook_minutes_per_day: number;
  skill: "beginner" | "comfortable" | "expert";
  batch_cooking: boolean;
}

export interface Profile {
  basics: Basics;
  background: Background;
  typical_day: TypicalDay;
  kitchen: Kitchen;
}

export interface Targets {
  bmi: number;
  bmi_category: string;
  target_bmi: number;
  bmr: number;
  tdee: number;
  goal: "lose" | "gain" | "maintain";
  target_kcal: number;
  weekly_change_kg: number;
  weeks_to_goal: number | null;
  planned_target_weight_kg: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  water_l: number;
  warnings: string[];
}

export interface Options {
  diet_types: Record<string, { label: string; desc: string; excludes: string[] }>;
  diet_styles: Record<string, string>;
  restrictions: Record<string, string>;
  allergies: Record<string, string>;
  equipment: Record<string, string>;
  cuisines: { key: string; name: string; region: string }[];
}

export interface PlannedMeal {
  slot: string;
  time: string;
  dish: string;
  recipe_id: string | null;
  portion: string;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  cost: number;
  top_up: boolean; // added by the backend's deterministic balancer
}

export interface Recipe {
  id: string;
  name: string;
  servings: number;
  time_min: number;
  equipment: string[];
  ingredients: { item: string; qty: string; in_pantry: boolean }[];
  steps: string[];
  tip: string;
}

export interface PlanDay {
  day: string;
  meals: PlannedMeal[];
  day_total_kcal?: number | null;
}

export interface Plan {
  summary: string;
  days: PlanDay[];
  recipes: Recipe[];
  shopping_list: { item: string; qty: string; est_cost: number; category: string }[];
  tips: string[];
}

export interface DayCheck {
  day: string;
  kcal: number;
  protein_g: number;
  cost: number;
  kcal_ok: boolean;
  protein_ok: boolean;
  budget_ok: boolean;
}

export interface PlanResponse {
  targets: Targets;
  plan: Plan;
  checks: DayCheck[];
  warnings: string[];
  currency_symbol: string;
  model: string;
  model_label: string;
  provider: string;
  route_reason: string;
  seconds: number;
}

// Agent results (Next.js route handlers backed by Mastra)

export interface AgentMeta {
  model: string;
  route_reason: string;
}

export interface IntakeResult extends AgentMeta {
  meals: DayMeal[];
  total_kcal: number;
  total_protein_g: number;
  questions: string[];
  notes: string[];
}

export interface PantryResult extends AgentMeta {
  items: { name: string; category: string }[];
  equipment: string[];
  suggestions: string[];
}

// Proposed by the chat agent's swapMeal tool; applied only when the user clicks Apply.
export interface MealSwap {
  day: string;
  slot: string;
  dish: string;
  portion: string;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  cost: number;
  reason: string;
}
