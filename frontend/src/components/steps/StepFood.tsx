"use client";

import { useEffect, useRef, useState } from "react";
import { regionStatus, resolveRegion } from "@/lib/api";
import { money, regionCurrency } from "@/lib/form";
import { usePlan } from "@/lib/store";
import type { RegionRef, RegionResolution } from "@/lib/types";
import { Card, ChipsWithCustom, Section, TagInput, Tile, cx } from "../ui";

const DIET_ICONS: Record<string, string> = {
  omnivore: "🍽️",
  flexitarian: "🥗",
  pollotarian: "🍗",
  pescatarian: "🐟",
  eggetarian: "🥚",
  vegetarian: "🥦",
  vegan: "🌱",
  jain: "🙏",
  sattvic: "🪷",
  paleo: "🥩",
};

const EXAMPLES = ["London", "New York", "Mumbai", "Paris", "Tokyo", "Mexico City", "Dubai"];

// Broad, widely recognised food cultures; anything else can be typed in.
const CULTURES = [
  "Indian", "Chinese", "Italian", "Mexican", "Middle Eastern", "Mediterranean", "Japanese", "Korean",
  "Thai", "French", "British", "American", "African", "Latin American",
];

export function StepFood() {
  const { profile, options, setBackground, setKitchen } = usePlan();
  const bg = profile.background;
  const [query, setQuery] = useState(bg.location);
  const [resolution, setResolution] = useState<RegionResolution | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const polling = useRef<ReturnType<typeof setInterval> | null>(null);

  // A profile's budget only applies when it's priced in this place's currency (Toronto eats "American" but pays CAD).
  const budgetFor = (place: RegionRef, r: RegionResolution) =>
    place.budget?.typical ? place.budget : r.region.currency_code === place.currency_code ? r.budget : {};

  const applyBudget = (place: RegionRef, budget: RegionRef["budget"]) => {
    if (budget?.typical) setKitchen({ daily_budget: budget.typical, budget_currency: place.currency_code });
  };

  // Show the card for a region chosen on an earlier visit.
  useEffect(() => {
    if (bg.region && !resolution) {
      const place = bg.region;
      regionStatus(place.key)
        .then((r) => setResolution({ ...r, region: place, budget: budgetFor(place, r) }))
        .catch(() => undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A brand-new region is written by Gemma in the background; poll until it's ready.
  useEffect(() => {
    if (resolution?.status !== "generating") return;
    polling.current = setInterval(async () => {
      try {
        const r = await regionStatus(resolution.region.key);
        if (r.status !== "generating") {
          const place = resolution.region;
          const budget = budgetFor(place, r);
          setResolution({ ...r, region: place, budget });
          // Fill the budget in only if the quick lookup couldn't estimate one.
          if (!place.budget?.typical && budget.typical) {
            setBackground({ region: { ...place, budget } });
            applyBudget(place, budget);
          }
        }
      } catch {
        /* keep polling */
      }
    }, 3000);
    return () => {
      if (polling.current) clearInterval(polling.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolution]);

  async function find(location: string) {
    const loc = location.trim();
    if (loc.length < 2) return;
    setBusy(true);
    setError(null);
    try {
      const r = await resolveRegion(loc);
      setResolution(r);
      setBackground({ location: loc, region: r.region });
      applyBudget(r.region, r.region.budget?.typical ? r.region.budget : r.budget);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const cultureSuggestions = CULTURES.filter((c) => !bg.cultures.some((x) => x.toLowerCase() === c.toLowerCase()));

  return (
    <div className="space-y-6">
      <Card className="space-y-4">
        <Section title="Where do you live?" hint="A city, region or country — any language. We load what people there actually cook and buy.">
          <form
            className="flex flex-col gap-2 sm:flex-row"
            onSubmit={(e) => {
              e.preventDefault();
              void find(query);
            }}
          >
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. London, Mumbai, Paris, New York…"
              aria-label="Where you live"
              className="min-w-0 flex-1 rounded-xl border border-line bg-surface-2 px-4 py-3 text-base outline-none transition placeholder:text-muted focus:border-accent focus:bg-surface"
            />
            <button
              type="submit"
              disabled={busy || query.trim().length < 2}
              className="rounded-xl bg-accent px-5 py-3 font-semibold text-accent-ink transition hover:brightness-105 disabled:opacity-40"
            >
              {busy ? "Looking up…" : "Find"}
            </button>
          </form>
          {!bg.region && (
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="text-muted">Try:</span>
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => {
                    setQuery(ex);
                    void find(ex);
                  }}
                  className="rounded-full border border-dashed border-line px-2.5 py-0.5 hover:border-accent hover:bg-accent-soft"
                >
                  {ex}
                </button>
              ))}
            </div>
          )}
          {error && <p className="rounded-lg bg-chili-soft px-3 py-2 text-sm text-chili">{error}</p>}
        </Section>

        {resolution && <RegionCard r={resolution} />}
      </Card>

      <Card>
        <Section title="Food culture you grew up with" hint="Optional — it can differ from where you live now. Pick or type any.">
          <TagInput values={bg.cultures} onChange={(cultures) => setBackground({ cultures })} placeholder="Type any cuisine and press Enter, e.g. Indian, Italian…" />
          {cultureSuggestions.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {cultureSuggestions.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setBackground({ cultures: [...bg.cultures, c] })}
                  className="rounded-full border border-dashed border-line px-3 py-1 text-xs hover:border-accent hover:bg-accent-soft"
                >
                  + {c}
                </button>
              ))}
            </div>
          )}
        </Section>
      </Card>

      <Card className="space-y-6">
        <Section title="What kind of eater are you?">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {Object.entries(options?.diet_types ?? {}).map(([key, d]) => (
              <Tile
                key={key}
                icon={DIET_ICONS[key] ?? "🍽️"}
                title={d.label}
                desc={d.desc}
                selected={bg.diet_type === key}
                onClick={() => setBackground({ diet_type: key })}
              />
            ))}
          </div>
        </Section>

        <Section title="Any eating style?" hint="Optional. These shape your macros and recipes rather than banning foods. Add your own if it's not listed.">
          <ChipsWithCustom
            options={options?.diet_styles ?? {}}
            values={bg.diet_styles}
            onChange={(diet_styles) => setBackground({ diet_styles })}
            addLabel="Add your own style"
          />
        </Section>

        <Section title="Religious or personal rules" hint="Treated as hard rules, never suggestions — e.g. “no food after sunset”, “no red meat on Tuesdays”.">
          <ChipsWithCustom
            options={options?.restrictions ?? {}}
            values={bg.restrictions}
            onChange={(restrictions) => setBackground({ restrictions })}
            addLabel="Add your own rule"
          />
        </Section>

        <Section title="Allergies & intolerances" hint="Anything missing? Type it — e.g. kiwi, mustard, lupin.">
          <ChipsWithCustom
            options={options?.allergies ?? {}}
            values={bg.allergies}
            onChange={(allergies) => setBackground({ allergies })}
            addLabel="Add an allergy"
          />
        </Section>

        <Section title="Anything you just don't like?" hint="Type and press Enter — e.g. mushrooms, coriander, olives.">
          <TagInput values={bg.avoid_foods} onChange={(avoid_foods) => setBackground({ avoid_foods })} placeholder="Foods to avoid…" />
        </Section>
      </Card>
    </div>
  );
}

