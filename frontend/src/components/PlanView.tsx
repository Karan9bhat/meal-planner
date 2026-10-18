"use client";

import { useEffect, useMemo, useState } from "react";
import { money } from "@/lib/form";
import type { PlanResponse, Recipe } from "@/lib/types";
import { Card, cx } from "./ui";

export function PlanView({
  data,
  budget,
  onEdit,
  onRegenerate,
  regenerating,
}: {
  data: PlanResponse;
  budget: number;
  onEdit: () => void;
  onRegenerate: () => void;
  regenerating: boolean;
}) {
  const { plan, targets: t, checks } = data;
  const sym = data.currency_symbol;
  const [dayIdx, setDayIdx] = useState(0);
  const [openRecipe, setOpenRecipe] = useState<Recipe | null>(null);
  const recipes = useMemo(() => new Map(plan.recipes.map((r) => [r.id, r])), [plan.recipes]);
  const day = plan.days[Math.min(dayIdx, plan.days.length - 1)];
  const check = checks.find((c) => c.day === day?.day);
  const weekCost = checks.reduce((s, c) => s + c.cost, 0);
  const shopCost = plan.shopping_list.reduce((s, i) => s + i.est_cost, 0);

  return (
    <div className="animate-rise space-y-6">
      <Card className="space-y-4 bg-gradient-to-br from-accent-soft to-surface">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-wider text-accent">Your week is ready</p>
            <h2 className="mt-1 font-display text-3xl font-semibold">7 days, {plan.recipes.length} recipes, one shopping trip</h2>
            <p className="mt-2 leading-relaxed text-muted">{plan.summary}</p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={onEdit} className="rounded-full border border-line bg-surface px-4 py-2 text-sm font-medium hover:border-accent">
              ✏️ Edit answers
            </button>
            <button
              type="button"
              onClick={onRegenerate}
              disabled={regenerating}
              className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-accent-ink hover:brightness-105 disabled:opacity-50"
            >
              {regenerating ? "Planning…" : "↻ Try another week"}
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Pill label="Daily calories" value={`${t.target_kcal.toLocaleString()} kcal`} />
          <Pill label="Daily protein" value={`${t.protein_g} g`} />
          <Pill label="Food cost this week" value={money(weekCost, sym)} sub={`budget ${money(budget * 7, sym)}`} />
          <Pill
            label="Goal"
            value={t.goal === "maintain" ? "Maintain" : `${t.planned_target_weight_kg} kg`}
            sub={t.weeks_to_goal ? `${t.weekly_change_kg} kg/wk · ~${Math.ceil(t.weeks_to_goal)} wks` : undefined}
          />
        </div>
        {data.warnings.length > 0 && (
          <ul className="space-y-1.5">
            {data.warnings.map((w) => (
              <li key={w} className="rounded-lg bg-chili-soft px-3 py-2 text-sm text-chili">
                {w}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1" role="tablist">
        {plan.days.map((d, i) => {
          const c = checks.find((x) => x.day === d.day);
          const ok = c?.kcal_ok && c?.protein_ok && c?.budget_ok;
          return (
            <button
              key={d.day}
              role="tab"
              aria-selected={i === dayIdx}
              onClick={() => setDayIdx(i)}
              className={cx(
                "flex min-w-[5.5rem] flex-col items-center rounded-xl border-2 px-3 py-2 transition",
                i === dayIdx ? "border-accent bg-accent-soft" : "border-line bg-surface hover:border-accent/50",
              )}
            >
              <span className="text-sm font-semibold">{d.day.slice(0, 3)}</span>
              <span className="text-xs tabular-nums text-muted">{c?.kcal ?? "–"} kcal</span>
              <span className={cx("mt-1 h-1.5 w-1.5 rounded-full", ok ? "bg-leaf" : "bg-accent")} />
            </button>
          );
        })}
      </div>

      {day && (
        <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
          <Card className="space-y-1">
            <h3 className="mb-3 font-display text-2xl font-semibold">{day.day}</h3>
            <ol className="relative space-y-4 border-l-2 border-dashed border-line pl-6">
              {day.meals.map((m, i) => {
                const recipe = m.recipe_id ? recipes.get(m.recipe_id) : undefined;
                const removal = m.top_up && m.kcal < 0;
                return (
                  <li key={i} className="animate-rise relative" style={{ animationDelay: `${i * 40}ms` }}>
                    <span className="absolute -left-[33px] top-1 grid h-4 w-4 place-items-center rounded-full border-2 border-accent bg-surface" />
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted">
                      {m.time} · {m.slot}
                    </p>
                    <div
                      className={cx(
                        "mt-1 rounded-xl border p-3.5",
                        m.top_up ? "border-dashed border-leaf/50 bg-leaf-soft/50" : "border-line bg-surface-2/60",
                      )}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          {m.top_up && (
                            <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-wide text-leaf">
                              {removal ? "✓ Swapped out to make room for protein" : "✓ Added to hit your targets"}
                            </p>
                          )}
                          <p className="font-semibold">{m.dish.replace(/^(Top-up|Swap out):\s*/, removal ? "− " : m.top_up ? "+ " : "")}</p>
                          <p className="text-sm text-muted">{m.portion}</p>
                        </div>
                        <span className="text-sm font-medium tabular-nums">{money(m.cost, sym)}</span>
                      </div>
                      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-xs">
                        <Tag>{Math.round(m.kcal)} kcal</Tag>
                        <Tag className="bg-leaf-soft text-leaf">P {Math.round(m.protein_g)}g</Tag>
                        <Tag>C {Math.round(m.carbs_g)}g</Tag>
                        <Tag>F {Math.round(m.fat_g)}g</Tag>
                        {recipe && (
                          <button
                            type="button"
                            onClick={() => setOpenRecipe(recipe)}
                            className="ml-auto rounded-full bg-accent px-3 py-1 font-semibold text-accent-ink hover:brightness-105"
                          >
                            Recipe · {recipe.time_min} min →
                          </button>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          </Card>

          {check && (
            <Card className="space-y-4 lg:sticky lg:top-24 lg:self-start">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">{day.day} totals</p>
              <Meter label="Calories" value={check.kcal} target={t.target_kcal} fmt={(n) => `${n.toLocaleString()} kcal`} ok={check.kcal_ok} />
              <Meter label="Protein" value={check.protein_g} target={t.protein_g} fmt={(n) => `${n} g`} ok={check.protein_ok} />
              <Meter label="Cost" value={check.cost} target={budget} fmt={(n) => money(n, sym)} ok={check.budget_ok} />
              <p className="text-[11px] leading-relaxed text-muted">
                Totals are re-added by our code, not trusted from the AI. Where a day fell short, the code made small diet-safe adjustments
                (marked in green).
              </p>
            </Card>
          )}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <Card>
          <h3 className="mb-4 font-display text-2xl font-semibold">Recipes</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {plan.recipes.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setOpenRecipe(r)}
                className="rounded-xl border border-line p-4 text-left transition hover:border-accent hover:bg-accent-soft"
              >
                <p className="font-semibold">{r.name}</p>
                <p className="mt-1 text-xs text-muted">
                  ⏱ {r.time_min} min · serves {r.servings} · {r.ingredients.length} ingredients
                </p>
              </button>
            ))}
          </div>
        </Card>
        <ShoppingList items={plan.shopping_list} total={shopCost} sym={sym} />
      </div>

      {plan.tips.length > 0 && (
        <Card>
          <h3 className="mb-3 font-display text-2xl font-semibold">Tips for your week</h3>
          <ul className="grid gap-2 sm:grid-cols-2">
            {plan.tips.map((tip) => (
              <li key={tip} className="flex gap-2 rounded-xl bg-surface-2 p-3 text-sm leading-relaxed">
                <span>💡</span>
                {tip}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <p className="text-center text-xs text-muted">
        Planned by the open-weight model <b>{data.model_label}</b> <span className="font-mono">({data.model})</span> via {data.provider} in{" "}
        {data.seconds}s · routed: {data.route_reason}. Calorie targets come from standard formulas, not the AI. General guidance, not medical
        advice.
      </p>

      {openRecipe && <RecipeModal recipe={openRecipe} onClose={() => setOpenRecipe(null)} />}
    </div>
  );
}

function Pill({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-surface/80 px-3.5 py-2.5">
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="font-semibold tabular-nums">{value}</p>
      {sub && <p className="text-[11px] text-muted">{sub}</p>}
    </div>
  );
}

function Tag({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cx("rounded-full bg-surface px-2 py-0.5 tabular-nums text-muted", className)}>{children}</span>;
}

function Meter({ label, value, target, fmt, ok }: { label: string; value: number; target: number; fmt: (n: number) => string; ok: boolean }) {
  const pct = Math.min(130, (value / (target || 1)) * 100);
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="tabular-nums text-muted">
          <b className={ok ? "text-leaf" : "text-accent"}>{fmt(value)}</b> / {fmt(target)}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-surface-2">
        <div className={cx("h-full rounded-full transition-all", ok ? "bg-leaf" : "bg-accent")} style={{ width: `${(pct / 130) * 100}%` }} />
        <div className="absolute -top-0.5 h-3 w-0.5 bg-ink/60" style={{ left: `${(100 / 130) * 100}%` }} />
      </div>
    </div>
  );
}

function ShoppingList({ items, total, sym }: { items: PlanResponse["plan"]["shopping_list"]; total: number; sym: string }) {
  const [got, setGot] = useState<Set<string>>(new Set());
  const groups = useMemo(() => {
    const m = new Map<string, typeof items>();
    items.forEach((i) => m.set(i.category || "Other", [...(m.get(i.category || "Other") ?? []), i]));
    return [...m.entries()];
  }, [items]);

  return (
    <Card className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h3 className="font-display text-2xl font-semibold">Shopping list</h3>
        <span className="text-sm tabular-nums text-muted">≈ {money(total, sym)}</span>
      </div>
      {items.length === 0 && <p className="text-sm text-muted">Nothing to buy — your pantry has it all.</p>}
      {groups.map(([cat, list]) => (
        <div key={cat} className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">{cat}</p>
          {list.map((i) => {
            const done = got.has(i.item);
            return (
              <label key={i.item} className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-surface-2">
                <input
                  type="checkbox"
                  checked={done}
                  onChange={() =>
                    setGot((s) => {
                      const n = new Set(s);
                      if (n.has(i.item)) n.delete(i.item);
                      else n.add(i.item);
                      return n;
                    })
                  }
                  className="h-4 w-4 accent-[var(--leaf)]"
                />
                <span className={cx("flex-1 text-sm", done && "text-muted line-through")}>
                  {i.item} <span className="text-muted">· {i.qty}</span>
                </span>
                <span className="text-xs tabular-nums text-muted">{money(i.est_cost, sym)}</span>
              </label>
            );
          })}
        </div>
      ))}
    </Card>
  );
}

function RecipeModal({ recipe: r, onClose }: { recipe: Recipe; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-6" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={r.name}
        onClick={(e) => e.stopPropagation()}
        className="animate-rise max-h-[90vh] w-full max-w-2xl overflow-auto rounded-t-3xl bg-surface p-6 shadow-2xl sm:rounded-3xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="font-display text-3xl font-semibold">{r.name}</h3>
            <p className="mt-1 text-sm text-muted">
              ⏱ {r.time_min} min · serves {r.servings}
              {r.equipment.length > 0 && ` · ${r.equipment.map((e) => e.replace(/_/g, " ")).join(", ")}`}
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="grid h-9 w-9 place-items-center rounded-full bg-surface-2 text-lg hover:bg-line">
            ×
          </button>
        </div>
        {r.steps.length === 0 ? (
          <p className="mt-6 text-sm text-muted">This recipe&apos;s steps didn&apos;t come through. Ask the assistant for them, or try another week.</p>
        ) : (
          <div className="mt-6 grid gap-6 sm:grid-cols-[220px_1fr]">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Ingredients</p>
              <ul className="space-y-1.5 text-sm">
                {r.ingredients.map((ing) => (
                  <li key={ing.item} className="flex gap-2">
                    <span className={ing.in_pantry ? "text-leaf" : "text-accent"} title={ing.in_pantry ? "In your pantry" : "To buy"}>
                      {ing.in_pantry ? "●" : "○"}
                    </span>
                    <span>
                      {ing.item} <span className="text-muted">— {ing.qty}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Method</p>
              <ol className="space-y-3 text-sm leading-relaxed">
                {r.steps.map((s, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-bold text-accent">{i + 1}</span>
                    {s}
                  </li>
                ))}
              </ol>
              {r.tip && <p className="mt-4 rounded-xl bg-leaf-soft p-3 text-sm text-leaf">💡 {r.tip}</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
