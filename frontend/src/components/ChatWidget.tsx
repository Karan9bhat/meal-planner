"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { useEffect, useMemo, useRef, useState } from "react";
import { money } from "@/lib/form";
import { usePlan } from "@/lib/store";
import type { MealSwap } from "@/lib/types";
import { cx } from "./ui";

type Part = UIMessage["parts"][number];

interface SwapOutput {
  ok: boolean;
  error?: string;
  swap?: MealSwap;
  replaces?: string | null;
  day_kcal_before?: number;
  day_kcal_after?: number;
  target_kcal?: number;
}

const TOOL_NOTES: Record<string, string> = {
  searchFoods: "🔎 looked up nutrition in the knowledge base",
  getDay: "📅 checked that day of your plan",
};

export function ChatWidget() {
  const store = usePlan();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  // The transport is created once; it reads the latest profile and plan from this ref on every send.
  const ctx = useRef({ profile: store.profile, targets: store.result?.targets ?? store.targets, result: store.result });
  ctx.current = { profile: store.profile, targets: store.result?.targets ?? store.targets, result: store.result };

  const transport = useMemo(
    () =>
      new DefaultChatTransport<UIMessage>({
        api: "/api/agent/chat",
        prepareSendMessagesRequest: ({ messages }) => ({ body: { messages, context: ctx.current } }),
      }),
    [],
  );
  const { messages, sendMessage, status, error } = useChat({ transport });
  const busy = status === "submitted" || status === "streaming";

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, open]);

  const suggestions = store.result
    ? ["Swap Wednesday's dinner for something cheaper", "I'm eating out tonight — what should I order?", "How do I meal-prep this week on Sunday?"]
    : ["How much protein should I eat a day?", "What's a cheap high-protein breakfast?", "Is skipping breakfast bad for weight loss?"];

  const send = (text: string) => {
    if (!text.trim() || busy) return;
    void sendMessage({ text: text.trim() });
    setInput("");
  };

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed bottom-24 right-4 z-40 flex items-center gap-2 rounded-full bg-ink px-4 py-3 text-sm font-semibold text-bg shadow-lg transition hover:scale-105 sm:bottom-6"
        >
          💬 Ask about food
          {store.generating && <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />}
        </button>
      )}

      {open && (
        <section
          aria-label="Meal planner assistant"
          className="animate-rise fixed inset-0 z-50 flex flex-col bg-surface shadow-2xl sm:inset-auto sm:bottom-6 sm:right-6 sm:h-[600px] sm:w-[400px] sm:rounded-2xl sm:border sm:border-line"
        >
          <header className="flex items-center gap-3 border-b border-line px-4 py-3">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-accent text-lg">🧑‍🍳</span>
            <div className="flex-1">
              <p className="font-semibold leading-tight">Food assistant</p>
              <p className="text-xs text-muted">
                {store.generating ? "Your plan is cooking — ask me anything meanwhile" : "Food, diet and your plan only"}
              </p>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close chat" className="grid h-8 w-8 place-items-center rounded-full hover:bg-surface-2">
              ×
            </button>
          </header>

          <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {messages.length === 0 && (
              <div className="space-y-3">
                <p className="text-sm text-muted">
                  Ask about swaps, recipes, groceries or your targets. I know your profile{store.result ? " and this week's plan" : ""}.
                </p>
                <div className="flex flex-col gap-2">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => send(s)}
                      className="rounded-xl border border-dashed border-line px-3 py-2 text-left text-sm hover:border-accent hover:bg-accent-soft"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m) => (
              <Message key={m.id} message={m} />
            ))}
            {status === "submitted" && <p className="animate-pulse text-sm text-muted">Thinking…</p>}
            {error && <p className="rounded-lg bg-chili-soft px-3 py-2 text-sm text-chili">The assistant is busy right now. Please try again.</p>}
          </div>

          <form
            className="flex gap-2 border-t border-line p-3"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. a vegetarian swap for Friday lunch"
              aria-label="Message"
              maxLength={1000}
              className="min-w-0 flex-1 rounded-full border border-line bg-surface-2 px-4 py-2 text-sm outline-none focus:border-accent"
            />
            <button type="submit" disabled={busy || !input.trim()} className="rounded-full bg-accent px-4 text-sm font-semibold text-accent-ink disabled:opacity-40">
              Send
            </button>
          </form>
        </section>
      )}
    </>
  );
}

