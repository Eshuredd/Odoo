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
