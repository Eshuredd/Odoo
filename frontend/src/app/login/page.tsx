"use client";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Layers, ShieldCheck } from "lucide-react";
import { Brand } from "@/components/brand";
import { useAuth } from "@/components/auth-provider";
import { Button, Notice } from "@/components/ui";

export default function Login() {
  const { user, login, notice } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      setPassword("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign in failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <Brand large />
        <div className="login-story-copy">
          <span className="pill">YOUR SUBSCRIPTION WORKSPACE</span>
          <h1>
            Every subscription.
            <br />
            <span>In cadence.</span>
          </h1>
          <p>
            Bring your customer agreements, recurring plans, and subscription
            lifecycle into one clear view.
          </p>
          <div className="login-flow">
            <span>Draft</span>
            <i />
            <span>Quotation</span>
            <i />
            <span>Active</span>
          </div>
        </div>
        <div className="login-story-footer">
          <Layers size={18} />
          One workspace. Clear commercial terms.
        </div>
      </section>
      <section className="login-form-wrap">
        <div className="login-form">
          <div className="login-icon">
            <ShieldCheck size={25} />
          </div>
          <div className="eyebrow">WELCOME TO SUBCADENCE</div>
          <h2>Sign in to your workspace</h2>
          <p>Use the account provided by your administrator.</p>
          {notice && <Notice kind="info">{notice}</Notice>}
          {error && <Notice>{error}</Notice>}
          <form onSubmit={submit}>
            <label className="field">
              Email address
              <input
                aria-label="Email address"
                type="email"
                autoComplete="username"
                required
                maxLength={320}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@company.com"
              />
            </label>
            <label className="field">
              Password
              <input
                aria-label="Password"
                type="password"
                autoComplete="current-password"
                required
                maxLength={128}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
              />
            </label>
            <Button type="submit" variant="primary" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
              <ArrowRight size={16} />
            </Button>
          </form>
          <p className="login-help">
            <Link href="/signup">Create a customer account</Link> ·{" "}
            <Link href="/forgot-password">Forgot password?</Link>
          </p>
          <div className="login-security">
            <ShieldCheck size={14} />
            Sessions expire after two hours. Refreshing signs you out.
          </div>
          <Link className="subtle-link" href="/dashboard">
            Back to workspace
          </Link>
        </div>
      </section>
    </main>
  );
}
