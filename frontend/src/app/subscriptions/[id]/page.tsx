"use client";
import Link from "next/link";
import { use, useCallback, useState } from "react";
import { Zap as Bolt, LockKeyhole } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Shell } from "@/components/shell";
import { Badge, Button, Loading, Notice, Panel, Table } from "@/components/ui";
import { LifecycleDialog } from "@/components/lifecycle-dialog";
import { chargesBeforeTax, labelsFor } from "@/components/subscription-data";
import { formatDate, formatINR, formatRate, titleCase } from "@/lib/format";
import { useResource } from "@/lib/hooks";
import {
  actionLabels,
  allowedActions,
  isOperator,
  statuses,
} from "@/lib/lifecycle";
import type { LifecycleAction, Subscription } from "@/lib/types";

export default function SubscriptionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <Shell>
      {/^[1-9]\d*$/.test(id) && Number.isSafeInteger(Number(id)) ? (
        <SubscriptionDetail key={id} id={Number(id)} />
      ) : (
        <Notice>
          Invalid subscription ID.{" "}
          <Link href="/subscriptions">Back to subscriptions</Link>.
        </Notice>
      )}
    </Shell>
  );
}
function SubscriptionDetail({ id }: { id: number }) {
  const { api, user } = useAuth();
  const operator = user ? isOperator(user.role) : false;
  const result = useResource(
    useCallback(
      async (signal) => {
        const subscription = await api.subscription(id, signal);
        return {
          subscription,
          ...(await labelsFor(api, [subscription], operator, signal)),
        };
      },
      [api, id, operator],
    ),
  );
  const [updated, setUpdated] = useState<Subscription | null>(null);
  const [action, setAction] = useState<LifecycleAction | null>(null);
  const [success, setSuccess] = useState("");
  if (result.loading) return <Loading label="Loading subscription…" />;
  if (result.error || !result.data)
    return (
      <div className="stack">
        <Link className="table-link" href="/subscriptions">
          ← Back to subscriptions
        </Link>
        <Notice>
          {result.error || "Subscription not found."}
          <Button onClick={result.reload}>Retry</Button>
        </Notice>
      </div>
    );
  const row = updated || result.data.subscription;
  const customer = result.data.customers.get(row.customer_id);
  const plan =
    row.commercial_snapshot?.plan || result.data.plans.get(row.plan_id);
  const stage = statuses.indexOf(row.status);
  return (
    <div className="stack">
      <div className="breadcrumb">
        <Link href="/subscriptions">Subscriptions</Link>
        <span>/</span>
        <span>{row.number}</span>
      </div>
      {success && <Notice kind="success">{success}</Notice>}
      <section className="page-header block!">
        <div className="flex items-start justify-between gap-5 flex-wrap">
          <div>
            <h1>Subscription {row.number}</h1>
            <div className="row mt-3 wrap">
              <Badge status={row.status} paused={row.is_paused} />
              <span className="pill">
                {plan ? titleCase(plan.billing_period) : "Plan cadence"}{" "}
                recurring
              </span>
            </div>
            <p>
              {customer?.company_name ||
                customer?.contact_name ||
                `Customer #${row.customer_id}`}
            </p>
            <p className="text-xs! muted">{customer?.contact_name}</p>
          </div>
          <div className="header-actions">
            {user &&
              allowedActions(row, user.role).map((value) => (
                <Button
                  key={value}
                  variant={
                    value === "close"
                      ? "danger"
                      : value === "confirm" ||
                          value === "activate" ||
                          value === "quotation"
                        ? "primary"
                        : "secondary"
                  }
                  onClick={() => {
                    setSuccess("");
                    setAction(value);
                  }}
                >
                  {actionLabels[value]}
                </Button>
              ))}
            {operator && (
              <Link href="/billing" className="button button-secondary">
                <Bolt size={14} />
                Open Billing Center
              </Link>
            )}
          </div>
        </div>
        <div className="detail-summary">
          <div>
            <div className="eyebrow">Recurring charges · excl. tax</div>
            <div className="value text-primary">
              {formatINR(chargesBeforeTax(row))}
            </div>
          </div>
          <div>
            <div className="eyebrow">Next invoice date</div>
            <div className="value text-cyan">
              {formatDate(row.next_invoice_date)}
            </div>
          </div>
          <div>
            <div className="eyebrow">Contract expiry</div>
            <div className="value">{formatDate(row.expiry_date)}</div>
          </div>
          <div>
            <div className="eyebrow">Commercial terms</div>
            <div className="value">
              {row.commercial_snapshot ? "Frozen" : "Indicative"}
            </div>
          </div>
        </div>
      </section>
      <Panel
        title="Lifecycle State Machine"
        subtitle="Current state of this agreement; pause is an independent condition"
      >
        <ol className="lifecycle">
          {statuses.map((status, index) => (
            <li
              key={status}
              className={`lifecycle-step ${index === stage ? "current" : index < stage ? "complete" : ""}`}
              aria-current={index === stage ? "step" : undefined}
            >
              <span>STEP 0{index + 1}</span>
              <strong>{titleCase(status)}</strong>
            </li>
          ))}
        </ol>
      </Panel>
      <div className="two-columns equal-columns">
        <Panel
          title="Billing Rules & Terms"
          action={
            row.commercial_snapshot ? (
              <span className="pill">
                <LockKeyhole size={10} className="mr-1" />
                ACCEPTED
              </span>
            ) : undefined
          }
        >
          <div className="detail-grid">
            <Detail
              label="Assigned plan"
              value={plan?.name || `Plan #${row.plan_id}`}
            />
            <Detail
              label="Billing cadence"
              value={
                plan
                  ? titleCase(plan.billing_period)
                  : "Available on confirmation"
              }
            />
            <Detail
              label="Payment terms"
              value={`Net ${row.payment_terms_days} days`}
            />
            <Detail
              label="Recurring base charge"
              value={formatINR(row.recurring_base_price_paise)}
            />
          </div>
        </Panel>
        <Panel title="Tenure & Plan Permissions">
          <div className="detail-grid">
            <Detail
              label="Start / original billing anchor"
              value={formatDate(row.start_date)}
            />
            <Detail
              label="Expiry / renewal date"
              value={formatDate(row.expiry_date)}
            />
            <Detail
              label="Quotation date"
              value={formatDate(row.quotation_date)}
            />
            <Detail
              label="Quotation expires"
              value={formatDate(row.quotation_expiry_date)}
            />
            <Detail
              label="Pause / close / renew"
              value={
                plan
                  ? `${plan.pausable ? "Pause" : "No pause"} · ${plan.closable ? "Close" : "No close"} · ${plan.renewable ? "Renew" : "No renew"}`
                  : "Available on confirmation"
              }
            />
            <Detail label="Automatic closure" value="Not scheduled" />
          </div>
        </Panel>
      </div>
      <Panel
        title="Product Lines & Recurring Charges"
        subtitle={
          row.commercial_snapshot
            ? "Accepted prices are frozen. Product line amendments are not available."
            : "Indicative charges are recalculated at confirmation."
        }
        action={<span className="pill">{row.lines.length} LINE ITEMS</span>}
      >
        <Table
          label="Subscription product lines"
          columns={[
            { name: "Product" },
            { name: "Variant / add-on" },
            { name: "Qty", numeric: true },
            { name: "Unit price", numeric: true },
            { name: "Tax rate", numeric: true },
            { name: "Line amount", numeric: true },
          ]}
        >
          {row.lines.map((line, index) => {
            const description = row.commercial_snapshot?.lines[index];
            return (
              <tr key={line.id}>
                <td>
                  {description?.product_name || `Product #${line.product_id}`}
                  <small>
                    {row.commercial_snapshot
                      ? "Accepted product description"
                      : "Catalog item"}
                  </small>
                </td>
                <td>
                  {line.variant_id
                    ? description?.value
                      ? `${description.attribute}: ${description.value}`
                      : `Variant #${line.variant_id}`
                    : "—"}
                </td>
                <td className="numeric">{line.quantity}</td>
                <td className="numeric money">
                  {formatINR(line.unit_price_paise)}
                </td>
                <td className="numeric">
                  {formatRate(line.tax_rate_basis_points)}
                  <small>Exclusive rate</small>
                </td>
                <td className="numeric money">
                  {formatINR(line.amount_paise)}
                </td>
              </tr>
            );
          })}
        </Table>
        <div className="financial-summary">
          <div>
            <span>Plan recurring base</span>
            <span className="money">
              {formatINR(row.recurring_base_price_paise)}
            </span>
          </div>
          <div>
            <span>Additional product lines</span>
            <span className="money">
              {formatINR(
                row.lines.reduce((sum, line) => sum + line.amount_paise, 0n),
              )}
            </span>
          </div>
          <div className="total">
            <span>Recurring charges before tax</span>
            <span className="money text-primary">
              {formatINR(chargesBeforeTax(row))}
            </span>
          </div>
          <p>
            Exclusive tax and invoice totals are not calculated here. This is a
            commercial agreement, not an issued invoice.
          </p>
        </div>
      </Panel>
      <Panel
        title="Invoice History"
        subtitle="Persisted billing periods; payments remain unavailable"
      >
        <div className="panel-body">
          <p>
            Open the invoice register and filter by Subscription ID {row.id} to
            review this agreement’s invoices.
          </p>
          <Link href="/invoices" className="button button-secondary mt-3">
            View invoice register
          </Link>
        </div>
      </Panel>
      {action && (
        <LifecycleDialog
          key={action}
          subscription={row}
          action={action}
          onClose={() => setAction(null)}
          onSuccess={(value) => {
            setUpdated(value);
            setAction(null);
            setSuccess(`${actionLabels[action]} completed successfully.`);
          }}
        />
      )}
    </div>
  );
}
function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-cell">
      <div className="eyebrow">{label}</div>
      <strong>{value}</strong>
    </div>
  );
}
