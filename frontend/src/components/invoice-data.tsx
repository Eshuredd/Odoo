"use client";
import { useCallback } from "react";
import { useAuth } from "./auth-provider";
import { useResource } from "@/lib/hooks";
import { formatDate, formatINR, formatRate, titleCase } from "@/lib/format";
import type {
  InvoiceAmounts,
  InvoiceLine,
  InvoiceStatus,
  Query,
} from "@/lib/types";
import { Table } from "./ui";

export function InvoiceBadge({ status }: { status: InvoiceStatus }) {
  const color = {
    draft: "draft",
    confirmed: "confirmed",
    paid: "active",
    cancelled: "closed",
  }[status];
  return (
    <span className={`status status-${color}`}>
      <span className="status-dot" />
      {titleCase(status)}
    </span>
  );
}
export function InvoiceLines({ lines }: { lines: InvoiceLine[] }) {
  return (
    <Table
      label="Invoice items"
      columns={[
        { name: "Item & description" },
        { name: "Quantity", numeric: true },
        { name: "Unit rate", numeric: true },
        { name: "Subtotal", numeric: true },
        { name: "Discount", numeric: true },
        { name: "Taxable", numeric: true },
        { name: "Tax rate", numeric: true },
        { name: "Tax", numeric: true },
        { name: "Total", numeric: true },
      ]}
    >
      {lines.map((line, index) => (
        <tr key={line.id ?? index}>
          <td>
            {line.description}
            <small>{titleCase(line.line_type)}</small>
          </td>
          <td className="numeric">{line.quantity}</td>
          {[
            line.unit_price_paise,
            line.subtotal_paise,
            line.discount_paise,
            line.taxable_amount_paise,
          ].map((amount, i) => (
            <td className="numeric money" key={i}>
              {formatINR(amount)}
            </td>
          ))}
          <td className="numeric">{formatRate(line.tax_rate_basis_points)}</td>
          <td className="numeric money">{formatINR(line.tax_paise)}</td>
          <td className="numeric money">{formatINR(line.total_paise)}</td>
        </tr>
      ))}
    </Table>
  );
}
export function InvoiceTotals({ invoice }: { invoice: InvoiceAmounts }) {
  return (
    <div className="financial-summary m-0! max-w-none!">
      <div>
        <span>Subtotal</span>
        <strong>{formatINR(invoice.subtotal_paise)}</strong>
      </div>
      <div>
        <span>Discount</span>
        <strong>{formatINR(invoice.discount_total_paise)}</strong>
      </div>
      <div>
        <span>Taxable amount</span>
        <strong>
          {formatINR(invoice.subtotal_paise - invoice.discount_total_paise)}
        </strong>
      </div>
      <div>
        <span>Exclusive tax</span>
        <strong>{formatINR(invoice.tax_total_paise)}</strong>
      </div>
      <div className="total">
        <span>Grand total</span>
        <strong>{formatINR(invoice.total_paise)}</strong>
      </div>
      <p>
        {invoice.applied_discount_snapshot
          ? `Applied: ${invoice.applied_discount_snapshot.name} (#${invoice.applied_discount_id})`
          : "No discount applied"}
      </p>
    </div>
  );
}
export function Period({ start, end }: { start: string; end: string }) {
  return (
    <span>
      {formatDate(start)} → {formatDate(end)}
      <small className="block mt-1 text-xs muted">Start inclusive · End exclusive</small>
    </span>
  );
}
export function useInvoices(query: Query) {
  const { api } = useAuth();
  return useResource(
    useCallback(
      async (signal) => {
        const page = await api.invoices(query, signal);
        const customers = await Promise.all(
          [...new Set(page.items.map((row) => row.customer_id))].map((id) =>
            api.customer(id, signal),
          ),
        );
        const subscriptions = await Promise.all(
          [...new Set(page.items.map((row) => row.subscription_id))].map((id) =>
            api.subscription(id, signal),
          ),
        );
        return {
          page,
          customers: new Map(customers.map((row) => [row.id, row])),
          subscriptions: new Map(subscriptions.map((row) => [row.id, row])),
        };
      },
      [api, query],
    ),
  );
}
