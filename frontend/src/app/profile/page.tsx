"use client";
import { useCallback, useState, type FormEvent } from "react";
import { Shell } from "@/components/shell";
import { useAuth } from "@/components/auth-provider";
import { useResource } from "@/lib/hooks";
import { Button, Loading, Notice, PageHeader, Panel } from "@/components/ui";
import type { Customer } from "@/lib/types";
export default function Page() {
  return (
    <Shell>
      <Profile />
    </Shell>
  );
}
function Profile() {
  const { api, user } = useAuth();
  const resource = useResource(
    useCallback(
      async (signal) =>
        user?.role === "customer"
          ? (await api.customers({ limit: 1 }, signal)).items[0]
          : null,
      [api, user?.role],
    ),
  );
  return (
    <div className="stack">
      <PageHeader
        title="My Profile"
        description="Your account and customer contact details."
      />
      <p>
        {user?.email} · {user?.role}
      </p>
      {resource.loading ? (
        <Loading />
      ) : resource.error ? (
        <Notice>{resource.error}</Notice>
      ) : resource.data ? (
        <Edit key={resource.data.id} customer={resource.data} />
      ) : (
        <p>Customer profile editing is available to customer accounts.</p>
      )}
    </div>
  );
}
function Edit({ customer }: { customer: Customer }) {
  const { api } = useAuth();
  const [company, setCompany] = useState(customer.company_name),
    [contact, setContact] = useState(customer.contact_name),
    [phone, setPhone] = useState(customer.phone || ""),
    [notice, setNotice] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.request(`/customers/${customer.id}`, {
        method: "PATCH",
        body: {
          company_name: company,
          contact_name: contact,
          phone: phone || null,
        },
      });
      setNotice("Profile saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel title="Contact Details">
      <form onSubmit={save} className="panel-body stack">
        <label className="field">
          Company name
          <input
            required
            value={company}
            onChange={(e) => setCompany(e.target.value)}
          />
        </label>
        <label className="field">
          Contact name
          <input
            required
            value={contact}
            onChange={(e) => setContact(e.target.value)}
          />
        </label>
        <label className="field">
          Phone
          <input
            maxLength={50}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </label>
        {notice && <Notice kind="success">{notice}</Notice>}
        {error && <Notice>{error}</Notice>}
        <Button disabled={busy} variant="primary">
          {busy ? "Saving…" : "Save profile"}
        </Button>
      </form>
    </Panel>
  );
}
