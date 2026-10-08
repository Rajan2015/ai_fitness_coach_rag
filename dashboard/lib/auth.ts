import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

const API_BASE = (process.env.DASHBOARD_API_BASE ?? "http://localhost:8000").replace(/\/+$/, "");

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "WhatsApp OTP",
      credentials: {
        phone_number: { label: "Phone number", type: "text" },
        code: { label: "Code", type: "text" },
      },
      async authorize(credentials) {
        if (!credentials?.phone_number || !credentials?.code) return null;

        const res = await fetch(`${API_BASE}/api/dashboard/auth/verify-otp`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            phone_number: credentials.phone_number,
            code: credentials.code,
          }),
        });
        if (!res.ok) return null;

        const data = (await res.json()) as { phone_hash: string; name: string | null };
        return {
          id: data.phone_hash,
          name: data.name ?? data.phone_hash,
          phoneHash: data.phone_hash,
        };
      },
    }),
  ],
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.phoneHash = (user as { phoneHash: string }).phoneHash;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.phoneHash = token.phoneHash as string;
      }
      return session;
    },
  },
};
