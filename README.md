# SubCadence

A subscription management and recurring billing platform for the Odoo × Make-A-Ton hackathon. The planned workflow connects catalog configuration, quotations, subscription activation, recurring invoices, partial payments, reports, and customer self-service.

**Stages 1–4 and Stitch frontend integration are implemented:** backend foundation, authentication/RBAC/reset, SMTP/offline mail, customer/catalog/plans, quotations, subscription lifecycle, recurring billing, automatic discounts, persisted invoices, and the connected local Next.js frontend. Payment recording, PDFs/email, and financial reports remain deferred.

## Architecture and stack

FastAPI routes delegate persistence to SQLAlchemy 2.x services. Pydantic v2/pydantic-settings validate configuration and requests. Argon2id hashes passwords; PyJWT signs HS256 Bearer tokens; email-validator validates syntax without DNS. SQLite uses WAL, foreign keys, a 5-second busy timeout, and explicit transactions. Alembic owns schema changes. pytest/httpx tests use temporary databases. Python 3.11+ is required; Python 3.12 is used for local verification. No Docker, database server, paid APIs, or application-runtime internet access is required for offline operation.

The repository root is the `subcadence/` project root from the brief, even if the local checkout directory has a different name.

```text
.
├── backend/
│   ├── app/
│   │   ├── api/v1/         # Auth, catalog, subscriptions, billing, discounts, invoices, health
│   │   ├── api/dependencies.py # Bearer auth and reusable role dependencies
│   │   ├── core/           # Settings, validation, principal, clock, JWT/password helpers
│   │   ├── db/             # Metadata, UTC type, engine and sessions
│   │   ├── models/         # Auth, commercial and immutable financial ORM models
│   │   ├── schemas/        # Auth, customer/catalog/lifecycle inputs, outputs and pagination
│   │   ├── services/       # Auth, catalog, customer, lifecycle, audit and mailer logic
│   │   ├── static/swagger-ui/ # Vendored offline API docs assets and licenses
│   │   └── main.py         # App factory, lifespan, server entry point
│   ├── alembic/versions/   # 0001 foundation through 0004 financial
│   ├── tests/             # Foundation, auth/RBAC, reset concurrency, SMTP/outbox, seed
│   ├── scripts/seed_admin.py # Explicit, idempotent admin bootstrap
│   ├── data/              # Ignored local database; tracked .gitkeep only
│   ├── alembic.ini
│   └── pyproject.toml
├── docs/
│   ├── REQUIREMENTS.md
│   ├── DECISIONS.md
│   └── API_CONTRACT.md
├── .env.example
└── .gitignore
```

## Local setup

Run these commands from `backend/`. Dependencies require internet or a local package cache during installation. The editable install is the supported development setup, because configuration/data/migrations live beside the source tree.

Windows PowerShell:

```powershell
cd backend
py -3.12 -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item ..\.env.example ..\.env
$env:AUTH_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))"
python -m alembic upgrade head
subcadence-api
```

If PowerShell policy prevents activation, invoke the virtual environment directly without changing policy: `..\.venv\Scripts\python.exe -m pip install -e ".[test]"`, `..\.venv\Scripts\python.exe -m alembic upgrade head`, and `..\.venv\Scripts\subcadence-api.exe`.

Linux/macOS:

```bash
cd backend
python3 -m venv ../.venv
source ../.venv/bin/activate
python -m pip install -e '.[test]'
cp ../.env.example ../.env
export AUTH_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python -m alembic upgrade head
subcadence-api
```

Use any available Python 3.11+ interpreter when `py -3.12` is unavailable. Do not overwrite an existing local `.env` when repeating setup. To upgrade an existing checkout, activate the existing environment, run `python -m pip install -e ".[test]"`, configure a secret, then run `python -m alembic upgrade head`. Existing users/audits survive the upgrade; auth version defaults to zero. Tests never use the developer database.

The generated key above is held in that terminal's environment. For persistence, privately put one generated value in the ignored root `.env`. Do not regenerate it on every startup: changing it invalidates all existing JWTs. Health/docs work with no signing key; auth endpoints fail closed with 503 until a strong key is supplied.

## Configuration

Settings load `.env` from the repository root regardless of working directory; environment variables take precedence. Never commit `.env`. [.env.example](.env.example) contains safe defaults and empty credential fields:

