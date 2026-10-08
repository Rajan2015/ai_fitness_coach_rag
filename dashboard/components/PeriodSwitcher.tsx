"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";

const PERIODS = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
] as const;

export function PeriodSwitcher({ current }: { current: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  function setPeriod(period: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("period", period);
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="inline-flex border border-[#c9d8d1] bg-white p-1 shadow-sm">
      {PERIODS.map((p) => (
        <button
          key={p.value}
          type="button"
          onClick={() => setPeriod(p.value)}
          className={`px-3 py-1.5 text-sm font-semibold transition ${
            current === p.value
              ? "bg-[#063f3b] text-[#d7ff5f]"
              : "text-slate-500 hover:bg-[#e7f0ec] hover:text-[#063f3b]"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
