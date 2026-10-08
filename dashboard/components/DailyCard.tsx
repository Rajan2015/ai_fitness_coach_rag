import type { DailyCardData, DailyLogRow, DailyTargets } from "@/lib/queries";

function formatDateLabel(date: string): string {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function scoreBadgeClass(score: number | null): string {
  if (score === null) return "bg-slate-100 text-slate-400";
  if (score >= 80) return "bg-emerald-100 text-emerald-700";
  if (score >= 50) return "bg-amber-100 text-amber-700";
  return "bg-rose-100 text-rose-700";
}

function ItemList({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="mt-1.5 space-y-0.5">
      {items.map((item, index) => (
        <li key={index} className="truncate text-[11px] text-slate-500">
          {item}
        </li>
      ))}
    </ul>
  );
}

function MetricRow({
  label,
  actual,
  target,
  unit,
  barColor,
  items,
}: {
  label: string;
  actual: number;
  target: number | null;
  unit: string;
  barColor: string;
  items?: string[];
}) {
  const pct = target ? Math.min(100, Math.round((actual / target) * 100)) : null;
  const missing = target ? Math.max(0, Math.round(target - actual)) : null;

  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-medium text-slate-600">{label}</span>
        <span className="text-slate-400">
          {Math.round(actual).toLocaleString()}
          {unit}
          {target ? ` / ${Math.round(target).toLocaleString()}${unit}` : ""}
        </span>
      </div>
      {target && (
        <>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
          </div>
          {missing !== null && missing > 0 && (
            <p className="mt-0.5 text-[11px] text-slate-400">
              {missing.toLocaleString()}
              {unit} short of target
            </p>
          )}
        </>
      )}
      {items && <ItemList items={items} />}
    </div>
  );
}

export function DailyCard({
  data,
  targets,
  logs,
}: {
  data: DailyCardData;
  targets: DailyTargets;
  logs: DailyLogRow[];
}) {
  const foodItems = logs
    .filter((log) => log.logType === "food")
    .map((log) => `${log.description ?? "Food"}${log.quantity ? ` (${log.quantity})` : ""} — ${Math.round(log.calories ?? 0)} kcal`);

  const waterItems = logs
    .filter((log) => log.logType === "water")
    .map((log) => `${Math.round(log.waterMl ?? 0)} ml${log.quantity ? ` (${log.quantity})` : ""}`);

  const workoutItems = logs
    .filter((log) => log.logType === "workout")
    .map(
      (log) =>
        `${log.description ?? "Workout"}${log.durationMinutes ? ` — ${Math.round(log.durationMinutes)} min` : ""}`
    );
  const workoutHit = data.workoutCount > 0;

  return (
    <div className="border border-[#d8e3dd] bg-white p-5 shadow-[0_8px_24px_rgba(6,63,59,0.06)]">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[#102a28]">{formatDateLabel(data.date)}</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${scoreBadgeClass(data.overallScore)}`}>
          {data.overallScore !== null ? `${Math.round(data.overallScore)} pts` : "No score"}
        </span>
      </div>

      <div className="mt-4 space-y-3">
        <MetricRow
          label="Food logged"
          actual={data.calories}
          target={targets.calorieTarget}
          unit=" kcal"
          barColor="bg-orange-500"
          items={foodItems}
        />
        <MetricRow
          label="Water intake"
          actual={data.waterMl}
          target={targets.waterTarget}
          unit=" ml"
          barColor="bg-sky-500"
          items={waterItems}
        />
        <div>
          <div className="flex items-baseline justify-between text-xs">
            <span className="font-medium text-slate-600">Workout done</span>
            <span
              className={`rounded-full px-1.5 py-0.5 text-[11px] font-semibold ${
                workoutHit ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
              }`}
            >
              {workoutHit ? "Hit" : "Miss"}
            </span>
          </div>
          <ItemList items={workoutItems} />
        </div>
        <MetricRow
          label="Steps taken"
          actual={data.steps}
          target={targets.stepsTarget}
          unit=""
          barColor="bg-violet-500"
        />
      </div>
    </div>
  );
}

