"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useState } from "react";
import { FileDown, Send, Wallet } from "lucide-react";
import { Shell } from "@/components/shell";
import { useAuth } from "@/components/auth-provider";
import {
  Button,
  Loading,
  Modal,
  Notice,
  PageHeader,
  Panel,
  Unavailable,
} from "@/components/ui";
import {
  InvoiceBadge,
  InvoiceLines,
  InvoiceTotals,
  Period,
} from "@/components/invoice-data";
import { formatDate } from "@/lib/format";
import { isOperator } from "@/lib/lifecycle";
import { useResource } from "@/lib/hooks";
import type { Invoice } from "@/lib/types";

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <Shell>
      <InvoiceDetail key={id} id={Number(id)} />
    </Shell>
  );
}
function InvoiceDetail({ id }: { id: number }) {
  const { api, user } = useAuth();
  const [changed, setChanged] = useState<Invoice>();
  const [action, setAction] = useState<"confirm" | "cancel">();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const resource = useResource(
    useCallback(
      async (signal) => {
        if (!Number.isSafeInteger(id) || id < 1)
          throw new Error("Invalid invoice ID.");
        const invoice = await api.invoice(id, signal);
        const [customer, subscription] = await Promise.all([
          api.customer(invoice.customer_id, signal),
          api.subscription(invoice.subscription_id, signal),
        ]);
        return { invoice, customer, subscription };
      },
      [api, id],
    ),
  );
  if (resource.loading) return <Loading label="Loading invoice…" />;
  if (resource.error)
    return (
      <Notice>
        {resource.error} <Button onClick={resource.reload}>Retry</Button>
      </Notice>
    );
  if (!resource.data) return null;
  const { customer, subscription } = resource.data;
  const invoice = changed || resource.data.invoice;
  const operator = !!user && isOperator(user.role);
  async function submit() {
    if (!action) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.invoiceAction(id, action);
      setChanged(result);
      setAction(undefined);
      setNotice(`Invoice ${result.number} ${result.status}.`);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Invoice action failed.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack">
      <div className="breadcrumb">
        <Link href="/invoices">Invoices</Link>
        <span>/</span>
        <span>{invoice.number}</span>
      </div>
      <PageHeader
        title={invoice.number}
        description={`Invoice detail · ${subscription.number}`}
        actions={
          <>
            {operator && invoice.status === "draft" && (
              <Button variant="primary" onClick={() => setAction("confirm")}>
                Confirm invoice
              </Button>
            )}
            {operator && ["draft", "confirmed"].includes(invoice.status) && (
              <Button variant="danger" onClick={() => setAction("cancel")}>
                Cancel invoice
              </Button>
            )}
            <Button disabled variant="primary">
              <Wallet size={14} />
              Record Payment
            </Button>
            <Button disabled>
              <Send size={14} />
              Resend Email
            </Button>
            <Button disabled>
              <FileDown size={14} />
              Download PDF
            </Button>
          </>
        }
      />
      {notice && <Notice kind="success">{notice}</Notice>}
      {error && <Notice>{error}</Notice>}
      <div className="pending-grid">
        <div className="pending-cell">
          <div className="eyebrow">Invoice date</div>
          <strong>{formatDate(invoice.invoice_date)}</strong>
        </div>
        <div className="pending-cell">
          <div className="eyebrow">Billing period</div>
          <Period start={invoice.period_start} end={invoice.period_end} />
        </div>
        <div className="pending-cell">
          <div className="eyebrow">Payment terms</div>
          <strong>{subscription.payment_terms_days} days</strong>
          <p>From scheduled invoice date</p>
        </div>
        <div className="pending-cell">
          <div className="eyebrow">Due date</div>
          <strong>{formatDate(invoice.due_date)}</strong>
        </div>
        <div className="pending-cell">
          <div className="eyebrow">Status</div>
          <InvoiceBadge status={invoice.status} />
        </div>
      </div>
      <section className="panel invoice-identity">
        <div>
          <h2>{customer.company_name || customer.contact_name}</h2>
          <p className="text-xs mt-2">
            {customer.contact_name} · Customer #{customer.id}
          </p>
          <Link href={`/subscriptions/${subscription.id}`}>
            {subscription.number}
          </Link>
        </div>
        <InvoiceBadge status={invoice.status} />
      </section>
      <Panel
        title="Billable Items & Tax Allocations"
        subtitle="Historical invoice calculations remain fixed after catalog and discount changes"
      >
        <InvoiceLines lines={invoice.lines} />
        <div className="invoice-summary">
          <div className="detail-cell">
            <div className="eyebrow">INVOICE NOTES</div>
            <p>
              The recurring plan base charge has 0% tax. Product taxes are
              exclusive and calculated after discounts. Full billing periods are
              charged without proration.
            </p>
            {invoice.status === "cancelled" && (
              <p>
                Cancelled: this period remains reserved. Discount usage has not
                been restored.
              </p>
            )}
          </div>
          <InvoiceTotals invoice={invoice} />
        </div>
      </Panel>
      <div className="two-columns equal-columns">
        <Panel title="Payment History">
          <Unavailable detail="Payment recording is reserved for Stage 5. Paid amounts, balances, and payment history are unavailable." />
        </Panel>
        <Panel
          title="Record Payment"
          subtitle="Payment recording is not available yet"
        >
          <div className="panel-body">
            <fieldset disabled className="form-grid">
              <label className="field">
                Payment date
                <input type="date" aria-label="Payment date" />
              </label>
              <label className="field">
                Amount (INR)
                <input placeholder="Unavailable" aria-label="Payment amount" />
              </label>
              <label className="field">
                Payment method
                <select aria-label="Payment method">
                  <option>Unavailable</option>
                </select>
              </label>
              <label className="field">
                Payment reference
                <input
                  placeholder="Unavailable"
                  aria-label="Payment reference"
                />
              </label>
            </fieldset>
            <Button disabled variant="primary" className="mt-5 w-full">
              Record payment
            </Button>
          </div>
        </Panel>
      </div>
      {action && (
        <Modal
          title={`${action === "confirm" ? "Confirm" : "Cancel"} invoice?`}
          onClose={() => setAction(undefined)}
          busy={busy}
        >
          <div className="panel-body stack">
            <p>
              {action === "confirm"
                ? "Confirm this draft invoice. Its lines and calculated amounts remain immutable."
                : "Cancel this unpaid invoice. Its period reservation and historical discount usage will remain; no replacement, refund, or credit note is created."}
            </p>
            {error && <Notice>{error}</Notice>}
            <div className="form-actions">
              <Button disabled={busy} onClick={() => setAction(undefined)}>
                Go back
              </Button>
              <Button
                variant={action === "cancel" ? "danger" : "primary"}
                disabled={busy}
                onClick={() => void submit()}
              >
                {busy
                  ? "Saving…"
                  : action === "confirm"
                    ? "Confirm now"
                    : "Cancel now"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
