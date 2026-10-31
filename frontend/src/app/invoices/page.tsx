"use client";
import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";
import { Shell } from "@/components/shell";
import { useAuth } from "@/components/auth-provider";
import {
  Button,
  Empty,
  Loading,
  Notice,
  PageHeader,
  Panel,
  Pagination,
  Table,
} from "@/components/ui";
import { InvoiceBadge, Period, useInvoices } from "@/components/invoice-data";
import { formatDate, formatINR } from "@/lib/format";
import { isOperator } from "@/lib/lifecycle";

export default function InvoicesPage() {
  return (
    <Shell>
      <InvoiceRegister />
    </Shell>
  );
}
function InvoiceRegister() {
  const { user } = useAuth();
  const operator = !!user && isOperator(user.role);
  const [filters, setFilters] = useState({
    search: "",
    status: "",
    customer_id: "",
    subscription_id: "",
    due_from: "",
    due_to: "",
  });
  const [applied, setApplied] = useState(filters);
  const [offset, setOffset] = useState(0),
    [limit, setLimit] = useState(20);
  const query = useMemo(
    () => ({ ...applied, limit, offset }),
    [applied, limit, offset],
  );
  const records = useInvoices(query);
  const data = records.data;
  function filter(event: FormEvent) {
    event.preventDefault();
    setOffset(0);
    setApplied({ ...filters });
  }
  return (
    <div className="stack">
      <PageHeader
        title="Invoices"
        description="Persisted invoice periods, immutable charges, discounts, and exclusive taxes."
        actions={
          operator ? (
            <Link href="/billing" className="button button-primary">
              Open Billing Center
            </Link>
          ) : undefined
        }
      />
      <Panel
        title="Invoice Filters"
        subtitle="Filters and pagination apply on the server"
      >
        <form onSubmit={filter} className="panel-body form-grid">
          <label className="field">
            Invoice number
            <input
              value={filters.search}
              onChange={(e) =>
                setFilters({ ...filters, search: e.target.value })
              }
              placeholder="INV-…"
            />
          </label>
          <label className="field">
            Invoice status
            <select
              value={filters.status}
              onChange={(e) =>
                setFilters({ ...filters, status: e.target.value })
              }
            >
              <option value="">All statuses</option>
              {["draft", "confirmed", "paid", "cancelled"].map((s) => (
                <option key={s} value={s}>
                  {s[0].toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </label>
          {operator && (
            <label className="field">
              Customer ID
              <input
                type="number"
                min="1"
                step="1"
                value={filters.customer_id}
                onChange={(e) =>
                  setFilters({ ...filters, customer_id: e.target.value })
                }
              />
            </label>
          )}
          <label className="field">
            Subscription ID
            <input
              type="number"
              min="1"
              step="1"
              value={filters.subscription_id}
              onChange={(e) =>
                setFilters({ ...filters, subscription_id: e.target.value })
              }
            />
          </label>
          <label className="field">
            Due from
            <input
              type="date"
              value={filters.due_from}
              onChange={(e) =>
                setFilters({ ...filters, due_from: e.target.value })
              }
            />
          </label>
          <label className="field">
            Due to
            <input
              type="date"
              min={filters.due_from || undefined}
              value={filters.due_to}
              onChange={(e) =>
                setFilters({ ...filters, due_to: e.target.value })
              }
            />
          </label>
          <div className="row wrap">
            <Button type="submit" variant="primary" disabled={records.loading}>
              Apply filters
            </Button>
            <Button
              type="button"
              onClick={() => {
                const empty = {
                  search: "",
                  status: "",
                  customer_id: "",
                  subscription_id: "",
                  due_from: "",
                  due_to: "",
                };
                setFilters(empty);
                setApplied(empty);
                setOffset(0);
              }}
            >
              Clear filters
            </Button>
          </div>
        </form>
      </Panel>
      {records.loading && <Loading label="Loading invoices…" />}
      {records.error && (
        <Notice>
          {records.error} <Button onClick={records.reload}>Retry</Button>
        </Notice>
      )}
      {data && (
        <Panel
          title="Invoice Register"
          subtitle={`${data.page.total} accessible invoices · newest first`}
        >
          {data.page.items.length ? (
            <Table
              label="Invoices"
              columns={[
                { name: "Invoice #" },
                { name: "Customer" },
                { name: "Subscription" },
                { name: "Period" },
                { name: "Due date" },
                { name: "Status" },
                { name: "Total", numeric: true },
              ]}
            >
              {data.page.items.map((row) => (
                <tr key={row.id}>
                  <td>
                    <Link className="table-link" href={`/invoices/${row.id}`}>
                      {row.number}
                    </Link>
                    <small>Issued {formatDate(row.invoice_date)}</small>
                  </td>
                  <td>
                    {data.customers.get(row.customer_id)?.company_name ||
                      data.customers.get(row.customer_id)?.contact_name ||
                      `Customer #${row.customer_id}`}
                  </td>
                  <td>
                    <Link
                      className="table-link"
                      href={`/subscriptions/${row.subscription_id}`}
                    >
                      {data.subscriptions.get(row.subscription_id)?.number ||
                        `#${row.subscription_id}`}
                    </Link>
                  </td>
                  <td>
                    <Period start={row.period_start} end={row.period_end} />
                  </td>
                  <td>{formatDate(row.due_date)}</td>
                  <td>
                    <InvoiceBadge status={row.status} />
                  </td>
                  <td className="numeric money">
                    {formatINR(row.total_paise)}
                  </td>
                </tr>
              ))}
            </Table>
          ) : (
            <Empty
              title="No invoices found"
              detail="Adjust filters, or generate due periods through Billing Center."
            />
          )}
          <Pagination
            total={data.page.total}
            offset={offset}
            limit={limit}
            busy={records.loading}
            onChange={(next, size) => {
              setOffset(next);
              setLimit(size);
            }}
          />
        </Panel>
      )}
      <Notice kind="info">
        Payments and balances are not available until payment recording is
        implemented. Cancelled invoices remain in the register and reserve their
        billing periods.
      </Notice>
    </div>
  );
}
