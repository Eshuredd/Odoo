"use client";
import {
  Zap as Bolt,
  ClipboardCheck,
  FlaskConical,
  RefreshCw,
} from "lucide-react";
import { Shell } from "@/components/shell";
import {
  Button,
  KpiCard,
  Notice,
  PageHeader,
  Panel,
  Table,
  Unavailable,
} from "@/components/ui";
import { todayInIndia } from "@/lib/format";

export default function BillingPage() {
  return (
    <Shell operatorOnly>
      <div className="stack">
        <PageHeader
          title="Automated Billing Center"
          description="The workspace for future recurring invoice previews, actual billing execution, and catch-up period review."
          actions={<span className="pill">BILLING NOT AVAILABLE</span>}
        />
        <Notice kind="info">
          Billing APIs are pending. Preview and execution are disabled, and no
          invoice amounts or run results are estimated.
        </Notice>
        <Panel
          title="Execution Parameters"
          subtitle="Preview and actual execution will be separate actions"
          action={<span className="pill">PENDING</span>}
        >
          <div className="panel-body">
            <fieldset disabled className="pending-grid">
              <div className="pending-cell">
                <label htmlFor="billing-date">Run billing as of date</label>
                <input
                  id="billing-date"
                  type="date"
                  defaultValue={todayInIndia()}
                />
              </div>
              <div className="pending-cell">
                <label htmlFor="billing-cadence">Cadence scope</label>
                <select id="billing-cadence">
                  <option>All recurring</option>
                  <option>Daily</option>
                  <option>Weekly</option>
                  <option>Monthly</option>
                  <option>Yearly</option>
                </select>
              </div>
              <div className="pending-cell">
                <label htmlFor="billing-accounts">Customer scope</label>
                <select id="billing-accounts">
                  <option>Not evaluated</option>
                </select>
              </div>
              <div className="pending-cell">
                <label htmlFor="billing-strategy">Missed periods</label>
                <select id="billing-strategy">
                  <option>Catch-up rules pending</option>
                </select>
              </div>
              <div className="pending-cell">
                <label htmlFor="billing-mode">Execution mode</label>
                <select id="billing-mode">
                  <option>Dry-run preview</option>
                  <option>Actual execution</option>
                </select>
              </div>
            </fieldset>
            <div className="row wrap space-between mt-5">
              <p className="text-xs max-w-xl">
                A future preview will make no persistent changes. Actual
                execution will require a separate review and confirmation.
              </p>
              <div className="row">
                <Button disabled>
                  <FlaskConical size={15} />
                  Preview dry run
                </Button>
                <Button disabled variant="primary">
                  <Bolt size={15} />
                  Execute billing
                </Button>
              </div>
            </div>
          </div>
        </Panel>
        <div className="kpi-grid kpi-grid-five">
          <KpiCard
            label="Eligible subscriptions"
            value="—"
            detail="Eligibility has not been evaluated"
          />
          <KpiCard
            label="Invoices to generate"
            value="—"
            detail="Preview API pending"
            accent="cyan"
          />
          <KpiCard
            label="Invoice totals"
            value="—"
            detail="No amounts calculated"
            accent="green"
          />
          <KpiCard
            label="Catch-up periods"
            value="—"
            detail="No periods evaluated"
          />
          <KpiCard
            label="Failed subscriptions"
            value="—"
            detail="No billing run has executed"
            accent="rose"
          />
        </div>
        <Panel
          title="Billing Review"
          subtitle="Review existing periods and catch-up candidates before execution"
        >
          <div className="three-columns panel-body">
            <div className="detail-cell">
              <ClipboardCheck size={20} className="text-primary" />
              <h3 className="mt-3">Already billed periods</h3>
              <p>
                Will be distinguished from new invoice periods. No period
                history is available yet.
              </p>
            </div>
            <div className="detail-cell">
              <RefreshCw size={20} className="text-cyan" />
              <h3 className="mt-3">Catch-up periods</h3>
              <p>
                Missed periods will be reviewed separately, with paused-period
                rules finalized first.
              </p>
            </div>
            <div className="detail-cell">
              <FlaskConical size={20} className="text-primary" />
              <h3 className="mt-3">Dry-run vs execution</h3>
              <p>
                A preview will remain separate from persistent invoice
                generation.
              </p>
            </div>
          </div>
        </Panel>
        <Panel
          title="Generation Queue"
          subtitle="Preview candidates, billed periods, catch-up periods, and failures"
        >
          <Table
            label="Billing generation queue"
            columns={[
              { name: "Subscription #" },
              { name: "Customer" },
              { name: "Cycle assessment" },
              { name: "Target periods" },
              { name: "Invoice amount", numeric: true },
              { name: "Verdict" },
            ]}
          >
            <tr>
              <td colSpan={6}>
                <Unavailable
                  title="No billing evaluation available"
                  detail="The backend does not yet provide billing preview or execution. No candidates, results, or invoice totals are shown."
                />
              </td>
            </tr>
          </Table>
        </Panel>
        <div className="two-columns">
          <Panel
            title="Billing Workflow"
            subtitle="Future integration points; none of these steps has executed"
          >
            <div className="pipeline">
              {[
                "Evaluate contracts",
                "Check billed periods",
                "Generate invoices",
                "Record results",
              ].map((title, index) => (
                <div key={title}>
                  <span className="circle">{index + 1}</span>
                  <h3>{title}</h3>
                  <p>Pending backend support</p>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title="Previous Executions">
            <Unavailable detail="Billing run history will appear when execution and history APIs are available." />
          </Panel>
        </div>
      </div>
    </Shell>
  );
}
