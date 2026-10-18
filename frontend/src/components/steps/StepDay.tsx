"use client";

import { useState } from "react";
import { analyzeDay } from "@/lib/api";
import { usePlan } from "@/lib/store";
import type { DayItem, DayMeal, IntakeResult } from "@/lib/types";
import { Card, RangeField, Section, cx } from "../ui";

const PLACEHOLDER =
  "e.g. I wake up around 7 and have tea with milk and two sugars. Breakfast is usually two slices of toast with butter or a bowl of cornflakes. " +
  "Lunch at work is a sandwich or leftover rice and curry. Around 5 I snack on biscuits. Dinner at 8:30 is rice or two rotis with dal and a vegetable, sometimes chicken.";

export function StepDay() {
  const { profile, targets, setDay } = usePlan();
  const day = profile.typical_day;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Pick<IntakeResult, "questions" | "notes" | "model" | "route_reason"> | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const items = day.meals.flatMap((m) => m.items);
  const total = Math.round(items.reduce((s, i) => s + (i.kcal ?? 0), 0));
  const protein = Math.round(items.reduce((s, i) => s + (i.protein_g ?? 0), 0));

  async function analyze(withAnswers = false) {
    setBusy(true);
    setError(null);
    const answerText = withAnswers
      ? Object.entries(answers)
          .filter(([, a]) => a.trim())
          .map(([q, a]) => `Q: ${q}\nA: ${a}`)
          .join("\n")
      : undefined;
    try {
      const r = await analyzeDay({ description: day.description, answers: answerText, profile });
      setDay({ meals: r.meals });
      setResult({ questions: r.questions, notes: r.notes, model: r.model, route_reason: r.route_reason });
      setAnswers({});
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const updateMeal = (i: number, meal: DayMeal | null) =>
    setDay({ meals: meal ? day.meals.map((m, j) => (j === i ? meal : m)) : day.meals.filter((_, j) => j !== i) });

  return (
    <div className="space-y-6">
      <Card className="space-y-3">
        <Section
          title="What does a normal day of eating look like?"
          hint="Write it the way you'd tell a friend — times, drinks, snacks, rough amounts. Any language works."
        >
          <textarea
            value={day.description}
            onChange={(e) => setDay({ description: e.target.value })}
            rows={6}
            maxLength={4000}
            placeholder={PLACEHOLDER}
            aria-label="Describe a normal day of eating"
            className="w-full resize-y rounded-xl border border-line bg-surface-2 px-4 py-3 text-[15px] leading-relaxed outline-none transition placeholder:text-muted/80 focus:border-accent focus:bg-surface"
          />
        </Section>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-muted">{day.description.length}/4000</span>
          <button
            type="button"
            onClick={() => void analyze(false)}
            disabled={busy || day.description.trim().length < 10}
            className="rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-accent-ink transition hover:brightness-105 disabled:opacity-40"
          >
            {busy ? "Reading your day…" : day.meals.length ? "↻ Analyze again" : "✨ Analyze my day"}
          </button>
        </div>
        {error && <p className="rounded-lg bg-chili-soft px-3 py-2 text-sm text-chili">{error}</p>}
      </Card>

      {day.meals.length > 0 && (
        <Card className="animate-rise space-y-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">Your usual day, roughly</p>
              <p className="font-display text-3xl font-semibold tabular-nums">
                {total.toLocaleString()} <span className="text-base font-normal text-muted">kcal · {protein} g protein</span>
              </p>
            </div>
            {targets && (
              <p
                className={cx(
                  "rounded-full px-3 py-1 text-sm font-medium",
                  Math.abs(total - targets.target_kcal) < targets.target_kcal * 0.1 ? "bg-leaf-soft text-leaf" : "bg-accent-soft text-accent",
                )}
              >
                Target {targets.target_kcal.toLocaleString()} kcal ·{" "}
                {total > targets.target_kcal
                  ? `${(total - targets.target_kcal).toLocaleString()} over`
                  : `${(targets.target_kcal - total).toLocaleString()} under`}
              </p>
            )}
          </div>

          {result && result.notes.length > 0 && (
            <ul className="space-y-2">
              {result.notes.map((n) => (
                <li key={n} className="rounded-lg bg-accent-soft px-3 py-2 text-sm text-ink">
                  ⚠️ {n}
                </li>
              ))}
            </ul>
          )}

          <ol className="space-y-3">
            {day.meals.map((meal, i) => (
              <MealEditor key={`${meal.slot}-${i}`} meal={meal} onChange={(m) => updateMeal(i, m)} />
            ))}
          </ol>

          {result && result.questions.length > 0 && (
            <div className="space-y-3 rounded-xl border border-dashed border-accent/50 bg-accent-soft/40 p-4">
              <p className="text-sm font-semibold">A few quick questions to sharpen the numbers</p>
              {result.questions.map((q) => (
                <label key={q} className="block space-y-1">
                  <span className="text-sm">{q}</span>
                  <input
                    value={answers[q] ?? ""}
                    onChange={(e) => setAnswers((a) => ({ ...a, [q]: e.target.value }))}
                    className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
                  />
                </label>
              ))}
              <button
                type="button"
                disabled={busy || !Object.values(answers).some((a) => a.trim())}
                onClick={() => void analyze(true)}
                className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-bg transition disabled:opacity-40"
              >
                {busy ? "Updating…" : "Update with my answers"}
              </button>
            </div>
          )}

          {result && (
            <p className="text-[11px] text-muted">
              Read by {result.model} · routed: {result.route_reason}. Totals are added up by our code; edit anything that looks off.
            </p>
          )}
        </Card>
      )}

      <Card>
        <RangeField
          label="Meals eaten out or ordered in, per week"
          value={day.eat_out_per_week}
          min={0}
          max={14}
          onChange={(eat_out_per_week) => setDay({ eat_out_per_week })}
          display={day.eat_out_per_week === 0 ? "Never" : `${day.eat_out_per_week}×`}
          hint="We'll leave room for these and suggest lighter restaurant picks."
        />
      </Card>
    </div>
  );
}

function MealEditor({ meal, onChange }: { meal: DayMeal; onChange: (m: DayMeal | null) => void }) {
  const setItem = (i: number, item: DayItem | null) =>
    onChange({ ...meal, items: item ? meal.items.map((it, j) => (j === i ? item : it)) : meal.items.filter((_, j) => j !== i) });
  const kcal = Math.round(meal.items.reduce((s, i) => s + (i.kcal ?? 0), 0));

  return (
    <li className="rounded-xl border border-line">
      <div className="flex items-center gap-3 border-b border-line px-3 py-2">
        <input
          type="time"
          value={meal.time}
          onChange={(e) => onChange({ ...meal, time: e.target.value })}
          aria-label={`${meal.slot} time`}
          className="rounded-md border border-line bg-surface-2 px-1.5 py-0.5 text-sm tabular-nums"
        />
        <span className="font-semibold">{meal.slot}</span>
        <span className="ml-auto text-sm tabular-nums text-muted">{kcal} kcal</span>
        <button type="button" onClick={() => onChange(null)} aria-label={`Remove ${meal.slot}`} className="text-muted hover:text-chili">
          ×
        </button>
      </div>
      <ul className="divide-y divide-line">
        {meal.items.map((it, i) => (
          <li key={i} className="grid grid-cols-[1fr_auto] items-center gap-2 px-3 py-2 sm:grid-cols-[1fr_8rem_5rem_auto]">
            <span className="text-sm font-medium">{it.name}</span>
            <input
              value={it.portion}
              onChange={(e) => setItem(i, { ...it, portion: e.target.value })}
              aria-label={`${it.name} portion`}
              className="hidden rounded-md border border-line bg-surface-2 px-2 py-1 text-xs sm:block"
            />
            <label className="flex items-center gap-1 text-xs text-muted">
              <input
                type="number"
                min={0}
                value={it.kcal ?? ""}
                onChange={(e) => setItem(i, { ...it, kcal: e.target.value === "" ? null : Number(e.target.value) })}
                aria-label={`${it.name} calories`}
                className="w-16 rounded-md border border-line bg-surface-2 px-2 py-1 text-right text-xs tabular-nums text-ink"
              />
              kcal
            </label>
            <button type="button" onClick={() => setItem(i, null)} aria-label={`Remove ${it.name}`} className="justify-self-end text-muted hover:text-chili">
              ×
            </button>
          </li>
        ))}
      </ul>
    </li>
  );
}
