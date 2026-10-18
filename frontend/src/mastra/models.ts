import "server-only";

import { createGoogleGenerativeAI } from "@ai-sdk/google";
import { createGroq } from "@ai-sdk/groq";
import type { ModelWithRetries } from "@mastra/core/agent";
import type { LanguageModel } from "ai";

type ProviderOptions = Record<string, Record<string, string | number | boolean>>;

// Keys come from the project-root .env (loaded in next.config.ts); never from code.
const groqKey = process.env.GROQ_API_KEY ?? process.env.API_KEY;
const googleKey = process.env.GEMINI_API_KEY ?? process.env.GOOGLE_API_KEY ?? process.env.GEMMA_API_KEY;

const groq = createGroq({ apiKey: groqKey });
const google = createGoogleGenerativeAI({ apiKey: googleKey });

interface Spec {
  label: string;
  available: boolean;
  entry: () => ModelWithRetries;
}

// All open-weight models: gpt-oss and Qwen on Groq, Gemma 4 on Google AI Studio.
const MODELS = {
  "gpt-oss-120b": {
    label: "gpt-oss-120b",
    available: Boolean(groqKey),
    entry: () => ({
      model: groq("openai/gpt-oss-120b"),
      maxRetries: 1,
      providerOptions: { groq: { reasoningEffort: "low" } },
    }),
  },
  "qwen-27b": {
    label: "Qwen 3.8 27B",
    available: Boolean(groqKey),
    entry: () => ({
      model: groq("qwen/qwen3.8-27b"),
      maxRetries: 1,
      providerOptions: { groq: { reasoningEffort: "none" } },
    }),
  },
  "gpt-oss-safeguard-20b": {
    label: "gpt-oss-safeguard-20b",
    available: Boolean(groqKey),
    entry: () => ({
      model: groq("openai/gpt-oss-safeguard-20b"),
      maxRetries: 1,
      providerOptions: { groq: { reasoningEffort: "low" } },
    }),
  },
  "gemma-4-26b": {
    label: "Gemma 4 26B-A4B",
    available: Boolean(googleKey),
    entry: () => ({ model: google("gemma-4-26b-a4b-it"), maxRetries: 1 }),
  },
} satisfies Record<string, Spec>;

type ModelId = keyof typeof MODELS;
export type Task = "intake" | "pantry" | "chat" | "guard";

export interface RouteDecision {
  ids: ModelId[];
  labels: string[];
  reason: string;
}

const NON_LATIN = /[Ѐ-ӿ؀-ۿऀ-෿฀-๿぀-ヿ㐀-鿿가-힯]/;

/**
 * The user never picks a model: the router looks at the task and the input and orders a fallback chain.
 * Later entries take over on rate limits, overload or errors (Mastra handles the fallback).
 */
export function route(task: Task, input: string): RouteDecision {
  let ids: ModelId[];
  let reason: string;
  switch (task) {
    case "guard":
      ids = ["gpt-oss-safeguard-20b", "qwen-27b"];
      reason = "topic check → gpt-oss-safeguard (open policy-classification model)";
      break;
    case "chat":
      ids = ["gpt-oss-120b", "qwen-27b", "gemma-4-26b"];
      reason = "conversation with tool calls → gpt-oss-120b";
      break;
    default:
      ids = ["qwen-27b", "gpt-oss-120b", "gemma-4-26b"];
      reason = "short extraction → fast Qwen";
      if (input.length > 1200) {
        ids = ["gpt-oss-120b", "qwen-27b", "gemma-4-26b"];
        reason = "long, detailed description → larger gpt-oss-120b";
      }
  }
  if (task !== "guard" && NON_LATIN.test(input)) {
    ids = ["gemma-4-26b", ...ids.filter((i) => i !== "gemma-4-26b")];
    reason = "non-Latin script → Gemma 4 (trained on 140+ languages)";
  }
  ids = ids.filter((i) => MODELS[i].available);
  return { ids, labels: ids.map((i) => MODELS[i].label), reason };
}

export function modelChain(decision: RouteDecision): ModelWithRetries[] {
  if (!decision.ids.length) throw new Error("No model is configured. Add an API key to the project .env file.");
  return decision.ids.map((i) => MODELS[i].entry());
}

/** Plain AI SDK models for direct calls outside an agent (the topic guard). */
export function languageModels(decision: RouteDecision) {
  return decision.ids.map((i) => {
    const e: ModelWithRetries = MODELS[i].entry();
    return { label: MODELS[i].label, model: e.model as LanguageModel, providerOptions: e.providerOptions as ProviderOptions | undefined };
  });
}

export const BACKEND_URL = (process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
