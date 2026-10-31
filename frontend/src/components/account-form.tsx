"use client";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { ApiClient } from "@/lib/api";
import { Brand } from "./brand";
import { Button, Notice } from "./ui";
export function AccountForm({ mode }: { mode: "signup" | "forgot" | "reset" }) {
  const search = useSearchParams();
  const [api] = useState(
    () =>
      new ApiClient(
        process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api/v1",
      ),
  );
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [company, setCompany] = useState(""),
    [contact, setContact] = useState("");
  const [token, setToken] = useState(() => search.get("token") || "");
  const [notice, setNotice] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (mode === "reset" && search.has("token"))
      window.history.replaceState(null, "", "/reset-password");
  }, [mode, search]);
  const title =
    mode === "signup"
      ? "Create customer account"
      : mode === "forgot"
        ? "Request password reset"
        : "Reset password";
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (mode === "signup") {
        await api.request("/auth/signup", {
          method: "POST",
          public: true,
          body: {
            email,
            password,
            company_name: company,
            contact_name: contact,
          },
        });
        setNotice("Customer account created. You can now sign in.");
      } else if (mode === "forgot") {
        const result = await api.request<{ message: string }>(
          "/auth/password-reset/request",
          { method: "POST", public: true, body: { email } },
        );
        setNotice(result.message);
      } else {
        const result = await api.request<{ message: string }>(
          "/auth/password-reset/confirm",
          {
            method: "POST",
            public: true,
            body: { token, new_password: password },
          },
        );
        setNotice(result.message);
        setToken("");
      }
      setPassword("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <Brand large />
        <div className="login-story-copy">
          <h1>
            Your account.
            <br />
            <span>In cadence.</span>
          </h1>
          <p>Manage customer access to SubCadence.</p>
        </div>
      </section>
      <section className="login-form-wrap">
        <div className="login-form">
          <h1>{title}</h1>
          {notice && <Notice kind="success">{notice}</Notice>}
          {error && <Notice>{error}</Notice>}
          <form onSubmit={submit}>
            {mode !== "reset" && (
              <label className="field">
                Email address
                <input
                  required
                  type="email"
                  autoComplete="email"
                  maxLength={320}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
            )}
            {mode === "signup" && (
              <>
                <label className="field">
                  Company name
                  <input
                    required
                    maxLength={200}
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                  />
                </label>
                <label className="field">
                  Contact name
                  <input
                    required
                    maxLength={200}
                    value={contact}
                    onChange={(e) => setContact(e.target.value)}
                  />
                </label>
              </>
            )}
            {mode === "reset" && (
              <label className="field">
                Reset token
                <input
                  required
                  type="password"
                  autoComplete="off"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                />
              </label>
            )}
            {mode !== "forgot" && (
              <>
                <label className="field">
                  New password
                  <input
                    required
                    type="password"
                    minLength={9}
                    maxLength={128}
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </label>
                <p className="text-xs">
                  Use 9–128 characters, uppercase, lowercase and a special
                  character.
                </p>
              </>
            )}
            <Button disabled={busy} variant="primary">
              {busy ? "Submitting…" : title}
            </Button>
          </form>
          <Link className="subtle-link" href="/login">
            Back to sign in
          </Link>
        </div>
      </section>
    </main>
  );
}
