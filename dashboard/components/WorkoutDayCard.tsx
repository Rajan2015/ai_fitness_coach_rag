import type { WorkoutExerciseType, WorkoutPlanDay } from "@/lib/queries";
import { estimateDayMinutes } from "@/lib/queries";
import { ClockIcon, DumbbellIcon, LeafIcon, TargetIcon } from "@/components/ui/KpiIcons";

const EXERCISE_TYPE_META: Record<
  WorkoutExerciseType,
  { label: string; icon: React.ReactNode; badgeClass: string }
> = {
  warm_up: {
    label: "Warm-up",
    icon: <LeafIcon className="h-3.5 w-3.5" />,
    badgeClass: "bg-amber-50 text-amber-600",
  },
  main: {
    label: "Main set",
    icon: <TargetIcon className="h-3.5 w-3.5" />,
    badgeClass: "bg-violet-50 text-violet-600",
  },
  cool_down: {
    label: "Cool-down",
    icon: <LeafIcon className="h-3.5 w-3.5" />,
    badgeClass: "bg-sky-50 text-sky-600",
  },
};

function ExerciseRow({
  exerciseId,
  name,
  exerciseType,
  sets,
  reps,
  restSeconds,
  notes,
  imageUrl,
}: {
  exerciseId: string;
  name: string;
  exerciseType: WorkoutExerciseType;
  sets: number;
  reps: string;
  restSeconds: number;
  notes: string | null;
  imageUrl: string | null;
}) {
  const meta = EXERCISE_TYPE_META[exerciseType];

  return (
    <li key={exerciseId} className="flex gap-3 border-t border-[#eef2ef] py-3 first:border-t-0 first:pt-0">
      {imageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={imageUrl} alt={name} className="h-12 w-12 flex-none rounded-lg object-cover" />
      ) : (
        <div className="grid h-12 w-12 flex-none place-items-center rounded-lg bg-[#f0f4f1] text-[#063f3b]">
          <DumbbellIcon className="h-5 w-5" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate text-sm font-semibold text-[#102a28]">{name}</p>
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${meta.badgeClass}`}>
            {meta.icon}
            {meta.label}
          </span>
        </div>
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[#638076]">
          <span>
            <strong className="font-semibold text-[#102a28]">{sets}</strong> sets
          </span>
          <span>
            <strong className="font-semibold text-[#102a28]">{reps}</strong> reps
          </span>
          <span className="inline-flex items-center gap-1">
            <ClockIcon className="h-3.5 w-3.5" />
            {restSeconds}s rest
          </span>
        </div>
        {notes && <p className="mt-1 text-xs italic text-[#638076]">{notes}</p>}
      </div>
    </li>
  );
}

export function WorkoutDayCard({ day }: { day: WorkoutPlanDay }) {
  const minutes = estimateDayMinutes(day);

  return (
    <div className="border border-[#d8e3dd] bg-white p-5 shadow-[0_8px_24px_rgba(6,63,59,0.06)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold tracking-[0.1em] text-brand uppercase">{day.day}</h3>
          <p className="mt-1 text-base font-semibold text-[#102a28]">{day.focus}</p>
        </div>
        <span className="inline-flex flex-none items-center gap-1 rounded-full bg-[#f0f4f1] px-2.5 py-1 text-xs font-semibold text-[#063f3b]">
          <ClockIcon className="h-3.5 w-3.5" />
          {minutes} min
        </span>
      </div>

      <ul className="mt-3">
        {day.exercises.map((exercise, index) => (
          <ExerciseRow key={`${exercise.exerciseId}-${index}`} {...exercise} />
        ))}
      </ul>
    </div>
  );
}
