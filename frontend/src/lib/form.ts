import type { Profile } from "./types";

export const STEPS = [
  { slug: "basics", title: "Your body", blurb: "The basics we need to work out how much you should eat." },
  { slug: "food", title: "Your food", blurb: "Where you live and the food you grew up with shape what tastes like home." },
  { slug: "day", title: "Your day", blurb: "Describe a normal day of eating in your own words." },
  { slug: "kitchen", title: "Your kitchen", blurb: "What you can cook with, what's in the cupboard, and what you can spend." },
] as const;

export type StepSlug = (typeof STEPS)[number]["slug"];

export const DEFAULT_PROFILE: Profile = {
  basics: {
    sex: "female",
    age: 28,
    height_cm: 165,
    weight_kg: 70,
    target_weight_kg: 63,
    activity: "light",
    pace: "steady",
  },
  background: {
    location: "",
    region: null,
    cultures: [],
    diet_type: "omnivore",
    diet_styles: [],
    restrictions: [],
    allergies: [],
    avoid_foods: [],
  },
  typical_day: { description: "", meals: [], eat_out_per_week: 2 },
  kitchen: {
    equipment: ["stove", "refrigerator"],
    pantry: [],
    daily_budget: 10,
    cook_minutes_per_day: 45,
    skill: "comfortable",
    batch_cooking: false,
  },
};

export function cmToFtIn(cm: number) {
  const totalIn = cm / 2.54;
  const ft = Math.floor(totalIn / 12);
  const inch = Math.round(totalIn - ft * 12);
  return inch === 12 ? { ft: ft + 1, inch: 0 } : { ft, inch };
}

export function money(n: number, symbol: string) {
  const digits = Math.abs(n) >= 100 ? 0 : n % 1 === 0 ? 0 : 2;
  return `${symbol}${n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

/** First blocker for a step, or null when it can be left. */
export function stepBlocker(step: StepSlug, p: Profile): string | null {
  if (step === "food") {
    if (!p.background.region) return "Tell us where you live";
  }
  if (step === "day") {
    if (!p.typical_day.meals.length) return "Describe your day and press “Analyze”";
  }
  if (step === "kitchen") {
    if (!p.kitchen.equipment.some((e) => ["stove", "induction", "microwave", "rice_cooker", "oven"].includes(e)))
      return "Select at least one way to cook";
  }
  return null;
}
