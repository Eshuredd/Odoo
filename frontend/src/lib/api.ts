import { isLosslessNumber, parse, stringify } from "lossless-json";
import type {
  ActionBody,
  Customer,
  LifecycleAction,
  LoginResponse,
  Page,
  Plan,
  Product,
  Query,
  Subscription,
  SubscriptionCreate,
  User,
  Variant,
  BillingReport,
  Invoice,
  Payment,
  PaymentInput,
  ReportSummary,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function decodeJSON(text: string): unknown {
  function convert(value: unknown, key = ""): unknown {
    if (isLosslessNumber(value)) {
      if (!/^-?\d+$/.test(value.value))
        throw new Error("The API returned an unexpected non-integer value.");
      if (key.endsWith("_paise")) return BigInt(value.value);
      const integer = Number(value.value);
      if (!Number.isSafeInteger(integer))
        throw new Error(
          "The API returned an identifier or count outside the supported range.",
        );
      return integer;
    }
    if (Array.isArray(value)) return value.map((item) => convert(item));
    if (value !== null && typeof value === "object")
      return Object.fromEntries(
        Object.entries(value).map(([name, item]) => [
          name,
          convert(item, name),
        ]),
      );
    return value;
  }
  return convert(parse(text));
}

function errorMessage(body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((item) => {
        const error = item as { loc?: (string | number)[]; msg?: string };
        return `${error.loc?.filter((part) => part !== "body").join(".") || "Request"}: ${error.msg || "Invalid value"}`;
      })
      .join(" · ");
  return "The request could not be completed. Please try again.";
}

export class ApiClient {
  private token: string | null = null;
  private onUnauthorized: (() => void) | undefined;
  constructor(private baseURL: string) {}
  setToken(token: string | null): void {
    this.token = token;
  }
  setUnauthorizedHandler(handler: (() => void) | undefined): void {
    this.onUnauthorized = handler;
  }

  async request<T>(
    path: string,
    options: {
      method?: string;
      body?: unknown;
      signal?: AbortSignal;
      public?: boolean;
    } = {},
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (options.body !== undefined)
      headers["Content-Type"] = "application/json";
    if (!options.public && this.token)
      headers.Authorization = `Bearer ${this.token}`;
    let response: Response;
    try {
      response = await fetch(`${this.baseURL.replace(/\/$/, "")}${path}`, {
        method: options.method ?? "GET",
        headers,
        body: options.body === undefined ? undefined : stringify(options.body),
        signal: options.signal,
        cache: "no-store",
        credentials: "omit",
      });
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") throw error;
      throw new ApiError(
        0,
        "Cannot reach SubCadence. Check that the backend is running and the API URL and CORS origin are configured.",
      );
    }
    if (response.status === 401 && !options.public) this.onUnauthorized?.();
    const raw = await response.text();
    let body: unknown;
    try {
      body = raw ? decodeJSON(raw) : undefined;
    } catch {
      throw new ApiError(
        response.status,
        "The API returned an unreadable response. No values have been estimated.",
      );
    }
    if (!response.ok) throw new ApiError(response.status, errorMessage(body));
    return body as T;
  }

  private query(query: Query): string {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query))
      if (value !== undefined && value !== "") params.set(key, String(value));
    return params.size ? `?${params}` : "";
  }
  billingPreview(as_of: string) {
    return this.request<BillingReport>("/billing/preview", {
      method: "POST",
      body: { as_of },
    });
  }
  billingRun(as_of: string) {
    return this.request<BillingReport>("/billing/run", {
      method: "POST",
      body: { as_of },
    });
  }
  invoices(query: Query = {}, signal?: AbortSignal) {
    return this.request<Page<Invoice>>(`/invoices${this.query(query)}`, {
      signal,
    });
  }
  invoice(id: number, signal?: AbortSignal, asOf?: string) {
    return this.request<Invoice>(
      `/invoices/${id}${asOf ? this.query({ as_of: asOf }) : ""}`,
      { signal },
    );
  }
  invoiceAction(id: number, action: "confirm" | "cancel") {
    return this.request<Invoice>(`/invoices/${id}/${action}`, {
      method: "POST",
    });
  }
  recordPayment(id: number, body: PaymentInput) {
    return this.request<Payment>(`/invoices/${id}/payments`, {
      method: "POST",
      body,
    });
  }
  settleZero(id: number) {
    return this.request<Invoice>(`/invoices/${id}/settle-zero`, {
      method: "POST",
    });
  }
  payments(query: Query = {}, signal?: AbortSignal) {
    return this.request<Page<Payment>>(`/payments${this.query(query)}`, {
      signal,
    });
  }
  invoicePayments(id: number, query: Query = {}, signal?: AbortSignal) {
    return this.request<Page<Payment>>(
      `/invoices/${id}/payments${this.query(query)}`,
      { signal },
    );
  }
  summary(query: Query, signal?: AbortSignal) {
    return this.request<ReportSummary>(`/reports/summary${this.query(query)}`, {
      signal,
    });
  }
  login(email: string, password: string) {
    return this.request<LoginResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
      public: true,
    });
  }
  me(signal?: AbortSignal) {
    return this.request<User>("/auth/me", { signal });
  }
  logout() {
    return this.request<{ message: string }>("/auth/logout", {
      method: "POST",
    });
  }
  subscriptions(query: Query = {}, signal?: AbortSignal) {
    return this.request<Page<Subscription>>(
      `/subscriptions${this.query(query)}`,
      { signal },
    );
  }
  subscription(id: number, signal?: AbortSignal) {
    return this.request<Subscription>(`/subscriptions/${id}`, { signal });
  }
  createSubscription(body: SubscriptionCreate) {
    return this.request<Subscription>("/subscriptions", {
      method: "POST",
      body,
    });
  }
  action(id: number, action: LifecycleAction, body: ActionBody) {
    return this.request<Subscription>(`/subscriptions/${id}/${action}`, {
      method: "POST",
      body,
    });
  }
  customers(query: Query = {}, signal?: AbortSignal) {
    return this.request<Page<Customer>>(`/customers${this.query(query)}`, {
      signal,
    });
  }
  customer(id: number, signal?: AbortSignal) {
    return this.request<Customer>(`/customers/${id}`, { signal });
  }
  plans(query: Query = {}, signal?: AbortSignal) {
    return this.request<Page<Plan>>(`/plans${this.query(query)}`, { signal });
  }
  plan(id: number, signal?: AbortSignal) {
    return this.request<Plan>(`/plans/${id}`, { signal });
  }
  products(query: Query = {}, signal?: AbortSignal) {
    return this.request<Page<Product>>(`/products${this.query(query)}`, {
      signal,
    });
  }
  variants(productId: number, query: Query = {}, signal?: AbortSignal) {
    return this.request<Page<Variant>>(
      `/products/${productId}/variants${this.query(query)}`,
      { signal },
    );
  }
}
