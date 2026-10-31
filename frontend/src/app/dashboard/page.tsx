"use client";
import Link from "next/link";
import { useMemo } from "react";
import { ArrowRight, Zap as Bolt, Plus } from "lucide-react";
import { Shell } from "@/components/shell";
import { useAuth } from "@/components/auth-provider";
import {
  Button,
  Empty,
  KpiCard,
  Loading,
  Notice,
  PageHeader,
  Panel,
  Unavailable,
} from "@/components/ui";
import {
  SubscriptionTable,
  useSubscriptionCounts,
  useSubscriptions,
} from "@/components/subscription-data";
import { isOperator, statuses } from "@/lib/lifecycle";
import { titleCase } from "@/lib/format";

export default function DashboardPage() {
  return (
    <Shell>
      <Dashboard />
    </Shell>
  );
}
function Dashboard() {
  const { user } = useAuth();
  const counts = useSubscriptionCounts();
  const query = useMemo(() => ({ limit: 5, offset: 0 }), []);
  const register = useSubscriptions(query);
  return (
    <div className="stack">
      <PageHeader
        eyebrow="MISSION CONTROL · SUBSCRIPTION OPERATIONS"
        title="Executive Revenue & Billing Dashboard"
        description="A clear view of your subscriptions and commercial lifecycle. Financial reporting will appear when billing is available."
        actions={
          <>
            {user && isOperator(user.role) && (
              <Link className="button button-primary" href="/subscriptions/new">
                <Plus size={15} />
                New Subscription
              </Link>
            )}
            {user && isOperator(user.role) && (
              <Link
                className="button button-secondary text-cyan"
                href="/billing"
              >
                <Bolt size={14} />
                Open Billing Center
              </Link>
            )}
          </>
        }
      />
      {counts.error && (
        <Notice>
          {counts.error}
          <Button onClick={counts.reload}>Retry counts</Button>
        </Notice>
      )}
      <div className="kpi-grid">
        <KpiCard
          label="Active subscriptions"
          value={counts.data?.active ?? "—"}
          detail={
            counts.loading
              ? "Loading subscription counts…"
              : counts.error
                ? "Count unavailable"
                : `${counts.data?.total ?? 0} subscriptions across all lifecycle states`
          }
        />
        <KpiCard
          label="Revenue collected"
          value="—"
          detail="Not available · payments are pending"
          accent="green"
        />
        <KpiCard
          label="Outstanding balance"
          value="—"
          detail="Not available · invoices are pending"
          accent="cyan"
        />
        <KpiCard
          label="Overdue invoices"
          value="—"
          detail="Not available · overdue tracking is pending"
          accent="rose"
        />
      </div>
      <div className="two-columns">
        <Panel
          title="Revenue Realization vs Expected MRR"
          subtitle="Collections and recurring revenue reporting"
        >
          <div className="chart-pending">
            <Unavailable
              title="Revenue reporting is not available yet"
              detail="No revenue, collection, or target amounts are estimated. Financial data will appear here once reporting is supported."
            />
          </div>
        </Panel>
        <Panel
          title="Lifecycle Distribution"
          subtitle="Current counts from your accessible subscriptions"
          action={
            <span className="pill">{counts.data?.total ?? "—"} TOTAL</span>
          }
        >
          <div className="distribution">
            {counts.loading ? (
              <Loading />
            ) : counts.data ? (
              <>
                <div className="distribution-track" aria-hidden="true">
                  {statuses.map((status, index) => (
                    <div
                      key={status}
                      style={{
                        width: `${counts.data!.total ? (counts.data![status] / counts.data!.total) * 100 : 0}%`,
                        background: [
                          "#918fa1",
                          "#c3c0ff",
                          "#4cd7f6",
                          "#4edea3",
                          "#464555",
                        ][index],
                      }}
                    />
                  ))}
                </div>
                <div className="distribution-rows">
                  {statuses.map((status) => (
                    <div className="distribution-item" key={status}>
                      <span>{titleCase(status)}</span>
                      <strong className="tabular">
                        {counts.data![status]}
                      </strong>
                    </div>
                  ))}
                </div>
                <p className="muted mt-4 text-xs">
                  Paused subscriptions remain in Active state.
                </p>
              </>
            ) : (
              <p className="muted text-xs">
                Lifecycle counts could not be loaded.
              </p>
            )}
          </div>
        </Panel>
      </div>
      <Panel
        title="Subscription Register"
        subtitle="Current agreements ordered by subscription number"
        action={
          <Link
            className="button button-ghost text-primary"
            href="/subscriptions"
          >
            View all
            <ArrowRight size={14} />
          </Link>
        }
      >
        {register.loading ? (
          <Loading />
        ) : register.error ? (
          <div className="panel-body">
            <Notice>
              {register.error}
              <Button onClick={register.reload}>Retry</Button>
            </Notice>
          </div>
        ) : register.data?.page.items.length ? (
          <SubscriptionTable
            rows={register.data.page.items}
            customers={register.data.customers}
            plans={register.data.plans}
          />
        ) : (
          <Empty
            title="No subscriptions yet"
            detail="Your subscription agreements will appear here."
          />
        )}
      </Panel>
      <div className="two-columns equal-columns">
        <Panel
          title="Overdue Invoices Requiring Attention"
          subtitle="Outstanding invoice balances"
        >
          <Unavailable detail="Invoices and overdue calculations are pending. There are no invoice balances to display." />
        </Panel>
        <Panel
          title="Recent Billing Events"
          subtitle="Invoice generation and payment activity"
        >
          <Unavailable detail="Billing events and payment history are not available yet." />
        </Panel>
      </div>
    </div>
  );
}
