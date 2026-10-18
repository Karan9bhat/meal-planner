import "server-only";

import { Agent } from "@mastra/core/agent";
import type { RequestContext } from "@mastra/core/request-context";
import { createTool } from "@mastra/core/tools";
import { z } from "zod";
import type { PlanResponse, Profile, Targets } from "@/lib/types";
import { kbLookup, planSummary, profileSummary } from "../context";
import { OFF_TOPIC_REPLY, TopicGuard } from "../guard";
import { modelChain, type RouteDecision } from "../models";

function ctx(rc: RequestContext | undefined) {
  return {
    profile: rc?.get("profile") as Profile,
    targets: (rc?.get("targets") as Targets | null) ?? null,
    result: (rc?.get("result") as PlanResponse | null) ?? null,
  };
}

const findDay = (result: PlanResponse | null, day: string) =>
  result?.plan.days.find((d) => d.day.toLowerCase().startsWith(day.toLowerCase().slice(0, 3)));

const searchFoods = createTool({
  id: "searchFoods",
  description: "Look up nutrition (kcal, protein per portion) for foods or dishes in the knowledge base, already filtered for the user's diet and allergies.",
  inputSchema: z.object({ query: z.string().describe("Food or dish, e.g. 'lentil soup' or 'paneer'") }),
  execute: async ({ query }, { requestContext }) => {
    const { profile } = ctx(requestContext);
    const { dishes } = await kbLookup(profile, query, "search", 6);
    return { dishes };
  },
});

const getDay = createTool({
  id: "getDay",
  description: "Get every meal of one day of the user's plan with portions, macros and cost, plus that day's totals versus targets.",
  inputSchema: z.object({ day: z.string().describe("Day name, e.g. 'Tuesday'") }),
  execute: async ({ day }, { requestContext }) => {
    const { result } = ctx(requestContext);
    const d = findDay(result, day);
    if (!result || !d) return { error: "No plan for that day yet." };
    const check = result.checks.find((c) => c.day === d.day);
    return { day: d.day, meals: d.meals, totals: check, targets: { kcal: result.targets.target_kcal, protein_g: result.targets.protein_g } };
  },
});

const proposeSwap = createTool({
  id: "proposeSwap",
  description:
    "Propose replacing one meal in the plan. This does NOT change the plan: the user sees the proposal and decides whether to apply it. Give honest macros for the new portion.",
  inputSchema: z.object({
    day: z.string(),
    slot: z.string().describe("Meal slot as named in the plan, e.g. 'Dinner'"),
    dish: z.string(),
    portion: z.string(),
    kcal: z.number(),
    protein_g: z.number(),
    carbs_g: z.number(),
    fat_g: z.number(),
    cost: z.number().describe("Estimated cost in the user's currency"),
    reason: z.string().describe("One short sentence on why this swap helps"),
  }),
  execute: async (swap, { requestContext }) => {
    const { result } = ctx(requestContext);
    const d = findDay(result, swap.day);
    if (!result || !d) return { ok: false, error: "That day isn't in the plan." };
    const old = d.meals.find((m) => !m.top_up && m.slot.toLowerCase() === swap.slot.toLowerCase());
    const before = Math.round(d.meals.reduce((s, m) => s + m.kcal, 0));
    const after = Math.round(before - (old?.kcal ?? 0) + swap.kcal);
    return {
      ok: true,
      swap: { ...swap, day: d.day, slot: old?.slot ?? swap.slot },
      replaces: old?.dish ?? null,
      day_kcal_before: before,
      day_kcal_after: after,
      target_kcal: result.targets.target_kcal,
    };
  },
});

export const chatAgent = new Agent({
  id: "chat-agent",
  name: "Meal planner assistant",
  description: "Answers food, diet and meal-plan questions for the user, and proposes meal swaps.",
  instructions: ({ requestContext }) => {
    const { profile, targets, result } = ctx(requestContext);
    return `You are the meal-planner assistant: a friendly, practical home-cooking and nutrition coach.

SCOPE: only food, cooking, recipes, groceries, nutrition, diets, weight goals and this user's meal plan.
For anything else reply exactly: "${OFF_TOPIC_REPLY}"
You are not a doctor: for medical conditions, medication or symptoms, give general food guidance and suggest a doctor or dietitian.

RULES
- Respect the user's diet type, restrictions and allergies absolutely, and their kitchen equipment and budget.
- Use searchFoods for nutrition numbers instead of guessing; use getDay before discussing a specific day in detail.
- To change a meal, call proposeSwap (it only proposes; the user clicks Apply). Keep swaps close to the old meal's calories unless asked otherwise.
- Be brief: a few sentences or a short "- " bullet list. No tables, no headings. Use the user's currency and local household portions.
- After proposeSwap, the app already shows the swap details as a card: reply with one or two sentences, don't repeat the numbers.

USER
${profile ? profileSummary(profile, targets) : "- (profile not filled in yet)"}

CURRENT PLAN
${planSummary(result)}`;
  },
  model: ({ requestContext }) => modelChain(requestContext.get("route") as RouteDecision),
  tools: { searchFoods, getDay, proposeSwap },
  inputProcessors: [new TopicGuard()],
});
