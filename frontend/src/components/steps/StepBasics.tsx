"use client";

import { cmToFtIn } from "@/lib/form";
import type { Activity, Basics, Pace, Sex, Targets } from "@/lib/types";
import { Card, RangeField, Section, Segmented, Tile, cx } from "../ui";

const ACTIVITIES: { value: Activity; icon: string; title: string; desc: string }[] = [
  { value: "sedentary", icon: "🪑", title: "Mostly sitting", desc: "Desk job, little walking" },
  { value: "light", icon: "🚶", title: "Lightly active", desc: "Walks, chores, 1–3 workouts/week" },
  { value: "moderate", icon: "🚴", title: "Moderately active", desc: "On your feet or 3–5 workouts/week" },
  { value: "active", icon: "🏃", title: "Very active", desc: "Physical job or daily training" },
  { value: "very_active", icon: "🏋️", title: "Athlete", desc: "Hard training twice a day" },
];

const PACES: { value: Pace; label: string }[] = [
  { value: "gentle", label: "Gentle · 0.25 kg/wk" },
  { value: "steady", label: "Steady · 0.5 kg/wk" },
  { value: "fast", label: "Faster · 0.75 kg/wk" },
];

export function StepBasics({
  basics: b,
  heightUnit,
  setBasics,
  setHeightUnit,
  targets,
  targetsError,
}: {
  basics: Basics;
  heightUnit: "cm" | "ft";
  setBasics: (patch: Partial<Basics>) => void;
  setHeightUnit: (u: "cm" | "ft") => void;
  targets: Targets | null;
  targetsError: string | null;
}) {
  const { ft, inch } = cmToFtIn(b.height_cm);
  const diff = b.target_weight_kg - b.weight_kg;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <div className="space-y-6">
        <Card className="space-y-6">
          <Section title="About you" hint="Used for the standard Mifflin-St Jeor energy formula.">
            <Segmented<Sex>
              label="Sex"
              value={b.sex}
              onChange={(sex) => setBasics({ sex })}
              options={[
                { value: "female", label: "Female" },
                { value: "male", label: "Male" },
                { value: "other", label: "Prefer not to say" },
              ]}
            />
          </Section>
          <RangeField label="Age" value={b.age} min={18} max={80} onChange={(age) => setBasics({ age })} display={`${b.age} yrs`} />
          <div className="space-y-2">
            <div className="flex justify-end">
              <Segmented
                label="Height unit"
                value={heightUnit}
                onChange={setHeightUnit}
                options={[
                  { value: "cm", label: "cm" },
                  { value: "ft", label: "ft / in" },
                ]}
              />
            </div>
            <RangeField
              label="Height"
              value={b.height_cm}
              min={130}
              max={210}
              step={heightUnit === "cm" ? 1 : 2.54}
              onChange={(h) => setBasics({ height_cm: Math.round(h * 10) / 10 })}
              display={heightUnit === "cm" ? `${Math.round(b.height_cm)} cm` : `${ft}′ ${inch}″`}
            />
          </div>
        </Card>

        <Card className="space-y-6">
          <RangeField
            label="Current weight"
            value={b.weight_kg}
            min={35}
            max={180}
            step={0.5}
            onChange={(weight_kg) => setBasics({ weight_kg })}
            display={`${b.weight_kg} kg`}
          />
          <RangeField
            label="Target weight"
            value={b.target_weight_kg}
            min={35}
            max={180}
            step={0.5}
            onChange={(target_weight_kg) => setBasics({ target_weight_kg })}
            display={`${b.target_weight_kg} kg`}
            hint={
              Math.abs(diff) < 1
                ? "Maintaining — we'll plan to keep you steady."
                : diff < 0
                  ? `That's ${Math.abs(diff).toFixed(1)} kg to lose.`
                  : `That's ${diff.toFixed(1)} kg to gain.`
            }
          />
          {Math.abs(diff) >= 1 && (
            <Section title="How fast?" hint="Slower is easier to stick with. We cap it at a safe rate either way.">
              <Segmented<Pace> label="Pace" value={b.pace} onChange={(pace) => setBasics({ pace })} options={PACES} />
            </Section>
          )}
        </Card>

        <Card>
          <Section title="How active is a normal week?">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {ACTIVITIES.map((a) => (
                <Tile
                  key={a.value}
                  icon={a.icon}
                  title={a.title}
                  desc={a.desc}
                  selected={b.activity === a.value}
                  onClick={() => setBasics({ activity: a.value })}
                />
              ))}
            </div>
          </Section>
        </Card>
      </div>

      <aside className="lg:sticky lg:top-6 lg:self-start">
        <TargetsPanel targets={targets} error={targetsError} weight={b.weight_kg} />
      </aside>
    </div>
  );
}

