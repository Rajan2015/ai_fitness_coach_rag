import { NextResponse } from "next/server";
import { withAuth } from "next-auth/middleware";

// Dev-only escape hatch: DASHBOARD_SKIP_AUTH=true bypasses NextAuth entirely so the
// dashboard can be viewed locally without a WhatsApp OTP login (see requireSession.ts
// for the matching default-user lookup).
const skipAuth = process.env.DASHBOARD_SKIP_AUTH === "true";

export default skipAuth
  ? () => NextResponse.next()
  : withAuth({
      pages: { signIn: "/login" },
    });

export const config = {
  matcher: ["/((?!login|api/auth|_next/static|_next/image|favicon\\.ico).*)"],
};
