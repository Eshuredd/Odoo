"use client";
import Link from "next/link";
import { FileDown, Send, Wallet } from "lucide-react";
import { Shell } from "@/components/shell";
import {
  Button,
  Notice,
  PageHeader,
  Panel,
  Table,
  Unavailable,
} from "@/components/ui";

export default function InvoiceDetailPage() {
  return (
    <Shell>
      <div className="stack">
        <div className="breadcrumb">
          <Link href="/invoices">Invoices</Link>
          <span>/</span>
          <span>Detail workspace</span>
        </div>
        <PageHeader
          title="Invoice Detail"
          description="No invoice is loaded. Invoice data and payment recording are pending backend support."
          actions={
            <>
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
        <Notice kind="info">
          This workspace preserves the invoice layout, but does not represent an
          issued invoice. All execution, email, PDF, and payment actions are
          disabled.
        </Notice>
        <div className="pending-grid">
          {[
            "Invoice date",
            "Billing period",
            "Payment terms",
            "Due date",
            "Tax details",
          ].map((label) => (
            <div className="pending-cell" key={label}>
              <div className="eyebrow">{label}</div>
              <strong>—</strong>
              <p className="text-xs muted">Not available</p>
            </div>
          ))}
        </div>
        <section className="panel invoice-identity">
          <div>
            <h2>Customer & Invoice Address</h2>
            <p className="text-xs mt-2">
              No invoice customer or billing address is available.
            </p>
          </div>
          <span className="pill">NO INVOICE LOADED</span>
        </section>
        <Panel
          title="Billable Items & Tax Allocations"
          subtitle="Immutable invoice lines will be displayed when issued invoices are supported"
        >
          <Table
            label="Invoice items"
            columns={[
              { name: "Item & description" },
              { name: "Quantity", numeric: true },
              { name: "Unit rate", numeric: true },
              { name: "Discount", numeric: true },
              { name: "Tax rate", numeric: true },
              { name: "Net amount", numeric: true },
            ]}
          >
            <tr>
              <td colSpan={6}>
                <Unavailable detail="Invoice lines, tax allocations, and discounts are not available. Subscription charges have not been presented as invoice amounts." />
              </td>
            </tr>
          </Table>
          <div className="invoice-summary">
            <div className="detail-cell">
              <div className="eyebrow">INVOICE NOTES</div>
              <p>
                No invoice notes, statutory declarations, or payment
                instructions are available.
              </p>
            </div>
            <div className="financial-summary m-0! max-w-none!">
              {[
                "Subtotal",
                "Discount",
                "Taxable amount",
                "Tax",
                "Total invoice amount",
                "Amount paid",
              ].map((label) => (
                <div key={label}>
                  <span>{label}</span>
                  <span>—</span>
                </div>
              ))}
              <div className="total">
                <span>Remaining balance</span>
                <span>—</span>
              </div>
              <p>Balances will come from invoice and payment records.</p>
            </div>
          </div>
        </Panel>
        <div className="two-columns equal-columns">
          <Panel title="Payment History">
            <Unavailable detail="No payment records can be retrieved until payment APIs are implemented." />
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
                  <input
                    placeholder="Unavailable"
                    aria-label="Payment amount"
                  />
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
      </div>
    </Shell>
  );
}
