"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PlanView } from "@/components/PlanView";
import { STEPS, stepBlocker } from "@/lib/form";
import { usePlan } from "@/lib/store";

const LOADING_LINES = [
  "Reading your usual day…",
  "Picking dishes from your region…",
  "Balancing protein, carbs and fat…",
  "Fitting it into your budget…",
  "Writing up recipes and a shopping list…",
  "Checking every day's numbers…",
];

export default function ResultPage() {
  const { hydrated, result, generating, generateError, generate, profile } = usePlan();
  const router = useRouter();

  if (!hydrated) return <div className="h-96 animate-pulse rounded-2xl bg-surface-2" />;
  if (generating) return <Generating />;

  if (!result) {
    const missing = STEPS.find((s) => stepBlocker(s.slug, profile));
    return (
      <div className="mx-auto max-w-xl py-16 text-center">
        {generateError ? (
          <>
            <p className="font-display text-2xl font-semibold">That didn&apos;t work this time</p>
            <p className="mt-2 rounded-xl bg-chili-soft px-4 py-3 text-sm text-chili">{generateError}</p>
            <button type="button" onClick={() => void generate()} className="mt-6 rounded-full bg-accent px-6 py-3 font-semibold text-accent-ink">
              ↻ Try again
            </button>
          </>
        ) : (
          <>
            <p className="font-display text-2xl font-semibold">No plan yet</p>
            <p className="mt-2 text-muted">Answer the four short steps and we&apos;ll build your week.</p>
            <Link href={`/plan/${missing?.slug ?? "basics"}`} className="mt-6 inline-block rounded-full bg-accent px-6 py-3 font-semibold text-accent-ink">
              {missing ? "Continue the questions →" : "Go to the last step →"}
            </Link>
          </>
        )}
      </div>
    );
  }

  return (
    <>
      {generateError && <p className="mb-4 rounded-xl bg-chili-soft px-4 py-3 text-sm text-chili">Couldn&apos;t build a new week: {generateError}</p>}
      <PlanView
        data={result}
        budget={profile.kitchen.daily_budget}
        onEdit={() => router.push("/plan/basics")}
        onRegenerate={() => void generate()}
        regenerating={generating}
      />
    </>
  );
}

function Generating() {
  const [i, setI] = useState(0);
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    const a = setInterval(() => setI((x) => (x + 1) % LOADING_LINES.length), 2200);
    const b = setInterval(() => setSecs((x) => x + 1), 1000);
    return () => {
      clearInterval(a);
      clearInterval(b);
    };
  }, []);
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <div className="relative h-24 w-24">
        <div className="absolute inset-0 animate-spin rounded-full border-4 border-line border-t-accent" />
        <span className="absolute inset-0 grid place-items-center text-4xl">🍲</span>
      </div>
      <p key={i} className="animate-rise mt-8 font-display text-2xl font-semibold">
        {LOADING_LINES[i]}
      </p>
      <p className="mt-2 text-sm text-muted">
        {secs}s · usually 10–30 seconds; longer if the fast models are busy and we fall back to Gemma
      </p>
      <p className="mt-6 text-sm text-muted">While you wait, try the 💬 food assistant in the corner.</p>
    </div>
  );
}
