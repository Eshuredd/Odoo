# REST API contract

Base path: `/api/v1`. Stage 2 implements health, authentication, admin-created staff, and the development email outbox. Other business resources remain planned. Swagger UI is at `/docs`; OpenAPI is at `/openapi.json`. Documentation assets are served locally.

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
| `/customers` | Business customer profiles and account linkage | Admin/staff manage; customer reads own profile |
| `/products` | Products and sellable variants | Admin manages; staff reads; customer visibility restricted to permitted catalog/self-service views |
| `/taxes` | Exclusive tax configuration in basis points | Admin manages; staff reads |
| `/plans` | Billing intervals, base charges, flags | Admin manages; staff reads; customer views permitted plans |
| `/quotation-templates` | Reusable quote defaults, lines, and terms | Admin manages; staff uses/reads |
| `/subscriptions` | Quotations, snapshots, authorized lifecycle transitions | Admin/staff perform explicitly granted actions; customer reads own records |
| `/discounts` | Rule eligibility, validity, redemption limits | Admin creates/manages; staff may view operational eligibility; no unrestricted customer rule access |
| `/invoices` | Issued invoices, line snapshots, balances, overdue views | Admin/staff read operational records; customer reads own; generation through billing |
| `/payments` | Positive partial/full payment recording and allocations | Admin/staff record/read; customer reads own; no gateway |
| `/reports` | Financial summaries, aging, recurring charges, lifecycle analytics | Admin and appropriately scoped staff; any customer summary limited to own data |
| `/billing` | Explicit `as_of` billing runs, dry-run, run results | Admin or explicitly authorized staff/system invocation; never customers |

Detailed HTTP methods, actions, schemas, and permissions will be specified with each implementation stage. Transition endpoints must validate current state and authority. Automated billing must use the same rules as manual invocation.

## Shared planned conventions

- JSON bodies; IDs are stable integers unless a resource explicitly defines otherwise. Monetary fields are named with `_paise`, use integers, and represent INR. Rates use `_basis_points`. Timestamps use ISO 8601 UTC (`Z` or `+00:00`); billing dates use `YYYY-MM-DD`.
- Lists use `limit` (default 20, range 1–100) and `offset` (default 0, nonnegative). Return `{"items": [], "total": 0, "limit": 20, "offset": 0}`. Use deterministic ordering with an ID tie-breaker. Apply authorization/ownership filters before both counting and pagination. Later billing and reports may use dedicated bounded result schemas.
- Preserve FastAPI's `{"detail": ...}` error envelope. General errors use a safe string; validation returns a list with `type`, `loc`, and `msg`, omitting submitted inputs/context to protect credentials and tokens. Expected statuses: 400 for invalid reset tokens, 401 for missing/invalid credentials, 403 for disallowed operations, 404 for absent/inaccessible resources, 409 for uniqueness or state conflicts, 422 for invalid input, and 503 for database/auth-configuration unavailability. No stack traces, SMTP details, or sensitive database details in public responses.
- Customer ownership is enforced server-side on every record, relationship, list, report, and export. A guessed ID must not reveal another customer's records. Admin/staff access is separately authorized; being authenticated is insufficient.
- Idempotent billing and invoice period uniqueness are mandatory. Per-subscription transaction boundaries cover invoice persistence, discount redemption, and next billing date. Dry-run persists nothing. Payment retries and any general idempotency-key convention need a later explicit contract.

Future business-resource conventions remain documentation only; Stage 2 adds no placeholder business routes or ownership models.
