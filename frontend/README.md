# SubCadence frontend

A local Next.js App Router, TypeScript, and Tailwind frontend for the existing FastAPI backend. The five exports under `../docs/stitch/` are the visual references; their static pages are not embedded or executed.

The final sprint connects manual partial/final payments, persisted payment history, exact remaining balances, Paid status, overdue filters and SQL financial summaries. Configuration pages cover customers, products/variants, taxes, plans, quotation templates and discounts. Staff can create template quotations; customers can review their own subscriptions/invoices/payments/profile. Signup, forgot/reset password, invoice Send and browser Print are connected. See `../docs/DEMO_SCRIPT.md` for exact demo credentials/setup and screen navigation.

Additional routes: `/configuration/{customers,products,taxes,plans,quotation-templates,discounts}`, `/configuration/products/{id}/variants`, `/subscriptions/from-template`, `/payments`, `/profile`, `/signup`, `/forgot-password`, `/reset-password`. Configuration is operator-only; admin controls catalog writes, while staff manages supported customer/subscription/invoice operations. Account creation is public customer-only. All financial forms serialize BigInt paise losslessly; INR entry permits at most two decimal places and never converts money through JavaScript Number.

Dashboard dates explicitly select collection payment dates and overdue as_of. Balances use all currently persisted payments; these reports do not reconstruct historical invoice statuses. Customer dashboards omit business-wide summaries. In-memory JWTs still require sign-in after refresh. Next dev request URL logging is disabled so reset query tokens are not written to incoming-request logs; the reset form removes the token query from the address bar after reading it.

## Run locally

Use Node.js 22.13+ on the 22.x line (or supported 24/26 LTS), npm, and the existing Python backend environment. Dependency installation needs internet or cached packages. Application runtime, icons, documentation, and fonts do not depend on third-party hosted assets.

Terminal 1, from `backend/`, with the Python environment activated and the root `.env` configured:

```powershell
python -m alembic upgrade head
python -m scripts.seed_admin
subcadence-api
```

Use the root README's secure admin setup instructions. Seeding is explicit and does not reset an existing account. The frontend never creates hardcoded demo accounts in the normal database.

Terminal 2, from `frontend/` (same npm commands on Windows, Linux, and macOS):

```powershell
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), then sign in using an existing account. Use `localhost` for the frontend: it matches the backend's default CORS origin. The default API URL is `http://127.0.0.1:8000/api/v1`.

For a different API address, copy `.env.example` to `.env.local` and set `NEXT_PUBLIC_API_BASE_URL` before starting/building. Never put passwords, JWTs, or signing keys in public frontend environment variables. For a different frontend origin, explicitly add it to backend `CORS_ORIGINS`.

