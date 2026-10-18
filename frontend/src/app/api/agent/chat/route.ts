import { handleChatStream } from "@mastra/ai-sdk";
import { RequestContext } from "@mastra/core/request-context";
import { createUIMessageStreamResponse, type UIMessage } from "ai";
import type { PlanResponse, Profile, Targets } from "@/lib/types";
import { mastra } from "@/mastra";
import { route } from "@/mastra/models";

export const runtime = "nodejs";

interface ChatBody {
  messages: UIMessage[];
  context: { profile: Profile; targets: Targets | null; result: PlanResponse | null };
}

export async function POST(req: Request) {
  const { messages, context } = (await req.json()) as ChatBody;
  const last = [...messages].reverse().find((m) => m.role === "user");
  const lastText = last?.parts.map((p) => (p.type === "text" ? p.text : "")).join(" ") ?? "";

  const decision = route("chat", lastText);
  const requestContext = new RequestContext();
  requestContext.set("route", decision);
  requestContext.set("profile", context.profile);
  requestContext.set("targets", context.targets);
  requestContext.set("result", context.result);

  const stream = await handleChatStream({
    mastra,
    agentId: "chat-agent",
    version: "v7",
    // Keep the last few turns: enough context, small enough for free-tier token limits.
    params: { messages: messages.slice(-12), requestContext, maxSteps: 5 },
    onError: () => "The assistant is busy right now. Please try again in a moment.",
    messageMetadata: ({ part }) => (part.type === "start" ? { model: decision.labels[0], route_reason: decision.reason } : undefined),
  });
  return createUIMessageStreamResponse({ stream });
}
