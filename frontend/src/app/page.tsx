"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { STEPS, stepBlocker } from "@/lib/form";
import { usePlan } from "@/lib/store";

const FEATURES = [
  {
    icon: "🌍",
    title: "Your food, wherever you are",
    body: "Type any city — London, Mumbai, Mexico City, Tokyo. We plan with what people there actually cook and buy, priced in your currency.",
  },
  {
    icon: "💬",
    title: "Just describe your day",
    body: "No dropdowns of foods you don't eat. Write your usual day and your pantry in plain words; AI agents turn them into numbers and ask what's missing.",
  },
  {
    icon: "✅",
    title: "Checked by code, not vibes",
    body: "Calorie targets come from standard formulas. Every day is re-added and topped up by code, so the AI's arithmetic never sets your diet.",
  },
];

export default function Home() {
  const { hydrated, profile, result, generating, reset } = usePlan();
  const router = useRouter();
  const started = Boolean(profile.background.region || profile.typical_day.meals.length || result);
  const nextStep = STEPS.find((s) => stepBlocker(s.slug, profile)) ?? STEPS[STEPS.length - 1];

  return (
    <main className="mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-6 sm:pt-16">
      <section className="max-w-3xl">
        <p className="text-sm font-semibold text-accent">Open-weight AI · no sign-up · answers stay in your browser</p>
        <h1 className="mt-3 font-display text-4xl font-semibold leading-tight sm:text-6xl">A week of meals that fits your kitchen, your wallet and your culture.</h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-muted">
          Most diet apps hand everyone the same chicken-and-broccoli plan. meal-planner starts from what you already eat, where you live and what&apos;s in
          your cupboard — then gets you to your target weight with food you&apos;d actually cook.
        </p>

        <div className="mt-8 flex flex-wrap gap-3">
          {hydrated && started ? (
            <>
              {(result || generating) && (
                <Link href="/plan/result" className="rounded-full bg-leaf px-6 py-3 font-semibold text-white shadow-sm transition hover:brightness-110">
                  {generating ? "🍳 See my plan cooking" : "🍽️ View my plan"}
                </Link>
              )}
              <Link
                href={`/plan/${nextStep.slug}`}
                className="rounded-full bg-accent px-6 py-3 font-semibold text-accent-ink shadow-sm transition hover:brightness-105"
              >
                Continue where I left off →
              </Link>
              <button
                type="button"
                onClick={() => {
                  reset();
                  router.push("/plan/basics");
                }}
                className="rounded-full border border-line bg-surface px-6 py-3 font-semibold transition hover:border-accent"
              >
                Start a new plan
              </button>
            </>
          ) : (
            <Link href="/plan/basics" className="rounded-full bg-accent px-7 py-3.5 text-lg font-semibold text-accent-ink shadow-sm transition hover:brightness-105">
              Build my week →
            </Link>
          )}
        </div>
      </section>

      <section className="mt-16 grid gap-4 md:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title} className="rounded-2xl border border-line bg-surface p-5">
            <span className="text-3xl">{f.icon}</span>
            <h2 className="mt-3 font-semibold">{f.title}</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.body}</p>
          </div>
        ))}
      </section>

      <section className="mt-10 rounded-2xl border border-dashed border-line p-5 text-sm text-muted">
        <p>
          <b className="text-ink">How it works:</b> 4 short steps (about 3 minutes) → a 7-day plan with recipes, a shopping list of only what you&apos;re
          missing, and a food assistant you can ask for swaps. Models: gpt-oss-120b and Qwen on Groq, Gemma 4 on Google AI Studio — all
          open-weight, picked automatically per task.
        </p>
        <p className="mt-2">General guidance, not medical advice.</p>
      </section>
    </main>
  );
}
