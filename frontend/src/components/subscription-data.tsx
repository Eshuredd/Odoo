"use client";
import Link from "next/link";
import { useCallback } from "react";
import { ArrowUpRight } from "lucide-react";
import type { ApiClient } from "@/lib/api";
import type { Customer, Plan, Query, Subscription } from "@/lib/types";
import { formatDate, formatINR, initials, titleCase } from "@/lib/format";
import { isOperator, statuses } from "@/lib/lifecycle";
import { useResource } from "@/lib/hooks";
import { useAuth } from "./auth-provider";
import { Badge, Table } from "./ui";

export function chargesBeforeTax(subscription: Subscription): bigint {
  return (
    subscription.recurring_base_price_paise +
    subscription.lines.reduce((sum, line) => sum + line.amount_paise, 0n)
  );
}
export async function labelsFor(
  api: ApiClient,
  subscriptions: Subscription[],
  operator: boolean,
  signal: AbortSignal,
) {
  const customers = await Promise.all(
    [...new Set(subscriptions.map((row) => row.customer_id))].map((id) =>
      api.customer(id, signal),
    ),
  );
  const plans = operator
    ? await Promise.all(
        [...new Set(subscriptions.map((row) => row.plan_id))].map((id) =>
          api.plan(id, signal),
        ),
      )
    : [];
  return {
    customers: new Map(customers.map((row) => [row.id, row])),
    plans: new Map(plans.map((row) => [row.id, row])),
  };
}
export function useSubscriptionCounts() {
  const { api } = useAuth();
  return useResource(
    useCallback(
      async (signal) => {
        const pages = await Promise.all(
          statuses.map((status) =>
            api.subscriptions({ status, limit: 1 }, signal),
          ),
        );
        const counts = Object.fromEntries(
          statuses.map((status, index) => [status, pages[index].total]),
        ) as Record<(typeof statuses)[number], number>;
        return {
          ...counts,
          total: pages.reduce((sum, page) => sum + page.total, 0),
        };
      },
      [api],
    ),
  );
}
export function useSubscriptions(query: Query) {
  const { api, user } = useAuth();
  const operator = user ? isOperator(user.role) : false;
  return useResource(
    useCallback(
      async (signal) => {
        const page = await api.subscriptions(query, signal);
        return {
          page,
          ...(await labelsFor(api, page.items, operator, signal)),
        };
      },
      [api, query, operator],
    ),
  );
}
export function SubscriptionTable({
  rows,
  customers,
  plans,
}: {
  rows: Subscription[];
  customers: Map<number, Customer>;
  plans: Map<number, Plan>;
}) {
  return (
    <Table
      label="Subscriptions"
      columns={[
        { name: "Subscription #" },
        { name: "Customer & contact" },
        { name: "Plan & cadence" },
        { name: "Recurring charges", numeric: true },
        { name: "Start date" },
        { name: "Next invoice" },
        { name: "Lifecycle state" },
        { name: "Details" },
      ]}
    >
      {rows.map((row) => {
        const customer = customers.get(row.customer_id);
        const name =
          customer?.company_name ||
          customer?.contact_name ||
          `Customer #${row.customer_id}`;
        const plan = row.commercial_snapshot?.plan || plans.get(row.plan_id);
        return (
          <tr key={row.id}>
            <td>
              <Link className="table-link" href={`/subscriptions/${row.id}`}>
                {row.number}
              </Link>
              <small>
                {row.commercial_snapshot
                  ? "Accepted terms"
                  : "Before confirmation"}
              </small>
            </td>
            <td>
              <div className="row">
                <span className="avatar">{initials(name)}</span>
                <div>
                  {name}
                  <small>{customer?.contact_name}</small>
                </div>
              </div>
            </td>
            <td>
              {plan?.name || `Plan #${row.plan_id}`}
              <small>
                {plan
                  ? titleCase(plan.billing_period)
                  : "Cadence available on confirmation"}
              </small>
            </td>
            <td className="numeric money">
              {formatINR(chargesBeforeTax(row))}
              <small>Base + lines · excl. tax</small>
            </td>
            <td className="tabular">{formatDate(row.start_date)}</td>
            <td className="tabular">
              {formatDate(row.next_invoice_date)}
              {row.next_invoice_date && (
                <small>Billing date, not an issued invoice</small>
              )}
            </td>
            <td>
              <Badge status={row.status} paused={row.is_paused} />
            </td>
            <td>
              <Link
                className="button button-ghost"
                aria-label={`View ${row.number}`}
                href={`/subscriptions/${row.id}`}
              >
                <ArrowUpRight size={17} />
              </Link>
            </td>
          </tr>
        );
      })}
    </Table>
  );
}
