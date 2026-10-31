"use client";
import Link from "next/link";
import { Suspense, useCallback, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Plus, Search } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Shell } from "@/components/shell";
import {
  Button,
  Empty,
  KpiCard,
  Loading,
  Notice,
  PageHeader,
  Pagination,
} from "@/components/ui";
import { RemoteSelect } from "@/components/remote-select";
import {
  SubscriptionTable,
  useSubscriptionCounts,
  useSubscriptions,
} from "@/components/subscription-data";
import { isOperator, statuses } from "@/lib/lifecycle";
import { titleCase } from "@/lib/format";
import type { Plan, Status } from "@/lib/types";

export default function SubscriptionsPage() {
  return (
    <Shell>
      <Suspense fallback={<Loading />}>
        <ListRoute />
      </Suspense>
    </Shell>
  );
}
function ListRoute() {
  const params = useSearchParams();
  return (
    <Subscriptions
      key={params.toString()}
      initialSearch={params.get("search") || ""}
      initialStatus={
        statuses.find((status) => status === params.get("status")) || ""
      }
    />
  );
}
function Subscriptions({
  initialSearch,
  initialStatus,
}: {
  initialSearch: string;
  initialStatus: Status | "";
}) {
  const { user, api } = useAuth();
  const [input, setInput] = useState(initialSearch);
  const [search, setSearch] = useState(initialSearch);
  const [status, setStatus] = useState<Status | "">(initialStatus);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const query = useMemo(
    () => ({ search, status, plan_id: plan?.id, offset, limit }),
    [search, status, plan, offset, limit],
  );
  const result = useSubscriptions(query);
  const counts = useSubscriptionCounts();
  const loadPlans = useCallback(
    (search: string, offset: number, signal: AbortSignal) =>
      api.plans({ search, offset, limit: 10 }, signal),
    [api],
  );
  return (
    <div className="stack">
      <PageHeader
        title="Subscriptions"
        description="Manage recurring subscription agreements, billing cadences, lifecycle states, and customer terms."
        actions={
          <>
            <span className="pill">{counts.data?.total ?? "—"} TOTAL</span>
            {user && isOperator(user.role) && (
              <Link href="/subscriptions/new" className="button button-primary">
                <Plus size={16} />
                Create Subscription
              </Link>
            )}
          </>
        }
      />
      <div className="kpi-grid kpi-grid-five">
        {(["active", "confirmed", "quotation", "draft", "closed"] as const).map(
          (state, index) => (
            <KpiCard
              key={state}
              label={titleCase(state)}
              value={counts.data?.[state] ?? "—"}
              detail={
                counts.error
                  ? "Count unavailable"
                  : "Across your accessible subscriptions"
              }
              accent={
                (["green", "cyan", "primary", "primary", "rose"] as const)[
                  index
                ]
              }
            />
          ),
        )}
      </div>
      <section className="panel" aria-label="Subscription filters">
        <div className="filter-bar">
          <form
            className="filter-search"
            onSubmit={(event) => {
              event.preventDefault();
              setSearch(input.trim());
              setOffset(0);
            }}
          >
            <Search size={17} />
            <input
              aria-label="Search subscription list"
              placeholder="Search by SUB-… subscription number"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              maxLength={200}
            />
            <Button type="submit" variant="ghost">
              Search
            </Button>
          </form>
          {user && isOperator(user.role) && (
            <RemoteSelect
              label="Plan filter"
              optional
              value={plan}
              onChange={(value) => {
                setPlan(value);
                setOffset(0);
              }}
              load={loadPlans}
              describe={(value) => value.name}
            />
          )}
        </div>
        <div className="tabs" role="tablist" aria-label="Subscription status">
          {(["", ...statuses] as const).map((value) => (
            <button
              key={value}
              role="tab"
              aria-selected={status === value}
              className="tab"
              onClick={() => {
                setStatus(value);
                setOffset(0);
              }}
            >
              {value ? titleCase(value) : "All"}
            </button>
          ))}
        </div>
      </section>
      <section className="panel" aria-label="Subscription records">
        {result.loading ? (
          <Loading />
        ) : result.error ? (
          <div className="panel-header">
            <Notice>
              {result.error}
              <Button onClick={result.reload}>Retry</Button>
            </Notice>
          </div>
        ) : result.data?.page.items.length ? (
          <>
            <SubscriptionTable
              rows={result.data.page.items}
              customers={result.data.customers}
              plans={result.data.plans}
            />
            <Pagination
              total={result.data.page.total}
              offset={offset}
              limit={limit}
              onChange={(nextOffset, nextLimit) => {
                setOffset(nextOffset);
                setLimit(nextLimit);
              }}
            />
          </>
        ) : (
          <Empty
            title="No matching subscriptions"
            detail={
              search || status || plan
                ? "Try a different search, plan, or lifecycle state."
                : "Create a subscription to begin the commercial workflow."
            }
          >
            {user && isOperator(user.role) && (
              <Link href="/subscriptions/new" className="button button-primary">
                Create Subscription
              </Link>
            )}
          </Empty>
        )}
      </section>
      <div className="three-columns">
        <div className="panel p-4">
          <h3>Confirmed terms stay fixed</h3>
          <p className="mt-2 text-xs">
            Accepted prices, tax rates, and plan flags are retained on each
            subscription.
          </p>
        </div>
        <div className="panel p-4">
          <h3>Pause is a condition</h3>
          <p className="mt-2 text-xs">
            Paused subscriptions remain Active. Pausing does not advance the
            billing date.
          </p>
        </div>
        <div className="panel p-4">
          <h3>Billing uses full periods</h3>
          <p className="mt-2 text-xs">
            Billing Center previews and generates due invoices. Pausing defers
            charges; payments remain unavailable.
          </p>
        </div>
      </div>
    </div>
  );
}