PowerShell environment-only configuration:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
npm run dev
```

Bash equivalent:

```bash
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
npm run dev
```

Production-style local build:

```powershell
npm run build
npm start
```

The public API URL is embedded at build time. This implementation targets local use; no hosting, payment integration, or cloud deployment is configured.

## Screens and routes

| Route | Behavior |
| --- | --- |
| `/login` | JSON login, error feedback, account/role verification through `/auth/me` |
| `/dashboard` | Subscription lifecycle, actual collections, collectible balances, overdue aging and invoices |
| `/subscriptions` | Server pagination, number search, lifecycle status and plan filters |
| `/subscriptions/{id}` | Owned/authorized detail, accepted snapshots, explicit-date lifecycle actions |
| `/subscriptions/new` | Admin/staff draft creation using paginated customer/plan/product/variant selectors |
| `/billing` | Admin/staff explicit-date zero-write preview, confirmed execution, catch-up/totals/errors and generated invoice links |
| `/invoices` | Real persisted register with number/status/customer/subscription/due-date filters and server pagination |
| `/invoices/{id}` | Immutable line calculations and discount/tax totals; operator confirm/cancel; payment/PDF/email disabled |

Customers, taxes, products/variants, plans, templates and discounts can be configured through the frontend or API/docs. Customer navigation omits administrative configuration and billing controls; direct protected page access is also guarded. Backend authorization remains authoritative.

## Connected API contract

All paths below are relative to `NEXT_PUBLIC_API_BASE_URL`:

- POST `/auth/login`, GET `/auth/me`, POST `/auth/logout`.
- GET `/subscriptions` with actual `limit`, `offset`, `search`, `status`, and `plan_id` query fields; GET `/subscriptions/{id}`; POST `/subscriptions`.
- POST `/subscriptions/{id}/quotation`, `/confirm`, `/activate`, `/pause`, `/resume`, `/renew`, `/close` with explicit `as_of`; quotation includes validity_days, renewal includes new_expiry_date.
- GET `/customers`, `/customers/{id}`, `/plans`, `/plans/{id}`, `/products`, `/products/{product_id}/variants` for selections and labels. Administrative plan/catalog calls are skipped for customer-role readers.
- POST `/billing/preview` and `/billing/run` with required `{as_of}`; execution follows a confirmation dialog. All cadence/customer scope labels accurately describe all eligible accounts, rather than silently ignoring filters.
- GET `/invoices` and `/invoices/{id}`, POST `/invoices/{id}/confirm` and `/cancel` (no body). Execution reloads generated invoice details from the database before completing refresh. Financial totals come from persisted backend calculations.

Payment and reporting endpoints are implemented in the final sprint: POST/GET `/invoices/{id}/payments`, GET `/payments` and `/payments/{id}`, POST `/invoices/{id}/settle-zero`, GET `/reports/summary`, POST `/invoices/{id}/send`. Full audit-history endpoints are not invented. Lifecycle progress displays current state. Frozen commercial labels come from accepted snapshots. Discount configuration is available to admins in the UI and API/docs.

JWTs live only in the in-memory API client; user state lives in React context. Client-side Next.js navigation preserves the session. Refreshing, opening a new tab, expiry, or a protected 401 requires sign-in again. No tokens go into localStorage, sessionStorage, cookies, URLs, or logs. Logout claims revocation only after the backend succeeds and invalidates all account sessions. Network failure keeps the session visible so logout can be retried.

Lifecycle controls use backend state, role, and accepted plan flags. Paused is a boolean on Active, not an extra lifecycle state. Pausing defers billing; resume catches up outstanding periods without shifting the anchor. Confirmation dialogs use explicit business dates where required; API validation/state conflicts remain visible and are not treated as success. Product-line amendments, quarterly billing, proration, automatic renewals, background billing jobs, and payment execution are not introduced.

## Exact amounts

`lossless-json` preserves the original integer tokens while decoding responses. Monetary fields become BigInt paise before rendering or arithmetic. Formatting divides/modulos with integers, adds Indian grouping, and retains two paise digits. The full SQLite signed 64-bit monetary range is supported without floating-point rounding.

Subscription charges sum base and lines explicitly **before exclusive tax**. Billing and invoice pages display the backend's exact persisted/projected tax, discount and grand totals using the same BigInt formatting, including batch sums larger than SQLite's per-invoice limit. No invoice balance, MRR, ARR, collection amount or historical trend is invented. Non-money IDs/counts must fit JavaScript's safe-integer range; oversized values produce an explicit response error rather than being silently rounded.

## Design and accessibility

The app preserves the exported slate/cobalt palette, Plus Jakarta Sans/Inter hierarchy, 256px desktop sidebar, header, cards, tables, lifecycle steps, billing console, and invoice/payment sections. The theme is centralized in `src/app/globals.css` using Tailwind `@theme` tokens. Shared components cover the shell, branding, panels, KPIs, badges, tables, pagination, remote search/select controls, notices, loading/empty/unavailable states, and native confirmation dialogs.

Changes from the prototype are deliberate: an inline local SVG fixes the broken brand; bundled font files and Lucide icons replace hosted fonts/images; user initials replace a fictional avatar; navigation includes implemented screens only; unsupported Odoo/gateway/cloud/scheduler claims and invented financial values are removed. Login and create-draft pages extend the same design system. Mobile uses an off-canvas navigation, wrapping forms/actions, and horizontally contained tables. Native dialogs trap focus, support Escape, and restore the invoking button's focus. Motion respects reduced-motion settings.

## Verification

Final sprint results (2026-10-31): TypeScript, lint and production build passed; 20 unit tests and all 11 real-backend browser tests passed. The backend regression suite passed all 312 tests. Browser scenarios include the full payment-to-Paid workflow, overdue refresh after partial payment, idempotent retry, configuration/variants/templates, account recovery/profile editing, offline invoice notice and print styling. No normal developer database was modified by automated checks.

From `frontend/`:

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npx playwright install chromium
npm run test:e2e
npm audit --omit=dev
```

Browser tests start a real FastAPI app and Next.js server on ports 8766 and 3000, which must be free. They use a fresh temporary SQLite file, migrations, random environment-only secrets, and explicitly synthetic accounts/catalog data; they never test against `backend/data/subcadence.db`. The existing root `.venv` must have the backend test dependencies installed (`python -m pip install -e ".[test]"` from backend). `scripts/test-backend.mjs` chooses the appropriate Windows/POSIX Python path.

Unit tests cover exact integer formatting/parsing, billing/invoice request contracts, failures, and lifecycle permissions. Browser tests exercise real login, role-based UI and backend denials, search/pagination, subscription creation/lifecycle, billing preview/execution, persisted invoice navigation/confirmation/cancellation, repeat billing, customer ownership, revoked JWTs, server failures without false success, disabled payments, mobile containment, and keyboard dialogs. Screenshots of synthetic test data are written under ignored `test-results/screenshots/` for comparison with Stitch, on desktop and mobile. The suite stops its temporary servers; screenshots do not imply the normal application has those records.

The production dependency audit is clean. The full development-tool audit currently reports moderate advisories in transitive lint/glob dependencies; no critical/high advisory remains. These tooling alerts are not suppressed or addressed with forced dependency downgrades. Review them as upstream tooling updates become compatible.

## Remaining scope

Dedicated PDF export, persisted billing-run history, reversals/refunds, payment gateways, historical-balance reconstruction and persistent/refresh-token sessions remain future work. Browser Print supports Save as PDF where available. Invoice notices use configured SMTP or the offline outbox; real provider delivery is unverified. The full-scale performance target remains unbenchmarked. Billing is an explicit operator request, not a background scheduler. The Stitch theme/layout is preserved.