| Setting | Local default / meaning |
| --- | --- |
| `DATABASE_URL` | `sqlite:///data/subcadence.db`; relative paths resolve from `backend/` |
| `API_HOST`, `API_PORT` | `127.0.0.1`, `8000`; used by `subcadence-api` |
| `CORS_ORIGINS` | JSON array, default `["http://localhost:3000"]`; explicit HTTP(S) origins, no trailing slash or wildcards |
| `APP_ENV` | `development`; only this mode registers the admin-only development outbox API; `test`/`production` omit it |
| `PASSWORD_RESET_BASE_URL` | `http://localhost:3000/reset-password`; absolute HTTP(S) URL without query/fragment, used for the future frontend |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Empty; required only for explicit admin seeding; never automatically creates an account |
| `AUTH_SECRET_KEY` | Empty; require at least 32 UTF-8 bytes, 8 distinct characters, and no surrounding whitespace; generate with `secrets` as above |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` | Optional; default port 587; username/password must be supplied together |
| `SMTP_FROM_EMAIL` | Explicit sender; defaults to SMTP username when omitted |
| `SMTP_STARTTLS`, `SMTP_TIMEOUT` | `true`, `5` seconds; verified STARTTLS is mandatory when credentials are supplied |

Standard SQLite and `sqlite+pysqlite` URLs are supported; URI/query-string modes and external databases are deliberately excluded. Parent directories are created as needed. WAL/SHM companion files are expected and ignored by Git. WAL improves reader/writer coexistence; writes still serialize.

## Run, migrate, and test

With the environment activated, from `backend/`:

```bash
# Apply schema before using application tables.
python -m alembic upgrade head
python -m alembic current

# Start with API_HOST and API_PORT from settings.
subcadence-api

# Or run a development server with explicit host/port and reload.
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run isolated tests; never migrates the developer's application database.
python -m pytest
python -m compileall -q app alembic tests

# Check metadata matches the migrated database.
python -m alembic check

# After adding future models: import them in app/models/__init__.py,
# generate a revision, review it, then apply it.
python -m alembic revision --autogenerate -m "describe schema change"
python -m alembic upgrade head
```

`uvicorn` command-line flags control its binding; it does not consume our `API_HOST`/`API_PORT` settings automatically. The `subcadence-api` entry point does.

Health: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health). Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Documentation assets are bundled locally, so `/docs` also works offline. The health endpoint executes `SELECT 1`, returning `{"status":"ok","service":"subcadence-api"}` or a sanitized HTTP 503 for database access failure. It checks connectivity, not schema readiness. The app never calls `metadata.create_all()` or runs migrations at startup.

## Models and transaction behavior

Stage 3 adds CustomerProfile, Tax, Product, ProductVariant, Plan, QuotationTemplate, QuotationTemplateLine, Subscription, and SubscriptionLine. Migration `0003_commercial` creates their tables/indexes/constraints, backfills a profile for each existing customer, and preserves authentication tables, credentials, reset tokens, and audits. Migrations 0001 and 0002 are unchanged. Re-run `python -m alembic upgrade head` after pulling the update.

`User` stores an auto-incrementing ID, required case-insensitively unique email (`NOCASE`), Argon2id password hash, checked admin/staff/customer role, active flag defaulting to true, UTC created/updated timestamps, and nonnegative `auth_version` defaulting to zero. API emails are ASCII-only, syntax-validated, trimmed and lowercased. `updated_at` is maintained for ORM updates; future raw SQL writers must maintain it explicitly.

`AuditLog` stores an auto-incrementing ID, nullable actor reference, required action/entity/entity ID, UTC timestamp, and JSON detail. Actor deletion clears its reference while preserving the event. Signup, staff creation, successful reset, logout, and admin seed write credential-free audits in the same transaction. Replace JSON detail values when updating; nested in-place mutations are not tracked.

`PasswordResetToken` stores a user reference, unique SHA-256 digest, UTC created/expiry/consumption timestamps, and indexes for user/consumption and expiry. It never stores raw reset tokens. `EmailOutbox` stores recipient, subject, full body, and UTC creation time, indexed for pagination. Full email bodies intentionally contain sensitive usable reset links in offline mode.

Each business request receives a fresh session; authentication uses a separate short-lived read session and returns an immutable principal. Authentication never begins/commits/rolls back the business session. Services use `with session.begin():`; closing a session rolls back pending work. SQLAlchemy emits an explicit BEGIN so transactional DDL and rollback behavior are predictable. For an immediate write transaction before any query:

```python
with engine.connect().execution_options(sqlite_begin_mode="IMMEDIATE") as connection:
    with connection.begin():
        # Future transactional writes go here.
        ...
