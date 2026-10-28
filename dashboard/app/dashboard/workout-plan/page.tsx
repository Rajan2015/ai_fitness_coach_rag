import { requireSession } from "@/lib/requireSession";
import { getWorkoutPlans, type WorkoutPlanRecord } from "@/lib/queries";
import { EmptyState } from "@/components/ui/EmptyState";
import { WorkoutDayCard } from "@/components/WorkoutDayCard";
import { ArchiveIcon, CheckCircleIcon, ClockIcon } from "@/components/ui/KpiIcons";

function formatDate(value: string | null): string {
  if (!value) return "Not approved yet";
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function goalLabel(goal: string): string {
  if (goal === "lose") return "Fat loss";
  if (goal === "gain") return "Muscle gain";
  return "General fitness";
}

function ArchivedPlanRow({ plan }: { plan: WorkoutPlanRecord }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#eef2ef] py-3 first:border-t-0 first:pt-0">
      <div>
        <p className="text-sm font-semibold text-[#102a28]">{plan.title}</p>
        <p className="text-xs text-[#638076]">
          {goalLabel(plan.goalType)} · {plan.plan.days.length} day{plan.plan.days.length === 1 ? "" : "s"}/week
        </p>
      </div>
      <span className="inline-flex items-center gap-1 rounded-full bg-[#f0f4f1] px-2.5 py-1 text-xs font-semibold text-[#638076]">
        <ArchiveIcon className="h-3.5 w-3.5" />
        Approved {formatDate(plan.approvedAt)}
      </span>
    </div>
  );
}

export default async function WorkoutPlanPage() {
  const user = await requireSession();
  const plans = await getWorkoutPlans(user.id);
  const activePlan = plans.find((plan) => plan.status === "active");
  const archivedPlans = plans.filter((plan) => plan.status !== "active");

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[10px] font-semibold tracking-[0.18em] text-brand">SHOW UP STRONG</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#102a28]">Your workout plan.</h1>
        <p className="mt-2 text-sm text-[#638076]">Your active, coach-approved training split.</p>
      </div>

      {!activePlan ? (
        <EmptyState
          title="No active workout plan yet"
          description="Ask your WhatsApp coach for a workout plan and approve it to see it here."
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-4 border border-[#d8e3dd] bg-white p-5 shadow-[0_8px_24px_rgba(6,63,59,0.06)]">
            <div>
              <h2 className="text-lg font-semibold text-[#102a28]">{activePlan.title}</h2>
              <p className="mt-1 text-sm text-[#638076]">
                {goalLabel(activePlan.goalType)} · {activePlan.plan.days.length} day
                {activePlan.plan.days.length === 1 ? "" : "s"}/week
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
                <CheckCircleIcon className="h-3.5 w-3.5" />
                Active
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f0f4f1] px-3 py-1 text-xs font-semibold text-[#063f3b]">
                <ClockIcon className="h-3.5 w-3.5" />
                Approved {formatDate(activePlan.approvedAt)}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {activePlan.plan.days.map((day, index) => (
              <WorkoutDayCard key={`${day.day}-${index}`} day={day} />
            ))}
          </div>

          {(activePlan.plan.progressionRule || activePlan.plan.safetyNote) && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {activePlan.plan.progressionRule && (
                <div className="border border-[#d8e3dd] bg-white p-5 shadow-[0_8px_24px_rgba(6,63,59,0.06)]">
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-brand">Progression</p>
                  <p className="mt-2 text-sm text-[#102a28]">{activePlan.plan.progressionRule}</p>
                </div>
              )}
              {activePlan.plan.safetyNote && (
                <div className="border border-[#d8e3dd] bg-white p-5 shadow-[0_8px_24px_rgba(6,63,59,0.06)]">
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-brand">Safety note</p>
                  <p className="mt-2 text-sm text-[#102a28]">{activePlan.plan.safetyNote}</p>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {archivedPlans.length > 0 && (
        <div className="border border-[#d8e3dd] bg-white p-5 shadow-[0_8px_24px_rgba(6,63,59,0.06)]">
          <p className="text-xs font-semibold uppercase tracking-[0.1em] text-brand">Plan history</p>
          <div className="mt-1">
            {archivedPlans.map((plan) => (
              <ArchivedPlanRow key={plan.id} plan={plan} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
