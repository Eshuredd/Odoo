# REST API contract

Base path: `/api/v1`. Stages 1–3 implement health, authentication, staff creation, development outbox, customer profiles, catalog/plans, quotation templates, and subscription lifecycle. Billing/invoices/discounts/payments/reports remain planned. Swagger UI is at `/docs`; `/openapi.json` is the authoritative machine-readable schema for all exact request/response types/defaults/bounds. Documentation assets are served locally.

## Implemented health endpoint

`GET /api/v1/health` is public and executes `SELECT 1` through a request-scoped database session. HTTP 200 response:

```json
{"status":"ok","service":"subcadence-api"}
```

Database access failures return HTTP 503 with `{"detail":"Database unavailable"}`. No database path, credentials, SQL error, or traceback appears in that response. This is a connectivity check, not a check that migrations have been applied.

## Implemented authentication and administration

| Method and path | JSON request | Result and access |
| --- | --- | --- |
| `POST /auth/signup` | `email`, `password` | Public; 201 public user, always customer; 409 duplicate email |
| `POST /auth/login` | `email`, `password` | Public; 200 token response; unknown/wrong/inactive account gets the same 401 |
| `GET /auth/me` | None | Bearer required; current public user |
| `POST /auth/logout` | None | Bearer required; 200 message; revokes all sessions for this account |
| `POST /auth/password-reset/request` | `email` | Public; 200 identical generic message for eligible/unknown/inactive/SMTP-failure cases |
| `POST /auth/password-reset/confirm` | `token`, `new_password` | Public; 200 success message, 400 invalid/expired/used token, 422 invalid password |
| `POST /users/staff` | `email`, `password` | Active admin only; 201 public staff user; 409 duplicate, 401 anonymous, 403 staff/customer |
| `GET /dev/email-outbox` | None; query `limit`, `offset` | Active admin in development only; paginated full email content; 404 when not registered outside development |

All auth request models reject unexpected fields. Public signup/staff bodies cannot set `role`, `is_active`, or `auth_version`. Email is trimmed, syntax-validated offline, lowercased, and restricted to ASCII; internationalized input returns 422. Passwords require 9–128 characters, uppercase, lowercase, and a non-whitespace special character. Digits are optional; passwords are never trimmed or truncated. Login does not impose new-password composition rules on stored credentials but bounds password length to 128.

A public user has `id`, `email`, `role`, `is_active`, and UTC `created_at`. Password hashes and authentication versions are never included. Login responds:

```json
{
  "access_token": "<signed JWT>",
  "token_type": "bearer",
  "expires_in": 7200,
  "user": {"id": 1, "email": "customer@example.com", "role": "customer", "is_active": true, "created_at": "2026-10-31T00:00:00Z"}
}
```

Send `Authorization: Bearer <access_token>` on protected requests. Tokens use HS256 and require subject, issued-at, expiry, auth version, issuer, and audience. The current database role/active state/version are loaded per request; client/JWT role values are never authority. Logout/reset invalidate every existing token for the account by incrementing its stored version. Missing, expired, tampered, revoked, or otherwise invalid authentication returns 401 with `WWW-Authenticate: Bearer`. Valid users without permission receive 403. Missing/insecure AUTH_SECRET_KEY returns generic 503 for auth endpoints; health remains public and usable.

Reset request response:

```json
{"message":"If the account exists, password reset instructions have been sent."}
```

Reset URLs use `PASSWORD_RESET_BASE_URL?token=<random-token>`. The future frontend must collect the new password and POST the token to confirm; no reset webpage exists now. A reset token expires after 30 minutes, is consumed once, and is replaced by a newer request. Confirmation atomically replaces the Argon2id hash, consumes the token, revokes sessions, and records an audit. Success: `{"message":"Password reset successful. Please log in again."}`. Invalid/expired/consumed tokens all get `{"detail":"Invalid or expired reset token"}`. No raw token is included in these API responses.

With SMTP absent, email content goes to the local database outbox. Admins can retrieve `GET /dev/email-outbox?limit=20&offset=0` in `APP_ENV=development`. Items contain `id`, `recipient_email`, `subject`, `body`, and `created_at`, ordered newest first by timestamp then ID. Full bodies intentionally expose usable reset links to the local demo admin: protect this database and API. The endpoint is absent from routing and OpenAPI in `test`/`production`. Authentication and outbox responses use `Cache-Control: no-store`.

The future Next.js frontend will send Bearer headers and keep tokens in memory, reauthenticate after two hours/revocation, invoke server-side logout, and clear local state. No refresh-token, cookie-session, or frontend implementation is provided.

## Resource roadmap

