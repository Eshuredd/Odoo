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
  PageHeader,
  Pagination,
  Panel,
  Table,
} from "./ui";
import { useResource } from "@/lib/hooks";
import { formatINR, parseINR, todayInIndia } from "@/lib/format";
import type { Page } from "@/lib/types";

type Row = { id: number; [key: string]: unknown };
type Field = {
  key: string;
  label: string;
  kind?:
    | "money"
    | "percent"
    | "number"
    | "date"
    | "boolean"
    | "password"
    | "email";
  choices?: string[];
  optional?: boolean;
  initial?: string | boolean;
  createOnly?: boolean;
};
type Definition = {
  title: string;
  path: string;
  fields: Field[];
  operatorWrite?: boolean;
  lines?: boolean;
};
const active: Field = {
  key: "active",
  label: "Active",
  kind: "boolean",
  initial: true,
};
const dates: Field[] = [
  {
    key: "valid_from",
    label: "Valid from",
    kind: "date",
    initial: todayInIndia(),
  },
  { key: "valid_to", label: "Valid to", kind: "date" },
];
const name: Field = { key: "name", label: "Name" };
export const definitions: Record<string, Definition> = {
  customers: {
    title: "Customers",
    path: "/customers",
    operatorWrite: true,
    fields: [
      { key: "company_name", label: "Company name" },
      { key: "contact_name", label: "Contact name" },
      { key: "email", label: "Email", kind: "email", createOnly: true },
      {
        key: "password",
        label: "Initial password",
        kind: "password",
        createOnly: true,
      },
      { key: "phone", label: "Phone", optional: true },
      { key: "notes", label: "Notes", optional: true },
    ],
  },
  taxes: {
    title: "Taxes",
    path: "/taxes",
    fields: [
      name,
      {
        key: "rate_basis_points",
        label: "Tax rate (%)",
        kind: "percent",
        initial: "0",
      },
      active,
    ],
  },
  products: {
    title: "Products",
    path: "/products",
    fields: [
      name,
      {
        key: "product_type",
        label: "Product type",
        choices: ["goods", "service"],
        initial: "service",
      },
      {
        key: "sales_price_paise",
        label: "Sales price (INR)",
        kind: "money",
        initial: "0",
      },
      {
        key: "cost_price_paise",
        label: "Cost price (INR)",
        kind: "money",
        initial: "0",
      },
      {
        key: "tax_id",
        label: "Tax ID (from Taxes)",
        kind: "number",
        optional: true,
      },
      { key: "notes", label: "Notes", optional: true },
      active,
    ],
  },
  plans: {
    title: "Subscription Plans",
    path: "/plans",
    fields: [
      name,
      {
        key: "price_paise",
        label: "Base price (INR)",
        kind: "money",
        initial: "0",
      },
      {
        key: "billing_period",
        label: "Billing period",
        choices: ["daily", "weekly", "monthly", "yearly"],
        initial: "monthly",
      },
      {
        key: "min_quantity",
        label: "Minimum product quantity",
        kind: "number",
        initial: "1",
      },
      ...dates,
      ...["auto_close", "closable", "pausable", "renewable"].map((key) => ({
        key,
        label: key.replaceAll("_", " "),
        kind: "boolean" as const,
        initial: key !== "auto_close",
      })),
      active,
    ],
  },
  "quotation-templates": {
    title: "Quotation Templates",
    path: "/quotation-templates",
    lines: true,
    fields: [
      name,
      { key: "plan_id", label: "Plan ID (from Plans)", kind: "number" },
      {
        key: "validity_days",
        label: "Quotation validity (days)",
        kind: "number",
        initial: "30",
      },
      active,
    ],
  },
  discounts: {
    title: "Discounts",
    path: "/discounts",
    fields: [
      name,
      {
        key: "discount_type",
        label: "Discount type",
        choices: ["fixed", "percentage"],
        initial: "percentage",
      },
      {
        key: "scope",
        label: "Scope",
        choices: ["subscription", "product"],
        initial: "subscription",
      },
      {
        key: "product_id",
        label: "Product ID (product scope only)",
        kind: "number",
        optional: true,
      },
      {
        key: "value_paise",
        label: "Fixed discount (INR; fixed type only)",
        kind: "money",
        optional: true,
      },
      {
        key: "rate_basis_points",
        label: "Percentage (%; percentage type only)",
        kind: "percent",
        optional: true,
      },
      {
        key: "minimum_purchase_paise",
        label: "Minimum invoice purchase (INR)",
        kind: "money",
        initial: "0",
      },
      {
        key: "minimum_quantity",
        label: "Minimum product quantity",
        kind: "number",
        initial: "1",
      },
      ...dates,
      {
        key: "usage_limit",
        label: "Global usage limit (blank = unlimited)",
        kind: "number",
        optional: true,
      },
      active,
    ],
  },
};
export function variantsDefinition(id: number): Definition {
  return {
    title: `Product #${id} Variants`,
    path: `/products/${id}/variants`,
    fields: [
      { key: "attribute", label: "Attribute" },
      { key: "value", label: "Value" },
      {
        key: "extra_price_paise",
        label: "Extra price (INR)",
        kind: "money",
        initial: "0",
      },
      active,
    ],
  };
}
function decimal(value: bigint) {
  return `${value / 100n}.${(value % 100n).toString().padStart(2, "0")}`;
}
export function Configuration({ definition }: { definition: Definition }) {
  const { api, user } = useAuth();
  const [offset, setOffset] = useState(0),
    [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Row | null | undefined>();
  const [notice, setNotice] = useState("");
  const [limit, setLimit] = useState(20);
  const writable =
    user?.role === "admin" ||
    (user?.role === "staff" && definition.operatorWrite);
  const resource = useResource(
    useCallback(
      (signal) =>
        api.request<Page<Row>>(
          `${definition.path}?limit=${limit}&offset=${offset}${definition.path.includes("/variants") ? "" : `&search=${encodeURIComponent(search)}`}`,
          { signal },
        ),
      [api, definition.path, offset, search, limit],
    ),
  );
  return (
    <div className="stack">
      <PageHeader
        title={definition.title}
        description="Configure real business records. Changes do not alter accepted subscription or invoice snapshots."
        actions={
          writable ? (
            <Button variant="primary" onClick={() => setEditing(null)}>
              Create {definition.title}
            </Button>
          ) : (
            <span className="pill">READ ONLY</span>
          )
        }
      />
      {notice && <Notice kind="success">{notice}</Notice>}
      {!definition.path.includes("/variants") && (
        <label className="field">
          Search {definition.title}
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </label>
      )}
      <Panel
        title={definition.title}
        subtitle="IDs can be used in related configuration forms"
      >
        {resource.loading ? (
          <Loading />
        ) : resource.error ? (
          <Notice>
            {resource.error}
            <Button onClick={resource.reload}>Retry</Button>
          </Notice>
        ) : resource.data?.items.length ? (
          <Table
            label={definition.title}
            columns={[
              { name: "ID" },
              { name: "Name / contact" },
              { name: "State / price" },
              { name: "Actions" },
            ]}
          >
            {resource.data.items.map((row) => (
              <tr key={row.id}>
                <td>#{row.id}</td>
                <td>
                  {String(
                    row.name || row.company_name || row.value || `#${row.id}`,
                  )}
                  <small>
                    {String(row.contact_name || row.attribute || "")}
                  </small>
                </td>
                <td>
                  {typeof row.price_paise === "bigint"
                    ? formatINR(row.price_paise)
                    : typeof row.sales_price_paise === "bigint"
                      ? formatINR(row.sales_price_paise)
                      : row.active === false
                        ? "Inactive"
                        : "Available"}
                  {row.times_used !== undefined && (
                    <small>{String(row.times_used)} redemptions</small>
                  )}
                </td>
                <td>
                  <div className="row wrap">
                    {writable && (
                      <Button onClick={() => setEditing(row)}>
                        Edit #{row.id}
                      </Button>
                    )}
                    {definition.path === "/products" && (
                      <Link
                        href={`/configuration/products/${row.id}/variants`}
                        className="button button-secondary"
                      >
                        Variants #{row.id}
                      </Link>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        ) : (
          <Empty
            title="No records found"
            detail="Create a record or adjust your search."
          />
        )}
        {resource.data && (
          <Pagination
            total={resource.data.total}
            offset={offset}
            limit={limit}
            onChange={(next, size) => {
              setOffset(next);
              setLimit(size);
            }}
          />
        )}
      </Panel>
      {editing !== undefined && (
        <RecordForm
          key={editing?.id || "new"}
          definition={definition}
          row={editing}
          onClose={() => setEditing(undefined)}
          onSaved={() => {
            setEditing(undefined);
            setNotice("Record saved by the backend.");
            resource.reload();
          }}
        />
      )}
    </div>
  );
}
function RecordForm({
  definition,
  row,
  onClose,
  onSaved,
}: {
  definition: Definition;
  row: Row | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { api } = useAuth();
  const fields = definition.fields.filter((field) => !row || !field.createOnly);
  const [values, setValues] = useState<Record<string, string | boolean>>(() =>
    Object.fromEntries(
      fields.map((field) => {
        let value =
          row?.[field.key] ??
          field.initial ??
          (field.kind === "boolean" ? false : "");
        if (typeof value === "bigint") value = decimal(value);
        else if (field.kind === "percent" && typeof value === "number")
          value = decimal(BigInt(value));
        return [field.key, typeof value === "boolean" ? value : String(value)];
      }),
    ),
  );
  const [lines, setLines] = useState<
    { product_id: string; variant_id: string; quantity: string }[]
  >(() =>
    (
      (row?.lines || []) as {
        product_id: number;
        variant_id: number | null;
        quantity: number;
      }[]
    ).map((line) => ({
      product_id: String(line.product_id),
      variant_id: line.variant_id ? String(line.variant_id) : "",
      quantity: String(line.quantity),
    })),
  );
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body: Record<string, unknown> = {};
      for (const field of fields) {
        const value = values[field.key];
        if (value === "" && field.optional) {
          body[field.key] = null;
          continue;
        }
        if (field.kind === "money") body[field.key] = parseINR(String(value));
        else if (field.kind === "number" || field.kind === "percent") {
          const number =
            field.kind === "percent"
              ? Number(parseINR(String(value)))
              : Number(value);
          if (!Number.isSafeInteger(number) || number < 0)
            throw new Error(
              `${field.label} must be a nonnegative whole value.`,
            );
          body[field.key] = number;
        } else body[field.key] = value;
      }
      if (definition.lines)
        body.lines = lines.map((line) => {
          const product = Number(line.product_id),
            quantity = Number(line.quantity),
            variant = line.variant_id ? Number(line.variant_id) : null;
          if (
            !Number.isSafeInteger(product) ||
            product < 1 ||
            !Number.isSafeInteger(quantity) ||
            quantity < 1 ||
            (variant !== null &&
              (!Number.isSafeInteger(variant) || variant < 1))
          )
            throw new Error(
              "Template lines need positive product IDs and quantities.",
            );
          return { product_id: product, variant_id: variant, quantity };
        });
      await api.request(`${definition.path}${row ? `/${row.id}` : ""}`, {
        method: row ? "PATCH" : "POST",
        body,
      });
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={`${row ? "Edit" : "Create"} ${definition.title}`}
      onClose={onClose}
      busy={busy}
    >
      <form onSubmit={submit} className="panel-body stack">
        <fieldset disabled={busy} className="form-grid">
          {fields.map((field) => (
            <label className="field" key={field.key}>
              {field.label}
              {field.kind === "boolean" ? (
                <input
                  type="checkbox"
                  checked={!!values[field.key]}
                  onChange={(e) =>
                    setValues({ ...values, [field.key]: e.target.checked })
                  }
                />
              ) : field.choices ? (
                <select
                  value={String(values[field.key])}
                  onChange={(e) =>
                    setValues({ ...values, [field.key]: e.target.value })
                  }
                >
                  {field.choices.map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              ) : (
                <input
                  required={!field.optional}
                  type={
                    ["date", "email", "password"].includes(field.kind || "")
                      ? field.kind
                      : "text"
                  }
                  inputMode={
                    ["money", "percent"].includes(field.kind || "")
                      ? "decimal"
                      : field.kind === "number"
                        ? "numeric"
                        : undefined
                  }
                  maxLength={field.kind === "password" ? 128 : 2000}
                  minLength={field.kind === "password" ? 9 : undefined}
                  value={String(values[field.key])}
                  onChange={(e) =>
                    setValues({ ...values, [field.key]: e.target.value })
                  }
                />
              )}
            </label>
          ))}
        </fieldset>
        {definition.lines && (
          <div className="stack">
            <h3>Template product lines</h3>
            {lines.map((line, index) => (
              <div className="form-grid" key={index}>
                {(["product_id", "variant_id", "quantity"] as const).map(
                  (key) => (
                    <label className="field" key={key}>
                      {key.replaceAll("_", " ")}
                      <input
                        inputMode="numeric"
                        value={line[key]}
                        onChange={(e) =>
                          setLines((current) =>
                            current.map((item, i) =>
                              i === index
                                ? { ...item, [key]: e.target.value }
                                : item,
                            ),
                          )
                        }
                      />
                    </label>
                  ),
                )}
                <Button
                  type="button"
                  onClick={() =>
                    setLines((current) => current.filter((_, i) => i !== index))
                  }
                >
                  Remove line {index + 1}
                </Button>
              </div>
            ))}
            <Button
              type="button"
              onClick={() =>
                setLines([
                  ...lines,
                  { product_id: "", variant_id: "", quantity: "1" },
                ])
              }
            >
              Add template line
            </Button>
          </div>
        )}
        {error && <Notice>{error}</Notice>}
        <div className="form-actions">
          <Button type="button" disabled={busy} onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={busy}>
            {busy ? "Saving…" : "Save record"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
