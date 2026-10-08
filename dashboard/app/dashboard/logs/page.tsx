import { requireSession } from "@/lib/requireSession";
import { getLogs, type DailyLogRow, type Period } from "@/lib/queries";
import { PeriodSwitcher } from "@/components/PeriodSwitcher";
import { EmptyState } from "@/components/ui/EmptyState";

function parsePeriod(value?: string): Period {
  return value === "day" || value === "month" ? value : "week";
}

const LOG_TYPE_LABELS: Record<string, string> = {
  food: "Food",
  workout: "Workout",
  metric: "Metric",
  water: "Water",
};

function logDetails(log: DailyLogRow): string {
  switch (log.logType) {
    case "food":
      return (
        [
          log.calories != null ? `${Math.round(log.calories)} kcal` : null,
          log.proteinG != null ? `${Math.round(log.proteinG)}g protein` : null,
        ]
          .filter(Boolean)
          .join(" · ") || "—"
      );
    case "workout":
      return (
        [
          log.durationMinutes != null ? `${Math.round(log.durationMinutes)} min` : null,
          log.caloriesBurned != null ? `${Math.round(log.caloriesBurned)} kcal burned` : null,
        ]
          .filter(Boolean)
          .join(" · ") || "—"
      );
    case "water":
      return log.waterMl != null ? `${Math.round(log.waterMl)} ml` : "—";
    case "metric":
      return log.metricName && log.metricValue != null
        ? `${log.metricName}: ${log.metricValue}`
        : "—";
    default:
      return "—";
  }
}

export default async function LogsPage({
  searchParams,
}: {
  searchParams: Promise<{ period?: string; type?: string }>;
}) {
  const user = await requireSession();
  const { period: rawPeriod, type } = await searchParams;
  const period = parsePeriod(rawPeriod);
  const logs = await getLogs(user.id, period, user.timezone, type);
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold tracking-[0.18em] text-brand">THE RECEIPTS</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#102a28]">Every rep counts.</h1>
          <p className="mt-2 text-sm text-[#638076]">Everything you&apos;ve logged over WhatsApp.</p>
        </div>
        <PeriodSwitcher current={period} />
      </div>

      {logs.length === 0 ? (
        <EmptyState
          title="No logs for this period"
          description="Log food, workouts, water, or metrics with the WhatsApp bot to see them here."
        />
      ) : (
        <div className="overflow-hidden border border-[#d8e3dd] bg-white shadow-[0_8px_24px_rgba(6,63,59,0.06)]">
          <table className="min-w-full divide-y divide-[#d8e3dd] text-sm">
            <thead className="bg-[#e7f0ec] text-left text-[10px] font-semibold uppercase tracking-[0.14em] text-[#638076]">
              <tr>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Description</th>
                <th className="px-4 py-3">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#edf2ef]">
              {logs.map((log) => (
                <tr key={log.id}>
                  <td className="px-4 py-3 whitespace-nowrap text-slate-500">{log.logDate}</td>
                  <td className="px-4 py-3 whitespace-nowrap font-semibold text-[#102a28]">
                    {LOG_TYPE_LABELS[log.logType] ?? log.logType}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{log.description ?? "—"}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-slate-500">
                    {logDetails(log)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