| Prefix | Responsibility | Expected access |
| --- | --- | --- |
| `/auth` | Implemented signup, login, logout, current identity, password reset | See implemented contract above |
| `/users` | Staff creation implemented; broader account management deferred | Admin creates staff; other operations need later contracts |
| `/customers` | Implemented profiles and transactional customer account creation | Admin/staff manage; customer reads/edits basic own profile |
| `/products` | Implemented products and sellable variants | Admin manages; staff reads; customers denied administrative catalog access |
| `/taxes` | Exclusive tax configuration in basis points | Admin manages; staff reads |
| `/plans` | Implemented billing periods, base charges, independent flags | Admin manages; staff reads/selects; customers denied administrative configuration |
| `/quotation-templates` | Reusable quote defaults, lines, and terms | Admin manages; staff uses/reads |
| `/subscriptions` | Quotations, snapshots, authorized lifecycle transitions | Admin/staff perform explicitly granted actions; customer reads own records |
| `/discounts` | Rule eligibility, validity, redemption limits | Admin creates/manages; staff may view operational eligibility; no unrestricted customer rule access |
| `/invoices` | Issued invoices, line snapshots, balances, overdue views | Admin/staff read operational records; customer reads own; generation through billing |
| `/payments` | Positive partial/full payment recording and allocations | Admin/staff record/read; customer reads own; no gateway |
| `/reports` | Financial summaries, aging, recurring charges, lifecycle analytics | Admin and appropriately scoped staff; any customer summary limited to own data |
| `/billing` | Explicit `as_of` billing runs, dry-run, run results | Admin or explicitly authorized staff/system invocation; never customers |

Commercial endpoints are detailed below. Future resource methods/permissions will be specified in their implementation stages. Automated billing must use the same accepted commercial terms.

## Shared planned conventions

- JSON bodies; IDs are stable integers unless a resource explicitly defines otherwise. Monetary fields are named with `_paise`, use integers, and represent INR. Rates use `_basis_points`. Timestamps use ISO 8601 UTC (`Z` or `+00:00`); billing dates use `YYYY-MM-DD`.
- Lists use `limit` (default 20, range 1–100) and `offset` (default 0, nonnegative). Return `{"items": [], "total": 0, "limit": 20, "offset": 0}`. Use deterministic ordering with an ID tie-breaker. Apply authorization/ownership filters before both counting and pagination. Later billing and reports may use dedicated bounded result schemas.
- Preserve FastAPI's `{"detail": ...}` error envelope. General errors use a safe string; validation returns a list with `type`, `loc`, and `msg`, omitting submitted inputs/context to protect credentials and tokens. Expected statuses: 400 for invalid reset tokens, 401 for missing/invalid credentials, 403 for disallowed operations, 404 for absent/inaccessible resources, 409 for uniqueness or state conflicts, 422 for invalid input, and 503 for database/auth-configuration unavailability. No stack traces, SMTP details, or sensitive database details in public responses.
- Customer ownership is enforced server-side on every record, relationship, list, report, and export. A guessed ID must not reveal another customer's records. Admin/staff access is separately authorized; being authenticated is insufficient.
- Idempotent billing and invoice period uniqueness are mandatory. Per-subscription transaction boundaries cover invoice persistence, discount redemption, and next billing date. Dry-run persists nothing. Payment retries and any general idempotency-key convention need a later explicit contract.

Billing/invoice/discount/payment/report resources remain documentation only; there are no placeholder routes for them.

## Stage 3 implemented routes

The following paths are relative to `/api/v1`. Every operation requires an active authenticated user. Admin-only writes return 403 to staff/customers; missing/invalid authentication returns 401. Admin/staff may operate customers/subscriptions; customers get SQL-filtered read access to their own records only. Inaccessible IDs return 404. All create operations return 201, ordinary reads/updates/actions return 200, and template-line deletion returns 204.

