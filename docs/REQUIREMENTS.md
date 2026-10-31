# SubCadence requirements

SubCadence is a subscription management and recurring billing system for the Odoo × Make-A-Ton hackathon. This contract describes the planned system. Only the backend foundation, User/AuditLog models, migrations, and database-aware health endpoint are implemented in Stage 1. No official problem statement PDF was present; the supplied Stage 1 brief is the source of requirements.

## Access and identity

| Role | Planned authority |
| --- | --- |
| Admin | Manage configuration, products, taxes, plans, quotation templates, users, discounts, and operational records; access reports and billing operations. Only admins create staff accounts and discount rules. |
| Staff | Manage customer quotations, authorized subscription transitions, invoices, and recorded payments; access operational reports. Cannot create staff accounts or discount rules. |
| Customer | View only their own profile, subscriptions, quotations, invoices, and payments. Self-service actions require an explicit later contract. |

Authorization must run on the server for every action. Ownership filters apply to lists, detail lookups, exports, and nested resources. Never accept a caller-supplied customer ID as proof of ownership. Inactive users cannot authenticate. Unauthenticated signup must never grant staff or admin roles. A customer-account-to-business-customer association will be specified in Stage 2.

Stage 2 implements signup/login, credential validation, session/token handling, and authorization. Use argon2-cffi for salted Argon2id password hashes; never persist or log plaintext passwords. Proposed password baseline: 12–128 characters, allow passphrases, do not silently truncate. Final policy and session expiry require Stage 2 review. Password reset must give generic account-existence responses, use expiring single-use cryptographically random tokens stored as hashes, and invalidate them after use. Final token expiry and session revocation rules remain unresolved. SMTP configuration is optional and must not create an internet requirement for the local demonstration. Demo reset delivery must be explicitly documented and contain no real user data.

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

Future seed data is synthetic. A future idempotent seed command will demonstrate role separation, variants, taxes, all billing frequencies, quotations, active/closed subscriptions, discounts, overdue invoices, and partial payments. Initial admin credentials must come from local environment variables; no fixed password or real personal data is committed. No seed command or account creation is implemented in Stage 1.

## Runtime and performance

Use Python 3.11+, FastAPI, typed SQLAlchemy 2.x, SQLite in WAL mode, Alembic, Pydantic v2/pydantic-settings, pytest/httpx, and later argon2-cffi. Run on Windows 11, Linux, and macOS without an external database, Docker, paid APIs, payment gateways, AI features, or internet access at application runtime. Package installation can require internet. The eventual frontend is Next.js/TypeScript/Tailwind with exported Google Stitch designs; Stage 1 creates no frontend.

Provisional hackathon performance targets (not yet benchmarked): on a documented local machine and synthetic dataset of 1,000 subscriptions and 10,000 invoices, common paginated lists should return within 500 ms and a 1,000-subscription billing run within 60 seconds without skipping periods. Establish benchmarks during the relevant stages and adjust explicitly if required. Use bounded pagination and indexes for ownership, due dates, billing periods, and common report filters. Stage 1 sets a 5-second SQLite busy timeout; SQLite still permits only one writer at a time.
