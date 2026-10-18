import "server-only";

import { Agent } from "@mastra/core/agent";
import { z } from "zod";
import { modelChain, type RouteDecision } from "../models";

export const intakeSchema = z.object({
  meals: z
    .array(
      z.object({
        slot: z.string().describe("Meal name in English, e.g. Breakfast, Lunch, Afternoon snack, Dinner"),
        time: z.string().describe("HH:MM; estimate from local habits if not stated"),
        items: z.array(
          z.object({
            name: z.string().describe("Food as the person called it, in English; keep dish names like 'Rogan josh'"),
            portion: z.string().describe("Concrete household portion, e.g. '2 rotis', '1 bowl', '1 slice'"),
            kcal: z.number().describe("Calories for that portion"),
            protein_g: z.number().describe("Protein grams for that portion"),
          }),
        ),
      }),
    )
    .describe("Every meal and drink they mentioned, in time order"),
  questions: z.array(z.string()).max(3).describe("Up to 3 short follow-up questions (one line each), only where the answer changes calories a lot"),
  notes: z
    .array(z.string())
    .max(3)
    .describe("Only real problems, one short sentence each: diet-rule conflicts, implausible amounts, skipped meals. Empty if none."),
});

export type IntakeOutput = z.infer<typeof intakeSchema>;

export const intakeAgent = new Agent({
  id: "intake-agent",
  name: "Typical-day intake agent",
  description: "Turns a free-text description of a normal day of eating into structured meals with calorie estimates.",
  instructions: `You read how someone describes a normal day of eating (in any language) and turn it into structured meals.
- List only foods and drinks they actually mentioned. Never invent meals; a skipped meal is a note, not a guess.
- Use the KNOWLEDGE BASE nutrition values when an item matches one; otherwise estimate from typical home portions where they live.
- When something is vague ("some rice", "tea"), assume the most common local portion and preparation (e.g. tea with milk and sugar in India, black coffee in Finland).
- Ask at most 3 short questions, only about things that change calories a lot (oil or ghee, sugar in drinks, number of rotis, portion of rice, alcohol). If the description is clear, ask nothing.
- In notes, flag only real problems in one short sentence each: conflicts with their diet rules or allergies (e.g. vegetarian but mentions chicken), implausible amounts, skipped meals. Never write a note saying something is fine.
- If previous answers are given, apply them and do not ask the same question again.
- Write everything in English.`,
  model: ({ requestContext }) => modelChain(requestContext.get("route") as RouteDecision),
});
