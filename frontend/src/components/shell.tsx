"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowUpRight,
  Zap as Bolt,
  CircleHelp,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Search,
  ShieldCheck,
  X,
  RefreshCw,
} from "lucide-react";
import { useAuth } from "./auth-provider";
import { Brand } from "./brand";
import { Button, Loading, Notice } from "./ui";
import { initials, titleCase } from "@/lib/format";
import { isOperator } from "@/lib/lifecycle";

export function Shell({
  children,
  operatorOnly = false,
}: {
  children: ReactNode;
  operatorOnly?: boolean;
}) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [menu, setMenu] = useState(false);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  useEffect(() => {
    if (!user) router.replace("/login");
  }, [user, router]);
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setMenu(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  if (!user) return <Loading label="Opening your workspace…" />;
  const operator = isOperator(user.role);
  function searchSubscriptions(event: FormEvent) {
    event.preventDefault();
    router.push(`/subscriptions?search=${encodeURIComponent(search)}`);
  }
  const links = [
    {
      title: "Overview",
      items: [
        { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      ],
    },
    {
      title: "Operations",
      items: [
        { href: "/subscriptions", label: "Subscriptions", icon: RefreshCw },
      ],
    },
    {
      title: "Finance",
      items: [
        ...(operator
          ? [{ href: "/billing", label: "Billing Center", icon: Bolt }]
          : []),
        { href: "/invoices", label: "Invoices", icon: FileText },
      ],
    },
  ];
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      {menu && (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        />
      )}
      <aside
        id="workspace-navigation"
        className={`sidebar ${menu ? "sidebar-open" : ""}`}
      >
        <div className="sidebar-top">
          <Brand />
          <Button
            variant="ghost"
            className="mobile-close"
            aria-label="Close navigation"
            onClick={() => setMenu(false)}
          >
            <X size={18} />
          </Button>
        </div>
        <div className="role-context">
          <ShieldCheck size={17} />
          <div>
            <span>ACTIVE CONTEXT</span>
            <strong>{titleCase(user.role)}</strong>
          </div>
        </div>
        <nav aria-label="Main navigation">
          {links.map((group) => (
            <div className="nav-group" key={group.title}>
              <div className="nav-label">{group.title}</div>
              {group.items.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMenu(false)}
                  aria-current={
                    pathname === item.href ||
                    pathname.startsWith(item.href + "/")
                      ? "page"
                      : undefined
                  }
                  className="nav-link"
                >
                  <item.icon size={18} />
                  <span>{item.label}</span>
                  {["/billing", "/invoices"].includes(item.href) && (
                    <span className="nav-pending">Pending</span>
                  )}
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span>
            <i />
            LOCAL DEVELOPMENT
          </span>
          <p>INR · Single-currency workspace</p>
          <a
            href={`${(process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api/v1").replace(/\/api\/v1\/?$/, "")}/docs`}
            target="_blank"
            rel="noreferrer"
          >
            <CircleHelp size={13} />
            API documentation
            <ArrowUpRight size={12} />
          </a>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <Button
            variant="ghost"
            className="menu-toggle"
            aria-label="Open navigation"
            aria-controls="workspace-navigation"
            aria-expanded={menu}
            onClick={() => setMenu(!menu)}
          >
            <Menu size={21} />
          </Button>
          <form className="global-search" onSubmit={searchSubscriptions}>
            <Search size={16} />
            <input
              aria-label="Search subscription number"
              placeholder="Search subscriptions…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <kbd>↵</kbd>
          </form>
          <div className="topbar-actions">
            {operator && (
              <>
                <Button
                  disabled
                  title="Billing execution is not available yet."
                  className="run-billing"
                >
                  <Bolt size={14} />
                  Run Billing
                </Button>
                <Link
                  className="button button-primary new-subscription"
                  href="/subscriptions/new"
                >
                  <Plus size={15} />
                  New Subscription
                </Link>
              </>
            )}
            <div className="identity">
              <span className="avatar">{initials(user.email)}</span>
              <div>
                <strong>{user.email}</strong>
                <span>{titleCase(user.role)}</span>
              </div>
            </div>
            <Button
              variant="ghost"
              aria-label="Sign out"
              disabled={signingOut}
              onClick={async () => {
                setError("");
                setSigningOut(true);
                try {
                  await logout();
                } catch (cause) {
                  setError(
                    cause instanceof Error
                      ? cause.message
                      : "Sign out failed. Try again.",
                  );
                } finally {
                  setSigningOut(false);
                }
              }}
            >
              <LogOut size={17} />
            </Button>
          </div>
        </header>
        <main id="main-content" className="main-content">
          {error && <Notice>{error}</Notice>}
          {operatorOnly && !operator ? (
            <Notice>
              You do not have access to this page.{" "}
              <Link href="/subscriptions">View your subscriptions</Link>.
            </Notice>
          ) : (
            children
          )}
        </main>
        <footer className="workspace-footer">
          SubCadence <span>Subscription management · INR</span>
        </footer>
      </div>
    </div>
  );
}
