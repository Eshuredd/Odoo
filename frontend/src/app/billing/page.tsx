"use client";
import Link from "next/link";
import { useState } from "react";
import { Zap, FlaskConical, ClipboardCheck, RefreshCw } from "lucide-react";
import { Shell } from "@/components/shell";
import { useAuth } from "@/components/auth-provider";
import {
  Button,
  Empty,
  KpiCard,
  Loading,
  Modal,
  Notice,
  PageHeader,
  Panel,
  Table,
} from "@/components/ui";
import { Period } from "@/components/invoice-data";
import { formatDate, formatINR, todayInIndia } from "@/lib/format";
import type { BillingReport } from "@/lib/types";

export default function BillingPage() {
  return (
    <Shell operatorOnly>
      <BillingWorkspace />
    </Shell>
  );
}
function BillingWorkspace() {
  const { api } = useAuth();
  const [asOf, setAsOf] = useState(todayInIndia);
  const [report, setReport] = useState<BillingReport>();
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function evaluate(actual = false) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = actual
        ? await api.billingRun(asOf)
        : await api.billingPreview(asOf);
      setReport(result);
      setConfirm(false);
      if (actual) {
        setNotice(
          `Billing completed: ${result.generated_or_proposed_invoice_count} invoices generated; ${result.failed_count} subscriptions failed.`,
        );
        try {
          const records = await Promise.all(
            result.invoices.map((row) => api.invoice(row.invoice_id!)),
          );
          setReport({
            ...result,
            invoices: result.invoices.map((row, index) => ({
              ...row,
              ...records[index],
              invoice_id: records[index].id,
              invoice_number: records[index].number,
            })),
          });
        } catch {
          setError(
            "Billing completed, but refreshing persisted invoice details failed. Review the invoice register before retrying.",
          );
        }
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Billing could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }
  const rows = [
    ...(report?.invoices || []),
    ...(report?.existing_invoices || []),
  ];
  return (
    <div className="stack">
      <PageHeader
        title="Automated Billing Center"
        description="Preview due periods, review exact charges, then generate persisted draft invoices."
        actions={<span className="pill">EXPLICIT DATE · INR</span>}
      />
      <Notice kind="info">
        Pausing defers billing rather than forgiving charges. Resuming catches
        up every outstanding period. Final periods are billed in full without
        proration.
      </Notice>
      {error && <Notice>{error}</Notice>}
      {notice && <Notice kind="success">{notice}</Notice>}
      <Panel
        title="Execution Parameters"
        subtitle="Preview makes no database changes; execution requires confirmation"
        action={
          <span className="pill">
            {report ? (report.dry_run ? "DRY RUN" : "EXECUTED") : "READY"}
          </span>
        }
      >
        <div className="panel-body">
          <div className="pending-grid">
            <div className="pending-cell">
              <label htmlFor="billing-date">Run billing as of date</label>
              <input
                id="billing-date"
                type="date"
                required
                value={asOf}
                disabled={busy}
                onChange={(event) => {
                  setAsOf(event.target.value);
                  setReport(undefined);
                  setNotice("");
                  setError("");
                }}
              />
            </div>
            <div className="pending-cell">
              <div className="eyebrow">Cadence scope</div>
              <strong>All recurring</strong>
              <p>Daily, weekly, monthly, yearly</p>
            </div>
            <div className="pending-cell">
              <div className="eyebrow">Customer scope</div>
              <strong>All eligible accounts</strong>
              <p>No customer filter applied</p>
            </div>
            <div className="pending-cell">
              <div className="eyebrow">Missed periods</div>
              <strong>Full catch-up</strong>
              <p>Original billing anchor retained</p>
            </div>
            <div className="pending-cell">
              <div className="eyebrow">Execution mode</div>
              <strong>
                {report?.dry_run === false
                  ? "Actual execution"
                  : "Dry-run preview"}
              </strong>
              <p>Separate explicit actions</p>
            </div>
          </div>
          <div className="row wrap space-between mt-5">
            <p className="text-xs max-w-xl">
              Discount eligibility uses each period’s start date. A preview is a
              snapshot; execution rechecks current database state.
            </p>
            <div className="row wrap">
              <Button disabled={busy || !asOf} onClick={() => void evaluate()}>
                <FlaskConical size={15} />
                Preview dry run
              </Button>
              <Button
                variant="primary"
                disabled={
                  busy ||
                  !report?.dry_run ||
                  report.as_of !== asOf ||
                  (!report.invoices.length &&
                    !report.auto_closed_subscription_ids.length &&
                    !report.existing_invoices.length)
                }
                onClick={() => setConfirm(true)}
              >
                <Zap size={15} />
                Execute billing
              </Button>
            </div>
          </div>
        </div>
      </Panel>
      {busy && <Loading label="Evaluating billing periods…" />}
      <div className="kpi-grid kpi-grid-five">
        <KpiCard
          label="Eligible subscriptions"
          value={report?.eligible_subscription_count ?? "—"}
          detail="Selected for due billing or closure"
        />
        <KpiCard
          label={
            report?.dry_run === false
              ? "Invoices generated"
              : "Invoices to generate"
          }
          value={report?.generated_or_proposed_invoice_count ?? "—"}
          detail="New periods only"
          accent="cyan"
        />
        <KpiCard
          label={
            report?.dry_run === false
              ? "Actual invoice totals"
              : "Projected invoice totals"
          }
          value={
            report ? formatINR(report.projected_or_actual_total_paise) : "—"
          }
          detail="After discounts and exclusive tax"
          accent="green"
        />
        <KpiCard
          label="Skipped / existing"
          value={report?.skipped_count ?? "—"}
          detail="No duplicate invoices generated"
        />
        <KpiCard
          label="Failed subscriptions"
          value={report?.failed_count ?? "—"}
          detail="Each failed subscription rolls back"
          accent="rose"
        />
      </div>
      <Panel
        title="Billing Review"
        subtitle={
          report
            ? `${report.dry_run ? "Preview" : "Execution"} as of ${formatDate(report.as_of)}`
            : "Select a date and preview due periods"
        }
      >
        <div className="three-columns panel-body">
          <div className="detail-cell">
            <ClipboardCheck size={20} className="text-primary" />
            <h3 className="mt-3">Already billed periods</h3>
            <p>
              {report?.existing_invoices.length ?? "—"} reserved periods
              encountered. Cancelled invoices also keep their reservation.
            </p>
            <Link href="/invoices">View persisted invoice register</Link>
          </div>
          <div className="detail-cell">
            <RefreshCw size={20} className="text-cyan" />
            <h3 className="mt-3">Catch-up periods</h3>
            <p>
              {report
                ? report.invoices.filter((row) => row.catch_up).length
                : "—"}{" "}
              full periods ending on or before the selected date.
            </p>
          </div>
          <div className="detail-cell">
            <FlaskConical size={20} className="text-primary" />
            <h3 className="mt-3">Automatic closures</h3>
            <p>
              {report?.auto_closed_subscription_ids.length ?? "—"}{" "}
              {report?.dry_run === false ? "closed" : "will close"} after all
              eligible periods. Paused subscriptions stay open.
            </p>
          </div>
        </div>
      </Panel>
      <Panel
        title="Generation Queue"
        subtitle="Each half-open billing period has its own immutable invoice"
      >
        {rows.length ? (
          <Table
            label="Billing generation queue"
            columns={[
              { name: "Subscription #" },
              { name: "Customer" },
              { name: "Period" },
              { name: "Subtotal", numeric: true },
              { name: "Discount", numeric: true },
              { name: "Tax", numeric: true },
              { name: "Total", numeric: true },
              { name: "Verdict / invoice" },
            ]}
          >
            {rows.map((row) => (
              <tr key={`${row.subscription_id}-${row.period_start}`}>
                <td>
                  <Link
                    className="table-link"
                    href={`/subscriptions/${row.subscription_id}`}
                  >
                    {row.subscription_number}
                  </Link>
                  <small>
                    {row.catch_up ? "Catch-up period" : "Scheduled period"}
                  </small>
                </td>
                <td>Customer #{row.customer_id}</td>
                <td>
                  <Period start={row.period_start} end={row.period_end} />
                </td>
                {[
                  row.subtotal_paise,
                  row.discount_total_paise,
                  row.tax_total_paise,
                  row.total_paise,
                ].map((amount, index) => (
                  <td className="numeric money" key={index}>
                    {formatINR(amount)}
                  </td>
                ))}
                <td>
                  {row.disposition}
                  <small>
                    {row.invoice_id ? (
                      <Link href={`/invoices/${row.invoice_id}`}>
                        {row.invoice_number}
                      </Link>
                    ) : (
                      "Not persisted"
                    )}
                  </small>
                  <small>
                    {row.applied_discount_snapshot?.name || "No discount"}
                  </small>
                </td>
              </tr>
            ))}
          </Table>
        ) : (
          <Empty
            title={report ? "No new invoice periods" : "No billing preview yet"}
            detail={
              report
                ? "Review skipped subscriptions and failures below, or choose another date."
                : "Preview with an explicit billing date to evaluate eligible subscriptions."
            }
          />
        )}
      </Panel>
      <div className="two-columns equal-columns">
        <Panel title="Skipped Subscriptions">
          <div className="panel-body">
            {report?.skipped.length ? (
              report.skipped.map((row) => (
                <p key={row.subscription_id}>
                  <strong>{row.subscription_number}</strong> · {row.reason}
                </p>
              ))
            ) : (
              <p>No skipped subscriptions in this evaluation.</p>
            )}
          </div>
        </Panel>
        <Panel title="Failed Subscriptions">
          <div className="panel-body">
            {report?.errors.length ? (
              report.errors.map((row) => (
                <Notice key={row.subscription_id}>
                  <strong>{row.subscription_number}</strong> · {row.reason}
                </Notice>
              ))
            ) : (
              <p>No failures reported. Results appear after evaluation.</p>
            )}
          </div>
        </Panel>
      </div>
      {confirm && (
        <Modal
          title="Execute billing?"
          onClose={() => setConfirm(false)}
          busy={busy}
        >
          <div className="panel-body stack">
            <p>
              Generate draft invoices for every eligible period as of{" "}
              <strong>{formatDate(asOf)}</strong>. This persists invoice lines,
              discount redemptions, billing dates, audits, and eligible
              automatic closures.
            </p>
            <p>
              Previewed totals may change if another operator edits data before
              execution. Each subscription commits independently.
            </p>
            {error && <Notice>{error}</Notice>}
            <div className="form-actions">
              <Button disabled={busy} onClick={() => setConfirm(false)}>
                Go back
              </Button>
              <Button
                variant="primary"
                disabled={busy}
                onClick={() => void evaluate(true)}
              >
                {busy ? "Executing…" : "Confirm execution"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
