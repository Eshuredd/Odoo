# SubCadence

A subscription management and recurring billing platform for the Odoo × Make-A-Ton hackathon. The planned workflow connects catalog configuration, quotations, subscription activation, recurring invoices, partial payments, reports, and customer self-service.

**Stages 1–3 are implemented:** backend foundation, authentication/RBAC/reset, SMTP/offline mail, customer profiles, taxes, products/variants, plans, quotation templates, and subscription lifecycle management. Recurring invoice generation, discounts, payments, reports, and the frontend remain deferred.

## Architecture and stack

FastAPI routes delegate persistence to SQLAlchemy 2.x services. Pydantic v2/pydantic-settings validate configuration and requests. Argon2id hashes passwords; PyJWT signs HS256 Bearer tokens; email-validator validates syntax without DNS. SQLite uses WAL, foreign keys, a 5-second busy timeout, and explicit transactions. Alembic owns schema changes. pytest/httpx tests use temporary databases. Python 3.11+ is required; Python 3.12 is used for local verification. No Docker, database server, paid APIs, or application-runtime internet access is required for offline operation.

The repository root is the `subcadence/` project root from the brief, even if the local checkout directory has a different name.

```text
.
├── backend/
│   ├── app/
│   │   ├── api/v1/         # Auth, customers, catalog, templates, subscriptions and health
│   │   ├── api/dependencies.py # Bearer auth and reusable role dependencies
│   │   ├── core/           # Settings, validation, principal, clock, JWT/password helpers
│   │   ├── db/             # Metadata, UTC type, engine and sessions
│   │   ├── models/         # Auth, customer and commercial typed ORM models
│   │   ├── schemas/        # Auth, customer/catalog/lifecycle inputs, outputs and pagination
│   │   ├── services/       # Auth, catalog, customer, lifecycle, audit and mailer logic
│   │   ├── static/swagger-ui/ # Vendored offline API docs assets and licenses
│   │   └── main.py         # App factory, lifespan, server entry point
│   ├── alembic/versions/   # 0001 foundation, 0002 authentication, 0003 commercial
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

Session-based services select `sqlite_begin_mode="IMMEDIATE"` on their connection before reading/writing reset state. This serializes concurrent redemption so only one consumer succeeds. Sensitive administrative writes recheck the principal after acquiring the lock. No billing engine is implemented.

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

Use offline Swagger at `/docs` to sign up and log in, then paste the returned access token into **Authorize**. To create staff, log in as the seeded admin and POST an email/password to `/users/staff`. Staff/customers receive 403, anonymous callers 401. Stage 3 customer profiles and subscriptions filter ownership in SQL using the authenticated User ID, before totals and pagination. Invoice ownership awaits its future model.

For local reset demonstration:

1. Leave SMTP fields empty and set `APP_ENV=development`.
2. POST `{"email":"<your synthetic account email>"}` to `/auth/password-reset/request`. Known/unknown/inactive accounts and SMTP failures get the same generic response.
3. Log in as the seeded admin and GET `/dev/email-outbox?limit=20&offset=0` with its Bearer token. Full email bodies contain the reset URL. The future frontend page does not exist yet; extract the `token` query value from the email.
4. POST `{"token":"<email token>","new_password":"<compliant new password>"}` to `/auth/password-reset/confirm`.
5. Log in using the new password. The old password and all old JWTs no longer work. Reused, replaced, or expired reset links fail.

Reset tokens contain 256 random bits, expire in 30 minutes, and are single use; issuing a replacement invalidates prior unused tokens. The reset table stores only SHA-256 digests. Password change, consumption, revocation, and audit commit atomically under `BEGIN IMMEDIATE`. Tests simulate expiry using an injectable UTC clock and exercise real concurrent SQLite consumers.

With SMTP configured, email uses standard-library SMTP and verified STARTTLS by default. Set SMTP_HOST, sender, and optional paired username/password. Credentials cannot be sent with STARTTLS disabled. Partial/invalid SMTP configuration fails delivery rather than falling back to the outbox. Public reset responses hide delivery errors; failed delivery rolls back token issuance/replacement. Tests mock SMTP and send no actual mail.

**The offline outbox is sensitive local demonstration data:** it stores usable reset links in full bodies and is designed for synthetic accounts. Only admins can retrieve it, and its route/OpenAPI entry are absent outside development. Authentication/outbox responses use `Cache-Control: no-store`. There is no retention/retry worker. SMTP acceptance cannot be atomically rolled back if a later DB commit fails; no production delivery guarantee is claimed.

The future Next.js client will keep access tokens in memory, use Bearer headers, reauthenticate after expiry/revocation, and invoke server-side logout before clearing local state. No cookie auth or frontend page has been built.

This hackathon auth implementation is not production-hardened: rate limiting, MFA, refresh rotation, uniform request timing, and operational security monitoring remain outside Stage 2.

## Planned stages and contract

Stage 3 adds customer/catalog management, quotation templates, and the subscription lifecycle. Later stages add idempotent recurring billing and discounts, invoices/payments/overdue tracking, reports, and frontend integration. The planned scale is approximately **5,000 subscriptions and 20,000+ invoices**, with paginated lists under **2 seconds**; these targets have not yet been benchmarked. Future demo/seed data is **synthetic**. No real credentials or personal data belong in the repository.

The frontend will use Next.js, TypeScript, and Tailwind, integrating exported Google Stitch designs. It will be implemented later; no frontend files are generated now.

See [requirements](docs/REQUIREMENTS.md), [decisions and unresolved rules](docs/DECISIONS.md), and the [planned API contract](docs/API_CONTRACT.md). Financial rules mandate INR integer paise, basis-point rates, half-up rounding, half-open billing periods, pricing snapshots, no proration, idempotency, no skipped periods, zero-write dry runs, and one transaction per subscription. Pause/expiration semantics and other detailed business rules remain explicitly unresolved.

## Stage 3 commercial workflow

Use `/docs` and the [exact contracts and six example requests](docs/API_CONTRACT.md#stage-3-request-examples) to:

1. As admin, create a tax, product, priced variant, monthly plan, and quotation template.
2. Sign up a customer (creates a profile atomically), or POST `/api/v1/customers` as admin/staff with validated email/password and profile fields.
3. As admin/staff, POST `/api/v1/subscriptions` for a Draft, or `/api/v1/subscriptions/from-template` for a copied Quotation.
4. Follow **draft → quotation → confirmed → active → closed** with the corresponding action endpoints and an explicit `as_of` date. Draft-to-active jumps return 409. Confirmation freezes prices, taxes, plan flags, and terms; activation sets `next_invoice_date` to the original `start_date`, without generating an invoice.

Plan price is a separate recurring base charge; product lines are additional recurring charges. A line's unit price is sales price plus the selected variant's extra price, and amount is quantity × unit price, all using integers. Taxes are exclusive, with rates from 0–10,000 basis points (0–100%); tax amounts and invoice totals are not calculated yet. Money inputs must be JSON integers in SQLite's signed 64-bit range; quantities are 1–1,000,000, with at most 100 lines in a new subscription/template. Overflow is rejected.

Plan validity dates are inclusive availability dates for **new sales**, not subscription end dates. Subscription expiry is independent. New Draft/Quotation selection and confirmation validate current catalog availability/minimum quantity. Confirmation captures the then-current pricing; later plan/product/variant/tax edits never change confirmed snapshots. Plan flags used by close/pause/renew are the accepted, snapshotted flags. `auto_close` is stored for future automation and does nothing automatically yet.

Admin configures the catalog; staff reads it and operates customers/subscriptions. Customers can list/read only their own profiles and subscriptions and update their own company/contact/phone fields. Only admin/staff can edit profile notes or run lifecycle actions. Other customers' record IDs return 404. No catalog hard-delete API exists; deactivate records instead. Template lines can be managed independently, and edits never propagate into earlier copied quotations.

Pause/resume require Active state and preserve the billing anchor/next invoice date. Pausing requires accepted `pausable=true`; closure requires `closable=true`. Renewal is Active-only, requires `renewable=true`, and extends expiry past both its prior value and `as_of`. Closed subscriptions cannot resume or renew. Missed paused periods, mid-period expiry, automatic closure, and billing catch-up policy must be finalized before billing implementation. No proration is introduced.

All lists use `limit` (20 by default, maximum 100) and `offset` (0 by default), deterministic ID ordering, and SQL counts. Subscription filters include customer, plan, product, status, and number search. Authentication retains its separate read session; commercial writes and credential-free audit events share an explicit write transaction.
