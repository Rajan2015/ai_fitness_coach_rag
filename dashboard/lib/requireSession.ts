import { createHash } from "crypto";
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { authOptions } from "./auth";
import { getUserByPhoneHash, type DashboardUser } from "./queries";

// Must match ai_fitness_coach_rag/agent/tools/onboarding_tools.py::hash_phone.
function hashPhone(phoneNumber: string): string {
  return createHash("sha256").update(phoneNumber.trim()).digest("hex");
}

/** Resolves the logged-in NextAuth session to the user's DB row, scoping all reads. */
export async function requireSession(): Promise<DashboardUser> {
  if (process.env.DASHBOARD_SKIP_AUTH === "true") {
    const devPhoneNumber = process.env.DASHBOARD_DEV_PHONE_NUMBER;
    if (!devPhoneNumber) {
      throw new Error("DASHBOARD_SKIP_AUTH is true but DASHBOARD_DEV_PHONE_NUMBER is not set");
    }
    const user = await getUserByPhoneHash(hashPhone(devPhoneNumber));
    if (!user) {
      throw new Error(`No user found for DASHBOARD_DEV_PHONE_NUMBER=${devPhoneNumber}`);
    }
    return user;
  }

  const session = await getServerSession(authOptions);
  const phoneHash = session?.user?.phoneHash;
  if (!phoneHash) {
    redirect("/login");
  }

  const user = await getUserByPhoneHash(phoneHash);
  if (!user) {
    redirect("/login");
  }

  return user;
}
