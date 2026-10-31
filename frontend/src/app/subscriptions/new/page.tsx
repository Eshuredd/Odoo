"use client";
import Link from "next/link";
import { useCallback, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2 } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Shell } from "@/components/shell";
import { Button, Notice, PageHeader, Panel } from "@/components/ui";
import { RemoteSelect } from "@/components/remote-select";
import { formatINR, todayInIndia } from "@/lib/format";
import type { Customer, Plan, Product, Variant } from "@/lib/types";

interface DraftLine {
  key: number;
  product: Product | null;
  variant: Variant | null;
  quantity: string;
}
export default function NewSubscriptionPage() {
  return (
    <Shell operatorOnly>
      <NewSubscription />
    </Shell>
  );
}
function NewSubscription() {
  const { api } = useAuth();
  const router = useRouter();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [asOf, setAsOf] = useState(todayInIndia());
  const [start, setStart] = useState(todayInIndia());
  const [expiry, setExpiry] = useState("");
  const [terms, setTerms] = useState("15");
  const [lines, setLines] = useState<DraftLine[]>([
    { key: 1, product: null, variant: null, quantity: "1" },
  ]);
  const [nextKey, setNextKey] = useState(2);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const loadCustomers = useCallback(
    (search: string, offset: number, signal: AbortSignal) =>
      api.customers({ search, offset, limit: 10 }, signal),
    [api],
  );
  const loadPlans = useCallback(
    (search: string, offset: number, signal: AbortSignal) =>
      api.plans(
        { search, offset, limit: 10, active: true, as_of: asOf },
        signal,
      ),
    [api, asOf],
  );
  const loadProducts = useCallback(
    (search: string, offset: number, signal: AbortSignal) =>
      api.products({ search, offset, limit: 10, active: true }, signal),
    [api],
  );
  function changeLine(key: number, patch: Partial<DraftLine>) {
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    );
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!customer || !plan) {
      setError("Select a customer and an available plan.");
      return;
    }
    if (!expiry || start > expiry || asOf > expiry) {
      setError("Expiry must be on or after the start and business dates.");
      return;
    }
    if (
      lines.some(
        (line) =>
          !line.product ||
          !/^\d+$/.test(line.quantity) ||
          Number(line.quantity) < 1 ||
          Number(line.quantity) > 1000000,
      )
    ) {
      setError(
        "Every line needs a product and a whole quantity from 1 to 1,000,000.",
      );
      return;
    }
    if (
      lines.reduce((sum, line) => sum + Number(line.quantity), 0) <
      plan.min_quantity
    ) {
      setError(
        `The plan requires a total product quantity of at least ${plan.min_quantity}.`,
      );
      return;
    }
    setBusy(true);
    try {
      const created = await api.createSubscription({
        customer_id: customer.id,
        plan_id: plan.id,
        start_date: start,
        expiry_date: expiry,
        payment_terms_days: Number(terms),
        as_of: asOf,
        lines: lines.map((line) => ({
          product_id: line.product!.id,
          variant_id: line.variant?.id || null,
          quantity: Number(line.quantity),
        })),
      });
      router.push(`/subscriptions/${created.id}`);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Subscription creation failed.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack">
      <div className="breadcrumb">
        <Link href="/subscriptions">Subscriptions</Link>
        <span>/</span>
        <span>New agreement</span>
      </div>
      <PageHeader
        title="Create Subscription"
        actions={
          <Link
            className="button button-secondary"
            href="/subscriptions/from-template"
          >
            Use quotation template
          </Link>
        }
        description="Start a draft agreement using an existing customer, plan, and product catalog. Prices are accepted and frozen later, at confirmation."
      />
      <form onSubmit={submit} className="stack">
        {error && <Notice>{error}</Notice>}
        <Panel
          title="Customer & Commercial Plan"
          subtitle="Choose the customer account and a plan available on the business date"
        >
          <div className="form-section form-grid">
            <div className="field">
              <span>Customer</span>
              <RemoteSelect
                label="Customer"
                value={customer}
                onChange={setCustomer}
                load={loadCustomers}
                describe={(value) => value.company_name || value.contact_name}
              />
            </div>
            <div className="field">
              <span>Plan</span>
              <RemoteSelect
                label="Plan"
                value={plan}
                onChange={setPlan}
                load={loadPlans}
                describe={(value) =>
                  `${value.name} · ${formatINR(value.price_paise)} / ${value.billing_period}`
                }
              />
            </div>
            <label className="field">
              Business date (as of)
              <input
                aria-label="Business date (as of)"
                required
                type="date"
                value={asOf}
                onChange={(event) => {
                  const next = event.target.value;
                  setAsOf(next);
                  if (plan && (next < plan.valid_from || next > plan.valid_to))
                    setPlan(null);
                }}
              />
            </label>
            <label className="field">
              Payment terms (days)
              <input
                aria-label="Payment terms (days)"
                required
                type="number"
                min={0}
                max={3650}
                step={1}
                value={terms}
                onChange={(event) => setTerms(event.target.value)}
              />
            </label>
            <label className="field">
              Start date
              <input
                aria-label="Start date"
                required
                type="date"
                value={start}
                onChange={(event) => setStart(event.target.value)}
              />
            </label>
            <label className="field">
              Expiry date
              <input
                aria-label="Expiry date"
                required
                type="date"
                value={expiry}
                onChange={(event) => setExpiry(event.target.value)}
              />
            </label>
          </div>
          {plan && (
            <div className="panel-body">
              <Notice kind="info">
                Recurring base: {formatINR(plan.price_paise)} per{" "}
                {plan.billing_period} period. Product lines add to this charge.
                Minimum total product quantity: {plan.min_quantity}.
              </Notice>
            </div>
          )}
        </Panel>
        <Panel
          title="Product Lines"
          subtitle="Choose one optional variant per product line. Taxes and final prices are validated by the backend."
          action={<span className="pill">{lines.length} / 100 LINES</span>}
        >
          <div className="form-section">
            {lines.map((line, index) => (
              <div className="line-form" key={line.key}>
                <div className="eyebrow mb-3">LINE {index + 1}</div>
                <div className="line-controls">
                  <div className="field">
                    <span>Product</span>
                    <RemoteSelect
                      label={`Product for line ${index + 1}`}
                      value={line.product}
                      onChange={(value) =>
                        changeLine(line.key, { product: value, variant: null })
                      }
                      load={loadProducts}
                      describe={(value) =>
                        `${value.name} · ${formatINR(value.sales_price_paise)}`
                      }
                    />
                  </div>
                  <div className="field">
                    <span>Variant (optional)</span>
                    {line.product ? (
                      <VariantSelect
                        key={line.product.id}
                        product={line.product}
                        value={line.variant}
                        onChange={(value) =>
                          changeLine(line.key, { variant: value })
                        }
                        index={index}
                      />
                    ) : (
                      <span className="muted text-xs p-2">
                        Choose a product first
                      </span>
                    )}
                  </div>
                  <label className="field">
                    Quantity
                    <input
                      aria-label={`Quantity for line ${index + 1}`}
                      required
                      type="number"
                      min={1}
                      max={1000000}
                      step={1}
                      value={line.quantity}
                      onChange={(event) =>
                        changeLine(line.key, { quantity: event.target.value })
                      }
                    />
                  </label>
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={lines.length === 1}
                    aria-label={`Remove line ${index + 1}`}
                    onClick={() =>
                      setLines((current) =>
                        current.filter((item) => item.key !== line.key),
                      )
                    }
                  >
                    <Trash2 size={17} />
                  </Button>
                </div>
                {line.product && (
                  <p className="muted text-xs mt-3">
                    Indicative unit price:{" "}
                    {formatINR(
                      line.product.sales_price_paise +
                        (line.variant?.extra_price_paise || 0n),
                    )}{" "}
                    · excluding tax
                  </p>
                )}
              </div>
            ))}
            <Button
              type="button"
              disabled={lines.length >= 100}
              onClick={() => {
                setLines((current) => [
                  ...current,
                  { key: nextKey, product: null, variant: null, quantity: "1" },
                ]);
                setNextKey((current) => current + 1);
              }}
            >
              <Plus size={15} />
              Add product line
            </Button>
          </div>
          <div className="form-actions">
            <Link className="button button-secondary" href="/subscriptions">
              Cancel
            </Link>
            <Button type="submit" variant="primary" disabled={busy}>
              {busy ? "Creating draft…" : "Create draft subscription"}
            </Button>
          </div>
        </Panel>
      </form>
    </div>
  );
}
function VariantSelect({
  product,
  value,
  onChange,
  index,
}: {
  product: Product;
  value: Variant | null;
  onChange: (value: Variant | null) => void;
  index: number;
}) {
  const { api } = useAuth();
  const load = useCallback(
    (_search: string, offset: number, signal: AbortSignal) =>
      api.variants(product.id, { active: true, offset, limit: 10 }, signal),
    [api, product.id],
  );
  return (
    <RemoteSelect
      label={`Variant for line ${index + 1}`}
      value={value}
      onChange={onChange}
      load={load}
      searchable={false}
      optional
      describe={(variant) =>
        `${variant.attribute}: ${variant.value} · +${formatINR(variant.extra_price_paise)}`
      }
    />
  );
}