| Paths | Methods | Permissions |
| --- | --- | --- |
| `/customers` | GET, POST | GET: admin/staff all, customer own only; POST: admin/staff |
| `/customers/me` | GET | Own linked customer profile; admin/staff without one get 404 |
| `/customers/{id}` | GET, PATCH | Admin/staff all; customer own basic profile only |
| `/taxes`, `/taxes/{id}` | Collection GET/POST; detail GET/PATCH | Admin writes, staff reads; customers denied |
| `/products`, `/products/{id}` | Collection GET/POST; detail GET/PATCH | Admin writes, staff reads; customers denied |
| `/products/{product_id}/variants` | GET, POST | Admin writes, staff reads |
| `/products/{product_id}/variants/{id}` | GET, PATCH | Admin writes, staff reads; variant scoped to parent |
| `/plans`, `/plans/{id}` | Collection GET/POST; detail GET/PATCH | Admin writes, staff reads |
| `/quotation-templates`, `/quotation-templates/{id}` | Collection GET/POST; detail GET/PATCH | Admin writes, staff reads/uses |
| `/quotation-templates/{template_id}/lines` | GET, POST | Admin writes, staff reads |
| `/quotation-templates/{template_id}/lines/{id}` | PATCH, DELETE | Admin only; line scoped to parent |
| `/subscriptions` | GET, POST | GET: admin/staff all, customer own; POST: admin/staff |
| `/subscriptions/{id}` | GET | Admin/staff all, customer own |
| `/subscriptions/from-template` | POST | Admin/staff |
| `/subscriptions/{id}/quotation` | POST | Admin/staff; Draft only |
| `/subscriptions/{id}/confirm` | POST | Admin/staff; valid Quotation only |
| `/subscriptions/{id}/activate` | POST | Admin/staff; Confirmed only |
| `/subscriptions/{id}/close` | POST | Admin/staff; Active and accepted closable flag |
| `/subscriptions/{id}/pause` | POST | Admin/staff; Active, unpaused, accepted pausable flag |
| `/subscriptions/{id}/resume` | POST | Admin/staff; Active and paused |
| `/subscriptions/{id}/renew` | POST | Admin/staff; Active and accepted renewable flag |

No catalog/customer/plan/subscription hard-delete or subscription-commercial-term PATCH is exposed. Deactivate catalog/plan/template records with PATCH active=false. Template-line edits/deletions affect only the template's own rows.

## Stage 3 exact schema conventions

All inputs reject extra fields. Names are trimmed and nonempty (maximum 200 characters); variant attribute/value maximum 100. Money is strict JSON integer paise, 0–9,223,372,036,854,775,807. Rates are strict integers 0–10,000 basis points. Quantities are strict integers 1–1,000,000. Booleans are JSON true/false, not numeric or string substitutes. IDs are positive SQLite-range integers. Optional IDs may be null where specified. New subscription/template line arrays have at most 100 entries. Date fields are ISO `YYYY-MM-DD`; timestamps are aware UTC.

| Create input | Required fields | Optional fields/defaults |
| --- | --- | --- |
| CustomerCreate | email, password, company_name, contact_name | phone=null (max 50), notes=null (max 10,000) |
| TaxCreate | name, rate_basis_points | active=true |
| ProductCreate | name, product_type (`goods`/`service`), sales_price_paise | cost_price_paise=0, notes=null, tax_id=null, active=true |
| VariantCreate | attribute, value | extra_price_paise=0, active=true; parent product comes from path |
| PlanCreate | name, price_paise, billing_period (`daily`/`weekly`/`monthly`/`yearly`), valid_from, valid_to | min_quantity=1; auto_close=false, closable=true, pausable=false, renewable=true, active=true |
| TemplateCreate | name, plan_id | validity_days=30 (1–3650), active=true, lines=[] |
| LineInput | product_id, quantity | variant_id=null |
| SubscriptionCreate | customer_id, plan_id, start_date, expiry_date, as_of, lines (1–100) | payment_terms_days=0 (0–3650) |
| FromTemplate | customer_id, template_id, start_date, expiry_date, as_of | payment_terms_days=0; lines/plan copied from template; returned state is quotation |

Signup remains backwards compatible with email/password and the same public-user response. It additionally accepts company_name (default empty), contact_name (default email local part), and phone=null, and inserts the associated profile transactionally. Existing customer accounts are backfilled during migration. Public signup cannot set notes, role, user_id, or profile ID.

PATCH accepts only the corresponding mutable create fields, all optional, and updates only supplied fields. Product PATCH excludes variant management, which uses its own endpoints. Customer PATCH allows company_name/contact_name/phone/notes; only admin/staff may write notes, and email/password/user_id cannot be patched. Explicit null is permitted only for product notes/tax_id, customer phone/notes, and template-line variant_id. Required fields cannot be set to null. Partial plan-date changes are checked against the other stored date. Template PATCH may replace lines with a new array (including empty). Template-line PATCH accepts product_id/variant_id/quantity, revalidating the resulting pair.

Response schemas include:

- CustomerOut: id, user_id, company_name, contact_name, nullable phone/notes, created_at, updated_at. No credentials.
- TaxOut: id plus TaxCreate fields and created_at.
- ProductOut: id plus ProductCreate fields and created_at/updated_at.
- VariantOut: id, product_id plus VariantCreate fields.
- PlanOut: id plus PlanCreate fields and created_at/updated_at.
- TemplateLineOut: id, template_id plus LineInput fields.
- TemplateOut: id, name, validity_days, plan_id, active, lines=[TemplateLineOut].
- SubscriptionLineOut: id, subscription_id, product_id, nullable variant_id, quantity, unit_price_paise, tax_rate_basis_points, amount_paise.
- SubscriptionOut: id, number, customer_id, plan_id, status, start_date, expiry_date, nullable quotation_date/quotation_expiry_date, payment_terms_days, nullable next_invoice_date, is_paused, recurring_base_price_paise, nullable billing_period/commercial_snapshot, created_at, updated_at, lines=[SubscriptionLineOut].

