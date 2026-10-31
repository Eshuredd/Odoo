# REST API contract

Base path: `/api/v1`. Only `GET /api/v1/health` is implemented in Stage 1. The remaining entries are a planned resource structure, not available endpoints. Swagger UI is at `/docs`; OpenAPI is at `/openapi.json`.

## Implemented health endpoint

`GET /api/v1/health` is public and executes `SELECT 1` through a request-scoped database session. HTTP 200 response:

```json
{"status":"ok","service":"subcadence-api"}
```

Database access failures return HTTP 503 with `{"detail":"Database unavailable"}`. No database path, credentials, SQL error, or traceback appears in that response. This is a connectivity check, not a check that migrations have been applied.

## Planned resources

| Prefix | Responsibility | Expected access |
| --- | --- | --- |
| `/auth` | Signup, login, logout/session handling, current identity, password reset | Public entry points with credential validation; authenticated session operations; no privileged self-registration |
| `/users` | Accounts, activation, role administration | Admin; self-profile operations explicitly scoped later; only admin creates staff |
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
- Preserve FastAPI's `{"detail": ...}` error envelope. General errors use a safe string; request validation uses FastAPI's standard structured detail list. Expected statuses: 401 for missing/invalid credentials, 403 for disallowed operations, 404 for absent or inaccessible customer-owned objects, 409 for uniqueness or state conflicts, 422 for invalid input, and 503 for database unavailability. No stack traces or sensitive database details in public responses. Authentication-specific headers/cookies remain Stage 2 decisions.
- Customer ownership is enforced server-side on every record, relationship, list, report, and export. A guessed ID must not reveal another customer's records. Admin/staff access is separately authorized; being authenticated is insufficient.
- Idempotent billing and invoice period uniqueness are mandatory. Per-subscription transaction boundaries cover invoice persistence, discount redemption, and next billing date. Dry-run persists nothing. Payment retries and any general idempotency-key convention need a later explicit contract.

These future conventions are documentation only; Stage 1 adds no placeholder business routes.
