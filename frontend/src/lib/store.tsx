"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { checkPlan, createPlan, getOptions, getTargets } from "./api";
import { DEFAULT_PROFILE } from "./form";
import type { Background, Basics, Kitchen, MealSwap, Options, PlanResponse, Profile, Targets, TypicalDay } from "./types";

const STORAGE_KEY = "meal-planner:v1";

interface Saved {
  profile: Profile;
  result: PlanResponse | null;
  heightUnit: "cm" | "ft";
}

interface PlanStore {
  hydrated: boolean;
  profile: Profile;
  heightUnit: "cm" | "ft";
  setHeightUnit: (u: "cm" | "ft") => void;
  setBasics: (p: Partial<Basics>) => void;
  setBackground: (p: Partial<Background>) => void;
  setDay: (p: Partial<TypicalDay>) => void;
  setKitchen: (p: Partial<Kitchen>) => void;
  options: Options | null;
  optionsError: string | null;
  targets: Targets | null;
  targetsError: string | null;
  result: PlanResponse | null;
  generating: boolean;
  generateError: string | null;
  generate: () => Promise<boolean>;
  applySwap: (swap: MealSwap) => Promise<void>;
  reset: () => void;
}

const Ctx = createContext<PlanStore | null>(null);

function loadSaved(): Partial<Saved> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Saved) : {};
  } catch {
    return {};
  }
}

export function PlanProvider({ children }: { children: React.ReactNode }) {
  const [hydrated, setHydrated] = useState(false);
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE);
  const [heightUnit, setHeightUnit] = useState<"cm" | "ft">("cm");
  const [options, setOptions] = useState<Options | null>(null);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [targets, setTargets] = useState<Targets | null>(null);
  const [targetsError, setTargetsError] = useState<string | null>(null);
  const [result, setResult] = useState<PlanResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const generation = useRef(0);

  // Restore from this browser only: no accounts, nothing stored server-side.
  useEffect(() => {
    const saved = loadSaved();
    if (saved.profile) {
      setProfile({
        basics: { ...DEFAULT_PROFILE.basics, ...saved.profile.basics },
        background: { ...DEFAULT_PROFILE.background, ...saved.profile.background },
        typical_day: { ...DEFAULT_PROFILE.typical_day, ...saved.profile.typical_day },
        kitchen: { ...DEFAULT_PROFILE.kitchen, ...saved.profile.kitchen },
      });
    }
    if (saved.result) setResult(saved.result);
    if (saved.heightUnit) setHeightUnit(saved.heightUnit);
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ profile, result, heightUnit } satisfies Saved));
    } catch {
      /* storage full or blocked: the app still works */
    }
  }, [profile, result, heightUnit, hydrated]);

  useEffect(() => {
    getOptions()
      .then(setOptions)
      .catch((e: Error) => setOptionsError(e.message));
  }, []);

  // Live targets from the backend's deterministic formula, debounced.
  useEffect(() => {
    const ctrl = new AbortController();
    const id = setTimeout(() => {
      getTargets(profile.basics, ctrl.signal)
        .then((t) => {
          setTargets(t);
          setTargetsError(null);
        })
        .catch((e: Error) => e.name !== "AbortError" && setTargetsError(e.message));
    }, 250);
    return () => {
      clearTimeout(id);
      ctrl.abort();
    };
  }, [profile.basics]);

  const setBasics = useCallback((p: Partial<Basics>) => setProfile((f) => ({ ...f, basics: { ...f.basics, ...p } })), []);
  const setBackground = useCallback(
    (p: Partial<Background>) => setProfile((f) => ({ ...f, background: { ...f.background, ...p } })),
    [],
  );
  const setDay = useCallback((p: Partial<TypicalDay>) => setProfile((f) => ({ ...f, typical_day: { ...f.typical_day, ...p } })), []);
  const setKitchen = useCallback((p: Partial<Kitchen>) => setProfile((f) => ({ ...f, kitchen: { ...f.kitchen, ...p } })), []);

  const generate = useCallback(async () => {
    const id = ++generation.current;
    setGenerating(true);
    setGenerateError(null);
    try {
      const res = await createPlan(profile);
      if (id !== generation.current) return false; // superseded by a reset or a newer run
      setResult(res);
      return true;
    } catch (e) {
      if (id === generation.current) setGenerateError((e as Error).message);
      return false;
    } finally {
      if (id === generation.current) setGenerating(false);
    }
  }, [profile]);

  const applySwap = useCallback(
    async (swap: MealSwap) => {
      if (!result) return;
      const days = result.plan.days.map((d) => {
        if (d.day.toLowerCase() !== swap.day.toLowerCase()) return d;
        const i = d.meals.findIndex((m) => !m.top_up && m.slot.toLowerCase() === swap.slot.toLowerCase());
        const meal = {
          slot: i >= 0 ? d.meals[i].slot : swap.slot,
          time: i >= 0 ? d.meals[i].time : "",
          dish: swap.dish,
          recipe_id: null,
          portion: swap.portion,
          kcal: swap.kcal,
          protein_g: swap.protein_g,
          carbs_g: swap.carbs_g,
          fat_g: swap.fat_g,
          cost: swap.cost,
          top_up: false,
        };
        const meals = i >= 0 ? d.meals.map((m, j) => (j === i ? meal : m)) : [...d.meals, meal];
        return { ...d, meals };
      });
      const plan = { ...result.plan, days };
      const checks = await checkPlan(plan, result.targets, profile.kitchen.daily_budget).catch(() => result.checks);
      setResult({ ...result, plan, checks });
    },
    [result, profile.kitchen.daily_budget],
  );

  const reset = useCallback(() => {
    generation.current++;
    setProfile(DEFAULT_PROFILE);
    setResult(null);
    setGenerating(false);
    setGenerateError(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<PlanStore>(
    () => ({
      hydrated,
      profile,
      heightUnit,
      setHeightUnit,
      setBasics,
      setBackground,
      setDay,
      setKitchen,
      options,
      optionsError,
      targets,
      targetsError,
      result,
      generating,
      generateError,
      generate,
      applySwap,
      reset,
    }),
    [hydrated, profile, heightUnit, setBasics, setBackground, setDay, setKitchen, options, optionsError, targets, targetsError, result, generating, generateError, generate, applySwap, reset],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePlan() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("usePlan must be used inside <PlanProvider>");
  return ctx;
}
