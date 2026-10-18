"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { usePlan } from "@/lib/store";
import { cx } from "./ui";

export function AppHeader() {
  const { result, generating, reset } = usePlan();
  const pathname = usePathname();
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!confirming) return;
    const t = setTimeout(() => setConfirming(false), 4000);
    return () => clearTimeout(t);
  }, [confirming]);

  const nav = [
    { href: "/", label: "Home", active: pathname === "/" },
    { href: "/plan/basics", label: "Questions", active: pathname.startsWith("/plan/") && pathname !== "/plan/result" },
    ...(result || generating ? [{ href: "/plan/result", label: generating ? "My plan…" : "My plan", active: pathname === "/plan/result" }] : []),
  ];

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-accent text-lg">🍲</span>
          <span className="font-display text-lg font-semibold leading-none">meal-planner</span>
        </Link>
        <nav className="ml-auto flex items-center gap-1 text-sm">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={cx("rounded-full px-3 py-1.5 transition", n.active ? "bg-surface-2 font-semibold text-ink" : "text-muted hover:text-ink")}
            >
              {n.label}
            </Link>
          ))}
          <button
            type="button"
            onClick={() => {
              if (!confirming) return setConfirming(true);
              reset();
              setConfirming(false);
              router.push("/plan/basics");
            }}
            className={cx(
              "ml-1 rounded-full border px-3 py-1.5 transition",
              confirming ? "border-chili bg-chili-soft text-chili" : "border-line text-muted hover:border-accent hover:text-ink",
            )}
          >
            {confirming ? "Clear everything?" : "Start over"}
          </button>
        </nav>
      </div>
    </header>
  );
}
