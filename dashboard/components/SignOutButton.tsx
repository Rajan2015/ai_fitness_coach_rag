"use client";

import { signOut } from "next-auth/react";

export function SignOutButton() {
  return (
    <button
      type="button"
      onClick={() => signOut({ callbackUrl: "/login" })}
      className="mt-3 border border-white/25 px-3 py-2 text-xs font-semibold text-white/80 transition hover:border-[#d7ff5f] hover:bg-white/10 hover:text-[#d7ff5f]"
    >
      Sign out
    </button>
  );
}
