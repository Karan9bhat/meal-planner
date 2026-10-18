import "server-only";

import { Mastra } from "@mastra/core/mastra";
import type { AnyExportedSpan } from "@mastra/core/observability";
import { InMemoryStore } from "@mastra/core/storage";
import { Observability } from "@mastra/observability";
import { SentryExporter } from "@mastra/sentry";
import { chatAgent } from "./agents/chat";
import { intakeAgent } from "./agents/intake";
import { pantryAgent } from "./agents/pantry";

const REDACTED = "[redacted: user content stays in the browser]";

/** Keep the trace shape (agents, model calls, tools, timings, tokens) but never ship what users typed. */
function redact(span: AnyExportedSpan): AnyExportedSpan {
  return { ...span, input: span.input === undefined ? undefined : REDACTED, output: span.output === undefined ? undefined : REDACTED };
}

const dsn = process.env.SENTRY_DSN;

export const mastra = new Mastra({
  agents: { "intake-agent": intakeAgent, "pantry-agent": pantryAgent, "chat-agent": chatAgent },
  // Deliberately in-memory: agents are stateless per request and chat history lives in the user's browser,
  // so no user data is persisted server-side. (Declaring it also silences Mastra's fallback warning.)
  storage: new InMemoryStore({ id: "meal-planner" }),
  ...(dsn
    ? {
        // Agent runs -> model generations -> tool calls, with latency and token usage, in Sentry's AI monitoring.
        observability: new Observability({
          configs: {
            sentry: {
              serviceName: "meal-planner-agents",
              exporters: [
                new SentryExporter({
                  dsn,
                  environment: process.env.SENTRY_ENVIRONMENT ?? (process.env.NODE_ENV === "production" ? "production" : "development"),
                  tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE ?? 1),
                  customSpanFormatter: redact,
                }),
              ],
            },
          },
        }),
      }
    : {}),
});
