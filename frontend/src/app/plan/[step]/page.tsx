"use client";

import Link from "next/link";
import { notFound, useParams, useRouter } from "next/navigation";
import { StepBasics } from "@/components/steps/StepBasics";
import { StepDay } from "@/components/steps/StepDay";
import { StepFood } from "@/components/steps/StepFood";
import { StepKitchen } from "@/components/steps/StepKitchen";
import { TargetsPanel } from "@/components/steps/StepBasics";
import { cx } from "@/components/ui";
import { STEPS, type StepSlug, stepBlocker } from "@/lib/form";
import { usePlan } from "@/lib/store";

export default function StepPage() {
  const { step } = useParams<{ step: string }>();
  const router = useRouter();
  const store = usePlan();
  const index = STEPS.findIndex((s) => s.slug === step);
  if (index === -1) notFound();
  const current = STEPS[index];
  const last = index === STEPS.length - 1;
  const blocker = stepBlocker(current.slug, store.profile);

  if (!store.hydrated) return <div className="h-96 animate-pulse rounded-2xl bg-surface-2" />;
  if (store.optionsError) {
    return (
      <div className="rounded-2xl border border-chili/30 bg-chili-soft p-6 text-chili">
        <p className="font-semibold">Can&apos;t reach the planner service.</p>
        <p className="mt-1 text-sm">{store.optionsError}. Is the FastAPI backend running on port 8000?</p>
      </div>
    );
  }

  const next = () => {
    if (last) {
      void store.generate();
      router.push("/plan/result");
    } else {
      router.push(`/plan/${STEPS[index + 1].slug}`);
    }
    window.scrollTo({ top: 0 });
  };

  return (
    <>
      <Progress current={current.slug} />
      <div className="mb-6 mt-8">
        <p className="text-sm font-semibold text-accent">
          Step {index + 1} of {STEPS.length}
        </p>
        <h1 className="mt-1 font-display text-3xl font-semibold sm:text-4xl">{current.title}</h1>
        <p className="mt-1 text-muted">{current.blurb}</p>
      </div>

      <div key={current.slug} className="animate-rise">
        {current.slug === "basics" && (
          <StepBasics
            basics={store.profile.basics}
            heightUnit={store.heightUnit}
            setBasics={store.setBasics}
            setHeightUnit={store.setHeightUnit}
            targets={store.targets}
            targetsError={store.targetsError}
          />
        )}
        {current.slug === "food" && <StepFood />}
        {current.slug === "day" && (
          <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
            <StepDay />
            <aside className="hidden lg:sticky lg:top-24 lg:block lg:self-start">
              <TargetsPanel targets={store.targets} error={store.targetsError} weight={store.profile.basics.weight_kg} />
            </aside>
          </div>
        )}
        {current.slug === "kitchen" && <StepKitchen />}
      </div>

      <div className="sticky bottom-0 z-20 -mx-4 mt-8 border-t border-line bg-bg/90 px-4 py-4 backdrop-blur sm:-mx-6 sm:px-6">
        <div className="flex items-center justify-between gap-3">
          {index > 0 ? (
            <Link href={`/plan/${STEPS[index - 1].slug}`} className="rounded-full px-5 py-2.5 text-sm font-medium text-muted transition hover:text-ink">
              ← Back
            </Link>
          ) : (
            <Link href="/" className="rounded-full px-5 py-2.5 text-sm font-medium text-muted transition hover:text-ink">
              ← Home
            </Link>
          )}
          <div className="flex items-center gap-3">
            {blocker && <span className="hidden text-sm text-muted sm:inline">{blocker}</span>}
            <button
              type="button"
              disabled={!!blocker || (last && store.generating)}
              onClick={next}
              className={cx(
                "rounded-full px-6 py-2.5 text-sm font-semibold shadow-sm transition active:scale-95 disabled:cursor-not-allowed disabled:opacity-40",
                last ? "bg-leaf text-white hover:brightness-110" : "bg-accent text-accent-ink hover:brightness-105",
              )}
            >
              {last ? (store.result ? "🍽️ Build a new week" : "🍽️ Build my week") : "Continue →"}
            </button>
          </div>
        </div>
        {blocker && <p className="mt-2 text-right text-xs text-muted sm:hidden">{blocker}</p>}
      </div>
    </>
  );
}

function Progress({ current }: { current: StepSlug }) {
  const { profile } = usePlan();
  const index = STEPS.findIndex((s) => s.slug === current);
  // A step is reachable when every step before it is complete.
  const reachable = (i: number) => STEPS.slice(0, i).every((s) => !stepBlocker(s.slug, profile));
  return (
    <ol className="flex items-center gap-2">
      {STEPS.map((s, i) => {
        const done = i < index || (i !== index && !stepBlocker(s.slug, profile) && reachable(i));
        const content = (
          <>
            <span
              className={cx(
                "grid h-8 w-8 shrink-0 place-items-center rounded-full border-2 text-xs font-bold transition",
                i === index && "border-accent bg-accent text-accent-ink",
                i !== index && done && "border-leaf bg-leaf text-white",
                i !== index && !done && "border-line",
              )}
            >
              {i !== index && done ? "✓" : i + 1}
            </span>
            <span className="hidden md:inline">{s.title}</span>
          </>
        );
        return (
          <li key={s.slug} className="flex flex-1 items-center gap-2">
            {reachable(i) && i !== index ? (
              <Link href={`/plan/${s.slug}`} className="flex items-center gap-2 text-sm font-medium text-ink transition hover:text-accent">
                {content}
              </Link>
            ) : (
              <span className={cx("flex items-center gap-2 text-sm font-medium", i <= index ? "text-ink" : "text-muted")}>{content}</span>
            )}
            {i < STEPS.length - 1 && (
              <span className="h-0.5 flex-1 rounded-full bg-line">
                <span className={cx("block h-full rounded-full bg-leaf transition-all duration-500", i < index ? "w-full" : "w-0")} />
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
