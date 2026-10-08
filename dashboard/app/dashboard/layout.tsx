import Link from "next/link";

import { requireSession } from "@/lib/requireSession";
import { SignOutButton } from "@/components/SignOutButton";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/logs", label: "Logs" },
  { href: "/dashboard/scores", label: "Scores" },
  { href: "/dashboard/meal-plan", label: "Meal Plan" },
  { href: "/dashboard/workout-plan", label: "Workout Plan" },
];

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const user = await requireSession();

  return (
    <div className="flex min-h-screen flex-1 bg-[#f4f7f3]">
      <aside className="hidden w-64 flex-col bg-[#063f3b] p-6 text-white sm:flex">
        <div className="flex items-center gap-3 text-lg font-semibold tracking-tight">
          <span className="grid size-9 place-items-center rounded-full bg-[#d7ff5f] text-sm font-bold text-[#063f3b]">F</span>
          FitChat
        </div>
        <p className="mt-7 text-[10px] font-semibold tracking-[0.18em] text-[#d7ff5f]">YOUR DAILY EDGE</p>
        <nav className="mt-3 flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="border-l-2 border-transparent px-3 py-2.5 text-sm font-medium text-white/65 transition hover:border-[#d7ff5f] hover:bg-white/10 hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto border-t border-white/15 pt-6">
          <p className="text-[10px] font-semibold tracking-[0.15em] text-[#d7ff5f]">ATHLETE PROFILE</p>
          <p className="mt-2 truncate text-sm text-white/75">{user.name ?? "Your FitChat"}</p>
          <SignOutButton />
        </div>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between bg-[#063f3b] px-6 py-4 text-white sm:hidden">
          <div className="flex items-center gap-2 text-lg font-semibold tracking-tight"><span className="grid size-8 place-items-center rounded-full bg-[#d7ff5f] text-xs text-[#063f3b]">F</span> FitChat</div>
          <SignOutButton />
        </header>
        <main className="flex-1 p-5 sm:p-8 lg:p-10">{children}</main>
      </div>
    </div>
  );
}
