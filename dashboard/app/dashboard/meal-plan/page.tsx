import ReactMarkdown from "react-markdown";

import { requireSession } from "@/lib/requireSession";
import { getPlans } from "@/lib/queries";
import { EmptyState } from "@/components/ui/EmptyState";

export default async function MealPlanPage() {
  const user = await requireSession();
  const plans = await getPlans(user.id, "meal");
  const latest = plans[0];

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[10px] font-semibold tracking-[0.18em] text-brand">FUEL WITH INTENT</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#102a28]">Your meal plan.</h1>
        <p className="mt-2 text-sm text-[#638076]">Your most recently generated meal plan.</p>
      </div>

      {!latest ? (
        <EmptyState
          title="No meal plan yet"
          description="Ask your WhatsApp coach for a meal plan and it will show up here."
        />
      ) : (
        <article className="markdown-body border border-[#d8e3dd] bg-white p-6 shadow-[0_8px_24px_rgba(6,63,59,0.06)]">
          <ReactMarkdown>{latest.content}</ReactMarkdown>
        </article>
      )}
    </div>
  );
}