function Message({ message }: { message: UIMessage }) {
  const mine = message.role === "user";
  const meta = message.metadata as { model?: string; route_reason?: string } | undefined;
  return (
    <div className={cx("flex flex-col gap-1.5", mine ? "items-end" : "items-start")}>
      {message.parts.map((part, i) => (
        <PartView key={i} part={part} mine={mine} />
      ))}
      {!mine && meta?.model && <p className="text-[10px] text-muted">via {meta.model}</p>}
    </div>
  );
}

function PartView({ part, mine }: { part: Part; mine: boolean }) {
  if (part.type === "text") {
    if (!part.text.trim()) return null;
    return (
      <div
        className={cx(
          "max-w-[88%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
          mine ? "rounded-br-sm bg-accent text-accent-ink" : "rounded-bl-sm bg-surface-2",
        )}
      >
        <RichText text={part.text} />
      </div>
    );
  }
  if (part.type === "data-tripwire") {
    const reason = (part.data as { reason?: string } | undefined)?.reason;
    return <div className="max-w-[88%] rounded-2xl rounded-bl-sm bg-accent-soft px-3.5 py-2 text-sm">{reason}</div>;
  }
  // Tool parts arrive as `tool-<name>` (or `dynamic-tool` with a toolName).
  const toolName =
    part.type === "dynamic-tool" ? (part as { toolName: string }).toolName : part.type.startsWith("tool-") ? part.type.slice(5) : null;
  if (!toolName) return null;
  const state = (part as { state?: string }).state;
  const output = (part as { output?: unknown }).output;
  if (toolName === "proposeSwap") {
    if (state !== "output-available") return <p className="text-xs text-muted">🔁 working out a swap…</p>;
    return <SwapCard output={output as SwapOutput} />;
  }
  return TOOL_NOTES[toolName] ? <p className="text-xs text-muted">{TOOL_NOTES[toolName]}</p> : null;
}

/** Just enough markdown for chat: **bold** and "- " bullets. */
function RichText({ text }: { text: string }) {
  const inline = (line: string) =>
    line.split(/(\*\*[^*]+\*\*)/g).map((seg, i) => (seg.startsWith("**") && seg.endsWith("**") ? <strong key={i}>{seg.slice(2, -2)}</strong> : seg));
  return (
    <>
      {text.split("\n").map((line, i) =>
        /^\s*[-*•]\s+/.test(line) ? (
          <span key={i} className="block pl-3 -indent-3">
            • {inline(line.replace(/^\s*[-*•]\s+/, ""))}
          </span>
        ) : (
          <span key={i} className="block min-h-[0.5em]">
            {inline(line)}
          </span>
        ),
      )}
    </>
  );
}

function SwapCard({ output }: { output: SwapOutput }) {
  const { applySwap, result } = usePlan();
  const [applied, setApplied] = useState(false);
  if (!output?.ok || !output.swap) return <p className="text-xs text-chili">{output?.error ?? "Couldn't propose that swap."}</p>;
  const s = output.swap;
  const cur = { code: result?.currency_code, symbol: result?.currency_symbol };
  return (
    <div className="w-[88%] rounded-2xl border border-leaf/40 bg-leaf-soft/50 p-3 text-sm">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-leaf">
        Proposed swap · {s.day} {s.slot}
      </p>
      {output.replaces && <p className="mt-1 text-muted line-through">{output.replaces}</p>}
      <p className="font-semibold">{s.dish}</p>
      <p className="text-muted">{s.portion}</p>
      <p className="mt-1 text-xs tabular-nums text-muted">
        {Math.round(s.kcal)} kcal · P {Math.round(s.protein_g)}g · {money(s.cost, cur)} · day total {output.day_kcal_before} → {output.day_kcal_after} kcal
        (target {output.target_kcal})
      </p>
      {s.reason && <p className="mt-1 text-xs">{s.reason}</p>}
      <button
        type="button"
        disabled={applied || !result}
        onClick={async () => {
          await applySwap(s);
          setApplied(true);
        }}
        className="mt-2 rounded-full bg-leaf px-3 py-1 text-xs font-semibold text-white disabled:opacity-60"
      >
        {applied ? "✓ Applied to your plan" : "Apply to my plan"}
      </button>
    </div>
  );
}
