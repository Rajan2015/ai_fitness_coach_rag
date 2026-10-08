import { requireSession } from "@/lib/requireSession";
import { getScores, type Period } from "@/lib/queries";
import { PeriodSwitcher } from "@/components/PeriodSwitcher";
import { EmptyState } from "@/components/ui/EmptyState";
import { ScoreBreakdownChart } from "@/components/charts/ScoreBreakdownChart";

function parsePeriod(value?: string): Period {
  return value === "day" || value === "month" ? value : "week";
}

export default async function ScoresPage({
  searchParams,
}: {
  searchParams: Promise<{ period?: string }>;
}) {
  const user = await requireSession();
  const { period: rawPeriod } = await searchParams;
  const period = parsePeriod(rawPeriod);
  const scores = await getScores(user.id, period, user.timezone);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold tracking-[0.18em] text-brand">PERFORMANCE SIGNAL</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#102a28]">Know your numbers.</h1>
          <p className="mt-2 text-sm text-[#638076]">How each part of your day is scored.</p>
        </div>
        <PeriodSwitcher current={period} />
      </div>

      {scores.length === 0 ? (
        <EmptyState
          title="No scores yet"
          description="Scores are computed automatically from your logged food, workouts, water, and activity."
        />
      ) : (
        <div className="border border-[#d8e3dd] bg-white p-5 shadow-[0_8px_24px_rgba(6,63,59,0.06)]">
          <ScoreBreakdownChart data={scores} />
        </div>
      )}
    </div>
  );
}
