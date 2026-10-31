"use client";
import { Shell } from "@/components/shell";
import { PageHeader } from "@/components/ui";
import { PaymentHistory } from "@/components/payments";
export default function Page() {
  return (
    <Shell>
      <div className="stack">
        <PageHeader
          title="Payments"
          description="Your accessible manually recorded payments, ordered newest first."
        />
        <PaymentHistory />
      </div>
    </Shell>
  );
}