function RegionCard({ r }: { r: RegionResolution }) {
  const cur = regionCurrency(r.region);
  return (
    <div className={cx("animate-rise rounded-xl border p-4", r.status === "failed" ? "border-chili/30 bg-chili-soft" : "border-leaf/30 bg-leaf-soft/60")}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold">
          📍 {r.region.place} <span className="font-normal text-muted">→ {r.region.name} home cooking</span>
        </p>
        <span className="text-xs text-muted">
          {r.region.currency_code} {r.region.currency_symbol}
        </span>
      </div>
      {r.status === "generating" && (
        <p className="mt-2 flex items-center gap-2 text-sm">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-line border-t-accent" />
          New to our knowledge base — Gemma 4 is writing a food profile for this region. Keep going; it&apos;ll be ready before you finish.
        </p>
      )}
      {r.status === "failed" && <p className="mt-2 text-sm text-chili">We couldn&apos;t build a detailed profile, so we&apos;ll plan with general home cooking in your currency.</p>}
      {r.status === "ready" && r.staples.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {r.staples.slice(0, 10).map((s) => (
            <span key={s} className="rounded-full bg-surface px-2.5 py-0.5 text-xs">
              {s}
            </span>
          ))}
        </div>
      )}
      {r.status === "ready" && r.budget.typical != null && (
        <p className="mt-3 text-xs text-muted">
          Typical home food budget there: {money(r.budget.low ?? 0, cur)}–{money(r.budget.high ?? 0, cur)} per person per day
        </p>
      )}
      <p className="mt-2 text-[11px] text-muted">
        Source: {r.source}
        {r.route_reason && ` · routed: ${r.route_reason}`}
      </p>
    </div>
  );
}