const BMI_MIN = 15;
const BMI_MAX = 40;
const pos = (bmi: number) => `${((Math.min(BMI_MAX, Math.max(BMI_MIN, bmi)) - BMI_MIN) / (BMI_MAX - BMI_MIN)) * 100}%`;

export function TargetsPanel({ targets: t, error, weight }: { targets: Targets | null; error: string | null; weight: number }) {
  if (error) return <Card className="text-sm text-chili">{error}</Card>;
  if (!t) return <Card className="h-72 animate-pulse bg-surface-2" />;

  const goalDate =
    t.weeks_to_goal != null
      ? new Date(Date.now() + t.weeks_to_goal * 7 * 864e5).toLocaleDateString("en-IN", { month: "short", year: "numeric" })
      : null;
  const kcalFromP = t.protein_g * 4;
  const kcalFromF = t.fat_g * 9;
  const kcalFromC = t.carbs_g * 4;
  const total = kcalFromP + kcalFromF + kcalFromC || 1;

  return (
    <Card className="space-y-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">Your daily target</p>
        <p className="mt-1 font-display text-5xl font-semibold tabular-nums text-ink">
          {t.target_kcal.toLocaleString("en-IN")}
          <span className="ml-1 text-lg font-normal text-muted">kcal</span>
        </p>
        <p className="mt-1 text-sm text-muted">
          You burn ~{t.tdee.toLocaleString("en-IN")} kcal/day ·{" "}
          {t.goal === "maintain"
            ? "maintenance"
            : `${t.goal === "lose" ? "−" : "+"}${Math.abs(t.tdee - t.target_kcal)} kcal/day`}
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex h-3 overflow-hidden rounded-full">
          <div className="bg-leaf" style={{ width: `${(kcalFromP / total) * 100}%` }} />
          <div className="bg-accent" style={{ width: `${(kcalFromC / total) * 100}%` }} />
          <div className="bg-chili/70" style={{ width: `${(kcalFromF / total) * 100}%` }} />
        </div>
        <div className="grid grid-cols-3 text-xs">
          <Macro color="bg-leaf" label="Protein" g={t.protein_g} />
          <Macro color="bg-accent" label="Carbs" g={t.carbs_g} />
          <Macro color="bg-chili/70" label="Fat" g={t.fat_g} />
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-baseline justify-between text-sm">
          <span className="text-muted">BMI</span>
          <span>
            <b className="tabular-nums">{t.bmi}</b> · {t.bmi_category}
          </span>
        </div>
        <div className="relative h-2.5 rounded-full">
          <div className="absolute inset-0 flex overflow-hidden rounded-full">
            <div className="bg-sky-300/70" style={{ width: pos(18.5) }} />
            <div className="bg-leaf/70" style={{ width: `calc(${pos(25)} - ${pos(18.5)})` }} />
            <div className="bg-accent/70" style={{ width: `calc(${pos(30)} - ${pos(25)})` }} />
            <div className="flex-1 bg-chili/60" />
          </div>
          <Marker left={pos(t.target_bmi)} label="goal" hollow />
          <Marker left={pos(t.bmi)} label="now" />
        </div>
        <p className="pt-3 text-[11px] text-muted">WHO adult BMI categories (healthy 18.5–24.9). BMI is a rough guide, not a diagnosis.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <Stat label="Goal" value={`${t.planned_target_weight_kg} kg`} />
        <Stat label="Pace" value={t.goal === "maintain" ? "—" : `${t.weekly_change_kg} kg/wk`} />
        <Stat label="Reach it by" value={goalDate ?? "—"} sub={t.weeks_to_goal ? `~${Math.ceil(t.weeks_to_goal)} weeks` : undefined} />
        <Stat label="Water" value={`${t.water_l} L/day`} sub={`for ${weight} kg`} />
      </div>

      {t.warnings.length > 0 && (
        <ul className="space-y-2">
          {t.warnings.map((w) => (
            <li key={w} className="rounded-lg bg-chili-soft px-3 py-2 text-xs leading-relaxed text-chili">
              {w}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Macro({ color, label, g }: { color: string; label: string; g: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={cx("h-2 w-2 rounded-full", color)} />
      <span className="text-muted">{label}</span>
      <b className="tabular-nums">{g}g</b>
    </div>
  );
}

function Marker({ left, label, hollow }: { left: string; label: string; hollow?: boolean }) {
  return (
    <div className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 transition-all duration-300" style={{ left }}>
      <div className={cx("h-4 w-4 rounded-full border-[3px] border-ink", hollow ? "bg-surface" : "bg-ink")} />
      <span className="absolute left-1/2 top-5 -translate-x-1/2 text-[10px] font-medium text-muted">{label}</span>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-surface-2 px-3 py-2.5">
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="font-semibold tabular-nums">{value}</p>
      {sub && <p className="text-[11px] text-muted">{sub}</p>}
    </div>
  );
}
