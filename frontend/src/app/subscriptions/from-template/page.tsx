"use client";
import { useCallback, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/shell";
import { useAuth } from "@/components/auth-provider";
import { RemoteSelect } from "@/components/remote-select";
import { Button, Notice, PageHeader, Panel } from "@/components/ui";
import type { Customer, Page as PageType, Subscription } from "@/lib/types";
import { todayInIndia } from "@/lib/format";
interface Template {
  id: number;
  name: string;
  validity_days: number;
  plan_id: number;
}
export default function Page() {
  return (
    <Shell operatorOnly>
      <FromTemplate />
    </Shell>
  );
}
function FromTemplate() {
  const { api } = useAuth();
  const router = useRouter();
  const [selection, setSelection] = useState<{
    customer: Customer | null;
    template: Template | null;
  }>({ customer: null, template: null });
  const { customer, template } = selection;
  const [asOf, setAsOf] = useState(todayInIndia),
    [start, setStart] = useState(todayInIndia),
    [expiry, setExpiry] = useState(""),
    [days, setDays] = useState("15"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const loadCustomers = useCallback(
    (search: string, offset: number, signal: AbortSignal) =>
      api.customers({ search, offset, limit: 10 }, signal),
    [api],
  );
  const loadTemplates = useCallback(
    (search: string, offset: number, signal: AbortSignal) =>
      api.request<PageType<Template>>(
        `/quotation-templates?active=true&limit=10&offset=${offset}&search=${encodeURIComponent(search)}`,
        { signal },
      ),
    [api],
  );
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!customer || !template) {
      setError("Select a customer and quotation template.");
      return;
    }
    setBusy(true);
    try {
      const row = await api.request<Subscription>(
        "/subscriptions/from-template",
        {
          method: "POST",
          body: {
            customer_id: customer.id,
            template_id: template.id,
            start_date: start,
            expiry_date: expiry,
            payment_terms_days: Number(days),
            as_of: asOf,
          },
        },
      );
      router.push(`/subscriptions/${row.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Creation failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack">
      <PageHeader
        title="Create from Quotation Template"
        description="Copy a template into an independent quotation. Accepted terms remain frozen at confirmation."
      />
      <Panel title="Quotation Details">
        <form onSubmit={submit} className="panel-body stack">
          <RemoteSelect
            key="customer"
            label="Customer"
            value={customer}
            onChange={(value) =>
              setSelection((current) => ({ ...current, customer: value }))
            }
            load={loadCustomers}
            describe={(row) => row.company_name || row.contact_name}
          />
          <RemoteSelect
            key="template"
            label="Quotation template"
            value={template}
            onChange={(value) =>
              setSelection((current) => ({ ...current, template: value }))
            }
            load={loadTemplates}
            describe={(row) => `${row.name} · ${row.validity_days} days`}
          />
          <div className="form-grid">
            <label className="field">
              Business date
              <input
                type="date"
                required
                value={asOf}
                onChange={(e) => setAsOf(e.target.value)}
              />
            </label>
            <label className="field">
              Start date
              <input
                type="date"
                required
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label className="field">
              Expiry date
              <input
                type="date"
                required
                min={start > asOf ? start : asOf}
                value={expiry}
                onChange={(e) => setExpiry(e.target.value)}
              />
            </label>
            <label className="field">
              Payment terms (days)
              <input
                type="number"
                min="0"
                max="3650"
                required
                value={days}
                onChange={(e) => setDays(e.target.value)}
              />
            </label>
          </div>
          {error && <Notice>{error}</Notice>}
          <Button disabled={busy} variant="primary">
            {busy ? "Creating…" : "Create quotation from template"}
          </Button>
        </form>
      </Panel>
    </div>
  );
}
