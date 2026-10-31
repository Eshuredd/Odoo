"use client";
import Link from "next/link";
import { useCallback, useState, type FormEvent } from "react";
import { useAuth } from "./auth-provider";
import {
  Button,
  Empty,
  Loading,
  Modal,
  Notice,
  Pagination,
  Panel,
  Table,
} from "./ui";
import { useResource } from "@/lib/hooks";
import { formatDate, formatINR, parseINR, todayInIndia } from "@/lib/format";
import type { Invoice, PaymentMethod } from "@/lib/types";

export function PaymentHistory({
  invoiceId,
  revision = 0,
}: {
  invoiceId?: number;
  revision?: number;
}) {
  const { api } = useAuth();
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(10);
  const records = useResource(
    useCallback(
      (signal) => {
        void revision;
        return invoiceId
          ? api.invoicePayments(invoiceId, { limit, offset }, signal)
          : api.payments({ limit, offset }, signal);
      },
      [api, invoiceId, offset, revision, limit],
    ),
  );
  return (
    <Panel
      title="Payment History"
      subtitle="Manually recorded payments; no gateway processing"
    >
      {records.loading ? (
        <Loading />
      ) : records.error ? (
        <Notice>
          {records.error}
          <Button onClick={records.reload}>Retry</Button>
        </Notice>
      ) : records.data?.items.length ? (
        <Table
          label="Payments"
          columns={[
            { name: "Invoice" },
            { name: "Date" },
            { name: "Method" },
            { name: "Amount", numeric: true },
            { name: "Reference" },
          ]}
        >
          {records.data.items.map((row) => (
            <tr key={row.id}>
              <td>
                <Link href={`/invoices/${row.invoice_id}`}>
                  Invoice #{row.invoice_id}
                </Link>
              </td>
              <td>{formatDate(row.payment_date)}</td>
              <td>{row.method.replaceAll("_", " ")}</td>
              <td className="numeric money">{formatINR(row.amount_paise)}</td>
              <td>{row.reference || "—"}</td>
            </tr>
          ))}
        </Table>
      ) : (
        <Empty
          title="No payments recorded"
          detail="Payment records will appear after a successful manual payment."
        />
      )}
      {records.data && (
        <Pagination
          total={records.data.total}
          limit={limit}
          offset={offset}
          onChange={(next, size) => {
            setOffset(next);
            setLimit(size);
          }}
        />
      )}
    </Panel>
  );
}
export function PaymentDialog({
  invoice,
  onClose,
  onPaid,
}: {
  invoice: Invoice;
  onClose: () => void;
  onPaid: (invoice: Invoice) => void;
}) {
  const { api } = useAuth();
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<PaymentMethod>("bank_transfer");
  const [date, setDate] = useState(todayInIndia);
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [key] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (invoice.total_paise === 0n) {
        onPaid(await api.settleZero(invoice.id));
        onClose();
        return;
      }
      const paise = parseINR(amount);
      if (paise <= 0n) throw new Error("Payment must be greater than zero.");
      if (paise > invoice.remaining_balance_paise)
        throw new Error("Payment exceeds the outstanding balance.");
      await api.recordPayment(invoice.id, {
        amount_paise: paise,
        method,
        payment_date: date,
        reference: reference || null,
        note: note || null,
        idempotency_key: key,
      });
      try {
        onPaid(await api.invoice(invoice.id, undefined, todayInIndia()));
        onClose();
      } catch {
        setError(
          "Payment was recorded. Retry this unchanged request to refresh safely; do not create another payment.",
        );
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Payment recording failed.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={
        invoice.total_paise === 0n
          ? "Settle zero invoice"
          : "Record manual payment"
      }
      onClose={onClose}
      busy={busy}
    >
      <form onSubmit={submit} className="panel-body stack">
        <p>
          Outstanding:{" "}
          <strong>{formatINR(invoice.remaining_balance_paise)}</strong>. This
          records an existing payment; it does not transfer funds.
        </p>
        {invoice.total_paise === 0n ? (
          <p>
            Explicitly mark this confirmed zero-total invoice Paid without
            creating a zero-amount payment.
          </p>
        ) : (
          <fieldset disabled={busy} className="form-grid">
            <label className="field">
              Amount (INR)
              <input
                autoFocus
                required
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                maxLength={24}
              />
            </label>
            <label className="field">
              Payment method
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value as PaymentMethod)}
              >
                {["cash", "bank_transfer", "upi", "card", "other"].map(
                  (value) => (
                    <option key={value} value={value}>
                      {value.replaceAll("_", " ")}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label className="field">
              Payment date
              <input
                type="date"
                required
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </label>
            <label className="field">
              Reference
              <input
                maxLength={200}
                value={reference}
                onChange={(e) => setReference(e.target.value)}
              />
            </label>
            <label className="field">
              Note
              <textarea
                maxLength={2000}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
          </fieldset>
        )}
        {error && <Notice>{error}</Notice>}
        <div className="form-actions">
          <Button type="button" disabled={busy} onClick={onClose}>
            Go back
          </Button>
          <Button variant="primary" disabled={busy}>
            {busy
              ? "Saving…"
              : invoice.total_paise === 0n
                ? "Confirm zero settlement"
                : "Save payment"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