```

Session-based services select `sqlite_begin_mode="IMMEDIATE"` before sensitive writes. Billing processes each subscription in its own transaction, rechecks the principal and subscription after locking, and commits invoices, discount redemption, schedule changes and audits together. A failed subscription rolls back while the rest continue.

## Create the first admin

From `backend/`, with the virtual environment activated and migrations applied, PowerShell:

```powershell
$adminCredential = Get-Credential -Message "Enter the synthetic local admin email and password"
$env:ADMIN_EMAIL = $adminCredential.UserName
$env:ADMIN_PASSWORD = $adminCredential.GetNetworkCredential().Password
python -m scripts.seed_admin
Remove-Item Env:\ADMIN_PASSWORD
Remove-Variable adminCredential
```

Linux/macOS (Bash):

```bash
read -r -p 'Synthetic admin email: ' ADMIN_EMAIL
read -r -s -p 'Admin password: ' ADMIN_PASSWORD
printf '\n'
export ADMIN_EMAIL ADMIN_PASSWORD
python -m scripts.seed_admin
unset ADMIN_PASSWORD
```

Alternatively set the values privately in root `.env`. Password requirements are **9–128 characters, uppercase, lowercase, and a special character; no digit required**. Whitespace alone does not count as special. Passwords are never trimmed/truncated. The seed script validates both fields, is idempotent, never overwrites an existing admin's password/active state, and refuses to promote an existing customer/staff. Missing configuration returns a useful error without printing credentials. It never runs automatically on startup.

## Authentication and password-reset demo

Implemented endpoints:

| Method | Path | Access |
| --- | --- | --- |
| POST | `/api/v1/auth/signup` | Public; customer only |
| POST | `/api/v1/auth/login` | Public; JSON email/password |
| GET | `/api/v1/auth/me` | Active authenticated user |
| POST | `/api/v1/auth/logout` | Active authenticated user; revokes all sessions |
| POST | `/api/v1/auth/password-reset/request` | Public; generic response |
| POST | `/api/v1/auth/password-reset/confirm` | Public; token/new_password |
| POST | `/api/v1/users/staff` | Active admin only |
| GET | `/api/v1/dev/email-outbox` | Active admin, development only |

Signup/staff creation reject extra fields, including role. Login returns `access_token`, `token_type=bearer`, `expires_in=7200`, and a safe public user. Protected requests send `Authorization: Bearer <token>`. Current database role, active state, and auth version are checked on every request; missing/invalid auth is 401, insufficient role is 403. Logout/reset increment the auth version, revoking all existing access tokens. No refresh tokens are implemented. Validation errors omit submitted values; password hashes never appear in API responses.

Use offline Swagger at `/docs` to sign up and log in, then paste the returned access token into **Authorize**. To create staff, log in as the seeded admin and POST an email/password to `/users/staff`. Staff/customers receive 403, anonymous callers 401. Customer profiles, subscriptions, and invoices filter ownership in SQL using the authenticated User ID, before totals and pagination. Inaccessible record IDs return 404.

For local reset demonstration:

1. Leave SMTP fields empty and set `APP_ENV=development`.
2. POST `{"email":"<your synthetic account email>"}` to `/auth/password-reset/request`. Known/unknown/inactive accounts and SMTP failures get the same generic response.
3. Log in as the seeded admin and GET `/dev/email-outbox?limit=20&offset=0` with its Bearer token. Full email bodies contain the reset URL. The future frontend page does not exist yet; extract the `token` query value from the email.
4. POST `{"token":"<email token>","new_password":"<compliant new password>"}` to `/auth/password-reset/confirm`.
5. Log in using the new password. The old password and all old JWTs no longer work. Reused, replaced, or expired reset links fail.

Reset tokens contain 256 random bits, expire in 30 minutes, and are single use; issuing a replacement invalidates prior unused tokens. The reset table stores only SHA-256 digests. Password change, consumption, revocation, and audit commit atomically under `BEGIN IMMEDIATE`. Tests simulate expiry using an injectable UTC clock and exercise real concurrent SQLite consumers.

With SMTP configured, email uses standard-library SMTP and verified STARTTLS by default. Set SMTP_HOST, sender, and optional paired username/password. Credentials cannot be sent with STARTTLS disabled. Partial/invalid SMTP configuration fails delivery rather than falling back to the outbox. Public reset responses hide delivery errors; failed delivery rolls back token issuance/replacement. Tests mock SMTP and send no actual mail.

**The offline outbox is sensitive local demonstration data:** it stores usable reset links in full bodies and is designed for synthetic accounts. Only admins can retrieve it, and its route/OpenAPI entry are absent outside development. Authentication/outbox responses use `Cache-Control: no-store`. There is no retention/retry worker. SMTP acceptance cannot be atomically rolled back if a later DB commit fails; no production delivery guarantee is claimed.

The Next.js client keeps access tokens in memory, uses Bearer headers, requires sign-in after expiry/revocation, and invokes server-side logout before clearing local state. Refreshing the page also requires sign-in; there is no cookie authentication.

This hackathon auth implementation is not production-hardened: rate limiting, MFA, refresh rotation, uniform request timing, and operational security monitoring remain outside Stage 2.

## Planned stages and contract

Stages 3–4 implement customer/catalog management, quotations, subscription lifecycle, idempotent recurring billing, discounts and invoices; the Stitch frontend connects these operations. Later stages add payments, overdue balances and reports. The planned scale is approximately **5,000 subscriptions and 20,000+ invoices**, with paginated lists under **2 seconds**; these targets have not yet been benchmarked. Browser-test seed data is **synthetic**. No real credentials or personal data belong in the repository.

The frontend uses Next.js App Router, TypeScript, and Tailwind, integrating the exported Google Stitch designs. It supports real login, dashboard counts, subscription lists/details, draft creation, lifecycle actions, billing preview/execution, invoice lists/details and confirmation/cancellation. Payment controls remain explicitly unavailable.

See [requirements](docs/REQUIREMENTS.md), [financial decisions](docs/DECISIONS.md), and the [API contract](docs/API_CONTRACT.md). Stage 4 defines anchored periods, deferred paused charges, inclusive expiry with full final periods, auto-closure after billing, integer discount allocation, line-level exclusive tax, zero-write previews and atomic idempotent execution. Payment and reporting rules remain future work.

## Stage 3 commercial workflow

Use `/docs` and the [exact contracts and six example requests](docs/API_CONTRACT.md#stage-3-request-examples) to:

1. As admin, create a tax, product, priced variant, monthly plan, and quotation template.
2. Sign up a customer (creates a profile atomically), or POST `/api/v1/customers` as admin/staff with validated email/password and profile fields.
3. As admin/staff, POST `/api/v1/subscriptions` for a Draft, or `/api/v1/subscriptions/from-template` for a copied Quotation.
4. Follow **draft → quotation → confirmed → active → closed** with the corresponding action endpoints and an explicit `as_of` date. Draft-to-active jumps return 409. Confirmation freezes prices, taxes, plan flags, and terms; activation sets `next_invoice_date` to the original `start_date`, without generating an invoice.

Plan price is a separate recurring base charge; product lines are additional recurring charges. A line's unit price is sales price plus the selected variant's extra price, and amount is quantity × unit price, all using integers. Taxes are exclusive, with rates from 0–10,000 basis points (0–100%); Stage 4 computes line taxes after discounts when invoicing. Money inputs must be JSON integers in SQLite's signed 64-bit range; quantities are 1–1,000,000, with at most 100 lines in a new subscription/template. Overflow is rejected.

Plan validity dates are inclusive availability dates for **new sales**, not subscription end dates. Subscription expiry is independent. New Draft/Quotation selection and confirmation validate current catalog availability/minimum quantity. Confirmation captures the then-current pricing; later plan/product/variant/tax edits never change confirmed snapshots. Plan flags used by close/pause/renew are the accepted, snapshotted flags. `auto_close` is stored for future automation and does nothing automatically yet.

Admin configures the catalog; staff reads it and operates customers/subscriptions. Customers can list/read only their own profiles and subscriptions and update their own company/contact/phone fields. Only admin/staff can edit profile notes or run lifecycle actions. Other customers' record IDs return 404. No catalog hard-delete API exists; deactivate records instead. Template lines can be managed independently, and edits never propagate into earlier copied quotations.

Pause/resume require Active state and preserve the billing anchor/next invoice date. Pausing requires accepted `pausable=true`; closure requires `closable=true`. Renewal is Active-only, requires `renewable=true`, and extends expiry past both its prior value and `as_of`. Closed subscriptions cannot resume or renew. Missed paused periods, mid-period expiry, automatic closure, and billing catch-up policy must be finalized before billing implementation. No proration is introduced.

All lists use `limit` (20 by default, maximum 100) and `offset` (0 by default), deterministic ID ordering, and SQL counts. Subscription filters include customer, plan, product, status, and number search. Authentication retains its separate read session; commercial writes and credential-free audit events share an explicit write transaction.

## Stage 4 recurring billing demonstration

Migration `0004_financial` adds `discounts`, `invoices`, `invoice_lines`, and `discount_redemptions` with foreign keys, integer/check constraints, useful indexes, generated invoice numbers, permanent period uniqueness/overlap protection, sealed immutable lines/calculations, and atomic usage-counter triggers. Migrations 0001–0003 are unchanged. Apply upgrades explicitly; startup never migrates. No payment table or gateway is added.

From `backend/`, using the existing root virtual environment and configured `.env`:

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m alembic check
..\.venv\Scripts\subcadence-api.exe
```

