import "server-only";

import type { PlanResponse, Profile, Targets } from "@/lib/types";
import { BACKEND_URL } from "./models";

export interface KbDish {
  name: string;
  portion: string;
  kcal: number;
  protein_g: number;
  contains: string[];
  cuisine: string;
}

export interface KbLookup {
  dishes: KbDish[];
  pantry_basics?: string[];
  meal_times?: Record<string, string>;
}

export function regionKeys(profile: Profile): string[] {
  return profile.background.region ? [profile.background.region.key] : [];
}

/** Knowledge-base grounding from the FastAPI backend: nutrition for dishes named in text, or a search. */
export async function kbLookup(profile: Profile, text: string, mode: "mentioned" | "search" = "mentioned", limit = 20): Promise<KbLookup> {
  const bg = profile.background;
  try {
    const res = await fetch(`${BACKEND_URL}/api/kb/lookup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: text.slice(0, 4000),
        region_keys: regionKeys(profile),
        diet_type: bg.diet_type,
        restrictions: bg.restrictions,
        allergies: bg.allergies,
        mode,
        limit,
      }),
    });
    return res.ok ? ((await res.json()) as KbLookup) : { dishes: [] };
  } catch {
    return { dishes: [] }; // the agents still work without grounding, just less precisely
  }
}

export function kbLines(dishes: KbDish[]): string {
  return dishes.map((d) => `- ${d.name} | ${d.portion} | ${d.kcal} kcal | ${d.protein_g} g protein (${d.cuisine})`).join("\n") || "- (no matches)";
}

export function profileSummary(profile: Profile, targets?: Targets | null): string {
  const b = profile.basics;
  const bg = profile.background;
  const k = profile.kitchen;
  const cur = bg.region ? `${bg.region.currency_code} ${bg.region.currency_symbol}` : "";
  return [
    `- ${b.age}-year-old ${b.sex}, ${b.height_cm} cm, ${b.weight_kg} kg, target ${b.target_weight_kg} kg, ${b.activity.replace("_", " ")} activity`,
    targets ? `- Daily targets: ${targets.target_kcal} kcal, ${targets.protein_g} g protein, ${targets.carbs_g} g carbs, ${targets.fat_g} g fat` : "",
    `- Lives in: ${bg.region ? `${bg.region.place} (${bg.region.name} cuisine)` : bg.location || "unknown"}`,
    bg.cultures.length ? `- Food culture: ${bg.cultures.join(", ")}` : "",
    `- Diet: ${bg.diet_type}${bg.diet_styles.length ? `; styles: ${bg.diet_styles.join(", ")}` : ""}`,
    `- Restrictions: ${bg.restrictions.join(", ") || "none"}; allergies: ${bg.allergies.join(", ") || "none"}; avoids: ${bg.avoid_foods.join(", ") || "nothing"}`,
    `- Kitchen: ${k.equipment.join(", ") || "basic"}; budget ${cur}${k.daily_budget}/day (${bg.region?.currency_code ?? "local currency"}); ${k.cook_minutes_per_day} min cooking/day`,
  ]
    .filter(Boolean)
    .join("\n");
}

/** One line per day: compact enough to send on every chat turn without blowing free-tier token limits. */
export function planSummary(result: PlanResponse | null): string {
  if (!result) return "No plan generated yet.";
  const days = result.plan.days.map((d) => {
    const meals = d.meals
      .filter((m) => !m.top_up)
      .map((m) => `${m.slot}: ${m.dish} (${Math.round(m.kcal)} kcal, ${Math.round(m.protein_g)} g P)`)
      .join("; ");
    const c = result.checks.find((x) => x.day === d.day);
    return `- ${d.day} [${c?.kcal ?? "?"} kcal, ${c?.protein_g ?? "?"} g P, ${result.currency_code ?? ""} ${result.currency_symbol}${c?.cost ?? "?"}]: ${meals}`;
  });
  return [`Plan summary: ${result.plan.summary}`, ...days, `Recipes: ${result.plan.recipes.map((r) => r.name).join(", ")}`].join("\n");
}
