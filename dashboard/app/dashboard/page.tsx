import { requireSession } from "@/lib/requireSession";
import {
  getDailyCards,
  getLogs,
  groupLogsByDate,
  calculateDailyTargets,
  windowDays,
  type Period,
} from "@/lib/queries";
import { PeriodSwitcher } from "@/components/PeriodSwitcher";
import { DailyCard } from "@/components/DailyCard";
import { KpiCard } from "@/components/ui/KpiCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { FlameIcon, DumbbellIcon, DropletIcon, FootprintsIcon, StarIcon } from "@/components/ui/KpiIcons";

function parsePeriod(value?: string): Period {
  return value === "day" || value === "month" ? value : "week";
}

export default async function OverviewPage({
  searchParams,
}: {
  searchParams: Promise<{ period?: string }>;
}) {
  const user = await requireSession();
  const { period: rawPeriod } = await searchParams;
  const period = parsePeriod(rawPeriod);
  const targets = calculateDailyTargets(user);

  const [cards, logs] = await Promise.all([
    getDailyCards(user.id, period, user.timezone),
    getLogs(user.id, period, user.timezone),
  ]);
  const logsByDate = groupLogsByDate(logs);

  const days = windowDays(period);
  const totalCalories = cards.reduce((sum, card) => sum + card.calories, 0);
  const totalWaterMl = cards.reduce((sum, card) => sum + card.waterMl, 0);
  const totalSteps = cards.reduce((sum, card) => sum + card.steps, 0);
  const totalWorkoutMinutes = cards.reduce((sum, card) => sum + card.workoutMinutes, 0);
  const workoutDays = cards.filter((card) => card.workoutCount > 0).length;
  const avgWorkoutMinutes = workoutDays > 0 ? Math.round(totalWorkoutMinutes / workoutDays) : 0;
  const scoredDays = cards.filter((card) => card.overallScore !== null);
  const avgScore =
    scoredDays.length > 0
      ? Math.round(scoredDays.reduce((sum, card) => sum + (card.overallScore ?? 0), 0) / scoredDays.length)
      : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold tracking-[0.18em] text-brand">DAILY TRAINING LOG</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#102a28]">Your momentum, mapped.</h1>
          <p className="mt-2 text-sm text-[#638076]">The habits behind your progress, all in one place.</p>
        </div>
        <PeriodSwitcher current={period} />
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <KpiCard
          label="Avg calories/day"
          value={Math.round(totalCalories / days).toLocaleString()}
          icon={<FlameIcon />}
          accentClassName="bg-orange-50 text-orange-500"
        />
        <KpiCard
          label="Workout days"
          value={`${workoutDays} / ${days}`}
          icon={<DumbbellIcon />}
          accentClassName="bg-violet-50 text-violet-500"
        />
        <KpiCard
          label="Avg workout min/day worked out"
          value={avgWorkoutMinutes.toLocaleString()}
          icon={<DumbbellIcon />}
          accentClassName="bg-violet-50 text-violet-500"
        />
        <KpiCard
          label="Avg water/day"
          value={`${Math.round(totalWaterMl / days).toLocaleString()} ml`}
          icon={<DropletIcon />}
          accentClassName="bg-sky-50 text-sky-500"
        />
        <KpiCard
          label="Avg steps/day"
          value={Math.round(totalSteps / days).toLocaleString()}
          icon={<FootprintsIcon />}
          accentClassName="bg-emerald-50 text-emerald-500"
        />
        <KpiCard
          label="Avg score"
          value={avgScore !== null ? avgScore.toLocaleString() : "—"}
          icon={<StarIcon />}
          accentClassName="bg-amber-50 text-amber-500"
        />
      </div>

      {cards.length === 0 ? (
        <EmptyState
          title="No activity logged yet"
          description="Log food, water, workouts, and steps on WhatsApp to see your daily breakdown here."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {cards.map((card) => (
            <DailyCard
              key={card.date}
              data={card}
              targets={targets}
              logs={logsByDate.get(card.date) ?? []}
            />
          ))}
        </div>
      )}
    </div>
  );
}


