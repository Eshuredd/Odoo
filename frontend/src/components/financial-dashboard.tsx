"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useAuth } from "./auth-provider";
import { Button, Empty, KpiCard, Loading, Notice, Panel, Table } from "./ui";
import { useResource } from "@/lib/hooks";
import { formatINR, formatDate, todayInIndia } from "@/lib/format";

export function FinancialDashboard() {
  const { api } = useAuth();
  const [asOf, setAsOf] = useState(todayInIndia);
  const [from, setFrom] = useState(() => todayInIndia().slice(0, 8) + "01");
  const [to, setTo] = useState(todayInIndia);
  const data = useResource(
    useCallback(
      async (signal) => {
        const [summary, overdue] = await Promise.all([
          api.summary({ as_of: asOf, from_date: from, to_date: to }, signal),
          api.invoices({ as_of: asOf, overdue: true, limit: 5 }, signal),
        ]);
        return { summary, overdue };
      },
      [api, asOf, from, to],
    ),
  );
  const report = data.data?.summary;
  const largest =
    report?.monthly_collections.reduce(
      (max, row) => (row.amount_paise > max ? row.amount_paise : max),
      0n,
    ) || 1n;
  return (
    <div className="stack">
      <Panel
        title="Financial Reporting Dates"
        subtitle="Collections use the inclusive date range; balances use all recorded payments and current invoice status"
      >
        <div className="panel-body form-grid">
          <label className="field">
            Report as of
            <input
              type="date"
              required
              value={asOf}
              onChange={(e) => e.target.value && setAsOf(e.target.value)}
            />
          </label>
          <label className="field">
            Collections from
            <input
              type="date"
              required
              value={from}
              onChange={(e) => e.target.value && setFrom(e.target.value)}
            />
          </label>
          <label className="field">
            Collections to
            <input
              type="date"
              required
              value={to}
              onChange={(e) => e.target.value && setTo(e.target.value)}
            />
          </label>
        </div>
      </Panel>
      {data.loading && <Loading label="Loading financial report…" />}
      {data.error && (
        <Notice>
          {data.error}
          <Button onClick={data.reload}>Retry report</Button>
        </Notice>
      )}
      <div className="kpi-grid">
        <KpiCard
          label="Active subscriptions"
          value={report?.active_subscription_count ?? "—"}
          detail={`${report?.paused_subscription_count ?? "—"} paused · included in Active`}
        />
        <KpiCard
          label="Revenue collected"
          value={report ? formatINR(report.revenue_collected_paise) : "—"}
          detail="Recorded payments in selected date range"
          accent="green"
        />
        <KpiCard
          label="Outstanding balance"
          value={report ? formatINR(report.outstanding_balance_paise) : "—"}
          detail="Unpaid amounts on Confirmed invoices"
          accent="cyan"
        />
        <KpiCard
          label="Overdue invoices"
          value={report?.overdue_invoice_count ?? "—"}
          detail={
            report ? formatINR(report.overdue_amount_paise) : "No report loaded"
          }
          accent="rose"
        />
      </div>
      <div className="two-columns equal-columns">
        <Panel
          title="Collections Over Time"
          subtitle="Actual manually recorded payments, grouped by payment month"
        >
          <div className="panel-body stack">
            {report?.monthly_collections.length ? (
              report.monthly_collections.map((row) => (
                <div key={row.month}>
                  <div className="row space-between">
                    <span>{row.month}</span>
                    <strong className="money">
                      {formatINR(row.amount_paise)}
                    </strong>
                  </div>
                  <div className="distribution-track mt-2">
                    <div
                      style={{
                        width: `${Number((row.amount_paise * 10000n) / largest) / 100}%`,
                        background: "var(--color-emerald)",
                      }}
                    />
                  </div>
                </div>
              ))
            ) : (
              <p>No collections in this date range.</p>
            )}
          </div>
        </Panel>
        <Panel
          title="Overdue Aging"
          subtitle="Outstanding amounts on overdue Confirmed invoices"
        >
          <div className="panel-body stack">
            {Object.entries(report?.aging_buckets || {}).map(([key, value]) => (
              <div className="row space-between" key={key}>
                <span>
                  {key === "1_30"
                    ? "1–30 days"
                    : key === "31_60"
                      ? "31–60 days"
                      : "61+ days"}{" "}
                  · {value.invoice_count} invoices
                </span>
                <strong>{formatINR(value.amount_paise)}</strong>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel
        title="Overdue Invoices Requiring Attention"
        subtitle={`As of ${formatDate(asOf)} · first five by newest invoice`}
      >
        {data.data?.overdue.items.length ? (
          <Table
            label="Overdue invoices"
            columns={[
              { name: "Invoice" },
              { name: "Due date" },
              { name: "Unpaid balance", numeric: true },
              { name: "Days overdue" },
            ]}
          >
            {data.data.overdue.items.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link href={`/invoices/${row.id}`}>{row.number}</Link>
                </td>
                <td>{formatDate(row.due_date)}</td>
                <td className="numeric money">
                  {formatINR(row.remaining_balance_paise)}
                </td>
                <td>{row.days_overdue}</td>
              </tr>
            ))}
          </Table>
        ) : (
          <Empty
            title="No overdue invoices"
            detail="Confirmed invoices become overdue only after their due date while a positive balance remains."
          />
        )}
      </Panel>
    </div>
  );
}
