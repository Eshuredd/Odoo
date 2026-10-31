# SubCadence requirements

SubCadence is a subscription management and recurring billing system for the Odoo × Make-A-Ton hackathon. Stages 1–4 implement the backend foundation, authentication/RBAC/reset, mail delivery/outbox, admin seeding, customers, catalog/plans, quotations, subscription lifecycle, recurring billing, automatic discounts and immutable invoices. The Stitch Next.js frontend connects subscription and billing/invoice workflows. Payment recording, PDFs/email, and financial reports remain deferred. Supplied briefs are the requirements source; the Stage 4 financial decisions below supersede earlier deferred billing notes.

## Access and identity

| Role | Planned authority |
| --- | --- |
| Admin | Manage configuration, products, taxes, plans, quotation templates, users, discounts, and operational records; access reports and billing operations. Only admins create staff accounts and discount rules. |
| Staff | Manage customer quotations, authorized subscription transitions, invoices, and recorded payments; access operational reports. Cannot create staff accounts or discount rules. |
| Customer | View only their own profile, subscriptions, quotations, invoices, and payments. Self-service actions require an explicit later contract. |

Authorization runs on the server for every protected action. CustomerProfile is linked one-to-one to a customer-role User, protected by a unique foreign key and cross-table role triggers. Signup creates a profile in the same transaction; migration backfills existing customers. Staff/admin can create customer accounts with validated initial credentials, without acquiring staff/admin-creation privileges. Customers can edit their own basic company/contact/phone fields; profile notes are edited by staff/admin. Ownership filters apply to profile/subscription lists and detail queries using the authenticated User ID before counting/pagination; inaccessible IDs return 404. Apply equivalent filters to future exports/invoices. Never accept a caller-supplied customer ID as ownership proof. Inactive users cannot authenticate. Signup only creates customers and rejects unexpected privilege fields.

Passwords must contain **9–128 characters, at least one uppercase letter, one lowercase letter, and one special character**. A digit is not required; compliant passwords of 9–11 characters are valid. Whitespace alone is not a special character. Passwords are never trimmed or silently truncated. The same validator applies to signup, admin-created staff, reset, and admin seeding. Persist salted Argon2id hashes using argon2-cffi, never plaintext passwords. Validation responses identify the field and omit submitted values.

Authentication uses HS256 JWT Bearer access tokens valid for 2 hours. Required claims include subject, issued-at, expiry, authentication version, issuer, and audience. Signatures, algorithm, claims, and expiry are verified. Require a locally generated signing secret of at least 32 UTF-8 bytes (and 8 distinct characters), without a default. Auth endpoints fail closed with 503 when missing/insecure; health remains available. Every protected request loads the current active state, role, and authentication version from the database. Explicit logout increments the version and revokes **all** existing access tokens for that user. Password reset also revokes all sessions. There are no refresh tokens in Stage 2.

Authentication returns an immutable principal from a short-lived separate read session. The business request session is not queried, committed, or rolled back by authentication; services can independently use `with session.begin():`. Administrative writes recheck authority inside the write transaction.

Accepted email addresses must be syntactically valid ASCII, trimmed and lowercased consistently for signup, login, reset, and seeding. Reject unsupported internationalized addresses clearly. Keep the SQLite NOCASE UNIQUE constraint as the final duplicate arbiter; signup/staff duplicates return 409.

Password-reset requests return the same generic response for eligible, unknown, inactive, or undeliverable accounts. Generate 256-bit random tokens, store only SHA-256 digests in `password_reset_tokens`, expire them in 30 minutes, and consume them once. Replacement invalidates older unused tokens. Issuance and redemption use `BEGIN IMMEDIATE`; password replacement, consumption, version increment, and audit insertion commit atomically. A shared injectable UTC clock controls token lifecycle tests.

Configured SMTP uses the standard library with STARTTLS by default; credentials are refused without STARTTLS. Without SMTP configuration, the database outbox stores full email bodies for offline demonstrations and future invoice mail. **Outbox data is sensitive local demonstration data because it contains usable reset URLs.** Only active admins in development mode can use the paginated `/api/v1/dev/email-outbox`; the route is absent outside development. Never log credentials/tokens or expose raw reset tokens in other API responses. Demo data must be synthetic. SMTP errors do not expose account existence or provider details; failed delivery rolls back reset issuance. No automatic SMTP retry is implemented.

