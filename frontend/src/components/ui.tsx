"use client";

import { type ReactNode, useId, useState } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Card({ children, className }: { children?: ReactNode; className?: string }) {
  return (
    <div className={cx("rounded-2xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgb(0_0_0/0.04)]", className)}>
      {children}
    </div>
  );
}

export function Section({ title, hint, children }: { title: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
        {hint && <p className="mt-0.5 text-sm text-muted">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

export function Chip({
  selected,
  onClick,
  children,
  title,
}: {
  selected?: boolean;
  onClick?: () => void;
  children: ReactNode;
  title?: string;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-pressed={selected}
      onClick={onClick}
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm transition-all active:scale-95",
        selected
          ? "border-accent bg-accent text-accent-ink shadow-sm"
          : "border-line bg-surface text-ink hover:border-accent/60 hover:bg-accent-soft",
      )}
    >
      {selected && <span aria-hidden>✓</span>}
      {children}
    </button>
  );
}

export function Tile({
  selected,
  onClick,
  icon,
  title,
  desc,
}: {
  selected?: boolean;
  onClick?: () => void;
  icon?: ReactNode;
  title: string;
  desc?: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={cx(
        "group relative flex h-full flex-col items-start gap-1 rounded-xl border-2 p-3.5 text-left transition-all active:scale-[0.98]",
        selected ? "border-accent bg-accent-soft" : "border-line bg-surface hover:border-accent/50",
      )}
    >
      {icon && <span className="text-2xl leading-none">{icon}</span>}
      <span className="font-semibold text-ink">{title}</span>
      {desc && <span className="text-xs leading-snug text-muted">{desc}</span>}
      <span
        className={cx(
          "absolute right-2.5 top-2.5 grid h-5 w-5 place-items-center rounded-full border text-[11px] transition",
          selected ? "border-accent bg-accent text-accent-ink" : "border-line text-transparent",
        )}
        aria-hidden
      >
        ✓
      </span>
    </button>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap rounded-xl border border-line bg-surface-2 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cx(
            "rounded-lg px-4 py-1.5 text-sm font-medium transition-all",
            value === o.value ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function RangeField({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  display,
  hint,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  display?: ReactNode;
  hint?: ReactNode;
}) {
  const id = useId();
  const clamp = (v: number) => Math.min(max, Math.max(min, Math.round(v / step) * step));
  const fill = ((value - min) / (max - min)) * 100;
  return (
    <div className="space-y-2.5">
      <div className="flex items-end justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-muted">
          {label}
        </label>
        <div className="flex items-center gap-2">
          <StepButton label={`Decrease ${label}`} onClick={() => onChange(clamp(value - step))}>
            −
          </StepButton>
          <span className="min-w-[4.5rem] text-center font-display text-2xl font-semibold tabular-nums text-ink">
            {display ?? value}
          </span>
          <StepButton label={`Increase ${label}`} onClick={() => onChange(clamp(value + step))}>
            +
          </StepButton>
        </div>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ ["--fill" as string]: `${fill}%` }}
        className="w-full"
      />
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
  );
}

function StepButton({ children, onClick, label }: { children: ReactNode; onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="grid h-8 w-8 place-items-center rounded-full border border-line bg-surface text-lg text-ink transition hover:border-accent hover:text-accent active:scale-90"
    >
      {children}
    </button>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cx(
        "relative h-6 w-11 shrink-0 rounded-full transition-colors",
        checked ? "bg-leaf" : "bg-line",
      )}
    >
      <span
        className={cx(
          "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all",
          checked ? "left-[22px]" : "left-0.5",
        )}
      />
    </button>
  );
}

export function TagInput({
  values,
  onChange,
  placeholder,
}: {
  values: string[];
  onChange: (v: string[]) => void;
  placeholder: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 focus-within:border-accent">
      {values.map((v) => (
        <span key={v} className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2.5 py-1 text-sm">
          {v}
          <button
            type="button"
            aria-label={`Remove ${v}`}
            onClick={() => onChange(values.filter((x) => x !== v))}
            className="text-muted hover:text-chili"
          >
            ×
          </button>
        </span>
      ))}
      <input
        placeholder={values.length ? "" : placeholder}
        className="min-w-[10rem] flex-1 bg-transparent py-1 text-sm outline-none placeholder:text-muted"
        onKeyDown={(e) => {
          const el = e.currentTarget;
          const v = el.value.trim().replace(/,$/, "");
          if ((e.key === "Enter" || e.key === ",") && v) {
            e.preventDefault();
            if (!values.some((x) => x.toLowerCase() === v.toLowerCase())) onChange([...values, v]);
            el.value = "";
          } else if (e.key === "Backspace" && !el.value && values.length) {
            onChange(values.slice(0, -1));
          }
        }}
      />
    </div>
  );
}

/** Preset options as toggle chips, plus the user's own entries (stored as plain text alongside the preset keys). */
export function ChipsWithCustom({
  options,
  values,
  onChange,
  addLabel,
}: {
  options: Record<string, string>;
  values: string[];
  onChange: (v: string[]) => void;
  addLabel: string;
}) {
  const [draft, setDraft] = useState("");
  const custom = values.filter((v) => !(v in options));
  const add = () => {
    const v = draft.trim().slice(0, 40);
    const known = Object.entries(options).find(([, label]) => label.toLowerCase() === v.toLowerCase())?.[0];
    const value = known ?? v;
    if (value && !values.some((x) => x.toLowerCase() === value.toLowerCase())) onChange([...values, value]);
    setDraft("");
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      {Object.entries(options).map(([key, label]) => (
        <Chip key={key} selected={values.includes(key)} onClick={() => onChange(toggleIn(values, key))}>
          {label}
        </Chip>
      ))}
      {custom.map((v) => (
        <span key={v} className="inline-flex items-center gap-1.5 rounded-full border border-accent bg-accent px-3.5 py-1.5 text-sm text-accent-ink">
          ✓ {v}
          <button type="button" aria-label={`Remove ${v}`} onClick={() => onChange(values.filter((x) => x !== v))} className="opacity-80 hover:opacity-100">
            ×
          </button>
        </span>
      ))}
      <form
        className="inline-flex"
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => draft.trim() && add()}
          placeholder={`+ ${addLabel}`}
          aria-label={addLabel}
          maxLength={40}
          className="w-44 rounded-full border border-dashed border-line bg-transparent px-3.5 py-1.5 text-sm outline-none placeholder:text-muted focus:border-accent"
        />
      </form>
    </div>
  );
}

export function toggleIn<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}
