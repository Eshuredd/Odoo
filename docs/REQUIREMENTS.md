# SubCadence requirements

SubCadence is a subscription management and recurring billing system for the Odoo × Make-A-Ton hackathon. This contract describes the planned system. Stages 1–2 implement the backend foundation, migrations, health, authentication/RBAC, password reset, mail delivery/outbox, and explicit admin seeding. Business workflows and the frontend remain planned. No official problem statement PDF was present; the supplied briefs are the source of requirements, including Stage 2's corrections to password and performance rules.

## Access and identity

| Role | Planned authority |
| --- | --- |
| Admin | Manage configuration, products, taxes, plans, quotation templates, users, discounts, and operational records; access reports and billing operations. Only admins create staff accounts and discount rules. |
| Staff | Manage customer quotations, authorized subscription transitions, invoices, and recorded payments; access operational reports. Cannot create staff accounts or discount rules. |
| Customer | View only their own profile, subscriptions, quotations, invoices, and payments. Self-service actions require an explicit later contract. |

Authorization runs on the server for every protected action. Ownership filters must apply to future lists, detail lookups, exports, and nested resources at the query level using the authenticated principal's user ID, before counting and pagination. Never accept a caller-supplied customer ID as proof of ownership. Inactive users cannot authenticate. Signup only creates customers and rejects extra fields, including role. Business-customer linkage and subscription/invoice ownership models remain deferred.

Passwords must contain **9–128 characters, at least one uppercase letter, one lowercase letter, and one special character**. A digit is not required; compliant passwords of 9–11 characters are valid. Whitespace alone is not a special character. Passwords are never trimmed or silently truncated. The same validator applies to signup, admin-created staff, reset, and admin seeding. Persist salted Argon2id hashes using argon2-cffi, never plaintext passwords. Validation responses identify the field and omit submitted values.

Authentication uses HS256 JWT Bearer access tokens valid for 2 hours. Required claims include subject, issued-at, expiry, authentication version, issuer, and audience. Signatures, algorithm, claims, and expiry are verified. Require a locally generated signing secret of at least 32 UTF-8 bytes (and 8 distinct characters), without a default. Auth endpoints fail closed with 503 when missing/insecure; health remains available. Every protected request loads the current active state, role, and authentication version from the database. Explicit logout increments the version and revokes **all** existing access tokens for that user. Password reset also revokes all sessions. There are no refresh tokens in Stage 2.

Authentication returns an immutable principal from a short-lived separate read session. The business request session is not queried, committed, or rolled back by authentication; services can independently use `with session.begin():`. Administrative writes recheck authority inside the write transaction.

Accepted email addresses must be syntactically valid ASCII, trimmed and lowercased consistently for signup, login, reset, and seeding. Reject unsupported internationalized addresses clearly. Keep the SQLite NOCASE UNIQUE constraint as the final duplicate arbiter; signup/staff duplicates return 409.

Password-reset requests return the same generic response for eligible, unknown, inactive, or undeliverable accounts. Generate 256-bit random tokens, store only SHA-256 digests in `password_reset_tokens`, expire them in 30 minutes, and consume them once. Replacement invalidates older unused tokens. Issuance and redemption use `BEGIN IMMEDIATE`; password replacement, consumption, version increment, and audit insertion commit atomically. A shared injectable UTC clock controls token lifecycle tests.

Configured SMTP uses the standard library with STARTTLS by default; credentials are refused without STARTTLS. Without SMTP configuration, the database outbox stores full email bodies for offline demonstrations and future invoice mail. **Outbox data is sensitive local demonstration data because it contains usable reset URLs.** Only active admins in development mode can use the paginated `/api/v1/dev/email-outbox`; the route is absent outside development. Never log credentials/tokens or expose raw reset tokens in other API responses. Demo data must be synthetic. SMTP errors do not expose account existence or provider details; failed delivery rolls back reset issuance. No automatic SMTP retry is implemented.

## Catalog and commercial configuration

- Products have names, identifiers, active state, and integer-paise prices. Variants represent sellable combinations of product attributes; quotations and subscriptions identify the selected variant. Deactivated catalog records remain available to historical documents.
- Taxes are exclusive: compute them in addition to taxable charges. Store percentage rates as integer basis points. Exact handling of multiple taxes, discount allocation, and rounding order needs a later detailed rule.
- Plans support daily, weekly, monthly, and yearly billing with a positive interval, an INR recurring base price, and active state. Product lines are additional charges. Planned flags control renewal, permitted customer actions, and expiration/closure behavior; exact flag names, defaults, and effects must be agreed before implementation. Pause behavior is unresolved.
- Quotation templates prefill the plan, product/variant lines, terms, and applicable configuration. Editing a template must not retroactively change issued quotations or confirmed subscriptions.

## Quotations and subscription lifecycle

The lifecycle is **Draft → Quotation → Confirmed → Active → Closed**. Transitions must be explicit, validated against the current state, authorized by role, and audited. Invalid transitions fail without partial writes. Detailed actor permissions, correction/cancellation paths, and activation dates will be defined with lifecycle services. Customers do not gain transition permissions merely by owning a record.

Confirmation snapshots relevant pricing, tax, plan, variant, quantity, discount, and terms information. Catalog edits cannot rewrite these snapshots. Monthly schedules retain the original billing-day anchor; short months clamp to the last valid day without drifting the anchor. Yearly leap-day behavior requires a detailed later rule. There is no proration in the MVP. Mid-period expiration and pause/resume behavior remain unresolved and must not be silently inferred.

## Billing and discounts

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

The system target is approximately **5,000 subscriptions and 20,000+ invoices**, with paginated list response times **under 2 seconds** on a documented local machine. This has not yet been benchmarked; business tables are not implemented. Smaller development benchmarks (for example, 1,000 subscriptions / 10,000 invoices) may supplement but must never replace this target. Establish billing benchmarks during its implementation without skipping periods. Use bounded pagination and indexes for ownership, due dates, billing periods, and common report filters. SQLite has a 5-second busy timeout and only one writer at a time.
