import "server-only";

import { Agent } from "@mastra/core/agent";
import { z } from "zod";
import { modelChain, type RouteDecision } from "../models";

export const PANTRY_CATEGORIES = [
  "Grains & bread",
  "Pulses & beans",
  "Dairy & eggs",
  "Meat & fish",
  "Vegetables",
  "Fruit",
  "Spices & herbs",
  "Oils, sauces & condiments",
  "Nuts & seeds",
  "Drinks",
  "Other",
] as const;

export const EQUIPMENT_KEYS = [
  "stove",
  "induction",
  "oven",
  "microwave",
  "air_fryer",
  "pressure_cooker",
  "slow_cooker",
  "rice_cooker",
  "blender",
  "toaster",
  "grill",
  "kettle",
  "refrigerator",
  "freezer",
] as const;

export const pantrySchema = z.object({
  items: z
    .array(z.object({ name: z.string().describe("Ingredient in English, singular, e.g. 'Basmati rice'"), category: z.enum(PANTRY_CATEGORIES) }))
    .describe("Every ingredient they said they usually have"),
  equipment: z.array(z.enum(EQUIPMENT_KEYS)).describe("Kitchen equipment they mentioned, if any"),
  suggestions: z
    .array(z.string())
    .max(6)
    .describe("Up to 6 everyday basics common in their region that they did not mention and their diet allows"),
});

export type PantryOutput = z.infer<typeof pantrySchema>;

export const pantryAgent = new Agent({
  id: "pantry-agent",
  name: "Pantry agent",
  description: "Turns a free-text description of a kitchen cupboard into a categorised pantry list.",
  instructions: `You turn a free-text description of what someone usually keeps in their kitchen (any language) into a clean pantry list.
- Go through their text item by item: every ingredient they name becomes exactly one item (fats and oils like ghee or olive oil too).
- Never add an ingredient they did not write. Translate to English and keep common local names in brackets, e.g. "Turmeric (haldi)".
- equipment: only appliances named in THEIR TEXT (e.g. "pressure cooker", "microwave"). Ingredients never go in equipment.
- Suggestions are basics that are common in their region's kitchens, that they did not mention and their diet allows (e.g. salt, cooking oil, onions). Never suggest anything their diet or allergies forbid.`,
  model: ({ requestContext }) => modelChain(requestContext.get("route") as RouteDecision),
});