In a second terminal from `frontend/`:

```powershell
npm ci
npm run dev
```

Open http://localhost:3000 and log in as an existing synthetic admin/staff. Create/select a customer, plan and product through the API/docs if needed; create a draft subscription in the UI, quote, confirm and activate it using valid explicit dates. Admins may optionally POST a discount in `/docs`:

```json
{"name":"Synthetic launch offer","discount_type":"percentage","scope":"subscription","rate_basis_points":1000,"minimum_purchase_paise":0,"minimum_quantity":1,"valid_from":"2026-01-01","valid_to":"2026-12-31","usage_limit":10,"active":true}
```

Open **Billing Center**, set an `as_of` on/after the subscription start, select **Preview dry run**, inspect periods/tax/discount totals, then **Execute billing → Confirm execution**. Open a generated invoice link (or **Invoices**) and select **Confirm invoice → Confirm now**. Re-preview/re-run the same date: no duplicate invoice or redemption is created. Customers see only their own invoices. Cancel preserves the period and discount usage; payment recording/PDF/email remain disabled.

For an entirely isolated synthetic demonstration and verification (never uses the ordinary database):

```powershell
# From backend/
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m compileall -q app alembic scripts tests
# From frontend/, with ports 3000 and 8766 free
npm run typecheck
npm run lint
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The browser suite migrates a temporary SQLite database and demonstrates the real backend/UI workflow. It shuts down its servers and deletes temporary data. Screenshots stay under ignored `frontend/test-results/screenshots/`. Detailed financial rules and response contracts are in `docs/DECISIONS.md` and `docs/API_CONTRACT.md`; no live/local developer database is changed by automated checks.

## Frontend development commands

Keep the backend running using the setup above. In a second terminal, with Node.js 22.13+ (22.x) or a supported newer LTS installed:

```powershell
cd frontend
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and sign in with an existing account. The frontend defaults to `http://127.0.0.1:8000/api/v1`; override `NEXT_PUBLIC_API_BASE_URL` in an ignored `frontend/.env.local` when needed. The default backend CORS setting already permits `http://localhost:3000`. JWTs stay in memory, so refreshing requires signing in again.

From `frontend/`, run `npm run typecheck`, `npm run lint`, `npm test`, and `npm run build`. For actual backend/browser integration tests, run `npx playwright install chromium` then `npm run test:e2e`; these start isolated synthetic fixtures, never the developer database. Full setup, connected endpoints, design decisions, limitations, and screenshot locations are in [frontend/README.md](frontend/README.md).