`commercial_snapshot` is null until confirmation. Once confirmed it contains `plan` (id, name, billing_period, min_quantity, auto_close, closable, pausable, renewable), `lines` (product_id/product_name, nullable variant_id/attribute/value/tax_id/tax_name), start_date, original_expiry_date, and payment_terms_days. Final amounts/rates/quantities reside on frozen SubscriptionLine rows; base charge resides on Subscription. No tax amount or invoice grand total is computed in Stage 3.

Action bodies:

```json
{"as_of":"2026-01-15"}
```

Quotation additionally accepts `validity_days` (default 30). Renew additionally requires `new_expiry_date`, later than both prior expiry and as_of. Lifecycle/status values are lowercase: draft → quotation → confirmed → active → closed. Illegal transitions, expired quotations, and forbidden pause/close/renew states return 409; invalid references, quantities, availability, dates, or overflow return 422. Duplicate catalog variant configuration returns 409. Failed operations leave mutations and audit entries rolled back.

Plan availability is checked inclusively on explicit as_of for new sales and confirmation. Quotation expiry is quotation_date + validity_days, inclusive for confirmation. Confirmation uses current selected catalog prices and freezes them. Activation requires start_date <= as_of <= expiry_date and sets next_invoice_date to original start, even for delayed activation. Pause/resume never advance billing dates; no scheduler, invoice generation, paused-period catch-up, or proration exists yet.

Every list returns the shared items/total/limit/offset envelope, using SQL counts, deterministic ascending IDs, and ownership before filtering/counting. Filters: customers search company/contact; taxes/products/plans/templates search name and active; products tax_id/product_type; variants active; plans as_of availability; templates plan_id; subscriptions customer_id/plan_id/product_id/status/search(number). Searches use escaped literal substrings. Product filtering uses EXISTS so multiple lines do not duplicate subscriptions. limit defaults to 20 (1–100); offset defaults to 0 (nonnegative SQLite-range integer).

## Stage 3 request examples

All URLs below start with `/api/v1`. Send an admin Bearer token for configuration; staff/admin may create and activate subscriptions. IDs in examples assume the preceding requests returned 1; use actual response IDs in practice. Business dates are supplied explicitly and may be independent of the server clock.

1. POST `/taxes`:

```json
{"name":"GST 18%","rate_basis_points":1800,"active":true}
```

2. POST `/products`, then POST `/products/1/variants`:

```json
{"name":"Business Software","product_type":"service","sales_price_paise":10000,"cost_price_paise":3000,"tax_id":1}
```

```json
{"attribute":"Brand","value":"Odoo","extra_price_paise":56000}
```

3. POST `/plans`:

```json
{"name":"Monthly Business","price_paise":50000,"billing_period":"monthly","min_quantity":2,"valid_from":"2026-01-01","valid_to":"2026-12-31","auto_close":false,"closable":true,"pausable":true,"renewable":true}
```

4. POST `/quotation-templates`:

```json
{"name":"Standard Quote","validity_days":14,"plan_id":1,"lines":[{"product_id":1,"variant_id":1,"quantity":2}]}
```

5. First sign up a synthetic customer or POST `/customers` with its validated initial credentials and company/contact names. Retrieve its CustomerProfile ID from `/customers`. POST `/subscriptions` for a Draft:

```json
{"customer_id":1,"plan_id":1,"start_date":"2026-01-15","expiry_date":"2026-07-15","payment_terms_days":15,"as_of":"2026-01-15","lines":[{"product_id":1,"variant_id":1,"quantity":2}]}
```

Alternatively POST `/subscriptions/from-template` to create a Quotation directly with copied lines:

```json
{"customer_id":1,"template_id":1,"start_date":"2026-01-15","expiry_date":"2026-07-15","payment_terms_days":15,"as_of":"2026-01-15"}
```

6. For a Draft returned with id 1, POST `/subscriptions/1/quotation`, then `/subscriptions/1/confirm`, then `/subscriptions/1/activate`, each with:

```json
{"as_of":"2026-01-15"}
```

Skip only the quotation action when starting from the from-template result, which is already a Quotation. The Active response has next_invoice_date=2026-01-15, recurring_base_price_paise=50000, line unit_price_paise=66000, amount_paise=132000, and tax_rate_basis_points=1800. These are separate base/line charges and a stored exclusive rate, not an invoice total. No invoices have been generated.
