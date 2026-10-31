export type Role = "admin" | "staff" | "customer";
export type Status = "draft" | "quotation" | "confirmed" | "active" | "closed";
export type BillingPeriod = "daily" | "weekly" | "monthly" | "yearly";
export interface User {
  id: number;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
export interface Customer {
  id: number;
  user_id: number;
  company_name: string;
  contact_name: string;
  phone: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}
export interface PlanTerms {
  id: number;
  name: string;
  billing_period: BillingPeriod;
  min_quantity: number;
  auto_close: boolean;
  closable: boolean;
  pausable: boolean;
  renewable: boolean;
}
export interface Plan extends PlanTerms {
  price_paise: bigint;
  valid_from: string;
  valid_to: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}
export interface Product {
  id: number;
  name: string;
  product_type: "goods" | "service";
  sales_price_paise: bigint;
  cost_price_paise: bigint;
  notes: string | null;
  tax_id: number | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}
export interface Variant {
  id: number;
  product_id: number;
  attribute: string;
  value: string;
  extra_price_paise: bigint;
  active: boolean;
}
export interface LineInput {
  product_id: number;
  variant_id: number | null;
  quantity: number;
}
export interface SubscriptionLine extends LineInput {
  id: number;
  subscription_id: number;
  unit_price_paise: bigint;
  tax_rate_basis_points: number;
  amount_paise: bigint;
}
export interface LineDescription {
  product_id: number;
  product_name: string;
  variant_id: number | null;
  attribute: string | null;
  value: string | null;
  tax_id: number | null;
  tax_name: string | null;
}
export interface CommercialSnapshot {
  plan: PlanTerms;
  lines: LineDescription[];
  start_date: string;
  original_expiry_date: string;
  payment_terms_days: number;
}
export interface Subscription {
  id: number;
  number: string;
  customer_id: number;
  plan_id: number;
  status: Status;
  start_date: string;
  expiry_date: string;
  quotation_date: string | null;
  quotation_expiry_date: string | null;
  payment_terms_days: number;
  next_invoice_date: string | null;
  is_paused: boolean;
  recurring_base_price_paise: bigint;
  billing_period: BillingPeriod | null;
  commercial_snapshot: CommercialSnapshot | null;
  created_at: string;
  updated_at: string;
  lines: SubscriptionLine[];
}
export interface SubscriptionCreate {
  customer_id: number;
  plan_id: number;
  start_date: string;
  expiry_date: string;
  payment_terms_days: number;
  as_of: string;
  lines: LineInput[];
}
export type LifecycleAction =
  | "quotation"
  | "confirm"
  | "activate"
  | "pause"
  | "resume"
  | "renew"
  | "close";
export interface ActionBody {
  as_of: string;
  validity_days?: number;
  new_expiry_date?: string;
}
export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}
export type Query = Record<string, string | number | boolean | undefined>;

export type InvoiceStatus = "draft" | "confirmed" | "paid" | "cancelled";
export interface InvoiceLine {
  id?: number;
  invoice_id?: number;
  line_type: "plan" | "product";
  product_id: number | null;
  variant_id: number | null;
  description: string;
  quantity: number;
  unit_price_paise: bigint;
  subtotal_paise: bigint;
  discount_paise: bigint;
  taxable_amount_paise: bigint;
  tax_rate_basis_points: number;
  tax_paise: bigint;
  total_paise: bigint;
}
export interface DiscountSnapshot {
  id: number;
  name: string;
  discount_type: "fixed" | "percentage";
  scope: "subscription" | "product";
  value_paise: bigint | null;
  rate_basis_points: number | null;
}
export interface InvoiceAmounts {
  subtotal_paise: bigint;
  discount_total_paise: bigint;
  tax_total_paise: bigint;
  total_paise: bigint;
  applied_discount_id: number | null;
  applied_discount_snapshot: DiscountSnapshot | null;
  lines: InvoiceLine[];
}
export interface Invoice extends InvoiceAmounts {
  paid_amount_paise: bigint;
  remaining_balance_paise: bigint;
  payment_progress: "unpaid" | "partial" | "paid";
  is_overdue: boolean | null;
  days_overdue: number | null;
  id: number;
  number: string;
  subscription_id: number;
  customer_id: number;
  period_start: string;
  period_end: string;
  invoice_date: string;
  due_date: string;
  status: InvoiceStatus;
  created_at: string;
  updated_at: string;
}
export type PaymentMethod = "cash" | "bank_transfer" | "upi" | "card" | "other";
export interface PaymentInput {
  amount_paise: bigint;
  method: PaymentMethod;
  payment_date: string;
  reference: string | null;
  note: string | null;
  idempotency_key: string;
}
export interface Payment {
  id: number;
  invoice_id: number;
  amount_paise: bigint;
  method: PaymentMethod;
  payment_date: string;
  reference: string | null;
  note: string | null;
  created_at: string;
}
export interface ReportSummary {
  as_of: string;
  from_date: string;
  to_date: string;
  active_subscription_count: number;
  paused_subscription_count: number;
  revenue_collected_paise: bigint;
  outstanding_balance_paise: bigint;
  overdue_invoice_count: number;
  overdue_amount_paise: bigint;
  aging_buckets: Record<
    string,
    { invoice_count: number; amount_paise: bigint }
  >;
  invoice_count_by_status: Record<InvoiceStatus, number>;
  monthly_collections: { month: string; amount_paise: bigint }[];
}
export interface BillingInvoice extends InvoiceAmounts {
  subscription_id: number;
  subscription_number: string;
  customer_id: number;
  period_start: string;
  period_end: string;
  invoice_date: string;
  due_date: string;
  invoice_id: number | null;
  invoice_number: string | null;
  disposition: "proposed" | "generated" | "existing";
  catch_up: boolean;
}
export interface BillingIssue {
  subscription_id: number;
  subscription_number: string;
  reason: string;
}
export interface BillingReport {
  as_of: string;
  dry_run: boolean;
  eligible_subscription_count: number;
  generated_or_proposed_invoice_count: number;
  projected_or_actual_total_paise: bigint;
  skipped_count: number;
  failed_count: number;
  invoices: BillingInvoice[];
  existing_invoices: BillingInvoice[];
  skipped: BillingIssue[];
  errors: BillingIssue[];
  auto_closed_subscription_ids: number[];
}
