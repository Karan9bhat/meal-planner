import { RequestContext } from "@mastra/core/request-context";
import * as Sentry from "@sentry/node";
import type { DayMeal, IntakeResult, Profile } from "@/lib/types";
import { mastra } from "@/mastra";
import { intakeSchema } from "@/mastra/agents/intake";
import { kbLines, kbLookup, profileSummary } from "@/mastra/context";
import { route } from "@/mastra/models";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const { description, answers, profile } = (await req.json()) as { description?: string; answers?: string; profile: Profile };
  const text = (description ?? "").trim();
  if (text.length < 10) return Response.json({ error: "Tell us a bit more about what you eat in a day." }, { status: 400 });
  if (text.length > 4000) return Response.json({ error: "That's a lot! Please keep it under 4,000 characters." }, { status: 400 });

  const decision = route("intake", `${text} ${answers ?? ""}`);
  const requestContext = new RequestContext();
  requestContext.set("route", decision);

  // Knowledge-base grounding: nutrition for dishes the user named, plus their region's usual meal times.
  const kb = await kbLookup(profile, `${text} ${answers ?? ""}`, "mentioned", 25);
  const times = Object.entries(kb.meal_times ?? {})
    .map(([k, v]) => `${k.replace("_", " ")} ${v}`)
    .join(", ");

  const prompt = `USER
${profileSummary(profile)}
${times ? `- Usual local meal times: ${times}` : ""}

KNOWLEDGE BASE (prefer these values when an item matches)
${kbLines(kb.dishes)}

THEIR DESCRIPTION OF A NORMAL DAY
"""${text}"""
${answers?.trim() ? `\nTHEIR ANSWERS TO YOUR EARLIER QUESTIONS\n"""${answers.trim()}"""` : ""}`;

  try {
    const out = await mastra.getAgent("intake-agent").generate(prompt, {
      requestContext,
      structuredOutput: { schema: intakeSchema, jsonPromptInjection: "auto" },
      modelSettings: { temperature: 0.1 },
    });
    const parsed = out.object;
    const meals: DayMeal[] = parsed.meals.map((m) => ({
      slot: m.slot,
      time: m.time,
      items: m.items.map((i) => ({ name: i.name, portion: i.portion, kcal: Math.round(i.kcal), protein_g: Math.round(i.protein_g) })),
    }));
    // Totals are added up here, not trusted from the model.
    const items = meals.flatMap((m) => m.items);
    const body: IntakeResult = {
      meals,
      total_kcal: Math.round(items.reduce((s, i) => s + (i.kcal ?? 0), 0)),
      total_protein_g: Math.round(items.reduce((s, i) => s + (i.protein_g ?? 0), 0)),
      questions: parsed.questions,
      notes: parsed.notes,
      model: out.response?.modelId ?? decision.labels[0],
      route_reason: decision.reason,
    };
    return Response.json(body);
  } catch (e) {
    console.error("intake agent failed", e);
    Sentry.captureException(e, { tags: { agent: "intake" } });
    const detail = process.env.NODE_ENV === "development" ? String(e) : undefined;
    return Response.json({ error: "The assistant couldn't read that right now. Please try again in a moment.", detail }, { status: 502 });
  }
}
