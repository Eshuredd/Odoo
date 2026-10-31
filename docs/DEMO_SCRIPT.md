# SubCadence: 2–3 minute hackathon demonstration

## Prepare once

Use synthetic credentials only. From the repository root, install the backend test extras (the demo seeder uses TestClient to exercise real API services):

```powershell
rtk proxy .\.venv\Scripts\python.exe -m pip install -e ".\backend[test]"
```

If the virtual environment does not exist yet, create it with `rtk proxy py -3.12 -m venv .venv`. Use Node.js 22.13+ (22.x), or supported 24/26 LTS, and npm for the frontend.

Set explicit synthetic account credentials in the backend terminal. PowerShell prompts keep passwords out of command history:

```powershell
$demoAdmin = Get-Credential -Message "Synthetic demo admin"
$demoStaff = Get-Credential -Message "Synthetic demo staff (different email)"
$demoCustomer = Get-Credential -Message "Synthetic demo customer (different email)"
$env:ADMIN_EMAIL = $demoAdmin.UserName
$env:ADMIN_PASSWORD = $demoAdmin.GetNetworkCredential().Password
$env:DEMO_STAFF_EMAIL = $demoStaff.UserName
$env:DEMO_STAFF_PASSWORD = $demoStaff.GetNetworkCredential().Password
$env:DEMO_CUSTOMER_EMAIL = $demoCustomer.UserName
$env:DEMO_CUSTOMER_PASSWORD = $demoCustomer.GetNetworkCredential().Password
$env:AUTH_SECRET_KEY = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
$env:DEMO_DATABASE_URL = "sqlite:///data/synthetic_demo.db"
$env:DATABASE_URL = $env:DEMO_DATABASE_URL
$env:APP_ENV = "development"
```

Use syntactically valid, distinct emails such as addresses under `demo.example.com`. Passwords require 9–128 characters, uppercase, lowercase, and a special character. Do not print or commit these environment values. Keep the signing key stable while demonstrating; changing it revokes existing sessions.

The seeder deliberately ignores the ordinary `DATABASE_URL`. Its default is the separate `backend/data/synthetic_demo.db`, optionally overridden only by `DEMO_DATABASE_URL`. It refuses any nonempty database lacking its demo marker. Re-running a completed seed does not reset accounts or append invoices/payments. Failed/incomplete seeds should be investigated and retried using a fresh, explicitly named demo database; the script never deletes data automatically.

From `backend/`, in that terminal:

```powershell
rtk proxy ..\.venv\Scripts\python.exe -m scripts.seed_demo
rtk proxy ..\.venv\Scripts\python.exe -m alembic check
rtk proxy ..\.venv\Scripts\subcadence-api.exe
```

In another terminal, from `frontend/`:

```powershell
rtk proxy npm ci
rtk proxy npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The API defaults to `http://127.0.0.1:8000/api/v1`; backend CORS permits `http://localhost:3000`. A private frontend `.env.local` may override `NEXT_PUBLIC_API_BASE_URL`; never place secrets in a public variable. The seeder makes no external email requests; normal invoice Send uses configured SMTP or the development database outbox.

## Show the product

**0:00–0:20 — Problem and architecture.** “Recurring billing needs accurate schedules, historical prices, partial payments and clear balances. SubCadence uses a local Next.js interface, a FastAPI service, and SQLite WAL. All amounts are integer paise, with database-backed ownership and roles.” Log in as the synthetic admin and show actual dashboard collections, unpaid balances and overdue aging.

**0:20–0:45 — Configuration and quotation.** Open **Configuration → Products**, show the synthetic product and its variant; show tax and monthly plan. Log out and log in as staff. Open **New Subscription → Use quotation template**, choose a synthetic customer and template, set expiry after today, and create the quotation. Its validity appears in Subscription Detail. Select **Confirm subscription**, then **Activate subscription**, using today's business date.

**0:45–1:20 — Billing.** Open **Billing Center**, set today's explicit date and **Preview dry run**. Show each half-open period, discount, exclusive tax and total; the preview writes nothing. Select **Execute billing → Confirm execution**, then open the generated invoice. If there is no newly activated agreement, choose tomorrow to show the synthetic daily plan's next period. Explain that monthly/yearly boundaries recover their original anchors and paused billing is deferred.

**1:20–1:55 — Partial and final payments.** Confirm the draft invoice, select **Record Payment**, enter a positive amount less than its displayed balance, choose method/date, and save. Show the real payment row, partial progress and reduced balance. Record exactly the remaining amount; status becomes **Paid** and balance becomes zero. No gateway transfer is claimed.

**1:55–2:20 — Financial visibility.** Return to **Dashboard**; set the collections date range to include today. Show actual payment collections, collectible Confirmed balances, and overdue amounts grouped into 1–30/31–60/61+ days. Draft, Paid and Cancelled are not overdue. Open a confirmed/paid invoice and select **Send Invoice**: without SMTP the notice explicitly says it was saved to the offline outbox. **Print Invoice** opens the browser print dialog, where Save as PDF is available when supported.

**2:20–2:45 — Reliability and portal.** Repeat billing with the same date: no new duplicate invoices or discount redemptions. Show customer login and **Subscriptions**, **Invoices**, **Payments**, **My Profile**. There are no business-wide customer reports or enabled operator actions. A refresh intentionally signs the user out because JWTs live only in memory.

## Automated evidence

Verified 2026-10-31: **312 backend tests, 20 frontend unit tests and 11 Playwright tests passed**. TypeScript, ESLint, production build, compileall and migration upgrade/check passed. The actual demo CLI succeeded on a temporary database and a second invocation left its accounts and records unchanged. Dedicated PDF export, live provider delivery and the full-scale performance target remain unverified/unimplemented as noted below.

All automated checks use temporary file-backed databases, not the ordinary database or the persistent demo file. With ports 3000 and 8766 free:

```powershell
# backend/
rtk proxy ..\.venv\Scripts\python.exe -m pytest -q
rtk proxy ..\.venv\Scripts\python.exe -m compileall -q app alembic scripts tests
# frontend/
rtk proxy npm run typecheck
rtk proxy npm run lint
rtk proxy npm test
rtk proxy npm run build
rtk proxy npx playwright install chromium
rtk proxy npm run test:e2e
```

The full business test exercises actual APIs and the browser: billing, confirmation, partial/full payments, identical-key retry, Paid balance, dashboard reconciliation, ownership, repeated billing, and immutable invoice calculations. Additional browser checks cover configuration, templates, signup/reset, profile editing, errors, mobile layouts and keyboard dialogs. Screenshots are under ignored `frontend/test-results/screenshots/`.

## State the limits accurately

- Manual payment recording only; no gateway, reversal, refund, reconciliation, Odoo synchronization or cloud deployment.
- Browser printing is supported; there is no dedicated PDF generation endpoint.
- SMTP acceptance is not guaranteed mailbox delivery, and cannot be rolled back after acceptance if a later database commit fails. Offline outbox/audit writes are atomic. Live SMTP delivery requires configuration and has not been tested against a real provider in this sprint.
- Reports show current persisted balances/statuses; as_of controls aging, not historical reconstruction. The collection date range applies to payment dates.
- No background billing scheduler or persisted run-history UI. Operators explicitly preview and execute.
- The 5,000-subscription/20,000-invoice performance target remains unbenchmarked. Hackathon verification demonstrates correctness, not production readiness.
