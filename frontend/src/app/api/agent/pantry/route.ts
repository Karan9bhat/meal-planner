import { RequestContext } from "@mastra/core/request-context";
import * as Sentry from "@sentry/node";
import type { PantryResult, Profile } from "@/lib/types";
import { mastra } from "@/mastra";
import { pantrySchema } from "@/mastra/agents/pantry";
import { kbLookup } from "@/mastra/context";
import { route } from "@/mastra/models";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const { text: raw, profile } = (await req.json()) as { text?: string; profile: Profile };
  const text = (raw ?? "").trim();
  if (text.length < 3) return Response.json({ error: "List a few things you usually have in your kitchen." }, { status: 400 });
  if (text.length > 3000) return Response.json({ error: "Please keep it under 3,000 characters." }, { status: 400 });

  const decision = route("pantry", text);
  const requestContext = new RequestContext();
  requestContext.set("route", decision);
  const kb = await kbLookup(profile, "", "mentioned", 1);

  const bg = profile.background;
  // Deliberately small context: no existing kitchen details for the model to copy from.
  const prompt = `USER
- Lives in: ${bg.region ? `${bg.region.place} (${bg.region.name} cuisine)` : bg.location || "unknown"}
- Diet: ${bg.diet_type}; allergies: ${bg.allergies.join(", ") || "none"}; avoids: ${bg.avoid_foods.join(", ") || "nothing"}
${kb.pantry_basics?.length ? `- Common pantry basics where they live (for suggestions only): ${kb.pantry_basics.join(", ")}` : ""}

WHAT THEY SAY IS USUALLY IN THEIR KITCHEN
"""${text}"""`;

  try {
    const out = await mastra.getAgent("pantry-agent").generate(prompt, {
      requestContext,
      structuredOutput: { schema: pantrySchema, jsonPromptInjection: "auto" },
      modelSettings: { temperature: 0 },
    });
    const parsed = out.object;
    const seen = new Set<string>();
    const items = parsed.items.filter((i) => {
      const k = i.name.trim().toLowerCase();
      if (!k || seen.has(k)) return false;
      seen.add(k);
      return true;
    });
    const body: PantryResult = {
      items,
      equipment: parsed.equipment,
      suggestions: parsed.suggestions.filter((s) => !seen.has(s.trim().toLowerCase())),
      model: out.response?.modelId ?? decision.labels[0],
      route_reason: decision.reason,
    };
    return Response.json(body);
  } catch (e) {
    console.error("pantry agent failed", e);
    Sentry.captureException(e, { tags: { agent: "pantry" } });
    const detail = process.env.NODE_ENV === "development" ? String(e) : undefined;
    return Response.json({ error: "The assistant couldn't read that right now. Please try again in a moment.", detail }, { status: 502 });
  }
}
