"use client";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Shell } from "@/components/shell";
import { PageHeader, Panel, Unavailable } from "@/components/ui";

export default function InvoicesPage() {
  return (
    <Shell>
      <div className="stack">
        <PageHeader
          title="Invoices"
          description="Issued invoices, balances, and recorded payments will be available here once invoicing is supported."
        />
        <Panel title="Invoice Register">
          <Unavailable
            title="Invoices are not available yet"
            detail="The current backend does not expose invoices or payment records. No sample invoices or balances are presented as real data."
          />
          <div className="form-actions">
            <Link href="/invoices/pending" className="button button-secondary">
              Invoice detail workspace
              <ArrowUpRight size={15} />
            </Link>
          </div>
        </Panel>
      </div>
    </Shell>
  );
}
