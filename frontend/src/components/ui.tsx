"use client";
import {
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Inbox,
  LoaderCircle,
  LockKeyhole,
  X,
} from "lucide-react";
import type { Status } from "@/lib/types";
import { titleCase } from "@/lib/format";

export function Button({
  variant = "secondary",
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
}) {
  return (
    <button className={`button button-${variant} ${className}`} {...props}>
      {children}
    </button>
  );
}
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <section className="page-header">
      <div>
        <div className="eyebrow">{eyebrow || "SUBCADENCE WORKSPACE"}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </section>
  );
}
export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-header">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Badge({
  status,
  paused = false,
}: {
  status: Status;
  paused?: boolean;
}) {
  return (
    <span className={`status status-${paused ? "paused" : status}`}>
      <span className="status-dot" />
      {titleCase(status)}
      {paused ? " · Paused" : ""}
    </span>
  );
}
export function KpiCard({
  label,
  value,
  detail,
  accent = "primary",
}: {
  label: string;
  value: ReactNode;
  detail: string;
  accent?: "primary" | "green" | "cyan" | "rose";
}) {
  return (
    <div className={`kpi kpi-${accent}`}>
      <div className="eyebrow">{label}</div>
      <div className="metric">{value}</div>
      <p>{detail}</p>
      <div className="kpi-underline" />
    </div>
  );
}
export function Notice({
  children,
  kind = "error",
}: {
  children: ReactNode;
  kind?: "error" | "success" | "info";
}) {
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={`notice notice-${kind}`}
    >
      <AlertCircle size={18} />
      <div>{children}</div>
    </div>
  );
}
export function Loading({ label = "Loading records…" }: { label?: string }) {
  return (
    <div className="state" role="status">
      <LoaderCircle className="spin" size={24} />
      <p>{label}</p>
    </div>
  );
}
export function Empty({
  title = "No records found",
  detail = "Try changing your filters.",
  children,
}: {
  title?: string;
  detail?: string;
  children?: ReactNode;
}) {
  return (
    <div className="state">
      <Inbox size={28} />
      <h3>{title}</h3>
      <p>{detail}</p>
      {children}
    </div>
  );
}
export function Unavailable({
  title = "Not available yet",
  detail,
}: {
  title?: string;
  detail: string;
}) {
  return (
    <div className="unavailable">
      <LockKeyhole size={24} />
      <h3>{title}</h3>
      <p>{detail}</p>
      <span className="pill">Pending backend support</span>
    </div>
  );
}
export function Pagination({
  total,
  offset,
  limit,
  onChange,
  busy = false,
}: {
  total: number;
  offset: number;
  limit: number;
  onChange: (offset: number, limit: number) => void;
  busy?: boolean;
}) {
  return (
    <div className="pagination">
      <span>
        Showing{" "}
        <strong>
          {total ? offset + 1 : 0}–{Math.min(offset + limit, total)}
        </strong>{" "}
        of <strong>{total}</strong>
      </span>
      <label>
        Rows per page{" "}
        <select
          aria-label="Rows per page"
          value={limit}
          disabled={busy}
          onChange={(event) => onChange(0, Number(event.target.value))}
        >
          {[10, 20, 50, 100].map((size) => (
            <option key={size}>{size}</option>
          ))}
        </select>
      </label>
      <div className="pagination-actions">
        <Button
          aria-label="Previous page"
          disabled={busy || offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit), limit)}
        >
          <ArrowLeft size={14} />
          Previous
        </Button>
        <span className="page-number">{Math.floor(offset / limit) + 1}</span>
        <Button
          aria-label="Next page"
          disabled={busy || offset + limit >= total}
          onClick={() => onChange(offset + limit, limit)}
        >
          Next
          <ArrowRight size={14} />
        </Button>
      </div>
    </div>
  );
}
export function Table({
  columns,
  children,
  label,
}: {
  columns: { name: string; numeric?: boolean }[];
  children: ReactNode;
  label: string;
}) {
  return (
    <div
      className="table-scroll"
      tabIndex={0}
      aria-label={`${label}, horizontally scrollable`}
    >
      <table>
        <caption className="sr-only">{label}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.name}
                className={column.numeric ? "numeric" : ""}
                scope="col"
              >
                {column.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
  busy = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const element = dialog.current;
    const previous = document.activeElement as HTMLElement | null;
    element?.showModal();
    return () => {
      element?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = Array.from(
          dialog.current?.querySelectorAll<HTMLElement>(
            'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex="0"]',
          ) || [],
        ).filter((element) => element.getClientRects().length > 0);
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (!first || !last) {
          event.preventDefault();
          return;
        }
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            !dialog.current?.contains(document.activeElement))
        ) {
          event.preventDefault();
          last.focus();
        } else if (
          !event.shiftKey &&
          (document.activeElement === last ||
            !dialog.current?.contains(document.activeElement))
        ) {
          event.preventDefault();
          first.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(event) => {
        if (event.target === dialog.current && !busy) onClose();
      }}
    >
      <div className="modal-header">
        <h2 id={titleId}>{title}</h2>
        <Button
          variant="ghost"
          aria-label="Close dialog"
          disabled={busy}
          onClick={onClose}
        >
          <X size={20} />
        </Button>
      </div>
      {children}
    </dialog>
  );
}