## Catalog and commercial configuration

- Products have nonempty names, goods/service type, active state, nonnegative integer-paise sales/cost prices, optional notes, and one optional tax. A selected variant adds its nonnegative extra price. Variant/product association is enforced in both services and composite foreign keys. Admin manages catalog records; staff reads them; customers cannot access administrative configuration. Deactivate instead of hard-deleting referenced records.
- Taxes are exclusive. Stage 3 configures rates and captures them on lines without calculating tax amounts. Rates are integer basis points in 0–10,000 (0–100%). Multiple taxes, discount allocation, and rounding order need later detailed rules.
- Plans support daily, weekly, monthly, and yearly periods, a nonnegative recurring base price, positive minimum product quantity, and independent `auto_close`, `closable`, `pausable`, `renewable`, `active` flags. `valid_from`/`valid_to` are inclusive availability dates for new sales, not termination dates; subscription expiry is separate. Staff can select active available plans; admin configures them. Product lines are additional recurring charges and their summed quantity must meet the minimum at Draft creation, quotation, and confirmation. No automatic closure job exists yet.
- Quotation templates contain a plan, positive validity days, active state, and positive-quantity product/variant lines. Admin manages them; staff reads/uses them. Creating a quotation copies lines and sets quotation expiry to explicit `as_of + validity_days`. Editing templates never changes earlier copied quotation/subscription lines.

## Quotations and subscription lifecycle

The lifecycle is **Draft → Quotation → Confirmed → Active → Closed**, represented as lowercase constrained enum values. Only admin/staff can invoke transitions; customers read their own subscriptions. Illegal transitions return 409. Subscription mutation and audit commit together or roll back together. Subscription numbers derive from database primary keys (`SUB-000001`), never row counts. Start must not exceed expiry; payment terms are nonnegative. Every date-dependent request supplies `as_of`; domain logic does not call `date.today()`.

Confirmation requires a valid, non-expired quotation (expiry date inclusive), revalidates the current active/available plan and line selections/minimum, and snapshots prices, tax rates, names/variant labels, billing period, plan flags, and commercial terms. Unit price is product sales price plus variant extra price; amount is quantity × unit price, excluding tax; the plan base price is separate. Accepted terms and lines are frozen, including against direct SQL edits. Activation requires `start_date <= as_of <= expiry_date`, initializes next_invoice_date to the original start, and never generates invoices. Delayed activation preserves missed periods for future billing. Plan catalog expiry after confirmation does not terminate an existing subscription.

Normal closure requires Active and accepted `closable=true`, clears pause/next invoice date, and cannot be reversed. Pause requires Active, not already paused, and accepted `pausable=true`; resume requires Active and paused. Neither advances billing dates. Renewal requires Active and accepted `renewable=true`, with a new expiry later than both old expiry and `as_of`; it preserves prices/start/billing anchor. A paused Active subscription may renew; an expired-but-still-Active subscription may extend to a future expiry. Stage 4 implements deferred paused billing, original-anchor short-month/leap-year arithmetic, full final periods and automatic closure during explicit billing runs as specified below. No proration or background job is introduced.

## Billing and discounts

Stage 4 implements explicit-date preview/execution with daily/weekly/monthly/yearly anchor-preserving full periods; invoice date=period start, due date adds accepted terms. Starts are eligible through inclusive expiry; no proration. Paused contracts defer all charges and retain the schedule, then catch up on resume. Accepted auto_close acts only after expiry and billing completion, independently of manual closable, and never discards paused periods. Exact policy and algorithms are in DECISIONS.md.

Invoices permanently reserve unique/overlap-free subscription periods, even after cancellation. Per-subscription BEGIN IMMEDIATE transactions atomically persist invoice snapshots, discount redemptions/counters, schedules and audits. Pure preview writes nothing and simulates usage across the batch. One best discount is selected by actual grand-total saving; ties choose lowest ID. Integer largest-remainder allocation precedes per-line exclusive half-up tax. Global usage limits are implemented; per-customer limits are deferred. See Stage 4 API_CONTRACT.md for exact schemas and filters.

