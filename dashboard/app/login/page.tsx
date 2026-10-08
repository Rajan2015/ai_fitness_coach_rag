"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";

const API_BASE = (process.env.NEXT_PUBLIC_DASHBOARD_API_BASE ?? "http://localhost:8000").replace(
  /\/+$/,
  ""
);

export default function LoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRequestOtp(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await fetch(`${API_BASE}/api/dashboard/auth/request-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: phoneNumber }),
      });
      setStep("code");
    } catch {
      setError("Could not reach the server. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    const result = await signIn("credentials", {
      phone_number: phoneNumber,
      code,
      redirect: false,
    });
    setLoading(false);
    if (result?.error) {
      setError("Invalid or expired code. Please try again.");
      return;
    }
    router.push("/dashboard");
  }

  return (
    <main className="min-h-screen bg-[#f4f7f3] p-3 sm:p-5">
      <div className="grid min-h-[calc(100vh-1.5rem)] overflow-hidden border border-slate-200 bg-white shadow-2xl shadow-slate-900/10 sm:min-h-[calc(100vh-2.5rem)] lg:grid-cols-[1.12fr_0.88fr]">
        <section className="relative hidden min-h-full overflow-hidden bg-[#063f3b] p-10 text-white lg:flex lg:flex-col xl:p-14">
          <div
            className="absolute inset-0 bg-cover bg-center opacity-70"
            style={{
              backgroundImage:
                "url('https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1600&q=85')",
            }}
          />
          <div className="absolute inset-0 bg-[linear-gradient(125deg,rgba(1,30,29,0.96)_10%,rgba(3,65,60,0.66)_58%,rgba(14,116,108,0.2)_100%)]" />

          <div className="relative flex items-center gap-3 text-lg font-semibold tracking-tight">
            <span className="grid size-9 place-items-center rounded-full bg-[#d7ff5f] text-sm font-bold text-[#063f3b]">F</span>
            FitChat
          </div>

          <div className="relative my-auto max-w-xl pt-20">
            <p className="mb-5 text-xs font-semibold tracking-[0.18em] text-[#d7ff5f]">COACHING THAT MEETS YOU MID-SET</p>
            <h1 className="max-w-lg text-5xl font-semibold leading-[0.98] tracking-tight xl:text-6xl">
              Train with purpose. Live with momentum.
            </h1>
            <p className="mt-6 max-w-md text-base leading-7 text-white/80">
              Your WhatsApp check-ins become a clearer view of your training, nutrition, and the progress you are building every day.
            </p>
          </div>

          <div className="relative grid grid-cols-3 gap-3 border-t border-white/25 pt-7 text-sm">
            <div><p className="text-2xl font-semibold text-[#d7ff5f]">01</p><p className="mt-1 text-white/75">Log the work</p></div>
            <div><p className="text-2xl font-semibold text-[#d7ff5f]">02</p><p className="mt-1 text-white/75">See the signal</p></div>
            <div><p className="text-2xl font-semibold text-[#d7ff5f]">03</p><p className="mt-1 text-white/75">Keep moving</p></div>
          </div>
        </section>

        <section className="relative flex min-h-[calc(100vh-1.5rem)] items-center justify-center px-5 py-10 sm:px-10 lg:min-h-full lg:px-16 xl:px-24">
          <div className="absolute inset-x-0 top-0 h-2 bg-[#d7ff5f] lg:hidden" />
          <div className="w-full max-w-md">
            <div className="mb-12 flex items-center justify-between lg:hidden">
              <div className="flex items-center gap-2 font-semibold text-[#063f3b]"><span className="grid size-8 place-items-center rounded-full bg-[#063f3b] text-xs text-[#d7ff5f]">F</span> FitChat</div>
              <span className="text-xs font-medium text-slate-400">YOUR DAILY EDGE</span>
            </div>
            <p className="text-xs font-semibold tracking-[0.18em] text-brand">MEMBER ACCESS</p>
            <h2 className="mt-4 text-4xl font-semibold tracking-tight text-[#102a28]">
              {step === "phone" ? "Pick up where you left off." : "One step from your dashboard."}
            </h2>
            <p className="mt-4 max-w-sm text-base leading-7 text-slate-500">
              {step === "phone"
                ? "Use the WhatsApp number you used when you joined FitChat (e.g. +91 98765 43210)."
                : `We sent a six-digit code to ${phoneNumber}.`}
            </p>

            {step === "phone" ? (
              <form onSubmit={handleRequestOtp} className="mt-9 space-y-5">
                <div>
                  <label className="block text-sm font-semibold text-[#102a28]">Phone number</label>
                  <input
                    type="tel"
                    required
                    autoComplete="tel"
                    placeholder="+91 99XXX XXXXX"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    className="mt-2 w-full border border-slate-300 bg-slate-50 px-4 py-3.5 text-base text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-brand focus:bg-white focus:ring-2 focus:ring-brand/15"
                  />
                </div>
                {error && <p className="border-l-2 border-red-500 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-brand px-4 py-3.5 text-sm font-semibold text-white transition hover:bg-brand-dark focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loading ? "Sending your code..." : "Send login code"}
                </button>
              </form>
            ) : (
              <form onSubmit={handleVerify} className="mt-9 space-y-5">
                <div>
                  <label className="block text-sm font-semibold text-[#102a28]">6-digit code</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    required
                    maxLength={6}
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    className="mt-2 w-full border border-slate-300 bg-slate-50 px-4 py-3.5 text-center text-lg font-semibold tracking-[0.35em] text-slate-900 outline-none transition focus:border-brand focus:bg-white focus:ring-2 focus:ring-brand/15"
                  />
                </div>
                {error && <p className="border-l-2 border-red-500 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-brand px-4 py-3.5 text-sm font-semibold text-white transition hover:bg-brand-dark focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loading ? "Verifying..." : "Verify and sign in"}
                </button>
                <button
                  type="button"
                  onClick={() => setStep("phone")}
                  className="w-full py-2 text-sm font-medium text-slate-500 underline decoration-slate-300 underline-offset-4 transition hover:text-brand"
                >
                  Use a different number
                </button>
              </form>
            )}

            <p className="mt-10 text-xs leading-5 text-slate-400">Your progress stays private and linked only to your registered number.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
