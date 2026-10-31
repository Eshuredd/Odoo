# SubCadence frontend

A local Next.js App Router, TypeScript, and Tailwind frontend for the existing FastAPI backend. The five exports under `../docs/stitch/` are the visual references; their static pages are not embedded or executed.

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
| `/dashboard` | Real accessible subscription counts and lifecycle distribution; financial widgets unavailable |
| `/subscriptions` | Server pagination, number search, lifecycle status and plan filters |
| `/subscriptions/{id}` | Owned/authorized detail, accepted snapshots, explicit-date lifecycle actions |
| `/subscriptions/new` | Admin/staff draft creation using paginated customer/plan/product/variant selectors |
| `/billing` | Admin/staff billing layout, disabled preview/execution, no fictional run data |
| `/invoices` | Unavailable invoice register and navigation to the detail workspace |
| `/invoices/{id}` | Unavailable invoice/payment layout; does not claim a supplied ID is a real invoice |

Normal use needs customers, taxes, products, variants, and plans configured through the existing backend API/docs. This frontend stage does not add configuration CRUD screens. Customer navigation omits billing and creation controls; direct protected page access is also guarded. Backend authorization remains authoritative.

## Connected API contract

All paths below are relative to `NEXT_PUBLIC_API_BASE_URL`:

- POST `/auth/login`, GET `/auth/me`, POST `/auth/logout`.
- GET `/subscriptions` with actual `limit`, `offset`, `search`, `status`, and `plan_id` query fields; GET `/subscriptions/{id}`; POST `/subscriptions`.
- POST `/subscriptions/{id}/quotation`, `/confirm`, `/activate`, `/pause`, `/resume`, `/renew`, `/close` with explicit `as_of`; quotation includes validity_days, renewal includes new_expiry_date.
- GET `/customers`, `/customers/{id}`, `/plans`, `/plans/{id}`, `/products`, `/products/{product_id}/variants` for selections and labels. Administrative plan/catalog calls are skipped for customer-role readers.

No billing, invoice, payment, reporting, or audit-history endpoints are invented. Lifecycle progress displays current state, not a fabricated event timeline. Frozen product/plan labels come from accepted snapshots. When an unconfirmed customer's role cannot access catalog configuration, IDs identify unsnapshotted products/plans rather than fabricating names.

JWTs live only in the in-memory API client; user state lives in React context. Client-side Next.js navigation preserves the session. Refreshing, opening a new tab, expiry, or a protected 401 requires sign-in again. No tokens go into localStorage, sessionStorage, cookies, URLs, or logs. Logout claims revocation only after the backend succeeds and invalidates all account sessions. Network failure keeps the session visible so logout can be retried.

Lifecycle controls use backend state, role, and accepted plan flags. Paused is a boolean on Active, not an extra lifecycle state. The confirmation dialog uses a required business date; API validation/state conflicts remain visible and are not treated as success. Product-line amendments, quarterly billing, proration, automatic renewals, and automatic invoice/payment execution are not introduced.

## Exact amounts

`lossless-json` preserves the original integer tokens while decoding responses. Monetary fields become BigInt paise before rendering or arithmetic. Formatting divides/modulos with integers, adds Indian grouping, and retains two paise digits. The full SQLite signed 64-bit monetary range is supported without floating-point rounding.

The UI may sum the backend's base price and line amounts, explicitly labeled **before exclusive tax**. It never invents a tax total, invoice balance, MRR, ARR, collection amount, or historical trend. Non-money IDs/counts must fit JavaScript's safe-integer range; oversized values produce an explicit response error rather than being silently rounded.

## Design and accessibility

The app preserves the exported slate/cobalt palette, Plus Jakarta Sans/Inter hierarchy, 256px desktop sidebar, header, cards, tables, lifecycle steps, billing console, and invoice/payment sections. The theme is centralized in `src/app/globals.css` using Tailwind `@theme` tokens. Shared components cover the shell, branding, panels, KPIs, badges, tables, pagination, remote search/select controls, notices, loading/empty/unavailable states, and native confirmation dialogs.

Changes from the prototype are deliberate: an inline local SVG fixes the broken brand; bundled font files and Lucide icons replace hosted fonts/images; user initials replace a fictional avatar; navigation includes implemented screens only; unsupported Odoo/gateway/cloud/scheduler claims and invented financial values are removed. Login and create-draft pages extend the same design system. Mobile uses an off-canvas navigation, wrapping forms/actions, and horizontally contained tables. Native dialogs trap focus, support Escape, and restore the invoking button's focus. Motion respects reduced-motion settings.

## Verification

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

Unit tests cover exact integer formatting/parsing, request contracts, failures, and lifecycle permissions. Browser tests exercise real login, role-based UI and backend denials, search/pagination, create subscription and all lifecycle actions, snapshot amounts, customer ownership, revoked JWTs, loading/error/empty states, unavailable finance actions, mobile containment, and keyboard dialogs. Screenshots of synthetic test data are written under ignored `test-results/screenshots/` for comparison with Stitch, on desktop and mobile. The suite stops its temporary servers; screenshots do not imply the normal application has those records.

The production dependency audit is clean. The full development-tool audit currently reports moderate advisories in transitive lint/glob dependencies; no critical/high advisory remains. These tooling alerts are not suppressed or addressed with forced dependency downgrades. Review them as upstream tooling updates become compatible.

## Remaining scope

Billing previews/execution, invoice retrieval and PDFs/email, payment recording, reporting, configuration screens, signup/reset UI, and persistent/refresh-token sessions are future work. Billing/invoice layouts contain clear unavailable states and disabled controls, not simulated business behavior.
