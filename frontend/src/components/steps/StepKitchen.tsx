"use client";

import { useEffect, useState } from "react";
import { analyzePantry } from "@/lib/api";
import { money, regionCurrency } from "@/lib/form";
import { usePlan } from "@/lib/store";
import type { PantryResult } from "@/lib/types";
import { Card, RangeField, Section, Segmented, Tile, Toggle, toggleIn } from "../ui";

const EQUIPMENT_ICONS: Record<string, string> = {
  stove: "🔥",
  induction: "⚡",
  oven: "🔲",
  microwave: "📻",
  air_fryer: "💨",
  pressure_cooker: "♨️",
  slow_cooker: "🍲",
  rice_cooker: "🍚",
  blender: "🌀",
  toaster: "🍞",
  grill: "🍢",
  kettle: "🫖",
  refrigerator: "🧊",
  freezer: "❄️",
};

export function StepKitchen() {
  const { profile, options, setKitchen } = usePlan();
  const k = profile.kitchen;
  const region = profile.background.region;
  const cur = regionCurrency(region);
  const [pantryText, setPantryText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agent, setAgent] = useState<Pick<PantryResult, "suggestions" | "model" | "route_reason" | "equipment"> | null>(null);
  const [categories, setCategories] = useState<Record<string, string>>({});
  const range = region?.budget?.low != null && region.budget.high != null ? { low: region.budget.low, high: region.budget.high } : null;

  // A budget set for another region is in the wrong currency (₹250 is not $250): reset it to the local typical.
  useEffect(() => {
    if (!region || k.budget_currency === region.currency_code) return;
    setKitchen({
      budget_currency: region.currency_code,
      ...(region.budget?.typical ? { daily_budget: region.budget.typical } : {}),
    });
  }, [region, k.budget_currency, setKitchen]);

  async function readPantry() {
    setBusy(true);
    setError(null);
    try {
      const r = await analyzePantry({ text: pantryText, profile });
      const names = r.items.map((i) => i.name);
      setKitchen({
        pantry: Array.from(new Set([...k.pantry, ...names])),
        equipment: Array.from(new Set([...k.equipment, ...r.equipment])),
      });
      setCategories((c) => ({ ...c, ...Object.fromEntries(r.items.map((i) => [i.name, i.category])) }));
      setAgent({ suggestions: r.suggestions, model: r.model, route_reason: r.route_reason, equipment: r.equipment });
      setPantryText("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const grouped = new Map<string, string[]>();
  for (const item of k.pantry) {
    const cat = categories[item] ?? "Your pantry";
    grouped.set(cat, [...(grouped.get(cat) ?? []), item]);
  }

  // Slider spans half of "low" to twice "high" in the local currency, with a step that suits its magnitude
  // (0.5 for £/€/$, 10 for ₹, 100 for CLP or JPY).
  const minB = range ? Math.max(0.5, Math.floor(range.low * 0.5)) : 1;
  const maxB = range ? Math.ceil(range.high * 2) : Math.max(50, k.daily_budget * 3);
  const step = Math.max(0.5, 10 ** Math.floor(Math.log10(maxB / 100)));

  return (
    <div className="space-y-6">
      <Card>
        <Section title="What's in your kitchen?" hint="Recipes will only use what you have — no oven, no baking.">
          <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-4 lg:grid-cols-7">
            {Object.entries(options?.equipment ?? {}).map(([key, label]) => (
              <Tile
                key={key}
                icon={EQUIPMENT_ICONS[key]}
                title={label}
                selected={k.equipment.includes(key)}
                onClick={() => setKitchen({ equipment: toggleIn(k.equipment, key) })}
              />
            ))}
          </div>
        </Section>
      </Card>

      <Card className="space-y-4">
        <Section
          title="What do you usually have in the cupboard and fridge?"
          hint="Just list it — 'rice, pasta, eggs, a bag of lentils, onions, frozen peas, olive oil…'. Your shopping list will only include what's missing."
        >
          <textarea
            value={pantryText}
            onChange={(e) => setPantryText(e.target.value)}
            rows={3}
            maxLength={3000}
            placeholder="rice, atta, toor dal, onions, tomatoes, potatoes, milk, curd, eggs, mustard oil, the usual spices…"
            aria-label="What you usually have in your kitchen"
            className="w-full resize-y rounded-xl border border-line bg-surface-2 px-4 py-3 text-[15px] outline-none transition placeholder:text-muted/80 focus:border-accent focus:bg-surface"
          />
          <div className="flex flex-wrap items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => void readPantry()}
              disabled={busy || pantryText.trim().length < 3}
              className="rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-accent-ink transition hover:brightness-105 disabled:opacity-40"
            >
              {busy ? "Reading…" : "✨ Add to my pantry"}
            </button>
          </div>
          {error && <p className="rounded-lg bg-chili-soft px-3 py-2 text-sm text-chili">{error}</p>}
        </Section>

        {k.pantry.length > 0 && (
          <div className="animate-rise space-y-3">
            <div className="flex items-baseline justify-between">
              <p className="text-sm text-muted">
                <b className="text-ink">{k.pantry.length}</b> items in your pantry
              </p>
              <button type="button" onClick={() => setKitchen({ pantry: [] })} className="text-sm text-muted hover:text-chili">
                Clear all
              </button>
            </div>
            {[...grouped.entries()].map(([cat, items]) => (
              <div key={cat} className="space-y-1.5">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted">{cat}</p>
                <div className="flex flex-wrap gap-1.5">
                  {items.map((item) => (
                    <span key={item} className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2.5 py-1 text-sm">
                      {item}
                      <button
                        type="button"
                        aria-label={`Remove ${item}`}
                        onClick={() => setKitchen({ pantry: k.pantry.filter((p) => p !== item) })}
                        className="text-muted hover:text-chili"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {agent && (
          <div className="space-y-2">
            {agent.equipment.length > 0 && (
              <p className="text-xs text-leaf">✓ Also ticked equipment you mentioned: {agent.equipment.map((e) => options?.equipment[e] ?? e).join(", ")}</p>
            )}
            {agent.suggestions.filter((s) => !k.pantry.includes(s)).length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-muted">Most kitchens near you also have:</span>
                {agent.suggestions
                  .filter((s) => !k.pantry.includes(s))
                  .map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setKitchen({ pantry: [...k.pantry, s] })}
                      className="rounded-full border border-dashed border-line px-3 py-1 text-xs hover:border-accent hover:bg-accent-soft"
                    >
                      + {s}
                    </button>
                  ))}
              </div>
            )}
            <p className="text-[11px] text-muted">
              Read by {agent.model} · routed: {agent.route_reason}
            </p>
          </div>
        )}
      </Card>

      <Card className="grid gap-8 md:grid-cols-2">
        <RangeField
          label="Food budget per day (just for you)"
          value={Math.min(Math.max(k.daily_budget, minB), maxB)}
          min={minB}
          max={maxB}
          step={step}
          onChange={(daily_budget) => setKitchen({ daily_budget })}
          display={money(k.daily_budget, cur)}
          hint={`≈ ${money(k.daily_budget * 30, cur)} a month on groceries${range ? ` · typical locally: ${money(range.low, cur)}–${money(range.high, cur)}/day` : ""}`}
        />
        <RangeField
          label="Time you can spend cooking per day"
          value={k.cook_minutes_per_day}
          min={10}
          max={150}
          step={5}
          onChange={(cook_minutes_per_day) => setKitchen({ cook_minutes_per_day })}
          display={`${k.cook_minutes_per_day} min`}
          hint={k.cook_minutes_per_day <= 20 ? "Quick fixes, one-pot meals and leftovers." : "Enough for a fresh main and a side most days."}
        />
        <Section title="Cooking skill">
          <Segmented
            label="Cooking skill"
            value={k.skill}
            onChange={(skill) => setKitchen({ skill })}
            options={[
              { value: "beginner", label: "Beginner" },
              { value: "comfortable", label: "Comfortable" },
              { value: "expert", label: "Expert" },
            ]}
          />
        </Section>
        <div className="flex items-start justify-between gap-4 rounded-xl bg-surface-2 p-4">
          <div>
            <p className="text-[15px] font-semibold">Batch cook on weekends</p>
            <p className="text-sm text-muted">Cook bases, sauces and grains once, reuse through the week.</p>
          </div>
          <Toggle checked={k.batch_cooking} onChange={(batch_cooking) => setKitchen({ batch_cooking })} label="Batch cooking" />
        </div>
      </Card>
    </div>
  );
}