The following original planning requirements are historical context; Stage 4's explicit decisions above control implemented billing:

- Billing accepts a caller-provided `as_of` date and generates every due period, including missed periods, in order. Periods are half-open `[start, end)`; exact invoice issue/due-date policy is to be specified.
- Billing is idempotent. Enforce `UNIQUE(subscription_id, period_start, period_end)` on the future invoice schema, alongside appropriate overlap checks.
- Process each subscription in its own transaction. Invoice creation, discount redemption, and schedule advancement commit together or roll back together. One subscription failure must not roll back successfully processed subscriptions. Concurrent writers use SQLite write locking, including `BEGIN IMMEDIATE` where required.
- Dry-run billing makes **no persistent changes**, including audit records, redemption counters, and next-billing dates. Its proposed outputs should explain generated periods and failures.
- Discount rules are created and managed by admins, automatically evaluated for eligibility, and constrained by validity windows and global/per-customer redemption limits. Define percentage/fixed types, scope, stacking precedence, allocation, and redemption behavior before implementation. Redemptions must be atomic with the relevant invoice and must never exceed limits under retries.

## Invoices, payments, and overdue balances

Money is always integer paise in INR; never use binary floating-point values. Historical invoices retain original descriptions, prices, discounts, tax rates, and tax calculations. Amounts must follow the documented half-up calculation rules. Invoice numbers must be stable and unique under a later numbering policy.

Recorded payment amounts are strictly positive. Partial payments are allowed and a customer invoice's balance equals its total minus posted payments (and any future explicitly supported adjustments). Payment allocation, overpayments, reversals, and duplicate-entry handling need detailed rules; no payment gateway integration is planned. Invoice paid/partial/unpaid state follows the recorded balance. An invoice is overdue when it has a positive balance and its due date is earlier than the caller's `as_of` date. Days overdue equals the positive date difference, with zero on the due date. Reporting and list views must use the same rules.

## Reporting, audit, and customer access

Reports will cover recurring charges, invoiced revenue, collections, outstanding balances, overdue aging, and subscription lifecycle counts, with date filters. Define accounting meaning, recurring-revenue normalization, and report visibility in their implementation stage; invoiced revenue and cash collected must remain distinct. Reports must reconcile with invoice/payment source records. Customer reports, if offered, are restricted to that customer's data.

Audit important state transitions, invoice generation, discount redemption, payments, and administrative actions. Audit entries include actor (nullable for system actions), action, entity, entity ID, UTC time, and structured JSON details. Do not record credentials, reset tokens, or authentication secrets. Actor deletion retains audit entries and clears the actor reference. A complete audit service is deferred.

## Seed data and demonstration

Future business seed data is synthetic. A future command will demonstrate variants, taxes, billing frequencies, quotations, subscriptions, discounts, overdue invoices, and partial payments. Stage 2 provides only `python -m scripts.seed_admin`: validate ADMIN_EMAIL/ADMIN_PASSWORD, hash with Argon2id, and create an admin explicitly. Repeated runs never change an existing admin's credentials and never promote an existing staff/customer account. No automatic startup seeding or embedded demo credentials.

## Runtime and performance

Use Python 3.11+, FastAPI, typed SQLAlchemy 2.x, SQLite in WAL mode, Alembic, Pydantic v2/pydantic-settings, pytest/httpx, argon2-cffi, PyJWT, and email-validator (syntax-only, no DNS lookup). Run on Windows 11, Linux, and macOS without an external database, Docker, paid APIs, payment gateways, AI features, or internet access at application runtime. Package installation can require internet. The eventual frontend is Next.js/TypeScript/Tailwind with exported Google Stitch designs; no frontend is implemented in Stages 1–2.

The system target is approximately **5,000 subscriptions and 20,000+ invoices**, with paginated list response times **under 2 seconds** on a documented local machine. This full-scale target has not yet been benchmarked; Stage 4 prioritizes billing correctness and the demonstrable workflow. Smaller development checks must never be presented as meeting that target. Lists use bounded pagination and indexes for ownership, due dates and billing periods. SQLite has a 5-second busy timeout and only one writer at a time. A dedicated performance benchmark remains deferred.
